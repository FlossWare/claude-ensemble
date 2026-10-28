"""Regression tests for source adapters, provenance, and lifecycle tracking."""
import tempfile
import unittest
from pathlib import Path

from runtime.source_ingestion import (
    DocumentAdapter, GitRepositoryAdapter, MemoryRestClient, PatentAdapter,
    RfcAdapter, SourceDocument, SourceIngestionError, SourceManifest, SourcePipeline,
)


SCOPE = {"type": "project", "id": "ce-docs", "visibility": "private"}
PROFILE = {"name": "default", "version": "0.1", "digest": "0123456789abcdef" * 4}


class FakeMemoryClient:
    def __init__(self):
        self.calls = []
        self.records = {}
        self.next_id = 0

    def request(self, method, path, payload=None, idempotency_key=None):
        self.calls.append((method, path, payload, idempotency_key))
        if method == "POST" and path == "/api/v1/memories":
            self.next_id += 1
            memory_id = f"mem-{self.next_id}"
            self.records[memory_id] = {"memory_id": memory_id, "revision_sequence": 1,
                                       "content": payload["content"]}
            return 202, {"memory_id": memory_id, "revision_sequence": 1,
                         "operation_id": "memory:op:one", "indexing_status": "pending_index"}
        if method == "GET" and path.startswith("/api/v1/memories/"):
            memory_id = path.rsplit("/", 1)[-1]
            record = self.records.get(memory_id)
            if record is None:
                return 404, {}
            return 200, dict(record)
        if method == "POST" and path.endswith("/revisions"):
            memory_id = path.split("/")[-2]
            record = self.records[memory_id]
            self.assert_sequence = payload["expected_base_revision_sequence"]
            record["revision_sequence"] += 1
            record["content"] = payload["content"]
            return 202, {"memory_id": memory_id, "revision_sequence": record["revision_sequence"],
                         "operation_id": "memory:op:update", "indexing_status": "pending_index"}
        if method == "DELETE":
            memory_id = path.rsplit("/", 1)[-1]
            self.records.pop(memory_id, None)
            return 202, {"operation_id": "memory:op:delete"}
        raise AssertionError(f"unexpected REST request: {method} {path}")


class SourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_rfc_adapter_preserves_identity_title_and_sections(self):
        path = self.root / "rfc9999.txt"
        path.write_text(
            "Network Working Group\nRequest for Comments: 9999\nTitle: A Test RFC\n\n"
            "1. Introduction\nThis is the introduction.\n\n"
            "2. Protocol\nThe protocol follows.\n", encoding="utf-8")
        doc = RfcAdapter().read(path)[0]
        self.assertEqual(doc.source_key, "rfc:9999")
        self.assertEqual(doc.title, "A Test RFC")
        self.assertEqual([x["heading"] for x in doc.metadata["sections"]], ["1. Introduction", "2. Protocol"])
        self.assertIn("This is the introduction", doc.content)
        self.assertEqual(len(doc.content_sha256), 64)

    def test_patent_xml_extracts_title_identifier_abstract_and_claims(self):
        path = self.root / "patent.xml"
        path.write_text("""<patent-document><bibliographic-data><publication-reference>
          <document-id><doc-number>US1234567</doc-number></document-id></publication-reference>
          <invention-title>Useful Widget</invention-title></bibliographic-data>
          <abstract><p>A widget that works.</p></abstract><claims><claim><claim-text>1. A widget comprising a gear.</claim-text></claim></claims></patent-document>""",
          encoding="utf-8")
        doc = PatentAdapter().read(path)[0]
        self.assertEqual(doc.title, "Useful Widget")
        self.assertEqual(doc.metadata["patent_id"], "US1234567")
        self.assertIn("A widget that works", doc.content)
        self.assertIn("A widget comprising a gear", doc.content)

    def test_repository_adapter_retains_relative_path_and_symbols(self):
        repo = self.root / "sample-repo"
        (repo / "src").mkdir(parents=True)
        (repo / ".git").mkdir()
        (repo / "src" / "Thing.java").write_text(
            "public class Thing {\n  public void run() {}\n}\n", encoding="utf-8")
        (repo / ".git" / "secret.txt").write_text("must not ingest", encoding="utf-8")
        docs = GitRepositoryAdapter().read(repo)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["relative_path"], "src/Thing.java")
        self.assertIn("Thing", docs[0].metadata["symbols"])
        self.assertNotIn("must not ingest", docs[0].content)

    def test_document_adapter_rejects_unsupported_format(self):
        path = self.root / "archive.bin"
        path.write_bytes(b"not a document")
        with self.assertRaisesRegex(SourceIngestionError, "unsupported document format"):
            DocumentAdapter().read(path)

    def test_symlink_input_is_rejected(self):
        real = self.root / "real.txt"
        real.write_text("safe", encoding="utf-8")
        link = self.root / "link.txt"
        link.symlink_to(real)
        with self.assertRaisesRegex(SourceIngestionError, "non-symlink"):
            DocumentAdapter().read(link)

    def test_memory_payload_preserves_source_provenance(self):
        doc = SourceDocument("rfc:123", "file:///rfc123.txt", "RFC 123", "rfc",
                             "text/plain", "body", {"rfc_number": "123"}, "a" * 64,
                             "rev-1", "2026-10-28T00:00:00Z")
        payload = doc.to_memory_payload(scope=SCOPE, index_profile=PROFILE)
        self.assertEqual(payload["provenance"]["source_uri"], "file:///rfc123.txt")
        self.assertEqual(payload["provenance"]["content_sha256"], "a" * 64)
        self.assertEqual(payload["scope"], SCOPE)


class SourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manifest = SourceManifest(Path(self.temp.name) / "manifest.sqlite3")
        self.client = FakeMemoryClient()
        self.pipeline = SourcePipeline(self.client, self.manifest)
        self.doc = SourceDocument("document:guide.md", "file:///guide.md", "guide", "document",
                                  "text/markdown", "# Guide\n\nOriginal", {"format": "md"},
                                  "a" * 64, "a" * 64, "2026-10-28T00:00:00Z")

    def test_unchanged_rerun_skips_memory_write(self):
        first = self.pipeline.ingest(self.doc, scope=SCOPE, index_profile=PROFILE)
        count = len(self.client.calls)
        second = self.pipeline.ingest(self.doc, scope=SCOPE, index_profile=PROFILE)
        self.assertEqual(first["status"], "submitted")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(len(self.client.calls), count)

    def test_changed_revision_updates_same_memory_record(self):
        first = self.pipeline.ingest(self.doc, scope=SCOPE, index_profile=PROFILE)
        changed = SourceDocument(**{**self.doc.__dict__, "content": "# Guide\n\nUpdated",
                                    "content_sha256": "b" * 64, "source_revision": "b" * 64})
        second = self.pipeline.ingest(changed, scope=SCOPE, index_profile=PROFILE)
        self.assertEqual(first["memory_id"], second["memory_id"])
        self.assertEqual(second["revision_sequence"], 2)
        self.assertEqual(self.client.records[first["memory_id"]]["content"], changed.content)

    def test_removed_source_is_tombstoned_through_memory_rest(self):
        self.pipeline.ingest(self.doc, scope=SCOPE, index_profile=PROFILE)
        results = self.pipeline.remove_missing(set())
        self.assertEqual(results[0]["status"], "tombstoned")
        self.assertEqual(self.manifest.get(self.doc.source_key)["state"], "removed")
        self.assertIn("DELETE", [call[0] for call in self.client.calls])

    def test_batch_isolates_item_failures(self):
        bad = SourceDocument("document:bad", "file:///bad", "bad", "document",
                             "text/plain", "bad", {}, "c" * 64, "c" * 64,
                             "2026-10-28T00:00:00Z")
        class FailingClient(FakeMemoryClient):
            def request(self, method, path, payload=None, idempotency_key=None):
                if path == "/api/v1/memories" and payload and payload.get("content") == "bad":
                    return 422, {"error": {"message": "rejected"}}
                return super().request(method, path, payload, idempotency_key)
        pipeline = SourcePipeline(FailingClient(), self.manifest)
        results = pipeline.ingest_many([bad, self.doc], scope=SCOPE, index_profile=PROFILE)
        self.assertEqual([r["status"] for r in results], ["error", "submitted"])


if __name__ == "__main__":
    unittest.main()
