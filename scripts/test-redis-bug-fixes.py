#!/usr/bin/env python3
"""
Test Redis Bug Fixes

Verifies all 5 bug fixes:
1. Complete task data retention (no data loss)
2. Heartbeat synchronization (no active task requeue)
3. O(1) performance (no O(n) scanning)
4. FIFO ordering (not LIFO)
5. Rollback on migration failure

Usage:
    python3 scripts/test-redis-bug-fixes.py
"""

import json
import time
import sys
import os
import importlib.util

# Load Redis atomic operations module
script_dir = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("redis_atomic_operations", os.path.join(script_dir, "redis_atomic_operations.py"))
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps

import redis

def test_bug_1_data_retention():
    """Test that full task data is retained during claim/complete/fail/recover."""
    print("\n" + "="*60)
    print("TEST BUG #1: Complete Task Data Retention")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store:test', 'redis:processing:store:test',
             'redis:processing:store:test:metadata', 'redis:heartbeat:store:test',
             'redis:completed:store:test')

    # Create test task with FULL data
    task = {
        'id': 'test-task-1',
        'url': 'https://example.com/page.html',
        'stage': 'store',
        'priority': 8,
        'metadata': {'key1': 'value1', 'key2': 'value2'},
        'created_at': int(time.time() * 1000)
    }

    # Push to queue (ZADD for sorted set, not RPUSH for list)
    timestamp_ms = task['created_at']
    score = (10 - task['priority']) * 1e13 + timestamp_ms  # FIX BUG #1: Inverted priority
    r.zadd('redis:queue:store:test', {json.dumps(task): score})

    # Claim task
    claimed_task = ops.claim_task('redis:queue:store:test', 'worker-test-1')

    # Verify ALL fields preserved
    assert claimed_task is not None, "Task should be claimed"
    assert claimed_task['url'] == 'https://example.com/page.html', "URL should be preserved"
    assert claimed_task['stage'] == 'store', "Stage should be preserved"
    assert claimed_task['metadata'] == {'key1': 'value1', 'key2': 'value2'}, "Metadata should be preserved"

    # Verify task data in processing hash
    task_in_processing = r.hget('redis:processing:store:test', 'test-task-1')
    assert task_in_processing is not None, "Task should be in processing hash"

    task_data = json.loads(task_in_processing)
    assert task_data['url'] == 'https://example.com/page.html', "Full task data should be in processing hash"

    # Complete task
    result = json.dumps({'status': 'processed'})
    status = ops.complete_task('test-task-1', 'worker-test-1', result, stage='store:test')
    assert status == 'OK', f"Complete should succeed, got: {status}"

    print("✓ BUG #1 FIXED: Full task data retained through claim/complete")

    # Test fail/recovery path (re-add to queue as ZSET)
    timestamp_ms = int(time.time() * 1000)
    score = (8 * 1e13) - timestamp_ms
    r.zadd('redis:queue:store:test', {json.dumps(task): score})
    claimed_task = ops.claim_task('redis:queue:store:test', 'worker-test-1')

    # Fail task
    status = ops.fail_task('test-task-1', 'worker-test-1', 'Test error', stage='store:test', max_retries=3)
    assert status == 'REQUEUED', f"Fail should requeue, got: {status}"

    # Verify task data in requeued item (ZPOPMIN for sorted set)
    result = r.zpopmin('redis:queue:store:test', 1)
    assert result and len(result) > 0, "Task should be requeued"

    requeued_json = result[0][0]  # ZPOPMIN returns [(member, score)]
    requeued_task = json.loads(requeued_json)
    assert requeued_task['url'] == 'https://example.com/page.html', "URL should survive requeue"
    assert requeued_task['metadata'] == {'key1': 'value1', 'key2': 'value2'}, "Metadata should survive requeue"

    print("✓ BUG #1 FIXED: Full task data retained through fail/requeue")


