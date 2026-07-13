#!/usr/bin/env python3
"""
Redis Queue Worker with Atomic Operations

Uses Lua scripts for race-condition-free queue operations.
Supports heartbeat updates, graceful shutdown, batch claiming, and HYBRID queue mode.

Queue Modes:
    - zset: Priority queues using sorted sets (ZPOPMIN/ZPOPMAX)
            Best for: Priority-based task processing
            Example: High-priority scraping tasks first

    - list: FIFO queues using lists (RPOP/LPUSH)
            Best for: Strict ordering, sequential processing
            Example: Processing pipeline stages in order

Usage:
    # Store stage (auto-detects ZPOPMIN priority queue)
    python3 redis-worker-with-atomic-ops.py --worker-id worker-1 --stage store

    # Chunk/Embed/Graph stages (auto-detect BRPOP FIFO queue)
    python3 redis-worker-with-atomic-ops.py --worker-id worker-2 --stage chunk --batch-size 5
    python3 redis-worker-with-atomic-ops.py --worker-id worker-3 --stage embed
    python3 redis-worker-with-atomic-ops.py --worker-id worker-4 --stage graph

    # Override queue mode if needed
    python3 redis-worker-with-atomic-ops.py --worker-id worker-5 --stage store --queue-mode list
"""

import argparse
import signal
import sys
import time
import json
import logging
from typing import Optional, List
from datetime import datetime
from redis_atomic_operations import RedisAtomicOps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


