"""REST-first request orchestration for CE's proof of concept."""
from __future__ import annotations

import base64
import json
import os
import re
import unicodedata
import uuid
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from typing import Any

from .internal_calls import INTERNAL_CALL_TOKEN
from .context_budget import count_context_tokens


INTENTS = ["memory_recall", "knowledge_lookup", "relationship_exploration", "troubleshooting",
           "explanation", "decision_support", "general"]
FAILURE_CODES = {
    "active_generation_cannot_be_abandoned", "candidate_identity_conflict", "conflict",
    "context_assembly_failed", "cutover_in_progress", "deadline_exceeded", "dependency_unavailable",
    "duplicate_list_id", "duplicate_retrieval_rank", "endpoint_not_found", "fence_expired",
    "fence_released", "generation_not_caught_up", "generation_not_found", "graph_replay_incomplete",
    "idempotency_conflict", "idempotency_key_expired", "incompatible_representation", "internal_error",
    "invalid_candidate", "invalid_embedding_mode", "invalid_fence", "invalid_node", "invalid_parameter",
    "invalid_request", "invalid_scope", "local_access_denied", "missing_endpoint_node", "not_found",
    "not_ready", "operation_failed", "operation_not_found", "profile_digest_mismatch", "profile_invalid",
    "profile_mismatch", "profile_not_found", "profile_retired", "rate_limited", "reconciliation_required",
    "request_too_large", "revision_conflict", "revision_sequence_regression", "sequence_regression",
    "service_unavailable", "source_revision_mismatch", "source_tombstoned", "source_too_large",
    "source_unavailable", "tokenization_failed", "traversal_limit_exceeded", "unsupported_media_type",
    "unsupported_policy", "unsupported_profile", "upstream_failure", "vector_dimension_mismatch",
}


class GatewayError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False):
        super().__init__(message)
        self.code = code if code in FAILURE_CODES else "dependency_unavailable"
        self.status = status
        self.retryable = retryable or status >= 500


