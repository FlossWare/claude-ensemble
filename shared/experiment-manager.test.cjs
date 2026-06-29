/**
 * Test Suite for experiment-manager.cjs
 *
 * Tests all pure-function statistical logic without requiring PostgreSQL.
 * Database-dependent functions (recordExperiment, getExperimentHistory) are
 * tested via integration tests only.
 *
 * Run: node shared/experiment-manager.test.cjs
 */

const em = require('./experiment-manager.cjs');

// ============================================================================
// TEST FRAMEWORK
// ============================================================================

let testCount = 0;
let passCount = 0;
let failCount = 0;

function assert(condition, message) {
  testCount++;
  if (condition) {
    passCount++;
    console.log('ok ' + testCount + ' - ' + message);
  } else {
    failCount++;
    console.log('not ok ' + testCount + ' - ' + message);
  }
}

function assertApprox(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  assert(diff <= tolerance, message + ' (expected ~' + expected + ', got ' + actual + ')');
}

function assertEqual(actual, expected, message) {
  assert(actual === expected, message + ' (expected ' + JSON.stringify(expected) + ', got ' + JSON.stringify(actual) + ')');
}

function test(name, fn) {
  console.log('# ' + name);
  try {
    fn();
  } catch (err) {
    testCount++;
    failCount++;
    console.log('not ok ' + testCount + ' - Uncaught error: ' + err.message);
  }
}

// ============================================================================
// TESTS: Basic statistics
// ============================================================================

test('mean - standard cases', function() {
  assertApprox(em.mean([1, 2, 3, 4, 5]), 3, 0.001, 'Mean of [1..5]');
  assertApprox(em.mean([10]), 10, 0.001, 'Mean of single element');
  assertApprox(em.mean([]), 0, 0.001, 'Mean of empty array');
  assertApprox(em.mean([-1, 0, 1]), 0, 0.001, 'Mean with negatives');
});

test('variance - standard cases', function() {
  assertApprox(em.variance([1, 2, 3, 4, 5]), 2.5, 0.001, 'Variance of [1..5]');
  assertApprox(em.variance([5, 5, 5]), 0, 0.001, 'Variance of constant');
  assertApprox(em.variance([1]), 0, 0.001, 'Variance of single element');
  assertApprox(em.variance([]), 0, 0.001, 'Variance of empty');
});

test('stddev - standard cases', function() {
  assertApprox(em.stddev([1, 2, 3, 4, 5]), Math.sqrt(2.5), 0.01, 'Stddev of [1..5]');
  assertApprox(em.stddev([5, 5, 5, 5]), 0, 0.001, 'Stddev of constant');
});

// ============================================================================
// TESTS: Welch's t-test
// ============================================================================

test('welchTTest - identical samples', function() {
  const r = em.welchTTest([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]);
  assertApprox(r.t_stat, 0, 0.001, 'T-stat is 0 for identical samples');
  assertApprox(r.p_value, 1, 0.001, 'P-value is 1 for identical samples');
});

test('welchTTest - clearly different samples', function() {
  const r = em.welchTTest([1, 2, 3, 4, 5], [10, 11, 12, 13, 14]);
  assert(r.p_value < 0.001, 'P-value < 0.001 for very different samples (got ' + r.p_value + ')');
  assert(r.t_stat > 0, 'Positive t-stat when group2 > group1 (welchTTest computes m2-m1) (got ' + r.t_stat + ')');
});

test('welchTTest - overlapping samples', function() {
  const r = em.welchTTest([1, 2, 3, 4, 5], [3, 4, 5, 6, 7]);
  assert(r.p_value > 0.01, 'P-value > 0.01 for overlapping samples (got ' + r.p_value + ')');
});

test('welchTTest - zero variance', function() {
  const r = em.welchTTest([5, 5, 5], [5, 5, 5]);
  assertApprox(r.t_stat, 0, 0.001, 'T-stat 0 for same constant');
  assertApprox(r.p_value, 1, 0.001, 'P-value 1 for same constant');

  const r2 = em.welchTTest([5, 5, 5], [10, 10, 10]);
  assert(r2.p_value < 0.001, 'P-value tiny for different constants');
});

// ============================================================================
// TESTS: tDistPValue
// ============================================================================

test('tDistPValue - edge cases', function() {
  assertApprox(em.tDistPValue(0, 10), 1.0, 0.001, 'P-value = 1 at t=0');
  assert(em.tDistPValue(100, 10) < 0.001, 'P-value near 0 for extreme t');
  assertApprox(em.tDistPValue(Infinity, 10), 0, 0.001, 'P-value 0 for Infinity');
});

