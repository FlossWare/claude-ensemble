"""Unit and HTTP tests for the local CPU-only Reranking service."""
from __future__ import annotations

import json
import threading
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from runtime.reranking import (
    EXPECTED_MODEL_ID,
    RerankingEngine,
    RerankingError,
)
from runtime.server import BoundedThreadingHTTPServer, Handler


def candidate(suffix, *, exact=None, prior_rank=1):
    return {
        "source_id": f"knowledge:doc-{suffix}",
        "source_revision": "rev-1",
        "revision_sequence": 1,
        "chunk_id": f"chunk-{suffix}",
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "text": f"candidate text {suffix}",
        "prior_rank": prior_rank,
        "prior_score": 0.5,
        "matched_exact_identifiers": exact or [],
        "provenance": {"origin": "test"},
    }


class FakeCrossEncoder:
    def __init__(self, scores):
        self.scores = scores
        self.pairs = []
        self.kwargs = None

    def predict(self, pairs, **kwargs):
        self.pairs = pairs
        self.kwargs = kwargs
        return self.scores


class RerankingUnitTests(unittest.TestCase):
    def request(self, candidates, limit=2):
        return {
            "request_id": "rerank-test-1",
            "query": "How are source revisions indexed?",
            "profile": {"name": "default-reranker", "version": "0.1"},
            "candidates": candidates,
            "limit": limit,
        }

    def test_cross_encoder_scores_reorder_candidates_and_preserve_identity(self):
        model = FakeCrossEncoder([0.1, 0.9, 0.4])
        engine = RerankingEngine(model=model, model_id=EXPECTED_MODEL_ID, model_version="local-r1")
        inputs = [candidate("a", prior_rank=1), candidate("b", prior_rank=2), candidate("c", prior_rank=3)]
        result = engine.rerank(self.request(inputs, limit=2))
        self.assertEqual([x["chunk_id"] for x in result["candidates"]], ["chunk-b", "chunk-c"])
        self.assertEqual([x["rerank"] for x in result["candidates"]], [1, 2])
        self.assertEqual(result["candidates"][0]["score_semantics"], "cross-encoder-profile-score-v1")
        self.assertEqual(result["candidates"][0]["provenance"]["origin"], "test")
        self.assertEqual(model.pairs[0], ("How are source revisions indexed?", "candidate text a"))
        self.assertEqual(model.kwargs["batch_size"], 3)

    def test_exact_identifier_candidates_are_never_dropped_to_meet_limit(self):
        model = FakeCrossEncoder([0.1, 0.2, 0.99])
        engine = RerankingEngine(model=model, model_id=EXPECTED_MODEL_ID, model_version="local-r1")
        inputs = [
            candidate("a", exact=["RFC-123"], prior_rank=1),
            candidate("b", exact=["RFC-456"], prior_rank=2),
            candidate("c", prior_rank=3),
        ]
        result = engine.rerank(self.request(inputs, limit=1))
        self.assertEqual({x["chunk_id"] for x in result["candidates"]}, {"chunk-a", "chunk-b"})
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["candidates"][0]["matched_exact_identifiers"], ["RFC-456"])

    def test_duplicate_candidate_identity_is_rejected(self):
        engine = RerankingEngine(model=FakeCrossEncoder([0.1, 0.2]), model_id=EXPECTED_MODEL_ID, model_version="r1")
        item = candidate("a")
        with self.assertRaises(RerankingError):
            engine.rerank(self.request([item, dict(item)]))

    def test_non_finite_model_score_is_rejected(self):
        engine = RerankingEngine(model=FakeCrossEncoder([float("nan")]), model_id=EXPECTED_MODEL_ID, model_version="r1")
        with self.assertRaises(RerankingError):
            engine.rerank(self.request([candidate("a")]))

    def test_unknown_request_fields_are_rejected(self):
        engine = RerankingEngine(model=FakeCrossEncoder([0.1]), model_id=EXPECTED_MODEL_ID, model_version="r1")
        request = self.request([candidate("a")])
        request["model"] = "caller-selected-model"
        with self.assertRaises(RerankingError):
            engine.rerank(request)

    def test_versioned_evaluation_fixture_has_unique_candidates_and_relevant_ids(self):
        fixture_path = Path(__file__).resolve().parents[1] / "docs" / "evaluation" / "reranking-fixtures.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        chunk_ids = [item["chunk_id"] for item in fixture["candidates"]]
        self.assertEqual(len(chunk_ids), 20)
        self.assertEqual(len(set(chunk_ids)), 20)
        self.assertTrue(set(fixture["relevant_chunk_ids"]).issubset(set(chunk_ids)))
        self.assertEqual(sorted(item["prior_rank"] for item in fixture["candidates"]), list(range(1, 21)))

    def test_local_model_loader_is_cpu_only_and_offline(self):
        calls = {}
        class FakeCrossEncoderLoader:
            def __init__(self, path, **kwargs):
                calls["path"] = path
                calls.update(kwargs)
        import types
        from unittest.mock import patch
        import tempfile
        fake_package = types.SimpleNamespace(CrossEncoder=FakeCrossEncoderLoader)
        with tempfile.TemporaryDirectory() as model_dir, patch.dict("sys.modules", {"sentence_transformers": fake_package}):
            engine = RerankingEngine(model_path=model_dir, model_id=EXPECTED_MODEL_ID, model_version="pinned-r1")
            engine._load()
        self.assertEqual(calls["device"], "cpu")
        self.assertEqual(calls["max_length"], 512)
        self.assertIs(calls["local_files_only"], True)
        self.assertIs(calls["trust_remote_code"], False)


class RerankingHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def test_rerank_endpoint_returns_contract_response(self):
        engine = RerankingEngine(model=FakeCrossEncoder([0.8]), model_id=EXPECTED_MODEL_ID, model_version="r1")
        body = {
            "request_id": "http-rerank-1",
            "query": "revision indexing",
            "profile": {"name": "default-reranker", "version": "0.1"},
            "candidates": [candidate("http")],
            "limit": 1,
        }
        data = json.dumps(body).encode()
        request = Request(
            self.base + "/api/v1/reranking/rerank", data=data,
            headers={"Content-Type": "application/json", "X-CE-Request-ID": "http-rerank-1"},
            method="POST",
        )
        with patch("runtime.server.get_reranking_engine", return_value=engine):
            with urlopen(request, timeout=3) as response:
                payload = json.loads(response.read())
        self.assertEqual(payload["request_id"], "http-rerank-1")
        self.assertEqual(payload["candidates"][0]["chunk_id"], "chunk-http")

    def test_health_is_available_without_model_weights(self):
        request = Request(self.base + "/api/v1/reranking/health", method="GET")
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["service"], "reranking")
        self.assertEqual(payload["status"], "alive")


if __name__ == "__main__":
    unittest.main()
