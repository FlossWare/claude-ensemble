#!/usr/bin/env python3
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

memory_spec = importlib.util.spec_from_file_location("ce_memory_service", ROOT / "memory-service" / "memory_service.py")
memory_module = importlib.util.module_from_spec(memory_spec)
memory_spec.loader.exec_module(memory_module)
sync_spec = importlib.util.spec_from_file_location("ce_memory_sync", ROOT / "tools" / "claude-config" / "lib" / "memory_sync.py")
sync_module = importlib.util.module_from_spec(sync_spec)
sync_spec.loader.exec_module(sync_module)


class MemoryIngestTests(unittest.TestCase):
    def test_new_changed_and_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = memory_module.MemoryStore(Path(tmp))
            path = "/home/test/.claude/projects/project-a/memory/pattern.md"
            first = "first"
            sha1 = hashlib.sha256(first.encode()).hexdigest()
            self.assertEqual(store.ingest_claude_markdown(path, first, sha1, {"project": "project-a"})["status"], "ingested")
            self.assertEqual(store.ingest_claude_markdown(path, first, sha1, {"project": "project-a"})["status"], "unchanged")
            second = "second"
            sha2 = hashlib.sha256(second.encode()).hexdigest()
            self.assertEqual(store.ingest_claude_markdown(path, second, sha2, {"project": "project-a"})["status"], "ingested")

    def test_duplicate_basenames_remain_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = memory_module.MemoryStore(Path(tmp))
            paths = [
                "/home/test/.claude/projects/project-a/memory/MEMORY.md",
                "/home/test/.claude/projects/project-b/memory/MEMORY.md",
            ]
            for path in paths:
                content = path
                digest = hashlib.sha256(content.encode()).hexdigest()
                store.ingest_claude_markdown(path, content, digest, {"project": path.split("/projects/")[1].split("/")[0]})
            index = store.list_claude_ingest()
            self.assertEqual(len(index), 2)
            self.assertNotEqual(index[paths[0]]["document"], index[paths[1]]["document"])

    def test_reconcile_marks_deletion_stale_without_removing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = memory_module.MemoryStore(Path(tmp))
            path = "/home/test/.claude/projects/project-a/memory/old.md"
            content = "old"
            digest = hashlib.sha256(content.encode()).hexdigest()
            result = store.ingest_claude_markdown(path, content, digest, {"project": "project-a"})
            self.assertEqual(store.reconcile_claude_markdown("claude-code", [])["count"], 1)
            self.assertEqual(store.list_claude_ingest(), {})
            self.assertTrue((Path(tmp) / f"{result['document']}.md").exists())
            results = store.search_semantic("old")
            self.assertFalse(any(item["file"] == result["document"] for item in results))


class SyncTests(unittest.TestCase):
    def test_unavailable_memory_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".claude"
            (root / "projects" / "project-a" / "memory").mkdir(parents=True)
            (root / "projects" / "project-a" / "memory" / "one.md").write_text("one", encoding="utf-8")
            original = sync_module.post
            sync_module.post = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline"))
            try:
                self.assertEqual(sync_module.sync_once(root), 1)
            finally:
                sync_module.post = original


if __name__ == "__main__":
    unittest.main()
