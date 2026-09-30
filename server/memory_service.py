#!/usr/bin/env python3
"""HTTP adapter for the existing Claude Ensemble memory daemon."""

from __future__ import annotations

import json
import os
import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import unquote

DEFAULT_SOCKET = str(
    Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".cache")))
    / "claude-ensemble"
    / "memory.sock"
)
REQUEST_TIMEOUT = 5.0
MEMORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class MemoryHTTPService:
    """Translate REST operations into the existing memory daemon protocol."""

    def __init__(self, socket_path: str | None = None) -> None:
        self.socket_path = socket_path or os.environ.get(
            "ENSEMBLE_MEMORY_SOCKET", DEFAULT_SOCKET
        )

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = (json.dumps(payload) + "\n").encode("utf-8")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(REQUEST_TIMEOUT)
                sock.connect(self.socket_path)
                sock.sendall(data)
                response = bytearray()
                while b"\n" not in response:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response.extend(chunk)
                if not response:
                    raise ConnectionError("memory service returned no response")
                result = json.loads(bytes(response).decode("utf-8").strip())
        except (OSError, TimeoutError) as exc:
            raise ConnectionError("memory service unavailable") from exc
        except json.JSONDecodeError as exc:
            raise ConnectionError("memory service returned invalid JSON") from exc

        if not isinstance(result, dict):
            raise ConnectionError("memory service returned an invalid response")
        return result

    @staticmethod
    def _memory_name(raw_name: str) -> str:
        """Decode and validate a memory name before crossing the socket boundary."""
        name = unquote(raw_name)
        if (
            not name
            or name in {".", ".."}
            or not MEMORY_NAME_PATTERN.fullmatch(name)
        ):
            raise ValueError("invalid memory name")
        return name

    def dispatch(
        self,
        method: str,
        parts: list[str],
        body: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        if not parts:
            return 404, {"error": "not found"}

        operation = parts[0]
        try:
            if operation == "ping" and method == "GET":
                payload = {"op": "ping"}
            elif operation == "list" and method == "GET":
                payload = {"op": "list"}
            elif operation == "read" and method == "GET" and len(parts) == 2:
                payload = {"op": "read", "name": self._memory_name(parts[1])}
            elif operation == "write" and method == "PUT" and len(parts) == 2:
                content = (body or {}).get("content")
                if not isinstance(content, str):
                    return 400, {"error": "content must be a string"}
                payload = {
                    "op": "write",
                    "name": self._memory_name(parts[1]),
                    "content": content,
                }
            elif operation == "append" and method == "POST" and len(parts) == 2:
                payload = {
                    "op": "append",
                    "name": self._memory_name(parts[1]),
                    "entry": (body or {}).get("entry", {}),
                }
            elif operation in {"search", "search_semantic", "search_hybrid"} and method == "POST":
                payload = {**(body or {}), "op": operation}
            elif operation == "chunk" and method == "GET" and len(parts) == 2:
                payload = {"op": "chunk", "name": self._memory_name(parts[1])}
            else:
                return 404, {"error": "not found"}
        except ValueError as exc:
            return 400, {"error": str(exc)}

        try:
            result = self.request(payload)
        except ConnectionError as exc:
            return 503, {"error": str(exc)}

        if not result.get("ok", False):
            error = result.get("error", "memory operation failed")
            if operation == "read" and error == "memory not found":
                return 404, {"error": error}
            return 400, {"error": error}

        return 200, result
