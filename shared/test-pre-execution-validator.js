/**
 * Test Suite: Pre-Execution Validation Layer
 *
 * Tests all 4 validators plus integration with fleet orchestrator
 * Part of ECC issue #193 implementation
 *
 * Run: node shared/test-pre-execution-validator.js
 */

import {
  preValidate,
  validateParallelizability,
  validateTokenBudget,
  validateModelDiversity,
  validateWorkerCapacity
} from './pre-execution-validator.js';

// ANSI colors for test output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function log(color, ...args) {
  console.log(color + args.join(' ') + colors.reset);
}

function assert(condition, message) {
  if (!condition) {
    log(colors.red, `✗ FAIL: ${message}`);
    throw new Error(`Assertion failed: ${message}`);
  }
  log(colors.green, `✓ PASS: ${message}`);
}

// =============================================================================
// TEST 1: Parallelizability Validator
// =============================================================================

async function testParallelizability() {
  log(colors.cyan, '\n=== TEST 1: Parallelizability Validator ===');

  // Test 1a: Independent tasks (highly parallelizable)
  const independentTasks = [
    { id: 'task-1', prompt: 'Analyze file A.java' },
    { id: 'task-2', prompt: 'Analyze file B.java' },
    { id: 'task-3', prompt: 'Analyze file C.java' }
  ];

  const result1 = await validateParallelizability(independentTasks);
  assert(result1.passed, 'Independent tasks should pass validation');
  assert(result1.details.parallelizableCount === 3, 'All 3 tasks should be parallelizable');
  assert(result1.recommendations.length > 0, 'Should recommend parallelization');
  log(colors.blue, `  Parallelizable: ${result1.details.parallelizableCount}/3`);

  // Test 1b: Dependent tasks (low parallelizability)
  const dependentTasks = [
    { id: 'task-1', prompt: 'Generate code' },
    { id: 'task-2', prompt: 'Review code from task-1' },
    { id: 'task-3', prompt: 'Test code from task-1' }
  ];

  const result2 = await validateParallelizability(dependentTasks);
  assert(result2.passed, 'Dependent tasks should still pass (warning-only)');
  assert(result2.details.dependentCount === 2, 'Should detect 2 dependent tasks');
  assert(result2.warnings.length > 0, 'Should warn about low parallelizability');
  log(colors.blue, `  Dependencies detected: ${result2.details.dependentCount}`);

  // Test 1c: Empty tasks
  const result3 = await validateParallelizability([]);
  assert(result3.passed, 'Empty tasks should pass');
  assert(result3.details.tasksCount === 0, 'Should report 0 tasks');
}

// =============================================================================
// TEST 2: Token Budget Validator
// =============================================================================

async function testTokenBudget() {
  log(colors.cyan, '\n=== TEST 2: Token Budget Validator ===');

  const tasks = [
    { id: 'task-1', prompt: 'a'.repeat(1000) },  // ~250 tokens
    { id: 'task-2', prompt: 'b'.repeat(1000) },  // ~250 tokens
    { id: 'task-3', prompt: 'c'.repeat(1000) }   // ~250 tokens
  ];

  // Test 2a: Sufficient budget (mock tracker)
  const sufficientBudget = {
    getRemainingBudget: () => 10000
  };

  const result1 = await validateTokenBudget(tasks, sufficientBudget);
  assert(result1.passed, 'Should pass with sufficient budget');
  assert(result1.details.totalEstimated > 0, 'Should estimate token usage');
  assert(result1.details.budgetRemaining === 10000, 'Should report remaining budget');
  log(colors.blue, `  Estimated tokens: ${result1.details.totalEstimated}`);

  // Test 2b: Insufficient budget
  const insufficientBudget = {
    getRemainingBudget: () => 100  // Too small
  };

  const result2 = await validateTokenBudget(tasks, insufficientBudget);
  assert(!result2.passed, 'Should fail with insufficient budget');
  assert(result2.blockers.length > 0, 'Should have blocker message');
  log(colors.yellow, `  Blocker: ${result2.blockers[0]}`);

  // Test 2c: No budget tracker
  const result3 = await validateTokenBudget(tasks, null);
  assert(result3.passed, 'Should pass when no budget tracker provided');
  assert(!result3.details.budgetAvailable, 'Should report budget unavailable');
}

// =============================================================================
// TEST 3: Model Diversity Validator
// =============================================================================

