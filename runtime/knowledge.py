"""Canonical sourced Knowledge records for the CE proof of concept.

Knowledge owns source identity, immutable revisions, scope, provenance and
lifecycle. Indexing remains a derived REST workflow owned by the dispatcher.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote, parse_qs


_ID = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")
_SOURCE_ID = re.compile(r"^knowledge:[A-Za-z0-9._~-]{1,128}$")


class KnowledgeError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


class KnowledgeService:
    def __init__(self, db_path: str | Path):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS knowledge_sources(
                source_key TEXT PRIMARY KEY, scope_json TEXT NOT NULL, source_kind TEXT NOT NULL,
                canonical_locator TEXT, retention_policy_json TEXT NOT NULL,
                current_revision TEXT NOT NULL, revision_sequence INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE IF NOT EXISTS knowledge_revisions(
                source_key TEXT NOT NULL, revision TEXT NOT NULL, revision_sequence INTEGER NOT NULL,
                content TEXT NOT NULL, provenance_json TEXT NOT NULL, index_profile_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(source_key, revision_sequence),
                FOREIGN KEY(source_key) REFERENCES knowledge_sources(source_key));
              CREATE TABLE IF NOT EXISTS knowledge_operations(
                operation_id TEXT PRIMARY KEY, source_key TEXT NOT NULL, revision TEXT NOT NULL,
                revision_sequence INTEGER NOT NULL, status TEXT NOT NULL, indexing_status TEXT NOT NULL,
                graph_status TEXT NOT NULL DEFAULT 'not_started', request_id TEXT NOT NULL,
                index_profile_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE IF NOT EXISTS knowledge_idempotency(
                idempotency_key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, operation_id TEXT NOT NULL,
                FOREIGN KEY(operation_id) REFERENCES knowledge_operations(operation_id));
              CREATE TABLE IF NOT EXISTS knowledge_graph_sequence(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), next_sequence INTEGER NOT NULL);
              INSERT OR IGNORE INTO knowledge_graph_sequence(singleton,next_sequence) VALUES(1,1);
              CREATE TABLE IF NOT EXISTS knowledge_graph_journal(
                operation_id TEXT PRIMARY KEY, owner_projection_sequence INTEGER NOT NULL UNIQUE,
                operation_kind TEXT NOT NULL, source_id TEXT NOT NULL, revision_sequence INTEGER NOT NULL,
                payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE INDEX IF NOT EXISTS knowledge_graph_journal_pending
                ON knowledge_graph_journal(status, owner_projection_sequence);
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(knowledge_operations)")}
            if "index_profile_json" not in columns:
                db.execute("ALTER TABLE knowledge_operations ADD COLUMN index_profile_json TEXT NOT NULL DEFAULT '{}'")

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _id(value: Any, field: str) -> str:
        if not isinstance(value, str) or not _ID.fullmatch(value):
            raise KnowledgeError("invalid_request", f"{field} must be a stable opaque identifier")
        return value

    @staticmethod
    def _scope(value: Any) -> dict[str, str]:
        if (not isinstance(value, dict) or set(value) != {"type", "id", "visibility"}
                or value.get("type") not in {"user", "project", "shared", "global"}
                or not isinstance(value.get("id"), str) or not value["id"]
                or value.get("visibility") not in {"private", "shared", "global"}):
            raise KnowledgeError("invalid_request", "scope is invalid")
        return value

    @staticmethod
    def _profile(value: Any) -> dict[str, str]:
        if (not isinstance(value, dict) or set(value) != {"name", "version", "digest"}
                or not isinstance(value.get("name"), str) or not value["name"]
                or not isinstance(value.get("version"), str) or not value["version"]
                or not isinstance(value.get("digest"), str)
                or not re.fullmatch(r"[A-Fa-f0-9]{64}", value["digest"])):
            raise KnowledgeError("invalid_request", "index_profile must include name, version, and digest")
        return value

    @staticmethod
    def _json_object(value: Any, field: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise KnowledgeError("invalid_request", f"{field} must be an object")
        return value

    def _create_payload(self, request: Any) -> dict[str, Any]:
        required = {"scope", "source_kind", "content", "provenance", "retention_policy", "index_profile"}
        allowed = required | {"canonical_locator", "request_id"}
        if not isinstance(request, dict) or set(request) - allowed or not required.issubset(request):
            raise KnowledgeError("invalid_request", "create request has missing or unknown fields")
        scope = self._scope(request["scope"])
        if not isinstance(request["source_kind"], str) or not 1 <= len(request["source_kind"]) <= 128:
            raise KnowledgeError("invalid_request", "source_kind is invalid")
        if not isinstance(request["content"], str) or not request["content"].strip():
            raise KnowledgeError("invalid_request", "content must be a non-empty string")
        if len(request["content"].encode("utf-8")) > 262144:
            raise KnowledgeError("source_too_large", "content exceeds the CE proof-of-concept source limit", 422)
        locator = request.get("canonical_locator")
        if locator is not None and (not isinstance(locator, str) or len(locator) > 4096):
            raise KnowledgeError("invalid_request", "canonical_locator is invalid")
        return {
            "scope": scope, "source_kind": request["source_kind"], "canonical_locator": locator,
            "content": request["content"], "provenance": self._json_object(request["provenance"], "provenance"),
            "retention_policy": self._json_object(request["retention_policy"], "retention_policy"),
            "index_profile": self._profile(request["index_profile"]),
        }

    def _record_operation(self, db, source_key, revision, sequence, status, indexing_status, request_id, index_profile):
        operation_id = "knowledge:op:" + secrets.token_hex(16)
        db.execute("""INSERT INTO knowledge_operations(operation_id,source_key,revision,revision_sequence,
                      status,indexing_status,request_id,index_profile_json) VALUES(?,?,?,?,?,?,?,?)""",
                   (operation_id, source_key, revision, sequence, status, indexing_status, request_id,
                    json.dumps(index_profile, sort_keys=True)))
        return operation_id

    def _mutation_response(self, row, request_id: str) -> dict[str, Any]:
        return {"operation_id": row["operation_id"], "source_id": "knowledge:" + row["source_key"],
                "revision": row["revision"], "revision_sequence": row["revision_sequence"],
                "status": row["status"], "indexing_status": row["indexing_status"],
                "index_profile": json.loads(row["index_profile_json"]),
                "request_id": request_id}

    def _profile_from_revision(self, source_key: str, sequence: int) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT index_profile_json FROM knowledge_revisions WHERE source_key=? AND revision_sequence=?",
                             (source_key, sequence)).fetchone()
        return json.loads(row["index_profile_json"]) if row else {}

    def _idempotent_response(self, db, key: str, digest: str, request_id: str):
        row = db.execute("""SELECT i.payload_hash,o.* FROM knowledge_idempotency i
                            JOIN knowledge_operations o ON o.operation_id=i.operation_id
                            WHERE i.idempotency_key=?""", (key,)).fetchone()
        if row is None:
            return None
        if row["payload_hash"] != digest:
            raise KnowledgeError("idempotency_conflict", "Idempotency-Key was reused with a different payload", 409)
        return self._mutation_response(row, request_id)

    def _enqueue_graph_projection(self, db, operation_id: str, source_key: str, revision: str,
                                 revision_sequence: int, scope: dict[str, str], source_kind: str,
                                 content: str, provenance: dict[str, Any]) -> None:
        row = db.execute("SELECT next_sequence FROM knowledge_graph_sequence WHERE singleton=1").fetchone()
        sequence = int(row["next_sequence"])
        db.execute("UPDATE knowledge_graph_sequence SET next_sequence=? WHERE singleton=1", (sequence + 1,))
        source_id = "knowledge:" + source_key
        payload = {"operation_id": operation_id, "source_id": source_id, "source_revision": revision,
                   "revision_sequence": revision_sequence, "owner_projection_sequence": sequence,
                   "scope": scope, "nodes": [{"node_id": source_id, "node_type": "knowledge",
                   "label": content[:1024], "aliases": [], "properties": {"source_kind": source_kind},
                   "provenance": provenance}], "edges": []}
        db.execute("""INSERT INTO knowledge_graph_journal(operation_id,owner_projection_sequence,operation_kind,
                      source_id,revision_sequence,payload_json,status) VALUES(?,?,?,?,?,?,'pending')""",
                   (operation_id, sequence, "project", source_id, revision_sequence,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
        db.execute("UPDATE knowledge_operations SET graph_status='pending' WHERE operation_id=?", (operation_id,))

    def _enqueue_graph_deletion(self, db, operation_id: str, source_key: str, revision: str,
                                revision_sequence: int, scope: dict[str, str]) -> None:
        row = db.execute("SELECT next_sequence FROM knowledge_graph_sequence WHERE singleton=1").fetchone()
        sequence = int(row["next_sequence"])
        db.execute("UPDATE knowledge_graph_sequence SET next_sequence=? WHERE singleton=1", (sequence + 1,))
        source_id = "knowledge:" + source_key
        payload = {"operation_id": operation_id, "source_id": source_id, "source_revision": revision,
                   "revision_sequence": revision_sequence, "owner_projection_sequence": sequence,
                   "scope": scope, "delete_scope": "source"}
        db.execute("""INSERT INTO knowledge_graph_journal(operation_id,owner_projection_sequence,operation_kind,
                      source_id,revision_sequence,payload_json,status) VALUES(?,?,?,?,?,?,'pending')""",
                   (operation_id, sequence, "delete", source_id, revision_sequence,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
        db.execute("UPDATE knowledge_operations SET graph_status='pending' WHERE operation_id=?", (operation_id,))

    def pending_graph_projections(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT operation_id,owner_projection_sequence,operation_kind,payload_json
                                 FROM knowledge_graph_journal WHERE status IN ('pending','failed')
                                 ORDER BY owner_projection_sequence""").fetchall()
        return [{"operation_id": row["operation_id"], "owner_projection_sequence": row["owner_projection_sequence"],
                 "operation_kind": row["operation_kind"], "payload": json.loads(row["payload_json"])} for row in rows]

    def update_graph_operation(self, operation_id: str, graph_status: str, error: str | None = None) -> dict[str, Any]:
        if graph_status not in {"indexed", "graph_failed"}:
            raise KnowledgeError("invalid_request", "graph status is invalid")
        with self._lock, self._connect() as db:
            journal = db.execute("SELECT status FROM knowledge_graph_journal WHERE operation_id=?", (operation_id,)).fetchone()
            operation = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
            if journal is None or operation is None:
                raise KnowledgeError("not_found", "Knowledge Graph projection operation was not found", 404)
            applied = graph_status == "indexed"
            db.execute("UPDATE knowledge_graph_journal SET status=?,last_error=?,updated_at=CURRENT_TIMESTAMP WHERE operation_id=?",
                       ("applied" if applied else "failed", None if applied else (error or "Graph request failed")[:512], operation_id))
            status = "complete" if applied and operation["indexing_status"] == "indexed" else ("failed" if not applied else "pending")
            db.execute("UPDATE knowledge_operations SET graph_status=?,status=? WHERE operation_id=?",
                       (graph_status, status, operation_id))
            row = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
            return self._mutation_response(row, row["request_id"])

    def create(self, request: Any, idempotency_key: str, request_id: str) -> tuple[int, dict[str, Any]]:
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise KnowledgeError("invalid_request", "Idempotency-Key is required")
        payload = self._create_payload(request)
        digest = self._hash(payload)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_response(db, idempotency_key, digest, request_id)
            if prior is not None:
                return 202, prior
            source_key = "src-" + secrets.token_hex(12)
            revision = "rev-" + secrets.token_hex(12)
            sequence = 1
            db.execute("""INSERT INTO knowledge_sources(source_key,scope_json,source_kind,canonical_locator,
                       retention_policy_json,current_revision,revision_sequence,status)
                       VALUES(?,?,?,?,?,?,?,'active')""",
                       (source_key, json.dumps(payload["scope"], sort_keys=True), payload["source_kind"],
                        payload["canonical_locator"], json.dumps(payload["retention_policy"], sort_keys=True),
                        revision, sequence))
            db.execute("""INSERT INTO knowledge_revisions(source_key,revision,revision_sequence,content,
                       provenance_json,index_profile_json) VALUES(?,?,?,?,?,?)""",
                       (source_key, revision, sequence, payload["content"], json.dumps(payload["provenance"], sort_keys=True),
                        json.dumps(payload["index_profile"], sort_keys=True)))
            operation_id = self._record_operation(db, source_key, revision, sequence, "accepted", "pending_index", request_id, payload["index_profile"])
            self._enqueue_graph_projection(db, operation_id, source_key, revision, sequence, payload["scope"],
                                           payload["source_kind"], payload["content"], payload["provenance"])
            db.execute("INSERT INTO knowledge_idempotency(idempotency_key,payload_hash,operation_id) VALUES(?,?,?)",
                       (idempotency_key, digest, operation_id))
            row = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
            return 202, self._mutation_response(row, request_id)

    def read(self, source_key: str, scope: Any, request_id: str = "knowledge") -> dict[str, Any]:
        source_key = self._id(source_key, "source_key")
        scope = self._scope(scope)
        with self._connect() as db:
            row = db.execute("""SELECT s.*,r.revision,r.revision_sequence,r.content,r.provenance_json,
                                r.index_profile_json FROM knowledge_sources s JOIN knowledge_revisions r
                                ON r.source_key=s.source_key AND r.revision_sequence=s.revision_sequence
                                WHERE s.source_key=?""", (source_key,)).fetchone()
        if row is None or row["status"] != "active":
            raise KnowledgeError("not_found", "knowledge source was not found", 404)
        if json.loads(row["scope_json"]) != scope:
            raise KnowledgeError("not_found", "knowledge source was not found", 404)
        result = {"source_id": "knowledge:" + source_key, "source_revision": row["revision"],
                  "revision_sequence": row["revision_sequence"], "scope": json.loads(row["scope_json"]),
                  "source_kind": row["source_kind"], "content": row["content"],
                  "provenance": json.loads(row["provenance_json"]),
                  "retention_policy": json.loads(row["retention_policy_json"]),
                  "index_profile": json.loads(row["index_profile_json"]), "status": row["status"],
                  "request_id": request_id}
        if row["canonical_locator"] is not None:
            result["canonical_locator"] = row["canonical_locator"]
        return result

    def read_for_ingestion(self, source_key: str, scope: Any, revision_sequence: int) -> dict[str, Any]:
        source_key = self._id(source_key, "source_key")
        scope = self._scope(scope)
        with self._connect() as db:
            row = db.execute("""SELECT s.scope_json,s.status,s.revision_sequence AS current_sequence,r.content,r.revision,r.revision_sequence
                                FROM knowledge_sources s JOIN knowledge_revisions r ON r.source_key=s.source_key
                                WHERE s.source_key=? AND r.revision_sequence=?""",
                             (source_key, revision_sequence)).fetchone()
        if row is None or row["status"] != "active" or row["current_sequence"] != revision_sequence:
            raise KnowledgeError("stale_revision", "knowledge source revision is no longer active", 409)
        if json.loads(row["scope_json"]) != scope:
            raise KnowledgeError("not_found", "knowledge source was not found", 404)
        return {"source_id": "knowledge:" + source_key, "content": row["content"],
                "scope": json.loads(row["scope_json"]), "revision": row["revision"],
                "revision_sequence": row["revision_sequence"]}

    def update(self, source_key: str, request: Any, idempotency_key: str, request_id: str, scope: Any) -> tuple[int, dict[str, Any]]:
        source_key = self._id(source_key, "source_key")
        if not isinstance(request, dict) or set(request) - {"expected_base_revision_sequence", "content", "provenance", "index_profile", "request_id"}:
            raise KnowledgeError("invalid_request", "revision request has unknown fields")
        if not {"expected_base_revision_sequence", "content", "provenance", "index_profile"}.issubset(request):
            raise KnowledgeError("invalid_request", "revision request has missing fields")
        if type(request["expected_base_revision_sequence"]) is not int or request["expected_base_revision_sequence"] < 1:
            raise KnowledgeError("invalid_request", "expected_base_revision_sequence is invalid")
        payload = {"source_key": source_key, "scope": self._scope(scope),
                   "expected_base_revision_sequence": request["expected_base_revision_sequence"],
                   "content": request["content"], "provenance": self._json_object(request["provenance"], "provenance"),
                   "index_profile": self._profile(request["index_profile"])}
        if not isinstance(payload["content"], str) or not payload["content"].strip():
            raise KnowledgeError("invalid_request", "content must be a non-empty string")
        if len(payload["content"].encode("utf-8")) > 262144:
            raise KnowledgeError("source_too_large", "content exceeds the CE proof-of-concept source limit", 422)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise KnowledgeError("invalid_request", "Idempotency-Key is required")
        digest = self._hash(payload)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_response(db, idempotency_key, digest, request_id)
            if prior is not None:
                return 202, prior
            current = db.execute("SELECT * FROM knowledge_sources WHERE source_key=?", (source_key,)).fetchone()
            if current is None or current["status"] != "active" or json.loads(current["scope_json"]) != payload["scope"]:
                raise KnowledgeError("not_found", "knowledge source was not found", 404)
            if current["revision_sequence"] != payload["expected_base_revision_sequence"]:
                raise KnowledgeError("revision_conflict", "expected base revision does not match current revision", 409)
            sequence = current["revision_sequence"] + 1
            revision = "rev-" + secrets.token_hex(12)
            db.execute("INSERT INTO knowledge_revisions(source_key,revision,revision_sequence,content,provenance_json,index_profile_json) VALUES(?,?,?,?,?,?)",
                       (source_key, revision, sequence, payload["content"], json.dumps(payload["provenance"], sort_keys=True),
                        json.dumps(payload["index_profile"], sort_keys=True)))
            db.execute("UPDATE knowledge_sources SET current_revision=?,revision_sequence=? WHERE source_key=?",
                       (revision, sequence, source_key))
            operation_id = self._record_operation(db, source_key, revision, sequence, "accepted", "pending_index", request_id, payload["index_profile"])
            self._enqueue_graph_projection(db, operation_id, source_key, revision, sequence, payload["scope"],
                                           current["source_kind"], payload["content"], payload["provenance"])
            db.execute("INSERT INTO knowledge_idempotency(idempotency_key,payload_hash,operation_id) VALUES(?,?,?)",
                       (idempotency_key, digest, operation_id))
            row = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
            return 202, self._mutation_response(row, request_id)

    def delete(self, source_key: str, scope: Any, delete_scope: str, idempotency_key: str, request_id: str):
        source_key = self._id(source_key, "source_key")
        scope = self._scope(scope)
        if delete_scope != "source":
            raise KnowledgeError("invalid_request", "delete_scope must be source")
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise KnowledgeError("invalid_request", "Idempotency-Key is required")
        digest = self._hash({"source_key": source_key, "scope": scope, "delete_scope": delete_scope})
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_response(db, idempotency_key, digest, request_id)
            if prior is not None:
                prior.pop("index_profile", None)
                graph = db.execute("SELECT graph_status FROM knowledge_operations WHERE operation_id=?",
                                   (prior["operation_id"],)).fetchone()
                return 202, {**prior, "graph_status": graph["graph_status"] if graph else "pending"}
            current = db.execute("SELECT * FROM knowledge_sources WHERE source_key=?", (source_key,)).fetchone()
            if current is None or current["status"] != "active" or json.loads(current["scope_json"]) != scope:
                raise KnowledgeError("not_found", "knowledge source was not found", 404)
            active_revision = db.execute("SELECT index_profile_json FROM knowledge_revisions WHERE source_key=? AND revision_sequence=?",
                                         (source_key, current["revision_sequence"])).fetchone()
            active_profile = json.loads(active_revision["index_profile_json"])
            sequence = current["revision_sequence"] + 1
            revision = "tombstone-" + secrets.token_hex(12)
            db.execute("UPDATE knowledge_sources SET status='tombstoned',current_revision=?,revision_sequence=? WHERE source_key=?",
                       (revision, sequence, source_key))
            # A tombstone revision is immutable lifecycle evidence, with no source content.
            db.execute("INSERT INTO knowledge_revisions(source_key,revision,revision_sequence,content,provenance_json,index_profile_json) VALUES(?,?,?,?,?,?)",
                       (source_key, revision, sequence, "", "{}", json.dumps(active_profile, sort_keys=True)))
            operation_id = self._record_operation(db, source_key, revision, sequence, "pending", "pending_index", request_id, active_profile)
            self._enqueue_graph_deletion(db, operation_id, source_key, revision, sequence, scope)
            db.execute("INSERT INTO knowledge_idempotency(idempotency_key,payload_hash,operation_id) VALUES(?,?,?)",
                       (idempotency_key, digest, operation_id))
            row = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
            response = self._mutation_response(row, request_id)
            response.pop("index_profile", None)
            return 202, {**response, "graph_status": "pending"}

    def deletion_details(self, operation_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("""SELECT o.*,s.scope_json FROM knowledge_operations o
                                JOIN knowledge_sources s ON s.source_key=o.source_key
                                WHERE o.operation_id=?""", (operation_id,)).fetchone()
        if row is None:
            raise KnowledgeError("not_found", "knowledge operation was not found", 404)
        return {"source_id": "knowledge:" + row["source_key"], "revision_sequence": row["revision_sequence"],
                "scope": json.loads(row["scope_json"]), "index_profile": json.loads(row["index_profile_json"])}

    def update_operation(self, operation_id: str, status: str, indexing_status: str) -> dict[str, Any]:
        with self._connect() as db:
            row_before = db.execute("SELECT graph_status FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row_before is None:
                raise KnowledgeError("not_found", "knowledge operation was not found", 404)
            graph_status = row_before["graph_status"]
            if indexing_status == "indexed" and graph_status == "indexed" and status in {"complete", "pending", "accepted"}:
                status = "complete"
            elif status == "complete" and graph_status != "indexed":
                status = "pending"
            db.execute("UPDATE knowledge_operations SET status=?,indexing_status=? WHERE operation_id=?",
                       (status, indexing_status, operation_id))
            row = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None:
            raise KnowledgeError("not_found", "knowledge operation was not found", 404)
        return self._mutation_response(row, row["request_id"])

    def operation(self, operation_id: str, source_key: str | None, request_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM knowledge_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None or (source_key is not None and row["source_key"] != source_key):
            raise KnowledgeError("not_found", "knowledge operation was not found", 404)
        return {"operation_id": row["operation_id"], "status": row["status"],
                "canonical_status": "tombstoned" if row["revision"].startswith("tombstone-") else "committed",
                "indexing_status": row["indexing_status"], "revision_sequence": row["revision_sequence"],
                "graph_status": row["graph_status"], "request_id": request_id}

    def verify_revisions(self, items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise KnowledgeError("invalid_request", "items must contain 1 to 100 entries")
        results = []
        with self._connect() as db:
            for item in items:
                if not isinstance(item, dict) or set(item) != {"source_id", "revision_sequence"}:
                    raise KnowledgeError("invalid_request", "each verification item requires source_id and revision_sequence")
                source_id = item["source_id"]
                sequence = item["revision_sequence"]
                if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id) or type(sequence) is not int or sequence < 1:
                    raise KnowledgeError("invalid_request", "source_id or revision_sequence is invalid")
                source_key = source_id.removeprefix("knowledge:")
                row = db.execute("SELECT status,revision_sequence FROM knowledge_sources WHERE source_key=?", (source_key,)).fetchone()
                if row is None:
                    status = "not_found"
                elif row["status"] != "active":
                    status = "tombstoned"
                elif row["revision_sequence"] == sequence:
                    status = "current"
                else:
                    status = "stale"
                result = {"source_id": source_id, "requested_revision_sequence": sequence, "status": status}
                if row is not None and row["status"] == "active":
                    result["canonical_revision_sequence"] = row["revision_sequence"]
                results.append(result)
        return results

    def handle(self, method: str, path: str, query: dict[str, list[str]], body: Any, headers: Any,
               request_id: str) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/api/v1/knowledge/health":
            return 200, {"service": "knowledge", "status": "alive", "request_id": request_id}
        if method == "GET" and path == "/api/v1/knowledge/ready":
            return 200, {"service": "knowledge", "status": "ready", "ready": True,
                         "checks": [{"name": "canonical_source_store", "status": "ok"}], "request_id": request_id}
        if method == "POST" and path == "/api/v1/knowledge/sources":
            return self.create(body, headers.get("Idempotency-Key", ""), request_id)
        if method == "POST" and path == "/api/v1/knowledge/sources/verify-revisions":
            if not isinstance(body, dict) or set(body) - {"items", "request_id"} or "items" not in body:
                raise KnowledgeError("invalid_request", "verification request has missing or unknown fields")
            return 200, {"results": self.verify_revisions(body["items"]), "request_id": request_id}
        if method == "POST" and path.startswith("/api/v1/knowledge/sources/") and path.endswith("/revisions"):
            source_key = unquote(path.split("/")[-2])
            scope = {"type": query.get("scope_type", [""])[0], "id": query.get("scope_id", [""])[0],
                     "visibility": query.get("visibility", [""])[0]}
            return self.update(source_key, body, headers.get("Idempotency-Key", ""), request_id, scope)
        if method == "DELETE" and path.startswith("/api/v1/knowledge/sources/"):
            source_key = unquote(path.rsplit("/", 1)[-1])
            scope = body.get("scope") if isinstance(body, dict) else None
            delete_scope = body.get("delete_scope") if isinstance(body, dict) else None
            return self.delete(source_key, scope, delete_scope, headers.get("Idempotency-Key", ""), request_id)
        if method == "GET" and path.startswith("/api/v1/knowledge/operations/"):
            return 200, self.operation(unquote(path.rsplit("/", 1)[-1]), None, request_id)
        if method == "GET" and path.startswith("/api/v1/knowledge/sources/"):
            parts = path.strip("/").split("/")
            source_key = unquote(parts[3]) if len(parts) == 4 else unquote(parts[4])
            scope = {"type": query.get("scope_type", [""])[0], "id": query.get("scope_id", [""])[0],
                     "visibility": query.get("visibility", [""])[0]}
            if len(parts) >= 6 and parts[-2] == "operations":
                return 200, self.operation(unquote(parts[-1]), source_key, request_id)
            return 200, self.read(source_key, scope, request_id)
        raise KnowledgeError("endpoint_not_found", "endpoint not found", 404)


_SERVICE: KnowledgeService | None = None
_SERVICE_LOCK = threading.Lock()


def get_knowledge_service() -> KnowledgeService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            path = os.environ.get("CE_KNOWLEDGE_DB_PATH", "~/.FlossWare/claude-ensemble/knowledge.sqlite3")
            _SERVICE = KnowledgeService(path)
        return _SERVICE
