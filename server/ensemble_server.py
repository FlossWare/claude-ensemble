#!/usr/bin/env python3
"""Single HTTP/REST server for Claude Ensemble logical services."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from server.secrets_service import SecretsService
from server.service_router import ServiceRouter


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def service_url(name: str) -> str | None:
    return os.environ.get(f"ENSEMBLE_{name.upper()}_URL")


class EnsembleHTTPServer:
    """Own the single HTTP server and its local logical service handlers."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.router = ServiceRouter(host=host, port=port)
        self.secrets = SecretsService()
        self.router.register("secrets", self.secrets)

    def serve_forever(self) -> None:
        application = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "ClaudeEnsemble/1"

            def do_GET(self) -> None:  # noqa: N802
                application.handle(self)

            def do_POST(self) -> None:  # noqa: N802
                application.handle(self)

            def do_PUT(self) -> None:  # noqa: N802
                application.handle(self)

            def do_DELETE(self) -> None:  # noqa: N802
                application.handle(self)

            def log_message(self, format: str, *args: object) -> None:
                # Keep the standard HTTP access log, but never log request bodies.
                super().log_message(format, *args)

        httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        httpd.daemon_threads = True
        print(f"Claude Ensemble HTTP server listening on http://{self.host}:{self.port}")
        httpd.serve_forever()

    def handle(self, request: BaseHTTPRequestHandler) -> None:
        parsed = urlsplit(request.path)
        if not parsed.path.startswith("/api/v1/"):
            self._json(request, HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        parts = parsed.path.split("/")
        if len(parts) < 5:
            self._json(request, HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        service = parts[3]
        configured_url = service_url(service)

        # A remote service is simply another Ensemble REST endpoint.
        if configured_url and not self.router.is_local(configured_url):
            if request.headers.get("X-Claude-Ensemble-Forwarded") == "1":
                self._json(request, HTTPStatus.LOOP_DETECTED, {"error": "forwarding loop"})
                return

            body = self._body(request)
            try:
                status, headers, response_body = self.router.forward(
                    base_url=configured_url,
                    method=request.command,
                    path=parsed.path,
                    query=parsed.query,
                    headers=dict(request.headers),
                    body=body,
                )
            except ConnectionError as exc:
                self._json(request, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
                return

            self._respond(request, status, headers, response_body)
            return

        if service == "health":
            self._json(request, HTTPStatus.OK, {"ok": True, "service": "claude-ensemble"})
            return

        if service == "secrets":
            self._handle_secrets(request, parts[4:])
            return

        self._json(
            request,
            HTTPStatus.NOT_IMPLEMENTED,
            {"error": f"local service not implemented: {service}"},
        )

    def _handle_secrets(self, request: BaseHTTPRequestHandler, parts: list[str]) -> None:
        if request.command != "GET" or len(parts) != 1:
            self._json(request, HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        name = parts[0]
        try:
            value = self.secrets.get(name)
        except ValueError:
            self._json(request, HTTPStatus.BAD_REQUEST, {"error": "invalid secret name"})
            return

        if value is None:
            self._json(request, HTTPStatus.NOT_FOUND, {"error": "secret not found"})
            return

        self._json(request, HTTPStatus.OK, {"name": name, "value": value})

    @staticmethod
    def _body(request: BaseHTTPRequestHandler) -> bytes:
        length = int(request.headers.get("Content-Length", "0"))
        if length < 0 or length > 16 * 1024 * 1024:
            raise ValueError("request body too large")
        return request.rfile.read(length)

    @staticmethod
    def _json(
        request: BaseHTTPRequestHandler, status: int | HTTPStatus, payload: dict
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request.send_response(int(status))
        request.send_header("Content-Type", "application/json")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)

    @staticmethod
    def _respond(
        request: BaseHTTPRequestHandler,
        status: int,
        headers: list[tuple[str, str]],
        body: bytes,
    ) -> None:
        request.send_response(status)
        for key, value in headers:
            if key.lower() not in {"content-length", "content-encoding"}:
                request.send_header(key, value)
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)


def main() -> None:
    host = os.environ.get("ENSEMBLE_HTTP_HOST", DEFAULT_HOST)
    port = int(os.environ.get("ENSEMBLE_HTTP_PORT", str(DEFAULT_PORT)))
    EnsembleHTTPServer(host, port).serve_forever()


if __name__ == "__main__":
    main()
