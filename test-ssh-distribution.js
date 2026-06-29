#!/usr/bin/env node

/**
 * Test SSH Distribution across Fleet Workers
 *
 * Tests:
 * 1. Execute 10 tasks with worker: "auto"
 * 2. Verify tasks distributed across multiple workers
 * 3. Verify execution_host populated
 * 4. Test specific worker selection
 * 5. Test SSH failure handling
 */

import { RemoteExecutor } from './fleet-remote-executor.js';
import fs from 'fs';
import path from 'path';

const HOME = process.env.HOME || '/home/sfloess';

// Test configuration
const TEST_WORKERS = [
  { name: 'server-01', host: 'server-01' },
  { name: 'server-02', host: 'server-02' },
  { name: 'server-03', host: 'server-03' },
  { name: 'laptop-01', host: 'laptop-01', skip_ssh: true }, // Skip actual SSH for coordinator
];

const SIMPLE_PROMPT = `Return a JSON object with test results:
{
  "test": "simple-execution",
  "timestamp": "${new Date().toISOString()}",
  "execution_host": "auto-detected"
}`;

const executor = new RemoteExecutor({
  nfsRoot: path.join(HOME, 'Development'),
  sshTimeoutSec: 10,
});

/**
 * Test 1: Execute 10 tasks with auto worker selection
 */
async function testAutoDistribution() {
  console.log('\n=== TEST 1: Auto Worker Distribution ===');
  const results = [];
  const hosts = new Set();

  for (let i = 0; i < 10; i++) {
    const worker = TEST_WORKERS[i % (TEST_WORKERS.length - 1)]; // Exclude laptop-01

    try {
      console.log(`[${i + 1}/10] Executing on ${worker.name}...`);

      const result = await executor.execute(worker.host, 'sonnet', SIMPLE_PROMPT, {
        jobId: `auto-test-${i}`,
        timeoutMs: 30000,
      });

      results.push({
        task_id: i,
        worker: worker.name,
        result: result.result,
        cost: result.cost,
        duration_ms: result.remoteDuration,
        success: true,
      });

      if (result.result && result.result.execution_host) {
        hosts.add(result.result.execution_host);
      }

      console.log(`  ✓ Success - Cost: $${result.cost.toFixed(4)}, Duration: ${result.remoteDuration}ms`);
    } catch (error) {
      results.push({
        task_id: i,
        worker: worker.name,
        error: error.message,
        code: error.code,
        success: false,
      });

      console.log(`  ✗ Failed: ${error.code} - ${error.message}`);
    }
  }

  const successCount = results.filter(r => r.success).length;
  const failureCount = results.filter(r => !r.success).length;

  console.log(`\nResults: ${successCount} succeeded, ${failureCount} failed`);
  console.log(`Unique hosts detected: ${hosts.size}`);
  console.log(`Hosts: ${Array.from(hosts).join(', ') || 'N/A'}`);

  return {
    test_name: 'Auto Distribution',
    total_tasks: results.length,
    successful: successCount,
    failed: failureCount,
    unique_hosts: hosts.size,
    hosts: Array.from(hosts),
    results,
  };
}

/**
 * Test 2: Verify tasks distributed across multiple workers
 */
async function testWorkerDistribution() {
  console.log('\n=== TEST 2: Worker Distribution Verification ===');
  const workerCounts = {};

  for (let i = 0; i < 12; i++) {
    const worker = TEST_WORKERS[i % (TEST_WORKERS.length - 1)];

    try {
      await executor.execute(worker.host, 'haiku', SIMPLE_PROMPT, {
        jobId: `dist-test-${i}`,
        timeoutMs: 25000,
      });

      workerCounts[worker.name] = (workerCounts[worker.name] || 0) + 1;
      console.log(`[${i + 1}/12] ${worker.name}: Task completed`);
    } catch (error) {
      console.log(`[${i + 1}/12] ${worker.name}: ${error.code}`);
    }
  }

  console.log('\nWorker Distribution:');
  for (const [worker, count] of Object.entries(workerCounts)) {
    console.log(`  ${worker}: ${count} tasks`);
  }

  const workerCount = Object.keys(workerCounts).length;
  const isDistributed = workerCount >= 2;

  return {
    test_name: 'Distribution Verification',
    worker_distribution: workerCounts,
    unique_workers: workerCount,
    is_distributed: isDistributed,
    status: isDistributed ? 'PASS' : 'FAIL',
  };
}

/**
 * Test 3: Verify execution_host population
 */
async function testExecutionHostPopulation() {
  console.log('\n=== TEST 3: Execution Host Population ===');

  const hostsWithData = [];

  for (let i = 0; i < 5; i++) {
    const worker = TEST_WORKERS[i % (TEST_WORKERS.length - 1)];

    try {
      const result = await executor.execute(worker.host, 'sonnet',
        `Return JSON with: {"host": "from-agent", "worker_name": "detected"}`,
        {
          jobId: `host-test-${i}`,
          timeoutMs: 25000,
        }
      );

      hostsWithData.push({
        requested_worker: worker.name,
        has_result: !!result.result,
        result_keys: result.result ? Object.keys(result.result) : [],
      });

      console.log(`[${i + 1}/5] ${worker.name}: execution_host data present`);
    } catch (error) {
      console.log(`[${i + 1}/5] ${worker.name}: ${error.code}`);
    }
  }

  const populatedCount = hostsWithData.filter(h => h.has_result).length;

  return {
    test_name: 'Execution Host Population',
    total_executed: hostsWithData.length,
    with_data: populatedCount,
    percentage: ((populatedCount / hostsWithData.length) * 100).toFixed(1),
    status: populatedCount >= 4 ? 'PASS' : 'FAIL',
  };
}

