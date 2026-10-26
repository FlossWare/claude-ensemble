"""Local REST dispatcher for the first Claude Ensemble service."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .chunking import (
    MAX_CONTENT_BYTES, MAX_CHUNKS, DEFAULT_POLICY, ChunkingError, Policy, chunk_document, chunk_spans, validate_index_profile,
)

REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SOURCE_ID = re.compile(r"^(memory|knowledge):[A-Za-z0-9._~-]{1,128}$")
MAX_REQUEST_BYTES = 300_000
MAX_PROFILE_REQUEST_BYTES = 2_097_152
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
SUPPORTED_PROFILES = {"markdown-default": {"0.1"}, "plain-text-default": {"0.1"}}


def _profile_digest(bundle: dict[str, Any]) -> str:
    # Index profile schema values are JSON primitives; sorted compact UTF-8 JSON
    # is RFC 8785-equivalent for this schema (which excludes floating-point values).
    covered = {k: v for k, v in bundle.items() if k not in {"digest", "status"}}
    canonical = json.dumps(covered, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    import hashlib
    return hashlib.sha256(canonical).hexdigest()


def _validate_profile_bundle(bundle: Any) -> dict[str, Any]:
    """Validate the full Index profile shape and its cross-field size invariants."""
    if not isinstance(bundle, dict):
        raise ChunkingError("invalid_request", "profile_bundle must be an object", status=400)
    required = {"name", "version", "status", "chunking", "tokenization", "lexical",
                "embedding", "limits", "digest"}
    if set(bundle) != required:
        raise ChunkingError("invalid_request", "profile_bundle has missing or unknown fields", status=400)
    def obj(name: str, keys: set[str]) -> dict[str, Any]:
        value = bundle[name]
        if not isinstance(value, dict) or set(value) != keys:
            raise ChunkingError("invalid_request", f"profile_bundle.{name} has missing, unknown, or invalid fields", status=400)
        return value
    def string(value: Any, maximum: int, field: str) -> None:
        if not isinstance(value, str) or not 1 <= len(value) <= maximum:
            raise ChunkingError("invalid_request", f"profile_bundle.{field} is invalid", status=400)
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ChunkingError("invalid_request", f"profile_bundle.{field} contains invalid Unicode", status=400) from exc
    string(bundle["name"], 128, "name")
    string(bundle["version"], 64, "version")
    if not isinstance(bundle["status"], str) or bundle["status"] not in {"active", "deprecated", "retired"}:
        raise ChunkingError("invalid_request", "profile_bundle.status is invalid", status=400)
    chunking = obj("chunking", {"profile", "version", "max_units"})
    string(chunking["profile"], 128, "chunking.profile")
    string(chunking["version"], 64, "chunking.version")
    if type(chunking["max_units"]) is not int or not 1 <= chunking["max_units"] <= 65536:
        raise ChunkingError("invalid_request", "profile_bundle.chunking.max_units is invalid", status=400)
    tokenization = obj("tokenization", {"profile", "version"})
    string(tokenization["profile"], 128, "tokenization.profile")
    string(tokenization["version"], 64, "tokenization.version")
    lexical = obj("lexical", {"profile", "version", "statistics_policy"})
    string(lexical["profile"], 128, "lexical.profile")
    string(lexical["version"], 64, "lexical.version")
    if not isinstance(lexical["statistics_policy"], str) or lexical["statistics_policy"] not in {"scope_partition", "isolated_corpus"}:
        raise ChunkingError("invalid_request", "profile_bundle.lexical.statistics_policy is invalid", status=400)
    embedding = obj("embedding", {"required", "profile", "version", "model", "model_version",
                                  "input_types", "dimensions", "normalization", "metric", "max_input_tokens"})
    if type(embedding["required"]) is not bool:
        raise ChunkingError("invalid_request", "profile_bundle.embedding.required is invalid", status=400)
    for key, maximum in (("profile",128),("version",64),("model",256),("model_version",128)):
        string(embedding[key], maximum, "embedding."+key)
    if (not isinstance(embedding["input_types"], list) or not 1 <= len(embedding["input_types"]) <= 2
            or any(not isinstance(v, str) or v not in {"query", "document"} for v in embedding["input_types"])
            or len(set(embedding["input_types"])) != len(embedding["input_types"])):
        raise ChunkingError("invalid_request", "profile_bundle.embedding.input_types is invalid", status=400)
    if type(embedding["dimensions"]) is not int or not 1 <= embedding["dimensions"] <= 4096:
        raise ChunkingError("invalid_request", "profile_bundle.embedding.dimensions is invalid", status=400)
    if (not isinstance(embedding["normalization"], str) or embedding["normalization"] not in {"none", "l2"}
            or not isinstance(embedding["metric"], str) or embedding["metric"] not in {"cosine", "dot_product", "euclidean"}):
        raise ChunkingError("invalid_request", "profile_bundle.embedding normalization or metric is invalid", status=400)
    if type(embedding["max_input_tokens"]) is not int or not 1 <= embedding["max_input_tokens"] <= 1_000_000:
        raise ChunkingError("invalid_request", "profile_bundle.embedding.max_input_tokens is invalid", status=400)
    limits = obj("limits", {"max_chunks", "max_source_bytes", "max_chunk_text_bytes", "max_request_bytes",
                            "max_chunk_representation_bytes", "max_envelope_bytes", "max_metadata_bytes",
                            "max_lexical_terms_per_chunk", "max_lexical_term_bytes"})
    bounds = {
        "max_chunks": (1, 256), "max_source_bytes": (1, 262144),
        "max_chunk_text_bytes": (1, 65536), "max_request_bytes": (1024, 2097152),
        "max_chunk_representation_bytes": (256, 1048576), "max_envelope_bytes": (1024, 131072),
        "max_metadata_bytes": (0, 8192), "max_lexical_terms_per_chunk": (1, 512),
        "max_lexical_term_bytes": (1, 128),
    }
    for key, (minimum, maximum) in bounds.items():
        value = limits[key]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ChunkingError("invalid_request", f"profile_bundle.limits.{key} is invalid", status=400)
    if limits["max_chunks"] * limits["max_chunk_representation_bytes"] + limits["max_envelope_bytes"] > limits["max_request_bytes"]:
        raise ChunkingError("invalid_request", "profile_bundle limits violate the complete request-size bound", status=400)
    representation_minimum = (6 * limits["max_chunk_text_bytes"] + 2
        + (25 * embedding["dimensions"] + 2 if embedding["required"] else 0)
        + limits["max_lexical_terms_per_chunk"] * (6 * limits["max_lexical_term_bytes"] + 4)
        + limits["max_metadata_bytes"] + 1024)
    if limits["max_chunk_representation_bytes"] < representation_minimum:
        raise ChunkingError("invalid_request", "profile_bundle limits violate the conservative representation-size bound", status=400)
    digest = bundle["digest"]
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
        raise ChunkingError("invalid_request", "profile_bundle.digest is invalid", status=400)
    if _profile_digest(bundle).lower() != digest.lower():
        raise ChunkingError("profile_digest_mismatch", "profile_bundle content does not match its digest", status=409)
    return bundle


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


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _validate_json_unicode(value: Any) -> None:
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ChunkingError("invalid_request", "request contains invalid Unicode scalar values", status=400) from exc
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_json_unicode(key)
            _validate_json_unicode(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json_unicode(item)


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
    timeout = 5.0

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(self.timeout)

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
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnects are not application failures and cannot be retried here.
            return

    def _fail(self, exc: ChunkingError, request_id: str) -> None:
        self._send(exc.status, _error(exc.code, str(exc), details=exc.details), request_id)

    def _deadline_error(self) -> ChunkingError | None:
        # Establish one monotonic absolute deadline per request. Caller deadlines
        # may shorten, but never extend, the local default request budget.
        if not hasattr(self, "_request_deadline_monotonic"):
            supplied = self.headers.get("X-CE-Deadline")
            now_mono = time.monotonic()
            if supplied is None:
                self._request_deadline_monotonic = now_mono + DEFAULT_REQUEST_TIMEOUT_SECONDS
            else:
                try:
                    if not supplied.endswith("Z"):
                        raise ValueError("deadline must be UTC and end in Z")
                    deadline = datetime.fromisoformat(supplied[:-1] + "+00:00")
                    if deadline.tzinfo != timezone.utc:
                        raise ValueError("deadline must be UTC")
                except (ValueError, TypeError):
                    return ChunkingError("invalid_parameter", "X-CE-Deadline must be an RFC 3339 UTC timestamp ending in Z", status=400)
                remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    return ChunkingError("deadline_exceeded", "request deadline has expired", status=504, details={"retry_after_deadline": False})
                self._request_deadline_monotonic = now_mono + min(remaining, DEFAULT_REQUEST_TIMEOUT_SECONDS)
        if time.monotonic() >= self._request_deadline_monotonic:
            return ChunkingError("deadline_exceeded", "request deadline has expired", status=504, details={"retry_after_deadline": False})
        return None

    def _check_deadline(self) -> None:
        error = self._deadline_error()
        if error is not None:
            raise error

    def _read_body(self, length: int) -> bytes:
        """Read with a monotonic total deadline, even when the peer trickles bytes."""
        body = bytearray()
        while len(body) < length:
            if (error := self._deadline_error()) is not None:
                raise error
            remaining = self._request_deadline_monotonic - time.monotonic()
            self.connection.settimeout(max(0.001, min(self.timeout, remaining)))
            # read1 performs at most one underlying read, allowing us to refresh
            # the remaining budget between trickled packets.
            part = self.rfile.read1(min(8192, length - len(body)))
            if not part:
                raise ChunkingError("invalid_request", "request body ended before Content-Length bytes were read", status=400)
            body.extend(part)
        return bytes(body)

    def _method_not_allowed(self) -> None:
        request_id, invalid_id = self._request_id()
        self.close_connection = True
        if invalid_id:
            self._send(400, _error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length"), request_id)
        else:
            self._send(405, _error("method_not_allowed", "HTTP method is not supported"), request_id)

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    def do_TRACE(self) -> None:
        self._method_not_allowed()

    def do_CONNECT(self) -> None:
        self._method_not_allowed()

    def do_GET(self) -> None:
        request_id, invalid_id = self._request_id()
        if invalid_id:
            self._send(400, _error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length"), request_id)
        elif (deadline_error := self._deadline_error()) is not None:
            self._fail(deadline_error, request_id)
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
        deadline_error = self._deadline_error()
        if deadline_error is not None:
            self._fail(deadline_error, request_id)
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
                # Do not drain an attacker-controlled body just to preserve keep-alive.
                # Explicitly close after the bounded 413 response; unread bytes must not
                # be interpreted as another request on this connection.
                self.close_connection = True
                raise ChunkingError("request_too_large", "request exceeds configured byte limit", status=413)
            raw = self._read_body(length)
            try:
                request = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ChunkingError("invalid_request", "request body must be valid UTF-8 JSON without duplicate object keys", status=400) from exc
            _validate_json_unicode(request)
            if self.path.endswith("/preflight"):
                response = self._preflight(request)
            else:
                response = self._chunks(request)
            if (deadline_error := self._deadline_error()) is not None:
                self._fail(deadline_error, request_id)
                return
            self._send(200, response, request_id)
        except TimeoutError:
            deadline_error = self._deadline_error()
            if deadline_error is not None:
                self._fail(deadline_error, request_id)
            else:
                self._send(408, _error("request_timeout", "request body was not received before the socket timeout"), request_id)
        except ChunkingError as exc:
            self._fail(exc, request_id)
        except Exception:
            self._send(500, _error("internal_error", "request could not be processed"), request_id)

    def _chunks(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "source", "policy", "options"},
            {"index_profile", "source"})
        if "request_id" in request and (not isinstance(request["request_id"], str)
                or not 1 <= len(request["request_id"]) <= 128):
            raise ChunkingError("invalid_request", "request.request_id must be a string of 1 to 128 characters", status=400)
        profile = validate_index_profile(request["index_profile"])
        source = _require_object(request["source"], "source",
            {"source_id", "revision", "revision_sequence", "media_type", "content"},
            {"source_id", "revision", "revision_sequence", "content"})
        if not isinstance(source["source_id"], str) or not SOURCE_ID.fullmatch(source["source_id"]):
            raise ChunkingError("invalid_parameter", "source.source_id is invalid", status=400)
        if "media_type" in source and (not isinstance(source["media_type"], str) or len(source["media_type"]) > 128):
            raise ChunkingError("invalid_parameter", "source.media_type is invalid", status=400)
        policy = Policy.from_dict(request["policy"]) if "policy" in request else DEFAULT_POLICY
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
            deadline_check=self._check_deadline,
        )
        if len(result["chunks"]) > 256:
            raise ChunkingError("source_too_large", "source requires more than 256 chunks")
        return result

    def _preflight(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "source_text", "chunking_profile", "profile_bundle"},
            {"index_profile", "source_text", "chunking_profile", "profile_bundle"})
        if "request_id" in request and (not isinstance(request["request_id"], str)
                or not 1 <= len(request["request_id"]) <= 128):
            raise ChunkingError("invalid_request", "request.request_id must be a string of 1 to 128 characters", status=400)
        identity = validate_index_profile(request["index_profile"])
        source_text = request["source_text"]
        if not isinstance(source_text, str) or not source_text:
            raise ChunkingError("invalid_parameter", "source_text must be a non-empty string", status=400)
        source_bytes = len(source_text.encode("utf-8"))
        if source_bytes > MAX_CONTENT_BYTES:
            raise ChunkingError("source_too_large", "source_text exceeds 262144 UTF-8 bytes")

        bundle = _validate_profile_bundle(request["profile_bundle"])
        if any(bundle[k] != identity[k] for k in ("name", "version", "digest")):
            raise ChunkingError("profile_digest_mismatch", "index_profile identity does not match profile_bundle", status=409)
        if bundle["status"] == "retired":
            raise ChunkingError("unsupported_profile", "retired Index profile bundles cannot be used for ingestion")
        chunking = bundle["chunking"]
        requested = _require_object(request["chunking_profile"], "chunking_profile",
            {"profile", "version", "max_units", "overlap_units"},
            {"profile", "version", "max_units", "overlap_units"})
        if not isinstance(chunking, dict) or any(requested.get(k) != chunking.get(k) for k in ("profile", "version", "max_units")):
            raise ChunkingError("profile_mismatch", "chunking_profile does not match the pinned Index profile bundle", status=409)
        policy = Policy.from_dict({
            "profile": requested["profile"],
            "profile_version": requested["version"],
            "max_units": requested["max_units"],
            "overlap_units": requested["overlap_units"],
            "unit": "unicode_code_points",
        })
        if policy.profile not in SUPPORTED_PROFILES or policy.profile_version not in SUPPORTED_PROFILES[policy.profile]:
            raise ChunkingError("unsupported_profile", "chunking profile or version is not configured")
        limits = bundle["limits"]
        spans = chunk_spans(source_text, policy, max_chunks=MAX_CHUNKS,
                            deadline_check=self._check_deadline)
        chunk_count = len(spans)
        max_text_bytes = 0
        for start, end in spans:
            self._check_deadline()
            max_text_bytes = max(max_text_bytes, len(source_text[start:end].encode("utf-8")))
        if max_text_bytes > 65536:
            raise ChunkingError("source_too_large", "a chunk's UTF-8 text exceeds the contract response limit")
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
