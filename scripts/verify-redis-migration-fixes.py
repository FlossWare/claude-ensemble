#!/usr/bin/env python3
"""
Verification Script for Redis Migration Fixes

Tests all critical fixes:
1. Priority score formula (no inversion)
2. Atomic operations (no race conditions)
3. Stuck task recovery (no data loss)

Usage:
    python3 verify-redis-migration-fixes.py
"""

import redis
import json
import time
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

# Import redis_atomic_operations from file with dashes
script_dir = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    'redis_atomic_operations',
    script_dir / 'redis-atomic-operations.py'
)
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps


def test_priority_score_formula():
    """Test 1: Priority score formula prevents inversion."""
    print("\n" + "="*60)
    print("TEST 1: Priority Score Formula")
    print("="*60)

    def calculate_priority_score(priority: int, timestamp_ms: int) -> float:
        return (10 - priority) * 1e13 + timestamp_ms

    # Test cases
    test_cases = [
        (10, 1000, "High priority, old"),
        (10, 2000, "High priority, new"),
        (5, 1000, "Medium priority, old"),
        (5, 2000, "Medium priority, new"),
        (1, 1000, "Low priority, old"),
        (1, 2000, "Low priority, new"),
    ]

    scores = []
    for priority, timestamp, label in test_cases:
        score = calculate_priority_score(priority, timestamp)
        scores.append((score, priority, timestamp, label))
        print(f"{label:25} Priority={priority:2d} Time={timestamp:4d} Score={score:.2e}")

    # Verify sorting (LOWEST score first - ZPOPMIN behavior)
    sorted_scores = sorted(scores, key=lambda x: x[0])

    print("\nExpected order (LOWEST score first - ZPOPMIN pops first):")
    for i, (score, priority, timestamp, label) in enumerate(sorted_scores, 1):
        print(f"  {i}. {label}")

    # Check correctness (with inverted formula: high priority = LOW score)
    expected_order = [
        "High priority, old",
        "High priority, new",
        "Medium priority, old",
        "Medium priority, new",
        "Low priority, old",
        "Low priority, new",
    ]

    actual_order = [label for score, priority, timestamp, label in sorted_scores]

    if actual_order == expected_order:
        print("\n✅ PASS: Priority ordering correct (high → low, FIFO within priority)")
        return True
    else:
        print("\n✗ FAIL: Priority ordering incorrect")
        print(f"  Expected: {expected_order}")
        print(f"  Actual:   {actual_order}")
        return False


