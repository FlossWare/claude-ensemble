"""Local REST dispatcher for the first Claude Ensemble service."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import hmac
import math
import os
import re
import select
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .tokenization import PROFILE_NAME, PROFILE_VERSION, NORMALIZATION_VERSION, TokenizationError, tokenize
from .embedding import EmbeddingError, PROFILE_NAME as EMBEDDING_PROFILE_NAME, PROFILE_VERSION as EMBEDDING_PROFILE_VERSION, get_engine as get_embedding_engine, validate_index_profile as validate_embedding_index_profile, validate_text as validate_embedding_text
from .ranking import RankingError, rank as rank_candidates
from .intent_classification import IntentClassificationError, classify as classify_intent
from .entity_extraction import EntityExtractionError, PROFILE_NAME as ENTITY_PROFILE_NAME, PROFILE_VERSION as ENTITY_PROFILE_VERSION, get_extractor as get_entity_extractor
from .reranking import RerankingError, get_engine as get_reranking_engine
from .retrieval import RetrievalError, configured_retrieval_services, retrieval_readiness
from .index import IndexError as IndexServiceError, get_index_service
from .memory import MemoryError as MemoryServiceError, get_memory_service
from .graph import GraphError, get_graph_service
from .thompson import ThompsonError, get_thompson_service
from .internal_calls import INTERNAL_CALL_TOKEN
from .chunking import (
    MAX_CONTENT_BYTES, MAX_CHUNKS, DEFAULT_POLICY, ChunkingError, Policy, chunk_document, chunk_spans, validate_index_profile,
)

REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
DEADLINE_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
SOURCE_ID = re.compile(r"^(memory|knowledge):[A-Za-z0-9._~-]{1,128}$")
MAX_REQUEST_BYTES = 300_000
MAX_PROFILE_REQUEST_BYTES = 2_097_152
MAX_TOKENIZATION_BATCH_REQUEST_BYTES = 524_288
MAX_RANKING_REQUEST_BYTES = 1_048_576
MAX_INTENT_REQUEST_BYTES = 1_048_576
MAX_ENTITY_REQUEST_BYTES = 1_048_576
MAX_GRAPH_REQUEST_BYTES = 1_048_576
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
SUPPORTED_PROFILES = {"markdown-default": {"0.1"}}
_MEMORY_RECOVERY_LOCK = threading.Lock()
_MEMORY_GRAPH_LOCK = threading.Lock()
_MEMORY_GRAPH_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ce-memory-graph")
_MEMORY_INGEST_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ce-memory-ingest")


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
    chunking = obj("chunking", {"profile", "version", "max_units", "overlap_units"})
    string(chunking["profile"], 128, "chunking.profile")
    string(chunking["version"], 64, "chunking.version")
    if type(chunking["max_units"]) is not int or not 1 <= chunking["max_units"] <= 65536:
        raise ChunkingError("invalid_request", "profile_bundle.chunking.max_units is invalid", status=400)
    if type(chunking["overlap_units"]) is not int or not 0 <= chunking["overlap_units"] <= min(8192, chunking["max_units"] - 1):
        raise ChunkingError("invalid_request", "profile_bundle.chunking.overlap_units is invalid", status=400)
    tokenization = obj("tokenization", {"profile", "version"})
    string(tokenization["profile"], 128, "tokenization.profile")
    string(tokenization["version"], 64, "tokenization.version")
    if tokenization["profile"] != "technical-default" or tokenization["version"] != "0.1":
        raise ChunkingError("unsupported_profile", "profile_bundle tokenization profile/version is not supported")
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


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant {value} is not permitted")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON numeric value is outside the finite floating-point range")
    return parsed


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
        except OSError:
            # Broken pipes, resets, and aborted connections are client disconnects,
            # not application failures; there is no response to retry here.
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
                    if not DEADLINE_TIMESTAMP.fullmatch(supplied):
                        raise ValueError("deadline must be an RFC 3339 UTC timestamp with at most microsecond precision")
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

    def __getattr__(self, name: str) -> Any:
        # BaseHTTPRequestHandler otherwise emits its own uncorrelated 501 response
        # for arbitrary verbs. Route unknown do_* methods through the shared error path.
        if name.startswith("do_") and name[3:].isupper():
            return self._method_not_allowed
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def do_HEAD(self) -> None:
        # HEAD is bodyless by HTTP semantics. Return the same 405/error metadata
        # and correlation headers as other unsupported methods, but suppress payload bytes.
        request_id, invalid_id = self._request_id()
        status = 400 if invalid_id else 405
        body = (_error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length")
                if invalid_id else _error("method_not_allowed", "HTTP method is not supported"))
        body["request_id"] = request_id
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-CE-Request-ID", request_id)
        self.end_headers()

    def _dispatch_index_method(self, method: str, read_body: bool) -> None:
        request_id, invalid_id = self._request_id()
        if invalid_id:
            self._send(400, _error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length"), request_id)
            return
        if (deadline_error := self._deadline_error()) is not None:
            self._fail(deadline_error, request_id)
            return
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/api/v1/index/"):
            self._method_not_allowed()
            return
        body: dict[str, Any] | None = None
        try:
            if read_body:
                if self.headers.get_content_type() != "application/json":
                    self._send(415, _error("unsupported_media_type", "Content-Type must be application/json"), request_id)
                    return
                length_text = self.headers.get("Content-Length")
                if length_text is None or not length_text.isdecimal():
                    raise ChunkingError("invalid_request", "a valid Content-Length is required", status=400)
                length = int(length_text)
                if length > MAX_PROFILE_REQUEST_BYTES:
                    self.close_connection = True
                    raise ChunkingError("request_too_large", "request exceeds configured byte limit", status=413)
                raw = self._read_body(length)
                try:
                    body = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object,
                                      parse_constant=_reject_json_constant, parse_float=_parse_json_float)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    raise ChunkingError("invalid_request", "request body must be valid UTF-8 JSON without duplicate object keys", status=400) from exc
                _validate_json_unicode(body)
                if not isinstance(body, dict):
                    raise ChunkingError("invalid_request", "request body must be a JSON object", status=400)
            status, response = get_index_service().handle(method, parsed.path, parse_qs(parsed.query), body, self.headers, request_id)
            response["request_id"] = request_id
            self._send(status, response, request_id)
        except IndexServiceError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except ChunkingError as exc:
            self._fail(exc, request_id)
        except Exception:
            self._send(500, _error("internal_error", "request could not be processed"), request_id)

    def do_PUT(self) -> None:
        self._dispatch_index_method("PUT", True)

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        if not urlsplit(self.path).path.startswith("/api/v1/memories/"):
            self._dispatch_index_method("DELETE", False)
            return
        request_id, invalid_id = self._request_id()
        if invalid_id:
            self._send(400, _error("invalid_parameter", "X-CE-Request-ID contains invalid characters or length"), request_id)
            return
        if (deadline_error := self._deadline_error()) is not None:
            self._fail(deadline_error, request_id)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                self._send(415, _error("unsupported_media_type", "Content-Type must be application/json"), request_id)
                return
            length_text = self.headers.get("Content-Length")
            if length_text is None or not length_text.isdecimal():
                raise ChunkingError("invalid_request", "a valid Content-Length is required", status=400)
            length = int(length_text)
            if length > MAX_REQUEST_BYTES:
                self.close_connection = True
                raise ChunkingError("request_too_large", "request exceeds configured byte limit", status=413)
            body = json.loads(self._read_body(length).decode("utf-8"), object_pairs_hook=_unique_json_object,
                              parse_constant=_reject_json_constant)
            _validate_json_unicode(body)
            if not isinstance(body, dict):
                raise ChunkingError("invalid_request", "request body must be a JSON object", status=400)
            if set(body) - {"scope", "delete_scope", "request_id"} or not {"scope", "delete_scope"}.issubset(body):
                raise MemoryServiceError("invalid_request", "delete request has missing or unknown fields", 400)
            memory_id = urlsplit(self.path).path.rsplit("/", 1)[-1]
            service = get_memory_service()
            status, response = service.delete(
                memory_id, body.get("scope"), body.get("delete_scope"),
                self.headers.get("Idempotency-Key", ""), request_id)
            response["request_id"] = request_id
            if response.get("status") in {"accepted", "pending", "failed"} and response.get("indexing_status") != "indexed":
                details = service.deletion_details(response["operation_id"])
                threading.Thread(target=self._memory_delete_index,
                                 args=(service, response, details), daemon=True).start()
                _MEMORY_GRAPH_EXECUTOR.submit(self._memory_graph_project, service)
            self._send(status, response, request_id)
        except MemoryServiceError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._send(400, _error("invalid_request", "request body must be valid UTF-8 JSON"), request_id)
        except ChunkingError as exc:
            self._fail(exc, request_id)
        except Exception:
            self._send(500, _error("internal_error", "request could not be processed"), request_id)

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
                          {"name": "markdown-default@0.1", "status": "ok"}],
            }, request_id)
        elif self.path == "/api/v1/tokenization/health":
            self._send(200, {"service": "tokenization", "status": "alive"}, request_id)
        elif self.path == "/api/v1/tokenization/ready":
            self._send(200, {
                "service": "tokenization",
                "status": "ready",
                "ready": True,
                "checks": [{"name": "technical-default@0.1", "status": "ok"},
                           {"name": "normalization@0.1", "status": "ok"}],
            }, request_id)
        elif self.path == "/api/v1/embedding/health":
            self._send(200, {"service": "embedding", "status": "alive"}, request_id)
        elif self.path == "/api/v1/embedding/ready":
            self._send(200, get_embedding_engine().readiness(), request_id)
        elif self.path == "/api/v1/ranking/health":
            self._send(200, {"service": "ranking", "status": "alive"}, request_id)
        elif self.path == "/api/v1/ranking/ready":
            self._send(200, {"service": "ranking", "status": "ready", "ready": True,
                             "checks": [{"name": "rrf-v1@1", "status": "ok"}]}, request_id)
        elif self.path == "/api/v1/intent-classification/health":
            self._send(200, {"service": "intent-classification", "status": "alive"}, request_id)
        elif self.path == "/api/v1/intent-classification/ready":
            self._send(200, {"service": "intent-classification", "status": "ready", "ready": True,
                             "checks": [{"name": "default-intents@0.1", "status": "ok"}]}, request_id)
        elif self.path == "/api/v1/entity-extraction/health":
            self._send(200, {"service": "entity-extraction", "status": "alive"}, request_id)
        elif self.path == "/api/v1/entity-extraction/ready":
            self._send(200, get_entity_extractor().readiness(), request_id)
        elif self.path == "/api/v1/reranking/health":
            self._send(200, {"service": "reranking", "status": "alive"}, request_id)
        elif self.path == "/api/v1/reranking/ready":
            response = get_reranking_engine().readiness()
            self._send(200 if response["ready"] else 503, response, request_id)
        elif self.path in ("/api/v1/lexical-retrieval/health", "/api/v1/vector-retrieval/health"):
            service = "lexical-retrieval" if "lexical-retrieval" in self.path else "vector-retrieval"
            self._send(200, {"service": service, "status": "alive"}, request_id)
        elif self.path in ("/api/v1/lexical-retrieval/ready", "/api/v1/vector-retrieval/ready"):
            service = "lexical-retrieval" if "lexical-retrieval" in self.path else "vector-retrieval"
            response = retrieval_readiness(service)
            self._send(200 if response["ready"] else 503, response, request_id)
        elif self.path == "/api/v1/memory/health":
            self._send(200, {"service": "memory", "status": "alive"}, request_id)
        elif self.path == "/api/v1/memory/ready":
            self._start_memory_recovery()
            self._send(200, {"service": "memory", "status": "ready", "ready": True,
                             "checks": [{"name": "canonical_store", "status": "ok"},
                                        {"name": "pending_ingestion_recovery", "status": "scheduled"}]}, request_id)
        elif urlsplit(self.path).path.startswith("/api/v1/memories/operations/"):
            try:
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                scope = {"type": query.get("scope_type", [""])[0],
                         "id": query.get("scope_id", [""])[0],
                         "visibility": query.get("visibility", [""])[0]}
                operation_id = parsed.path.rsplit("/", 1)[-1]
                response = get_memory_service().operation(operation_id, scope_value=scope)
                response["request_id"] = request_id
                self._send(200, response, request_id)
            except MemoryServiceError as exc:
                self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        elif len(urlsplit(self.path).path.strip("/").split("/")) == 6 and urlsplit(self.path).path.startswith("/api/v1/memories/") and urlsplit(self.path).path.split("/")[-2] == "operations":
            try:
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                scope = {"type": query.get("scope_type", [""])[0],
                         "id": query.get("scope_id", [""])[0],
                         "visibility": query.get("visibility", [""])[0]}
                parts = parsed.path.strip("/").split("/")
                response = get_memory_service().operation(parts[-1], memory_id=parts[-3], scope_value=scope)
                response["request_id"] = request_id
                self._send(200, response, request_id)
            except MemoryServiceError as exc:
                self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        elif urlsplit(self.path).path.startswith("/api/v1/memories/"):
            try:
                parsed = urlsplit(self.path)
                memory_id = parsed.path.rsplit("/", 1)[-1]
                query = parse_qs(parsed.query)
                scope = {
                    "type": query.get("scope_type", [""])[0],
                    "id": query.get("scope_id", [""])[0],
                    "visibility": query.get("visibility", [""])[0],
                }
                response = get_memory_service().read(memory_id, scope)
                response["request_id"] = request_id
                self._send(200, response, request_id)
            except MemoryServiceError as exc:
                self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        elif urlsplit(self.path).path.startswith("/api/v1/thompson/"):
            try:
                parsed = urlsplit(self.path)
                status, response = get_thompson_service().handle("GET", parsed.path, parse_qs(parsed.query), None, self.headers, request_id)
                self._send(status, response, request_id)
            except ThompsonError as exc:
                self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        elif urlsplit(self.path).path.startswith("/api/v1/graph/"):
            try:
                parsed = urlsplit(self.path)
                status, response = get_graph_service().handle("GET", parsed.path, parse_qs(parsed.query), None, request_id)
                self._send(status, response, request_id)
            except GraphError as exc:
                self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        elif urlsplit(self.path).path.startswith("/api/v1/index/"):
            try:
                parsed = urlsplit(self.path)
                status, response = get_index_service().handle("GET", parsed.path, parse_qs(parsed.query), None, self.headers, request_id)
                response["request_id"] = request_id
                self._send(status, response, request_id)
            except IndexServiceError as exc:
                self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
            except Exception:
                self._send(500, _error("internal_error", "request could not be processed"), request_id)
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
        is_index_route = urlsplit(self.path).path.startswith("/api/v1/index/")
        memory_path = urlsplit(self.path).path
        is_memory_route = memory_path == "/api/v1/memories" or memory_path == "/api/v1/memories/verify-revisions" or (
            memory_path.startswith("/api/v1/memories/") and memory_path.endswith("/revisions"))
        is_graph_route = memory_path.startswith("/api/v1/graph/")
        is_thompson_route = memory_path.startswith("/api/v1/thompson/")
        if not is_index_route and not is_memory_route and not is_graph_route and not is_thompson_route and self.path not in (
            "/api/v1/chunking/chunks", "/api/v1/chunking/preflight",
            "/api/v1/tokenization/lexical", "/api/v1/tokenization/lexical/batch",
            "/api/v1/embeddings", "/api/v1/ranking/rank",
            "/api/v1/intent-classification/classify", "/api/v1/entity-extraction/extract",
            "/api/v1/reranking/rerank",
            "/api/v1/lexical-retrieval/search", "/api/v1/vector-retrieval/search",
        ):
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
            if is_index_route:
                limit = MAX_PROFILE_REQUEST_BYTES
            elif is_graph_route:
                limit = MAX_GRAPH_REQUEST_BYTES
            elif self.path == "/api/v1/chunking/chunks":
                limit = MAX_REQUEST_BYTES
            elif self.path == "/api/v1/chunking/preflight":
                limit = MAX_PROFILE_REQUEST_BYTES
            elif self.path == "/api/v1/tokenization/lexical/batch":
                limit = MAX_TOKENIZATION_BATCH_REQUEST_BYTES
            elif self.path == "/api/v1/embeddings":
                limit = MAX_TOKENIZATION_BATCH_REQUEST_BYTES
            elif self.path == "/api/v1/ranking/rank":
                limit = MAX_RANKING_REQUEST_BYTES
            elif self.path == "/api/v1/intent-classification/classify":
                limit = MAX_INTENT_REQUEST_BYTES
            elif self.path == "/api/v1/entity-extraction/extract":
                limit = MAX_ENTITY_REQUEST_BYTES
            else:
                limit = MAX_REQUEST_BYTES
            if length > limit:
                # Do not drain an attacker-controlled body just to preserve keep-alive.
                # Explicitly close after the bounded 413 response; unread bytes must not
                # be interpreted as another request on this connection.
                self.close_connection = True
                raise ChunkingError("request_too_large", "request exceeds configured byte limit", status=413)
            raw = self._read_body(length)
            try:
                request = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object,
                                  parse_constant=_reject_json_constant)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ChunkingError("invalid_request", "request body must be valid UTF-8 JSON without duplicate object keys", status=400) from exc
            _validate_json_unicode(request)
            if is_thompson_route:
                parsed = urlsplit(self.path)
                status, response = get_thompson_service().handle("POST", parsed.path, parse_qs(parsed.query), request, self.headers, request_id)
                self._send(status, response, request_id)
                return
            if is_graph_route:
                parsed = urlsplit(self.path)
                status, response = get_graph_service().handle("POST", parsed.path, parse_qs(parsed.query), request, request_id)
                self._send(status, response, request_id)
                return
            if is_memory_route:
                parsed = urlsplit(self.path)
                path = parsed.path
                request["request_id"] = request_id
                service = get_memory_service()
                if path == "/api/v1/memories":
                    context = self._memory_preflight(request, request_id)
                    status, response = service.create(request, self.headers.get("Idempotency-Key", ""), request_id)
                    if response.get("status") in {"accepted", "pending", "failed"} and response.get("indexing_status") != "indexed":
                        _MEMORY_INGEST_EXECUTOR.submit(self._memory_ingest, service, response, dict(request), context)
                elif path == "/api/v1/memories/verify-revisions":
                    if set(request) - {"items", "request_id"} or "items" not in request:
                        raise MemoryServiceError("invalid_request", "verification request has missing or unknown fields", 400)
                    response = {"results": service.verify_revisions(request["items"]), "request_id": request_id}
                    status = 200
                else:
                    memory_id = path.split("/")[-2]
                    query = parse_qs(parsed.query)
                    scope = {"type": query.get("scope_type", [""])[0],
                             "id": query.get("scope_id", [""])[0],
                             "visibility": query.get("visibility", [""])[0]}
                    service.read(memory_id, scope)
                    context = self._memory_preflight(request, request_id)
                    status, response = service.update(
                        memory_id, request, self.headers.get("Idempotency-Key", ""), request_id, scope)
                    if response.get("status") in {"accepted", "pending", "failed"} and response.get("indexing_status") != "indexed":
                        ingestion_request = {**request, "scope": scope}
                        _MEMORY_INGEST_EXECUTOR.submit(self._memory_ingest, service, response, ingestion_request, context)
                if response.get("source_id", "").startswith("memory:") and response.get("graph_status") != "indexed":
                    _MEMORY_GRAPH_EXECUTOR.submit(self._memory_graph_project, service)
                response["request_id"] = request_id
                self._send(status, response, request_id)
                return
            if is_index_route:
                parsed = urlsplit(self.path)
                request["request_id"] = request_id
                status, response = get_index_service().handle("POST", parsed.path, parse_qs(parsed.query), request, self.headers, request_id)
                response["request_id"] = request_id
                if (deadline_error := self._deadline_error()) is not None:
                    self._fail(deadline_error, request_id)
                    return
                self._send(status, response, request_id)
                return
            if self.path == "/api/v1/chunking/preflight":
                response = self._preflight(request)
            elif self.path == "/api/v1/tokenization/lexical":
                response = self._tokenize(request)
            elif self.path == "/api/v1/tokenization/lexical/batch":
                response = self._tokenize_batch(request)
            elif self.path == "/api/v1/embeddings":
                response = self._embed(request)
            elif self.path == "/api/v1/ranking/rank":
                response = self._rank(request)
            elif self.path == "/api/v1/intent-classification/classify":
                response = self._classify_intent(request)
            elif self.path == "/api/v1/entity-extraction/extract":
                response = self._extract_entities(request)
            elif self.path == "/api/v1/reranking/rerank":
                response = get_reranking_engine().rerank(request)
            elif self.path in ("/api/v1/lexical-retrieval/search", "/api/v1/vector-retrieval/search"):
                lexical_service, vector_service = configured_retrieval_services(deadline=self.headers.get("X-CE-Deadline"))
                if self.path == "/api/v1/lexical-retrieval/search":
                    response = lexical_service.search(request)
                else:
                    response = vector_service.search(request)
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
        except TokenizationError as exc:
            self._send(exc.status, _error(exc.code, str(exc)), request_id)
        except EmbeddingError as exc:
            self._send(exc.status, _error(exc.code, str(exc)), request_id)
        except RankingError as exc:
            self._send(exc.status, _error(exc.code, str(exc)), request_id)
        except IntentClassificationError as exc:
            self._send(exc.status, _error(exc.code, str(exc)), request_id)
        except EntityExtractionError as exc:
            self._send(exc.status, _error(exc.code, str(exc)), request_id)
        except RerankingError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except RetrievalError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except MemoryServiceError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except GraphError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except IndexServiceError as exc:
            self._send(exc.status, _error(exc.code, str(exc), retryable=exc.status >= 500), request_id)
        except Exception:
            self._send(500, _error("internal_error", "request could not be processed"), request_id)

    def _memory_rest_json(self, base_url: str, path: str, *, payload: dict[str, Any] | None = None,
                          request_id: str, timeout: float, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "X-CE-Request-ID": request_id,
            "X-CE-Internal-Call": "true",
            "X-CE-Internal-Token": INTERNAL_CALL_TOKEN,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if extra_headers:
            headers.update(extra_headers)
        request = Request(base_url.rstrip("/") + path, data=body, headers=headers,
                          method="GET" if body is None else "POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                error_body = json.loads(exc.read().decode("utf-8"))
                error = error_body.get("error", {})
                code = error.get("code", "dependency_unavailable")
                message = error.get("message", "Memory dependency request failed")
            except Exception:
                code, message = "dependency_unavailable", "Memory dependency request failed"
            raise MemoryServiceError(code, message, exc.code if exc.code in {400, 404, 409, 413, 422, 503, 504} else 503) from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise MemoryServiceError("dependency_unavailable", "Memory dependency did not return a valid response", 503) from exc
        if not isinstance(decoded, dict):
            raise MemoryServiceError("dependency_unavailable", "Memory dependency returned an invalid response", 503)
        return decoded

    def _memory_preflight(self, request: dict[str, Any], request_id: str) -> dict[str, Any]:
        profile = request.get("index_profile")
        if not isinstance(profile, dict) or not isinstance(profile.get("name"), str) or not isinstance(profile.get("version"), str):
            raise MemoryServiceError("invalid_request", "index_profile identity is required", 400)
        local_base = f"http://127.0.0.1:{self.server.server_address[1]}"
        index_base = os.environ.get("CE_INDEX_BASE_URL", local_base)
        chunking_base = os.environ.get("CE_CHUNKING_BASE_URL", local_base)
        profile_path = ("/api/v1/index/profiles/" + quote(profile["name"], safe="")
                        + "/versions/" + quote(profile["version"], safe=""))
        resolved = self._memory_rest_json(index_base, profile_path, request_id=request_id, timeout=2.0)
        bundle = resolved.get("bundle", resolved.get("profile_bundle"))
        if not isinstance(bundle, dict):
            raise MemoryServiceError("profile_not_found", "Index did not return the requested profile bundle", 503)
        for field in ("name", "version", "digest"):
            if bundle.get(field) != profile.get(field):
                raise MemoryServiceError("profile_mismatch", "Index returned a different pinned profile identity", 409)
        chunking = bundle.get("chunking")
        if not isinstance(chunking, dict):
            raise MemoryServiceError("profile_mismatch", "Index profile has no chunking policy", 409)
        preflight = self._memory_rest_json(
            chunking_base, "/api/v1/chunking/preflight",
            payload={
                "request_id": request_id,
                "index_profile": {key: profile[key] for key in ("name", "version", "digest")},
                "source_text": request.get("content"),
                "chunking_profile": {key: chunking[key] for key in ("profile", "version", "max_units", "overlap_units")},
                "profile_bundle": bundle,
            },
            request_id=request_id, timeout=0.5,
        )
        if preflight.get("fits_profile") is not True:
            raise MemoryServiceError("source_too_large", "content exceeds the pinned Index profile limits", 422)
        return {"bundle": bundle, "preflight": preflight, "index_base": index_base,
                "chunking_base": chunking_base,
                "tokenization_base": os.environ.get("CE_TOKENIZATION_BASE_URL", local_base),
                "embedding_base": os.environ.get("CE_EMBEDDING_BASE_URL", local_base),
                "local_base": local_base}

    def _start_memory_recovery(self) -> None:
        """Run one startup recovery pass for durable, unfinished Memory ingestion."""
        with _MEMORY_RECOVERY_LOCK:
            if getattr(self.server, "_memory_recovery_started", False):
                return
            self.server._memory_recovery_started = True
        service = get_memory_service()
        threading.Thread(target=self._recover_pending_memory, args=(service,), daemon=True).start()

    def _memory_delete_index(self, service: Any, accepted: dict[str, Any], details: dict[str, Any]) -> None:
        operation_id = accepted["operation_id"]
        request_id = accepted.get("request_id", operation_id)
        local_base = f"http://127.0.0.1:{self.server.server_address[1]}"
        index_base = os.environ.get("CE_INDEX_BASE_URL", local_base)
        try:
            self._memory_rest_json(
                index_base, "/api/v1/index/operations/delete",
                payload={
                    "operation_id": operation_id, "request_id": request_id,
                    "source_id": details["source_id"],
                    "revision_sequence": details["revision_sequence"],
                    "scope": details["scope"], "index_profile": details["index_profile"],
                    "delete_scope": "source",
                },
                request_id=request_id, timeout=10.0,
                extra_headers={"Idempotency-Key": operation_id})
            # Graph deletion is deliberately not implemented in this slice.
            # Keep the overall operation pending until that independent owner
            # projection is acknowledged; Index alone is not full delete acceptance.
            service.update_operation(operation_id, "pending", "indexed")
        except Exception:
            try:
                service.update_operation(operation_id, "failed", "index_failed")
            except Exception:
                pass

    def _recover_pending_memory(self, service: Any) -> None:
        self._memory_graph_project(service)
        for item in service.pending_ingestions():
            accepted = item["accepted"]
            request = item["request"]
            request_id = accepted.get("request_id", accepted["operation_id"])
            try:
                context = self._memory_preflight(request, request_id)
                _MEMORY_INGEST_EXECUTOR.submit(self._memory_ingest, service, accepted, request, context)
            except Exception:
                try:
                    service.update_operation(accepted["operation_id"], "failed", "index_failed")
                except Exception:
                    pass
        for item in service.pending_deletions():
            self._memory_delete_index(service, item["accepted"], item["details"])
        self._memory_graph_project(service)

    def _memory_graph_project(self, service: Any) -> None:
        """Replay durable Memory Graph intents in owner-sequence order through REST."""
        if not _MEMORY_GRAPH_LOCK.acquire(blocking=False):
            return
        try:
            for item in service.pending_graph_projections():
                payload = dict(item["payload"])
                operation_id = item["operation_id"]
                request_id = payload.get("request_id", operation_id)
                payload["request_id"] = request_id
                local_base = f"http://127.0.0.1:{self.server.server_address[1]}"
                graph_base = os.environ.get("CE_GRAPH_BASE_URL", local_base)
                endpoint = ("/api/v1/graph/source-deletions" if item["operation_kind"] == "delete"
                            else "/api/v1/graph/source-projections")
                try:
                    self._memory_rest_json(graph_base, endpoint, payload=payload, request_id=request_id,
                                           timeout=10.0, extra_headers={"Idempotency-Key": operation_id})
                    service.update_graph_operation(operation_id, "indexed")
                except Exception as exc:
                    try:
                        service.update_graph_operation(operation_id, "graph_failed",
                                                       f"{type(exc).__name__}: {str(exc)[:400]}")
                    except Exception:
                        pass
                    break
        finally:
            _MEMORY_GRAPH_LOCK.release()

    def _memory_ingest(self, service: Any, accepted: dict[str, Any], original_request: dict[str, Any],
                       context: dict[str, Any]) -> None:
        """Run the derived ingestion path after canonical commit, using REST only."""
        operation_id = accepted["operation_id"]
        request_id = accepted.get("request_id", operation_id)
        try:
            service.update_operation(operation_id, "pending", "pending_index")
            canonical = service.read_for_ingestion(accepted["memory_id"], original_request["scope"], accepted["revision_sequence"])
            bundle = context["bundle"]
            profile = accepted["index_profile"]
            # Chunking owns document structure, not access-control scope.
            # Its source contract rejects unknown fields; scope is supplied
            # separately to Index after representations are produced.
            source = {
                "source_id": accepted["source_id"], "revision": accepted["revision"],
                "revision_sequence": accepted["revision_sequence"],
                "media_type": "text/markdown", "content": canonical["content"],
            }
            chunks_response = self._memory_rest_json(
                context["chunking_base"], "/api/v1/chunking/chunks",
                payload={"request_id": request_id, "index_profile": profile,
                         "source": source, "profile_bundle": bundle},
                request_id=request_id, timeout=10.0)
            chunks = chunks_response.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                raise MemoryServiceError("invalid_dependency_response", "Chunking returned no chunks", 503)
            tokenization_profile = bundle["tokenization"]
            token_results: dict[str, list[str]] = {}
            for start in range(0, len(chunks), 64):
                batch = chunks[start:start + 64]
                token_response = self._memory_rest_json(
                    context["tokenization_base"], "/api/v1/tokenization/lexical/batch",
                    payload={
                        "request_id": request_id, "index_profile": profile,
                        "profile": tokenization_profile["profile"],
                        "profile_version": tokenization_profile["version"],
                        "inputs": [{"input_id": chunk["chunk_id"], "text": chunk["text"]} for chunk in batch],
                    },
                    request_id=request_id, timeout=10.0)
                for item in token_response.get("results", []):
                    if not isinstance(item, dict) or "error" in item or not isinstance(item.get("tokens"), list):
                        raise MemoryServiceError("tokenization_failed", "Tokenization failed for one or more chunks", 422)
                    terms = []
                    seen = set()
                    for token in item["tokens"]:
                        term = token.get("term") if isinstance(token, dict) else None
                        if isinstance(term, str) and term and term not in seen:
                            seen.add(term)
                            terms.append(term)
                    token_results[item["input_id"]] = terms
            embedding_profile = bundle["embedding"]
            embedded: dict[str, dict[str, Any]] = {}
            for start in range(0, len(chunks), 64):
                batch = chunks[start:start + 64]
                embedding_response = self._memory_rest_json(
                    context["embedding_base"], "/api/v1/embeddings",
                    payload={
                        "request_id": request_id, "index_profile": profile,
                        "profile": embedding_profile["profile"],
                        "profile_version": embedding_profile["version"],
                        "normalize": embedding_profile["normalization"],
                        "inputs": [{"input_id": chunk["chunk_id"], "input_type": "document", "text": chunk["text"]}
                                   for chunk in batch],
                    },
                    request_id=request_id, timeout=20.0)
                model = embedding_response.get("model", {})
                if (model.get("model_id") != embedding_profile["model"]
                        or model.get("model_version") != embedding_profile["model_version"]
                        or model.get("dimensions") != embedding_profile["dimensions"]):
                    raise MemoryServiceError("incompatible_representation", "Embedding model identity does not match the pinned Index profile", 422)
                for item in embedding_response.get("results", []):
                    if not isinstance(item, dict) or item.get("status") != "complete" or not isinstance(item.get("vector"), list):
                        raise MemoryServiceError("embedding_failed", "Embedding failed for one or more chunks", 503)
                    embedded[item["input_id"]] = {"model": model["model_id"], "version": model["model_version"],
                                                  "dimensions": model["dimensions"], "values": item["vector"]}
            lexical = bundle["lexical"]
            representations = []
            for chunk in chunks:
                chunk_id = chunk["chunk_id"]
                if chunk_id not in token_results or chunk_id not in embedded:
                    raise MemoryServiceError("invalid_dependency_response", "A chunk is missing tokenization or embedding output", 503)
                representations.append({
                    "chunk_id": chunk_id,
                    "chunker": {"profile": chunks_response["chunker"]["profile"],
                                "version": chunks_response["chunker"]["version"]},
                    "text": chunk["text"],
                    "lexical": {"profile": lexical["profile"], "version": lexical["version"],
                                "terms": token_results[chunk_id]},
                    "vector": {"input_type": "document", **embedded[chunk_id]},
                    "metadata": chunk.get("metadata", {}),
                })
            self._memory_rest_json(
                context["index_base"], "/api/v1/index/operations/upsert",
                payload={"operation_id": operation_id, "request_id": request_id,
                         "source": {"source_id": accepted["source_id"], "revision": accepted["revision"],
                                    "revision_sequence": accepted["revision_sequence"], "scope": canonical["scope"]},
                         "index_profile": profile, "representations": representations},
                request_id=request_id, timeout=20.0,
                extra_headers={"Idempotency-Key": operation_id})
            service.update_operation(operation_id, "complete", "indexed")
        except MemoryServiceError as exc:
            # Keep the durable public operation status coarse, but retain a
            # bounded diagnostic in service logs for operational troubleshooting.
            print(f"Memory ingestion {operation_id} failed ({exc.code}): {str(exc)[:512]}")
            try:
                if exc.code == "stale_revision":
                    service.update_operation(operation_id, "reconciliation_required", "reconciliation_required")
                else:
                    service.update_operation(operation_id, "failed", "index_failed")
            except Exception:
                pass
        except Exception as exc:
            print(f"Memory ingestion {operation_id} failed ({type(exc).__name__}): {str(exc)[:512]}")
            try:
                service.update_operation(operation_id, "failed", "index_failed")
            except Exception:
                pass

    def _rank(self, value: Any) -> dict[str, Any]:
        return rank_candidates(value)

    def _classify_intent(self, value: Any) -> dict[str, Any]:
        return classify_intent(value)

    def _extract_entities(self, value: Any) -> dict[str, Any]:
        request = _require_object(
            value, "request", {"request_id", "text", "profile"},
            {"request_id", "text", "profile"},
        )
        if not isinstance(request["request_id"], str) or not 1 <= len(request["request_id"]) <= 128:
            raise EntityExtractionError("invalid_parameter", "request_id must be a string of 1 to 128 characters", status=400)
        profile = _require_object(request["profile"], "profile", {"name", "version"}, {"name", "version"})
        if profile != {"name": ENTITY_PROFILE_NAME, "version": ENTITY_PROFILE_VERSION}:
            raise EntityExtractionError("unsupported_profile", "entity extraction profile or version is not supported")
        return {
            "profile": {"name": ENTITY_PROFILE_NAME, "version": ENTITY_PROFILE_VERSION},
            "entities": get_entity_extractor().extract(request["text"]),
        }

    def _embed(self, value: Any) -> dict[str, Any]:
        request = _require_object(
            value, "request",
            {"request_id", "index_profile", "profile", "profile_version", "inputs", "normalize"},
            {"index_profile", "profile", "profile_version", "inputs"},
        )
        if "request_id" in request and (
            not isinstance(request["request_id"], str) or not 1 <= len(request["request_id"]) <= 128
        ):
            raise EmbeddingError("invalid_parameter", "request.request_id must be a string of 1 to 128 characters", status=400)
        identity = validate_embedding_index_profile(request["index_profile"])
        if request["profile"] != EMBEDDING_PROFILE_NAME or request["profile_version"] != EMBEDDING_PROFILE_VERSION:
            raise EmbeddingError("unsupported_profile", "embedding profile or version is not supported")
        inputs = request["inputs"]
        if not isinstance(inputs, list) or not 1 <= len(inputs) <= 64:
            raise EmbeddingError("invalid_parameter", "inputs must contain between 1 and 64 items", status=400)
        normalized_inputs: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for item in inputs:
            item = _require_object(item, "inputs[]", {"input_id", "input_type", "text"}, {"input_id", "input_type", "text"})
            input_id = item["input_id"]
            if not isinstance(input_id, str) or not 1 <= len(input_id) <= 128:
                raise EmbeddingError("invalid_parameter", "input_id must be a string of 1 to 128 characters", status=400)
            if input_id in seen_ids:
                raise EmbeddingError("invalid_parameter", "input_id values must be unique", status=400)
            seen_ids.add(input_id)
            input_type = item["input_type"]
            if not isinstance(input_type, str) or input_type not in {"query", "document"}:
                raise EmbeddingError("invalid_parameter", "input_type must be query or document", status=400)
            text = validate_embedding_text(item["text"], f"inputs[{input_id}].text")
            normalized_inputs.append({"input_id": input_id, "input_type": input_type, "text": text})
        normalization = request.get("normalize", "profile-default")
        if not isinstance(normalization, str) or normalization not in {"profile-default", "none", "l2"}:
            raise EmbeddingError("invalid_parameter", "normalize must be profile-default, none, or l2", status=400)
        model, results = get_embedding_engine().embed(normalized_inputs, normalization)
        return {
            "index_profile": identity,
            "profile": EMBEDDING_PROFILE_NAME,
            "profile_version": EMBEDDING_PROFILE_VERSION,
            "model": model,
            "results": results,
        }

    def _tokenization_context(self, request: Any, *, batch: bool) -> tuple[dict[str, Any], dict[str, bool]]:
        allowed = {"request_id", "index_profile", "profile", "profile_version", "options"}
        required = {"index_profile", "profile", "profile_version", "inputs"} if batch else {
            "index_profile", "profile", "profile_version", "text", "options"
        }
        if batch:
            allowed.add("inputs")
        else:
            allowed.add("text")
        body = _require_object(request, "request", allowed, required)
        if "request_id" in body and (not isinstance(body["request_id"], str)
                or not 1 <= len(body["request_id"]) <= 128):
            raise TokenizationError("invalid_parameter", "request.request_id must be a string of 1 to 128 characters", status=400)
        identity = validate_index_profile(body["index_profile"])
        if body["profile"] != PROFILE_NAME or body["profile_version"] != PROFILE_VERSION:
            raise TokenizationError("unsupported_profile", "tokenization profile or version is not supported")
        options = _require_object(body.get("options", {}), "options",
            {"preserve_identifiers", "include_offsets", "include_normalized_terms"}, set())
        effective = {
            "preserve_identifiers": options.get("preserve_identifiers", True),
            "include_offsets": options.get("include_offsets", True),
            "include_normalized_terms": options.get("include_normalized_terms", True),
        }
        for name, value in effective.items():
            if type(value) is not bool:
                raise TokenizationError("invalid_parameter", f"options.{name} must be a boolean", status=400)
        return identity, effective

    def _tokenize(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "text", "profile", "profile_version", "options"},
            {"index_profile", "text", "profile", "profile_version", "options"})
        identity, options = self._tokenization_context(request, batch=False)
        tokens = tokenize(request["text"], **options)
        return {
            "profile": PROFILE_NAME,
            "version": PROFILE_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
            "index_profile": identity,
            "tokens": tokens,
        }

    def _tokenize_batch(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "profile", "profile_version", "options", "inputs"},
            {"index_profile", "profile", "profile_version", "inputs"})
        identity, options = self._tokenization_context(request, batch=True)
        inputs = request["inputs"]
        if not isinstance(inputs, list) or not 1 <= len(inputs) <= 64:
            raise TokenizationError("invalid_parameter", "inputs must contain between 1 and 64 items", status=400)
        input_ids: set[str] = set()
        results: list[dict[str, Any]] = []
        for item in inputs:
            item = _require_object(item, "inputs[]", {"input_id", "text"}, {"input_id", "text"})
            input_id = item["input_id"]
            if not isinstance(input_id, str) or not 1 <= len(input_id) <= 128:
                raise TokenizationError("invalid_parameter", "input_id must be a string of 1 to 128 characters", status=400)
            if input_id in input_ids:
                raise TokenizationError("invalid_parameter", "input_id values must be unique", status=400)
            input_ids.add(input_id)
            try:
                results.append({"input_id": input_id, "tokens": tokenize(item["text"], **options)})
            except TokenizationError as exc:
                results.append({"input_id": input_id, "error": {
                    "code": exc.code, "message": str(exc), "retryable": False,
                }})
        return {
            "profile": PROFILE_NAME,
            "version": PROFILE_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
            "index_profile": identity,
            "results": results,
        }

    def _chunks(self, value: Any) -> dict[str, Any]:
        request = _require_object(value, "request",
            {"request_id", "index_profile", "source", "policy", "options", "profile_bundle"},
            {"index_profile", "source", "profile_bundle"})
        if "request_id" in request and (not isinstance(request["request_id"], str)
                or not 1 <= len(request["request_id"]) <= 128):
            raise ChunkingError("invalid_request", "request.request_id must be a string of 1 to 128 characters", status=400)
        profile = validate_index_profile(request["index_profile"])
        bundle = _validate_profile_bundle(request["profile_bundle"])
        if any(bundle[k] != profile[k] for k in ("name", "version", "digest")):
            raise ChunkingError("profile_digest_mismatch", "index_profile identity does not match profile_bundle", status=409)
        if bundle["status"] == "retired":
            raise ChunkingError("unsupported_profile", "retired Index profile bundles cannot be used for ingestion")
        source = _require_object(request["source"], "source",
            {"source_id", "revision", "revision_sequence", "media_type", "content"},
            {"source_id", "revision", "revision_sequence", "content"})
        if not isinstance(source["source_id"], str) or not SOURCE_ID.fullmatch(source["source_id"]):
            raise ChunkingError("invalid_parameter", "source.source_id is invalid", status=400)
        if "media_type" in source and (not isinstance(source["media_type"], str) or len(source["media_type"]) > 128):
            raise ChunkingError("invalid_parameter", "source.media_type is invalid", status=400)
        pinned = bundle["chunking"]
        policy = Policy.from_dict(request["policy"]) if "policy" in request else Policy(
            pinned["profile"], pinned["version"], pinned["max_units"], pinned["overlap_units"])
        if policy.profile not in SUPPORTED_PROFILES or policy.profile_version not in SUPPORTED_PROFILES[policy.profile]:
            raise ChunkingError("unsupported_profile", "chunking profile or version is not configured")
        if any(getattr(policy, attr) != expected for attr, expected in (
            ("profile", pinned["profile"]), ("profile_version", pinned["version"]),
            ("max_units", pinned["max_units"]), ("overlap_units", pinned["overlap_units"]))):
            raise ChunkingError("profile_mismatch", "policy does not match the pinned Index profile bundle", status=409)
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
            media_type=source.get("media_type"),
            deadline_check=self._check_deadline,
        )
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
        if not isinstance(chunking, dict) or any(requested.get(k) != chunking.get(k) for k in ("profile", "version", "max_units", "overlap_units")):
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


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Bound handlers while reserving capacity for nested in-process REST calls.

    External requests can consume at most 24 of 32 workers. Requests carrying
    X-CE-Internal-Call: true use the reserved eight-worker pool. This prevents
    retrieval fan-out from occupying every worker while waiting on sibling REST
    calls handled by this same server. The marker is capacity classification,
    not an authentication mechanism.
    """
    max_workers = 32
    max_internal_workers = 8
    max_external_workers = max_workers - max_internal_workers
    request_queue_size = 64
    daemon_threads = True

    def __init__(self, server_address: Any, RequestHandlerClass: type[BaseHTTPRequestHandler],
                 bind_and_activate: bool = True):
        self._worker_slots = threading.BoundedSemaphore(self.max_workers)
        self._internal_slots = threading.BoundedSemaphore(self.max_internal_workers)
        self._external_slots = threading.BoundedSemaphore(self.max_external_workers)
        self._slot_lock = threading.Lock()
        self._request_slots: dict[Any, threading.BoundedSemaphore] = {}
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

    @staticmethod
    def _is_internal_request(request: Any, wait_seconds: float = 0) -> bool:
        # Peek only; BaseHTTPRequestHandler still consumes the original bytes.
        # If external capacity is exhausted, process_request may wait briefly for
        # the complete header block. TCP accept can precede the client's first
        # write, so a single zero-timeout peek is not a reliable classifier.
        # The process-local token prevents ordinary clients from claiming the lane.
        deadline = time.monotonic() + max(0.0, wait_seconds)
        try:
            while True:
                remaining = max(0.0, deadline - time.monotonic())
                readable, _, _ = select.select([request], [], [], remaining)
                if not readable:
                    return False
                head = request.recv(16384, socket.MSG_PEEK)
                if b"\r\n\r\n" in head or len(head) >= 16384:
                    break
                if wait_seconds <= 0 or time.monotonic() >= deadline:
                    return False
                time.sleep(min(0.001, max(0.0, deadline - time.monotonic())))
            header_block = head.split(b"\r\n\r\n", 1)[0]
            headers = {}
            for line in header_block.split(b"\r\n")[1:]:
                name, separator, value = line.partition(b":")
                if separator:
                    headers[name.strip().lower()] = value.strip()
            marker = headers.get(b"x-ce-internal-call", b"").lower() == b"true"
            token = headers.get(b"x-ce-internal-token", b"")
            expected = INTERNAL_CALL_TOKEN.encode("ascii")
            return marker and hmac.compare_digest(token, expected)
        except (OSError, ValueError):
            return False

    def _reject_capacity(self, request: Any) -> None:
        request_id = str(uuid.uuid4())
        body = _error("service_unavailable", "request capacity is temporarily exhausted", retryable=True)
        body["request_id"] = request_id
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response = (
            b"HTTP/1.1 503 Service Unavailable\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            + f"Content-Length: {len(payload)}\r\n".encode("ascii")
            + f"X-CE-Request-ID: {request_id}\r\n".encode("ascii")
            + b"Connection: close\r\n\r\n"
            + payload
        )
        try:
            request.sendall(response)
        except OSError:
            pass
        finally:
            self.shutdown_request(request)

    def process_request(self, request: Any, client_address: Any) -> None:
        if self._is_internal_request(request):
            slot = self._internal_slots
            if not slot.acquire(blocking=False):
                self._reject_capacity(request)
                return
        else:
            slot = self._external_slots
            if not slot.acquire(blocking=False):
                # Only wait for headers when the external lane is full. This
                # avoids stalling the accept loop during normal traffic while
                # closing the accept-before-write race for nested REST calls.
                if self._is_internal_request(request, wait_seconds=0.25):
                    slot = self._internal_slots
                    if not slot.acquire(blocking=False):
                        self._reject_capacity(request)
                        return
                else:
                    self._reject_capacity(request)
                    return
        if not self._worker_slots.acquire(blocking=False):
            slot.release()
            self._reject_capacity(request)
            return
        with self._slot_lock:
            self._request_slots[request] = slot
        try:
            super().process_request(request, client_address)
        except Exception:
            with self._slot_lock:
                self._request_slots.pop(request, None)
            slot.release()
            self._worker_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._slot_lock:
                slot = self._request_slots.pop(request, None)
            if slot is not None:
                slot.release()
            self._worker_slots.release()


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    BoundedThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
