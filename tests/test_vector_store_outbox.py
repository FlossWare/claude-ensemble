"""Tests for durable vector-store intent ordering and retry behavior."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.vector_store_outbox import VectorStoreOutbox


class VectorStoreOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "index.sqlite")
        self.outbox = VectorStoreOutbox(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def enqueue(self, operation_id="op-1", source_id="knowledge:doc-a",
                sequence=1, kind="upsert"):
        with sqlite3.connect(self.db_path) as db:
            return VectorStoreOutbox.enqueue(
                db, generation_id="gen-1", source_id=source_id,
                revision_sequence=sequence, operation_id=operation_id,
                operation_kind=kind,
            )

    def test_intent_is_atomic_with_canonical_transaction(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("CREATE TABLE canonical (source_id TEXT PRIMARY KEY)")
        with self.assertRaises(RuntimeError):
            with sqlite3.connect(self.db_path) as db:
                db.execute("INSERT INTO canonical VALUES ('knowledge:doc-a')")
                self.enqueue()
                raise RuntimeError("simulated crash before commit")
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM canonical").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM vector_store_intents").fetchone()[0], 0)

    def test_replay_is_ordered_and_acknowledges_after_success(self):
        self.enqueue("op-1", sequence=1)
        self.enqueue("op-2", source_id="knowledge:doc-b", sequence=2)
        seen = []
        result = self.outbox.replay(lambda item: seen.append(item["operation_id"]))
        self.assertEqual(seen, ["op-1", "op-2"])
        self.assertEqual(result, {"applied": 2, "failed": 0, "pending": 0})

    def test_external_success_before_ack_is_safe_to_retry(self):
        self.enqueue()
        external_state = {}

        def crash_after_external_apply(item):
            external_state[(item["generation_id"], item["source_id"])] = item["revision_sequence"]
            raise RuntimeError("crash between external apply and acknowledgement")

        result = self.outbox.replay(crash_after_external_apply)
        self.assertEqual(result, {"applied": 0, "failed": 1, "pending": 1})
        self.assertEqual(external_state[("gen-1", "knowledge:doc-a")], 1)

        # Idempotent apply repeats the same deterministic mutation and then acks.
        result = self.outbox.replay(
            lambda item: external_state.__setitem__(
                (item["generation_id"], item["source_id"]), item["revision_sequence"]
            )
        )
        self.assertEqual(result, {"applied": 1, "failed": 0, "pending": 0})
        self.assertEqual(len(external_state), 1)

    def test_failed_intent_stays_pending_and_blocks_later_intents(self):
        self.enqueue("op-1", sequence=1)
        self.enqueue("op-2", source_id="knowledge:doc-b", sequence=2)
        result = self.outbox.replay(lambda item: (_ for _ in ()).throw(OSError("Chroma offline")))
        self.assertEqual(result, {"applied": 0, "failed": 1, "pending": 2})
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT operation_id,attempts,last_error,status FROM vector_store_intents ORDER BY intent_id"
            ).fetchall()
        self.assertEqual(rows[0][0], "op-1")
        self.assertEqual(rows[0][1], 1)
        self.assertIn("Chroma offline", rows[0][2])
        self.assertEqual(rows[0][3], "pending")
        self.assertEqual(rows[1][3], "pending")

    def test_duplicate_intent_is_idempotent_but_identity_conflicts_fail(self):
        first = self.enqueue()
        self.assertEqual(self.enqueue(), first)
        with self.assertRaisesRegex(ValueError, "reused"):
            self.enqueue(source_id="knowledge:doc-b")


if __name__ == "__main__":
    unittest.main()
