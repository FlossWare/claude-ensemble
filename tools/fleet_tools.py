#!/usr/bin/env python3
"""
Fleet Tools Wrapper

Wires up fleet components:
- fleet_executor.py (#262)
- fleet_health_monitor.py (already tested in Issue #257)

Usage:
    from fleet_tools import execute_on_fleet, monitor_fleet_health
    results = execute_on_fleet(tasks, workers=['server-01', 'server-02'])

Test:
    python3 tools/fleet_tools.py --test
"""

import sys
from pathlib import Path

# Import fleet components
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import fleet_executor
sys.path.insert(0, str(Path(__file__).parent))
import fleet_health_monitor

def execute_on_fleet(tasks, workers=None, max_parallel=6, model='gpt-4o-mini'):
    """Execute tasks across fleet workers (Python alternative to JS orchestrator)"""
    if workers is None:
        workers = ['server-01', 'server-02', 'server-03', 'laptop-01', 'pi-01', 'pi-02']
    return fleet_executor.execute_on_fleet_parallel(
        workers=workers[:max_parallel],
        model=model,
        tasks=tasks,
        check_health=True
    )

def monitor_fleet_health(workers=None):
    """Get current health status of all fleet workers"""
    if workers is None:
        workers = ['server-01', 'server-02', 'server-03', 'laptop-01', 'pi-01', 'pi-02']

    results = {}
    for worker in workers:
        results[worker] = fleet_health_monitor.check_worker_health(worker)
    return results

def check_worker_health(worker_hostname):
    """Check health of a specific worker"""
    return fleet_health_monitor.check_worker_health(worker_hostname)

if __name__ == '__main__':
    if '--test' in sys.argv:
        print('=== Testing Fleet Tools ===\n')

        passed = 0
        failed = 0

        try:
            print('Test 1: Import modules...')
            assert fleet_executor is not None
            assert fleet_health_monitor is not None
            print('✓ All modules loaded\n')
            passed += 1
        except Exception as e:
            print(f'✗ Import failed: {e}\n')
            failed += 1

        try:
            print('Test 2: Check functions...')
            assert callable(execute_on_fleet)
            assert callable(monitor_fleet_health)
            assert callable(check_worker_health)
            print('✓ All functions available\n')
            passed += 1
        except Exception as e:
            print(f'✗ Function check failed: {e}\n')
            failed += 1

        print(f'\n=== Results: {passed} passed, {failed} failed ===')
        if failed == 0:
            print('✅ ALL TESTS PASSED')
            sys.exit(0)
        else:
            print('❌ SOME TESTS FAILED')
            sys.exit(1)
