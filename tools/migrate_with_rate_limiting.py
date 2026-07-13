#!/usr/bin/env python3
"""
Migration script with rate limiting integration.
Checks rate limits before queueing documents to prevent overwhelming the system.

Architecture:
  1. Query PostgreSQL for unprocessed documents
  2. Check Redis rate limits before queueing
  3. Queue to Redis only if under limit
  4. Track migration progress in PostgreSQL
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import redis
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
REDIS_HOST = "aio-01"
REDIS_PORT = 6379
POSTGRES_HOST = "aio-01"
POSTGRES_PORT = 5433
POSTGRES_DB = "learning"
POSTGRES_USER = "sfloess"

# Rate limiting configuration
DEFAULT_RATE_LIMIT = 100  # documents per minute
DEFAULT_BURST_LIMIT = 200  # max queue size
RATE_LIMIT_WINDOW = 60  # seconds

# Queue names
STORE_QUEUE = "queue:store"
CHUNK_QUEUE = "queue:chunk"
EMBED_QUEUE = "queue:embed"
GRAPH_QUEUE = "queue:graph"

# Rate limit keys
RATE_LIMIT_KEY_PREFIX = "rate_limit:"
QUEUE_SIZE_KEY_PREFIX = "queue_size:"


class RateLimiter:
    """Token bucket rate limiter using Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def check_rate_limit(
        self,
        queue_name: str,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window: int = RATE_LIMIT_WINDOW
    ) -> Tuple[bool, int]:
        """
        Check if we can queue more items without exceeding rate limit.

        Returns:
            (allowed: bool, remaining: int)
        """
        key = f"{RATE_LIMIT_KEY_PREFIX}{queue_name}"
        current_time = int(time.time())
        window_start = current_time - window

        # Remove old entries outside window
        self.redis.zremrangebyscore(key, 0, window_start)

        # Count entries in current window
        current_count = self.redis.zcard(key)

        if current_count >= rate_limit:
            return False, 0

        remaining = rate_limit - current_count
        return True, remaining

    def record_queued(self, queue_name: str):
        """Record that an item was queued."""
        key = f"{RATE_LIMIT_KEY_PREFIX}{queue_name}"
        current_time = time.time()

        # Add timestamp to sorted set
        self.redis.zadd(key, {str(current_time): current_time})

        # Set expiration to clean up old data
        self.redis.expire(key, RATE_LIMIT_WINDOW * 2)

    def check_queue_size(
        self,
        queue_name: str,
        max_size: int = DEFAULT_BURST_LIMIT
    ) -> Tuple[bool, int]:
        """
        Check if queue size is under limit.

        Returns:
            (allowed: bool, current_size: int)
        """
        current_size = self.redis.llen(queue_name)
        allowed = current_size < max_size
        return allowed, current_size

    def wait_for_capacity(
        self,
        queue_name: str,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        max_size: int = DEFAULT_BURST_LIMIT,
        timeout: int = 300
    ) -> bool:
        """
        Wait for rate limit and queue size to have capacity.

        Returns:
            True if capacity available, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check both rate limit and queue size
            rate_allowed, rate_remaining = self.check_rate_limit(queue_name, rate_limit)
            size_allowed, current_size = self.check_queue_size(queue_name, max_size)

            if rate_allowed and size_allowed:
                return True

            # Calculate wait time
            if not rate_allowed:
                # Wait for rate limit window
                wait_time = min(5, RATE_LIMIT_WINDOW / 10)
            else:
                # Wait for queue to drain
                wait_time = min(10, max_size / (rate_limit / 60))

            print(f"Waiting {wait_time:.1f}s - Rate: {rate_remaining} remaining, Queue: {current_size}/{max_size}")
            time.sleep(wait_time)

        return False


class MigrationManager:
    """Manages migration of documents from PostgreSQL to Redis queues."""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
        self.rate_limiter = RateLimiter(self.redis_client)
        self.pg_conn = None

    def connect_postgres(self):
        """Connect to PostgreSQL database."""
        self.pg_conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER
        )

    def get_unprocessed_documents(
        self,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict]:
        """
        Query PostgreSQL for documents that need processing.

        Returns documents that:
        - Exist in raw storage
        - Haven't been queued for processing
        - Haven't been processed yet
        """
        query = """
        SELECT
            url,
            category,
            title,
            content,
            metadata,
            created_at
        FROM web_content.raw_documents
        WHERE
            processed = false
            AND queued_at IS NULL
        ORDER BY created_at ASC
        LIMIT %s OFFSET %s
        """

        with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (limit, offset))
            return cursor.fetchall()

    def mark_as_queued(self, url: str):
        """Mark document as queued in PostgreSQL."""
        query = """
        UPDATE web_content.raw_documents
        SET
            queued_at = NOW(),
            queue_name = %s
        WHERE url = %s
        """

        with self.pg_conn.cursor() as cursor:
            cursor.execute(query, (STORE_QUEUE, url))
            self.pg_conn.commit()

    def queue_document(
        self,
        document: Dict,
        queue_name: str = STORE_QUEUE
    ) -> bool:
        """
        Queue a document to Redis, respecting rate limits.

        Returns:
            True if queued, False if rate limited
        """
        # Check rate limit first
        rate_allowed, rate_remaining = self.rate_limiter.check_rate_limit(queue_name)
        if not rate_allowed:
            print(f"Rate limit exceeded for {queue_name}, waiting...")
            if not self.rate_limiter.wait_for_capacity(queue_name):
                print(f"Timeout waiting for capacity on {queue_name}")
                return False

        # Check queue size
        size_allowed, current_size = self.rate_limiter.check_queue_size(queue_name)
        if not size_allowed:
            print(f"Queue size limit exceeded for {queue_name} ({current_size} items), waiting...")
            if not self.rate_limiter.wait_for_capacity(queue_name):
                print(f"Timeout waiting for queue space on {queue_name}")
                return False

        # Generate hash for deduplication
        url_hash = hashlib.md5(document['url'].encode()).hexdigest()

        # Prepare queue payload
        payload = {
            'url': document['url'],
            'category': document['category'],
            'title': document.get('title'),
            'content': document['content'],
            'metadata': document.get('metadata', {}),
            'hash': url_hash,
            'queued_at': datetime.now().isoformat()
        }

        # Push to Redis queue
        self.redis_client.rpush(queue_name, json.dumps(payload))

        # Record in rate limiter
        self.rate_limiter.record_queued(queue_name)

        # Mark as queued in PostgreSQL
        self.mark_as_queued(document['url'])

        return True

    def migrate_batch(
        self,
        batch_size: int = 100,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        max_queue_size: int = DEFAULT_BURST_LIMIT
    ) -> Tuple[int, int]:
        """
        Migrate a batch of documents to Redis queue.

        Returns:
            (queued_count, skipped_count)
        """
        documents = self.get_unprocessed_documents(limit=batch_size)

        if not documents:
            print("No unprocessed documents found")
            return 0, 0

        queued = 0
        skipped = 0

        for doc in documents:
            if self.queue_document(doc, STORE_QUEUE):
                queued += 1
                print(f"Queued: {doc['url']} ({doc['category']})")
            else:
                skipped += 1
                print(f"Skipped: {doc['url']} (rate limited)")

        return queued, skipped

    def migrate_all(
        self,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        max_queue_size: int = DEFAULT_BURST_LIMIT,
        batch_size: int = 100
    ):
        """
        Migrate all unprocessed documents to Redis queue.
        """
        self.connect_postgres()

        total_queued = 0
        total_skipped = 0
        offset = 0

        print(f"Starting migration with rate limit: {rate_limit}/min, max queue: {max_queue_size}")

        while True:
            print(f"\n--- Batch starting at offset {offset} ---")

            queued, skipped = self.migrate_batch(
                batch_size=batch_size,
                rate_limit=rate_limit,
                max_queue_size=max_queue_size
            )

            total_queued += queued
            total_skipped += skipped

            print(f"Batch complete: {queued} queued, {skipped} skipped")

            if queued == 0:
                # No more documents to migrate
                break

            offset += batch_size

        print(f"\n=== Migration Complete ===")
        print(f"Total queued: {total_queued}")
        print(f"Total skipped: {total_skipped}")

        # Show final queue stats
        self.show_queue_stats()

    def show_queue_stats(self):
        """Display current queue statistics."""
        print("\n=== Queue Statistics ===")

        for queue_name in [STORE_QUEUE, CHUNK_QUEUE, EMBED_QUEUE, GRAPH_QUEUE]:
            size = self.redis_client.llen(queue_name)
            rate_allowed, rate_remaining = self.rate_limiter.check_rate_limit(queue_name)

            print(f"{queue_name}:")
            print(f"  Size: {size}")
            print(f"  Rate remaining: {rate_remaining}/{DEFAULT_RATE_LIMIT}")

    def close(self):
        """Clean up connections."""
        if self.pg_conn:
            self.pg_conn.close()
        self.redis_client.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate documents to Redis queue with rate limiting")
    parser.add_argument('--batch-size', type=int, default=100, help="Batch size for migration")
    parser.add_argument('--rate-limit', type=int, default=DEFAULT_RATE_LIMIT, help="Rate limit (docs/min)")
    parser.add_argument('--max-queue', type=int, default=DEFAULT_BURST_LIMIT, help="Max queue size")
    parser.add_argument('--stats-only', action='store_true', help="Show stats without migrating")

    args = parser.parse_args()

    manager = MigrationManager()

    try:
        if args.stats_only:
            manager.show_queue_stats()
        else:
            manager.migrate_all(
                rate_limit=args.rate_limit,
                max_queue_size=args.max_queue,
                batch_size=args.batch_size
            )
    finally:
        manager.close()


if __name__ == '__main__':
    main()
