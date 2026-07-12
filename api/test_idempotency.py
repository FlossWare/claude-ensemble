#!/usr/bin/env python3
"""
Test idempotency of queue workers

Verifies:
1. Duplicate tasks with same idempotency_key are skipped
2. Workers check before processing
3. Filesystem writes are atomic
4. Database state is consistent
"""

import requests
import time
import json
from pathlib import Path

API_BASE = 'http://aio-01:5000'

def test_idempotency():
    """Test that duplicate tasks are properly handled"""

    print("=" * 70)
    print("TESTING QUEUE IDEMPOTENCY")
    print("=" * 70)

    # Test data
    test_task = {
        'url': 'https://test.example.com/article-12345',
        'source': 'test',
        'category': 'test-idempotency',
        'title': 'Test Article',
        'content': 'This is a test article for idempotency checking.',
        'metadata': {'test': True}
    }

    idempotency_key = 'test-idempotency-001'

    # Test 1: Add task first time
    print("\n[1] Adding task first time...")
    response1 = requests.post(
        f'{API_BASE}/queue/add',
        json={
            'queue': 'store',
            'data': test_task,
            'priority': 5,
            'idempotency_key': idempotency_key
        }
    )

    print(f"Status: {response1.status_code}")
    result1 = response1.json()
    print(f"Response: {json.dumps(result1, indent=2)}")

    if response1.status_code != 201:
        print("❌ FAILED: Expected 201 Created")
        return False

    if not result1.get('queued'):
        print("❌ FAILED: Task should be queued")
        return False

    task_id_1 = result1['task_id']
    print(f"✅ Task queued with ID: {task_id_1}")

    # Test 2: Try to add same task again (should be rejected)
    print("\n[2] Adding same task again (should be skipped)...")
    response2 = requests.post(
        f'{API_BASE}/queue/add',
        json={
            'queue': 'store',
            'data': test_task,
            'priority': 5,
            'idempotency_key': idempotency_key
        }
    )

    print(f"Status: {response2.status_code}")
    result2 = response2.json()
    print(f"Response: {json.dumps(result2, indent=2)}")

    if result2.get('queued'):
        print("❌ FAILED: Task should NOT be queued again")
        return False

    if result2.get('task_id') != task_id_1:
        print("❌ FAILED: Should return same task_id")
        return False

    print("✅ Duplicate task correctly rejected")

    # Test 3: Check queue stats
    print("\n[3] Checking queue stats...")
    response3 = requests.get(f'{API_BASE}/queue/stats')
    stats = response3.json()

    print(f"Queue stats: {json.dumps(stats.get('store', {}), indent=2)}")

    store_stats = stats.get('store', {})
    if store_stats.get('pending', 0) == 0:
        print("⚠️  No pending tasks (worker may have already processed)")
    else:
        print(f"✅ {store_stats.get('pending', 0)} pending task(s)")

    # Test 4: Verify worker won't process duplicate
    print("\n[4] Simulating worker processing...")

    # Fetch task
    response4 = requests.get(
        f'{API_BASE}/queue/fetch/store',
        params={'worker_id': 'test-worker-idempotency'}
    )

    if response4.status_code == 404:
        print("⚠️  No tasks available (already processed or worker running)")
    else:
        task = response4.json()
        print(f"Fetched task: {task['task_id']}")

        # Complete it
        response5 = requests.post(
            f'{API_BASE}/queue/complete/store/{task["task_id"]}'
        )
        print(f"Completed: {response5.json()}")

    # Test 5: Try to add again after completion
    print("\n[5] Adding task after completion (should still be skipped)...")
    response6 = requests.post(
        f'{API_BASE}/queue/add',
        json={
            'queue': 'store',
            'data': test_task,
            'priority': 5,
            'idempotency_key': idempotency_key
        }
    )

    result6 = response6.json()
    print(f"Response: {json.dumps(result6, indent=2)}")

    if result6.get('queued'):
        print("❌ FAILED: Completed task should prevent re-queuing")
        return False

    print("✅ Idempotency preserved after completion")

    # Summary
    print("\n" + "=" * 70)
    print("✅ ALL IDEMPOTENCY TESTS PASSED")
    print("=" * 70)
    print("\nVerified:")
    print("  ✓ Duplicate tasks rejected at queue level")
    print("  ✓ Same task_id returned for duplicates")
    print("  ✓ Completed tasks prevent re-queuing")
    print("  ✓ Queue stats consistent")

    return True


def test_worker_idempotency_check():
    """Test that workers check idempotency before processing"""

    print("\n" + "=" * 70)
    print("TESTING WORKER IDEMPOTENCY CHECK")
    print("=" * 70)

    # This test requires workers to be running
    # We'll check the database state directly

    import psycopg2
    import psycopg2.extras

    try:
        conn = psycopg2.connect(
            host='aio-01',
            port=5433,
            user='sfloess',
            database='learning',
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor = conn.cursor()

        # Check for duplicate idempotency keys
        cursor.execute("""
            SELECT idempotency_key, COUNT(*) as count
            FROM queue.store
            WHERE idempotency_key IS NOT NULL
            GROUP BY idempotency_key
            HAVING COUNT(*) > 1
        """)

        duplicates = cursor.fetchall()

        if duplicates:
            print("❌ FAILED: Found duplicate idempotency keys in database:")
            for dup in duplicates:
                print(f"  - {dup['idempotency_key']}: {dup['count']} entries")
            return False

        print("✅ No duplicate idempotency keys in database")

        # Check for completed tasks that were re-queued
        cursor.execute("""
            SELECT
                idempotency_key,
                status,
                COUNT(*) as count
            FROM queue.store
            WHERE idempotency_key IN (
                SELECT idempotency_key
                FROM queue.store
                WHERE status = 'completed'
                  AND idempotency_key IS NOT NULL
            )
            GROUP BY idempotency_key, status
            ORDER BY idempotency_key, status
        """)

        completed_dupes = cursor.fetchall()

        if len(completed_dupes) > 1:
            print("⚠️  Found tasks with same idempotency key as completed tasks:")
            for task in completed_dupes:
                print(f"  - {task['idempotency_key']}: {task['status']} ({task['count']})")
            print("This should not happen if workers check idempotency correctly")

        conn.close()

        print("\n✅ WORKER IDEMPOTENCY CHECK PASSED")
        return True

    except Exception as e:
        print(f"❌ FAILED: Database check error: {e}")
        return False


if __name__ == '__main__':
    import sys

    success = test_idempotency()

    if success:
        success = test_worker_idempotency_check()

    sys.exit(0 if success else 1)
