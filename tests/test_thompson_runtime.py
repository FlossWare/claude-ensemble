import pytest

from runtime.thompson import POLICY, ThompsonError, ThompsonService


def service(tmp_path):
    return ThompsonService(tmp_path / "thompson.sqlite3")


def selection_request():
    return {
        "context_id": "search-quality",
        "policy": POLICY,
        "eligible_arms": [{"arm_id": "bm25"}, {"arm_id": "hybrid"}],
    }


def test_selection_is_persisted_and_same_key_retry_does_not_add_exposure(tmp_path):
    svc = service(tmp_path)
    request = selection_request()
    first = svc.select(request, "selection-key-1", "req-1")
    again = svc.select(request, "selection-key-1", "req-2")
    assert first["selection_id"] == again["selection_id"]
    assert first["chosen_arm_id"] == again["chosen_arm_id"]
    assert again["request_id"] == "req-2"
    state = svc.state("search-quality", "req-3")
    assert sum(arm["exposure_count"] for arm in state["arms"]) == 1
    with pytest.raises(ThompsonError) as error:
        svc.select({**request, "eligible_arms": [{"arm_id": "other"}]}, "selection-key-1", "req-4")
    assert error.value.code == "idempotency_conflict"


def test_binary_update_advances_state_once_and_duplicate_is_idempotent(tmp_path):
    svc = service(tmp_path)
    selected = svc.select(selection_request(), "selection-key", "req-1")
    request = {
        "event_id": "feedback-1",
        "selection_id": selected["selection_id"],
        "context_id": "search-quality",
        "arm_id": selected["chosen_arm_id"],
        "reward": 1,
        "reward_semantics": "binary",
        "evidence_ref": "feedback-opaque-1",
    }
    first = svc.update(request, "update-key", "req-2")
    again = svc.update(request, "update-key", "req-3")
    assert first["operation_id"] == again["operation_id"]
    assert first["state_version"] == again["state_version"] == 1
    assert svc.state("search-quality", "req-4")["state_version"] == 1
    import sqlite3
    with sqlite3.connect(svc.db_path) as db:
        assert db.execute("SELECT evidence_ref FROM updates WHERE event_id=?", ("feedback-1",)).fetchone()[0] == "feedback-opaque-1"


def test_selection_can_only_receive_one_terminal_outcome(tmp_path):
    svc = service(tmp_path)
    selected = svc.select(selection_request(), "selection-key", "req-1")
    base = {
        "selection_id": selected["selection_id"],
        "context_id": "search-quality",
        "arm_id": selected["chosen_arm_id"],
        "reward_semantics": "binary",
        "evidence_ref": "feedback-opaque-2",
    }
    svc.update({**base, "event_id": "event-a", "reward": 1}, "update-a", "req-2")
    with pytest.raises(ThompsonError) as error:
        svc.update({**base, "event_id": "event-b", "reward": 0}, "update-b", "req-3")
    assert error.value.code == "selection_outcome_conflict"
    assert svc.state("search-quality", "req-4")["state_version"] == 1


def test_update_rejects_wrong_selection_identity_without_mutating_state(tmp_path):
    svc = service(tmp_path)
    selected = svc.select(selection_request(), "selection-key", "req-1")
    request = {
        "event_id": "feedback-2",
        "selection_id": selected["selection_id"],
        "context_id": "search-quality",
        "arm_id": "not-the-selected-arm",
        "reward": 1,
        "reward_semantics": "binary",
        "evidence_ref": "feedback-opaque-3",
    }
    with pytest.raises(ThompsonError) as error:
        svc.update(request, "update-key", "req-2")
    assert error.value.status == 404
    assert svc.state("search-quality", "req-3")["state_version"] == 0


def test_state_survives_service_restart(tmp_path):
    first_service = service(tmp_path)
    selected = first_service.select(selection_request(), "selection-key", "req-1")
    first_service.update({
        "event_id": "feedback-3",
        "selection_id": selected["selection_id"],
        "context_id": "search-quality",
        "arm_id": selected["chosen_arm_id"],
        "reward": 0,
        "reward_semantics": "binary",
        "evidence_ref": "feedback-opaque-4",
    }, "update-key", "req-2")

    restarted = service(tmp_path)
    state = restarted.state("search-quality", "req-3")
    assert state["state_version"] == 1
    chosen = next(arm for arm in state["arms"] if arm["arm_id"] == selected["chosen_arm_id"])
    assert chosen["reward_count"] == 1
    assert chosen["exposure_count"] == 1


def test_invalid_policy_and_no_eligible_arms_fail_explicitly(tmp_path):
    svc = service(tmp_path)
    with pytest.raises(ThompsonError) as unsupported:
        svc.select({**selection_request(), "policy": {"name": "other", "version": "1"}}, "key-a", "req")
    assert unsupported.value.code == "unsupported_profile"
    with pytest.raises(ThompsonError) as empty:
        svc.select({**selection_request(), "eligible_arms": []}, "key-b", "req")
    assert empty.value.code == "no_eligible_arms"



def test_thompson_rest_routes_are_reachable(tmp_path):
    import json
    import threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from unittest.mock import patch
    from runtime.server import BoundedThreadingHTTPServer, Handler

    svc = service(tmp_path)
    server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("runtime.server.get_thompson_service", return_value=svc):
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/api/v1/thompson/health", timeout=2) as response:
                assert response.status == 200
                assert json.loads(response.read())["service"] == "thompson"
            body = json.dumps(selection_request()).encode()
            request = Request(base + "/api/v1/thompson/selections", data=body, method="POST",
                              headers={"Content-Type": "application/json", "Idempotency-Key": "http-selection-key"})
            with urlopen(request, timeout=2) as response:
                selected = json.loads(response.read())
                assert response.status == 200
                assert selected["chosen_arm_id"] in {"bm25", "hybrid"}
            invalid = Request(base + "/api/v1/thompson/updates", data=b"{}", method="POST",
                              headers={"Content-Type": "application/json", "Idempotency-Key": "http-invalid-key"})
            with pytest.raises(HTTPError) as error:
                urlopen(invalid, timeout=2)
            assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
