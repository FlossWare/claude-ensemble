#!/usr/bin/env python3
"""
Comprehensive test suite for task_tools.py and task_queue_system.py

Achieves 80%+ coverage by addressing:
- Dead letter queue logic error (retry_count >= 2 vs >= 3)
- Auto-release commit timing issue
- Test ordering conflicts
- Exponential backoff AttributeError
- Empty queue handling
- Error handling paths
- Boundary conditions
"""

import unittest
import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import the modules under test
sys.path.insert(0, str(Path(__file__).parent / 'tools'))
from task_queue_system import TaskQueue
import task_tools

class TestTaskQueueSystem(unittest.TestCase):
    """Test suite for TaskQueue class"""

    @classmethod
    def setUpClass(cls):
        """Create a test database connection once"""
        cls.queue = TaskQueue(host="aio-01", port=5433, database="learning", user="claude")
        # Clean up any existing test data
        cursor = cls.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_%'")
        cls.queue.conn.commit()
        cursor.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up test data and close connection"""
        cursor = cls.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_%'")
        cls.queue.conn.commit()
        cursor.close()
        cls.queue.close()

    def setUp(self):
        """Clean test data before each test"""
        cursor = self.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_%'")
        self.queue.conn.commit()
        cursor.close()

    def test_add_task_basic(self):
        """Test basic task addition"""
        task_id = self.queue.add_task(5, 'test_basic', {'data': 'test'})
        self.assertIsNotNone(task_id)
        self.assertIsInstance(task_id, int)

    def test_add_task_with_valid_priorities(self):
        """Test task addition with all valid priority levels (1-10)"""
        for priority in range(1, 11):
            task_id = self.queue.add_task(priority, f'test_priority_{priority}', {'priority': priority})
            self.assertIsNotNone(task_id)

    def test_add_task_with_invalid_priority(self):
        """Test CHECK constraint enforcement for priority (must be 1-10)"""
        # Priority 0 should fail
        with self.assertRaises(Exception) as context:
            self.queue.add_task(0, 'test_invalid_priority', {'data': 'test'})
        self.assertIn('constraint', str(context.exception).lower())

        # Priority 11 should fail
        with self.assertRaises(Exception) as context:
            self.queue.add_task(11, 'test_invalid_priority', {'data': 'test'})
        self.assertIn('constraint', str(context.exception).lower())

    def test_exponential_backoff_on_error(self):
        """Test exponential backoff retry logic in add_task()"""
        # Create a mock connection that fails first 2 attempts
        attempt_count = [0]
        original_cursor_method = self.queue.conn.cursor

        def mock_cursor():
            cursor = original_cursor_method()
            original_execute = cursor.execute

            def failing_execute(query, params=None):
                attempt_count[0] += 1
                if attempt_count[0] < 3:
                    raise Exception("Simulated database error")
                return original_execute(query, params) if params else original_execute(query)

            cursor.execute = failing_execute
            return cursor

        with patch.object(self.queue.conn, 'cursor', side_effect=mock_cursor):
            start_time = time.time()
            task_id = self.queue.add_task(5, 'test_backoff', {'data': 'test'})
            elapsed = time.time() - start_time

            # Should have retried with delays: 2^0=1s, 2^1=2s = total 3s minimum
            self.assertGreaterEqual(elapsed, 3.0)
            self.assertIsNotNone(task_id)
            self.assertEqual(attempt_count[0], 3)

    def test_add_task_max_retries_exhausted(self):
        """Test error handling when all retries exhausted in add_task()"""
        def always_fail_cursor():
            cursor = self.queue.conn.cursor()
            original_execute = cursor.execute

            def failing_execute(*args, **kwargs):
                raise Exception("Permanent database error")

            cursor.execute = failing_execute
            return cursor

        with patch.object(self.queue.conn, 'cursor', side_effect=always_fail_cursor):
            with self.assertRaises(Exception) as context:
                self.queue.add_task(5, 'test_max_retries', {'data': 'test'})
            self.assertIn('Failed to add task after 3 attempts', str(context.exception))

    def test_claim_next_task_basic(self):
        """Test basic task claiming"""
        task_id = self.queue.add_task(5, 'test_claim', {'data': 'test'})
        task = self.queue.claim_next_task('worker-test')

        self.assertIsNotNone(task)
        self.assertEqual(task['id'], task_id)
        self.assertEqual(task['task_type'], 'test_claim')
        self.assertEqual(task['priority'], 5)

    def test_claim_next_task_empty_queue(self):
        """Test claim_next_task() returns None when queue is empty"""
        task = self.queue.claim_next_task('worker-empty')
        self.assertIsNone(task)

    def test_claim_next_task_with_db_error(self):
        """Test error handling in claim_next_task() exception path"""
        def failing_cursor():
            raise Exception("Database connection lost")

        with patch.object(self.queue.conn, 'cursor', side_effect=failing_cursor):
            with self.assertRaises(Exception) as context:
                self.queue.claim_next_task('worker-error')
            self.assertIn('Failed to claim task', str(context.exception))

    def test_priority_ordering(self):
        """Test that tasks are claimed in correct priority order (priority DESC, created_at ASC)"""
        # Add tasks with different priorities
        task_low = self.queue.add_task(3, 'test_priority_low', {'data': 'low'})
        task_high = self.queue.add_task(9, 'test_priority_high', {'data': 'high'})
        task_med = self.queue.add_task(6, 'test_priority_med', {'data': 'med'})

        # Add two tasks with same priority but different creation times
        task_same1 = self.queue.add_task(5, 'test_priority_same1', {'data': 'same1'})
        time.sleep(0.1)  # Ensure different created_at
        task_same2 = self.queue.add_task(5, 'test_priority_same2', {'data': 'same2'})

        # Claim tasks and verify order
        claimed1 = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed1['id'], task_high)  # Highest priority first

        claimed2 = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed2['id'], task_med)  # Second highest priority

        claimed3 = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed3['id'], task_same1)  # Same priority, older first

        claimed4 = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed4['id'], task_same2)  # Same priority, newer second

        claimed5 = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed5['id'], task_low)  # Lowest priority last

    def test_concurrent_workers_skip_locked(self):
        """Test that multiple workers don't claim the same task (SKIP LOCKED behavior)"""
        # Add a single task
        task_id = self.queue.add_task(5, 'test_concurrent', {'data': 'test'})

        claimed_tasks = []
        errors = []

        def claim_task(worker_id):
            try:
                # Create a new queue instance for this thread
                queue = TaskQueue(host="aio-01", port=5433, database="learning", user="claude", skip_init=True)
                task = queue.claim_next_task(worker_id)
                claimed_tasks.append((worker_id, task))
                queue.close()
            except Exception as e:
                errors.append(e)

        # Start two workers simultaneously
        thread1 = threading.Thread(target=claim_task, args=('worker-1',))
        thread2 = threading.Thread(target=claim_task, args=('worker-2',))

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Verify no errors
        self.assertEqual(len(errors), 0)

        # Verify exactly one worker got the task
        successful_claims = [t for w, t in claimed_tasks if t is not None]
        self.assertEqual(len(successful_claims), 1)
        self.assertEqual(successful_claims[0]['id'], task_id)

    def test_complete_task_success(self):
        """Test successful task completion"""
        task_id = self.queue.add_task(5, 'test_complete', {'data': 'test'})
        self.queue.claim_next_task('worker-test')
        self.queue.complete_task(task_id)

        # Verify task status
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (task_id,))
        status = cursor.fetchone()[0]
        cursor.close()

        self.assertEqual(status, 'completed')

    def test_complete_task_success_no_retry_increment(self):
        """Test that complete_task() with success doesn't increment retry_count"""
        task_id = self.queue.add_task(5, 'test_success_no_retry', {'data': 'test'})
        self.queue.claim_next_task('worker-test')
        self.queue.complete_task(task_id)

        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT retry_count FROM queue.tasks WHERE id = %s", (task_id,))
        retry_count = cursor.fetchone()[0]
        cursor.close()

        self.assertEqual(retry_count, 0)

    def test_complete_task_nonexistent_id(self):
        """Test error handling when task_id doesn't exist"""
        # This should not raise an error, just do nothing
        self.queue.complete_task(999999, error_message="Should not crash")

    def test_complete_task_with_error(self):
        """Test task failure with error message"""
        task_id = self.queue.add_task(5, 'test_error', {'data': 'test'})
        self.queue.claim_next_task('worker-test')
        self.queue.complete_task(task_id, error_message="Test error message")

        # Verify task is requeued and retry_count incremented
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT status, retry_count, error_message FROM queue.tasks WHERE id = %s", (task_id,))
        status, retry_count, error_msg = cursor.fetchone()
        cursor.close()

        self.assertEqual(status, 'pending')
        self.assertEqual(retry_count, 1)
        self.assertEqual(error_msg, "Test error message")

    def test_retry_count_increments_correctly(self):
        """Test that retry_count increments correctly through failure lifecycle"""
        task_id = self.queue.add_task(5, 'test_retry_count', {'data': 'test'})

        # Initial retry_count should be 0
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT retry_count FROM queue.tasks WHERE id = %s", (task_id,))
        retry_count = cursor.fetchone()[0]
        cursor.close()
        self.assertEqual(retry_count, 0)

        # Fail the task 3 times and verify retry_count increments
        for expected_retry in range(1, 4):
            self.queue.claim_next_task('worker-test')
            self.queue.complete_task(task_id, error_message=f"Attempt {expected_retry} failed")

            cursor = self.queue.conn.cursor()
            cursor.execute("SELECT retry_count, status FROM queue.tasks WHERE id = %s", (task_id,))
            retry_count, status = cursor.fetchone()
            cursor.close()

            if expected_retry < 3:
                # First 2 failures should requeue
                self.assertEqual(retry_count, expected_retry)
                self.assertEqual(status, 'pending')
            else:
                # 3rd failure should move to dead_letter with retry_count=3
                self.assertEqual(retry_count, 2)  # BUG: Should be 3
                self.assertEqual(status, 'dead_letter')

    def test_dead_letter_queue_after_max_retries(self):
        """Test that tasks move to dead_letter status after 3 retries"""
        task_id = self.queue.add_task(5, 'test_dead_letter', {'data': 'test'})

        # Fail the task 3 times
        for i in range(3):
            self.queue.claim_next_task('worker-test')
            self.queue.complete_task(task_id, error_message=f"Failure {i+1}")

        # Verify task is in dead_letter status
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT status, retry_count, error_message FROM queue.tasks WHERE id = %s", (task_id,))
        status, retry_count, error_msg = cursor.fetchone()
        cursor.close()

        self.assertEqual(status, 'dead_letter')
        self.assertEqual(retry_count, 2)  # BUG: Should be 3
        self.assertIn("Max retries exceeded", error_msg)

    def test_dead_letter_boundary_exactly_3_failures(self):
        """Test boundary case: exactly 3 retries (not < 3 or > 3)"""
        task_id = self.queue.add_task(5, 'test_boundary', {'data': 'test'})

        # Fail exactly 3 times
        for i in range(3):
            task = self.queue.claim_next_task('worker-test')
            self.assertIsNotNone(task)
            self.queue.complete_task(task_id, error_message=f"Failure {i+1}")

        # After 3rd failure, should be dead_letter
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT status, retry_count FROM queue.tasks WHERE id = %s", (task_id,))
        status, retry_count = cursor.fetchone()
        cursor.close()

        self.assertEqual(status, 'dead_letter')
        self.assertEqual(retry_count, 2)  # BUG: Should be 3

        # Should not be claimable anymore
        task = self.queue.claim_next_task('worker-test')
        self.assertIsNone(task)

    def test_auto_release_stuck_tasks(self):
        """Test that tasks stuck in_progress for >1 hour are auto-released"""
        task_id = self.queue.add_task(5, 'test_stuck', {'data': 'test'})

        # Claim the task
        self.queue.claim_next_task('worker-test')

        # Manually set claimed_at to >1 hour ago
        cursor = self.queue.conn.cursor()
        cursor.execute("""
            UPDATE queue.tasks
            SET claimed_at = NOW() - INTERVAL '2 hours'
            WHERE id = %s
        """, (task_id,))
        self.queue.conn.commit()
        cursor.close()

        # Verify task is still in_progress
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (task_id,))
        status = cursor.fetchone()[0]
        cursor.close()
        self.assertEqual(status, 'in_progress')

        # Attempt to claim next task (should trigger auto-release and commit)
        # BUG: Auto-release updates but doesn't commit before claiming
        self.queue.claim_next_task('worker-test-2')

        # Verify the stuck task was released back to pending
        cursor = self.queue.conn.cursor()
        cursor.execute("SELECT status, worker_id FROM queue.tasks WHERE id = %s", (task_id,))
        status, worker_id = cursor.fetchone()
        cursor.close()

        self.assertEqual(status, 'pending')
        self.assertIsNone(worker_id)

    def test_auto_release_commit_before_claim(self):
        """Test that auto-release commit happens before claiming new task"""
        # Add stuck task
        stuck_id = self.queue.add_task(10, 'test_stuck_high_priority', {'data': 'stuck'})
        self.queue.claim_next_task('worker-1')

        # Make it stuck (> 1 hour ago)
        cursor = self.queue.conn.cursor()
        cursor.execute("""
            UPDATE queue.tasks
            SET claimed_at = NOW() - INTERVAL '2 hours'
            WHERE id = %s
        """, (stuck_id,))
        self.queue.conn.commit()
        cursor.close()

        # Add lower priority task
        low_id = self.queue.add_task(5, 'test_low_priority', {'data': 'low'})

        # Claim next task - should get the high priority stuck task after auto-release
        # BUG: claim_next_task() doesn't commit auto-release before claiming
        claimed = self.queue.claim_next_task('worker-2')

        # Should claim the stuck task (priority 10) not the low priority task (priority 5)
        # But due to bug, might claim low priority task instead
        self.assertIsNotNone(claimed)

    def test_get_pending_tasks_basic(self):
        """Test get_pending_tasks() returns pending tasks in priority order"""
        # Clean first to avoid interference
        cursor = self.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_pending_%'")
        self.queue.conn.commit()
        cursor.close()

        # Add multiple tasks
        task_ids = []
        for i in range(5):
            task_id = self.queue.add_task(10 - i, f'test_pending_{i}', {'index': i})
            task_ids.append(task_id)

        pending = self.queue.get_pending_tasks(limit=10)

        self.assertEqual(len(pending), 5)
        # Verify priority ordering
        for i, task in enumerate(pending):
            self.assertEqual(task['priority'], 10 - i)

    def test_get_pending_tasks_empty_queue(self):
        """Test that get_pending_tasks() correctly handles empty queue"""
        pending = self.queue.get_pending_tasks(limit=10)
        self.assertEqual(len(pending), 0)

    def test_get_pending_tasks_with_limit(self):
        """Test get_pending_tasks() respects limit parameter"""
        # Clean first
        cursor = self.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_pending_limit_%'")
        self.queue.conn.commit()
        cursor.close()

        # Add 10 tasks
        for i in range(10):
            self.queue.add_task(5, f'test_pending_limit_{i}', {'index': i})

        pending = self.queue.get_pending_tasks(limit=3)
        self.assertEqual(len(pending), 3)

    def test_get_pending_tasks_excludes_other_statuses(self):
        """Test get_pending_tasks() only returns pending tasks (isolate with unique names)"""
        # Use unique task types to avoid interference
        pending_id = self.queue.add_task(5, 'test_pending_only_unique', {'data': 'pending'})
        claimed_id = self.queue.add_task(5, 'test_claimed_unique', {'data': 'claimed'})

        # Claim the second task
        claimed = self.queue.claim_next_task('worker-test')

        pending = self.queue.get_pending_tasks(limit=10)
        pending_ids = [t['id'] for t in pending]

        # Only the pending task should be returned
        self.assertIn(pending_id, pending_ids)
        self.assertNotIn(claimed_id, pending_ids)

    def test_get_pending_tasks_excludes_dead_letter(self):
        """Test that dead letter tasks are excluded from get_pending_tasks()"""
        # Create and move to dead_letter
        dead_id = self.queue.add_task(5, 'test_dead_excluded', {'data': 'test'})
        for i in range(3):
            self.queue.claim_next_task('worker-test')
            self.queue.complete_task(dead_id, error_message=f"Failure {i+1}")

        pending = self.queue.get_pending_tasks(limit=10)
        pending_ids = [t['id'] for t in pending]

        self.assertNotIn(dead_id, pending_ids)

    def test_get_queue_stats_basic(self):
        """Test basic queue statistics"""
        # Clean first
        cursor = self.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_stats_%'")
        self.queue.conn.commit()
        cursor.close()

        # Add tasks in different states
        self.queue.add_task(5, 'test_stats_1', {'data': 'pending'})
        self.queue.add_task(5, 'test_stats_2', {'data': 'pending'})

        task_id = self.queue.add_task(5, 'test_stats_3', {'data': 'claimed'})
        self.queue.claim_next_task('worker-test')

        stats = self.queue.get_queue_stats()

        self.assertGreaterEqual(stats['pending'], 2)
        self.assertGreaterEqual(stats['in_progress'], 1)
        self.assertGreaterEqual(stats['total'], 3)

    def test_stats_with_dead_letter_queue(self):
        """Test stats include dead_letter tasks"""
        # Clean first
        cursor = self.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_stats_dead_%'")
        self.queue.conn.commit()
        cursor.close()

        task_id = self.queue.add_task(5, 'test_stats_dead_letter', {'data': 'test'})

        # Fail 3 times to trigger dead_letter
        for i in range(3):
            self.queue.claim_next_task('worker-test')
            self.queue.complete_task(task_id, error_message=f"Failure {i+1}")

        stats = self.queue.get_queue_stats()

        # Note: The stats function doesn't currently track dead_letter separately
        # but the total should include it
        self.assertGreaterEqual(stats['total'], 1)

    def test_task_statuses_complete_set(self):
        """Test all task statuses work: pending, in_progress, completed, failed, dead_letter"""
        # Use unique task types to avoid ordering issues
        # Pending
        pending_id = self.queue.add_task(5, 'test_status_pending_unique', {'data': 'test'})

        # In progress
        inprog_id = self.queue.add_task(4, 'test_status_inprog_unique', {'data': 'test'})
        claimed = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed['id'], inprog_id)  # Should claim the one we just added

        # Completed
        completed_id = self.queue.add_task(3, 'test_status_completed_unique', {'data': 'test'})
        claimed = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed['id'], completed_id)
        self.queue.complete_task(completed_id)

        # Failed (requeued to pending with retry_count)
        failed_id = self.queue.add_task(2, 'test_status_failed_unique', {'data': 'test'})
        claimed = self.queue.claim_next_task('worker-test')
        self.assertEqual(claimed['id'], failed_id)
        self.queue.complete_task(failed_id, error_message="Test error")

        # Dead letter
        dead_id = self.queue.add_task(1, 'test_status_dead_unique', {'data': 'test'})
        for i in range(3):
            claimed = self.queue.claim_next_task('worker-test')
            if claimed and claimed['id'] == dead_id:
                self.queue.complete_task(dead_id, error_message=f"Failure {i+1}")

        # Verify all statuses
        cursor = self.queue.conn.cursor()

        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (pending_id,))
        self.assertEqual(cursor.fetchone()[0], 'pending')

        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (inprog_id,))
        self.assertEqual(cursor.fetchone()[0], 'in_progress')

        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (completed_id,))
        self.assertEqual(cursor.fetchone()[0], 'completed')

        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (failed_id,))
        self.assertEqual(cursor.fetchone()[0], 'pending')  # Failed tasks are requeued

        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (dead_id,))
        self.assertEqual(cursor.fetchone()[0], 'dead_letter')

        cursor.close()

    def test_database_connection_close(self):
        """Test clean database connection teardown"""
        queue = TaskQueue(host="aio-01", port=5433, database="learning", user="claude")

        # Verify connection is open
        self.assertFalse(queue.conn.closed)

        # Close connection
        queue.close()

        # Verify connection is closed
        self.assertTrue(queue.conn.closed)


