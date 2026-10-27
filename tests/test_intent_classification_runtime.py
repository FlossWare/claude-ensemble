"""Contract and HTTP tests for the deterministic Intent Classification service."""
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from runtime.intent_classification import INTENTS, PROFILE_NAME, PROFILE_VERSION, IntentClassificationError, classify
from runtime.server import BoundedThreadingHTTPServer, Handler

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/contracts/schemas/intent-classification.schema.json").read_text())


def request(text, allowed=None, profile=None):
    return {
        "request_id": "intent-test-1",
        "text": text,
        "profile": profile or {"name": PROFILE_NAME, "version": PROFILE_VERSION},
        "allowed_intents": list(allowed or INTENTS),
    }


class IntentUnitTests(unittest.TestCase):
    def test_memory_recall_intent(self):
        result = classify(request("What did we decide last time about embedding?"))
        self.assertEqual(result["results"][0]["intent"], "memory_recall")
        self.assertGreaterEqual(result["results"][0]["confidence"], 0.8)
        self.assertFalse(result["uncertain"])

    def test_troubleshooting_intent(self):
        result = classify(request("Fix the HTTP 503 error when the service crashes"))
        self.assertEqual(result["results"][0]["intent"], "troubleshooting")
        self.assertTrue(any(item["kind"] == "keyword-rule:troubleshooting" for item in result["evidence"]))

    def test_decision_support_intent(self):
        result = classify(request("Compare these options and recommend the best one"))
        self.assertEqual(result["results"][0]["intent"], "decision_support")

    def test_ambiguous_input_marks_uncertainty(self):
        result = classify(request("What is the best way to fix this?"))
        self.assertTrue(result["uncertain"])
        self.assertIn(result["results"][0]["intent"], INTENTS)

    def test_unmatched_input_falls_back_to_general(self):
        result = classify(request("The sky is blue."))
        self.assertEqual(result["results"][0]["intent"], "general")
        self.assertTrue(result["uncertain"])
        self.assertEqual(result["results"][0]["confidence"], 0.35)

    def test_allowed_intents_constrain_result(self):
        result = classify(request("Why is this broken?", allowed=["knowledge_lookup", "general"]))
        self.assertEqual(result["results"][0]["intent"], "general")
        self.assertTrue(result["uncertain"])

    def test_no_allowed_rule_uses_safe_allowed_fallback(self):
        result = classify(request("The sky is blue.", allowed=["explanation", "decision_support"]))
        self.assertEqual(result["results"][0]["intent"], "explanation")
        self.assertTrue(result["uncertain"])
        self.assertEqual(result["results"][0]["confidence"], 0.25)

    def test_unsupported_profile_is_rejected(self):
        with self.assertRaises(IntentClassificationError) as caught:
            classify(request("Explain this", profile={"name": "other", "version": "0.1"}))
        self.assertEqual(caught.exception.code, "unsupported_profile")
        self.assertEqual(caught.exception.status, 422)

    def test_invalid_allowed_intents_are_rejected(self):
        for labels in ([], ["general", "general"], [["general"]], ["not-a-label"]):
            with self.subTest(labels=labels):
                with self.assertRaises(IntentClassificationError):
                    classify(request("Explain this", allowed=labels))

    def test_blank_and_oversized_text_are_rejected(self):
        with self.assertRaises(IntentClassificationError) as caught:
            classify(request("   "))
        self.assertEqual(caught.exception.code, "invalid_parameter")
        with self.assertRaises(IntentClassificationError) as caught:
            classify(request("x" * (262_144 + 1)))
        self.assertEqual(caught.exception.code, "source_too_large")
        self.assertEqual(caught.exception.status, 413)

    def test_response_matches_schema(self):
        result = classify(request("Explain why ranking is deterministic"))
        Draft202012Validator(SCHEMA).validate({**result, "request_id": "intent-test-1"})


class IntentHttpTests(unittest.TestCase):
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

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"X-CE-Request-ID": "intent-http-test"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, response.headers, json.load(response)
        except HTTPError as error:
            return error.code, error.headers, json.load(error)

    def test_classify_endpoint_and_health_routes(self):
        status, headers, result = self.call("POST", "/api/v1/intent-classification/classify",
                                            request("What did we decide previously?"))
        self.assertEqual(status, 200)
        self.assertEqual(result["request_id"], "intent-http-test")
        self.assertEqual(headers["X-CE-Request-ID"], "intent-http-test")
        self.assertEqual(result["results"][0]["intent"], "memory_recall")
        Draft202012Validator(SCHEMA).validate(result)
        status, _, health = self.call("GET", "/api/v1/intent-classification/health")
        self.assertEqual(status, 200)
        self.assertEqual((health["service"], health["status"]), ("intent-classification", "alive"))
        status, _, ready = self.call("GET", "/api/v1/intent-classification/ready")
        self.assertEqual(status, 200)
        self.assertTrue(ready["ready"])

    def test_invalid_request_uses_common_error_envelope(self):
        body = request("Explain this")
        body["allowed_intents"] = []
        status, _, result = self.call("POST", "/api/v1/intent-classification/classify", body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")
        Draft202012Validator(SCHEMA).validate(result)


if __name__ == "__main__":
    unittest.main()
