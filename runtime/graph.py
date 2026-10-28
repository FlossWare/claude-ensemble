"""Durable, source-supported Graph service for Claude Ensemble.

Graph owns projected relationships and bounded traversal. Canonical Memory/Knowledge
content remains with its source owner; all cross-service freshness checks belong to Gateway.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SOURCE_ID = re.compile(r"^(memory|knowledge):[A-Za-z0-9._~-]{1,128}$")
MAX_SAFE_INTEGER = 9_007_199_254_740_991


class GraphError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _string(value: Any, field: str, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value):
        raise GraphError("invalid_request", f"{field} is invalid")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise GraphError("invalid_request", f"{field} contains invalid Unicode") from exc
    return value


def _sequence(value: Any, field: str, *, minimum: int = 1) -> int:
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise GraphError("invalid_request", f"{field} is invalid")
    return value


def _scope(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"type", "id", "visibility"}:
        raise GraphError("invalid_scope", "scope must contain exactly type, id, and visibility")
    if value["type"] not in {"user", "project", "shared", "global"}:
        raise GraphError("invalid_scope", "scope.type is invalid")
    if value["visibility"] not in {"private", "shared", "global"}:
        raise GraphError("invalid_scope", "scope.visibility is invalid")
    return {"type": value["type"], "id": _string(value["id"], "scope.id", 256),
            "visibility": value["visibility"]}


class GraphService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS graph_sources(
                    source_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    revision_sequence INTEGER NOT NULL, source_revision TEXT NOT NULL,
                    scope_json TEXT NOT NULL, status TEXT NOT NULL,
                    payload_hash TEXT NOT NULL, owner_projection_sequence INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS graph_nodes(
                    scope_json TEXT NOT NULL, node_id TEXT NOT NULL, source_id TEXT NOT NULL,
                    source_revision TEXT NOT NULL, revision_sequence INTEGER NOT NULL,
                    node_type TEXT NOT NULL, label TEXT NOT NULL, aliases_json TEXT NOT NULL,
                    properties_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
                    PRIMARY KEY(scope_json,node_id,source_id)
                );
                CREATE INDEX IF NOT EXISTS graph_nodes_scope_label
                    ON graph_nodes(scope_json,label);
                CREATE TABLE IF NOT EXISTS graph_edges(
                    edge_id TEXT NOT NULL, scope_json TEXT NOT NULL,
                    source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL, directed INTEGER NOT NULL,
                    source_id TEXT NOT NULL, source_revision TEXT NOT NULL,
                    revision_sequence INTEGER NOT NULL, source_edge_id TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    PRIMARY KEY(edge_id,source_id,source_edge_id)
                );
                CREATE INDEX IF NOT EXISTS graph_edges_scope_source
                    ON graph_edges(scope_json,source_node_id);
                CREATE INDEX IF NOT EXISTS graph_edges_scope_target
                    ON graph_edges(scope_json,target_node_id);
                CREATE TABLE IF NOT EXISTS graph_operations(
                    operation_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL, owner TEXT NOT NULL,
                    owner_projection_sequence INTEGER NOT NULL, source_id TEXT NOT NULL,
                    revision_sequence INTEGER NOT NULL, status TEXT NOT NULL,
                    terminal_disposition TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS graph_owner_events(
                    owner TEXT NOT NULL, sequence INTEGER NOT NULL,
                    operation_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
                    terminal_disposition TEXT NOT NULL,
                    PRIMARY KEY(owner,sequence)
                );
                CREATE TABLE IF NOT EXISTS graph_owner_state(
                    owner TEXT PRIMARY KEY, terminal_sequence INTEGER NOT NULL DEFAULT 0,
                    sealed_sequence INTEGER, reconciliation_required INTEGER NOT NULL DEFAULT 0
                );
            """)
            for owner in ("memory", "knowledge"):
                db.execute("INSERT OR IGNORE INTO graph_owner_state(owner) VALUES(?)", (owner,))

    @staticmethod
    def _owner(source_id: str) -> str:
        match = SOURCE_ID.fullmatch(source_id)
        if not match:
            raise GraphError("invalid_request", "source_id is invalid")
        return match.group(1)

    @staticmethod
    def _ready(db: sqlite3.Connection) -> bool:
        rows = db.execute("SELECT terminal_sequence,sealed_sequence,reconciliation_required FROM graph_owner_state").fetchall()
        return len(rows) == 2 and all(
            row["sealed_sequence"] is not None
            and row["terminal_sequence"] >= row["sealed_sequence"]
            and not row["reconciliation_required"] for row in rows
        )

    @staticmethod
    def _advance(db: sqlite3.Connection, owner: str) -> int:
        row = db.execute("SELECT terminal_sequence FROM graph_owner_state WHERE owner=?", (owner,)).fetchone()
        terminal = int(row["terminal_sequence"])
        while db.execute(
            "SELECT 1 FROM graph_owner_events WHERE owner=? AND sequence=? AND terminal_disposition IS NOT NULL",
            (owner, terminal + 1),
        ).fetchone():
            terminal += 1
        db.execute("UPDATE graph_owner_state SET terminal_sequence=? WHERE owner=?", (terminal, owner))
        return terminal

    @staticmethod
    def _store_event(db: sqlite3.Connection, owner: str, sequence: int, operation_id: str,
                     payload_hash: str, disposition: str) -> None:
        prior = db.execute("SELECT * FROM graph_owner_events WHERE owner=? AND sequence=?",
                           (owner, sequence)).fetchone()
        if prior:
            if prior["operation_id"] != operation_id or prior["payload_hash"] != payload_hash:
                db.execute("UPDATE graph_owner_state SET reconciliation_required=1 WHERE owner=?", (owner,))
                db.commit()
                raise GraphError("revision_conflict", "owner projection sequence was reused with a different operation or payload", 409)
            return
        db.execute("INSERT INTO graph_owner_events VALUES(?,?,?,?,?)",
                   (owner, sequence, operation_id, payload_hash, disposition))
        GraphService._advance(db, owner)

    @staticmethod
    def _cached_operation(db: sqlite3.Connection, operation_id: str, payload_hash: str):
        row = db.execute("SELECT payload_hash,response_json FROM graph_operations WHERE operation_id=?",
                         (operation_id,)).fetchone()
        if not row:
            return None
        if row["payload_hash"] != payload_hash:
            raise GraphError("idempotency_conflict", "operation_id was reused with a different payload", 409)
        return json.loads(row["response_json"])

    @staticmethod
    def _persist_operation(db: sqlite3.Connection, response: dict[str, Any], payload_hash: str,
                           owner: str, sequence: int, source_id: str, revision_sequence: int,
                           disposition: str) -> None:
        response["status"] = "superseded" if disposition == "superseded" else "complete"
        response["terminal_disposition"] = disposition
        db.execute(
            "INSERT INTO graph_operations VALUES(?,?,?,?,?,?,?,?,?)",
            (response["operation_id"], payload_hash, _json(response), owner, sequence, source_id,
             revision_sequence, response["status"], disposition),
        )

    def project(self, request: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        if not isinstance(request, dict):
            raise GraphError("invalid_request", "request must be an object")
        allowed = {"operation_id", "source_id", "source_revision", "revision_sequence",
                   "owner_projection_sequence", "scope", "nodes", "edges", "request_id"}
        required = allowed - {"request_id"}
        if set(request) - allowed or required - set(request):
            raise GraphError("invalid_request", "projection request has missing or unknown fields")
        operation_id = _string(request["operation_id"], "operation_id", 128)
        source_id = _string(request["source_id"], "source_id", 138)
        owner = self._owner(source_id)
        source_revision = _string(request["source_revision"], "source_revision", 256)
        revision_sequence = _sequence(request["revision_sequence"], "revision_sequence")
        owner_sequence = _sequence(request["owner_projection_sequence"], "owner_projection_sequence")
        scope = _scope(request["scope"])
        scope_json = _json(scope)
        nodes, edges = request["nodes"], request["edges"]
        if not isinstance(nodes, list) or len(nodes) > 256 or not isinstance(edges, list) or len(edges) > 512:
            raise GraphError("source_too_large", "projection exceeds node or edge limits", 422)
        canonical_nodes: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        for item in nodes:
            if not isinstance(item, dict) or set(item) - {"node_id", "node_type", "label", "aliases", "properties", "provenance"}:
                raise GraphError("invalid_request", "node has unknown fields")
            if not {"node_id", "node_type", "label"} <= set(item):
                raise GraphError("invalid_request", "node is missing required fields")
            node_id = _string(item["node_id"], "node.node_id", 512)
            if node_id in node_ids:
                raise GraphError("invalid_request", "projection contains duplicate node_id values")
            node_ids.add(node_id)
            aliases = item.get("aliases", [])
            if not isinstance(aliases, list) or len(aliases) > 32:
                raise GraphError("invalid_request", "node.aliases exceeds its bound")
            aliases = [_string(v, "node.alias", 512) for v in aliases]
            properties = item.get("properties", {})
            provenance = item.get("provenance", {})
            if not isinstance(properties, dict) or not isinstance(provenance, dict):
                raise GraphError("invalid_request", "node properties and provenance must be objects")
            canonical_nodes.append({
                "node_id": node_id, "node_type": _string(item["node_type"], "node.node_type", 128),
                "label": _string(item["label"], "node.label", 512), "aliases": aliases,
                "properties": properties, "provenance": provenance,
            })
        canonical_edges: list[dict[str, Any]] = []
        source_edge_ids: set[str] = set()
        for item in edges:
            if not isinstance(item, dict) or set(item) - {"edge_id", "source_node_id", "target_node_id",
                                                            "relationship_type", "directed", "provenance"}:
                raise GraphError("invalid_request", "edge has unknown fields")
            if not {"edge_id", "source_node_id", "target_node_id", "relationship_type", "directed"} <= set(item):
                raise GraphError("invalid_request", "edge is missing required fields")
            source_edge_id = _string(item["edge_id"], "edge.edge_id", 512)
            if source_edge_id in source_edge_ids:
                raise GraphError("invalid_request", "projection contains duplicate source edge IDs")
            source_edge_ids.add(source_edge_id)
            source_node_id = _string(item["source_node_id"], "edge.source_node_id", 512)
            target_node_id = _string(item["target_node_id"], "edge.target_node_id", 512)
            relationship_type = unicodedata.normalize("NFC", _string(item["relationship_type"], "edge.relationship_type", 128))
            if type(item["directed"]) is not bool:
                raise GraphError("invalid_request", "edge.directed must be a boolean")
            directed = item["directed"]
            if not directed and target_node_id < source_node_id:
                source_node_id, target_node_id = target_node_id, source_node_id
            provenance = item.get("provenance", {})
            if not isinstance(provenance, dict):
                raise GraphError("invalid_request", "edge.provenance must be an object")
            identity = [scope["type"], scope["id"], scope["visibility"], source_node_id,
                        target_node_id, relationship_type, directed]
            edge_id = "rel:" + _digest(identity)
            canonical_edges.append({
                "edge_id": edge_id, "source_node_id": source_node_id, "target_node_id": target_node_id,
                "relationship_type": relationship_type, "directed": directed,
                "source_edge_id": source_edge_id, "provenance": provenance,
            })
        payload = {k: request[k] for k in required if k != "request_id"}
        payload_hash = _digest(payload)
        source_payload_hash = _digest({"source_revision": source_revision, "revision_sequence": revision_sequence,
                                       "scope": scope, "nodes": canonical_nodes, "edges": canonical_edges})
        response = {"operation_id": operation_id, "source_id": source_id,
                    "revision_sequence": revision_sequence, "request_id": request_id,
                    "owner": owner, "owner_projection_sequence": owner_sequence}
        with self._connect() as db:
            cached = self._cached_operation(db, operation_id, payload_hash)
            if cached is not None:
                return 202, cached
            prior_event = db.execute("SELECT operation_id,payload_hash FROM graph_owner_events WHERE owner=? AND sequence=?",
                                     (owner, owner_sequence)).fetchone()
            if prior_event:
                if prior_event["operation_id"] != operation_id or prior_event["payload_hash"] != payload_hash:
                    db.execute("UPDATE graph_owner_state SET reconciliation_required=1 WHERE owner=?", (owner,))
                    db.commit()
                    raise GraphError("revision_conflict", "owner projection sequence was reused with a different operation or payload", 409)
            current = db.execute("SELECT * FROM graph_sources WHERE source_id=?", (source_id,)).fetchone()
            if current and revision_sequence <= current["revision_sequence"]:
                if revision_sequence == current["revision_sequence"] and current["status"] == "active":
                    if current["source_revision"] != source_revision or current["payload_hash"] != source_payload_hash:
                        raise GraphError("revision_conflict", "equal source revision was reused with a different projection", 409)
                disposition = "superseded"
                self._store_event(db, owner, owner_sequence, operation_id, payload_hash, disposition)
                self._persist_operation(db, response, payload_hash, owner, owner_sequence, source_id,
                                        revision_sequence, disposition)
                return 202, response
            incoming_ids = {n["node_id"] for n in canonical_nodes}
            for edge in canonical_edges:
                for endpoint in (edge["source_node_id"], edge["target_node_id"]):
                    if endpoint in incoming_ids:
                        continue
                    exists = db.execute(
                        "SELECT 1 FROM graph_nodes WHERE scope_json=? AND node_id=? AND source_id<>? LIMIT 1",
                        (scope_json, endpoint, source_id),
                    ).fetchone()
                    if not exists:
                        raise GraphError("missing_endpoint_node", "edge endpoint has no supported node in the requested scope", 404)
            db.execute("DELETE FROM graph_nodes WHERE source_id=?", (source_id,))
            db.execute("DELETE FROM graph_edges WHERE source_id=?", (source_id,))
            for node in canonical_nodes:
                db.execute("INSERT INTO graph_nodes VALUES(?,?,?,?,?,?,?,?,?,?)", (
                    scope_json, node["node_id"], source_id, source_revision, revision_sequence,
                    node["node_type"], node["label"], _json(node["aliases"]), _json(node["properties"]),
                    _json(node["provenance"]),
                ))
            for edge in canonical_edges:
                db.execute("INSERT INTO graph_edges VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                    edge["edge_id"], scope_json, edge["source_node_id"], edge["target_node_id"],
                    edge["relationship_type"], int(edge["directed"]), source_id, source_revision,
                    revision_sequence, edge["source_edge_id"], _json(edge["provenance"]),
                ))
            db.execute(
                "INSERT INTO graph_sources VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET "
                "owner=excluded.owner,revision_sequence=excluded.revision_sequence,source_revision=excluded.source_revision,"
                "scope_json=excluded.scope_json,status='active',payload_hash=excluded.payload_hash,"
                "owner_projection_sequence=excluded.owner_projection_sequence",
                (source_id, owner, revision_sequence, source_revision, scope_json, "active", source_payload_hash, owner_sequence),
            )
            self._store_event(db, owner, owner_sequence, operation_id, payload_hash, "applied")
            self._persist_operation(db, response, payload_hash, owner, owner_sequence, source_id,
                                    revision_sequence, "applied")
        return 202, response

    def delete_source(self, request: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        if not isinstance(request, dict):
            raise GraphError("invalid_request", "request must be an object")
        allowed = {"operation_id", "source_id", "revision_sequence", "owner_projection_sequence",
                   "scope", "delete_scope", "source_revision", "request_id"}
        required = {"operation_id", "source_id", "revision_sequence", "owner_projection_sequence", "scope", "delete_scope"}
        if set(request) - allowed or required - set(request):
            raise GraphError("invalid_request", "deletion request has missing or unknown fields")
        operation_id = _string(request["operation_id"], "operation_id", 128)
        source_id = _string(request["source_id"], "source_id", 138)
        owner = self._owner(source_id)
        revision_sequence = _sequence(request["revision_sequence"], "revision_sequence")
        owner_sequence = _sequence(request["owner_projection_sequence"], "owner_projection_sequence")
        scope = _scope(request["scope"])
        if request["delete_scope"] != "source":
            raise GraphError("invalid_request", "delete_scope must be source")
        source_revision = request.get("source_revision", "tombstone")
        if not isinstance(source_revision, str) or not source_revision:
            raise GraphError("invalid_request", "source_revision is invalid")
        payload_hash = _digest({k: v for k, v in request.items() if k != "request_id"})
        response = {"operation_id": operation_id, "source_id": source_id,
                    "revision_sequence": revision_sequence, "request_id": request_id,
                    "owner": owner, "owner_projection_sequence": owner_sequence}
        with self._connect() as db:
            cached = self._cached_operation(db, operation_id, payload_hash)
            if cached is not None:
                return 202, cached
            prior_event = db.execute("SELECT operation_id,payload_hash FROM graph_owner_events WHERE owner=? AND sequence=?",
                                     (owner, owner_sequence)).fetchone()
            if prior_event:
                if prior_event["operation_id"] != operation_id or prior_event["payload_hash"] != payload_hash:
                    db.execute("UPDATE graph_owner_state SET reconciliation_required=1 WHERE owner=?", (owner,))
                    raise GraphError("revision_conflict", "owner projection sequence was reused with a different operation or payload", 409)
            current = db.execute("SELECT * FROM graph_sources WHERE source_id=?", (source_id,)).fetchone()
            if current and revision_sequence <= current["revision_sequence"]:
                raise GraphError("revision_conflict", "tombstone sequence must exceed the source high-water mark", 409)
            scope_json = _json(scope)
            if current and current["scope_json"] != scope_json:
                raise GraphError("invalid_scope", "source deletion scope does not match the active source", 409)
            db.execute("DELETE FROM graph_nodes WHERE source_id=?", (source_id,))
            db.execute("DELETE FROM graph_edges WHERE source_id=?", (source_id,))
            db.execute(
                "INSERT INTO graph_sources VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET "
                "revision_sequence=excluded.revision_sequence,source_revision=excluded.source_revision,"
                "scope_json=excluded.scope_json,status='tombstoned',payload_hash=excluded.payload_hash,"
                "owner_projection_sequence=excluded.owner_projection_sequence",
                (source_id, owner, revision_sequence, source_revision, scope_json, "tombstoned", payload_hash, owner_sequence),
            )
            self._store_event(db, owner, owner_sequence, operation_id, payload_hash, "applied")
            self._persist_operation(db, response, payload_hash, owner, owner_sequence, source_id,
                                    revision_sequence, "applied")
        return 202, response

    def checkpoint(self, request: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        if not isinstance(request, dict) or set(request) - {"owner", "sealed_projection_sequence", "request_id"} or not {"owner", "sealed_projection_sequence"} <= set(request):
            raise GraphError("invalid_request", "checkpoint request has missing or unknown fields")
        owner = request["owner"]
        if owner not in {"memory", "knowledge"}:
            raise GraphError("invalid_request", "owner must be memory or knowledge")
        sealed = _sequence(request["sealed_projection_sequence"], "sealed_projection_sequence", minimum=0)
        with self._connect() as db:
            state = db.execute("SELECT * FROM graph_owner_state WHERE owner=?", (owner,)).fetchone()
            if state["sealed_sequence"] is not None and sealed < state["sealed_sequence"]:
                raise GraphError("revision_conflict", "sealed projection checkpoint cannot move backwards", 409)
            db.execute("UPDATE graph_owner_state SET sealed_sequence=? WHERE owner=?", (sealed, owner))
            state = db.execute("SELECT * FROM graph_owner_state WHERE owner=?", (owner,)).fetchone()
            if state["terminal_sequence"] >= sealed:
                # The owner checkpoint is its durable assertion that replay through
                # this sealed journal position is consistent.
                db.execute("UPDATE graph_owner_state SET reconciliation_required=0 WHERE owner=?", (owner,))
                state = db.execute("SELECT * FROM graph_owner_state WHERE owner=?", (owner,)).fetchone()
            ready = state["terminal_sequence"] >= sealed and not state["reconciliation_required"]
            overall_ready = self._ready(db)
            response = {"owner": owner, "sealed_projection_sequence": sealed,
                        "terminal_projection_sequence": state["terminal_sequence"],
                        "ready": ready, "request_id": request_id}
            if not ready:
                db.commit()
                raise GraphError("graph_replay_incomplete", "Graph has not applied every owner projection through the sealed sequence", 409)
            return 200, response

    def operation(self, operation_id: str, request_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT response_json FROM graph_operations WHERE operation_id=?", (operation_id,)).fetchone()
            if not row:
                raise GraphError("not_found", "operation was not found", 404)
            response = json.loads(row["response_json"])
            response["request_id"] = request_id
            return response

    def manifest(self, query: dict[str, list[str]], request_id: str) -> dict[str, Any]:
        try:
            limit = int(query.get("limit", ["100"])[0])
            offset = int(query.get("cursor", ["0"])[0])
        except (TypeError, ValueError) as exc:
            raise GraphError("invalid_request", "manifest limit or cursor is invalid") from exc
        if not 1 <= limit <= 100 or offset < 0:
            raise GraphError("invalid_request", "manifest limit or cursor is outside bounds")
        owner_filter = query.get("owner", [None])[0]
        if owner_filter not in {None, "memory", "knowledge"}:
            raise GraphError("invalid_request", "manifest owner is invalid")
        with self._connect() as db:
            sql = "SELECT source_id,source_revision,revision_sequence,status,owner FROM graph_sources"
            args: list[Any] = []
            if owner_filter:
                sql += " WHERE owner=?"
                args.append(owner_filter)
            sql += " ORDER BY source_id LIMIT ? OFFSET ?"
            args.extend([limit + 1, offset])
            rows = db.execute(sql, args).fetchall()
            page, has_more = rows[:limit], len(rows) > limit
            watermarks = {row["owner"]: {"terminal_projection_sequence": row["terminal_sequence"],
                                         "sealed_projection_sequence": row["sealed_sequence"],
                                         "reconciliation_required": bool(row["reconciliation_required"])}
                          for row in db.execute("SELECT * FROM graph_owner_state")}
            return {"items": [{"source_id": row["source_id"], "source_revision": row["source_revision"],
                               "revision_sequence": row["revision_sequence"], "status": row["status"]}
                              for row in page],
                    "next_cursor": str(offset + limit) if has_more else None,
                    "owner_watermarks": watermarks, "ready": self._ready(db), "request_id": request_id}

    def traverse(self, request: Any, request_id: str) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise GraphError("invalid_request", "traversal request must be an object")
        allowed = {"scope", "start_node_ids", "entity_mentions", "relationship_types", "direction",
                   "max_depth", "max_visited_nodes", "limit", "request_id", "page_token"}
        if set(request) - allowed or "scope" not in request:
            raise GraphError("invalid_request", "traversal request has missing or unknown fields")
        if "page_token" in request:
            raise GraphError("invalid_request", "page_token is not supported in Graph v1")
        has_ids = "start_node_ids" in request
        has_mentions = "entity_mentions" in request
        if has_ids == has_mentions:
            raise GraphError("invalid_request", "exactly one of start_node_ids or entity_mentions is required")
        scope = _scope(request["scope"])
        scope_json = _json(scope)
        direction = request.get("direction", "both")
        if direction not in {"outgoing", "incoming", "both"}:
            raise GraphError("invalid_request", "direction is invalid")
        max_depth = request.get("max_depth", 3)
        max_visited = request.get("max_visited_nodes", 500)
        limit = request.get("limit", 10)
        if type(max_depth) is not int or not 1 <= max_depth <= 3:
            raise GraphError("invalid_request", "max_depth must be between 1 and 3")
        if type(max_visited) is not int or not 1 <= max_visited <= 500:
            raise GraphError("invalid_request", "max_visited_nodes must be between 1 and 500")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise GraphError("invalid_request", "limit must be between 1 and 10")
        relationship_types = request.get("relationship_types", [])
        if not isinstance(relationship_types, list) or len(relationship_types) > 100:
            raise GraphError("invalid_request", "relationship_types is invalid")
        relationship_types = {unicodedata.normalize("NFC", _string(v, "relationship_type", 128)) for v in relationship_types}
        with self._connect() as db:
            all_nodes = db.execute("SELECT * FROM graph_nodes WHERE scope_json=? ORDER BY node_id,source_id", (scope_json,)).fetchall()
            by_node: dict[str, list[sqlite3.Row]] = {}
            for row in all_nodes:
                by_node.setdefault(row["node_id"], []).append(row)
            resolved: list[str] = []
            unresolved: list[str] = []
            evidence: list[dict[str, Any]] = []
            if has_ids:
                ids = request["start_node_ids"]
                if not isinstance(ids, list) or not 1 <= len(ids) <= 16:
                    raise GraphError("invalid_request", "start_node_ids must contain 1 to 16 IDs")
                if any(not isinstance(v, str) or not v for v in ids) or len(set(ids)) != len(ids):
                    raise GraphError("invalid_request", "start_node_ids contains invalid or duplicate IDs")
                missing = [v for v in ids if v not in by_node]
                if missing:
                    raise GraphError("not_found", "one or more start nodes were not found in the requested scope", 404)
                resolved = sorted(ids)
            else:
                mentions = request["entity_mentions"]
                if not isinstance(mentions, list) or not 1 <= len(mentions) <= 16:
                    raise GraphError("invalid_request", "entity_mentions must contain 1 to 16 mentions")
                for mention in mentions:
                    mention = _string(mention, "entity_mention", 512)
                    normalized = unicodedata.normalize("NFC", mention).casefold()
                    matches: list[str] = []
                    for node_id, rows in by_node.items():
                        for row in rows:
                            values = [("label", row["label"])] + [("alias", a) for a in json.loads(row["aliases_json"])]
                            for kind, value in values:
                                if unicodedata.normalize("NFC", value).casefold() == normalized:
                                    matches.append(node_id)
                                    supports = [{
                                        "source_id": row["source_id"], "source_revision": row["source_revision"],
                                        "revision_sequence": row["revision_sequence"], "scope": scope,
                                        "attribute_kind": kind, "matched_value": value,
                                        "provenance": json.loads(row["provenance_json"]),
                                    }]
                                    evidence.append({"entity_mention": mention, "node_id": node_id, "supports": supports})
                    ordered = sorted(set(matches))[:4]
                    if not ordered:
                        unresolved.append(mention)
                    resolved.extend(ordered)
                resolved = sorted(set(resolved))[:16]
                evidence = [e for e in evidence if e["node_id"] in resolved][:64]
            starts_truncated = len(resolved) > max_visited
            if starts_truncated:
                resolved = resolved[:max_visited]
            edge_count = db.execute("SELECT COUNT(*) AS n FROM graph_edges WHERE scope_json=?", (scope_json,)).fetchone()["n"]
            edges_rows = db.execute("SELECT * FROM graph_edges WHERE scope_json=? ORDER BY edge_id,source_id LIMIT 10000", (scope_json,)).fetchall()
            edges_truncated = edge_count > len(edges_rows)
            grouped: dict[str, dict[str, Any]] = {}
            for row in edges_rows:
                if relationship_types and row["relationship_type"] not in relationship_types:
                    continue
                item = grouped.setdefault(row["edge_id"], {
                    "edge_id": row["edge_id"], "source_node_id": row["source_node_id"],
                    "target_node_id": row["target_node_id"], "relationship_type": row["relationship_type"],
                    "directed": bool(row["directed"]), "supports": [],
                })
                item["supports"].append({
                    "source_id": row["source_id"], "source_revision": row["source_revision"],
                    "revision_sequence": row["revision_sequence"], "scope": scope,
                    "source_edge_id": row["source_edge_id"], "provenance": json.loads(row["provenance_json"]),
                })
            adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
            for edge in grouped.values():
                edge["supports"].sort(key=lambda x: (x["source_id"], -x["revision_sequence"], x["source_edge_id"]))
                edge["supports"] = edge["supports"][:100]
                src, dst = edge["source_node_id"], edge["target_node_id"]
                adjacency.setdefault(src, []).append((dst, edge))
                if not edge["directed"]:
                    adjacency.setdefault(dst, []).append((src, edge))
                elif direction in {"incoming", "both"}:
                    adjacency.setdefault(dst, []).append((src, edge))
            for node, neighbors in adjacency.items():
                neighbors.sort(key=lambda pair: (pair[0], pair[1]["source_node_id"], pair[1]["target_node_id"],
                                                 pair[1]["relationship_type"], pair[1]["directed"], pair[1]["edge_id"]))
            if direction == "incoming":
                adjacency = {node: [(next_node, edge) for next_node, edge in pairs
                                    if not edge["directed"] or edge["target_node_id"] == node]
                             for node, pairs in adjacency.items()}
            paths: list[dict[str, Any]] = []
            truncated = starts_truncated or edges_truncated
            visited_global: set[str] = set(resolved)
            queue: list[tuple[list[str], list[dict[str, Any]]]] = [([node], []) for node in resolved]
            seen_node_paths: set[tuple[str, ...]] = set()
            while queue:
                node_ids, path_edges = queue.pop(0)
                if path_edges:
                    key = tuple(node_ids)
                    if key not in seen_node_paths:
                        seen_node_paths.add(key)
                        paths.append({"path_id": "path:" + _digest({"nodes": node_ids, "edges": [e["edge_id"] for e in path_edges]}),
                                      "node_ids": node_ids, "edges": path_edges})
                if len(path_edges) >= max_depth:
                    continue
                for next_node, edge in adjacency.get(node_ids[-1], []):
                    if next_node in node_ids:
                        continue
                    if next_node not in visited_global:
                        if len(visited_global) >= max_visited:
                            truncated = True
                            break
                        visited_global.add(next_node)
                    if len(queue) >= 10000:
                        truncated = True
                        break
                    queue.append((node_ids + [next_node], path_edges + [edge]))
                if truncated:
                    break
            paths.sort(key=lambda p: (len(p["edges"]), tuple(p["node_ids"]),
                                      tuple((e["source_node_id"], e["target_node_id"], e["relationship_type"],
                                             e["directed"], e["edge_id"]) for e in p["edges"])))
            if len(paths) > limit:
                paths = paths[:limit]
                truncated = True
            return {"scope": scope, "resolved_start_node_ids": resolved,
                    "unresolved_entity_mentions": unresolved, "resolution_evidence": evidence,
                    "paths": paths, "truncated": truncated, "request_id": request_id}

    def handle(self, method: str, path: str, query: dict[str, list[str]], body: Any,
               request_id: str) -> tuple[int, dict[str, Any]]:
        if method == "GET":
            if path == "/api/v1/graph/health":
                return 200, {"service": "graph", "status": "alive", "request_id": request_id}
            if path == "/api/v1/graph/ready":
                with self._connect() as db:
                    ready = self._ready(db)
                    checks = [{"name": row["owner"] + "_projection_replay",
                               "status": "ok" if row["sealed_sequence"] is not None and
                               row["terminal_sequence"] >= row["sealed_sequence"] and
                               not row["reconciliation_required"] else "not_ready"}
                              for row in db.execute("SELECT * FROM graph_owner_state")]
                return (200 if ready else 503), {"service": "graph", "status": "ready" if ready else "not_ready",
                                                 "ready": ready, "checks": checks, "request_id": request_id}
            if path.startswith("/api/v1/graph/operations/"):
                operation_id = unquote(path.rsplit("/", 1)[-1])
                response = self.operation(operation_id, request_id)
                return 200, response
            if path == "/api/v1/graph/sources/manifest":
                return 200, self.manifest(query, request_id)
            raise GraphError("endpoint_not_found", "endpoint not found", 404)
        if method == "POST":
            if path == "/api/v1/graph/source-projections":
                return self.project(body, request_id)
            if path == "/api/v1/graph/source-deletions":
                return self.delete_source(body, request_id)
            if path == "/api/v1/graph/traversals":
                return 200, self.traverse(body, request_id)
            if path == "/api/v1/graph/reconciliation/checkpoints":
                return self.checkpoint(body, request_id)
            raise GraphError("endpoint_not_found", "endpoint not found", 404)
        raise GraphError("method_not_allowed", "method not allowed", 405)


_service_lock = threading.Lock()
_service_instance: GraphService | None = None


def get_graph_service() -> GraphService:
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            path = os.environ.get("CE_GRAPH_DB_PATH") or str(Path.home() / ".FlossWare" / "graph" / "graph.sqlite3")
            _service_instance = GraphService(path)
        return _service_instance


def reset_graph_service_for_tests() -> None:
    global _service_instance
    with _service_lock:
        _service_instance = None
