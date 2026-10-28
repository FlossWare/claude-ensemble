"""Durability and canonical lifecycle tests for Memory owner state."""
import tempfile
import unittest
import json
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from jsonschema import Draft202012Validator
from pathlib import Path

from runtime.memory import MemoryError, MemoryService
from runtime.server import BoundedThreadingHTTPServer, Handler


SCOPE = {"type": "project", "id": "project-a", "visibility": "private"}
PROFILE = {"name": "default", "version": "0.1", "digest": "0123456789abcdef" * 4}
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "docs/contracts/schemas/memory.schema.json").read_text())


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

    def test_pending_ingestion_is_recoverable_after_restart(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        self.service.update_operation(created["operation_id"], "pending", "pending_index")
        restarted = MemoryService(self.path)
        pending = restarted.pending_ingestions()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["accepted"]["operation_id"], created["operation_id"])
        self.assertEqual(pending[0]["request"]["content"], "remember the REST contract")
        self.assertEqual(pending[0]["request"]["scope"], SCOPE)

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
        _, updated = self.service.update(created["memory_id"], update, "update-1", "req-2", SCOPE)
        self.assertGreater(updated["revision_sequence"], created["revision_sequence"])
        self.assertEqual(self.service.read(created["memory_id"], SCOPE)["content"], "updated content")
        with self.assertRaises(MemoryError) as caught:
            self.service.update(created["memory_id"], update, "update-stale", "req-3", SCOPE)
        self.assertEqual(caught.exception.code, "revision_conflict")

    def test_ingestion_requires_the_exact_current_revision(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        self.assertEqual(self.service.read_for_ingestion(
            created["memory_id"], SCOPE, created["revision_sequence"])["content"], "remember the REST contract")
        update = {
            "expected_base_revision_sequence": created["revision_sequence"],
            "content": "newer revision",
            "provenance": {"origin": "test"},
            "index_profile": PROFILE,
        }
        _, updated = self.service.update(created["memory_id"], update, "update-1", "req-2", SCOPE)
        with self.assertRaises(MemoryError) as caught:
            self.service.read_for_ingestion(created["memory_id"], SCOPE, created["revision_sequence"])
        self.assertEqual(caught.exception.code, "stale_revision")
        self.assertEqual(self.service.read_for_ingestion(
            created["memory_id"], SCOPE, updated["revision_sequence"])["content"], "newer revision")

    def test_update_rejects_wrong_scope(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        update = {
            "expected_base_revision_sequence": created["revision_sequence"],
            "content": "unauthorized update",
            "provenance": {"origin": "test"},
            "index_profile": PROFILE,
        }
        with self.assertRaises(MemoryError) as caught:
            self.service.update(created["memory_id"], update, "wrong-scope", "req-2",
                                {"type": "project", "id": "other", "visibility": "private"})
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.service.read(created["memory_id"], SCOPE)["content"], "remember the REST contract")

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

    def test_http_create_read_update_delete_and_verification_routes(self):
        import runtime.server as server_module
        httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.addCleanup(thread.join, 2)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        with patch.object(server_module, "get_memory_service", return_value=self.service), patch.object(Handler, "_memory_preflight", return_value={}), patch.object(Handler, "_memory_ingest", return_value=None):
            payload = json.dumps(create_request()).encode()
            req = Request(base + "/api/v1/memories", data=payload, method="POST",
                          headers={"Content-Type": "application/json", "Idempotency-Key": "http-create"})
            with urlopen(req, timeout=3) as response:
                self.assertEqual(response.status, 202)
                created = json.loads(response.read())
            self.assertEqual(list(Draft202012Validator({"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], **SCHEMA["$defs"]["createResponse"]}).iter_errors(created)), [])
            memory_id = created["memory_id"]
            read_url = (base + f"/api/v1/memories/{memory_id}"
                        + "?scope_type=project&scope_id=project-a&visibility=private")
            with urlopen(read_url, timeout=3) as response:
                read_result = json.loads(response.read())
                self.assertEqual(read_result["content"], "remember the REST contract")
                self.assertEqual(list(Draft202012Validator({"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], **SCHEMA["$defs"]["canonicalReadResponse"]}).iter_errors(read_result)), [])
            verify = json.dumps({"items": [{"source_id": created["source_id"],
                                            "revision_sequence": created["revision_sequence"]}]}).encode()
            req = Request(base + "/api/v1/memories/verify-revisions", data=verify, method="POST",
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=3) as response:
                self.assertEqual(json.loads(response.read())["results"][0]["status"], "current")
            update = json.dumps({
                "expected_base_revision_sequence": created["revision_sequence"],
                "content": "updated through REST",
                "provenance": {"origin": "http-update"},
                "index_profile": PROFILE,
            }).encode()
            update_url = (base + f"/api/v1/memories/{memory_id}/revisions"
                          + "?scope_type=project&scope_id=project-a&visibility=private")
            req = Request(update_url, data=update, method="POST",
                          headers={"Content-Type": "application/json", "Idempotency-Key": "http-update"})
            with urlopen(req, timeout=3) as response:
                updated = json.loads(response.read())
                self.assertEqual(response.status, 202)
            self.assertGreater(updated["revision_sequence"], created["revision_sequence"])
            self.assertEqual(self.service.read(memory_id, SCOPE)["content"], "updated through REST")
            wrong_scope_url = (base + f"/api/v1/memories/{memory_id}/revisions"
                               + "?scope_type=project&scope_id=other&visibility=private")
            req = Request(wrong_scope_url, data=update, method="POST",
                          headers={"Content-Type": "application/json", "Idempotency-Key": "wrong-scope-update"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(req, timeout=3)
            self.assertEqual(caught.exception.code, 404)
            delete = json.dumps({"scope": SCOPE, "delete_scope": "source"}).encode()
            req = Request(base + f"/api/v1/memories/{memory_id}", data=delete, method="DELETE",
                          headers={"Content-Type": "application/json", "Idempotency-Key": "http-delete"})
            with urlopen(req, timeout=3) as response:
                self.assertEqual(response.status, 202)
                deleted = json.loads(response.read())
            self.assertEqual(list(Draft202012Validator({"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], **SCHEMA["$defs"]["deleteResponse"]}).iter_errors(deleted)), [])
            with urlopen(base + "/api/v1/memories/operations/" + created["operation_id"] + "?scope_type=project&scope_id=project-a&visibility=private", timeout=3) as response:
                operation = json.loads(response.read())
            self.assertEqual(list(Draft202012Validator({"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], **SCHEMA["$defs"]["operationStatusResponse"]}).iter_errors(operation)), [])
            with self.assertRaises(HTTPError) as caught:
                urlopen(read_url, timeout=3)
            self.assertEqual(caught.exception.code, 404)

    def test_async_ingestion_wires_chunks_tokens_vectors_and_index_over_rest(self):
        import runtime.server as server_module
        bundle = {
            "name": PROFILE["name"], "version": PROFILE["version"], "digest": PROFILE["digest"], "status": "active",
            "chunking": {"profile": "markdown-default", "version": "0.1", "max_units": 1200, "overlap_units": 120},
            "tokenization": {"profile": "technical-default", "version": "0.1"},
            "lexical": {"profile": "bm25-v1", "version": "0.1", "statistics_policy": "scope_partition"},
            "embedding": {"required": True, "profile": "technical-default", "version": "0.1",
                          "model": "test-model", "model_version": "test-v1", "input_types": ["document"],
                          "dimensions": 3, "normalization": "l2", "metric": "cosine", "max_input_tokens": 8192},
            "limits": {},
        }
        context = {"bundle": bundle, "index_base": "http://unused", "chunking_base": "http://unused",
                   "tokenization_base": "http://unused", "embedding_base": "http://unused",
                   "local_base": "http://unused"}
        def fake_rest(_self, _base, path, *, payload=None, request_id, timeout, extra_headers=None):
            if path == "/api/v1/chunking/chunks":
                return {"source_id": payload["source"]["source_id"],
                        "chunker": {"profile": "markdown-default", "version": "0.1"},
                        "chunks": [{"chunk_id": "chk_test", "text": "remember REST", "metadata": {}}]}
            if path == "/api/v1/tokenization/lexical/batch":
                return {"results": [{"input_id": "chk_test", "tokens": [{"term": "remember"}, {"term": "rest"}]}]}
            if path == "/api/v1/embeddings":
                return {"model": {"model_id": "test-model", "model_version": "test-v1", "dimensions": 3},
                        "results": [{"input_id": "chk_test", "status": "complete", "vector": [1.0, 0.0, 0.0]}]}
            if path == "/api/v1/index/operations/upsert":
                self.assertEqual(payload["representations"][0]["lexical"]["terms"], ["remember", "rest"])
                self.assertEqual(payload["representations"][0]["vector"]["values"], [1.0, 0.0, 0.0])
                self.assertEqual(extra_headers["Idempotency-Key"], payload["operation_id"])
                return {"status": "complete"}
            raise AssertionError(f"unexpected REST dependency path: {path}")

        httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.addCleanup(thread.join, 2)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        with patch.object(server_module, "get_memory_service", return_value=self.service), \
             patch.object(Handler, "_memory_preflight", return_value=context), \
             patch.object(Handler, "_memory_rest_json", new=fake_rest):
            req = Request(base + "/api/v1/memories", data=json.dumps(create_request()).encode(), method="POST",
                          headers={"Content-Type": "application/json", "Idempotency-Key": "async-create"})
            with urlopen(req, timeout=3) as response:
                created = json.loads(response.read())
            deadline = time.monotonic() + 3
            operation = None
            while time.monotonic() < deadline:
                operation = self.service.operation(created["operation_id"], scope_value=SCOPE)
                if operation["status"] in {"complete", "failed"}:
                    break
                time.sleep(0.02)
            self.assertEqual(operation["status"], "complete")
            self.assertEqual(operation["indexing_status"], "indexed")

    def test_pending_tombstone_contains_stable_index_replay_identity(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        _, deleted = self.service.delete(created["memory_id"], SCOPE, "source", "delete-1", "req-2")
        pending = self.service.pending_deletions()
        self.assertEqual(len(pending), 1)
        details = pending[0]["details"]
        self.assertEqual(details["source_id"], created["source_id"])
        self.assertEqual(details["revision_sequence"], deleted["revision_sequence"])
        self.assertEqual(details["scope"], SCOPE)
        self.assertEqual(details["index_profile"], PROFILE)

    def test_scope_mismatch_does_not_disclose_record(self):
        _, created = self.service.create(create_request(), "create-1", "req-1")
        with self.assertRaises(MemoryError) as caught:
            self.service.read(created["memory_id"], {"type": "project", "id": "other", "visibility": "private"})
        self.assertEqual(caught.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