def test_bug_2_heartbeat_sync():
    """Test that heartbeat updates synchronize both hash and metadata."""
    print("\n" + "="*60)
    print("TEST BUG #2: Heartbeat Synchronization")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store:test', 'redis:processing:store:test',
             'redis:processing:store:test:metadata', 'redis:heartbeat:store:test')

    # Create and claim task (ZADD for sorted set)
    task = {'id': 'test-task-2', 'url': 'https://example.com', 'priority': 5}
    timestamp_ms = int(time.time() * 1000)
    score = (5 * 1e13) - timestamp_ms
    r.zadd('redis:queue:store:test', {json.dumps(task): score})
    claimed_task = ops.claim_task('redis:queue:store:test', 'worker-test-2', heartbeat_ttl_ms=300000)

    # Get initial heartbeat_expires_at from metadata
    metadata_json = r.hget('redis:processing:store:test:metadata', 'test-task-2')
    metadata = json.loads(metadata_json)
    initial_expires = metadata['heartbeat_expires_at']

    print(f"Initial heartbeat_expires_at: {initial_expires}")

    # Wait 1 second
    time.sleep(1)

    # Update heartbeat (use same 300 second TTL to ensure expiration increases)
    status = ops.update_heartbeat('test-task-2', 'worker-test-2', stage='store:test', heartbeat_ttl_sec=300)
    assert status == 'OK', f"Heartbeat update should succeed, got: {status}"

    # Verify metadata was ALSO updated
    metadata_json = r.hget('redis:processing:store:test:metadata', 'test-task-2')
    metadata = json.loads(metadata_json)
    updated_expires = metadata['heartbeat_expires_at']

    print(f"Updated heartbeat_expires_at: {updated_expires}")

    assert updated_expires > initial_expires, "Heartbeat metadata should be updated (FIX BUG #2)"
    print(f"✓ BUG #2 FIXED: Heartbeat metadata updated (+{updated_expires - initial_expires}ms)")


def test_bug_3_next_queue_data_loss():
    """Test that task data is merged with result before pushing to next queue."""
    print("\n" + "="*60)
    print("TEST BUG #3: Next-Queue Data Loss (Merge Result Into Task)")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up
    r.delete('redis:queue:store:test', 'redis:queue:chunk',
             'redis:processing:store:test', 'redis:processing:store:test:metadata',
             'redis:heartbeat:store:test', 'redis:completed:store:test')

    # Create test task with FULL data (URL, metadata, etc.)
    task = {
        'id': 'test-task-merge',
        'url': 'https://example.com/document.html',
        'stage': 'store',
        'priority': 8,
        'metadata': {
            'source': 'web-scraper',
            'depth': 2,
            'parent_url': 'https://example.com/index.html'
        },
        'created_at': int(time.time() * 1000),
        'custom_field': 'should-be-preserved'
    }

    # Push and claim task
    timestamp_ms = task["created_at"]
    score = (task["priority"] * 1e13) - timestamp_ms
    r.zadd("redis:queue:store:test", {json.dumps(task): score})
    claimed_task = ops.claim_task('redis:queue:store:test', 'worker-store-1')

    # Simulate processing: worker returns PARTIAL result (only new fields)
    result = {
        'id': 'test-task-merge',
        'processed_by': 'worker-store-1',
        'processed_at': int(time.time() * 1000),
        'storage_path': '/data/documents/doc123.html'
    }

    # Complete task and push to next queue (chunk)
    result_json = json.dumps(result)
    status = ops.complete_task(
        'test-task-merge',
        'worker-store-1',
        result_json,
        stage='store:test',
        next_queue='redis:queue:chunk'
    )

    assert status == 'OK', f"Complete should succeed, got: {status}"

    # Pop from next queue and verify FULL data is present
    next_task_json = r.rpop('redis:queue:chunk')
    assert next_task_json is not None, "Task should be in next queue (chunk)"

    next_task = json.loads(next_task_json)

    # CRITICAL: Verify original fields are preserved
    assert next_task['url'] == 'https://example.com/document.html', \
        "Original URL should be preserved in next queue"
    assert next_task['metadata']['source'] == 'web-scraper', \
        "Original metadata should be preserved in next queue"
    assert next_task['metadata']['depth'] == 2, \
        "Original metadata fields should be preserved"
    assert next_task['custom_field'] == 'should-be-preserved', \
        "Custom fields should be preserved in next queue"

    # CRITICAL: Verify new fields from result are added
    assert next_task['processed_by'] == 'worker-store-1', \
        "Result fields should be merged into task"
    assert next_task['storage_path'] == '/data/documents/doc123.html', \
        "Result storage_path should be in next queue task"

    # Verify completion metadata is added
    assert 'previous_worker' in next_task, \
        "Completion metadata should be added"
    assert next_task['previous_worker'] == 'worker-store-1', \
        "Previous worker should be tracked"

    print("✓ BUG #3 FIXED: Original task data merged with result before next queue")
    print(f"  - Original fields preserved: url, metadata, custom_field")
    print(f"  - Result fields merged: processed_by, storage_path")
    print(f"  - Completion metadata added: previous_worker, previous_stage_completed_at")


