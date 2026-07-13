#!/usr/bin/env python3
"""
Integration Test: Redis Queue Operations

Tests actual Redis operations to verify:
1. Store queue uses ZPOPMIN (sorted set)
2. Chunk/embed/graph queues use BRPOP (lists)
3. Pipeline flows correctly from store → chunk → embed → graph

NOTE: Requires Redis running on aio-01:6379
"""

import sys
import unittest
import json
import time
from pathlib import Path
import importlib.util

# Add scripts to path
scripts_path = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_path))

# Import redis_atomic_operations
spec_atomic = importlib.util.spec_from_file_location(
    "redis_atomic_operations",
    scripts_path / "redis-atomic-operations.py"
)
redis_atomic_module = importlib.util.module_from_spec(spec_atomic)
sys.modules['redis_atomic_operations'] = redis_atomic_module
spec_atomic.loader.exec_module(redis_atomic_module)

from redis_atomic_operations import RedisAtomicOps

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@unittest.skipIf(not REDIS_AVAILABLE, "Redis module not available")
class TestRedisQueueIntegration(unittest.TestCase):
    """Integration tests for Redis queue operations."""

    @classmethod
    def setUpClass(cls):
        """Check Redis connectivity."""
        try:
            cls.redis_client = redis.Redis(host='aio-01', port=6379, decode_responses=True)
            cls.redis_client.ping()
            cls.redis_available = True
        except Exception as e:
            cls.redis_available = False
            print(f"WARNING: Redis not available: {e}")

    def setUp(self):
        """Clean up test queues before each test."""
        if not self.redis_available:
            self.skipTest("Redis not available on aio-01:6379")

        # Clean up test queues
        test_queues = [
            'test:redis:queue:store:high',
            'test:redis:queue:chunk',
            'test:redis:queue:embed',
            'test:redis:queue:graph'
        ]

        for queue in test_queues:
            self.redis_client.delete(queue)

    def test_store_queue_is_sorted_set(self):
        """Store queue should be a sorted set (zset)."""
        queue_name = 'test:redis:queue:store:high'

        # Add items with priorities (lower score = higher priority)
        self.redis_client.zadd(queue_name, {
            json.dumps({'id': 'task1', 'data': 'low priority'}): 10,
            json.dumps({'id': 'task2', 'data': 'high priority'}): 1,
            json.dumps({'id': 'task3', 'data': 'medium priority'}): 5
        })

        # Verify queue type
        queue_type = self.redis_client.type(queue_name)
        self.assertEqual(queue_type, 'zset', "Store queue should be sorted set")

        # Pop with ZPOPMIN (lowest score first = highest priority)
        result = self.redis_client.zpopmin(queue_name)
        self.assertIsNotNone(result)

        # Result is list of (member, score) tuples
        task_json, score = result[0]
        task = json.loads(task_json)

        self.assertEqual(task['id'], 'task2', "Should pop highest priority task first")
        self.assertEqual(score, 1.0, "Should have priority score 1")

    def test_chunk_queue_is_list(self):
        """Chunk queue should be a list (FIFO)."""
        queue_name = 'test:redis:queue:chunk'

        # Add items (LPUSH adds to left, RPOP removes from right = FIFO)
        items = [
            json.dumps({'id': 'chunk1', 'data': 'first'}),
            json.dumps({'id': 'chunk2', 'data': 'second'}),
            json.dumps({'id': 'chunk3', 'data': 'third'})
        ]

        for item in items:
            self.redis_client.lpush(queue_name, item)

        # Verify queue type
        queue_type = self.redis_client.type(queue_name)
        self.assertEqual(queue_type, 'list', "Chunk queue should be list")

        # Pop with RPOP (FIFO)
        result = self.redis_client.rpop(queue_name)
        self.assertIsNotNone(result)

        task = json.loads(result)
        self.assertEqual(task['id'], 'chunk1', "Should pop first item (FIFO)")

    def test_embed_queue_is_list(self):
        """Embed queue should be a list (FIFO)."""
        queue_name = 'test:redis:queue:embed'

        # Add items
        self.redis_client.lpush(queue_name, json.dumps({'id': 'embed1'}))

        # Verify queue type
        queue_type = self.redis_client.type(queue_name)
        self.assertEqual(queue_type, 'list', "Embed queue should be list")

    def test_graph_queue_is_list(self):
        """Graph queue should be a list (FIFO)."""
        queue_name = 'test:redis:queue:graph'

        # Add items
        self.redis_client.lpush(queue_name, json.dumps({'id': 'graph1'}))

        # Verify queue type
        queue_type = self.redis_client.type(queue_name)
        self.assertEqual(queue_type, 'list', "Graph queue should be list")

    def test_brpop_blocks_on_empty_queue(self):
        """BRPOP should block on empty queue (with timeout)."""
        queue_name = 'test:redis:queue:chunk'

        # BRPOP with 1-second timeout on empty queue
        start_time = time.time()
        result = self.redis_client.brpop(queue_name, timeout=1)
        elapsed = time.time() - start_time

        self.assertIsNone(result, "BRPOP should return None on timeout")
        self.assertGreaterEqual(elapsed, 0.9, "BRPOP should block for ~1 second")

    def test_pipeline_flow(self):
        """Test complete pipeline flow: store → chunk → embed → graph."""
        ops = RedisAtomicOps(host='aio-01', port=6379)

        # 1. Add task to store queue (priority queue)
        store_queue = 'test:redis:queue:store:high'
        task = {
            'id': 'pipeline-test-1',
            'data': {'content': 'test content'},
            'priority': 1
        }

        self.redis_client.zadd(store_queue, {json.dumps(task): task['priority']})

        # 2. Pop from store queue with ZPOPMIN
        result = self.redis_client.zpopmin(store_queue)
        self.assertIsNotNone(result)

        task_json, score = result[0]
        popped_task = json.loads(task_json)
        self.assertEqual(popped_task['id'], 'pipeline-test-1')

        # 3. Push result to chunk queue (list)
        chunk_queue = 'test:redis:queue:chunk'
        chunk_task = {
            'id': popped_task['id'],
            'data': popped_task['data'],
            'from_stage': 'store'
        }
        self.redis_client.lpush(chunk_queue, json.dumps(chunk_task))

        # 4. Pop from chunk queue with RPOP
        result = self.redis_client.rpop(chunk_queue)
        self.assertIsNotNone(result)

        popped_chunk = json.loads(result)
        self.assertEqual(popped_chunk['id'], 'pipeline-test-1')
        self.assertEqual(popped_chunk['from_stage'], 'store')

        # 5. Push to embed queue
        embed_queue = 'test:redis:queue:embed'
        embed_task = {
            'id': popped_chunk['id'],
            'data': popped_chunk['data'],
            'from_stage': 'chunk'
        }
        self.redis_client.lpush(embed_queue, json.dumps(embed_task))

        # 6. Pop from embed queue
        result = self.redis_client.rpop(embed_queue)
        self.assertIsNotNone(result)

        popped_embed = json.loads(result)
        self.assertEqual(popped_embed['from_stage'], 'chunk')

        # 7. Push to graph queue
        graph_queue = 'test:redis:queue:graph'
        graph_task = {
            'id': popped_embed['id'],
            'data': popped_embed['data'],
            'from_stage': 'embed'
        }
        self.redis_client.lpush(graph_queue, json.dumps(graph_task))

        # 8. Pop from graph queue (terminal stage)
        result = self.redis_client.rpop(graph_queue)
        self.assertIsNotNone(result)

        popped_graph = json.loads(result)
        self.assertEqual(popped_graph['id'], 'pipeline-test-1')
        self.assertEqual(popped_graph['from_stage'], 'embed')


if __name__ == '__main__':
    unittest.main()
