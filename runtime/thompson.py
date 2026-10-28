"""SQLite-backed Thompson sampling for the CE proof of concept.

The module owns decision-selection state only. Feedback interpretation remains in
Learning; this service accepts already-validated binary reward events.
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
from random import SystemRandom
from typing import Any
from urllib.parse import unquote

POLICY = {"name": "beta-bernoulli-v1", "version": "1"}
_ID = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")
_RANDOM = SystemRandom()


class ThompsonError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


class ThompsonService:
    def __init__(self, db_path: str | Path):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
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

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS contexts(
                context_id TEXT PRIMARY KEY, state_version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE IF NOT EXISTS arms(
                context_id TEXT NOT NULL, arm_id TEXT NOT NULL,
                alpha REAL NOT NULL DEFAULT 1, beta REAL NOT NULL DEFAULT 1,
                exposures INTEGER NOT NULL DEFAULT 0, rewards INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(context_id, arm_id),
                FOREIGN KEY(context_id) REFERENCES contexts(context_id));
              CREATE TABLE IF NOT EXISTS selections(
                selection_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, arm_id TEXT NOT NULL,
                policy_json TEXT NOT NULL, state_version INTEGER NOT NULL,
                audit_ref TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                payload_hash TEXT NOT NULL, response_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE IF NOT EXISTS updates(
                event_id TEXT PRIMARY KEY, selection_id TEXT NOT NULL UNIQUE, idempotency_key TEXT NOT NULL UNIQUE,
                context_id TEXT NOT NULL, arm_id TEXT NOT NULL, reward INTEGER NOT NULL,
                payload_hash TEXT NOT NULL, response_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)

    @staticmethod
    def _ident(value: Any, field: str) -> str:
        if not isinstance(value, str) or not _ID.fullmatch(value):
            raise ThompsonError("invalid_request", f"{field} must be a stable opaque identifier")
        return value

    @staticmethod
    def _hash(value: dict[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hashlib.sha256(raw).hexdigest()

    def select(self, request: dict[str, Any], key: str, request_id: str) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ThompsonError("invalid_request", "request body must be an object")
        required = {"context_id", "policy", "eligible_arms"}
        if set(request) - (required | {"expected_state_version", "request_id"}) or not required.issubset(request):
            raise ThompsonError("invalid_request", "selection request has missing or unknown fields")
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise ThompsonError("invalid_request", "Idempotency-Key is required")
        context = self._ident(request["context_id"], "context_id")
        if request["policy"] != POLICY:
            raise ThompsonError("unsupported_profile", "only beta-bernoulli-v1@1 is supported", 422)
        eligible = request["eligible_arms"]
        if not isinstance(eligible, list) or not eligible:
            raise ThompsonError("no_eligible_arms", "eligible_arms must contain at least one arm", 422)
        ids = []
        for item in eligible:
            if not isinstance(item, dict) or set(item) - {"arm_id", "features"} or "arm_id" not in item:
                raise ThompsonError("invalid_request", "each eligible arm requires arm_id and optional features")
            arm_id = self._ident(item["arm_id"], "arm_id")
            if arm_id in ids:
                raise ThompsonError("invalid_request", "eligible arm IDs must be unique")
            if "features" in item and not isinstance(item["features"], dict):
                raise ThompsonError("invalid_request", "arm features must be an object")
            ids.append(arm_id)
        semantic = {k: v for k, v in request.items() if k != "request_id"}
        digest = self._hash(semantic)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT payload_hash,response_json FROM selections WHERE idempotency_key=?", (key,)).fetchone()
            if prior:
                if prior["payload_hash"] != digest:
                    raise ThompsonError("idempotency_conflict", "Idempotency-Key was reused with a different payload", 409)
                response = json.loads(prior["response_json"])
                response["request_id"] = request_id
                return response
            db.execute("INSERT OR IGNORE INTO contexts(context_id,state_version) VALUES(?,0)", (context,))
            state = db.execute("SELECT state_version FROM contexts WHERE context_id=?", (context,)).fetchone()
            expected = request.get("expected_state_version")
            if expected is not None and (type(expected) is not int or expected != state["state_version"]):
                raise ThompsonError("revision_conflict", "expected_state_version does not match current state", 409)
            for arm_id in ids:
                db.execute("INSERT OR IGNORE INTO arms(context_id,arm_id) VALUES(?,?)", (context, arm_id))
            rows = {r["arm_id"]: r for r in db.execute(
                "SELECT * FROM arms WHERE context_id=? AND arm_id IN (%s)" % ",".join("?" for _ in ids),
                (context, *ids))}
            draws = {arm_id: _RANDOM.betavariate(float(rows[arm_id]["alpha"]), float(rows[arm_id]["beta"])) for arm_id in ids}
            chosen = min(ids, key=lambda arm_id: (-draws[arm_id], arm_id))
            selection_id = "thompson:selection:" + secrets.token_hex(16)
            audit_ref = "thompson:audit:" + secrets.token_hex(12)
            response = {"selection_id": selection_id, "chosen_arm_id": chosen, "policy": POLICY,
                        "state_version": int(state["state_version"]), "evidence": {"audit_ref": audit_ref},
                        "request_id": request_id}
            db.execute("UPDATE arms SET exposures=exposures+1 WHERE context_id=? AND arm_id=?", (context, chosen))
            db.execute("""INSERT INTO selections(selection_id,context_id,arm_id,policy_json,state_version,
                       audit_ref,idempotency_key,payload_hash,response_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                       (selection_id, context, chosen, json.dumps(POLICY), state["state_version"], audit_ref,
                        key, digest, json.dumps(response, separators=(",", ":"))))
            return response

    def update(self, request: dict[str, Any], key: str, request_id: str) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ThompsonError("invalid_request", "request body must be an object")
        required = {"event_id", "selection_id", "context_id", "arm_id", "reward", "reward_semantics", "evidence"}
        if set(request) - (required | {"expected_state_version", "request_id"}) or not required.issubset(request):
            raise ThompsonError("invalid_request", "update request has missing or unknown fields")
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise ThompsonError("invalid_request", "Idempotency-Key is required")
        event_id = self._ident(request["event_id"], "event_id")
        selection_id = self._ident(request["selection_id"], "selection_id") if not str(request["selection_id"]).startswith("thompson:selection:") else request["selection_id"]
        context = self._ident(request["context_id"], "context_id")
        arm = self._ident(request["arm_id"], "arm_id")
        if type(request["reward"]) is not int or request["reward"] not in (0, 1) or request["reward_semantics"] != "binary":
            raise ThompsonError("invalid_request", "reward must be integer 0 or 1 with reward_semantics=binary")
        if not isinstance(request["evidence"], dict):
            raise ThompsonError("invalid_request", "evidence must be an object")
        semantic = {k: v for k, v in request.items() if k != "request_id"}
        digest = self._hash(semantic)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT payload_hash,response_json FROM updates WHERE event_id=?", (event_id,)).fetchone()
            if prior:
                if prior["payload_hash"] != digest:
                    raise ThompsonError("idempotency_conflict", "event_id was reused with a different payload", 409)
                response = json.loads(prior["response_json"])
                response["request_id"] = request_id
                return response
            duplicate_key = db.execute("SELECT payload_hash,response_json FROM updates WHERE idempotency_key=?", (key,)).fetchone()
            if duplicate_key:
                if duplicate_key["payload_hash"] != digest:
                    raise ThompsonError("idempotency_conflict", "Idempotency-Key was reused with a different payload", 409)
                response = json.loads(duplicate_key["response_json"])
                response["request_id"] = request_id
                return response
            prior_selection = db.execute("SELECT * FROM updates WHERE selection_id=?", (selection_id,)).fetchone()
            if prior_selection:
                raise ThompsonError("selection_outcome_conflict", "selection already has a terminal outcome", 409)
            selection = db.execute("SELECT * FROM selections WHERE selection_id=?", (selection_id,)).fetchone()
            if not selection or selection["context_id"] != context or selection["arm_id"] != arm:
                raise ThompsonError("not_found", "selection, context, and chosen arm must match a persisted selection", 404)
            state = db.execute("SELECT state_version FROM contexts WHERE context_id=?", (context,)).fetchone()
            expected = request.get("expected_state_version")
            if expected is not None and (type(expected) is not int or expected != state["state_version"]):
                raise ThompsonError("revision_conflict", "expected_state_version does not match current state", 409)
            column = "alpha" if request["reward"] == 1 else "beta"
            db.execute(f"UPDATE arms SET {column}={column}+1,rewards=rewards+1 WHERE context_id=? AND arm_id=?", (context, arm))
            db.execute("UPDATE contexts SET state_version=state_version+1 WHERE context_id=?", (context,))
            version = int(state["state_version"]) + 1
            operation_id = "thompson:op:" + secrets.token_hex(16)
            response = {"event_id": event_id, "operation_id": operation_id, "applied": True,
                        "state_version": version, "request_id": request_id}
            db.execute("""INSERT INTO updates(event_id,selection_id,idempotency_key,context_id,arm_id,reward,payload_hash,response_json)
                          VALUES(?,?,?,?,?,?,?,?)""",
                       (event_id, selection_id, key, context, arm, request["reward"], digest,
                        json.dumps(response, separators=(",", ":"))))
            return response

    def state(self, context: str, request_id: str) -> dict[str, Any]:
        context = self._ident(context, "context_id")
        with self._connect() as db:
            row = db.execute("SELECT state_version FROM contexts WHERE context_id=?", (context,)).fetchone()
            if row is None:
                raise ThompsonError("not_found", "context was not found", 404)
            arms = []
            for arm in db.execute("SELECT * FROM arms WHERE context_id=? ORDER BY arm_id", (context,)):
                total = arm["alpha"] + arm["beta"]
                arms.append({"arm_id": arm["arm_id"], "exposure_count": arm["exposures"],
                             "reward_count": arm["rewards"],
                             "mean_reward": round(arm["alpha"] / total, 9) if total else None})
            return {"context_id": context, "state_version": row["state_version"], "arms": arms, "request_id": request_id}

    def handle(self, method: str, path: str, query: dict[str, list[str]], body: Any,
               headers: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/api/v1/thompson/health":
            return 200, {"service": "thompson", "status": "alive", "request_id": request_id}
        if method == "GET" and path == "/api/v1/thompson/ready":
            return 200, {"service": "thompson", "status": "ready", "ready": True,
                         "checks": [{"name": "sqlite_state_store", "status": "ok"}], "request_id": request_id}
        if method == "GET" and path.startswith("/api/v1/thompson/state/"):
            context = unquote(path.rsplit("/", 1)[-1])
            return 200, self.state(context, request_id)
        if method == "POST" and path == "/api/v1/thompson/selections":
            return 200, self.select(body, headers.get("Idempotency-Key", ""), request_id)
        if method == "POST" and path == "/api/v1/thompson/updates":
            return 200, self.update(body, headers.get("Idempotency-Key", ""), request_id)
        raise ThompsonError("endpoint_not_found", "endpoint not found", 404)


_SERVICE: ThompsonService | None = None
_SERVICE_LOCK = threading.Lock()


def get_thompson_service() -> ThompsonService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            path = os.environ.get("CE_THOMPSON_DB_PATH", "~/.FlossWare/claude-ensemble/thompson.sqlite3")
            _SERVICE = ThompsonService(path)
        return _SERVICE