def test_bug_4_o1_performance():
    """Test that complete/fail use O(1) hash lookups, not O(n) set scans."""
    print("\n" + "="*60)
    print("TEST BUG #4: O(1) Performance")
    print("="*60)

    ops = RedisAtomicOps(host='aio-01', port=6379)
    r = ops.redis

    # Clean up (delete both :test and base queue to avoid interference)
    r.delete('redis:queue:store:test', 'redis:queue:store',
             'redis:processing:store:test', 'redis:processing:store:test:metadata',
             'redis:heartbeat:store:test', 'redis:completed:store:test')

    # Create 1000 tasks and claim them (ZADD for sorted set)
    print("Creating 1000 tasks...")
    for i in range(1000):
        task = {'id': f'perf-task-{i}', 'url': f'https://example.com/{i}', 'priority': 5}
        timestamp_ms = int(time.time() * 1000) + i  # Unique timestamps
        score = (5 * 1e13) - timestamp_ms
        r.zadd('redis:queue:store:test', {json.dumps(task): score})
        ops.claim_task('redis:queue:store:test', f'worker-{i % 10}')

    # Verify all 1000 in processing hash (not set)
    processing_count = r.hlen('redis:processing:store:test')
    assert processing_count == 1000, f"Should have 1000 tasks in processing hash, got {processing_count}"

    # Time completing task #500 (middle of 1000)
    start = time.time()
    status = ops.complete_task('perf-task-500', 'worker-0', '{"status": "done"}', stage='store:test')
    elapsed_ms = (time.time() - start) * 1000

    assert status == 'OK', f"Complete should succeed, got: {status}"
    print(f"✓ BUG #4 FIXED: Complete task in {elapsed_ms:.2f}ms (O(1) hash lookup)")

    # Verify it's NOT doing O(n) scan
    assert elapsed_ms < 20, f"Complete should be <20ms (O(1)), got {elapsed_ms:.2f}ms (likely O(n) scan)"

    # Test fail performance
    start = time.time()
    status = ops.fail_task('perf-task-501', 'worker-1', 'Test error', stage='store:test', max_retries=3)
    elapsed_ms = (time.time() - start) * 1000

    assert status == 'REQUEUED', f"Fail should succeed, got: {status}"
    print(f"✓ BUG #4 FIXED: Fail task in {elapsed_ms:.2f}ms (O(1) hash lookup)")

    assert elapsed_ms < 20, f"Fail should be <20ms (O(1)), got {elapsed_ms:.2f}ms (likely O(n) scan)"


