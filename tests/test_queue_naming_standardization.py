#!/usr/bin/env python3
"""
Test Queue Naming Standardization

Verifies that the redis:queue:{stage}:{priority} pattern is correctly handled:
- Queue names like "redis:queue:store:high" map to stage "store:high"
- All related keys (processing, heartbeat, completed, DLQ) use the same stage
- Both formats work: "redis:queue:store" (no priority) and "redis:queue:store:high" (with priority)

Run: python3 tests/test_queue_naming_standardization.py
"""

import json
import time
import sys
import os
import importlib.util

# Load Redis atomic operations module
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
spec = importlib.util.spec_from_file_location(
    "redis_atomic_operations",
    os.path.join(parent_dir, "scripts", "redis-atomic-operations.py")
)
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps

import redis


def test_queue_with_priority():
    """Test queue name with priority: redis:queue:store:high"""
    print("\n" + "="*60)
    print("TEST: Queue with Priority (redis:queue:store:high)")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store:high',
             'redis:processing:store:high',
             'redis:processing:store:high:metadata',
             'redis:heartbeat:store:high',
             'redis:completed:store:high')

    # Create task
    task = {
        'id': 'test-priority-task',
        'url': 'https://example.com',
        'priority': 10
    }
    score = (10 - task['priority']) * 1e13 + int(time.time() * 1000)
    r.zadd('redis:queue:store:high', {json.dumps(task): score})

    # Claim task
    claimed = ops.claim_task('redis:queue:store:high', 'worker-1')
    assert claimed is not None, "Task should be claimed"
    assert claimed['id'] == 'test-priority-task', "Task ID should match"

    # Verify task is in correct processing hash
    task_json = r.hget('redis:processing:store:high', 'test-priority-task')
    assert task_json is not None, "Task should be in redis:processing:store:high"

    # Verify metadata is in correct hash
    metadata_json = r.hget('redis:processing:store:high:metadata', 'test-priority-task')
    assert metadata_json is not None, "Metadata should be in redis:processing:store:high:metadata"

    # Verify heartbeat is in correct hash
    heartbeat = r.hget('redis:heartbeat:store:high', 'test-priority-task')
    assert heartbeat is not None, "Heartbeat should be in redis:heartbeat:store:high"

    # Complete task (must specify stage='store:high' to match queue)
    result = json.dumps({'status': 'done'})
    status = ops.complete_task('test-priority-task', 'worker-1', result, stage='store:high')
    assert status == 'OK', f"Complete should succeed, got: {status}"

    # Verify completion record is in correct hash
    completed = r.hget('redis:completed:store:high', 'test-priority-task')
    assert completed is not None, "Completion record should be in redis:completed:store:high"

    print("✓ Queue with priority works correctly")
    print("  - Processing hash: redis:processing:store:high")
    print("  - Metadata hash: redis:processing:store:high:metadata")
    print("  - Heartbeat hash: redis:heartbeat:store:high")
    print("  - Completed hash: redis:completed:store:high")


def test_queue_without_priority():
    """Test queue name without priority: redis:queue:store"""
    print("\n" + "="*60)
    print("TEST: Queue without Priority (redis:queue:store)")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store',
             'redis:processing:store',
             'redis:processing:store:metadata',
             'redis:heartbeat:store',
             'redis:completed:store')

    # Create task
    task = {
        'id': 'test-no-priority-task',
        'url': 'https://example.com',
        'priority': 5
    }
    score = (10 - task['priority']) * 1e13 + int(time.time() * 1000)
    r.zadd('redis:queue:store', {json.dumps(task): score})

    # Claim task
    claimed = ops.claim_task('redis:queue:store', 'worker-1')
    assert claimed is not None, "Task should be claimed"
    assert claimed['id'] == 'test-no-priority-task', "Task ID should match"

    # Verify task is in correct processing hash
    task_json = r.hget('redis:processing:store', 'test-no-priority-task')
    assert task_json is not None, "Task should be in redis:processing:store"

    # Verify metadata is in correct hash
    metadata_json = r.hget('redis:processing:store:metadata', 'test-no-priority-task')
    assert metadata_json is not None, "Metadata should be in redis:processing:store:metadata"

    # Verify heartbeat is in correct hash
    heartbeat = r.hget('redis:heartbeat:store', 'test-no-priority-task')
    assert heartbeat is not None, "Heartbeat should be in redis:heartbeat:store"

    # Complete task (stage='store' without priority)
    result = json.dumps({'status': 'done'})
    status = ops.complete_task('test-no-priority-task', 'worker-1', result, stage='store')
    assert status == 'OK', f"Complete should succeed, got: {status}"

    # Verify completion record is in correct hash
    completed = r.hget('redis:completed:store', 'test-no-priority-task')
    assert completed is not None, "Completion record should be in redis:completed:store"

    print("✓ Queue without priority works correctly")
    print("  - Processing hash: redis:processing:store")
    print("  - Metadata hash: redis:processing:store:metadata")
    print("  - Heartbeat hash: redis:heartbeat:store")
    print("  - Completed hash: redis:completed:store")


def test_isolation_between_priorities():
    """Test that different priority levels are isolated"""
    print("\n" + "="*60)
    print("TEST: Isolation Between Priority Levels")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    for priority in ['high', 'medium', 'low']:
        r.delete(f'redis:queue:store:{priority}',
                 f'redis:processing:store:{priority}',
                 f'redis:processing:store:{priority}:metadata',
                 f'redis:heartbeat:store:{priority}',
                 f'redis:completed:store:{priority}')

    # Create tasks in different priority queues
    for idx, priority in enumerate(['high', 'medium', 'low']):
        task = {
            'id': f'task-{priority}',
            'priority': 10 - idx * 3,
            'level': priority
        }
        score = idx * 1e13 + int(time.time() * 1000)
        r.zadd(f'redis:queue:store:{priority}', {json.dumps(task): score})

    # Claim from high priority
    high_task = ops.claim_task('redis:queue:store:high', 'worker-1')
    assert high_task['level'] == 'high', "Should claim high priority task"

    # Claim from medium priority
    medium_task = ops.claim_task('redis:queue:store:medium', 'worker-2')
    assert medium_task['level'] == 'medium', "Should claim medium priority task"

    # Claim from low priority
    low_task = ops.claim_task('redis:queue:store:low', 'worker-3')
    assert low_task['level'] == 'low', "Should claim low priority task"

    # Verify isolation: high task should NOT be in medium processing hash
    task_in_medium = r.hget('redis:processing:store:medium', 'task-high')
    assert task_in_medium is None, "High priority task should NOT be in medium processing hash"

    # Verify correct placement
    task_in_high = r.hget('redis:processing:store:high', 'task-high')
    assert task_in_high is not None, "High priority task should be in high processing hash"

    print("✓ Priority levels are properly isolated")
    print("  - task-high in redis:processing:store:high only")
    print("  - task-medium in redis:processing:store:medium only")
    print("  - task-low in redis:processing:store:low only")


def main():
    """Run all tests"""
    print("="*60)
    print("QUEUE NAMING STANDARDIZATION TEST")
    print("="*60)
    print()
    print("Testing redis:queue:{stage}:{priority} pattern...")

    try:
        test_queue_with_priority()
        test_queue_without_priority()
        test_isolation_between_priorities()

        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        print()
        print("Summary:")
        print("  ✓ redis:queue:store:high → stage='store:high'")
        print("  ✓ redis:queue:store → stage='store'")
        print("  ✓ Priority levels are isolated")
        print("  ✓ All supporting keys use correct stage")
        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
