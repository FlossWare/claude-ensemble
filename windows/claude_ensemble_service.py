"""Windows Service Control Manager integration for Claude Ensemble.

This module keeps Windows service lifecycle concerns outside the Ensemble
application services. Each Windows service hosts the existing Python daemon
and lets the Windows Service Control Manager handle startup, shutdown,
dependencies, and recovery.
"""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys
import time

import servicemanager
import win32event
import win32service
import win32serviceutil


REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICE_LOG_DIR = Path(os.environ.get("PROGRAMDATA", REPO_ROOT)) / "ClaudeEnsemble" / "logs"


class EnsembleWindowsService(win32serviceutil.ServiceFramework):
    """Base SCM service that hosts one Claude Ensemble daemon."""

    target_script: str = ""
    _svc_deps_: tuple[str, ...] = ()
    restart_delay_seconds = 10

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen | None = None

    @property
    def repo_root(self) -> Path:
        configured = win32serviceutil.GetServiceCustomOption(
            self._svc_name_, "RepoRoot", str(REPO_ROOT)
        )
        return Path(configured)

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env["ENSEMBLE_REPO_ROOT"] = str(self.repo_root)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _log_path(self) -> Path:
        SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return SERVICE_LOG_DIR / f"{self._svc_name_}.log"

    def _start_process(self) -> subprocess.Popen:
        script = self.repo_root / self.target_script
        if not script.is_file():
            raise FileNotFoundError(f"Service script not found: {script}")

        log_file = self._log_path().open("a", encoding="utf-8")
        return subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(self.repo_root),
            env=self._environment(),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def SvcDoRun(self):
        servicemanager.LogInfoMsg(
            f"{self._svc_display_name_} starting from {self.repo_root}"
        )

        while True:
            if win32event.WaitForSingleObject(self.stop_event, 0) == win32event.WAIT_OBJECT_0:
                break

            try:
                self.process = self._start_process()
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            except Exception as exc:
                servicemanager.LogErrorMsg(
                    f"{self._svc_display_name_} failed to start: {exc}"
                )
                time.sleep(self.restart_delay_seconds)
                continue

            while self.process.poll() is None:
                if (
                    win32event.WaitForSingleObject(self.stop_event, 1000)
                    == win32event.WAIT_OBJECT_0
                ):
                    return

            exit_code = self.process.returncode
            if win32event.WaitForSingleObject(self.stop_event, 0) == win32event.WAIT_OBJECT_0:
                break

            servicemanager.LogWarningMsg(
                f"{self._svc_display_name_} exited with code {exit_code}; restarting"
            )
            time.sleep(self.restart_delay_seconds)


class MemoryService(EnsembleWindowsService):
    _svc_name_ = "ClaudeEnsembleMemory"
    _svc_display_name_ = "Claude Ensemble Memory Service"
    _svc_description_ = "Claude Ensemble shared memory service."
    target_script = "memory-service/memory_service.py"


class ThompsonService(EnsembleWindowsService):
    _svc_name_ = "ClaudeEnsembleThompson"
    _svc_display_name_ = "Claude Ensemble Thompson Service"
    _svc_description_ = "Claude Ensemble Thompson Sampling model router."
    target_script = "thompson-service/thompson_service.py"


class LearningService(EnsembleWindowsService):
    _svc_name_ = "ClaudeEnsembleLearning"
    _svc_display_name_ = "Claude Ensemble Learning Service"
    _svc_description_ = "Claude Ensemble learning and outcome service."
    target_script = "learning-service/learning_service.py"
    _svc_deps_ = ("ClaudeEnsembleThompson",)


class AlertService(EnsembleWindowsService):
    _svc_name_ = "ClaudeEnsembleAlert"
    _svc_display_name_ = "Claude Ensemble Alert Service"
    _svc_description_ = "Claude Ensemble alert and anomaly monitoring service."
    target_script = "alert_service/alert_service.py"
    _svc_deps_ = ("ClaudeEnsembleLearning",)


class MessengerService(EnsembleWindowsService):
    _svc_name_ = "ClaudeEnsembleMessenger"
    _svc_display_name_ = "Claude Ensemble Session Messaging Service"
    _svc_description_ = "Claude Ensemble inter-session messaging service."
    target_script = "session-messaging/messenger_service.py"


SERVICES = (
    MemoryService,
    ThompsonService,
    LearningService,
    AlertService,
    MessengerService,
)


def _configure_recovery(service_name: str) -> None:
    """Ask SCM to restart a failed service, analogous to systemd Restart=always."""
    scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_ALL_ACCESS
    )
    try:
        service = win32service.OpenService(
            scm, service_name, win32service.SERVICE_ALL_ACCESS
        )
        try:
            win32service.ChangeServiceConfig2(
                service,
                win32service.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG,
                True,
            )
            win32service.ChangeServiceConfig2(
                service,
                win32service.SERVICE_CONFIG_FAILURE_ACTIONS,
                {
                    "ResetPeriod": 86400,
                    "RebootMsg": "",
                    "Command": "",
                    "Actions": [
                        (win32service.SC_ACTION_RESTART, 10000),
                        (win32service.SC_ACTION_RESTART, 10000),
                        (win32service.SC_ACTION_RESTART, 30000),
                    ],
                },
            )
        finally:
            win32service.CloseServiceHandle(service)
    finally:
        win32service.CloseServiceHandle(scm)


def install_services(username: str | None) -> None:
    password = None
    if username:
        password = getpass.getpass(f"Password for {username}: ")

    for cls in SERVICES:
        try:
            win32serviceutil.StopService(cls._svc_name_)
        except win32service.error:
            pass
        try:
            win32serviceutil.RemoveService(cls._svc_name_)
        except win32service.error:
            pass

        win32serviceutil.InstallService(
            win32serviceutil.GetServiceClassString(cls),
            cls._svc_name_,
            cls._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            serviceDeps=cls._svc_deps_,
            userName=username,
            password=password,
            description=cls._svc_description_,
        )
        win32serviceutil.SetServiceCustomOption(
            cls._svc_name_, "RepoRoot", str(REPO_ROOT)
        )
        _configure_recovery(cls._svc_name_)
        print(f"Installed {cls._svc_name_}")


def remove_services() -> None:
    for cls in reversed(SERVICES):
        try:
            win32serviceutil.StopService(cls._svc_name_)
        except win32service.error:
            pass
        try:
            win32serviceutil.RemoveService(cls._svc_name_)
            print(f"Removed {cls._svc_name_}")
        except win32service.error:
            pass


def start_services() -> None:
    for cls in SERVICES:
        win32serviceutil.StartService(cls._svc_name_)
        print(f"Started {cls._svc_name_}")


def stop_services() -> None:
    for cls in reversed(SERVICES):
        try:
            win32serviceutil.StopService(cls._svc_name_)
            print(f"Stopped {cls._svc_name_}")
        except win32service.error:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Claude Ensemble Windows services")
    parser.add_argument("command", choices=("install", "remove", "start", "stop"))
    parser.add_argument(
        "--username",
        help="Windows account for the services. Use DOMAIN\\\\user or .\\\\user.",
    )
    args = parser.parse_args()

    if args.command == "install":
        install_services(args.username)
        start_services()
    elif args.command == "remove":
        remove_services()
    elif args.command == "start":
        start_services()
    else:
        stop_services()


if __name__ == "__main__":
    main()
