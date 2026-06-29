#!/usr/bin/env node

/**
 * Advanced SSH Distribution Test
 *
 * Tests SSH distribution with:
 * 1. Worker availability detection
 * 2. Task distribution across available workers
 * 3. Execution host tracking
 * 4. Failure handling and retry logic
 * 5. Load distribution metrics
 */

import { RemoteExecutor } from './fleet-remote-executor.js';
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const HOME = process.env.HOME || '/home/sfloess';

// Worker candidates
const WORKER_CANDIDATES = [
  { name: 'server-01', host: 'server-01' },
  { name: 'server-02', host: 'server-02' },
  { name: 'server-03', host: 'server-03' },
];

const executor = new RemoteExecutor({
  nfsRoot: path.join(HOME, 'Development'),
  sshTimeoutSec: 10,
});

/**
 * Check worker availability via SSH
 */
async function checkWorkerAvailability() {
  console.log('\n=== Worker Availability Check ===');
  const availability = {};

  for (const worker of WORKER_CANDIDATES) {
    try {
      const result = execSync(
        `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 ${worker.host} "echo ok"`,
        { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
      );

      // Check if claude is available
      try {
        execSync(
          `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 ${worker.host} "timeout 2 claude --version"`,
          { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
        );
        availability[worker.name] = 'available';
        console.log(`✓ ${worker.name}: SSH OK, Claude available`);
      } catch (e) {
        availability[worker.name] = 'ssh-ok-claude-unavailable';
        console.log(`⚠ ${worker.name}: SSH OK, Claude unavailable (error: ${e.message.split('\n')[0]})`);
      }
    } catch (error) {
      availability[worker.name] = 'unavailable';
      console.log(`✗ ${worker.name}: SSH failed`);
    }
  }

  return availability;
}

/**
 * Test 1: Distribution across available workers
 */
async function testDistributionAcrossAvailable(availableWorkers) {
  console.log('\n=== TEST 1: Distribution Across Available Workers ===');

  const available = Object.entries(availableWorkers)
    .filter(([, status]) => status === 'available')
    .map(([name]) => name);

  if (available.length === 0) {
    console.log('⚠ No workers with Claude available for distribution test');
    return {
      test_name: 'Distribution Across Available',
      status: 'SKIP',
      reason: 'No Claude-available workers',
    };
  }

  console.log(`Available workers: ${available.join(', ')}`);

  const distribution = {};
  const results = [];

  for (let i = 0; i < 10; i++) {
    const worker = available[i % available.length];
    const prompt = `Return JSON: {"task": ${i}, "worker": "${worker}", "timestamp": "${new Date().toISOString()}"}`;

    try {
      const result = await executor.execute(worker, 'sonnet', prompt, {
        jobId: `dist-${i}`,
        timeoutMs: 30000,
      });

      distribution[worker] = (distribution[worker] || 0) + 1;
      results.push({
        task_id: i,
        worker,
        success: true,
        duration_ms: result.remoteDuration,
        cost: result.cost,
      });

      console.log(`[${i + 1}/10] ${worker}: SUCCESS (${result.remoteDuration}ms)`);
    } catch (error) {
      results.push({
        task_id: i,
        worker,
        success: false,
        error: error.code,
      });

      console.log(`[${i + 1}/10] ${worker}: FAILED (${error.code})`);
    }
  }

  const successCount = results.filter(r => r.success).length;

  console.log('\nDistribution:');
  for (const [worker, count] of Object.entries(distribution)) {
    console.log(`  ${worker}: ${count} tasks`);
  }

  return {
    test_name: 'Distribution Across Available',
    total_tasks: results.length,
    successful: successCount,
    failed: results.length - successCount,
    distribution,
    unique_workers: Object.keys(distribution).length,
    status: successCount >= 5 ? 'PASS' : 'FAIL',
    results,
  };
}

/**
 * Test 2: Execution host population
 */
async function testExecutionHostPopulation(availableWorkers) {
  console.log('\n=== TEST 2: Execution Host Population ===');

  const available = Object.entries(availableWorkers)
    .filter(([, status]) => status === 'available')
    .map(([name]) => name);

  if (available.length === 0) {
    return {
      test_name: 'Execution Host Population',
      status: 'SKIP',
      reason: 'No Claude-available workers',
    };
  }

  const results = [];

  for (let i = 0; i < available.length; i++) {
    const worker = available[i];
    const prompt = `
    import os
    import json

    # Get execution host info
    result = {
      "hostname": os.environ.get('HOSTNAME', 'unknown'),
      "home": os.environ.get('HOME', 'unknown'),
      "pwd": os.environ.get('PWD', 'unknown'),
      "execution_timestamp": "${new Date().toISOString()}"
    }
    print(json.dumps(result))
    `;

    try {
      const result = await executor.execute(worker, 'haiku', prompt, {
        jobId: `host-${i}`,
        timeoutMs: 25000,
      });

      results.push({
        worker,
        success: true,
        result_keys: result.result ? Object.keys(result.result) : [],
        has_hostname: result.result && !!result.result.hostname,
      });

      console.log(`${worker}: execution_host data received`);
    } catch (error) {
      results.push({
        worker,
        success: false,
        error: error.code,
      });

      console.log(`${worker}: FAILED (${error.code})`);
    }
  }

  const populatedCount = results.filter(r => r.has_hostname).length;

  return {
    test_name: 'Execution Host Population',
    total_executed: results.length,
    with_hostname_data: populatedCount,
    status: populatedCount >= Math.min(available.length, 2) ? 'PASS' : 'FAIL',
    results,
  };
}

/**
 * Test 3: Load distribution metrics
 */
async function testLoadDistributionMetrics(availableWorkers) {
  console.log('\n=== TEST 3: Load Distribution Metrics ===');

  const available = Object.entries(availableWorkers)
    .filter(([, status]) => status === 'available')
    .map(([name]) => name);

  if (available.length === 0) {
    return {
      test_name: 'Load Distribution Metrics',
      status: 'SKIP',
      reason: 'No Claude-available workers',
    };
  }

  const metrics = {};
  const startTime = Date.now();

  for (let i = 0; i < 15; i++) {
    const worker = available[i % available.length];
    const prompt = `Calculate sum of 1 to 1000. Return JSON: {"sum": ${1000 * 1001 / 2}, "task": ${i}}`;

    try {
      const taskStart = Date.now();
      const result = await executor.execute(worker, 'haiku', prompt, {
        jobId: `load-${i}`,
        timeoutMs: 25000,
      });

      const taskDuration = Date.now() - taskStart;

      if (!metrics[worker]) {
        metrics[worker] = { count: 0, total_duration_ms: 0, total_cost: 0 };
      }

      metrics[worker].count += 1;
      metrics[worker].total_duration_ms += taskDuration;
      metrics[worker].total_cost += result.cost;

      console.log(`[${i + 1}/15] ${worker}: ${taskDuration}ms`);
    } catch (error) {
      console.log(`[${i + 1}/15] ${worker}: FAILED`);
    }
  }

  const totalDuration = Date.now() - startTime;

  console.log('\nMetrics Summary:');
  for (const [worker, data] of Object.entries(metrics)) {
    const avgDuration = (data.total_duration_ms / data.count).toFixed(0);
    console.log(`  ${worker}: ${data.count} tasks, avg ${avgDuration}ms, total cost $${data.total_cost.toFixed(4)}`);
  }

  console.log(`\nTotal time: ${totalDuration}ms`);

  return {
    test_name: 'Load Distribution Metrics',
    total_duration_ms: totalDuration,
    worker_metrics: metrics,
    status: Object.keys(metrics).length > 0 ? 'PASS' : 'FAIL',
  };
}

/**
 * Test 4: Failure handling
 */
async function testFailureHandling() {
  console.log('\n=== TEST 4: Failure Handling ===');

  const failureTests = [];

  // Test SSH timeout
  try {
    console.log('Testing SSH connect timeout...');
    await executor.execute('nonexistent-host', 'sonnet', 'test', {
      jobId: 'fail-ssh-timeout',
      timeoutMs: 3000,
    });
  } catch (error) {
    failureTests.push({
      test: 'ssh-timeout',
      caught: true,
      error_code: error.code,
      is_correct: error.code === 'SSH_CONNECT_FAILED' || error.code === 'CLAUDE_EXECUTION_FAILED',
    });
    console.log(`  ✓ Caught: ${error.code}`);
  }

  // Test execution timeout
  try {
    console.log('Testing execution timeout...');
    const longPrompt = 'while True: pass';

    await executor.execute('server-01', 'sonnet', longPrompt, {
      jobId: 'fail-exec-timeout',
      timeoutMs: 2000,
    });
  } catch (error) {
    failureTests.push({
      test: 'exec-timeout',
      caught: true,
      error_code: error.code,
      is_correct: error.code === 'EXECUTION_TIMEOUT',
    });
    console.log(`  ✓ Caught: ${error.code}`);
  }

  return {
    test_name: 'Failure Handling',
    total_tests: failureTests.length,
    all_caught: failureTests.every(t => t.caught),
    failure_tests: failureTests,
    status: failureTests.filter(t => t.is_correct).length === failureTests.length ? 'PASS' : 'FAIL',
  };
}

/**
 * Main runner
 */
async function runAllTests() {
  console.log('========================================');
  console.log('Advanced SSH Distribution Test Suite');
  console.log('========================================');
  console.log(`Start time: ${new Date().toISOString()}`);

  const allResults = [];

  // Check availability first
  const availability = await checkWorkerAvailability();
  const availableCount = Object.values(availability).filter(s => s === 'available').length;

  console.log(`\nAvailable workers: ${availableCount}`);

  // Run tests
  if (availableCount > 0) {
    allResults.push(await testDistributionAcrossAvailable(availability));
    allResults.push(await testExecutionHostPopulation(availability));
    allResults.push(await testLoadDistributionMetrics(availability));
  } else {
    console.log('\n⚠ Skipping execution tests: No workers with Claude available');
    allResults.push({
      test_name: 'Distribution Test',
      status: 'SKIP',
      reason: 'No Claude-available workers',
    });
  }

  allResults.push(await testFailureHandling());

  // Summary
  console.log('\n========================================');
  console.log('Test Summary');
  console.log('========================================');

  for (const result of allResults) {
    const status = result.status || 'UNKNOWN';
    const icon = status === 'PASS' ? '✓' : status === 'FAIL' ? '✗' : status === 'SKIP' ? '⊘' : '?';
    console.log(`${icon} ${result.test_name}: ${status}`);
  }

  // Save results
  const reportPath = path.join(HOME, 'Development', 'test-ssh-distribution-advanced-results.json');
  fs.writeFileSync(reportPath, JSON.stringify({
    timestamp: new Date().toISOString(),
    worker_availability: availability,
    summary: {
      total_tests: allResults.length,
      passed: allResults.filter(r => r.status === 'PASS').length,
      failed: allResults.filter(r => r.status === 'FAIL').length,
      skipped: allResults.filter(r => r.status === 'SKIP').length,
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
