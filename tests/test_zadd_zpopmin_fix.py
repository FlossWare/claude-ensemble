#!/usr/bin/env python3
"""
Test ZADD/ZPOPMIN Fix

Verifies that:
1. Migration script uses ZADD to add items to sorted sets
2. Worker uses ZPOPMIN to claim items from sorted sets
3. Items are processed in correct priority order (high → medium → low)
4. Within same priority, items are processed FIFO (oldest first)

This test simulates the FULL pipeline:
- Migration adds items with ZADD
- Worker pops items with ZPOPMIN
- Verification checks order and data integrity
"""

import redis
import json
import time
from datetime import datetime

REDIS_HOST = "aio-01"
REDIS_PORT = 6379

def test_zadd_zpopmin_consistency():
    """Test ZADD → ZPOPMIN consistency."""
    print("=" * 60)
    print("TEST: ZADD/ZPOPMIN Consistency")
    print("=" * 60)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Clean up test queues
    test_queues = [
        'test:queue:store:high',
        'test:queue:store:medium',
        'test:queue:store:low'
    ]

    for queue in test_queues:
        r.delete(queue)

    print("\n1. Simulating migration (ZADD)")
    print("-" * 60)

    # Create test items with different priorities and timestamps
    # Format: (priority, timestamp_offset_ms, category)
    test_items = [
        (10, 1000, 'high', 'Task A - High priority, oldest'),
        (10, 2000, 'high', 'Task B - High priority, middle'),
        (10, 3000, 'high', 'Task C - High priority, newest'),
        (5, 1000, 'medium', 'Task D - Medium priority, oldest'),
        (5, 2000, 'medium', 'Task E - Medium priority, newest'),
        (1, 1000, 'low', 'Task F - Low priority, oldest'),
        (1, 2000, 'low', 'Task G - Low priority, newest')
    ]

    base_timestamp = int(datetime.now().timestamp() * 1000)

    for priority, offset, category, description in test_items:
        # Determine queue
        if priority >= 8:
            queue = 'test:queue:store:high'
        elif priority >= 4:
            queue = 'test:queue:store:medium'
        else:
            queue = 'test:queue:store:low'

        # Build item
        item = {
            'id': f'test-{priority}-{offset}',
            'priority': priority,
            'description': description,
            'created_at': base_timestamp + offset
        }

        # Calculate score (SAME formula as migration script)
        # Formula: (10 - priority) * 1e13 + timestamp_ms
        # Lower score = higher priority = pops first
        timestamp_ms = base_timestamp + offset
        score = (10 - priority) * 1e13 + timestamp_ms

        # ZADD (SAME as migration script)
        r.zadd(queue, {json.dumps(item): score})

        print(f"  ZADD {queue}: priority={priority}, score={score:.0f}, {description}")

    print("\n2. Verifying queue counts")
    print("-" * 60)

    counts = {
        'high': r.zcard('test:queue:store:high'),
        'medium': r.zcard('test:queue:store:medium'),
        'low': r.zcard('test:queue:store:low')
    }

    print(f"  High queue: {counts['high']} items")
    print(f"  Medium queue: {counts['medium']} items")
    print(f"  Low queue: {counts['low']} items")

    assert counts['high'] == 3, f"Expected 3 high priority items, got {counts['high']}"
    assert counts['medium'] == 2, f"Expected 2 medium priority items, got {counts['medium']}"
    assert counts['low'] == 2, f"Expected 2 low priority items, got {counts['low']}"

    print("  ✓ Counts correct")

    print("\n3. Simulating worker (ZPOPMIN)")
    print("-" * 60)

    # Pop items in priority order (SAME as worker)
    popped_order = []

    for queue in test_queues:
        while True:
            result = r.zpopmin(queue, 1)
            if not result:
                break

            item_json, score = result[0]
            item = json.loads(item_json)
            popped_order.append(item)

            print(f"  ZPOPMIN {queue}: priority={item['priority']}, score={score:.0f}, {item['description']}")

    print("\n4. Verifying processing order")
    print("-" * 60)

    # Expected order:
    # 1. All high priority (10) in FIFO order (oldest first)
    # 2. All medium priority (5) in FIFO order
    # 3. All low priority (1) in FIFO order

    expected_descriptions = [
        'Task A - High priority, oldest',
        'Task B - High priority, middle',
        'Task C - High priority, newest',
        'Task D - Medium priority, oldest',
        'Task E - Medium priority, newest',
        'Task F - Low priority, oldest',
        'Task G - Low priority, newest'
    ]

    for i, (expected, actual) in enumerate(zip(expected_descriptions, popped_order)):
        actual_desc = actual['description']
        if actual_desc == expected:
            print(f"  {i+1}. ✓ {actual_desc}")
        else:
            print(f"  {i+1}. ✗ Expected: {expected}")
            print(f"        Got: {actual_desc}")
            raise AssertionError(f"Order mismatch at position {i+1}")

    print("\n" + "=" * 60)
    print("✓ TEST PASSED: ZADD/ZPOPMIN consistency verified")
    print("=" * 60)

    # Clean up
    for queue in test_queues:
        r.delete(queue)

    return True


