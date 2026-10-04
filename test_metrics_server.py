"""REST tests for the operational metrics stream."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from server.ensemble_server import create_server


def request(server, method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        data=data,
        method=method,
    )
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_metrics_endpoint_and_aggregate(tmp_path, monkeypatch):
    monkeypatch.setenv("ENSEMBLE_METRICS_FILE", str(tmp_path / "metrics.jsonl"))
    server = create_server("127.0.0.1", 0, graph_url="", memory_url="")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        metric = {
            "execution_id": "rest-1",
            "timestamp": "2026-10-04T00:00:00+00:00",
            "service": "model",
            "provider": "fake",
            "model": "test-model",
            "status": "success",
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
            "estimated_cost": 0.004,
        }
        status, body = request(server, "POST", "/api/v1/metrics", metric)
        assert status == 201
        assert body["metric"]["execution_id"] == "rest-1"

        status, body = request(server, "GET", "/api/v1/metrics")
        assert status == 200
        assert len(body["metrics"]) == 1

        status, body = request(server, "GET", "/api/v1/metrics/aggregate")
        assert status == 200
        assert body["aggregate"]["records"] == 1
        assert body["aggregate"]["by_model"] == {"test-model": 1}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
