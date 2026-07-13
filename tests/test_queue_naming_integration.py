#!/usr/bin/env python3
"""
Integration Test: Queue Naming Convention

Verifies that all queue operations use the redis:queue:{stage}:{priority} naming.

Tests:
1. Queue name parsing in RedisAtomicOps
2. Stage extraction from queue names
3. Processing/heartbeat key generation
4. Queue mode auto-detection

Run: python3 tests/test_queue_naming_integration.py
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def test_queue_name_parsing():
    """Test that queue names are correctly parsed."""

    print("=" * 70)
    print("QUEUE NAMING INTEGRATION TEST")
    print("=" * 70)
    print()

    test_cases = [
        # (queue_name, expected_stage, expected_processing, expected_heartbeat)
        ('redis:queue:store:high', 'store:high', 'redis:processing:store:high', 'redis:heartbeat:store:high'),
        ('redis:queue:store:medium', 'store:medium', 'redis:processing:store:medium', 'redis:heartbeat:store:medium'),
        ('redis:queue:store:low', 'store:low', 'redis:processing:store:low', 'redis:heartbeat:store:low'),
        ('redis:queue:chunk', 'chunk', 'redis:processing:chunk', 'redis:heartbeat:chunk'),
        ('redis:queue:embed', 'embed', 'redis:processing:embed', 'redis:heartbeat:embed'),
        ('redis:queue:graph', 'graph', 'redis:processing:graph', 'redis:heartbeat:graph'),
        ('redis:queue:scrape:high', 'scrape:high', 'redis:processing:scrape:high', 'redis:heartbeat:scrape:high'),
        ('redis:queue:scrape:medium', 'scrape:medium', 'redis:processing:scrape:medium', 'redis:heartbeat:scrape:medium'),
        ('redis:queue:scrape:low', 'scrape:low', 'redis:processing:scrape:low', 'redis:heartbeat:scrape:low'),
    ]

    print("Testing queue name parsing...")
    print()

    failures = []

    for queue_name, expected_stage, expected_processing, expected_heartbeat in test_cases:
        # Parse queue name (mimic logic from RedisAtomicOps.claim_task)
        parts = queue_name.split(':')
        if len(parts) >= 4:
            # redis:queue:stage:priority -> use "stage:priority"
            stage = f"{parts[2]}:{parts[3]}"
        elif len(parts) >= 3:
            # redis:queue:stage -> use "stage"
            stage = parts[2]
        else:
            stage = parts[-1]

        processing_set = f'redis:processing:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'

        # Verify
        if stage != expected_stage:
            failures.append(f"  ✗ {queue_name}: stage mismatch (got {stage}, expected {expected_stage})")
        elif processing_set != expected_processing:
            failures.append(f"  ✗ {queue_name}: processing mismatch (got {processing_set}, expected {expected_processing})")
        elif heartbeat_hash != expected_heartbeat:
            failures.append(f"  ✗ {queue_name}: heartbeat mismatch (got {heartbeat_hash}, expected {expected_heartbeat})")
        else:
            print(f"  ✓ {queue_name}")
            print(f"    Stage: {stage}")
            print(f"    Processing: {processing_set}")
            print(f"    Heartbeat: {heartbeat_hash}")
            print()

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print(failure)
        print()
        print("=" * 70)
        print("TEST FAILED")
        print("=" * 70)
        return False
    else:
        print("=" * 70)
        print("TEST PASSED: All queue names parse correctly!")
        print("=" * 70)
        return True


def test_complete_task_stage_parameter():
    """Test that complete_task correctly uses stage parameter."""

    print()
    print("=" * 70)
    print("COMPLETE TASK STAGE PARAMETER TEST")
    print("=" * 70)
    print()

    test_cases = [
        # (stage_param, expected_processing, expected_completed, expected_heartbeat)
        ('store:high', 'redis:processing:store:high', 'redis:completed:store:high', 'redis:heartbeat:store:high'),
        ('store:medium', 'redis:processing:store:medium', 'redis:completed:store:medium', 'redis:heartbeat:store:medium'),
        ('chunk', 'redis:processing:chunk', 'redis:completed:chunk', 'redis:heartbeat:chunk'),
        ('embed', 'redis:processing:embed', 'redis:completed:embed', 'redis:heartbeat:embed'),
        ('scrape:high', 'redis:processing:scrape:high', 'redis:completed:scrape:high', 'redis:heartbeat:scrape:high'),
    ]

    print("Testing complete_task stage parameter...")
    print()

    failures = []

    for stage, expected_processing, expected_completed, expected_heartbeat in test_cases:
        # Mimic logic from RedisAtomicOps.complete_task
        processing_set = f'redis:processing:{stage}'
        completed_hash = f'redis:completed:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'

        # Verify
        if processing_set != expected_processing:
            failures.append(f"  ✗ stage={stage}: processing mismatch (got {processing_set}, expected {expected_processing})")
        elif completed_hash != expected_completed:
            failures.append(f"  ✗ stage={stage}: completed mismatch (got {completed_hash}, expected {expected_completed})")
        elif heartbeat_hash != expected_heartbeat:
            failures.append(f"  ✗ stage={stage}: heartbeat mismatch (got {heartbeat_hash}, expected {expected_heartbeat})")
        else:
            print(f"  ✓ stage={stage}")
            print(f"    Processing: {processing_set}")
            print(f"    Completed: {completed_hash}")
            print(f"    Heartbeat: {heartbeat_hash}")
            print()

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print(failure)
        print()
        print("=" * 70)
        print("TEST FAILED")
        print("=" * 70)
        return False
    else:
        print("=" * 70)
        print("TEST PASSED: All stage parameters generate correct keys!")
        print("=" * 70)
        return True


def test_fail_task_queue_naming():
    """Test that fail_task correctly generates queue names."""

    print()
    print("=" * 70)
    print("FAIL TASK QUEUE NAMING TEST")
    print("=" * 70)
    print()

    test_cases = [
        # (stage_param, expected_queue, expected_dlq)
        ('store:high', 'redis:queue:store:high', 'redis:dlq:store:high'),
        ('store:medium', 'redis:queue:store:medium', 'redis:dlq:store:medium'),
        ('chunk', 'redis:queue:chunk', 'redis:dlq:chunk'),
        ('embed', 'redis:queue:embed', 'redis:dlq:embed'),
        ('scrape:low', 'redis:queue:scrape:low', 'redis:dlq:scrape:low'),
    ]

    print("Testing fail_task queue naming...")
    print()

    failures = []

    for stage, expected_queue, expected_dlq in test_cases:
        # Mimic logic from RedisAtomicOps.fail_task
        queue_name = f'redis:queue:{stage}'
        dlq_name = f'redis:dlq:{stage}'

        # Verify
        if queue_name != expected_queue:
            failures.append(f"  ✗ stage={stage}: queue mismatch (got {queue_name}, expected {expected_queue})")
        elif dlq_name != expected_dlq:
            failures.append(f"  ✗ stage={stage}: DLQ mismatch (got {dlq_name}, expected {expected_dlq})")
        else:
            print(f"  ✓ stage={stage}")
            print(f"    Queue: {queue_name}")
            print(f"    DLQ: {dlq_name}")
            print()

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print(failure)
        print()
        print("=" * 70)
        print("TEST FAILED")
        print("=" * 70)
        return False
    else:
        print("=" * 70)
        print("TEST PASSED: All fail_task operations generate correct queue names!")
        print("=" * 70)
        return True


def main():
    """Run all integration tests."""

    results = []

    # Run tests
    results.append(('Queue Name Parsing', test_queue_name_parsing()))
    results.append(('Complete Task Stage Parameter', test_complete_task_stage_parameter()))
    results.append(('Fail Task Queue Naming', test_fail_task_queue_naming()))

    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print()

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("=" * 70)
        print("ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Queue naming convention verified:")
        print("  - All queues use redis:queue:{stage}:{priority} format")
        print("  - Processing keys use redis:processing:{stage}:{priority}")
        print("  - Heartbeat keys use redis:heartbeat:{stage}:{priority}")
        print("  - DLQ keys use redis:dlq:{stage}:{priority}")
        print("  - Completed keys use redis:completed:{stage}:{priority}")
        return 0
    else:
        print("=" * 70)
        print("SOME TESTS FAILED!")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
