"""Contract and HTTP tests for the local CPU-only Embedding service."""
import json
import os
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from runtime.embedding import EmbeddingEngine, PROFILE_NAME, PROFILE_VERSION
from runtime.server import BoundedThreadingHTTPServer, Handler

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/contracts/schemas/embedding.schema.json").read_text())
INDEX_PROFILE = {
    "name": "default",
    "version": "0.1",
    "digest": "0123456789abcdef" * 4,
}


class FakeModel:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts, **kwargs):
        if any("raise-inference-error" in text for text in texts):
            raise RuntimeError("deliberately private test error")
        return [[1.0, 2.0, 2.0] if "bad-dimension" not in text else [1.0, 2.0] for text in texts]


class EmbeddingUnitTests(unittest.TestCase):
    def test_cpu_engine_normalizes_vectors_and_preserves_input_identity(self):
        engine = EmbeddingEngine(model=FakeModel(), model_id="test-model", model_version="test-v1")
        model, results = engine.embed([
            {"input_id": "q1", "input_type": "query", "text": "hello"},
            {"input_id": "d1", "input_type": "document", "text": "world"},
        ], "profile-default")
        self.assertEqual(model["provider"], "local")
        self.assertEqual(model["model_id"], "test-model")
        self.assertEqual(model["model_version"], "test-v1")
        self.assertEqual(model["dimensions"], 3)
        self.assertEqual(model["normalization"], "l2")
        self.assertEqual([result["input_id"] for result in results], ["q1", "d1"])
        self.assertAlmostEqual(results[0]["vector"][0], 1 / 3)
        self.assertAlmostEqual(sum(value * value for value in results[0]["vector"]), 1.0)
        self.assertTrue(all(result["status"] == "complete" for result in results))

    def test_invalid_dimensions_are_explicit_per_item_failures(self):
        engine = EmbeddingEngine(model=FakeModel(), model_id="test-model", model_version="test-v1")
        _, results = engine.embed([
            {"input_id": "good", "input_type": "query", "text": "hello"},
            {"input_id": "bad", "input_type": "document", "text": "bad-dimension"},
        ], "none")
        self.assertEqual(results[0]["status"], "complete")
        self.assertEqual(results[1]["status"], "failed")
        self.assertEqual(results[1]["error_code"], "invalid_model_vector")
        self.assertNotIn("vector", results[1])

    def test_inference_exception_is_returned_as_per_item_failure_without_exception_text(self):
        engine = EmbeddingEngine(model=FakeModel(), model_id="test-model", model_version="test-v1")
        _, results = engine.embed([
            {"input_id": "one", "input_type": "query", "text": "raise-inference-error"},
        ], "none")
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["error_code"], "model_inference_failed")

    def test_zero_vector_cannot_be_l2_normalized(self):
        class ZeroModel(FakeModel):
            def encode(self, texts, **kwargs):
                return [[0.0, 0.0, 0.0] for _ in texts]
        engine = EmbeddingEngine(model=ZeroModel(), model_id="zero", model_version="v1")
        _, results = engine.embed([
            {"input_id": "zero", "input_type": "query", "text": "zero"},
        ], "l2")
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["error_code"], "invalid_model_vector")

    def test_model_loader_forces_cpu_and_offline_local_only_mode(self):
        calls = {}
        class FakeSentenceTransformer:
            def __init__(self, path, **kwargs):
                calls["path"] = path
                calls.update(kwargs)
            def get_sentence_embedding_dimension(self):
                return 768
        fake_package = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
        with tempfile.TemporaryDirectory() as model_dir, patch.dict("sys.modules", {"sentence_transformers": fake_package}):
            engine = EmbeddingEngine(model_path=model_dir, model_id="nomic-ai/nomic-embed-text-v1.5", model_version="v1")
            engine.readiness()
        self.assertEqual(calls["device"], "cpu")
        self.assertIs(calls["local_files_only"], True)
        self.assertIs(calls["trust_remote_code"], False)

    def test_default_model_location_uses_flossware_model_root(self):
        with patch.dict(os.environ, {"CE_EMBEDDING_MODEL_PATH": "", "CE_EMBEDDING_MODEL_ID": "", "CE_EMBEDDING_MODEL_VERSION": ""}):
            engine = EmbeddingEngine()
        self.assertEqual(
            Path(engine.model_path),
            Path.home() / ".FlossWare" / "models" / "nomic-embed-text-v1.5",
        )
        self.assertEqual(engine.model_id, "nomic-ai/nomic-embed-text-v1.5")
        self.assertIsNone(engine.model_version)

    def test_missing_model_fails_readiness_without_downloading(self):
        with patch.dict(os.environ, {"CE_EMBEDDING_MODEL_PATH": "", "CE_EMBEDDING_MODEL_VERSION": ""}):
            engine = EmbeddingEngine(model_path="", model_version="")
            readiness = engine.readiness()
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["status"], "not_ready")


