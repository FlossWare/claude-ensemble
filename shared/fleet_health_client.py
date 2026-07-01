#!/usr/bin/env python3
"""
Fleet Health Client - Query fleet health status
Used by orchestration layer to check worker availability before dispatching tasks
"""

import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# PostgreSQL connection config
DB_CONFIG = {
    'host': 'aio-01',
    'port': 5433,
    'database': 'learning',
    'user': 'claude'
}

def get_healthy_workers(max_failures: int = 2, max_age_seconds: int = 300) -> List[str]:
    """
    Get list of currently healthy workers

    Args:
        max_failures: Maximum consecutive failures to still consider healthy
        max_age_seconds: Maximum age of last check (default 5 minutes)

    Returns:
        List of healthy worker hostnames
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)

    try:
        cursor.execute("""
            SELECT DISTINCT worker_id
            FROM monitoring.health_checks
            WHERE checked_at > %s
              AND status = 'healthy'
            ORDER BY worker_id
        """, (cutoff_time,))

        healthy = [row[0] for row in cursor.fetchall()]

        # Get workers with too many consecutive failures
        cursor.execute("""
            WITH latest_checks AS (
                SELECT worker_id, status, checked_at,
                       ROW_NUMBER() OVER (PARTITION BY worker_id ORDER BY checked_at DESC) as rn
                FROM monitoring.health_checks
                WHERE checked_at > %s
            ),
            consecutive_failures AS (
                SELECT worker_id, COUNT(*) as failure_count
                FROM latest_checks
                WHERE status != 'healthy' AND rn <= %s
                GROUP BY worker_id
            )
            SELECT worker_id FROM consecutive_failures WHERE failure_count >= %s
        """, (cutoff_time, max_failures + 1, max_failures))

        unhealthy = {row[0] for row in cursor.fetchall()}

        # Filter out unhealthy workers
        return [w for w in healthy if w not in unhealthy]

    finally:
        cursor.close()
        conn.close()


def get_worker_health_status(worker: str) -> Dict[str, any]:
    """
    Get detailed health status for a specific worker

    Args:
        worker: Worker hostname

    Returns:
        Dict with status, last_check, consecutive_failures, avg_response_time
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Get latest check
        cursor.execute("""
            SELECT status, response_time_ms, error_message, checked_at
            FROM monitoring.health_checks
            WHERE worker_id = %s
            ORDER BY checked_at DESC
            LIMIT 1
        """, (worker,))

        row = cursor.fetchone()
        if not row:
            return {
                'worker': worker,
                'status': 'unknown',
                'error': 'No health checks found'
            }

        status, response_time_ms, error_message, checked_at = row

        # Count consecutive failures
        cursor.execute("""
            WITH ordered_checks AS (
                SELECT status, checked_at,
                       ROW_NUMBER() OVER (ORDER BY checked_at DESC) as rn
                FROM monitoring.health_checks
                WHERE worker_id = %s
            )
            SELECT COUNT(*) FROM ordered_checks
            WHERE status != 'healthy' AND rn <= 10
        """, (worker,))

        consecutive_failures = cursor.fetchone()[0]

        # Get average response time (last 20 successful checks)
        cursor.execute("""
            SELECT AVG(response_time_ms)
            FROM (
                SELECT response_time_ms
                FROM monitoring.health_checks
                WHERE worker_id = %s AND status = 'healthy'
                ORDER BY checked_at DESC
                LIMIT 20
            ) recent
        """, (worker,))

        avg_response = cursor.fetchone()[0]

        return {
            'worker': worker,
            'status': status,
            'last_check': checked_at.isoformat() if checked_at else None,
            'response_time_ms': response_time_ms,
            'avg_response_time_ms': float(avg_response) if avg_response else None,
            'consecutive_failures': consecutive_failures,
            'error': error_message,
            'healthy': status == 'healthy' and consecutive_failures < 3
        }

    finally:
        cursor.close()
        conn.close()


def get_fleet_summary() -> Dict[str, any]:
    """
    Get overall fleet health summary

    Returns:
        Dict with total_workers, healthy_workers, unhealthy_workers, worker_details
    """
    workers = [
        "server-01", "server-02", "server-03",
        "laptop-01", "pi-01", "pi-02",
        "server-ap", "desktop-ap"
    ]

    healthy = get_healthy_workers()
    details = {w: get_worker_health_status(w) for w in workers}

    return {
        'total_workers': len(workers),
        'healthy_workers': len(healthy),
        'unhealthy_workers': len(workers) - len(healthy),
        'healthy_worker_list': healthy,
        'worker_details': details,
        'timestamp': datetime.now().isoformat()
    }


if __name__ == '__main__':
    import json
    summary = get_fleet_summary()
    print(json.dumps(summary, indent=2, default=str))
