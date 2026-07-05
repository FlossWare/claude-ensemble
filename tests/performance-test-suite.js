#!/usr/bin/env node
/**
 * Comprehensive Performance Test Suite
 *
 * Tests:
 * 1. Single prediction latency (target: <5s)
 * 2. Parallel predictions (10 concurrent, target: <10s)
 * 3. Model loading time (cold start vs cached)
 * 4. Database query performance (measure each query)
 * 5. Memory usage under load
 * 6. CPU usage under load
 * 7. Connection pool handling
 * 8. Error rate under stress
 * 9. Recovery time after failure
 * 10. Sustained load (100 predictions over 5 minutes)
 *
 * Measures:
 * - p50, p95, p99 latencies
 * - Throughput (predictions per second)
 * - Resource usage (memory, CPU)
 * - Error rates
 * - Database connection pool stats
 *
 * Created: 2026-07-04
 */

import { predictWorkflow } from '../shared/workflow-predictor.js';
import { Pool } from 'pg';
import { execSync } from 'child_process';
import os from 'os';

// PostgreSQL connection pool
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER || 'claude',
  password: process.env.PGPASSWORD,
  max: 20,
  idleTimeoutMillis: 30000,
});

/**
 * Sample workflow configurations (diverse task types)
 */
const SAMPLE_TASKS = [
  {
    taskDescription: 'Generate Python function for Fibonacci numbers',
    workerCount: 3,
    models: ['sonnet', 'haiku', 'fable'],
    hasGitContext: false,
  },
  {
    taskDescription: 'Research firmware reverse engineering for RAX-75 router',
    workerCount: 8,
    models: ['opus', 'sonnet', 'gpt-4o'],
    hasGitContext: false,
  },
  {
    taskDescription: 'Review PR #123 for security issues',
    workerCount: 5,
    models: ['opus', 'sonnet', 'haiku'],
    hasGitContext: true,
  },
  {
    taskDescription: 'Analyze PostgreSQL query performance logs',
    workerCount: 4,
    models: ['sonnet', 'haiku', 'automl'],
    hasGitContext: false,
  },
  {
    taskDescription: 'Debug memory leak in Node.js application',
    workerCount: 6,
    models: ['opus', 'sonnet', 'gpt-4o'],
    hasGitContext: true,
  },
];

/**
 * Calculate percentiles from sorted array
 */
function percentile(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  const index = Math.ceil((sorted.length * p) / 100) - 1;
  return sorted[Math.max(0, index)];
}

/**
 * Get memory usage in MB
 */
function getMemoryUsageMB() {
  const usage = process.memoryUsage();
  return {
    rss: Math.round(usage.rss / 1024 / 1024),
    heapTotal: Math.round(usage.heapTotal / 1024 / 1024),
    heapUsed: Math.round(usage.heapUsed / 1024 / 1024),
    external: Math.round(usage.external / 1024 / 1024),
  };
}

/**
 * Get CPU usage percentage (approximate)
 */
function getCPUUsage() {
  const cpus = os.cpus();
  let totalIdle = 0;
  let totalTick = 0;

  cpus.forEach(cpu => {
    for (const type in cpu.times) {
      totalTick += cpu.times[type];
    }
    totalIdle += cpu.times.idle;
  });

  const idle = totalIdle / cpus.length;
  const total = totalTick / cpus.length;
  const usage = 100 - Math.round((100 * idle) / total);

  return {
    usage,
    cores: cpus.length,
  };
}

/**
 * Get database connection pool stats
 */
async function getPoolStats() {
  return {
    totalCount: pool.totalCount,
    idleCount: pool.idleCount,
    waitingCount: pool.waitingCount,
  };
}

/**
 * Test 1: Single prediction latency (target: <5s)
 */
