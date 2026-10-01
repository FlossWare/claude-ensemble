from __future__ import annotations

import json

import pytest

from providers import ModelProvider, ModelRequest, ModelResponse

from arbitration.orchestrator import ArbitrationOrchestrator, ModelPool, TaskType


ARBITER_RESPONSE = json.dumps(
    {
        "adjudicated_result": "arbiter synthesis",
        "selected_worker": "sonnet",
        "rationale": "selected",
        "supporting_evidence": ["worker analysis"],
        "rejected_alternatives": [],
        "next_phase_questions": [],
    }
)


class FakeProvider(ModelProvider):
    def __init__(self, responses: dict[str, str], failures: set[str] | None = None):
        self.responses = responses
        self.failures = failures or set()
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.model in self.failures:
            raise RuntimeError(f"provider failure for {request.model}")
        return ModelResponse(
            provider="fake",
            model=request.model or "unknown",
            text=self.responses.get(request.model or "", f"response:{request.model}"),
        )


def test_arbitration_uses_real_provider_results() -> None:
    provider = FakeProvider(
        {
            "sonnet": "worker analysis",
            "haiku": "second worker analysis",
            "opus": ARBITER_RESPONSE,
        }
    )
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "haiku": provider, "opus": provider},
    )
    orchestrator.add_phase(["sonnet", "haiku"], "opus", "Analyze the change.")

    result = orchestrator.run()

    assert result == "arbiter synthesis"
    assert len(provider.requests) == 3
    assert [request.model for request in provider.requests] == ["sonnet", "haiku", "opus"]
    assert "worker analysis" in provider.requests[2].prompt
    assert "second worker analysis" in provider.requests[2].prompt
    assert "Review the supplied change." in provider.requests[2].prompt


def test_worker_failure_is_reported_not_fabricated() -> None:
    provider = FakeProvider(
        {
            "haiku": "second worker analysis",
            "opus": ARBITER_RESPONSE,
        },
        failures={"sonnet"},
    )
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "haiku": provider, "opus": provider},
    )
    orchestrator.add_phase(["sonnet", "haiku"], "opus", "Analyze the change.")

    assert orchestrator.run() == "arbiter synthesis"
    worker_results = orchestrator.results[0][0]
    assert worker_results[0].succeeded is False
    assert worker_results[0].analysis == ""
    assert worker_results[0].error == "provider failure for sonnet"
    assert "FAILED" in provider.requests[2].prompt
    assert "second worker analysis" in provider.requests[2].prompt


def test_unknown_model_fails_explicitly() -> None:
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
    )
    orchestrator.add_phase(["gemini"], "opus", "Analyze the change.")

    result = orchestrator._run_workers(orchestrator.phases[0], "evidence")

    assert result[0].succeeded is False
    assert "No ModelProvider configured" in (result[0].error or "")


def test_auto_phase_uses_provider_models() -> None:
    provider = FakeProvider(
        {
            "sonnet": "worker",
            "haiku": "worker",
            "opus": ARBITER_RESPONSE,
        }
    )
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "haiku": provider, "opus": provider},
    )

    orchestrator.auto_phases()
    assert orchestrator.phases[0].workers == ["sonnet", "haiku"]
    assert orchestrator.phases[0].arbiter == "opus"
    assert orchestrator.run() == "arbiter synthesis"


def test_auto_phases_support_multiple_phases_with_explicit_reuse() -> None:
    provider = FakeProvider(
        {
            "sonnet": "worker",
            "haiku": "worker",
            "opus": ARBITER_RESPONSE,
        }
    )
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "haiku": provider, "opus": provider},
    )

    orchestrator.auto_phases(num_phases=2)

    assert len(orchestrator.phases) == 2
    assert orchestrator.phases[0].workers == ["sonnet", "haiku"]
    assert orchestrator.phases[0].arbiter == "opus"
    assert orchestrator.phases[1].workers == ["sonnet", "haiku"]
    assert orchestrator.phases[1].arbiter == "opus"

    assert orchestrator.run() == "arbiter synthesis"
    assert len(provider.requests) == 6


def test_model_pool_rejects_arbiter_when_current_phase_has_no_free_model() -> None:
    pool = ModelPool()

    assert pool.get_workers(3) == ["sonnet", "haiku", "opus"]

    with pytest.raises(ValueError, match="current phase"):
        pool.get_arbiter()


def test_model_pool_releases_role_reservations_between_phases() -> None:
    pool = ModelPool()

    assert pool.get_workers(1) == ["sonnet"]
    assert pool.get_arbiter() == "opus"

    with pytest.raises(ValueError, match="worker model"):
        pool.get_workers(2)

    pool.reset_phase()

    assert pool.get_workers(1) == ["sonnet"]
    assert pool.get_arbiter() == "opus"


def test_builtin_claude_models_use_the_explicit_default_provider() -> None:
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
    )

    assert type(orchestrator._provider_for("sonnet")).__name__ == "ClaudeCodeProvider"