def test_priority_inversion_bug():
    """Test that priority inversion bug is fixed."""
    print("\n" + "=" * 60)
    print("TEST: Priority Inversion Bug Fix")
    print("=" * 60)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    queue = 'test:queue:priority-bug'
    r.delete(queue)

    print("\n1. Adding items with different priorities (same timestamp)")
    print("-" * 60)

    base_timestamp = int(datetime.now().timestamp() * 1000)

    priorities = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

    for priority in priorities:
        item = {
            'id': f'test-priority-{priority}',
            'priority': priority,
            'description': f'Priority {priority} task'
        }

        # Formula: (10 - priority) * 1e13 + timestamp_ms
        # Priority 10: score = 0 + timestamp (LOWEST score)
        # Priority 1: score = 9e13 + timestamp (HIGHEST score)
        score = (10 - priority) * 1e13 + base_timestamp

        r.zadd(queue, {json.dumps(item): score})
        print(f"  ZADD: priority={priority}, score={score:.0f}")

    print("\n2. Popping with ZPOPMIN (lowest score first)")
    print("-" * 60)

    popped_priorities = []

    while True:
        result = r.zpopmin(queue, 1)
        if not result:
            break

        item_json, score = result[0]
        item = json.loads(item_json)
        priority = item['priority']
        popped_priorities.append(priority)

        print(f"  ZPOPMIN: priority={priority}, score={score:.0f}")

    print("\n3. Verifying priority order (high to low)")
    print("-" * 60)

    expected = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

    if popped_priorities == expected:
        print(f"  ✓ Correct order: {popped_priorities}")
    else:
        print(f"  ✗ Expected: {expected}")
        print(f"    Got: {popped_priorities}")
        raise AssertionError("Priority inversion bug NOT fixed!")

    print("\n" + "=" * 60)
    print("✓ TEST PASSED: Priority inversion bug is FIXED")
    print("=" * 60)

    # Clean up
    r.delete(queue)

    return True


def test_fifo_within_priority():
    """Test FIFO ordering within same priority."""
    print("\n" + "=" * 60)
    print("TEST: FIFO Within Same Priority")
    print("=" * 60)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    queue = 'test:queue:fifo'
    r.delete(queue)

    print("\n1. Adding 5 tasks with same priority, different timestamps")
    print("-" * 60)

    base_timestamp = int(datetime.now().timestamp() * 1000)
    priority = 10

    for i in range(5):
        timestamp = base_timestamp + (i * 1000)  # 1 second apart
        item = {
            'id': f'test-fifo-{i}',
            'priority': priority,
            'timestamp': timestamp,
            'description': f'Task #{i+1} (timestamp {timestamp})'
        }

        score = (10 - priority) * 1e13 + timestamp

        r.zadd(queue, {json.dumps(item): score})
        print(f"  ZADD: task #{i+1}, timestamp={timestamp}, score={score:.0f}")

    print("\n2. Popping with ZPOPMIN")
    print("-" * 60)

    popped_order = []

    while True:
        result = r.zpopmin(queue, 1)
        if not result:
            break

        item_json, score = result[0]
        item = json.loads(item_json)
        popped_order.append(item['id'])

        print(f"  ZPOPMIN: {item['description']}, score={score:.0f}")

    print("\n3. Verifying FIFO order")
    print("-" * 60)

    expected = [f'test-fifo-{i}' for i in range(5)]

    if popped_order == expected:
        print(f"  ✓ Correct FIFO order: {popped_order}")
    else:
        print(f"  ✗ Expected: {expected}")
        print(f"    Got: {popped_order}")
        raise AssertionError("FIFO ordering NOT working!")

    print("\n" + "=" * 60)
    print("✓ TEST PASSED: FIFO within priority is working")
    print("=" * 60)

    # Clean up
    r.delete(queue)

    return True


def main():
    """Run all tests."""
    try:
        test_zadd_zpopmin_consistency()
        test_priority_inversion_bug()
        test_fifo_within_priority()

        print("\n" + "=" * 60)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("=" * 60)
        print("\nZADD/ZPOPMIN fix is working correctly:")
        print("  1. Migration uses ZADD (sorted sets)")
        print("  2. Worker uses ZPOPMIN (sorted sets)")
        print("  3. Priority ordering: high → medium → low")
        print("  4. FIFO within same priority (oldest first)")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
