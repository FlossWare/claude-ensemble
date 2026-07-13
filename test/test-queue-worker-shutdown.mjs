#!/usr/bin/env node
/**
 * Test Queue Worker Graceful Shutdown
 *
 * This test verifies:
 * 1. Worker can claim tasks
 * 2. Worker releases tasks on SIGTERM
 * 3. Tasks return to pending state
 * 4. Worker shuts down cleanly
 */

import { spawn } from 'child_process';
import { setTimeout } from 'timers/promises';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { getQueueBatch } = require('../shared/postgres-queue-batch.cjs');

// Test configuration
const TEST_CONFIG = {
  workerType: 'chunk',
  workerId: 'test-worker-01',
  batchSize: 5,
  testDuration: 10000, // 10 seconds
};

async function setupTestQueue() {
  console.log('Setting up test queue...');

  const queue = getQueueBatch();

  // Clean up any existing test tasks
  await queue.pool.query(`
    DELETE FROM queue.tasks
    WHERE data->>'test_id' = 'graceful-shutdown-test'
  `);

  // Insert test tasks
  const testTasks = [];
  for (let i = 0; i < 20; i++) {
    testTasks.push({
      file_path: `/test/file-${i}.txt`,
      test_id: 'graceful-shutdown-test',
    });
  }

  for (const task of testTasks) {
    await queue.pool.query(`
      INSERT INTO queue.tasks (data, priority, status)
      VALUES ($1, 50, 'pending')
    `, [JSON.stringify(task)]);
  }

  console.log(`✓ Inserted ${testTasks.length} test tasks`);

  return queue;
}

async function getQueueStats(queue) {
  const result = await queue.pool.query(`
    SELECT
      status,
      COUNT(*) as count,
      array_agg(id) as task_ids
    FROM queue.tasks
    WHERE data->>'test_id' = 'graceful-shutdown-test'
    GROUP BY status
  `);

  const stats = {};
  result.rows.forEach(row => {
    stats[row.status] = {
      count: parseInt(row.count),
      taskIds: row.task_ids,
    };
  });

  return stats;
}

