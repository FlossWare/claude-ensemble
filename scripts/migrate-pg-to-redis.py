#!/usr/bin/env python3
"""
PostgreSQL to Redis Queue Migration Script (HYBRID Architecture)

Safely migrates 3,026 pending items from PostgreSQL queue.store to Redis queues
with full verification and rollback capability.

HYBRID ARCHITECTURE:
- Initial queues (store:high/medium/low): ZADD with priority scores (sorted sets)
  - Supports priority-based ordering with FIFO within priority
  - Uses ZPOPMIN to claim tasks (lowest score = highest priority + oldest timestamp)
- Processing pipeline (chunk, embed, index): LPUSH (lists, simple FIFO)
  - No priority needed after initial stage
  - Uses RPOP/BLPOP for simple worker claiming

This migration populates the INITIAL queues (sorted sets with ZADD).
Subsequent stages are populated by workers via LPUSH (see redis-atomic-operations.py).

Usage:
    python3 scripts/migrate-pg-to-redis.py --dry-run    # Preview only
    python3 scripts/migrate-pg-to-redis.py              # Execute migration
    python3 scripts/migrate-pg-to-redis.py --verify     # Verify only
"""

import psycopg2
import redis
import json
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Tuple

class QueueMigrator:
    def __init__(self, pg_host='aio-01', pg_port=5433, pg_user='sfloess',
                 pg_db='learning', redis_host='aio-01', redis_port=6379):
        self.pg_conn = psycopg2.connect(
            host=pg_host, port=pg_port, user=pg_user, database=pg_db
        )
        self.pg_cursor = self.pg_conn.cursor()
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        self.stats = {
            'total_pending': 0,
            'migrated': 0,
            'skipped': 0,
            'errors': 0,
            'high_priority': 0,
            'medium_priority': 0,
            'low_priority': 0
        }

    def check_prerequisites(self) -> bool:
        """Verify PostgreSQL and Redis are accessible and ready."""
        print("Checking prerequisites...")

        # Check PostgreSQL
        try:
            self.pg_cursor.execute("SELECT 1")
            print("✓ PostgreSQL connection OK")
        except Exception as e:
            print(f"✗ PostgreSQL connection failed: {e}")
            return False

        # Check Redis
        try:
            self.redis.ping()
            print("✓ Redis connection OK")
        except Exception as e:
            print(f"✗ Redis connection failed: {e}")
            return False

        # Check for existing Redis queues (warn if not empty)
        # Using ZCARD for sorted sets instead of LLEN for lists
        existing_counts = {
            'high': self.redis.zcard('redis:queue:store:high'),
            'medium': self.redis.zcard('redis:queue:store:medium'),
            'low': self.redis.zcard('redis:queue:store:low')
        }

        total_existing = sum(existing_counts.values())
        if total_existing > 0:
            print(f"⚠ Warning: Redis queues not empty ({total_existing} items)")
            print(f"  - high: {existing_counts['high']}")
            print(f"  - medium: {existing_counts['medium']}")
            print(f"  - low: {existing_counts['low']}")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                return False
        else:
            print("✓ Redis queues are empty")

        # Count pending items in PostgreSQL
        self.pg_cursor.execute("SELECT COUNT(*) FROM queue.store WHERE status = 'pending'")
        self.stats['total_pending'] = self.pg_cursor.fetchone()[0]
        print(f"✓ Found {self.stats['total_pending']} pending items in PostgreSQL")

        # Check memory
        redis_info = self.redis.info('memory')
        used_memory_mb = redis_info['used_memory'] / 1024 / 1024
        max_memory_mb = redis_info.get('maxmemory', 0) / 1024 / 1024

        estimated_needed_mb = (self.stats['total_pending'] * 2048) / 1024 / 1024  # 2KB per item

        print(f"✓ Redis memory: {used_memory_mb:.1f} MB used")
        print(f"  Estimated needed: {estimated_needed_mb:.1f} MB")

        if max_memory_mb > 0 and (used_memory_mb + estimated_needed_mb) > (max_memory_mb * 0.8):
            print(f"✗ Insufficient Redis memory (would exceed 80% of {max_memory_mb:.1f} MB)")
            return False

        return True

    def get_priority_queue(self, priority: int) -> str:
        """Determine Redis queue name based on priority."""
        if priority >= 8:
            return 'redis:queue:store:high'
        elif priority >= 4:
            return 'redis:queue:store:medium'
        else:
            return 'redis:queue:store:low'

    def calculate_priority_score(self, priority: int, timestamp_ms: int) -> float:
        """
        Calculate priority score for ZSET ordering.

        Formula: (10 - priority) * 1e13 + timestamp_ms

        This ensures:
        - Priority 10 @ t=1000: 0 * 1e13 + 1000 = 1000 (LOWEST score, pops FIRST)
        - Priority 10 @ t=2000: 0 * 1e13 + 2000 = 2000 (pops SECOND - FIFO ✓)
        - Priority 9 @ t=1000:  1 * 1e13 + 1000 = 10000000000001000 (higher score, pops AFTER priority 10)
        - Priority 1 @ t=1000:  9 * 1e13 + 1000 = 90000000000001000 (highest score, pops LAST)

        ZPOPMIN pops LOWEST score first:
        1. Higher priority = LOWER base score (10 - priority) → processes first
        2. Within same priority: older timestamp (smaller) = lower score → processes first (FIFO ✓)

        Example timeline (all priority 10):
        - Task A @ t=1000 → score = 0 + 1000 = 1000 (LOWEST, pops FIRST)
        - Task B @ t=2000 → score = 0 + 2000 = 2000 (pops SECOND)
        - Task C @ t=3000 → score = 0 + 3000 = 3000 (pops THIRD)

        FIX BUG #1: Priority inversion - inverted formula to ensure high priority = low score.
        """
        return (10 - priority) * 1e13 + timestamp_ms

    def migrate_batch(self, batch_size: int = 1000, offset: int = 0, dry_run: bool = False) -> int:
        """Migrate a batch of items from PostgreSQL to Redis."""
        self.pg_cursor.execute("""
            SELECT id, data, priority, status, retries, error,
                   created_at, started_at, completed_at,
                   document_id, file_path, idempotency_key, worker_id
            FROM queue.store
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT %s OFFSET %s
        """, (batch_size, offset))

        rows = self.pg_cursor.fetchall()
        if not rows:
            return 0

        if dry_run:
            print(f"[DRY RUN] Would migrate {len(rows)} items (offset {offset})")
            for row in rows[:3]:  # Show first 3
                priority = row[2]
                queue = self.get_priority_queue(priority)
                print(f"  - ID {row[0]}, priority {priority} → {queue}")
            if len(rows) > 3:
                print(f"  ... and {len(rows) - 3} more")
            return len(rows)

        # Migrate to Redis
        pipeline = self.redis.pipeline()
        migrated_ids = []

        for row in rows:
            pg_id, data, priority, status, retries, error = row[0:6]
            created_at, started_at, completed_at = row[6:9]
            document_id, file_path, idempotency_key, worker_id = row[9:13]

            # Build Redis item
            item = {
                'id': pg_id,
                'pg_id': pg_id,
                'data': data,  # Already JSON
                'priority': priority,
                'retries': retries or 0,
                'created_at': created_at.isoformat() if created_at else None,
                'document_id': str(document_id) if document_id else None,
                'file_path': file_path,
                'idempotency_key': idempotency_key,
                'worker_id': worker_id,
                'migration_timestamp': datetime.utcnow().isoformat(),
                'source': 'postgresql_migration'
            }

            # Determine queue
            queue_name = self.get_priority_queue(priority)

            # Calculate priority score for ZSET (fixes priority inversion bug)
            timestamp_ms = int(created_at.timestamp() * 1000) if created_at else int(datetime.utcnow().timestamp() * 1000)
            score = self.calculate_priority_score(priority, timestamp_ms)

            # HYBRID ARCHITECTURE: ZADD for initial queues (sorted sets with priority)
            # - ZADD: Adds to sorted set with score (priority-based ordering)
            # - ZPOPMIN pops LOWEST score first → high priority = LOW score
            # - Formula: (10 - priority) * 1e13 + timestamp_ms
            #   - Priority 10: score ≈ 0 + timestamp (pops FIRST)
            #   - Priority 1: score ≈ 9e13 + timestamp (pops LAST)
            # - Next stages use LPUSH (lists) populated by complete_task in redis-atomic-operations.py
            pipeline.zadd(queue_name, {json.dumps(item): score})

            # Track idempotency
            if idempotency_key:
                pipeline.hset('redis:idempotency:store', idempotency_key, pg_id)

            migrated_ids.append(pg_id)

            # Update stats
            if priority >= 8:
                self.stats['high_priority'] += 1
            elif priority >= 4:
                self.stats['medium_priority'] += 1
            else:
                self.stats['low_priority'] += 1

        # Execute pipeline
        try:
            pipeline.execute()
            self.stats['migrated'] += len(rows)
            return len(rows)
        except Exception as e:
            print(f"✗ Error migrating batch: {e}")
            self.stats['errors'] += len(rows)
            return 0

    def migrate_all(self, batch_size: int = 1000, dry_run: bool = False) -> bool:
        """Migrate all pending items in batches."""
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Starting migration...")
        print(f"Batch size: {batch_size}")

        offset = 0
        batch_num = 1

        while True:
            print(f"\nBatch {batch_num} (offset {offset})...")
            migrated = self.migrate_batch(batch_size, offset, dry_run)

            if migrated == 0:
                break

            print(f"  Migrated: {migrated} items")
            print(f"  Total progress: {self.stats['migrated']}/{self.stats['total_pending']} " +
                  f"({100 * self.stats['migrated'] / self.stats['total_pending']:.1f}%)")

            offset += batch_size
            batch_num += 1

        return True

    def verify_migration(self) -> Tuple[bool, Dict]:
        """Verify migration completeness and correctness."""
        print("\nVerifying migration...")

        # Count PostgreSQL pending items
        self.pg_cursor.execute("SELECT COUNT(*) FROM queue.store WHERE status = 'pending'")
        pg_pending = self.pg_cursor.fetchone()[0]

        # Count Redis queue items (using ZCARD for sorted sets)
        redis_high = self.redis.zcard('redis:queue:store:high')
        redis_medium = self.redis.zcard('redis:queue:store:medium')
        redis_low = self.redis.zcard('redis:queue:store:low')
        redis_total = redis_high + redis_medium + redis_low

        verification = {
            'pg_pending': pg_pending,
            'redis_total': redis_total,
            'redis_high': redis_high,
            'redis_medium': redis_medium,
            'redis_low': redis_low,
            'counts_match': pg_pending == redis_total,
            'sample_verified': False,
            'idempotency_verified': False
        }

        print(f"PostgreSQL pending: {pg_pending}")
        print(f"Redis total: {redis_total}")
        print(f"  - high: {redis_high}")
        print(f"  - medium: {redis_medium}")
        print(f"  - low: {redis_low}")

        if verification['counts_match']:
            print("✓ Counts match!")
        else:
            print(f"✗ COUNT MISMATCH: {abs(pg_pending - redis_total)} items difference")
            return False, verification

        # Sample verification (10 random items)
        print("\nVerifying sample items...")
        self.pg_cursor.execute("""
            SELECT id, data, priority FROM queue.store
            WHERE status = 'pending'
            ORDER BY RANDOM() LIMIT 10
        """)

        pg_samples = {row[0]: (row[1], row[2]) for row in self.pg_cursor.fetchall()}
        verified_count = 0

        for pg_id, (pg_data, pg_priority) in pg_samples.items():
            queue = self.get_priority_queue(pg_priority)

            # Get all items from the sorted set (ZRANGE with scores)
            items_with_scores = self.redis.zrange(queue, 0, -1, withscores=False)
            items = [json.loads(item) for item in items_with_scores]

            found = False
            for item in items:
                if item.get('pg_id') == pg_id:
                    found = True
                    # Verify data matches
                    if item['data'] == pg_data and item['priority'] == pg_priority:
                        verified_count += 1
                        print(f"  ✓ Item {pg_id} verified")
                    else:
                        print(f"  ✗ Item {pg_id} DATA MISMATCH")
                    break

            if not found:
                print(f"  ✗ Item {pg_id} NOT FOUND in Redis")

        verification['sample_verified'] = verified_count == len(pg_samples)

        # Verify idempotency keys
        print("\nVerifying idempotency keys...")
        self.pg_cursor.execute("""
            SELECT idempotency_key, id FROM queue.store
            WHERE status = 'pending' AND idempotency_key IS NOT NULL
            LIMIT 10
        """)

        idempotency_samples = {row[0]: row[1] for row in self.pg_cursor.fetchall()}
        idempotency_verified = 0

        for key, pg_id in idempotency_samples.items():
            redis_id = self.redis.hget('redis:idempotency:store', key)
            if redis_id and int(redis_id) == pg_id:
                idempotency_verified += 1
                print(f"  ✓ Idempotency key {key[:20]}... → {pg_id}")
            else:
                print(f"  ✗ Idempotency key {key[:20]}... MISMATCH (PG: {pg_id}, Redis: {redis_id})")

        verification['idempotency_verified'] = (
            idempotency_verified == len(idempotency_samples) if idempotency_samples else True
        )

        # Overall success
        success = (
            verification['counts_match'] and
            verification['sample_verified'] and
            verification['idempotency_verified']
        )

        return success, verification

    def mark_migrated(self, dry_run: bool = False) -> int:
        """Mark PostgreSQL items as migrated."""
        if dry_run:
            print("[DRY RUN] Would mark items as migrated in PostgreSQL")
            return self.stats['total_pending']

        print("\nMarking PostgreSQL items as migrated...")

        # Add columns if not exist
        try:
            self.pg_cursor.execute("""
                ALTER TABLE queue.store
                ADD COLUMN IF NOT EXISTS migrated_to_redis BOOLEAN DEFAULT FALSE
            """)
            self.pg_cursor.execute("""
                ALTER TABLE queue.store
                ADD COLUMN IF NOT EXISTS migrated_at TIMESTAMP
            """)
            self.pg_conn.commit()
        except Exception as e:
            print(f"Note: Column already exists or error: {e}")
            self.pg_conn.rollback()

        # Mark items
        self.pg_cursor.execute("""
            UPDATE queue.store
            SET migrated_to_redis = TRUE,
                migrated_at = NOW(),
                status = 'migrated'
            WHERE status = 'pending'
            RETURNING id
        """)

        updated_ids = [row[0] for row in self.pg_cursor.fetchall()]
        self.pg_conn.commit()

        print(f"✓ Marked {len(updated_ids)} items as migrated")
        return len(updated_ids)

    def rollback_migration(self) -> int:
        """
        Rollback migration by clearing Redis queues.

        WARNING: Only call this if verification fails and PostgreSQL items
        have NOT been marked as migrated yet.

        Returns:
            Number of items removed from Redis
        """
        print("\n⚠ ROLLING BACK MIGRATION...")

        removed = 0

        # Clear all Redis queues
        queues = [
            'redis:queue:store:high',
            'redis:queue:store:medium',
            'redis:queue:store:low'
        ]

        for queue in queues:
            count = self.redis.zcard(queue)
            if count > 0:
                self.redis.delete(queue)
                removed += count
                print(f"  Removed {count} items from {queue}")

        # Clear idempotency hash
        idem_count = self.redis.hlen('redis:idempotency:store')
        if idem_count > 0:
            self.redis.delete('redis:idempotency:store')
            print(f"  Removed {idem_count} idempotency keys")

        # Clear any processing/completed hashes
        for hash_name in ['redis:processing:store', 'redis:processing:store:metadata',
                          'redis:completed:store', 'redis:heartbeat:store']:
            if self.redis.exists(hash_name):
                self.redis.delete(hash_name)
                print(f"  Cleared {hash_name}")

        print(f"\n✓ Rollback complete: {removed} items removed from Redis")
        print("PostgreSQL data is intact and unchanged")

        return removed

    def print_summary(self):
        """Print migration summary."""
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Total pending in PostgreSQL: {self.stats['total_pending']}")
        print(f"Migrated to Redis: {self.stats['migrated']}")
        print(f"  - High priority: {self.stats['high_priority']}")
        print(f"  - Medium priority: {self.stats['medium_priority']}")
        print(f"  - Low priority: {self.stats['low_priority']}")
        print(f"Skipped: {self.stats['skipped']}")
        print(f"Errors: {self.stats['errors']}")
        print("="*60)

    def close(self):
        """Close connections."""
        self.pg_cursor.close()
        self.pg_conn.close()
        self.redis.close()

