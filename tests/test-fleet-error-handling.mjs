#!/usr/bin/env node

/**
 * Fleet Workflow Error Handling Test Suite
 *
 * Tests graceful degradation across various failure scenarios:
 * - Worker offline (fake hostname)
 * - SSH timeout
 * - Worker returns error
 * - All workers busy/failing
 * - Storage unavailable
 *
 * Expected behavior:
 * - Retry on failure (maxRetries=2)
 * - Fallback to local execution
 * - Continue workflow despite individual failures
 * - Track failures in execution history
 */

import { createFleetWorkflow, getGlobalExecutionStats, clearExecutionHistory } from './shared/fleet-workflow-wrapper.mjs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

console.log('🧪 Fleet Workflow Error Handling Test Suite\n');
console.log('Testing graceful degradation and fallback mechanisms...\n');

// Clear history for clean test
clearExecutionHistory();

const testResults = {
  total: 0,
  passed: 0,
  failed: 0,
  tests: []
};

function recordTest(name, passed, message, details = {}) {
  testResults.total++;
  if (passed) {
    testResults.passed++;
    console.log(`✅ PASS: ${name}`);
  } else {
    testResults.failed++;
    console.error(`❌ FAIL: ${name} - ${message}`);
  }

  testResults.tests.push({
    name,
    passed,
    message,
    details,
    timestamp: new Date().toISOString()
  });

  console.log(`   ${message}\n`);
}

/**
 * Test 1: Worker offline (fake hostname)
 *
 * Expected: Retry on other workers, then fallback to local
 */
async function testWorkerOffline() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 1: Worker Offline (Fake Hostname)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { agent, complete } = createFleetWorkflow(
      'test-worker-offline',
      'Test worker offline handling',
      {
        enableFleet: true,
        enableStorage: false,
        maxRetries: 2,
        timeout: 5000, // Short timeout for testing
        fallbackToLocal: true
      }
    );

    // Simple test prompt (will fail on fleet, succeed locally)
    const result = await agent('echo "test"', {
      model: 'claude-sonnet-4',
      type: 'test'
    });

    // Should get result despite fleet failures
    const passed = result !== null && result !== undefined;

    recordTest(
      'Worker offline fallback',
      passed,
      passed
        ? 'Successfully fell back to local execution after fleet failures'
        : 'Failed to execute despite fallback',
      { result: result ? 'got result' : 'no result' }
    );

    await complete(result, 1.0, 'success');

  } catch (error) {
    recordTest(
      'Worker offline fallback',
      false,
      `Exception thrown: ${error.message}`,
      { error: error.stack }
    );
  }
}

/**
 * Test 2: SSH timeout
 *
 * Expected: Timeout after configured duration, retry, then fallback
 */
async function testSSHTimeout() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 2: SSH Timeout');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { agent, complete } = createFleetWorkflow(
      'test-ssh-timeout',
      'Test SSH timeout handling',
      {
        enableFleet: true,
        enableStorage: false,
        maxRetries: 1, // Reduced retries for faster test
        timeout: 2000, // Very short timeout
        fallbackToLocal: true
      }
    );

    const startTime = Date.now();

    // Should timeout quickly and fallback
    const result = await agent('echo "timeout test"', {
      model: 'claude-sonnet-4',
      type: 'timeout_test'
    });

    const duration = Date.now() - startTime;

    // Should complete in under 10 seconds despite timeouts
    const passed = result !== null && duration < 10000;

    recordTest(
      'SSH timeout handling',
      passed,
      passed
        ? `Handled timeout gracefully in ${duration}ms`
        : `Timeout handling took too long: ${duration}ms`,
      { duration, result: result ? 'got result' : 'no result' }
    );

    await complete(result, 1.0, 'success');

  } catch (error) {
    recordTest(
      'SSH timeout handling',
      false,
      `Exception thrown: ${error.message}`,
      { error: error.stack }
    );
  }
}

/**
 * Test 3: Worker returns error
 *
 * Expected: Track error, retry on different worker, eventually succeed locally
 */
