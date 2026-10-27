"""Local CPU-only second-stage cross-encoder reranking for Claude Ensemble."""
from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

PROFILE_NAME = "default-reranker"
PROFILE_VERSION = "0.1"
EXPECTED_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
MAX_CANDIDATES = 20
MAX_QUERY_CHARS = 16_384
MAX_CANDIDATE_CHARS = 65_536
MAX_SEQUENCE_LENGTH = 512
BATCH_SIZE = 8


class RerankingError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _bounded_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RerankingError("invalid_request", f"{field} must be a non-empty string of at most {maximum} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RerankingError("invalid_request", f"{field} contains invalid Unicode") from exc
    return value


def _candidate_identity(candidate: dict[str, Any]) -> tuple[Any, ...]:
    chunker = candidate["chunker"]
    return (
        candidate["source_id"],
        -candidate["revision_sequence"],
        candidate["chunk_id"],
        chunker["profile"],
        chunker["version"],
    )


class RerankingEngine:
    """Rerank at most 20 candidates with a pre-provisioned local cross-encoder."""

    def __init__(self, *, model_path: str | None = None, model_id: str | None = None,
                 model_version: str | None = None, model: Any = None):
        self.model_path = model_path if model_path is not None else (
            os.environ.get("CE_RERANKING_MODEL_PATH")
            or str(Path.home() / ".FlossWare" / "models" / "ms-marco-MiniLM-L6-v2")
        )
        self.model_id = model_id or os.environ.get("CE_RERANKING_MODEL_ID") or EXPECTED_MODEL_ID
        self.model_version = model_version or os.environ.get("CE_RERANKING_MODEL_VERSION")
        self._model = model

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.model_path or not self.model_version or self.model_id != EXPECTED_MODEL_ID:
            raise RerankingError(
                "service_unavailable",
                "configure CE_RERANKING_MODEL_PATH, CE_RERANKING_MODEL_VERSION, and CE_RERANKING_MODEL_ID=cross-encoder/ms-marco-MiniLM-L6-v2",
                503,
            )
        path = Path(self.model_path).expanduser()
        if not path.is_dir():
            raise RerankingError("service_unavailable", "configured local reranking model directory does not exist", 503)
        try:
            # Import lazily so contract tests do not require ML dependencies.
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(
                str(path),
                device="cpu",
                max_length=MAX_SEQUENCE_LENGTH,
                local_files_only=True,
                trust_remote_code=False,
            )
            return self._model
        except Exception as exc:
            self._model = None
            raise RerankingError(
                "service_unavailable",
                "configured local reranking model could not be loaded offline",
                503,
            ) from exc

    def readiness(self) -> dict[str, Any]:
        try:
            self._load()
            return {
                "service": "reranking",
                "status": "ready",
                "ready": True,
                "checks": [
                    {"name": "local_cross_encoder", "status": "ok"},
                    {"name": "cpu_inference", "status": "ok"},
                    {"name": f"{PROFILE_NAME}@{PROFILE_VERSION}", "status": "ok"},
                ],
            }
        except RerankingError:
            return {
                "service": "reranking",
                "status": "not_ready",
                "ready": False,
                "checks": [
                    {"name": "local_cross_encoder", "status": "unavailable"},
                    {"name": "cpu_inference", "status": "not_ready"},
                    {"name": f"{PROFILE_NAME}@{PROFILE_VERSION}", "status": "not_ready"},
                ],
            }

    def rerank(self, request: Any) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) - {"request_id", "query", "profile", "candidates", "limit"}:
            raise RerankingError("invalid_request", "request must be an object with only documented fields")
        request_id = request.get("request_id", "reranking-request")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise RerankingError("invalid_request", "request_id must contain 1 to 128 characters")
        query = _bounded_text(request.get("query"), "query", MAX_QUERY_CHARS)
        profile = request.get("profile")
        if profile != {"name": PROFILE_NAME, "version": PROFILE_VERSION}:
            raise RerankingError("unsupported_profile", "reranking profile or version is not supported", 422)
        candidates = request.get("candidates")
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES:
            raise RerankingError("invalid_request", "candidates must contain between 1 and 20 items")
        limit = request.get("limit")
        if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
            raise RerankingError("invalid_request", "limit must be an integer between 1 and 20")

        validated: list[dict[str, Any]] = []
        identities: set[tuple[Any, ...]] = set()
        for index, raw in enumerate(candidates):
            allowed_candidate_fields = {
                "source_id", "source_revision", "revision_sequence", "chunk_id", "chunker",
                "text", "prior_rank", "prior_score", "matched_exact_identifiers", "provenance",
            }
            if not isinstance(raw, dict) or set(raw) - allowed_candidate_fields:
                raise RerankingError("invalid_request", f"candidates[{index}] must contain only documented fields")
            _bounded_text(raw.get("source_id"), f"candidates[{index}].source_id", 138)
            if not re.fullmatch(r"(memory|knowledge):[A-Za-z0-9._~-]{1,128}", raw["source_id"]):
                raise RerankingError("invalid_request", f"candidates[{index}].source_id is invalid")
            _bounded_text(raw.get("source_revision"), f"candidates[{index}].source_revision", 256)
            _bounded_text(raw.get("chunk_id"), f"candidates[{index}].chunk_id", 512)
            _bounded_text(raw.get("text"), f"candidates[{index}].text", MAX_CANDIDATE_CHARS)
            if type(raw.get("revision_sequence")) is not int or not 1 <= raw["revision_sequence"] <= 9007199254740991:
                raise RerankingError("invalid_request", f"candidates[{index}].revision_sequence is invalid")
            if type(raw.get("prior_rank")) is not int or not 1 <= raw["prior_rank"] <= 100:
                raise RerankingError("invalid_request", f"candidates[{index}].prior_rank is invalid")
            chunker = raw.get("chunker")
            if (not isinstance(chunker, dict) or set(chunker) != {"profile", "version"}
                    or not all(isinstance(chunker[k], str) and chunker[k] for k in ("profile", "version"))):
                raise RerankingError("invalid_request", f"candidates[{index}].chunker is invalid")
            if "prior_score" in raw and (
                    not isinstance(raw["prior_score"], (int, float))
                    or not math.isfinite(float(raw["prior_score"]))):
                raise RerankingError("invalid_request", f"candidates[{index}].prior_score is invalid")
            exact = raw.get("matched_exact_identifiers")
            if (not isinstance(exact, list) or len(exact) > 32
                    or any(not isinstance(value, str) or not value or len(value) > 256 for value in exact)):
                raise RerankingError("invalid_request", f"candidates[{index}].matched_exact_identifiers is invalid")
            if "provenance" in raw and not isinstance(raw["provenance"], dict):
                raise RerankingError("invalid_request", f"candidates[{index}].provenance must be an object")
            candidate = dict(raw)
            identity = _candidate_identity(candidate)
            if identity in identities:
                raise RerankingError("invalid_request", "candidate identity tuples must be unique")
            identities.add(identity)
            validated.append(candidate)

        model = self._load()
        pairs = [(query, candidate["text"]) for candidate in validated]
        try:
            raw_scores = model.predict(
                pairs,
                batch_size=min(BATCH_SIZE, len(pairs)),
                show_progress_bar=False,
            )
            scores = raw_scores.tolist() if hasattr(raw_scores, "tolist") else list(raw_scores)
            if len(scores) != len(validated):
                raise ValueError("cross-encoder returned an invalid score count")
        except Exception as exc:
            raise RerankingError("provider_unavailable", "local reranking inference failed", 503) from exc

        scored: list[dict[str, Any]] = []
        for candidate, raw_score in zip(validated, scores):
            if not isinstance(raw_score, (int, float)) or not math.isfinite(float(raw_score)):
                raise RerankingError("provider_unavailable", "local reranking model returned a non-finite score", 503)
            score = round(float(raw_score), 9)
            provenance = dict(candidate.get("provenance") or {})
            provenance.update({
                "reranker_profile": f"{PROFILE_NAME}@{PROFILE_VERSION}",
                "reranker_model_id": self.model_id or EXPECTED_MODEL_ID,
                "reranker_model_version": self.model_version or "injected-test-model",
                "reranker_sequence_length": MAX_SEQUENCE_LENGTH,
            })
            scored.append({
                "source_id": candidate["source_id"],
                "source_revision": candidate["source_revision"],
                "revision_sequence": candidate["revision_sequence"],
                "chunk_id": candidate["chunk_id"],
                "chunker": dict(candidate["chunker"]),
                "text": candidate["text"],
                "matched_exact_identifiers": list(candidate["matched_exact_identifiers"]),
                "score": score,
                "score_semantics": "cross-encoder-profile-score-v1",
                "evidence": {
                    "kind": "model-assessment",
                    "model_id": self.model_id or EXPECTED_MODEL_ID,
                    "model_version": self.model_version or "injected-test-model",
                    "sequence_length": MAX_SEQUENCE_LENGTH,
                    "scoring_policy": "cross-encoder-profile-score-v1",
                },
                "provenance": provenance,
                "_prior_rank": candidate["prior_rank"],
            })
        scored.sort(key=lambda c: (-c["score"], c["_prior_rank"], *_candidate_identity(c)))
        exact = [candidate for candidate in scored if candidate["matched_exact_identifiers"]]
        other = [candidate for candidate in scored if not candidate["matched_exact_identifiers"]]
        # Exact-identifier candidates are never dropped merely to satisfy limit.
        selected = exact + other[:max(0, limit - len(exact))]
        selected.sort(key=lambda c: (-c["score"], c["_prior_rank"], *_candidate_identity(c)))
        for rank, candidate in enumerate(selected, 1):
            candidate["rerank"] = rank
            candidate.pop("_prior_rank", None)
        return {
            "profile": dict(profile),
            "candidates": selected,
            "request_id": request_id,
        }


_engine: RerankingEngine | None = None


def get_engine() -> RerankingEngine:
    global _engine
    if _engine is None:
        _engine = RerankingEngine()
    return _engine


def reset_engine_for_tests() -> None:
    global _engine
    _engine = None
