"""Tests for recursive execution and Solve/Review semantics."""

from __future__ import annotations

import json

import pytest

from execution import ExecutionContext, ExecutionEngine, ExecutionLimits, ExecutionStatus
from execution.nodes import CompositeExecution, ModelExecution
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
    assert result.children[0].children[0].children[0].metadata["lineage"] == ("root", "middle", "inner", "inner.a")
    envelope = result.children[0].children[0].children[0].metadata["context"]
    assert envelope["objective"] == "solve this"
    assert envelope["artifact"] == {"name": "artifact"}
    assert envelope["requirements"] == ("must work",)
    assert envelope["evidence"] == ("evidence-1",)
    assert envelope["constraints"] == ("no mocks",)


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
