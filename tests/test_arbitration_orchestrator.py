import json

from arbitration.orchestrator import ArbitrationOrchestrator, TaskType
from providers.model_provider import ModelResponse


class FakeProvider:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if request.model == "opus":
            return ModelResponse(
                provider="fake",
                model=request.model,
                text=json.dumps(
                    {
                        "adjudicated_result": f"stage result for {request.model}",
                        "selected_worker": "sonnet",
                        "rationale": "selected from the supplied evidence",
                        "supporting_evidence": ["worker evidence"],
                        "rejected_alternatives": ["other worker result"],
                        "next_phase_questions": ["recheck the changed behavior"],
                    }
                ),
            )
        return ModelResponse(
            provider="fake",
            model=request.model,
            text=f"worker analysis from {request.model}",
        )


def test_every_stage_runs_multiple_workers_and_an_arbiter():
    provider = FakeProvider()
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the change.",
        default_provider=provider,
    )
    orchestrator.auto_phases(num_phases=3)

    result = orchestrator.run()

    assert result == "stage result for opus"
    assert len(orchestrator.results) == 3
    assert all(len(workers) == 2 for workers, _ in orchestrator.results)
    assert all(arbiter.adjudicated_result for _, arbiter in orchestrator.results)
    assert len(provider.requests) == 9


def test_stage_handoff_preserves_worker_results_and_adjudication():
    provider = FakeProvider()
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the change.",
        default_provider=provider,
    )
    orchestrator.auto_phases(num_phases=2)

    orchestrator.run()

    worker_prompts = [
        request.prompt
        for request in provider.requests
        if request.model != "opus"
    ]
    stage_one_prompts = worker_prompts[:2]
    stage_two_prompts = worker_prompts[2:]

    assert all("worker analysis from sonnet" not in prompt for prompt in stage_one_prompts)
    assert all("Prior Arbitration Stage 1" in prompt for prompt in stage_two_prompts)
    assert all("worker analysis from sonnet" in prompt for prompt in stage_two_prompts)
    assert all("stage result for opus" in prompt for prompt in stage_two_prompts)
    assert all("Rejected alternatives" in prompt for prompt in stage_two_prompts)


def test_arbiter_receives_all_worker_results():
    provider = FakeProvider()
    orchestrator = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the change.",
        default_provider=provider,
    )
    orchestrator.auto_phases(num_phases=1)

    orchestrator.run()

    arbiter_prompt = next(
        request.prompt for request in provider.requests if request.model == "opus"
    )
    assert "### Worker sonnet" in arbiter_prompt
    assert "### Worker haiku" in arbiter_prompt


def test_configured_stage_count_controls_termination():
    provider = FakeProvider()
    orchestrator = ArbitrationOrchestrator(
        TaskType.BUG_ANALYSIS,
        "Analyze the bug.",
        default_provider=provider,
    )
    orchestrator.auto_phases(num_phases=4)

    orchestrator.run()

    assert len(orchestrator.results) == 4
    assert len(provider.requests) == 12


def test_arbiter_plain_text_has_a_safe_adjudication_fallback():
    class PlainTextProvider(FakeProvider):
        def generate(self, request):
            self.requests.append(request)
            if request.model == "opus":
                return ModelResponse(
                    provider="fake",
                    model=request.model,
                    text="plain text adjudication",
                )
            return ModelResponse(
                provider="fake",
                model=request.model,
                text="worker result",
            )

    provider = PlainTextProvider()
    orchestrator = ArbitrationOrchestrator(
        TaskType.SOLVE if hasattr(TaskType, "SOLVE") else TaskType.BUG_ANALYSIS,
        "Solve the problem.",
        default_provider=provider,
    )
    orchestrator.auto_phases(num_phases=1)

    assert orchestrator.run() == "plain text adjudication"
