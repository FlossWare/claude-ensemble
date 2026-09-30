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

    def _ensure_private_file(self) -> None:
        """Require the secrets file to be private on POSIX systems."""
        if os.name != "posix" or not self.path.exists():
            return
        if self.path.is_symlink():
            raise PermissionError("secrets file must not be a symbolic link")
        try:
            mode = stat.S_IMODE(self.path.stat().st_mode)
            if mode & 0o077:
                os.chmod(self.path, 0o600)
                mode = stat.S_IMODE(self.path.stat().st_mode)
            if mode & 0o077:
                raise PermissionError(
                    f"secrets file has insecure permissions {oct(mode)}"
                )
        except OSError as exc:
            raise PermissionError(f"cannot secure secrets file: {exc}") from exc

    def get(self, name: str) -> str | None:
        if not name or "=" in name or any(char in name for char in "\r\n"):
            raise ValueError("invalid secret name")

        if not self.path.exists():
            return None

        self._ensure_private_file()

        for line in self.path.read_text(encoding="utf-8").splitlines():
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
