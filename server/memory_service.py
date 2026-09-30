#!/usr/bin/env python3
"""HTTP adapter for the existing Claude Ensemble memory daemon."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

DEFAULT_SOCKET = str(
    Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".cache")))
    / "claude-ensemble"
    / "memory.sock"
)
REQUEST_TIMEOUT = 5.0


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

    def dispatch(
        self,
        method: str,
        parts: list[str],
        body: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        if not parts:
            return 404, {"error": "not found"}

        operation = parts[0]
        if operation == "ping" and method == "GET":
            payload = {"op": "ping"}
        elif operation == "list" and method == "GET":
            payload = {"op": "list"}
        elif operation == "read" and method == "GET" and len(parts) == 2:
            payload = {"op": "read", "name": parts[1]}
        elif operation == "write" and method == "PUT" and len(parts) == 2:
            payload = {"op": "write", "name": parts[1], "content": (body or {}).get("content")}
        elif operation == "append" and method == "POST" and len(parts) == 2:
            payload = {"op": "append", "name": parts[1], "entry": (body or {}).get("entry", {})}
        elif operation in {"search", "search_semantic", "search_hybrid"} and method == "POST":
            payload = {"op": operation, **(body or {})}
        elif operation == "chunk" and method == "GET" and len(parts) == 2:
            payload = {"op": "chunk", "name": parts[1]}
        else:
            return 404, {"error": "not found"}

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
