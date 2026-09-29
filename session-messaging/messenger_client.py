#!/usr/bin/env python3
"""Client for the Claude Ensemble session messaging service."""

from __future__ import annotations

import json
import os
import socket
import time
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client as PipeClient
from pathlib import Path
from typing import Any, Iterator

MAX_MESSAGE_BYTES = 1024 * 1024
WINDOWS_PIPE = r"\\.\pipe\ClaudeEnsembleMessenger"


def socket_path() -> Path:
    configured = os.environ.get("CLAUDE_MESSENGER_SOCKET")
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path(
            os.environ.get("CLAUDE_MESSENGER_PIPE", WINDOWS_PIPE)
        )
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "claude-messenger" / "claude-messenger.sock"
    return Path(f"/run/user/{os.getuid()}/claude-messenger/claude-messenger.sock")


def auth_key_path() -> Path:
    configured = os.environ.get("CLAUDE_MESSENGER_AUTH_FILE")
    if configured:
        return Path(configured)
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    return Path(program_data) / "ClaudeEnsemble" / "run" / "messenger.key"


def _auth_key() -> bytes:
    try:
        key = auth_key_path().read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Windows Messenger authentication key not found: {auth_key_path()}"
        ) from exc
    if len(key) < 32:
        raise RuntimeError("Windows Messenger authentication key is too short")
    return key


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

                    if os.name == "nt":
                        while True:
                            message = json.loads(
                                client.recv_bytes().decode("utf-8")
                            )
                            if isinstance(message, dict) and message.get("topic") == topic:
                                yield message
                    else:
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
            except (
                OSError,
                ConnectionError,
                TimeoutError,
                EOFError,
                AuthenticationError,
                json.JSONDecodeError,
            ):
                if not reconnect:
                    raise
                time.sleep(self.reconnect_delay)

    def _connect(self):
        if os.name == "nt":
            return PipeClient(
                str(self.path),
                family="AF_PIPE",
                authkey=_auth_key(),
            )
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.connect_timeout)
        client.connect(str(self.path))
        client.settimeout(None)
        return client

    @staticmethod
    def _send(client, request: dict) -> None:
        payload = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
        if len(payload) > MAX_MESSAGE_BYTES:
            raise ValueError("message too large")
        if os.name == "nt":
            client.send_bytes(payload)
        else:
            client.sendall(payload)

    @staticmethod
    def _receive(client) -> dict:
        if os.name == "nt":
            payload = client.recv_bytes()
            if not payload:
                raise ConnectionError("messenger closed connection")
            line = payload.decode("utf-8")
        else:
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
