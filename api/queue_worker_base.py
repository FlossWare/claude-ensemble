#!/usr/bin/env python3
"""
Base class for queue workers with idempotency checking

All workers inherit from this to get:
- Idempotency key checking before processing
- Automatic status updates (started_at, completed_at)
- Error handling and retry logic
- Worker heartbeat registration
"""

import os
import sys
import time
import json
import psycopg2
import psycopg2.extras
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class QueueWorkerBase:
    """Base class for all queue workers with idempotency"""

    def __init__(self, queue_name: str, worker_id: str):
        """
        Initialize worker

        Args:
            queue_name: Name of queue table (e.g., 'store', 'chunk', 'embed', 'graph')
            worker_id: Unique worker identifier (e.g., 'store-worker-server-01')
        """
        self.queue_name = queue_name
        self.worker_id = worker_id
        self.logger = logging.getLogger(f'{queue_name}-worker')

        # Database connection
        self.conn = None
        self._connect_db()

    def _connect_db(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=os.environ.get('POSTGRES_HOST', 'aio-01'),
                port=int(os.environ.get('POSTGRES_PORT', 5433)),
                user=os.environ.get('POSTGRES_USER', 'sfloess'),
                password=os.environ.get('POSTGRES_PASSWORD', ''),
                database='learning',
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            self.logger.info(f"Connected to PostgreSQL (queue.{self.queue_name})")
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise

    def _register_heartbeat(self):
        """Register/update worker heartbeat"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO queue.worker_heartbeat (worker_id, queue_name, last_seen)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (worker_id) DO UPDATE SET
                        last_seen = NOW(),
                        queue_name = EXCLUDED.queue_name
                """, (self.worker_id, self.queue_name))
                self.conn.commit()
        except Exception as e:
            self.logger.warning(f"Heartbeat registration failed: {e}")

    def fetch_task(self, timeout_seconds: int = 30) -> Optional[Dict[str, Any]]:
        """
        Fetch next pending task with idempotency check

        Returns None if no tasks available or all tasks already processed
        """
        try:
            with self.conn.cursor() as cursor:
                # CRITICAL: Check idempotency BEFORE claiming task
                cursor.execute(f"""
                    WITH next_task AS (
                        SELECT id, data, idempotency_key, file_path
                        FROM queue.{self.queue_name}
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    SELECT *
                    FROM next_task
                    WHERE NOT EXISTS (
                        -- Skip if already completed with this idempotency key
                        SELECT 1
                        FROM queue.{self.queue_name}
                        WHERE idempotency_key = next_task.idempotency_key
                          AND idempotency_key IS NOT NULL
                          AND status = 'completed'
                    )
                """)

                task = cursor.fetchone()

                if not task:
                    return None

                # Claim the task
                cursor.execute(f"""
                    UPDATE queue.{self.queue_name}
                    SET status = 'processing',
                        started_at = NOW(),
                        worker_id = %s
                    WHERE id = %s
                """, (self.worker_id, task['id']))

                self.conn.commit()

                self.logger.info(
                    f"Claimed task {task['id']} "
                    f"(idempotency_key: {task.get('idempotency_key', 'none')})"
                )

                return dict(task)

        except Exception as e:
            self.logger.error(f"Error fetching task: {e}")
            self.conn.rollback()
            return None

    def complete_task(self, task_id: int, result: Optional[Dict] = None):
        """Mark task as completed"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"""
                    UPDATE queue.{self.queue_name}
                    SET status = 'completed',
                        completed_at = NOW(),
                        error = NULL
                    WHERE id = %s
                """, (task_id,))
                self.conn.commit()

                self.logger.info(f"Completed task {task_id}")

        except Exception as e:
            self.logger.error(f"Error completing task {task_id}: {e}")
            self.conn.rollback()

    def fail_task(self, task_id: int, error: str, max_retries: int = 3):
        """Mark task as failed and optionally retry"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"""
                    UPDATE queue.{self.queue_name}
                    SET retries = retries + 1,
                        error = %s,
                        status = CASE
                            WHEN retries + 1 >= %s THEN 'failed'
                            ELSE 'pending'
                        END,
                        started_at = NULL,
                        worker_id = NULL
                    WHERE id = %s
                """, (error, max_retries, task_id))
                self.conn.commit()

                self.logger.warning(f"Failed task {task_id}: {error}")

        except Exception as e:
            self.logger.error(f"Error failing task {task_id}: {e}")
            self.conn.rollback()

    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Override this method in subclasses to implement task processing

        Returns:
            True if successful, False if failed
        """
        raise NotImplementedError("Subclasses must implement process_task()")

    def run_forever(self, poll_interval: int = 5):
        """
        Main worker loop - polls queue and processes tasks

        Args:
            poll_interval: Seconds to wait between polls when queue is empty
        """
        self.logger.info(f"Starting {self.worker_id} (queue: {self.queue_name})")

        # Initial heartbeat
        self._register_heartbeat()
        last_heartbeat = time.time()

        while True:
            try:
                # Update heartbeat every 30 seconds
                if time.time() - last_heartbeat > 30:
                    self._register_heartbeat()
                    last_heartbeat = time.time()

                # Fetch next task
                task = self.fetch_task()

                if not task:
                    # No tasks available, wait before polling again
                    time.sleep(poll_interval)
                    continue

                # Process the task
                task_id = task['id']
                try:
                    success = self.process_task(task)

                    if success:
                        self.complete_task(task_id)
                    else:
                        self.fail_task(task_id, "Processing returned False")

                except Exception as e:
                    error_msg = f"Exception during processing: {str(e)}"
                    self.logger.error(error_msg)
                    self.fail_task(task_id, error_msg)

            except KeyboardInterrupt:
                self.logger.info("Shutting down gracefully...")
                break

            except Exception as e:
                self.logger.error(f"Worker loop error: {e}")
                time.sleep(poll_interval)

        # Cleanup
        if self.conn:
            self.conn.close()

        self.logger.info("Worker stopped")
