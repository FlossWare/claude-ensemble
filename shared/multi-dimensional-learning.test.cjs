/**
 * Multi-Dimensional Learning Tests
 *
 * Comprehensive test suite for Thompson Sampling and experience tracking.
 * Tests cover:
 * - Beta distribution sampling
 * - Thompson Sampling strategy selection
 * - Bandit state updates (Bayesian conjugate)
 * - Experience storage and retrieval
 * - Performance analytics
 *
 * Created: 2026-06-28
 */

const assert = require('assert');
const mdl = require('./multi-dimensional-learning.cjs');

// Test utilities
let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
    testsPassed++;
  } catch (error) {
    console.error(`✗ ${name}`);
    console.error(`  ${error.message}`);
    testsFailed++;
  }
}

async function asyncTest(name, fn) {
  try {
    await fn();
    console.log(`✓ ${name}`);
    testsPassed++;
  } catch (error) {
    console.error(`✗ ${name}`);
    console.error(`  ${error.message}`);
    testsFailed++;
  }
}

// ============================================================================
// Unit Tests
// ============================================================================

test('makeCacheKey creates consistent keys', () => {
  const key1 = mdl.makeCacheKey('code_gen', 'bug_fix', 'opus');
  const key2 = mdl.makeCacheKey('code_gen', 'bug_fix', 'opus');
  assert.strictEqual(key1, key2, 'Same input should create same key');
  assert.strictEqual(key1, 'code_gen|bug_fix|opus');
});

test('makeCacheKey creates unique keys', () => {
  const key1 = mdl.makeCacheKey('code_gen', 'bug_fix', 'opus');
  const key2 = mdl.makeCacheKey('code_gen', 'refactor', 'opus');
  assert.notStrictEqual(key1, key2, 'Different inputs should create different keys');
});

test('sampleBeta returns value in [0, 1]', () => {
  // Sample multiple times to test randomness
  for (let i = 0; i < 100; i++) {
    const sample = mdl.sampleBeta(2, 2);
    assert(sample >= 0 && sample <= 1, `Sample ${sample} should be in [0, 1]`);
  }
});

test('sampleBeta with alpha > beta biases toward 1', () => {
  // High alpha should bias toward higher values
  const samples = [];
  for (let i = 0; i < 50; i++) {
    samples.push(mdl.sampleBeta(10, 1));
  }
  const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
  assert(mean > 0.7, `Mean ${mean} should be > 0.7 for Beta(10, 1)`);
});

test('sampleBeta with alpha < beta biases toward 0', () => {
  // Low alpha should bias toward lower values
  const samples = [];
  for (let i = 0; i < 50; i++) {
    samples.push(mdl.sampleBeta(1, 10));
  }
  const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
  assert(mean < 0.3, `Mean ${mean} should be < 0.3 for Beta(1, 10)`);
});

// ============================================================================
// Integration Tests (require database)
// ============================================================================

