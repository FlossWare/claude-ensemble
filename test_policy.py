"""Tests for the lightweight policy evaluator."""
from __future__ import annotations

from policy import Policy, evaluate


def test_policy_allows_matching_request() -> None:
    policy = Policy(
        allowed_models=("sonnet",),
        allowed_providers=("anthropic",),
        max_cost_usd=1.0,
        max_latency_ms=5000,
        required_capabilities=("code",),
        min_confidence=0.7,
    )
    result = evaluate(
        {
            "model": "sonnet",
            "provider": "anthropic",
            "capabilities": ["code", "reasoning"],
            "estimated_cost_usd": 0.25,
            "estimated_latency_ms": 1000,
            "confidence": 0.9,
        },
        policy,
    )
    assert result.allowed
    assert result.reasons == ()


def test_policy_rejects_and_offers_fallback() -> None:
    policy = Policy(allowed_models=("sonnet",), max_cost_usd=1.0)
    result = evaluate({"model": "opus", "estimated_cost_usd": 2.0}, policy)
    assert not result.allowed
    assert "model is not allowed" in result.reasons
    assert "estimated cost exceeds policy limit" in result.reasons
    assert result.actions == ("fallback", "escalate")


def test_policy_can_disable_recovery_actions() -> None:
    policy = Policy(
        allowed_models=("sonnet",),
        allow_fallback=False,
        allow_escalation=False,
    )
    result = evaluate({"model": "opus"}, policy)
    assert not result.allowed
    assert result.actions == ()


def test_policy_from_dict_validates_input() -> None:
    try:
        Policy.from_dict({"allowed_models": "sonnet"})
    except ValueError as exc:
        assert "allowed_models" in str(exc)
    else:
        raise AssertionError("expected validation failure")
