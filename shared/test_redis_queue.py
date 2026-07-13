#!/usr/bin/env python3
"""
Test Redis queue O(1) operations.

Tests:
1. Add task (O(1) - RPUSH)
2. Claim task (O(1) - BLPOP + HSET)
3. Complete task (O(1) - HGET + HDEL + HSET)
4. Fail task (O(1) - HGET + HDEL + HSET)
5. Stats (O(1) - LLEN + HLEN)
"""

import sys
import time
import redis
from redis_queue import RedisQueue


def test_basic_operations():
    """Test basic queue operations."""
    print("Testing Redis Queue O(1) operations...")

    # Connect to local Redis (no Sentinel for testing)
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
    except redis.ConnectionError:
        print("ERROR: Cannot connect to Redis on localhost:6379")
        print("Start Redis with: redis-server --port 6379")
        return False

    # Create queue
    queue = RedisQueue('test-queue', redis_client)

    # Clear queue
    redis_client.delete(queue.pending_key)
    redis_client.delete(queue.processing_key)
    redis_client.delete(queue.completed_key)
    redis_client.delete(queue.failed_key)

    print("\n1. Testing add (O(1) - RPUSH)")
    queue.add('task-1', {'url': 'https://example.com/page1'})
    queue.add('task-2', {'url': 'https://example.com/page2'})
    queue.add('task-3', {'url': 'https://invalid-url'})
    stats = queue.stats()
    assert stats['pending'] == 3, f"Expected 3 pending, got {stats['pending']}"
    print(f"   ✓ Added 3 tasks: {stats}")

    print("\n2. Testing claim (O(1) - BLPOP + HSET)")
    task1 = queue.claim('worker-1', timeout=1)
    assert task1 is not None, "Expected to claim task"
    assert task1['task_id'] == 'task-1', f"Expected task-1, got {task1['task_id']}"
    stats = queue.stats()
    assert stats['pending'] == 2, f"Expected 2 pending, got {stats['pending']}"
    assert stats['processing'] == 1, f"Expected 1 processing, got {stats['processing']}"
    print(f"   ✓ Claimed task-1: {stats}")

    print("\n3. Testing complete (O(1) - HGET + HDEL + HSET)")
    success = queue.complete('task-1', {'status': 'success', 'size': 1024})
    assert success, "Complete should return True"
    stats = queue.stats()
    assert stats['processing'] == 0, f"Expected 0 processing, got {stats['processing']}"
    assert stats['completed'] == 1, f"Expected 1 completed, got {stats['completed']}"
    print(f"   ✓ Completed task-1: {stats}")

    print("\n4. Testing fail (O(1) - HGET + HDEL + HSET)")
    task2 = queue.claim('worker-2', timeout=1)
    task3 = queue.claim('worker-2', timeout=1)
    assert task3['task_id'] == 'task-3', "Expected task-3"

    success = queue.fail('task-3', 'Invalid URL format')
    assert success, "Fail should return True"
    stats = queue.stats()
    assert stats['processing'] == 1, f"Expected 1 processing (task-2), got {stats['processing']}"
    assert stats['failed'] == 1, f"Expected 1 failed, got {stats['failed']}"
    print(f"   ✓ Failed task-3: {stats}")

    # Complete remaining task
    queue.complete('task-2', {'status': 'success'})

    print("\n5. Testing stats (O(1) - LLEN + HLEN)")
    final_stats = queue.stats()
    print(f"   ✓ Final stats: {final_stats}")
    assert final_stats['pending'] == 0
    assert final_stats['processing'] == 0
    assert final_stats['completed'] == 2
    assert final_stats['failed'] == 1

    print("\n✅ All O(1) operations working correctly!")
    return True


def test_performance():
    """Test performance of O(1) operations."""
    print("\n\nPerformance Test")
    print("=" * 50)

    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
    except redis.ConnectionError:
        print("ERROR: Cannot connect to Redis")
        return False

    queue = RedisQueue('perf-test', redis_client)

    # Clear
    redis_client.delete(queue.pending_key)
    redis_client.delete(queue.processing_key)
    redis_client.delete(queue.completed_key)
    redis_client.delete(queue.failed_key)

    # Test add
    n = 1000
    start = time.time()
    for i in range(n):
        queue.add(f'task-{i}', {'index': i})
    add_time = (time.time() - start) * 1000 / n
    print(f"Add:      {add_time:.3f}ms per task (n={n})")

    # Test claim + complete
    start = time.time()
    for i in range(n):
        task = queue.claim(f'worker-{i % 10}', timeout=0.1)
        if task:
            queue.complete(task['task_id'], {'result': 'ok'})
    claim_complete_time = (time.time() - start) * 1000 / n
    print(f"Claim+Complete: {claim_complete_time:.3f}ms per task (n={n})")

    # Test stats
    start = time.time()
    for _ in range(100):
        queue.stats()
    stats_time = (time.time() - start) * 1000 / 100
    print(f"Stats:    {stats_time:.3f}ms per call (n=100)")

    print("\n✅ Performance test complete!")
    return True


if __name__ == '__main__':
    success = test_basic_operations()

    if success:
        test_performance()
        sys.exit(0)
    else:
        sys.exit(1)
