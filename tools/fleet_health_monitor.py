#!/usr/bin/env python3
"""
Fleet Health Monitor - Check API worker health and auto-recovery
Monitors DYNAMIC workers from PostgreSQL fleet.workers registry
Auto-recovery after 3 consecutive failures
"""

import time
import subprocess
import json
import psycopg2
from datetime import datetime
from pathlib import Path

# Health check configuration
CHECK_INTERVAL = 60  # seconds
FAILURE_THRESHOLD = 3
RECOVERY_WAIT = 300  # 5 minutes

# State tracking (populated dynamically from registry)
health_state = {}

def get_active_workers(conn):
    """Get list of active workers from PostgreSQL fleet.workers registry"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT hostname
            FROM fleet.workers
            WHERE status IN ('active', 'degraded')
              AND last_heartbeat > NOW() - INTERVAL '5 minutes'
            ORDER BY hostname
        """)
        workers = [row[0] for row in cursor.fetchall()]
        cursor.close()

        # Initialize health_state for new workers
        for worker in workers:
            if worker not in health_state:
                health_state[worker] = {
                    "consecutive_failures": 0,
                    "last_success": None,
                    "recovering": False
                }

        return workers
    except Exception as e:
        print(f"  ⚠️  Failed to get workers from registry: {e}")
        return []

def check_worker_health(worker):
    """Check if worker is reachable and responsive"""
    start = time.time()
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'LogLevel=ERROR', f'claude@{worker}', 'echo', 'OK'],
            capture_output=True,
            text=True,
            timeout=10
        )
        duration_ms = int((time.time() - start) * 1000)

        if result.returncode == 0 and 'OK' in result.stdout:
            return {'status': 'healthy', 'duration_ms': duration_ms, 'error': None}
        else:
            return {'status': 'unhealthy', 'duration_ms': duration_ms, 'error': f'Exit code {result.returncode}'}
    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'duration_ms': 10000, 'error': 'SSH timeout'}
    except Exception as e:
        return {'status': 'error', 'duration_ms': int((time.time() - start) * 1000), 'error': str(e)}

def store_health_check(conn, worker, status, duration_ms, error):
    """Store health check result to PostgreSQL"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO monitoring.health_checks
            (worker_id, status, response_time_ms, error_message, checked_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (worker, status, duration_ms, error))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"  ⚠️  Failed to store health check: {e}")
        conn.rollback()

def attempt_recovery(worker):
    """Attempt to recover failed worker"""
    print(f"  🔧 Attempting recovery for {worker}...")

    # Try to restart SSH service (if we have sudo)
    try:
        subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', f'root@{worker}', 'systemctl', 'restart', 'sshd'],
            capture_output=True,
            timeout=10
        )
        print(f"  ✓ Restarted SSH service on {worker}")
        return True
    except:
        print(f"  ✗ Could not restart SSH on {worker}")
        return False

def main():
    print("="*60)
    print("FLEET HEALTH MONITOR STARTED (Dynamic Registry)")
    print(f"Checking workers every {CHECK_INTERVAL}s")
    print("="*60)

    # Create health_checks table if not exists
    conn = psycopg2.connect(host="aio-01", port=5433, database="learning", user="claude")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.health_checks (
            id SERIAL PRIMARY KEY,
            worker_id TEXT NOT NULL,
            status TEXT NOT NULL,
            response_time_ms INTEGER,
            error_message TEXT,
            checked_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cursor.close()

    try:
        while True:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Health Check Cycle")
            print("-" * 60)

            # Get current active workers from registry (dynamic!)
            workers = get_active_workers(conn)
            print(f"Monitoring {len(workers)} workers from registry: {', '.join(workers)}")

            for worker in workers:
                result = check_worker_health(worker)
                state = health_state[worker]

                if result['status'] == 'healthy':
                    # Reset failure count on success
                    if state['consecutive_failures'] > 0:
                        print(f"  ✅ {worker}: RECOVERED (was down {state['consecutive_failures']} checks)")
                    else:
                        print(f"  ✅ {worker}: OK ({result['duration_ms']}ms)")

                    state['consecutive_failures'] = 0
                    state['last_success'] = datetime.now()
                    state['recovering'] = False

                else:
                    # Increment failure count
                    state['consecutive_failures'] += 1
                    print(f"  ❌ {worker}: {result['status'].upper()} ({state['consecutive_failures']}/{FAILURE_THRESHOLD} failures)")

                    # Attempt recovery after threshold
                    if state['consecutive_failures'] >= FAILURE_THRESHOLD and not state['recovering']:
                        state['recovering'] = True
                        if attempt_recovery(worker):
                            state['consecutive_failures'] = 0  # Reset after recovery attempt
                            state['recovering'] = False

                # Store to PostgreSQL
                store_health_check(conn, worker, result['status'], result['duration_ms'], result['error'])

            # Summary
            healthy = sum(1 for s in health_state.values() if s['consecutive_failures'] == 0)
            print(f"\n📊 Fleet Status: {healthy}/{len(workers)} workers healthy")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nShutting down health monitor...")
        conn.close()

if __name__ == "__main__":
    main()