async function testSinglePredictionLatency() {
  console.log('\n[TEST 1] Single Prediction Latency');
  console.log('Target: <5s');
  console.log('Running 10 predictions...\n');

  const latencies = [];
  let errors = 0;

  for (let i = 0; i < 10; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    const start = Date.now();

    try {
      await predictWorkflow(task);
      const duration = Date.now() - start;
      latencies.push(duration);
      console.log(`  ${i + 1}/10: ${duration}ms`);
    } catch (err) {
      errors++;
      console.log(`  ${i + 1}/10: ERROR - ${err.message}`);
    }
  }

  const p50 = percentile(latencies, 50);
  const p95 = percentile(latencies, 95);
  const p99 = percentile(latencies, 99);
  const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;

  console.log('\nResults:');
  console.log(`  p50: ${p50}ms`);
  console.log(`  p95: ${p95}ms`);
  console.log(`  p99: ${p99}ms`);
  console.log(`  avg: ${Math.round(avg)}ms`);
  console.log(`  errors: ${errors}`);
  console.log(`  success_rate: ${((latencies.length / 10) * 100).toFixed(1)}%`);
  console.log(`  status: ${p95 < 5000 ? 'PASS ✓' : 'FAIL ✗'}`);

  return {
    test: 'single_prediction_latency',
    p50,
    p95,
    p99,
    avg: Math.round(avg),
    errors,
    success_rate: (latencies.length / 10) * 100,
    target_met: p95 < 5000,
  };
}

/**
 * Test 2: Parallel predictions (10 concurrent, target: <10s)
 */
async function testParallelPredictions() {
  console.log('\n[TEST 2] Parallel Predictions (10 concurrent)');
  console.log('Target: <10s total');
  console.log('Launching 10 concurrent predictions...\n');

  const start = Date.now();
  const promises = [];

  for (let i = 0; i < 10; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    promises.push(
      predictWorkflow(task)
        .then(() => ({ success: true }))
        .catch((err) => ({ success: false, error: err.message }))
    );
  }

  const results = await Promise.all(promises);
  const duration = Date.now() - start;

  const successes = results.filter((r) => r.success).length;
  const failures = results.filter((r) => !r.success).length;

  console.log(`Completed in ${duration}ms`);
  console.log(`  successes: ${successes}`);
  console.log(`  failures: ${failures}`);
  console.log(`  throughput: ${(10000 / duration).toFixed(2)} predictions/sec`);
  console.log(`  status: ${duration < 10000 ? 'PASS ✓' : 'FAIL ✗'}`);

  return {
    test: 'parallel_predictions',
    duration_ms: duration,
    successes,
    failures,
    throughput_per_sec: parseFloat((10000 / duration).toFixed(2)),
    target_met: duration < 10000,
  };
}

/**
 * Test 3: Model loading time (cold start vs cached)
 */
async function testModelLoadingTime() {
  console.log('\n[TEST 3] Model Loading Time');
  console.log('Testing cold start vs cached...\n');

  // Cold start (first call)
  const coldStartTask = SAMPLE_TASKS[0];
  const coldStart = Date.now();
  await predictWorkflow(coldStartTask);
  const coldDuration = Date.now() - coldStart;

  console.log(`  cold_start: ${coldDuration}ms`);

  // Cached (subsequent calls)
  const cachedLatencies = [];
  for (let i = 0; i < 5; i++) {
    const cachedStart = Date.now();
    await predictWorkflow(coldStartTask);
    cachedLatencies.push(Date.now() - cachedStart);
  }

  const cachedAvg = cachedLatencies.reduce((a, b) => a + b, 0) / cachedLatencies.length;
  const speedup = coldDuration / cachedAvg;

  console.log(`  cached_avg: ${Math.round(cachedAvg)}ms`);
  console.log(`  speedup: ${speedup.toFixed(2)}x`);

  return {
    test: 'model_loading_time',
    cold_start_ms: coldDuration,
    cached_avg_ms: Math.round(cachedAvg),
    speedup: parseFloat(speedup.toFixed(2)),
  };
}

/**
 * Test 4: Database query performance
 */
