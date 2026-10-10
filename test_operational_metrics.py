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


def test_read_skips_malformed_records(tmp_path):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    store.record(
        MetricsRecord(
            execution_id="exec-valid",
            timestamp="now",
            service="model",
        )
    )
    with store.path.open("a", encoding="utf-8") as stream:
        stream.write("{not-json}\n")
        stream.write("[]\n")
        stream.write("\n")

    records = store.read()
    assert [record.execution_id for record in records] == ["exec-valid"]


def test_read_limit_returns_latest_records(tmp_path):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    for execution_id in ("exec-1", "exec-2", "exec-3"):
        store.record(
            MetricsRecord(
                execution_id=execution_id,
                timestamp="now",
                service="model",
            )
        )

    assert [record.execution_id for record in store.read(limit=2)] == ["exec-2", "exec-3"]
    with pytest.raises(ValueError, match="positive integer"):
        store.read(limit=0)


def test_limited_read_retains_only_the_latest_bounded_records(tmp_path):
    store = MetricsStore(tmp_path / "large.jsonl")
    for index in range(2500):
        store.record(MetricsRecord(
            execution_id=f"exec-{index}", timestamp="now", service="metrics"
        ))
    page = store.read(limit=10)
    assert len(page) == 10
    assert [record.execution_id for record in page] == [
        f"exec-{index}" for index in range(2490, 2500)
    ]


def test_aggregate_streams_all_records_without_calling_read(tmp_path, monkeypatch):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    for index in range(5):
        store.record(MetricsRecord(
            execution_id=f"exec-{index}", timestamp="now", service="metrics",
            estimated_cost=0.25, latency_ms=10,
        ))
    def fail_read(*args, **kwargs):
        raise AssertionError("aggregate must stream instead of materializing read()")
    monkeypatch.setattr(store, "read", fail_read)
    result = store.aggregate()
    assert result["records"] == 5
    assert result["total_estimated_cost"] == 1.25
    assert result["average_latency_ms"] == 10


def test_read_page_is_bounded_and_chronological(tmp_path):
    store = MetricsStore(tmp_path / "metrics.jsonl")
    for index in range(12):
        store.record(MetricsRecord(
            execution_id=f"exec-{index}", timestamp="now", service="metrics"
        ))
    assert [r.execution_id for r in store.read_page(5, 5)] == [
        "exec-5", "exec-6", "exec-7", "exec-8", "exec-9"
    ]
    with pytest.raises(ValueError, match="non-negative"):
        store.read_page(5, -1)


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
