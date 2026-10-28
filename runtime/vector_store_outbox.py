"""SQLite-backed durable outbox for external vector-store mutations.

Call enqueue() using the same SQLite connection and transaction that changes
canonical Index state. replay() invokes an idempotent external apply callback,
then acknowledges only after that callback succeeds. A crash between apply and
acknowledgement causes a safe retry, so the callback must use deterministic IDs
and idempotent upserts/deletes.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Callable


class VectorStoreOutbox:
    def __init__(self, db_path: str):
        self.db_path = db_path
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS vector_store_intents (
                    intent_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    revision_sequence INTEGER NOT NULL,
                    operation_id TEXT NOT NULL,
                    operation_kind TEXT NOT NULL CHECK(operation_kind IN ('upsert','delete')),
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','applied')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    applied_at TEXT,
                    UNIQUE(generation_id, operation_id)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS vector_store_intents_pending
                ON vector_store_intents(status, intent_id)
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def enqueue(db: sqlite3.Connection, *, generation_id: str, source_id: str,
                revision_sequence: int, operation_id: str, operation_kind: str) -> int:
        """Enqueue inside the caller's canonical-state transaction."""
        if not all(isinstance(value, str) and value for value in
                   (generation_id, source_id, operation_id)):
            raise ValueError("generation_id, source_id, and operation_id are required")
        if type(revision_sequence) is not int or revision_sequence < 1:
            raise ValueError("revision_sequence must be a positive integer")
        if operation_kind not in {"upsert", "delete"}:
            raise ValueError("operation_kind must be upsert or delete")
        db.execute("""
            INSERT INTO vector_store_intents
                (generation_id, source_id, revision_sequence, operation_id, operation_kind)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(generation_id, operation_id) DO NOTHING
        """, (generation_id, source_id, revision_sequence, operation_id, operation_kind))
        row = db.execute(
            "SELECT intent_id, source_id, revision_sequence, operation_kind "
            "FROM vector_store_intents WHERE generation_id=? AND operation_id=?",
            (generation_id, operation_id),
        ).fetchone()
        if (row["source_id"] != source_id or row["revision_sequence"] != revision_sequence
                or row["operation_kind"] != operation_kind):
            raise ValueError("operation_id was reused for a different vector-store intent")
        return int(row["intent_id"])

    def replay(self, apply: Callable[[dict[str, Any]], None], *, limit: int = 100) -> dict[str, int]:
        """Apply pending intents in ID order; leave failures pending for restart/retry."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM vector_store_intents WHERE status='pending' "
                "ORDER BY intent_id LIMIT ?", (limit,),
            ).fetchall()
        applied = 0
        failed = 0
        for row in rows:
            intent = dict(row)
            with self._connect() as db:
                db.execute(
                    "UPDATE vector_store_intents SET attempts=attempts+1,last_error=NULL "
                    "WHERE intent_id=? AND status='pending'", (intent["intent_id"],),
                )
            try:
                apply(intent)
            except Exception as exc:
                with self._connect() as db:
                    db.execute(
                        "UPDATE vector_store_intents SET last_error=? "
                        "WHERE intent_id=? AND status='pending'",
                        (f"{type(exc).__name__}: {exc}"[:1000], intent["intent_id"]),
                    )
                failed += 1
                break
            with self._connect() as db:
                db.execute(
                    "UPDATE vector_store_intents SET status='applied',applied_at=CURRENT_TIMESTAMP,"
                    "last_error=NULL WHERE intent_id=? AND status='pending'",
                    (intent["intent_id"],),
                )
            applied += 1
        with self._connect() as db:
            pending = db.execute(
                "SELECT COUNT(*) FROM vector_store_intents WHERE status='pending'"
            ).fetchone()[0]
        return {"applied": applied, "failed": failed, "pending": int(pending)}
