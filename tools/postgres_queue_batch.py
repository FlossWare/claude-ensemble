#!/usr/bin/env python3
"""
PostgreSQL Queue Batch Operations (Python)

Supports atomic claiming of multiple tasks from PostgreSQL queues.

Features:
- Atomic batch claiming using SELECT FOR UPDATE SKIP LOCKED
- Configurable batch sizes
- Worker affinity (prefer tasks for same worker)
- Priority-aware batching
- Heartbeat updates for batch items
- Batch completion/failure handling

Usage:
    from postgres_queue_batch import PostgresQueueBatch

    queue = PostgresQueueBatch()

    # Claim batch of tasks
    tasks = queue.claim_batch('store', 'worker-01', batch_size=10)

    # Process tasks...

    # Complete batch
    queue.complete_batch('store', [t['id'] for t in tasks])
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json


class PostgresQueueBatch:
    """PostgreSQL queue batch operations handler"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize queue batch handler

        Args:
            config: Database configuration (host, port, database, user, password)
        """
        config = config or {}
        self.config = {
            'host': config.get('host', 'aio-01'),
            'port': config.get('port', 5433),
            'database': config.get('database', 'learning'),
            'user': config.get('user', 'sfloess'),
            'password': config.get('password', ''),
        }
        self.conn = None

    def _get_connection(self):
        """Get or create database connection"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**self.config)
        return self.conn

    def claim_batch(
        self,
        queue_name: str,
        worker_id: str,
        batch_size: int = 10,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Atomically claim a batch of tasks from the queue

        Args:
            queue_name: Queue name (store, chunk, embed, graph)
            worker_id: Worker identifier
            batch_size: Number of tasks to claim (default: 10)
            options: Additional options (priority_min, priority_max, timeout, affinity_weight)

        Returns:
            List of claimed tasks

        Example:
            tasks = queue.claim_batch('store', 'worker-01', 10)
            for task in tasks:
                print(f"Processing task {task['id']}: {task['data']}")
        """
        options = options or {}
        priority_min = options.get('priority_min', 0)
        priority_max = options.get('priority_max', 100)
        timeout = options.get('timeout', 300)  # 5 minutes default
        affinity_weight = options.get('affinity_weight', 0.3)

        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Build query to select tasks atomically
            # Uses SELECT FOR UPDATE SKIP LOCKED for atomic claiming
            query = f"""
                WITH available_tasks AS (
                    SELECT
                        id,
                        data,
                        priority,
                        created_at,
                        retry_count,
                        CASE
                            WHEN last_worker_id = %s THEN priority + (%s * 100)
                            ELSE priority
                        END AS effective_priority
                    FROM queue.{queue_name}
                    WHERE status = 'pending'
                        AND priority BETWEEN %s AND %s
                        AND (scheduled_at IS NULL OR scheduled_at <= NOW())
                        AND retry_count < 3
                    ORDER BY effective_priority DESC, created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE queue.{queue_name} q
                SET
                    status = 'processing',
                    claimed_by = %s,
                    claimed_at = NOW(),
                    last_heartbeat = NOW(),
                    last_worker_id = %s,
                    timeout_at = NOW() + INTERVAL '%s seconds'
                FROM available_tasks at
                WHERE q.id = at.id
                RETURNING q.id, q.data, q.priority, q.created_at, q.retry_count, q.timeout_at
            """

            cursor.execute(query, (
                worker_id,
                affinity_weight,
                priority_min,
                priority_max,
                batch_size,
                worker_id,
                worker_id,
                timeout,
            ))

            tasks = cursor.fetchall()
            conn.commit()

            return [
                {
                    'id': task['id'],
                    'data': task['data'],
                    'priority': task['priority'],
                    'created_at': task['created_at'],
                    'retry_count': task['retry_count'],
                    'timeout_at': task['timeout_at'],
                    'queue_name': queue_name,
                    'worker_id': worker_id,
                }
                for task in tasks
            ]

        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to claim batch from {queue_name}: {str(e)}")
        finally:
            cursor.close()

    def complete_batch(
        self,
        queue_name: str,
        task_ids: List[int],
        results: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Complete a batch of tasks atomically

        Args:
            queue_name: Queue name
            task_ids: List of task IDs to complete
            results: Optional results to store

        Returns:
            Number of tasks completed

        Example:
            completed = queue.complete_batch('store', [1, 2, 3], {'status': 'success'})
            print(f"Completed {completed} tasks")
        """
        if not task_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = f"""
                UPDATE queue.{queue_name}
                SET
                    status = 'completed',
                    completed_at = NOW(),
                    result = %s::jsonb
                WHERE id = ANY(%s)
                    AND status = 'processing'
            """

            cursor.execute(query, (
                json.dumps(results or {}),
                task_ids,
            ))

            count = cursor.rowcount
            conn.commit()
            return count

        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to complete batch in {queue_name}: {str(e)}")
        finally:
            cursor.close()

    def fail_batch(
        self,
        queue_name: str,
        task_ids: List[int],
        error: str,
        retry: bool = True
    ) -> int:
        """
        Fail a batch of tasks atomically

        Args:
            queue_name: Queue name
            task_ids: List of task IDs to fail
            error: Error message
            retry: Whether to retry (default: True)

        Returns:
            Number of tasks failed

        Example:
            failed = queue.fail_batch('store', [1, 2], 'Connection timeout', retry=True)
            print(f"Failed {failed} tasks (will retry)")
        """
        if not task_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = f"""
                UPDATE queue.{queue_name}
                SET
                    status = CASE
                        WHEN retry_count >= 2 OR %s = false THEN 'failed'
                        ELSE 'pending'
                    END,
                    error = %s,
                    retry_count = retry_count + 1,
                    claimed_by = NULL,
                    claimed_at = NULL,
                    last_heartbeat = NULL,
                    scheduled_at = CASE
                        WHEN retry_count >= 2 OR %s = false THEN NULL
                        ELSE NOW() + (INTERVAL '1 minute' * POWER(2, retry_count))
                    END
                WHERE id = ANY(%s)
                    AND status = 'processing'
            """

            cursor.execute(query, (retry, error, retry, task_ids))

            count = cursor.rowcount
            conn.commit()
            return count

        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to fail batch in {queue_name}: {str(e)}")
        finally:
            cursor.close()

    def heartbeat_batch(self, queue_name: str, task_ids: List[int]) -> int:
        """
        Update heartbeat for a batch of tasks

        Args:
            queue_name: Queue name
            task_ids: List of task IDs

        Returns:
            Number of tasks updated

        Example:
            updated = queue.heartbeat_batch('store', [1, 2, 3])
            print(f"Updated heartbeat for {updated} tasks")
        """
        if not task_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = f"""
                UPDATE queue.{queue_name}
                SET last_heartbeat = NOW()
                WHERE id = ANY(%s)
                    AND status = 'processing'
            """

            cursor.execute(query, (task_ids,))

            count = cursor.rowcount
            conn.commit()
            return count

        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to update heartbeat in {queue_name}: {str(e)}")
        finally:
            cursor.close()

    def get_batch_stats(self, queue_name: str) -> Dict[str, Any]:
        """
        Get batch statistics

        Args:
            queue_name: Queue name

        Returns:
            Statistics dictionary

        Example:
            stats = queue.get_batch_stats('store')
            print(f"Pending: {stats['pending']}, Processing: {stats['processing']}")
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            query = f"""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    COUNT(DISTINCT claimed_by) FILTER (WHERE status = 'processing') as active_workers,
                    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) FILTER (WHERE status = 'completed') as avg_completion_time,
                    AVG(retry_count) FILTER (WHERE status = 'completed' OR status = 'failed') as avg_retries
                FROM queue.{queue_name}
            """

            cursor.execute(query)
            return dict(cursor.fetchone())

        finally:
            cursor.close()

    def reclaim_timed_out(self, queue_name: str) -> int:
        """
        Reclaim timed-out tasks

        Args:
            queue_name: Queue name

        Returns:
            Number of tasks reclaimed

        Example:
            reclaimed = queue.reclaim_timed_out('store')
            print(f"Reclaimed {reclaimed} timed-out tasks")
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = f"""
                UPDATE queue.{queue_name}
                SET
                    status = 'pending',
                    claimed_by = NULL,
                    claimed_at = NULL,
                    last_heartbeat = NULL,
                    retry_count = retry_count + 1,
                    scheduled_at = NOW() + (INTERVAL '1 minute' * POWER(2, retry_count))
                WHERE status = 'processing'
                    AND timeout_at < NOW()
                    AND retry_count < 3
            """

            cursor.execute(query)

            count = cursor.rowcount
            conn.commit()
            return count

        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to reclaim timed-out tasks in {queue_name}: {str(e)}")
        finally:
            cursor.close()

    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()


# Singleton instance
_instance = None


def get_queue_batch(config: Optional[Dict[str, Any]] = None) -> PostgresQueueBatch:
    """
    Get the queue batch instance (singleton)

    Args:
        config: Optional configuration

    Returns:
        PostgresQueueBatch instance
    """
    global _instance
    if _instance is None:
        _instance = PostgresQueueBatch(config)
    return _instance


if __name__ == '__main__':
    # Example usage
    queue = get_queue_batch()

    print("Queue Batch Statistics:")
    for queue_name in ['store', 'chunk', 'embed', 'graph']:
        try:
            stats = queue.get_batch_stats(queue_name)
            print(f"\n{queue_name}:")
            print(f"  Pending: {stats.get('pending', 0)}")
            print(f"  Processing: {stats.get('processing', 0)}")
            print(f"  Completed: {stats.get('completed', 0)}")
            print(f"  Failed: {stats.get('failed', 0)}")
            print(f"  Active workers: {stats.get('active_workers', 0)}")
        except Exception as e:
            print(f"  Error: {e}")

    queue.close()
