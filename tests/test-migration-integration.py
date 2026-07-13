#!/usr/bin/env python3
"""
PostgreSQL → Redis Migration Integration Test

Tests the complete migration and processing pipeline:
1. Insert 100 test tasks into PostgreSQL (scraping.tasks)
2. Migrate tasks from PostgreSQL to Redis queues
3. Simulate worker processing (fetch from Redis)
4. Store content in PostgreSQL (knowledge.documents)
5. Verify data integrity and performance

Usage:
  python3 tests/test-migration-integration.py [--tasks N] [--cleanup]

Options:
  --tasks N    Number of test tasks (default: 100)
  --cleanup    Remove test data after completion

Created: 2026-07-11
"""

import sys
import time
import json
import hashlib
import psycopg2
import redis
from datetime import datetime
from typing import List, Dict, Tuple

# Configuration
CONFIG = {
    'postgres': {
        'host': 'aio-01',
        'port': 5433,
        'database': 'learning',
        'user': 'sfloess',
    },
    'redis': {
        'host': 'aio-01',
        'port': 6379,
        'decode_responses': True,
    },
    'test_tasks': 100,
    'cleanup': False,
}

# Test state
STATE = {
    'start_time': time.time(),
    'inserted_ids': [],
    'migrated_count': 0,
    'processed_count': 0,
    'stored_count': 0,
    'errors': [],
    'metrics': {
        'insert_time': 0,
        'migration_time': 0,
        'processing_time': 0,
        'total_time': 0,
    },
}

# Utilities
def log(msg, level='INFO'):
    timestamp = datetime.now().isoformat()
    prefix = {
        'INFO': '📋',
        'SUCCESS': '✅',
        'ERROR': '❌',
        'WARN': '⚠️ ',
        'METRIC': '📊',
    }.get(level, '  ')
    print(f"{timestamp} {prefix} {msg}")

def get_pg_conn():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**CONFIG['postgres'])

def get_redis_client():
    """Get Redis client."""
    return redis.Redis(**CONFIG['redis'])

# Test phases
def phase1_insert_test_tasks() -> bool:
    """Insert test tasks into PostgreSQL."""
    log('=' * 60)
    log('PHASE 1: Insert Test Tasks into PostgreSQL')
    log('=' * 60)

    conn = get_pg_conn()
    cur = conn.cursor()

    phase_start = time.time()

    try:
        for i in range(1, CONFIG['test_tasks'] + 1):
            url = f"https://example.com/test-doc-{i}"
            category = 'performance' if i % 4 == 0 else 'ai' if i % 3 == 0 else 'ml' if i % 2 == 0 else 'ga'
            priority = (i % 10) + 1

            cur.execute("""
                INSERT INTO scraping.tasks (url, category, priority, status)
                VALUES (%s, %s, %s, 'pending')
                RETURNING id
            """, (url, category, priority))

            task_id = cur.fetchone()[0]
            STATE['inserted_ids'].append(task_id)

        conn.commit()

        STATE['metrics']['insert_time'] = time.time() - phase_start
        log(f"Inserted {len(STATE['inserted_ids'])} tasks", 'SUCCESS')
        log(f"Insert time: {STATE['metrics']['insert_time']:.2f}s", 'METRIC')

        return len(STATE['inserted_ids']) == CONFIG['test_tasks']

    except Exception as e:
        conn.rollback()
        STATE['errors'].append(f"Insert failed: {e}")
        log(f"Insert failed: {e}", 'ERROR')
        return False
    finally:
        cur.close()
        conn.close()

