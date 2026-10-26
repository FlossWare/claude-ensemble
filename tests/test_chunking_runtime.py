"""Contract, algorithm, and real-HTTP-boundary tests for Chunking."""
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from runtime.chunking import ChunkingError, Policy, chunk_document
from runtime.server import Handler

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/contracts/schemas/chunking.schema.json").read_text())
PROFILE = {"name": "default", "version": "0.1", "digest": "0123456789abcdef" * 4}
POLICY_DICT = {"profile": "plain-text-default", "profile_version": "0.1", "max_units": 12,
               "overlap_units": 2, "unit": "unicode_code_points"}
POLICY = Policy.from_dict(POLICY_DICT)


def chunk(content="hello world", **overrides):
    args = dict(source_id="knowledge:source01", revision="r1", revision_sequence=1,
                content=content, index_profile=PROFILE, policy=POLICY)
    args.update(overrides)
    return chunk_document(**args)


def request_body(**overrides):
    body = {
        "index_profile": PROFILE,
        "source": {"source_id": "knowledge:source01", "revision": "r1",
                   "revision_sequence": 1, "media_type": "text/plain", "content": "hello world"},
        "policy": dict(POLICY_DICT),
    }
    body.update(overrides)
    return body


def profile_bundle():
    return {
        "name": PROFILE["name"], "version": PROFILE["version"], "status": "active",
        "chunking": {"profile": "plain-text-default", "version": "0.1", "max_units": 12},
        "tokenization": {"profile": "default", "version": "0.1"},
        "lexical": {"profile": "default", "version": "0.1", "statistics_policy": "scope_partition"},
        "embedding": {"required": False, "profile": "default", "version": "0.1", "model": "none",
                      "model_version": "none", "input_types": ["document"], "dimensions": 1,
                      "normalization": "none", "metric": "cosine", "max_input_tokens": 1000},
        "limits": {"max_chunks": 1, "max_source_bytes": 1000, "max_chunk_text_bytes": 64,
                   "max_request_bytes": 8192, "max_chunk_representation_bytes": 4096,
                   "max_envelope_bytes": 1024, "max_metadata_bytes": 0,
                   "max_lexical_terms_per_chunk": 10, "max_lexical_term_bytes": 32},
        "digest": PROFILE["digest"],
    }


