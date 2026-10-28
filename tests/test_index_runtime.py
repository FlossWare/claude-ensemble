"""Contract-focused tests for the durable Index retrieval slice."""
from __future__ import annotations

import tempfile
import unittest
import json
import os
import threading
from datetime import datetime, timezone, timedelta
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
        self.assertEqual(status, 202)
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

    def test_vector_neighbor_rejects_hostile_magnitudes_without_crashing_lookup(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        request = {
            "request_id": "req-hostile-vector", "scope": SCOPE, "index_profile": self.identity,
            "embedding_profile": {"name": "technical-default", "version": "0.1"},
            "query_vector": [1e200, 0.0, 0.0], "input_type": "query", "metric": "cosine", "limit": 5,
            "index_generation": self.service.active_generation()["generation_id"],
        }
        with self.assertRaisesRegex(IndexError, "query vector"):
            self.service.vector_neighbors(request)
        request["query_vector"] = [1.0, 0.0, 0.0]
        self.assertEqual(self.service.vector_neighbors(request)["candidates"][0]["chunk_id"], "chunk-a")

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

    def test_new_operation_can_reuse_a_matching_source_revision_sequence(self):
        self.service.upsert(self.upsert_request(), "idem-a")
        status, result = self.service.upsert(self.upsert_request(operation_id="op-other"), "idem-other")
        self.assertEqual(status, 202)
        self.assertEqual(result["revision_sequence"], 1)

    def test_idempotency_conflict_and_expiry_precede_durable_validation_failures(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-idem-validation"}), "build"
        )
        target = generation["generation_id"]
        original = self.upsert_request(operation_id="target-bound")
        original["target_generation"] = target
        self.service.upsert(original, "target-bound-key")
        changed = self.upsert_request(operation_id="target-bound", reps=[
            representation("chunk-a", "x" * 600, ["ranking"], [1.0, 0.0, 0.0])
        ])
        changed["target_generation"] = target
        with self.assertRaises(IndexError) as conflict:
            self.service.upsert(changed, "target-bound-key")
        self.assertEqual(conflict.exception.code, "idempotency_conflict")
        with self.service._connect() as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM generation_source_failures WHERE generation_id=? AND source_id=?",
                (target, "knowledge:doc-a")
            ).fetchone()[0], 0)
        expired = self.upsert_request(operation_id="target-expired")
        expired["target_generation"] = target
        self.service.upsert(expired, "target-expired-key")
        with self.service._connect() as db:
            db.execute("UPDATE operations SET created_at='2000-01-01 00:00:00', terminal_at='2000-01-01 00:00:00' WHERE idempotency_key='target-expired-key'")
        changed_expired = self.upsert_request(operation_id="target-expired", reps=[
            representation("chunk-a", "y" * 600, ["ranking"], [1.0, 0.0, 0.0])
        ])
        changed_expired["target_generation"] = target
        with self.assertRaises(IndexError) as expiry:
            self.service.upsert(changed_expired, "target-expired-key")
        self.assertEqual(expiry.exception.code, "idempotency_key_expired")
        with self.service._connect() as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM generation_source_failures WHERE generation_id=? AND source_id=?",
                (target, "knowledge:doc-a")
            ).fetchone()[0], 0)

    def test_source_status_and_manifest_include_target_only_high_water(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-high-water"}), "build"
        )
        target = generation["generation_id"]
        target_only = self.upsert_request(source_id="knowledge:target-only", sequence=10, operation_id="target-only")
        target_only["target_generation"] = target
        self.service.upsert(target_only, "target-only-key")
        self.service.upsert(self.upsert_request(source_id="knowledge:active-and-target", sequence=1,
                                                operation_id="active-first"), "active-first-key")
        target_newer = self.upsert_request(source_id="knowledge:active-and-target", sequence=10,
                                           operation_id="target-newer")
        target_newer["target_generation"] = target
        self.service.upsert(target_newer, "target-newer-key")
        restarted = IndexService(Path(self.temp.name) / "index.sqlite3", self.bundle)
        target_status = restarted.source_status("knowledge:target-only")
        self.assertEqual(target_status["latest_revision_sequence"], 10)
        self.assertIsNone(target_status["indexed_revision_sequence"])
        mixed_status = restarted.source_status("knowledge:active-and-target")
        self.assertEqual(mixed_status["latest_revision_sequence"], 10)
        self.assertEqual(mixed_status["indexed_revision_sequence"], 1)
        status, manifest = restarted.handle(
            "GET", "/api/v1/index/sources/manifest", {"owner": ["knowledge"], "limit": ["100"]},
            None, Headers(), "high-water-manifest"
        )
        self.assertEqual(status, 200)
        items = {item["source_id"]: item for item in manifest["items"]}
        self.assertEqual(items["knowledge:target-only"]["latest_revision_sequence"], 10)
        self.assertIsNone(items["knowledge:target-only"]["indexed_revision_sequence"])
        self.assertEqual(items["knowledge:active-and-target"]["latest_revision_sequence"], 10)
        self.assertEqual(items["knowledge:active-and-target"]["indexed_revision_sequence"], 1)

    def test_aggregate_chunk_limit_records_durable_generation_failure(self):
        limited_bundle = json.loads(json.dumps(self.bundle))
        limited_bundle["limits"]["max_chunks"] = 1
        limited_bundle["digest"] = profile_digest(limited_bundle)
        db_path = Path(self.temp.name) / "limited-index.sqlite3"
        limited = IndexService(db_path, limited_bundle)
        identity = {k: limited_bundle[k] for k in ("name", "version", "digest")}

        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        _, generation = limited.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": identity}, Headers({"Idempotency-Key": "build-aggregate-failure"}), "build"
        )
        target = generation["generation_id"]
        request = self.upsert_request(source_id="knowledge:too-many", sequence=3, operation_id="too-many")
        request["index_profile"] = identity
        request["target_generation"] = target
        request["representations"] = [
            representation("chunk-a", "ranking", ["ranking"], [1.0, 0.0, 0.0]),
            representation("chunk-b", "fusion", ["fusion"], [0.0, 1.0, 0.0]),
        ]
        with self.assertRaises(IndexError) as raised:
            limited.upsert(request, "too-many-key")
        self.assertEqual(raised.exception.code, "source_too_large")
        details = limited.handle("GET", f"/api/v1/index/generations/{target}", {}, None, Headers(), "status")[1]
        self.assertEqual(details["counts"]["failed_sources"], 1)
        restarted = IndexService(db_path, limited_bundle)
        with restarted._connect() as db:
            failure = db.execute(
                "SELECT reason_code FROM generation_source_failures WHERE generation_id=? AND source_id=?",
                (target, "knowledge:too-many")
            ).fetchone()
        self.assertEqual(failure["reason_code"], "source_too_large")
        corrected = self.upsert_request(source_id="knowledge:too-many", sequence=4, operation_id="corrected")
        corrected["index_profile"] = identity
        corrected["target_generation"] = target
        limited.upsert(corrected, "corrected-key")
        with restarted._connect() as db:
            cleared = db.execute(
                "SELECT COUNT(*) FROM generation_source_failures WHERE generation_id=? AND source_id=?",
                (target, "knowledge:too-many")
            ).fetchone()[0]
        self.assertEqual(cleared, 0)

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
                "CE_EMBEDDING_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
            }):
                base = f"http://127.0.0.1:{server.server_address[1]}"
                health = json.loads(urlopen(base + "/api/v1/index/health", timeout=2).read())
                self.assertEqual(health["status"], "alive")
                malformed_number = Request(
                    base + "/api/v1/index/lexical/lookup",
                    data=b'{"overflow":1e999}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as malformed_error:
                    urlopen(malformed_number, timeout=2)
                self.assertEqual(malformed_error.exception.code, 400)
                profile_request = Request(base + "/api/v1/index/profiles/test-profile/versions/0.1",
                                          headers={"X-CE-Request-ID": "profile-http"})
                with urlopen(profile_request, timeout=2) as response:
                    profile_response = json.loads(response.read())
                self.assertEqual(profile_response["request_id"], "profile-http")
                active_request = Request(base + "/api/v1/index/generations/active",
                                          headers={"X-CE-Request-ID": "active-http"})
                with urlopen(active_request, timeout=2) as response:
                    active_response = json.loads(response.read())
                self.assertEqual(active_response["request_id"], "active-http")
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
                    self.assertEqual(response.status, 202)
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

                class DeterministicEmbeddingEngine:
                    # Controlled fake for REST wiring only. The pinned real-model
                    # inference remains covered by the separate offline CPU CI job.
                    def embed(self, inputs, normalization):
                        return (
                            {"provider": "local", "model_id": "local-nomic", "model_version": "r1",
                             "dimensions": 3, "normalization": "l2"},
                            [{"input_id": item["input_id"], "input_type": item["input_type"],
                              "status": "complete", "vector": [1.0, 0.0, 0.0], "dimensions": 3}
                             for item in inputs],
                        )

                vector_body = {
                    "query_id": "query-vector-http", "request_id": "vector-retrieval-http",
                    "scope": SCOPE, "index_profile": self.identity,
                    "embedding_profile": {"name": "technical-default", "version": "0.1"},
                    "index_generation": generation["generation_id"], "limit": 5,
                    "query": {"text": "ranking algorithm"},
                }
                deadline = (datetime.now(timezone.utc) + timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                vector_request = Request(base + "/api/v1/vector-retrieval/search",
                    data=json.dumps(vector_body).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-CE-Deadline": deadline}, method="POST")
                observed_deadlines = {}
                original_embed = Handler._embed
                def capture_embedding_deadline(handler, request_value):
                    observed_deadlines["embedding"] = handler.headers.get("X-CE-Deadline")
                    return original_embed(handler, request_value)
                with patch.object(Handler, "_embed", capture_embedding_deadline), \
                     patch("runtime.server.get_embedding_engine", return_value=DeterministicEmbeddingEngine()):
                    with urlopen(vector_request, timeout=4) as response:
                        vector_result = json.loads(response.read())
                self.assertEqual(observed_deadlines["embedding"], deadline)
                self.assertEqual(vector_result["metric"], "cosine")
                self.assertEqual(vector_result["candidates"][0]["source_id"], "knowledge:doc-a")
                self.assertEqual(vector_result["candidates"][0]["retrieval_rank"], 1)
                self.assertEqual(vector_result["candidates"][0]["provenance"]["embedding_model"], "local-nomic")
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
        self.assertEqual(first["request_id"], "one")
        self.assertEqual(set(first["owner_reconciliation_checkpoints"]), {"memory", "knowledge"})
        self.assertIn("failed_sources", first["counts"])
        status, second = self.service.handle(
            "POST", "/api/v1/index/generations", {}, {"index_profile": self.identity, "request_id": "two"}, headers, "two"
        )
        self.assertEqual(status, 200)
        self.assertEqual(second["request_id"], "two")
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


    def test_known_index_routes_reject_unsupported_methods_with_405(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        mismatches = [
            ("POST", "/api/v1/index/health"),
            ("GET", "/api/v1/index/operations/upsert"),
            ("GET", "/api/v1/index/operations/delete"),
            ("GET", "/api/v1/index/vector-neighbors"),
            ("GET", "/api/v1/index/lexical/lookup"),
            ("POST", "/api/v1/index/sources/manifest"),
            ("POST", "/api/v1/index/generations/active"),
            ("DELETE", "/api/v1/index/generations/gen-test/abandon"),
            ("GET", "/api/v1/index/generations/gen-test/cutover"),
            ("POST", "/api/v1/index/sources/knowledge%3Adoc-a/status"),
        ]
        for method, path in mismatches:
            with self.subTest(method=method, path=path):
                with self.assertRaises(IndexError) as raised:
                    self.service.handle(method, path, {}, {}, Headers(), "wrong-method")
                self.assertEqual(raised.exception.status, 405)
                self.assertEqual(raised.exception.code, "method_not_allowed")

    def test_runtime_error_codes_are_declared_by_index_schema(self):
        schema_path = Path(__file__).resolve().parents[1] / "docs" / "contracts" / "schemas" / "index.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        allowed = set(schema["$defs"]["errorResponse"]["properties"]["error"]["properties"]["code"]["enum"])
        for code in ("invalid_cursor", "scope_conflict", "source_not_found"):
            with self.subTest(code=code):
                self.assertIn(code, allowed)

    def test_terminal_idempotency_binding_expires_after_thirty_days(self):
        request = self.upsert_request()
        self.service.upsert(request, "idem-expire")
        with self.service._connect() as db:
            db.execute("UPDATE operations SET created_at='2000-01-01 00:00:00', terminal_at='2000-01-01 00:00:00' WHERE idempotency_key='idem-expire'")
        with self.assertRaises(IndexError) as raised:
            self.service.upsert(request, "idem-expire")
        self.assertEqual(raised.exception.code, "idempotency_key_expired")
        changed = self.upsert_request(reps=[representation("chunk-a", "changed payload", ["changed"], [0.0, 1.0, 0.0])])
        with self.assertRaises(IndexError) as reused:
            self.service.upsert(changed, "idem-expire")
        self.assertEqual(reused.exception.code, "idempotency_key_expired")
        with self.assertRaises(IndexError) as operation_reuse:
            self.service.upsert(request, "fresh-idempotency-key")
        self.assertEqual(operation_reuse.exception.code, "idempotency_conflict")

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
        with self.service._connect() as db:
            copied = db.execute(
                "SELECT source_id,revision_sequence FROM representations WHERE generation_id=?",
                (target,)
            ).fetchall()
            self.assertEqual([(item["source_id"], item["revision_sequence"]) for item in copied],
                             [("knowledge:doc-a", 1)])
        details = self.service.handle("GET", f"/api/v1/index/generations/{target}", {}, None, Headers(), "status")[1]
        self.assertGreater(int(details["dual_apply_journal_position"]), 0)
        delete = {
            "operation_id": "delete-dual", "request_id": "delete-dual", "source_id": "knowledge:doc-a",
            "source_revision": "tombstone-rev-2", "revision_sequence": 2, "scope": SCOPE,
            "index_profile": self.identity, "delete_scope": "source",
        }
        self.service.delete(delete, "idem-delete-dual")
        with self.service._connect() as db:
            remaining = db.execute("SELECT COUNT(*) AS count FROM representations WHERE generation_id=? AND source_id=?",
                                   (target, "knowledge:doc-a")).fetchone()["count"]
            journal_count = db.execute("SELECT COUNT(*) AS count FROM dual_apply_journal WHERE generation_id=?",
                                        (target,)).fetchone()["count"]
        self.assertEqual(remaining, 0)
        self.assertEqual(journal_count, 2)

    def test_stale_dual_apply_is_journaled_as_skipped_stale(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-stale"}), "build"
        )
        target = generation["generation_id"]
        newer = self.upsert_request(source_id="knowledge:stale-doc", sequence=10, operation_id="target-newer")
        newer["target_generation"] = target
        self.service.upsert(newer, "target-newer-key")
        # Model a target generation restored from a snapshot whose source
        # high-water metadata has not yet been reconciled.
        with self.service._connect() as db:
            db.execute("DELETE FROM source_high_water WHERE source_id=?", ("knowledge:stale-doc",))
        active = self.upsert_request(source_id="knowledge:stale-doc", sequence=1, operation_id="active-older")
        self.service.upsert(active, "active-older-key")
        with self.service._connect() as db:
            rows = db.execute(
                "SELECT status,revision_sequence FROM dual_apply_journal WHERE generation_id=? AND source_id=? ORDER BY revision_sequence",
                (target, "knowledge:stale-doc")
            ).fetchall()
            target_sequence = db.execute(
                "SELECT MAX(revision_sequence) AS sequence FROM representations WHERE generation_id=? AND source_id=?",
                (target, "knowledge:stale-doc")
            ).fetchone()["sequence"]
        self.assertEqual(target_sequence, 10)
        self.assertEqual([(row["status"], row["revision_sequence"]) for row in rows],
                         [("skipped_stale", 1), ("applied", 10)])

    def test_completed_operations_record_terminal_timestamp(self):
        self.service.upsert(self.upsert_request(), "terminal-time")
        with self.service._connect() as db:
            row = db.execute("SELECT terminal_at,status FROM operations WHERE idempotency_key=?",
                             ("terminal-time",)).fetchone()
        self.assertEqual(row["status"], "complete")
        self.assertIsNotNone(row["terminal_at"])

    def test_owner_checkpoints_are_monotonic_and_fences_are_explicit(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        status, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-fence"}), "build"
        )
        target = generation["generation_id"]
        status, checkpoint = self.service.handle(
            "POST", f"/api/v1/index/generations/{target}/owner-checkpoints", {},
            {"owner": "memory", "applied_change_sequence": 3}, Headers({"Idempotency-Key": "checkpoint-3"}), "checkpoint"
        )
        self.assertEqual(status, 200)
        self.assertEqual(checkpoint["applied_change_sequence"], 3)
        with self.assertRaises(IndexError) as raised:
            self.service.handle(
                "POST", f"/api/v1/index/generations/{target}/owner-checkpoints", {},
                {"owner": "memory", "applied_change_sequence": 2}, Headers({"Idempotency-Key": "checkpoint-2"}), "checkpoint-regress"
            )
        self.assertEqual(raised.exception.code, "revision_sequence_regression")
        from datetime import datetime, timezone, timedelta
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
        fence_payload = {
            "owner": "memory", "target_generation": target, "fence_id": "memory-fence-1",
            "fence_token": "fence-token-with-enough-entropy", "sealed_change_sequence": 3,
            "expires_at": expiry, "state": "held",
        }
        naive_fence = dict(fence_payload)
        naive_fence["fence_id"] = "memory-fence-naive"
        naive_fence["expires_at"] = "2026-10-28T00:00:00"
        with self.assertRaises(IndexError) as naive_expiry:
            self.service.handle(
                "PUT", f"/api/v1/index/generations/{target}/owner-fences/memory/memory-fence-naive", {},
                naive_fence, Headers(), "fence-naive"
            )
        self.assertEqual(naive_expiry.exception.code, "invalid_request")
        status, fence = self.service.handle(
            "PUT", f"/api/v1/index/generations/{target}/owner-fences/memory/memory-fence-1", {},
            fence_payload, Headers(), "fence"
        )
        self.assertEqual(status, 200)
        self.assertEqual(fence["fence_state"], "held")
        status, released = self.service.handle(
            "DELETE", f"/api/v1/index/generations/{target}/owner-fences/memory/memory-fence-1",
            {}, None, Headers(), "release"
        )
        self.assertEqual(status, 200)
        self.assertTrue(released["released"])

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

    def test_active_same_revision_is_idempotent_only_for_matching_payload(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        first = self.upsert_request(operation_id="active-same-first")
        self.service.upsert(first, "active-same-key-1")
        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-after-active"}), "build"
        )
        target = generation["generation_id"]
        matching = self.upsert_request(operation_id="active-same-second")
        status, _ = self.service.upsert(matching, "active-same-key-2")
        self.assertEqual(status, 202)
        with self.service._connect() as db:
            copied = db.execute("SELECT COUNT(*) AS count FROM representations WHERE generation_id=? AND source_id=?",
                                (target, "knowledge:doc-a")).fetchone()["count"]
        self.assertEqual(copied, 1)
        conflicting = self.upsert_request(
            operation_id="active-same-conflict",
            reps=[representation("chunk-a", "different payload", ["different"], [0.0, 1.0, 0.0])]
        )
        with self.assertRaises(IndexError) as raised:
            self.service.upsert(conflicting, "active-same-key-3")
        self.assertEqual(raised.exception.code, "revision_conflict")

    def test_target_generation_replay_accepts_same_revision_only_for_same_payload(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-replay"}), "build"
        )
        target = generation["generation_id"]
        active_request = self.upsert_request(operation_id="active-op")
        self.service.upsert(active_request, "active-key")
        replay = dict(active_request)
        replay["operation_id"] = "replay-op"
        replay["target_generation"] = target
        status, result = self.service.upsert(replay, "replay-key")
        self.assertEqual(status, 202)
        self.assertEqual(result["index_generation"], target)
        conflicting = dict(replay)
        conflicting["operation_id"] = "replay-conflict"
        conflicting["representations"] = [representation("chunk-a", "different payload", ["different"], [0.0, 1.0, 0.0])]
        with self.assertRaises(IndexError) as raised:
            self.service.upsert(conflicting, "replay-conflict-key")
        self.assertEqual(raised.exception.code, "revision_conflict")

    def test_delete_rejects_scope_partition_mismatch(self):
        self.service.upsert(self.upsert_request(), "scope-upsert")
        delete = {
            "operation_id": "wrong-scope-delete", "source_id": "knowledge:doc-a",
            "source_revision": "tombstone-rev-2", "revision_sequence": 2,
            "scope": {"type": "project", "id": "project-b", "visibility": "private"},
            "index_profile": self.identity, "delete_scope": "source",
        }
        with self.assertRaises(IndexError) as raised:
            self.service.delete(delete, "wrong-scope-key")
        self.assertEqual(raised.exception.code, "scope_conflict")

    def test_abandon_and_checkpoint_require_idempotency_and_allow_safe_retries(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-lifecycle"}), "build"
        )
        target = generation["generation_id"]
        with self.assertRaises(IndexError) as missing_key:
            self.service.handle("POST", f"/api/v1/index/generations/{target}/owner-checkpoints", {},
                               {"owner": "memory", "applied_change_sequence": 0}, Headers(), "missing-key")
        self.assertEqual(missing_key.exception.code, "invalid_request")
        checkpoint_headers = Headers({"Idempotency-Key": "checkpoint-retry"})
        first = self.service.handle("POST", f"/api/v1/index/generations/{target}/owner-checkpoints", {},
                                    {"owner": "memory", "applied_change_sequence": 1}, checkpoint_headers, "first")[1]
        second = self.service.handle("POST", f"/api/v1/index/generations/{target}/owner-checkpoints", {},
                                     {"owner": "memory", "applied_change_sequence": 1}, checkpoint_headers, "second")[1]
        self.assertEqual(first["applied_change_sequence"], second["applied_change_sequence"])
        abandon_headers = Headers({"Idempotency-Key": "abandon-retry"})
        first_abandon = self.service.handle("POST", f"/api/v1/index/generations/{target}/abandon", {},
                                            {}, abandon_headers, "abandon-1")[1]
        second_abandon = self.service.handle("POST", f"/api/v1/index/generations/{target}/abandon", {},
                                             {}, abandon_headers, "abandon-2")[1]
        self.assertEqual(first_abandon["status"], "abandoned")
        self.assertEqual(second_abandon["status"], "abandoned")

    def test_target_generation_source_failure_clears_after_successful_replay(self):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        _, generation = self.service.handle(
            "POST", "/api/v1/index/generations", {},
            {"index_profile": self.identity}, Headers({"Idempotency-Key": "build-failure-recovery"}), "build"
        )
        target = generation["generation_id"]
        oversized = self.upsert_request(
            operation_id="oversized-target",
            reps=[representation("chunk-a", "x" * 513, ["x"], [0.0, 1.0, 0.0])]
        )
        oversized["target_generation"] = target
        with self.assertRaises(IndexError) as failed:
            self.service.upsert(oversized, "oversized-target-key")
        self.assertEqual(failed.exception.code, "source_too_large")
        _, details = self.service.handle(
            "GET", f"/api/v1/index/generations/{target}", {}, None, Headers(), "failure-status"
        )
        self.assertEqual(details["counts"]["failed_sources"], 1)
        valid = self.upsert_request(operation_id="recovered-target")
        valid["target_generation"] = target
        self.service.upsert(valid, "recovered-target-key")
        _, details = self.service.handle(
            "GET", f"/api/v1/index/generations/{target}", {}, None, Headers(), "recovered-status"
        )
        self.assertEqual(details["counts"]["failed_sources"], 0)
        self.assertEqual(details["source_failures"], [])

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
