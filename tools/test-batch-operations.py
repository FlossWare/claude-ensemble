#!/usr/bin/env python3
"""
Quick test of batch operations

Creates test queue, adds tasks, claims batch, verifies atomicity.
"""

import sys
from postgres_queue_batch import get_queue_batch
import psycopg2
import json

def main():
    """Test batch operations"""

    # Connect to database
    queue = get_queue_batch()
    conn = psycopg2.connect(
        host='aio-01',
        port=5433,
        database='learning',
        user='sfloess',
        password=''
    )
    cursor = conn.cursor()

    # Create test queue if not exists
    print("Setting up test queue...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queue.batch_test (
            id SERIAL PRIMARY KEY,
            data JSONB NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            priority INTEGER DEFAULT 50,
            created_at TIMESTAMP DEFAULT NOW(),
            claimed_by VARCHAR(255),
            claimed_at TIMESTAMP,
            last_heartbeat TIMESTAMP,
            last_worker_id VARCHAR(255),
            timeout_at TIMESTAMP,
            completed_at TIMESTAMP,
            retry_count INTEGER DEFAULT 0,
            scheduled_at TIMESTAMP,
            error TEXT,
            result JSONB
        )
    """)
    conn.commit()

    # Clear existing data
    cursor.execute("TRUNCATE queue.batch_test RESTART IDENTITY")
    conn.commit()

    # Insert test tasks
    print("Inserting 20 test tasks...")
    for i in range(20):
        cursor.execute("""
            INSERT INTO queue.batch_test (data, priority)
            VALUES (%s::jsonb, %s)
        """, (json.dumps({'task': f'task-{i}'}), i % 100))
    conn.commit()

    # Test 1: Claim batch
    print("\nTest 1: Claiming batch of 10 tasks...")
    tasks = queue.claim_batch('batch_test', 'worker-test', batch_size=10)
    print(f"✓ Claimed {len(tasks)} tasks")
    assert len(tasks) == 10, f"Expected 10 tasks, got {len(tasks)}"

    # Verify atomicity - all tasks should be marked as processing
    cursor.execute("""
        SELECT COUNT(*) FROM queue.batch_test
        WHERE status = 'processing' AND claimed_by = 'worker-test'
    """)
    processing_count = cursor.fetchone()[0]
    print(f"✓ {processing_count} tasks marked as processing")
    assert processing_count == 10, f"Expected 10 processing, got {processing_count}"

    # Test 2: Heartbeat
    print("\nTest 2: Updating heartbeat...")
    task_ids = [t['id'] for t in tasks]
    updated = queue.heartbeat_batch('batch_test', task_ids)
    print(f"✓ Updated heartbeat for {updated} tasks")
    assert updated == 10, f"Expected 10 updated, got {updated}"

    # Test 3: Complete batch
    print("\nTest 3: Completing batch...")
    completed = queue.complete_batch('batch_test', task_ids[:5], {'status': 'success'})
    print(f"✓ Completed {completed} tasks")
    assert completed == 5, f"Expected 5 completed, got {completed}"

    # Test 4: Fail batch
    print("\nTest 4: Failing batch with retry...")
    failed = queue.fail_batch('batch_test', task_ids[5:], 'Test error', retry=True)
    print(f"✓ Failed {failed} tasks (will retry)")
    assert failed == 5, f"Expected 5 failed, got {failed}"

    # Verify retry logic
    cursor.execute("""
        SELECT status, retry_count FROM queue.batch_test
        WHERE id = ANY(%s)
    """, (task_ids[5:],))
    for row in cursor.fetchall():
        assert row[0] == 'pending', f"Expected pending, got {row[0]}"
        assert row[1] == 1, f"Expected retry_count=1, got {row[1]}"
    print("✓ Tasks marked for retry")

    # Test 5: Stats
    print("\nTest 5: Getting stats...")
    stats = queue.get_batch_stats('batch_test')
    print(f"  Pending: {stats.get('pending', 0)}")
    print(f"  Processing: {stats.get('processing', 0)}")
    print(f"  Completed: {stats.get('completed', 0)}")
    print(f"  Failed: {stats.get('failed', 0)}")

    # Test 6: Claim another batch (should get retry tasks + remaining)
    print("\nTest 6: Claiming another batch...")
    tasks2 = queue.claim_batch('batch_test', 'worker-test', batch_size=10)
    print(f"✓ Claimed {len(tasks2)} tasks (includes retries)")
    assert len(tasks2) == 10, f"Expected 10 tasks, got {len(tasks2)}"

    # Cleanup
    print("\n✓ All tests passed!")
    cursor.close()
    conn.close()
    queue.close()

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