class EmbeddingHttpTests(unittest.TestCase):
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

    def setUp(self):
        self.engine = EmbeddingEngine(model=FakeModel(), model_id="test-model", model_version="test-v1")

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"X-CE-Request-ID": "embedding-test-1"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path, data=data, headers=headers, method=method)
        with patch("runtime.server.get_embedding_engine", return_value=self.engine):
            try:
                with urlopen(request, timeout=3) as response:
                    return response.status, response.headers, json.load(response)
            except HTTPError as error:
                return error.code, error.headers, json.load(error)

    def body(self, **overrides):
        value = {
            "index_profile": dict(INDEX_PROFILE),
            "profile": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "inputs": [
                {"input_id": "query-1", "input_type": "query", "text": "find a thing"},
                {"input_id": "doc-1", "input_type": "document", "text": "a thing"},
            ],
        }
        value.update(overrides)
        return value

    def test_embedding_endpoint_returns_schema_valid_cpu_vectors(self):
        status, headers, result = self.request("POST", "/api/v1/embeddings", self.body())
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-CE-Request-ID"], "embedding-test-1")
        self.assertEqual(result["request_id"], "embedding-test-1")
        self.assertEqual(result["model"]["provider"], "local")
        self.assertEqual([item["input_id"] for item in result["results"]], ["query-1", "doc-1"])
        Draft202012Validator(SCHEMA["$defs"]["response"]).validate(result)

    def test_unknown_profile_is_rejected(self):
        status, _, result = self.request("POST", "/api/v1/embeddings", self.body(profile="other"))
        self.assertEqual(status, 422)
        self.assertEqual(result["error"]["code"], "unsupported_profile")
        Draft202012Validator(SCHEMA["$defs"]["errorResponse"]).validate(result)

    def test_duplicate_input_ids_are_rejected(self):
        body = self.body(inputs=[
            {"input_id": "same", "input_type": "query", "text": "one"},
            {"input_id": "same", "input_type": "document", "text": "two"},
        ])
        status, _, result = self.request("POST", "/api/v1/embeddings", body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")

    def test_invalid_input_type_is_rejected_as_400_not_internal_error(self):
        status, _, result = self.request("POST", "/api/v1/embeddings", self.body(inputs=[
            {"input_id": "one", "input_type": [], "text": "hello"},
        ]))
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")

    def test_batch_limit_and_empty_batch_are_rejected(self):
        for inputs in ([], [
            {"input_id": str(i), "input_type": "query", "text": "x"} for i in range(65)
        ]):
            with self.subTest(count=len(inputs)):
                status, _, result = self.request("POST", "/api/v1/embeddings", self.body(inputs=inputs))
                self.assertEqual(status, 400)
                self.assertEqual(result["error"]["code"], "invalid_parameter")

    def test_per_item_invalid_vector_is_explicit_and_schema_valid(self):
        status, _, result = self.request("POST", "/api/v1/embeddings", self.body(inputs=[
            {"input_id": "bad", "input_type": "query", "text": "bad-dimension"},
        ]))
        self.assertEqual(status, 200)
        self.assertEqual(result["results"][0]["status"], "failed")
        self.assertEqual(result["results"][0]["error_code"], "invalid_model_vector")
        Draft202012Validator(SCHEMA["$defs"]["response"]).validate(result)

    def test_health_and_readiness_endpoints(self):
        status, _, health = self.request("GET", "/api/v1/embedding/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["service"], "embedding")
        self.assertEqual(health["status"], "alive")
        Draft202012Validator(SCHEMA["$defs"]["healthResponse"]).validate(health)
        status, _, ready = self.request("GET", "/api/v1/embedding/ready")
        self.assertEqual(status, 200)
        self.assertTrue(ready["ready"])
        Draft202012Validator(SCHEMA["$defs"]["readinessResponse"]).validate(ready)


if __name__ == "__main__":
    unittest.main()