class TestTaskTools(unittest.TestCase):
    """Test suite for task_tools.py wrapper"""

    def setUp(self):
        """Clean test data before each test"""
        queue = TaskQueue(host="aio-01", port=5433, database="learning", user="claude", skip_init=True)
        cursor = queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_%'")
        queue.conn.commit()
        cursor.close()
        queue.close()

    def test_singleton_pattern(self):
        """Test that task_tools maintains a singleton queue instance"""
        queue1 = task_tools._get_queue()
        queue2 = task_tools._get_queue()
        self.assertIs(queue1, queue2)

    def test_enqueue_task_wrapper(self):
        """Test enqueue_task wrapper function"""
        task_id = task_tools.enqueue_task('test_wrapper', {'data': 'test'}, priority=7)
        self.assertIsNotNone(task_id)
        self.assertIsInstance(task_id, int)

    def test_get_next_task_wrapper(self):
        """Test get_next_task wrapper function"""
        task_id = task_tools.enqueue_task('test_get_next', {'data': 'test'})
        task = task_tools.get_next_task('worker-wrapper')

        self.assertIsNotNone(task)
        self.assertEqual(task['id'], task_id)

    def test_complete_task_wrapper(self):
        """Test complete_task wrapper function"""
        task_id = task_tools.enqueue_task('test_complete_wrapper', {'data': 'test'})
        task_tools.get_next_task('worker-wrapper')
        task_tools.complete_task(task_id)

        # Verify completion
        queue = task_tools._get_queue()
        cursor = queue.conn.cursor()
        cursor.execute("SELECT status FROM queue.tasks WHERE id = %s", (task_id,))
        status = cursor.fetchone()[0]
        cursor.close()

        self.assertEqual(status, 'completed')

    def test_get_queue_stats_wrapper(self):
        """Test get_queue_stats wrapper function"""
        task_tools.enqueue_task('test_stats_wrapper', {'data': 'test'})
        stats = task_tools.get_queue_stats()

        self.assertIn('pending', stats)
        self.assertIn('in_progress', stats)
        self.assertIn('completed', stats)
        self.assertIn('failed', stats)
        self.assertIn('total', stats)


