#!/usr/bin/env python3
"""
Redis Queue Integration Test

Tests complete workflow:
1. Migrate 100 test items to Redis using HYBRID mode
2. Start workers to process them
3. Verify all 100 complete successfully
4. Check data integrity

Exit codes:
  0 = All tests passed
  1 = Test failed
"""

import sys
import json
import time
import redis
import psycopg2
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Add scripts directory to path
script_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(script_dir))

# Import Redis operations
import importlib.util
spec = importlib.util.spec_from_file_location("redis_atomic_operations", script_dir / "redis-atomic-operations.py")
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps

# Configuration
REDIS_HOST = 'aio-01'
REDIS_PORT = 6379
PG_HOST = 'aio-01'
PG_PORT = 5433
PG_USER = 'sfloess'
PG_DB = 'learning'

TEST_QUEUE_PREFIX = 'test:integration'
NUM_TEST_ITEMS = 100

class IntegrationTest:
    def __init__(self):
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self.pg_conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, user=PG_USER, database=PG_DB
        )
        self.pg_cursor = self.pg_conn.cursor()
        self.ops = RedisAtomicOps(host=REDIS_HOST, port=REDIS_PORT)

        self.stats = {
            'items_created': 0,
            'items_migrated': 0,
            'items_processed': 0,
            'items_completed': 0,
            'items_failed': 0,
            'duration_seconds': 0
        }

    def cleanup_test_data(self):
        """Clean up all test data from Redis and PostgreSQL."""
        print("\n=== Cleanup ===")

        # Clean Redis test queues and processing/completed hashes
        cleanup_keys = [
            'redis:queue:testintegration:high',
            'redis:queue:testintegration:medium',
            'redis:queue:testintegration:low',
            'redis:processing:testintegration',
            'redis:processing:testintegration:metadata',
            'redis:completed:testintegration',
            'redis:heartbeat:testintegration',
            f'{TEST_QUEUE_PREFIX}:idempotency'
        ]

        deleted_count = 0
        for key in cleanup_keys:
            if self.redis.exists(key):
                self.redis.delete(key)
                deleted_count += 1

        if deleted_count > 0:
            print(f"✓ Deleted {deleted_count} Redis keys")

        # Clean PostgreSQL test items
        self.pg_cursor.execute("""
            DELETE FROM queue.store
            WHERE idempotency_key LIKE 'test-integration-%'
        """)
        deleted = self.pg_cursor.rowcount
        self.pg_conn.commit()
        if deleted > 0:
            print(f"✓ Deleted {deleted} PostgreSQL test items")

    def create_test_items_in_pg(self, num_items: int) -> List[int]:
        """Create test items in PostgreSQL queue.store table."""
        print(f"\n=== Step 1: Create {num_items} Test Items in PostgreSQL ===")

        item_ids = []

        for i in range(num_items):
            # Vary priorities: 10% high (8-10), 60% medium (4-7), 30% low (1-3)
            if i % 10 == 0:
                priority = 8 + (i % 3)  # High: 8, 9, 10
            elif i % 10 < 7:
                priority = 4 + (i % 4)  # Medium: 4, 5, 6, 7
            else:
                priority = 1 + (i % 3)  # Low: 1, 2, 3

            data = {
                'test_id': i,
                'test_type': 'integration_test',
                'priority': priority,
                'created_at': datetime.utcnow().isoformat()
            }

            self.pg_cursor.execute("""
                INSERT INTO queue.store
                (data, priority, status, retries, created_at, idempotency_key)
                VALUES (%s, %s, 'pending', 0, NOW(), %s)
                RETURNING id
            """, (json.dumps(data), priority, f'test-integration-{i}'))

            item_id = self.pg_cursor.fetchone()[0]
            item_ids.append(item_id)

        self.pg_conn.commit()
        self.stats['items_created'] = len(item_ids)

        print(f"✓ Created {len(item_ids)} test items in PostgreSQL")

        # Show distribution
        self.pg_cursor.execute("""
            SELECT priority, COUNT(*)
            FROM queue.store
            WHERE idempotency_key LIKE 'test-integration-%'
            GROUP BY priority
            ORDER BY priority DESC
        """)
        print("  Priority distribution:")
        for priority, count in self.pg_cursor.fetchall():
            print(f"    Priority {priority}: {count} items")

        return item_ids

    def migrate_to_redis(self) -> bool:
        """Migrate test items from PostgreSQL to Redis using HYBRID mode."""
        print("\n=== Step 2: Migrate to Redis (HYBRID mode) ===")

        # Fetch test items
        self.pg_cursor.execute("""
            SELECT id, data, priority, created_at, idempotency_key
            FROM queue.store
            WHERE idempotency_key LIKE 'test-integration-%'
            AND status = 'pending'
            ORDER BY priority DESC, created_at ASC
        """)

        items = self.pg_cursor.fetchall()
        print(f"  Found {len(items)} items to migrate")

        # Migrate to Redis using HYBRID architecture
        # Use standard queue naming: redis:queue:STAGE:PRIORITY
        for pg_id, data, priority, created_at, idempotency_key in items:
            # Determine queue based on priority
            # Standard naming allows claim_task to extract stage correctly
            if priority >= 8:
                queue = 'redis:queue:testintegration:high'
            elif priority >= 4:
                queue = 'redis:queue:testintegration:medium'
            else:
                queue = 'redis:queue:testintegration:low'

            # Build Redis item
            item = {
                'id': pg_id,
                'pg_id': pg_id,
                'data': data,
                'priority': priority,
                'retries': 0,
                'created_at': created_at.isoformat() if created_at else None,
                'idempotency_key': idempotency_key,
                'migration_timestamp': datetime.utcnow().isoformat(),
                'source': 'integration_test'
            }

            # Calculate priority score (HYBRID: ZADD for initial queues)
            timestamp_ms = int(created_at.timestamp() * 1000) if created_at else int(time.time() * 1000)
            score = (10 - priority) * 1e13 + timestamp_ms

            # ZADD to sorted set
            self.redis.zadd(queue, {json.dumps(item): score})

            # Track idempotency
            self.redis.hset(f'{TEST_QUEUE_PREFIX}:idempotency', idempotency_key, pg_id)

            self.stats['items_migrated'] += 1

        # Verify migration
        high_count = self.redis.zcard('redis:queue:testintegration:high')
        medium_count = self.redis.zcard('redis:queue:testintegration:medium')
        low_count = self.redis.zcard('redis:queue:testintegration:low')
        total = high_count + medium_count + low_count

        print(f"✓ Migrated {self.stats['items_migrated']} items to Redis")
        print(f"  Queue distribution:")
        print(f"    High: {high_count}")
        print(f"    Medium: {medium_count}")
        print(f"    Low: {low_count}")
        print(f"    Total: {total}")

        return total == self.stats['items_migrated']

    def start_test_workers(self, num_workers: int = 4) -> List[subprocess.Popen]:
        """Start test workers to process queue items."""
        print(f"\n=== Step 3: Start {num_workers} Test Workers ===")

        workers = []

        # Create simple test worker script
        worker_script = script_dir / "test-redis-worker-temp.py"
        worker_script.write_text(f"""#!/usr/bin/env python3
import sys
import json
import time
import redis
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(script_dir))

import importlib.util
spec = importlib.util.spec_from_file_location("redis_atomic_operations", script_dir / "redis-atomic-operations.py")
redis_atomic_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redis_atomic_operations)
RedisAtomicOps = redis_atomic_operations.RedisAtomicOps

REDIS_HOST = '{REDIS_HOST}'
REDIS_PORT = {REDIS_PORT}
TEST_QUEUE_PREFIX = '{TEST_QUEUE_PREFIX}'

def main():
    worker_id = sys.argv[1] if len(sys.argv) > 1 else 'worker-1'
    ops = RedisAtomicOps(host=REDIS_HOST, port=REDIS_PORT)
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    queues = [
        'redis:queue:testintegration:high',
        'redis:queue:testintegration:medium',
        'redis:queue:testintegration:low'
    ]

    processed = 0

    while processed < 30:  # Process max 30 items per worker
        # Try to claim from any queue
        task = None
        claimed_queue = None
        for queue_name in queues:
            task = ops.claim_task(queue_name, worker_id, queue_mode='zset')
            if task:
                claimed_queue = queue_name
                break

        if not task:
            time.sleep(0.1)  # Brief pause before retry
            continue

        # Simulate processing (0.1s)
        time.sleep(0.1)

        # Extract stage from queue name (redis:queue:STAGE:PRIORITY)
        # claim_task uses parts[2], so for redis:queue:testintegration:high, stage = 'testintegration'
        stage = claimed_queue.split(':')[2]

        # Complete task - CRITICAL: result_json must be JSON string, not dict!
        result = {{'status': 'success', 'worker': worker_id, 'task_id': task['id']}}
        result_json = json.dumps(result)

        # Complete with correct stage parameter
        status = ops.complete_task(task['id'], worker_id, result_json, stage=stage)

        if status == 'OK':
            processed += 1
        else:
            print(f"Worker {{worker_id}} error completing task {{task['id']}}: {{status}}")
            break

    print(f"Worker {{worker_id}} completed {{processed}} tasks")

if __name__ == '__main__':
    main()
""")
        worker_script.chmod(0o755)

        # Start workers in background
        for i in range(num_workers):
            worker_id = f'test-worker-{i+1}'
            proc = subprocess.Popen(
                ['python3', str(worker_script), worker_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            workers.append(proc)
            print(f"  ✓ Started {worker_id} (PID {proc.pid})")

        return workers

    def monitor_processing(self, workers: List[subprocess.Popen], timeout: int = 60) -> bool:
        """Monitor workers and wait for completion."""
        print(f"\n=== Step 4: Monitor Processing (timeout {timeout}s) ===")

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check queue sizes
            high = self.redis.zcard('redis:queue:testintegration:high')
            medium = self.redis.zcard('redis:queue:testintegration:medium')
            low = self.redis.zcard('redis:queue:testintegration:low')

            # Check completed/processing for stage 'testintegration'
            completed = self.redis.hlen('redis:completed:testintegration') or 0
            processing = self.redis.hlen('redis:processing:testintegration') or 0

            pending = high + medium + low

            print(f"  [{int(time.time() - start_time)}s] Pending: {pending}, Processing: {processing}, Completed: {completed}")

            # Check if all done
            if pending == 0 and processing == 0 and completed >= self.stats['items_migrated']:
                self.stats['items_completed'] = completed
                self.stats['duration_seconds'] = int(time.time() - start_time)
                print(f"\n✓ All items processed in {self.stats['duration_seconds']}s!")
                return True

            time.sleep(2)

        print(f"\n✗ Timeout after {timeout}s")
        return False

    def verify_results(self) -> bool:
        """Verify all items were processed correctly."""
        print("\n=== Step 5: Verify Results ===")

        # Check completed items for stage 'testintegration'
        completed = self.redis.hlen('redis:completed:testintegration') or 0

        print(f"  Completed items: {completed}/{self.stats['items_migrated']}")

        if completed != self.stats['items_migrated']:
            print(f"  ✗ MISMATCH: Expected {self.stats['items_migrated']}, got {completed}")
            return False

        # Sample completed items and verify data integrity
        hash_name = 'redis:completed:testintegration'
        keys = self.redis.hkeys(hash_name)

        if keys:
            print(f"  Verifying sample of {min(5, len(keys))} items...")
            for i, sample_key in enumerate(keys[:5]):
                result = self.redis.hget(hash_name, sample_key)
                if result:
                    result_data = json.loads(result)
                    if result_data.get('result'):
                        inner_result = json.loads(result_data['result'])
                        if inner_result.get('status') == 'success':
                            print(f"    ✓ Item {sample_key}: {inner_result.get('worker')}")
                        else:
                            print(f"    ✗ Item {sample_key}: FAILED")
                            return False

        # Check for stuck items in processing
        processing = self.redis.hlen('redis:processing:testintegration') or 0

        if processing > 0:
            print(f"  ⚠ Warning: {processing} items stuck in processing")

        # Calculate throughput
        if self.stats['duration_seconds'] > 0:
            throughput = (completed / self.stats['duration_seconds']) * 3600
            print(f"\n  Performance:")
            print(f"    Duration: {self.stats['duration_seconds']}s")
            print(f"    Throughput: {throughput:.0f} items/hour")
            print(f"    Avg time per item: {self.stats['duration_seconds'] / completed:.3f}s")

        return True

    def cleanup_workers(self, workers: List[subprocess.Popen]):
        """Stop all workers."""
        print("\n=== Cleanup Workers ===")

        for proc in workers:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"  ✓ Stopped worker (PID {proc.pid})")

        # Remove temp worker script
        temp_script = script_dir / "test-redis-worker-temp.py"
        if temp_script.exists():
            temp_script.unlink()
            print("  ✓ Removed temp worker script")

    def print_summary(self, success: bool):
        """Print test summary."""
        print("\n" + "="*60)
        print("INTEGRATION TEST SUMMARY")
        print("="*60)
        print(f"Items created: {self.stats['items_created']}")
        print(f"Items migrated: {self.stats['items_migrated']}")
        print(f"Items completed: {self.stats['items_completed']}")
        print(f"Items failed: {self.stats['items_failed']}")
        print(f"Duration: {self.stats['duration_seconds']}s")

        if self.stats['duration_seconds'] > 0 and self.stats['items_completed'] > 0:
            throughput = (self.stats['items_completed'] / self.stats['duration_seconds']) * 3600
            print(f"Throughput: {throughput:.0f} items/hour")

        print("="*60)

        if success:
            print("✓ ALL TESTS PASSED")
        else:
            print("✗ TESTS FAILED")

        print("="*60)

    def run_test(self) -> bool:
        """Run complete integration test."""
        print("="*60)
        print("REDIS QUEUE INTEGRATION TEST")
        print("="*60)
        print(f"Test items: {NUM_TEST_ITEMS}")
        print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
        print(f"PostgreSQL: {PG_HOST}:{PG_PORT}")

        workers = []

        try:
            # Step 0: Cleanup
            self.cleanup_test_data()

            # Step 1: Create test items in PostgreSQL
            item_ids = self.create_test_items_in_pg(NUM_TEST_ITEMS)

            # Step 2: Migrate to Redis
            if not self.migrate_to_redis():
                print("✗ Migration failed")
                return False

            # Step 3: Start workers
            workers = self.start_test_workers(num_workers=4)

            # Step 4: Monitor processing
            if not self.monitor_processing(workers, timeout=60):
                print("✗ Processing timeout")
                return False

            # Step 5: Verify results
            if not self.verify_results():
                print("✗ Verification failed")
                return False

            return True

        finally:
            # Cleanup
            if workers:
                self.cleanup_workers(workers)
            self.cleanup_test_data()

    def close(self):
        """Close connections."""
        self.pg_cursor.close()
        self.pg_conn.close()
        self.redis.close()


def main():
    test = IntegrationTest()

    try:
        success = test.run_test()
        test.print_summary(success)

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        test.close()


if __name__ == '__main__':
    main()
