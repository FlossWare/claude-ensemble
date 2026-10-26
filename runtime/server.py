"""Local REST dispatcher for the first Claude Ensemble service."""
from __future__ import annotations

import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .chunking import (
    MAX_CONTENT_BYTES, ChunkingError, Policy, chunk_document, chunk_spans, validate_index_profile,
)

REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SOURCE_ID = re.compile(r"^(memory|knowledge):[A-Za-z0-9._~-]{1,128}$")
MAX_REQUEST_BYTES = 300_000
MAX_PROFILE_REQUEST_BYTES = 2_097_152
SUPPORTED_PROFILES = {"markdown-default": {"0.1"}, "plain-text-default": {"0.1"}}


def _error(code: str, message: str, retryable: bool = False,
           details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message[:1024],
            "retryable": retryable,
            "details": details or {},
        }
    }


def _require_object(value: Any, name: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ChunkingError("invalid_request", f"{name} must be an object", status=400)
    missing = required - set(value)
    unknown = set(value) - allowed
    if missing or unknown:
        details = {}
        if missing:
            details["missing_fields"] = sorted(missing)
        if unknown:
            details["unknown_fields"] = sorted(unknown)
        raise ChunkingError("invalid_request", f"{name} has missing or unknown fields", status=400, details=details)
    return value


class Handler(BaseHTTPRequestHandler):
    server_version = "ClaudeEnsemble/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Avoid default access logs that can accidentally expose sensitive request data.
        return

    def _request_id(self) -> tuple[str, bool]:
        supplied = self.headers.get("X-CE-Request-ID")
        if supplied is None:
            return str(uuid.uuid4()), False
        if REQUEST_ID.fullmatch(supplied):
            return supplied, False
        return str(uuid.uuid4()), True

    def _send(self, status: int, body: dict[str, Any], request_id: str) -> None:
        body.setdefault("request_id", request_id)
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-CE-Request-ID", request_id)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnects are not application failures and cannot be retried here.
            return

    def _fail(self, exc: ChunkingError, request_id: str) -> None:
        self._send(exc.status, _error(exc.code, str(exc), details=exc.details), request_id)

    def do_GET(self) -> None:
        request_id, invalid_id = self._request_id()
        if invalid_id:
            self._send(400, _error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length"), request_id)
        elif self.path == "/api/v1/chunking/health":
            self._send(200, {"service": "chunking", "status": "alive"}, request_id)
        elif self.path == "/api/v1/chunking/ready":
            self._send(200, {
                "service": "chunking",
                "status": "ready",
                "ready": True,
                "checks": [{"name": "chunking_engine", "status": "ok"},
                          {"name": "markdown-default@0.1", "status": "ok"},
                          {"name": "plain-text-default@0.1", "status": "ok"}],
            }, request_id)
        else:
            self._send(404, _error("endpoint_not_found", "endpoint not found"), request_id)

    def do_POST(self) -> None:
        request_id, invalid_id = self._request_id()
        if invalid_id:
            self._send(400, _error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length"), request_id)
            return
        if self.path not in ("/api/v1/chunking/chunks", "/api/v1/chunking/preflight"):
            self._send(404, _error("endpoint_not_found", "endpoint not found"), request_id)
            return
        if self.headers.get_content_type() != "application/json":
            self._send(415, _error("unsupported_media_type", "Content-Type must be application/json"), request_id)
            return
        try:
            length_text = self.headers.get("Content-Length")
            if length_text is None or not length_text.isdecimal():
                raise ChunkingError("invalid_request", "a valid Content-Length is required", status=400)
            length = int(length_text)
            limit = MAX_REQUEST_BYTES if self.path.endswith("/chunks") else MAX_PROFILE_REQUEST_BYTES
            if length > limit:
                raise ChunkingError("request_too_large", "request exceeds configured byte limit", status=413)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ChunkingError("invalid_request", "request body ended before Content-Length bytes were read", status=400)
            try:
                request = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ChunkingError("invalid_request", "request body must be valid UTF-8 JSON", status=400) from exc
            if self.path.endswith("/preflight"):
                response = self._preflight(request)
            else:
                response = self._chunks(request)
            self._send(200, response, request_id)
        except ChunkingError as exc:
            self._fail(exc, request_id)
        except Exception:
            self._send(500, _error("internal_error", "request could not be processed"), request_id)

    def _chunks(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "source", "policy", "options"},
            {"index_profile", "source", "policy"})
        profile = validate_index_profile(request["index_profile"])
        source = _require_object(request["source"], "source",
            {"source_id", "revision", "revision_sequence", "media_type", "content"},
            {"source_id", "revision", "revision_sequence", "content"})
        if not isinstance(source["source_id"], str) or not SOURCE_ID.fullmatch(source["source_id"]):
            raise ChunkingError("invalid_parameter", "source.source_id is invalid", status=400)
        if "media_type" in source and (not isinstance(source["media_type"], str) or len(source["media_type"]) > 128):
            raise ChunkingError("invalid_parameter", "source.media_type is invalid", status=400)
        policy = Policy.from_dict(request["policy"])
        if policy.profile not in SUPPORTED_PROFILES or policy.profile_version not in SUPPORTED_PROFILES[policy.profile]:
            raise ChunkingError("unsupported_profile", "chunking profile or version is not configured")
        options = _require_object(request.get("options", {}), "options",
            {"include_text", "include_line_spans"}, set())
        include_text = options.get("include_text", True)
        include_line_spans = options.get("include_line_spans", True)
        if type(include_text) is not bool or type(include_line_spans) is not bool:
            raise ChunkingError("invalid_parameter", "options.include_text and options.include_line_spans must be booleans", status=400)
        result = chunk_document(
            source_id=source["source_id"],
            revision=source["revision"],
            revision_sequence=source["revision_sequence"],
            content=source["content"],
            index_profile=profile,
            policy=policy,
            include_text=include_text,
            include_line_spans=include_line_spans,
        )
        if len(result["chunks"]) > 256:
            raise ChunkingError("source_too_large", "source requires more than 256 chunks")
        return result

    def _preflight(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "source_text", "chunking_profile", "profile_bundle"},
            {"index_profile", "source_text", "chunking_profile", "profile_bundle"})
        identity = validate_index_profile(request["index_profile"])
        source_text = request["source_text"]
        if not isinstance(source_text, str) or not source_text:
            raise ChunkingError("invalid_parameter", "source_text must be a non-empty string", status=400)
        source_bytes = len(source_text.encode("utf-8"))
        if source_bytes > MAX_CONTENT_BYTES:
            raise ChunkingError("source_too_large", "source_text exceeds 262144 UTF-8 bytes")

        bundle = request["profile_bundle"]
        if not isinstance(bundle, dict):
            raise ChunkingError("invalid_request", "profile_bundle must be an object", status=400)
        required_bundle = {"name", "version", "status", "chunking", "tokenization", "lexical", "embedding", "limits", "digest"}
        if set(bundle) != required_bundle:
            raise ChunkingError("invalid_request", "profile_bundle does not match the Index profile bundle shape", status=400)
        if any(bundle.get(k) != identity[k] for k in ("name", "version", "digest")):
            raise ChunkingError("profile_digest_mismatch", "index_profile identity does not match profile_bundle")
        if bundle.get("status") == "retired":
            raise ChunkingError("unsupported_profile", "retired Index profile bundles cannot be used for ingestion")
        chunking = bundle.get("chunking")
        requested = _require_object(request["chunking_profile"], "chunking_profile",
            {"profile", "version", "max_units", "overlap_units"},
            {"profile", "version", "max_units", "overlap_units"})
        if not isinstance(chunking, dict) or any(requested.get(k) != chunking.get(k) for k in ("profile", "version", "max_units")):
            raise ChunkingError("profile_mismatch", "chunking_profile does not match the pinned Index profile bundle")
        policy = Policy.from_dict({
            "profile": requested["profile"],
            "profile_version": requested["version"],
            "max_units": requested["max_units"],
            "overlap_units": requested["overlap_units"],
            "unit": "unicode_code_points",
        })
        if policy.profile not in SUPPORTED_PROFILES or policy.profile_version not in SUPPORTED_PROFILES[policy.profile]:
            raise ChunkingError("unsupported_profile", "chunking profile or version is not configured")
        limits = bundle.get("limits")
        if not isinstance(limits, dict):
            raise ChunkingError("invalid_request", "profile_bundle.limits must be an object", status=400)
        limit_keys = {
            "max_chunks", "max_source_bytes", "max_chunk_text_bytes", "max_request_bytes",
            "max_chunk_representation_bytes", "max_envelope_bytes", "max_metadata_bytes",
            "max_lexical_terms_per_chunk", "max_lexical_term_bytes",
        }
        if (not limit_keys.issubset(limits)
                or any(type(limits[k]) is not int or limits[k] < (0 if k == "max_metadata_bytes" else 1)
                       for k in limit_keys)):
            raise ChunkingError("invalid_request", "profile_bundle.limits is incomplete or invalid", status=400)
        if bundle.get("status") not in {"active", "deprecated", "retired"}:
            raise ChunkingError("invalid_request", "profile_bundle.status is invalid", status=400)
        spans = chunk_spans(source_text, policy, max_chunks=MAX_CONTENT_BYTES)
        chunk_count = len(spans)
        max_text_bytes = max(len(source_text[start:end].encode("utf-8")) for start, end in spans)
        upper_bound = chunk_count * limits["max_chunk_representation_bytes"] + limits["max_envelope_bytes"]
        fits = (
            source_bytes <= limits["max_source_bytes"]
            and chunk_count <= limits["max_chunks"]
            and max_text_bytes <= limits["max_chunk_text_bytes"]
            and upper_bound <= limits["max_request_bytes"]
        )
        return {
            "chunk_count": chunk_count,
            "max_chunk_text_bytes": max_text_bytes,
            "estimated_representation_bytes_upper_bound": upper_bound,
            "max_request_bytes": limits["max_request_bytes"],
            "fits_profile": fits,
            "chunking_profile": {"profile": policy.profile, "version": policy.profile_version},
        }


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
