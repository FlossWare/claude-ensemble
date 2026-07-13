"""
Redis Atomic Operations Wrapper (Python)

Loads and executes Lua scripts for atomic multi-step operations.
All operations are transactional and race-condition free.

Usage:
    from redis_atomic_wrapper import RedisAtomic
    import redis

    r = redis.Redis(host='aio-01', port=6379, db=0)
    atomic = RedisAtomic(r)

    result = atomic.enqueue('scrape_queue', 'https://example.com')
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class RedisAtomic:
    """Atomic Redis operations via Lua scripts"""

    def __init__(self, redis_client):
        """
        Initialize with a Redis client

        Args:
            redis_client: redis.Redis instance
        """
        self.redis = redis_client
        self.scripts = {}
        self._load_scripts()

    def _load_scripts(self):
        """Load Lua scripts from file"""
        lua_path = Path(__file__).parent / 'redis-atomic-operations.lua'
        lua_content = lua_path.read_text()

        # Define script templates
        # Each script extracts the function and calls it

        self.scripts['enqueue'] = self._register_script("""
            {function}
            return atomic_enqueue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2])
        """, lua_content, 'atomic_enqueue')

        self.scripts['dequeue'] = self._register_script("""
            {function}
            return atomic_dequeue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3])
        """, lua_content, 'atomic_dequeue')

        self.scripts['complete'] = self._register_script("""
            {function}
            return atomic_complete(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3], ARGV[4])
        """, lua_content, 'atomic_complete')

        self.scripts['retry'] = self._register_script("""
            {function}
            return atomic_retry(KEYS[1], KEYS[2], KEYS[3], KEYS[4], ARGV[1], ARGV[2], ARGV[3], ARGV[4])
        """, lua_content, 'atomic_retry')

        self.scripts['reclaim_stale'] = self._register_script("""
            {function}
            return atomic_reclaim_stale(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2])
        """, lua_content, 'atomic_reclaim_stale')

        self.scripts['batch_enqueue'] = self._register_script("""
            {function}
            return atomic_batch_enqueue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2])
        """, lua_content, 'atomic_batch_enqueue')

        self.scripts['stats'] = self._register_script("""
            {function}
            return atomic_queue_stats(KEYS[1], KEYS[2], KEYS[3], KEYS[4])
        """, lua_content, 'atomic_queue_stats')

        self.scripts['priority_enqueue'] = self._register_script("""
            {function}
            return atomic_priority_enqueue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3])
        """, lua_content, 'atomic_priority_enqueue')

    def _register_script(self, template: str, lua_content: str, function_name: str):
        """
        Register a Lua script with Redis

        Args:
            template: Script template with {function} placeholder
            lua_content: Full Lua file content
            function_name: Name of function to extract

        Returns:
            redis.client.Script object
        """
        function_code = self._extract_function(lua_content, function_name)
        script = template.format(function=function_code)
        return self.redis.register_script(script)

    def _extract_function(self, content: str, function_name: str) -> str:
        """
        Extract a function definition from Lua content

        Args:
            content: Full Lua file content
            function_name: Name of function to extract

        Returns:
            Function definition as string
        """
        import re

        start_pattern = f"local function {function_name}("
        start = content.find(start_pattern)

        if start == -1:
            raise ValueError(f"Function {function_name} not found in Lua file")

        # Count depth of block structures starting from the function definition
        # Keywords that start a block: function, if, for, while, repeat, do
        # Keywords that end a block: end, until

        lines = content[start:].split('\n')
        depth = 0
        end_line = 0
        started = False

        for i, line in enumerate(lines):
            # Remove comments and strings to avoid false matches
            stripped = re.sub(r'--.*$', '', line)  # Remove comments
            stripped = re.sub(r'"[^"]*"', '', stripped)  # Remove double-quoted strings
            stripped = re.sub(r"'[^']*'", '', stripped)  # Remove single-quoted strings

            # Count block starters
            # Note: 'for' and 'while' include implicit 'do', so don't count 'do' separately
            starters = 0
            starters += len(re.findall(r'\bfunction\b', stripped))
            starters += len(re.findall(r'\bif\b', stripped))
            starters += len(re.findall(r'\bfor\b', stripped))
            starters += len(re.findall(r'\bwhile\b', stripped))
            starters += len(re.findall(r'\brepeat\b', stripped))
            # Only count 'do' if not preceded by 'for' or 'while' on same line
            if re.search(r'\bdo\b', stripped) and not re.search(r'\b(for|while)\b.*\bdo\b', stripped):
                starters += 1

            depth += starters

            # Mark that we've started (first line will have 'function')
            if not started and starters > 0:
                started = True

            # Count block enders
            end_count = len(re.findall(r'\bend\b', stripped))
            until_count = len(re.findall(r'\buntil\b', stripped))
            depth -= (end_count + until_count)

            # When depth reaches 0 after we've started past the first line, we found the function's end
            if started and depth == 0 and i > 0:
                end_line = i
                break

        # Extract the function text
        function_text = '\n'.join(lines[:end_line+1])
        return function_text

    def enqueue(self, queue_name: str, url: str, timestamp: Optional[str] = None) -> int:
        """
        Atomically enqueue a URL with deduplication

        Args:
            queue_name: Name of the queue
            url: URL to enqueue
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            1 if enqueued, 0 if duplicate, -1 if already processed
        """
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))

        keys = [
            queue_name,
            f'{queue_name}:processed',
            f'{queue_name}:queued'
        ]
        args = [url, timestamp]

        return self.scripts['enqueue'](keys=keys, args=args)

    def dequeue(self, queue_name: str, worker_id: str, timeout: int = 300) -> Optional[str]:
        """
        Atomically dequeue a URL and claim it for processing

        Args:
            queue_name: Name of the queue
            worker_id: Identifier for the worker claiming this job
            timeout: Timeout in seconds before job is considered stale (default: 300)

        Returns:
            URL to process, or None if queue empty
        """
        keys = [
            queue_name,
            f'{queue_name}:queued',
            f'{queue_name}:in_progress'
        ]
        args = [worker_id, str(int(time.time() * 1000)), str(timeout)]

        result = self.scripts['dequeue'](keys=keys, args=args)
        return result.decode('utf-8') if result else None

    def complete(self, queue_name: str, url: str, worker_id: str, result: str = 'success') -> int:
        """
        Atomically mark a job as completed

        Args:
            queue_name: Name of the queue
            url: URL that was processed
            worker_id: Worker that processed this job
            result: Result status (success/failure)

        Returns:
            1 if completed, 0 if not owned by worker, -1 if not in progress
        """
        keys = [
            f'{queue_name}:in_progress',
            f'{queue_name}:processed',
            queue_name
        ]
        args = [url, worker_id, str(int(time.time() * 1000)), result]

        return self.scripts['complete'](keys=keys, args=args)

    def retry(self, queue_name: str, url: str, worker_id: str, max_retries: int = 3) -> int:
        """
        Atomically retry a failed job with backoff

        Args:
            queue_name: Name of the queue
            url: URL to retry
            worker_id: Worker that failed this job
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Retry count if requeued, -1 if max retries exceeded, -2 if not owned by worker
        """
        keys = [
            f'{queue_name}:in_progress',
            queue_name,
            f'{queue_name}:queued',
            f'{queue_name}:retry_count'
        ]
        args = [url, worker_id, str(max_retries), str(int(time.time() * 1000))]

        return self.scripts['retry'](keys=keys, args=args)

    def reclaim_stale(self, queue_name: str, timeout: int = 300) -> List[str]:
        """
        Atomically reclaim stale jobs that have timed out

        Args:
            queue_name: Name of the queue
            timeout: Timeout in seconds (default: 300)

        Returns:
            List of reclaimed URLs
        """
        keys = [
            f'{queue_name}:in_progress',
            queue_name,
            f'{queue_name}:queued'
        ]
        args = [str(int(time.time() * 1000)), str(timeout)]

        result = self.scripts['reclaim_stale'](keys=keys, args=args)
        return [url.decode('utf-8') for url in result] if result else []

    def batch_enqueue(self, queue_name: str, urls: List[str]) -> Dict[str, int]:
        """
        Atomically enqueue multiple URLs in a batch

        Args:
            queue_name: Name of the queue
            urls: List of URLs to enqueue

        Returns:
            Dict with keys: enqueued, duplicates, already_processed
        """
        keys = [
            queue_name,
            f'{queue_name}:processed',
            f'{queue_name}:queued'
        ]
        args = [json.dumps(urls), str(int(time.time() * 1000))]

        result = self.scripts['batch_enqueue'](keys=keys, args=args)

        return {
            'enqueued': result[0],
            'duplicates': result[1],
            'already_processed': result[2]
        }

    def stats(self, queue_name: str) -> Dict[str, int]:
        """
        Atomically get queue statistics

        Args:
            queue_name: Name of the queue

        Returns:
            Dict with keys: pending, processed, queued, in_progress, dead_letter
        """
        keys = [
            queue_name,
            f'{queue_name}:processed',
            f'{queue_name}:queued',
            f'{queue_name}:in_progress'
        ]
        args = []

        result = self.scripts['stats'](keys=keys, args=args)

        return {
            'pending': result[0],
            'processed': result[1],
            'queued': result[2],
            'in_progress': result[3],
            'dead_letter': result[4]
        }

    def priority_enqueue(self, queue_name: str, url: str, priority: str = 'normal') -> int:
        """
        Atomically enqueue a URL with priority

        Args:
            queue_name: Name of the queue
            url: URL to enqueue
            priority: Priority level (high/normal, default: normal)

        Returns:
            1 if enqueued, 0 if duplicate, -1 if already processed
        """
        keys = [
            queue_name,
            f'{queue_name}:processed',
            f'{queue_name}:queued'
        ]
        args = [url, str(int(time.time() * 1000)), priority]

        return self.scripts['priority_enqueue'](keys=keys, args=args)


# Example usage
if __name__ == '__main__':
    import redis

    # Connect to Redis
    r = redis.Redis(host='aio-01', port=6379, db=0)
    atomic = RedisAtomic(r)

    # Test operations
    print("Testing atomic operations...")

    # Enqueue
    result = atomic.enqueue('test_queue', 'https://example.com')
    print(f"Enqueue result: {result}")

    # Stats
    stats = atomic.stats('test_queue')
    print(f"Queue stats: {stats}")

    # Dequeue
    url = atomic.dequeue('test_queue', 'worker-1')
    print(f"Dequeued URL: {url}")

    # Complete
    if url:
        result = atomic.complete('test_queue', url, 'worker-1', 'success')
        print(f"Complete result: {result}")

    # Final stats
    stats = atomic.stats('test_queue')
    print(f"Final stats: {stats}")
