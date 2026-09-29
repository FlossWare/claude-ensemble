"""Static Windows service integration tests."""

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


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
