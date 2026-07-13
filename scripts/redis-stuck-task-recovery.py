#!/usr/bin/env python3
"""
Redis Stuck Task Recovery Job

Background job to scan for tasks with expired heartbeats and requeue them.
Runs continuously or as a cron job to prevent data loss from worker crashes.

Usage:
    # Run continuously (daemon mode)
    python3 redis-stuck-task-recovery.py --daemon --interval 60

    # Run once (cron mode)
    python3 redis-stuck-task-recovery.py --once

    # Custom thresholds
    python3 redis-stuck-task-recovery.py --daemon --stuck-threshold 180000
"""

import argparse
import time
import sys
import logging
from datetime import datetime
from redis_atomic_operations import RedisAtomicOps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class StuckTaskRecovery:
    def __init__(self, redis_host='aio-01', redis_port=6379,
                 stuck_threshold_ms=300000, stages=None):
        """
        Initialize stuck task recovery job.

        Args:
            redis_host: Redis host
            redis_port: Redis port
            stuck_threshold_ms: Time without heartbeat to consider stuck (default 5 min)
            stages: List of stages to monitor (default: ['store', 'chunk', 'embed', 'graph'])
        """
        self.ops = RedisAtomicOps(host=redis_host, port=redis_port)
        self.stuck_threshold_ms = stuck_threshold_ms
        self.stages = stages or ['store', 'chunk', 'embed', 'graph']

        self.stats = {
            'total_recovered': 0,
            'by_stage': {stage: 0 for stage in self.stages},
            'last_run': None,
            'run_count': 0
        }

    def recover_all_stages(self) -> int:
        """
        Scan all stages for stuck tasks and recover them.

        Returns:
            Total number of recovered tasks
        """
        total_recovered = 0

        logger.info(f"Starting stuck task recovery scan (threshold: {self.stuck_threshold_ms}ms)")

        for stage in self.stages:
            try:
                recovered = self.ops.recover_stuck_tasks(stage, self.stuck_threshold_ms)

                if recovered > 0:
                    logger.warning(f"Stage '{stage}': Recovered {recovered} stuck tasks")
                    self.stats['by_stage'][stage] += recovered
                    total_recovered += recovered
                else:
                    logger.debug(f"Stage '{stage}': No stuck tasks found")

            except Exception as e:
                logger.error(f"Error recovering stuck tasks in stage '{stage}': {e}")

        self.stats['total_recovered'] += total_recovered
        self.stats['last_run'] = datetime.utcnow().isoformat()
        self.stats['run_count'] += 1

        if total_recovered > 0:
            logger.info(f"Recovery complete: {total_recovered} tasks recovered")
        else:
            logger.info("Recovery complete: No stuck tasks found")

        return total_recovered

    def get_statistics(self) -> dict:
        """Get recovery statistics."""
        return {
            **self.stats,
            'stuck_threshold_ms': self.stuck_threshold_ms,
            'monitored_stages': self.stages
        }

    def print_statistics(self):
        """Print recovery statistics to log."""
        logger.info("=== Stuck Task Recovery Statistics ===")
        logger.info(f"Total runs: {self.stats['run_count']}")
        logger.info(f"Total recovered: {self.stats['total_recovered']}")
        logger.info(f"Last run: {self.stats['last_run']}")
        logger.info("By stage:")
        for stage, count in self.stats['by_stage'].items():
            logger.info(f"  - {stage}: {count}")
        logger.info("=" * 40)


def run_daemon(recovery: StuckTaskRecovery, interval_sec: int = 60):
    """
    Run recovery job in daemon mode (continuous loop).

    Args:
        recovery: StuckTaskRecovery instance
        interval_sec: Seconds between recovery scans (default 60)
    """
    logger.info(f"Starting stuck task recovery daemon (interval: {interval_sec}s)")

    try:
        while True:
            recovery.recover_all_stages()
            time.sleep(interval_sec)

    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
        recovery.print_statistics()
        sys.exit(0)

    except Exception as e:
        logger.error(f"Daemon crashed: {e}")
        recovery.print_statistics()
        sys.exit(1)


def run_once(recovery: StuckTaskRecovery):
    """
    Run recovery job once (cron mode).

    Args:
        recovery: StuckTaskRecovery instance
    """
    try:
        total_recovered = recovery.recover_all_stages()

        # Print statistics if any tasks recovered
        if total_recovered > 0:
            recovery.print_statistics()

        sys.exit(0)

    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Redis Stuck Task Recovery Job'
    )
    parser.add_argument('--daemon', action='store_true',
                       help='Run in daemon mode (continuous loop)')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit (cron mode)')
    parser.add_argument('--interval', type=int, default=60,
                       help='Seconds between scans in daemon mode (default: 60)')
    parser.add_argument('--stuck-threshold', type=int, default=300000,
                       help='Milliseconds without heartbeat to consider stuck (default: 300000 = 5 min)')
    parser.add_argument('--stages', nargs='+',
                       help='Stages to monitor (default: store chunk embed graph)')
    parser.add_argument('--redis-host', default='aio-01',
                       help='Redis host (default: aio-01)')
    parser.add_argument('--redis-port', type=int, default=6379,
                       help='Redis port (default: 6379)')

    args = parser.parse_args()

    # Validate mode
    if not args.daemon and not args.once:
        parser.error("Must specify either --daemon or --once")

    # Create recovery instance
    recovery = StuckTaskRecovery(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        stuck_threshold_ms=args.stuck_threshold,
        stages=args.stages
    )

    # Run in appropriate mode
    if args.daemon:
        run_daemon(recovery, args.interval)
    elif args.once:
        run_once(recovery)


if __name__ == '__main__':
    main()
