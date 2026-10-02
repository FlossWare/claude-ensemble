"""Tests for canonical cost logging overrides."""

from cost_tracking.logger import CostLogger


def test_log_call_accepts_provider_reported_cost(tmp_path) -> None:
    logger = CostLogger(tmp_path / "cost.jsonl")
    entry = logger.log_call(
        model="gemini-test",
        input_tokens=10,
        output_tokens=5,
        task_name="test",
        provider="google",
        cost_usd=0.123,
    )

    assert entry["cost_usd"] == 0.123
    assert entry["provider"] == "google"