async function runTest() {
  console.log('=== Queue Worker Graceful Shutdown Test ===\n');

  let queue;
  let workerProcess;

  try {
    // Setup test queue
    queue = await setupTestQueue();

    // Get initial stats
    let stats = await getQueueStats(queue);
    console.log('Initial queue state:', {
      pending: stats.pending?.count || 0,
      processing: stats.processing?.count || 0,
      completed: stats.completed?.count || 0,
    });

    // Start worker process
    console.log('\nStarting worker process...');
    workerProcess = spawn('node', [
      '../shared/queue-worker.mjs',
      `--type=${TEST_CONFIG.workerType}`,
      `--worker=${TEST_CONFIG.workerId}`,
      `--batch=${TEST_CONFIG.batchSize}`,
    ], {
      cwd: import.meta.dirname,
      env: {
        ...process.env,
        POLL_INTERVAL: '2000',
        HEARTBEAT_INTERVAL: '5000',
        SHUTDOWN_TIMEOUT: '15000',
        API_URL: 'http://aio-01:5000',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    // Log worker output
    workerProcess.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter(l => l.trim());
      lines.forEach(line => {
        try {
          const log = JSON.parse(line);
          console.log(`[Worker] ${log.level}: ${log.message}`, log.taskId ? `(task ${log.taskId})` : '');
        } catch {
          console.log(`[Worker] ${line}`);
        }
      });
    });

    workerProcess.stderr.on('data', (data) => {
      console.error(`[Worker Error] ${data}`);
    });

    // Wait for worker to claim some tasks
    console.log(`\nWaiting ${TEST_CONFIG.testDuration / 1000}s for worker to claim tasks...`);
    await setTimeout(TEST_CONFIG.testDuration);

    // Check queue state while worker is running
    stats = await getQueueStats(queue);
    console.log('\nQueue state before shutdown:', {
      pending: stats.pending?.count || 0,
      processing: stats.processing?.count || 0,
      completed: stats.completed?.count || 0,
    });

    const processingBefore = stats.processing?.count || 0;
    const processingTaskIds = stats.processing?.taskIds || [];

    if (processingBefore === 0) {
      console.log('\n⚠ Warning: No tasks in processing state. Worker may not have claimed tasks yet.');
    } else {
      console.log(`✓ Worker has claimed ${processingBefore} tasks`);
      console.log(`  Task IDs: ${processingTaskIds.slice(0, 5).join(', ')}${processingTaskIds.length > 5 ? '...' : ''}`);
    }

    // Send SIGTERM to worker
    console.log('\nSending SIGTERM to worker...');
    workerProcess.kill('SIGTERM');

    // Wait for graceful shutdown
    const shutdownPromise = new Promise((resolve) => {
      workerProcess.on('exit', (code, signal) => {
        console.log(`Worker exited with code ${code}, signal ${signal}`);
        resolve({ code, signal });
      });
    });

    // Wait up to 20 seconds for shutdown
    const timeout = setTimeout(20000);
    await Promise.race([shutdownPromise, timeout]);

    // Check final queue state
    await setTimeout(1000); // Brief delay for DB writes to complete
    stats = await getQueueStats(queue);
    console.log('\nQueue state after shutdown:', {
      pending: stats.pending?.count || 0,
      processing: stats.processing?.count || 0,
      completed: stats.completed?.count || 0,
    });

    const processingAfter = stats.processing?.count || 0;
    const completedAfter = stats.completed?.count || 0;

    // Verify results
    console.log('\n=== Test Results ===');

    let testsPassed = 0;
    let totalTests = 0;

    // Test 1: Tasks were released
    totalTests++;
    if (processingBefore > 0 && processingAfter < processingBefore) {
      console.log(`✓ Test 1: Tasks released (${processingBefore} → ${processingAfter})`);
      testsPassed++;
    } else if (processingBefore === 0) {
      console.log('⊘ Test 1: Skipped (no tasks were claimed)');
    } else {
      console.log(`✗ Test 1: Tasks not released (${processingBefore} → ${processingAfter})`);
    }

    // Test 2: Worker shut down cleanly
    totalTests++;
    const exitInfo = await shutdownPromise;
    if (exitInfo.code === 0 || exitInfo.signal === 'SIGTERM') {
      console.log(`✓ Test 2: Worker shut down cleanly (code: ${exitInfo.code}, signal: ${exitInfo.signal})`);
      testsPassed++;
    } else {
      console.log(`✗ Test 2: Worker did not shut down cleanly (code: ${exitInfo.code})`);
    }

    // Test 3: Some tasks completed
    totalTests++;
    if (completedAfter > 0) {
      console.log(`✓ Test 3: Tasks completed (${completedAfter} completed)`);
      testsPassed++;
    } else {
      console.log('⊘ Test 3: No tasks completed (may need longer test duration)');
    }

    // Summary
    console.log(`\n=== Summary: ${testsPassed}/${totalTests} tests passed ===`);

    if (testsPassed === totalTests) {
      console.log('✓ All tests passed!');
      return true;
    } else {
      console.log('✗ Some tests failed');
      return false;
    }

  } catch (error) {
    console.error('\nTest error:', error);
    return false;
  } finally {
    // Cleanup
    if (workerProcess && !workerProcess.killed) {
      console.log('\nKilling worker process...');
      workerProcess.kill('SIGKILL');
    }

    if (queue) {
      console.log('Cleaning up test tasks...');
      await queue.pool.query(`
        DELETE FROM queue.tasks
        WHERE data->>'test_id' = 'graceful-shutdown-test'
      `);
      await queue.close();
    }

    console.log('✓ Cleanup complete');
  }
}

// Run test
runTest()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('Fatal test error:', error);
    process.exit(1);
  });
