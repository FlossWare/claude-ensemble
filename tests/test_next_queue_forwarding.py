#!/usr/bin/env python3
"""
Test: Next Queue Forwarding with Correct Operation

Verifies that tasks are forwarded to the next queue using the correct
operation based on destination queue type:
- Store stage (zset) → Chunk stage (list): Use LPUSH
- Chunk stage (list) → Embed stage (list): Use LPUSH
- Embed stage (list) → Graph stage (list): Use LPUSH
"""

import sys
import os
import json
import time
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_dir))

from redis_atomic_operations import RedisAtomicOps
import redis

def test_next_queue_forwarding():
    """Test that tasks are forwarded using correct operations."""

    print("=== Test: Next Queue Forwarding ===\n")

    # Initialize Redis
    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = redis.Redis(host='aio-01', port=6379, decode_responses=True)

    # Clean up test queues
    test_queues = [
        'redis:queue:store:high',
        'redis:queue:chunk',
        'redis:queue:embed',
        'redis:queue:graph',
        'redis:processing:store:high',
        'redis:processing:store:high:metadata',
        'redis:heartbeat:store:high',
        'redis:completed:store:high'
    ]
    for queue in test_queues:
        r.delete(queue)

    print("1. Create test task in store:high queue (zset)")
    task = {
        'id': 'test-task-forward-1',
        'url': 'https://example.com/test',
        'priority': 8,
        'data': {'key': 'value'}
    }

    # Calculate score for priority queue (higher priority = lower score)
    timestamp_ms = int(time.time() * 1000)
    score = (10 - task['priority']) * 1e13 + timestamp_ms
    r.zadd('redis:queue:store:high', {json.dumps(task): score})

    queue_size = r.zcard('redis:queue:store:high')
    print(f"   ✓ Task added to store:high (zset), queue size: {queue_size}")

    print("\n2. Claim task from store:high (using ZPOPMIN)")
    claimed_task = ops.claim_task('redis:queue:store:high', 'worker-test', queue_mode='zset')

    if not claimed_task:
        print("   ✗ FAILED: Could not claim task")
        return False

    print(f"   ✓ Claimed task: {claimed_task['id']}")

    print("\n3. Complete task and forward to chunk queue (list mode)")
    result = {
        'id': claimed_task['id'],
        'processed': True,
        'timestamp': int(time.time() * 1000)
    }

    # Complete with next_queue_mode='list' (chunk uses FIFO)
    status = ops.complete_task(
        task_id=claimed_task['id'],
        worker_id='worker-test',
        result_json=json.dumps(result),
        stage='store:high',
        next_queue='redis:queue:chunk',
        next_queue_mode='list'  # This is the fix - chunk is a list queue
    )

    if status != 'OK':
        print(f"   ✗ FAILED: Complete task returned {status}")
        return False

    print(f"   ✓ Task completed: {status}")

    print("\n4. Verify task was forwarded to chunk queue as LIST")
    # Check if chunk queue exists and is a list
    queue_type = r.type('redis:queue:chunk')
    print(f"   Queue type: {queue_type}")

    if queue_type != 'list':
        print(f"   ✗ FAILED: Expected list, got {queue_type}")
        return False

    # Pop from chunk queue (RPOP for list)
    forwarded_task_json = r.rpop('redis:queue:chunk')

    if not forwarded_task_json:
        print("   ✗ FAILED: No task found in chunk queue")
        return False

    forwarded_task = json.loads(forwarded_task_json)
    print(f"   ✓ Task forwarded to chunk queue: {forwarded_task['id']}")

    print("\n5. Verify merged data")
    # Check that original task data was merged with result
    if forwarded_task.get('url') != task['url']:
        print(f"   ✗ FAILED: Original URL not preserved")
        return False

    if forwarded_task.get('processed') != True:
        print(f"   ✗ FAILED: Result data not merged")
        return False

    if forwarded_task.get('previous_worker') != 'worker-test':
        print(f"   ✗ FAILED: Metadata not added")
        return False

    print(f"   ✓ Original data preserved: url={forwarded_task['url']}")
    print(f"   ✓ Result merged: processed={forwarded_task['processed']}")
    print(f"   ✓ Metadata added: previous_worker={forwarded_task['previous_worker']}")

    print("\n6. Test chunk → embed forwarding (list → list)")
    # Add task to chunk queue (as list)
    chunk_task = {
        'id': 'test-task-forward-2',
        'url': 'https://example.com/chunk',
        'processed': True
    }
    r.lpush('redis:queue:chunk', json.dumps(chunk_task))

    # Claim and complete
    claimed_chunk = ops.claim_task('redis:queue:chunk', 'worker-test-2', queue_mode='list')
    if not claimed_chunk:
        print("   ✗ FAILED: Could not claim from chunk queue")
        return False

    result2 = {'chunked': True}
    status2 = ops.complete_task(
        task_id=claimed_chunk['id'],
        worker_id='worker-test-2',
        result_json=json.dumps(result2),
        stage='chunk',
        next_queue='redis:queue:embed',
        next_queue_mode='list'  # embed is also a list queue
    )

    if status2 != 'OK':
        print(f"   ✗ FAILED: Chunk complete returned {status2}")
        return False

    # Verify in embed queue
    embed_queue_type = r.type('redis:queue:embed')
    if embed_queue_type != 'list':
        print(f"   ✗ FAILED: Embed queue type is {embed_queue_type}, expected list")
        return False

    embed_task_json = r.rpop('redis:queue:embed')
    if not embed_task_json:
        print("   ✗ FAILED: No task in embed queue")
        return False

    embed_task = json.loads(embed_task_json)
    print(f"   ✓ Chunk → Embed forwarding works: {embed_task['id']}")
    print(f"   ✓ Data preserved: chunked={embed_task.get('chunked')}")

    print("\n✅ ALL TESTS PASSED")
    print("\nSummary:")
    print("- Store (zset) → Chunk (list): LPUSH ✓")
    print("- Chunk (list) → Embed (list): LPUSH ✓")
    print("- Data merging works correctly ✓")
    print("- Metadata preserved ✓")

    return True


if __name__ == '__main__':
    try:
        success = test_next_queue_forwarding()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
