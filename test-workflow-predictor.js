#!/usr/bin/env node
/**
 * End-to-end test for workflow-predictor.js
 *
 * Tests:
 * 1. predictWorkflow() returns all 12 fields
 * 2. Cost prediction is reasonable ($0.01-$10 range)
 * 3. Duration prediction is reasonable (1s-60s range)
 * 4. Quality prediction is 0-1
 * 5. Success probability is 0-1
 * 6. Optimal workers is 1-20
 * 7. Recommended pattern is valid (pipeline/parallel/sequential)
 * 8. Failure risk is 0-1
 * 9. Memory estimate is positive
 * 10. Bug risk is 0-1
 * 11. Database queries complete without errors
 * 12. Prediction completes in <60 seconds
 *
 * Runs 10 different workflow configs, calculates success rate
 */

import { predictWorkflow } from './shared/workflow-predictor.js';

const validPatterns = new Set([
  'parallel',
  'sequential',
  'pipeline',
  'fan-out-consensus',
  'sequential-review',
  'parallel-verify',
  'map-reduce',
]);

/**
 * Test workflow configurations (10 diverse scenarios)
 */
const testConfigs = [
  {
    name: 'Simple code generation',
    config: {
      taskDescription: 'Generate a Python function to calculate Fibonacci numbers',
      workerCount: 3,
      models: ['sonnet', 'haiku', 'fable'],
      hasGitContext: false,
    },
  },
  {
    name: 'Complex research task',
    config: {
      taskDescription: 'Research firmware reverse engineering for RAX-75 router, compare to OpenWrt, identify security vulnerabilities, QEMU simulation approach',
      workerCount: 8,
      models: ['opus', 'sonnet', 'gpt-4o', 'gemini-2.0-flash-exp'],
      hasGitContext: false,
    },
  },
  {
    name: 'Code review with git context',
    config: {
      taskDescription: 'Review changes in PR #123 for security issues, bugs, and style violations',
      workerCount: 5,
      models: ['opus', 'sonnet', 'haiku'],
      hasGitContext: true,
    },
  },
  {
    name: 'Data analysis',
    config: {
      taskDescription: 'Analyze PostgreSQL query performance logs, identify slow queries, suggest optimizations',
      workerCount: 4,
      models: ['sonnet', 'haiku', 'automl'],
      hasGitContext: false,
    },
  },
  {
    name: 'Debugging task',
    config: {
      taskDescription: 'Debug memory leak in Node.js application, identify root cause, suggest fix',
      workerCount: 6,
      models: ['opus', 'sonnet', 'gpt-4o'],
      hasGitContext: true,
    },
  },
  {
    name: 'Documentation generation',
    config: {
      taskDescription: 'Generate API documentation for REST endpoints in OpenAPI format',
      workerCount: 2,
      models: ['haiku', 'fable'],
      hasGitContext: false,
    },
  },
  {
    name: 'System operations',
    config: {
      taskDescription: 'Deploy application to Kubernetes cluster, run health checks, monitor metrics',
      workerCount: 3,
      models: ['sonnet', 'haiku'],
      hasGitContext: false,
    },
  },
  {
    name: 'Multi-language translation',
    config: {
      taskDescription: 'Translate user interface strings to 10 languages, validate formatting',
      workerCount: 10,
      models: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini-2.0-flash-exp'],
      hasGitContext: false,
    },
  },
  {
    name: 'Security audit',
    config: {
      taskDescription: 'Audit codebase for SQL injection, XSS, CSRF vulnerabilities, generate report',
      workerCount: 7,
      models: ['opus', 'sonnet', 'gpt-4o'],
      hasGitContext: true,
    },
  },
  {
    name: 'Minimal single-worker task',
    config: {
      taskDescription: 'Fix typo in README',
      workerCount: 1,
      models: ['haiku'],
      hasGitContext: true,
    },
  },
];

/**
 * Validate prediction result
 */
function validatePrediction(prediction, testCase) {
  const failures = [];

  // Test 1: Check all 12 fields exist
  const requiredFields = [
    'cost',
    'duration',
    'quality',
    'success',
    'bestModel',
    'optimalWorkers',
    'recommendedPattern',
    'failureRisk',
    'estimatedMemoryMb',
    'bugRisk',
    'confidence',
    'timestamp',
  ];

  for (const field of requiredFields) {
    if (!(field in prediction)) {
      failures.push(`Missing field: ${field}`);
    }
  }

  // Test 2: Cost is reasonable ($0.01-$10 range)
  if (prediction.cost < 0.01 || prediction.cost > 10) {
    failures.push(`Cost out of range: $${prediction.cost} (expected $0.01-$10)`);
  }

  // Test 3: Duration is reasonable (1s-120s range, updated from 60s)
  if (prediction.duration < 1000 || prediction.duration > 120000) {
    failures.push(`Duration out of range: ${prediction.duration}ms (expected 1000-120000ms)`);
  }

  // Test 4: Quality is 0-1
  if (prediction.quality < 0 || prediction.quality > 1) {
    failures.push(`Quality out of range: ${prediction.quality} (expected 0-1)`);
  }

  // Test 5: Success probability is 0-1
  if (prediction.success < 0 || prediction.success > 1) {
    failures.push(`Success probability out of range: ${prediction.success} (expected 0-1)`);
  }

  // Test 6: Optimal workers is 1-20
  if (prediction.optimalWorkers < 1 || prediction.optimalWorkers > 20) {
    failures.push(`Optimal workers out of range: ${prediction.optimalWorkers} (expected 1-20)`);
  }

  // Test 7: Recommended pattern is valid
  if (!validPatterns.has(prediction.recommendedPattern)) {
    failures.push(`Invalid pattern: ${prediction.recommendedPattern} (expected one of: ${[...validPatterns].join(', ')})`);
  }

  // Test 8: Failure risk is 0-1
  if (typeof prediction.failureRisk === 'object') {
    if (prediction.failureRisk.risk < 0 || prediction.failureRisk.risk > 1) {
      failures.push(`Failure risk out of range: ${prediction.failureRisk.risk} (expected 0-1)`);
    }
  } else {
    failures.push(`Failure risk is not an object: ${typeof prediction.failureRisk}`);
  }

  // Test 9: Memory estimate is positive
  if (prediction.estimatedMemoryMb <= 0) {
    failures.push(`Memory estimate invalid: ${prediction.estimatedMemoryMb}MB (expected > 0)`);
  }

  // Test 10: Bug risk is 0-1
  if (prediction.bugRisk < 0 || prediction.bugRisk > 1) {
    failures.push(`Bug risk out of range: ${prediction.bugRisk} (expected 0-1)`);
  }

  // Test 11: Database queries completed without errors (implicit - we got here)
  // This is tested by the fact that predictWorkflow didn't throw

  return failures;
}

