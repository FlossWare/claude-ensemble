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
            lineage=(*self.lineage, execution_id),
            stage=stage,
            worker_id=worker_id,
            prior_results=self.prior_results if prior_results is None else prior_results,
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

    @property
    def successful(self) -> bool:
        return self.status is ExecutionStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status is ExecutionStatus.FAILURE
