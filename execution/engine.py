"""Concurrent recursive execution engine."""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
import threading

from providers.model_provider import ModelRequest

from .context import ExecutionContext, ExecutionLimits, ExecutionResult, ExecutionStatus
from .nodes import CompositeExecution, ExecutionNode, ModelExecution


@dataclass
class _Budget:
    used: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class ExecutionEngine:
    """Evaluate arbitrary-depth execution trees against real providers."""

    def __init__(self, *, limits: ExecutionLimits | None = None) -> None:
        self.limits = limits or ExecutionLimits()
        self.limits.validate()

    def execute(self, node: ExecutionNode, context: ExecutionContext) -> ExecutionResult:
        budget = _Budget()
        return self._execute(node, context, depth=0, budget=budget)

    def _execute(self, node: ExecutionNode, context: ExecutionContext, *, depth: int, budget: _Budget) -> ExecutionResult:
        if depth > self.limits.max_depth:
            return ExecutionResult(node.execution_id, type(node).__name__, ExecutionStatus.FAILURE, error="maximum execution depth exceeded")
        with budget.lock:
            budget.used += 1
            exceeded = budget.used > self.limits.max_total_executions
        if exceeded:
            return ExecutionResult(node.execution_id, type(node).__name__, ExecutionStatus.FAILURE, error="maximum total executions exceeded")

        node_context = context.child(execution_id=node.execution_id, stage=node.stage, worker_id=getattr(node, "worker_id", None))
        if isinstance(node, ModelExecution):
            return self._model(node, node_context)
        if isinstance(node, CompositeExecution):
            return self._composite(node, node_context, depth=depth, budget=budget)
        return ExecutionResult(node.execution_id, type(node).__name__, ExecutionStatus.FAILURE, error=f"unsupported execution node: {type(node).__name__}")

    def _model(self, node: ModelExecution, context: ExecutionContext) -> ExecutionResult:
        try:
            response = node.provider.generate(ModelRequest(
                prompt=node.prompt,
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
                metadata={"lineage": context.lineage, "stage": context.stage, "worker_id": context.worker_id, "context": {"request_id": context.request_id, "objective": context.objective, "artifact": context.artifact, "requirements": context.requirements, "evidence": context.evidence, "constraints": context.constraints, "prior_result_ids": tuple(r.execution_id for r in context.prior_results)}, "raw_metadata": response.raw_metadata},
            )
        except Exception as exc:
            return ExecutionResult(node.execution_id, "model", ExecutionStatus.FAILURE, error=f"{type(exc).__name__}: {exc}", metadata={"lineage": context.lineage, "stage": context.stage, "worker_id": context.worker_id, "context": {"request_id": context.request_id, "objective": context.objective, "artifact": context.artifact, "requirements": context.requirements, "evidence": context.evidence, "constraints": context.constraints, "prior_result_ids": tuple(r.execution_id for r in context.prior_results)}})

    def _composite(self, node: CompositeExecution, context: ExecutionContext, *, depth: int, budget: _Budget) -> ExecutionResult:
        if len(node.children) > self.limits.max_children:
            return ExecutionResult(node.execution_id, "composite", ExecutionStatus.FAILURE, error="maximum children exceeded")
        # The executor bounds concurrency locally. A child may itself be a composite,
        # so recursion naturally supports N-of-N-of-N structures.
        workers = min(self.limits.max_concurrent_executions, len(node.children))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._execute, child, context, depth=depth + 1, budget=budget) for child in node.children]
            results = tuple(f.result() for f in futures)

        successes = tuple(r for r in results if r.successful)
        failures = tuple(r for r in results if r.failed)
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
