"""Runtime and deterministic behavior tests for Chunking."""
import json
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runtime.chunking import ChunkingError, Policy, chunk_document
from runtime.server import Handler

PROFILE = {"name": "default", "version": "0.1", "digest": "0123456789abcdef" * 4}
POLICY = Policy.from_dict({"profile": "plain-text-default", "profile_version": "0.1", "max_units": 12, "overlap_units": 2, "unit": "unicode_code_points"})


def chunk(content="hello world", **overrides):
    args = dict(source_id="knowledge:source01", revision="r1", revision_sequence=1,
                content=content, index_profile=PROFILE, policy=POLICY)
    args.update(overrides)
    return chunk_document(**args)


class ChunkingAlgorithmTests(unittest.TestCase):
    def test_repeatability_and_stable_ids(self):
        self.assertEqual(chunk("same input"), chunk("same input"))
        self.assertEqual([c["chunk_id"] for c in chunk("same input")["chunks"]],
                         [c["chunk_id"] for c in chunk("same input")["chunks"]])

    def test_revision_changes_identity(self):
        self.assertNotEqual(chunk()["chunks"][0]["chunk_id"], chunk(revision="r2")["chunks"][0]["chunk_id"])

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

    def test_empty_input_has_no_chunks(self):
        self.assertEqual(chunk("")["chunks"], [])

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ChunkingError):
            Policy.from_dict({"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 2, "unit": "unicode_code_points"})

    def test_content_byte_limit(self):
        with self.assertRaises(ChunkingError):
            chunk("é" * 140_000)

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

    def test_health_and_readiness(self):
        for path, expected in (("/api/v1/chunking/health", "ok"), ("/api/v1/chunking/ready", "ready")):
            with urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response)["status"], expected)

    def test_chunk_endpoint_and_request_id_propagation(self):
        body = {"index_profile": PROFILE, "source": {"source_id": "knowledge:source01", "revision": "r1", "revision_sequence": 1, "content": "hello world"}, "policy": {"profile": "p", "profile_version": "1", "max_units": 8, "overlap_units": 1, "unit": "unicode_code_points"}}
        request = Request(self.base + "/api/v1/chunking/chunks", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-CE-Request-ID": "test-request-01"}, method="POST")
        with urlopen(request) as response:
            result = json.load(response)
            self.assertEqual(response.headers["X-CE-Request-ID"], "test-request-01")
            self.assertEqual(result["request_id"], "test-request-01")
            self.assertTrue(result["chunks"])

    def test_invalid_policy_returns_client_error(self):
        body = {"index_profile": PROFILE, "source": {"source_id": "knowledge:source01", "revision": "r1", "revision_sequence": 1, "content": "hello"}, "policy": {"profile": "p", "profile_version": "1", "max_units": 1, "overlap_units": 1, "unit": "unicode_code_points"}}
        request = Request(self.base + "/api/v1/chunking/chunks", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 422)


if __name__ == "__main__":
    unittest.main()
