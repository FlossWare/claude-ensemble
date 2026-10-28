"""Bounded Learning service for explicit feedback and Thompson updates.

Learning validates feedback evidence and persists the decision before calling the
Thompson REST contract. It stores no raw prompt or response content.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen
from typing import Any

from .internal_calls import INTERNAL_CALL_TOKEN


_ID = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")
_POLICY = "binary-reward-v1"
_MAX_EVIDENCE = 20
_MAX_BODY_BYTES = 300_000


class LearningError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


class LearningService:
    def __init__(self, db_path: str | Path, thompson_base_url: str | None = None):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.thompson_base_url = (thompson_base_url or os.environ.get("CE_THOMPSON_BASE_URL", "http://127.0.0.1:8765")).rstrip("/")
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS learning_events(
                    event_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL UNIQUE,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    selection_id TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    arm_id TEXT NOT NULL,
                    result TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason_code TEXT,
                    thompson_operation_id TEXT,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS learning_events_scope ON learning_events(scope_id, status)")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        return _Connection(db)

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _identifier(value: Any, name: str) -> str:
        if not isinstance(value, str) or not _ID.fullmatch(value):
            raise LearningError("invalid_request", f"{name} must be a stable opaque identifier")
        return value

    @staticmethod
    def _timestamp(value: Any, name: str) -> str:
        if not isinstance(value, str) or len(value) > 64:
            raise LearningError("invalid_request", f"{name} must be an ISO-8601 timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LearningError("invalid_request", f"{name} must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise LearningError("invalid_request", f"{name} must include a timezone")
        return value

    def _validate(self, request: Any) -> dict[str, Any]:
        required = {"event_id", "selection_id", "context_id", "arm_id", "outcome", "evidence", "occurred_at", "policy_version"}
        if not isinstance(request, dict) or set(request) - (required | {"request_id"}) or not required.issubset(request):
            raise LearningError("invalid_request", "outcome request has missing or unknown fields")
        event_id = self._identifier(request["event_id"], "event_id")
        selection_id = request["selection_id"]
        if not isinstance(selection_id, str) or not selection_id.startswith("thompson:selection:") or len(selection_id) > 160:
            raise LearningError("invalid_request", "selection_id is invalid")
        context_id = self._identifier(request["context_id"], "context_id")
        arm_id = self._identifier(request["arm_id"], "arm_id")
        outcome = request["outcome"]
        if not isinstance(outcome, dict) or set(outcome) != {"result"} or outcome["result"] not in {"success", "failure"}:
            raise LearningError("invalid_request", "outcome.result must be success or failure")
        if request["policy_version"] != _POLICY:
            raise LearningError("unsupported_profile", "only binary-reward-v1 is supported", 422)
        evidence = request["evidence"]
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= _MAX_EVIDENCE:
            raise LearningError("invalid_request", f"evidence must contain 1 to {_MAX_EVIDENCE} items")
        normalized_evidence = []
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {"kind", "reference", "asserted_result", "observed_at"}:
                raise LearningError("invalid_request", "each evidence item requires kind, reference, asserted_result, and observed_at")
            if item["kind"] != "explicit_user_feedback":
                raise LearningError("invalid_request", "only explicit_user_feedback evidence is supported by v1")
            reference = self._identifier(item["reference"], "evidence.reference")
            if item["asserted_result"] not in {"success", "failure"} or item["asserted_result"] != outcome["result"]:
                raise LearningError("invalid_request", "evidence asserted_result must match outcome.result")
            normalized_evidence.append({
                "kind": item["kind"], "reference": reference,
                "asserted_result": item["asserted_result"],
                "observed_at": self._timestamp(item["observed_at"], "evidence.observed_at"),
            })
        occurred_at = self._timestamp(request["occurred_at"], "occurred_at")
        return {
            "event_id": event_id, "selection_id": selection_id, "context_id": context_id,
            "arm_id": arm_id, "outcome": {"result": outcome["result"]},
            "evidence": normalized_evidence, "occurred_at": occurred_at,
            "policy_version": _POLICY,
        }

    def submit(self, request: Any, idempotency_key: str, request_id: str) -> tuple[int, dict[str, Any]]:
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 256:
            raise LearningError("invalid_request", "Idempotency-Key is required")
        payload = self._validate(request)
        digest = self._hash(payload)
        existing_operation = None
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM learning_events WHERE event_id=? OR idempotency_key=?",
                (payload["event_id"], idempotency_key),
            ).fetchone()
            if existing:
                if existing["payload_hash"] != digest or existing["event_id"] != payload["event_id"]:
                    raise LearningError("idempotency_conflict", "event ID or Idempotency-Key was reused with a different payload", 409)
                response = self._response(existing, request_id)
                if existing["status"] in {"pending", "reconciliation_required"}:
                    existing_operation = existing["operation_id"]
            else:
                operation_id = "learning:op:" + secrets.token_hex(16)
                initial = {
                    "event_id": payload["event_id"], "operation_id": operation_id, "status": "pending",
                    "request_id": request_id,
                }
                db.execute("""INSERT INTO learning_events(
                    event_id,operation_id,idempotency_key,payload_hash,scope_id,selection_id,context_id,arm_id,
                    result,evidence_json,occurred_at,policy_version,status,response_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (payload["event_id"], operation_id, idempotency_key, digest, payload["context_id"],
                     payload["selection_id"], payload["context_id"], payload["arm_id"], payload["outcome"]["result"],
                     json.dumps(payload["evidence"], separators=(",", ":")), payload["occurred_at"],
                     payload["policy_version"], "pending", json.dumps(initial, separators=(",", ":"))))
                existing_operation = operation_id
        if existing_operation is not None:
            self._apply_thompson(existing_operation, payload, request_id)
            with self._connect() as db:
                row = db.execute("SELECT * FROM learning_events WHERE operation_id=?", (existing_operation,)).fetchone()
            return 202, self._response(row, request_id)
        return 202, response

    def _apply_thompson(self, operation_id: str, payload: dict[str, Any], request_id: str) -> None:
        reward = 1 if payload["outcome"]["result"] == "success" else 0
        body = {
            "event_id": payload["event_id"], "selection_id": payload["selection_id"],
            "context_id": payload["context_id"], "arm_id": payload["arm_id"],
            "reward": reward, "reward_semantics": "binary",
            "evidence_ref": payload["evidence"][0]["reference"],
        }
        headers = {
            "Accept": "application/json", "Content-Type": "application/json",
            "Idempotency-Key": "learning-" + payload["event_id"],
            "X-CE-Request-ID": request_id, "X-CE-Internal-Call": "true", "X-CE-Internal-Token": INTERNAL_CALL_TOKEN,
        }
        request = Request(self.thompson_base_url + "/api/v1/thompson/updates",
                          data=json.dumps(body, separators=(",", ":")).encode(), headers=headers, method="POST")
        status, reason, downstream_id = "complete", None, None
        try:
            with urlopen(request, timeout=2.0) as response:
                decoded = json.loads(response.read().decode("utf-8"))
                if response.status not in (200, 202) or decoded.get("applied") is not True:
                    raise ValueError("Thompson did not confirm update")
                downstream_id = decoded.get("operation_id")
        except HTTPError as exc:
            status, reason = "reconciliation_required", "dependency_unavailable" if exc.code >= 500 else "thompson_rejected_update"
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            status, reason = "reconciliation_required", "dependency_unavailable"
        with self._connect() as db:
            db.execute("UPDATE learning_events SET status=?,reason_code=?,thompson_operation_id=? WHERE operation_id=?",
                       (status, reason, downstream_id, operation_id))
            row = db.execute("SELECT * FROM learning_events WHERE operation_id=?", (operation_id,)).fetchone()
            if row:
                db.execute("UPDATE learning_events SET response_json=? WHERE operation_id=?",
                           (json.dumps(self._response(row, request_id), separators=(",", ":")), operation_id))

    @staticmethod
    def _response(row: sqlite3.Row, request_id: str) -> dict[str, Any]:
        result = {"event_id": row["event_id"], "operation_id": row["operation_id"],
                  "status": row["status"], "request_id": request_id}
        if row["reason_code"]:
            result["reason_code"] = row["reason_code"]
        if row["thompson_operation_id"]:
            result["thompson_operation_id"] = row["thompson_operation_id"]
        return result

    def operation(self, operation_id: str, request_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM learning_events WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None:
            raise LearningError("not_found", "learning operation was not found", 404)
        return self._response(row, request_id)

    def state(self, scope_id: str, request_id: str) -> dict[str, Any]:
        scope_id = self._identifier(scope_id, "scope_id")
        with self._connect() as db:
            rows = db.execute("SELECT status,COUNT(*) AS count FROM learning_events WHERE scope_id=? GROUP BY status", (scope_id,)).fetchall()
        if not rows:
            raise LearningError("not_found", "learning scope was not found", 404)
        counts = {"accepted": 0, "rejected": 0, "pending": 0, "reconciliation_required": 0, "complete": 0, "failed": 0}
        for row in rows:
            counts[row["status"]] = row["count"]
        return {"scope_id": scope_id, "counts": counts, "request_id": request_id}

    def handle(self, method: str, path: str, body: Any, headers: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/api/v1/learning/health":
            return 200, {"service": "learning", "status": "alive", "request_id": request_id}
        if method == "GET" and path == "/api/v1/learning/ready":
            return 200, {"service": "learning", "status": "ready", "ready": True,
                         "checks": [{"name": "sqlite_event_store", "status": "ok"}], "request_id": request_id}
        if method == "POST" and path == "/api/v1/learning/outcomes":
            return self.submit(body, headers.get("Idempotency-Key", ""), request_id)
        if method == "GET" and path.startswith("/api/v1/learning/operations/"):
            return 200, self.operation(unquote(path.rsplit("/", 1)[-1]), request_id)
        if method == "GET" and path.startswith("/api/v1/learning/state/"):
            return 200, self.state(unquote(path.rsplit("/", 1)[-1]), request_id)
        raise LearningError("endpoint_not_found", "endpoint not found", 404)


class _Connection:
    """Small context wrapper that commits/rolls back and always closes SQLite."""
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
    def __enter__(self) -> sqlite3.Connection:
        return self.connection
    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()


_SERVICE: LearningService | None = None
_SERVICE_LOCK = threading.Lock()


def get_learning_service() -> LearningService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            path = os.environ.get("CE_LEARNING_DB_PATH", "~/.FlossWare/claude-ensemble/learning.sqlite3")
            _SERVICE = LearningService(path)
        return _SERVICE