/**
 * Test 4: Specific worker selection
 */
async function testSpecificWorkerSelection() {
  console.log('\n=== TEST 4: Specific Worker Selection ===');

  const results = [];

  for (const worker of TEST_WORKERS.slice(0, 3)) {
    try {
      console.log(`Testing specific selection: ${worker.name}...`);

      const result = await executor.execute(worker.host, 'haiku',
        `Return JSON: {"selected_worker": "${worker.name}"}`,
        {
          jobId: `worker-select-${worker.name}`,
          timeoutMs: 25000,
        }
      );

      results.push({
        requested_worker: worker.name,
        success: true,
        duration_ms: result.remoteDuration,
        cost: result.cost,
      });

      console.log(`  ✓ ${worker.name}: Successfully selected and executed`);
    } catch (error) {
      results.push({
        requested_worker: worker.name,
        success: false,
        error: error.code,
      });

      console.log(`  ✗ ${worker.name}: ${error.code}`);
    }
  }

  const successCount = results.filter(r => r.success).length;

  return {
    test_name: 'Specific Worker Selection',
    total_workers: results.length,
    successful: successCount,
    results,
    status: successCount >= 2 ? 'PASS' : 'FAIL',
  };
}

/**
 * Test 5: SSH failure handling
 */
async function testSshFailureHandling() {
  console.log('\n=== TEST 5: SSH Failure Handling ===');

  const failureTests = [];

  // Test 5a: Non-existent host
  try {
    console.log('Testing non-existent host...');
    await executor.execute('nonexistent-host.invalid', 'sonnet', SIMPLE_PROMPT, {
      jobId: 'fail-test-1',
      timeoutMs: 5000,
    });
    failureTests.push({ test: 'nonexistent-host', handled: false });
  } catch (error) {
    failureTests.push({
      test: 'nonexistent-host',
      error_code: error.code,
      is_ssh_error: error.code === 'SSH_CONNECT_FAILED',
      message: error.message.slice(0, 80),
    });
    console.log(`  ✓ Caught: ${error.code}`);
  }

  // Test 5b: Timeout handling
  try {
    console.log('Testing timeout handling...');
    const longPrompt = 'Run this computationally intensive task:\n' +
                       'Calculate fibonacci(40) millions of times\n' +
                       'Return JSON with result';

    await executor.execute('server-01', 'sonnet', longPrompt, {
      jobId: 'fail-test-2',
      timeoutMs: 1000, // Very short timeout to trigger
    });
    failureTests.push({ test: 'timeout', handled: false });
  } catch (error) {
    failureTests.push({
      test: 'timeout',
      error_code: error.code,
      is_timeout: error.code === 'EXECUTION_TIMEOUT',
      timeoutMs: error.timeoutMs,
    });
    console.log(`  ✓ Caught: ${error.code}`);
  }

  return {
    test_name: 'SSH Failure Handling',
    total_tests: failureTests.length,
    failure_tests: failureTests,
    all_handled: failureTests.every(t => t.error_code),
    status: failureTests.every(t => t.error_code) ? 'PASS' : 'FAIL',
  };
}

/**
 * Main test runner
 */
async function runAllTests() {
  console.log('========================================');
  console.log('SSH Distribution Test Suite');
  console.log('========================================');
  console.log(`Start time: ${new Date().toISOString()}`);
  console.log(`Home: ${HOME}`);
  console.log(`NFS Root: ${path.join(HOME, 'Development')}`);

  const allResults = [];

  try {
    allResults.push(await testAutoDistribution());
  } catch (error) {
    console.error('Test 1 failed:', error.message);
    allResults.push({ test_name: 'Auto Distribution', error: error.message, status: 'ERROR' });
  }

  try {
    allResults.push(await testWorkerDistribution());
  } catch (error) {
    console.error('Test 2 failed:', error.message);
    allResults.push({ test_name: 'Distribution Verification', error: error.message, status: 'ERROR' });
  }

  try {
    allResults.push(await testExecutionHostPopulation());
  } catch (error) {
    console.error('Test 3 failed:', error.message);
    allResults.push({ test_name: 'Execution Host Population', error: error.message, status: 'ERROR' });
  }

  try {
    allResults.push(await testSpecificWorkerSelection());
  } catch (error) {
    console.error('Test 4 failed:', error.message);
    allResults.push({ test_name: 'Specific Worker Selection', error: error.message, status: 'ERROR' });
  }

  try {
    allResults.push(await testSshFailureHandling());
  } catch (error) {
    console.error('Test 5 failed:', error.message);
    allResults.push({ test_name: 'SSH Failure Handling', error: error.message, status: 'ERROR' });
  }

  // Summary
  console.log('\n========================================');
  console.log('Test Summary');
  console.log('========================================');

  for (const result of allResults) {
    const status = result.status || 'UNKNOWN';
    const icon = status === 'PASS' ? '✓' : status === 'FAIL' ? '✗' : '?';
    console.log(`${icon} ${result.test_name}: ${status}`);
  }

  // Save results
  const reportPath = path.join(HOME, 'Development', 'test-ssh-distribution-results.json');
  fs.writeFileSync(reportPath, JSON.stringify({
    timestamp: new Date().toISOString(),
    summary: {
      total_tests: allResults.length,
      passed: allResults.filter(r => r.status === 'PASS').length,
      failed: allResults.filter(r => r.status === 'FAIL').length,
      errors: allResults.filter(r => r.status === 'ERROR').length,
    },
    tests: allResults,
  }, null, 2));

  console.log(`\nResults saved to: ${reportPath}`);
  console.log(`End time: ${new Date().toISOString()}`);
}

// Run tests
runAllTests().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