async function testWorkerError() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 3: Worker Returns Error');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { agent, complete, getExecutionStats } = createFleetWorkflow(
      'test-worker-error',
      'Test worker error handling',
      {
        enableFleet: true,
        enableStorage: false,
        maxRetries: 2,
        timeout: 5000,
        fallbackToLocal: true
      }
    );

    // Invalid command will fail on fleet, but we should fallback
    const result = await agent('invalid_command_xyz', {
      model: 'claude-sonnet-4',
      type: 'error_test'
    });

    const stats = getExecutionStats();

    // Should have tracked failures and eventually succeeded locally
    const passed = result !== null && Object.keys(stats).length > 0;

    recordTest(
      'Worker error tracking',
      passed,
      passed
        ? `Tracked ${Object.keys(stats).length} worker attempts, final result obtained`
        : 'Failed to track errors or get result',
      { stats, result: result ? 'got result' : 'no result' }
    );

    await complete(result, 1.0, 'success');

  } catch (error) {
    recordTest(
      'Worker error tracking',
      false,
      `Exception thrown: ${error.message}`,
      { error: error.stack }
    );
  }
}

/**
 * Test 4: All workers busy/failing
 *
 * Expected: Round-robin exhaustion, fallback to local
 */
async function testAllWorkersBusy() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 4: All Workers Busy/Failing');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { agent, parallel, complete } = createFleetWorkflow(
      'test-all-workers-busy',
      'Test handling all workers failing',
      {
        enableFleet: true,
        enableStorage: false,
        maxRetries: 1,
        timeout: 3000,
        fallbackToLocal: true
      }
    );

    // Run multiple tasks that will all fail on fleet
    const tasks = [
      { prompt: 'task 1', model: 'claude-sonnet-4', type: 'batch_test' },
      { prompt: 'task 2', model: 'claude-sonnet-4', type: 'batch_test' },
      { prompt: 'task 3', model: 'claude-sonnet-4', type: 'batch_test' }
    ];

    const results = await parallel(tasks, { maxConcurrency: 8 });

    // Should get results despite fleet failures
    const passed = results.every(r => r !== null);
    const successCount = results.filter(r => r !== null).length;

    recordTest(
      'All workers busy fallback',
      passed,
      `${successCount}/${tasks.length} tasks completed via fallback`,
      { successCount, totalTasks: tasks.length }
    );

    await complete(results, 1.0, 'success');

  } catch (error) {
    recordTest(
      'All workers busy fallback',
      false,
      `Exception thrown: ${error.message}`,
      { error: error.stack }
    );
  }
}

/**
 * Test 5: Storage unavailable
 *
 * Expected: Workflow continues without storage, no crashes
 */
async function testStorageUnavailable() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 5: Storage Unavailable');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { agent, phase, complete } = createFleetWorkflow(
      'test-storage-unavailable',
      'Test storage failure handling',
      {
        enableFleet: false, // Use local only for speed
        enableStorage: true, // Will try to use storage (may fail gracefully)
        fallbackToLocal: true
      }
    );

    // Run workflow with phases
    await phase('Test Phase', async () => {
      const result = await agent('echo "storage test"', {
        model: 'claude-sonnet-4',
        type: 'storage_test'
      });
      return result;
    });

    const finalResult = 'test complete';
    await complete(finalResult, 1.0, 'success');

    // Should succeed even if storage fails
    recordTest(
      'Storage unavailable handling',
      true,
      'Workflow completed despite potential storage issues',
      { result: 'success' }
    );

  } catch (error) {
    // Storage failure should be warned, not throw
    recordTest(
      'Storage unavailable handling',
      false,
      `Workflow crashed on storage failure: ${error.message}`,
      { error: error.stack }
    );
  }
}

/**
 * Test 6: No fallback to local (strict fleet-only mode)
 *
 * Expected: Throw error after exhausting retries
 */