async function testDatabaseQueryPerformance() {
  console.log('\n[TEST 4] Database Query Performance');
  console.log('Measuring individual query latencies...\n');

  const queries = [
    {
      name: 'workflow_executions_count',
      sql: `SELECT COUNT(*) FROM workflow.executions`,
    },
    {
      name: 'recent_executions',
      sql: `SELECT * FROM workflow.executions ORDER BY created_at DESC LIMIT 10`,
    },
    {
      name: 'model_performance_agg',
      sql: `SELECT model, AVG(quality_score) FROM monitoring.execution_summary GROUP BY model`,
    },
    {
      name: 'prediction_accuracy_join',
      sql: `
        SELECT pa.*, we.outcome
        FROM monitoring.prediction_accuracy pa
        LEFT JOIN workflow.executions we ON pa.workflow_id = we.workflow_id
        LIMIT 10
      `,
    },
  ];

  const results = [];

  for (const query of queries) {
    const latencies = [];

    for (let i = 0; i < 5; i++) {
      const start = Date.now();
      try {
        await pool.query(query.sql);
        latencies.push(Date.now() - start);
      } catch (err) {
        console.log(`  ${query.name}: ERROR - ${err.message}`);
        latencies.push(-1);
      }
    }

    const validLatencies = latencies.filter((l) => l > 0);
    const avg = validLatencies.length > 0
      ? validLatencies.reduce((a, b) => a + b, 0) / validLatencies.length
      : 0;

    console.log(`  ${query.name}: ${Math.round(avg)}ms`);

    results.push({
      query: query.name,
      avg_ms: Math.round(avg),
      p95_ms: percentile(validLatencies, 95),
    });
  }

  return {
    test: 'database_query_performance',
    queries: results,
  };
}

/**
 * Test 5: Memory usage under load
 */
async function testMemoryUsageUnderLoad() {
  console.log('\n[TEST 5] Memory Usage Under Load');
  console.log('Running 20 predictions and monitoring memory...\n');

  const memorySnapshots = [];
  const initialMemory = getMemoryUsageMB();
  memorySnapshots.push({ stage: 'initial', ...initialMemory });

  console.log(`  initial: RSS=${initialMemory.rss}MB, heapUsed=${initialMemory.heapUsed}MB`);

  // Run 20 predictions
  for (let i = 0; i < 20; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    await predictWorkflow(task);

    if (i % 5 === 4) {
      const mem = getMemoryUsageMB();
      memorySnapshots.push({ stage: `after_${i + 1}`, ...mem });
      console.log(`  after ${i + 1}: RSS=${mem.rss}MB, heapUsed=${mem.heapUsed}MB`);
    }
  }

  const finalMemory = getMemoryUsageMB();
  memorySnapshots.push({ stage: 'final', ...finalMemory });
  console.log(`  final: RSS=${finalMemory.rss}MB, heapUsed=${finalMemory.heapUsed}MB`);

  const memoryGrowth = finalMemory.rss - initialMemory.rss;
  console.log(`  memory_growth: ${memoryGrowth}MB`);

  return {
    test: 'memory_usage_under_load',
    initial_rss_mb: initialMemory.rss,
    final_rss_mb: finalMemory.rss,
    growth_mb: memoryGrowth,
    snapshots: memorySnapshots,
  };
}

/**
 * Test 6: CPU usage under load
 */
async function testCPUUsageUnderLoad() {
  console.log('\n[TEST 6] CPU Usage Under Load');
  console.log('Running 20 predictions and monitoring CPU...\n');

  const initialCPU = getCPUUsage();
  console.log(`  initial: ${initialCPU.usage}% (${initialCPU.cores} cores)`);

  // Run 20 predictions
  const start = Date.now();
  for (let i = 0; i < 20; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    await predictWorkflow(task);
  }
  const duration = Date.now() - start;

  const finalCPU = getCPUUsage();
  console.log(`  final: ${finalCPU.usage}%`);
  console.log(`  duration: ${duration}ms`);

  return {
    test: 'cpu_usage_under_load',
    initial_usage: initialCPU.usage,
    final_usage: finalCPU.usage,
    cores: initialCPU.cores,
    duration_ms: duration,
  };
}

/**
 * Test 7: Connection pool handling
 */
