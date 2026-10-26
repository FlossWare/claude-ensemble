"""Contract, algorithm, and real-HTTP-boundary tests for Chunking."""
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from runtime.chunking import DEFAULT_POLICY, MAX_CHUNKS, ChunkingError, Policy, chunk_document, chunk_spans
from runtime.server import BoundedThreadingHTTPServer, Handler, _profile_digest

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


def refresh_profile_digest(bundle):
    covered = {key: value for key, value in bundle.items() if key not in {"digest", "status"}}
    canonical = json.dumps(covered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    bundle["digest"] = hashlib.sha256(canonical).hexdigest()
    PROFILE["digest"] = bundle["digest"]
    return bundle


def profile_bundle():
    bundle = {
        "name": "default", "version": "0.1", "status": "active",
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
        "digest": "",
    }
    return refresh_profile_digest(bundle)


class ChunkingAlgorithmTests(unittest.TestCase):
    def test_repeatability_and_stable_ids(self):
        self.assertEqual(chunk("same input"), chunk("same input"))
        self.assertEqual([c["chunk_id"] for c in chunk("same input")["chunks"]],
                         [c["chunk_id"] for c in chunk("same input")["chunks"]])

    def test_chunk_spans_stops_when_deadline_check_expires(self):
        calls = 0

        def check_deadline():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ChunkingError("deadline_exceeded", "request deadline expired", status=504)

        with self.assertRaises(ChunkingError) as raised:
            chunk_spans("x" * 100, Policy("plain-text-default", "0.1", 10, 0),
                        deadline_check=check_deadline)
        self.assertEqual(raised.exception.code, "deadline_exceeded")
        self.assertEqual(calls, 3)

    def test_markdown_heading_scan_checks_deadline(self):
        from runtime.chunking import _heading_path
        calls = 0

        def check_deadline():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ChunkingError("deadline_exceeded", "request deadline expired", status=504)

        source = "# Root\n" + ("ordinary text\n" * 130) + "# Tail\nbody"
        with self.assertRaises(ChunkingError) as raised:
            _heading_path(source, len(source), deadline_check=check_deadline)
        self.assertEqual(raised.exception.code, "deadline_exceeded")
        self.assertEqual(calls, 2)

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
        result = chunk(content, policy=Policy("markdown-default", "0.1", 10, 0))["chunks"]
        content_start = content.index("alpha")
        body_chunks = [c for c in result if c["start_offset"] >= content_start]
        self.assertTrue(body_chunks)
        self.assertTrue(all(c["heading_path"] == ["Root", "Child"] for c in body_chunks))
        self.assertTrue(all(c["start_line"] <= c["end_line"] for c in result))

    def test_heading_provenance_ignores_atx_lines_inside_fenced_code(self):
        content = "# Real\n```python\n# not a heading\n```\n" + "body text " * 10
        result = chunk(content, policy=Policy("markdown-default", "0.1", 16, 0))["chunks"]
        body_chunks = [c for c in result if c["start_offset"] >= content.index("body")]
        self.assertTrue(body_chunks)
        self.assertTrue(all(c["heading_path"] == ["Real"] for c in body_chunks))

    def test_heading_provenance_uses_complete_ancestry(self):
        cases = [
            ("# Heading\nbody", 4, []),
            ("# Real\n    # code\nbody", len("# Real\n    # code\n"), ["Real"]),
            ("# Root\n### Deep\n#### Leaf\n### Peer\nbody", len("# Root\n### Deep\n#### Leaf\n### Peer\n"), ["Root", "Peer"]),
            ("# Root\n~~~md\n# fenced\n~~~\nbody", len("# Root\n~~~md\n# fenced\n~~~\n"), ["Root"]),
            ("# A literal#\nbody", len("# A literal#\n"), ["A literal#"]),
        ]
        from runtime.chunking import _heading_path
        for source, offset, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(_heading_path(source, offset), expected)

    def test_overlong_heading_is_not_emitted_as_provenance(self):
        from runtime.chunking import _heading_path
        source = "# " + ("x" * 1100) + "\nbody"
        self.assertEqual(_heading_path(source, len(source)), [])

    def test_omitted_replacement_heading_clears_stale_ancestry(self):
        from runtime.chunking import _heading_path
        cases = (
            ("# Old\n## Old child\n# " + ("x" * 1100) + "\nbody", []),
            ("# Old\n## Old child\n#\nbody", []),
            ("# Root\n## Old child\n## " + ("x" * 1100) + "\nbody", ["Root"]),
            ("# Root\n## Old child\n##\nbody", ["Root"]),
        )
        for source, expected in cases:
            with self.subTest(source=source[:40]):
                self.assertEqual(_heading_path(source, len(source)), expected)

    def test_omitted_replacement_heading_provenance_through_chunking(self):
        source = "# Old\n## Old child\n# " + ("x" * 1100) + "\nbody"
        result = chunk(source, policy=Policy("markdown-default", "0.1", 100, 0))
        self.assertEqual(result["chunks"][-1]["heading_path"], [])

    def test_empty_and_oversized_content_rejected(self):
        with self.assertRaises(ChunkingError):
            chunk("")
        with self.assertRaises(ChunkingError):
            chunk("é" * 140_000)

    def test_chunk_count_is_bounded(self):
        with self.assertRaises(ChunkingError) as caught:
            chunk("x" * 257, policy=Policy("plain-text-default", "0.1", 1, 0))
        self.assertEqual(caught.exception.code, "source_too_large")

    def test_adversarial_short_residual_fragments_preserve_bounds_and_coverage(self):
        cases = [
            ("a", 3, 2),
            ("ab", 3, 2),
            ("abc", 3, 2),
            ("abcd", 3, 2),
            ("abcdefg", 3, 2),
            ("\\n" * 19, 3, 2),
            ("\\n\\n\\n\\n\\n\\n\\n", 3, 2),
            ("a\\n\\nb\\n\\nc\\n", 3, 2),
            ("\n" * 19, 3, 2),
            ("\n\n\n\n\n\n\n", 3, 2),
            ("a\n\nb\n\nc\n", 3, 2),
            ("x" * 32, 3, 2),
        ]
        for text, max_units, overlap in cases:
            with self.subTest(text=repr(text), max_units=max_units, overlap=overlap):
                spans = chunk_spans(text, Policy("plain-text-default", "0.1", max_units, overlap))
                self.assertEqual(spans[0][0], 0)
                self.assertEqual(spans[-1][1], len(text))
                for start, end in spans:
                    self.assertLess(start, end)
                    self.assertLessEqual(end - start, max_units)
                for (left_start, left_end), (right_start, right_end) in zip(spans, spans[1:]):
                    self.assertGreater(right_start, left_start)
                    self.assertLessEqual(right_start, left_end)
                    self.assertEqual(left_end - right_start, min(overlap, left_end - left_start - 1))
                reconstructed = set()
                for start, end in spans:
                    reconstructed.update(range(start, end))
                self.assertEqual(reconstructed, set(range(len(text))))

    def test_preflight_hard_limit_is_global_chunk_limit(self):
        policy = Policy("plain-text-default", "0.1", 1, 0)
        with self.assertRaises(ChunkingError):
            chunk_spans("x" * (MAX_CHUNKS + 1), policy, max_chunks=MAX_CHUNKS)

    def test_configured_default_policy_is_explicit(self):
        self.assertEqual(DEFAULT_POLICY.profile, "markdown-default")
        self.assertEqual(DEFAULT_POLICY.profile_version, "0.1")
        self.assertGreater(DEFAULT_POLICY.max_units, DEFAULT_POLICY.overlap_units)

    def test_plain_text_does_not_claim_markdown_heading_context(self):
        result = chunk("# Not a parsed heading\\nbody", policy=Policy("plain-text-default", "0.1", 64, 0))
        self.assertEqual(result["chunks"][0]["heading_path"], [])

    def test_invalid_policy_rejected(self):
        for policy in (
            {"profile": "p", "profile_version": "1", "max_units": True, "overlap_units": 0, "unit": "unicode_code_points"},
            {"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 2, "unit": "unicode_code_points"},
            {"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 0, "unit": "bytes"},
            {"profile": "p", "profile_version": "1", "max_units": 2, "overlap_units": 0, "unit": "unicode_code_points", "surprise": True},
        ):
            with self.subTest(policy=policy), self.assertRaises(ChunkingError):
                Policy.from_dict(policy)

    def test_profile_digest_matches_independent_canonicalization_golden_vector(self):
        bundle = {
            "name": "café",
            "version": "1",
            "status": "active",
            "chunking": {"profile": "plain", "version": "0.1", "max_units": 8},
            "digest": "ignored",
        }
        # Fixed expected SHA-256 for sorted compact UTF-8 canonical bytes,
        # independent of the test fixture's digest-refresh helper.
        self.assertEqual(
            _profile_digest(bundle),
            "d1275710b5bcd4ccda890b8bda0c707b0a2e7bc9aa660777957552c3e7527f92",
        )

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
        cls.httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
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

    def assert_error_schema(self, payload, headers):
        Draft202012Validator(SCHEMA["$defs"]["errorResponse"]).validate(payload)
        self.assertIn("request_id", payload)
        self.assertEqual(payload["request_id"], headers["X-CE-Request-ID"])

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

    def test_omitted_policy_uses_documented_default(self):
        body = request_body()
        del body["policy"]
        status, headers, result = self.post(body=body)
        self.assertEqual(status, 200)
        self.assertEqual(result["chunker"], {"profile": DEFAULT_POLICY.profile, "version": DEFAULT_POLICY.profile_version})
        Draft202012Validator(SCHEMA["$defs"]["chunkResponse"]).validate(result)

    def test_concurrent_http_requests_keep_responses_isolated(self):
        def send(i):
            body = request_body()
            body["source"]["content"] = f"concurrent payload {i}"
            request_id = f"parallel-{i}"
            status, headers, result = self.post(body=body, headers={"X-CE-Request-ID": request_id})
            return status, headers.get("X-CE-Request-ID"), result

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(send, range(24)))
        self.assertEqual(len(results), 24)
        for i, (status, header_id, result) in enumerate(results):
            with self.subTest(request=i):
                self.assertEqual(status, 200)
                self.assertEqual(header_id, f"parallel-{i}")
                self.assertEqual(result["request_id"], f"parallel-{i}")
                expected = f"concurrent payload {i}"
                for item in result["chunks"]:
                    self.assertEqual(item["text"], expected[item["start_offset"]:item["end_offset"]])
                self.assertEqual(result["source_id"], "knowledge:source01")
                self.assertEqual(result["chunks"][0]["text"], expected[:result["chunks"][0]["end_offset"]])

    def test_include_text_false_is_honored(self):
        body = request_body(options={"include_text": False})
        status, headers, result = self.post(body=body)
        self.assertEqual(status, 200)
        self.assertNotIn("text", result["chunks"][0])
        Draft202012Validator(SCHEMA["$defs"]["chunkResponse"]).validate(result)

    def test_unknown_fields_and_missing_fields_rejected(self):
        bad_unknown = request_body()
        bad_unknown["surprise"] = True
        bad_missing = request_body()
        del bad_missing["source"]["content"]
        for body in (bad_unknown, bad_missing):
            status, headers, result = self.post(body=body)
            self.assertEqual(status, 400)
            self.assert_error_schema(result, headers)

    def test_bad_option_type_rejected(self):
        status, headers, result = self.post(body=request_body(options={"include_text": "false"}))
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")
        self.assert_error_schema(result, headers)

    def test_malformed_json_and_unsupported_media_type_for_both_post_endpoints(self):
        for path in ("/api/v1/chunking/chunks", "/api/v1/chunking/preflight"):
            with self.subTest(path=path):
                status, headers, result = self.post(path, raw=b"{")
                self.assertEqual(status, 400)
                self.assert_error_schema(result, headers)
                status, headers, result = self.post(path, body=request_body(), headers={"Content-Type": "text/plain"})
                self.assertEqual(status, 415)
                self.assertEqual(result["error"]["code"], "unsupported_media_type")
                endpoint = SCHEMA["x-endpoints"]["POST " + path]
                self.assertIn(status, endpoint["error_statuses"])
                self.assert_error_schema(result, headers)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            status, headers, result = self.post(raw=raw)
            self.assertEqual(status, 400)
            self.assert_error_schema(result, headers)

    def test_invalid_request_id_is_not_silently_accepted(self):
        status, headers, result = self.post(body=request_body(), headers={"X-CE-Request-ID": "bad id"})
        self.assertEqual(status, 400)
        self.assertNotEqual(headers["X-CE-Request-ID"], "bad id")
        self.assertEqual(result["request_id"], headers["X-CE-Request-ID"])
        self.assert_error_schema(result, headers)

    def test_malformed_and_expired_deadlines_are_rejected(self):
        for invalid_deadline in (
            "tomorrow",
            "2026-10-26 12:00:00Z",
            "2026-10-26T12:00Z",
            "2026-10-26T12:00:00.1234567Z",
            "2026-10-26T12:00:00+00:00",
        ):
            status, headers, malformed = self.post(body=request_body(), headers={"X-CE-Deadline": invalid_deadline})
            self.assertEqual(status, 400, invalid_deadline)
            self.assertEqual(malformed["error"]["code"], "invalid_parameter")
            self.assert_error_schema(malformed, headers)
        status, headers, expired = self.post(body=request_body(), headers={"X-CE-Deadline": "2000-01-01T00:00:00Z"})
        self.assertEqual(status, 504)
        self.assertEqual(expired["error"]["code"], "deadline_exceeded")
        self.assert_error_schema(expired, headers)

    def test_body_inactivity_timeout_matches_declared_contract(self):
        original_timeout = Handler.timeout
        Handler.timeout = 0.05
        conn = socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=2)
        try:
            conn.sendall(
                b"POST /api/v1/chunking/chunks HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 100\r\n"
                b"Connection: close\r\n\r\n"
            )
            response = bytearray()
            while True:
                part = conn.recv(4096)
                if not part:
                    break
                response.extend(part)
            raw = bytes(response)
            self.assertIn(b"408 Request Timeout", raw)
            self.assertIn(b'"code":"request_timeout"', raw)
        finally:
            Handler.timeout = original_timeout
            conn.close()

    def test_trickled_body_hits_absolute_deadline_while_health_stays_responsive(self):
        deadline = (datetime.now(timezone.utc) + timedelta(milliseconds=900)).isoformat().replace("+00:00", "Z")
        body = json.dumps(request_body()).encode("utf-8")
        conn = socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=3)
        try:
            headers = (
                "POST /api/v1/chunking/chunks HTTP/1.1\r\n"
                "Host: 127.0.0.1\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"X-CE-Deadline: {deadline}\r\n"
                "X-CE-Request-ID: trickle-deadline-1\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            conn.sendall(headers)
            started = time.monotonic()

            def trickle():
                try:
                    for byte in body:
                        conn.sendall(bytes([byte]))
                        time.sleep(0.02)
                except OSError:
                    return

            sender = threading.Thread(target=trickle, daemon=True)
            sender.start()
            with urlopen(self.base + "/api/v1/chunking/health", timeout=1) as health:
                health_payload = json.load(health)
                health_elapsed = time.monotonic() - started
                self.assertEqual(health.status, 200)
                self.assertEqual(health_payload["status"], "alive")
                self.assertLess(health_elapsed, 0.5)
            response = bytearray()
            while True:
                part = conn.recv(4096)
                if not part:
                    break
                response.extend(part)
            elapsed = time.monotonic() - started
            raw = bytes(response)
            status_line = raw.split(b"\r\n", 1)[0]
            self.assertRegex(status_line, rb"^HTTP/1\.[01] 504(?: |$)")
            header_bytes, body_bytes = raw.split(b"\r\n\r\n", 1)
            headers_out = {}
            for line in header_bytes.split(b"\r\n")[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    headers_out[key.decode("ascii")] = value.strip().decode("ascii")
            result = json.loads(body_bytes)
            self.assertEqual(result["error"]["code"], "deadline_exceeded")
            self.assertEqual(result["request_id"], "trickle-deadline-1")
            self.assertEqual(headers_out["X-CE-Request-ID"], "trickle-deadline-1")
            self.assertLess(elapsed, 2.0)
            sender.join(timeout=0.2)
        finally:
            conn.close()

    def test_absolute_deadline_bounds_slow_body_receipt(self):
        deadline = (datetime.now(timezone.utc) + timedelta(milliseconds=250)).isoformat().replace("+00:00", "Z")
        body = json.dumps(request_body()).encode("utf-8")
        conn = socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=2)
        started = time.monotonic()
        try:
            headers = (
                "POST /api/v1/chunking/chunks HTTP/1.1\r\n"
                "Host: 127.0.0.1\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"X-CE-Deadline: {deadline}\r\n"
                "X-CE-Request-ID: slow-deadline-1\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            conn.sendall(headers)
            response = bytearray()
            while True:
                part = conn.recv(4096)
                if not part:
                    break
                response.extend(part)
            elapsed = time.monotonic() - started
            raw = bytes(response)
            self.assertIn(b"504 Gateway Timeout", raw)
            header_bytes, body_bytes = raw.split(b"\r\n\r\n", 1)
            headers_out = {}
            for line in header_bytes.split(b"\r\n")[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    headers_out[key.decode("ascii")] = value.strip().decode("ascii")
            result = json.loads(body_bytes)
            self.assertEqual(result["error"]["code"], "deadline_exceeded")
            self.assertEqual(result["request_id"], "slow-deadline-1")
            self.assertEqual(headers_out["X-CE-Request-ID"], "slow-deadline-1")
            self.assertLess(elapsed, 1.5)
        finally:
            conn.close()

    def test_invalid_policy_returns_contract_error(self):
        body = request_body()
        body["policy"]["overlap_units"] = body["policy"]["max_units"]
        status, headers, result = self.post(body=body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_parameter")
        self.assert_error_schema(result, headers)

    def test_unknown_profile_and_version_are_rejected(self):
        for profile, version in (("missing-profile", "0.1"), ("plain-text-default", "9.9")):
            body = request_body()
            body["policy"]["profile"] = profile
            body["policy"]["profile_version"] = version
            status, headers, result = self.post(body=body)
            self.assertEqual(status, 422)
            self.assertEqual(result["error"]["code"], "unsupported_profile")
            self.assert_error_schema(result, headers)

    def test_oversized_http_body_is_rejected_before_json_parsing(self):
        # Advertise an oversized body without sending it: the server must reject
        # from Content-Length before reading/parsing, avoiding a client-side reset.
        conn = socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=3)
        try:
            conn.sendall(
                b"POST /api/v1/chunking/chunks HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 300001\r\n"
                b"X-CE-Request-ID: oversized-body-1\r\n"
                b"Connection: close\r\n\r\n"
            )
            response = bytearray()
            while True:
                part = conn.recv(4096)
                if not part:
                    break
                response.extend(part)
            raw = bytes(response)
            status_line = raw.split(b"\r\n", 1)[0]
            self.assertRegex(status_line, rb"^HTTP/1\.[01] 413(?: |$)")
            header_bytes, body_bytes = raw.split(b"\r\n\r\n", 1)
            headers = {}
            for line in header_bytes.split(b"\r\n")[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    headers[key.decode("ascii")] = value.strip().decode("ascii")
            result = json.loads(body_bytes)
            self.assertEqual(result["error"]["code"], "request_too_large")
            self.assertEqual(headers["X-CE-Request-ID"], "oversized-body-1")
            self.assert_error_schema(result, headers)
        finally:
            conn.close()

    def test_unsupported_methods_use_declared_shared_error_envelope(self):
        for method in ("PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            request = Request(self.base + "/api/v1/chunking/chunks", data=b"",
                              headers={"X-CE-Request-ID": "method-test-1"}, method=method)
            try:
                with urlopen(request, timeout=3) as response:
                    status, headers, payload = response.status, response.headers, json.load(response)
            except HTTPError as exc:
                status, headers, payload = exc.code, exc.headers, json.loads(exc.read())
            with self.subTest(method=method):
                self.assertEqual(status, 405)
                self.assertEqual(payload["error"]["code"], "method_not_allowed")
                self.assertEqual(payload["request_id"], headers["X-CE-Request-ID"])
                self.assertIn(status, SCHEMA["x-endpoints"]["POST /api/v1/chunking/chunks"]["error_statuses"])
                self.assert_error_schema(payload, headers)

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
        status, headers, error = self.post("/api/v1/chunking/preflight", body)
        self.assertEqual(status, 409)
        self.assertEqual(error["error"]["code"], "profile_mismatch")
        self.assert_error_schema(error, headers)

    def test_preflight_rejects_digest_tampering_and_invalid_nested_profile(self):
        for mutate in (
            lambda bundle: bundle.update({"digest": "f" * 64}),
            lambda bundle: bundle["chunking"].update({"max_units": 0}),
            lambda bundle: bundle["tokenization"].pop("version"),
            lambda bundle: bundle["lexical"].update({"statistics_policy": "unknown"}),
            lambda bundle: bundle.update({"embedding": None}),
            # A digest-covered content mutation with the original digest must fail.
            lambda bundle: bundle["embedding"].update({"model": "tampered-model"}),
            lambda bundle: bundle["limits"].update({"unexpected": 1}),
            lambda bundle: bundle["limits"].update({"max_chunk_representation_bytes": 256}),
        ):
            bundle = profile_bundle()
            mutate(bundle)
            body = {"index_profile": dict(PROFILE), "source_text": "hello world",
                    "chunking_profile": {"profile": "plain-text-default", "version": "0.1",
                                          "max_units": 12, "overlap_units": 2},
                    "profile_bundle": bundle}
            status, headers, result = self.post("/api/v1/chunking/preflight", body)
            self.assertIn(status, (400, 409))
            self.assert_error_schema(result, headers)

    def test_preflight_unicode_over_chunk_byte_limit_returns_contract_error(self):
        bundle = profile_bundle()
        bundle["chunking"]["max_units"] = 20000
        bundle["limits"]["max_chunk_text_bytes"] = 65536
        bundle["limits"]["max_chunk_representation_bytes"] = 500000
        bundle["limits"]["max_chunks"] = 1
        bundle["limits"]["max_request_bytes"] = 600000
        refresh_profile_digest(bundle)
        body = {"index_profile": dict(PROFILE), "source_text": "🙂" * 20000,
                "chunking_profile": {"profile": "plain-text-default", "version": "0.1",
                                     "max_units": 20000, "overlap_units": 0},
                "profile_bundle": bundle}
        status, headers, result = self.post("/api/v1/chunking/preflight", body)
        self.assertEqual(status, 422)
        self.assertEqual(result["error"]["code"], "source_too_large")
        self.assert_error_schema(result, headers)

    def test_preflight_reports_profile_limit_without_materializing_all_chunks(self):
        bundle = profile_bundle()
        bundle["limits"]["max_chunks"] = 2
        bundle["limits"]["max_request_bytes"] = 12288
        bundle["chunking"]["max_units"] = 4
        refresh_profile_digest(bundle)
        body = {"index_profile": dict(PROFILE), "source_text": "abcdefghijklmnop",
                "chunking_profile": {"profile": "plain-text-default", "version": "0.1",
                                     "max_units": 4, "overlap_units": 0},
                "profile_bundle": bundle}
        status, headers, result = self.post("/api/v1/chunking/preflight", body)
        self.assertEqual(status, 200)
        self.assertFalse(result["fits_profile"])
        self.assertGreater(result["chunk_count"], bundle["limits"]["max_chunks"])
        Draft202012Validator(SCHEMA["$defs"]["preflightResponse"]).validate(result)

    def test_capacity_limit_rejects_excess_handler_with_correlated_503(self):
        class SingleWorkerServer(BoundedThreadingHTTPServer):
            max_workers = 1

        original_timeout = Handler.timeout
        Handler.timeout = 1.0
        server = SingleWorkerServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stalled = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        try:
            stalled.sendall(
                b"POST /api/v1/chunking/chunks HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 100\r\n"
                b"Connection: close\r\n\r\n"
            )
            rejected = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
            try:
                rejected.sendall(
                    b"GET /api/v1/chunking/health HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Connection: close\r\n\r\n"
                )
                response = bytearray()
                while True:
                    part = rejected.recv(4096)
                    if not part:
                        break
                    response.extend(part)
            finally:
                rejected.close()
            raw = bytes(response)
            status_line = raw.split(b"\r\n", 1)[0]
            self.assertRegex(status_line, rb"^HTTP/1\.[01] 503(?: |$)")
            header_bytes, body_bytes = raw.split(b"\r\n\r\n", 1)
            headers = {}
            for line in header_bytes.split(b"\r\n")[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    headers[key.decode("ascii")] = value.strip().decode("ascii")
            payload = json.loads(body_bytes)
            self.assertEqual(payload["error"]["code"], "service_unavailable")
            self.assertEqual(payload["request_id"], headers["X-CE-Request-ID"])
            Draft202012Validator(SCHEMA["$defs"]["errorResponse"]).validate(payload)
        finally:
            stalled.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            Handler.timeout = original_timeout

    def test_unknown_endpoint_uses_shared_error_envelope(self):
        status, headers, result = self.post("/api/v1/chunking/unknown", body={})
        self.assertEqual(status, 404)
        self.assertEqual(result["error"]["code"], "endpoint_not_found")
        self.assert_error_schema(result, headers)


if __name__ == "__main__":
    unittest.main()
