#!/usr/bin/env python3
"""Tests for the memory service security boundary."""

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SERVICE_DIR))
from execution.context import ExecutionContext, ExecutionResult, ExecutionStatus  # noqa: E402
from memory_client import MemoryClient  # noqa: E402


SERVICE = Path(__file__).with_name("memory_service.py")


def send_request(socket_path: Path, request: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(str(socket_path))
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        response = b""
        while b"\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        return json.loads(response.decode("utf-8").strip())


class MemoryClientContextTest(unittest.TestCase):
    def test_append_accepts_canonical_context_without_duplicate_schema(self):
        client = MemoryClient(socket_path=Path("/does/not/exist"))
        captured = {}

        def send_request(request):
            captured.update(request=request)
            return {"ok": True}

        client._send_request = send_request
        context = ExecutionContext(
            request_id="request-1",
            execution_id="execution-1",
            parent_execution_id="parent-1",
            objective="objective",
            artifact="artifact",
            requirements=("requirement",),
            evidence=("evidence",),
            constraints=("constraint",),
            lineage=("parent-1", "execution-1"),
            stage="review",
            worker_id="worker-1",
        )

        self.assertTrue(client.append("context", {"result": "actual"}, context=context))
        self.assertEqual(captured["request"]["entry"]["result"], "actual")
        self.assertEqual(
            captured["request"]["entry"]["execution_context"],
            context.to_dict(),
        )

        restored = ExecutionContext.from_dict(captured["request"]["entry"]["execution_context"])
        self.assertEqual(restored, context)


class MemoryServiceIdempotencyTest(unittest.TestCase):
    def test_append_once_deduplicates_retries_and_rejects_key_reuse(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            from memory_service import MemoryService

            memory = MemoryService(root / "memory.sock", root / "memory")
            first = json.loads(memory._process_request(json.dumps({
                "op": "append_once",
                "name": "claude_code_events",
                "event_id": "session-123:SessionEnd",
                "entry": {"event": "SessionEnd", "session_id": "session-123"},
            })))
            duplicate = json.loads(memory._process_request(json.dumps({
                "op": "append_once",
                "name": "claude_code_events",
                "event_id": "session-123:SessionEnd",
                "entry": {"event": "SessionEnd", "session_id": "session-123"},
            })))
            conflict = json.loads(memory._process_request(json.dumps({
                "op": "append_once",
                "name": "claude_code_events",
                "event_id": "session-123:SessionEnd",
                "entry": {"event": "SessionEnd", "session_id": "different-session"},
            })))

            self.assertEqual(first["status"], "stored")
            self.assertEqual(duplicate["status"], "duplicate")
            self.assertFalse(conflict["ok"])
            self.assertIn("different payload", conflict["error"])
            entries = memory.store.read_entries("claude_code_events")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["event_id"], "session-123:SessionEnd")

    def test_append_once_requires_stable_event_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            from memory_service import MemoryService

            memory = MemoryService(Path(temp_dir) / "memory.sock", Path(temp_dir) / "memory")
            response = json.loads(memory._process_request(json.dumps({
                "op": "append_once", "name": "claude_code_events", "entry": {"event": "SessionEnd"}
            })))
            self.assertFalse(response["ok"])
            self.assertIn("event_id", response["error"])


    def test_append_once_rejects_malformed_and_non_object_jsonl_records(self):
        from memory_service import MemoryStore

        cases = (
            ("malformed", "{not-json\n", "malformed record at line 1"),
            ("array", "[1, 2]\n", "is not a JSON object"),
            ("null", "null\n", "is not a JSON object"),
        )
        for label, content, message in cases:
            with self.subTest(record=label), tempfile.TemporaryDirectory() as temp_dir:
                store = MemoryStore(Path(temp_dir))
                (Path(temp_dir) / "events.jsonl").write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, message):
                    store.append_entry_once("events", "event-1", {"event": "SessionEnd"})
                self.assertEqual((Path(temp_dir) / "events.jsonl").read_text(encoding="utf-8"), content)

    def test_append_once_rejects_existing_event_without_payload_digest(self):
        from memory_service import MemoryStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = MemoryStore(Path(temp_dir))
            path = Path(temp_dir) / "events.jsonl"
            path.write_text(
                json.dumps({"event_id": "event-1", "event": "SessionEnd"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "without a verifiable payload digest"):
                store.append_entry_once("events", "event-1", {"event": "SessionEnd"})
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_append_once_rejects_empty_entry(self):
        from memory_service import MemoryStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = MemoryStore(Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "non-empty JSON object"):
                store.append_entry_once("events", "event-1", {})


    def test_append_once_retries_fsync_failure_before_duplicate_ack(self):
        from unittest.mock import patch
        from memory_service import MemoryStore

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = MemoryStore(root)
            entry = {"event": "SessionEnd", "session_id": "session-1"}
            with patch("memory_service.os.fsync", side_effect=[OSError("sync failed"), None]) as sync:
                with self.assertRaisesRegex(OSError, "sync failed"):
                    store.append_entry_once("events", "event-1", entry)
                result = store.append_entry_once("events", "event-1", entry)
            self.assertEqual(result["status"], "duplicate")
            self.assertEqual(sync.call_count, 2)
            records = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            # A newly constructed store can safely retry after a service restart.
            restarted = MemoryStore(root)
            self.assertEqual(restarted.append_entry_once("events", "event-1", entry)["status"], "duplicate")
            self.assertEqual(len((root / "events.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_append_once_preserves_payload_timestamp_and_reserves_digest(self):
        from memory_service import MemoryStore

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = MemoryStore(root)
            entry = {"event": "SessionEnd", "timestamp": "2026-10-08T23:00:00Z"}
            result = store.append_entry_once("events", "event-1", entry)
            self.assertEqual(result["status"], "stored")
            record = json.loads((root / "events.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(record["timestamp"], entry["timestamp"])
            self.assertIn("captured_at", record)
            self.assertEqual(store.append_entry_once("events", "event-1", entry)["status"], "duplicate")
            with self.assertRaisesRegex(ValueError, "payload_sha256 is reserved"):
                store.append_entry_once("events", "event-2", {
                    "event": "SessionEnd", "payload_sha256": "caller-value"
                })



class MemoryServiceRestIdempotencyTest(unittest.TestCase):
    def test_append_once_rest_endpoint_maps_validation_conflict_and_corruption(self):
        from memory_service import MemoryService, create_http_server

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = MemoryService(root / "memory.sock", root / "memory")
            server = create_http_server(service, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/memory/append-once"

                def post(payload):
                    request = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=2) as response:
                            return response.status, json.loads(response.read().decode("utf-8"))
                    except urllib.error.HTTPError as response:
                        return response.code, json.loads(response.read().decode("utf-8"))

                base = {
                    "name": "events",
                    "event_id": "event-1",
                    "entry": {"event": "SessionEnd", "session_id": "session-1"},
                }
                self.assertEqual(post(base)[0], 200)
                conflict = dict(base)
                conflict["entry"] = {"event": "SessionEnd", "session_id": "different"}
                status, payload = post(conflict)
                self.assertEqual(status, 409)
                self.assertFalse(payload["ok"])
                self.assertIn("different payload", payload["error"])

                status, payload = post({"name": "events", "entry": {"event": "SessionEnd"}})
                self.assertEqual(status, 400)
                self.assertFalse(payload["ok"])

                (root / "memory" / "corrupt.jsonl").write_text("{broken\n", encoding="utf-8")
                status, payload = post({
                    "name": "corrupt",
                    "event_id": "event-corrupt",
                    "entry": {"event": "SessionEnd"},
                })
                self.assertEqual(status, 500)
                self.assertFalse(payload["ok"])
                self.assertIn("malformed record", payload["error"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_append_once_rest_endpoint_acknowledges_stored_and_duplicate(self):
        from memory_service import MemoryService, create_http_server

        with tempfile.TemporaryDirectory() as temp_dir:
            service = MemoryService(Path(temp_dir) / "memory.sock", Path(temp_dir) / "memory")
            server = create_http_server(service, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/memory/append-once"
                payload = {
                    "name": "claude_code_events",
                    "event_id": "session-456:SessionEnd",
                    "entry": {"event": "SessionEnd", "session_id": "session-456"},
                }
                results = []
                for _ in range(2):
                    request = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=2) as response:
                        results.append(json.loads(response.read().decode("utf-8")))
                self.assertEqual(results[0]["status"], "stored")
                self.assertEqual(results[1]["status"], "duplicate")
                self.assertEqual(len(service.store.read_entries("claude_code_events")), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class MemoryServiceSecurityTest(unittest.TestCase):
    def test_private_runtime_directory_socket_permissions_and_name_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            runtime = root / "runtime"
            (home / ".claude").mkdir(parents=True)
            runtime.mkdir()

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["XDG_RUNTIME_DIR"] = str(runtime)
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                [sys.executable, str(SERVICE)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            socket_path = runtime / "claude-ensemble" / "memory.sock"
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not socket_path.exists():
                    time.sleep(0.05)

                self.assertTrue(socket_path.exists(), "memory socket was not created")

                runtime_mode = stat.S_IMODE(socket_path.parent.stat().st_mode)
                socket_mode = stat.S_IMODE(socket_path.stat().st_mode)
                self.assertEqual(runtime_mode, 0o700)
                self.assertEqual(socket_mode, 0o600)

                valid = send_request(
                    socket_path,
                    {"op": "write", "name": "project_test-1.v2", "content": "ok"},
                )
                self.assertEqual(valid, {"ok": True})

                read = send_request(
                    socket_path, {"op": "read", "name": "project_test-1.v2"}
                )
                self.assertEqual(read["content"], "ok")

                for invalid_name in ("../escape", "foo/bar", "/absolute", ".."):
                    response = send_request(
                        socket_path,
                        {"op": "write", "name": invalid_name, "content": "nope"},
                    )
                    self.assertFalse(response["ok"])
                    self.assertIn("Invalid memory name", response["error"])

                    entries_response = send_request(
                        socket_path,
                        {"op": "entries", "name": invalid_name},
                    )
                    self.assertFalse(entries_response["ok"])
                    self.assertIn("Invalid memory name", entries_response["error"])

                outside = home / "escape.md"
                self.assertFalse(outside.exists())
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


class MemoryServiceContextTest(unittest.TestCase):
    def test_execution_aware_retrieval_returns_related_prior_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            runtime = root / "runtime"
            (home / ".claude").mkdir(parents=True)
            runtime.mkdir()

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["XDG_RUNTIME_DIR"] = str(runtime)
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                [sys.executable, str(SERVICE)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            socket_path = runtime / "claude-ensemble" / "memory.sock"
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not socket_path.exists():
                    time.sleep(0.05)
                self.assertTrue(socket_path.exists(), "memory socket was not created")

                grandparent = ExecutionContext(
                    request_id="request-1",
                    execution_id="grandparent",
                    objective="solve",
                    lineage=("grandparent",),
                    stage="root",
                )
                parent = grandparent.child(
                    execution_id="parent",
                    stage="solve",
                    worker_id="worker-1",
                )
                sibling = grandparent.child(
                    execution_id="sibling",
                    stage="solve",
                    worker_id="worker-2",
                )
                separate_root = ExecutionContext(
                    request_id="request-1",
                    execution_id="separate-root",
                    objective="solve",
                    lineage=("separate-root",),
                    stage="other",
                )
                child = parent.child(
                    execution_id="child",
                    stage="review",
                    worker_id="reviewer-1",
                )
                descendant = child.child(
                    execution_id="grandchild",
                    stage="future",
                    worker_id="future-worker",
                )
                reused_id = ExecutionContext(
                    request_id="request-2",
                    execution_id="parent",
                    objective="other",
                    lineage=("parent",),
                )
                cross_request_shared_lineage = ExecutionContext(
                    request_id="request-2",
                    execution_id="other-child",
                    objective="other",
                    lineage=("parent", "other-child"),
                )
                unrelated = ExecutionContext(
                    request_id="request-2",
                    execution_id="unrelated",
                    objective="other",
                    lineage=("unrelated",),
                )

                for context, result in (
                    (grandparent, "grandparent result"),
                    (parent, "parent result"),
                    (sibling, "sibling result"),
                    (separate_root, "separate root result"),
                    (descendant, "descendant result"),
                    (reused_id, "reused id result"),
                    (
                        cross_request_shared_lineage,
                        "cross-request shared lineage result",
                    ),
                    (unrelated, "unrelated result"),
                ):
                    response = send_request(
                        socket_path,
                        {
                            "op": "append",
                            "name": "execution-context",
                            "entry": {
                                "result": result,
                                "execution_context": context.to_dict(),
                            },
                        },
                    )
                    self.assertEqual(response, {"ok": True})

                response = send_request(
                    socket_path,
                    {
                        "op": "retrieve",
                        "name": "execution-context",
                        "context": child.to_dict(),
                        "limit": 10,
                    },
                )
                self.assertTrue(response["ok"])
                results = response["results"]
                self.assertEqual(
                    [item["relation"] for item in results],
                    ["parent", "ancestor", "same-request", "related-lineage"],
                )
                self.assertEqual(results[0]["record"]["result"], "parent result")
                self.assertEqual(results[1]["record"]["result"], "grandparent result")
                self.assertEqual(results[2]["record"]["result"], "separate root result")
                self.assertEqual(results[3]["record"]["result"], "sibling result")
                self.assertEqual(results[3]["relation"], "related-lineage")
                self.assertFalse(results[0]["authoritative"])
                retrieved_values = [item["record"]["result"] for item in results]
                self.assertNotIn("descendant result", retrieved_values)
                self.assertNotIn("reused id result", retrieved_values)
                self.assertNotIn(
                    "cross-request shared lineage result", retrieved_values
                )
                self.assertNotIn("unrelated result", retrieved_values)

                limited = send_request(
                    socket_path,
                    {
                        "op": "retrieve",
                        "name": "execution-context",
                        "context": child.to_dict(),
                        "limit": 1,
                    },
                )
                self.assertTrue(limited["ok"])
                self.assertEqual(len(limited["results"]), 1)
                self.assertEqual(limited["results"][0]["relation"], "parent")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

    def test_execution_aware_retrieval_rejects_invalid_requests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            runtime = root / "runtime"
            (home / ".claude").mkdir(parents=True)
            runtime.mkdir()

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["XDG_RUNTIME_DIR"] = str(runtime)
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                [sys.executable, str(SERVICE)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            socket_path = runtime / "claude-ensemble" / "memory.sock"
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not socket_path.exists():
                    time.sleep(0.05)
                self.assertTrue(socket_path.exists(), "memory socket was not created")

                context = ExecutionContext(
                    request_id="request-1",
                    execution_id="child",
                    objective="test retrieval",
                    parent_execution_id="parent",
                    lineage=("parent", "child"),
                )
                invalid_requests = [
                    {"name": "../escape", "context": context.to_dict(), "limit": 10},
                    {"name": "execution-context", "context": {}, "limit": 10},
                    {"name": "execution-context", "context": context.to_dict(), "limit": 0},
                    {"name": "execution-context", "context": context.to_dict(), "limit": 101},
                    {"name": "execution-context", "context": context.to_dict(), "limit": "10"},
                    {"name": "execution-context", "context": context.to_dict(), "limit": True},
                    {"name": "execution-context", "context": context.to_dict(), "limit": -1},
                ]
                for request in invalid_requests:
                    response = send_request(
                        socket_path,
                        {"op": "retrieve", **request},
                    )
                    self.assertFalse(response["ok"])
                    self.assertIn("error", response)

                invalid_record = send_request(
                    socket_path,
                    {
                        "op": "append",
                        "name": "execution-context",
                        "entry": {
                            "result": "bad context",
                            "execution_context": {"not": "a valid context"},
                        },
                    },
                )
                self.assertEqual(invalid_record, {"ok": True})

                valid = send_request(
                    socket_path,
                    {
                        "op": "retrieve",
                        "name": "execution-context",
                        "context": context.to_dict(),
                        "limit": 10,
                    },
                )
                self.assertEqual(valid, {"ok": True, "results": []})
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

    def test_canonical_execution_context_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            runtime = root / "runtime"
            (home / ".claude").mkdir(parents=True)
            runtime.mkdir()

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["XDG_RUNTIME_DIR"] = str(runtime)
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                [sys.executable, str(SERVICE)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            socket_path = runtime / "claude-ensemble" / "memory.sock"
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not socket_path.exists():
                    time.sleep(0.05)
                self.assertTrue(socket_path.exists(), "memory socket was not created")

                result = ExecutionResult(
                    execution_id="parent.worker",
                    node_type="model",
                    status=ExecutionStatus.SUCCESS,
                    output="prior",
                )
                parent = ExecutionContext(
                    request_id="request-1",
                    execution_id="parent",
                    objective="solve",
                    artifact={"name": "artifact"},
                    requirements=("requirement",),
                    evidence=("evidence",),
                    constraints=("constraint",),
                    prior_results=(result,),
                    lineage=("parent",),
                    stage="solve",
                    worker_id="worker-1",
                )
                child = parent.child(
                    execution_id="child",
                    stage="review",
                    worker_id="reviewer-1",
                )

                legacy_response = send_request(
                    socket_path,
                    {
                        "op": "append",
                        "name": "execution-context",
                        "entry": {"result": "legacy"},
                    },
                )
                self.assertEqual(legacy_response, {"ok": True})

                response = send_request(
                    socket_path,
                    {
                        "op": "append",
                        "name": "execution-context",
                        "entry": {
                            "artifact": child.artifact,
                            "result": child.prior_results[0].output,
                            "execution_context": child.to_dict(),
                        },
                    },
                )
                self.assertEqual(response, {"ok": True})

                entries = send_request(
                    socket_path,
                    {"op": "entries", "name": "execution-context"},
                )
                self.assertEqual(entries["ok"], True)
                self.assertEqual(len(entries["entries"]), 2)
                self.assertEqual(entries["entries"][0]["result"], "legacy")
                self.assertNotIn("execution_context", entries["entries"][0])
                self.assertEqual(entries["entries"][1]["artifact"], {"name": "artifact"})
                self.assertEqual(entries["entries"][1]["result"], "prior")
                restored = ExecutionContext.from_dict(entries["entries"][1]["execution_context"])

                self.assertEqual(restored.request_id, "request-1")
                self.assertEqual(restored.execution_id, "child")
                self.assertEqual(restored.parent_execution_id, "parent")
                self.assertEqual(restored.lineage, ("parent", "child"))
                self.assertEqual(restored.stage, "review")
                self.assertEqual(restored.worker_id, "reviewer-1")
                self.assertEqual(restored.objective, "solve")
                self.assertEqual(restored.artifact, {"name": "artifact"})
                self.assertEqual(restored.requirements, ("requirement",))
                self.assertEqual(restored.evidence, ("evidence",))
                self.assertEqual(restored.constraints, ("constraint",))
                self.assertEqual(restored.prior_results[0].execution_id, "parent.worker")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


class MemorySchemaVersionTest(unittest.TestCase):
    def test_current_context_includes_schema_version(self):
        context = ExecutionContext(
            request_id="request-1",
            execution_id="execution-1",
            objective="objective",
        )
        serialized = context.to_dict()
        self.assertEqual(serialized["schema_version"], 1)

    def test_legacy_context_without_schema_version_is_supported(self):
        legacy = {
            "request_id": "request-1",
            "execution_id": "execution-1",
            "objective": "objective",
            "legacy_field": "ignored",
        }
        restored = ExecutionContext.from_dict(legacy)
        self.assertEqual(restored.request_id, "request-1")
        self.assertEqual(restored.execution_id, "execution-1")
        self.assertEqual(restored.objective, "objective")
        self.assertNotIn("legacy_field", restored.to_dict())
        self.assertEqual(restored.to_dict()["schema_version"], 1)

    def test_unknown_fields_are_ignored_for_supported_schema_version(self):
        value = ExecutionContext(
            request_id="request-1",
            execution_id="execution-1",
            objective="objective",
        ).to_dict()
        value["future_optional_field"] = {"ignored": True}
        restored = ExecutionContext.from_dict(value)
        self.assertEqual(restored.execution_id, "execution-1")
        self.assertNotIn("future_optional_field", restored.to_dict())

    def test_future_schema_version_is_rejected(self):
        value = ExecutionContext(
            request_id="request-1",
            execution_id="execution-1",
            objective="objective",
        ).to_dict()
        value["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "newer than supported"):
            ExecutionContext.from_dict(value)

    def test_invalid_schema_version_is_rejected(self):
        value = ExecutionContext(
            request_id="request-1",
            execution_id="execution-1",
            objective="objective",
        ).to_dict()
        for schema_version in (True, "1", -1):
            value["schema_version"] = schema_version
            with self.subTest(schema_version=schema_version):
                with self.assertRaises(ValueError):
                    ExecutionContext.from_dict(value)


if __name__ == "__main__":
    unittest.main()