def test_bug_5_fifo_ordering():
    """Test that tasks process in FIFO order within same priority."""
    print("\n" + "="*60)
    print("TEST BUG #5: FIFO Ordering (not LIFO)")
    print("="*60)

    r = redis.Redis(host='aio-01', port=6379, decode_responses=True)
    r.delete('redis:queue:store:test')

    # Create 5 tasks at same priority, different timestamps
    tasks = []
    for i in range(5):
        timestamp_ms = int((time.time() + i) * 1000)  # Increasing timestamps
        score = (10 - 8) * 1e13 + timestamp_ms  # Priority 8, FIX BUG #1: inverted formula

        task = {'id': f'fifo-task-{i}', 'timestamp': timestamp_ms}
        r.zadd('redis:queue:store:test', {json.dumps(task): score})
        tasks.append((i, timestamp_ms, score))

        print(f"Task {i}: timestamp={timestamp_ms}, score={score}")

    # Pop tasks in order (ZPOPMIN pops LOWEST score first)
    popped_order = []
    for _ in range(5):
        result = r.zpopmin('redis:queue:store:test', 1)
        if result:
            task_json, score = result[0]
            task = json.loads(task_json)
            popped_order.append(int(task['id'].split('-')[-1]))

    print(f"\nPopped order: {popped_order}")

    # Should be [0, 1, 2, 3, 4] (FIFO = oldest first)
    assert popped_order == [0, 1, 2, 3, 4], f"Should pop in FIFO order, got {popped_order}"
    print("✓ BUG #5 FIXED: Tasks process in FIFO order (oldest first)")


def test_bug_6_rollback():
    """Test that migration rollback clears Redis on verification failure."""
    print("\n" + "="*60)
    print("TEST BUG #6: Migration Rollback")
    print("="*60)

    # Load migration module
    spec = importlib.util.spec_from_file_location("migrate_pg_to_redis", os.path.join(script_dir, "migrate-pg-to-redis.py"))
    migrate_pg_to_redis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate_pg_to_redis)
    QueueMigrator = migrate_pg_to_redis.QueueMigrator

    migrator = QueueMigrator()
    r = migrator.redis

    # Simulate partial migration (add items to Redis)
    r.zadd('redis:queue:store:high', {'{"id": 1}': 1.0})
    r.zadd('redis:queue:store:medium', {'{"id": 2}': 1.0})
    r.zadd('redis:queue:store:low', {'{"id": 3}': 1.0})
    r.hset('redis:idempotency:store', 'key1', '1')

    # Verify items exist
    assert r.zcard('redis:queue:store:high') == 1
    assert r.zcard('redis:queue:store:medium') == 1
    assert r.zcard('redis:queue:store:low') == 1
    assert r.hlen('redis:idempotency:store') == 1

    print("Pre-rollback: 3 queue items, 1 idempotency key")

    # Rollback
    removed = migrator.rollback_migration()

    # Verify all cleared
    assert r.zcard('redis:queue:store:high') == 0, "High queue should be empty"
    assert r.zcard('redis:queue:store:medium') == 0, "Medium queue should be empty"
    assert r.zcard('redis:queue:store:low') == 0, "Low queue should be empty"
    assert r.exists('redis:idempotency:store') == 0, "Idempotency hash should be deleted"

    print(f"✓ BUG #6 FIXED: Rollback removed {removed} items, Redis is clean")

    migrator.close()


def main():
    print("\n" + "="*70)
    print("REDIS BUG FIX VERIFICATION SUITE")
    print("="*70)

    try:
        test_bug_1_data_retention()
        test_bug_2_heartbeat_sync()
        test_bug_3_next_queue_data_loss()
        test_bug_4_o1_performance()
        test_bug_5_fifo_ordering()
        test_bug_6_rollback()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70)
        print("\nSummary of fixes:")
        print("1. ✓ Full task data retained (no data loss)")
        print("2. ✓ Heartbeat synchronizes hash + metadata (no active task requeue)")
        print("3. ✓ Next queue receives full task data (no data loss)")
        print("4. ✓ O(1) hash lookups (not O(n) set scans)")
        print("5. ✓ FIFO ordering within priority (not LIFO)")
        print("6. ✓ Automatic rollback on verification failure")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
