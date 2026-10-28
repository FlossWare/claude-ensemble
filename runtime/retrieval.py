"""Stateless lexical and vector retrieval algorithms for Claude Ensemble.

The services own retrieval scoring, not Index storage. Dependencies are supplied
as REST-call functions so tests can exercise the algorithms without persistence.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Any, Callable, Iterable

from .internal_calls import INTERNAL_CALL_TOKEN


class RetrievalError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _string(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RetrievalError("invalid_request", f"{field} must be a non-empty string of at most {maximum} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RetrievalError("invalid_request", f"{field} contains invalid Unicode") from exc
    return value


def _identity(candidate: dict[str, Any]) -> tuple[Any, ...]:
    chunker = candidate.get("chunker") or {}
    return (
        candidate.get("source_id", ""),
        -int(candidate.get("revision_sequence", 0)),
        candidate.get("chunk_id", ""),
        chunker.get("profile", ""),
        chunker.get("version", ""),
    )


def _canonical_scope(scope: Any) -> dict[str, str]:
    if not isinstance(scope, dict) or set(scope) != {"type", "id", "visibility"}:
        raise RetrievalError("invalid_request", "scope must contain exactly type, id, and visibility")
    if scope["type"] not in {"user", "project", "shared", "global"}:
        raise RetrievalError("invalid_request", "scope.type is invalid")
    if scope["visibility"] not in {"private", "shared", "global"}:
        raise RetrievalError("invalid_request", "scope.visibility is invalid")
    _string(scope["id"], "scope.id", 256)
    return dict(scope)


def bm25_v1(
    query_terms: Iterable[str],
    candidates: list[dict[str, Any]],
    corpus_statistics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Score an Index shortlist with the documented deterministic bm25-v1 policy."""
    terms: list[str] = []
    seen: set[str] = set()
    for term in query_terms:
        if not isinstance(term, str) or not term:
            continue
        if term not in seen:
            seen.add(term)
            terms.append(term)
    if not terms:
        raise RetrievalError("invalid_request", "tokenization produced no searchable terms")

    try:
        n = int(corpus_statistics["document_count"])
        avgdl = float(corpus_statistics["average_document_length"])
        dfs = corpus_statistics["document_frequency"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RetrievalError("dependency_unavailable", "Index returned invalid lexical corpus statistics", 503) from exc
    if n < 0 or not math.isfinite(avgdl) or avgdl < 0 or not isinstance(dfs, dict):
        raise RetrievalError("dependency_unavailable", "Index returned invalid lexical corpus statistics", 503)
    if n == 0 or avgdl == 0:
        return []

    scored: list[dict[str, Any]] = []
    k1, b = 1.2, 0.75
    for raw in candidates:
        c = dict(raw)
        tf_items = c.get("term_frequency_evidence")
        dl = c.get("document_length")
        if not isinstance(tf_items, list) or type(dl) is not int or dl < 0:
            raise RetrievalError("dependency_unavailable", "Index candidate is missing term-frequency evidence", 503)
        tf = {item.get("term"): item.get("term_frequency") for item in tf_items if isinstance(item, dict)}
        score = 0.0
        matched: list[str] = []
        for term in terms:
            frequency = tf.get(term, 0)
            df = dfs.get(term, 0)
            if type(frequency) is not int or frequency < 0 or type(df) is not int or not 0 <= df <= n:
                raise RetrievalError("dependency_unavailable", "Index returned invalid term statistics", 503)
            if frequency:
                matched.append(term)
                idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
                denominator = frequency + k1 * (1.0 - b + b * dl / avgdl)
                if denominator:
                    score += idf * frequency * (k1 + 1.0) / denominator
        # Python round uses ties-to-even, matching the contract's score rounding.
        c["score"] = round(score, 9)
        c["score_semantics"] = "bm25-v1"
        c["matched_terms"] = matched
        scored.append(c)

    scored.sort(key=lambda c: (-c["score"], *_identity(c)))
    for rank, candidate in enumerate(scored, 1):
        candidate["retrieval_rank"] = rank
        candidate.pop("term_frequency_evidence", None)
        candidate.pop("document_length", None)
    return scored


class LexicalRetrievalService:
    """Orchestrates Tokenization and Index through injected REST call functions."""

    def __init__(
        self,
        tokenize_call: Callable[[dict[str, Any]], dict[str, Any]],
        index_lookup_call: Callable[[dict[str, Any]], dict[str, Any]],
        profile_resolve_call: Callable[[dict[str, Any]], dict[str, Any]],
    ):
        self._tokenize_call = tokenize_call
        self._index_lookup_call = index_lookup_call
        self._profile_resolve_call = profile_resolve_call

    def search(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise RetrievalError("invalid_request", "request must be an object")
        query_id = _string(request.get("query_id"), "query_id", 128)
        request_id = _string(request.get("request_id", query_id), "request_id", 128)
        query_text = _string(request.get("query_text"), "query_text", 8192)
        scope = _canonical_scope(request.get("scope"))
        index_profile = request.get("index_profile")
        lexical_profile = request.get("lexical_profile")
        generation = _string(request.get("index_generation"), "index_generation", 256)
        limit = request.get("limit")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise RetrievalError("invalid_request", "limit must be an integer between 1 and 100")
        for name, profile in (("index_profile", index_profile), ("lexical_profile", lexical_profile)):
            if not isinstance(profile, dict) or not isinstance(profile.get("name"), str) or not isinstance(profile.get("version"), str):
                raise RetrievalError("invalid_request", f"{name} identity is invalid")
        if not isinstance(index_profile.get("digest"), str) or len(index_profile["digest"]) != 64:
            raise RetrievalError("invalid_request", "index_profile.digest is invalid")

        pinned = self._profile_resolve_call({
            "index_profile": index_profile, "index_generation": generation, "scope": scope,
            "request_id": request_id,
        })
        bundle = pinned.get("profile_bundle", pinned)
        if bundle.get("digest") != index_profile["digest"] or bundle.get("name") != index_profile["name"] or bundle.get("version") != index_profile["version"]:
            raise RetrievalError("profile_mismatch", "resolved Index profile does not match the pinned identity", 409)
        expected_lexical = bundle.get("lexical", {})
        expected_tokenization = bundle.get("tokenization", {})
        if (expected_lexical.get("profile") != lexical_profile["name"]
                or expected_lexical.get("version") != lexical_profile["version"]):
            raise RetrievalError("unsupported_profile", "lexical profile does not match the pinned Index bundle", 422)

        tokenized = self._tokenize_call({
            "request_id": request_id, "index_profile": index_profile,
            "profile": expected_tokenization.get("profile"),
            "profile_version": expected_tokenization.get("version"),
            "text": query_text,
            "options": {"preserve_identifiers": True, "include_offsets": False, "include_normalized_terms": True},
        })
        if tokenized.get("index_profile") != index_profile:
            raise RetrievalError("profile_mismatch", "Tokenization returned a different Index profile", 409)
        if tokenized.get("profile") != expected_tokenization.get("profile") or tokenized.get("version") != expected_tokenization.get("version"):
            raise RetrievalError("incompatible_representation", "Tokenization returned an incompatible profile", 422)
        terms = [t.get("term") for t in tokenized.get("tokens", []) if isinstance(t, dict)]
        terms = [term for term in terms if isinstance(term, str) and term]
        if not terms:
            return {
                "query_id": query_id, "request_id": request_id, "index_generation": generation,
                "index_profile": index_profile, "lexical_profile": lexical_profile,
                "candidates": [], "truncated": False,
            }
        lookup_request = {
            "request_id": request_id, "scope": scope, "index_generation": generation,
            "index_profile": index_profile, "lexical_profile": lexical_profile, "terms": terms,
            "limit": limit, "source_ids": request.get("source_ids", []),
            "source_revisions": request.get("source_revisions", []),
        }
        lookup = self._index_lookup_call(lookup_request)
        if lookup.get("index_generation") != generation:
            raise RetrievalError("profile_mismatch", "Index lookup returned a different pinned generation", 409)
        stats = lookup.get("corpus_statistics", {})
        candidates = lookup.get("candidates", [])
        ranked = bm25_v1(terms, candidates, stats)
        for candidate in ranked:
            candidate["provenance"] = {
                "index_generation": generation,
                "index_profile_digest": index_profile["digest"],
                "lexical_profile": f"{lexical_profile['name']}@{lexical_profile['version']}",
                "retrieval_policy": "bm25-v1",
            }
        return {
            "query_id": query_id, "request_id": request_id, "index_generation": generation,
            "index_profile": index_profile, "lexical_profile": lexical_profile,
            "candidates": ranked[:limit], "truncated": bool(lookup.get("truncated", False)),
        }


def vector_rank(
    candidates: list[dict[str, Any]],
    metric: str,
) -> list[dict[str, Any]]:
    """Validate and deterministically rank Index vector-neighbor evidence."""
    if metric not in {"cosine", "dot_product", "euclidean"}:
        raise RetrievalError("incompatible_representation", "unsupported vector metric", 422)
    result = [dict(c) for c in candidates]
    for c in result:
        value = c.get("distance", c.get("similarity"))
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RetrievalError("dependency_unavailable", "Index candidate has invalid vector distance/similarity", 503)
        c["distance"] = float(value)
    if metric == "euclidean":
        result.sort(key=lambda c: (c["distance"], *_identity(c)))
    else:
        result.sort(key=lambda c: (-c["distance"], *_identity(c)))
    for rank, candidate in enumerate(result, 1):
        candidate["retrieval_rank"] = rank
        # The retrieval response schema is deliberately smaller than Index's
        # low-level representation; do not leak Index-only metadata.
        for key in ("similarity", "embedding", "term_frequency_evidence"):
            candidate.pop(key, None)
    return result


class VectorRetrievalService:
    """Orchestrates Embedding and Index through injected REST call functions."""

    def __init__(
        self,
        embed_call: Callable[[dict[str, Any]], dict[str, Any]],
        index_neighbors_call: Callable[[dict[str, Any]], dict[str, Any]],
        profile_resolve_call: Callable[[dict[str, Any]], dict[str, Any]],
        rerank_call: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self._embed_call = embed_call
        self._index_neighbors_call = index_neighbors_call
        self._profile_resolve_call = profile_resolve_call
        self._rerank_call = rerank_call

    def search(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise RetrievalError("invalid_request", "request must be an object")
        query_id = _string(request.get("query_id"), "query_id", 128)
        request_id = _string(request.get("request_id", query_id), "request_id", 128)
        generation = _string(request.get("index_generation"), "index_generation", 256)
        scope = _canonical_scope(request.get("scope"))
        index_profile = request.get("index_profile")
        embedding_profile = request.get("embedding_profile")
        limit = request.get("limit")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise RetrievalError("invalid_request", "limit must be an integer between 1 and 100")
        if not isinstance(index_profile, dict) or not isinstance(embedding_profile, dict):
            raise RetrievalError("invalid_request", "pinned Index and embedding profiles are required")
        if not isinstance(index_profile.get("digest"), str) or len(index_profile["digest"]) != 64:
            raise RetrievalError("invalid_request", "index_profile.digest is invalid")

        pinned = self._profile_resolve_call({
            "index_profile": index_profile, "index_generation": generation, "scope": scope,
            "request_id": request_id,
        })
        bundle = pinned.get("profile_bundle", pinned)
        if any(bundle.get(k) != index_profile.get(k) for k in ("name", "version", "digest")):
            raise RetrievalError("profile_mismatch", "resolved Index profile does not match the pinned identity", 409)
        expected = bundle.get("embedding", {})
        if expected.get("profile") != embedding_profile.get("name") or expected.get("version") != embedding_profile.get("version"):
            raise RetrievalError("unsupported_profile", "embedding profile does not match the pinned Index bundle", 422)
        query = request.get("query")
        if not isinstance(query, dict):
            raise RetrievalError("invalid_request", "query must be an object")
        if "text" in query:
            text = _string(query["text"], "query.text", 16384)
            embedded = self._embed_call({
                "request_id": request_id, "index_profile": index_profile,
                "profile": embedding_profile["name"], "profile_version": embedding_profile["version"],
                "inputs": [{"input_id": query_id, "input_type": "query", "text": text}],
                "normalize": "profile-default",
            })
            if embedded.get("index_profile") != index_profile or embedded.get("profile") != embedding_profile["name"] or embedded.get("profile_version") != embedding_profile["version"]:
                raise RetrievalError("profile_mismatch", "Embedding returned an incompatible profile", 409)
            matches = [x for x in embedded.get("results", []) if x.get("input_id") == query_id and x.get("status") == "complete"]
            if len(matches) != 1:
                raise RetrievalError("dependency_unavailable", "Embedding did not return a usable query vector", 503)
            query_vector = matches[0].get("vector")
            model = embedded.get("model", {})
            model_id = model.get("model_id")
            model_version = model.get("model_version")
            dimensions = model.get("dimensions")
        else:
            query_vector = query.get("vector")
            model_id, model_version, dimensions = query.get("model"), query.get("model_version"), query.get("dimensions")
            if query.get("input_type") != "query":
                raise RetrievalError("invalid_request", "provided vectors must explicitly declare input_type=query")
        if (not isinstance(query_vector, list) or not query_vector or type(dimensions) is not int
                or len(query_vector) != dimensions or not isinstance(model_id, str) or not isinstance(model_version, str)
                or any(not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in query_vector)):
            raise RetrievalError("incompatible_representation", "query vector/model/dimension metadata is invalid", 422)
        if (model_id != expected.get("model") or model_version != expected.get("model_version")
                or dimensions != expected.get("dimensions")):
            raise RetrievalError("incompatible_representation", "query embedding model/version/dimensions do not match the pinned Index profile", 422)
        metric = expected.get("metric")
        lookup = self._index_neighbors_call({
            "request_id": request_id, "scope": scope, "index_generation": generation,
            "index_profile": index_profile, "embedding_profile": embedding_profile,
            "input_type": "query", "query_vector": query_vector, "metric": metric, "limit": limit,
            "source_ids": request.get("filters", {}).get("source_ids", []),
        })
        if lookup.get("index_generation") != generation:
            raise RetrievalError("profile_mismatch", "Index lookup returned a different pinned generation", 409)
        candidates = vector_rank(lookup.get("candidates", []), metric)
        for candidate in candidates:
            candidate["provenance"] = {"index_generation": generation, "embedding_model": model_id, "embedding_model_version": model_version}
        response = {
            "query_id": query_id, "request_id": request_id, "index_generation": generation,
            "index_profile": index_profile, "embedding_profile": embedding_profile,
            "metric": metric, "candidates": candidates[:limit],
            "truncated": bool(lookup.get("truncated", False)),
        }
        rerank_query = query.get("text", request.get("rerank_query"))
        shortlist = candidates[:min(limit, 20)]
        if shortlist:
            if self._rerank_call is None:
                raise RetrievalError("dependency_unavailable", "reranking endpoint is required for vector retrieval", 503)
            rerank_query = _string(rerank_query, "rerank_query", 16384)
            rerank_request = {
                "request_id": request_id,
                "query": rerank_query,
                "profile": {"name": "default-reranker", "version": "0.1"},
                "limit": len(shortlist),
                "candidates": [{
                    "source_id": candidate.get("source_id"),
                    "source_revision": candidate.get("source_revision"),
                    "revision_sequence": candidate.get("revision_sequence"),
                    "chunk_id": candidate.get("chunk_id"),
                    "chunker": candidate.get("chunker"),
                    "text": candidate.get("text"),
                    "prior_rank": candidate.get("retrieval_rank"),
                    "prior_score": candidate.get("distance"),
                    "matched_exact_identifiers": candidate.get("matched_exact_identifiers", []),
                    "provenance": candidate.get("provenance", {}),
                } for candidate in shortlist],
            }
            reranked = self._rerank_call(rerank_request)
            expected_profile = {"name": "default-reranker", "version": "0.1"}
            if reranked.get("profile") != expected_profile or not isinstance(reranked.get("candidates"), list):
                raise RetrievalError("dependency_unavailable", "Reranking returned an invalid response contract", 503)
            reranked_candidates = reranked["candidates"]
            if len(reranked_candidates) > len(shortlist):
                raise RetrievalError("dependency_unavailable", "Reranking returned more candidates than requested", 503)
            original_by_id = {(c.get("source_id"), c.get("source_revision"), c.get("chunk_id")): c for c in shortlist}
            restored = []
            for item in reranked_candidates:
                if not isinstance(item, dict):
                    raise RetrievalError("dependency_unavailable", "Reranking returned an invalid candidate", 503)
                identity = (item.get("source_id"), item.get("source_revision"), item.get("chunk_id"))
                original = original_by_id.get(identity)
                if original is None:
                    raise RetrievalError("dependency_unavailable", "Reranking returned an unknown candidate identity", 503)
                merged = dict(original)
                merged["rerank_score"] = item.get("score")
                merged["rerank_rank"] = item.get("rerank")
                merged["score_semantics"] = item.get("score_semantics")
                merged["provenance"] = item.get("provenance", original["provenance"])
                restored.append(merged)
            response["candidates"] = restored
            response["reranking_profile"] = expected_profile
        return response



def _rest_json(base_url: str, path: str, *, payload: dict[str, Any] | None = None,
               request_id: str = "retrieval", timeout: float = 15.0,
               deadline: str | None = None) -> dict[str, Any]:
    """Call another CE logical service over REST with bounded deadline propagation."""
    if deadline is not None:
        try:
            if not deadline.endswith("Z"):
                raise ValueError("deadline must end in Z")
            deadline_at = datetime.fromisoformat(deadline[:-1] + "+00:00")
        except (TypeError, ValueError) as exc:
            raise RetrievalError("invalid_parameter", "X-CE-Deadline must be an RFC 3339 UTC timestamp ending in Z", 400) from exc
        remaining = (deadline_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            raise RetrievalError("deadline_exceeded", "request deadline expired before a dependency call", 504)
        timeout = min(timeout, remaining)
    body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json", "X-CE-Request-ID": request_id,
        "X-CE-Internal-Call": "true", "X-CE-Internal-Token": INTERNAL_CALL_TOKEN,
    }
    if deadline is not None:
        headers["X-CE-Deadline"] = deadline
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(base_url.rstrip("/") + path, data=body, headers=headers,
                      method="GET" if payload is None else "POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            detail = error_body.get("error", {})
            code = detail.get("code", "dependency_unavailable")
            message = detail.get("message", "CE dependency returned an HTTP error")
        except (ValueError, UnicodeDecodeError):
            code, message = "dependency_unavailable", "CE dependency returned an unreadable HTTP error"
        raise RetrievalError(code, message, exc.code) from exc
    except TimeoutError as exc:
        if deadline is not None:
            raise RetrievalError("deadline_exceeded", "dependency call exceeded the request deadline", 504) from exc
        raise RetrievalError("dependency_unavailable", "required CE REST dependency is unavailable", 503) from exc
    except (URLError, OSError, ValueError, UnicodeDecodeError) as exc:
        if deadline is not None and isinstance(getattr(exc, "reason", None), TimeoutError):
            raise RetrievalError("deadline_exceeded", "dependency call exceeded the request deadline", 504) from exc
        raise RetrievalError("dependency_unavailable", "required CE REST dependency is unavailable", 503) from exc
    if not isinstance(decoded, dict):
        raise RetrievalError("dependency_unavailable", "CE REST dependency returned a non-object response", 503)
    return decoded


def configured_retrieval_services(deadline: str | None = None) -> tuple[LexicalRetrievalService, VectorRetrievalService]:
    """Build retrieval services whose dependencies are addressed only over REST."""
    index_url = os.environ.get("CE_INDEX_BASE_URL", "http://127.0.0.1:8080")
    tokenization_url = os.environ.get("CE_TOKENIZATION_BASE_URL", "http://127.0.0.1:8080")
    embedding_url = os.environ.get("CE_EMBEDDING_BASE_URL", "http://127.0.0.1:8080")
    reranking_url = os.environ.get("CE_RERANKING_BASE_URL", "http://127.0.0.1:8080")

    def resolve(request: dict[str, Any]) -> dict[str, Any]:
        profile = request["index_profile"]
        response = _rest_json(
            index_url,
            f"/api/v1/index/profiles/{quote(profile['name'], safe='')}/versions/{quote(profile['version'], safe='')}",
            request_id=request.get("request_id", "retrieval"), deadline=deadline,
        )
        bundle = response.get("profile_bundle", response.get("bundle"))
        if bundle is None:
            bundle = response
        if bundle.get("name") != profile["name"] or bundle.get("version") != profile["version"] or bundle.get("digest") != profile["digest"]:
            raise RetrievalError("profile_mismatch", "Index profile registry did not return the exact pinned profile", 409)
        return {"profile_bundle": bundle}

    def tokenize_call(payload: dict[str, Any]) -> dict[str, Any]:
        return _rest_json(tokenization_url, "/api/v1/tokenization/lexical", payload=payload,
                          request_id=payload.get("request_id", "retrieval"), deadline=deadline)

    def embed_call(payload: dict[str, Any]) -> dict[str, Any]:
        return _rest_json(embedding_url, "/api/v1/embeddings", payload=payload,
                          request_id=payload.get("request_id", "retrieval"), deadline=deadline)

    def lexical_lookup(payload: dict[str, Any]) -> dict[str, Any]:
        return _rest_json(index_url, "/api/v1/index/lexical/lookup", payload=payload,
                          request_id=payload.get("request_id", "retrieval"), deadline=deadline)

    def vector_neighbors(payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload["input_type"] = "query"
        return _rest_json(index_url, "/api/v1/index/vector-neighbors", payload=payload,
                          request_id=payload.get("request_id", "retrieval"), deadline=deadline)

    def rerank_call(payload: dict[str, Any]) -> dict[str, Any]:
        return _rest_json(reranking_url, "/api/v1/reranking/rerank", payload=payload,
                          request_id=payload.get("request_id", "retrieval"), deadline=deadline)

    return (
        LexicalRetrievalService(tokenize_call, lexical_lookup, resolve),
        VectorRetrievalService(embed_call, vector_neighbors, resolve, rerank_call),
    )


def retrieval_readiness(service: str) -> dict[str, Any]:
    """Report readiness only when all required logical REST dependencies are ready."""
    if service not in {"lexical-retrieval", "vector-retrieval"}:
        raise ValueError("unknown retrieval service")
    index_url = os.environ.get("CE_INDEX_BASE_URL", "http://127.0.0.1:8080")
    tokenization_url = os.environ.get("CE_TOKENIZATION_BASE_URL", "http://127.0.0.1:8080")
    checks = []
    dependencies = [("index", index_url, "/api/v1/index/ready")]
    if service == "lexical-retrieval":
        dependencies.append(("tokenization", tokenization_url, "/api/v1/tokenization/ready"))
    else:
        embedding_url = os.environ.get("CE_EMBEDDING_BASE_URL", "http://127.0.0.1:8080")
        dependencies.append(("embedding", embedding_url, "/api/v1/embedding/ready"))
    for name, base_url, path in dependencies:
        try:
            response = _rest_json(base_url, path, request_id=f"{service}-readiness")
            ready = response.get("ready") is True and response.get("status") == "ready"
            checks.append({"name": name, "status": "ok" if ready else "not_ready"})
        except RetrievalError:
            checks.append({"name": name, "status": "unavailable"})
    ready = all(item["status"] == "ok" for item in checks)
    return {
        "service": service,
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "checks": checks,
    }