def phase2_migrate_to_redis() -> bool:
    """Migrate tasks from PostgreSQL to Redis."""
    log('=' * 60)
    log('PHASE 2: Migrate PostgreSQL → Redis Queues')
    log('=' * 60)

    conn = get_pg_conn()
    cur = conn.cursor()
    redis_client = get_redis_client()

    phase_start = time.time()

    try:
        # Get pending tasks
        cur.execute("""
            SELECT id, url, category, priority
            FROM scraping.tasks
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
        """)

        tasks = cur.fetchall()
        log(f"Found {len(tasks)} pending tasks", 'INFO')

        # Queue mapping
        queue_map = {
            'performance': 'queue:performance:high',
            'ai': 'queue:ai:medium',
            'ml': 'queue:ml:medium',
            'ga': 'queue:ga:low',
        }

        # Migrate to Redis
        for task_id, url, category, priority in tasks:
            queue = queue_map.get(category, 'queue:ga:low')

            item = json.dumps({
                'url': url,
                'category': category,
                'priority': priority,
                'task_id': task_id,
            })

            redis_client.lpush(queue, item)

            # Update PostgreSQL status
            cur.execute("""
                UPDATE scraping.tasks
                SET status = 'queued', queued_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (task_id,))

            STATE['migrated_count'] += 1

        conn.commit()

        STATE['metrics']['migration_time'] = time.time() - phase_start
        log(f"Migrated {STATE['migrated_count']} tasks", 'SUCCESS')
        log(f"Migration time: {STATE['metrics']['migration_time']:.2f}s", 'METRIC')

        # Verify Redis queues
        total_in_redis = 0
        for queue_name, queue_key in queue_map.items():
            count = redis_client.llen(queue_key)
            total_in_redis += count
            log(f"  {queue_name}: {count} tasks", 'INFO')

        log(f"Total in Redis: {total_in_redis}", 'INFO')

        return STATE['migrated_count'] >= CONFIG['test_tasks'] * 0.95

    except Exception as e:
        conn.rollback()
        STATE['errors'].append(f"Migration failed: {e}")
        log(f"Migration failed: {e}", 'ERROR')
        return False
    finally:
        cur.close()
        conn.close()

def phase3_process_redis_queues() -> bool:
    """Process tasks from Redis queues (simulated workers)."""
    log('=' * 60)
    log('PHASE 3: Process Redis Queues')
    log('=' * 60)

    conn = get_pg_conn()
    cur = conn.cursor()
    redis_client = get_redis_client()

    phase_start = time.time()

    queues = [
        'queue:performance:high',
        'queue:ai:medium',
        'queue:ml:medium',
        'queue:ga:low',
    ]

    try:
        # Process all queues until empty
        while True:
            # Try to pop from queues (priority order)
            result = redis_client.brpop(queues, timeout=2)

            if not result:
                # Queues empty
                break

            queue, item_json = result
            item = json.loads(item_json)

            url = item['url']
            category = item['category']
            task_id = item['task_id']

            # Simulate content storage
            content = f"This is test content for {url}. " * 20
            content_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

            cur.execute("""
                INSERT INTO knowledge.documents (url, title, content, category, fetched_at, content_hash)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (content_hash) DO UPDATE SET content = EXCLUDED.content
            """, (url, f"Test Document {task_id}", content, category, content_hash))

            # Update task status
            cur.execute("""
                UPDATE scraping.tasks
                SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (task_id,))

            STATE['processed_count'] += 1

            if STATE['processed_count'] % 10 == 0:
                conn.commit()
                log(f"Processed {STATE['processed_count']} tasks...", 'INFO')

        conn.commit()

        STATE['metrics']['processing_time'] = time.time() - phase_start
        log(f"Processed {STATE['processed_count']} tasks", 'SUCCESS')
        log(f"Processing time: {STATE['metrics']['processing_time']:.2f}s", 'METRIC')

        avg_latency = STATE['metrics']['processing_time'] / STATE['processed_count'] if STATE['processed_count'] > 0 else 0
        log(f"Average latency: {avg_latency * 1000:.0f}ms per task", 'METRIC')

        return STATE['processed_count'] >= CONFIG['test_tasks'] * 0.95

    except Exception as e:
        conn.rollback()
        STATE['errors'].append(f"Processing failed: {e}")
        log(f"Processing failed: {e}", 'ERROR')
        return False
    finally:
        cur.close()
        conn.close()

def phase4_verify_storage() -> bool:
    """Verify data was stored correctly."""
    log('=' * 60)
    log('PHASE 4: Verify Storage')
    log('=' * 60)

    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        # Count stored documents
        cur.execute("""
            SELECT COUNT(*)
            FROM knowledge.documents
            WHERE url LIKE 'https://example.com/test-doc-%'
        """)

        STATE['stored_count'] = cur.fetchone()[0]
        log(f"Stored documents: {STATE['stored_count']}", 'SUCCESS')

        # Verify content integrity (sample 10 docs)
        cur.execute("""
            SELECT id, url, content
            FROM knowledge.documents
            WHERE url LIKE 'https://example.com/test-doc-%'
            LIMIT 10
        """)

        integrity_ok = True
        for doc_id, url, content in cur.fetchall():
            if not content or len(content) < 100:
                STATE['errors'].append(f"Document {doc_id} has insufficient content: {len(content)} chars")
                integrity_ok = False

        if integrity_ok:
            log("Content integrity: PASS", 'SUCCESS')
        else:
            log("Content integrity: FAIL", 'ERROR')

        return STATE['stored_count'] >= CONFIG['test_tasks'] * 0.95 and integrity_ok

    except Exception as e:
        STATE['errors'].append(f"Verification failed: {e}")
        log(f"Verification failed: {e}", 'ERROR')
        return False
    finally:
        cur.close()
        conn.close()

