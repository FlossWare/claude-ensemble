"""Regression tests for Nomic task-prefix behavior in the embedding profile."""
import unittest

from runtime.embedding import EmbeddingEngine


class CapturingModel:
    def __init__(self):
        self.seen = []

    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts, **kwargs):
        self.seen.extend(texts)
        return [[1.0, 2.0, 2.0] for _ in texts]


class NomicPrefixTests(unittest.TestCase):
    def test_query_and_document_receive_distinct_nomic_prefixes(self):
        model = CapturingModel()
        engine = EmbeddingEngine(model=model, model_id="nomic-ai/nomic-embed-text-v1.5", model_version="test")
        _, results = engine.embed([
            {"input_id": "q", "input_type": "query", "text": "How does ranking work?"},
            {"input_id": "d", "input_type": "document", "text": "Ranking combines candidates."},
        ], "none")
        self.assertEqual(model.seen, [
            "search_query: How does ranking work?",
            "search_document: Ranking combines candidates.",
        ])
        self.assertEqual([item["status"] for item in results], ["complete", "complete"])

    def test_prefix_is_applied_to_raw_input_exactly_once_by_the_service(self):
        model = CapturingModel()
        engine = EmbeddingEngine(model=model, model_id="nomic-ai/nomic-embed-text-v1.5", model_version="test")
        engine.embed([
            {"input_id": "q", "input_type": "query", "text": "search_query: already prefixed"},
        ], "none")
        self.assertEqual(model.seen, ["search_query: search_query: already prefixed"])


if __name__ == "__main__":
    unittest.main()
