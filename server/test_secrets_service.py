from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from server.secrets_service import SecretsService


class SecretsServiceSecurityTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX file permissions required")
    def test_insecure_permissions_are_tightened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secrets.env"
            path.write_text("TOKEN=value\n", encoding="utf-8")
            path.chmod(0o644)

            self.assertEqual(SecretsService(path).get("TOKEN"), "value")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions required")
    def test_symbolic_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.env"
            target.write_text("TOKEN=value\n", encoding="utf-8")
            link = Path(directory) / "secrets.env"
            link.symlink_to(target)

            with self.assertRaises(PermissionError):
                SecretsService(link).get("TOKEN")


if __name__ == "__main__":
    unittest.main()
