import json
import tempfile
from pathlib import Path

from learning_service import LearningService


class SnapshotMemory:
    def __init__(self):
        self.events = []

    def write_event(self, event_id, event_type, source, payload):
        self.events.append((event_id, event_type, source, payload))
        if event_type == "thompson.state":
            return False
        return True


class SuccessfulThompson:
    def get_circuit_breaker_state(self):
        return {"state": "closed"}

    def record_outcome(self, **kwargs):
        return True

    def get_state(self):
        return {"models": {"haiku": {"successes": 1}}}


def test_thompson_snapshot_failure_blocks_checkpoint():
    with tempfile.TemporaryDirectory() as temp_dir:
        memory = SnapshotMemory()
        service = LearningService(
            Path(temp_dir) / "learning.sock",
            Path(temp_dir) / "learning",
            operational_memory=memory,
        )
        service.thompson_client = SuccessfulThompson()

        response = json.loads(service._process_request(json.dumps({
            "op": "process_outcome",
            "task_id": "snapshot_failure_001",
            "task_type": "testing",
            "model": "haiku",
            "rating": 4,
            "tokens": 1000,
            "cost": 0.005,
        })))

        assert response["ok"] is False
        assert response["thompson"] is True
        assert response["thompson_state_memory"] is False
        assert response["checkpoint_advanced"] is False
        assert not service.system.is_processed("snapshot_failure_001")
        assert [event[1] for event in memory.events] == [
            "learning.outcome",
            "thompson.state",
        ]
