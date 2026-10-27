"""Regression tests for the canonical lexical Tokenization runtime."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runtime.server import BoundedThreadingHTTPServer, Handler
from runtime.tokenization import (
    NORMALIZATION_VERSION,
    PROFILE_NAME,
    PROFILE_VERSION,
    TokenizationError,
    tokenize,
)

INDEX_PROFILE = {
    "name": "default",
    "version": "0.1",
    "digest": "0123456789abcdef" * 4,
}


class TokenizationUnitTests(unittest.TestCase):
    def test_technical_identifier_and_path_preserve_exact_and_normalized_terms(self):
        tokens = tokenize("Fix FooBarException in src/FooBar.java")
        identifiers = [token for token in tokens if token["kind"] == "identifier"]
        paths = [token for token in tokens if token["kind"] == "path"]
        self.assertTrue(any(token["term"] == "FooBarException" for token in identifiers))
        self.assertTrue(any(token["term"] == "foobarexception" for token in identifiers))
        self.assertTrue(any(token["term"] == "src/FooBar.java" for token in paths))
        self.assertTrue(any(token["term"] == "src/foobar.java" for token in paths))

    def test_offsets_are_half_open_unicode_code_point_offsets(self):
        tokens = tokenize("é FooBar")
        token = next(item for item in tokens if item["surface"] == "FooBar")
        self.assertEqual((token["start_offset"], token["end_offset"]), (2, 8))

    def test_options_are_applied_and_offsets_can_be_omitted(self):
        tokens = tokenize("FooBar", preserve_identifiers=False,
                          include_offsets=False, include_normalized_terms=False)
        self.assertEqual(tokens, [{"term": "FooBar", "surface": "FooBar", "kind": "word"}])

    def test_empty_input_is_valid(self):
        self.assertEqual(tokenize(""), [])

    def test_invalid_option_types_are_rejected(self):
        with self.assertRaises(TokenizationError) as caught:
            tokenize("hello", include_offsets=1)
        self.assertEqual(caught.exception.code, "invalid_parameter")

    def test_token_count_is_bounded(self):
        with self.assertRaises(TokenizationError) as caught:
            tokenize("word " * 513)
        self.assertEqual(caught.exception.code, "source_too_large")


class TokenizationHttpTests(unittest.TestCase):
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

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"X-CE-Request-ID": "tokenization-test-1"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.headers, json.load(response)
        except HTTPError as error:
            return error.code, error.headers, json.load(error)

    def single_body(self, text="Fix FooBarException"):
        return {
            "index_profile": dict(INDEX_PROFILE),
            "text": text,
            "profile": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "options": {
                "preserve_identifiers": True,
                "include_offsets": True,
                "include_normalized_terms": True,
            },
        }

    def test_single_endpoint_echoes_pinned_identity_and_profile(self):
        status, headers, body = self.request(
            "POST", "/api/v1/tokenization/lexical", self.single_body()
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["profile"], "technical-default")
        self.assertEqual(body["version"], "0.1")
        self.assertEqual(body["normalization_version"], NORMALIZATION_VERSION)
        self.assertEqual(body["index_profile"], INDEX_PROFILE)
        self.assertEqual(body["request_id"], "tokenization-test-1")
        self.assertEqual(headers["X-CE-Request-ID"], "tokenization-test-1")
        self.assertTrue(body["tokens"])

    def test_noncanonical_profile_is_rejected_without_fallback(self):
        body = self.single_body()
        body["profile"] = "other-profile"
        status, headers, result = self.request("POST", "/api/v1/tokenization/lexical", body)
        self.assertEqual(status, 422)
        self.assertEqual(result["error"]["code"], "unsupported_profile")
        self.assertEqual(headers["X-CE-Request-ID"], "tokenization-test-1")

    def test_invalid_index_identity_is_rejected(self):
        body = self.single_body()
        body["index_profile"]["digest"] = "not-a-digest"
        status, _, result = self.request("POST", "/api/v1/tokenization/lexical", body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")

    def test_batch_correlates_each_result_by_input_id_and_keeps_item_errors_local(self):
        body = {
            "index_profile": dict(INDEX_PROFILE),
            "profile": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "inputs": [
                {"input_id": "valid", "text": "hello"},
                {"input_id": "too-many", "text": "word " * 513},
            ],
        }
        status, _, result = self.request(
            "POST", "/api/v1/tokenization/lexical/batch", body
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["input_id"] for item in result["results"]], ["valid", "too-many"])
        self.assertIn("tokens", result["results"][0])
        self.assertEqual(result["results"][1]["error"]["code"], "source_too_large")

    def test_duplicate_batch_ids_are_rejected(self):
        body = {
            "index_profile": dict(INDEX_PROFILE),
            "profile": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "inputs": [
                {"input_id": "same", "text": "one"},
                {"input_id": "same", "text": "two"},
            ],
        }
        status, _, result = self.request(
            "POST", "/api/v1/tokenization/lexical/batch", body
        )
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")

    def test_health_and_readiness_endpoints(self):
        status, _, health = self.request("GET", "/api/v1/tokenization/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["service"], "tokenization")
        self.assertEqual(health["status"], "alive")
        status, _, ready = self.request("GET", "/api/v1/tokenization/ready")
        self.assertEqual(status, 200)
        self.assertTrue(ready["ready"])
        self.assertIn("technical-default@0.1", [item["name"] for item in ready["checks"]])


if __name__ == "__main__":
    unittest.main()
