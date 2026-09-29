from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from server.ensemble_server import EnsembleHTTPServer


class EnsembleServerTest(unittest.TestCase):
    def test_health(self) -> None:
        with self._server() as (server, thread):
            connection = HTTPConnection("127.0.0.1", server.port)
            connection.request("GET", "/api/v1/health")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {"ok": True, "service": "claude-ensemble"})
            connection.close()

    def test_secrets_uses_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secrets = Path(directory) / "secrets.env"
            secrets.write_text(
                "ANTHROPIC_PERSONAL_API_KEY=personal\n"
                "ANTHROPIC_WORK_API_KEY=work\n",
                encoding="utf-8",
            )
            previous = os.environ.get("CLAUDE_ENSEMBLE_SECRETS_FILE")
            os.environ["CLAUDE_ENSEMBLE_SECRETS_FILE"] = str(secrets)
            try:
                with self._server() as (server, thread):
                    connection = HTTPConnection("127.0.0.1", server.port)
                    connection.request(
                        "GET", "/api/v1/secrets/ANTHROPIC_WORK_API_KEY"
                    )
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read())
                    self.assertEqual(payload["value"], "work")
                    connection.close()
            finally:
                if previous is None:
                    os.environ.pop("CLAUDE_ENSEMBLE_SECRETS_FILE", None)
                else:
                    os.environ["CLAUDE_ENSEMBLE_SECRETS_FILE"] = previous

    def _server(self):
        class Context:
            def __init__(self):
                self.server = EnsembleHTTPServer("127.0.0.1", 0)
                # ThreadingHTTPServer needs a concrete port, so use a helper
                # subclass with an ephemeral port.
                import http.server

                application = self.server

                class Handler(http.server.BaseHTTPRequestHandler):
                    def do_GET(self):
                        application.handle(self)

                    def do_POST(self):
                        application.handle(self)

                    def log_message(self, *_args):
                        pass

                self.httpd = http.server.ThreadingHTTPServer(
                    ("127.0.0.1", 0), Handler
                )
                self.server.port = self.httpd.server_address[1]
                self.thread = threading.Thread(
                    target=self.httpd.serve_forever, daemon=True
                )

            def __enter__(self):
                self.thread.start()
                return self.server, self.thread

            def __exit__(self, *_args):
                self.httpd.shutdown()
                self.httpd.server_close()
                self.thread.join(timeout=2)

        return Context()


if __name__ == "__main__":
    unittest.main()