class GatewayService:
    """Orchestrates domain services through REST; it does not import their runtimes."""

    def __init__(self, base_url: str | None = None, transport=None):
        self.base_url = (base_url or os.environ.get("CE_GATEWAY_INTERNAL_BASE_URL", "http://127.0.0.1:8080")).rstrip("/")
        self._transport = transport

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None,
              request_id: str = "gateway", headers: dict[str, str] | None = None,
              timeout: float = 30.0) -> tuple[int, dict[str, Any]]:
        extra = dict(headers or {})
        if self._transport is not None:
            return self._transport(method, path, payload, request_id, extra, timeout)
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request_headers = {
            "Accept": "application/json", "X-CE-Request-ID": request_id,
            "X-CE-Internal-Call": "true", "X-CE-Internal-Token": INTERNAL_CALL_TOKEN,
        }
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request_headers.update(extra)
        request = Request(self.base_url + path, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                decoded = json.loads(response.read().decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise GatewayError("dependency_unavailable", "service returned a non-object JSON response", 503, True)
                return response.status, decoded
        except HTTPError as exc:
            try:
                decoded = json.loads(exc.read().decode("utf-8"))
                error = decoded.get("error", {})
                code = error.get("code", "dependency_unavailable")
                message = error.get("message", "upstream request failed")
            except Exception:
                code, message = "dependency_unavailable", "upstream request failed"
            raise GatewayError(code, message, exc.code, exc.code >= 500) from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise GatewayError("dependency_unavailable", "upstream service is unavailable", 503, True) from exc

    @staticmethod
    def _query(query: dict[str, list[str]]) -> str:
        pairs = [(key, values[-1]) for key, values in query.items() if values]
        return "?" + urlencode(pairs) if pairs else ""

    def _write_profile(self, request_id: str, expected: dict[str, Any] | None = None, call=None) -> dict[str, Any]:
        call = call or self._call
        name = os.environ.get("CE_GATEWAY_WRITE_PROFILE_NAME", "")
        if not name:
            raise GatewayError("not_ready", "CE_GATEWAY_WRITE_PROFILE_NAME is not configured", 503, True)
        if expected is not None and expected.get("name") != name:
            raise GatewayError("profile_mismatch", "requested Index profile is not the configured write profile", 409)
        if expected is None:
            _, response = call("GET", f"/api/v1/index/profiles/{quote(name, safe='')}/current", request_id=request_id)
        else:
            version = expected.get("version")
            if not isinstance(version, str) or not version:
                raise GatewayError("invalid_request", "index_profile.version is required")
            _, response = call("GET", f"/api/v1/index/profiles/{quote(name, safe='')}/versions/{quote(version, safe='')}",
                                     request_id=request_id)
        bundle = response.get("bundle")
        if not isinstance(bundle, dict) or not all(isinstance(bundle.get(key), str) for key in ("name", "version", "digest")):
            raise GatewayError("profile_invalid", "Index did not return a valid immutable profile bundle", 503, True)
        if expected is not None and expected.get("digest") and expected["digest"] != bundle["digest"]:
            raise GatewayError("profile_digest_mismatch", "requested profile digest does not match the pinned bundle", 409)
        return {"name": bundle["name"], "version": bundle["version"], "digest": bundle["digest"], "bundle": bundle}

    def _active_generation(self, request_id: str, call=None) -> tuple[str, dict[str, Any], dict[str, Any]]:
        call = call or self._call
        _, active = call("GET", "/api/v1/index/generations/active", request_id=request_id)
        generation = active.get("generation_id")
        identity = active.get("index_profile")
        if not isinstance(generation, str) or not generation or not isinstance(identity, dict):
            raise GatewayError("not_ready", "Index has no usable active generation", 503, True)
        pinned = self._write_profile(request_id, identity, call=call)
        return generation, identity, pinned["bundle"]

    @staticmethod
    def _scope(value: Any) -> dict[str, str]:
        if (not isinstance(value, dict) or set(value) != {"type", "id", "visibility"}
                or value.get("type") not in {"user", "project", "shared", "global"}
                or value.get("visibility") not in {"private", "shared", "global"}
                or not isinstance(value.get("id"), str) or not 1 <= len(value["id"]) <= 256):
            raise GatewayError("invalid_scope", "scope must contain valid type, id, and visibility")
        return value

    @staticmethod
    def _exact_matches(text: str, identifiers: list[str]) -> list[str]:
        found = []
        for identifier in identifiers:
            start = 0
            while True:
                index = text.find(identifier, start)
                if index < 0:
                    break
                before = text[index - 1] if index else ""
                after_index = index + len(identifier)
                after = text[after_index] if after_index < len(text) else ""
                def word_char(char: str) -> bool:
                    if not char:
                        return False
                    category = unicodedata.category(char)
                    return category[0] in {"L", "M", "N"} or char in "_-."
                if not word_char(before) and not word_char(after):
                    found.append(identifier)
                    break
                start = index + 1
        return found

    def _fresh_candidates(self, candidates: list[dict[str, Any]], request_id: str,
                          reasons: list[str], failures: list[dict[str, Any]], call=None) -> list[dict[str, Any]]:
        call = call or self._call
        by_owner: dict[str, list[dict[str, Any]]] = {"memory": [], "knowledge": []}
        unsupported_owner_seen = False
        for candidate in candidates:
            source_id = candidate.get("source_id", "")
            owner = source_id.split(":", 1)[0] if isinstance(source_id, str) else ""
            if owner in by_owner:
                by_owner[owner].append({"source_id": source_id, "revision_sequence": candidate.get("revision_sequence")})
            else:
                unsupported_owner_seen = True
        if unsupported_owner_seen:
            reasons.append("unsupported_candidate_owner")
        status_by_identity: dict[tuple[str, int], str] = {}
        for owner, items in by_owner.items():
            unique = {(item["source_id"], item["revision_sequence"]) for item in items
                      if isinstance(item["source_id"], str) and type(item["revision_sequence"]) is int}
            if not unique:
                continue
            path = "/api/v1/memories/verify-revisions" if owner == "memory" else "/api/v1/knowledge/sources/verify-revisions"
            try:
                ordered = sorted(unique)
                for offset in range(0, len(ordered), 100):
                    batch = ordered[offset:offset + 100]
                    _, response = call("POST", path, {"items": [
                        {"source_id": source, "revision_sequence": sequence} for source, sequence in batch
                    ], "request_id": request_id}, request_id)
                    for result in response.get("results", []):
                        status_by_identity[(result.get("source_id"), result.get("requested_revision_sequence"))] = result.get("status")
            except GatewayError as exc:
                reasons.append("freshness_verification_degraded")
                failures.append({"service": owner, "code": exc.code, "retryable": exc.retryable})
        fresh = []
        stale_seen = False
        for candidate in candidates:
            source_id = candidate.get("source_id", "")
            owner = source_id.split(":", 1)[0]
            if owner not in by_owner:
                continue
            if any(f["service"] == owner for f in failures):
                continue
            state = status_by_identity.get((source_id, candidate.get("revision_sequence")))
            if state == "current":
                fresh.append(candidate)
            else:
                stale_seen = True
        if stale_seen:
            reasons.append("stale_candidates_filtered")
        return fresh

    def _wait_for_operation(self, operation_id: str, scope: dict[str, str], request_id: str,
                            call, deadline_at: datetime | None) -> None:
        """Enforce a read-your-writes barrier before starting retrieval."""
        match = re.fullmatch(r"(memory|knowledge):op:[A-Za-z0-9._~-]{1,128}", operation_id)
        if not match:
            raise GatewayError("invalid_request", "after_operation_id is invalid")
        owner = match.group(1)
        if owner == "memory":
            path = "/api/v1/memories/operations/" + quote(operation_id, safe=":")
            path += self._query({
                "scope_type": [scope["type"]], "scope_id": [scope["id"]],
                "visibility": [scope["visibility"]],
            })
        else:
            path = "/api/v1/knowledge/operations/" + quote(operation_id, safe=":")
        # Without an explicit caller deadline, bound the barrier to the hook's
        # 1.5-second budget rather than allowing a pending write to hang recall.
        local_deadline = time.monotonic() + 1.5 if deadline_at is None else None
        while True:
            remaining = (
                local_deadline - time.monotonic()
                if deadline_at is None
                else (deadline_at - datetime.now(timezone.utc)).total_seconds()
            )
            if remaining <= 0:
                raise GatewayError("deadline_exceeded", "after_operation_id is still pending at the request deadline", 504)
            _, status = call("GET", path, request_id=request_id, timeout=min(1.0, remaining))
            indexing_status = status.get("indexing_status")
            operation_status = status.get("status")
            if indexing_status == "indexed":
                return
            if operation_status in {"failed", "operation_failed"} or indexing_status in {"failed", "reconciliation_required"}:
                raise GatewayError("operation_failed", "after_operation_id did not reach indexed state", 409)
            time.sleep(min(0.05, max(0.0, remaining)))

    def search(self, request: Any, request_id: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        allowed = {"request_id", "query", "scope", "mode", "context_budget", "exact_identifiers", "limit", "after_operation_id"}
        required = {"query", "scope", "mode", "context_budget"}
        if not isinstance(request, dict) or set(request) - allowed or not required.issubset(request):
            raise GatewayError("invalid_request", "Gateway request has missing or unknown fields")
        query_text = request["query"]
        if not isinstance(query_text, str) or not 1 <= len(query_text) <= 16384:
            raise GatewayError("invalid_request", "query must contain 1 to 16384 characters")
        scope = self._scope(request["scope"])
        if request["mode"] not in {"prompt_recall", "interactive", "lookup"}:
            raise GatewayError("invalid_request", "mode is invalid")
        budget = request["context_budget"]
        if (not isinstance(budget, dict) or set(budget) != {"unit", "model", "max"}
                or budget.get("unit") != "provider_tokens" or not isinstance(budget.get("model"), str)
                or not 1 <= len(budget["model"]) <= 256 or type(budget.get("max")) is not int
                or not 1 <= budget["max"] <= 32000):
            raise GatewayError("invalid_request", "context_budget is invalid")
        limit = request.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GatewayError("invalid_request", "limit must be between 1 and 100")
        exact = request.get("exact_identifiers", [])
        if not isinstance(exact, list) or len(exact) > 32 or any(not isinstance(x, str) or not 1 <= len(x) <= 256 for x in exact):
            raise GatewayError("invalid_request", "exact_identifiers must contain at most 32 bounded strings")
        request_id = request.get("request_id") or request_id or uuid.uuid4().hex
        inbound_headers = {str(key).lower(): value for key, value in dict(headers or {}).items()}
        deadline = inbound_headers.get("x-ce-deadline")
        deadline_at = None
        if deadline is not None:
            try:
                if not isinstance(deadline, str) or not deadline.endswith("Z"):
                    raise ValueError("deadline must end in Z")
                deadline_at = datetime.fromisoformat(deadline[:-1] + "+00:00")
                if deadline_at.tzinfo != timezone.utc:
                    raise ValueError("deadline must be UTC")
            except (TypeError, ValueError) as exc:
                raise GatewayError("invalid_parameter", "X-CE-Deadline must be an RFC 3339 UTC timestamp ending in Z") from exc
        else:
            # Hook recall is tightly bounded; interactive/lookup API calls get
            # the documented five-second default unless the caller supplies less.
            request_budget_ms = 1500 if request["mode"] == "prompt_recall" else 5000
            deadline_at = datetime.now(timezone.utc) + timedelta(milliseconds=request_budget_ms)
            deadline = deadline_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")

        def request_call(method, path, payload=None, request_id=request_id, headers=None, timeout=30.0):
            extra = dict(headers or {})
            if deadline is not None:
                remaining = (deadline_at - datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    raise GatewayError("deadline_exceeded", "request deadline expired before a dependency call", 504)
                timeout = min(timeout, remaining)
                extra.setdefault("X-CE-Deadline", deadline)
            return self._call(method, path, payload, request_id, headers=extra, timeout=timeout)

        def stage_call(budget_ms: int):
            stage_deadline = time.monotonic() + budget_ms / 1000.0
            stage_deadline_at = datetime.now(timezone.utc) + timedelta(milliseconds=budget_ms)
            stage_header = stage_deadline_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            def call(method, path, payload=None, request_id=request_id, headers=None, timeout=30.0):
                remaining_stage = stage_deadline - time.monotonic()
                remaining_request = (deadline_at - datetime.now(timezone.utc)).total_seconds()
                remaining = min(remaining_stage, remaining_request)
                if remaining <= 0:
                    raise GatewayError("deadline_exceeded", "Gateway stage budget exhausted", 504)
                extra = dict(headers or {})
                extra["X-CE-Deadline"] = min(stage_deadline_at, deadline_at).isoformat(
                    timespec="milliseconds"
                ).replace("+00:00", "Z")
                return request_call(method, path, payload, request_id, extra, min(timeout, remaining))
            call.deadline = stage_deadline
            return call

        after_operation_id = request.get("after_operation_id")
        if after_operation_id is not None:
            if not isinstance(after_operation_id, str):
                raise GatewayError("invalid_request", "after_operation_id must be a string")
            self._wait_for_operation(after_operation_id, scope, request_id, request_call, deadline_at)
        planning_call = stage_call(100)
        generation, index_profile, bundle = self._active_generation(request_id, call=planning_call)
        reasons: list[str] = []
        failures: list[dict[str, Any]] = []
        intent = "general"
        entity_response: dict[str, Any] = {"entities": []}
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            intent_future = pool.submit(planning_call, "POST", "/api/v1/intent-classification/classify", {
                "request_id": request_id, "text": query_text,
                "profile": {"name": "default-intents", "version": "0.1"}, "allowed_intents": INTENTS,
            }, request_id)
            entity_future = pool.submit(planning_call, "POST", "/api/v1/entity-extraction/extract", {
                "request_id": request_id, "text": query_text,
                "profile": {"name": "technical-default", "version": "0.1"},
            }, request_id)
            try:
                _, response = intent_future.result(timeout=max(0, planning_call.deadline - time.monotonic()))
                results = response.get("results", [])
                if results and isinstance(results[0].get("intent"), str) and results[0]["intent"] in INTENTS:
                    intent = results[0]["intent"]
            except Exception as exc:
                intent_future.cancel()
                reasons.append("query_understanding_degraded")
                failures.append({"service": "intent-classification", "code": getattr(exc, "code", "deadline_exceeded" if isinstance(exc, FutureTimeoutError) else "dependency_unavailable"), "retryable": True})
            try:
                _, entity_response = entity_future.result(timeout=max(0, planning_call.deadline - time.monotonic()))
            except Exception as exc:
                entity_future.cancel()
                reasons.append("query_understanding_degraded")
                failures.append({"service": "entity-extraction", "code": getattr(exc, "code", "deadline_exceeded" if isinstance(exc, FutureTimeoutError) else "dependency_unavailable"), "retryable": True})
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        identifiers = list(dict.fromkeys(exact + [
            item.get("text") for item in entity_response.get("entities", [])
            if isinstance(item, dict) and item.get("exact") is True and isinstance(item.get("text"), str) and item.get("text")
        ]))[:32]
        lexical_profile = bundle.get("lexical", {})
        embedding_profile = bundle.get("embedding", {})
        if not isinstance(lexical_profile, dict) or not isinstance(embedding_profile, dict):
            raise GatewayError("profile_invalid", "active Index profile lacks retrieval components", 503, True)
        retrieval_requests = {
            "lexical": ("POST", "/api/v1/lexical-retrieval/search", {
                "request_id": request_id, "query_id": request_id, "scope": scope, "index_profile": index_profile,
                "lexical_profile": {"name": lexical_profile.get("profile"), "version": lexical_profile.get("version")},
                "limit": limit, "index_generation": generation, "query_text": query_text,
            }),
            "vector": ("POST", "/api/v1/vector-retrieval/search", {
                "request_id": request_id, "query_id": request_id, "scope": scope, "index_profile": index_profile,
                "embedding_profile": {"name": embedding_profile.get("profile"), "version": embedding_profile.get("version")},
                "limit": limit, "index_generation": generation, "query": {"text": query_text},
            }),
        }
        responses: dict[str, dict[str, Any]] = {}
        graph_response: dict[str, Any] | None = None
        graph_required = intent == "relationship_exploration"
        graph_mentions = list(dict.fromkeys(
            item.get("text") for item in entity_response.get("entities", [])
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text")
        ))[:16]
        if graph_required and not graph_mentions:
            reasons.append("graph_entity_extraction_unavailable")
            failures.append({"service": "graph", "code": "no_resolvable_entity_mentions", "retryable": False})
        retrieval_call = stage_call(350)
        graph_call = stage_call(250)
        pool = ThreadPoolExecutor(max_workers=3)
        try:
            futures = {name: pool.submit(retrieval_call, method, path, payload, request_id)
                       for name, (method, path, payload) in retrieval_requests.items()}
            graph_future = None
            if graph_required and graph_mentions:
                graph_future = pool.submit(graph_call, "POST", "/api/v1/graph/traversals", {
                    "request_id": request_id, "scope": scope, "entity_mentions": graph_mentions,
                    "direction": "both", "max_depth": 3, "max_visited_nodes": 500, "limit": 10,
                }, request_id)
            for name, future in futures.items():
                try:
                    _, responses[name] = future.result(timeout=max(0, retrieval_call.deadline - time.monotonic()))
                except (GatewayError, FutureTimeoutError) as exc:
                    future.cancel()
                    code = exc.code if isinstance(exc, GatewayError) else "deadline_exceeded"
                    retryable = exc.retryable if isinstance(exc, GatewayError) else True
                    reasons.append("lexical_degraded" if name == "lexical" else "vector_degraded")
                    failures.append({"service": "lexical-retrieval" if name == "lexical" else "vector-retrieval",
                                     "code": code, "message": str(exc), "retryable": retryable})
                    responses[name] = {"candidates": [], "truncated": False}
            if graph_future is not None:
                try:
                    _, graph_response = graph_future.result(timeout=max(0, graph_call.deadline - time.monotonic()))
                except (GatewayError, FutureTimeoutError) as exc:
                    graph_future.cancel()
                    code = exc.code if isinstance(exc, GatewayError) else "deadline_exceeded"
                    retryable = exc.retryable if isinstance(exc, GatewayError) else True
                    reasons.append("graph_degraded")
                    failures.append({"service": "graph", "code": code, "retryable": retryable})
                    failures.append({"service": "graph", "code": "required_evidence_unavailable",
                                     "retryable": False, "required": True})
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        all_candidates: list[dict[str, Any]] = []
        raw_by_path: dict[str, list[dict[str, Any]]] = {"lexical": [], "vector": []}
        for path, response in responses.items():
            for candidate in response.get("candidates", []):
                if not isinstance(candidate, dict):
                    continue
                c = dict(candidate)
                c["retrieval_source"] = path
                c["score_semantics"] = c.get("score_semantics") or ("bm25-v1" if path == "lexical" else f"vector-{responses[path].get('metric', 'cosine')}-v1")
                c["matched_exact_identifiers"] = self._exact_matches(c.get("text", ""), identifiers) if isinstance(c.get("text"), str) else []
                if "score" in c:
                    c["source_score"] = c["score"]
                elif "distance" in c:
                    c["source_score"] = c["distance"]
                c.setdefault("provenance", {})
                raw_by_path[path].append(c)
                all_candidates.append(c)
        if any(bool(response.get("truncated")) for response in responses.values()):
            reasons.append("candidate_pool_truncated")
        graph_supports: list[dict[str, Any]] = []
        if graph_response is not None:
            for evidence in graph_response.get("resolution_evidence", []):
                graph_supports.extend(evidence.get("supports", []))
            for path_item in graph_response.get("paths", []):
                for edge in path_item.get("edges", []):
                    graph_supports.extend(edge.get("supports", []))
        graph_support_keys = {
            (item.get("source_id"), item.get("revision_sequence"))
            for item in graph_supports
            if isinstance(item, dict) and isinstance(item.get("source_id"), str)
            and type(item.get("revision_sequence")) is int
        }
        # Text candidates and Graph supports share one canonical verification pass
        # and therefore one freshness-stage budget.
        freshness_call = stage_call(250)
        verified_all = self._fresh_candidates(
            all_candidates + graph_supports, request_id, reasons, failures, call=freshness_call
        )
        verified_keys = {
            (item.get("source_id"), item.get("revision_sequence"))
            for item in verified_all
            if (item.get("source_id"), item.get("revision_sequence")) in graph_support_keys
        }
        fresh = [item for item in verified_all if item.get("retrieval_source") in {"lexical", "vector"}]
        graph_context: list[str] = []
        if graph_response is not None:
            for evidence in graph_response.get("resolution_evidence", []):
                evidence["supports"] = [support for support in evidence.get("supports", [])
                                        if (support.get("source_id"), support.get("revision_sequence")) in verified_keys]
            verified_node_ids = {
                item.get("node_id") for item in graph_response.get("resolution_evidence", [])
                if item.get("supports")
            }
            verified_paths = []
            for path_item in graph_response.get("paths", []):
                node_ids = path_item.get("node_ids", [])
                edges = []
                valid = bool(node_ids) and node_ids[0] in verified_node_ids
                for edge in path_item.get("edges", []):
                    supports = [support for support in edge.get("supports", [])
                                if (support.get("source_id"), support.get("revision_sequence")) in verified_keys]
                    if not supports:
                        valid = False
                        break
                    edges.append({**edge, "supports": supports})
                if valid and edges:
                    verified_paths.append({**path_item, "edges": edges})
            graph_response["paths"] = verified_paths
            graph_response["resolution_evidence"] = [
                item for item in graph_response.get("resolution_evidence", []) if item.get("supports")
            ]
            for path_item in verified_paths:
                edge_descriptions = [
                    f"{edge['source_node_id']} -[{edge['relationship_type']}]-> {edge['target_node_id']}"
                    for edge in path_item["edges"]
                ]
                graph_context.append("Graph relationship: " + " ; ".join(edge_descriptions))
            if graph_response.get("truncated"):
                reasons.append("graph_results_truncated")
            if graph_required and not verified_paths:
                reasons.append("graph_required_evidence_unavailable")
                failures.append({"service": "graph", "code": "required_evidence_unavailable",
                                 "retryable": False, "required": True})
        fresh_by_path = {path: [c for c in fresh if c.get("retrieval_source") == path] for path in ("lexical", "vector")}
        partition = f"{scope['type']}:{scope['id']}:{scope['visibility']}"
        suffix = base64.urlsafe_b64encode(partition.encode("utf-8")).decode("ascii").rstrip("=")
        lists = []
        for path in ("lexical", "vector"):
            candidates = []
            for c in fresh_by_path[path][:100]:
                needed = {"source_id", "source_revision", "revision_sequence", "chunk_id", "chunker",
                          "retrieval_rank", "score_semantics", "text", "matched_exact_identifiers", "provenance"}
                if not needed.issubset(c):
                    continue
                selected = {key: c[key] for key in needed}
                if "retrieval_source" in c:
                    selected["retrieval_source"] = path
                if "source_score" in c:
                    selected["source_score"] = c["source_score"]
                candidates.append(selected)
            lists.append({"list_id": f"rl1:{path}:original:{suffix}", "retrieval_path": path,
                          "query_variant_id": "original", "scope_partition_id": partition, "candidates": candidates})
        ranking_call = stage_call(150)
        try:
            _, ranked_response = ranking_call("POST", "/api/v1/ranking/rank", {
                "request_id": request_id, "policy": {"name": "rrf-v1", "version": "1"},
                "exact_identifiers": identifiers, "lists": lists, "limit": limit,
            }, request_id)
            ranked = ranked_response.get("candidates", [])
        except GatewayError as exc:
            failures.append({"service": "ranking", "code": exc.code, "retryable": exc.retryable})
            reasons.append("ranking_degraded")
            ranked = []
        exact_ranked = [candidate for candidate in ranked if candidate.get("matched_exact_identifiers")]
        non_exact_ranked = [candidate for candidate in ranked if not candidate.get("matched_exact_identifiers")]
        rerank_input = non_exact_ranked[:20]
        non_reranked_tail = non_exact_ranked[20:]
        if rerank_input:
            rerank_candidates = [{
                "source_id": candidate["source_id"], "source_revision": candidate["source_revision"],
                "revision_sequence": candidate["revision_sequence"], "chunk_id": candidate["chunk_id"],
                "chunker": candidate["chunker"], "text": candidate["text"], "prior_rank": candidate["rank"],
                "prior_score": candidate["score"], "matched_exact_identifiers": [],
                "provenance": candidate.get("provenance", {}),
            } for candidate in rerank_input]
            try:
                reranking_call = stage_call(250)
                _, reranked_response = reranking_call("POST", "/api/v1/reranking/rerank", {
                    "request_id": request_id, "profile": {"name": "default-reranker", "version": "0.1"},
                    "query": query_text, "candidates": rerank_candidates, "limit": len(rerank_candidates),
                }, request_id)
                returned = reranked_response.get("candidates", [])
                if not isinstance(returned, list) or any(
                    not isinstance(candidate, dict) or not isinstance(candidate.get("chunker"), dict)
                    for candidate in returned
                ):
                    raise GatewayError("candidate_identity_conflict", "reranker returned malformed candidates", 502)
                expected = {(c["source_id"], c["revision_sequence"], c["chunk_id"],
                             c["chunker"]["profile"], c["chunker"]["version"]) for c in rerank_input}
                actual = {(c.get("source_id"), c.get("revision_sequence"), c.get("chunk_id"),
                           (c.get("chunker") or {}).get("profile"), (c.get("chunker") or {}).get("version"))
                          for c in returned}
                if actual != expected or len(returned) != len(rerank_input):
                    raise GatewayError("candidate_identity_conflict", "reranker changed or omitted candidate identity", 502)
                original = {(
                    c["source_id"], c["revision_sequence"], c["chunk_id"],
                    c["chunker"]["profile"], c["chunker"]["version"]
                ): c for c in rerank_input}
                ranked = exact_ranked + [original[(
                    c["source_id"], c["revision_sequence"], c["chunk_id"],
                    c["chunker"]["profile"], c["chunker"]["version"]
                )] for c in returned] + non_reranked_tail
            except GatewayError as exc:
                reasons.append("reranking_degraded")
                failures.append({"service": "reranking", "code": exc.code, "retryable": exc.retryable})
                ranked = exact_ranked + non_exact_ranked
        assembly_deadline = time.monotonic() + 0.100
        output_candidates = []
        context_parts = []
        used_tokens = 0
        context_truncated = False
        context_budget_truncated = False
        token_counting_method = "conservative_utf8_byte_upper_bound"
        token_count_fallback_reason = "no_configured_tokenizer"
        for candidate in ranked[:100]:
            if time.monotonic() >= assembly_deadline:
                context_truncated = True
                reasons.append("assembly_degraded")
                break
            text = candidate.get("text", "")
            context_fragment = f"[{candidate['source_id']}@{candidate['revision_sequence']}] {text}"
            prospective_context = "\n\n".join(context_parts + [context_fragment])
            estimate, token_counting_method, fallback_reason = count_context_tokens(
                prospective_context, budget["model"]
            )
            if fallback_reason is not None:
                token_count_fallback_reason = fallback_reason
            else:
                token_count_fallback_reason = None
            output_candidates.append({
                "source_id": candidate["source_id"], "source_revision": candidate["source_revision"],
                "revision_sequence": candidate["revision_sequence"], "chunk_id": candidate["chunk_id"],
                "chunker": candidate["chunker"], "text": text, "freshness": "verified_current",
                "rank": candidate["rank"], "score": candidate["score"],
                "score_semantics": candidate["score_semantics"], "evidence": candidate["evidence"],
                "provenance": candidate["provenance"],
                "matched_exact_identifiers": candidate.get("matched_exact_identifiers", []),
            })
            if estimate <= budget["max"]:
                context_parts.append(context_fragment)
                used_tokens = estimate
            else:
                context_truncated = True
                context_budget_truncated = True
        if graph_context and time.monotonic() >= assembly_deadline:
            context_truncated = True
            reasons.append("assembly_degraded")
        elif graph_context:
            graph_text = "\n".join(graph_context)
            prospective_context = "\n\n".join(context_parts + [graph_text])
            graph_estimate, graph_method, graph_fallback_reason = count_context_tokens(
                prospective_context, budget["model"]
            )
            if graph_method != token_counting_method:
                token_counting_method = graph_method
            if graph_fallback_reason is not None:
                token_count_fallback_reason = graph_fallback_reason
            if graph_estimate <= budget["max"]:
                context_parts.append(graph_text)
                used_tokens = graph_estimate
            else:
                context_truncated = True
                context_budget_truncated = True
        if context_budget_truncated:
            reasons.append(
                "token_budget_estimated"
                if token_counting_method != "configured_model_tokenizer"
                else "context_budget_truncated"
            )
        if ranked and not context_parts:
            reasons.append("context_assembly_failed")
        reasons = list(dict.fromkeys(reasons))[:20]
        failures = failures[:20]
        if failures and not output_candidates:
            status = "failed"
        elif reasons or failures:
            status = "partial"
        else:
            status = "complete"
        response = {
            "request_id": request_id, "status": status, "candidates": output_candidates,
            "context_budget": {
                "unit": "provider_tokens", "model": budget["model"], "max": budget["max"],
                "used": used_tokens, "counting_method": token_counting_method,
                "is_estimate": token_counting_method != "configured_model_tokenizer",
                "fallback_reason": token_count_fallback_reason,
            },
            "degraded": status != "complete", "degradation_reasons": reasons, "failures": failures,
            "plan": {"intent": intent, "variants_used": 1, "policy_version": "gateway-rag-v1",
                     "index_generation": generation, "index_profile": index_profile},
            "index_freshness": (
                "unknown" if ("freshness_verification_degraded" in reasons
                               or "stale_candidates_filtered" in reasons
                               or not all_candidates)
                else "current"
            ), "truncated": (
                context_truncated
                or any(bool(x.get("truncated")) for x in responses.values())
                or bool(graph_response and graph_response.get("truncated"))
            ),
        }
        if time.monotonic() > assembly_deadline:
            reasons.append("assembly_degraded")
            context_truncated = True
            response["status"] = "partial"
            response["degraded"] = True
            response["degradation_reasons"] = list(dict.fromkeys(reasons))[:20]
            response["truncated"] = True
        if context_parts:
            response["context"] = "\n\n".join(context_parts)[:65536]
        return response

    def handle(self, method: str, path: str, query: dict[str, list[str]], body: Any, headers: Any,
               request_id: str) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/api/v1/gateway/health":
            return 200, {"service": "gateway", "status": "alive", "request_id": request_id}
        if method == "GET" and path == "/api/v1/gateway/ready":
            try:
                self._active_generation(request_id)
                self._write_profile(request_id)
                return 200, {"service": "gateway", "status": "ready", "ready": True,
                             "checks": [{"name": "active_generation", "status": "ok"},
                                        {"name": "write_profile", "status": "ok"}], "request_id": request_id}
            except GatewayError as exc:
                return 503, {"service": "gateway", "status": "not_ready", "ready": False,
                             "checks": [{"name": "configuration", "status": "unavailable", "reason": exc.code}],
                             "request_id": request_id}
        if method == "GET" and path == "/api/v1/gateway/index/write-profile":
            return 200, self._write_profile(request_id)
        if method == "POST" and path == "/api/v1/requests":
            return 200, self.search(body, request_id, headers=headers)
        if method == "POST" and path == "/api/v1/selections":
            payload = dict(body or {})
            payload["request_id"] = payload.get("request_id", request_id)
            return self._call("POST", "/api/v1/thompson/selections", payload, request_id,
                              {"Idempotency-Key": headers.get("Idempotency-Key", "")})
        if method == "POST" and path == "/api/v1/outcomes":
            payload = dict(body or {})
            payload["request_id"] = payload.get("request_id", request_id)
            return self._call("POST", "/api/v1/learning/outcomes", payload, request_id,
                              {"Idempotency-Key": headers.get("Idempotency-Key", "")})
        raise GatewayError("endpoint_not_found", "Gateway endpoint not found", 404)
