#!/usr/bin/env python3
"""Verify Linux service installers render valid units from a clean checkout."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SERVICES = (
    ("memory-service", "claude-memory.service"),
    ("thompson-service", "claude-thompson.service"),
    ("learning-service", "claude-learning.service"),
    ("alert_service", "claude-alert.service"),
    ("session-messaging", "claude-messenger.service"),
    ("graph-service", "claude-graph.service"),
)


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / "home"
    bin_dir = Path(tmp) / "bin"
    home.mkdir()
    bin_dir.mkdir()

    fake_systemctl = bin_dir / "systemctl"
    fake_systemctl.write_text(
        '''#!/usr/bin/env bash
if [[ "$*" == *"is-active"* ]]; then exit 0; fi
exit 0
''',
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    for service_dir, service_name in SERVICES:
        script = ROOT / service_dir / "install.sh"
        if not script.is_file():
            fail(f"missing installer: {script}")

        result = subprocess.run(
            ["bash", str(script)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            fail(
                f"{script} failed with exit {result.returncode}: "
                f"{result.stdout}\n{result.stderr}"
            )

        installed = home / ".config/systemd/user" / service_name
        if not installed.is_file():
            fail(f"{script} did not install {installed}")

        text = installed.read_text(encoding="utf-8")
        if "%REPO_PATH%" in text:
            fail(f"{installed} still contains %REPO_PATH%")
        if "[Service]" not in text or "ExecStart=" not in text:
            fail(f"{installed} is not a usable systemd unit")
        if "Type=simple" not in text:
            fail(f"{installed} is not Type=simple")

        exec_line = next(
            line for line in text.splitlines() if line.startswith("ExecStart=")
        )
        exec_tokens = shlex.split(exec_line.split("=", 1)[1])
        executable = next((token for token in reversed(exec_tokens) if token.endswith(".py")), None)
        if executable is None or not Path(executable).is_file():
            fail(f"{installed} ExecStart does not reference a repository Python executable: {exec_line}")

if not (ROOT / "toolkit-models.yaml.default").is_file():
    fail("missing toolkit-models.yaml.default")

print("PASS: Linux service installers render valid systemd units")
