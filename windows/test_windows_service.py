"""Windows service and IPC integration tests."""

import os
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MESSAGING_DIR = ROOT / "session-messaging"
if str(MESSAGING_DIR) not in sys.path:
    sys.path.insert(0, str(MESSAGING_DIR))


def test_windows_service_definitions_are_complete():
    source = (ROOT / "windows" / "claude_ensemble_service.py").read_text()
    for name in (
        "MemoryService",
        "ThompsonService",
        "LearningService",
        "AlertService",
        "MessengerService",
    ):
        assert f"class {name}" in source


def test_windows_service_targets_exist():
    targets = (
        "memory-service/memory_service.py",
        "thompson-service/thompson_service.py",
        "learning-service/learning_service.py",
        "alert_service/alert_service.py",
        "session-messaging/messenger_service.py",
    )
    for target in targets:
        assert (ROOT / target).is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows-only runtime test")
def test_pywin32_service_imports():
    import win32service  # noqa: F401
    import win32serviceutil  # noqa: F401


@pytest.mark.skipif(os.name != "nt", reason="Windows-only Messenger test")
def test_windows_messenger_endpoint_is_deterministic(monkeypatch):
    import messenger_client
    import messenger_service

    monkeypatch.delenv("CLAUDE_MESSENGER_SOCKET", raising=False)
    monkeypatch.delenv("CLAUDE_MESSENGER_PIPE", raising=False)

    expected = Path(r"\\.\pipe\ClaudeEnsembleMessenger")
    assert messenger_service.socket_path() == expected
    assert messenger_client.socket_path() == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows-only named-pipe test")
def test_windows_messenger_named_pipe_bind_and_connect(tmp_path, monkeypatch):
    import messenger_client
    import messenger_service

    pipe_name = rf"\\.\pipe\ClaudeEnsembleMessengerTest-{os.getpid()}"
    auth_path = tmp_path / "messenger.key"
    auth_path.write_bytes(os.urandom(32))

    monkeypatch.setenv("CLAUDE_MESSENGER_SOCKET", pipe_name)
    monkeypatch.setenv("CLAUDE_MESSENGER_AUTH_FILE", str(auth_path))

    server = messenger_service.MessengerServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = messenger_client.MessengerClient(
        connect_timeout=2.0, reconnect_delay=0.1
    )
    deadline = time.time() + 10
    connected = False
    try:
        while time.time() < deadline:
            try:
                assert client.publish("windows-test", {"ok": True}) == 0
                connected = True
                break
            except (OSError, ConnectionError, TimeoutError):
                time.sleep(0.1)
        assert connected, "Messenger service did not accept a named-pipe connection"
    finally:
        server.stop()
        thread.join(timeout=5)

    assert not thread.is_alive()


@pytest.mark.skipif(os.name != "nt", reason="Windows-only named-pipe test")
def test_windows_messenger_idle_stop_wakes_accept(tmp_path, monkeypatch):
    import messenger_service

    pipe_name = rf"\\.\pipe\ClaudeEnsembleMessengerIdleStop-{os.getpid()}"
    auth_path = tmp_path / "messenger.key"
    auth_path.write_bytes(os.urandom(32))

    monkeypatch.setenv("CLAUDE_MESSENGER_SOCKET", pipe_name)
    monkeypatch.setenv("CLAUDE_MESSENGER_AUTH_FILE", str(auth_path))

    server = messenger_service.MessengerServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        assert server._ready.wait(timeout=5), "Messenger service did not initialize"
        server.stop()
        thread.join(timeout=5)
        assert not thread.is_alive(), "Messenger service did not stop while idle"
    finally:
        server.stop()
        thread.join(timeout=1)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only named-pipe test")
def test_windows_messenger_stop_closes_live_client(tmp_path, monkeypatch):
    from multiprocessing.connection import Client as PipeClient

    import messenger_service

    pipe_name = rf"\\.\pipe\ClaudeEnsembleMessengerStop-{os.getpid()}"
    auth_path = tmp_path / "messenger.key"
    auth_path.write_bytes(os.urandom(32))

    monkeypatch.setenv("CLAUDE_MESSENGER_SOCKET", pipe_name)
    monkeypatch.setenv("CLAUDE_MESSENGER_AUTH_FILE", str(auth_path))
    monkeypatch.setattr(messenger_service, "WINDOWS_CLIENT_IDLE_TIMEOUT", 30.0)

    server = messenger_service.MessengerServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = None
    try:
        assert server._ready.wait(timeout=5), "Messenger service did not initialize"
        deadline = time.time() + 5
        while client is None and time.time() < deadline:
            try:
                client = PipeClient(
                    pipe_name,
                    family="AF_PIPE",
                    authkey=auth_path.read_bytes(),
                )
            except (OSError, ConnectionError):
                time.sleep(0.05)
        assert client is not None, "Messenger service did not accept a client"

        client.send_bytes(
            b'{"op":"subscribe","topic":"windows-shutdown"}'
        )
        assert client.recv_bytes().startswith(b'{"ok":true}')

        started = time.monotonic()
        server.stop()
        thread.join(timeout=3)

        assert not thread.is_alive(), "Messenger service did not stop promptly"
        assert time.monotonic() - started < 3
    finally:
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
        server.stop()
        thread.join(timeout=1)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only named-pipe test")
def test_windows_messenger_reclaims_idle_clients(tmp_path, monkeypatch):
    from multiprocessing.connection import Client as PipeClient

    import messenger_client
    import messenger_service

    pipe_name = rf"\\.\pipe\ClaudeEnsembleMessengerIdle-{os.getpid()}"
    auth_path = tmp_path / "messenger.key"
    auth_path.write_bytes(os.urandom(32))

    monkeypatch.setenv("CLAUDE_MESSENGER_SOCKET", pipe_name)
    monkeypatch.setenv("CLAUDE_MESSENGER_AUTH_FILE", str(auth_path))
    monkeypatch.setattr(messenger_service, "WINDOWS_MAX_CLIENTS", 2)
    monkeypatch.setattr(messenger_service, "WINDOWS_CLIENT_IDLE_TIMEOUT", 0.5)

    server = messenger_service.MessengerServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    idle_clients = []
    try:
        assert server._ready.wait(timeout=5), "Messenger service did not initialize"

        deadline = time.time() + 5
        while len(idle_clients) < 2 and time.time() < deadline:
            try:
                idle_clients.append(
                    PipeClient(
                        pipe_name,
                        family="AF_PIPE",
                        authkey=auth_path.read_bytes(),
                    )
                )
            except (OSError, ConnectionError):
                time.sleep(0.05)

        assert len(idle_clients) == 2, "Messenger did not accept the idle clients"

        time.sleep(0.8)

        client = messenger_client.MessengerClient(
            connect_timeout=2.0, reconnect_delay=0.1
        )
        assert client.publish("windows-idle-recovery", {"ok": True}) == 0
    finally:
        for client in idle_clients:
            try:
                client.close()
            except OSError:
                pass
        server.stop()
        thread.join(timeout=5)

    assert not thread.is_alive()
