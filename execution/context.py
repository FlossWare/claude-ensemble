"""Execution context and result contracts shared by nested workflows."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass(frozen=True)
class ExecutionLimits:
    max_depth: int = 16
    max_children: int = 64
    max_total_executions: int = 256
    max_concurrent_executions: int = 16

    def validate(self) -> None:
        if self.max_depth < 0 or self.max_children < 1 or self.max_total_executions < 1 or self.max_concurrent_executions < 1:
            raise ValueError("execution limits must be positive (max_depth may be zero)")


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context propagated through every nested execution."""

    request_id: str
    objective: str
    execution_id: str | None = None
    parent_execution_id: str | None = None
    artifact: Any = None
    requirements: tuple[str, ...] = ()
    evidence: tuple[Any, ...] = ()
    constraints: tuple[str, ...] = ()
    prior_results: tuple["ExecutionResult", ...] = ()
    lineage: tuple[str, ...] = ()
    stage: str = "root"
    worker_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def child(self, *, execution_id: str, stage: str, worker_id: str | None = None, prior_results: tuple["ExecutionResult", ...] | None = None) -> "ExecutionContext":
        return replace(
            self,
            execution_id=execution_id,
            parent_execution_id=self.execution_id,
            lineage=(*self.lineage, execution_id),
            stage=stage,
            worker_id=worker_id,
            prior_results=self.prior_results if prior_results is None else prior_results,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the canonical context without defining a Memory schema."""
        return {
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "lineage": self.lineage,
            "stage": self.stage,
            "worker_id": self.worker_id,
            "objective": self.objective,
            "artifact": self.artifact,
            "requirements": self.requirements,
            "evidence": self.evidence,
            "constraints": self.constraints,
            "prior_results": tuple(result.to_dict() for result in self.prior_results),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionContext":
        """Restore a canonical context from its serialized representation."""
        required = ("request_id", "objective")
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"execution context missing required fields: {', '.join(missing)}")
        return cls(
            request_id=value["request_id"],
            execution_id=value.get("execution_id"),
            parent_execution_id=value.get("parent_execution_id"),
            objective=value["objective"],
            artifact=value.get("artifact"),
            requirements=tuple(value.get("requirements", ())),
            evidence=tuple(value.get("evidence", ())),
            constraints=tuple(value.get("constraints", ())),
            prior_results=tuple(ExecutionResult.from_dict(item) for item in value.get("prior_results", ())),
            lineage=tuple(value.get("lineage", ())),
            stage=value.get("stage", "root"),
            worker_id=value.get("worker_id"),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    node_type: str
    status: ExecutionStatus
    output: Any = None
    error: str | None = None
    children: tuple["ExecutionResult", ...] = ()
    provider: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize an execution result for canonical context persistence."""
        return {
            "execution_id": self.execution_id,
            "node_type": self.node_type,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "children": tuple(child.to_dict() for child in self.children),
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionResult":
        return cls(
            execution_id=value["execution_id"],
            node_type=value["node_type"],
            status=ExecutionStatus(value["status"]),
            output=value.get("output"),
            error=value.get("error"),
            children=tuple(cls.from_dict(child) for child in value.get("children", ())),
            provider=value.get("provider"),
            model=value.get("model"),
            input_tokens=value.get("input_tokens", 0),
            output_tokens=value.get("output_tokens", 0),
            cost_usd=value.get("cost_usd"),
            metadata=dict(value.get("metadata", {})),
        )

    @property
    def successful(self) -> bool:
        return self.status is ExecutionStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status is ExecutionStatus.FAILURE
