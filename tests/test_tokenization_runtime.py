"""Regression tests for the canonical lexical Tokenization runtime."""
import json
import threading
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runtime.server import BoundedThreadingHTTPServer, Handler
from runtime.tokenization import (
    MAX_TEXT_BYTES,
    NORMALIZATION_VERSION,
    PROFILE_NAME,
    PROFILE_VERSION,
    TokenizationError,
    tokenize,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/contracts/schemas/tokenization.schema.json").read_text())

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

        fix = next(token for token in tokens if token["surface"] == "Fix")
        self.assertEqual(fix["kind"], "word")

        technical = tokenize("snake_case FOO_BAR HTTPServer URL myVariable")
        identifiers = [token for token in technical if token["kind"] == "identifier"]
        exact_terms = {token["term"] for token in identifiers}
        self.assertTrue({"snake_case", "FOO_BAR", "HTTPServer", "URL", "myVariable"} <= exact_terms)

    def test_unicode_normalization_case_punctuation_and_numbers(self):
        tokens = tokenize("CAFÉ Cafe\u0301, 42!")
        surfaces = [token["surface"] for token in tokens]
        terms = [token["term"] for token in tokens]
        self.assertIn("CAFÉ", surfaces)
        self.assertIn("Cafe\u0301", surfaces)
        self.assertIn("café", terms)
        self.assertIn("42", terms)
        self.assertIn(",", surfaces)
        self.assertIn("!", surfaces)

    def test_digit_bearing_identifiers_preserve_exact_terms_and_offsets(self):
        text = "HTTP2 sha256sum utf8 HTTP2Client version2Name ID42 A1B"
        tokens = tokenize(text)
        expected = ["HTTP2", "sha256sum", "utf8", "HTTP2Client", "version2Name", "ID42", "A1B"]
        for surface in expected:
            with self.subTest(surface=surface):
                exact = next(item for item in tokens if item["surface"] == surface and item["term"] == surface)
                self.assertEqual(exact["kind"], "identifier")
                self.assertEqual(text[exact["start_offset"]:exact["end_offset"]], surface)
                self.assertIn(surface.casefold(), [item["term"] for item in tokens if item["surface"] == surface])

    def test_number_punctuation_does_not_merge_comma_separated_values(self):
        tokens = tokenize("1,2 3,4")
        self.assertEqual([item["term"] for item in tokens if item["kind"] == "number"], ["1", "2", "3", "4"])
        self.assertEqual([item["surface"] for item in tokens if item["kind"] == "punctuation"], [",", ","])

    def test_acronyms_preserve_exact_and_normalized_terms(self):
        tokens = tokenize("NASA HTTP API")
        exact = {token["term"] for token in tokens if token["kind"] == "identifier"}
        self.assertTrue({"NASA", "HTTP", "API"}.issubset(exact))
        normalized = {token["term"] for token in tokens}
        self.assertTrue({"nasa", "http", "api"}.issubset(normalized))

    def test_offsets_are_half_open_unicode_code_point_offsets(self):
        tokens = tokenize("é FooBar")
        token = next(item for item in tokens if item["surface"] == "FooBar")
        self.assertEqual((token["start_offset"], token["end_offset"]), (2, 8))

    def test_options_are_applied_and_offsets_can_be_omitted(self):
        tokens = tokenize("FooBar", preserve_identifiers=False,
                          include_offsets=False, include_normalized_terms=False)
        self.assertEqual(tokens, [{"term": "FooBar", "surface": "FooBar", "kind": "word"}])
        self.assertNotIn("start_offset", tokens[0])
        self.assertNotIn("end_offset", tokens[0])

    def test_empty_input_is_valid(self):
        self.assertEqual(tokenize(""), [])

    def test_invalid_option_types_are_rejected(self):
        with self.assertRaises(TokenizationError) as caught:
            tokenize("hello", include_offsets=1)
        self.assertEqual(caught.exception.code, "invalid_parameter")

    def test_overlong_terms_and_surfaces_are_rejected_not_silently_dropped(self):
        for text, should_fail in (("x" * 128, False), ("x" * 129, True),
                                  ("x" * 512, True), ("x" * 513, True), ("ﬃ" * 43, True)):
            with self.subTest(length=len(text), should_fail=should_fail):
                if should_fail:
                    with self.assertRaises(TokenizationError) as caught:
                        tokenize(text)
                    self.assertEqual(caught.exception.code, "source_too_large")
                    self.assertEqual(caught.exception.status, 413)
                else:
                    self.assertTrue(tokenize(text))

    def test_token_count_is_bounded(self):
        with self.assertRaises(TokenizationError) as caught:
            tokenize("word " * 513)
        self.assertEqual(caught.exception.code, "source_too_large")

    def test_oversized_text_uses_payload_too_large_status(self):
        with self.assertRaises(TokenizationError) as caught:
            tokenize("x" * (MAX_TEXT_BYTES + 1))
        self.assertEqual(caught.exception.code, "source_too_large")
        self.assertEqual(caught.exception.status, 413)


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

    def assert_error_schema(self, payload, headers):
        Draft202012Validator(SCHEMA["$defs"]["errorResponse"]).validate(payload)
        self.assertEqual(payload["request_id"], headers["X-CE-Request-ID"])

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
        Draft202012Validator(SCHEMA).validate(body)

    def test_noncanonical_profile_or_version_is_rejected_without_fallback(self):
        for field, value in (("profile", "other-profile"), ("profile_version", "9.9")):
            with self.subTest(field=field):
                body = self.single_body()
                body[field] = value
                status, headers, result = self.request("POST", "/api/v1/tokenization/lexical", body)
                self.assertEqual(status, 422)
                self.assertEqual(result["error"]["code"], "unsupported_profile")
                self.assertEqual(headers["X-CE-Request-ID"], "tokenization-test-1")

    def test_single_endpoint_preserves_digit_bearing_identifiers(self):
        text = "HTTP2 sha256sum utf8 HTTP2Client version2Name ID42 A1B"
        status, _, body = self.request("POST", "/api/v1/tokenization/lexical", self.single_body(text))
        self.assertEqual(status, 200)
        for surface in text.split():
            exact = next(item for item in body["tokens"] if item["surface"] == surface and item["term"] == surface)
            self.assertEqual(text[exact["start_offset"]:exact["end_offset"]], surface)
        Draft202012Validator(SCHEMA).validate(body)

    def test_options_without_offsets_are_valid_over_http(self):
        body = self.single_body("HTTP2 foo")
        body["options"]["include_offsets"] = False
        body["options"]["include_normalized_terms"] = False
        status, _, result = self.request("POST", "/api/v1/tokenization/lexical", body)
        self.assertEqual(status, 200)
        self.assertTrue(all("start_offset" not in item and "end_offset" not in item for item in result["tokens"]))
        self.assertTrue(any(item["term"] == "HTTP2" for item in result["tokens"]))
        self.assertFalse(any(item["term"] == "http2" for item in result["tokens"]))
        Draft202012Validator(SCHEMA).validate(result)

    def test_invalid_body_request_id_is_rejected_for_single_and_batch(self):
        for value in (7, "", "x" * 129):
            for path, body in (
                ("/api/v1/tokenization/lexical", self.single_body()),
                ("/api/v1/tokenization/lexical/batch", {
                    "index_profile": dict(INDEX_PROFILE), "profile": PROFILE_NAME,
                    "profile_version": PROFILE_VERSION, "inputs": [{"input_id": "one", "text": "hello"}],
                }),
            ):
                with self.subTest(value=repr(value), path=path):
                    body["request_id"] = value
                    status, headers, result = self.request("POST", path, body)
                    self.assertEqual(status, 400)
                    self.assertEqual(result["error"]["code"], "invalid_parameter")
                    self.assert_error_schema(result, headers)

    def test_invalid_index_identity_is_rejected(self):
        body = self.single_body()
        body["index_profile"]["digest"] = "not-a-digest"
        status, headers, result = self.request("POST", "/api/v1/tokenization/lexical", body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")
        self.assert_error_schema(result, headers)

    def test_batch_correlates_each_result_by_input_id_and_keeps_item_errors_local(self):
        body = {
            "index_profile": dict(INDEX_PROFILE),
            "profile": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "inputs": [
                {"input_id": "valid", "text": "hello"},
                {"input_id": "digit-id", "text": "HTTP2 sha256sum utf8"},
                {"input_id": "too-many", "text": "word " * 513},
                {"input_id": "overlong-term", "text": "x" * 129},
            ],
        }
        status, _, result = self.request(
            "POST", "/api/v1/tokenization/lexical/batch", body
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["input_id"] for item in result["results"]], ["valid", "digit-id", "too-many", "overlong-term"])
        self.assertIn("tokens", result["results"][0])
        exact_digit_terms = {item["term"] for item in result["results"][1]["tokens"]}
        self.assertTrue({"HTTP2", "sha256sum", "utf8"} <= exact_digit_terms)
        self.assertEqual(result["results"][2]["error"]["code"], "source_too_large")
        self.assertEqual(result["results"][3]["error"]["code"], "source_too_large")
        Draft202012Validator(SCHEMA).validate(result)

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
        Draft202012Validator(SCHEMA).validate(health)
        status, _, ready = self.request("GET", "/api/v1/tokenization/ready")
        self.assertEqual(status, 200)
        self.assertTrue(ready["ready"])
        self.assertIn("technical-default@0.1", [item["name"] for item in ready["checks"]])
        Draft202012Validator(SCHEMA).validate(ready)


if __name__ == "__main__":
    unittest.main()
