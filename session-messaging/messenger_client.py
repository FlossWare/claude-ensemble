#!/usr/bin/env python3
"""Client for the Claude Ensemble session messaging service."""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Iterator

MAX_MESSAGE_BYTES = 1024 * 1024


def socket_path() -> Path:
    configured = os.environ.get("CLAUDE_MESSENGER_SOCKET")
    if configured:
        return Path(configured)
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "claude-messenger" / "claude-messenger.sock"
    if os.name == "nt":
        return Path.home() / ".cache" / "claude-messenger" / "claude-messenger.sock"
    return Path(f"/run/user/{os.getuid()}/claude-messenger/claude-messenger.sock")


class MessengerClient:
    def __init__(self, path: Path | None = None, *, connect_timeout=2.0, reconnect_delay=0.5):
        self.path = path or socket_path()
        self.connect_timeout = connect_timeout
        self.reconnect_delay = reconnect_delay

    def publish(self, topic: str, data: Any) -> int:
        with self._connect() as client:
            self._send(client, {"op": "publish", "topic": topic, "data": data})
            response = self._receive(client)
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "publish failed"))
            return int(response.get("delivered", 0))

    def subscribe(self, topic: str, *, reconnect: bool = True) -> Iterator[dict]:
        while True:
            try:
                with self._connect() as client:
                    self._send(client, {"op": "subscribe", "topic": topic})
                    response = self._receive(client)
                    if not response.get("ok"):
                        raise RuntimeError(response.get("error", "subscribe failed"))

                    reader = client.makefile("r", encoding="utf-8")
                    try:
                        for line in reader:
                            if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
                                raise RuntimeError("message too large")
                            message = json.loads(line)
                            if isinstance(message, dict) and message.get("topic") == topic:
                                yield message
                    finally:
                        reader.close()
            except (OSError, ConnectionError, TimeoutError, json.JSONDecodeError):
                if not reconnect:
                    raise
                time.sleep(self.reconnect_delay)

    def _connect(self) -> socket.socket:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.connect_timeout)
        client.connect(str(self.path))
        client.settimeout(None)
        return client

    @staticmethod
    def _send(client: socket.socket, request: dict) -> None:
        payload = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
        if len(payload) > MAX_MESSAGE_BYTES:
            raise ValueError("message too large")
        client.sendall(payload)

    @staticmethod
    def _receive(client: socket.socket) -> dict:
        reader = client.makefile("r", encoding="utf-8")
        try:
            line = reader.readline()
        finally:
            reader.close()
        if not line:
            raise ConnectionError("messenger closed connection")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise RuntimeError("invalid messenger response")
        return response
