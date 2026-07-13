#!/usr/bin/env python3
"""
Test complete_task() HYBRID Mode Support

Verifies that complete_task() can push to either:
- List queues (FIFO with LPUSH) - for sequential processing
- Sorted set queues (Priority with ZADD) - for priority-based processing

This test is separate from test-redis-bug-fixes.py to focus on the HYBRID mode feature.

Usage:
    python3 scripts/test-complete-hybrid-mode.py
"""

import json
import time
import sys
import os
import importlib.util

# Load Redis atomic operations module
script_dir = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("redis_atomic_operations", os.path.join(script_dir, "redis-atomic-operations.py"))
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps

import redis


def test_complete_to_list():
    """Test complete_task with next_queue_mode='list' (LPUSH)."""
    print("\n" + "="*70)
    print("TEST 1: complete_task() → LIST queue (FIFO with LPUSH)")
    print("="*70)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store', 'redis:queue:chunk',
             'redis:processing:store', 'redis:processing:store:metadata',
             'redis:heartbeat:store', 'redis:completed:store')

    # Create and claim task
    task = {
        'id': 'test-list-mode',
        'url': 'https://example.com/doc.html',
        'priority': 8,
        'metadata': {'category': 'docs'}
    }

    r.zadd('redis:queue:store', {json.dumps(task): 1000})
    claimed = ops.claim_task('redis:queue:store', 'worker-1')

    print(f"✓ Claimed task: {claimed['id']}")

    # Complete with next_queue_mode='list'
    result = {'processed_at': int(time.time() * 1000), 'chunks': 5}
    status = ops.complete_task(
        'test-list-mode',
        'worker-1',
        json.dumps(result),
        stage='store',
        next_queue='redis:queue:chunk',
        next_queue_mode='list'  # FIFO queue
    )

    assert status == 'OK', f"Complete should succeed, got: {status}"
    print(f"✓ Complete status: {status}")

    # Verify task is in list queue (RPOP for LPUSH)
    next_task_json = r.rpop('redis:queue:chunk')
    assert next_task_json is not None, "Task should be in list queue"

    next_task = json.loads(next_task_json)

    # Verify fields
    assert next_task['url'] == 'https://example.com/doc.html', "URL should be preserved"
    assert next_task['metadata']['category'] == 'docs', "Metadata should be preserved"
    assert next_task['chunks'] == 5, "Result should be merged"
    assert next_task['previous_worker'] == 'worker-1', "Completion metadata should be added"

    print("✓ Task pushed to LIST queue via LPUSH")
    print(f"  - Original fields: url={next_task['url']}, metadata={next_task['metadata']}")
    print(f"  - Result fields: chunks={next_task['chunks']}")
    print(f"  - Completion metadata: previous_worker={next_task['previous_worker']}")


