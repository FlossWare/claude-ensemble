"""Durability and canonical lifecycle tests for Memory owner state."""
import tempfile
import unittest
from pathlib import Path

from runtime.memory import MemoryError, MemoryService


SCOPE = {"type": "project", "id": "project-a", "visibility": "private"}
PROFILE = {"name": "default", "version": "0.1", "digest": "0123456789abcdef" * 4}


def create_request(content="remember the REST contract"):
    return {
        "scope": SCOPE,
        "type": "semantic",
        "content": content,
        "provenance": {"origin": "test"},
        "retention_policy": {"kind": "standard"},
        "index_profile": PROFILE,
    }


class MemoryOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "memory.sqlite3"
        self.service = MemoryService(self.path)

    def test_create_is_durable_and_idempotent_across_restart(self):
        status, response = self.service.create(create_request(), "create-1", "req-1")
        self.assertEqual(status, 202)
        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["indexing_status"], "pending_index")
        restarted = MemoryService(self.path)
        retry_status, retry = restarted.create(create_request(), "create-1", "req-2")
        self.assertEqual(retry_status, 202)
        self.assertEqual(retry["memory_id"], response["memory_id"])
        self.assertEqual(retry["revision_sequence"], response["revision_sequence"])
        self.assertEqual(retry["request_id"], "req-2")
        self.assertEqual(restarted.read(response["memory_id"], SCOPE)["content"], "remember the REST contract")

    def test_idempotency_key_cannot_be_reused_for_different_payload(self):
        self.service.create(create_request(), "create-1", "req-1")
        with self.assertRaisesRegex(MemoryError, "different payload") as caught:
            self.service.create(create_request("different"), "create-1", "req-2")
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.service.list_records_for_tests(), 1)

    def test_update_uses_expected_base_sequence_and_keeps_revision_history(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        update = {
            "expected_base_revision_sequence": created["revision_sequence"],
            "content": "updated content",
            "provenance": {"origin": "test-update"},
            "index_profile": PROFILE,
        }
        _, updated = self.service.update(created["memory_id"], update, "update-1", "req-2")
        self.assertGreater(updated["revision_sequence"], created["revision_sequence"])
        self.assertEqual(self.service.read(created["memory_id"], SCOPE)["content"], "updated content")
        with self.assertRaises(MemoryError) as caught:
            self.service.update(created["memory_id"], update, "update-stale", "req-3")
        self.assertEqual(caught.exception.code, "revision_conflict")

    def test_tombstone_blocks_reads_and_survives_restart(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        _, deleted = self.service.delete(created["memory_id"], SCOPE, "source", "delete-1", "req-2")
        self.assertGreater(deleted["revision_sequence"], created["revision_sequence"])
        with self.assertRaises(MemoryError) as caught:
            self.service.read(created["memory_id"], SCOPE)
        self.assertEqual(caught.exception.status, 404)
        restarted = MemoryService(self.path)
        verified = restarted.verify_revisions([{
            "source_id": created["source_id"], "revision_sequence": created["revision_sequence"]
        }])
        self.assertEqual(verified[0]["status"], "tombstoned")
        self.assertEqual(verified[0]["canonical_revision_sequence"], deleted["revision_sequence"])

    def test_scope_mismatch_does_not_disclose_record(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        with self.assertRaises(MemoryError) as caught:
            self.service.read(created["memory_id"], {"type": "project", "id": "other", "visibility": "private"})
        self.assertEqual(caught.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
