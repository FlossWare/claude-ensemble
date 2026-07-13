#!/usr/bin/env python3
"""
Test Stuck Task Recovery

Verifies that stuck task recovery:
1. Correctly scans processing metadata hash for expired heartbeats
2. Requeues with FULL task data (not just task_id)
3. Preserves original task fields (url, priority, content, etc.)
4. Adds recovery metadata (recovered_at, previous_worker, etc.)
"""

import sys
import os
import json
import time
import redis

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from redis_atomic_operations import RedisAtomicOps

def cleanup_redis(r: redis.Redis, stage: str):
    """Clean up all Redis keys for a stage."""
    patterns = [
        f'redis:queue:{stage}*',
        f'redis:processing:{stage}*',
        f'redis:completed:{stage}*',
        f'redis:heartbeat:{stage}*',
        f'redis:dlq:{stage}*'
    ]
    for pattern in patterns:
        for key in r.scan_iter(match=pattern):
            r.delete(key)


def test_stuck_task_recovery_preserves_data():
    """Test that stuck task recovery preserves full task data."""

    print("Test: Stuck task recovery preserves full task data")
    print("=" * 60)

    # Setup
    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis
    stage = 'test_recovery'
    queue_name = f'redis:queue:{stage}'

    # Cleanup
    cleanup_redis(r, stage)

    # Create a task with rich data
    task = {
        'id': 'task-recovery-1',
        'url': 'https://example.com/docs/page1.html',
        'priority': 8,
        'content': 'Important firmware documentation',
        'metadata': {
            'source': 'web-scraper',
            'doc_type': 'firmware-manual'
        },
        'retry_count': 0
    }

    # Add to queue
    score = (10 - task['priority']) * 1e13 + int(time.time() * 1000)
    r.zadd(queue_name, {json.dumps(task): score})
    print(f"✓ Added task to queue: {task['id']}")

    # Claim task (heartbeat expires in 1 second for testing)
    claimed_task = ops.claim_task(queue_name, 'worker-test', heartbeat_ttl_ms=1000)
    print(f"✓ Claimed task: {claimed_task['id']}")

    # Verify task is in processing
    processing_hash = f'redis:processing:{stage}'
    processing_data = r.hget(processing_hash, task['id'])
    assert processing_data is not None, "Task should be in processing hash"
    processing_task = json.loads(processing_data)
    print(f"✓ Task in processing hash: {processing_task.keys()}")

    # Verify metadata exists
    metadata_hash = f'{processing_hash}:metadata'
    metadata_data = r.hget(metadata_hash, task['id'])
    assert metadata_data is not None, "Task metadata should exist"
    metadata = json.loads(metadata_data)
    print(f"✓ Task metadata exists: worker={metadata['worker_id']}, heartbeat_expires_at={metadata['heartbeat_expires_at']}")

    # Wait for heartbeat to expire
    print("⏳ Waiting 2 seconds for heartbeat to expire...")
    time.sleep(2)

    # Run recovery
    print("\n🔧 Running stuck task recovery...")
    recovered = ops.recover_stuck_tasks(stage, stuck_threshold_ms=1000)
    print(f"✓ Recovered {recovered} tasks")

    assert recovered == 1, f"Should recover exactly 1 task, got {recovered}"

    # Verify task is back in queue
    requeued_data = r.zpopmin(queue_name, 1)
    assert len(requeued_data) > 0, "Task should be back in queue"

    requeued_task = json.loads(requeued_data[0][0])
    print(f"\n📋 Requeued task data:")
    print(json.dumps(requeued_task, indent=2))

    # CRITICAL CHECKS: Verify FULL task data preserved
    print("\n🔍 Verification:")

    checks = [
        ('id', task['id'], requeued_task.get('id')),
        ('url', task['url'], requeued_task.get('url')),
        ('priority', task['priority'], requeued_task.get('priority')),
        ('content', task['content'], requeued_task.get('content')),
        ('metadata.source', task['metadata']['source'], requeued_task.get('metadata', {}).get('source')),
        ('metadata.doc_type', task['metadata']['doc_type'], requeued_task.get('metadata', {}).get('doc_type'))
    ]

    all_passed = True
    for field_name, expected, actual in checks:
        if expected == actual:
            print(f"  ✓ {field_name}: {actual}")
        else:
            print(f"  ✗ {field_name}: expected={expected}, actual={actual}")
            all_passed = False

    # Verify recovery metadata added
    recovery_checks = [
        'recovered_at',
        'previous_worker',
        'stuck_duration_ms',
        'recovery_reason'
    ]

    for field in recovery_checks:
        if field in requeued_task:
            print(f"  ✓ {field}: {requeued_task[field]}")
        else:
            print(f"  ✗ {field}: MISSING")
            all_passed = False

    # Verify NOT in processing anymore
    still_processing = r.hget(processing_hash, task['id'])
    if still_processing is None:
        print("  ✓ Task removed from processing hash")
    else:
        print("  ✗ Task still in processing hash (should be removed)")
        all_passed = False

    # Verify metadata removed
    still_has_metadata = r.hget(metadata_hash, task['id'])
    if still_has_metadata is None:
        print("  ✓ Task metadata removed")
    else:
        print("  ✗ Task metadata still exists (should be removed)")
        all_passed = False

    # Cleanup
    cleanup_redis(r, stage)

    if all_passed:
        print("\n✅ TEST PASSED: Stuck task recovery preserves full data")
        return True
    else:
        print("\n❌ TEST FAILED: Data loss detected in recovery")
        return False