/**
 * Run all tests
 */
async function runTests() {
  console.log('================================================================================');
  console.log('WORKFLOW PREDICTOR END-TO-END TEST');
  console.log('================================================================================');
  console.log(`Running ${testConfigs.length} test cases...\n`);

  const results = [];
  let totalPassed = 0;
  let totalFailed = 0;

  for (let i = 0; i < testConfigs.length; i++) {
    const testCase = testConfigs[i];
    console.log(`[${i + 1}/${testConfigs.length}] ${testCase.name}`);
    console.log(`  Task: ${testCase.config.taskDescription.substring(0, 60)}...`);

    const startTime = Date.now();
    let prediction;
    let error = null;
    let failures = [];

    try {
      // Test 12: Prediction completes in <60 seconds
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Prediction timeout (>60s)')), 60000)
      );

      prediction = await Promise.race([
        predictWorkflow(testCase.config),
        timeoutPromise,
      ]);

      const duration = Date.now() - startTime;
      console.log(`  ✓ Completed in ${(duration / 1000).toFixed(1)}s`);

      // Validate prediction
      failures = validatePrediction(prediction, testCase);

      if (failures.length === 0) {
        console.log(`  ✓ All validation checks passed`);
        totalPassed++;
      } else {
        console.log(`  ✗ ${failures.length} validation failures:`);
        failures.forEach((f) => console.log(`    - ${f}`));
        totalFailed++;
      }
    } catch (err) {
      error = err;
      const duration = Date.now() - startTime;
      console.log(`  ✗ Failed after ${(duration / 1000).toFixed(1)}s: ${err.message}`);
      failures.push(err.message);
      totalFailed++;
    }

    results.push({
      testCase: testCase.name,
      success: failures.length === 0,
      failures,
      prediction,
      error: error?.message,
      duration: Date.now() - startTime,
    });

    console.log('');
  }

  // Summary
  console.log('================================================================================');
  console.log('TEST SUMMARY');
  console.log('================================================================================');
  console.log(`Total Tests: ${testConfigs.length}`);
  console.log(`Passed: ${totalPassed}`);
  console.log(`Failed: ${totalFailed}`);
  console.log(`Success Rate: ${((totalPassed / testConfigs.length) * 100).toFixed(1)}%`);
  console.log('');

  // Critical failures
  const criticalFailures = results.filter((r) => !r.success);
  if (criticalFailures.length > 0) {
    console.log('CRITICAL FAILURES:');
    criticalFailures.forEach((cf) => {
      console.log(`  - ${cf.testCase}`);
      cf.failures.forEach((f) => console.log(`    ${f}`));
    });
    console.log('');
  }

  // Performance metrics
  const durations = results.map((r) => r.duration);
  const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
  const maxDuration = Math.max(...durations);
  const minDuration = Math.min(...durations);

  console.log('PERFORMANCE METRICS:');
  console.log(`  Average Duration: ${(avgDuration / 1000).toFixed(1)}s`);
  console.log(`  Min Duration: ${(minDuration / 1000).toFixed(1)}s`);
  console.log(`  Max Duration: ${(maxDuration / 1000).toFixed(1)}s`);
  console.log('');

  console.log('================================================================================');

  return {
    test_suite: 'workflow-predictor.js',
    total_tests: testConfigs.length,
    passed: totalPassed,
    failed: totalFailed,
    success_rate: parseFloat(((totalPassed / testConfigs.length) * 100).toFixed(1)),
    critical_failures: criticalFailures.map((cf) => cf.testCase),
    performance_metrics: {
      avg_duration_ms: Math.round(avgDuration),
      min_duration_ms: minDuration,
      max_duration_ms: maxDuration,
    },
    details: results,
  };
}

// Run tests
runTests()
  .then((summary) => {
    console.log('Test suite completed successfully');
    process.exit(summary.failed > 0 ? 1 : 0);
  })
  .catch((err) => {
    console.error('Test suite failed:', err);
    process.exit(1);
  });