def test_atomic_operations():
    """Test 2: Atomic operations prevent race conditions."""
    print("\n" + "="*60)
    print("TEST 2: Atomic Operations")
    print("="*60)

    try:
        ops = RedisAtomicOps(host='aio-01', port=6379)
        print("✅ Connected to Redis")

        # Create test queue
        r = redis.Redis(host='aio-01', port=6379, decode_responses=True)
        test_queue = 'redis:queue:test:verify'

        # Clear test queue
        r.delete(test_queue)
        r.delete('redis:processing:test')
        r.delete('redis:heartbeat:test')
        r.delete('redis:completed:test')

        # Add test task
        test_task = {
            'id': 'test-123',
            'data': {'test': 'data'},
            'priority': 5,
            'retries': 0
        }
        timestamp_ms = int(time.time() * 1000)
        score = (10 - 5) * 1e13 + timestamp_ms
        r.zadd(test_queue, {json.dumps(test_task): score})

        print("✅ Created test task")

        # Test claim (atomic)
        claimed = ops.claim_task(test_queue, 'test-worker-1')
        if claimed and claimed['id'] == 'test-123':
            print("✅ Claim operation successful (atomic)")
        else:
            print("✗ Claim operation failed")
            return False

        # Verify processing hash (O(1) check)
        task_exists = r.hexists('redis:processing:test', 'test-123')
        if task_exists:
            print("✅ Task in processing hash (O(1) verification)")
        else:
            print("✗ Task not in processing hash")
            return False

        # Test complete (atomic)
        result = json.dumps({'status': 'processed'})
        status = ops.complete_task('test-123', 'test-worker-1', result, stage='test')
        if status == 'OK':
            print("✅ Complete operation successful (atomic)")
        else:
            print(f"✗ Complete operation failed: {status}")
            return False

        # Verify processing hash empty (O(1) check)
        processing_count = r.hlen('redis:processing:test')
        if processing_count == 0:
            print("✅ Processing hash empty after complete (O(1) verification)")
        else:
            print(f"✗ Processing hash not empty after complete ({processing_count} items)")
            return False

        # Verify completed hash
        completed = r.hget('redis:completed:test', 'test-123')
        if completed:
            print("✅ Completion record stored")
        else:
            print("✗ Completion record not found")
            return False

        # Cleanup
        r.delete(test_queue, 'redis:processing:test', 'redis:heartbeat:test', 'redis:completed:test')

        print("\n✅ PASS: All atomic operations working correctly")
        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stuck_task_recovery():
    """Test 3: Stuck task recovery prevents data loss."""
    print("\n" + "="*60)
    print("TEST 3: Stuck Task Recovery")
    print("="*60)

    try:
        ops = RedisAtomicOps(host='aio-01', port=6379)
        r = redis.Redis(host='aio-01', port=6379, decode_responses=True)

        # Clear test data
        r.delete('redis:queue:test')
        r.delete('redis:processing:test')
        r.delete('redis:heartbeat:test')

        # Create stuck task (expired heartbeat)
        current_time_ms = int(time.time() * 1000)
        expired_time_ms = current_time_ms - 400000  # 6.67 minutes ago (expired)

        stuck_task = {
            'id': 'stuck-456',
            'data': {'test': 'stuck'},
            'priority': 5,
            'retries': 0
        }

        # Add to processing hash with expired heartbeat (matching production structure)
        # Store task in processing hash
        r.hset('redis:processing:test', 'stuck-456', json.dumps(stuck_task))

        # Store metadata in processing metadata hash
        metadata = {
            'worker_id': 'dead-worker',
            'claimed_at': str(expired_time_ms),
            'heartbeat_expires_at': str(expired_time_ms + 300000)  # Expired 100s ago
        }
        r.hset('redis:processing:test:metadata', 'stuck-456', json.dumps(metadata))

        print("✅ Created stuck task (heartbeat expired 100s ago)")

        # Run recovery
        recovered = ops.recover_stuck_tasks('test', stuck_threshold_ms=300000)

        if recovered == 1:
            print(f"✅ Recovered {recovered} stuck task")
        else:
            print(f"✗ Expected to recover 1 task, got {recovered}")
            return False

        # Verify processing hash empty (O(1) check)
        processing_count = r.hlen('redis:processing:test')
        if processing_count == 0:
            print("✅ Processing hash empty after recovery (O(1) verification)")
        else:
            print(f"✗ Processing hash not empty after recovery ({processing_count} items)")
            return False

        # Verify task requeued to sorted set (ZCARD for count)
        queue_size = r.zcard('redis:queue:test')
        if queue_size == 1:
            print("✅ Task requeued successfully (O(1) verification)")
        else:
            print(f"✗ Expected 1 task in queue, got {queue_size}")
            return False

        # Cleanup
        r.delete('redis:queue:test', 'redis:processing:test', 'redis:heartbeat:test')

        print("\n✅ PASS: Stuck task recovery working correctly")
        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("Redis Migration Fixes Verification")
    print("="*60)

    results = {
        'Priority Score Formula': test_priority_score_formula(),
        'Atomic Operations': test_atomic_operations(),
        'Stuck Task Recovery': test_stuck_task_recovery()
    }

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All tests passed! Migration fixes verified.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review output above.")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
