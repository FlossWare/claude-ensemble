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
from task_queue_system import TaskQueue

# Global queue instance
_queue = None

def _get_queue():
    """Get or create TaskQueue instance"""
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue

def enqueue_task(task_type, task_data, priority=5):
    """Add a task to the PostgreSQL queue"""
    queue = _get_queue()
    return queue.add_task(priority, task_type, task_data)

def get_next_task(worker_id='default'):
    """Get next task from queue for this worker"""
    queue = _get_queue()
    return queue.claim_next_task(worker_id)

def complete_task(task_id, error_message=None):
    """Mark task as completed (or failed if error_message provided)"""
    queue = _get_queue()
    return queue.complete_task(task_id, error_message)

def get_queue_stats():
    """Get queue statistics"""
    queue = _get_queue()
    return queue.get_queue_stats()

if __name__ == '__main__':
    if '--test' in sys.argv:
        print('=== Testing Task Tools ===\n')

        passed = 0
        failed = 0

        try:
            print('Test 1: Import module...')
            queue = _get_queue()
            assert queue is not None
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
            assert callable(get_queue_stats)
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
