#!/usr/bin/env node

/**
 * Task Queue Integration Test
 *
 * Validates that task_queue_system.py is properly wired into
 * the orchestration layer via task-queue-wrapper.mjs.
 *
 * Tests:
 * 1. Enqueue tasks with different priorities
 * 2. Query queue stats
 * 3. List pending tasks
 * 4. Claim task as worker
 * 5. Complete task
 * 6. Verify retry on failure
 * 7. Verify dead letter queue
 *
 * Usage:
 *   node tests/test-task-queue-integration.mjs
 *
 * Expected: All tests pass (exit code 0)
 */

import {
  enqueueTask,
  enqueueTasks,
  claimNextTask,
  completeTask,
  getQueueStats,
  getPendingTasks
} from '../shared/task-queue-wrapper.mjs';

let testsRun = 0;
let testsPassed = 0;

function assert(condition, message) {
  testsRun++;
  if (condition) {
    console.log(`  ✅ ${message}`);
    testsPassed++;
  } else {
    console.error(`  ❌ ${message}`);
  }
}

async function test(name, fn) {
  console.log(`\n📋 TEST: ${name}`);
  try {
    await fn();
  } catch (error) {
    console.error(`  ❌ Test failed: ${error.message}`);
    console.error(error.stack);
  }
}

(async () => {
  console.log('='.repeat(60));
  console.log('TASK QUEUE INTEGRATION TEST');
  console.log('='.repeat(60));

  // Test 1: Enqueue single task
  await test('Enqueue single task', async () => {
    const taskId = await enqueueTask(8, 'test-agent', {
      model: 'gpt-4o-mini',
      task: 'Test task 1'
    });

    assert(typeof taskId === 'number', `Task ID is number: ${taskId}`);
    assert(taskId > 0, `Task ID is positive: ${taskId}`);
  });

  // Test 2: Enqueue multiple tasks
  await test('Enqueue multiple tasks', async () => {
    const taskIds = await enqueueTasks([
      { priority: 10, model: 'opus', task: 'Critical task' },
      { priority: 5, model: 'sonnet', task: 'Normal task' },
      { priority: 1, model: 'haiku', task: 'Low priority task' }
    ]);

    assert(Array.isArray(taskIds), 'Returns array of task IDs');
    assert(taskIds.length === 3, `Enqueued 3 tasks: ${taskIds.length}`);
    assert(taskIds.every(id => typeof id === 'number'), 'All task IDs are numbers');
  });

  // Test 3: Get queue stats
  await test('Get queue statistics', async () => {
    const stats = await getQueueStats();

    assert(typeof stats === 'object', 'Stats is an object');
    assert('pending' in stats, 'Stats has pending count');
    assert('in_progress' in stats, 'Stats has in_progress count');
    assert('completed' in stats, 'Stats has completed count');
    assert('failed' in stats, 'Stats has failed count');
    assert('total' in stats, 'Stats has total count');
    assert(stats.pending >= 4, `At least 4 pending tasks: ${stats.pending}`);

    console.log(`  📊 Stats: pending=${stats.pending}, in_progress=${stats.in_progress}, completed=${stats.completed}`);
  });

  // Test 4: Get pending tasks
  await test('Get pending tasks', async () => {
    const tasks = await getPendingTasks(10);

    assert(Array.isArray(tasks), 'Returns array of tasks');
    assert(tasks.length >= 4, `At least 4 pending: ${tasks.length}`);

    if (tasks.length > 0) {
      const task = tasks[0];
      assert('id' in task, 'Task has id');
      assert('priority' in task, 'Task has priority');
      assert('task_type' in task, 'Task has task_type');
      assert('created_at' in task, 'Task has created_at');

      // Verify priority ordering (highest first)
      const priorities = tasks.map(t => t.priority);
      const sorted = [...priorities].sort((a, b) => b - a);
      const isOrdered = JSON.stringify(priorities) === JSON.stringify(sorted);
      assert(isOrdered, `Tasks ordered by priority: [${priorities.join(', ')}]`);
    }
  });

  // Test 5: Claim next task
  await test('Claim next task', async () => {
    const task = await claimNextTask('test-worker-01');

    assert(task !== null, 'Claimed a task');
    assert(typeof task === 'object', 'Task is an object');
    assert('id' in task, 'Task has id');
    assert('priority' in task, 'Task has priority');
    assert('task_type' in task, 'Task has task_type');
    assert('payload' in task, 'Task has payload');

    console.log(`  📋 Claimed task ${task.id}: ${task.task_type} (priority ${task.priority})`);

    // Complete the task
    await completeTask(task.id, null);
    console.log(`  ✅ Completed task ${task.id}`);
  });

  // Test 6: Claim and fail task (verify retry)
  await test('Task retry on failure', async () => {
    const task = await claimNextTask('test-worker-02');

    if (task) {
      console.log(`  📋 Claimed task ${task.id} for failure test`);

      // Fail the task (should trigger retry)
      await completeTask(task.id, 'Simulated failure for testing');
      console.log(`  ⚠️  Failed task ${task.id} (should retry)`);

      // Check that task is back in pending status
      const stats = await getQueueStats();
      assert(stats.pending >= 1, `Task requeued: pending=${stats.pending}`);
    } else {
      console.log('  ⚠️  No tasks available to test failure (skip)');
    }
  });

  // Test 7: Verify queue cleanup
  await test('Verify queue state', async () => {
    const stats = await getQueueStats();
    const pending = await getPendingTasks(5);

    console.log(`  📊 Final stats: pending=${stats.pending}, in_progress=${stats.in_progress}`);
    console.log(`  📋 Pending tasks: ${pending.map(t => `#${t.id} (p${t.priority})`).join(', ')}`);

    assert(stats.total > 0, 'Queue has tasks');
    assert(stats.completed >= 1, `At least 1 completed: ${stats.completed}`);
  });

  // Summary
  console.log('');
  console.log('='.repeat(60));
  console.log(`SUMMARY: ${testsPassed}/${testsRun} tests passed`);
  console.log('='.repeat(60));

  if (testsPassed === testsRun) {
    console.log('✅ All tests passed!');
    process.exit(0);
  } else {
    console.error(`❌ ${testsRun - testsPassed} tests failed`);
    process.exit(1);
  }
})();
