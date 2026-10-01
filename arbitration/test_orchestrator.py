from __future__ import annotations

from providers import ModelRequest, ModelResponse, ModelProvider

from arbitration.orchestrator import ArbitrationOrchestrator, TaskType


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
            "opus": "arbiter synthesis",
        }
    )
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "opus": provider},
    )
    orchestrator.add_phase(["sonnet"], "opus", "Analyze the change.")

    result = orchestrator.run()

    assert result == "arbiter synthesis"
    assert len(provider.requests) == 2
    assert provider.requests[0].model == "sonnet"
    assert provider.requests[1].model == "opus"
    assert "worker analysis" in provider.requests[1].prompt
    assert "Review the supplied change." in provider.requests[1].prompt


def test_worker_failure_is_reported_not_fabricated() -> None:
    provider = FakeProvider(
        {"opus": "arbiter synthesis"},
        failures={"sonnet"},
    )
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "opus": provider},
    )
    orchestrator.add_phase(["sonnet"], "opus", "Analyze the change.")

    assert orchestrator.run() == "arbiter synthesis"
    worker = orchestrator.results[0][0][0]
    assert worker.succeeded is False
    assert worker.analysis == ""
    assert worker.error == "provider failure for sonnet"
    assert "FAILED" in provider.requests[1].prompt


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
    provider = FakeProvider({"sonnet": "worker", "opus": "arbiter"})
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the supplied change.",
        providers={"sonnet": provider, "opus": provider},
    )

    orchestrator.auto_phases()
    assert orchestrator.phases[0].workers == ["sonnet"]
    assert orchestrator.phases[0].arbiter == "opus"
    assert orchestrator.run() == "arbiter"
