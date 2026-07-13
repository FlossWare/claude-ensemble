#!/usr/bin/env python3
"""
Priority Formula Verification

Tests that ZPOPMIN pops highest priority tasks first using the formula:
    score = (10 - priority) * 1e13 + timestamp_ms

Where:
- Priority 10 (highest) → score ~0 (popped first by ZPOPMIN)
- Priority 1 (lowest) → score ~9e13 (popped last by ZPOPMIN)
- Within same priority, older tasks (lower timestamp) popped first (FIFO)
"""

import redis
import json
import time


def calculate_priority_score(priority: int, timestamp_ms: int) -> float:
    """
    Calculate score for Redis sorted set.

    Args:
        priority: 1-10 (10 = highest priority)
        timestamp_ms: Unix timestamp in milliseconds

    Returns:
        Score for ZADD (lower score = higher priority for ZPOPMIN)
    """
    return (10 - priority) * 1e13 + timestamp_ms


def test_priority_formula():
    """Verify priority formula works correctly with ZPOPMIN."""
    print("="*60)
    print("PRIORITY FORMULA VERIFICATION")
    print("="*60)

    # Test cases: (priority, timestamp_offset_ms, label)
    test_cases = [
        (10, 0, "Urgent - Old"),
        (10, 1000, "Urgent - New"),
        (8, 0, "High - Old"),
        (8, 1000, "High - New"),
        (5, 0, "Medium - Old"),
        (5, 1000, "Medium - New"),
        (3, 0, "Low - Old"),
        (3, 1000, "Low - New"),
        (1, 0, "Lowest - Old"),
        (1, 1000, "Lowest - New"),
    ]

    base_timestamp = int(time.time() * 1000)

    print("\n1. Calculate scores:")
    print(f"{'Label':<20} {'Priority':<10} {'Timestamp':<15} {'Score':<15}")
    print("-" * 60)

    tasks = []
    for priority, offset, label in test_cases:
        timestamp = base_timestamp + offset
        score = calculate_priority_score(priority, timestamp)
        tasks.append((score, priority, timestamp, label))
        print(f"{label:<20} {priority:<10} {timestamp:<15} {score:<15.2e}")

    # Sort by score (what ZPOPMIN does)
    sorted_tasks = sorted(tasks, key=lambda x: x[0])

    print("\n2. Expected pop order (ZPOPMIN pops lowest score first):")
    print(f"{'Order':<8} {'Label':<20} {'Priority':<10} {'Score':<15}")
    print("-" * 60)

    for i, (score, priority, timestamp, label) in enumerate(sorted_tasks, 1):
        print(f"{i:<8} {label:<20} {priority:<10} {score:<15.2e}")

    # Verify correctness
    expected_order = [
        "Urgent - Old",
        "Urgent - New",
        "High - Old",
        "High - New",
        "Medium - Old",
        "Medium - New",
        "Low - Old",
        "Low - New",
        "Lowest - Old",
        "Lowest - New",
    ]

    actual_order = [label for _, _, _, label in sorted_tasks]

    print("\n3. Validation:")
    if actual_order == expected_order:
        print("✅ PASS: Tasks ordered correctly (high priority → low, FIFO within priority)")
        return True
    else:
        print("✗ FAIL: Tasks NOT ordered correctly")
        print(f"  Expected: {expected_order[:3]}...")
        print(f"  Actual:   {actual_order[:3]}...")
        return False


