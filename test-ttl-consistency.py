#!/usr/bin/env python3
"""
Test TTL consistency issue in Redis queue operations.

ISSUE: Line 62 of redis-atomic-operations.lua sets EXPIRE on a constructed key
(in_progress_set .. ':claims:' .. url) which creates a separate string key
instead of setting TTL on the hash field.

This causes:
1. Hash fields in ':claims' never expire
2. Phantom keys ':claims:<url>' are created and expire
3. Memory leak in the hash
"""

import redis
import time

# Connect to Redis
r = redis.Redis(host='aio-01', port=6379, db=15, decode_responses=True)

# Clean up test data
r.flushdb()

def test_current_behavior():
    """Demonstrate the bug in current implementation"""
    print("="*60)
    print("TEST 1: Current Behavior (Buggy)")
    print("="*60)

    queue_name = 'test_queue'
    in_progress_set = f'{queue_name}:in_progress'
    url = 'https://example.com'
    worker_id = 'worker-1'
    timeout = 5  # 5 seconds

    # Simulate what the Lua script does
    r.sadd(in_progress_set, url)
    r.hset(f'{in_progress_set}:claims', url, worker_id)
    r.hset(f'{in_progress_set}:timestamps', url, str(int(time.time() * 1000)))

    # This is the problematic line - sets EXPIRE on wrong key
    r.expire(f'{in_progress_set}:claims:{url}', timeout)

    print(f"\n1. Created hash field: {in_progress_set}:claims[{url}] = {worker_id}")
    print(f"2. Set EXPIRE on: {in_progress_set}:claims:{url} (WRONG - creates phantom key)")

    # Check what exists
    print(f"\n3. Hash field exists: {r.hexists(f'{in_progress_set}:claims', url)}")
    print(f"4. Hash field TTL: {r.ttl(f'{in_progress_set}:claims')} (ENTIRE HASH, not field)")
    print(f"5. Phantom key exists: {r.exists(f'{in_progress_set}:claims:{url}')}")
    print(f"6. Phantom key TTL: {r.ttl(f'{in_progress_set}:claims:{url}')}")

    # Wait for expiration
    print(f"\nWaiting {timeout} seconds for expiration...")
    time.sleep(timeout + 1)

    print(f"\nAfter expiration:")
    print(f"7. Hash field STILL exists: {r.hexists(f'{in_progress_set}:claims', url)} (MEMORY LEAK)")
    print(f"8. Phantom key expired: {r.exists(f'{in_progress_set}:claims:{url}')}")

    return r.hexists(f'{in_progress_set}:claims', url)

def test_fixed_behavior():
    """Demonstrate the correct implementation"""
    print("\n" + "="*60)
    print("TEST 2: Fixed Behavior (Correct)")
    print("="*60)

    r.flushdb()

    queue_name = 'test_queue_fixed'
    in_progress_set = f'{queue_name}:in_progress'
    url = 'https://example.com'
    worker_id = 'worker-1'
    timeout = 5

    # SOLUTION 1: Use separate keys with TTL for claims
    r.sadd(in_progress_set, url)
    r.hset(f'{in_progress_set}:timestamps', url, str(int(time.time() * 1000)))

    # Store claim in separate key with TTL
    r.setex(f'{in_progress_set}:claim:{url}', timeout, worker_id)

    print(f"\n1. Created set member: {in_progress_set} contains {url}")
    print(f"2. Created string key with TTL: {in_progress_set}:claim:{url} = {worker_id}")

    # Check what exists
    print(f"\n3. Claim key exists: {r.exists(f'{in_progress_set}:claim:{url}')}")
    print(f"4. Claim key TTL: {r.ttl(f'{in_progress_set}:claim:{url}')} seconds")
    print(f"5. Claim value: {r.get(f'{in_progress_set}:claim:{url}')}")

    # Wait for expiration
    print(f"\nWaiting {timeout} seconds for expiration...")
    time.sleep(timeout + 1)

    print(f"\nAfter expiration:")
    print(f"6. Claim key expired: {r.exists(f'{in_progress_set}:claim:{url}')} (CORRECTLY CLEANED UP)")
    print(f"7. Timestamp still exists: {r.hexists(f'{in_progress_set}:timestamps', url)} (for reclaim logic)")

    return not r.exists(f'{in_progress_set}:claim:{url}')

if __name__ == '__main__':
    print("\nTTL CONSISTENCY TEST\n")
    print("Testing Redis queue TTL behavior...")

    bug_demonstrated = test_current_behavior()
    fix_demonstrated = test_fixed_behavior()

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Bug reproduced (hash field didn't expire): {bug_demonstrated}")
    print(f"Fix verified (claim key expired correctly): {fix_demonstrated}")

    if bug_demonstrated and fix_demonstrated:
        print("\n✅ TTL consistency issue confirmed and fix validated")
        print("\nRECOMMENDATION:")
        print("1. Change line 62 in redis-atomic-operations.lua")
        print("   FROM: redis.call('EXPIRE', in_progress_set .. ':claims:' .. url, timeout)")
        print("   TO:   redis.call('SETEX', in_progress_set .. ':claim:' .. url, timeout, worker_id)")
        print("2. Update atomic_complete to use GET instead of HGET")
        print("3. Update atomic_retry to use GET instead of HGET")
    else:
        print("\n❌ Test failed")

    # Cleanup
    r.flushdb()
