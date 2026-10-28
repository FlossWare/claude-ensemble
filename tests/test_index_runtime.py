"""Contract-focused tests for the durable Index retrieval slice."""
from __future__ import annotations

import tempfile
import unittest
import json
import os
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from pathlib import Path

from runtime.index import IndexError, IndexService, profile_digest, reset_index_service_for_tests
from runtime.server import BoundedThreadingHTTPServer, Handler


SCOPE = {"type": "project", "id": "project-a", "visibility": "private"}


def profile():
    value = {
        "name": "test-profile",
        "version": "0.1",
        "status": "active",
        "chunking": {"profile": "markdown-default", "version": "0.1", "max_units": 1200, "overlap_units": 120},
        "tokenization": {"profile": "technical-default", "version": "0.1"},
        "lexical": {"profile": "bm25-v1", "version": "0.1", "statistics_policy": "scope_partition"},
        "embedding": {
            "required": True, "profile": "technical-default", "version": "0.1",
            "model": "local-nomic", "model_version": "r1", "input_types": ["query", "document"],
            "dimensions": 3, "normalization": "l2", "metric": "cosine", "max_input_tokens": 8192,
        },
        "limits": {
            "max_chunks": 64, "max_source_bytes": 131072, "max_chunk_text_bytes": 512,
            "max_request_bytes": 2097152, "max_chunk_representation_bytes": 18000,
            "max_envelope_bytes": 16384, "max_metadata_bytes": 1024,
            "max_lexical_terms_per_chunk": 64, "max_lexical_term_bytes": 32,
        },
    }
    value["digest"] = profile_digest(value)
    return value


def representation(chunk_id, text, terms, vector):
    return {
        "chunk_id": chunk_id,
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "text": text,
        "lexical": {"profile": "bm25-v1", "version": "0.1", "terms": terms},
        "vector": {"input_type": "document", "model": "local-nomic", "version": "r1",
                   "dimensions": 3, "values": vector},
        "metadata": {},
    }


class IndexRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = profile()
        self.identity = {k: self.bundle[k] for k in ("name", "version", "digest")}
        self.service = IndexService(Path(self.temp.name) / "index.sqlite3", self.bundle)

    def upsert_request(self, source_id="knowledge:doc-a", sequence=1, operation_id="op-a", reps=None):
        return {
            "operation_id": operation_id,
            "request_id": "req-1",
            "source": {"source_id": source_id, "revision": f"rev-{sequence}",
                       "revision_sequence": sequence, "scope": SCOPE},
            "index_profile": self.identity,
            "representations": reps or [representation("chunk-a", "ranking fusion", ["ranking", "fusion"], [1.0, 0.0, 0.0])],
        }

    def test_upsert_is_durable_and_profile_pinned(self):
        request = self.upsert_request()
        status, result = self.service.upsert(request, "idem-a")
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "complete")
        restarted = IndexService(Path(self.temp.name) / "index.sqlite3", self.bundle)
        self.assertEqual(restarted.operation("op-a")["status"], "complete")
        self.assertEqual(restarted.source_status("knowledge:doc-a")["indexed_revision_sequence"], 1)

    def test_lexical_lookup_returns_scoped_evidence_and_statistics(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        request = {
            "request_id": "req-2", "scope": SCOPE, "index_profile": self.identity,
            "lexical_profile": {"name": "bm25-v1", "version": "0.1"},
            "terms": ["ranking", "fusion"], "limit": 10,
            "index_generation": self.service.active_generation()["generation_id"],
        }
        result = self.service.lexical_lookup(request)
        self.assertEqual([c["chunk_id"] for c in result["candidates"]], ["chunk-a"])
        self.assertEqual(result["candidates"][0]["term_frequency_evidence"][0]["term"], "fusion")
        self.assertEqual(result["corpus_statistics"]["document_count"], 1)

    def test_vector_neighbors_obey_metric_and_profile(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        request = {
            "request_id": "req-3", "scope": SCOPE, "index_profile": self.identity,
            "embedding_profile": {"name": "technical-default", "version": "0.1"},
            "query_vector": [1.0, 0.0, 0.0], "input_type": "query", "metric": "cosine", "limit": 5,
            "index_generation": self.service.active_generation()["generation_id"],
        }
        result = self.service.vector_neighbors(request)
        self.assertEqual(result["candidates"][0]["chunk_id"], "chunk-a")
        self.assertEqual(result["candidates"][0]["similarity"], 1.0)

    def test_tombstone_is_durable_and_blocks_stale_upsert(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        delete = {
            "operation_id": "delete-a", "request_id": "req-delete", "source_id": "knowledge:doc-a",
            "source_revision": "tombstone-rev-2", "revision_sequence": 2,
            "scope": SCOPE, "index_profile": self.identity, "delete_scope": "source",
        }
        self.service.delete(delete, "idem-delete")
        with self.assertRaisesRegex(IndexError, "tombstone sequence"):
            self.service.upsert(self.upsert_request(sequence=1, operation_id="op-stale"), "idem-stale")
        restarted = IndexService(Path(self.temp.name) / "index.sqlite3", self.bundle)
        status = restarted.source_status("knowledge:doc-a")
        self.assertEqual(status["tombstone_sequence"], 2)
        self.assertEqual(status["deletion_state"], "tombstoned")

    def test_new_operation_cannot_reuse_a_source_revision_sequence(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        with self.assertRaisesRegex(IndexError, "strictly increase"):
            self.service.upsert(self.upsert_request(operation_id="op-other"), "idem-other")

    def test_profile_digest_mismatch_is_rejected(self):
        invalid = dict(self.bundle)
        invalid["lexical"] = dict(invalid["lexical"], profile="other")
        with self.assertRaisesRegex(IndexError, "digest"):
            IndexService(Path(self.temp.name) / "bad.sqlite3", invalid)

    def test_http_dispatch_supports_upsert_and_lexical_lookup(self):
        profile_path = Path(self.temp.name) / "profile.json"
        profile_path.write_text(json.dumps(self.bundle), encoding="utf-8")
        db_path = Path(self.temp.name) / "http-index.sqlite3"
        reset_index_service_for_tests()
        server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {
                "CE_INDEX_PROFILE_BUNDLE_PATH": str(profile_path),
                "CE_INDEX_DB_PATH": str(db_path),
                "CE_INDEX_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
                "CE_TOKENIZATION_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
            }):
                base = f"http://127.0.0.1:{server.server_address[1]}"
                health = json.loads(urlopen(base + "/api/v1/index/health", timeout=2).read())
                self.assertEqual(health["status"], "alive")
                expired = Request(base + "/api/v1/index/health",
                                  headers={"X-CE-Deadline": "2000-01-01T00:00:00Z"})
                with self.assertRaises(HTTPError) as timeout_error:
                    urlopen(expired, timeout=2)
                self.assertEqual(timeout_error.exception.code, 504)
                self.assertEqual(json.loads(timeout_error.exception.read())["error"]["code"], "deadline_exceeded")
                request_body = self.upsert_request()
                request = Request(base + "/api/v1/index/operations/upsert",
                                  data=json.dumps(request_body).encode("utf-8"),
                                  headers={"Content-Type": "application/json", "Idempotency-Key": "http-idem"},
                                  method="POST")
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    upsert = json.loads(response.read())
                generation = json.loads(urlopen(base + "/api/v1/index/generations/active", timeout=2).read())
                lookup_body = {
                    "request_id": "http-lookup", "scope": SCOPE, "index_profile": self.identity,
                    "lexical_profile": {"name": "bm25-v1", "version": "0.1"},
                    "terms": ["ranking", "fusion"], "limit": 10,
                    "index_generation": generation["generation_id"],
                }
                lookup_request = Request(base + "/api/v1/index/lexical/lookup",
                                         data=json.dumps(lookup_body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(lookup_request, timeout=2) as response:
                    lookup = json.loads(response.read())
                self.assertEqual(upsert["status"], "complete")
                self.assertEqual(lookup["candidates"][0]["source_id"], "knowledge:doc-a")

                retrieval_body = {
                    "query_id": "query-http", "request_id": "retrieval-http",
                    "query_text": "ranking fusion", "scope": SCOPE, "index_profile": self.identity,
                    "lexical_profile": {"name": "bm25-v1", "version": "0.1"},
                    "index_generation": generation["generation_id"], "limit": 10,
                }
                retrieval_request = Request(base + "/api/v1/lexical-retrieval/search",
                    data=json.dumps(retrieval_body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(retrieval_request, timeout=4) as response:
                    retrieval = json.loads(response.read())
                self.assertEqual(retrieval["candidates"][0]["source_id"], "knowledge:doc-a")
                self.assertEqual(retrieval["candidates"][0]["score_semantics"], "bm25-v1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            reset_index_service_for_tests()

    def test_manifest_cursor_uses_stable_snapshot(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        self.service.upsert(self.upsert_request(
            source_id="knowledge:doc-b", operation_id="op-b",
            reps=[representation("chunk-b", "ranking fusion", ["ranking", "fusion"], [0.0, 1.0, 0.0])],
        ), "idem-b")
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        status, first = self.service.handle(
            "GET", "/api/v1/index/sources/manifest", {"owner": ["knowledge"], "limit": ["1"]},
            None, Headers(), "manifest-1"
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["source_id"] for item in first["items"]], ["knowledge:doc-a"])
        self.assertIsNotNone(first["next_cursor"])
        self.service.upsert(self.upsert_request(
            source_id="knowledge:doc-c", operation_id="op-c",
            reps=[representation("chunk-c", "ranking fusion", ["ranking", "fusion"], [0.0, 0.0, 1.0])],
        ), "idem-c")
        status, second = self.service.handle(
            "GET", "/api/v1/index/sources/manifest",
            {"owner": ["knowledge"], "limit": ["1"], "cursor": [first["next_cursor"]]},
            None, Headers(), "manifest-2"
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["source_id"] for item in second["items"]], ["knowledge:doc-b"])

    def test_generation_creation_is_idempotent_and_payload_matches_schema(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        headers = Headers({"Idempotency-Key": "generation-key"})
        status, first = self.service.handle(
            "POST", "/api/v1/index/generations", {}, {"index_profile": self.identity, "request_id": "one"}, headers, "one"
        )
        self.assertEqual(status, 202)
        self.assertEqual(set(first["owner_reconciliation_checkpoints"]), {"memory", "knowledge"})
        self.assertIn("failed_sources", first["counts"])
        status, second = self.service.handle(
            "POST", "/api/v1/index/generations", {}, {"index_profile": self.identity, "request_id": "two"}, headers, "two"
        )
        self.assertEqual(status, 200)
        self.assertEqual(first["generation_id"], second["generation_id"])
        with self.assertRaisesRegex(IndexError, "idempotency key was reused"):
            self.service.handle(
                "POST", "/api/v1/index/generations", {},
                {"index_profile": self.identity, "unexpected_semantic_change": True}, headers, "three"
            )

    def test_vector_lookup_honors_source_revision_filter(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        request = {
            "request_id": "req-filter", "scope": SCOPE, "index_profile": self.identity,
            "embedding_profile": {"name": "technical-default", "version": "0.1"},
            "query_vector": [1.0, 0.0, 0.0], "input_type": "query", "metric": "cosine", "limit": 5,
            "index_generation": self.service.active_generation()["generation_id"],
            "source_revisions": ["not-rev-1"],
        }
        self.assertEqual(self.service.vector_neighbors(request)["candidates"], [])

    def test_handle_exposes_profile_and_health_routes(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        headers = Headers()
        status, health = self.service.handle("GET", "/api/v1/index/health", {}, None, headers, "req")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "alive")
        status, profile_response = self.service.handle(
            "GET", "/api/v1/index/profiles/test-profile/versions/0.1", {}, None, headers, "req"
        )
        self.assertEqual(status, 200)
        self.assertEqual(profile_response["digest"], self.bundle["digest"])


    def test_terminal_idempotency_binding_expires_after_thirty_days(self):
        request = self.upsert_request()
        self.service.upsert(request, "idem-expire")
        with self.service._connect() as db:
            db.execute("UPDATE operations SET created_at='2000-01-01 00:00:00' WHERE idempotency_key='idem-expire'")
        with self.assertRaises(IndexError) as raised:
            self.service.upsert(request, "idem-expire")
        self.assertEqual(raised.exception.code, "idempotency_key_expired")

    def test_active_writes_are_dual_applied_to_building_generation(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        status, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-dual"}), "build"
        )
        self.assertEqual(status, 202)
        target = generation["generation_id"]
        self.service.upsert(self.upsert_request(), "idem-dual")
        result = self.service.lexical_lookup({
            "request_id": "lookup-target", "scope": SCOPE, "index_profile": self.identity,
            "lexical_profile": {"name": "bm25-v1", "version": "0.1"},
            "terms": ["ranking"], "limit": 10, "index_generation": target,
        })
        self.assertEqual([item["source_id"] for item in result["candidates"]], ["knowledge:doc-a"])
        details = self.service.handle("GET", f"/api/v1/index/generations/{target}", {}, None, Headers(), "status")[1]
        self.assertGreater(int(details["dual_apply_journal_position"]), 0)

    def test_cutover_remains_fail_closed_until_owner_replay_protocol_is_integrated(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        status, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-cutover"}), "build"
        )
        self.assertEqual(status, 202)
        with self.assertRaises(IndexError) as raised:
            self.service.handle(
                "POST", f"/api/v1/index/generations/{generation['generation_id']}/cutover", {},
                {"expected_active_generation": self.service.active_generation()["generation_id"],
                 "owner_fences": []}, Headers({"Idempotency-Key": "cutover-key"}), "cutover"
            )
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(raised.exception.code, "not_ready")

    def test_target_generation_source_failure_is_durable_and_blocks_eligibility(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        status, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-failure"}), "build"
        )
        self.assertEqual(status, 202)
        target = generation["generation_id"]
        request = self.upsert_request(
            operation_id="too-large",
            reps=[representation("chunk-large", "x" * 513, ["x"], [1.0, 0.0, 0.0])]
        )
        request["target_generation"] = target
        with self.assertRaises(IndexError) as raised:
            self.service.upsert(request, "idem-too-large")
        self.assertEqual(raised.exception.code, "source_too_large")
        details = self.service.handle("GET", f"/api/v1/index/generations/{target}", {}, None, Headers(), "status")[1]
        self.assertEqual(details["counts"]["failed_sources"], 1)
        self.assertEqual(details["source_failures"][0]["reason_code"], "source_too_large")
        self.assertFalse(details["cutover_eligible"])


if __name__ == "__main__":
    unittest.main()