// ============================================================================
// TESTS: lnGamma
// ============================================================================

test('lnGamma - known values', function() {
  // lnGamma(1) = 0 (since Gamma(1) = 1)
  assertApprox(em.lnGamma(1), 0, 0.001, 'lnGamma(1) = 0');
  // lnGamma(0.5) = ln(sqrt(pi)) ~= 0.5723
  assertApprox(em.lnGamma(0.5), 0.5724, 0.001, 'lnGamma(0.5)');
  // lnGamma(5) = ln(24) ~= 3.1781
  assertApprox(em.lnGamma(5), Math.log(24), 0.001, 'lnGamma(5) = ln(4!)');
});

// ============================================================================
// TESTS: regularizedIncompleteBeta
// ============================================================================

test('regularizedIncompleteBeta - boundary values', function() {
  assertApprox(em.regularizedIncompleteBeta(0, 2, 3), 0, 0.001, 'I_0(a,b) = 0');
  assertApprox(em.regularizedIncompleteBeta(1, 2, 3), 1, 0.001, 'I_1(a,b) = 1');
});

// ============================================================================
// TESTS: bootstrapDifference
// ============================================================================

test('bootstrapDifference - no difference', function() {
  const r = em.bootstrapDifference([5, 5, 5, 5, 5], [5, 5, 5, 5, 5]);
  assertApprox(r.effect_size, 0, 0.001, 'Effect size 0 for identical');
  assertApprox(r.ci_lower, 0, 0.1, 'CI lower near 0');
  assertApprox(r.ci_upper, 0, 0.1, 'CI upper near 0');
});

test('bootstrapDifference - clear difference', function() {
  const r = em.bootstrapDifference([1, 2, 3, 4, 5], [10, 11, 12, 13, 14]);
  assert(r.ci_lower > 0, 'CI lower > 0 for positive difference');
  assert(r.ci_upper > 0, 'CI upper > 0 for positive difference');
  assert(Math.abs(r.effect_size) > 1, 'Large effect size');
});

// ============================================================================
// TESTS: compareResults
// ============================================================================

test('compareResults - invalid inputs', function() {
  const r = em.compareResults(null, [1, 2, 3]);
  assertEqual(r.verdict, 'inconclusive', 'Null baseline => inconclusive');
  assertEqual(r.significant, false, 'Not significant for invalid input');
});

test('compareResults - insufficient samples', function() {
  const r = em.compareResults([1], [2]);
  assertEqual(r.verdict, 'inconclusive', 'Single sample => inconclusive');
  assert(r.reason.includes('Insufficient'), 'Reason mentions insufficient');
});

test('compareResults - keep verdict (improvement)', function() {
  // Treatment clearly better
  const baseline = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.48, 0.52, 0.51, 0.49];
  const treatment = [0.70, 0.72, 0.68, 0.71, 0.69, 0.70, 0.68, 0.72, 0.71, 0.69];
  const r = em.compareResults(baseline, treatment);
  assertEqual(r.verdict, 'keep', 'Keep when treatment clearly better');
  assertEqual(r.significant, true, 'Significant');
  assert(r.improvement_pct > 30, 'Improvement > 30%');
});

test('compareResults - remove verdict (regression)', function() {
  // Treatment clearly worse
  const baseline = [0.70, 0.72, 0.68, 0.71, 0.69, 0.70, 0.68, 0.72, 0.71, 0.69];
  const treatment = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.48, 0.52, 0.51, 0.49];
  const r = em.compareResults(baseline, treatment);
  assertEqual(r.verdict, 'remove', 'Remove when treatment clearly worse');
  assertEqual(r.significant, true, 'Significant');
  assert(r.improvement_pct < -20, 'Negative improvement');
});

test('compareResults - inconclusive (no significant diff)', function() {
  // Very similar distributions
  const baseline = [0.50, 0.51, 0.49, 0.50, 0.51, 0.49, 0.50, 0.51, 0.49, 0.50];
  const treatment = [0.505, 0.515, 0.495, 0.505, 0.515, 0.495, 0.505, 0.515, 0.495, 0.505];
  const r = em.compareResults(baseline, treatment);
  assertEqual(r.verdict, 'inconclusive', 'Inconclusive for very similar distributions');
});

