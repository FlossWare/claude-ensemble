#!/usr/bin/env python3
"""
Test: Verify Next Queue Mode Configuration

Tests that the worker correctly configures next_queue_mode based on stage.
This is a unit test that doesn't require Redis connection.
"""

import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_dir))


def test_next_queue_mode_config():
    """Test that next_queue_mode is configured correctly."""
    print("=== Test: Next Queue Mode Configuration ===\n")

    # Import after path is set
    from redis_worker_with_atomic_ops import RedisWorker

    # Patch RedisAtomicOps to avoid Redis connection
    import redis_atomic_operations
    original_init = redis_atomic_operations.RedisAtomicOps.__init__

    def mock_init(self, host='aio-01', port=6379, db=0):
        # Skip Redis connection
        pass

    redis_atomic_operations.RedisAtomicOps.__init__ = mock_init

    try:
        # Test store stage
        print("1. Testing store stage configuration")
        worker_store = RedisWorker(
            worker_id='test-store',
            stage='store',
            batch_size=1
        )

        print(f"   Store stage:")
        print(f"   - Current queue_mode: {worker_store.queue_mode}")
        print(f"   - Next queue: {worker_store.next_queue}")
        print(f"   - Next queue_mode: {worker_store.next_queue_mode}")

        if worker_store.queue_mode != 'zset':
            print(f"   ✗ FAILED: Expected store queue_mode='zset', got '{worker_store.queue_mode}'")
            return False

        if worker_store.next_queue != 'redis:queue:chunk':
            print(f"   ✗ FAILED: Expected next_queue='redis:queue:chunk', got '{worker_store.next_queue}'")
            return False

        if worker_store.next_queue_mode != 'list':
            print(f"   ✗ FAILED: Expected next_queue_mode='list', got '{worker_store.next_queue_mode}'")
            return False

        print("   ✓ Store configuration correct\n")

        # Test chunk stage
        print("2. Testing chunk stage configuration")
        worker_chunk = RedisWorker(
            worker_id='test-chunk',
            stage='chunk',
            batch_size=1
        )

        print(f"   Chunk stage:")
        print(f"   - Current queue_mode: {worker_chunk.queue_mode}")
        print(f"   - Next queue: {worker_chunk.next_queue}")
        print(f"   - Next queue_mode: {worker_chunk.next_queue_mode}")

        if worker_chunk.queue_mode != 'list':
            print(f"   ✗ FAILED: Expected chunk queue_mode='list', got '{worker_chunk.queue_mode}'")
            return False

        if worker_chunk.next_queue != 'redis:queue:embed':
            print(f"   ✗ FAILED: Expected next_queue='redis:queue:embed', got '{worker_chunk.next_queue}'")
            return False

        if worker_chunk.next_queue_mode != 'list':
            print(f"   ✗ FAILED: Expected next_queue_mode='list', got '{worker_chunk.next_queue_mode}'")
            return False

        print("   ✓ Chunk configuration correct\n")

        # Test embed stage
        print("3. Testing embed stage configuration")
        worker_embed = RedisWorker(
            worker_id='test-embed',
            stage='embed',
            batch_size=1
        )

        print(f"   Embed stage:")
        print(f"   - Current queue_mode: {worker_embed.queue_mode}")
        print(f"   - Next queue: {worker_embed.next_queue}")
        print(f"   - Next queue_mode: {worker_embed.next_queue_mode}")

        if worker_embed.queue_mode != 'list':
            print(f"   ✗ FAILED: Expected embed queue_mode='list', got '{worker_embed.queue_mode}'")
            return False

        if worker_embed.next_queue != 'redis:queue:graph':
            print(f"   ✗ FAILED: Expected next_queue='redis:queue:graph', got '{worker_embed.next_queue}'")
            return False

        if worker_embed.next_queue_mode != 'list':
            print(f"   ✗ FAILED: Expected next_queue_mode='list', got '{worker_embed.next_queue_mode}'")
            return False

        print("   ✓ Embed configuration correct\n")

        # Test graph stage (terminal)
        print("4. Testing graph stage configuration (terminal)")
        worker_graph = RedisWorker(
            worker_id='test-graph',
            stage='graph',
            batch_size=1
        )

        print(f"   Graph stage:")
        print(f"   - Current queue_mode: {worker_graph.queue_mode}")
        print(f"   - Next queue: {worker_graph.next_queue}")
        print(f"   - Next queue_mode: {worker_graph.next_queue_mode}")

        if worker_graph.queue_mode != 'list':
            print(f"   ✗ FAILED: Expected graph queue_mode='list', got '{worker_graph.queue_mode}'")
            return False

        if worker_graph.next_queue is not None:
            print(f"   ✗ FAILED: Expected next_queue=None (terminal), got '{worker_graph.next_queue}'")
            return False

        if worker_graph.next_queue_mode is not None:
            print(f"   ✗ FAILED: Expected next_queue_mode=None (terminal), got '{worker_graph.next_queue_mode}'")
            return False

        print("   ✓ Graph configuration correct\n")

        print("✅ ALL TESTS PASSED\n")
        print("Summary:")
        print("- Store: zset → Chunk (list) ✓")
        print("- Chunk: list → Embed (list) ✓")
        print("- Embed: list → Graph (list) ✓")
        print("- Graph: list → None (terminal) ✓")

        return True

    finally:
        # Restore original init
        redis_atomic_operations.RedisAtomicOps.__init__ = original_init


if __name__ == '__main__':
    try:
        success = test_next_queue_mode_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