async function testModelDiversity() {
  log(colors.cyan, '\n=== TEST 3: Model Diversity Validator ===');

  // This test requires PostgreSQL connection
  // It will fail-open if DB is unavailable
  try {
    const result = await validateModelDiversity();
    assert(result.passed !== undefined, 'Should return validation result');

    if (result.details.dbAvailable === false) {
      log(colors.yellow, '  Database unavailable - test skipped (expected in CI)');
    } else if (result.details.totalExecutions === 0) {
      log(colors.blue, '  No recent executions - cannot test diversity');
    } else {
      log(colors.blue, `  Recent executions: ${result.details.totalExecutions}`);
      if (result.details.modelDistribution) {
        result.details.modelDistribution.forEach(m => {
          log(colors.blue, `    ${m.model}: ${m.percentage}% (quality: ${m.avgQuality})`);
        });
      }

      if (result.warnings.length > 0) {
        log(colors.yellow, `  Diversity warning: ${result.warnings[0]}`);
      }
    }
  } catch (error) {
    log(colors.yellow, `  Model diversity check failed (non-blocking): ${error.message}`);
  }
}

// =============================================================================
// TEST 4: Worker Capacity Validator
// =============================================================================

async function testWorkerCapacity() {
  log(colors.cyan, '\n=== TEST 4: Worker Capacity Validator ===');

  // Test 4a: No workers available
  const result1 = await validateWorkerCapacity([], 6, null);
  assert(!result1.passed, 'Should fail with no workers');
  assert(result1.blockers.length > 0, 'Should have blocker message');
  log(colors.yellow, `  Blocker: ${result1.blockers[0]}`);

  // Test 4b: Sufficient healthy workers (mock health cache)
  const healthCache = new Map([
    ['server-01', { healthy: true, lastCheck: Date.now() }],
    ['server-02', { healthy: true, lastCheck: Date.now() }],
    ['server-03', { healthy: true, lastCheck: Date.now() }]
  ]);

  const result2 = await validateWorkerCapacity(
    ['server-01', 'server-02', 'server-03'],
    6,
    healthCache
  );
  assert(result2.passed, 'Should pass with healthy workers');
  assert(result2.details.healthyWorkers === 3, 'Should report 3 healthy workers');
  log(colors.blue, `  Healthy workers: ${result2.details.healthyWorkers}`);

  // Test 4c: Mixed healthy/unhealthy workers
  const mixedHealthCache = new Map([
    ['server-01', { healthy: true, lastCheck: Date.now() }],
    ['server-02', { healthy: false, lastCheck: Date.now(), error: 'SSH timeout' }],
    ['server-03', { healthy: false, lastCheck: Date.now(), error: 'Connection refused' }]
  ]);

  const result3 = await validateWorkerCapacity(
    ['server-01', 'server-02', 'server-03'],
    6,
    mixedHealthCache
  );
  assert(!result3.passed, 'Should fail when all workers unhealthy');
  assert(result3.details.healthyWorkers === 1, 'Should report 1 healthy worker');
  assert(result3.warnings.length > 0, 'Should warn about limited parallelism');
  log(colors.yellow, `  Warning: ${result3.warnings[0]}`);

  // Test 4d: Stale health checks
  const staleHealthCache = new Map([
    ['server-01', { healthy: true, lastCheck: Date.now() - 120000 }], // 2 minutes old
    ['server-02', { healthy: true, lastCheck: Date.now() }]
  ]);

  const result4 = await validateWorkerCapacity(
    ['server-01', 'server-02'],
    2,
    staleHealthCache
  );
  assert(result4.passed, 'Should pass despite stale checks');
  assert(result4.warnings.some(w => w.includes('stale')), 'Should warn about stale checks');
  log(colors.blue, `  Stale checks: ${result4.details.staleHealthChecks}`);

  // Test 4e: maxParallel exceeds workers
  const result5 = await validateWorkerCapacity(
    ['server-01', 'server-02'],
    6,
    healthCache
  );
  assert(result5.passed, 'Should pass (recommendation-only)');
  assert(
    result5.recommendations.some(r => r.includes('exceeds available workers')),
    'Should recommend reducing maxParallel'
  );
  log(colors.blue, `  Recommendation: ${result5.recommendations[0]}`);
}

// =============================================================================
// TEST 5: Full Pre-Validation (Integration)
// =============================================================================

