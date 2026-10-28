"""Durable canonical Memory owner state for the first CE ingestion slice.

This module owns canonical records, immutable revisions, operation status, and
idempotency bindings. It deliberately does not import or access other services.
Service-to-service ingestion orchestration is performed by the REST dispatcher.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MEMORY_ID = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")
MAX_CONTENT_BYTES = 262_144
MAX_SEQUENCE = 9_007_199_254_740_991


class MemoryError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _payload_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise MemoryError("invalid_request", f"{field} must be a non-empty string", 400)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise MemoryError("invalid_request", f"{field} contains invalid Unicode", 400) from exc
    if len(encoded) > MAX_CONTENT_BYTES:
        raise MemoryError("source_too_large", f"{field} exceeds the UTF-8 byte limit", 413)
    return value


def _validate_scope(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"type", "id", "visibility"}:
        raise MemoryError("invalid_request", "scope must contain type, id, and visibility", 400)
    if not isinstance(value["type"], str) or value["type"] not in {"user", "project", "shared", "global"}:
        raise MemoryError("invalid_request", "scope.type is invalid", 400)
    if not isinstance(value["id"], str) or not 1 <= len(value["id"]) <= 256:
        raise MemoryError("invalid_request", "scope.id is invalid", 400)
    if not isinstance(value["visibility"], str) or value["visibility"] not in {"private", "shared", "global"}:
        raise MemoryError("invalid_request", "scope.visibility is invalid", 400)
    return dict(value)


def _validate_profile(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"name", "version", "digest"}:
        raise MemoryError("invalid_request", "index_profile must contain name, version, and digest", 400)
    if not isinstance(value["name"], str) or not 1 <= len(value["name"]) <= 128:
        raise MemoryError("invalid_request", "index_profile.name is invalid", 400)
    if not isinstance(value["version"], str) or not 1 <= len(value["version"]) <= 64:
        raise MemoryError("invalid_request", "index_profile.version is invalid", 400)
    digest = value["digest"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise MemoryError("invalid_request", "index_profile.digest is invalid", 400)
    return {"name": value["name"], "version": value["version"], "digest": digest}


class MemoryService:
    """SQLite-backed canonical owner with durable sequence/tombstone state."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(Path(db_path).expanduser())
        self._lock = threading.RLock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memories(
                    memory_id TEXT PRIMARY KEY,
                    scope_json TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    current_sequence INTEGER NOT NULL,
                    current_revision TEXT NOT NULL,
                    tombstone_sequence INTEGER,
                    index_profile_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions(
                    memory_id TEXT NOT NULL,
                    revision_sequence INTEGER NOT NULL,
                    revision_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    retention_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(memory_id, revision_sequence),
                    UNIQUE(memory_id, revision_id)
                );
                CREATE TABLE IF NOT EXISTS memory_operations(
                    operation_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    operation_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    indexing_status TEXT NOT NULL,
                    revision_sequence INTEGER NOT NULL,
                    response_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memory_idempotency(
                    idempotency_key TEXT PRIMARY KEY,
                    payload_hash TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memory_sequence(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    next_sequence INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO memory_sequence(singleton,next_sequence) VALUES(1,1);
            """)

    def _allocate_sequence(self, db: sqlite3.Connection) -> int:
        row = db.execute("SELECT next_sequence FROM memory_sequence WHERE singleton=1").fetchone()
        sequence = int(row["next_sequence"])
        if sequence > MAX_SEQUENCE:
            raise MemoryError("sequence_exhausted", "Memory revision sequence space is exhausted", 503)
        db.execute("UPDATE memory_sequence SET next_sequence=? WHERE singleton=1", (sequence + 1,))
        return sequence

    def create(self, request: dict[str, Any], idempotency_key: str, request_id: str) -> tuple[int, dict[str, Any]]:
        required = {"scope", "type", "content", "provenance", "retention_policy", "index_profile"}
        if set(request) - (required | {"request_id"}) or not required.issubset(request):
            raise MemoryError("invalid_request", "create request has missing or unknown fields", 400)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise MemoryError("invalid_request", "Idempotency-Key is required and must be 1 to 256 characters", 400)
        scope = _validate_scope(request["scope"])
        memory_type = request["type"]
        if not isinstance(memory_type, str) or memory_type not in {"episodic", "semantic", "decision", "fact", "preference", "task"}:
            raise MemoryError("invalid_request", "type is invalid", 400)
        content = _validate_text(request["content"], "content")
        if not isinstance(request["provenance"], dict):
            raise MemoryError("invalid_request", "provenance must be an object", 400)
        retention = request["retention_policy"]
        if not isinstance(retention, dict) or set(retention) - {"kind", "expires_at"} or not isinstance(retention.get("kind"), str) or retention.get("kind") not in {"standard", "ephemeral", "retained"}:
            raise MemoryError("invalid_request", "retention_policy is invalid", 400)
        profile = _validate_profile(request["index_profile"])
        semantic_request = {k: v for k, v in request.items() if k != "request_id"}
        payload_hash = _payload_hash(semantic_request)
        with self._lock, self._connect() as db:
            prior = db.execute("SELECT payload_hash,response_json FROM memory_idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise MemoryError("idempotency_conflict", "Idempotency-Key was already used with a different payload", 409)
                response = json.loads(prior["response_json"])
                response["request_id"] = request_id
                return 202, response
            memory_id = uuid.uuid4().hex
            revision = uuid.uuid4().hex
            operation_id = "memory:op:" + uuid.uuid4().hex
            sequence = self._allocate_sequence(db)
            response = {
                "operation_id": operation_id, "memory_id": memory_id,
                "revision": revision, "revision_sequence": sequence,
                "status": "accepted", "indexing_status": "pending_index",
                "source_id": "memory:" + memory_id, "index_profile": profile,
                "request_id": request_id,
            }
            db.execute("""INSERT INTO memories(memory_id,scope_json,memory_type,current_sequence,current_revision,index_profile_json)
                          VALUES(?,?,?,?,?,?)""",
                       (memory_id, _canonical(scope).decode(), memory_type, sequence, revision, _canonical(profile).decode()))
            db.execute("""INSERT INTO revisions(memory_id,revision_sequence,revision_id,content,provenance_json,retention_json)
                          VALUES(?,?,?,?,?,?)""",
                       (memory_id, sequence, revision, content, _canonical(request["provenance"]).decode(), _canonical(retention).decode()))
            db.execute("""INSERT INTO memory_operations(operation_id,memory_id,operation_kind,status,indexing_status,revision_sequence,response_json)
                          VALUES(?,?,?,?,?,?,?)""",
                       (operation_id, memory_id, "create", "accepted", "pending_index", sequence, _canonical(response).decode()))
            db.execute("INSERT INTO memory_idempotency(idempotency_key,payload_hash,operation_id,response_json) VALUES(?,?,?,?)",
                       (idempotency_key, payload_hash, operation_id, _canonical(response).decode()))
            return 202, response

    def read(self, memory_id: str, scope: dict[str, Any]) -> dict[str, Any]:
        if not MEMORY_ID.fullmatch(memory_id or ""):
            raise MemoryError("invalid_parameter", "memory_id is invalid", 400)
        scope = _validate_scope(scope)
        with self._connect() as db:
            row = db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
            if row is None:
                raise MemoryError("not_found", "memory was not found", 404)
            if row["tombstone_sequence"] is not None:
                raise MemoryError("not_found", "memory was deleted", 404)
            if json.loads(row["scope_json"]) != scope:
                raise MemoryError("not_found", "memory was not found in this scope", 404)
            rev = db.execute("SELECT * FROM revisions WHERE memory_id=? AND revision_sequence=?",
                             (memory_id, row["current_sequence"])).fetchone()
            return {
                "memory_id": memory_id,
                "scope": scope, "type": row["memory_type"],
                "revision": row["current_revision"], "revision_sequence": row["current_sequence"],
                "content": rev["content"], "provenance": json.loads(rev["provenance_json"]),
                "retention_policy": json.loads(rev["retention_json"]),
                "index_profile": json.loads(row["index_profile_json"]),
            }

    def operation(self, operation_id: str, memory_id: str | None = None,
                  scope_value: Any = None) -> dict[str, Any]:
        scope = _validate_scope(scope_value) if scope_value is not None else None
        with self._connect() as db:
            if memory_id is None:
                row = db.execute("""SELECT o.*,m.scope_json FROM memory_operations o
                                    JOIN memories m ON m.memory_id=o.memory_id WHERE o.operation_id=?""",
                                 (operation_id,)).fetchone()
            else:
                row = db.execute("""SELECT o.*,m.scope_json FROM memory_operations o
                                    JOIN memories m ON m.memory_id=o.memory_id
                                    WHERE o.operation_id=? AND o.memory_id=?""",
                                 (operation_id, memory_id)).fetchone()
            if row is None or (scope is not None and json.loads(row["scope_json"]) != scope):
                raise MemoryError("not_found", "operation was not found", 404)
            response = json.loads(row["response_json"])
            result = {
                "operation_id": row["operation_id"],
                "status": row["status"],
                "canonical_status": "tombstoned" if row["operation_kind"] == "delete" else "committed",
                "indexing_status": row["indexing_status"],
                "revision_sequence": row["revision_sequence"],
                "request_id": response.get("request_id", operation_id),
            }
            if row["operation_kind"] == "delete":
                result["graph_status"] = response.get("graph_status", "pending_graph")
            return result

    def update(self, memory_id: str, request: dict[str, Any], idempotency_key: str, request_id: str, scope_value: Any) -> tuple[int, dict[str, Any]]:
        required = {"expected_base_revision_sequence", "content", "provenance", "index_profile"}
        if set(request) - (required | {"request_id"}) or not required.issubset(request):
            raise MemoryError("invalid_request", "revision request has missing or unknown fields", 400)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise MemoryError("invalid_request", "Idempotency-Key is required and must be 1 to 256 characters", 400)
        if not MEMORY_ID.fullmatch(memory_id or ""):
            raise MemoryError("invalid_parameter", "memory_id is invalid", 400)
        content = _validate_text(request["content"], "content")
        if not isinstance(request["provenance"], dict):
            raise MemoryError("invalid_request", "provenance must be an object", 400)
        profile = _validate_profile(request["index_profile"])
        scope = _validate_scope(scope_value)
        expected = request["expected_base_revision_sequence"]
        if type(expected) is not int or not 1 <= expected <= MAX_SEQUENCE:
            raise MemoryError("invalid_request", "expected_base_revision_sequence is invalid", 400)
        semantic_request = {"memory_id": memory_id, **{k: v for k, v in request.items() if k != "request_id"}}
        payload_hash = _payload_hash(semantic_request)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
            if row is None or row["tombstone_sequence"] is not None or json.loads(row["scope_json"]) != scope:
                raise MemoryError("not_found", "memory was not found in this scope", 404)
            prior = db.execute("SELECT payload_hash,response_json FROM memory_idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise MemoryError("idempotency_conflict", "Idempotency-Key was already used with a different payload", 409)
                response = json.loads(prior["response_json"])
                response["request_id"] = request_id
                return 202, response
            if row["current_sequence"] != expected:
                raise MemoryError("revision_conflict", "expected base revision does not match the current revision", 409)
            if json.loads(row["index_profile_json"]) != profile:
                raise MemoryError("incompatible_representation", "changing index profile requires an explicit rebuild workflow", 422)
            revision_sequence = self._allocate_sequence(db)
            revision = uuid.uuid4().hex
            operation_id = "memory:op:" + uuid.uuid4().hex
            response = {
                "operation_id": operation_id, "memory_id": memory_id,
                "revision": revision, "revision_sequence": revision_sequence,
                "status": "accepted", "indexing_status": "pending_index",
                "source_id": "memory:" + memory_id, "index_profile": profile,
                "request_id": request_id,
            }
            db.execute("INSERT INTO revisions(memory_id,revision_sequence,revision_id,content,provenance_json,retention_json) VALUES(?,?,?,?,?,?)",
                       (memory_id, revision_sequence, revision, content, _canonical(request["provenance"]).decode(),
                        db.execute("SELECT retention_json FROM revisions WHERE memory_id=? AND revision_sequence=?", (memory_id, expected)).fetchone()["retention_json"]))
            db.execute("UPDATE memories SET current_sequence=?,current_revision=?,updated_at=CURRENT_TIMESTAMP WHERE memory_id=?",
                       (revision_sequence, revision, memory_id))
            db.execute("INSERT INTO memory_operations(operation_id,memory_id,operation_kind,status,indexing_status,revision_sequence,response_json) VALUES(?,?,?,?,?,?,?)",
                       (operation_id, memory_id, "update", "accepted", "pending_index", revision_sequence, _canonical(response).decode()))
            db.execute("INSERT INTO memory_idempotency(idempotency_key,payload_hash,operation_id,response_json) VALUES(?,?,?,?)",
                       (idempotency_key, payload_hash, operation_id, _canonical(response).decode()))
            return 202, response

    def delete(self, memory_id: str, scope_value: Any, delete_scope: str, idempotency_key: str, request_id: str) -> tuple[int, dict[str, Any]]:
        if not MEMORY_ID.fullmatch(memory_id or ""):
            raise MemoryError("invalid_parameter", "memory_id is invalid", 400)
        scope = _validate_scope(scope_value)
        if delete_scope != "source":
            raise MemoryError("invalid_request", "delete_scope must be source", 400)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise MemoryError("invalid_request", "Idempotency-Key is required and must be 1 to 256 characters", 400)
        payload_hash = _payload_hash({"memory_id": memory_id, "scope": scope, "delete_scope": delete_scope})
        with self._lock, self._connect() as db:
            prior = db.execute("SELECT payload_hash,response_json FROM memory_idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise MemoryError("idempotency_conflict", "Idempotency-Key was already used with a different payload", 409)
                response = json.loads(prior["response_json"])
                response["request_id"] = request_id
                return 202, response
            row = db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
            if row is None or json.loads(row["scope_json"]) != scope:
                raise MemoryError("not_found", "memory was not found in this scope", 404)
            if row["tombstone_sequence"] is not None:
                raise MemoryError("not_found", "memory was already deleted", 404)
            sequence = self._allocate_sequence(db)
            revision = uuid.uuid4().hex
            operation_id = "memory:op:" + uuid.uuid4().hex
            response = {
                "operation_id": operation_id, "memory_id": memory_id,
                "revision": revision, "revision_sequence": sequence, "status": "accepted",
                "indexing_status": "pending_index", "graph_status": "pending_graph",
                "request_id": request_id,
            }
            db.execute("UPDATE memories SET current_sequence=?,current_revision=?,tombstone_sequence=?,updated_at=CURRENT_TIMESTAMP WHERE memory_id=?",
                       (sequence, revision, sequence, memory_id))
            db.execute("INSERT INTO memory_operations(operation_id,memory_id,operation_kind,status,indexing_status,revision_sequence,response_json) VALUES(?,?,?,?,?,?,?)",
                       (operation_id, memory_id, "delete", "accepted", "pending_index", sequence, _canonical(response).decode()))
            db.execute("INSERT INTO memory_idempotency(idempotency_key,payload_hash,operation_id,response_json) VALUES(?,?,?,?)",
                       (idempotency_key, payload_hash, operation_id, _canonical(response).decode()))
            return 202, response

    def update_operation(self, operation_id: str, status: str, indexing_status: str) -> dict[str, Any]:
        if status not in {"accepted", "pending", "complete", "failed", "reconciliation_required"}:
            raise MemoryError("invalid_request", "operation status is invalid", 400)
        if indexing_status not in {"pending_index", "indexed", "index_failed", "reconciliation_required"}:
            raise MemoryError("invalid_request", "indexing status is invalid", 400)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT response_json FROM memory_operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise MemoryError("not_found", "operation was not found", 404)
            response = json.loads(row["response_json"])
            response["status"] = status
            response["indexing_status"] = indexing_status
            db.execute("UPDATE memory_operations SET status=?,indexing_status=?,response_json=?,updated_at=CURRENT_TIMESTAMP WHERE operation_id=?",
                       (status, indexing_status, _canonical(response).decode(), operation_id))
            db.execute("UPDATE memory_idempotency SET response_json=? WHERE operation_id=?", (_canonical(response).decode(), operation_id))
            return response

    def verify_revisions(self, items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise MemoryError("invalid_request", "items must contain 1 to 100 entries", 400)
        results = []
        with self._connect() as db:
            for item in items:
                if not isinstance(item, dict) or set(item) != {"source_id", "revision_sequence"}:
                    raise MemoryError("invalid_request", "each item must contain source_id and revision_sequence", 400)
                source_id = item["source_id"]
                sequence = item["revision_sequence"]
                if not isinstance(source_id, str) or not source_id.startswith("memory:") or not MEMORY_ID.fullmatch(source_id[7:]):
                    raise MemoryError("invalid_request", "source_id must use the memory: namespace", 400)
                if type(sequence) is not int or not 1 <= sequence <= MAX_SEQUENCE:
                    raise MemoryError("invalid_request", "revision_sequence is invalid", 400)
                row = db.execute("SELECT current_sequence,tombstone_sequence FROM memories WHERE memory_id=?", (source_id[7:],)).fetchone()
                if row is None:
                    result = {"source_id": source_id, "requested_revision_sequence": sequence, "status": "not_found"}
                elif row["tombstone_sequence"] is not None:
                    result = {"source_id": source_id, "requested_revision_sequence": sequence, "status": "tombstoned",
                              "canonical_revision_sequence": row["tombstone_sequence"]}
                elif row["current_sequence"] == sequence:
                    result = {"source_id": source_id, "requested_revision_sequence": sequence, "status": "current",
                              "canonical_revision_sequence": row["current_sequence"]}
                else:
                    result = {"source_id": source_id, "requested_revision_sequence": sequence, "status": "stale",
                              "canonical_revision_sequence": row["current_sequence"]}
                results.append(result)
        return results

    def deletion_details(self, operation_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("""SELECT o.operation_id,o.revision_sequence,m.memory_id,m.scope_json,m.index_profile_json
                                FROM memory_operations o JOIN memories m ON m.memory_id=o.memory_id
                                WHERE o.operation_id=? AND o.operation_kind='delete'""", (operation_id,)).fetchone()
            if row is None:
                raise MemoryError("not_found", "delete operation was not found", 404)
            return {
                "operation_id": row["operation_id"],
                "source_id": "memory:" + row["memory_id"],
                "revision_sequence": row["revision_sequence"],
                "scope": json.loads(row["scope_json"]),
                "index_profile": json.loads(row["index_profile_json"]),
            }

    def pending_deletions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT operation_id,response_json FROM memory_operations
                                 WHERE operation_kind='delete'
                                   AND status IN ('accepted','pending','failed')
                                   AND indexing_status IN ('pending_index','index_failed')
                                 ORDER BY updated_at,operation_id""").fetchall()
            return [{"accepted": json.loads(row["response_json"]),
                     "details": self.deletion_details(row["operation_id"])} for row in rows]

    def pending_ingestions(self) -> list[dict[str, Any]]:
        """Return durable, current ingestion work for startup recovery."""
        stale_operations: list[str] = []
        pending: list[dict[str, Any]] = []
        with self._connect() as db:
            rows = db.execute("""
                SELECT o.operation_id,o.operation_kind,o.status,o.indexing_status,o.revision_sequence,o.response_json,
                       m.memory_id,m.scope_json,m.memory_type,m.current_sequence,m.tombstone_sequence,m.index_profile_json,
                       r.content,r.provenance_json,r.retention_json
                FROM memory_operations o
                JOIN memories m ON m.memory_id=o.memory_id
                JOIN revisions r ON r.memory_id=o.memory_id AND r.revision_sequence=o.revision_sequence
                WHERE o.operation_kind IN ('create','update')
                  AND o.status IN ('accepted','pending','failed')
                  AND o.indexing_status IN ('pending_index','index_failed')
                ORDER BY o.updated_at,m.memory_id,o.revision_sequence
            """).fetchall()
            for row in rows:
                if row["tombstone_sequence"] is not None or row["current_sequence"] != row["revision_sequence"]:
                    stale_operations.append(row["operation_id"])
                    continue
                accepted = json.loads(row["response_json"])
                request = {
                    "scope": json.loads(row["scope_json"]),
                    "type": row["memory_type"],
                    "content": row["content"],
                    "provenance": json.loads(row["provenance_json"]),
                    "retention_policy": json.loads(row["retention_json"]),
                    "index_profile": json.loads(row["index_profile_json"]),
                    "request_id": accepted.get("request_id", row["operation_id"]),
                }
                pending.append({"accepted": accepted, "request": request})
        for operation_id in stale_operations:
            self.update_operation(operation_id, "reconciliation_required", "reconciliation_required")
        return pending

    def list_records_for_tests(self) -> int:
        """Small diagnostic used by tests; not exposed through REST."""
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) AS n FROM memories").fetchone()["n"])


_service_lock = threading.Lock()
_service_instance: MemoryService | None = None


def get_memory_service() -> MemoryService:
    """Return the process-local Memory owner configured for this deployment."""
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            path = os.environ.get("CE_MEMORY_DB_PATH") or str(Path.home() / ".FlossWare" / "memory" / "memory.sqlite3")
            _service_instance = MemoryService(path)
        return _service_instance


def reset_memory_service_for_tests() -> None:
    """Reset only the process-local singleton; persistent data is never deleted."""
    global _service_instance
    with _service_lock:
        _service_instance = None
