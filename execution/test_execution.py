"""Tests for recursive execution and Solve/Review semantics."""

from __future__ import annotations

import json

import pytest

from execution import ExecutionContext, ExecutionEngine, ExecutionLimits, ExecutionStatus
from execution.nodes import CompositeExecution, ModelExecution, PipelineExecution
from providers.model_provider import ModelProvider, ModelRequest, ModelResponse
from workflows.review import ReviewRequest, build_review


class FakeProvider(ModelProvider):
    name = "fake"

    def __init__(self, responses: dict[str, str], failures: set[str] | None = None) -> None:
        self.responses = responses
        self.failures = failures or set()
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        model = request.model or "fake"
        if model in self.failures:
            raise RuntimeError(f"worker {model} failed")
        return ModelResponse(provider=self.name, model=model, text=self.responses.get(model, model))


def context() -> ExecutionContext:
    return ExecutionContext(
        request_id="root", objective="solve this", artifact={"name": "artifact"},
        requirements=("must work",), evidence=("evidence-1",), constraints=("no mocks",),
    )


def model(provider: ModelProvider, execution_id: str, stage: str, model_name: str) -> ModelExecution:
    return ModelExecution(execution_id=execution_id, stage=stage, worker_id=model_name, provider=provider, model=model_name, prompt="prompt")


def test_arbitrary_nested_multi_execution_preserves_lineage_and_context() -> None:
    provider = FakeProvider({"a": "A", "b": "B", "c": "C"})
    inner = CompositeExecution("inner", "review", (model(provider, "inner.a", "review", "a"), model(provider, "inner.b", "review", "b")), quorum=2)
    middle = CompositeExecution("middle", "review", (inner, model(provider, "middle.c", "review", "c")), quorum=2)
    root = CompositeExecution("root", "solve", (middle,), quorum=1)

    result = ExecutionEngine().execute(root, context())

    assert result.status is ExecutionStatus.SUCCESS
    leaf = result.children[0].children[0].children[0]
    assert leaf.metadata["lineage"] == ("root", "middle", "inner", "inner.a")
    assert leaf.metadata["context"]["request_id"] == "root"
    assert leaf.metadata["context"]["execution_id"] == "inner.a"
    assert leaf.metadata["context"]["parent_execution_id"] == "inner"
    assert leaf.metadata["context"]["prior_result_ids"] == ()
    envelope = result.children[0].children[0].children[0].metadata["context"]
    assert envelope["objective"] == "solve this"
    assert envelope["artifact"] == {"name": "artifact"}
    assert envelope["requirements"] == ("must work",)
    assert envelope["evidence"] == ("evidence-1",)
    assert envelope["constraints"] == ("no mocks",)


def test_execution_context_round_trip_preserves_nested_results() -> None:
    provider = FakeProvider({"a": "A"})
    root = CompositeExecution("root", "solve", (model(provider, "a", "solve", "a"),), quorum=1)
    result = ExecutionEngine().execute(root, context())

    original = context().child(execution_id="root", stage="solve", prior_results=(result,))
    restored = ExecutionContext.from_dict(original.to_dict())

    assert restored.request_id == original.request_id
    assert restored.execution_id == "root"
    assert restored.parent_execution_id is None
    assert restored.lineage == ("root",)
    assert restored.objective == original.objective
    assert restored.artifact == original.artifact
    assert restored.requirements == original.requirements
    assert restored.evidence == original.evidence
    assert restored.constraints == original.constraints
    assert restored.prior_results == (result,)


def test_partial_result_is_not_success() -> None:
    provider = FakeProvider({"ok": "OK"}, failures={"bad"})
    root = CompositeExecution("root", "solve", (model(provider, "ok", "solve", "ok"), model(provider, "bad", "solve", "bad")), quorum=2)
    result = ExecutionEngine().execute(root, context())
    assert result.status is ExecutionStatus.FAILURE
    assert result.children[1].status is ExecutionStatus.FAILURE


def test_quorum_allows_partial_results_without_hiding_failure() -> None:
    provider = FakeProvider({"ok": "OK"}, failures={"bad"})
    root = CompositeExecution("root", "solve", (model(provider, "ok", "solve", "ok"), model(provider, "bad", "solve", "bad")), quorum=1)
    result = ExecutionEngine().execute(root, context())
    assert result.status is ExecutionStatus.PARTIAL
    assert result.metadata["failed"] == 1


def test_depth_limit_is_enforced() -> None:
    provider = FakeProvider({"ok": "OK"})
    leaf = model(provider, "leaf", "solve", "ok")
    nested = CompositeExecution("c1", "solve", (leaf,))
    root = CompositeExecution("c0", "solve", (nested,))
    result = ExecutionEngine(limits=ExecutionLimits(max_depth=0)).execute(root, context())
    assert result.children[0].status is ExecutionStatus.FAILURE


