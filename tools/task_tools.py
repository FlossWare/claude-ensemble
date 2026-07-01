#!/usr/bin/env python3
"""
Task Tools Wrapper

Wires up task queue component:
- task_queue_system.py (#254)

Usage:
    from task_tools import enqueue_task, get_next_task
    task_id = enqueue_task("process-data", {"file": "data.csv"})

Test:
    python3 tools/task_tools.py --test
"""

import sys
from pathlib import Path

# Import task queue
sys.path.insert(0, str(Path(__file__).parent))
import task_queue_system

def enqueue_task(task_type, task_data, priority=5):
    """Add a task to the PostgreSQL queue"""
    return task_queue_system.enqueue(task_type, task_data, priority)

def get_next_task(worker_id='default'):
    """Get next task from queue for this worker"""
    return task_queue_system.get_next(worker_id)

def complete_task(task_id, result_data):
    """Mark task as completed with result"""
    return task_queue_system.complete(task_id, result_data)

def fail_task(task_id, error_message):
    """Mark task as failed"""
    return task_queue_system.fail(task_id, error_message)

if __name__ == '__main__':
    if '--test' in sys.argv:
        print('=== Testing Task Tools ===\n')

        passed = 0
        failed = 0

        try:
            print('Test 1: Import module...')
            assert task_queue_system is not None
            print('✓ Module loaded\n')
            passed += 1
        except Exception as e:
            print(f'✗ Import failed: {e}\n')
            failed += 1

        try:
            print('Test 2: Check functions...')
            assert callable(enqueue_task)
            assert callable(get_next_task)
            assert callable(complete_task)
            assert callable(fail_task)
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
