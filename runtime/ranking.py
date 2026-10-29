"""Deterministic reciprocal-rank fusion for Claude Ensemble."""
from __future__ import annotations

import base64
import json
import math
import re
from typing import Any

POLICY_NAME = "rrf-v1"
POLICY_VERSION = "1"
SCORE_SCALE = 1_000_000_000_000
RRF_K = 60
MAX_LISTS = 20
MAX_CANDIDATES_PER_LIST = 100
MAX_OUTPUT = 100
SOURCE_ID = re.compile(r"^(memory|knowledge):[A-Za-z0-9._~-]{1,128}$")


class RankingError(ValueError):
    """A ranking request violates the v1 contract."""

    def __init__(self, code: str, message: str, *, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _object(value: Any, name: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not required.issubset(value) or not set(value).issubset(allowed):
        raise RankingError("invalid_candidate" if name.startswith("candidate") else "invalid_parameter",
                           f"{name} has missing, unknown, or invalid fields")
    return value


def _string(value: Any, name: str, maximum: int, *, minimum: int = 1) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise RankingError("invalid_candidate", f"{name} must be a string of {minimum} to {maximum} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RankingError("invalid_candidate", f"{name} contains invalid Unicode") from exc
    return value


def _candidate_key(candidate: dict[str, Any]) -> tuple[str, int, str, str, str]:
    chunker = candidate["chunker"]
    return (
        candidate["source_id"],
        candidate["revision_sequence"],
        candidate["chunk_id"],
        chunker["profile"],
        chunker["version"],
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _list_id(path: str, scope_id: str) -> str:
    suffix = base64.urlsafe_b64encode(scope_id.encode("utf-8")).decode("ascii").rstrip("=")
    return f"rl1:{path}:original:{suffix}"


def _validate_candidate(value: Any, exact_identifiers: set[str]) -> dict[str, Any]:
    allowed = {
        "source_id", "source_revision", "revision_sequence", "chunk_id", "chunker",
        "retrieval_source", "retrieval_rank", "source_score", "score_semantics", "text",
        "matched_exact_identifiers", "provenance",
    }
    required = {
        "source_id", "source_revision", "revision_sequence", "chunk_id", "chunker",
        "retrieval_rank", "score_semantics", "text", "matched_exact_identifiers", "provenance",
    }
    candidate = _object(value, "candidate", allowed, required)
    source_id = _string(candidate["source_id"], "candidate.source_id", 138)
    if not SOURCE_ID.fullmatch(source_id):
        raise RankingError("invalid_candidate", "candidate.source_id is invalid")
    _string(candidate["source_revision"], "candidate.source_revision", 256)
    sequence = candidate["revision_sequence"]
    if type(sequence) is not int or not 1 <= sequence <= 9_007_199_254_740_991:
        raise RankingError("invalid_candidate", "candidate.revision_sequence is invalid")
    _string(candidate["chunk_id"], "candidate.chunk_id", 512)
    chunker = _object(candidate["chunker"], "candidate.chunker", {"profile", "version"}, {"profile", "version"})
    _string(chunker["profile"], "candidate.chunker.profile", 128)
    _string(chunker["version"], "candidate.chunker.version", 64)
    rank = candidate["retrieval_rank"]
    if type(rank) is not int or not 1 <= rank <= 100:
        raise RankingError("invalid_candidate", "candidate.retrieval_rank must be between 1 and 100")
    if "retrieval_source" in candidate and (
        not isinstance(candidate["retrieval_source"], str)
        or candidate["retrieval_source"] not in {"lexical", "vector"}
    ):
        raise RankingError("invalid_candidate", "candidate.retrieval_source is invalid")
    if "source_score" in candidate:
        score = candidate["source_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise RankingError("invalid_candidate", "candidate.source_score must be finite")
    _string(candidate["score_semantics"], "candidate.score_semantics", 128)
    text = candidate["text"]
    if not isinstance(text, str) or len(text) > 65_536:
        raise RankingError("invalid_candidate", "candidate.text must be a string of at most 65536 characters")
    matched = candidate["matched_exact_identifiers"]
    if not isinstance(matched, list) or len(matched) > 32:
        raise RankingError("invalid_candidate", "candidate.matched_exact_identifiers must be a bounded array")
    if any(not isinstance(item, str) or not 1 <= len(item) <= 256 or item not in exact_identifiers for item in matched):
        raise RankingError("invalid_candidate", "matched exact identifiers must be members of request.exact_identifiers")
    provenance = candidate["provenance"]
    if not isinstance(provenance, dict):
        raise RankingError("invalid_candidate", "candidate.provenance must be an object")
    if "origin" in provenance and (not isinstance(provenance["origin"], str) or len(provenance["origin"]) > 2048):
        raise RankingError("invalid_candidate", "candidate.provenance.origin is invalid")
    if "evidence_ids" in provenance and (
        not isinstance(provenance["evidence_ids"], list) or len(provenance["evidence_ids"]) > 100
        or any(not isinstance(item, str) or len(item) > 512 for item in provenance["evidence_ids"])
    ):
        raise RankingError("invalid_candidate", "candidate.provenance.evidence_ids is invalid")
    try:
        _canonical_json(provenance)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RankingError("invalid_candidate", "candidate.provenance must contain finite JSON values") from exc
    return candidate


def rank(request: Any) -> dict[str, Any]:
    """Fuse bounded candidate lists using deterministic fixed-point RRF."""
    request = _object(request, "request", {"request_id", "policy", "exact_identifiers", "lists", "limit"},
                      {"request_id", "policy", "lists", "limit"})
    _string(request["request_id"], "request.request_id", 128)
    policy = _object(request["policy"], "policy", {"name", "version"}, {"name", "version"})
    if policy != {"name": POLICY_NAME, "version": POLICY_VERSION}:
        raise RankingError("unsupported_policy", "only rrf-v1 version 1 is supported", status=422)

    limit = request["limit"]
    if type(limit) is not int or not 1 <= limit <= MAX_OUTPUT:
        raise RankingError("invalid_parameter", "limit must be between 1 and 100")
    exact_values = request.get("exact_identifiers", [])
    if not isinstance(exact_values, list) or len(exact_values) > 32:
        raise RankingError("invalid_parameter", "exact_identifiers must contain at most 32 values")
    for item in exact_values:
        _string(item, "exact_identifiers[]", 256)
    exact_values = list(dict.fromkeys(exact_values))
    exact_set = set(exact_values)

    lists = request["lists"]
    if not isinstance(lists, list) or not 1 <= len(lists) <= MAX_LISTS:
        raise RankingError("invalid_parameter", "lists must contain between 1 and 20 ranked lists")
    seen_list_ids: set[str] = set()
    candidates: dict[tuple[str, int, str, str, str], dict[str, Any]] = {}

    for list_index, raw_list in enumerate(lists):
        ranked_list = _object(
            raw_list, f"lists[{list_index}]",
            {"list_id", "retrieval_path", "query_variant_id", "scope_partition_id", "candidates"},
            {"list_id", "retrieval_path", "query_variant_id", "scope_partition_id", "candidates"},
        )
        path = ranked_list["retrieval_path"]
        if not isinstance(path, str) or path not in {"lexical", "vector"}:
            raise RankingError("invalid_parameter", "retrieval_path must be lexical or vector")
        scope_id = _string(ranked_list["scope_partition_id"], "scope_partition_id", 256)
        if len(scope_id.encode("utf-8")) > 1024:
            raise RankingError("invalid_parameter", "scope_partition_id exceeds 1024 UTF-8 bytes")
        if ranked_list["query_variant_id"] != "original":
            raise RankingError("invalid_parameter", "query_variant_id must be original in v1")
        list_id = _string(ranked_list["list_id"], "list_id", 1400)
        if list_id in seen_list_ids:
            raise RankingError("duplicate_list_id", "list_id values must be unique")
        if list_id != _list_id(path, scope_id):
            raise RankingError("invalid_parameter", "list_id does not match the canonical v1 identity")
        seen_list_ids.add(list_id)
        raw_candidates = ranked_list["candidates"]
        if not isinstance(raw_candidates, list) or len(raw_candidates) > MAX_CANDIDATES_PER_LIST:
            raise RankingError("invalid_parameter", "each ranked list may contain at most 100 candidates")
        seen_ranks: set[int] = set()
        within_list: dict[tuple[str, int, str, str, str], dict[str, Any]] = {}
        for candidate_index, raw_candidate in enumerate(raw_candidates):
            candidate = _validate_candidate(raw_candidate, exact_set)
            if "retrieval_source" in candidate and candidate["retrieval_source"] != path:
                raise RankingError("invalid_candidate", "candidate retrieval_source does not match its ranked list")
            retrieval_rank = candidate["retrieval_rank"]
            if retrieval_rank in seen_ranks:
                raise RankingError("duplicate_retrieval_rank", "retrieval_rank values must be unique within a list")
            seen_ranks.add(retrieval_rank)
            key = _candidate_key(candidate)
            previous_in_list = within_list.get(key)
            if previous_in_list is None:
                within_list[key] = dict(candidate)
                continue
            if (previous_in_list["source_revision"] != candidate["source_revision"]
                    or previous_in_list["text"] != candidate["text"]
                    or _canonical_json(previous_in_list["provenance"]) != _canonical_json(candidate["provenance"])):
                raise RankingError("candidate_identity_conflict", "duplicate candidate identity has conflicting source data", status=409)
            merged_matches = list(dict.fromkeys(
                previous_in_list["matched_exact_identifiers"] + candidate["matched_exact_identifiers"]
            ))
            if retrieval_rank < previous_in_list["retrieval_rank"]:
                within_list[key] = dict(candidate)
            within_list[key]["matched_exact_identifiers"] = merged_matches

        for key, candidate in within_list.items():
            entry = candidates.get(key)
            if entry is None:
                entry = {
                    "source_id": candidate["source_id"],
                    "source_revision": candidate["source_revision"],
                    "revision_sequence": candidate["revision_sequence"],
                    "chunk_id": candidate["chunk_id"],
                    "chunker": dict(candidate["chunker"]),
                    "text": candidate["text"],
                    "provenance": dict(candidate["provenance"]),
                    "matched_exact_identifiers": set(),
                    "score": 0,
                    "evidence_bytes": set(),
                    "evidence": [],
                }
                candidates[key] = entry
            elif (entry["source_revision"] != candidate["source_revision"]
                  or entry["text"] != candidate["text"]):
                # Retrieval paths may attach different lineage metadata (for example,
                # the vector path records embedding model/generation). The canonical
                # source revision and chunk text must agree; retain the first path's
                # provenance while recording each path separately in ranking evidence.
                raise RankingError("candidate_identity_conflict", "duplicate candidate identity has conflicting source data", status=409)

            entry["matched_exact_identifiers"].update(candidate["matched_exact_identifiers"])
            contribution_rank = candidate["retrieval_rank"]
            entry["score"] += SCORE_SCALE // (RRF_K + contribution_rank)
            evidence: dict[str, Any] = {
                "list_id": list_id,
                "retrieval_path": path,
                "retrieval_rank": contribution_rank,
                "score_semantics": candidate["score_semantics"],
            }
            if "source_score" in candidate:
                evidence["source_score"] = candidate["source_score"]
            # Preserve retrieval-specific lineage without conflating it with the
            # canonical source provenance retained on the fused candidate.
            evidence["provenance"] = dict(candidate["provenance"])
            evidence_bytes = _canonical_json(evidence)
            if evidence_bytes not in entry["evidence_bytes"]:
                entry["evidence_bytes"].add(evidence_bytes)
                entry["evidence"].append((evidence_bytes, evidence))

    ordered = sorted(candidates.values(), key=lambda entry: (
        0 if entry["matched_exact_identifiers"] else 1,
        -entry["score"],
        entry["source_id"],
        -entry["revision_sequence"],
        entry["chunk_id"],
        entry["chunker"]["profile"],
        entry["chunker"]["version"],
    ))
    output: list[dict[str, Any]] = []
    for position, entry in enumerate(ordered[:limit], start=1):
        evidence = [item for _, item in sorted(entry["evidence"], key=lambda pair: pair[0])]
        output.append({
            "source_id": entry["source_id"],
            "source_revision": entry["source_revision"],
            "revision_sequence": entry["revision_sequence"],
            "chunk_id": entry["chunk_id"],
            "chunker": entry["chunker"],
            "rank": position,
            "score": entry["score"],
            "score_semantics": "rrf-v1-fixed-point-1e12",
            "evidence": evidence[:100],
            "provenance": entry["provenance"],
            "text": entry["text"],
            "matched_exact_identifiers": [value for value in exact_values if value in entry["matched_exact_identifiers"]],
        })
    return {"policy": {"name": POLICY_NAME, "version": POLICY_VERSION}, "score_scale": SCORE_SCALE, "candidates": output}
