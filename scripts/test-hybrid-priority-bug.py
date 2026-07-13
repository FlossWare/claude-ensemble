#!/usr/bin/env python3
"""
Test HYBRID Mode Priority Bug

Tests that priority system works correctly in HYBRID mode (ZSET queues).

BUG: claim_task() uses ZPOPMAX but migration uses (10-priority) scoring
Result: Priority inversion - LOW priority tasks process FIRST!

Expected:
- Priority 10 tasks process FIRST (highest priority)
- Priority 1 tasks process LAST (lowest priority)
- Within same priority: FIFO (oldest first)
"""

import redis
import json
import time
from typing import List, Dict

class HybridPriorityTester:
    def __init__(self, redis_host='aio-01', redis_port=6379):
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.test_queue = 'test:queue:hybrid:priority'

    def cleanup(self):
        """Clean up test queue."""
        self.redis.delete(self.test_queue)

    def calculate_priority_score(self, priority: int, timestamp_ms: int) -> float:
        """
        Current migration formula (BUGGY in HYBRID mode).

        Formula: (10 - priority) * 1e13 + timestamp_ms

        This gives:
        - Priority 10: score = 0 + timestamp (LOWEST score)
        - Priority 1:  score = 90000000000000 + timestamp (HIGHEST score)

        BUT claim_task() uses ZPOPMAX (pops HIGHEST score)!

        Result: Priority 1 tasks pop FIRST (priority inversion!)
        """
        return (10 - priority) * 1e13 + timestamp_ms

    def create_test_tasks(self) -> List[Dict]:
        """Create test tasks with different priorities and timestamps."""
        base_time = int(time.time() * 1000)

        tasks = [
            # Priority 10 (highest) - should process FIRST
            {'id': 'p10-1', 'url': 'https://example.com/p10-1', 'priority': 10, 'timestamp': base_time},
            {'id': 'p10-2', 'url': 'https://example.com/p10-2', 'priority': 10, 'timestamp': base_time + 1000},

            # Priority 5 (medium) - should process SECOND
            {'id': 'p5-1', 'url': 'https://example.com/p5-1', 'priority': 5, 'timestamp': base_time},
            {'id': 'p5-2', 'url': 'https://example.com/p5-2', 'priority': 5, 'timestamp': base_time + 1000},

            # Priority 1 (lowest) - should process LAST
            {'id': 'p1-1', 'url': 'https://example.com/p1-1', 'priority': 1, 'timestamp': base_time},
            {'id': 'p1-2', 'url': 'https://example.com/p1-2', 'priority': 1, 'timestamp': base_time + 1000},
        ]

        return tasks

    def populate_queue_with_current_formula(self, tasks: List[Dict]):
        """Populate queue using current (buggy) formula."""
        for task in tasks:
            score = self.calculate_priority_score(task['priority'], task['timestamp'])
            task_json = json.dumps(task)
            self.redis.zadd(self.test_queue, {task_json: score})
            print(f"  Added {task['id']}: priority={task['priority']}, score={score}")

    def test_zpopmax_current_formula(self) -> List[str]:
        """Test ZPOPMAX with current formula (demonstrates bug)."""
        print("\n" + "="*60)
        print("TEST 1: ZPOPMAX with current formula (10-priority)")
        print("="*60)

        self.cleanup()
        tasks = self.create_test_tasks()

        print("\nPopulating queue...")
        self.populate_queue_with_current_formula(tasks)

        print(f"\nQueue size: {self.redis.zcard(self.test_queue)}")

        # Pop all tasks using ZPOPMAX (what claim_task() currently does)
        print("\nPopping with ZPOPMAX (highest score first)...")
        popped_order = []
        while True:
            result = self.redis.zpopmax(self.test_queue)
            if not result:
                break
            task_json, score = result[0]
            task = json.loads(task_json)
            popped_order.append(task['id'])
            print(f"  Popped: {task['id']} (priority={task['priority']}, score={score})")

        print(f"\nPopped order: {popped_order}")

        # Expected (correct) order
        expected = ['p10-1', 'p10-2', 'p5-1', 'p5-2', 'p1-1', 'p1-2']

        # Actual buggy order with ZPOPMAX + (10-priority)
        # ZPOPMAX pops highest score first
        # Priority 1 has score ~90e12 (highest)
        # Priority 10 has score ~0 (lowest)
        # So order is: p1-1, p1-2, p5-1, p5-2, p10-1, p10-2 (INVERTED!)

        if popped_order == expected:
            print("\n✓ PASS: Priorities processed correctly")
            return popped_order
        else:
            print(f"\n✗ FAIL: Priority inversion detected!")
            print(f"  Expected: {expected}")
            print(f"  Got:      {popped_order}")
            return popped_order

    def test_zpopmin_current_formula(self) -> List[str]:
        """Test ZPOPMIN with current formula (FIX #1)."""
        print("\n" + "="*60)
        print("TEST 2: ZPOPMIN with current formula (10-priority)")
        print("="*60)

        self.cleanup()
        tasks = self.create_test_tasks()

        print("\nPopulating queue...")
        self.populate_queue_with_current_formula(tasks)

        print(f"\nQueue size: {self.redis.zcard(self.test_queue)}")

        # Pop all tasks using ZPOPMIN (FIX: pop lowest score first)
        print("\nPopping with ZPOPMIN (lowest score first)...")
        popped_order = []
        while True:
            result = self.redis.zpopmin(self.test_queue)
            if not result:
                break
            task_json, score = result[0]
            task = json.loads(task_json)
            popped_order.append(task['id'])
            print(f"  Popped: {task['id']} (priority={task['priority']}, score={score})")

        print(f"\nPopped order: {popped_order}")

        expected = ['p10-1', 'p10-2', 'p5-1', 'p5-2', 'p1-1', 'p1-2']

        if popped_order == expected:
            print("\n✓ PASS: Priorities processed correctly with ZPOPMIN!")
            return popped_order
        else:
            print(f"\n✗ FAIL: Still incorrect")
            print(f"  Expected: {expected}")
            print(f"  Got:      {popped_order}")
            return popped_order

    def test_zpopmax_reversed_formula(self) -> List[str]:
        """Test ZPOPMAX with reversed formula (FIX #2 - alternative)."""
        print("\n" + "="*60)
        print("TEST 3: ZPOPMAX with reversed formula (priority-10)")
        print("="*60)

        self.cleanup()
        tasks = self.create_test_tasks()

        print("\nPopulating queue with REVERSED formula...")
        for task in tasks:
            # REVERSED: (priority - 10) instead of (10 - priority)
            # This gives:
            # - Priority 10: score = 0 + timestamp (LOWEST... wait, still wrong!)
            # - Priority 1:  score = -90e12 + timestamp (LOWEST)
            # ZPOPMAX would pop priority 10 first (score ~0)
            # Then priority 1 (score ~-90e12)
            # That's still backwards!

            # Actually we want: priority * 1e13 + timestamp
            # - Priority 10: score = 100e12 + timestamp (HIGHEST)
            # - Priority 1:  score = 10e12 + timestamp (LOWEST)
            # ZPOPMAX pops priority 10 first ✓

            score = task['priority'] * 1e13 + task['timestamp']
            task_json = json.dumps(task)
            self.redis.zadd(self.test_queue, {task_json: score})
            print(f"  Added {task['id']}: priority={task['priority']}, score={score}")

        print(f"\nQueue size: {self.redis.zcard(self.test_queue)}")

        print("\nPopping with ZPOPMAX (highest score first)...")
        popped_order = []
        while True:
            result = self.redis.zpopmax(self.test_queue)
            if not result:
                break
            task_json, score = result[0]
            task = json.loads(task_json)
            popped_order.append(task['id'])
            print(f"  Popped: {task['id']} (priority={task['priority']}, score={score})")

        print(f"\nPopped order: {popped_order}")

        expected = ['p10-1', 'p10-2', 'p5-1', 'p5-2', 'p1-1', 'p1-2']

        if popped_order == expected:
            print("\n✓ PASS: Priorities processed correctly with priority*1e13!")
            return popped_order
        else:
            print(f"\n✗ FAIL: Still incorrect")
            print(f"  Expected: {expected}")
            print(f"  Got:      {popped_order}")
            return popped_order

