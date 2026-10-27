"""Stateless lexical and vector retrieval algorithms for Claude Ensemble.

The services own retrieval scoring, not Index storage. Dependencies are supplied
as REST-call functions so tests can exercise the algorithms without persistence.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable


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
        n = int(corpus_statistics["N"])
        avgdl = float(corpus_statistics["avgdl"])
        dfs = corpus_statistics["df"]
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
        tf = c.get("term_frequencies")
        dl = c.get("document_length")
        if not isinstance(tf, dict) or type(dl) is not int or dl < 0:
            raise RetrievalError("dependency_unavailable", "Index candidate is missing term-frequency evidence", 503)
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
        candidate.pop("term_frequencies", None)
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
        if lookup.get("index_generation") != generation or lookup.get("index_profile") != index_profile:
            raise RetrievalError("profile_mismatch", "Index lookup returned a different pinned generation or profile", 409)
        stats = lookup.get("corpus_statistics", {})
        candidates = lookup.get("candidates", [])
        ranked = bm25_v1(terms, candidates, stats)
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
            raise RetrievalError("dependency_unavailable", f"Index candidate has invalid {value_key}", 503)
        c["distance"] = float(value)
    if metric == "euclidean":
        result.sort(key=lambda c: (c["distance"], *_identity(c)))
    else:
        result.sort(key=lambda c: (-c["distance"], *_identity(c)))
    for rank, candidate in enumerate(result, 1):
        candidate["retrieval_rank"] = rank
    return result


class VectorRetrievalService:
    """Orchestrates Embedding and Index through injected REST call functions."""

    def __init__(
        self,
        embed_call: Callable[[dict[str, Any]], dict[str, Any]],
        index_neighbors_call: Callable[[dict[str, Any]], dict[str, Any]],
        profile_resolve_call: Callable[[dict[str, Any]], dict[str, Any]],
    ):
        self._embed_call = embed_call
        self._index_neighbors_call = index_neighbors_call
        self._profile_resolve_call = profile_resolve_call

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
        metric = expected.get("metric")
        lookup = self._index_neighbors_call({
            "request_id": request_id, "scope": scope, "index_generation": generation,
            "index_profile": index_profile, "embedding_profile": embedding_profile,
            "model": model_id, "model_version": model_version, "dimensions": dimensions,
            "query_vector": query_vector, "metric": metric, "limit": limit,
            "source_ids": request.get("filters", {}).get("source_ids", []),
            "source_revisions": request.get("filters", {}).get("source_revisions", []),
        })
        if lookup.get("index_generation") != generation or lookup.get("index_profile") != index_profile:
            raise RetrievalError("profile_mismatch", "Index lookup returned a different pinned generation or profile", 409)
        if lookup.get("metric") != metric:
            raise RetrievalError("incompatible_representation", "Index returned a different vector metric", 422)
        candidates = vector_rank(lookup.get("candidates", []), metric)
        return {
            "query_id": query_id, "request_id": request_id, "index_generation": generation,
            "index_profile": index_profile, "embedding_profile": embedding_profile,
            "metric": metric, "candidates": candidates[:limit],
            "truncated": bool(lookup.get("truncated", False)),
        }
