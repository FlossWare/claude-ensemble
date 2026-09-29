#!/usr/bin/env python3
"""Small Unix-socket topic pub/sub daemon for Claude Ensemble sessions."""

from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path

MAX_MESSAGE_BYTES = 1024 * 1024


def socket_path() -> Path:
    configured = os.environ.get("CLAUDE_MESSENGER_SOCKET")
    if configured:
        return Path(configured)
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "claude-messenger.sock"
    return Path(f"/run/user/{os.getuid()}/claude-messenger.sock")


class MessengerServer:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or socket_path()
        self._server: socket.socket | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[socket.socket]] = {}

    def serve_forever(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.path))
        os.chmod(self.path, 0o600)
        server.listen()
        server.settimeout(1.0)
        self._server = server

        try:
            while not self._stop.is_set():
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True,
                ).start()
        finally:
            server.close()
            self._close_all_subscribers()
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass

    def _handle_client(self, client: socket.socket) -> None:
        subscriptions: set[str] = set()
        reader = client.makefile("r", encoding="utf-8")
        try:
            for line in reader:
                if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
                    self._send(client, {"ok": False, "error": "message too large"})
                    break
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError("request must be an object")
                    response = self._dispatch(client, request, subscriptions)
                except (ValueError, json.JSONDecodeError) as exc:
                    response = {"ok": False, "error": str(exc)}
                self._send(client, response)
        finally:
            reader.close()
            self._remove_client(client, subscriptions)
            try:
                client.close()
            except OSError:
                pass

    def _dispatch(self, client, request: dict, subscriptions: set[str]) -> dict:
        op = request.get("op")
        topic = request.get("topic")
        if op not in {"subscribe", "unsubscribe", "publish"}:
            return {"ok": False, "error": "unsupported operation"}
        if not isinstance(topic, str) or not topic or len(topic) > 128:
            return {"ok": False, "error": "invalid topic"}

        if op == "subscribe":
            with self._lock:
                self._subscribers.setdefault(topic, set()).add(client)
            subscriptions.add(topic)
            return {"ok": True}

        if op == "unsubscribe":
            with self._lock:
                self._subscribers.get(topic, set()).discard(client)
            subscriptions.discard(topic)
            return {"ok": True}

        if "data" not in request:
            return {"ok": False, "error": "publish requires data"}
        message = {"topic": topic, "data": request["data"]}
        return {"ok": True, "delivered": self._publish(topic, message)}

    def _publish(self, topic: str, message: dict) -> int:
        payload = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        if len(payload) > MAX_MESSAGE_BYTES:
            return 0
        with self._lock:
            clients = list(self._subscribers.get(topic, set()))

        delivered = 0
        stale = []
        for client in clients:
            try:
                client.sendall(payload)
                delivered += 1
            except OSError:
                stale.append(client)
        for client in stale:
            with self._lock:
                self._remove_client_locked(client)
        return delivered

    @staticmethod
    def _send(client: socket.socket, response: dict) -> None:
        payload = (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            client.sendall(payload)
        except OSError:
            pass

    def _remove_client(self, client, subscriptions: set[str]) -> None:
        with self._lock:
            for topic in subscriptions:
                self._subscribers.get(topic, set()).discard(client)
            self._remove_client_locked(client)

    def _remove_client_locked(self, client) -> None:
        empty = []
        for topic, clients in self._subscribers.items():
            clients.discard(client)
            if not clients:
                empty.append(topic)
        for topic in empty:
            self._subscribers.pop(topic, None)

    def _close_all_subscribers(self) -> None:
        with self._lock:
            clients = {c for clients in self._subscribers.values() for c in clients}
            self._subscribers.clear()
        for client in clients:
            try:
                client.close()
            except OSError:
                pass


if __name__ == "__main__":
    MessengerServer().serve_forever()
