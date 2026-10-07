#!/usr/bin/env python3
"""Claude Code Markdown synchronization for the Ensemble Memory service."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import select
import struct
import sys
import time
from pathlib import Path
from urllib import error, request

DEFAULT_URL = "http://127.0.0.1:8767"
EXCLUDED_NAMES = {"CHANGELOG.md"}
EVENT_STRUCT = struct.Struct("iIII")


def memory_url() -> str:
    return os.environ.get("FLOSSWARE_MEMORY_URL", DEFAULT_URL).rstrip("/")


def claude_root() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_ROOT", Path.home() / ".claude")).expanduser()


def markdown_files(root: Path) -> list[Path]:
    projects = root / "projects"
    if not projects.is_dir():
        return []
    found: list[Path] = []
    for project in projects.iterdir():
        if not project.is_dir():
            continue
        memory = project / "memory"
        if memory.is_dir():
            found.extend(p for p in memory.rglob("*.md") if p.name not in EXCLUDED_NAMES)
        top = project / "MEMORY.md"
        if top.is_file():
            found.append(top)
    return sorted(set(found))


def project_name(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root / "projects")
        return relative.parts[0] if relative.parts else "unknown"
    except ValueError:
        return "unknown"


def payload(root: Path, path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "source": "claude-code",
        "path": str(path.resolve()),
        "content": content,
        "sha256": digest,
        "metadata": {
            "project": project_name(root, path),
            "kind": "markdown",
            "relative_path": str(path.relative_to(root / "projects")),
        },
    }


def post(path: str, body: dict, timeout: float = 2.0) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        memory_url() + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict) or not value.get("ok"):
        raise RuntimeError(value.get("error", "Memory request failed") if isinstance(value, dict) else "invalid response")
    return value


def sync_once(root: Path) -> int:
    paths = markdown_files(root)
    succeeded = 0
    for path in paths:
        try:
            result = post("/memory/ingest", payload(root, path))
            print(f"{result.get('status', 'ingested')}: {path}")
            succeeded += 1
        except (OSError, ValueError, RuntimeError, error.URLError) as exc:
            print(f"warning: Memory ingest failed for {path}: {exc}", file=sys.stderr)
    try:
        result = post("/memory/reconcile", {"source": "claude-code", "paths": [str(p.resolve()) for p in paths]})
        print(f"reconciled: {result.get('count', 0)} stale document(s)")
    except (OSError, ValueError, RuntimeError, error.URLError) as exc:
        print(f"warning: Memory reconciliation failed: {exc}", file=sys.stderr)
        return 1
    return 0 if succeeded == len(paths) else 1


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    result = {}
    for path in markdown_files(root):
        try:
            stat = path.stat()
            result[str(path)] = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            pass
    return result


def inotify_fd(root: Path) -> int | None:
    if sys.platform != "linux":
        return None
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            return None
        mask = 0x00000100 | 0x00000002 | 0x00000004 | 0x00000008 | 0x00000040 | 0x00000080
        if libc.inotify_add_watch(fd, os.fsencode(str(root / "projects")), mask) < 0:
            os.close(fd)
            return None
        return fd
    except (OSError, AttributeError):
        return None


def watch(root: Path, interval: float) -> int:
    root.mkdir(parents=True, exist_ok=True)
    fd = inotify_fd(root)
    if fd is None:
        print("inotify unavailable; using polling watcher", file=sys.stderr)
        previous = snapshot(root)
        while True:
            time.sleep(interval)
            current = snapshot(root)
            if current != previous:
                sync_once(root)
                previous = current
    else:
        print("watching Claude Code Markdown with inotify")
        try:
            previous = snapshot(root)
            while True:
                ready, _, _ = select.select([fd], [], [], interval)
                if ready:
                    os.read(fd, 65536)
                    current = snapshot(root)
                    if current != previous:
                        sync_once(root)
                        previous = current
                else:
                    current = snapshot(root)
                    if current != previous:
                        sync_once(root)
                        previous = current
        finally:
            os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync", "watch"))
    parser.add_argument("--root", default=None)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    root = Path(args.root).expanduser() if args.root else claude_root()
    if args.command == "sync":
        return sync_once(root)
    return watch(root, args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
