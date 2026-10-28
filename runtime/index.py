"""Durable local Index runtime for bounded lexical/vector retrieval.

Index owns derived representations and tombstones. It never calls Memory,
Knowledge, or retrieval services; all callers use this module through REST.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote, parse_qs
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def profile_digest(bundle: dict[str, Any]) -> str:
    covered = {key: value for key, value in bundle.items() if key not in {"digest", "status"}}
    return hashlib.sha256(_canonical(covered)).hexdigest()


def _error(code: str, message: str, status: int = 400) -> "IndexError":
    return IndexError(code, message, status)


class IndexError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class IndexService:
    """SQLite-backed Index operations, independently testable without HTTP."""

    def __init__(self, db_path: str | os.PathLike[str], profile_bundle: dict[str, Any] | None = None):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        Path(self.db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if profile_bundle is not None:
            self.provision_profile(profile_bundle)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profiles(
                    name TEXT NOT NULL, version TEXT NOT NULL, digest TEXT NOT NULL,
                    bundle_json TEXT NOT NULL, PRIMARY KEY(name, version)
                );
                CREATE TABLE IF NOT EXISTS generations(
                    generation_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                    profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
                    profile_digest TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS active_generation(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS representations(
                    generation_id TEXT NOT NULL, source_id TEXT NOT NULL,
                    source_revision TEXT NOT NULL, revision_sequence INTEGER NOT NULL,
                    scope_json TEXT NOT NULL, chunk_id TEXT NOT NULL,
                    chunker_profile TEXT NOT NULL, chunker_version TEXT NOT NULL,
                    text TEXT NOT NULL, lexical_profile TEXT, lexical_version TEXT,
                    terms_json TEXT NOT NULL, vector_json TEXT,
                    embedding_model TEXT, embedding_version TEXT, embedding_dimensions INTEGER,
                    metadata_json TEXT NOT NULL, PRIMARY KEY(generation_id,source_id,revision_sequence,chunk_id)
                );
                CREATE INDEX IF NOT EXISTS representations_scope ON representations(generation_id,scope_json);
                CREATE INDEX IF NOT EXISTS representations_source ON representations(source_id,revision_sequence);
                CREATE TABLE IF NOT EXISTS tombstones(
                    source_id TEXT PRIMARY KEY, tombstone_sequence INTEGER NOT NULL,
                    source_revision TEXT NOT NULL, scope_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sources(
                    source_id TEXT PRIMARY KEY, latest_sequence INTEGER NOT NULL,
                    indexed_sequence INTEGER NOT NULL, scope_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations(
                    operation_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL, status TEXT NOT NULL, response_json TEXT NOT NULL,
                    safe_error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS owner_checkpoints(
                    generation_id TEXT NOT NULL, owner TEXT NOT NULL, applied_sequence INTEGER NOT NULL,
                    PRIMARY KEY(generation_id,owner)
                );
                CREATE TABLE IF NOT EXISTS owner_fences(
                    generation_id TEXT NOT NULL, owner TEXT NOT NULL, fence_id TEXT NOT NULL,
                    fence_token TEXT NOT NULL, sealed_sequence INTEGER NOT NULL,
                    expires_at TEXT NOT NULL, state TEXT NOT NULL,
                    PRIMARY KEY(generation_id,owner,fence_id)
                );
            """)

    @staticmethod
    def _validate_profile(bundle: Any) -> dict[str, Any]:
        if not isinstance(bundle, dict):
            raise _error("invalid_request", "profile_bundle must be an object")
        required = {"name", "version", "status", "chunking", "tokenization", "lexical", "embedding", "limits", "digest"}
        if set(bundle) != required:
            raise _error("invalid_request", "profile_bundle has missing or unknown fields")
        if not isinstance(bundle["name"], str) or not bundle["name"] or not isinstance(bundle["version"], str) or not bundle["version"]:
            raise _error("invalid_request", "profile name/version are required")
        digest = bundle["digest"]
        if not isinstance(digest, str) or len(digest) != 64 or profile_digest(bundle) != digest.lower():
            raise _error("profile_digest_mismatch", "profile bundle digest does not match canonical content", 409)
        if bundle["status"] not in {"active", "deprecated", "retired"}:
            raise _error("invalid_request", "profile status is invalid")
        embedding = bundle["embedding"]
        limits = bundle["limits"]
        lexical = bundle["lexical"]
        if not isinstance(embedding, dict) or type(embedding.get("dimensions")) is not int or embedding["dimensions"] < 1:
            raise _error("invalid_request", "profile embedding dimensions are invalid")
        if not isinstance(lexical, dict) or not isinstance(limits, dict):
            raise _error("invalid_request", "profile lexical/limits sections are invalid")
        if limits.get("max_chunks", 0) * limits.get("max_chunk_representation_bytes", 0) + limits.get("max_envelope_bytes", 0) > limits.get("max_request_bytes", 0):
            raise _error("invalid_request", "profile size limits are inconsistent")
        return bundle

    def provision_profile(self, bundle: dict[str, Any]) -> None:
        bundle = self._validate_profile(bundle)
        encoded = _canonical(bundle).decode("utf-8")
        with self._lock, self._connect() as db:
            old = db.execute("SELECT digest FROM profiles WHERE name=? AND version=?", (bundle["name"], bundle["version"])).fetchone()
            if old and old["digest"] != bundle["digest"]:
                raise _error("profile_mismatch", "an immutable profile version cannot be changed", 409)
            db.execute("INSERT OR IGNORE INTO profiles(name,version,digest,bundle_json) VALUES(?,?,?,?)",
                       (bundle["name"], bundle["version"], bundle["digest"], encoded))
            active = db.execute("SELECT generation_id FROM active_generation LIMIT 1").fetchone()
            if not active:
                generation_id = "gen-" + uuid.uuid4().hex
                db.execute("INSERT INTO generations(generation_id,status,profile_name,profile_version,profile_digest) VALUES(?,?,?,?,?)",
                           (generation_id, "active", bundle["name"], bundle["version"], bundle["digest"]))
                db.execute("INSERT INTO active_generation(singleton,generation_id) VALUES(1,?)", (generation_id,))

    def _profile(self, db: sqlite3.Connection, identity: Any) -> tuple[dict[str, Any], sqlite3.Row]:
        if not isinstance(identity, dict) or not all(isinstance(identity.get(k), str) for k in ("name", "version", "digest")):
            raise _error("invalid_request", "pinned index_profile is required")
        row = db.execute("SELECT * FROM profiles WHERE name=? AND version=?", (identity["name"], identity["version"])).fetchone()
        if not row:
            raise _error("profile_not_found", "pinned Index profile version is not provisioned", 404)
        if row["digest"] != identity["digest"]:
            raise _error("profile_mismatch", "pinned Index profile digest does not match", 409)
        return json.loads(row["bundle_json"]), row

    def _generation(self, db: sqlite3.Connection, generation_id: str | None, identity: dict[str, Any]) -> sqlite3.Row:
        if generation_id is None:
            active = db.execute("SELECT generation_id FROM active_generation WHERE singleton=1").fetchone()
            if not active:
                raise _error("not_ready", "no active Index generation is provisioned", 503)
            generation_id = active["generation_id"]
        generation = db.execute("SELECT * FROM generations WHERE generation_id=?", (generation_id,)).fetchone()
        if not generation:
            raise _error("generation_not_found", "Index generation was not found", 404)
        if generation["profile_digest"] != identity["digest"]:
            raise _error("profile_mismatch", "generation and pinned Index profile differ", 409)
        if generation["status"] not in {"active", "building", "eligible"}:
            raise _error("generation_not_found", "generation is not queryable", 409)
        return generation

    @staticmethod
    def _scope(scope: Any) -> str:
        if not isinstance(scope, dict) or not all(isinstance(scope.get(k), str) and scope[k] for k in ("type", "id", "visibility")):
            raise _error("invalid_request", "canonical scope partition is required")
        return _canonical({k: scope[k] for k in ("type", "id", "visibility")}).decode("utf-8")

    def _check_representation(self, rep: Any, bundle: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(rep, dict) or not isinstance(rep.get("chunk_id"), str) or not rep["chunk_id"]:
            raise _error("invalid_request", "representation chunk_id is required")
        if not isinstance(rep.get("text"), str) or not rep["text"]:
            raise _error("invalid_request", "representation text is required")
        chunker = rep.get("chunker")
        if not isinstance(chunker, dict) or not chunker.get("profile") or not chunker.get("version"):
            raise _error("invalid_request", "representation chunker profile/version is required")
        terms = []
        lexical = rep.get("lexical")
        if lexical is not None:
            if lexical.get("profile") != bundle["lexical"].get("profile") or lexical.get("version") != bundle["lexical"].get("version"):
                raise _error("incompatible_representation", "lexical representation does not match pinned profile", 422)
            terms = lexical.get("terms", [])
            if not isinstance(terms, list) or any(not isinstance(t, str) or not t for t in terms):
                raise _error("invalid_request", "lexical terms are invalid")
        vector = rep.get("vector")
        if vector is not None:
            emb = bundle["embedding"]
            if vector.get("input_type") != "document" or vector.get("model") != emb.get("model") or vector.get("version") != emb.get("model_version") or vector.get("dimensions") != emb.get("dimensions"):
                raise _error("incompatible_representation", "vector model, version, dimensions, or input type does not match pinned profile", 422)
            values = vector.get("values")
            if not isinstance(values, list) or len(values) != emb["dimensions"] or any(not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in values):
                raise _error("incompatible_representation", "vector values are invalid", 422)
        elif bundle["embedding"].get("required"):
            raise _error("incompatible_representation", "pinned profile requires a vector representation", 422)
        if lexical is None and bundle.get("lexical", {}).get("required", True):
            raise _error("incompatible_representation", "pinned profile requires a lexical representation", 422)
        metadata = rep.get("metadata", {})
        if not isinstance(metadata, dict):
            raise _error("invalid_request", "representation metadata must be an object")
        return {"chunk_id": rep["chunk_id"], "chunker": chunker, "text": rep["text"],
                "terms": terms, "lexical": lexical, "vector": vector, "metadata": metadata}

    def upsert(self, request: dict[str, Any], idempotency_key: str) -> tuple[int, dict[str, Any]]:
        if not idempotency_key:
            raise _error("invalid_request", "Idempotency-Key header is required")
        source = request.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("source_id"), str) or not isinstance(source.get("revision"), str) or type(source.get("revision_sequence")) is not int or source["revision_sequence"] < 1:
            raise _error("invalid_request", "source identity, revision, and positive revision_sequence are required")
        source_id = source["source_id"]
        if not (source_id.startswith("memory:") or source_id.startswith("knowledge:")):
            raise _error("invalid_request", "source_id must have a canonical owner prefix")
        scope_json = self._scope(source.get("scope"))
        if not isinstance(request.get("operation_id"), str) or not request["operation_id"]:
            raise _error("invalid_request", "operation_id is required")
        reps = request.get("representations")
        if not isinstance(reps, list) or not 1 <= len(reps) <= 256:
            raise _error("invalid_request", "representations must contain 1 to 256 items")
        payload_hash = hashlib.sha256(_canonical(request)).hexdigest()
        with self._lock, self._connect() as db:
            prior = db.execute("SELECT * FROM operations WHERE operation_id=? OR idempotency_key=?", (request["operation_id"], idempotency_key)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash or prior["idempotency_key"] != idempotency_key or prior["operation_id"] != request["operation_id"]:
                    raise _error("idempotency_conflict", "operation identity was reused with different content", 409)
                return 200, json.loads(prior["response_json"])
            bundle, _ = self._profile(db, request.get("index_profile"))
            target = request.get("target_generation")
            gen = self._generation(db, target, request["index_profile"])
            tomb = db.execute("SELECT tombstone_sequence FROM tombstones WHERE source_id=?", (source_id,)).fetchone()
            seq = source["revision_sequence"]
            if tomb and seq <= tomb["tombstone_sequence"]:
                raise _error("revision_sequence_regression", "upsert is at or below the durable tombstone sequence", 409)
            old = db.execute("SELECT latest_sequence FROM sources WHERE source_id=?", (source_id,)).fetchone()
            if old and seq <= old["latest_sequence"]:
                raise _error("revision_sequence_regression", "a source revision sequence must strictly increase for a new operation", 409)
            validated = [self._check_representation(rep, bundle) for rep in reps]
            db.execute("DELETE FROM representations WHERE generation_id=? AND source_id=? AND revision_sequence<?",
                       (gen["generation_id"], source_id, seq))
            for rep in validated:
                lexical = rep["lexical"] or {}
                vector = rep["vector"] or {}
                db.execute("""INSERT OR REPLACE INTO representations
                    (generation_id,source_id,source_revision,revision_sequence,scope_json,chunk_id,
                     chunker_profile,chunker_version,text,lexical_profile,lexical_version,terms_json,
                     vector_json,embedding_model,embedding_version,embedding_dimensions,metadata_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (gen["generation_id"], source_id, source["revision"], seq, scope_json, rep["chunk_id"],
                     rep["chunker"]["profile"], rep["chunker"]["version"], rep["text"],
                     lexical.get("profile"), lexical.get("version"), _canonical(rep["terms"]).decode(),
                     _canonical(vector.get("values")).decode() if vector else None,
                     vector.get("model"), vector.get("version"), vector.get("dimensions"),
                     _canonical(rep["metadata"]).decode()))
            db.execute("INSERT INTO sources(source_id,latest_sequence,indexed_sequence,scope_json) VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET latest_sequence=MAX(latest_sequence,excluded.latest_sequence), indexed_sequence=MAX(indexed_sequence,excluded.indexed_sequence), scope_json=excluded.scope_json",
                       (source_id, seq, seq, scope_json))
            response = {"operation_id": request["operation_id"], "source_id": source_id, "source_revision": source["revision"],
                        "revision_sequence": seq, "status": "complete", "index_generation": gen["generation_id"],
                        "request_id": request.get("request_id", "index")}
            db.execute("INSERT INTO operations(operation_id,idempotency_key,payload_hash,status,response_json) VALUES(?,?,?,?,?)",
                       (request["operation_id"], idempotency_key, payload_hash, "complete", _canonical(response).decode()))
            return 200, response

    def delete(self, request: dict[str, Any], idempotency_key: str) -> tuple[int, dict[str, Any]]:
        if not idempotency_key:
            raise _error("invalid_request", "Idempotency-Key header is required")
        source_id = request.get("source_id")
        seq = request.get("revision_sequence")
        if not isinstance(source_id, str) or type(seq) is not int or seq < 1 or request.get("delete_scope") != "source":
            raise _error("invalid_request", "source-wide tombstone with a positive sequence is required")
        payload_hash = hashlib.sha256(_canonical(request)).hexdigest()
        with self._lock, self._connect() as db:
            prior = db.execute("SELECT * FROM operations WHERE operation_id=? OR idempotency_key=?", (request.get("operation_id"), idempotency_key)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash or prior["idempotency_key"] != idempotency_key:
                    raise _error("idempotency_conflict", "operation identity was reused with different content", 409)
                return 200, json.loads(prior["response_json"])
            self._profile(db, request.get("index_profile"))
            active = self._generation(db, None, request["index_profile"])
            existing = db.execute("SELECT tombstone_sequence FROM tombstones WHERE source_id=?", (source_id,)).fetchone()
            if existing and seq < existing["tombstone_sequence"]:
                raise _error("revision_sequence_regression", "tombstone sequence cannot regress", 409)
            db.execute("INSERT INTO tombstones(source_id,tombstone_sequence,source_revision,scope_json) VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET tombstone_sequence=MAX(tombstone_sequence,excluded.tombstone_sequence), source_revision=excluded.source_revision, scope_json=excluded.scope_json",
                       (source_id, seq, request.get("source_revision", ""), self._scope(request.get("scope"))))
            db.execute("DELETE FROM representations WHERE source_id=? AND revision_sequence<=?", (source_id, seq))
            response = {"operation_id": request.get("operation_id", ""), "source_id": source_id,
                        "source_revision": request.get("source_revision", ""), "revision_sequence": seq,
                        "status": "complete", "index_generation": active["generation_id"],
                        "request_id": request.get("request_id", "index")}
            db.execute("INSERT INTO operations(operation_id,idempotency_key,payload_hash,status,response_json) VALUES(?,?,?,?,?)",
                       (request["operation_id"], idempotency_key, payload_hash, "complete", _canonical(response).decode()))
            return 200, response

    def profile_version(self, name: str, version: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT bundle_json FROM profiles WHERE name=? AND version=?", (name, version)).fetchone()
            if not row:
                raise _error("profile_not_found", "pinned Index profile version is not provisioned", 404)
            bundle = json.loads(row["bundle_json"])
            return {"name": bundle["name"], "version": bundle["version"], "digest": bundle["digest"], "bundle": bundle}

    def active_generation(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("""SELECT g.* FROM active_generation a JOIN generations g ON g.generation_id=a.generation_id WHERE a.singleton=1""").fetchone()
            if not row:
                raise _error("not_ready", "no active Index generation is provisioned", 503)
            return self._generation_payload(db, row)

    def _generation_payload(self, db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        counts = db.execute("SELECT COUNT(DISTINCT source_id) sources, COUNT(*) chunks, SUM(CASE WHEN vector_json IS NOT NULL THEN 1 ELSE 0 END) vectors FROM representations WHERE generation_id=?", (row["generation_id"],)).fetchone()
        return {"generation_id": row["generation_id"], "status": row["status"],
                "index_profile": {"name": row["profile_name"], "version": row["profile_version"], "digest": row["profile_digest"]},
                "request_id": "index", "counts": {"sources": counts["sources"], "chunks": counts["chunks"], "vectors": counts["vectors"] or 0, "tombstones": 0, "failed_sources": 0},
                "owner_reconciliation_checkpoints": {}, "validation_results": [], "cutover_eligible": False}

    def operation(self, operation_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if not row:
                raise _error("operation_not_found", "Index operation was not found", 404)
            payload = json.loads(row["response_json"])
            payload["status"] = row["status"]
            payload["safe_error_code"] = row["safe_error_code"]
            return payload

    def source_status(self, source_id: str) -> dict[str, Any]:
        with self._connect() as db:
            source = db.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
            tomb = db.execute("SELECT tombstone_sequence FROM tombstones WHERE source_id=?", (source_id,)).fetchone()
            if not source and not tomb:
                raise _error("source_not_found", "Index source was not found", 404)
            return {"source_id": source_id, "latest_revision_sequence": source["latest_sequence"] if source else None,
                    "indexed_revision_sequence": source["indexed_sequence"] if source else None,
                    "tombstone_sequence": tomb["tombstone_sequence"] if tomb else None,
                    "deletion_state": "tombstoned" if tomb else "active", "request_id": "index"}

    def lexical_lookup(self, request: dict[str, Any]) -> dict[str, Any]:
        scope_json = self._scope(request.get("scope"))
        terms = request.get("terms")
        limit = request.get("limit")
        if not isinstance(terms, list) or not terms or any(not isinstance(t, str) or not t for t in terms) or type(limit) is not int or not 1 <= limit <= 100:
            raise _error("invalid_request", "terms and limit are invalid")
        with self._connect() as db:
            bundle, _ = self._profile(db, request.get("index_profile"))
            gen = self._generation(db, request.get("index_generation"), request["index_profile"])
            lexical = bundle["lexical"]
            if request.get("lexical_profile") != {"name": lexical["profile"], "version": lexical["version"]}:
                raise _error("unsupported_profile", "lexical profile does not match pinned bundle", 422)
            rows = db.execute("SELECT * FROM representations WHERE generation_id=? AND scope_json=? AND lexical_profile=? AND lexical_version=?",
                              (gen["generation_id"], scope_json, lexical["profile"], lexical["version"])).fetchall()
            rows = [row for row in rows if not (lambda tomb: tomb and row["revision_sequence"] <= tomb["tombstone_sequence"])(db.execute("SELECT tombstone_sequence FROM tombstones WHERE source_id=?", (row["source_id"],)).fetchone())]
            eligible = []
            for row in rows:
                if request.get("source_ids") and row["source_id"] not in request["source_ids"]:
                    continue
                if request.get("source_revisions") and row["source_revision"] not in request["source_revisions"]:
                    continue
                term_list = json.loads(row["terms_json"])
                freq = {term: term_list.count(term) for term in set(terms) if term in term_list}
                if freq:
                    eligible.append((row, freq, len(term_list)))
            n = len(rows)
            lengths = [len(json.loads(row["terms_json"])) for row in rows]
            avgdl = sum(lengths) / len(lengths) if lengths else 0.0
            df = {term: sum(1 for row in rows if term in set(json.loads(row["terms_json"]))) for term in set(terms)}
            eligible.sort(key=lambda item: (-sum(item[1].values()), item[0]["source_id"], -item[0]["revision_sequence"], item[0]["chunk_id"], item[0]["chunker_profile"], item[0]["chunker_version"]))
            truncated = len(eligible) > limit
            candidates = []
            for row, freq, length in eligible[:limit]:
                candidates.append({"source_id": row["source_id"], "source_revision": row["source_revision"], "revision_sequence": row["revision_sequence"],
                    "chunk_id": row["chunk_id"], "chunker": {"profile": row["chunker_profile"], "version": row["chunker_version"]},
                    "text": row["text"], "document_length": length,
                    "term_frequency_evidence": [{"term": t, "term_frequency": freq[t]} for t in sorted(freq)]})
            return {"candidates": candidates, "corpus_statistics": {"document_count": n, "average_document_length": avgdl, "document_frequency": df},
                    "truncated": truncated, "index_generation": gen["generation_id"], "request_id": request.get("request_id", "index")}

    def vector_neighbors(self, request: dict[str, Any]) -> dict[str, Any]:
        scope_json = self._scope(request.get("scope"))
        vector = request.get("query_vector")
        metric = request.get("metric")
        limit = request.get("limit")
        if request.get("input_type") != "query" or not isinstance(vector, list) or not vector or any(not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in vector):
            raise _error("invalid_request", "query vector/input_type is invalid")
        if metric not in {"cosine", "dot_product", "euclidean"} or type(limit) is not int or not 1 <= limit <= 100:
            raise _error("invalid_request", "metric or limit is invalid")
        with self._connect() as db:
            bundle, _ = self._profile(db, request.get("index_profile"))
            gen = self._generation(db, request.get("index_generation"), request["index_profile"])
            emb = bundle["embedding"]
            ep = request.get("embedding_profile")
            if not isinstance(ep, dict) or ep.get("name") != emb["profile"] or ep.get("version") != emb["version"] or len(vector) != emb["dimensions"] or metric != emb["metric"]:
                raise _error("incompatible_representation", "query vector profile/dimensions/metric mismatch", 422)
            rows = db.execute("SELECT * FROM representations WHERE generation_id=? AND scope_json=? AND vector_json IS NOT NULL AND embedding_model=? AND embedding_version=? AND embedding_dimensions=?",
                              (gen["generation_id"], scope_json, emb["model"], emb["model_version"], emb["dimensions"])).fetchall()
            scored = []
            for row in rows:
                tomb = db.execute("SELECT tombstone_sequence FROM tombstones WHERE source_id=?", (row["source_id"],)).fetchone()
                if tomb and row["revision_sequence"] <= tomb["tombstone_sequence"]:
                    continue
                if request.get("source_ids") and row["source_id"] not in request["source_ids"]:
                    continue
                candidate = json.loads(row["vector_json"])
                if metric == "euclidean":
                    score = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(vector, candidate)))
                    key = score
                elif metric == "dot_product":
                    score = sum(float(a) * float(b) for a, b in zip(vector, candidate))
                    key = -score
                else:
                    denom = math.sqrt(sum(float(a) ** 2 for a in vector) * sum(float(b) ** 2 for b in candidate))
                    score = sum(float(a) * float(b) for a, b in zip(vector, candidate)) / denom if denom else 0.0
                    key = -score
                scored.append((key, row, score))
            scored.sort(key=lambda item: (item[0], item[1]["source_id"], -item[1]["revision_sequence"], item[1]["chunk_id"], item[1]["chunker_profile"], item[1]["chunker_version"]))
            candidates = []
            for rank, (_, row, score) in enumerate(scored[:limit], 1):
                c = {"source_id": row["source_id"], "source_revision": row["source_revision"], "revision_sequence": row["revision_sequence"],
                     "chunk_id": row["chunk_id"], "chunker": {"profile": row["chunker_profile"], "version": row["chunker_version"]},
                     "text": row["text"], "retrieval_rank": rank,
                     "embedding": {"model": row["embedding_model"], "version": row["embedding_version"], "dimensions": row["embedding_dimensions"], "metric": metric, "input_type": "document"}}
                c["distance" if metric == "euclidean" else "similarity"] = score
                candidates.append(c)
            return {"candidates": candidates, "truncated": len(scored) > limit, "index_generation": gen["generation_id"], "request_id": request.get("request_id", "index")}


    def handle(self, method: str, path: str, query: dict[str, list[str]], body: dict[str, Any] | None,
               headers: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        """Dispatch one Index REST request. This is called only by the shared HTTP server."""
        parts = [unquote(p) for p in path.strip("/").split("/")]
        if parts[:3] != ["api", "v1", "index"]:
            raise _error("endpoint_not_found", "Index endpoint not found", 404)
        tail = parts[3:]
        payload = dict(body or {})
        payload["request_id"] = payload.get("request_id", request_id)

        if method == "GET" and tail == ["health"]:
            return 200, {"service": "index", "status": "alive", "request_id": request_id}
        if method == "GET" and tail == ["ready"]:
            try:
                active = self.active_generation()
                return 200, {"service": "index", "status": "ready", "ready": True,
                             "checks": [{"name": "profile_bundle", "status": "ok"},
                                        {"name": "active_generation", "status": "ok"}],
                             "active_generation": active["generation_id"], "request_id": request_id}
            except IndexError:
                return 503, {"service": "index", "status": "not_ready", "ready": False,
                             "checks": [{"name": "profile_bundle", "status": "unavailable"}],
                             "request_id": request_id}
        if method == "GET" and tail == ["generations", "active"]:
            return 200, self.active_generation()
        if method == "GET" and len(tail) == 5 and tail[0] == "profiles" and tail[2] == "versions":
            return 200, self.profile_version(tail[1], tail[3])
        if method == "GET" and len(tail) == 3 and tail[0] == "profiles" and tail[2] == "current":
            with self._connect() as db:
                rows = db.execute("SELECT bundle_json FROM profiles WHERE name=? ORDER BY version", (tail[1],)).fetchall()
                if not rows:
                    raise _error("profile_not_found", "Index profile was not found", 404)
                if len(rows) != 1:
                    raise _error("conflict", "multiple versions are provisioned; current profile selection is not configured", 409)
                bundle = json.loads(rows[0]["bundle_json"])
                return 200, {"name": bundle["name"], "version": bundle["version"], "digest": bundle["digest"],
                             "bundle": bundle, "request_id": request_id}
        if method == "GET" and len(tail) == 2 and tail[0] == "operations":
            result = self.operation(tail[1])
            result["request_id"] = request_id
            return 200, result
        if method == "GET" and len(tail) == 3 and tail[0] == "sources" and tail[2] == "status":
            result = self.source_status(tail[1])
            result["request_id"] = request_id
            return 200, result
        if method == "GET" and tail == ["sources", "manifest"]:
            params = {key: values[-1] for key, values in query.items() if values}
            owner = params.get("owner")
            limit_text = params.get("limit", "100")
            if owner not in {"memory", "knowledge"} or not limit_text.isdecimal() or not 1 <= int(limit_text) <= 100:
                raise _error("invalid_request", "owner and limit (1-100) are required")
            limit = int(limit_text)
            cursor = params.get("cursor")
            with self._connect() as db:
                rows = db.execute("SELECT s.source_id,s.latest_sequence,s.indexed_sequence,s.scope_json,t.tombstone_sequence FROM sources s LEFT JOIN tombstones t ON t.source_id=s.source_id WHERE s.source_id LIKE ? ORDER BY s.source_id",
                                  (owner + ":%",)).fetchall()
                rows = [row for row in rows if cursor is None or row["source_id"] > cursor]
                selected = rows[:limit]
                return 200, {"owner": owner, "items": [{"source_id": row["source_id"],
                    "latest_revision_sequence": row["latest_sequence"], "indexed_revision_sequence": row["indexed_sequence"],
                    "tombstone_sequence": row["tombstone_sequence"]} for row in selected],
                    "next_cursor": selected[-1]["source_id"] if len(rows) > limit and selected else None,
                    "request_id": request_id}
        if method == "GET" and len(tail) == 2 and tail[0] == "generations":
            with self._connect() as db:
                row = db.execute("SELECT * FROM generations WHERE generation_id=?", (tail[1],)).fetchone()
                if not row:
                    raise _error("generation_not_found", "Index generation was not found", 404)
                result = self._generation_payload(db, row)
                result["request_id"] = request_id
                return 200, result

        if method == "POST" and tail == ["operations", "upsert"]:
            return self.upsert(payload, headers.get("Idempotency-Key", ""))
        if method == "POST" and tail == ["operations", "delete"]:
            return self.delete(payload, headers.get("Idempotency-Key", ""))
        if method == "POST" and tail == ["lexical", "lookup"]:
            return 200, self.lexical_lookup(payload)
        if method == "POST" and tail == ["vector-neighbors"]:
            return 200, self.vector_neighbors(payload)
        if method == "POST" and tail == ["generations"]:
            if not headers.get("Idempotency-Key"):
                raise _error("invalid_request", "Idempotency-Key header is required")
            with self._lock, self._connect() as db:
                bundle, _ = self._profile(db, payload.get("index_profile"))
                generation_id = "gen-" + uuid.uuid4().hex
                db.execute("INSERT INTO generations(generation_id,status,profile_name,profile_version,profile_digest) VALUES(?,?,?,?,?)",
                           (generation_id, "building", bundle["name"], bundle["version"], bundle["digest"]))
                row = db.execute("SELECT * FROM generations WHERE generation_id=?", (generation_id,)).fetchone()
                return 202, self._generation_payload(db, row)
        if method == "POST" and len(tail) == 3 and tail[0] == "generations" and tail[2] == "abandon":
            with self._lock, self._connect() as db:
                row = db.execute("SELECT * FROM generations WHERE generation_id=?", (tail[1],)).fetchone()
                if not row:
                    raise _error("generation_not_found", "Index generation was not found", 404)
                active = db.execute("SELECT generation_id FROM active_generation WHERE singleton=1").fetchone()
                if active and active["generation_id"] == tail[1]:
                    raise _error("active_generation_cannot_be_abandoned", "active generation cannot be abandoned", 409)
                if row["status"] != "building":
                    raise _error("conflict", "only a building generation can be abandoned", 409)
                db.execute("UPDATE generations SET status='abandoned' WHERE generation_id=?", (tail[1],))
                updated = db.execute("SELECT * FROM generations WHERE generation_id=?", (tail[1],)).fetchone()
                return 200, self._generation_payload(db, updated)
        if method == "POST" and len(tail) == 3 and tail[0] == "generations" and tail[2] == "owner-checkpoints":
            owner = payload.get("owner")
            sequence = payload.get("applied_change_sequence")
            if owner not in {"memory", "knowledge"} or type(sequence) is not int or sequence < 0:
                raise _error("invalid_request", "owner and nonnegative applied_change_sequence are required")
            with self._lock, self._connect() as db:
                gen = db.execute("SELECT generation_id,status FROM generations WHERE generation_id=?", (tail[1],)).fetchone()
                if not gen or gen["status"] != "building":
                    raise _error("generation_not_found", "building generation was not found", 404)
                old = db.execute("SELECT applied_sequence FROM owner_checkpoints WHERE generation_id=? AND owner=?", (tail[1], owner)).fetchone()
                if old and sequence < old["applied_sequence"]:
                    raise _error("revision_sequence_regression", "owner checkpoint cannot regress", 409)
                db.execute("INSERT INTO owner_checkpoints(generation_id,owner,applied_sequence) VALUES(?,?,?) ON CONFLICT(generation_id,owner) DO UPDATE SET applied_sequence=excluded.applied_sequence",
                           (tail[1], owner, sequence))
                return 200, {"owner": owner, "applied_change_sequence": sequence, "request_id": request_id}
        if method == "PUT" and len(tail) == 5 and tail[0] == "generations" and tail[2] == "owner-fences":
            generation_id, owner, fence_id = tail[1], tail[3], tail[4]
            if payload.get("owner") != owner or payload.get("target_generation") != generation_id or payload.get("fence_id") != fence_id or payload.get("state") != "held":
                raise _error("invalid_request", "fence identity does not match URL")
            expires = payload.get("expires_at")
            try:
                expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                raise _error("invalid_request", "expires_at must be an RFC3339 timestamp")
            now = datetime.now(timezone.utc)
            if expiry <= now or (expiry - now).total_seconds() > 300:
                raise _error("fence_expired", "fence expiry must be in the future and within 300 seconds", 409)
            with self._lock, self._connect() as db:
                gen = db.execute("SELECT status FROM generations WHERE generation_id=?", (generation_id,)).fetchone()
                if not gen or gen["status"] != "building" or owner not in {"memory", "knowledge"}:
                    raise _error("generation_not_found", "building generation or owner was not found", 404)
                sequence = payload.get("sealed_change_sequence")
                if type(sequence) is not int or sequence < 0 or not isinstance(payload.get("fence_token"), str) or len(payload["fence_token"]) < 16:
                    raise _error("invalid_request", "fence token or sealed sequence is invalid")
                cp = db.execute("SELECT applied_sequence FROM owner_checkpoints WHERE generation_id=? AND owner=?", (generation_id, owner)).fetchone()
                if not cp or cp["applied_sequence"] < sequence:
                    raise _error("generation_not_caught_up", "owner checkpoint has not reached the sealed sequence", 409)
                old = db.execute("SELECT * FROM owner_fences WHERE generation_id=? AND owner=? AND fence_id=?", (generation_id, owner, fence_id)).fetchone()
                values = (generation_id, owner, fence_id, payload["fence_token"], sequence, expiry.isoformat(), "held")
                if old and tuple(old[k] for k in ("generation_id","owner","fence_id","fence_token","sealed_sequence","expires_at","state")) != values:
                    raise _error("conflict", "fence ID was reused with different contents", 409)
                db.execute("INSERT OR IGNORE INTO owner_fences VALUES(?,?,?,?,?,?,?)", values)
                return 200, {"owner": owner, "target_generation": generation_id, "fence_id": fence_id,
                             "fence_token": payload["fence_token"], "expires_at": expiry.isoformat(),
                             "sealed_change_sequence": sequence, "fence_state": "held", "request_id": request_id}
        if method == "DELETE" and len(tail) == 5 and tail[0] == "generations" and tail[2] == "owner-fences":
            generation_id, owner, fence_id = tail[1], tail[3], tail[4]
            with self._lock, self._connect() as db:
                row = db.execute("SELECT state FROM owner_fences WHERE generation_id=? AND owner=? AND fence_id=?", (generation_id, owner, fence_id)).fetchone()
                if not row:
                    raise _error("not_found", "owner fence was not found", 404)
                db.execute("UPDATE owner_fences SET state='released' WHERE generation_id=? AND owner=? AND fence_id=?", (generation_id, owner, fence_id))
                return 200, {"owner": owner, "target_generation": generation_id, "fence_id": fence_id, "released": True, "request_id": request_id}
        if method == "POST" and len(tail) == 3 and tail[0] == "generations" and tail[2] == "cutover":
            expected = payload.get("expected_active_generation")
            fences = payload.get("owner_fences")
            if not headers.get("Idempotency-Key") or not isinstance(fences, list) or len(fences) != 2:
                raise _error("invalid_request", "Idempotency-Key and exactly two owner fences are required")
            with self._lock, self._connect() as db:
                active = db.execute("SELECT generation_id FROM active_generation WHERE singleton=1").fetchone()
                target = db.execute("SELECT * FROM generations WHERE generation_id=?", (tail[1],)).fetchone()
                if not active or active["generation_id"] != expected:
                    raise _error("conflict", "active generation changed before cutover", 409)
                if not target or target["status"] != "building":
                    raise _error("generation_not_found", "building target generation was not found", 404)
                seen = set()
                for ref in fences:
                    owner = ref.get("owner")
                    if owner not in {"memory", "knowledge"} or owner in seen:
                        raise _error("invalid_request", "cutover requires one fence per owner")
                    seen.add(owner)
                    fence = db.execute("SELECT * FROM owner_fences WHERE generation_id=? AND owner=? AND fence_id=?", (tail[1], owner, ref.get("fence_id"))).fetchone()
                    if not fence or fence["state"] != "held" or fence["fence_token"] != ref.get("fence_token") or datetime.fromisoformat(fence["expires_at"]) <= datetime.now(timezone.utc):
                        raise _error("fence_expired", "cutover fence is missing, released, or expired", 409)
                    if fence["sealed_sequence"] != ref.get("sealed_change_sequence"):
                        raise _error("conflict", "cutover sealed sequence does not match registered fence", 409)
                    cp = db.execute("SELECT applied_sequence FROM owner_checkpoints WHERE generation_id=? AND owner=?", (tail[1], owner)).fetchone()
                    if not cp or cp["applied_sequence"] < fence["sealed_sequence"]:
                        raise _error("generation_not_caught_up", "owner checkpoint is behind sealed sequence", 409)
                if seen != {"memory", "knowledge"}:
                    raise _error("invalid_request", "cutover requires memory and knowledge fences")
                db.execute("UPDATE generations SET status='retired' WHERE generation_id=?", (active["generation_id"],))
                db.execute("UPDATE generations SET status='active' WHERE generation_id=?", (tail[1],))
                db.execute("UPDATE active_generation SET generation_id=? WHERE singleton=1", (tail[1],))
                row = db.execute("SELECT * FROM generations WHERE generation_id=?", (tail[1],)).fetchone()
                return 200, self._generation_payload(db, row)

        if path.startswith("/api/v1/index/"):
            if method in {"GET", "POST", "PUT", "DELETE"}:
                raise _error("endpoint_not_found", "Index endpoint not found", 404)
        raise _error("method_not_allowed", "HTTP method is not supported for this Index endpoint", 405)


_service_lock = threading.Lock()
_service: IndexService | None = None


def get_index_service() -> IndexService:
    """Load the explicitly provisioned profile; no built-in profile is assumed."""
    global _service
    if _service is not None:
        return _service
    with _service_lock:
        if _service is not None:
            return _service
        profile_path = os.environ.get("CE_INDEX_PROFILE_BUNDLE_PATH")
        db_path = os.environ.get("CE_INDEX_DB_PATH", str(Path.home() / ".FlossWare" / "index" / "index.sqlite3"))
        bundle = None
        if profile_path:
            try:
                bundle = json.loads(Path(profile_path).expanduser().read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise _error("not_ready", "configured Index profile bundle could not be loaded", 503) from exc
        _service = IndexService(db_path, bundle)
        return _service


def reset_index_service_for_tests() -> None:
    global _service
    with _service_lock:
        _service = None
