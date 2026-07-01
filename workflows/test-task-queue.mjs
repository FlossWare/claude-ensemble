#!/usr/bin/env node

/**
 * Test Task Queue Integration
 *
 * Simple workflow to test the priority task queue system.
 * Demonstrates:
 * - Enqueuing tasks with priorities
 * - Queue statistics monitoring
 * - Task claiming and completion
 *
 * Usage: node workflows/test-task-queue.mjs
 */

import { enqueueTasks, getQueueStats, getPendingTasks } from '../shared/task-queue-wrapper.mjs';

async function main() {
  console.log('🚀 Task Queue Integration Test\n');

  // 1. Check initial queue state
  console.log('1. Initial queue state:');
  const initialStats = await getQueueStats();
  console.log(`   Pending: ${initialStats.pending}`);
  console.log(`   In Progress: ${initialStats.in_progress}`);
  console.log(`   Completed: ${initialStats.completed}\n`);

  // 2. Enqueue test tasks with different priorities
  console.log('2. Enqueuing test tasks...');
  const taskIds = await enqueueTasks([
    { priority: 10, model: 'opus', task: 'Critical: Analyze security vulnerability', taskType: 'security_analysis' },
    { priority: 8, model: 'sonnet', task: 'Important: Review code changes', taskType: 'code_review' },
    { priority: 5, model: 'haiku', task: 'Standard: Generate test cases', taskType: 'test_generation' },
    { priority: 3, model: 'gpt-4o-mini', task: 'Low priority: Update documentation', taskType: 'documentation' },
  ]);
  console.log(`   ✅ Enqueued ${taskIds.length} tasks: ${taskIds.join(', ')}\n`);

  // 3. Check updated queue state
  console.log('3. Updated queue state:');
  const updatedStats = await getQueueStats();
  console.log(`   Pending: ${updatedStats.pending}`);
  console.log(`   In Progress: ${updatedStats.in_progress}`);
  console.log(`   Completed: ${updatedStats.completed}\n`);

  // 4. List pending tasks (should be ordered by priority)
  console.log('4. Pending tasks (by priority):');
  const pending = await getPendingTasks(10);
  pending.forEach(t => {
    console.log(`   - Task ${t.id}: ${t.task_type} (priority ${t.priority})`);
  });

  console.log('\n✅ Task queue integration test complete!');
  console.log('\nNotes:');
  console.log('- Tasks are now queued in PostgreSQL on aio-01:5433');
  console.log('- Workers can claim tasks by running: node shared/task-queue-wrapper.mjs --worker <hostname>');
  console.log('- Tasks are ordered by priority (10=highest)');
  console.log('- Failed tasks auto-retry up to 3 times');
}

main().catch(err => {
  console.error('❌ Test failed:', err.message);
  process.exit(1);
});
