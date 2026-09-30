#!/usr/bin/env python3
"""
Test Thompson Router Service and Client
"""

import sys
import os
import time
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.thompson_client import ThompsonClient
from shared.request_context import RequestContext
from thompson_service import ThompsonService, STATE_FILE, SOCKET_PATH

def test_service():
    """Test Thompson Service with direct instantiation"""
    print("\n" + "="*70)
    print("TEST 1: Direct Service Instantiation")
    print("="*70)

    # Create a test state file
    test_state_file = Path('/tmp/thompson-test-state.json')
    if test_state_file.exists():
        test_state_file.unlink()

    service = ThompsonService(SOCKET_PATH, test_state_file)

    # Test model selection
    print("\n[1.1] Testing select_model...")
    model1 = service.state.select_model(task_type="test-task", required_capability=0.5)
    print(f"  Selected: {model1}")
    assert model1 == "haiku", "Empty state should return haiku"

    # Test recording outcomes
    print("\n[1.2] Testing record_outcome...")
    service.state.record_outcome("haiku", "test-task", success=True, cost=0.01, tokens=100)
    service.state.record_outcome("sonnet", "test-task", success=True, cost=0.05, tokens=500)
    service.state.record_outcome("sonnet", "test-task", success=False, cost=0.05, tokens=500)
    service.state.record_outcome("opus", "test-task", success=True, cost=0.10, tokens=1000)
    print("  Recorded outcomes for haiku, sonnet (2x), opus")

    # Get state
    print("\n[1.3] Testing get_state...")
    state = service.state.get_state()
    print(f"  Models in state: {list(state['models'].keys())}")
    for name, stats in state['models'].items():
        print(f"    {name}: {stats['successes']}/{stats['calls']} success, "
              f"${stats['total_cost']:.4f} total")

    # Test selection with recorded data
    print("\n[1.4] Testing selection with priors...")
    for i in range(5):
        model = service.state.select_model(task_type="test-task", required_capability=0.5)
        print(f"  Sample {i+1}: {model}")

    # Test reset
    print("\n[1.5] Testing reset...")
    service.state.reset("haiku")
    state = service.state.get_state()
    haiku_stats = state['models'].get('haiku')
    print(f"  Haiku after reset: {haiku_stats['successes']}/{haiku_stats['calls']} success")

    # Test cost constraint
    print("\n[1.6] Testing cost constraints...")
    model_cheap = service.state.select_model(task_type="test-task", max_cost=0.02)
    model_expensive = service.state.select_model(task_type="test-task", max_cost=0.15)
    print(f"  Model with max_cost=0.02: {model_cheap}")
    print(f"  Model with max_cost=0.15: {model_expensive}")

    # Clean up
    test_state_file.unlink()
    print("\n✓ All direct service tests passed!")


def test_client():
    """Test Thompson Client"""
    print("\n" + "="*70)
    print("TEST 2: Thompson Client (without running daemon)")
    print("="*70)

    client = ThompsonClient()

    # Test ping (should fail gracefully)
    print("\n[2.1] Testing graceful degradation (daemon not running)...")
    result = client.ping()
    print(f"  Ping result (expected False): {result}")

    # Test fallback behavior
    print("\n[2.2] Testing fallback behavior...")
    model = client.select_model("test-task")
    print(f"  Selected model (expected haiku): {model}")
    assert model == "haiku", "Should fallback to haiku when service unavailable"

    print("\n✓ All client tests passed!")


def test_request_format():
    """Test request/response format validation"""
    print("\n" + "="*70)
    print("TEST 3: Request/Response Formats")
    print("="*70)

    test_state_file = Path('/tmp/thompson-test-state2.json')
    if test_state_file.exists():
        test_state_file.unlink()

    service = ThompsonService(SOCKET_PATH, test_state_file)

    # Prepare some data. Capability scores are required by the request below.
    service.state.register_model("haiku", 0.8)
    service.state.register_model("sonnet", 0.9)
    service.state.record_outcome("haiku", "code-review", success=True, cost=0.01, tokens=100)
    service.state.record_outcome("sonnet", "code-review", success=True, cost=0.05, tokens=500)

    ctx = RequestContext(caller="test", method="test_request_format")

    print("\n[3.1] Testing select_model request...")
    request = json.dumps({
        'action': 'select_model',
        'task_type': 'code-review',
        'required_capability': 0.7,
        'max_cost': 0.10
    })
    response = service._process_request(request, ctx)
    resp_data = json.loads(response)
    print(f"  Request: {request}")
    print(f"  Response: {response}")
    assert resp_data['ok'], "select_model should succeed"
    assert 'model' in resp_data, "Response should contain model"

    print("\n[3.2] Testing record_outcome request...")
    request = json.dumps({
        'action': 'record_outcome',
        'model': 'haiku',
        'task_type': 'code-review',
        'success': True,
        'cost': 0.01,
        'tokens': 100
    })
    response = service._process_request(request, ctx)
    resp_data = json.loads(response)
    print(f"  Request: {request}")
    print(f"  Response: {response}")
    assert resp_data['ok'], "record_outcome should succeed"

    print("\n[3.3] Testing get_state request...")
    request = json.dumps({'action': 'get_state'})
    response = service._process_request(request, ctx)
    resp_data = json.loads(response)
    print(f"  Response keys: {list(resp_data.keys())}")
    assert resp_data['ok'], "get_state should succeed"
    assert 'state' in resp_data, "Response should contain state"
    assert 'models' in resp_data['state'], "State should contain models"

    print("\n[3.4] Testing reset request...")
    request = json.dumps({'action': 'reset', 'model': 'haiku'})
    response = service._process_request(request, ctx)
    resp_data = json.loads(response)
    print(f"  Response: {response}")
    assert resp_data['ok'], "reset should succeed"

    print("\n[3.5] Testing ping request...")
    request = json.dumps({'action': 'ping'})
    response = service._process_request(request, ctx)
    resp_data = json.loads(response)
    print(f"  Response: {response}")
    assert resp_data['ok'], "ping should succeed"

    print("\n[3.6] Testing invalid action...")
    request = json.dumps({'action': 'invalid'})
    response = service._process_request(request, ctx)
    resp_data = json.loads(response)
    print(f"  Response: {response}")
    assert not resp_data['ok'], "Invalid action should fail"

    # Clean up
    test_state_file.unlink()
    print("\n✓ All request/response tests passed!")