def test_multiple_stuck_tasks():
    """Test recovery of multiple stuck tasks at once."""

    print("\n\nTest: Multiple stuck tasks recovery")
    print("=" * 60)

    # Setup
    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis
    stage = 'test_multi_recovery'
    queue_name = f'redis:queue:{stage}'

    # Cleanup
    cleanup_redis(r, stage)

    # Create 5 tasks with different data
    tasks = []
    for i in range(5):
        task = {
            'id': f'task-multi-{i}',
            'url': f'https://example.com/page{i}.html',
            'priority': 5 + i,
            'content': f'Content for task {i}',
            'index': i
        }
        tasks.append(task)
        score = (10 - task['priority']) * 1e13 + int(time.time() * 1000)
        r.zadd(queue_name, {json.dumps(task): score})

    print(f"✓ Added {len(tasks)} tasks to queue")

    # Claim all tasks (heartbeat expires in 1 second)
    for i, task in enumerate(tasks):
        claimed = ops.claim_task(queue_name, f'worker-{i}', heartbeat_ttl_ms=1000)
        assert claimed['id'] == task['id']

    print(f"✓ Claimed all {len(tasks)} tasks")

    # Wait for heartbeats to expire
    print("⏳ Waiting 2 seconds for heartbeats to expire...")
    time.sleep(2)

    # Run recovery
    print("\n🔧 Running stuck task recovery...")
    recovered = ops.recover_stuck_tasks(stage, stuck_threshold_ms=1000)
    print(f"✓ Recovered {recovered} tasks")

    assert recovered == 5, f"Should recover exactly 5 tasks, got {recovered}"

    # Verify all tasks back in queue with full data
    requeued = []
    while True:
        data = r.zpopmin(queue_name, 1)
        if not data:
            break
        requeued.append(json.loads(data[0][0]))

    print(f"✓ Found {len(requeued)} tasks in queue")
    assert len(requeued) == 5, f"Should have 5 tasks in queue, got {len(requeued)}"

    # Verify each task has full data
    all_valid = True
    for task in requeued:
        has_url = 'url' in task
        has_content = 'content' in task
        has_index = 'index' in task
        has_recovery = 'recovered_at' in task

        if has_url and has_content and has_index and has_recovery:
            print(f"  ✓ Task {task['id']}: full data preserved")
        else:
            print(f"  ✗ Task {task['id']}: missing data (url={has_url}, content={has_content}, index={has_index}, recovery={has_recovery})")
            all_valid = False

    # Cleanup
    cleanup_redis(r, stage)

    if all_valid:
        print("\n✅ TEST PASSED: Multiple stuck tasks recovered with full data")
        return True
    else:
        print("\n❌ TEST FAILED: Some tasks missing data")
        return False


def test_recovery_with_priority_stages():
    """Test recovery works with stage:priority naming (e.g., 'store:high')."""

    print("\n\nTest: Recovery with priority stages")
    print("=" * 60)

    # Setup
    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis
    stage = 'store:high'
    queue_name = f'redis:queue:{stage}'

    # Cleanup
    cleanup_redis(r, 'store')

    # Create task
    task = {
        'id': 'task-priority-1',
        'url': 'https://example.com/priority-test.html',
        'priority': 9,
        'stage': 'store',
        'priority_level': 'high'
    }

    score = (10 - task['priority']) * 1e13 + int(time.time() * 1000)
    r.zadd(queue_name, {json.dumps(task): score})
    print(f"✓ Added task to queue: {queue_name}")

    # Claim task
    claimed = ops.claim_task(queue_name, 'worker-priority', heartbeat_ttl_ms=1000)
    print(f"✓ Claimed task: {claimed['id']}")

    # Wait for heartbeat to expire
    print("⏳ Waiting 2 seconds for heartbeat to expire...")
    time.sleep(2)

    # Run recovery (with stage:priority format)
    print(f"\n🔧 Running stuck task recovery for stage '{stage}'...")
    recovered = ops.recover_stuck_tasks(stage, stuck_threshold_ms=1000)
    print(f"✓ Recovered {recovered} tasks")

    assert recovered == 1, f"Should recover exactly 1 task, got {recovered}"

    # Verify task back in queue
    requeued_data = r.zpopmin(queue_name, 1)
    assert len(requeued_data) > 0, "Task should be back in queue"

    requeued_task = json.loads(requeued_data[0][0])

    # Verify data preserved
    checks = [
        ('url', task['url'], requeued_task.get('url')),
        ('priority', task['priority'], requeued_task.get('priority')),
        ('stage', task['stage'], requeued_task.get('stage')),
        ('priority_level', task['priority_level'], requeued_task.get('priority_level'))
    ]

    all_passed = True
    for field_name, expected, actual in checks:
        if expected == actual:
            print(f"  ✓ {field_name}: {actual}")
        else:
            print(f"  ✗ {field_name}: expected={expected}, actual={actual}")
            all_passed = False

    # Cleanup
    cleanup_redis(r, 'store')

    if all_passed:
        print("\n✅ TEST PASSED: Priority stage recovery works")
        return True
    else:
        print("\n❌ TEST FAILED: Priority stage recovery failed")
        return False


if __name__ == '__main__':
    print("Running Stuck Task Recovery Tests")
    print("=" * 60)
    print()

    results = []

    # Run all tests
    results.append(("Single task recovery", test_stuck_task_recovery_preserves_data()))
    results.append(("Multiple tasks recovery", test_multiple_stuck_tasks()))
    results.append(("Priority stage recovery", test_recovery_with_priority_stages()))

    # Summary
    print("\n\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} TESTS FAILED")
        sys.exit(1)