class ChunkingAlgorithmTests(unittest.TestCase):
    def test_repeatability_and_stable_ids(self):
        self.assertEqual(chunk("same input"), chunk("same input"))
        self.assertEqual([c["chunk_id"] for c in chunk("same input")["chunks"]],
                         [c["chunk_id"] for c in chunk("same input")["chunks"]])

    def test_revision_and_policy_change_identity(self):
        base = chunk()["chunks"][0]["chunk_id"]
        self.assertNotEqual(base, chunk(revision="r2")["chunks"][0]["chunk_id"])
        self.assertNotEqual(base, chunk(policy=Policy("other", "2", 12, 2))["chunks"][0]["chunk_id"])

    def test_unicode_offsets_are_code_points(self):
        content = "a🙂é漢字\nnext"
        result = chunk(content, policy=Policy("p", "1", 5, 0))
        for item in result["chunks"]:
            self.assertEqual(content[item["start_offset"]:item["end_offset"]], item["text"])
            self.assertLessEqual(item["end_offset"] - item["start_offset"], 5)

    def test_overlap_and_contiguous_ordinals(self):
        content = "abcdefghijklmnopqrstuvwx"
        chunks = chunk(content, policy=Policy("p", "1", 8, 2))["chunks"]
        self.assertEqual([c["ordinal"] for c in chunks], list(range(len(chunks))))
        for left, right in zip(chunks, chunks[1:]):
            self.assertEqual(left["end_offset"] - right["start_offset"], 2)

    def test_markdown_heading_context_and_lines(self):
        content = "# Root\n## Child\nalpha beta gamma"
        result = chunk(content, policy=Policy("md", "1", 10, 0))["chunks"]
        self.assertTrue(any(c["heading_path"] == ["Root", "Child"] for c in result))
        self.assertTrue(all(c["start_line"] <= c["end_line"] for c in result))

    def test_empty_and_oversized_content_rejected(self):
        with self.assertRaises(ChunkingError):
            chunk("")
        with self.assertRaises(ChunkingError):
            chunk("é" * 140_000)

    def test_invalid_policy_rejected(self):
        for policy in (
            {"profile": "p", "profile_version": "1", "max_units": True, "overlap_units": 0, "unit": "unicode_code_points"},
            {"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 2, "unit": "unicode_code_points"},
            {"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 0, "unit": "bytes"},
            {"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 0, "unit": "unicode_code_points", "surprise": True},
        ):
            with self.subTest(policy=policy), self.assertRaises(ChunkingError):
                Policy.from_dict(policy)

    def test_fresh_process_determinism(self):
        script = ("import json; from runtime.chunking import *; "
                  "p=Policy('p','1',8,1); "
                  "print(json.dumps(chunk_document(source_id='knowledge:source01',revision='r1',revision_sequence=1,content='abcdefghijk',index_profile="
                  + repr(PROFILE) + ",policy=p),sort_keys=True))")
        outputs = [subprocess.check_output([sys.executable, "-c", script], text=True) for _ in range(2)]
        self.assertEqual(outputs[0], outputs[1])


class ChunkingHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def post(self, path="/api/v1/chunking/chunks", body=None, headers=None, raw=None):
        data = raw if raw is not None else json.dumps(body).encode("utf-8")
        request = Request(self.base + path, data=data,
                          headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.headers, json.load(response)
        except HTTPError as exc:
            return exc.code, exc.headers, json.loads(exc.read())

    def assert_error_schema(self, payload):
        Draft202012Validator(SCHEMA["$defs"]["errorResponse"]).validate(payload)
        self.assertEqual(payload["request_id"], payload["error"].get("request_id", payload["request_id"]))

    def test_health_and_readiness_match_contract(self):
        for path, definition in (("/api/v1/chunking/health", "healthResponse"),
                                 ("/api/v1/chunking/ready", "readinessResponse")):
            with urlopen(self.base + path) as response:
                result = json.load(response)
                self.assertEqual(response.headers["X-CE-Request-ID"], result["request_id"])
                Draft202012Validator(SCHEMA["$defs"][definition]).validate(result)

    def test_success_matches_schema_and_propagates_request_id(self):
        status, headers, result = self.post(body=request_body(), headers={"X-CE-Request-ID": "test-request-01"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-CE-Request-ID"], "test-request-01")
        self.assertEqual(result["request_id"], "test-request-01")
        Draft202012Validator(SCHEMA["$defs"]["chunkResponse"]).validate(result)

    def test_include_text_false_is_honored(self):
        body = request_body(options={"include_text": False})
        status, _, result = self.post(body=body)
        self.assertEqual(status, 200)
        self.assertNotIn("text", result["chunks"][0])
        Draft202012Validator(SCHEMA["$defs"]["chunkResponse"]).validate(result)

    def test_unknown_fields_and_missing_fields_rejected(self):
        bad_unknown = request_body()
        bad_unknown["surprise"] = True
        bad_missing = request_body()
        del bad_missing["source"]["content"]
        for body in (bad_unknown, bad_missing):
            status, _, result = self.post(body=body)
            self.assertEqual(status, 400)
            self.assert_error_schema(result)

    def test_bad_option_type_rejected(self):
        status, _, result = self.post(body=request_body(options={"include_text": "false"}))
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")
        self.assert_error_schema(result)

    def test_malformed_json_and_unsupported_media_type(self):
        status, _, result = self.post(raw=b"{")
        self.assertEqual(status, 400)
        self.assert_error_schema(result)
        status, _, result = self.post(body=request_body(), headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        self.assertEqual(result["error"]["code"], "unsupported_media_type")
        self.assert_error_schema(result)

    def test_invalid_request_id_is_not_silently_accepted(self):
        status, headers, result = self.post(body=request_body(), headers={"X-CE-Request-ID": "bad id"})
        self.assertEqual(status, 400)
        self.assertNotEqual(headers["X-CE-Request-ID"], "bad id")
        self.assertEqual(result["request_id"], headers["X-CE-Request-ID"])
        self.assert_error_schema(result)

    def test_invalid_policy_returns_contract_error(self):
        body = request_body()
        body["policy"]["overlap_units"] = body["policy"]["max_units"]
        status, _, result = self.post(body=body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")
        self.assert_error_schema(result)

    def test_unknown_profile_and_version_are_rejected(self):
        for profile, version in (("missing-profile", "0.1"), ("plain-text-default", "9.9")):
            body = request_body()
            body["policy"]["profile"] = profile
            body["policy"]["profile_version"] = version
            status, _, result = self.post(body=body)
            self.assertEqual(status, 422)
            self.assertEqual(result["error"]["code"], "unsupported_profile")
            self.assert_error_schema(result)

    def test_oversized_http_body_is_rejected_before_json_parsing(self):
        status, _, result = self.post(raw=b"x" * 300_001)
        self.assertEqual(status, 413)
        self.assertEqual(result["error"]["code"], "request_too_large")
        self.assert_error_schema(result)

    def test_preflight_matches_schema_and_checks_profile_identity(self):
        bundle = profile_bundle()
        body = {"index_profile": PROFILE, "source_text": "hello world",
                "chunking_profile": {"profile": "plain-text-default", "version": "0.1",
                                     "max_units": 12, "overlap_units": 2},
                "profile_bundle": bundle}
        status, headers, result = self.post("/api/v1/chunking/preflight", body,
                                            {"X-CE-Request-ID": "preflight-1"})
        self.assertEqual(status, 200)
        self.assertTrue(result["fits_profile"])
        self.assertEqual(result["request_id"], headers["X-CE-Request-ID"])
        Draft202012Validator(SCHEMA["$defs"]["preflightResponse"]).validate(result)
        body["chunking_profile"]["version"] = "99"
        status, _, error = self.post("/api/v1/chunking/preflight", body)
        self.assertEqual(status, 409)
        self.assertEqual(error["error"]["code"], "profile_mismatch")
        self.assert_error_schema(error)

    def test_preflight_reports_profile_limit_without_materializing_all_chunks(self):
        bundle = profile_bundle()
        bundle["limits"]["max_chunks"] = 2
        body = {"index_profile": PROFILE, "source_text": "abcdefghijklmnop",
                "chunking_profile": {"profile": "plain-text-default", "version": "0.1",
                                     "max_units": 4, "overlap_units": 0},
                "profile_bundle": bundle}
        bundle["chunking"]["max_units"] = 4
        status, _, result = self.post("/api/v1/chunking/preflight", body)
        self.assertEqual(status, 200)
        self.assertFalse(result["fits_profile"])
        self.assertGreater(result["chunk_count"], bundle["limits"]["max_chunks"])
        Draft202012Validator(SCHEMA["$defs"]["preflightResponse"]).validate(result)

    def test_unknown_endpoint_uses_shared_error_envelope(self):
        status, _, result = self.post("/api/v1/chunking/unknown", body={})
        self.assertEqual(status, 404)
        self.assertEqual(result["error"]["code"], "endpoint_not_found")
        self.assert_error_schema(result)


if __name__ == "__main__":
    unittest.main()
