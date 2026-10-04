"""Endpoint-level tests for the policy REST boundary."""
from __future__ import annotations

from types import SimpleNamespace

import server.ensemble_server as ensemble_server


def test_policy_endpoint_rejects_non_object_policy(monkeypatch) -> None:
    application = ensemble_server.EnsembleApplication.__new__(ensemble_server.EnsembleApplication)
    application.policy = ensemble_server.Policy()

    sent = {}

    def fake_send(_handler, status, payload):
        sent["status"] = status
        sent["payload"] = payload

    monkeypatch.setattr(ensemble_server, "_json_body", lambda _handler: {
        "request": {"model": "sonnet"},
        "policy": [],
    })
    monkeypatch.setattr(ensemble_server, "_send", fake_send)

    handler = SimpleNamespace(command="POST")
    application._handle_policy(handler, "/evaluate")

    assert sent["status"] == ensemble_server.HTTPStatus.BAD_REQUEST
    assert sent["payload"]["error_code"] == "invalid_request"
    assert sent["payload"]["error"] == "policy must be a JSON object"
