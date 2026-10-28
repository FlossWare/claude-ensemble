"""Contract and HTTP tests for local entity/identifier extraction."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from jsonschema import Draft202012Validator

from runtime.entity_extraction import (
    PROFILE_NAME, PROFILE_VERSION, EntityExtractionError, EntityExtractor, get_extractor,
)
from runtime.server import BoundedThreadingHTTPServer, Handler

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/contracts/schemas/entity-extraction.schema.json").read_text())


class FakeNlp:
    def __call__(self, text):
        entities = []
        for phrase, label in (("Alice", "PERSON"), ("Acme Corp", "ORG")):
            start = text.find(phrase)
            if start >= 0:
                entities.append(SimpleNamespace(
                    start_char=start, end_char=start + len(phrase), label_=label,
                ))
        return SimpleNamespace(ents=entities)


class EntityUnitTests(unittest.TestCase):
    def setUp(self):
        self.extractor = EntityExtractor(ner_model_path="")

    def test_file_paths_issue_ids_versions_and_technical_identifiers_preserve_spans(self):
        text = "😀 Review docs/contracts/INDEX.md and issue #17; version v1.2.3 uses EmbeddingService HTTP2."
        entities = self.extractor.extract(text)
        by_kind = {}
        for entity in entities:
            by_kind.setdefault(entity["kind"], []).append(entity)
            self.assertEqual(text[entity["start_offset"]:entity["end_offset"]], entity["text"])
        path = next(item for item in by_kind["file_path"] if item["text"] == "docs/contracts/INDEX.md")
        self.assertEqual(path["start_offset"], text.index("docs/contracts/INDEX.md"))
        issue = next(item for item in by_kind["issue_identifier"] if item["text"] == "issue #17")
        self.assertEqual(issue["normalized"], "17")
        version = next(item for item in by_kind["version"] if item["text"] == "v1.2.3")
        self.assertEqual(version["normalized"], "v1.2.3")
        identifiers = {item["text"] for item in by_kind["technical_identifier"]}
        self.assertIn("EmbeddingService", identifiers)
        self.assertIn("HTTP2", identifiers)

    def test_url_trailing_punctuation_is_not_part_of_span(self):
        text = "Read https://example.test/path?q=1."
        entities = self.extractor.extract(text)
        url = next(item for item in entities if item["kind"] == "url")
        self.assertEqual(url["text"], "https://example.test/path?q=1")
        self.assertEqual(text[url["start_offset"]:url["end_offset"]], url["text"])

    def test_known_aliases_resolve_to_canonical_project_name(self):
        text = "CE uses claude-ensemble."
        entities = self.extractor.extract(text)
        aliases = [item for item in entities if item["kind"] == "project"]
        self.assertEqual([item["text"] for item in aliases], ["CE", "claude-ensemble"])
        self.assertTrue(all(item["normalized"] == "Claude Ensemble" for item in aliases))
        self.assertTrue(all(item["exact"] is False for item in aliases))

    def test_local_ner_worker_adds_inferred_people_and_organizations(self):
        extractor = EntityExtractor(ner_model_path="", nlp=FakeNlp())
        text = "Alice works at Acme Corp."
        entities = extractor.extract(text)
        self.assertEqual([(item["kind"], item["text"]) for item in entities],
                         [("person", "Alice"), ("organization", "Acme Corp")])
        self.assertTrue(all(item["exact"] is False for item in entities))
        self.assertTrue(all(item["confidence"] == 0.5 for item in entities))

    def test_exact_path_wins_over_overlapping_inferred_entity(self):
        class OverlapNlp:
            def __call__(self, text):
                start = text.index("docs/contracts/INDEX.md")
                return SimpleNamespace(ents=[SimpleNamespace(
                    start_char=start, end_char=start + len("docs/contracts/INDEX.md"), label_="ORG",
                )])
        text = "Open docs/contracts/INDEX.md"
        entities = EntityExtractor(ner_model_path="", nlp=OverlapNlp()).extract(text)
        overlapping = [item for item in entities if item["text"] == "docs/contracts/INDEX.md"]
        self.assertEqual(len(overlapping), 1)
        self.assertEqual(overlapping[0]["kind"], "file_path")
        self.assertTrue(overlapping[0]["exact"])

    def test_unconfigured_ner_is_degraded_but_exact_workers_remain_ready(self):
        readiness = self.extractor.readiness()
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["status"], "degraded")
        self.assertEqual(self.extractor.extract(""), [])

    def test_configured_missing_model_reports_not_ready(self):
        with tempfile.TemporaryDirectory() as parent:
            missing = str(Path(parent) / "missing-model")
            extractor = EntityExtractor(ner_model_path=missing)
            readiness = extractor.readiness()
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["status"], "not_ready")

    def test_oversized_input_is_rejected(self):
        with self.assertRaises(EntityExtractionError) as caught:
            self.extractor.extract("x" * 262_145)
        self.assertEqual(caught.exception.code, "source_too_large")
        self.assertEqual(caught.exception.status, 413)

    def test_output_matches_schema(self):
        result = {
            "profile": {"name": PROFILE_NAME, "version": PROFILE_VERSION},
            "entities": self.extractor.extract("Review docs/contracts/INDEX.md and issue #1"),
            "request_id": "entity-test-1",
        }
        Draft202012Validator(SCHEMA).validate(result)


class EntityHttpTests(unittest.TestCase):
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
        headers = {"X-CE-Request-ID": "entity-http-test"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=headers, method=method)
        with patch("runtime.server.get_entity_extractor", return_value=EntityExtractor(ner_model_path="")):
            try:
                with urlopen(req, timeout=3) as response:
                    return response.status, response.headers, json.load(response)
            except HTTPError as error:
                return error.code, error.headers, json.load(error)

    def body(self, **overrides):
        value = {
            "request_id": "entity-body-request",
            "text": "Open docs/contracts/INDEX.md and issue #17",
            "profile": {"name": PROFILE_NAME, "version": PROFILE_VERSION},
        }
        value.update(overrides)
        return value

    def test_extract_endpoint_and_health_routes(self):
        status, headers, result = self.call("POST", "/api/v1/entity-extraction/extract", self.body())
        self.assertEqual(status, 200)
        self.assertEqual(result["request_id"], "entity-http-test")
        self.assertEqual(headers["X-CE-Request-ID"], "entity-http-test")
        Draft202012Validator(SCHEMA).validate(result)
        status, _, health = self.call("GET", "/api/v1/entity-extraction/health")
        self.assertEqual(status, 200)
        self.assertEqual((health["service"], health["status"]), ("entity-extraction", "alive"))
        status, _, ready = self.call("GET", "/api/v1/entity-extraction/ready")
        self.assertEqual(status, 200)
        self.assertTrue(ready["ready"])

    def test_unsupported_profile_uses_common_error_envelope(self):
        status, _, result = self.call("POST", "/api/v1/entity-extraction/extract",
                                      self.body(profile={"name": "other", "version": "0.1"}))
        self.assertEqual(status, 422)
        self.assertEqual(result["error"]["code"], "unsupported_profile")
        Draft202012Validator(SCHEMA).validate(result)


if __name__ == "__main__":
    unittest.main()
