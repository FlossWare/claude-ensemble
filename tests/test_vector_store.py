"""Contract tests for the isolated Chroma vector-store adapter primitives."""
from __future__ import annotations

import unittest

from runtime.vector_store import (
    ChromaVectorStore,
    VectorStoreError,
    collection_name,
    record_id,
)


PROFILE = "a" * 64
SCOPE = {"type": "project", "id": "project-a", "visibility": "private"}


def record(**overrides):
    value = {
        "generation_id": "generation-1",
        "profile_digest": PROFILE,
        "source_id": "knowledge:doc-a",
        "source_revision": "rev-1",
        "revision_sequence": 1,
        "chunk_id": "chunk-a",
        "chunker_profile": "markdown-default",
        "chunker_version": "0.1",
        "embedding_model": "nomic",
        "embedding_version": "r1",
        "embedding_dimensions": 3,
        "scope": dict(SCOPE),
        "text": "ranking fusion",
        "embedding": [1.0, 0.0, 0.0],
    }
    value.update(overrides)
    return value


class FakeCollection:
    def __init__(self):
        self.upsert_calls = []
        self.query_calls = []
        self.delete_calls = []
        self.records = {}

    def upsert(self, *, ids, documents, embeddings, metadatas):
        self.upsert_calls.append((ids, documents, embeddings, metadatas))
        for item_id, doc, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self.records[item_id] = (doc, embedding, metadata)

    @staticmethod
    def _matches(metadata, where):
        if "$and" in where:
            return all(FakeCollection._matches(metadata, clause) for clause in where["$and"])
        for key, expected in where.items():
            if isinstance(expected, dict) and "$in" in expected:
                if metadata.get(key) not in expected["$in"]:
                    return False
            elif metadata.get(key) != expected:
                return False
        return True

    def query(self, *, query_embeddings, n_results, where, include):
        self.query_calls.append((query_embeddings, n_results, where, include))
        selected = []
        for item_id, (doc, embedding, metadata) in self.records.items():
            if self._matches(metadata, where):
                selected.append((item_id, doc, metadata, 0.0))
        selected = selected[:n_results]
        return {
            "ids": [[row[0] for row in selected]],
            "documents": [[row[1] for row in selected]],
            "metadatas": [[row[2] for row in selected]],
            "distances": [[row[3] for row in selected]],
        }

    def delete(self, *, where=None, ids=None):
        self.delete_calls.append(where if where is not None else {"ids": ids})
        if ids is not None:
            self.records = {item_id: row for item_id, row in self.records.items() if item_id not in ids}
        else:
            self.records = {item_id: row for item_id, row in self.records.items()
                            if row[2].get("source_id") != where.get("source_id")}

    def get(self, *, include, where=None):
        selected = [(item_id, row) for item_id, row in self.records.items()
                    if where is None or self._matches(row[2], where)]
        result = {"ids": [item_id for item_id, _ in selected]}
        if "metadatas" in include:
            result["metadatas"] = [row[2] for _, row in selected]
        return result