def test_task_scoped_thompson_statistics_and_capability_filter():
    """Task history and capability requirements must constrain selection."""
    test_state_file = Path('/tmp/thompson-test-task-routing.json')
    if test_state_file.exists():
        test_state_file.unlink()

    service = ThompsonService(SOCKET_PATH, test_state_file)
    service.state.register_model("model-a", 0.4)
    service.state.register_model("model-b", 0.8)

    service.state.record_outcome("model-a", "task-a", True, 0.01, 10)
    service.state.record_outcome("model-b", "task-b", True, 0.01, 10)

    with patch("thompson_service.np.random.beta", side_effect=[0.9, 0.1]):
        assert service.state.select_model("task-a", required_capability=0.0) == "model-a"

    with patch("thompson_service.np.random.beta", side_effect=[0.1, 0.9]):
        assert service.state.select_model("task-b", required_capability=0.0) == "model-b"

    with patch("thompson_service.np.random.beta", return_value=0.1):
        assert service.state.select_model("task-a", required_capability=0.7) == "model-b"

    test_state_file.unlink()


def test_register_model_capability_persists():
    """Registered capabilities survive a state reload."""
    test_state_file = Path('/tmp/thompson-test-capability.json')
    if test_state_file.exists():
        test_state_file.unlink()

    service = ThompsonService(SOCKET_PATH, test_state_file)
    assert service.state.register_model("model-a", 0.75) is True

    reloaded = ThompsonService(SOCKET_PATH, test_state_file)
    assert reloaded.state.capabilities["model-a"] == 0.75

    test_state_file.unlink()


def test_max_cost_is_hard_constraint():
    """A finite max_cost must never return an over-budget model."""
    test_state_file = Path('/tmp/thompson-test-max-cost-final.json')
    if test_state_file.exists():
        test_state_file.unlink()

    service = ThompsonService(SOCKET_PATH, test_state_file)
    service.state.record_outcome("cheap", "test-task", True, 0.05, 100)
    service.state.record_outcome("expensive", "test-task", True, 0.10, 100)

    assert service.state.select_model("test-task", max_cost=0.05) == "cheap"
    assert service.state.select_model("test-task", max_cost=0.01) is None

    response = json.loads(service._process_request(
        json.dumps({
            'action': 'select_model',
            'task_type': 'test-task',
            'max_cost': 0.01,
        }),
        RequestContext(caller="test", method="select_model"),
    ))
    assert response['ok'] is False
    assert response['error'] == 'No model satisfies routing constraints'

    test_state_file.unlink()


def test_corrupt_state_preserves_existing_state():
    """A failed initial load stays empty and a failed reload preserves valid state."""
    valid_state = {
        'last_updated': '2026-09-30T00:00:00',
        'models': {
            'model-a': {
                'model_name': 'model-a',
                'successes': 1,
                'failures': 0,
                'total_cost': 0.01,
                'total_tokens': 10,
                'calls': 1,
            }
        },
        'tasks': {
            'task-a': {
                'model-a': {
                    'model_name': 'model-a',
                    'successes': 1,
                    'failures': 0,
                    'total_cost': 0.01,
                    'total_tokens': 10,
                    'calls': 1,
                },
            }
        },
        'capabilities': {
            'model-a': 0.9,
        },
    }
    corrupt_state = {
        'models': {
            'model-a': valid_state['models']['model-a'],
        },
        'tasks': {
            'task-a': {
                'model-a': valid_state['tasks']['task-a']['model-a'],
                'broken': {'successes': 1},
            }
        },
        'capabilities': {'model-a': 0.9},
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        test_state_file = Path(temp_dir) / 'thompson-test-corrupt-state.json'

        # Failed initial load preserves the constructor's empty state and timestamp.
        test_state_file.write_text(json.dumps(corrupt_state))
        initial_service = ThompsonService(SOCKET_PATH, test_state_file)
        assert initial_service.state.models == {}
        assert initial_service.state.task_models == {}
        assert initial_service.state.capabilities == {}

        # Failed reload must preserve the complete previously valid state.
        test_state_file.write_text(json.dumps(valid_state))
        service = ThompsonService(SOCKET_PATH, test_state_file)
        previous_state = service.state.get_state()
        previous_timestamp = service.state.last_updated

        test_state_file.write_text(json.dumps(corrupt_state))
        service.state._load()

        assert service.state.get_state() == previous_state
        assert service.state.last_updated == previous_timestamp

if __name__ == '__main__':
    try:
        test_service()
        test_client()
        test_request_format()

        print("\n" + "="*70)
        print("ALL TESTS PASSED!")
        print("="*70)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