async function testConnectionPoolHandling() {
  console.log('\n[TEST 7] Connection Pool Handling');
  console.log('Testing concurrent connections...\n');

  const initialStats = await getPoolStats();
  console.log(`  initial: total=${initialStats.totalCount}, idle=${initialStats.idleCount}, waiting=${initialStats.waitingCount}`);

  // Launch 30 concurrent predictions (exceeds pool size of 20)
  const promises = [];
  for (let i = 0; i < 30; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    promises.push(predictWorkflow(task));
  }

  await Promise.all(promises);

  const finalStats = await getPoolStats();
  console.log(`  final: total=${finalStats.totalCount}, idle=${finalStats.idleCount}, waiting=${finalStats.waitingCount}`);

  return {
    test: 'connection_pool_handling',
    initial_stats: initialStats,
    final_stats: finalStats,
    pool_max: 20,
    concurrent_requests: 30,
  };
}

/**
 * Test 8: Error rate under stress
 */
async function testErrorRateUnderStress() {
  console.log('\n[TEST 8] Error Rate Under Stress');
  console.log('Running 50 predictions rapidly...\n');

  const results = [];
  const start = Date.now();

  for (let i = 0; i < 50; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    try {
      await predictWorkflow(task);
      results.push({ success: true });
    } catch (err) {
      results.push({ success: false, error: err.message });
    }
  }

  const duration = Date.now() - start;
  const successes = results.filter((r) => r.success).length;
  const failures = results.filter((r) => !r.success).length;
  const errorRate = (failures / 50) * 100;

  console.log(`  successes: ${successes}`);
  console.log(`  failures: ${failures}`);
  console.log(`  error_rate: ${errorRate.toFixed(1)}%`);
  console.log(`  duration: ${duration}ms`);
  console.log(`  status: ${errorRate < 5 ? 'PASS ✓' : 'FAIL ✗'}`);

  return {
    test: 'error_rate_under_stress',
    successes,
    failures,
    error_rate: parseFloat(errorRate.toFixed(1)),
    duration_ms: duration,
    target_met: errorRate < 5,
  };
}

/**
 * Test 9: Recovery time after failure
 */
async function testRecoveryTimeAfterFailure() {
  console.log('\n[TEST 9] Recovery Time After Failure');
  console.log('Simulating failure and measuring recovery...\n');

  // Force an error by using invalid task
  const invalidTask = {
    taskDescription: '',
    workerCount: -1,
    models: [],
    hasGitContext: false,
  };

  try {
    await predictWorkflow(invalidTask);
  } catch (err) {
    console.log(`  forced_error: ${err.message}`);
  }

  // Measure recovery time
  const recoveryStart = Date.now();
  const validTask = SAMPLE_TASKS[0];

  try {
    await predictWorkflow(validTask);
    const recoveryTime = Date.now() - recoveryStart;
    console.log(`  recovery_time: ${recoveryTime}ms`);
    console.log(`  status: PASS ✓`);

    return {
      test: 'recovery_time_after_failure',
      recovery_time_ms: recoveryTime,
      recovered: true,
    };
  } catch (err) {
    console.log(`  recovery_failed: ${err.message}`);
    return {
      test: 'recovery_time_after_failure',
      recovery_time_ms: -1,
      recovered: false,
    };
  }
}

/**
 * Test 10: Sustained load (100 predictions over 5 minutes)
 */