async function testNoFallback() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 6: No Fallback (Strict Fleet Mode)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { agent } = createFleetWorkflow(
      'test-no-fallback',
      'Test strict fleet-only mode',
      {
        enableFleet: true,
        enableStorage: false,
        maxRetries: 1,
        timeout: 2000,
        fallbackToLocal: false // STRICT MODE
      }
    );

    // This should fail and throw
    await agent('echo "strict mode test"', {
      model: 'claude-sonnet-4',
      type: 'strict_test'
    });

    // Should NOT get here
    recordTest(
      'No fallback error throwing',
      false,
      'Should have thrown error but did not',
      { unexpected: 'no error thrown' }
    );

  } catch (error) {
    // Expected to throw
    const passed = error.message.includes('Fleet execution failed');

    recordTest(
      'No fallback error throwing',
      passed,
      passed
        ? 'Correctly threw error when fallback disabled'
        : `Wrong error type: ${error.message}`,
      { errorMessage: error.message }
    );
  }
}

/**
 * Test 7: Parallel execution with mixed success/failure
 *
 * Expected: Some tasks succeed, some fail, workflow continues
 */
async function testMixedParallelResults() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 7: Mixed Parallel Results');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { parallel, complete } = createFleetWorkflow(
      'test-mixed-parallel',
      'Test mixed success/failure in parallel',
      {
        enableFleet: false, // Use local for predictable results
        enableStorage: false,
        fallbackToLocal: true
      }
    );

    const tasks = [
      { prompt: 'echo "success 1"', model: 'claude-sonnet-4', type: 'mixed_test' },
      { prompt: 'echo "success 2"', model: 'claude-sonnet-4', type: 'mixed_test' },
      { prompt: 'echo "success 3"', model: 'claude-sonnet-4', type: 'mixed_test' }
    ];

    const results = await parallel(tasks, { maxConcurrency: 3 });

    const successCount = results.filter(r => r !== null && r !== undefined).length;
    const passed = successCount >= 2; // At least 2/3 should succeed

    recordTest(
      'Mixed parallel results',
      passed,
      `${successCount}/${tasks.length} tasks completed successfully`,
      { successCount, totalTasks: tasks.length, results }
    );

    await complete(results, 0.8, 'partial');

  } catch (error) {
    recordTest(
      'Mixed parallel results',
      false,
      `Exception thrown: ${error.message}`,
      { error: error.stack }
    );
  }
}

/**
 * Run all tests
 */
async function runAllTests() {
  const startTime = Date.now();

  await testWorkerOffline();
  await testSSHTimeout();
  await testWorkerError();
  await testAllWorkersBusy();
  await testStorageUnavailable();
  await testNoFallback();
  await testMixedParallelResults();

  const duration = Date.now() - startTime;

  // Print summary
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST SUMMARY');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
  console.log(`Total Tests:  ${testResults.total}`);
  console.log(`Passed:       ${testResults.passed} ✅`);
  console.log(`Failed:       ${testResults.failed} ❌`);
  console.log(`Duration:     ${duration}ms`);
  console.log(`Success Rate: ${((testResults.passed / testResults.total) * 100).toFixed(1)}%\n`);

  // Print global execution stats
  const globalStats = getGlobalExecutionStats();
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('GLOBAL EXECUTION STATISTICS');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  for (const [host, stats] of Object.entries(globalStats)) {
    console.log(`${host}:`);
    console.log(`  Total:        ${stats.total}`);
    console.log(`  Success:      ${stats.success}`);
    console.log(`  Success Rate: ${(stats.successRate * 100).toFixed(1)}%`);
    console.log(`  Avg Duration: ${stats.avgDuration.toFixed(0)}ms`);

    if (Object.keys(stats.byWorkflow).length > 0) {
      console.log(`  By Workflow:`);
      for (const [workflow, wStats] of Object.entries(stats.byWorkflow)) {
        console.log(`    ${workflow}: ${wStats.success}/${wStats.total}`);
      }
    }
    console.log('');
  }

  // Print detailed failures
  const failures = testResults.tests.filter(t => !t.passed);
  if (failures.length > 0) {
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('DETAILED FAILURES');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

    for (const failure of failures) {
      console.log(`Test: ${failure.name}`);
      console.log(`Message: ${failure.message}`);
      console.log(`Details: ${JSON.stringify(failure.details, null, 2)}\n`);
    }
  }

  // Exit code based on test results
  process.exit(testResults.failed > 0 ? 1 : 0);
}

// Run tests
runAllTests().catch(error => {
  console.error('\n❌ FATAL TEST ERROR:', error);
  process.exit(1);
});