def test_complete_to_zset():
    """Test complete_task with next_queue_mode='zset' (ZADD)."""
    print("\n" + "="*70)
    print("TEST 2: complete_task() → ZSET queue (Priority with ZADD)")
    print("="*70)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store', 'redis:queue:embed',
             'redis:processing:store', 'redis:processing:store:metadata',
             'redis:heartbeat:store', 'redis:completed:store')

    # Create and claim HIGH priority task
    task = {
        'id': 'test-zset-mode',
        'url': 'https://example.com/urgent.html',
        'priority': 9,  # High priority
        'metadata': {'urgency': 'critical'}
    }

    r.zadd('redis:queue:store', {json.dumps(task): 1000})
    claimed = ops.claim_task('redis:queue:store', 'worker-2')

    print(f"✓ Claimed task: {claimed['id']} (priority={claimed['priority']})")

    # Complete with next_queue_mode='zset'
    result = {'processed_at': int(time.time() * 1000), 'vector_id': 'v123'}
    status = ops.complete_task(
        'test-zset-mode',
        'worker-2',
        json.dumps(result),
        stage='store',
        next_queue='redis:queue:embed',
        next_queue_mode='zset'  # Priority queue
    )

    assert status == 'OK', f"Complete should succeed, got: {status}"
    print(f"✓ Complete status: {status}")

    # Verify task is in priority queue (ZPOPMIN)
    priority_result = r.zpopmin('redis:queue:embed', 1)
    assert priority_result and len(priority_result) > 0, "Task should be in priority queue"

    next_task_json, score = priority_result[0]
    next_task = json.loads(next_task_json)

    # Verify fields
    assert next_task['url'] == 'https://example.com/urgent.html', "URL should be preserved"
    assert next_task['priority'] == 9, "Priority should be preserved"
    assert next_task['metadata']['urgency'] == 'critical', "Metadata should be preserved"
    assert next_task['vector_id'] == 'v123', "Result should be merged"
    assert next_task['previous_worker'] == 'worker-2', "Completion metadata should be added"

    # Verify score (higher priority = lower score)
    # Score formula: (10 - priority) * 1e13 + timestamp
    # Priority 9 → (10 - 9) * 1e13 + timestamp = 1e13 + timestamp
    expected_min_score = 1e13
    expected_max_score = 2e13
    assert expected_min_score <= score <= expected_max_score, \
        f"Score {score} should be in range [{expected_min_score}, {expected_max_score}]"

    print("✓ Task pushed to ZSET queue via ZADD")
    print(f"  - Original fields: url={next_task['url']}, priority={next_task['priority']}")
    print(f"  - Result fields: vector_id={next_task['vector_id']}")
    print(f"  - Score: {score:.0f} (priority={next_task['priority']})")


def test_default_mode():
    """Test that default mode is 'list' (backward compatible)."""
    print("\n" + "="*70)
    print("TEST 3: Default mode (should be 'list' for backward compatibility)")
    print("="*70)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store', 'redis:queue:chunk',
             'redis:processing:store', 'redis:processing:store:metadata',
             'redis:heartbeat:store', 'redis:completed:store')

    # Create and claim task
    task = {'id': 'test-default', 'url': 'https://example.com/default.html'}

    r.zadd('redis:queue:store', {json.dumps(task): 1000})
    claimed = ops.claim_task('redis:queue:store', 'worker-3')

    # Complete WITHOUT specifying next_queue_mode (should default to 'list')
    result = {'processed': True}
    status = ops.complete_task(
        'test-default',
        'worker-3',
        json.dumps(result),
        stage='store',
        next_queue='redis:queue:chunk'
        # Note: next_queue_mode NOT specified
    )

    assert status == 'OK', f"Complete should succeed, got: {status}"

    # Verify task is in LIST queue (not ZSET)
    next_task_json = r.rpop('redis:queue:chunk')
    assert next_task_json is not None, "Task should be in list queue (default mode)"

    # Verify it's NOT in ZSET
    zset_result = r.zpopmin('redis:queue:chunk', 1)
    assert not zset_result or len(zset_result) == 0, "Task should NOT be in ZSET queue"

    print("✓ Default mode is 'list' (backward compatible)")
    print("  - Task pushed to LIST queue")
    print("  - ZSET queue is empty")


def main():
    print("\n" + "="*80)
    print("COMPLETE_TASK HYBRID MODE TEST SUITE")
    print("="*80)
    print("\nVerifying that complete_task() supports both:")
    print("  - next_queue_mode='list' → LPUSH to FIFO queue")
    print("  - next_queue_mode='zset' → ZADD to priority queue")

    try:
        test_complete_to_list()
        test_complete_to_zset()
        test_default_mode()

        print("\n" + "="*80)
        print("ALL TESTS PASSED ✓")
        print("="*80)
        print("\nSummary:")
        print("1. ✓ complete_task can push to FIFO list queue (LPUSH)")
        print("2. ✓ complete_task can push to priority queue (ZADD)")
        print("3. ✓ Default mode is 'list' (backward compatible)")
        print("\nUse cases:")
        print("  - Store → Chunk: next_queue_mode='list' (sequential chunking)")
        print("  - Chunk → Embed: next_queue_mode='list' (sequential embedding)")
        print("  - Embed → Graph: next_queue_mode='zset' (prioritize important docs)")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
