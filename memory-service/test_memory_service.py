#!/usr/bin/env python3
"""Tests for the memory service security boundary."""

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution.context import ExecutionContext, ExecutionResult, ExecutionStatus
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
        self.assertEqual(captured["entry"]["result"], "actual")
        self.assertEqual(
            captured["entry"]["execution_context"],
            context.to_dict(),
        )

        restored = ExecutionContext.from_dict(captured["entry"]["execution_context"])
        self.assertEqual(restored, context)


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

                outside = home / "escape.md"
                self.assertFalse(outside.exists())
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()


class MemoryServiceContextTest(unittest.TestCase):
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

                response = send_request(
                    socket_path,
                    {
                        "op": "append",
                        "name": "execution-context",
                        "entry": {"execution_context": child.to_dict()},
                    },
                )
                self.assertEqual(response, {"ok": True})

                entries = send_request(
                    socket_path,
                    {"op": "entries", "name": "execution-context"},
                )
                self.assertEqual(entries["ok"], True)
                restored = ExecutionContext.from_dict(entries["entries"][0]["execution_context"])

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
