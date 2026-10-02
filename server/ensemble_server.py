#!/usr/bin/env python3
"""Canonical Ensemble REST boundary.

The gateway is the single client-facing REST server. Services remain
independently deployable and are integrated through HTTP/JSON only.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

LOG = logging.getLogger(__name__)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
API_PREFIX = "/api/v1"
SERVICE_URLS = {
    "graph": lambda: os.environ.get("ENSEMBLE_GRAPH_URL", "http://127.0.0.1:8766"),
    "memory": lambda: os.environ.get("ENSEMBLE_MEMORY_URL", "http://127.0.0.1:8767"),
    "learning": lambda: os.environ.get("ENSEMBLE_LEARNING_URL"),
    "arbitration": lambda: os.environ.get("ENSEMBLE_ARBITRATION_URL"),
    "thompson": lambda: os.environ.get("ENSEMBLE_THOMPSON_URL"),
}

def _json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > 16 * 1024 * 1024:
        raise ValueError("request body must be between 1 byte and 16 MiB")
    value = json.loads(handler.rfile.read(length).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request body must be a JSON object")
    return value

def _send(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

class ServiceUnavailable(RuntimeError):
    pass

def _service_url(service: str) -> str | None:
    factory = SERVICE_URLS.get(service)
    return factory() if factory else None

def _forward(service: str, method: str, path: str, body: bytes | None) -> tuple[int, bytes]:
    base = _service_url(service)
    if not base:
        raise ServiceUnavailable(f"{service} service is not configured")
    request = urllib.request.Request(base.rstrip("/") + path, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ServiceUnavailable(f"{service} service unavailable: {exc}") from exc

class EnsembleApplication:
    """Single REST boundary over independently owned services."""
    def __init__(self, graph_url: str | None = None, memory_url: str | None = None):
        if graph_url is not None:
            os.environ["ENSEMBLE_GRAPH_URL"] = graph_url
        if memory_url is not None:
            os.environ["ENSEMBLE_MEMORY_URL"] = memory_url
        learning_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "learning"))
        if learning_dir not in sys.path:
            sys.path.insert(0, learning_dir)
        from learning.decision_support_api import DecisionSupportAPI
        self.decision = DecisionSupportAPI()
        # Replace the historical monolithic-server dependency with explicit
        # service REST endpoints. The implementations remain unchanged.
        graph = SERVICE_URLS["graph"]()
        memory = SERVICE_URLS["memory"]()
        self.decision.analytics.graph_service_url = graph
        self.decision.analytics.memory_service_url = memory
        self.decision.advisor.analytics.graph_service_url = graph
        self.decision.advisor.analytics.memory_service_url = memory
        self.decision.diagnostics.graph_service_url = graph
        self.decision.diagnostics.memory_service_url = memory

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlsplit(handler.path)
        if not parsed.path.startswith(API_PREFIX + "/"):
            _send(handler, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        route = parsed.path[len(API_PREFIX) + 1:]
        parts = route.split("/", 1)
        service = parts[0]
        remainder = "/" + parts[1] if len(parts) == 2 else "/"
        if service == "health":
            _send(handler, HTTPStatus.OK, {"ok": True, "service": "claude-ensemble"})
            return
        try:
            if service == "decision":
                self._handle_decision(handler, remainder)
                return
            if service not in SERVICE_URLS:
                _send(handler, HTTPStatus.NOT_FOUND, {"ok": False, "error": "service not found"})
                return
            body = None
            if handler.command in {"POST", "PUT", "PATCH"}:
                length = int(handler.headers.get("Content-Length", "0"))
                body = handler.rfile.read(length)
            status, response = _forward(service, handler.command, remainder, body)
            handler.send_response(status)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(response)))
            handler.end_headers()
            handler.wfile.write(response)
        except ValueError as exc:
            _send(handler, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except ServiceUnavailable as exc:
            _send(handler, HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
        except Exception:
            LOG.exception("REST request failed")
            _send(handler, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal server error"})

    def _handle_decision(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        body = _json_body(handler) if handler.command == "POST" else {}
        routes = {
            "/recommend": self.decision.handle_recommend,
            "/advisor/models": self.decision.handle_recommend_models,
            "/advisor/phases": self.decision.handle_recommend_phases,
            "/advisor/cost": self.decision.handle_estimate_cost,
            "/analytics/best-models": self.decision.handle_best_models,
            "/analytics/tradeoff": self.decision.handle_cost_quality_tradeoff,
            "/analytics/failure": self.decision.handle_failure_analysis,
            "/analytics/scope-costs": lambda _: self.decision.handle_scope_costs(),
            "/query/semantic": self.decision.handle_semantic_search,
            "/query/graph": self.decision.handle_graph_traversal,
            "/query/patterns": self.decision.handle_model_patterns,
            "/query/problems": lambda _: self.decision.handle_problematic_tasks(),
            "/query/outliers": self.decision.handle_cost_outliers,
            "/query/trend": self.decision.handle_trend,
        }
        fn = routes.get(path)
        if fn is None:
            _send(handler, HTTPStatus.NOT_FOUND, {"ok": False, "error": "decision endpoint not found"})
            return
        get_routes = {"/analytics/scope-costs", "/query/problems", "/query/outliers"}
        if handler.command == "GET" and path not in get_routes:
            _send(handler, HTTPStatus.METHOD_NOT_ALLOWED, {"ok": False, "error": "method not allowed"})
            return
        if handler.command == "POST" and path in get_routes:
            _send(handler, HTTPStatus.METHOD_NOT_ALLOWED, {"ok": False, "error": "method not allowed"})
            return
        required = {
            "/recommend": ("task_type",), "/advisor/models": ("task_type",),
            "/advisor/phases": ("task_type", "scope"), "/advisor/cost": ("models", "task_type"),
            "/analytics/best-models": ("task_type",), "/analytics/tradeoff": ("task_type",),
            "/analytics/failure": ("task_type",), "/query/semantic": ("query",),
            "/query/graph": ("start",), "/query/patterns": ("model",), "/query/trend": ("task_type",),
        }
        missing = [key for key in required.get(path, ()) if not body.get(key)]
        if missing:
            _send(handler, HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"missing required field(s): {', '.join(missing)}"})
            return
        result = fn(body)
        _send(handler, HTTPStatus.OK if result.get("ok") else HTTPStatus.SERVICE_UNAVAILABLE, result)

def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, **kwargs: Any) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Ensemble REST server must bind to loopback")
    server = ThreadingHTTPServer((host, port), EnsembleRequestHandler)
    server.application = EnsembleApplication(**kwargs)  # type: ignore[attr-defined]
    return server

class EnsembleRequestHandler(BaseHTTPRequestHandler):
    server_version = "ClaudeEnsembleREST/1"
    def do_GET(self): self.server.application.handle(self)  # type: ignore[attr-defined]
    def do_POST(self): self.server.application.handle(self)  # type: ignore[attr-defined]
    def do_PUT(self): self.server.application.handle(self)  # type: ignore[attr-defined]
    def do_PATCH(self): self.server.application.handle(self)  # type: ignore[attr-defined]
    def do_DELETE(self): self.server.application.handle(self)  # type: ignore[attr-defined]
    def log_message(self, fmt: str, *args: Any) -> None: LOG.info(fmt, *args)

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = create_server(os.environ.get("ENSEMBLE_HTTP_HOST", DEFAULT_HOST),
                           int(os.environ.get("ENSEMBLE_HTTP_PORT", str(DEFAULT_PORT))))
    LOG.info("Claude Ensemble REST gateway listening on http://%s:%s", *server.server_address)
    try: server.serve_forever()
    finally: server.server_close()

if __name__ == "__main__":
    main()
