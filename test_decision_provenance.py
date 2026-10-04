"""Tests for portable decision provenance and its gateway endpoints."""
from __future__ import annotations

import json
from types import SimpleNamespace

import server.ensemble_server as ensemble_server
from decision_provenance import DecisionProvenanceStore, DecisionRecord


def test_decision_record_is_versioned_and_json_safe() -> None:
    record = DecisionRecord.create(
        execution_id="exec-1",
        decision_type="model-routing",
        selected={"model": "sonnet"},
        alternatives=[{"model": "haiku"}, {"model": "opus"}],
        policy={"max_cost_usd": 0.25},
        strategy={"name": "thompson", "version": "0.1"},
        evidence=[{"source": "thompson", "success_rate": 0.9}],
    )
    payload = record.to_dict()
    assert payload["schema"] == "decision-provenance"
    assert payload["version"] == "0.1"
    assert payload["decision_id"]
    assert "reasoning" not in payload
    json.dumps(payload)
    restored = DecisionRecord.from_dict(payload)
    assert restored == record


def test_store_round_trips_records(tmp_path) -> None:
    store = DecisionProvenanceStore(tmp_path / "provenance.jsonl")
    record = DecisionRecord.create(execution_id="exec-2", decision_type="arbitration", selected="phase-2")
    store.record(record)
    assert store.get(record.decision_id) == record


def test_store_ignores_malformed_history(tmp_path) -> None:
    path = tmp_path / "provenance.jsonl"
    path.write_text("not json\n" + json.dumps({"decision_id": "other"}) + "\n")
    assert DecisionProvenanceStore(path).get("missing") is None


def test_provenance_create_endpoint(monkeypatch, tmp_path) -> None:
    application = ensemble_server.EnsembleApplication.__new__(ensemble_server.EnsembleApplication)
    application.provenance = DecisionProvenanceStore(tmp_path / "provenance.jsonl")
    sent = {}
    monkeypatch.setattr(ensemble_server, "_json_body", lambda _handler: {
        "execution_id": "exec-3",
        "decision_type": "model-routing",
        "selected": "sonnet",
        "alternatives": ["haiku", "opus"],
        "policy": {"max_cost_usd": 0.5},
        "strategy": {"name": "thompson"},
        "evidence": [{"source": "health", "state": "available"}],
    })
    monkeypatch.setattr(ensemble_server, "_send", lambda _handler, status, payload: sent.update(status=status, payload=payload))
    application._handle_decision(SimpleNamespace(command="POST"), "/provenance")
    assert sent["status"] == ensemble_server.HTTPStatus.CREATED
    decision_id = sent["payload"]["decision"]["decision_id"]
    assert application.provenance.get(decision_id) is not None


def test_provenance_get_endpoint(monkeypatch, tmp_path) -> None:
    application = ensemble_server.EnsembleApplication.__new__(ensemble_server.EnsembleApplication)
    application.provenance = DecisionProvenanceStore(tmp_path / "provenance.jsonl")
    record = DecisionRecord.create(execution_id="exec-4", decision_type="policy", selected=True)
    application.provenance.record(record)
    sent = {}
    monkeypatch.setattr(ensemble_server, "_send", lambda _handler, status, payload: sent.update(status=status, payload=payload))
    application._handle_decision(SimpleNamespace(command="GET"), f"/provenance/{record.decision_id}")
    assert sent["status"] == ensemble_server.HTTPStatus.OK
    assert sent["payload"]["decision"]["decision_id"] == record.decision_id


def test_provenance_get_missing_returns_not_found(monkeypatch, tmp_path) -> None:
    application = ensemble_server.EnsembleApplication.__new__(ensemble_server.EnsembleApplication)
    application.provenance = DecisionProvenanceStore(tmp_path / "provenance.jsonl")
    sent = {}
    monkeypatch.setattr(ensemble_server, "_send", lambda _handler, status, payload: sent.update(status=status, payload=payload))
    application._handle_decision(SimpleNamespace(command="GET"), "/provenance/missing")
    assert sent["status"] == ensemble_server.HTTPStatus.NOT_FOUND


def test_provenance_rejects_non_object_policy(monkeypatch, tmp_path) -> None:
    application = ensemble_server.EnsembleApplication.__new__(ensemble_server.EnsembleApplication)
    application.provenance = DecisionProvenanceStore(tmp_path / "provenance.jsonl")
    sent = {}
    monkeypatch.setattr(ensemble_server, "_json_body", lambda _handler: {
        "execution_id": "exec-5",
        "decision_type": "policy",
        "selected": "sonnet",
        "policy": [],
    })
    monkeypatch.setattr(ensemble_server, "_send", lambda _handler, status, payload: sent.update(status=status, payload=payload))
    application._handle_decision(SimpleNamespace(command="POST"), "/provenance")
    assert sent["status"] == ensemble_server.HTTPStatus.BAD_REQUEST
