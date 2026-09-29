#!/usr/bin/env python3
"""MCP + GitLab webhook boundary for autonomous merge-request review.

The server owns transport and normalization only. Review intelligence remains
behind REVIEW_COMMAND so the existing review implementation can be migrated
without duplicating it here.

Default mode speaks MCP JSON-RPC over stdin/stdout.
Use --http to expose POST /webhooks/gitlab for GitLab merge-request events.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import shlex
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from contract import ReviewRequest, ReviewResult


def normalize_gitlab_event(payload: dict[str, Any]) -> ReviewRequest:
    attrs = payload.get("object_attributes")
    project = payload.get("project")
    user = payload.get("user") or {}
    if not isinstance(attrs, dict) or not isinstance(project, dict):
        raise ValueError("GitLab merge request event requires object_attributes and project objects")

    repository = project.get("path_with_namespace")
    iid = attrs.get("iid")
    title = attrs.get("title")
    source_branch = attrs.get("source_branch")
    target_branch = attrs.get("target_branch")
    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("GitLab event requires project.path_with_namespace")
    if not isinstance(iid, int) or isinstance(iid, bool) or iid < 1:
        raise ValueError("GitLab event requires a positive integer object_attributes.iid")
    for name, value in (("title", title), ("source_branch", source_branch), ("target_branch", target_branch)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"GitLab event requires object_attributes.{name}")
    action = str(attrs.get("action") or attrs.get("state") or "open")

    return ReviewRequest(
        request_id=f"mr_review_{uuid.uuid4().hex[:12]}",
        platform="gitlab",
        repository=repository,
        merge_request_id=iid,
        title=title,
        author=str(user.get("username") or user.get("name") or ""),
        source_branch=source_branch,
        target_branch=target_branch,
        source_url=str(attrs.get("url") or project.get("web_url") or ""),
        action=action,
        metadata={
            "event": "merge_request",
            "project_id": project.get("id"),
            "object_kind": payload.get("object_kind"),
        },
    )


def run_review(request: ReviewRequest) -> ReviewResult:
    command = os.environ.get("REVIEW_COMMAND")
    if not command:
        raise RuntimeError(
            "REVIEW_COMMAND is not configured; refusing to pretend the review engine exists"
        )

    completed = subprocess.run(
        shlex.split(command),
        input=json.dumps(request.to_dict()),
        text=True,
        capture_output=True,
        timeout=int(os.environ.get("REVIEW_TIMEOUT_SECONDS", "900")),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or f"review command exited {completed.returncode}"
        )

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("review command returned invalid JSON") from exc
    return ReviewResult.from_dict(result, expected_request_id=request.request_id)


def tool_list() -> list[dict[str, Any]]:
    return [{
        "name": "review_merge_request",
        "description": "Submit a normalized merge request to the configured review engine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "platform": {"type": "string", "enum": ["gitlab", "github", "bitbucket"]},
                "repository": {"type": "string"},
                "merge_request_id": {"type": "integer", "minimum": 1},
                "title": {"type": "string"},
                "author": {"type": "string"},
                "source_branch": {"type": "string"},
                "target_branch": {"type": "string"},
                "source_url": {"type": "string"},
                "action": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": [
                "request_id", "platform", "repository", "merge_request_id",
                "title", "author", "source_branch", "target_branch",
            ],
        },
    }]


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": request.get("params", {}).get(
                    "protocolVersion", "2024-11-05"
                ),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "claude-ensemble-pr-review", "version": "0.1"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_list()}}
    if method == "tools/call":
        params = request.get("params", {})
        if params.get("name") != "review_merge_request":
            return {
                "jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32602, "message": "unknown tool"},
            }
        try:
            review_request = ReviewRequest.from_dict(params.get("arguments", {}))
            result = run_review(review_request)
            return {
                "jsonrpc": "2.0", "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result.to_dict())}]
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }

    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0", "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


class GitLabWebhookHandler(BaseHTTPRequestHandler):
    server_version = "claude-ensemble-pr-review/0.1"

    def do_POST(self) -> None:
        if self.path != "/webhooks/gitlab":
            self.send_error(404)
            return

        secret = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
        token = self.headers.get("X-Gitlab-Token", "")
        if secret and not hmac.compare_digest(token, secret):
            self.send_error(401)
            return

        try:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._json(400, {"status": "error", "message": "invalid Content-Length"})
                return
            length = int(raw_length)
            if length < 0:
                self._json(400, {"status": "error", "message": "invalid Content-Length"})
                return
            if length > 2_000_000:
                self.send_error(413)
                return

            payload = json.loads(self.rfile.read(length))
            if payload.get("object_kind") != "merge_request":
                self._json(202, {"status": "ignored", "reason": "not a merge request"})
                return
            request = normalize_gitlab_event(payload)
            result = run_review(request)
            self._json(200, result.to_dict())
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"status": "error", "message": str(exc)})
        except Exception as exc:
            self._json(500, {"status": "error", "message": str(exc)})

    def _json(self, status: int, value: dict[str, Any]) -> None:
        encoded = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        print(format % args, file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--host", default=os.environ.get("REVIEW_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("REVIEW_PORT", "8787")))
    args = parser.parse_args()

    if args.http:
        server = ThreadingHTTPServer((args.host, args.port), GitLabWebhookHandler)
        print(f"GitLab webhook endpoint listening on {args.host}:{args.port}", file=sys.stderr)
        server.serve_forever()
        return

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError as exc:
            print(json.dumps({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }), flush=True)


if __name__ == "__main__":
    main()
