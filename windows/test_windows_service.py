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


@pytest.mark.skipif(os.name != "nt", reason="Windows-only AF_UNIX test")
def test_windows_messenger_default_path_is_shared(monkeypatch):
    import messenger_client
    import messenger_service

    monkeypatch.delenv("CLAUDE_MESSENGER_SOCKET", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    expected = (
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        / "ClaudeEnsemble"
        / "run"
        / "claude-messenger.sock"
    )
    assert messenger_service.socket_path() == expected
    assert messenger_client.socket_path() == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows-only AF_UNIX test")
def test_windows_messenger_bind_and_connect(tmp_path, monkeypatch):
    import messenger_client
    import messenger_service

    socket_path = tmp_path / "claude-messenger.sock"
    monkeypatch.setenv("CLAUDE_MESSENGER_SOCKET", str(socket_path))

    server = messenger_service.MessengerServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline and not socket_path.exists():
        time.sleep(0.05)

    try:
        assert socket_path.exists(), "Messenger service did not create AF_UNIX socket"
        client = messenger_client.MessengerClient(
            connect_timeout=2.0, reconnect_delay=0.1
        )
        assert client.publish("windows-test", {"ok": True}) == 0
    finally:
        server.stop()
        thread.join(timeout=2)

    assert not thread.is_alive()
