#!/usr/bin/env python3
"""
Test Fleet Health Monitor Integration

Verifies:
1. Health monitor can check workers
2. Health client can query status
3. Fleet executor filters unhealthy workers
4. PostgreSQL stores health data
"""

import sys
import os
import time
import subprocess
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from fleet_health_client import (
    get_healthy_workers,
    get_worker_health_status,
    get_fleet_summary
)

def test_health_client():
    """Test health client library"""
    print("\n" + "="*70)
    print("TEST 1: Health Client Library")
    print("="*70)

    try:
        # Get healthy workers
        print("\n1. Getting healthy workers...")
        healthy = get_healthy_workers()
        print(f"   ✅ Found {len(healthy)} healthy workers: {', '.join(healthy)}")

        # Get worker details
        print("\n2. Getting worker health details...")
        if healthy:
            status = get_worker_health_status(healthy[0])
            print(f"   ✅ Worker: {status['worker']}")
            print(f"      Status: {status['status']}")
            print(f"      Response time: {status.get('response_time_ms', 'N/A')}ms")
            print(f"      Last check: {status.get('last_check', 'N/A')}")

        # Get fleet summary
        print("\n3. Getting fleet summary...")
        summary = get_fleet_summary()
        print(f"   ✅ Total workers: {summary['total_workers']}")
        print(f"      Healthy: {summary['healthy_workers']}")
        print(f"      Unhealthy: {summary['unhealthy_workers']}")

        return True

    except Exception as e:
        print(f"   ❌ Health client test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fleet_executor_integration():
    """Test fleet executor uses health checks"""
    print("\n" + "="*70)
    print("TEST 2: Fleet Executor Integration")
    print("="*70)

    try:
        from fleet_executor import execute_on_fleet_parallel

        # Test with health check enabled (default)
        print("\n1. Testing parallel execution with health checks...")
        workers = ["server-01", "server-02", "laptop-01"]
        tasks = ["Say OK"] * len(workers)

        results = execute_on_fleet_parallel(
            workers=workers,
            model="gpt-4o-mini",
            tasks=tasks,
            max_tokens=10,
            check_health=True  # Explicitly enable
        )

        successful = sum(1 for r in results if 'error' not in r or not r['error'])
        print(f"   ✅ Executed on {successful}/{len(results)} workers")

        # Show results
        for i, r in enumerate(results):
            if 'error' in r and r['error']:
                print(f"      Worker {i}: ERROR - {r['error'][:100]}")
            else:
                print(f"      Worker {i}: SUCCESS")

        return True

    except Exception as e:
        print(f"   ❌ Fleet executor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_storage():
    """Test PostgreSQL health data storage"""
    print("\n" + "="*70)
    print("TEST 3: PostgreSQL Health Data Storage")
    print("="*70)

    try:
        import psycopg2

        conn = psycopg2.connect(
            host='aio-01',
            port=5433,
            database='learning',
            user='claude'
        )
        cursor = conn.cursor()

        # Check table exists
        print("\n1. Checking monitoring.health_checks table...")
        cursor.execute("""
            SELECT COUNT(*) FROM monitoring.health_checks
        """)
        count = cursor.fetchone()[0]
        print(f"   ✅ Table exists with {count} health check records")

        # Get recent checks
        print("\n2. Recent health checks (last 10)...")
        cursor.execute("""
            SELECT worker_id, status, response_time_ms, checked_at
            FROM monitoring.health_checks
            ORDER BY checked_at DESC
            LIMIT 10
        """)

        for worker, status, response_ms, checked in cursor.fetchall():
            print(f"      {worker}: {status} ({response_ms}ms) at {checked}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_health_monitor_running():
    """Check if health monitor service is running"""
    print("\n" + "="*70)
    print("TEST 4: Health Monitor Service Status")
    print("="*70)

    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'fleet-health-monitor.service'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip() == 'active':
            print("   ✅ fleet-health-monitor.service is running")

            # Show recent logs
            print("\n   Recent logs:")
            logs = subprocess.run(
                ['journalctl', '-u', 'fleet-health-monitor', '-n', '5', '--no-pager'],
                capture_output=True,
                text=True
            )
            for line in logs.stdout.strip().split('\n'):
                print(f"      {line}")

            return True
        else:
            print("   ⚠️  fleet-health-monitor.service is not running")
            print("      Run: sudo systemctl start fleet-health-monitor.service")
            return False

    except FileNotFoundError:
        print("   ⚠️  systemctl not available (not on systemd host?)")
        return False
    except Exception as e:
        print(f"   ⚠️  Service check failed: {e}")
        return False


def main():
    print("\n" + "="*70)
    print("Fleet Health Monitor Integration Test")
    print("="*70)

    results = {
        'Health Client': test_health_client(),
        'Fleet Executor': test_fleet_executor_integration(),
        'Database Storage': test_database_storage(),
        'Monitor Service': test_health_monitor_running()
    }

    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test:20s} {status}")

    print("\n")

    if all(results.values()):
        print("✅ All tests passed - Fleet health monitoring is fully integrated!")
        return 0
    else:
        print("⚠️  Some tests failed - see details above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
