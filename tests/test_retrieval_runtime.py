"""Unit tests for stateless lexical and vector retrieval."""
from __future__ import annotations

import unittest

from runtime.retrieval import (
    LexicalRetrievalService,
    RetrievalError,
    VectorRetrievalService,
    bm25_v1,
    vector_rank,
)


PROFILE = {"name": "default", "version": "0.1", "digest": "a" * 64}
SCOPE = {"type": "project", "id": "ce", "visibility": "private"}
CANDIDATE = {
    "source_id": "knowledge:doc-a",
    "source_revision": "rev-1",
    "revision_sequence": 1,
    "chunk_id": "chunk-a",
    "chunker": {"profile": "markdown-default", "version": "0.1"},
    "text": "The ranking algorithm uses reciprocal rank fusion.",
}


class RetrievalAlgorithmTests(unittest.TestCase):
    def test_bm25_scores_and_orders_candidates_deterministically(self):
        common = dict(CANDIDATE)
        common.update({"term_frequency_evidence": [{"term": "ranking", "term_frequency": 2}], "document_length": 10})
        rare = dict(CANDIDATE)
        rare.update({
            "source_id": "knowledge:doc-b",
            "chunk_id": "chunk-b",
            "term_frequency_evidence": [
                {"term": "ranking", "term_frequency": 2},
                {"term": "fusion", "term_frequency": 1},
            ],
            "document_length": 10,
        })
        ranked = bm25_v1(
            ["ranking", "fusion", "ranking"],
            [common, rare],
            {"document_count": 10, "average_document_length": 10, "document_frequency": {"ranking": 4, "fusion": 1}},
        )
        self.assertEqual([c["chunk_id"] for c in ranked], ["chunk-b", "chunk-a"])
        self.assertEqual([c["retrieval_rank"] for c in ranked], [1, 2])
        self.assertEqual(ranked[0]["score_semantics"], "bm25-v1")
        self.assertEqual(ranked[0]["matched_terms"], ["ranking", "fusion"])
        self.assertNotIn("term_frequency_evidence", ranked[0])

    def test_bm25_empty_corpus_returns_no_candidates(self):
        self.assertEqual(
            bm25_v1(["needle"], [], {"document_count": 0, "average_document_length": 0, "document_frequency": {}}),
            [],
        )

    def test_bm25_rejects_empty_query_terms(self):
        with self.assertRaises(RetrievalError):
            bm25_v1([], [], {"document_count": 1, "average_document_length": 1, "document_frequency": {}})

    def test_vector_ranking_respects_metric_direction_and_ties(self):
        a = dict(CANDIDATE, distance=0.2)
        b = dict(CANDIDATE, source_id="knowledge:doc-b", chunk_id="chunk-b", distance=0.8)
        self.assertEqual([x["chunk_id"] for x in vector_rank([a, b], "cosine")], ["chunk-b", "chunk-a"])
        self.assertEqual([x["chunk_id"] for x in vector_rank([a, b], "euclidean")], ["chunk-a", "chunk-b"])

    def test_vector_rejects_non_finite_values(self):
        with self.assertRaises(RetrievalError):
            vector_rank([dict(CANDIDATE, distance=float("nan"))], "cosine")

    def test_lexical_service_calls_pinned_tokenization_and_index(self):
        calls = []
        def resolve(req):
            calls.append(("resolve", req))
            return {"profile_bundle": {
                "name": "default", "version": "0.1", "digest": "a" * 64,
                "lexical": {"profile": "bm25-v1", "version": "0.1"},
                "tokenization": {"profile": "technical-default", "version": "0.1"},
            }}
        def tokenize(req):
            calls.append(("tokenize", req))
            return {
                "index_profile": PROFILE, "profile": "technical-default", "version": "0.1",
                "tokens": [{"term": "ranking"}, {"term": "fusion"}],
            }
        def lookup(req):
            calls.append(("lookup", req))
            item = dict(CANDIDATE)
            item.update({
                "document_length": 10,
                "term_frequency_evidence": [
                    {"term": "ranking", "term_frequency": 2},
                    {"term": "fusion", "term_frequency": 1},
                ],
            })
            return {
                "index_generation": "g1", "request_id": "r1", "truncated": False,
                "candidates": [item],
                "corpus_statistics": {"document_count": 2, "average_document_length": 10,
                                      "document_frequency": {"ranking": 1, "fusion": 1}},
            }
        service = LexicalRetrievalService(tokenize, lookup, resolve)
        result = service.search({
            "request_id": "r1", "query_id": "q1", "query_text": "ranking fusion",
            "scope": SCOPE, "index_profile": PROFILE,
            "lexical_profile": {"name": "bm25-v1", "version": "0.1"},
            "index_generation": "g1", "limit": 10,
        })
        self.assertEqual([c["chunk_id"] for c in result["candidates"]], ["chunk-a"])
        self.assertEqual(calls[1][1]["text"], "ranking fusion")
        self.assertEqual(calls[2][1]["terms"], ["ranking", "fusion"])

    def test_vector_service_generates_query_embedding_and_pins_generation(self):
        def resolve(req):
            return {"profile_bundle": {
                "name": "default", "version": "0.1", "digest": "a" * 64,
                "embedding": {"profile": "technical-default", "version": "0.1", "metric": "cosine", "model": "local-nomic", "model_version": "r1", "dimensions": 3},
            }}
        def embed(req):
            return {
                "index_profile": PROFILE, "profile": "technical-default", "profile_version": "0.1",
                "model": {"model_id": "local-nomic", "model_version": "r1", "dimensions": 3},
                "results": [{"input_id": "q1", "status": "complete", "vector": [1.0, 0.0, 0.0]}],
            }
        def neighbors(req):
            self.assertEqual(req["index_generation"], "g1")
            self.assertEqual(req["input_type"], "query")
            return {"index_generation": "g1", "request_id": "r1", "truncated": False,
                    "candidates": [dict(CANDIDATE, similarity=0.9, embedding={"metric": "cosine"})]}
        service = VectorRetrievalService(embed, neighbors, resolve)
        result = service.search({
            "request_id": "r1", "query_id": "q1", "scope": SCOPE, "index_profile": PROFILE,
            "embedding_profile": {"name": "technical-default", "version": "0.1"},
            "index_generation": "g1", "limit": 5, "query": {"text": "ranking algorithm"},
        })
        self.assertEqual(result["metric"], "cosine")
        self.assertEqual(result["candidates"][0]["distance"], 0.9)
        self.assertEqual(result["candidates"][0]["retrieval_rank"], 1)
        self.assertNotIn("embedding", result["candidates"][0])


if __name__ == "__main__":
    unittest.main()
