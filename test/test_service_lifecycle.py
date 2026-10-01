#!/usr/bin/env python3
"""Verify the baseline systemd service ownership contract."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SERVICES = {
    "memory-service/claude-memory.service.template",
    "thompson-service/claude-thompson.service.template",
    "learning-service/claude-learning.service.template",
    "alert_service/claude-alert.service.template",
    "session-messaging/claude-messenger.service.template",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


for relative_path in EXPECTED_SERVICES:
    path = ROOT / relative_path
    if not path.is_file():
        fail(f"missing service template: {relative_path}")

    text = path.read_text(encoding="utf-8")

    if "[Service]" not in text:
        fail(f"{relative_path}: missing [Service] section")

    if not re.search(r"(?m)^Type=simple\s*$", text):
        fail(f"{relative_path}: service is not Type=simple")

    if not re.search(r"(?m)^ExecStart=.+\S", text):
        fail(f"{relative_path}: missing service-owned ExecStart")

    if re.search(r"(?mi)^ExecStart=.*(?:systemctl|start-stop-daemon)\b", text):
        fail(f"{relative_path}: ExecStart delegates lifecycle to another supervisor")

    if re.search(r"(?mi)^ExecStart=.*(?:ensemble_server|orchestrate)\b", text):
        fail(f"{relative_path}: ExecStart uses an orchestration process")

    if re.search(r"(?mi)\bsystemctl\s+--user\s+(?:start|restart|stop)\b", text):
        fail(f"{relative_path}: template starts/stops sibling services")

learning = (ROOT / "learning-service/claude-learning.service.template").read_text(
    encoding="utf-8"
)
if "After=network.target claude-thompson.service" not in learning:
    fail("Learning must declare ordering after Thompson")
if "Wants=claude-thompson.service" not in learning:
    fail("Learning must declare its Thompson dependency")

for relative_path in EXPECTED_SERVICES:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    if text.count("[Service]") != 1:
        fail(f"{relative_path}: expected exactly one [Service] section")

print("PASS: service lifecycle ownership contract")
