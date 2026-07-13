"""
Redis-based distributed queue implementation with O(1) operations.

Architecture:
- pending: LIST (RPUSH to add, BLPOP to claim)
- processing: HASH (task_id -> JSON metadata)
- completed: HASH (task_id -> result)
- failed: HASH (task_id -> error)

O(1) Operations:
- add: RPUSH to pending list
- claim: BLPOP from pending + HSET to processing
- complete: HGET from processing + HDEL from processing + HSET to completed
- fail: HGET from processing + HDEL from processing + HSET to failed
"""

import json
import time
from typing import Dict, Optional, Any, List
import redis
from redis.sentinel import Sentinel


class RedisQueue:
    """Distributed queue with O(1) claim/complete/fail operations."""

    def __init__(self, queue_name: str, redis_client: redis.Redis):
        """
        Initialize queue.

        Args:
            queue_name: Name of the queue (e.g., 'scrape', 'process')
            redis_client: Connected Redis client
        """
        self.queue_name = queue_name
        self.redis = redis_client

        # Key names
        self.pending_key = f"queue:{queue_name}:pending"
        self.processing_key = f"queue:{queue_name}:processing"
        self.completed_key = f"queue:{queue_name}:completed"
        self.failed_key = f"queue:{queue_name}:failed"

    def add(self, task_id: str, payload: Dict[str, Any]) -> bool:
        """
        Add task to queue.

        Args:
            task_id: Unique task identifier
            payload: Task data (will be JSON serialized)

        Returns:
            True if added successfully

        Complexity: O(1)
        """
        task_data = {
            'task_id': task_id,
            'payload': payload,
            'added_at': time.time()
        }

        # RPUSH is O(1)
        self.redis.rpush(self.pending_key, json.dumps(task_data))
        return True

    def claim(self, worker_id: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Claim next task from queue (blocking).

        Args:
            worker_id: ID of worker claiming task
            timeout: Seconds to wait for task (0 = forever)

        Returns:
            Task data or None if timeout

        Complexity: O(1)
        """
        # BLPOP is O(1)
        result = self.redis.blpop(self.pending_key, timeout=timeout)

        if not result:
            return None

        _, task_json = result
        task_data = json.loads(task_json)

        # Add to processing hash - O(1)
        task_data['claimed_at'] = time.time()
        task_data['worker_id'] = worker_id

        self.redis.hset(
            self.processing_key,
            task_data['task_id'],
            json.dumps(task_data)
        )

        return task_data

    def complete(self, task_id: str, result: Any) -> bool:
        """
        Mark task as completed.

        Args:
            task_id: Task identifier
            result: Result data (will be JSON serialized)

        Returns:
            True if completed successfully, False if task not found

        Complexity: O(1) - HGET + HDEL + HSET
        """
        # HGET to get task data - O(1)
        task_json = self.redis.hget(self.processing_key, task_id)

        if not task_json:
            return False

        task_data = json.loads(task_json)

        # HDEL from processing - O(1)
        self.redis.hdel(self.processing_key, task_id)

        # HSET to completed - O(1)
        completion_data = {
            'task_id': task_id,
            'result': result,
            'completed_at': time.time(),
            'worker_id': task_data.get('worker_id'),
            'duration': time.time() - task_data.get('claimed_at', time.time())
        }

        self.redis.hset(
            self.completed_key,
            task_id,
            json.dumps(completion_data)
        )

        return True

    def fail(self, task_id: str, error: str) -> bool:
        """
        Mark task as failed.

        Args:
            task_id: Task identifier
            error: Error message

        Returns:
            True if marked failed, False if task not found

        Complexity: O(1) - HGET + HDEL + HSET
        """
        # HGET to get task data - O(1)
        task_json = self.redis.hget(self.processing_key, task_id)

        if not task_json:
            return False

        task_data = json.loads(task_json)

        # HDEL from processing - O(1)
        self.redis.hdel(self.processing_key, task_id)

        # HSET to failed - O(1)
        failure_data = {
            'task_id': task_id,
            'error': error,
            'failed_at': time.time(),
            'worker_id': task_data.get('worker_id'),
            'duration': time.time() - task_data.get('claimed_at', time.time()),
            'payload': task_data.get('payload')  # Keep for retry
        }

        self.redis.hset(
            self.failed_key,
            task_id,
            json.dumps(failure_data)
        )

        return True

    def stats(self) -> Dict[str, int]:
        """
        Get queue statistics.

        Returns:
            Dictionary with pending/processing/completed/failed counts

        Complexity: O(1) for each HLEN/LLEN
        """
        return {
            'pending': self.redis.llen(self.pending_key),
            'processing': self.redis.hlen(self.processing_key),
            'completed': self.redis.hlen(self.completed_key),
            'failed': self.redis.hlen(self.failed_key)
        }

    def get_processing_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all currently processing tasks.

        Returns:
            List of task data dictionaries

        Complexity: O(N) where N = processing tasks
        WARNING: Use sparingly, only for monitoring
        """
        task_jsons = self.redis.hgetall(self.processing_key)
        return [json.loads(task_json) for task_json in task_jsons.values()]

    def requeue_stale(self, stale_seconds: int = 300) -> int:
        """
        Requeue tasks stuck in processing for too long.

        Args:
            stale_seconds: Tasks older than this are considered stale

        Returns:
            Number of tasks requeued

        Complexity: O(N) where N = processing tasks
        WARNING: Use sparingly, typically in cron job
        """
        now = time.time()
        requeued = 0

        # Get all processing tasks - O(N)
        processing = self.redis.hgetall(self.processing_key)

        for task_id, task_json in processing.items():
            task_data = json.loads(task_json)
            claimed_at = task_data.get('claimed_at', now)

            if now - claimed_at > stale_seconds:
                # Remove from processing - O(1)
                self.redis.hdel(self.processing_key, task_id)

                # Add back to pending - O(1)
                task_data.pop('claimed_at', None)
                task_data.pop('worker_id', None)
                self.redis.rpush(self.pending_key, json.dumps(task_data))

                requeued += 1

        return requeued


class SentinelQueue(RedisQueue):
    """Queue using Redis Sentinel for high availability."""

    def __init__(self, queue_name: str, sentinel_hosts: List[tuple], service_name: str = 'mymaster'):
        """
        Initialize queue with Sentinel.

        Args:
            queue_name: Name of the queue
            sentinel_hosts: List of (host, port) tuples for Sentinel nodes
            service_name: Name of the Redis service
        """
        sentinel = Sentinel(sentinel_hosts, socket_timeout=0.5)
        redis_client = sentinel.master_for(service_name, socket_timeout=0.5)
        super().__init__(queue_name, redis_client)


def create_queue(queue_name: str, use_sentinel: bool = True) -> RedisQueue:
    """
    Factory function to create queue instance.

    Args:
        queue_name: Name of the queue
        use_sentinel: Whether to use Sentinel (True) or direct connection (False)

    Returns:
        RedisQueue instance
    """
    if use_sentinel:
        sentinel_hosts = [
            ('laptop-01', 26379),
            ('aio-01', 26379),
            ('server-01', 26379)
        ]
        return SentinelQueue(queue_name, sentinel_hosts)
    else:
        # Direct connection (for testing)
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        return RedisQueue(queue_name, redis_client)


if __name__ == '__main__':
    # Example usage
    queue = create_queue('test-queue', use_sentinel=False)

    # Add task
    queue.add('task-1', {'url': 'https://example.com', 'type': 'scrape'})

    # Claim task
    task = queue.claim('worker-1', timeout=1)
    if task:
        print(f"Claimed: {task}")

        # Complete or fail
        if task['payload']['url'].startswith('https'):
            queue.complete(task['task_id'], {'status': 'success'})
        else:
            queue.fail(task['task_id'], 'Invalid URL')

    # Stats
    print(f"Stats: {queue.stats()}")
