"""Local CPU-only embedding generation for Claude Ensemble.

The model must already exist on disk. This module never resolves model IDs from
a remote registry and never downloads model files at runtime.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

PROFILE_NAME = "technical-default"
PROFILE_VERSION = "0.1"
EXPECTED_MODEL_ID = "nomic-ai/nomic-embed-text-v1.5"
EXPECTED_DIMENSIONS = 768
MAX_INPUTS = 64
MAX_TEXT_CHARS = 65_536
MAX_TEXT_BYTES = 262_144
MAX_DIMENSIONS = 4096


class EmbeddingError(ValueError):
    """An embedding request or local model cannot be processed."""

    def __init__(self, code: str, message: str, *, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def validate_index_profile(value: Any) -> dict[str, str]:
    """Validate and preserve Index identity without resolving a profile registry."""
    if not isinstance(value, dict) or set(value) != {"name", "version", "digest"}:
        raise EmbeddingError("invalid_parameter", "index_profile must contain name, version, and digest", status=400)
    name, version, digest = value["name"], value["version"], value["digest"]
    if not isinstance(name, str) or not 1 <= len(name) <= 128:
        raise EmbeddingError("invalid_parameter", "index_profile.name is invalid", status=400)
    if not isinstance(version, str) or not 1 <= len(version) <= 64:
        raise EmbeddingError("invalid_parameter", "index_profile.version is invalid", status=400)
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
        raise EmbeddingError("invalid_parameter", "index_profile.digest must be a 64-character hexadecimal digest", status=400)
    return {"name": name, "version": version, "digest": digest}


def validate_text(value: Any, field: str = "text") -> str:
    if not isinstance(value, str) or not value:
        raise EmbeddingError("invalid_parameter", f"{field} must be a non-empty string", status=400)
    if len(value) > MAX_TEXT_CHARS:
        raise EmbeddingError("source_too_large", f"{field} exceeds the character limit", status=413)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise EmbeddingError("invalid_parameter", f"{field} contains invalid Unicode", status=400) from exc
    if len(encoded) > MAX_TEXT_BYTES:
        raise EmbeddingError("source_too_large", f"{field} exceeds the UTF-8 byte limit", status=413)
    return value


class EmbeddingEngine:
    """One configured local sentence-transformer model, explicitly forced to CPU."""

    def __init__(self, *, model_path: str | None = None, model_id: str | None = None,
                 model_version: str | None = None, model: Any = None):
        self.model_path = model_path if model_path is not None else (
            os.environ.get("CE_EMBEDDING_MODEL_PATH")
            or str(Path.home() / ".FlossWare" / "models" / "nomic-embed-text-v1.5")
        )
        self.model_id = model_id or os.environ.get("CE_EMBEDDING_MODEL_ID") or EXPECTED_MODEL_ID
        self.model_version = model_version or os.environ.get("CE_EMBEDDING_MODEL_VERSION")
        self._model = model
        self._dimensions: int | None = None
        if model is not None:
            self._dimensions = self._read_dimensions(model)

    @staticmethod
    def _read_dimensions(model: Any) -> int:
        # Prefer the current API, retaining compatibility with older Sentence Transformers.
        getter = getattr(model, "get_embedding_dimension", None)
        if not callable(getter):
            getter = getattr(model, "get_sentence_embedding_dimension", None)
        dimensions = getter() if callable(getter) else None
        if type(dimensions) is not int or not 1 <= dimensions <= MAX_DIMENSIONS:
            raise EmbeddingError("service_unavailable", "local model has invalid or unknown embedding dimensions", status=503)
        return dimensions

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.model_path or not self.model_version or self.model_id != EXPECTED_MODEL_ID:
            raise EmbeddingError(
                "service_unavailable",
                "configure CE_EMBEDDING_MODEL_VERSION for the local Nomic profile; CE_EMBEDDING_MODEL_PATH and CE_EMBEDDING_MODEL_ID have supported defaults",
                status=503,
            )
        path = Path(self.model_path).expanduser()
        if not path.is_dir():
            raise EmbeddingError("service_unavailable", "configured local embedding model directory does not exist", status=503)
        try:
            # Import lazily so contract/unit tests do not require ML packages.
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                str(path),
                device="cpu",
                local_files_only=True,
                trust_remote_code=False,
            )
            self._dimensions = self._read_dimensions(self._model)
            if self._dimensions != EXPECTED_DIMENSIONS:
                raise EmbeddingError("service_unavailable", "configured model dimensions do not match the Nomic embedding profile", status=503)
            return self._model
        except EmbeddingError:
            self._model = None
            self._dimensions = None
            raise
        except Exception as exc:
            self._model = None
            self._dimensions = None
            # Do not include exception text; it can contain local paths or configuration.
            raise EmbeddingError("service_unavailable", "configured local embedding model could not be loaded offline", status=503) from exc

    def readiness(self) -> dict[str, Any]:
        try:
            self._load()
            return {
                "service": "embedding",
                "status": "ready",
                "ready": True,
                "checks": [
                    {"name": "local_model_files", "status": "ok"},
                    {"name": "cpu_inference", "status": "ok"},
                    {"name": f"{PROFILE_NAME}@{PROFILE_VERSION}", "status": "ok"},
                ],
            }
        except EmbeddingError as exc:
            return {
                "service": "embedding",
                "status": "not_ready",
                "ready": False,
                "checks": [
                    {"name": "local_model_files", "status": "not_ready", "code": exc.code},
                    {"name": "cpu_inference", "status": "not_ready", "code": exc.code},
                ],
            }

    def embed(self, inputs: list[dict[str, str]], normalization: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        model = self._load()
        if normalization == "profile-default":
            normalization = "l2"
        if not isinstance(normalization, str) or normalization not in {"none", "l2"}:
            raise EmbeddingError("invalid_parameter", "normalize must be profile-default, none, or l2", status=400)

        # The selected technical-default profile is Nomic Embed Text v1.5.
        # Nomic requires different task prefixes for retrieval queries and documents.
        texts = [
            ("search_query: " if item["input_type"] == "query" else "search_document: ") + item["text"]
            for item in inputs
        ]
        try:
            encoded = model.encode(
                texts,
                batch_size=min(32, len(texts)),
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
                device="cpu",
            )
            vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
            if len(texts) == 1 and vectors and isinstance(vectors[0], (int, float)):
                vectors = [vectors]
            if not isinstance(vectors, (list, tuple)) or len(vectors) != len(inputs):
                raise ValueError("model returned an invalid batch shape")
        except Exception as exc:
            results = [
                {"input_id": item["input_id"], "input_type": item["input_type"],
                 "status": "failed", "error_code": "model_inference_failed"}
                for item in inputs
            ]
            return self._model_metadata(normalization), results

        results: list[dict[str, Any]] = []
        for item, raw_vector in zip(inputs, vectors):
            try:
                vector = [float(value) for value in raw_vector]
                if len(vector) != self._dimensions or not vector or any(not math.isfinite(value) for value in vector):
                    raise ValueError("invalid vector")
                if normalization == "l2":
                    norm = math.sqrt(sum(value * value for value in vector))
                    if not math.isfinite(norm) or norm <= 0:
                        raise ValueError("zero or invalid vector norm")
                    vector = [value / norm for value in vector]
                results.append({
                    "input_id": item["input_id"],
                    "input_type": item["input_type"],
                    "status": "complete",
                    "vector": vector,
                    "dimensions": len(vector),
                })
            except (TypeError, ValueError, OverflowError):
                results.append({
                    "input_id": item["input_id"],
                    "input_type": item["input_type"],
                    "status": "failed",
                    "error_code": "invalid_model_vector",
                })
        return self._model_metadata(normalization), results

    def _model_metadata(self, normalization: str) -> dict[str, Any]:
        return {
            "provider": "local",
            "model_id": self.model_id or Path(self.model_path or "unconfigured-model").name,
            "model_version": self.model_version or "unconfigured",
            "dimensions": self._dimensions or 1,
            "normalization": normalization,
        }


_engine: EmbeddingEngine | None = None


def get_engine() -> EmbeddingEngine:
    global _engine
    if _engine is None:
        _engine = EmbeddingEngine()
    return _engine


def reset_engine_for_tests() -> None:
    """Reset the lazy singleton; intended for isolated tests only."""
    global _engine
    _engine = None
