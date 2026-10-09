#!/usr/bin/env python3
"""Run pytest-discoverable files independently to isolate integration failures."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "ga_tuning"}
EXCLUDED_FILES = {"learning-service/test_ga_artifact_contract.py"}
PER_TEST_TIMEOUT_SECONDS = 20
PER_FILE_TIMEOUT_SECONDS = 45


def discover_tests() -> list[Path]:
    candidates = set(ROOT.rglob("test_*.py")) | set(ROOT.rglob("*_test.py"))
    return sorted(
        path
        for path in candidates
        if not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.relative_to(ROOT).as_posix() not in EXCLUDED_FILES
        and path.is_file()
    )


def printable_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def main() -> int:
    tests = discover_tests()
    if not tests:
        print("ERROR: no non-GA pytest files discovered", file=sys.stderr)
        return 2

    failures: list[tuple[str, str]] = []
    started = time.monotonic()
    print(f"Discovered {len(tests)} non-GA pytest files.", flush=True)

    for index, path in enumerate(tests, start=1):
        relative = path.relative_to(ROOT).as_posix()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "--import-mode=importlib",
            "-q",
            f"--timeout={PER_TEST_TIMEOUT_SECONDS}",
            relative,
        ]
        print(f"\n=== [{index}/{len(tests)}] {relative} ===", flush=True)
        file_started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=PER_FILE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = printable_output(exc.stdout)
            if output:
                print(output, flush=True)
            elapsed = time.monotonic() - file_started
            print(f"TIMEOUT after {elapsed:.1f}s: {relative}", flush=True)
            failures.append((relative, "timeout"))
            continue

        output = result.stdout or ""
        if output:
            print(output.rstrip(), flush=True)
        elapsed = time.monotonic() - file_started
        if result.returncode:
            print(f"FAIL (exit {result.returncode}, {elapsed:.1f}s): {relative}", flush=True)
            failures.append((relative, f"exit {result.returncode}"))
        else:
            print(f"PASS ({elapsed:.1f}s): {relative}", flush=True)

    print("\n=== Non-GA Python test inventory summary ===")
    print(f"Files: {len(tests)}")
    print(f"Failures/timeouts: {len(failures)}")
    print(f"Elapsed: {time.monotonic() - started:.1f}s")
    for path, reason in failures:
        print(f"FAIL: {path} ({reason})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
