"""Regression tests for Index-owned immutable profile resolution."""
import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runtime.chunking import ChunkingError
from runtime.server import BoundedThreadingHTTPServer, Handler, IndexProfileRegistry, _profile_digest


def valid_bundle(name="default", version="0.1", status="active"):
    bundle = {
        "name": name,
        "version": version,
        "status": status,
        "chunking": {"profile": "plain-text-default", "version": "0.1", "max_units": 12},
        "tokenization": {"profile": "technical-default", "version": "0.1"},
        "lexical": {"profile": "technical-default", "version": "0.1", "statistics_policy": "scope_partition"},
        "embedding": {
            "required": False, "profile": "default", "version": "0.1", "model": "none",
            "model_version": "none", "input_types": ["document"], "dimensions": 1,
            "normalization": "none", "metric": "cosine", "max_input_tokens": 1000,
        },
        "limits": {
            "max_chunks": 1, "max_source_bytes": 1000, "max_chunk_text_bytes": 64,
            "max_request_bytes": 8192, "max_chunk_representation_bytes": 4096,
            "max_envelope_bytes": 1024, "max_metadata_bytes": 0,
            "max_lexical_terms_per_chunk": 10, "max_lexical_term_bytes": 32,
        },
        "digest": "",
    }
    bundle["digest"] = _profile_digest(bundle)
    return bundle


class IndexProfileRegistryUnitTests(unittest.TestCase):
    def test_no_implicit_default_profile(self):
        registry = IndexProfileRegistry()
        self.assertIsNone(registry.resolve_current("default"))
        self.assertIsNone(registry.resolve_version("default", "0.1"))

    def test_rejects_bad_digest_and_duplicate_versions(self):
        bad = valid_bundle()
        bad["digest"] = "0" * 64
        with self.assertRaises(ChunkingError):
            IndexProfileRegistry([bad], {})
        with self.assertRaises(ValueError):
            IndexProfileRegistry([valid_bundle(), valid_bundle()], {})

    def test_resolved_bundle_is_a_snapshot_not_mutable_registry_state(self):
        registry = IndexProfileRegistry([valid_bundle()], {"default": "0.1"})
        resolved = registry.resolve_current("default")
        resolved["tokenization"]["profile"] = "mutated"
        self.assertEqual(registry.resolve_current("default")["tokenization"]["profile"], "technical-default")

    def test_current_pointer_must_resolve_to_active_bundle(self):
        with self.assertRaises(ValueError):
            IndexProfileRegistry([valid_bundle(status="deprecated")], {"default": "0.1"})
        with self.assertRaises(ValueError):
            IndexProfileRegistry([valid_bundle()], {"default": "9.9"})

    def test_environment_configuration_is_strict_and_validated(self):
        document = {"profiles": [valid_bundle()], "current": {"default": "0.1"}}
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as config:
            json.dump(document, config)
            config.flush()
            old = os.environ.get("CE_INDEX_PROFILES_FILE")
            os.environ["CE_INDEX_PROFILES_FILE"] = config.name
            try:
                registry = IndexProfileRegistry.from_environment()
                self.assertEqual(registry.resolve_current("default")["digest"], document["profiles"][0]["digest"])
            finally:
                if old is None:
                    os.environ.pop("CE_INDEX_PROFILES_FILE", None)
                else:
                    os.environ["CE_INDEX_PROFILES_FILE"] = old


class IndexProfileRegistryHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.httpd.profile_registry = IndexProfileRegistry(
            [valid_bundle(), valid_bundle(version="0.2", status="retired")],
            {"default": "0.1"},
        )
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def get(self, path):
        request = Request(self.base + path, headers={"X-CE-Request-ID": "profile-test-1"})
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, response.headers, json.load(response)
        except HTTPError as error:
            return error.code, error.headers, json.load(error)

    def test_current_profile_returns_complete_immutable_identity(self):
        status, headers, body = self.get("/api/v1/index/profiles/default/current")
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "default")
        self.assertEqual(body["version"], "0.1")
        self.assertEqual(body["digest"], body["bundle"]["digest"])
        self.assertEqual(body["bundle"]["status"], "active")
        self.assertEqual(body["request_id"], "profile-test-1")
        self.assertEqual(headers["X-CE-Request-ID"], "profile-test-1")

    def test_versioned_profile_resolves_exact_version(self):
        status, _, body = self.get("/api/v1/index/profiles/default/versions/0.1")
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], "0.1")

    def test_unknown_profiles_do_not_fall_back(self):
        for path in (
            "/api/v1/index/profiles/missing/current",
            "/api/v1/index/profiles/default/versions/9.9",
        ):
            with self.subTest(path=path):
                status, _, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertEqual(body["error"]["code"], "profile_not_found")

    def test_retired_profile_is_rejected_for_new_work(self):
        status, _, body = self.get("/api/v1/index/profiles/default/versions/0.2")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "profile_retired")


if __name__ == "__main__":
    unittest.main()
