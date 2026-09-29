#!/usr/bin/env python3
"""Local topic pub/sub daemon for Claude Ensemble sessions."""

from __future__ import annotations

import json
import os
import socket
import stat
import threading
from multiprocessing.connection import Client as PipeClient
from multiprocessing.connection import Listener
from pathlib import Path

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


class MessengerServer:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or socket_path()
        self._server = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._subscribers: dict[str, set] = {}

    def serve_forever(self) -> None:
        if os.name == "nt":
            self._serve_windows()
        else:
            self._serve_posix()

    def _serve_windows(self) -> None:
        server = Listener(
            str(self.path),
            family="AF_PIPE",
            authkey=_auth_key(),
        )
        self._server = server
        self._ready.set()
        try:
            while not self._stop.is_set():
                try:
                    client = server.accept()
                except (OSError, EOFError):
                    if self._stop.is_set():
                        break
                    raise
                threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True,
                ).start()
        finally:
            try:
                server.close()
            except OSError:
                pass
            self._close_all_subscribers()

    def _serve_posix(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self._remove_stale_socket()

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.path))
        os.chmod(self.path, 0o600)
        server.listen()
        server.settimeout(1.0)
        self._server = server
        self._ready.set()

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
            self._remove_stale_socket()

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            if os.name == "nt":
                # Listener.accept() blocks in a Windows named-pipe wait that
                # cannot reliably be interrupted by Listener.close() from
                # another thread. A local authenticated connection wakes the
                # pending accept so the serving loop can observe _stop.
                threading.Thread(
                    target=self._wake_windows_accept,
                    daemon=True,
                ).start()
            else:
                try:
                    self._server.close()
                except OSError:
                    pass

    def _wake_windows_accept(self) -> None:
        import time

        expires = time.monotonic() + 2.0
        while time.monotonic() < expires:
            try:
                client = PipeClient(
                    str(self.path),
                    family="AF_PIPE",
                    authkey=_auth_key(),
                )
                client.close()
                return
            except (OSError, EOFError, ConnectionError):
                time.sleep(0.05)

    def _remove_stale_socket(self) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return

        if info.st_uid != os.getuid() or not stat.S_ISSOCK(info.st_mode):
            raise RuntimeError(
                f"refusing to remove unexpected socket path: {self.path}"
            )

        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _handle_client(self, client) -> None:
        subscriptions: set[str] = set()
        try:
            if os.name == "nt":
                while True:
                    try:
                        payload = client.recv_bytes()
                    except EOFError:
                        break
                    if len(payload) > MAX_MESSAGE_BYTES:
                        self._send(client, {"ok": False, "error": "message too large"})
                        break
                    response = self._process_payload(
                        client, payload, subscriptions
                    )
                    self._send(client, response)
            else:
                reader = client.makefile("r", encoding="utf-8")
                try:
                    for line in reader:
                        if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
                            self._send(client, {"ok": False, "error": "message too large"})
                            break
                        response = self._process_payload(
                            client, line.encode("utf-8"), subscriptions
                        )
                        self._send(client, response)
                finally:
                    reader.close()
        finally:
            self._remove_client(client, subscriptions)
            try:
                client.close()
            except OSError:
                pass

    def _process_payload(self, client, payload: bytes, subscriptions: set[str]) -> dict:
        try:
            request = json.loads(payload.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            return self._dispatch(client, request, subscriptions)
        except (ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}

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
                self._send_payload(client, payload)
                delivered += 1
            except (OSError, EOFError):
                stale.append(client)
        for client in stale:
            with self._lock:
                self._remove_client_locked(client)
        return delivered

    def _send(self, client, response: dict) -> None:
        payload = (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
        self._send_payload(client, payload)

    @staticmethod
    def _send_payload(client, payload: bytes) -> None:
        if os.name == "nt":
            client.send_bytes(payload)
        else:
            client.sendall(payload)

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
            clients = {
                client
                for clients in self._subscribers.values()
                for client in clients
            }
            self._subscribers.clear()
        for client in clients:
            try:
                client.close()
            except OSError:
                pass


if __name__ == "__main__":
    MessengerServer().serve_forever()
