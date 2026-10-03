"""Tests for the canonical REST model boundary."""

from __future__ import annotations

import json
import threading
import urllib.request


def test_models_endpoint_exposes_credential_status(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY_ACCOUNT_A", "secret-a")
    from server.ensemble_server import create_server

    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/api/v1/models/credentials",
            timeout=3,
        ) as response:
            payload = json.loads(response.read())
        assert payload["ok"]
        assert payload["credentials"]["anthropic"][0]["name"] == "account-a"
        assert "api_key" not in json.dumps(payload)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