def test_live_redis():
    """Test with actual Redis sorted set and ZPOPMIN."""
    print("\n" + "="*60)
    print("LIVE REDIS TEST")
    print("="*60)

    try:
        r = redis.Redis(host='aio-01', port=6379, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return False

    # Create test queue
    test_queue = 'redis:queue:test:priority-formula'
    r.delete(test_queue)

    # Add tasks with different priorities
    base_timestamp = int(time.time() * 1000)
    test_tasks = [
        (10, 0, "Urgent"),
        (8, 100, "High"),
        (5, 200, "Medium"),
        (3, 300, "Low"),
        (1, 400, "Lowest"),
    ]

    print("\n1. Adding tasks to sorted set:")
    for priority, offset, label in test_tasks:
        timestamp = base_timestamp + offset
        score = calculate_priority_score(priority, timestamp)
        task = {'id': f'task-{label}', 'priority': priority, 'label': label}
        r.zadd(test_queue, {json.dumps(task): score})
        print(f"  Added: {label:<10} Priority={priority:<2} Score={score:.2e}")

    # Pop tasks using ZPOPMIN (lowest score first)
    print("\n2. Popping tasks with ZPOPMIN (lowest score = highest priority):")
    pop_order = []
    while True:
        result = r.zpopmin(test_queue)
        if not result:
            break

        task_json, score = result[0]
        task = json.loads(task_json)
        pop_order.append(task['label'])
        print(f"  Popped: {task['label']:<10} Priority={task['priority']:<2} Score={score:.2e}")

    # Verify order
    expected_pop_order = ["Urgent", "High", "Medium", "Low", "Lowest"]

    print("\n3. Validation:")
    if pop_order == expected_pop_order:
        print("✅ PASS: ZPOPMIN popped tasks in correct priority order")
        return True
    else:
        print("✗ FAIL: ZPOPMIN did NOT pop in correct order")
        print(f"  Expected: {expected_pop_order}")
        print(f"  Actual:   {pop_order}")
        return False


def test_fifo_within_priority():
    """Test FIFO ordering within same priority level."""
    print("\n" + "="*60)
    print("FIFO WITHIN PRIORITY TEST")
    print("="*60)

    try:
        r = redis.Redis(host='aio-01', port=6379, decode_responses=True)
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return False

    # Create test queue
    test_queue = 'redis:queue:test:fifo'
    r.delete(test_queue)

    # Add 5 tasks with SAME priority but different timestamps
    priority = 5
    base_timestamp = int(time.time() * 1000)

    print("\n1. Adding 5 tasks with SAME priority (5) but different timestamps:")
    for i in range(5):
        timestamp = base_timestamp + (i * 1000)  # 1 second apart
        score = calculate_priority_score(priority, timestamp)
        task = {'id': f'task-{i}', 'priority': priority, 'order': i}
        r.zadd(test_queue, {json.dumps(task): score})
        print(f"  Task {i}: Timestamp={timestamp} Score={score:.2e}")

    # Pop all tasks
    print("\n2. Popping tasks with ZPOPMIN:")
    pop_order = []
    while True:
        result = r.zpopmin(test_queue)
        if not result:
            break

        task_json, score = result[0]
        task = json.loads(task_json)
        pop_order.append(task['order'])
        print(f"  Popped: Task {task['order']} (Score={score:.2e})")

    # Verify FIFO order (0, 1, 2, 3, 4)
    expected_order = [0, 1, 2, 3, 4]

    print("\n3. Validation:")
    if pop_order == expected_order:
        print("✅ PASS: Tasks with same priority popped in FIFO order (oldest first)")
        return True
    else:
        print("✗ FAIL: FIFO ordering broken")
        print(f"  Expected: {expected_order}")
        print(f"  Actual:   {pop_order}")
        return False


def main():
    print("\n" + "="*60)
    print("PRIORITY FORMULA COMPREHENSIVE TEST")
    print("="*60)
    print("\nFormula: score = (10 - priority) * 1e13 + timestamp_ms")
    print("ZPOPMIN behavior: Pops LOWEST score first")
    print("Expected: High priority (10) → Low score → Popped first\n")

    results = {
        'Formula Calculation': test_priority_formula(),
        'Live Redis ZPOPMIN': test_live_redis(),
        'FIFO Within Priority': test_fifo_within_priority(),
    }

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All tests passed! Priority formula is correct.")
        print("\nConclusion:")
        print("  • Formula inverts priority correctly (high priority = low score)")
        print("  • ZPOPMIN pops highest priority tasks first")
        print("  • FIFO ordering preserved within same priority level")
        return 0
    else:
        print("\n⚠️  Some tests failed. Formula may need adjustment.")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
