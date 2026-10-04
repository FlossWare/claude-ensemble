"""Small, portable provenance records for important CE decisions."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "decision-provenance"
VERSION = "0.1"
DEFAULT_PATH = Path(__file__).resolve().parent / "learning" / "decision-provenance.jsonl"


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a JSON array")
    return value


@dataclass(frozen=True)
class DecisionRecord:
    """Versioned decision facts, deliberately excluding private reasoning."""

    decision_id: str
    execution_id: str
    decision_type: str
    selected: Any
    alternatives: list[Any] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    strategy: dict[str, Any] = field(default_factory=dict)
    evidence: list[Any] = field(default_factory=list)
    created_at: str = ""
    schema: str = SCHEMA
    version: str = VERSION

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        decision_type: str,
        selected: Any,
        alternatives: list[Any] | None = None,
        policy: dict[str, Any] | None = None,
        strategy: dict[str, Any] | None = None,
        evidence: list[Any] | None = None,
    ) -> "DecisionRecord":
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("execution_id is required")
        if not isinstance(decision_type, str) or not decision_type:
            raise ValueError("decision_type is required")
        if alternatives is not None and not isinstance(alternatives, list):
            raise ValueError("alternatives must be a JSON array")
        if policy is not None and not isinstance(policy, dict):
            raise ValueError("policy must be a JSON object")
        if strategy is not None and not isinstance(strategy, dict):
            raise ValueError("strategy must be a JSON object")
        if evidence is not None and not isinstance(evidence, list):
            raise ValueError("evidence must be a JSON array")
        return cls(
            decision_id=str(uuid.uuid4()),
            execution_id=execution_id,
            decision_type=decision_type,
            selected=selected,
            alternatives=list(alternatives or []),
            policy=dict(policy or {}),
            strategy=dict(strategy or {}),
            evidence=list(evidence or []),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DecisionRecord":
        _object(value, "record")
        if value.get("schema") != SCHEMA or value.get("version") != VERSION:
            raise ValueError("unsupported decision provenance schema")
        return cls(
            decision_id=str(value["decision_id"]),
            execution_id=str(value["execution_id"]),
            decision_type=str(value["decision_type"]),
            selected=value.get("selected"),
            alternatives=_list(value.get("alternatives", []), "alternatives"),
            policy=_object(value.get("policy", {}), "policy"),
            strategy=_object(value.get("strategy", {}), "strategy"),
            evidence=_list(value.get("evidence", []), "evidence"),
            created_at=str(value["created_at"]),
            schema=SCHEMA,
            version=VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "decision_id": self.decision_id,
            "execution_id": self.execution_id,
            "decision_type": self.decision_type,
            "selected": self.selected,
            "alternatives": self.alternatives,
            "policy": self.policy,
            "strategy": self.strategy,
            "evidence": self.evidence,
            "created_at": self.created_at,
        }


class DecisionProvenanceStore:
    """Append-only JSONL store with simple lookup by decision identifier."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_PATH

    def record(self, decision: DecisionRecord) -> DecisionRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(decision.to_dict(), sort_keys=True) + "\n")
        return decision

    def get(self, decision_id: str) -> DecisionRecord | None:
        if not self.path.exists():
            return None
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict) and value.get("decision_id") == decision_id:
                    return DecisionRecord.from_dict(value)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
        return None
