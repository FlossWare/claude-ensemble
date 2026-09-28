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