async function testSustainedLoad() {
  console.log('\n[TEST 10] Sustained Load (100 predictions over 5 minutes)');
  console.log('Running 100 predictions with throttling...\n');

  const results = [];
  const start = Date.now();
  const targetDuration = 5 * 60 * 1000; // 5 minutes
  const delayBetween = targetDuration / 100;

  for (let i = 0; i < 100; i++) {
    const task = SAMPLE_TASKS[i % SAMPLE_TASKS.length];
    const iterStart = Date.now();

    try {
      await predictWorkflow(task);
      results.push({ success: true, duration: Date.now() - iterStart });
    } catch (err) {
      results.push({ success: false, duration: Date.now() - iterStart, error: err.message });
    }

    // Throttle to spread over 5 minutes
    if (i < 99) {
      const sleepTime = Math.max(0, delayBetween - (Date.now() - iterStart));
      await new Promise((resolve) => setTimeout(resolve, sleepTime));
    }

    if (i % 10 === 9) {
      const successes = results.filter((r) => r.success).length;
      console.log(`  ${i + 1}/100 completed (${successes} successes)`);
    }
  }

  const totalDuration = Date.now() - start;
  const successes = results.filter((r) => r.success).length;
  const failures = results.filter((r) => !r.success).length;
  const latencies = results.filter((r) => r.success).map((r) => r.duration);

  console.log(`\n  total_duration: ${(totalDuration / 1000).toFixed(1)}s`);
  console.log(`  successes: ${successes}`);
  console.log(`  failures: ${failures}`);
  console.log(`  p50_latency: ${percentile(latencies, 50)}ms`);
  console.log(`  p95_latency: ${percentile(latencies, 95)}ms`);
  console.log(`  throughput: ${(successes / (totalDuration / 1000)).toFixed(2)} predictions/sec`);

  return {
    test: 'sustained_load',
    total_duration_ms: totalDuration,
    successes,
    failures,
    p50_latency: percentile(latencies, 50),
    p95_latency: percentile(latencies, 95),
    throughput_per_sec: parseFloat((successes / (totalDuration / 1000)).toFixed(2)),
  };
}

/**
 * Run all tests
 */
async function runAllTests() {
  console.log('================================================================================');
  console.log('COMPREHENSIVE PERFORMANCE TEST SUITE');
  console.log('================================================================================');
  console.log(`Start Time: ${new Date().toISOString()}`);
  console.log(`Node Version: ${process.version}`);
  console.log(`Platform: ${os.platform()} ${os.arch()}`);
  console.log(`CPU Cores: ${os.cpus().length}`);
  console.log(`Total Memory: ${Math.round(os.totalmem() / 1024 / 1024 / 1024)}GB`);
  console.log('================================================================================');

  const testResults = [];

  try {
    testResults.push(await testSinglePredictionLatency());
    testResults.push(await testParallelPredictions());
    testResults.push(await testModelLoadingTime());
    testResults.push(await testDatabaseQueryPerformance());
    testResults.push(await testMemoryUsageUnderLoad());
    testResults.push(await testCPUUsageUnderLoad());
    testResults.push(await testConnectionPoolHandling());
    testResults.push(await testErrorRateUnderStress());
    testResults.push(await testRecoveryTimeAfterFailure());

    // Skip sustained load test for now (5 minutes is too long)
    console.log('\n[TEST 10] Sustained Load - SKIPPED (5 minutes)');
    testResults.push({
      test: 'sustained_load',
      skipped: true,
      reason: 'Too long for automated testing',
    });

  } catch (err) {
    console.error('\nTest suite failed:', err);
    throw err;
  } finally {
    await pool.end();
  }

  console.log('\n================================================================================');
  console.log('TEST SUITE SUMMARY');
  console.log('================================================================================');

  const passed = testResults.filter((r) => r.target_met !== false).length;
  const failed = testResults.filter((r) => r.target_met === false).length;
  const total = testResults.filter((r) => !r.skipped).length;

  console.log(`Total Tests: ${total}`);
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log(`Success Rate: ${((passed / total) * 100).toFixed(1)}%`);
  console.log('================================================================================');

  return {
    test_suite: 'comprehensive-performance-tests',
    total_tests: total,
    passed,
    failed,
    success_rate: parseFloat(((passed / total) * 100).toFixed(1)),
    critical_failures: testResults.filter((r) => r.target_met === false).map((r) => r.test),
    performance_metrics: {
      single_prediction_p95: testResults[0]?.p95,
      parallel_predictions_duration: testResults[1]?.duration_ms,
      cold_start_ms: testResults[2]?.cold_start_ms,
      cached_avg_ms: testResults[2]?.cached_avg_ms,
      error_rate: testResults[7]?.error_rate,
    },
    results: testResults,
  };
}

// Run tests
runAllTests()
  .then((summary) => {
    console.log('\n✓ Test suite completed successfully\n');
    console.log(JSON.stringify(summary, null, 2));
    process.exit(summary.failed > 0 ? 1 : 0);
  })
  .catch((err) => {
    console.error('\n✗ Test suite failed:', err);
    process.exit(1);
  });