test('compareResults - custom alpha threshold', function() {
  const baseline = [0.50, 0.52, 0.48, 0.51, 0.49];
  const treatment = [0.55, 0.57, 0.53, 0.56, 0.54];
  const strict = em.compareResults(baseline, treatment, { alpha: 0.001 });
  const loose = em.compareResults(baseline, treatment, { alpha: 0.10 });
  // Strict alpha should be less likely to find significance
  assert(
    strict.significant === false || loose.significant === true,
    'Stricter alpha means less significant or same'
  );
});

// ============================================================================
// TESTS: runExperiment (no DB -- record=false)
// ============================================================================

let asyncPending = [];

function testAsync(name, fn) {
  console.log('# ' + name);
  asyncPending.push(fn().catch(function(err) {
    testCount++;
    failCount++;
    console.log('not ok ' + testCount + ' - Async error: ' + err.message);
  }));
}

testAsync('runExperiment - basic execution without DB', async function() {
  const result = await em.runExperiment({
    name: 'test-exp-no-db',
    hypothesis: 'Treatment improves quality',
    metric: 'quality',
    baseline: { mode: 'simple' },
    treatment: { mode: 'enhanced' },
    collector: async function(config) {
      if (config.mode === 'enhanced') {
        return [0.80, 0.82, 0.78, 0.81, 0.79, 0.80, 0.82, 0.78, 0.81, 0.79];
      }
      return [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.52, 0.48, 0.51, 0.49];
    },
    record: false,
  });

  assertEqual(result.name, 'test-exp-no-db', 'Experiment name preserved');
  assertEqual(result.metric, 'quality', 'Metric preserved');
  assertEqual(result.verdict, 'keep', 'Verdict is keep (treatment better)');
  assertEqual(result.significant, true, 'Result is significant');
  assert(result.improvement_pct > 50, 'Improvement > 50%');
  assert(result.p_value < 0.05, 'P-value < 0.05');
  assert(result.duration_ms >= 0, 'Duration measured');
});

testAsync('runExperiment - missing name throws', async function() {
  try {
    await em.runExperiment({
      metric: 'quality',
      collector: async function() { return [1, 2, 3]; },
      record: false,
    });
    assert(false, 'Should have thrown for missing name');
  } catch (err) {
    assert(err.message.includes('name'), 'Error mentions name');
  }
});

testAsync('runExperiment - missing collector throws', async function() {
  try {
    await em.runExperiment({
      name: 'test',
      metric: 'quality',
      record: false,
    });
    assert(false, 'Should have thrown for missing collector');
  } catch (err) {
    assert(err.message.includes('collector'), 'Error mentions collector');
  }
});

testAsync('runExperiment - collector failure is reported', async function() {
  try {
    await em.runExperiment({
      name: 'test-fail',
      metric: 'quality',
      baseline: {},
      treatment: {},
      collector: async function(config) {
        throw new Error('Simulated failure');
      },
      record: false,
    });
    assert(false, 'Should have thrown for collector failure');
  } catch (err) {
    assert(err.message.includes('Baseline collection failed'), 'Reports baseline failure');
  }
});

// ============================================================================
// TESTS: EXPERIMENT_CONFIG
// ============================================================================

test('EXPERIMENT_CONFIG defaults', function() {
  assertEqual(em.EXPERIMENT_CONFIG.alpha, 0.05, 'Default alpha');
  assertEqual(em.EXPERIMENT_CONFIG.min_samples, 5, 'Default min_samples');
  assertEqual(em.EXPERIMENT_CONFIG.bootstrap_iterations, 1000, 'Default bootstrap iters');
  assertApprox(em.EXPERIMENT_CONFIG.bootstrap_confidence, 0.95, 0.001, 'Default bootstrap confidence');
  assertEqual(em.EXPERIMENT_CONFIG.default_min_improvement_pct, 3, 'Default min improvement %');
});

// ============================================================================
// RESULTS
// ============================================================================

Promise.all(asyncPending).then(function() {
  console.log('');
  console.log('# Test Results');
  console.log('# Total: ' + testCount);
  console.log('# Passed: ' + passCount);
  console.log('# Failed: ' + failCount);
  console.log('');

  if (failCount === 0) {
    console.log('# All tests passed!');
    process.exit(0);
  } else {
    console.log('# Some tests failed.');
    process.exit(1);
  }
}).catch(function(err) {
  console.log('# Unexpected error in test suite: ' + err.message);
  process.exit(1);
});