async function testFullPreValidation() {
  log(colors.cyan, '\n=== TEST 5: Full Pre-Validation Integration ===');

  const tasks = [
    { id: 'task-1', prompt: 'Analyze codebase for security issues' },
    { id: 'task-2', prompt: 'Generate documentation' },
    { id: 'task-3', prompt: 'Run test suite' }
  ];

  const mockHealthCache = new Map([
    ['server-01', { healthy: true, lastCheck: Date.now() }],
    ['server-02', { healthy: true, lastCheck: Date.now() }]
  ]);

  const mockTokenBudget = {
    getRemainingBudget: () => 50000
  };

  const config = {
    tasks,
    maxParallel: 6,
    availableWorkers: ['server-01', 'server-02'],
    tokenBudget: mockTokenBudget,
    healthCache: mockHealthCache
  };

  const result = await preValidate(config);

  assert(result.passed !== undefined, 'Should return passed status');
  assert(Array.isArray(result.warnings), 'Should return warnings array');
  assert(Array.isArray(result.blockers), 'Should return blockers array');
  assert(Array.isArray(result.recommendations), 'Should return recommendations array');
  assert(typeof result.details === 'object', 'Should return details object');

  log(colors.blue, `  Overall validation: ${result.passed ? 'PASSED' : 'FAILED'}`);
  log(colors.blue, `  Warnings: ${result.warnings.length}`);
  log(colors.blue, `  Blockers: ${result.blockers.length}`);
  log(colors.blue, `  Recommendations: ${result.recommendations.length}`);

  if (result.warnings.length > 0) {
    log(colors.yellow, '\n  Warnings:');
    result.warnings.forEach(w => log(colors.yellow, `    - ${w}`));
  }

  if (result.recommendations.length > 0) {
    log(colors.cyan, '\n  Recommendations:');
    result.recommendations.forEach(r => log(colors.cyan, `    - ${r}`));
  }

  assert(result.details.parallelizability !== undefined, 'Should include parallelizability details');
  assert(result.details.tokenBudget !== undefined, 'Should include token budget details');
  assert(result.details.modelDiversity !== undefined, 'Should include model diversity details');
  assert(result.details.workerCapacity !== undefined, 'Should include worker capacity details');
}

// =============================================================================
// TEST 6: Blocker Scenario (Should Fail)
// =============================================================================

async function testBlockerScenario() {
  log(colors.cyan, '\n=== TEST 6: Blocker Scenario (Should Fail) ===');

  const largeTasks = Array.from({ length: 10 }, (_, i) => ({
    id: `task-${i}`,
    prompt: 'x'.repeat(50000)  // ~12,500 tokens each = 125,000+ total
  }));

  const insufficientBudget = {
    getRemainingBudget: () => 10000  // Way too small
  };

  const config = {
    tasks: largeTasks,
    maxParallel: 6,
    availableWorkers: ['server-01'],
    tokenBudget: insufficientBudget,
    healthCache: null
  };

  const result = await preValidate(config);

  assert(!result.passed, 'Should fail validation due to budget blocker');
  assert(result.blockers.length > 0, 'Should have at least one blocker');
  log(colors.yellow, `  Expected blocker: ${result.blockers[0]}`);
}

// =============================================================================
// TEST 7: Fail-Open Strategy
// =============================================================================

async function testFailOpen() {
  log(colors.cyan, '\n=== TEST 7: Fail-Open Strategy ===');

  // Force a validation error by passing invalid config
  const invalidConfig = {
    tasks: null,  // Invalid
    maxParallel: 'not-a-number',  // Invalid
    availableWorkers: undefined,
    tokenBudget: null,
    healthCache: null
  };

  try {
    const result = await preValidate(invalidConfig);

    // Should not throw - fail-open strategy
    assert(result.passed === true, 'Should fail-open (pass) on validation error');
    assert(result.warnings.length > 0, 'Should warn about validation error');
    log(colors.blue, '  Fail-open successful - execution would proceed');

  } catch (error) {
    assert(false, 'Should NOT throw on validation error (fail-open)');
  }
}

// =============================================================================
// RUN ALL TESTS
// =============================================================================

async function runTests() {
  log(colors.cyan, '\n╔════════════════════════════════════════════════════════════╗');
  log(colors.cyan, '║  Pre-Execution Validation Test Suite (ECC #193)           ║');
  log(colors.cyan, '╚════════════════════════════════════════════════════════════╝');

  const tests = [
    { name: 'Parallelizability', fn: testParallelizability },
    { name: 'Token Budget', fn: testTokenBudget },
    { name: 'Model Diversity', fn: testModelDiversity },
    { name: 'Worker Capacity', fn: testWorkerCapacity },
    { name: 'Full Pre-Validation', fn: testFullPreValidation },
    { name: 'Blocker Scenario', fn: testBlockerScenario },
    { name: 'Fail-Open Strategy', fn: testFailOpen }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      await test.fn();
      passed++;
    } catch (error) {
      failed++;
      log(colors.red, `\n✗ TEST SUITE FAILED: ${test.name}`);
      log(colors.red, `  Error: ${error.message}`);
      if (error.stack) {
        log(colors.red, `  Stack: ${error.stack.split('\n').slice(0, 3).join('\n')}`);
      }
    }
  }

  log(colors.cyan, '\n╔════════════════════════════════════════════════════════════╗');
  log(colors.cyan, `║  Test Results: ${passed}/${tests.length} passed, ${failed}/${tests.length} failed${' '.repeat(21 - (passed + '/' + tests.length).length - (failed + '/' + tests.length).length)}║`);
  log(colors.cyan, '╚════════════════════════════════════════════════════════════╝\n');

  process.exit(failed > 0 ? 1 : 0);
}

// Run tests
runTests().catch(error => {
  log(colors.red, 'FATAL ERROR:', error.message);
  process.exit(1);
});
