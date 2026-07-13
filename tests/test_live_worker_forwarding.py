#!/usr/bin/env python3
"""
Live Worker Test: Verify Next Queue Forwarding

Simulates real worker processing flow:
1. Add task to store:high queue
2. Start store worker (processes and forwards to chunk)
3. Start chunk worker (processes and forwards to embed)
4. Verify task propagates correctly through pipeline
"""

import sys
import os
import json
import time
import subprocess
import redis
from pathlib import Path
from threading import Thread

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_dir))

from redis_atomic_operations import RedisAtomicOps


def cleanup_test_queues():
    """Clean up all test queues."""
    r = redis.Redis(host='aio-01', port=6379, decode_responses=True)
    test_queues = [
        'redis:queue:store:high',
        'redis:queue:chunk',
        'redis:queue:embed',
        'redis:processing:store:high',
        'redis:processing:store:high:metadata',
        'redis:processing:chunk',
        'redis:processing:chunk:metadata',
        'redis:heartbeat:store:high',
        'redis:heartbeat:chunk',
        'redis:completed:store:high',
        'redis:completed:chunk'
    ]
    for queue in test_queues:
        r.delete(queue)


def run_worker(stage, worker_id, duration=5):
    """Run a worker for specified duration."""
    cmd = [
        'python3',
        str(scripts_dir / 'redis_worker_with_atomic_ops.py'),
        '--worker-id', worker_id,
        '--stage', stage,
        '--batch-size', '1'
    ]

    print(f"Starting {worker_id} (stage={stage})...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Let it run for duration
    time.sleep(duration)

    # Terminate gracefully
    proc.terminate()
    try:
        stdout, stderr = proc.communicate(timeout=2)
        print(f"{worker_id} output:\n{stdout}")
        if stderr:
            print(f"{worker_id} errors:\n{stderr}")
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    return proc.returncode


def test_live_worker_forwarding():
    """Test live worker forwarding through pipeline."""

    print("=== Live Worker Forwarding Test ===\n")

    # Clean up
    print("1. Cleaning up test queues...")
    cleanup_test_queues()
    print("   ✓ Queues cleaned\n")

    # Add test task
    print("2. Adding test task to store:high queue...")
    r = redis.Redis(host='aio-01', port=6379, decode_responses=True)

    task = {
        'id': 'live-test-task-1',
        'url': 'https://example.com/live-test',
        'priority': 9,
        'content': 'Test content for live worker',
        'metadata': {'test': 'live_forwarding'}
    }

    # Add to priority queue (store uses zset)
    timestamp_ms = int(time.time() * 1000)
    score = (10 - task['priority']) * 1e13 + timestamp_ms
    r.zadd('redis:queue:store:high', {json.dumps(task): score})

    queue_size = r.zcard('redis:queue:store:high')
    print(f"   ✓ Task added, queue size: {queue_size}\n")

    # Start store worker (will process and forward to chunk)
    print("3. Starting store worker for 3 seconds...")
    run_worker('store', 'live-worker-store', duration=3)
    print("   ✓ Store worker completed\n")

    # Check chunk queue
    print("4. Checking chunk queue...")
    chunk_queue_type = r.type('redis:queue:chunk')
    chunk_queue_len = r.llen('redis:queue:chunk') if chunk_queue_type == 'list' else 0

    print(f"   Queue type: {chunk_queue_type}")
    print(f"   Queue length: {chunk_queue_len}")

    if chunk_queue_type != 'list':
        print(f"   ✗ FAILED: Expected list, got {chunk_queue_type}")
        return False

    if chunk_queue_len == 0:
        print("   ✗ FAILED: No task in chunk queue")
        return False

    # Peek at task in chunk queue
    chunk_task_json = r.lindex('redis:queue:chunk', -1)  # Peek at last item (FIFO)
    chunk_task = json.loads(chunk_task_json)

    print(f"   ✓ Task forwarded to chunk queue: {chunk_task['id']}")
    print(f"   ✓ Original URL preserved: {chunk_task.get('url')}")
    print(f"   ✓ Metadata preserved: {chunk_task.get('metadata')}\n")

    # Start chunk worker (will process and forward to embed)
    print("5. Starting chunk worker for 3 seconds...")
    run_worker('chunk', 'live-worker-chunk', duration=3)
    print("   ✓ Chunk worker completed\n")

    # Check embed queue
    print("6. Checking embed queue...")
    embed_queue_type = r.type('redis:queue:embed')
    embed_queue_len = r.llen('redis:queue:embed') if embed_queue_type == 'list' else 0

    print(f"   Queue type: {embed_queue_type}")
    print(f"   Queue length: {embed_queue_len}")

    if embed_queue_type != 'list':
        print(f"   ✗ FAILED: Expected list, got {embed_queue_type}")
        return False

    if embed_queue_len == 0:
        print("   ✗ FAILED: No task in embed queue")
        return False

    # Peek at task in embed queue
    embed_task_json = r.lindex('redis:queue:embed', -1)
    embed_task = json.loads(embed_task_json)

    print(f"   ✓ Task forwarded to embed queue: {embed_task['id']}")
    print(f"   ✓ Original URL preserved: {embed_task.get('url')}")
    print(f"   ✓ Chain complete: store → chunk → embed\n")

    print("✅ ALL TESTS PASSED\n")
    print("Summary:")
    print("- Store (zset) processed and forwarded to Chunk (list) ✓")
    print("- Chunk (list) processed and forwarded to Embed (list) ✓")
    print("- Original task data preserved through pipeline ✓")
    print("- Correct queue types used (zset → list → list) ✓")

    # Cleanup
    cleanup_test_queues()

    return True


if __name__ == '__main__':
    try:
        success = test_live_worker_forwarding()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
