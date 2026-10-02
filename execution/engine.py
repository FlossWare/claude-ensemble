"""Concurrent recursive execution engine."""

from __future__ import annotations

import concurrent.futures
import logging
import re
from dataclasses import dataclass, field, replace
import threading
from typing import Any, Protocol

from providers.model_provider import ModelRequest

from .context import ExecutionContext, ExecutionLimits, ExecutionResult, ExecutionStatus
from .nodes import CompositeExecution, ExecutionNode, ModelExecution, PipelineExecution


logger = logging.getLogger(__name__)


_MEMORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_memory_name(name: str) -> str:
    """Validate the configured Memory name before execution begins."""
    if (
        not isinstance(name, str)
        or not _MEMORY_NAME_PATTERN.fullmatch(name)
        or name in (".", "..")
    ):
        raise ValueError(
            "Invalid memory name: use only letters, numbers, '.', '_' and '-'; not '.' or '..'"
        )
    return name


class MemoryClientProtocol(Protocol):
    """Memory dependency required by the execution engine."""

    def retrieve_with_status(
        self,
        name: str,
        context: ExecutionContext,
        *,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], str | None]:
        ...

    def append(
        self,
        name: str,
        entry: dict[str, Any],
        *,
        context: ExecutionContext | None = None,
    ) -> bool:
        ...


@dataclass
class _Budget:
    used: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    semaphore: threading.Semaphore | None = None


