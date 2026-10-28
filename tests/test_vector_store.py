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

    def query(self, *, query_embeddings, n_results, where, include):
        self.query_calls.append((query_embeddings, n_results, where, include))
        selected = []
        for item_id, (doc, embedding, metadata) in self.records.items():
            if all(metadata.get(key) == value for key, value in where.items()
                   if not key.startswith("$")):
                selected.append((item_id, doc, metadata, 0.0))
        selected = selected[:n_results]
        return {
            "ids": [[row[0] for row in selected]],
            "documents": [[row[1] for row in selected]],
            "metadatas": [[row[2] for row in selected]],
            "distances": [[row[3] for row in selected]],
        }

    def delete(self, *, where):
        self.delete_calls.append(where)
        self.records = {item_id: row for item_id, row in self.records.items()
                        if row[2].get("source_id") != where.get("source_id")}

    def get(self, *, include):
        return {"ids": list(self.records)}


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
            self.store.query([1.0], scope=SCOPE, limit=101, metric="cosine")

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


if __name__ == "__main__":
    unittest.main()
