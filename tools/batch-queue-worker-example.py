#!/usr/bin/env python3
"""
Example Batch Queue Worker

Demonstrates how to use batch operations for efficient queue processing.

Features:
- Atomic batch claiming (10 tasks at once)
- Heartbeat updates during processing
- Automatic retry on failure
- Timeout handling

Usage:
    python3 batch-queue-worker-example.py --queue store --worker worker-01 --batch-size 10
"""

import argparse
import time
import sys
from typing import List, Dict, Any
from postgres_queue_batch import get_queue_batch


def process_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single task (placeholder implementation)

    Args:
        task: Task dictionary with id, data, etc.

    Returns:
        Result dictionary
    """
    print(f"  Processing task {task['id']}: {task['data'].get('url', 'unknown')}")

    # Simulate processing
    time.sleep(0.5)

    return {
        'task_id': task['id'],
        'status': 'success',
        'processed_at': time.time(),
    }


def process_batch(
    queue: Any,
    queue_name: str,
    worker_id: str,
    batch_size: int,
    heartbeat_interval: int = 30
) -> int:
    """
    Process a batch of tasks

    Args:
        queue: Queue batch instance
        queue_name: Queue name
        worker_id: Worker identifier
        batch_size: Number of tasks to claim
        heartbeat_interval: Heartbeat update interval (seconds)

    Returns:
        Number of tasks processed successfully
    """
    # Claim batch
    print(f"\n[{worker_id}] Claiming batch of {batch_size} tasks from {queue_name}...")
    tasks = queue.claim_batch(queue_name, worker_id, batch_size)

    if not tasks:
        print(f"[{worker_id}] No tasks available")
        return 0

    print(f"[{worker_id}] Claimed {len(tasks)} tasks")
    task_ids = [task['id'] for task in tasks]

    # Process tasks with heartbeat updates
    results = []
    last_heartbeat = time.time()
    failed_tasks = []

    for i, task in enumerate(tasks):
        try:
            # Update heartbeat if needed
            if time.time() - last_heartbeat > heartbeat_interval:
                print(f"[{worker_id}] Updating heartbeat...")
                queue.heartbeat_batch(queue_name, task_ids)
                last_heartbeat = time.time()

            # Process task
            result = process_task(task)
            results.append(result)

        except Exception as e:
            print(f"[{worker_id}] Task {task['id']} failed: {e}")
            failed_tasks.append(task['id'])

    # Complete successful tasks
    successful_ids = [r['task_id'] for r in results]
    if successful_ids:
        completed = queue.complete_batch(queue_name, successful_ids, {
            'batch_id': f"{worker_id}-{int(time.time())}",
            'results': results,
        })
        print(f"[{worker_id}] Completed {completed} tasks")

    # Fail unsuccessful tasks
    if failed_tasks:
        failed = queue.fail_batch(
            queue_name,
            failed_tasks,
            'Processing error',
            retry=True
        )
        print(f"[{worker_id}] Failed {failed} tasks (will retry)")

    return len(successful_ids)


def main():
    """Main worker loop"""
    parser = argparse.ArgumentParser(description='Batch queue worker')
    parser.add_argument('--queue', required=True, help='Queue name (store, chunk, embed, graph)')
    parser.add_argument('--worker', required=True, help='Worker identifier')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size (default: 10)')
    parser.add_argument('--poll-interval', type=int, default=5, help='Poll interval in seconds (default: 5)')
    parser.add_argument('--max-batches', type=int, default=0, help='Max batches to process (0 = infinite)')

    args = parser.parse_args()

    queue = get_queue_batch()
    batches_processed = 0

    print(f"Starting batch worker: {args.worker}")
    print(f"  Queue: {args.queue}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Poll interval: {args.poll_interval}s")

    try:
        while True:
            # Reclaim timed-out tasks
            reclaimed = queue.reclaim_timed_out(args.queue)
            if reclaimed > 0:
                print(f"\n[{args.worker}] Reclaimed {reclaimed} timed-out tasks")

            # Process batch
            processed = process_batch(
                queue,
                args.queue,
                args.worker,
                args.batch_size
            )

            if processed > 0:
                batches_processed += 1

            # Check if we've hit max batches
            if args.max_batches > 0 and batches_processed >= args.max_batches:
                print(f"\n[{args.worker}] Processed {batches_processed} batches, exiting")
                break

            # Show stats
            stats = queue.get_batch_stats(args.queue)
            print(f"\n[{args.worker}] Queue stats:")
            print(f"  Pending: {stats.get('pending', 0)}")
            print(f"  Processing: {stats.get('processing', 0)}")
            print(f"  Completed: {stats.get('completed', 0)}")
            print(f"  Failed: {stats.get('failed', 0)}")
            print(f"  Active workers: {stats.get('active_workers', 0)}")

            # Wait before next poll
            if processed == 0:
                print(f"\n[{args.worker}] Waiting {args.poll_interval}s...")
                time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        print(f"\n[{args.worker}] Interrupted by user")
    except Exception as e:
        print(f"\n[{args.worker}] Fatal error: {e}")
        sys.exit(1)
    finally:
        queue.close()


if __name__ == '__main__':
    main()
