#!/usr/bin/env python3
"""
Test Redis Worker Queue Mode Auto-Detection

Verifies that:
1. Store stage uses ZPOPMIN (sorted set priority queue)
2. Chunk/Embed/Graph stages use BRPOP (list FIFO queue)
3. Manual override works correctly
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import importlib.util

# Add scripts to path
scripts_path = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_path))

# Import redis_atomic_operations module first (dependency)
spec_atomic = importlib.util.spec_from_file_location(
    "redis_atomic_operations",
    scripts_path / "redis-atomic-operations.py"
)
redis_atomic_module = importlib.util.module_from_spec(spec_atomic)
sys.modules['redis_atomic_operations'] = redis_atomic_module
spec_atomic.loader.exec_module(redis_atomic_module)

# Import module with dashes in name
spec = importlib.util.spec_from_file_location(
    "redis_worker_with_atomic_ops",
    scripts_path / "redis-worker-with-atomic-ops.py"
)
redis_worker_module = importlib.util.module_from_spec(spec)
sys.modules['redis_worker_with_atomic_ops'] = redis_worker_module
spec.loader.exec_module(redis_worker_module)

from redis_worker_with_atomic_ops import RedisWorker


class TestRedisWorkerQueueModes(unittest.TestCase):
    """Test queue mode auto-detection in Redis worker."""

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_store_stage_uses_zset_mode(self, mock_signal, mock_redis_ops):
        """Store stage should auto-detect to 'zset' (ZPOPMIN priority queue)."""
        worker = RedisWorker(
            worker_id='test-worker-1',
            stage='store'
        )

        self.assertEqual(worker.queue_mode, 'zset',
                        "Store stage should use 'zset' for priority queue (ZPOPMIN)")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_chunk_stage_uses_list_mode(self, mock_signal, mock_redis_ops):
        """Chunk stage should auto-detect to 'list' (BRPOP FIFO queue)."""
        worker = RedisWorker(
            worker_id='test-worker-2',
            stage='chunk'
        )

        self.assertEqual(worker.queue_mode, 'list',
                        "Chunk stage should use 'list' for FIFO queue (BRPOP)")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_embed_stage_uses_list_mode(self, mock_signal, mock_redis_ops):
        """Embed stage should auto-detect to 'list' (BRPOP FIFO queue)."""
        worker = RedisWorker(
            worker_id='test-worker-3',
            stage='embed'
        )

        self.assertEqual(worker.queue_mode, 'list',
                        "Embed stage should use 'list' for FIFO queue (BRPOP)")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_graph_stage_uses_list_mode(self, mock_signal, mock_redis_ops):
        """Graph stage should auto-detect to 'list' (BRPOP FIFO queue)."""
        worker = RedisWorker(
            worker_id='test-worker-4',
            stage='graph'
        )

        self.assertEqual(worker.queue_mode, 'list',
                        "Graph stage should use 'list' for FIFO queue (BRPOP)")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_manual_override_to_list(self, mock_signal, mock_redis_ops):
        """Manual override to 'list' should work for store stage."""
        worker = RedisWorker(
            worker_id='test-worker-5',
            stage='store',
            queue_mode='list'
        )

        self.assertEqual(worker.queue_mode, 'list',
                        "Manual override to 'list' should work")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_manual_override_to_zset(self, mock_signal, mock_redis_ops):
        """Manual override to 'zset' should work for chunk stage."""
        worker = RedisWorker(
            worker_id='test-worker-6',
            stage='chunk',
            queue_mode='zset'
        )

        self.assertEqual(worker.queue_mode, 'zset',
                        "Manual override to 'zset' should work")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_queue_mode_passed_to_claim_tasks(self, mock_signal, mock_redis_ops):
        """Queue mode should be passed to RedisAtomicOps.claim_task()."""
        mock_ops_instance = Mock()
        mock_redis_ops.return_value = mock_ops_instance

        # Store stage (should use zset)
        worker = RedisWorker(
            worker_id='test-worker-7',
            stage='store'
        )

        # Mock claim_task to return None (no tasks)
        mock_ops_instance.claim_task.return_value = None

        # Call claim_tasks
        worker.claim_tasks()

        # Verify claim_task was called with queue_mode='zset'
        mock_ops_instance.claim_task.assert_called()
        call_args = mock_ops_instance.claim_task.call_args
        self.assertEqual(call_args.kwargs.get('queue_mode'), 'zset',
                        "claim_task should be called with queue_mode='zset' for store stage")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_chunk_queue_mode_passed_to_claim_tasks(self, mock_signal, mock_redis_ops):
        """Chunk stage should pass queue_mode='list' to claim_task()."""
        mock_ops_instance = Mock()
        mock_redis_ops.return_value = mock_ops_instance

        # Chunk stage (should use list)
        worker = RedisWorker(
            worker_id='test-worker-8',
            stage='chunk'
        )

        # Mock claim_task to return None (no tasks)
        mock_ops_instance.claim_task.return_value = None

        # Call claim_tasks
        worker.claim_tasks()

        # Verify claim_task was called with queue_mode='list'
        mock_ops_instance.claim_task.assert_called()
        call_args = mock_ops_instance.claim_task.call_args
        self.assertEqual(call_args.kwargs.get('queue_mode'), 'list',
                        "claim_task should be called with queue_mode='list' for chunk stage")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_store_stage_queue_names(self, mock_signal, mock_redis_ops):
        """Store stage should monitor priority queues (high/medium/low)."""
        worker = RedisWorker(
            worker_id='test-worker-9',
            stage='store'
        )

        expected_queues = [
            'redis:queue:store:high',
            'redis:queue:store:medium',
            'redis:queue:store:low'
        ]

        self.assertEqual(worker.queue_names, expected_queues,
                        "Store stage should monitor high/medium/low priority queues")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_chunk_stage_queue_names(self, mock_signal, mock_redis_ops):
        """Chunk stage should monitor single chunk queue."""
        worker = RedisWorker(
            worker_id='test-worker-10',
            stage='chunk'
        )

        expected_queues = ['redis:queue:chunk']

        self.assertEqual(worker.queue_names, expected_queues,
                        "Chunk stage should monitor single chunk queue")

    @patch('redis_worker_with_atomic_ops.RedisAtomicOps')
    @patch('redis_worker_with_atomic_ops.signal')
    def test_next_queue_mapping(self, mock_signal, mock_redis_ops):
        """Verify next_queue mapping for pipeline stages."""
        test_cases = [
            ('store', 'redis:queue:chunk'),
            ('chunk', 'redis:queue:embed'),
            ('embed', 'redis:queue:graph'),
            ('graph', None)  # Terminal stage
        ]

        for stage, expected_next in test_cases:
            worker = RedisWorker(
                worker_id=f'test-worker-{stage}',
                stage=stage
            )

            self.assertEqual(worker.next_queue, expected_next,
                           f"Stage '{stage}' should have next_queue={expected_next}")


if __name__ == '__main__':
    unittest.main()
