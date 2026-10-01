"""Execution-engine integration tests for canonical Memory retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

from execution.context import ExecutionContext, ExecutionStatus
from execution.engine import ExecutionEngine
from execution.nodes import CompositeExecution, ModelExecution, PipelineExecution
from providers.model_provider import ModelRequest, ModelResponse


@dataclass
class FakeProvider:
    prompts: list[str] = field(default_factory=list)

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.prompts.append(request.prompt)
        return ModelResponse(
            provider="fake",
            model=request.model or "fake-model",
            text="model-result",
        )


@dataclass
class FakeMemory:
    entries: list[dict] = field(default_factory=list)
    error: str | None = None
    calls: list[tuple[str, ExecutionContext, int]] = field(default_factory=list)

    def retrieve_with_status(
        self,
        name: str,
        context: ExecutionContext,
        *,
        limit: int = 10,
    ) -> tuple[list[dict], str | None]:
        self.calls.append((name, context, limit))
        if self.error is not None:
            return [], self.error
        return self.entries, None


def test_memory_context_flows_through_nested_composite_and_pipeline() -> None:
    provider = FakeProvider()
    memory = FakeMemory(entries=[{"record": {"lesson": "use the canonical context"}}])
    engine = ExecutionEngine(memory_client=memory, memory_name="session_learnings", memory_limit=4)

    model = ModelExecution(
        execution_id="model-1",
        stage="model",
        provider=provider,
        prompt_builder=lambda context: (
            f"memory={context.memory_context[0]['record']['lesson']};"
            f"lineage={','.join(context.lineage)}"
        ),
    )
    pipeline = PipelineExecution(
        execution_id="pipeline-1",
        stage="pipeline",
        children=(model,),
    )
    root = CompositeExecution(
        execution_id="composite-1",
        stage="composite",
        children=(pipeline,),
        quorum=1,
    )

    result = engine.execute(
        root,
        ExecutionContext(request_id="request-1", objective="test memory flow"),
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert provider.prompts == [
        "memory=use the canonical context;lineage=composite-1,pipeline-1,model-1"
    ]
    assert len(memory.calls) == 1
    name, retrieved_context, limit = memory.calls[0]
    assert name == "session_learnings"
    assert limit == 4
    assert retrieved_context.lineage == ("composite-1", "pipeline-1", "model-1")
    assert retrieved_context.memory_context == tuple(memory.entries)

    model_result = result.children[0].children[0]
    persisted_context = model_result.metadata["context"]
    assert persisted_context["memory_context"] == tuple(memory.entries)
    assert persisted_context["memory_retrieval"] == {"status": "success", "count": 1}


def test_memory_failure_is_distinguishable_from_successful_model_execution() -> None:
    provider = FakeProvider()
    memory = FakeMemory(error="memory service unavailable")
    engine = ExecutionEngine(memory_client=memory)

    model = ModelExecution(
        execution_id="model-1",
        stage="model",
        provider=provider,
        prompt="continue without memory",
    )

    result = engine.execute(
        model,
        ExecutionContext(request_id="request-1", objective="test memory failure"),
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.output == "model-result"
    assert result.metadata["context"]["memory_context"] == ()
    assert result.metadata["context"]["memory_retrieval"] == {
        "status": "failure",
        "error": "memory service unavailable",
        "count": 0,
    }
