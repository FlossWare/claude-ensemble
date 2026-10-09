"""Compatibility tests for the REST gateway's HTTP representation contract."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from server.ensemble_server import create_server


def request(server, path: str, accept: str | None = None):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        method="GET",
    )
    if accept is not None:
        request.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, response.headers.get("Content-Type", ""), json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Content-Type", ""), json.loads(error.read())


def test_errors_keep_legacy_json_by_default():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, content_type, body = request(server, "/api/v1/not-a-route")
        assert status == 404
        assert content_type.startswith("application/json")
        assert body == {"ok": False, "error": "service not found"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_errors_can_opt_into_rfc9457_problem_details():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, content_type, body = request(
            server,
            "/api/v1/not-a-route",
            "application/json, application/problem+json",
        )
        assert status == 404
        assert content_type.startswith("application/problem+json")
        assert body["type"] == "about:blank"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["detail"] == "service not found"
        assert body["instance"] == "/api/v1/not-a-route"
        # Keep the old error envelope as extension members for opting-in clients
        # that are migrating incrementally.
        assert body["ok"] is False
        assert body["error"] == "service not found"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_problem_details_q_zero_is_not_selected():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, content_type, body = request(
            server,
            "/api/v1/not-a-route",
            "application/problem+json;q=0, application/json",
        )
        assert status == 404
        assert content_type.startswith("application/json")
        assert body["error"] == "service not found"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_success_responses_remain_json():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, content_type, body = request(
            server,
            "/api/v1/health",
            "application/json, application/problem+json",
        )
        assert status == 200
        assert content_type.startswith("application/json")
        assert body["service"] == "claude-ensemble"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