def main():
    print("="*60)
    print("HYBRID MODE PRIORITY BUG TEST")
    print("="*60)
    print("\nThis test demonstrates the priority inversion bug in HYBRID mode.")
    print("\nBUG: claim_task() uses ZPOPMAX but migration uses (10-priority)")
    print("Result: Low priority tasks process FIRST (priority inversion!)")
    print("\nFIXES:")
    print("  1. Change claim_task() to use ZPOPMIN (pop lowest score)")
    print("  2. Change formula to priority*1e13 + keep ZPOPMAX")

    tester = HybridPriorityTester()

    try:
        # Test 1: Demonstrates the bug
        result1 = tester.test_zpopmax_current_formula()

        # Test 2: FIX #1 - Use ZPOPMIN instead of ZPOPMAX
        result2 = tester.test_zpopmin_current_formula()

        # Test 3: FIX #2 - Use priority*1e13 with ZPOPMAX
        result3 = tester.test_zpopmax_reversed_formula()

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        expected = ['p10-1', 'p10-2', 'p5-1', 'p5-2', 'p1-1', 'p1-2']

        print("\nExpected order (correct):")
        print(f"  {expected}")

        print("\nTest 1 (CURRENT - BUGGY):")
        print(f"  {result1}")
        print(f"  Status: {'✓ PASS' if result1 == expected else '✗ FAIL - Priority inversion!'}")

        print("\nTest 2 (FIX #1 - ZPOPMIN):")
        print(f"  {result2}")
        print(f"  Status: {'✓ PASS' if result2 == expected else '✗ FAIL'}")

        print("\nTest 3 (FIX #2 - priority*1e13):")
        print(f"  {result3}")
        print(f"  Status: {'✓ PASS' if result3 == expected else '✗ FAIL'}")

        print("\n" + "="*60)
        print("RECOMMENDATION")
        print("="*60)
        print("\nUse FIX #1 (ZPOPMIN) because:")
        print("  1. Smaller change (just ZPOPMAX → ZPOPMIN in Lua)")
        print("  2. Keeps existing formula (10-priority) unchanged")
        print("  3. Consistent with documentation (lower score = higher priority)")
        print("  4. Already used in non-HYBRID mode (LIST queues)")

    finally:
        tester.cleanup()
        print("\n✓ Cleanup complete")

if __name__ == '__main__':
    main()
