import json

import pytest

from arbitration.api_client import MultiModelClient
from operational_metrics import MetricsRecord, MetricsStore
from providers import ModelResponse


class FakeProvider:
    name = "fake"

    def generate(self, request):
        return ModelResponse(
            provider="fake",
            model=request.model or "fake-model",
            text="ok",
            input_tokens=3,
            output_tokens=2,
            cost_usd=0.004,
            request_id="req-1",
        )


class FakeRegistry:
    def resolve_model(self, model):
        return "fake", model

    def resolve(self, model):
        return FakeProvider()


def test_record_round_trip_and_csv(tmp_path):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    record = MetricsRecord(
        execution_id="exec-1",
        timestamp="2026-10-04T00:00:00+00:00",
        service="model",
        provider="fake",
        model="test-model",
        route="route-a",
        task_type="review",
        status="success",
        latency_ms=12.5,
        input_tokens=3,
        output_tokens=2,
        total_tokens=5,
        estimated_cost=0.004,
        quality=0.9,
        outcome="success",
    )

    store.record(record)

    rows = store.read()
    assert rows == [record]
    payload = json.loads((tmp_path / "metrics.jsonl").read_text().strip())
    assert payload["schema"] == "operational-metric"
    assert payload["total_tokens"] == 5

    csv_path = store.export_csv(tmp_path / "metrics.csv")
    assert "execution_id" in csv_path.read_text()
    assert "exec-1" in csv_path.read_text()


def test_record_rejects_inconsistent_token_total():
    with pytest.raises(ValueError, match="total_tokens"):
        MetricsRecord(
            execution_id="exec-1",
            timestamp="now",
            service="model",
            input_tokens=3,
            output_tokens=2,
            total_tokens=99,
        )


def test_model_client_emits_success_metric(tmp_path):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    client = MultiModelClient(
        registry=FakeRegistry(),
        metrics_store=store,
        task_name="review",
    )

    response = client.call_model_response(
        model="test-model",
        prompt="hello",
        execution_id="exec-42",
        worker="worker-1",
        route="thompson",
        task_type="code-review",
    )

    assert response.text == "ok"
    records = store.read()
    assert len(records) == 1
    assert records[0].execution_id == "exec-42"
    assert records[0].status == "success"
    assert records[0].provider == "fake"
    assert records[0].total_tokens == 5
    assert records[0].estimated_cost == 0.004
    assert records[0].route == "thompson"


def test_aggregate_counts_service_model_status(tmp_path):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    for status in ("success", "success", "failure"):
        store.record(
            MetricsRecord(
                execution_id=f"exec-{status}",
                timestamp="2026-10-04T00:00:00+00:00",
                service="model",
                model="test-model",
                status=status,
            )
        )

    aggregate = store.aggregate()
    assert aggregate["records"] == 3
    assert aggregate["by_service"] == {"model": 3}
    assert aggregate["by_model"] == {"test-model": 3}
    assert aggregate["by_status"] == {"success": 2, "failure": 1}