class FakeClient:
    def __init__(self):
        self.collections = {}
        self.calls = []

    def get_or_create_collection(self, *, name, metadata):
        self.calls.append((name, metadata))
        return self.collections.setdefault(name, FakeCollection())


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.store = ChromaVectorStore(
            "/tmp/not-used", profile_digest=PROFILE,
            generation_id="generation-1", metric="cosine", client=self.client,
        )

    def test_collection_identity_is_stable_and_isolates_generation_profile_metric(self):
        base = collection_name(PROFILE, "generation-1", "cosine")
        self.assertEqual(base, collection_name(PROFILE, "generation-1", "cosine"))
        self.assertNotEqual(base, collection_name(PROFILE, "generation-2", "cosine"))
        self.assertNotEqual(base, collection_name("b" * 64, "generation-1", "cosine"))
        self.assertNotEqual(base, collection_name(PROFILE, "generation-1", "dot_product"))
        with self.assertRaises(VectorStoreError):
            collection_name("not-a-digest", "generation-1", "cosine")

    def test_record_id_is_deterministic_and_revision_specific(self):
        self.assertEqual(record_id(record()), record_id(record()))
        self.assertNotEqual(record_id(record()), record_id(record(revision_sequence=2)))

    def test_query_enforces_scope_and_source_filters(self):
        self.store.upsert([
            record(),
            record(source_id="knowledge:doc-b", chunk_id="chunk-b",
                   scope={"type": "project", "id": "project-b", "visibility": "private"}),
        ])
        candidates = self.store.query(
            [1.0, 0.0, 0.0], scope=SCOPE, limit=5, metric="cosine",
            source_ids=["knowledge:doc-a"], source_revisions=["rev-1"],
        )
        self.assertEqual([item["source_id"] for item in candidates], ["knowledge:doc-a"])
        _, _, where, _ = self.client.collections[self.store.name].query_calls[0]
        self.assertIn({"source_id": {"$in": ["knowledge:doc-a"]}}, where["$and"])
        self.assertIn({"source_revision": {"$in": ["rev-1"]}}, where["$and"])

    def test_upsert_and_query_preserve_identity_and_contract_metadata(self):
        self.store.upsert([record()])
        candidates = self.store.query([1.0, 0.0, 0.0], scope=SCOPE, limit=5, metric="cosine")
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["source_id"], "knowledge:doc-a")
        self.assertEqual(candidate["source_revision"], "rev-1")
        self.assertEqual(candidate["revision_sequence"], 1)
        self.assertEqual(candidate["chunk_id"], "chunk-a")
        self.assertEqual(candidate["similarity"], 1.0)
        self.assertEqual(candidate["embedding"]["metric"], "cosine")
        _, limit, where, include = self.client.collections[self.store.name].query_calls[0]
        self.assertEqual(limit, 5)
        self.assertEqual(where["$and"][0], {"scope_id": "project-a"})
        self.assertIn("distances", include)

    def test_rejects_wrong_generation_profile_and_duplicate_ids(self):
        with self.assertRaisesRegex(VectorStoreError, "generation"):
            self.store.upsert([record(generation_id="generation-other")])
        with self.assertRaisesRegex(VectorStoreError, "profile"):
            self.store.upsert([record(profile_digest="b" * 64)])
        with self.assertRaisesRegex(VectorStoreError, "duplicate"):
            self.store.upsert([record(), record()])

    def test_query_rejects_metric_mismatch_and_unbounded_inputs(self):
        with self.assertRaisesRegex(VectorStoreError, "metric"):
            self.store.query([1.0, 0.0, 0.0], scope=SCOPE, limit=5, metric="euclidean")
        with self.assertRaises(VectorStoreError):
            self.store.query([float("nan")], scope=SCOPE, limit=5, metric="cosine")
        with self.assertRaises(VectorStoreError):
            self.store.query([1.0], scope=SCOPE, limit=1001, metric="cosine")

    def test_replace_source_upserts_before_removing_stale_vectors(self):
        first = record(source_id="knowledge:doc-a", chunk_id="chunk-1")
        second = record(source_id="knowledge:doc-a", chunk_id="chunk-2")
        self.store.replace_source("knowledge:doc-a", [first, second])
        self.assertEqual(len(self.store.list_ids()), 2)
        replacement = record(source_id="knowledge:doc-a", chunk_id="chunk-3")
        self.store.replace_source("knowledge:doc-a", [replacement])
        self.assertEqual(self.store.list_ids(), {record_id(replacement)})
        self.assertEqual(len(self.client.collections[self.store.name].records), 1)

    def test_source_deletion_and_id_enumeration(self):
        self.store.upsert([record()])
        ids = self.store.list_ids()
        self.assertEqual(ids, {record_id(record())})
        self.store.delete_source("knowledge:doc-a")
        self.assertEqual(self.store.list_ids(), set())

    def test_rejects_malformed_chroma_query_response(self):
        collection = self.client.collections[self.store.name]
        collection.query = lambda **kwargs: {"ids": [], "metadatas": [], "documents": [], "distances": []}
        with self.assertRaisesRegex(VectorStoreError, "malformed"):
            self.store.query([1.0, 0.0, 0.0], scope=SCOPE, limit=5, metric="cosine")


class PersistentChromaIntegrationTests(unittest.TestCase):
    """Exercise the real Chroma API and disk persistence, not only the fake client."""

    def test_persistent_upsert_scope_query_and_reopen(self):
        import tempfile
        import chromadb

        with tempfile.TemporaryDirectory(prefix="ce-chroma-test-") as directory:
            client = chromadb.PersistentClient(path=directory)
            store = ChromaVectorStore(
                directory, profile_digest=PROFILE, generation_id="generation-real",
                metric="cosine", client=client,
            )
            store.upsert([
                record(generation_id="generation-real", chunk_id="real-a",
                       embedding=[1.0, 0.0, 0.0]),
                record(generation_id="generation-real", source_id="knowledge:other",
                       chunk_id="real-b", scope={"type": "project", "id": "project-b",
                                                "visibility": "private"},
                       embedding=[0.0, 1.0, 0.0]),
            ])
            # Re-open the persistent database to prove the adapter isn't relying on
            # process-local fake state.
            reopened = ChromaVectorStore(
                directory, profile_digest=PROFILE, generation_id="generation-real",
                metric="cosine", client=chromadb.PersistentClient(path=directory),
            )
            results = reopened.query(
                [1.0, 0.0, 0.0], scope=SCOPE, limit=10, metric="cosine",
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["source_id"], "knowledge:doc-a")
            self.assertEqual(results[0]["chunk_id"], "real-a")
            self.assertAlmostEqual(results[0]["similarity"], 1.0, places=5)
            self.assertEqual(reopened.list_ids(), {
                record_id(record(generation_id="generation-real", chunk_id="real-a",
                                 embedding=[1.0, 0.0, 0.0])),
                record_id(record(generation_id="generation-real", source_id="knowledge:other",
                                 chunk_id="real-b", scope={"type": "project", "id": "project-b",
                                                          "visibility": "private"},
                                 embedding=[0.0, 1.0, 0.0])),
            })


if __name__ == "__main__":
    unittest.main()
