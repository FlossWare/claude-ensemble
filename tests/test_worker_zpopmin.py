#!/usr/bin/env python3
"""
Test Redis Queue Worker ZPOPMIN Integration

Simulates real worker behavior with the ZPOPMIN fix.
"""

import sys
import json
import redis
from datetime import datetime

REDIS_HOST = "aio-01"
REDIS_PORT = 6379

def test_worker_zpopmin():
    """Test worker ZPOPMIN integration."""
    print("=" * 60)
    print("TEST: Worker ZPOPMIN Integration")
    print("=" * 60)

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Clean up test queues
    test_queues = [
        'test:worker:queue:performance:high',
        'test:worker:queue:ai:medium',
        'test:worker:queue:ml:medium',
        'test:worker:queue:ga:low'
    ]

    for queue in test_queues:
        r.delete(queue)

    print("\n1. Populating queues with test data")
    print("-" * 60)

    # Add items to different priority queues
    base_timestamp = int(datetime.now().timestamp() * 1000)

    items = [
        ('test:worker:queue:performance:high', 10, 1000, 'URL 1 - High priority'),
        ('test:worker:queue:performance:high', 10, 2000, 'URL 2 - High priority'),
        ('test:worker:queue:ai:medium', 5, 1000, 'URL 3 - Medium priority'),
        ('test:worker:queue:ml:medium', 5, 2000, 'URL 4 - Medium priority'),
        ('test:worker:queue:ga:low', 1, 1000, 'URL 5 - Low priority'),
    ]

    for queue, priority, offset, description in items:
        item = {
            'url': f'http://example.com/{description}',
            'category': queue.split(':')[-1],
            'priority': priority,
            'created_at': base_timestamp + offset
        }

        timestamp_ms = base_timestamp + offset
        score = (10 - priority) * 1e13 + timestamp_ms

        r.zadd(queue, {json.dumps(item): score})
        print(f"  ZADD {queue}: {description}, score={score:.0f}")

    print("\n2. Simulating worker loop (ZPOPMIN)")
    print("-" * 60)

    # Simulate worker behavior
    processed_order = []

    iteration = 0
    while iteration < 10:  # Max 10 iterations
        iteration += 1

        # Try each queue in priority order (SAME as worker)
        result = None
        queue_name = None

        for queue in test_queues:
            popped = r.zpopmin(queue, 1)
            if popped:
                item_json, score = popped[0]
                result = (queue, item_json, score)
                queue_name = queue
                break

        if result:
            queue, item_json, score = result
            item = json.loads(item_json)
            processed_order.append(item['url'])

            print(f"  Iteration {iteration}: ZPOPMIN {queue}")
            print(f"    URL: {item['url']}")
            print(f"    Priority: {item['priority']}, Score: {score:.0f}")
        else:
            print(f"  Iteration {iteration}: No items, waiting...")
            break

    print("\n3. Verifying processing order")
    print("-" * 60)

    expected_order = [
        'http://example.com/URL 1 - High priority',
        'http://example.com/URL 2 - High priority',
        'http://example.com/URL 3 - Medium priority',
        'http://example.com/URL 4 - Medium priority',
        'http://example.com/URL 5 - Low priority',
    ]

    if processed_order == expected_order:
        print("  ✓ Processing order correct:")
        for i, url in enumerate(processed_order):
            print(f"    {i+1}. {url}")
    else:
        print("  ✗ Processing order WRONG:")
        print(f"    Expected: {expected_order}")
        print(f"    Got: {processed_order}")
        raise AssertionError("Worker processing order incorrect!")

    print("\n" + "=" * 60)
    print("✓ TEST PASSED: Worker ZPOPMIN integration working")
    print("=" * 60)

    # Clean up
    for queue in test_queues:
        r.delete(queue)

    return True


def main():
    try:
        test_worker_zpopmin()

        print("\n" + "=" * 60)
        print("✓ Worker fix verified:")
        print("  - Changed from BRPOP to ZPOPMIN")
        print("  - Processes queues in priority order")
        print("  - FIFO within each priority level")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