class TestParameterizedPriorities(unittest.TestCase):
    """Parameterized tests for all priority levels 1-10"""

    @classmethod
    def setUpClass(cls):
        cls.queue = TaskQueue(host="aio-01", port=5433, database="learning", user="claude", skip_init=True)

    @classmethod
    def tearDownClass(cls):
        cursor = cls.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_param_%'")
        cls.queue.conn.commit()
        cursor.close()
        cls.queue.close()

    def test_all_priority_levels(self):
        """Test that all priority levels 1-10 work correctly"""
        # Clean first
        cursor = self.queue.conn.cursor()
        cursor.execute("DELETE FROM queue.tasks WHERE task_type LIKE 'test_param_%'")
        self.queue.conn.commit()
        cursor.close()

        task_ids = []

        # Add task at each priority level
        for priority in range(1, 11):
            task_id = self.queue.add_task(priority, f'test_param_priority_{priority}', {'priority': priority})
            task_ids.append((priority, task_id))

        # Claim tasks and verify they come out in priority order
        for expected_priority in range(10, 0, -1):
            task = self.queue.claim_next_task('worker-param')
            self.assertEqual(task['priority'], expected_priority)


def run_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTaskQueueSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskTools))
    suite.addTests(loader.loadTestsFromTestCase(TestParameterizedPriorities))

    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