def main():
    parser = argparse.ArgumentParser(
        description='Migrate PostgreSQL queue.store to Redis queues'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview migration without executing')
    parser.add_argument('--verify', action='store_true',
                       help='Verify existing migration only')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Number of items per batch (default: 1000)')
    parser.add_argument('--skip-mark', action='store_true',
                       help='Skip marking PostgreSQL items as migrated')

    args = parser.parse_args()

    migrator = QueueMigrator()

    try:
        # Check prerequisites
        if not migrator.check_prerequisites():
            print("\n✗ Prerequisites check failed. Aborting.")
            sys.exit(1)

        if args.verify:
            # Verify only
            success, verification = migrator.verify_migration()
            if success:
                print("\n✓ Verification PASSED")
                sys.exit(0)
            else:
                print("\n✗ Verification FAILED")
                sys.exit(1)

        # Confirm if not dry-run
        if not args.dry_run:
            print("\n" + "="*60)
            print("WARNING: This will migrate data to Redis")
            print("="*60)
            response = input("Continue with migration? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                sys.exit(0)

        # Migrate
        success = migrator.migrate_all(args.batch_size, args.dry_run)

        if not success:
            print("\n✗ Migration failed")
            sys.exit(1)

        migrator.print_summary()

        if not args.dry_run:
            # Verify
            print("\nRunning verification...")
            success, verification = migrator.verify_migration()

            if not success:
                print("\n✗ Verification failed.")
                print("\n" + "="*60)
                print("AUTOMATIC ROLLBACK (FIX BUG #5)")
                print("="*60)

                # Rollback migration
                migrator.rollback_migration()

                print("\n✗ Migration aborted. PostgreSQL data is intact.")
                print("Fix issues and re-run migration.")
                sys.exit(1)

            # Mark as migrated
            if not args.skip_mark:
                migrator.mark_migrated(args.dry_run)

            print("\n✓ Migration completed successfully!")
        else:
            print("\n[DRY RUN] No changes made")

    except KeyboardInterrupt:
        print("\n\n✗ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        migrator.close()

if __name__ == '__main__':
    main()