def phase5_cleanup():
    """Cleanup test data."""
    if not CONFIG['cleanup']:
        log("Skipping cleanup (no --cleanup flag)", 'INFO')
        return True

    log('=' * 60)
    log('PHASE 5: Cleanup Test Data')
    log('=' * 60)

    conn = get_pg_conn()
    cur = conn.cursor()
    redis_client = get_redis_client()

    try:
        # Delete from PostgreSQL
        cur.execute("DELETE FROM knowledge.documents WHERE url LIKE 'https://example.com/test-doc-%'")
        cur.execute("DELETE FROM scraping.tasks WHERE url LIKE 'https://example.com/test-doc-%'")
        conn.commit()

        # Clear Redis queues
        queues = [
            'queue:performance:high',
            'queue:ai:medium',
            'queue:ml:medium',
            'queue:ga:low',
        ]
        for queue in queues:
            redis_client.delete(queue)

        log("Cleaned up test data", 'SUCCESS')
        return True

    except Exception as e:
        conn.rollback()
        STATE['errors'].append(f"Cleanup failed: {e}")
        log(f"Cleanup failed: {e}", 'ERROR')
        return False
    finally:
        cur.close()
        conn.close()

def print_summary() -> int:
    """Print test summary and return exit code."""
    log('')
    log('=' * 60)
    log('TEST SUMMARY')
    log('=' * 60)

    STATE['metrics']['total_time'] = time.time() - STATE['start_time']

    log(f"Total runtime: {STATE['metrics']['total_time']:.2f}s", 'METRIC')
    log('')
    log('Phase Breakdown:', 'METRIC')
    log(f"  Insert:      {STATE['metrics']['insert_time']:.2f}s", 'METRIC')
    log(f"  Migration:   {STATE['metrics']['migration_time']:.2f}s", 'METRIC')
    log(f"  Processing:  {STATE['metrics']['processing_time']:.2f}s", 'METRIC')
    log('')
    log('Data Flow:', 'METRIC')
    log(f"  Tasks inserted:   {len(STATE['inserted_ids'])}", 'METRIC')
    log(f"  Tasks migrated:   {STATE['migrated_count']}", 'METRIC')
    log(f"  Tasks processed:  {STATE['processed_count']}", 'METRIC')
    log(f"  Docs stored:      {STATE['stored_count']}", 'METRIC')
    log('')

    if STATE['errors']:
        log(f"Errors ({len(STATE['errors'])}):", 'ERROR')
        for err in STATE['errors'][:10]:
            log(f"  {err}", 'ERROR')
        if len(STATE['errors']) > 10:
            log(f"  ... and {len(STATE['errors']) - 10} more", 'ERROR')
    else:
        log('No errors encountered', 'SUCCESS')

    log('')
    log('=' * 60)

    # Pass/fail criteria
    pass_rate = STATE['processed_count'] / CONFIG['test_tasks'] if CONFIG['test_tasks'] > 0 else 0
    avg_latency = (STATE['metrics']['processing_time'] / STATE['processed_count']) * 1000 if STATE['processed_count'] > 0 else 0
    passed = (
        pass_rate >= 0.95
        and avg_latency < 2000
        and len(STATE['errors']) < 10
    )

    if passed:
        log('✅ INTEGRATION TEST PASSED', 'SUCCESS')
        return 0
    else:
        log('❌ INTEGRATION TEST FAILED', 'ERROR')
        if pass_rate < 0.95:
            log(f"  Pass rate: {pass_rate * 100:.1f}% (expected ≥95%)", 'ERROR')
        if avg_latency >= 2000:
            log(f"  Latency: {avg_latency:.0f}ms (expected <2000ms)", 'ERROR')
        if len(STATE['errors']) >= 10:
            log(f"  Errors: {len(STATE['errors'])} (expected <10)", 'ERROR')
        return 1

def main():
    """Main entry point."""
    # Parse CLI args
    for i in range(1, len(sys.argv)):
        arg = sys.argv[i]
        if arg == '--cleanup':
            CONFIG['cleanup'] = True
        elif arg == '--tasks':
            CONFIG['test_tasks'] = int(sys.argv[i + 1])

    log('Starting PostgreSQL → Redis Integration Test', 'INFO')
    log(f"Configuration: {CONFIG['test_tasks']} tasks, cleanup={CONFIG['cleanup']}", 'INFO')
    log('')

    try:
        results = {
            'phase1': phase1_insert_test_tasks(),
            'phase2': phase2_migrate_to_redis(),
            'phase3': phase3_process_redis_queues(),
            'phase4': phase4_verify_storage(),
            'phase5': phase5_cleanup(),
        }

        log('')
        log('Phase Results:', 'INFO')
        for phase, passed in results.items():
            log(f"  {phase}: {'PASS' if passed else 'FAIL'}", 'SUCCESS' if passed else 'ERROR')

        exit_code = print_summary()
        sys.exit(exit_code)

    except Exception as e:
        log(f"Test failed with error: {e}", 'ERROR')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
