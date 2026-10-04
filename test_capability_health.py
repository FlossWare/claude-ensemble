"""Tests for the model capability and health view."""
from __future__ import annotations

import json

from capability_health import CapabilityHealthView


class FakeRegistry:
    def resolve_model(self, model):
        if model.startswith("gemini"):
            return "google", model
        return "anthropic", model

    def credential_status(self, provider):
        return [{"name": "default", "state": "available", "source": "env:KEY"}]


def test_capabilities_are_stable_and_provider_aware() -> None:
    view = CapabilityHealthView(FakeRegistry(), models=("sonnet", "gemini-2.5-flash"))
    result = view.capabilities()
    assert result == {
        "models": [
            {
                "model": "sonnet",
                "canonical_model": "sonnet",
                "provider": "anthropic",
                "capabilities": ["text_generation", "reasoning", "code"],
                "available": True,
            },
            {
                "model": "gemini-2.5-flash",
                "canonical_model": "gemini-2.5-flash",
                "provider": "google",
                "capabilities": ["text_generation", "reasoning", "code"],
                "available": True,
            },
        ]
    }


def test_health_combines_thompson_and_cost_data(tmp_path) -> None:
    state = tmp_path / "thompson.json"
    state.write_text(json.dumps({
        "models": {
            "sonnet": {
                "calls": 4,
                "successes": 3,
                "failures": 1,
                "total_latency_ms": 800,
                "total_cost": 0.4,
                "last_updated": "2026-10-03T20:00:00+00:00",
            }
        }
    }))
    costs = tmp_path / "costs.jsonl"
    costs.write_text(json.dumps({
        "timestamp": "2026-10-03T20:01:00+00:00",
        "model": "sonnet",
        "cost_usd": 0.1,
    }) + "\n")
    result = CapabilityHealthView(
        FakeRegistry(),
        thompson_path=state,
        cost_path=costs,
        models=("sonnet",),
    ).health()
    entry = result["models"][0]
    assert entry["state"] == "available"
    assert entry["calls"] == 4
    assert entry["recent_calls"] == 1
    assert entry["success_rate"] == 0.75
    assert entry["avg_latency_ms"] == 200.0
    assert entry["avg_cost_usd"] == 0.1
    assert entry["last_activity"] == "2026-10-03T20:01:00+00:00"


def test_health_marks_model_degraded_when_failures_dominate(tmp_path) -> None:
    state = tmp_path / "thompson.json"
    state.write_text(json.dumps({
        "models": {
            "opus": {
                "calls": 5,
                "successes": 1,
                "failures": 4,
                "total_latency_ms": 100,
                "total_cost": 0.5,
            }
        }
    }))
    result = CapabilityHealthView(
        FakeRegistry(),
        thompson_path=state,
        cost_path=tmp_path / "missing.jsonl",
        models=("opus",),
    ).health()
    assert result["models"][0]["state"] == "degraded"


def test_health_is_available_without_history() -> None:
    result = CapabilityHealthView(FakeRegistry(), models=("haiku",)).health()
    entry = result["models"][0]
    assert entry["state"] == "available"
    assert entry["calls"] == 0
    assert entry["success_rate"] is None


def test_health_marks_missing_credentials_unavailable() -> None:
    class NoCredentials(FakeRegistry):
        def credential_status(self, provider):
            return []

    result = CapabilityHealthView(NoCredentials(), models=("sonnet",)).health()
    assert result["models"][0]["state"] == "unavailable"


def test_snapshot_is_json_safe() -> None:
    result = CapabilityHealthView(FakeRegistry(), models=("sonnet",)).snapshot()
    json.dumps(result)