def test_review_malformed_output_is_failure_not_zero_findings() -> None:
    provider = FakeProvider({"reviewer": "not json"})
    node, ctx = build_review(request=ReviewRequest(objective="review", artifact="code"), provider=provider, models=("reviewer",))
    result = ExecutionEngine().execute(node, ctx)
    assert result.status is ExecutionStatus.FAILURE
    assert "not valid JSON" in result.children[0].error


def test_review_structured_output_is_parsed() -> None:
    payload = {"findings": [{"id": "F1", "severity": "high", "subject": "x", "description": "bad", "evidence": "line 1", "disposition": "new"}]}
    provider = FakeProvider({"reviewer": json.dumps(payload)})
    node, ctx = build_review(request=ReviewRequest(objective="review", artifact="code"), provider=provider, models=("reviewer",))
    result = ExecutionEngine().execute(node, ctx)
    assert result.status is ExecutionStatus.SUCCESS
    assert result.children[0].output[0].id == "F1"


def test_pipeline_passes_prior_results_to_later_review_workers() -> None:
    provider = FakeProvider({"first": json.dumps({"findings": [{"id": "F1", "severity": "high", "subject": "x", "description": "bad", "evidence": "line 1"}]}), "second": json.dumps({"findings": []})})
    first, ctx = build_review(request=ReviewRequest(objective="review", artifact="code"), provider=provider, models=("first",), request_id="first-review")
    second, _ = build_review(request=ReviewRequest(objective="review", artifact="code"), provider=provider, models=("second",), request_id="second-review")
    root = PipelineExecution("reviews", "review-pipeline", (first, second))
    result = ExecutionEngine().execute(root, ctx)
    assert result.status is ExecutionStatus.SUCCESS
    second_prompt = next(r for r in provider.requests if r.model == "second")
    assert "first-review" in second_prompt.prompt
    assert "Prior Results" in second_prompt.prompt


def test_nested_composites_respect_global_concurrency_limit() -> None:
    import threading
    import time

    class TrackingProvider(FakeProvider):
        def __init__(self):
            super().__init__({"a": "A", "b": "B", "c": "C", "d": "D"})
            self.active = 0
            self.maximum = 0
            self.lock = threading.Lock()

        def generate(self, request: ModelRequest) -> ModelResponse:
            with self.lock:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
            try:
                time.sleep(0.02)
                return super().generate(request)
            finally:
                with self.lock:
                    self.active -= 1

    provider = TrackingProvider()
    inner = CompositeExecution("inner", "solve", (model(provider, "a", "solve", "a"), model(provider, "b", "solve", "b")), quorum=1)
    root = CompositeExecution("root", "solve", (inner, model(provider, "c", "solve", "c"), model(provider, "d", "solve", "d")), quorum=1)
    result = ExecutionEngine(limits=ExecutionLimits(max_concurrent_executions=2)).execute(root, context())
    assert result.status is ExecutionStatus.SUCCESS
    assert provider.maximum <= 2


def test_total_execution_limit_is_atomic_at_exact_boundary() -> None:
    provider = FakeProvider({"first": "FIRST", "second": "SECOND", "third": "THIRD"})
    engine = ExecutionEngine(limits=ExecutionLimits(max_total_executions=2))
    budget = __import__("execution.engine", fromlist=["_Budget"])._Budget(
        semaphore=__import__("threading").Semaphore(2)
    )

    first = engine._execute(model(provider, "first", "solve", "first"), context(), depth=0, budget=budget)
    second = engine._execute(model(provider, "second", "solve", "second"), context(), depth=0, budget=budget)
    rejected = engine._execute(model(provider, "third", "solve", "third"), context(), depth=0, budget=budget)

    assert first.status is ExecutionStatus.SUCCESS
    assert second.status is ExecutionStatus.SUCCESS
    assert rejected.status is ExecutionStatus.FAILURE
    assert rejected.error == "maximum total executions exceeded"
    assert budget.used == 2
    assert [request.model for request in provider.requests] == ["first", "second"]


def test_total_execution_limit_counts_structural_nodes() -> None:
    provider = FakeProvider({"leaf": "LEAF"})
    root = CompositeExecution("root", "solve", (model(provider, "leaf", "solve", "leaf"),))
    result = ExecutionEngine(limits=ExecutionLimits(max_total_executions=1)).execute(root, context())

    assert result.status is ExecutionStatus.FAILURE
    assert result.children[0].status is ExecutionStatus.FAILURE
    assert provider.requests == []


def test_total_execution_limit_applies_across_nested_pipeline_and_composite() -> None:
    provider = FakeProvider({"leaf": "LEAF"})
    leaf = model(provider, "leaf", "solve", "leaf")
    inner = CompositeExecution("inner", "solve", (leaf,))
    root = PipelineExecution("root", "solve", (inner, leaf))

    result = ExecutionEngine(limits=ExecutionLimits(max_total_executions=3)).execute(root, context())

    assert result.status is ExecutionStatus.FAILURE
    assert result.children[0].status is ExecutionStatus.SUCCESS
    assert result.children[1].status is ExecutionStatus.FAILURE
    assert len(provider.requests) == 1
