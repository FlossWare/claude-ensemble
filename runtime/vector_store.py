"""Persistent ChromaDB vector storage for Index.

SQLite remains authoritative for revisions, scopes, and tombstones. Index
writes vector IDs synchronously and validates every query candidate against
SQLite before returning it. Older vectors may remain physically stored after
an update or tombstone, but cannot be returned unless SQLite still authorizes them.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Protocol


SUPPORTED_METRICS = {"cosine", "dot_product", "euclidean"}
MAX_QUERY_RESULTS = 1000


class VectorStoreError(RuntimeError):
    """A vector-store operation failed or returned incompatible data."""


class VectorStore(Protocol):
    def upsert(self, records: list[dict[str, Any]]) -> None: ...
    def query(self, query_vector: list[float], *, scope: dict[str, str],
              limit: int, metric: str, source_ids: list[str] | None = None,
              source_revisions: list[str] | None = None, filter_scope: bool = True) -> list[dict[str, Any]]: ...
    def delete_source(self, source_id: str) -> None: ...
    def list_ids(self) -> set[str]: ...


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def collection_name(profile_digest: str, generation_id: str, metric: str) -> str:
    """Return a stable, Chroma-compatible name isolated by profile and generation."""
    if not re.fullmatch(r"[0-9a-f]{64}", profile_digest):
        raise VectorStoreError("profile digest must be a lowercase SHA-256 digest")
    if not isinstance(generation_id, str) or not generation_id:
        raise VectorStoreError("generation_id is required")
    if metric not in SUPPORTED_METRICS:
        raise VectorStoreError("unsupported vector metric")
    generation_key = hashlib.sha256(generation_id.encode("utf-8")).hexdigest()[:20]
    name = f"ce-{profile_digest[:12]}-{generation_key}-{metric.replace('_', '-')}"
    if not 3 <= len(name) <= 63:
        raise VectorStoreError("generated collection name is outside Chroma limits")
    return name


def record_id(record: dict[str, Any]) -> str:
    """Stable upsert ID: a retry of the same generation/source revision/chunk replaces."""
    required = ("generation_id", "source_id", "revision_sequence", "chunk_id")
    if any(key not in record for key in required):
        raise VectorStoreError("vector record identity is incomplete")
    return hashlib.sha256(_canonical({key: record[key] for key in required})).hexdigest()


def _metadata(record: dict[str, Any]) -> dict[str, str | int]:
    required = (
        "generation_id", "profile_digest", "source_id", "source_revision",
        "revision_sequence", "chunk_id", "chunker_profile", "chunker_version",
        "embedding_model", "embedding_version", "embedding_dimensions",
    )
    if any(key not in record for key in required):
        raise VectorStoreError("vector record metadata is incomplete")
    scope = record.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"type", "id", "visibility"}:
        raise VectorStoreError("vector record scope is invalid")
    if any(not isinstance(scope[key], str) or not scope[key] for key in scope):
        raise VectorStoreError("vector record scope values must be non-empty strings")
    metadata: dict[str, str | int] = {}
    for key in required:
        value = record[key]
        if key in {"revision_sequence", "embedding_dimensions"}:
            if type(value) is not int or value < 1:
                raise VectorStoreError(f"{key} must be a positive integer")
        elif not isinstance(value, str) or not value:
            raise VectorStoreError(f"{key} must be a non-empty string")
        metadata[key] = value
    for key, value in scope.items():
        metadata[f"scope_{key}"] = value
    return metadata


def _where(scope: dict[str, str], source_ids: list[str] | None,
           source_revisions: list[str] | None) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [
        {f"scope_{key}": value} for key, value in sorted(scope.items())
    ]
    if source_ids:
        clauses.append({"source_id": {"$in": source_ids}})
    if source_revisions:
        clauses.append({"source_revision": {"$in": source_revisions}})
    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class ChromaVectorStore:
    """ChromaDB adapter for one profile/generation/metric collection.

    The caller must validate every returned candidate against SQLite-owned
    source revision and tombstone state before exposing it to retrieval clients.
    """

    def __init__(self, path: str | Path, *, profile_digest: str,
                 generation_id: str, metric: str, client: Any | None = None):
        if metric not in SUPPORTED_METRICS:
            raise VectorStoreError("unsupported vector metric")
        self.profile_digest = profile_digest
        self.generation_id = generation_id
        self.metric = metric
        self.name = collection_name(profile_digest, generation_id, metric)
        if client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise VectorStoreError(
                    "ChromaDB backend requested but chromadb is not installed"
                ) from exc
            client = chromadb.PersistentClient(path=str(Path(path).expanduser()))
        self._client = client
        space = {"cosine": "cosine", "dot_product": "ip", "euclidean": "l2"}[metric]
        try:
            self._collection = client.get_or_create_collection(
                name=self.name,
                metadata={"hnsw:space": space, "hnsw:search_ef": MAX_QUERY_RESULTS,
                          "ce:profile_digest": profile_digest,
                          "ce:generation_id": generation_id},
            )
        except Exception as exc:
            raise VectorStoreError("could not open Chroma collection") from exc

    def upsert(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        ids: list[str] = []
        documents: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, str | int]] = []
        for record in records:
            if record.get("generation_id") != self.generation_id:
                raise VectorStoreError("record generation does not match collection")
            if record.get("profile_digest") != self.profile_digest:
                raise VectorStoreError("record profile does not match collection")
            vector = record.get("embedding")
            text = record.get("text")
            if (not isinstance(vector, list) or not vector
                    or any(type(v) not in (int, float) or not math.isfinite(float(v)) for v in vector)):
                raise VectorStoreError("embedding must be a non-empty finite numeric vector")
            if not isinstance(text, str):
                raise VectorStoreError("record text must be a string")
            ids.append(record_id(record))
            documents.append(text)
            embeddings.append([float(v) for v in vector])
            metadatas.append(_metadata(record))
        if len(set(ids)) != len(ids):
            raise VectorStoreError("duplicate vector record identity in one upsert")
        try:
            self._collection.upsert(ids=ids, documents=documents,
                                    embeddings=embeddings, metadatas=metadatas)
        except Exception as exc:
            raise VectorStoreError("Chroma vector upsert failed") from exc

    def query(self, query_vector: list[float], *, scope: dict[str, str],
              limit: int, metric: str, source_ids: list[str] | None = None,
              source_revisions: list[str] | None = None, filter_scope: bool = True) -> list[dict[str, Any]]:
        if metric != self.metric:
            raise VectorStoreError("query metric does not match collection metric")
        if (type(limit) is not int or not 1 <= limit <= MAX_QUERY_RESULTS
                or not isinstance(query_vector, list) or not query_vector
                or any(type(v) not in (int, float) or not math.isfinite(float(v))
                       for v in query_vector)):
            raise VectorStoreError("query vector or limit is invalid")
        if set(scope) != {"type", "id", "visibility"} or any(
                not isinstance(v, str) or not v for v in scope.values()):
            raise VectorStoreError("query scope is invalid")
        for name, values in (("source_ids", source_ids), ("source_revisions", source_revisions)):
            if values is not None and (
                    not isinstance(values, list)
                    or any(not isinstance(value, str) or not value for value in values)):
                raise VectorStoreError(f"{name} filter is invalid")
        try:
            query_args = {
                "query_embeddings": [[float(v) for v in query_vector]],
                "n_results": limit,
                "include": ["metadatas", "documents", "distances"],
            }
            where = _where(scope if filter_scope else {}, source_ids, source_revisions)
            if where:
                query_args["where"] = where
            result = self._collection.query(**query_args)
        except Exception as exc:
            raise VectorStoreError("Chroma vector query failed") from exc
        ids = result.get("ids")
        metadata_rows = result.get("metadatas")
        document_rows = result.get("documents")
        distance_rows = result.get("distances")
        if not all(isinstance(v, list) and len(v) == 1 for v in
                   (ids, metadata_rows, document_rows, distance_rows)):
            raise VectorStoreError("Chroma returned a malformed query response")
        row_ids, metas, docs, distances = ids[0], metadata_rows[0], document_rows[0], distance_rows[0]
        if not (len(row_ids) == len(metas) == len(docs) == len(distances)):
            raise VectorStoreError("Chroma query result arrays have inconsistent lengths")
        candidates: list[dict[str, Any]] = []
        for item_id, meta, document, distance in zip(row_ids, metas, docs, distances):
            required_metadata = (
                "generation_id", "profile_digest", "source_id", "source_revision",
                "revision_sequence", "chunk_id", "chunker_profile", "chunker_version",
                "embedding_model", "embedding_version", "embedding_dimensions",
            )
            if (not isinstance(item_id, str) or not isinstance(meta, dict)
                    or any(key not in meta for key in required_metadata)
                    or not isinstance(document, str)):
                raise VectorStoreError("Chroma candidate metadata or document is malformed")
            if (meta.get("generation_id") != self.generation_id
                    or meta.get("profile_digest") != self.profile_digest):
                raise VectorStoreError("Chroma returned a candidate outside the requested generation/profile")
            # When scope filtering is disabled, the caller deliberately scans a
            # broader approximate-neighbor window and authorizes each candidate
            # against SQLite. Do not reject cross-scope rows here: that would
            # prevent the authoritative filter from discarding them and refilling
            # the window to find valid neighbors.
            if filter_scope and any(meta.get(f"scope_{key}") != value for key, value in scope.items()):
                raise VectorStoreError("Chroma returned a candidate outside the requested scope")
            if (not isinstance(meta["source_id"], str) or not meta["source_id"]
                    or not isinstance(meta["source_revision"], str)
                    or not isinstance(meta["chunk_id"], str)
                    or not isinstance(meta["chunker_profile"], str)
                    or not isinstance(meta["chunker_version"], str)
                    or not isinstance(meta["embedding_model"], str)
                    or not isinstance(meta["embedding_version"], str)
                    or type(meta["revision_sequence"]) is not int or meta["revision_sequence"] < 1
                    or type(meta["embedding_dimensions"]) is not int or meta["embedding_dimensions"] < 1):
                raise VectorStoreError("Chroma candidate identity metadata is invalid")
            if type(distance) not in (int, float) or not math.isfinite(float(distance)):
                raise VectorStoreError("Chroma returned an invalid distance")
            distance = float(distance)
            if self.metric == "cosine":
                score: dict[str, float] = {"similarity": 1.0 - distance}
            elif self.metric == "dot_product":
                score = {"similarity": 1.0 - distance}
            else:
                score = {"distance": math.sqrt(max(0.0, distance))}
            candidates.append({
                "vector_id": item_id,
                "source_id": meta["source_id"],
                "source_revision": meta["source_revision"],
                "revision_sequence": meta["revision_sequence"],
                "chunk_id": meta["chunk_id"],
                "chunker": {"profile": meta["chunker_profile"], "version": meta["chunker_version"]},
                "text": document,
                "embedding": {"model": meta["embedding_model"],
                              "version": meta["embedding_version"],
                              "dimensions": meta["embedding_dimensions"],
                              "metric": self.metric, "input_type": "document"},
                **score,
            })
        # Chroma's approximate HNSW traversal can return fewer than the
        # requested number of neighbors after a metadata filter, even when
        # matching vectors exist. For the SQLite-authorized source set, use an
        # exact metadata read as a bounded-recall fallback rather than silently
        # losing valid candidates behind orphaned or unrelated vectors.
        if source_ids and not filter_scope and len(candidates) < limit:
            try:
                exact = self._collection.get(
                    where=_where({}, source_ids, source_revisions),
                    include=["metadatas", "documents", "embeddings"],
                )
            except Exception as exc:
                raise VectorStoreError("Chroma exact candidate fallback failed") from exc
            exact_ids = exact.get("ids")
            exact_metas = exact.get("metadatas")
            exact_docs = exact.get("documents")
            exact_vectors = exact.get("embeddings")
            if hasattr(exact_vectors, "tolist"):
                exact_vectors = exact_vectors.tolist()
            if not all(isinstance(values, list) for values in
                       (exact_ids, exact_metas, exact_docs, exact_vectors)):
                raise VectorStoreError("Chroma exact fallback returned malformed arrays")
            if not (len(exact_ids) == len(exact_metas) == len(exact_docs) == len(exact_vectors)):
                raise VectorStoreError("Chroma exact fallback arrays have inconsistent lengths")
            exact_candidates = []
            query_norm = math.sqrt(sum(float(value) ** 2 for value in query_vector))
            for item_id, meta, document, stored_vector in zip(exact_ids, exact_metas, exact_docs, exact_vectors):
                required_metadata = (
                    "generation_id", "profile_digest", "source_id", "source_revision",
                    "revision_sequence", "chunk_id", "chunker_profile", "chunker_version",
                    "embedding_model", "embedding_version", "embedding_dimensions",
                )
                if (not isinstance(item_id, str) or not isinstance(meta, dict)
                        or any(key not in meta for key in required_metadata)
                        or not isinstance(document, str)):
                    raise VectorStoreError("Chroma exact fallback metadata or document is malformed")
                if (meta.get("generation_id") != self.generation_id
                        or meta.get("profile_digest") != self.profile_digest):
                    raise VectorStoreError("Chroma exact fallback returned a candidate outside the requested generation/profile")
                try:
                    values = [float(value) for value in stored_vector]
                except (TypeError, ValueError) as exc:
                    raise VectorStoreError("Chroma exact fallback returned an invalid embedding") from exc
                if (len(values) != len(query_vector)
                        or any(not math.isfinite(value) for value in values)
                        or not isinstance(meta.get("source_id"), str)
                        or not isinstance(meta.get("source_revision"), str)
                        or not isinstance(meta.get("chunk_id"), str)
                        or not isinstance(meta.get("chunker_profile"), str)
                        or not isinstance(meta.get("chunker_version"), str)
                        or not isinstance(meta.get("embedding_model"), str)
                        or not isinstance(meta.get("embedding_version"), str)
                        or type(meta.get("revision_sequence")) is not int
                        or type(meta.get("embedding_dimensions")) is not int):
                    raise VectorStoreError("Chroma exact fallback candidate identity or dimensions are invalid")
                dot = sum(float(query) * value for query, value in zip(query_vector, values))
                if self.metric == "cosine":
                    stored_norm = math.sqrt(sum(value * value for value in values))
                    similarity = dot / (query_norm * stored_norm) if query_norm and stored_norm else 0.0
                    score = {"similarity": similarity}
                elif self.metric == "dot_product":
                    score = {"similarity": dot}
                else:
                    score = {"distance": math.sqrt(sum((float(query) - value) ** 2
                                                       for query, value in zip(query_vector, values))}
                exact_candidates.append({
                    "vector_id": item_id,
                    "source_id": meta["source_id"],
                    "source_revision": meta["source_revision"],
                    "revision_sequence": meta["revision_sequence"],
                    "chunk_id": meta["chunk_id"],
                    "chunker": {"profile": meta["chunker_profile"], "version": meta["chunker_version"]},
                    "text": document,
                    "embedding": {"model": meta["embedding_model"],
                                  "version": meta["embedding_version"],
                                  "dimensions": meta["embedding_dimensions"],
                                  "metric": self.metric, "input_type": "document"},
                    **score,
                })
            exact_candidates.sort(key=lambda item: (
                item.get("distance", -item.get("similarity", 0.0)),
                item["source_id"], -item["revision_sequence"], item["chunk_id"],
                item["chunker"]["profile"], item["chunker"]["version"],
            ))
            candidates = exact_candidates[:limit]
        return candidates

    def replace_source(self, source_id: str, records: list[dict[str, Any]]) -> None:
        """Synchronously replace one source without deleting good vectors before upsert succeeds."""
        if not isinstance(source_id, str) or not source_id:
            raise VectorStoreError("source_id is required")
        if any(record.get("source_id") != source_id for record in records):
            raise VectorStoreError("all replacement records must belong to source_id")
        self.upsert(records)
        keep_ids = {record_id(record) for record in records}
        try:
            existing = self._collection.get(where={"source_id": source_id}, include=[])
            existing_ids = existing.get("ids")
            if not isinstance(existing_ids, list) or any(not isinstance(item, str) for item in existing_ids):
                raise VectorStoreError("Chroma returned a malformed source listing")
            stale_ids = [item for item in existing_ids if item not in keep_ids]
            if stale_ids:
                self._collection.delete(ids=stale_ids)
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError("Chroma source replacement cleanup failed") from exc

    def delete_source(self, source_id: str) -> None:
        if not isinstance(source_id, str) or not source_id:
            raise VectorStoreError("source_id is required")
        try:
            self._collection.delete(where={"source_id": source_id})
        except Exception as exc:
            raise VectorStoreError("Chroma source deletion failed") from exc

    def clear(self) -> None:
        """Remove all vector records before a simple SQLite-driven bootstrap rebuild."""
        ids = self.list_ids()
        if not ids:
            return
        try:
            self._collection.delete(ids=list(ids))
        except Exception as exc:
            raise VectorStoreError("Chroma collection clear failed") from exc

    def list_ids(self) -> set[str]:
        try:
            result = self._collection.get(include=[])
        except Exception as exc:
            raise VectorStoreError("Chroma collection enumeration failed") from exc
        ids = result.get("ids")
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            raise VectorStoreError("Chroma returned a malformed collection listing")
        return set(ids)
