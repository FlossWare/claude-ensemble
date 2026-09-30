#!/usr/bin/env python3
"""Simple name-based secrets service."""

from __future__ import annotations

import os
import stat
from pathlib import Path

DEFAULT_SECRETS_FILE = "~/.FlossWare/secrets.env"


class SecretsService:
    """Read named secrets from a dotenv-style file without exposing values in logs."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get(
            "CLAUDE_ENSEMBLE_SECRETS_FILE", DEFAULT_SECRETS_FILE
        )
        self.path = Path(configured).expanduser()

    def _open_secure_file(self) -> int:
        """Open the secrets file without allowing pathname replacement races."""
        if os.name != "posix":
            raise PermissionError("secure POSIX file access is unavailable")

        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            raise PermissionError("secure file access requires O_NOFOLLOW")

        try:
            fd = os.open(self.path, os.O_RDONLY | nofollow)
        except OSError as exc:
            raise PermissionError(f"cannot open secrets file securely: {exc}") from exc

        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise PermissionError("secrets file must be a regular file")

            mode = stat.S_IMODE(info.st_mode)
            if mode & 0o077:
                os.fchmod(fd, 0o600)
                info = os.fstat(fd)
                mode = stat.S_IMODE(info.st_mode)

            if mode & 0o077:
                raise PermissionError(
                    f"secrets file has insecure permissions {oct(mode)}"
                )
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _read_lines(self) -> list[str] | None:
        """Read the secrets file through one validated file descriptor."""
        if os.name != "posix":
            if not self.path.exists():
                return None
            return self.path.read_text(encoding="utf-8").splitlines()

        try:
            fd = self._open_secure_file()
        except PermissionError as exc:
            if not self.path.exists():
                return None
            raise exc

        with os.fdopen(fd, encoding="utf-8") as file:
            return file.read().splitlines()

    def get(self, name: str) -> str | None:
        if not name or "=" in name or any(char in name for char in "\r\n"):
            raise ValueError("invalid secret name")

        for line in self._read_lines() or []:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("export "):
                stripped = stripped[7:].lstrip()
            if "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            if key != name:
                continue

            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            elif " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            return value

        return None
