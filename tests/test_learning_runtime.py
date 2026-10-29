import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from runtime.server import BoundedThreadingHTTPServer, Handler
from runtime.learning import LearningError, LearningService


class ThompsonStub(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        type(self).calls.append((body, self.headers.get("Idempotency-Key")))
        response = {"event_id": body["event_id"], "operation_id": "thompson:op:stub", "applied": True, "state_version": 1}
        encoded = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args):
        pass


@pytest.fixture
def service(tmp_path):
    ThompsonStub.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), ThompsonStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    svc = LearningService(tmp_path / "learning.sqlite3", f"http://127.0.0.1:{server.server_port}")
    yield svc
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request():
    return {
        "event_id": "feedback-001",
        "selection_id": "thompson:selection:abc123",
        "context_id": "search-quality",
        "arm_id": "hybrid",
        "outcome": {"result": "success"},
        "evidence": [{
            "kind": "explicit_user_feedback",
            "reference": "feedback-ref-001",
            "asserted_result": "success",
            "observed_at": "2026-10-28T19:00:00Z",
        }],
        "occurred_at": "2026-10-28T19:00:01Z",
        "policy_version": "binary-reward-v1",
    }


def test_valid_feedback_is_persisted_and_sent_to_thompson_over_rest(service):
    status, response = service.submit(request(), "learning-key-1", "req-1")
    assert status == 202
    assert response["status"] == "complete"
    assert response["thompson_operation_id"] == "thompson:op:stub"
    assert len(ThompsonStub.calls) == 1
    body, key = ThompsonStub.calls[0]
    assert body["reward"] == 1
    assert body["reward_semantics"] == "binary"
    assert key == "learning-feedback-001"
    assert service.operation(response["operation_id"], "req-2")["status"] == "complete"


def test_same_event_retry_is_idempotent_and_conflicting_payload_is_rejected(service):
    first_status, first = service.submit(request(), "learning-key-1", "req-1")
    second_status, second = service.submit(request(), "learning-key-1", "req-2")
    assert first_status == second_status == 202
    assert first["operation_id"] == second["operation_id"]
    assert second["request_id"] == "req-2"
    assert len(ThompsonStub.calls) == 1

    conflicting = request()
    conflicting["outcome"] = {"result": "failure"}
    conflicting["evidence"][0]["asserted_result"] = "failure"
    with pytest.raises(LearningError) as error:
        service.submit(conflicting, "learning-key-1", "req-3")
    assert error.value.code == "idempotency_conflict"


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(policy_version="other"),
    lambda value: value.update(outcome={"result": "unknown"}),
    lambda value: value.update(evidence=[]),
    lambda value: value["evidence"][0].update(asserted_result="failure"),
    lambda value: value["evidence"][0].update(kind="implicit_inference"),
])
def test_invalid_feedback_does_not_call_thompson(service, mutation):
    value = request()
    mutation(value)
    with pytest.raises(LearningError):
        service.submit(value, "invalid-key", "req-1")
    assert ThompsonStub.calls == []


def test_state_counts_are_bounded_by_scope(service):
    _, response = service.submit(request(), "learning-key-1", "req-1")
    state = service.state("search-quality", "req-2")
    assert state["scope_id"] == "search-quality"
    assert state["counts"]["complete"] == 1
    assert state["counts"]["reconciliation_required"] == 0
    with pytest.raises(LearningError) as error:
        service.state("unknown-scope", "req-3")
    assert error.value.status == 404



def test_learning_health_and_outcome_routes_are_reachable(service):
    ce_server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ce_thread = threading.Thread(target=ce_server.serve_forever, daemon=True)
    ce_thread.start()
    try:
        with patch("runtime.server.get_learning_service", return_value=service):
            base = f"http://127.0.0.1:{ce_server.server_port}"
            with urlopen(base + "/api/v1/learning/health", timeout=2) as response:
                assert response.status == 200
                assert json.loads(response.read())["service"] == "learning"
            body = json.dumps(request()).encode()
            call = Request(base + "/api/v1/learning/outcomes", data=body, method="POST",
                           headers={"Content-Type": "application/json", "Idempotency-Key": "http-key-1"})
            with urlopen(call, timeout=3) as response:
                result = json.loads(response.read())
                assert response.status == 202
                assert result["status"] == "complete"
            invalid = Request(base + "/api/v1/learning/outcomes", data=b"{}", method="POST",
                              headers={"Content-Type": "application/json", "Idempotency-Key": "http-invalid-key"})
            with pytest.raises(HTTPError) as error:
                urlopen(invalid, timeout=2)
            assert error.value.code == 400
    finally:
        ce_server.shutdown()
        ce_server.server_close()
        ce_thread.join(timeout=2)
