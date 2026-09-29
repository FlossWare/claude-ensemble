#!/usr/bin/env python3
"""Single HTTP/REST server for Claude Ensemble logical services."""

from __future__ import annotations

import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from server.secrets_service import SecretsService
from server.service_router import ServiceRouter

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
MAX_BODY_SIZE = 16 * 1024 * 1024
KNOWN_SERVICES = frozenset({"memory", "thompson", "learning", "alert", "messages", "secrets"})
NOT_FOUND_BODY = {"error": "not found"}


def service_url(name: str) -> str | None:
    if name not in KNOWN_SERVICES:
        return None
    return os.environ.get(f"ENSEMBLE_{name.upper()}_URL")


class EnsembleHTTPServer:
    """Own the single HTTP server and its local logical service handlers."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.router = ServiceRouter(host=host, port=port)
        self.secrets = SecretsService()

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
                super().log_message(format, *args)

        httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        httpd.daemon_threads = True
        self.port = httpd.server_address[1]
        self.router.port = self.port
        print(f"Claude Ensemble HTTP server listening on http://{self.host}:{self.port}")
        httpd.serve_forever()

    def handle(self, request: BaseHTTPRequestHandler) -> None:
        parsed = urlsplit(request.path)
        if not parsed.path.startswith("/api/v1/"):
            self._json(request, HTTPStatus.NOT_FOUND, NOT_FOUND_BODY)
            return

        parts = parsed.path.split("/")
        if len(parts) < 4:
            self._json(request, HTTPStatus.NOT_FOUND, NOT_FOUND_BODY)
            return

        service = parts[3]
        if service != "health" and service not in KNOWN_SERVICES:
            self._json(request, HTTPStatus.NOT_FOUND, NOT_FOUND_BODY)
            return

        hop_count = self._hop_count(request)
        if hop_count >= 8:
            self._json(request, HTTPStatus.LOOP_DETECTED, {"error": "forwarding hop limit exceeded"})
            return

        if service == "health":
            self._json(request, HTTPStatus.OK, {"ok": True, "service": "claude-ensemble"})
            return

        configured_url = service_url(service)
        if configured_url and not self.router.is_local(configured_url):
            if not self._authorized(request):
                self._json(request, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            if not self.router.is_loopback_url(configured_url) and urlsplit(configured_url).scheme != "https":
                self._json(request, HTTPStatus.BAD_REQUEST, {"error": "remote service URLs must use HTTPS"})
                return
            token = os.environ.get("ENSEMBLE_SERVICE_TOKEN")
            if not token:
                self._json(request, HTTPStatus.SERVICE_UNAVAILABLE, {"error": "service token not configured"})
                return
            try:
                body = self._body(request)
                status, headers, response_body = self.router.forward(
                    base_url=configured_url,
                    method=request.command,
                    path=parsed.path,
                    query=parsed.query,
                    headers=dict(request.headers),
                    body=body,
                    service_token=token,
                    hop_count=hop_count,
                )
            except ValueError as exc:
                self._json(request, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            except ConnectionError:
                self._json(request, HTTPStatus.BAD_GATEWAY, {"error": "service forwarding failed"})
                return
            self._respond(request, status, headers, response_body)
            return

        if service == "secrets":
            if not self._authorized(request):
                self._json(request, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            self._handle_secrets(request, parts[4:])
            return

        self._json(
            request,
            HTTPStatus.NOT_IMPLEMENTED,
            {"error": f"local service not implemented: {service}"},
        )

    @staticmethod
    def _hop_count(request: BaseHTTPRequestHandler) -> int:
        try:
            return int(request.headers.get("X-Claude-Ensemble-Forwarded", "0"))
        except ValueError:
            return 8

    @staticmethod
    def _authorized(request: BaseHTTPRequestHandler) -> bool:
        token = os.environ.get("ENSEMBLE_SERVICE_TOKEN")
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {token}" if token else ""
        return bool(token) and hmac.compare_digest(supplied, expected)

    def _handle_secrets(self, request: BaseHTTPRequestHandler, parts: list[str]) -> None:
        if request.command != "GET" or len(parts) != 1:
            self._json(request, HTTPStatus.NOT_FOUND, NOT_FOUND_BODY)
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

        self._json(request, HTTPStatus.OK, {"name": name, "value": value}, no_store=True)

    @staticmethod
    def _body(request: BaseHTTPRequestHandler) -> bytes:
        if request.headers.get("Transfer-Encoding"):
            raise ValueError("chunked request bodies are not supported")
        try:
            length = int(request.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0:
            raise ValueError("invalid Content-Length")
        if length > MAX_BODY_SIZE:
            raise ValueError("request body too large")
        return request.rfile.read(length)

    @staticmethod
    def _json(
        request: BaseHTTPRequestHandler,
        status: int | HTTPStatus,
        payload: dict,
        *,
        no_store: bool = False,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request.send_response(int(status))
        request.send_header("Content-Type", "application/json")
        if no_store:
            request.send_header("Cache-Control", "no-store")
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
