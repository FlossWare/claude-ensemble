"""Lightweight policy evaluation for Ensemble decisions.

The policy boundary deliberately uses plain dictionaries and deterministic
rules. It is a guardrail, not a policy language or framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Policy:
    allowed_models: tuple[str, ...] = ()
    allowed_providers: tuple[str, ...] = ()
    max_cost_usd: float | None = None
    max_latency_ms: float | None = None
    required_capabilities: tuple[str, ...] = ()
    min_confidence: float | None = None
    allow_fallback: bool = True
    allow_escalation: bool = True

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Policy":
        def strings(name: str) -> tuple[str, ...]:
            raw = value.get(name, ())
            if not isinstance(raw, (list, tuple)):
                raise ValueError(f"{name} must be a list")
            if any(not isinstance(item, str) or not item for item in raw):
                raise ValueError(f"{name} must contain non-empty strings")
            return tuple(raw)

        def number(name: str, minimum: float | None = None) -> float | None:
            raw = value.get(name)
            if raw is None:
                return None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{name} must be a number")
            result = float(raw)
            if minimum is not None and result < minimum:
                raise ValueError(f"{name} must be >= {minimum}")
            return result

        return cls(
            allowed_models=strings("allowed_models"),
            allowed_providers=strings("allowed_providers"),
            max_cost_usd=number("max_cost_usd", 0),
            max_latency_ms=number("max_latency_ms", 0),
            required_capabilities=strings("required_capabilities"),
            min_confidence=number("min_confidence", 0),
            allow_fallback=bool(value.get("allow_fallback", True)),
            allow_escalation=bool(value.get("allow_escalation", True)),
        )


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    reasons: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    policy: Policy = field(default_factory=Policy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "actions": list(self.actions),
            "policy": {
                "allowed_models": list(self.policy.allowed_models),
                "allowed_providers": list(self.policy.allowed_providers),
                "max_cost_usd": self.policy.max_cost_usd,
                "max_latency_ms": self.policy.max_latency_ms,
                "required_capabilities": list(self.policy.required_capabilities),
                "min_confidence": self.policy.min_confidence,
                "allow_fallback": self.policy.allow_fallback,
                "allow_escalation": self.policy.allow_escalation,
            },
        }


def evaluate(request: dict[str, Any], policy: Policy) -> PolicyResult:
    """Evaluate a proposed execution against a policy."""
    reasons: list[str] = []
    actions: list[str] = []

    model = request.get("model")
    provider = request.get("provider")
    capabilities = request.get("capabilities", [])
    cost = request.get("estimated_cost_usd")
    latency = request.get("estimated_latency_ms")
    confidence = request.get("confidence")

    if policy.allowed_models and model not in policy.allowed_models:
        reasons.append("model is not allowed")
    if policy.allowed_providers and provider not in policy.allowed_providers:
        reasons.append("provider is not allowed")

    if not isinstance(capabilities, list):
        reasons.append("capabilities must be a list")
    else:
        missing = [item for item in policy.required_capabilities if item not in capabilities]
        if missing:
            reasons.append(f"required capabilities missing: {', '.join(missing)}")

    if policy.max_cost_usd is not None and cost is not None:
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            reasons.append("estimated_cost_usd must be a number")
        elif cost > policy.max_cost_usd:
            reasons.append("estimated cost exceeds policy limit")

    if policy.max_latency_ms is not None and latency is not None:
        if isinstance(latency, bool) or not isinstance(latency, (int, float)):
            reasons.append("estimated_latency_ms must be a number")
        elif latency > policy.max_latency_ms:
            reasons.append("estimated latency exceeds policy limit")

    if policy.min_confidence is not None and confidence is not None:
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            reasons.append("confidence must be a number")
        elif confidence < policy.min_confidence:
            reasons.append("confidence is below policy threshold")

    if reasons:
        if policy.allow_fallback:
            actions.append("fallback")
        if policy.allow_escalation:
            actions.append("escalate")

    return PolicyResult(not reasons, tuple(reasons), tuple(actions), policy)
