#!/usr/bin/env python3
"""
Priority Task Queue System - PostgreSQL-based distributed task queue
Supports priority levels 1-10, worker claiming, and completion tracking
"""

import psycopg2
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

class TaskQueue:
    def __init__(self, host="aio-01", port=5433, database="learning", user="claude"):
        """Initialize connection to PostgreSQL"""
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create task queue tables and functions"""
        cursor = self.conn.cursor()

        # Create queue schema
        cursor.execute("CREATE SCHEMA IF NOT EXISTS queue")

        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue.tasks (
                id SERIAL PRIMARY KEY,
                priority INT NOT NULL CHECK (priority BETWEEN 1 AND 10),
                task_type VARCHAR(255) NOT NULL,
                payload JSONB NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                worker_id VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                claimed_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT,
                retry_count INT DEFAULT 0
            )
        """)

        # Create index for efficient claiming
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_claim
            ON queue.tasks (status, priority DESC, created_at ASC)
            WHERE status = 'pending'
        """)

        # Function to claim next task
        cursor.execute("""
            CREATE OR REPLACE FUNCTION queue.claim_next_task(p_worker_id VARCHAR)
            RETURNS TABLE (
                id INT,
                priority INT,
                task_type VARCHAR,
                payload JSONB,
                created_at TIMESTAMP WITH TIME ZONE
            ) AS $$
            BEGIN
                RETURN QUERY
                WITH claimed AS (
                    UPDATE queue.tasks
                    SET status = 'in_progress',
                        worker_id = p_worker_id,
                        claimed_at = NOW()
                    WHERE id IN (
                        SELECT t.id
                        FROM queue.tasks t
                        WHERE t.status = 'pending'
                        ORDER BY t.priority DESC, t.created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING *
                )
                SELECT c.id, c.priority, c.task_type, c.payload, c.created_at
                FROM claimed c;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Function to add task
        cursor.execute("""
            CREATE OR REPLACE FUNCTION queue.add_task(
                p_priority INT,
                p_type VARCHAR,
                p_payload JSONB
            ) RETURNS INT AS $$
            DECLARE
                task_id INT;
            BEGIN
                INSERT INTO queue.tasks (priority, task_type, payload)
                VALUES (p_priority, p_type, p_payload)
                RETURNING id INTO task_id;
                RETURN task_id;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Function to complete task
        cursor.execute("""
            CREATE OR REPLACE FUNCTION queue.complete_task(
                p_task_id INT,
                p_error TEXT DEFAULT NULL
            ) RETURNS VOID AS $$
            BEGIN
                IF p_error IS NULL THEN
                    UPDATE queue.tasks
                    SET status = 'completed',
                        completed_at = NOW()
                    WHERE id = p_task_id;
                ELSE
                    UPDATE queue.tasks
                    SET status = 'failed',
                        completed_at = NOW(),
                        error_message = p_error
                    WHERE id = p_task_id;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
        """)

        self.conn.commit()
        cursor.close()

    def add_task(self, priority: int, task_type: str, payload: Dict[str, Any]) -> int:
        """
        Add a new task to the queue with error handling

        Args:
            priority: Priority level 1-10 (10 is highest)
            task_type: Type of task (e.g., 'process_file', 'generate_embeddings')
            payload: Task data as dictionary

        Returns:
            Task ID
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT queue.add_task(%s, %s, %s)",
                    (priority, task_type, json.dumps(payload))
                )
                task_id = cursor.fetchone()[0]
                self.conn.commit()
                cursor.close()
                return task_id
            except Exception as e:
                self.conn.rollback()
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise Exception(f"Failed to add task after {max_retries} attempts: {e}")

    def claim_next_task(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Claim the next highest priority task with auto-release of stuck tasks

        Args:
            worker_id: Identifier for the worker claiming the task

        Returns:
            Task dict with id, priority, task_type, payload, created_at or None
        """
        try:
            cursor = self.conn.cursor()

            # First, auto-release stuck tasks (in_progress for > 1 hour)
            cursor.execute("""
                UPDATE queue.tasks
                SET status = 'pending', worker_id = NULL, claimed_at = NULL
                WHERE status = 'in_progress'
                  AND claimed_at < NOW() - INTERVAL '1 hour'
            """)

            # Now claim next task
            cursor.execute("SELECT * FROM queue.claim_next_task(%s)", (worker_id,))
            row = cursor.fetchone()
            self.conn.commit()
            cursor.close()

            if row:
                return {
                    'id': row[0],
                    'priority': row[1],
                    'task_type': row[2],
                    'payload': row[3],
                    'created_at': row[4]
                }
            return None
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Failed to claim task: {e}")

    def complete_task(self, task_id: int, error: Optional[str] = None):
        """
        Mark task as completed or failed, with dead letter queue for max retries

        Args:
            task_id: ID of the task to complete
            error: Optional error message if task failed
        """
        try:
            cursor = self.conn.cursor()

            if error:
                # Check retry count
                cursor.execute("SELECT retry_count FROM queue.tasks WHERE id = %s", (task_id,))
                row = cursor.fetchone()
                if row and row[0] >= 3:
                    # Max retries reached - move to dead letter queue
                    cursor.execute("""
                        UPDATE queue.tasks
                        SET status = 'dead_letter',
                            completed_at = NOW(),
                            error_message = %s
                        WHERE id = %s
                    """, (f"Max retries exceeded: {error}", task_id))
                else:
                    # Increment retry and requeue
                    cursor.execute("""
                        UPDATE queue.tasks
                        SET status = 'pending',
                            worker_id = NULL,
                            retry_count = retry_count + 1,
                            error_message = %s
                        WHERE id = %s
                    """, (error, task_id))
            else:
                # Success
                cursor.execute("SELECT queue.complete_task(%s, %s)", (task_id, error))

            self.conn.commit()
            cursor.close()
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Failed to complete task: {e}")

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the queue"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) as total
            FROM queue.tasks
        """)
        row = cursor.fetchone()
        cursor.close()

        return {
            'pending': row[0],
            'in_progress': row[1],
            'completed': row[2],
            'failed': row[3],
            'total': row[4]
        }

    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get list of pending tasks"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, priority, task_type, created_at
            FROM queue.tasks
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT %s
        """, (limit,))

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'priority': row[1],
                'task_type': row[2],
                'created_at': row[3]
            })

        cursor.close()
        return tasks

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Test the task queue system"""
    print("="*60)
    print("TASK QUEUE SYSTEM TEST")
    print("="*60)

    tq = TaskQueue()

    # Add some test tasks
    print("\n1. Adding tasks...")
    task1 = tq.add_task(10, 'urgent_process', {'file': 'data.csv', 'priority': 'high'})
    task2 = tq.add_task(5, 'generate_embeddings', {'batch': 100})
    task3 = tq.add_task(8, 'process_file', {'path': '/tmp/test.txt'})
    print(f"  ✓ Added tasks: {task1}, {task2}, {task3}")

    # Get stats
    print("\n2. Queue statistics...")
    stats = tq.get_queue_stats()
    print(f"  Pending: {stats['pending']}, In Progress: {stats['in_progress']}, Completed: {stats['completed']}")

    # Claim next task
    print("\n3. Claiming task as worker-01...")
    task = tq.claim_next_task('worker-01')
    if task:
        print(f"  ✓ Claimed task {task['id']}: {task['task_type']} (priority {task['priority']})")

        # Complete it
        tq.complete_task(task['id'])
        print(f"  ✓ Completed task {task['id']}")

    # Get pending tasks
    print("\n4. Pending tasks...")
    pending = tq.get_pending_tasks(limit=5)
    for t in pending:
        print(f"  - Task {t['id']}: {t['task_type']} (priority {t['priority']})")

    tq.close()
    print("\n✅ Task queue system test complete!")


if __name__ == "__main__":
    main()