class RedisWorker:
    def __init__(self, worker_id: str, stage: str, redis_host='aio-01',
                 redis_port=6379, batch_size=1, heartbeat_interval_sec=60,
                 max_retries=3, queue_mode=None):
        """
        Initialize Redis worker with atomic operations.

        Args:
            worker_id: Unique worker identifier
            stage: Stage name ('store', 'chunk', 'embed', 'graph')
            redis_host: Redis host
            redis_port: Redis port
            batch_size: Number of tasks to claim at once (1 = single, 5-10 = batch)
            heartbeat_interval_sec: Seconds between heartbeat updates
            max_retries: Max retries before dead letter queue
            queue_mode: Queue type override (None = auto-detect based on stage)
                       - 'zset' for priority queues (ZPOPMIN)
                       - 'list' for FIFO queues (BRPOP/RPOP)
        """
        self.worker_id = worker_id
        self.stage = stage
        self.batch_size = batch_size
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.max_retries = max_retries

        # Create worker-specific logger
        self.logger = logging.getLogger(f"{__name__}.{worker_id}")

        # Auto-detect queue mode based on stage (unless overridden)
        if queue_mode is None:
            # store queue uses priority (sorted set with ZPOPMIN)
            # chunk/embed/graph queues use FIFO (list with BRPOP)
            self.queue_mode = 'zset' if stage == 'store' else 'list'
        else:
            self.queue_mode = queue_mode

        self.ops = RedisAtomicOps(host=redis_host, port=redis_port)

        # Track claimed tasks for heartbeat updates and graceful shutdown
        self.claimed_tasks = {}  # task_id -> {'task': task_dict, 'last_heartbeat': timestamp}

        # Shutdown flag
        self.shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        signal.signal(signal.SIGINT, self._shutdown_handler)

        # Stats
        self.stats = {
            'claimed': 0,
            'completed': 0,
            'failed': 0,
            'dead_letter': 0,
            'heartbeats_sent': 0,
            'start_time': datetime.utcnow().isoformat()
        }

        # Determine queue names
        if stage == 'store':
            # Store stage has priority-based queues
            self.queue_names = [
                'redis:queue:store:high',
                'redis:queue:store:medium',
                'redis:queue:store:low'
            ]
        else:
            # Other stages have single queue
            self.queue_names = [f'redis:queue:{stage}']

        # Next stage queue and mode
        self.next_stage_map = {
            'store': ('redis:queue:chunk', 'list'),  # chunk uses FIFO
            'chunk': ('redis:queue:embed', 'list'),  # embed uses FIFO
            'embed': ('redis:queue:graph', 'list'),  # graph uses FIFO
            'graph': (None, None)  # Terminal stage
        }
        next_stage_info = self.next_stage_map.get(stage, (None, None))
        self.next_queue = next_stage_info[0]
        self.next_queue_mode = next_stage_info[1]

        self.logger.info(f"Worker initialized: stage={stage}, batch_size={batch_size}, queue_mode={self.queue_mode}, next_queue={self.next_queue}, next_queue_mode={self.next_queue_mode}, queues={self.queue_names}")

    def _shutdown_handler(self, signum, frame):
        """Handle graceful shutdown."""
        self.logger.warning(f"Shutdown signal received (signal={signum})")
        self.shutdown_requested = True

    def _graceful_shutdown(self):
        """Release all claimed tasks back to queue."""
        self.logger.info(f"Graceful shutdown: Releasing {len(self.claimed_tasks)} claimed tasks")

        for task_id, task_info in list(self.claimed_tasks.items()):
            try:
                result = self.ops.fail_task(
                    task_id,
                    self.worker_id,
                    'Worker shutting down',
                    stage=self.stage,
                    max_retries=self.max_retries + 1  # Extra retry for graceful shutdown
                )
                self.logger.info(f"Released task {task_id}: {result}")
            except Exception as e:
                self.logger.error(f"Error releasing task {task_id}: {e}")

        self.logger.info("Graceful shutdown complete")
        self._print_stats()

    def _print_stats(self):
        """Print worker statistics."""
        runtime_sec = (datetime.utcnow() - datetime.fromisoformat(self.stats['start_time'])).total_seconds()
        throughput = self.stats['completed'] / runtime_sec if runtime_sec > 0 else 0

        self.logger.info("=== Worker Statistics ===")
        self.logger.info(f"Worker ID: {self.worker_id}")
        self.logger.info(f"Stage: {self.stage}")
        self.logger.info(f"Runtime: {runtime_sec:.1f}s")
        self.logger.info(f"Claimed: {self.stats['claimed']}")
        self.logger.info(f"Completed: {self.stats['completed']}")
        self.logger.info(f"Failed (requeued): {self.stats['failed']}")
        self.logger.info(f"Dead letter: {self.stats['dead_letter']}")
        self.logger.info(f"Heartbeats sent: {self.stats['heartbeats_sent']}")
        self.logger.info(f"Throughput: {throughput:.2f} tasks/sec")
        self.logger.info("=" * 30)

    def claim_tasks(self) -> List[dict]:
        """
        Claim tasks from queues (priority order for store stage).

        Returns:
            List of claimed tasks
        """
        if self.batch_size == 1:
            # Single-task claim (try priority queues in order)
            for queue_name in self.queue_names:
                task = self.ops.claim_task(queue_name, self.worker_id, queue_mode=self.queue_mode)
                if task:
                    self.claimed_tasks[task['id']] = {
                        'task': task,
                        'last_heartbeat': time.time()
                    }
                    self.stats['claimed'] += 1
                    return [task]
            return []
        else:
            # Batch claim (try priority queues in order)
            for queue_name in self.queue_names:
                tasks = self.ops.batch_claim_tasks(queue_name, self.worker_id, self.batch_size, queue_mode=self.queue_mode)
                if tasks:
                    for task in tasks:
                        self.claimed_tasks[task['id']] = {
                            'task': task,
                            'last_heartbeat': time.time()
                        }
                    self.stats['claimed'] += len(tasks)
                    return tasks
            return []

    def process_task(self, task: dict) -> dict:
        """
        Process a task (implement stage-specific logic here).

        Args:
            task: Task dict

        Returns:
            Result dict for next stage
        """
        # Placeholder: Replace with actual processing logic
        self.logger.info(f"Processing task {task['id']} (priority={task.get('priority', 'N/A')})")

        # Simulate processing
        time.sleep(0.1)

        # Build result for next stage
        result = {
            'id': task['id'],
            'data': task.get('data', {}),
            'source_stage': self.stage,
            'processed_by': self.worker_id,
            'processed_at': datetime.utcnow().isoformat()
        }

        return result

    def update_heartbeats(self):
        """Update heartbeats for all claimed tasks."""
        current_time = time.time()

        for task_id, task_info in list(self.claimed_tasks.items()):
            last_heartbeat = task_info['last_heartbeat']

            # Update heartbeat if interval elapsed
            if current_time - last_heartbeat >= self.heartbeat_interval_sec:
                try:
                    result = self.ops.update_heartbeat(task_id, self.worker_id, self.stage)
                    if result == 'OK':
                        task_info['last_heartbeat'] = current_time
                        self.stats['heartbeats_sent'] += 1
                    else:
                        self.logger.warning(f"Heartbeat update failed for task {task_id}: {result}")
                except Exception as e:
                    self.logger.error(f"Error updating heartbeat for task {task_id}: {e}")

    def run(self):
        """Main worker loop."""
        self.logger.info(f"Worker starting: {self.worker_id} (stage={self.stage})")

        last_heartbeat_check = time.time()

        try:
            while not self.shutdown_requested:
                # Claim tasks
                tasks = self.claim_tasks()

                if not tasks:
                    # No tasks available, sleep briefly
                    time.sleep(1)

                    # Update heartbeats during idle time
                    current_time = time.time()
                    if current_time - last_heartbeat_check >= 10:  # Check every 10s
                        self.update_heartbeats()
                        last_heartbeat_check = current_time

                    continue

                # Process each task
                for task in tasks:
                    task_id = task['id']

                    try:
                        # Process task
                        result = self.process_task(task)

                        # Complete task (atomic)
                        result_json = json.dumps(result)
                        status = self.ops.complete_task(
                            task_id,
                            self.worker_id,
                            result_json,
                            stage=self.stage,
                            next_queue=self.next_queue,
                            next_queue_mode=self.next_queue_mode or 'list'
                        )

                        if status == 'OK':
                            self.logger.info(f"Completed task {task_id}")
                            self.stats['completed'] += 1
                            del self.claimed_tasks[task_id]
                        else:
                            self.logger.error(f"Complete failed for task {task_id}: {status}")

                    except Exception as e:
                        # Fail task (atomic, requeue or DLQ)
                        self.logger.error(f"Error processing task {task_id}: {e}")

                        try:
                            status = self.ops.fail_task(
                                task_id,
                                self.worker_id,
                                str(e),
                                stage=self.stage,
                                max_retries=self.max_retries
                            )

                            if status == 'REQUEUED':
                                self.logger.info(f"Requeued task {task_id} for retry")
                                self.stats['failed'] += 1
                            elif status == 'DEAD_LETTER':
                                self.logger.warning(f"Moved task {task_id} to dead letter queue")
                                self.stats['dead_letter'] += 1
                            else:
                                self.logger.error(f"Fail operation failed for task {task_id}: {status}")

                            del self.claimed_tasks[task_id]

                        except Exception as fail_error:
                            self.logger.error(f"Error failing task {task_id}: {fail_error}")

                # Update heartbeats after processing batch
                self.update_heartbeats()
                last_heartbeat_check = time.time()

        except KeyboardInterrupt:
            self.logger.warning("Worker interrupted by user")

        except Exception as e:
            self.logger.error(f"Worker crashed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self._graceful_shutdown()


def main():
    parser = argparse.ArgumentParser(description='Redis Queue Worker with Atomic Operations')
    parser.add_argument('--worker-id', required=True, help='Unique worker identifier')
    parser.add_argument('--stage', required=True, choices=['store', 'chunk', 'embed', 'graph'],
                       help='Processing stage')
    parser.add_argument('--batch-size', type=int, default=1,
                       help='Number of tasks to claim at once (default: 1)')
    parser.add_argument('--heartbeat-interval', type=int, default=60,
                       help='Seconds between heartbeat updates (default: 60)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Max retries before dead letter queue (default: 3)')
    parser.add_argument('--queue-mode', default=None, choices=['zset', 'list'],
                       help='Queue type override: zset for priority (ZPOPMIN), list for FIFO (BRPOP). Default: auto-detect (store=zset, others=list)')
    parser.add_argument('--redis-host', default='aio-01', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')

    args = parser.parse_args()

    # Add worker_id to logger
    logger = logging.LoggerAdapter(logging.getLogger(__name__), {'worker_id': args.worker_id})

    worker = RedisWorker(
        worker_id=args.worker_id,
        stage=args.stage,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        batch_size=args.batch_size,
        heartbeat_interval_sec=args.heartbeat_interval,
        max_retries=args.max_retries,
        queue_mode=args.queue_mode
    )

    worker.run()


if __name__ == '__main__':
    main()
