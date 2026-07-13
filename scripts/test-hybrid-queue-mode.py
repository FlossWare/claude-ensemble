#!/usr/bin/env python3
"""
Test HYBRID Queue Mode Support

Verifies that workers correctly handle both 'zset' and 'list' queue modes.

Tests:
1. ZSET mode: Priority-based processing (high priority first)
2. LIST mode: FIFO processing (oldest first)
3. Mode switching: Same worker code handles both modes
4. Batch claiming: Works in both modes
"""

import sys
import json
import time
import redis
from pathlib import Path

# Add scripts directory to path
script_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(script_dir))

# Import from redis-atomic-operations.py (with hyphen)
import importlib.util
spec = importlib.util.spec_from_file_location("redis_atomic_operations", script_dir / "redis-atomic-operations.py")
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps

# Configuration
REDIS_HOST = 'aio-01'
REDIS_PORT = 6379

def setup_redis():
    """Initialize Redis connection."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return r

def cleanup_queues(r):
    """Clean up test queues."""
    queues = [
        'test:queue:zset',
        'test:queue:list',
        'redis:processing:zset-test',
        'redis:processing:list-test',
        'redis:processing:zset-test:metadata',
        'redis:processing:list-test:metadata',
        'redis:heartbeat:zset-test',
        'redis:heartbeat:list-test',
        'redis:completed:zset-test',
        'redis:completed:list-test'
    ]
    for queue in queues:
        r.delete(queue)
    print("✓ Cleaned up test queues")

def test_zset_mode():
    """Test priority queue mode (ZSET)."""
    print("\n=== Test 1: ZSET Mode (Priority) ===")

    r = setup_redis()
    ops = RedisAtomicOps(host=REDIS_HOST, port=REDIS_PORT)

    # Create tasks with different priorities
    tasks = [
        {'id': 'task-low', 'priority': 3, 'data': 'Low priority'},
        {'id': 'task-high', 'priority': 10, 'data': 'High priority'},
        {'id': 'task-medium', 'priority': 6, 'data': 'Medium priority'}
    ]

    # Push to ZSET with priority scores
    # Formula: (10 - priority) * 1e13 + timestamp (lower score = higher priority)
    current_time = int(time.time() * 1000)
    for task in tasks:
        priority = task['priority']
        score = (10 - priority) * 1e13 + current_time
        r.zadd('test:queue:zset', {json.dumps(task): score})

    print(f"✓ Added 3 tasks to ZSET queue with priorities: 3, 10, 6")

    # Claim tasks in priority order
    claimed_order = []
    for i in range(3):
        task = ops.claim_task('test:queue:zset', f'worker-{i}', queue_mode='zset')
        if task:
            claimed_order.append((task['id'], task['priority']))
            print(f"  Claimed: {task['id']} (priority {task['priority']})")

    # Verify order: high (10) → medium (6) → low (3)
    expected_order = [('task-high', 10), ('task-medium', 6), ('task-low', 3)]
    if claimed_order == expected_order:
        print("✓ ZSET mode: Tasks claimed in priority order (high → low)")
        return True
    else:
        print(f"✗ ZSET mode FAILED: Expected {expected_order}, got {claimed_order}")
        return False

def test_list_mode():
    """Test FIFO queue mode (LIST)."""
    print("\n=== Test 2: LIST Mode (FIFO) ===")

    r = setup_redis()
    ops = RedisAtomicOps(host=REDIS_HOST, port=REDIS_PORT)

    # Create tasks with timestamps
    tasks = [
        {'id': 'task-1', 'timestamp': 1000, 'data': 'First'},
        {'id': 'task-2', 'timestamp': 2000, 'data': 'Second'},
        {'id': 'task-3', 'timestamp': 3000, 'data': 'Third'}
    ]

    # Push to LIST (LPUSH for FIFO with RPOP)
    for task in tasks:
        r.lpush('test:queue:list', json.dumps(task))

    print(f"✓ Added 3 tasks to LIST queue in order: task-1, task-2, task-3")

    # Claim tasks in FIFO order
    claimed_order = []
    for i in range(3):
        task = ops.claim_task('test:queue:list', f'worker-{i}', queue_mode='list')
        if task:
            claimed_order.append(task['id'])
            print(f"  Claimed: {task['id']}")

    # Verify order: task-1 → task-2 → task-3
    expected_order = ['task-1', 'task-2', 'task-3']
    if claimed_order == expected_order:
        print("✓ LIST mode: Tasks claimed in FIFO order (oldest → newest)")
        return True
    else:
        print(f"✗ LIST mode FAILED: Expected {expected_order}, got {claimed_order}")
        return False

def test_batch_claim_zset():
    """Test batch claiming in ZSET mode."""
    print("\n=== Test 3: Batch Claim (ZSET) ===")

    r = setup_redis()
    ops = RedisAtomicOps(host=REDIS_HOST, port=REDIS_PORT)

    # Create 5 tasks with priorities
    tasks = [
        {'id': f'task-{i}', 'priority': 10 - i, 'data': f'Task {i}'}
        for i in range(5)
    ]

    # Push to ZSET
    current_time = int(time.time() * 1000)
    for task in tasks:
        priority = task['priority']
        score = (10 - priority) * 1e13 + current_time
        r.zadd('test:queue:zset', {json.dumps(task): score})

    print(f"✓ Added 5 tasks to ZSET queue")

    # Batch claim 3 tasks
    claimed_tasks = ops.batch_claim_tasks('test:queue:zset', 'batch-worker', batch_size=3, queue_mode='zset')

    if len(claimed_tasks) == 3:
        print(f"✓ Batch claimed 3 tasks: {[t['id'] for t in claimed_tasks]}")

        # Verify priority order
        priorities = [t['priority'] for t in claimed_tasks]
        if priorities == sorted(priorities, reverse=True):
            print("✓ Batch claim respects priority order")
            return True
        else:
            print(f"✗ Priority order violated: {priorities}")
            return False
    else:
        print(f"✗ Batch claim FAILED: Expected 3 tasks, got {len(claimed_tasks)}")
        return False

def test_batch_claim_list():
    """Test batch claiming in LIST mode."""
    print("\n=== Test 4: Batch Claim (LIST) ===")

    r = setup_redis()
    ops = RedisAtomicOps(host=REDIS_HOST, port=REDIS_PORT)

    # Create 5 tasks
    tasks = [
        {'id': f'task-{i}', 'timestamp': 1000 + i * 100, 'data': f'Task {i}'}
        for i in range(5)
    ]

    # Push to LIST
    for task in tasks:
        r.lpush('test:queue:list', json.dumps(task))

    print(f"✓ Added 5 tasks to LIST queue")

    # Batch claim 3 tasks
    claimed_tasks = ops.batch_claim_tasks('test:queue:list', 'batch-worker', batch_size=3, queue_mode='list')

    if len(claimed_tasks) == 3:
        print(f"✓ Batch claimed 3 tasks: {[t['id'] for t in claimed_tasks]}")

        # Verify FIFO order
        task_ids = [t['id'] for t in claimed_tasks]
        if task_ids == ['task-0', 'task-1', 'task-2']:
            print("✓ Batch claim respects FIFO order")
            return True
        else:
            print(f"✗ FIFO order violated: {task_ids}")
            return False
    else:
        print(f"✗ Batch claim FAILED: Expected 3 tasks, got {len(claimed_tasks)}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("HYBRID Queue Mode Test Suite")
    print("=" * 60)

    r = setup_redis()

    # Cleanup before tests
    cleanup_queues(r)

    # Run tests
    results = []
    results.append(("ZSET Mode (Priority)", test_zset_mode()))

    cleanup_queues(r)
    results.append(("LIST Mode (FIFO)", test_list_mode()))

    cleanup_queues(r)
    results.append(("Batch Claim ZSET", test_batch_claim_zset()))

    cleanup_queues(r)
    results.append(("Batch Claim LIST", test_batch_claim_list()))

    # Final cleanup
    cleanup_queues(r)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    sys.exit(0 if passed == total else 1)

if __name__ == '__main__':
    main()