async function runIntegrationTests() {
  console.log('\n=== Integration Tests ===\n');

  // Check database connectivity
  let dbAvailable = false;
  try {
    const result = await mdl.pool.query('SELECT 1');
    dbAvailable = result.rows.length > 0;
  } catch (error) {
    console.warn('⚠ Database not available, skipping integration tests');
    console.warn(`  Error: ${error.message}`);
  }

  if (!dbAvailable) {
    console.log('Skipping integration tests (database unavailable)\n');
    return;
  }

  // Initialize schema
  await asyncTest('initializeSchema creates tables', async () => {
    await mdl.initializeSchema();
    const schemaExists = await mdl._checkSchema();
    assert(schemaExists, 'Schema should be initialized');
  });

  // Clear cache before tests
  mdl._clearCache();

  // Test selectStrategy with empty database
  await asyncTest('selectStrategy returns default for new capability', async () => {
    const choice = await mdl.selectStrategy('test_capability_1', 'test_task_1');
    assert(choice.strategy, 'Should return a strategy');
    assert(typeof choice.expected_reward === 'number', 'Should return expected_reward');
  });

  // Test updateStrategyBandit
  await asyncTest('updateStrategyBandit updates bandit state', async () => {
    mdl._clearCache();

    const cap = `test_capability_2_${Date.now()}`;
    const task = `test_task_2_${Date.now()}`;
    const strategy = 'test_strategy';

    // Initial update with success
    const result1 = await mdl.updateStrategyBandit(cap, task, strategy, {
      reward: 0.9,
      success: true
    });

    assert.strictEqual(result1.alpha, 2, 'Alpha should be 2 after one success');
    assert.strictEqual(result1.beta, 1, 'Beta should be 1 after one success');

    // Second update with failure
    const result2 = await mdl.updateStrategyBandit(cap, task, strategy, {
      reward: 0.3,
      success: false
    });

    assert.strictEqual(result2.alpha, 2, 'Alpha should stay 2');
    assert.strictEqual(result2.beta, 2, 'Beta should be 2 after one failure');
  });

  // Test selectStrategy with multiple candidates
  await asyncTest('selectStrategy samples all candidates', async () => {
    mdl._clearCache();

    const cap = 'test_capability_3';
    const task = 'test_task_3';
    const candidates = ['strategy-a', 'strategy-b', 'strategy-c'];

    // Initialize each with different rewards
    await mdl.updateStrategyBandit(cap, task, 'strategy-a', { reward: 0.9 });
    await mdl.updateStrategyBandit(cap, task, 'strategy-b', { reward: 0.5 });
    await mdl.updateStrategyBandit(cap, task, 'strategy-c', { reward: 0.3 });

    mdl._clearCache(); // Clear to force reload from DB

    const choice = await mdl.selectStrategy(cap, task, candidates);
    assert(candidates.includes(choice.strategy), 'Should select from candidates');
    assert(choice.all_candidates.length === 3, 'Should evaluate all 3 candidates');
  });

  // Test getPerformanceSummary
  await asyncTest('getPerformanceSummary aggregates correctly', async () => {
    mdl._clearCache();

    const cap = 'test_capability_4';
    const task = 'test_task_4';

    // Create multiple updates
    await mdl.updateStrategyBandit(cap, task, 'strat-1', { reward: 0.8 });
    await mdl.updateStrategyBandit(cap, task, 'strat-1', { reward: 0.9 });
    await mdl.updateStrategyBandit(cap, task, 'strat-2', { reward: 0.5 });

    const summary = await mdl.getPerformanceSummary(cap, task);

    assert.strictEqual(summary.capability, cap);
    assert.strictEqual(summary.task_type, task);
    assert(summary.strategies.length >= 2, 'Should have strategies');
    assert(summary.total_executions >= 3, 'Should count all executions');
  });

  // Test storeExperience
  await asyncTest('storeExperience stores with metadata', async () => {
    const experience = {
      capability: 'test_code_gen',
      task_type: 'test_bug_fix',
      strategy: 'test_model',
      task_description: 'Fix null pointer in validation.js',
      reward: 0.87,
      duration_ms: 3500,
      cost_usd: 0.02,
      metadata: { model: 'claude-opus', tokens_used: 1500 }
    };

    const result = await mdl.storeExperience(experience);

    assert(result.id, 'Should return experience ID');
    assert.strictEqual(result.capability, experience.capability);
    assert.strictEqual(result.task_type, experience.task_type);
    assert.strictEqual(result.strategy, experience.strategy);
  });

  // Test storeExperience validates inputs
  await asyncTest('storeExperience validates required fields', async () => {
    const incompleteExperience = {
      capability: 'test_code_gen',
      // missing task_type, strategy, task_description
      reward: 0.87
    };

    let errorThrown = false;
    try {
      await mdl.storeExperience(incompleteExperience);
    } catch (error) {
      errorThrown = error.message.includes('required fields');
    }

    assert(errorThrown, 'Should throw for missing required fields');
  });

  // Test getLearningStatistics
  await asyncTest('getLearningStatistics groups correctly', async () => {
    const stats = await mdl.getLearningStatistics({
      by_capability: true,
      by_task_type: false,
      by_strategy: false
    });

    // Should have at least one row from previous tests
    assert(Array.isArray(stats), 'Should return array');
    if (stats.length > 0) {
      assert(stats[0].capability, 'Should have capability field');
      assert(typeof stats[0].executions === 'number', 'Should have executions count');
    }
  });

  // Test Thompson Sampling convergence behavior
  await asyncTest('Thompson Sampling favors high-reward strategies', async () => {
    mdl._clearCache();

    const cap = 'test_convergence';
    const task = 'test_task';
    const good_strat = 'good-strategy';
    const bad_strat = 'bad-strategy';

    // Train good strategy with high rewards
    for (let i = 0; i < 10; i++) {
      await mdl.updateStrategyBandit(cap, task, good_strat, { reward: 0.95 });
    }

    // Train bad strategy with low rewards
    for (let i = 0; i < 10; i++) {
      await mdl.updateStrategyBandit(cap, task, bad_strat, { reward: 0.15 });
    }

    mdl._clearCache();

    // Sample many times
    let good_count = 0;
    for (let i = 0; i < 100; i++) {
      const choice = await mdl.selectStrategy(cap, task, [good_strat, bad_strat]);
      if (choice.strategy === good_strat) good_count++;
    }

    // Should select good strategy >80% of the time
    assert(good_count > 80, `Should select good strategy >80% (got ${good_count}%)`);
  });
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  console.log('=== Multi-Dimensional Learning Tests ===\n');

  // Run unit tests
  console.log('=== Unit Tests ===\n');

  test('makeCacheKey creates consistent keys', () => {
    const key1 = mdl.makeCacheKey('code_gen', 'bug_fix', 'opus');
    const key2 = mdl.makeCacheKey('code_gen', 'bug_fix', 'opus');
    assert.strictEqual(key1, key2);
  });

  test('makeCacheKey creates unique keys', () => {
    const key1 = mdl.makeCacheKey('code_gen', 'bug_fix', 'opus');
    const key2 = mdl.makeCacheKey('code_gen', 'refactor', 'opus');
    assert.notStrictEqual(key1, key2);
  });

  test('sampleBeta returns value in [0, 1]', () => {
    for (let i = 0; i < 100; i++) {
      const sample = mdl.sampleBeta(2, 2);
      assert(sample >= 0 && sample <= 1);
    }
  });

  test('sampleBeta with alpha > beta biases toward 1', () => {
    const samples = [];
    for (let i = 0; i < 50; i++) {
      samples.push(mdl.sampleBeta(10, 1));
    }
    const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
    assert(mean > 0.7, `Mean ${mean} should be > 0.7`);
  });

  test('sampleBeta with alpha < beta biases toward 0', () => {
    const samples = [];
    for (let i = 0; i < 50; i++) {
      samples.push(mdl.sampleBeta(1, 10));
    }
    const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
    assert(mean < 0.3, `Mean ${mean} should be < 0.3`);
  });

  // Run integration tests
  await runIntegrationTests();

  // Summary
  console.log(`\n=== Summary ===\n`);
  console.log(`Passed: ${testsPassed}`);
  console.log(`Failed: ${testsFailed}`);
  console.log(`Total:  ${testsPassed + testsFailed}`);

  // Exit with appropriate code
  process.exit(testsFailed > 0 ? 1 : 0);
}

main().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
