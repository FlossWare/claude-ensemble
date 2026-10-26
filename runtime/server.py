"""Minimal local REST dispatcher for the first Claude Ensemble service."""
from __future__ import annotations

import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .chunking import ChunkingError, Policy, chunk_document

REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
MAX_REQUEST_BYTES = 300_000


def _error(code: str, message: str, request_id: str, retryable: bool = False) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "retryable": retryable, "request_id": request_id}}


class Handler(BaseHTTPRequestHandler):
    server_version = "ClaudeEnsemble/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Avoid default access logs that can accidentally grow to include sensitive URLs.
        return

    def _request_id(self) -> str:
        supplied = self.headers.get("X-CE-Request-ID", "")
        return supplied if REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())

    def _send(self, status: int, body: dict[str, Any], request_id: str) -> None:
        body.setdefault("request_id", request_id)
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-CE-Request-ID", request_id)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        request_id = self._request_id()
        if self.path == "/api/v1/chunking/health":
            self._send(200, {"status": "ok"}, request_id)
        elif self.path == "/api/v1/chunking/ready":
            self._send(200, {"status": "ready", "profiles": ["markdown-default", "plain-text-default"]}, request_id)
        else:
            self._send(404, _error("not_found", "endpoint not found", request_id), request_id)

    def do_POST(self) -> None:
        request_id = self._request_id()
        if self.path != "/api/v1/chunking/chunks":
            self._send(404, _error("not_found", "endpoint not found", request_id), request_id)
            return
        if self.headers.get_content_type() != "application/json":
            self._send(415, _error("unsupported_media_type", "Content-Type must be application/json", request_id), request_id)
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0:
            self._send(400, _error("invalid_content_length", "Content-Length is required", request_id), request_id)
            return
        if length > MAX_REQUEST_BYTES:
            self._send(413, _error("request_too_large", "request exceeds configured byte limit", request_id), request_id)
            return
        try:
            raw = self.rfile.read(length)
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ChunkingError("request body must be a JSON object")
            source = request.get("source")
            if not isinstance(source, dict):
                raise ChunkingError("source must be an object")
            policy = Policy.from_dict(request.get("policy"))
            options = request.get("options") or {}
            if not isinstance(options, dict):
                raise ChunkingError("options must be an object")
            response = chunk_document(
                source_id=source.get("source_id", ""),
                revision=source.get("revision", ""),
                revision_sequence=source.get("revision_sequence"),
                content=source.get("content", ""),
                index_profile=request.get("index_profile", {}), policy=policy,
                include_text=options.get("include_text", True),
                include_line_spans=options.get("include_line_spans", True),
            )
            response["request_id"] = request_id
            self._send(200, response, request_id)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, _error("malformed_json", "request body must be valid UTF-8 JSON", request_id), request_id)
        except ChunkingError as exc:
            self._send(422, _error("invalid_request", str(exc), request_id), request_id)
        except Exception:
            self._send(500, _error("internal_error", "request could not be processed", request_id, True), request_id)


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
