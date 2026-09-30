#!/usr/bin/env python3
"""Single HTTP/REST server for Claude Ensemble logical services."""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import os
import subprocess
import time
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from pathlib import Path

from server.memory_service import MemoryHTTPService
from server.secrets_service import SecretsService
from server.service_router import ServiceRouter
from learning.learning_orchestrator import LearningOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
MAX_BODY_SIZE = 16 * 1024 * 1024
REQUEST_TIMEOUT = 30
MAX_FORWARD_HOPS = 8
KNOWN_SERVICES = frozenset({"memory", "thompson", "learning", "alert", "messages", "secrets", "graph", "decision"})
NOT_FOUND_BODY = {"error": "not found"}


def _is_loopback_bind_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def service_url(name: str) -> str | None:
    if name not in KNOWN_SERVICES:
        return None
    return os.environ.get(f"ENSEMBLE_{name.upper()}_URL")


class EnsembleHTTPServer:
    """Own the single HTTP server and its local logical service handlers."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        if not _is_loopback_bind_host(host):
            raise ValueError("HTTP server must bind to a loopback address unless TLS is provided")
        self.host = host
        self.port = port
        self.router = ServiceRouter(host=host, port=port)
        self.secrets = SecretsService()
        self.memory = MemoryHTTPService()
        self.learning = LearningOrchestrator()
        self.daemon_processes = []

        # Auto-spawn daemon services
        self._spawn_daemon_services()

    def _spawn_daemon_services(self) -> None:
        """Auto-spawn all daemon services on startup with health monitoring."""
        base_dir = Path(__file__).parent.parent
        services = [
            ("graph-service/graph_service.py", "GraphDB"),
            ("learning-service/learning_service.py", "Learning Service"),
            ("memory-service/memory_service.py", "Memory Service"),
        ]

        for script, name in services:
            script_path = base_dir / script
            if not script_path.exists():
                logger.warning(f"{name} not found at {script_path}")
                continue

            try:
                # Start daemon process with output captured
                # Use platform-specific subprocess flags for process isolation
                popen_kwargs = {
                    "cwd": str(base_dir),
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                }
                if sys.platform == "win32":
                    popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    popen_kwargs["start_new_session"] = True

                proc = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    **popen_kwargs
                )
                self.daemon_processes.append((name, proc))
                logger.info(f"{name} started (PID {proc.pid})")

                # Brief health check: ensure process doesn't immediately crash
                time.sleep(1)
                if proc.poll() is not None:
                    # Process exited
                    stdout, stderr = proc.communicate()
                    logger.error(f"{name} exited immediately")
                    if stderr:
                        stderr_text = stderr.decode()[:200]
                        logger.error(f"{name} error output: {stderr_text}")
                    self.daemon_processes.remove((name, proc))
                    continue

            except Exception as e:
                logger.error(f"Failed to start {name}: {e}", exc_info=True)

    def _monitor_daemon_processes(self) -> None:
        """Periodic health check of daemon processes."""
        for name, proc in self.daemon_processes:
            if proc.poll() is not None:
                logger.warning(f"{name} (PID {proc.pid}) crashed")
                # Could implement restart logic here

    def _stop_daemon_services(self) -> None:
        """Stop all daemon services on shutdown with graceful timeout + kill fallback."""
        for name, proc in list(self.daemon_processes):
            try:
                # Graceful termination with timeout
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                    logger.info(f"{name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if graceful timeout exceeded
                    logger.warning(f"{name} not responding to SIGTERM, killing...")
                    proc.kill()
                    proc.wait(timeout=1)
                    logger.info(f"{name} killed")
            except Exception as e:
                logger.warning(f"Error stopping {name}: {e}", exc_info=True)

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

        class TimedThreadingHTTPServer(ThreadingHTTPServer):
            def get_request(self):
                connection, client_address = super().get_request()
                connection.settimeout(REQUEST_TIMEOUT)
                return connection, client_address

        try:
            httpd = TimedThreadingHTTPServer((self.host, self.port), Handler)
        except OSError as e:
            logger.error(f"Failed to bind to {self.host}:{self.port} - {e}")
            logger.error(f"Port may already be in use. Check: lsof -i :{self.port} or netstat")
            self._stop_daemon_services()
            sys.exit(1)

        httpd.daemon_threads = True
        self.port = httpd.server_address[1]
        self.router.port = self.port
        logger.info(f"Claude Ensemble HTTP server listening on http://{self.host}:{self.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutdown requested via keyboard interrupt")
            self._stop_daemon_services()
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            self._stop_daemon_services()
            raise

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

        try:
            hop_count = self._hop_count(request)
        except ValueError as exc:
            self._json(request, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if hop_count >= MAX_FORWARD_HOPS:
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
            self.router.validate_url(configured_url)
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
            except TimeoutError:
                self._json(request, HTTPStatus.REQUEST_TIMEOUT, {"error": "request body timed out"})
                return
            except ConnectionError:
                self._json(request, HTTPStatus.BAD_GATEWAY, {"error": "service forwarding failed"})
                return
            self._respond(request, status, headers, response_body, no_store=service == "secrets")
            return

        if service == "memory":
            if not self._authorized(request):
                self._json(request, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            try:
                body = None
                if request.command in {"POST", "PUT"}:
                    raw = self._body(request)
                    body = json.loads(raw.decode("utf-8")) if raw else {}
                    if not isinstance(body, dict):
                        raise ValueError("request body must be a JSON object")
                status, payload = self.memory.dispatch(
                    request.command, parts[4:], body
                )
            except json.JSONDecodeError:
                self._json(request, HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                return
            except ValueError as exc:
                self._json(request, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(request, status, payload)
            return

        if service == "secrets":
            if not self._authorized(request):
                self._json(request, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            self._handle_secrets(request, parts[4:])
            return

        if service == "learning":
            if not self._authorized(request):
                self._json(request, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            self._handle_learning(request, parts[4:])
            return

        self._json(
            request,
            HTTPStatus.NOT_IMPLEMENTED,
            {"error": f"local service not implemented: {service}"},
        )

    @staticmethod
    def _hop_count(request: BaseHTTPRequestHandler) -> int:
        raw = request.headers.get("X-Claude-Ensemble-Forwarded", "0")
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError("invalid forwarding hop count") from exc
        if value < 0 or value > MAX_FORWARD_HOPS:
            raise ValueError("invalid forwarding hop count")
        return value

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
        except PermissionError:
            self._json(request, HTTPStatus.SERVICE_UNAVAILABLE, {"error": "secrets store is not securely configured"})
            return

        if value is None:
            self._json(request, HTTPStatus.NOT_FOUND, {"error": "secret not found"})
            return

        self._json(request, HTTPStatus.OK, {"name": name, "value": value}, no_store=True)

    def _handle_learning(self, request: BaseHTTPRequestHandler, parts: list[str]) -> None:
        try:
            body = None
            if request.command in {"POST", "PUT"}:
                raw = self._body(request)
                body = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(body, dict):
                    raise ValueError("request body must be a JSON object")

            if len(parts) == 0:
                self._json(request, HTTPStatus.NOT_FOUND, NOT_FOUND_BODY)
                return

            # Route to endpoint handler
            endpoint = parts[0]

            if endpoint == "sync-outcomes" and request.command == "POST":
                result = self.learning.handle_sync_request(body)
                self._json(request, HTTPStatus.OK, result)
                return

            if endpoint == "status" and request.command == "GET":
                result = self.learning.handle_status_request()
                self._json(request, HTTPStatus.OK, result)
                return

            if endpoint == "graph" and len(parts) >= 2:
                if parts[1] == "query" and request.command == "POST":
                    result = self.learning.handle_graph_query(body)
                    self._json(request, HTTPStatus.OK, result)
                    return

            if endpoint == "thompson" and len(parts) >= 2:
                if parts[1] == "query" and request.command == "POST":
                    result = self.learning.handle_thompson_query(body)
                    self._json(request, HTTPStatus.OK, result)
                    return

            self._json(request, HTTPStatus.NOT_FOUND, NOT_FOUND_BODY)

        except json.JSONDecodeError:
            self._json(request, HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
        except ValueError as exc:
            self._json(request, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

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
        body = request.rfile.read(length)
        if len(body) != length:
            raise ValueError("incomplete request body")
        return body

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
        *,
        no_store: bool = False,
    ) -> None:
        request.send_response(status)
        for key, value in headers:
            if key.lower() not in {"content-length", "cache-control"}:
                request.send_header(key, value)
        if no_store:
            request.send_header("Cache-Control", "no-store")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)


def _configured_port() -> int:
    raw = os.environ.get("ENSEMBLE_HTTP_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid ENSEMBLE_HTTP_PORT: {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid ENSEMBLE_HTTP_PORT: {port}; expected 1-65535")
    return port


def main() -> None:
    host = os.environ.get("ENSEMBLE_HTTP_HOST", DEFAULT_HOST)
    port = _configured_port()
    server = EnsembleHTTPServer(host, port)
    try:
        server.serve_forever()
    finally:
        # Ensure daemons are stopped on any exit path (KeyboardInterrupt, exception, etc.)
        server._stop_daemon_services()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception:
        # Exception already logged and daemons stopped in main's finally block
        sys.exit(1)
