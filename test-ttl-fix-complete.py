#!/usr/bin/env python3
"""
Comprehensive test for TTL consistency fix in Redis queue operations.

Tests all affected functions:
1. atomic_dequeue - Sets claim with TTL
2. atomic_complete - Reads and cleans up claim
3. atomic_retry - Reads and cleans up claim
4. atomic_reclaim_stale - Cleans up expired claims
"""

import sys
import time
from pathlib import Path

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent / 'shared'))

from redis_atomic_wrapper import RedisAtomic
import redis

def test_claim_expiration():
    """Test that claims properly expire with TTL"""
    print("="*60)
    print("TEST 1: Claim Expiration")
    print("="*60)

    r = redis.Redis(host='aio-01', port=6379, db=15)
    r.flushdb()

    atomic = RedisAtomic(r)
    queue_name = 'test_expire'

    # Enqueue URL
    result = atomic.enqueue(queue_name, 'https://example.com/1')
    print(f"1. Enqueued URL: result={result}")

    # Dequeue with short timeout
    url = atomic.dequeue(queue_name, 'worker-1', timeout=3)
    print(f"2. Dequeued URL: {url}")

    # Check claim exists
    claim_key = f'{queue_name}:in_progress:claim:{url}'
    claim_exists = r.exists(claim_key)
    claim_ttl = r.ttl(claim_key)
    claim_value = r.get(claim_key)
    if claim_value:
        claim_value = claim_value.decode('utf-8')

    print(f"3. Claim key exists: {claim_exists}")
    print(f"4. Claim TTL: {claim_ttl} seconds")
    print(f"5. Claim value: {claim_value}")

    # Wait for expiration
    print(f"\nWaiting {claim_ttl + 1} seconds for expiration...")
    time.sleep(claim_ttl + 1)

    claim_exists_after = r.exists(claim_key)
    print(f"6. Claim key after expiration: {claim_exists_after}")

    r.flushdb()

    if claim_exists and not claim_exists_after:
        print("\n✅ PASS: Claim expired correctly")
        return True
    else:
        print("\n❌ FAIL: Claim did not expire")
        return False


def test_complete_with_claim():
    """Test that complete operation works with separate claim key"""
    print("\n" + "="*60)
    print("TEST 2: Complete with Claim Verification")
    print("="*60)

    r = redis.Redis(host='aio-01', port=6379, db=15)
    r.flushdb()

    atomic = RedisAtomic(r)
    queue_name = 'test_complete'

    # Enqueue and dequeue
    atomic.enqueue(queue_name, 'https://example.com/2')
    url = atomic.dequeue(queue_name, 'worker-1', timeout=60)
    print(f"1. Dequeued URL: {url}")

    # Check claim
    claim_key = f'{queue_name}:in_progress:claim:{url}'
    claim_before = r.get(claim_key)
    if claim_before:
        claim_before = claim_before.decode('utf-8')
    print(f"2. Claim before complete: {claim_before}")

    # Complete task
    result = atomic.complete(queue_name, url, 'worker-1', 'success')
    print(f"3. Complete result: {result}")

    # Check claim cleaned up
    claim_after = r.exists(claim_key)
    processed = r.sismember(f'{queue_name}:processed', url)

    print(f"4. Claim after complete: {claim_after}")
    print(f"5. URL in processed set: {processed}")

    r.flushdb()

    if result == 1 and not claim_after and processed:
        print("\n✅ PASS: Complete cleaned up claim correctly")
        return True
    else:
        print("\n❌ FAIL: Complete did not clean up correctly")
        return False


def test_retry_with_claim():
    """Test that retry operation works with separate claim key"""
    print("\n" + "="*60)
    print("TEST 3: Retry with Claim Verification")
    print("="*60)

    r = redis.Redis(host='aio-01', port=6379, db=15)
    r.flushdb()

    atomic = RedisAtomic(r)
    queue_name = 'test_retry'

    # Enqueue and dequeue
    atomic.enqueue(queue_name, 'https://example.com/3')
    url = atomic.dequeue(queue_name, 'worker-1', timeout=60)
    print(f"1. Dequeued URL: {url}")

    # Check claim
    claim_key = f'{queue_name}:in_progress:claim:{url}'
    claim_before = r.get(claim_key)
    if claim_before:
        claim_before = claim_before.decode('utf-8')
    print(f"2. Claim before retry: {claim_before}")

    # Retry task
    retry_count = atomic.retry(queue_name, url, 'worker-1', max_retries=3)
    print(f"3. Retry result: {retry_count}")

    # Check claim cleaned up and URL re-queued
    claim_after = r.exists(claim_key)
    pending = r.llen(queue_name)
    queued = r.sismember(f'{queue_name}:queued', url)

    print(f"4. Claim after retry: {claim_after}")
    print(f"5. Pending count: {pending}")
    print(f"6. URL in queued set: {queued}")

    r.flushdb()

    if retry_count > 0 and not claim_after and pending == 1 and queued:
        print("\n✅ PASS: Retry cleaned up claim and re-queued correctly")
        return True
    else:
        print("\n❌ FAIL: Retry did not work correctly")
        return False