class ExecutionEngine:
    """Evaluate arbitrary-depth execution trees against real providers."""

    def __init__(
        self,
        *,
        limits: ExecutionLimits | None = None,
        memory_client: MemoryClientProtocol | None = None,
        memory_name: str = "session_learnings",
        memory_limit: int = 10,
    ) -> None:
        self.limits = limits or ExecutionLimits()
        self.limits.validate()
        if memory_limit < 1:
            raise ValueError("memory_limit must be at least 1")
        self.memory_client = memory_client
        self.memory_name = _validate_memory_name(memory_name)
        self.memory_limit = memory_limit

    def execute(self, node: ExecutionNode, context: ExecutionContext) -> ExecutionResult:
        budget = _Budget(semaphore=threading.Semaphore(self.limits.max_concurrent_executions))
        return self._execute(node, context, depth=0, budget=budget)

    def _execute(self, node: ExecutionNode, context: ExecutionContext, *, depth: int, budget: _Budget) -> ExecutionResult:
        if depth > self.limits.max_depth:
            return ExecutionResult(node.execution_id, type(node).__name__, ExecutionStatus.FAILURE, error="maximum execution depth exceeded")
        # max_total_executions counts node evaluations, including structural nodes.
        # Admission is atomic so rejected nodes never consume the budget.
        with budget.lock:
            if budget.used >= self.limits.max_total_executions:
                return ExecutionResult(
                    node.execution_id,
                    type(node).__name__,
                    ExecutionStatus.FAILURE,
                    error="maximum total executions exceeded",
                )
            budget.used += 1

        node_context = context.child(
            execution_id=node.execution_id,
            stage=node.stage,
            worker_id=getattr(node, "worker_id", None),
        )
        if isinstance(node, ModelExecution):
            node_context = self._retrieve_memory(node_context)
            result = self._model(node, node_context, budget=budget)
        elif isinstance(node, PipelineExecution):
            result = self._pipeline(node, node_context, depth=depth, budget=budget)
        elif isinstance(node, CompositeExecution):
            result = self._composite(node, node_context, depth=depth, budget=budget)
        else:
            result = ExecutionResult(
                node.execution_id,
                type(node).__name__,
                ExecutionStatus.FAILURE,
                error=f"unsupported execution node: {type(node).__name__}",
            )

        self._persist_result(result, node_context)
        return result

    def _retrieve_memory(self, context: ExecutionContext) -> ExecutionContext:
        """Load applicable Memory into the canonical context before model execution."""
        if self.memory_client is None:
            return replace(
                context,
                metadata={**context.metadata, "memory_retrieval": {"status": "disabled"}},
            )

        try:
            entries, error = self.memory_client.retrieve_with_status(
                self.memory_name,
                context,
                limit=self.memory_limit,
            )
        except Exception as exc:
            entries = []
            error = f"{type(exc).__name__}: {exc}"

        if error is None:
            retrieval = {"status": "success", "count": len(entries)}
        else:
            retrieval = {"status": "failure", "error": error, "count": 0}

        return replace(
            context,
            memory_context=tuple(entries),
            metadata={**context.metadata, "memory_retrieval": retrieval},
        )

    def _persist_result(self, result: ExecutionResult, context: ExecutionContext) -> None:
        """Persist the actual execution result without changing execution outcome."""
        if self.memory_client is None:
            return

        try:
            persisted = self.memory_client.append(
                self.memory_name,
                {
                    "execution_result": result.to_dict(),
                },
                context=context,
            )
            if not persisted:
                logger.warning(
                    "Memory write-back was rejected for execution %s",
                    result.execution_id,
                )
        except Exception as exc:
            # Memory persistence is deliberately best-effort. A Memory outage must
            # never turn an otherwise completed model execution into a model failure.
            logger.warning(
                "Memory write-back failed for execution %s: %s",
                result.execution_id,
                exc,
            )

    @staticmethod
    def _context_metadata(context: ExecutionContext) -> dict[str, object]:
        """Serialize canonical execution context without duplicating result bodies."""
        metadata = context.to_dict()
        metadata.pop("prior_results", None)
        metadata["prior_result_ids"] = tuple(result.execution_id for result in context.prior_results)
        return metadata

    def _model(self, node: ModelExecution, context: ExecutionContext, *, budget: _Budget) -> ExecutionResult:
        try:
            semaphore = budget.semaphore
            if semaphore is None:
                raise RuntimeError("execution budget is not initialized")
            with semaphore:
                response = node.provider.generate(ModelRequest(
                    prompt=node.prompt_builder(context) if node.prompt_builder is not None else node.prompt,
                    model=node.model,
                    system_prompt=node.system_prompt,
                    timeout=node.timeout,
                ))
            output = node.output_parser(response.text) if node.output_parser is not None else response.text
            return ExecutionResult(
                node.execution_id, "model", ExecutionStatus.SUCCESS, output=output,
                provider=response.provider, model=response.model,
                input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
                metadata={
                    "lineage": context.lineage,
                    "stage": context.stage,
                    "worker_id": context.worker_id,
                    "context": self._context_metadata(context),
                    "raw_metadata": response.raw_metadata,
                },
            )
        except Exception as exc:
            return ExecutionResult(
                node.execution_id,
                "model",
                ExecutionStatus.FAILURE,
                error=f"{type(exc).__name__}: {exc}",
                metadata={
                    "lineage": context.lineage,
                    "stage": context.stage,
                    "worker_id": context.worker_id,
                    "context": self._context_metadata(context),
                },
            )

    def _pipeline(self, node: PipelineExecution, context: ExecutionContext, *, depth: int, budget: _Budget) -> ExecutionResult:
        results: list[ExecutionResult] = []
        for child in node.children:
            child_context = replace(context, prior_results=tuple(results) + context.prior_results)
            result = self._execute(child, child_context, depth=depth + 1, budget=budget)
            results.append(result)
            if result.failed:
                return ExecutionResult(
                    node.execution_id, "pipeline", ExecutionStatus.FAILURE,
                    output=tuple(results), children=tuple(results), error=result.error,
                    metadata={"lineage": context.lineage, "completed": len(results), "total": len(node.children)},
                )
        return ExecutionResult(
            node.execution_id, "pipeline", ExecutionStatus.SUCCESS,
            output=tuple(r.output for r in results), children=tuple(results),
            metadata={"lineage": context.lineage, "completed": len(results), "total": len(node.children)},
        )

    def _composite(self, node: CompositeExecution, context: ExecutionContext, *, depth: int, budget: _Budget) -> ExecutionResult:
        if len(node.children) > self.limits.max_children:
            return ExecutionResult(node.execution_id, "composite", ExecutionStatus.FAILURE, error="maximum children exceeded")
        if not node.children:
            return ExecutionResult(
                node.execution_id,
                "composite",
                ExecutionStatus.FAILURE,
                error="composite execution has no children",
            )
        workers = min(self.limits.max_concurrent_executions, len(node.children))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._execute, child, context, depth=depth + 1, budget=budget) for child in node.children]
            results = tuple(f.result() for f in futures)

        successes = tuple(r for r in results if r.successful)
        failures = tuple(r for r in results if r.failed)
        # "first-success" selects the first successful child in declared order,
        # not the first child to finish on the wall clock.
        if node.aggregation == "first-success" and successes:
            output = successes[0].output
        else:
            output = tuple(r.output for r in successes)
        if len(successes) >= node.quorum:
            status = ExecutionStatus.SUCCESS if not failures else ExecutionStatus.PARTIAL
        else:
            status = ExecutionStatus.FAILURE
        return ExecutionResult(
            node.execution_id, "composite", status, output=output, children=results,
            error=None if status is not ExecutionStatus.FAILURE else f"quorum not met: {len(successes)}/{node.quorum} successful",
            metadata={"successful": len(successes), "failed": len(failures), "quorum": node.quorum, "lineage": context.lineage},
        )
