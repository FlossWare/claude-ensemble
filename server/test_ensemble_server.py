from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from server.ensemble_server import EnsembleHTTPServer, MAX_FORWARD_HOPS, REQUEST_TIMEOUT


class EnsembleServerTest(unittest.TestCase):
    def test_health(self) -> None:
        with self._server() as (server, _thread):
            response = self._request(server, "GET", "/api/v1/health")
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {"ok": True, "service": "claude-ensemble"})

    def test_secrets_requires_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secrets = Path(directory) / "secrets.env"
            secrets.write_text("ANTHROPIC_WORK_API_KEY=work\n", encoding="utf-8")
            previous_file = os.environ.get("CLAUDE_ENSEMBLE_SECRETS_FILE")
            previous_token = os.environ.get("ENSEMBLE_SERVICE_TOKEN")
            os.environ["CLAUDE_ENSEMBLE_SECRETS_FILE"] = str(secrets)
            os.environ["ENSEMBLE_SERVICE_TOKEN"] = "test-token"
            try:
                with self._server() as (server, _thread):
                    response = self._request(server, "GET", "/api/v1/secrets/ANTHROPIC_WORK_API_KEY")
                    self.assertEqual(response.status, 401)

                    response = self._request(
                        server,
                        "GET",
                        "/api/v1/secrets/ANTHROPIC_WORK_API_KEY",
                        headers={"Authorization": "Bearer test-token"},
                    )
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read())
                    self.assertEqual(payload["value"], "work")
                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
            finally:
                if previous_file is None:
                    os.environ.pop("CLAUDE_ENSEMBLE_SECRETS_FILE", None)
                else:
                    os.environ["CLAUDE_ENSEMBLE_SECRETS_FILE"] = previous_file
                if previous_token is None:
                    os.environ.pop("ENSEMBLE_SERVICE_TOKEN", None)
                else:
                    os.environ["ENSEMBLE_SERVICE_TOKEN"] = previous_token

    def test_non_loopback_bind_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            EnsembleHTTPServer("0.0.0.0", 0)

    def test_invalid_hop_counts_are_rejected(self) -> None:
        with self._server() as (server, _thread):
            for value in ("-1", str(MAX_FORWARD_HOPS + 1), "not-a-number"):
                response = self._request(
                    server,
                    "GET",
                    "/api/v1/health",
                    headers={"X-Claude-Ensemble-Forwarded": value},
                )
                self.assertEqual(response.status, 400)
                response.read()

    def test_forwarded_secret_response_is_no_store_and_preserves_encoding(self) -> None:
        import http.server

        token = "test-token"
        body = b'{"name":"SECRET","value":"work"}'

        class RemoteHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        remote = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RemoteHandler)
        remote_thread = threading.Thread(target=remote.serve_forever, daemon=True)
        remote_thread.start()
        previous_url = os.environ.get("ENSEMBLE_SECRETS_URL")
        previous_token = os.environ.get("ENSEMBLE_SERVICE_TOKEN")
        os.environ["ENSEMBLE_SECRETS_URL"] = f"http://127.0.0.1:{remote.server_address[1]}"
        os.environ["ENSEMBLE_SERVICE_TOKEN"] = token
        try:
            with self._server() as (server, _thread):
                response = self._request(
                    server,
                    "GET",
                    "/api/v1/secrets/SECRET",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                self.assertEqual(response.getheader("Content-Encoding"), "gzip")
                self.assertEqual(response.read(), body)
        finally:
            if previous_url is None:
                os.environ.pop("ENSEMBLE_SECRETS_URL", None)
            else:
                os.environ["ENSEMBLE_SECRETS_URL"] = previous_url
            if previous_token is None:
                os.environ.pop("ENSEMBLE_SERVICE_TOKEN", None)
            else:
                os.environ["ENSEMBLE_SERVICE_TOKEN"] = previous_token
            remote.shutdown()
            remote.server_close()
            remote_thread.join(timeout=2)

    def test_incomplete_body_is_rejected(self) -> None:
        with self._server() as (server, _thread):
            connection = HTTPConnection("127.0.0.1", server.port, timeout=REQUEST_TIMEOUT)
            connection.putrequest("POST", "/api/v1/memory/test")
            connection.putheader("Authorization", "Bearer test-token")
            connection.putheader("Content-Length", "10")
            connection.endheaders()
            connection.send(b"short")
            connection.close()

    def test_remote_service_forwarding_and_hops(self) -> None:
        import http.server

        token = "test-token"

        seen = {}

        class RemoteHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen["authorization"] = self.headers.get("Authorization")
                seen["forwarded"] = self.headers.get("X-Claude-Ensemble-Forwarded")
                body = json.dumps({"remote": True, "path": self.path}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        remote = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RemoteHandler)
        remote_thread = threading.Thread(target=remote.serve_forever, daemon=True)
        remote_thread.start()
        previous_url = os.environ.get("ENSEMBLE_MEMORY_URL")
        previous_token = os.environ.get("ENSEMBLE_SERVICE_TOKEN")
        os.environ["ENSEMBLE_MEMORY_URL"] = f"http://127.0.0.1:{remote.server_address[1]}"
        os.environ["ENSEMBLE_SERVICE_TOKEN"] = token
        try:
            with self._server() as (server, _thread):
                response = self._request(
                    server,
                    "GET",
                    "/api/v1/memory/echo?x=1",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["remote"])
                self.assertEqual(payload["path"], "/api/v1/memory/echo?x=1")
                self.assertEqual(seen["authorization"], f"Bearer {token}")
                self.assertEqual(seen["forwarded"], "1")
        finally:
            if previous_url is None:
                os.environ.pop("ENSEMBLE_MEMORY_URL", None)
            else:
                os.environ["ENSEMBLE_MEMORY_URL"] = previous_url
            if previous_token is None:
                os.environ.pop("ENSEMBLE_SERVICE_TOKEN", None)
            else:
                os.environ["ENSEMBLE_SERVICE_TOKEN"] = previous_token
            remote.shutdown()
            remote.server_close()
            remote_thread.join(timeout=2)

    @staticmethod
    def _request(server: EnsembleHTTPServer, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None):
        connection = HTTPConnection("127.0.0.1", server.port, timeout=REQUEST_TIMEOUT)
        connection.request(method, path, body=body, headers=headers or {})
        return connection.getresponse()

    def _server(self):
        class Context:
            def __init__(self):
                self.server = EnsembleHTTPServer("127.0.0.1", 0)
                import http.server

                application = self.server

                class Handler(http.server.BaseHTTPRequestHandler):
                    def do_GET(self):
                        application.handle(self)

                    def do_POST(self):
                        application.handle(self)

                    def do_PUT(self):
                        application.handle(self)

                    def do_DELETE(self):
                        application.handle(self)

                    def log_message(self, *_args):
                        pass

                class TimedTestServer(http.server.ThreadingHTTPServer):
                    def get_request(self):
                        connection, client_address = super().get_request()
                        connection.settimeout(REQUEST_TIMEOUT)
                        return connection, client_address

                self.httpd = TimedTestServer(("127.0.0.1", 0), Handler)
                self.server.port = self.httpd.server_address[1]
                self.server.router.port = self.server.port
                self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

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