def test_reclaim_stale():
    """Test that reclaim_stale cleans up expired claims"""
    print("\n" + "="*60)
    print("TEST 4: Reclaim Stale Tasks")
    print("="*60)

    r = redis.Redis(host='aio-01', port=6379, db=15)
    r.flushdb()

    atomic = RedisAtomic(r)
    queue_name = 'test_reclaim'

    # Enqueue and dequeue with short timeout
    atomic.enqueue(queue_name, 'https://example.com/4')
    url = atomic.dequeue(queue_name, 'worker-1', timeout=2)
    print(f"1. Dequeued URL: {url}")

    # Check claim
    claim_key = f'{queue_name}:in_progress:claim:{url}'
    claim_before = r.exists(claim_key)
    print(f"2. Claim before reclaim: {claim_before}")

    # Wait for task to become stale (based on timestamp, not TTL)
    print("\nWaiting 3 seconds for task to become stale...")
    time.sleep(3)

    # Reclaim stale tasks
    reclaimed = atomic.reclaim_stale(queue_name, timeout=2)
    print(f"3. Reclaimed URLs: {reclaimed}")

    # Check claim cleaned up and URL re-queued
    claim_after = r.exists(claim_key)
    pending = r.llen(queue_name)
    queued = r.sismember(f'{queue_name}:queued', url)

    print(f"4. Claim after reclaim: {claim_after}")
    print(f"5. Pending count: {pending}")
    print(f"6. URL in queued set: {queued}")

    r.flushdb()

    if len(reclaimed) == 1 and not claim_after and pending == 1 and queued:
        print("\n✅ PASS: Reclaim cleaned up claim and re-queued correctly")
        return True
    else:
        print("\n❌ FAIL: Reclaim did not work correctly")
        return False


def test_wrong_worker():
    """Test that operations fail when worker doesn't own claim"""
    print("\n" + "="*60)
    print("TEST 5: Wrong Worker Protection")
    print("="*60)

    r = redis.Redis(host='aio-01', port=6379, db=15)
    r.flushdb()

    atomic = RedisAtomic(r)
    queue_name = 'test_ownership'

    # Enqueue and dequeue
    atomic.enqueue(queue_name, 'https://example.com/5')
    url = atomic.dequeue(queue_name, 'worker-1', timeout=60)
    print(f"1. Dequeued URL by worker-1: {url}")

    # Try to complete as wrong worker
    result_complete = atomic.complete(queue_name, url, 'worker-2', 'success')
    print(f"2. Complete by worker-2: {result_complete} (should be 0)")

    # Try to retry as wrong worker
    result_retry = atomic.retry(queue_name, url, 'worker-2', max_retries=3)
    print(f"3. Retry by worker-2: {result_retry} (should be -2)")

    # Verify still in progress
    in_progress = r.sismember(f'{queue_name}:in_progress', url)
    print(f"4. Still in progress: {in_progress}")

    r.flushdb()

    if result_complete == 0 and result_retry == -2 and in_progress:
        print("\n✅ PASS: Wrong worker protection working")
        return True
    else:
        print("\n❌ FAIL: Wrong worker was able to modify claim")
        return False


if __name__ == '__main__':
    print("\nTTL CONSISTENCY FIX - COMPREHENSIVE TEST\n")

    tests = [
        test_claim_expiration,
        test_complete_with_claim,
        test_retry_with_claim,
        test_reclaim_stale,
        test_wrong_worker
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            results.append(False)

    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Passed: {sum(results)}/{len(results)}")

    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: Test {i} - {test.__name__}")

    if all(results):
        print("\n🎉 All tests passed! TTL consistency fix is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Review output above.")
        sys.exit(1)
