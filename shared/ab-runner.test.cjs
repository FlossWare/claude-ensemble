/**
 * Comprehensive Test Suite for ab-runner.cjs
 *
 * Tests all functionality:
 * 1. Feature toggles (enable/disable/clear)
 * 2. Statistical functions (mean, stddev, percentile, etc.)
 * 3. Welch's t-test
 * 4. Cohen's d effect size
 * 5. Bootstrap confidence intervals
 * 6. A/B test runner with multiple variants
 * 7. Report generation
 * 8. Cost/latency/quality tradeoff analysis
 *
 * Run: node shared/ab-runner.test.cjs
 * With TAP reporter: node shared/ab-runner.test.cjs | grep -E "^(ok|not ok|# )"
 */

const abRunner = require('./ab-runner.cjs');

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
  assert(actual === expected, message + ' (expected ' + expected + ', got ' + actual + ')');
}

function test(name, fn) {
  console.log('# ' + name);
  try {
    fn();
  } catch (err) {
    failCount++;
    console.log('not ok - Uncaught error: ' + err.message);
  }
}

// ============================================================================
// TEST SUITE
// ============================================================================

test('Feature toggles', function() {
  abRunner.clearFeatures();

  // Initially disabled
  assertEqual(abRunner.isFeatureEnabled('test_feature'), false, 'Feature not enabled by default');

  // Enable feature
  abRunner.enableFeatures(['test_feature', 'another_feature']);
  assertEqual(abRunner.isFeatureEnabled('test_feature'), true, 'Feature can be enabled');
  assertEqual(abRunner.isFeatureEnabled('another_feature'), true, 'Multiple features can be enabled');

  // Check enabled features list
  const enabled = abRunner.getEnabledFeatures();
  assertEqual(enabled.includes('test_feature'), true, 'Enabled features list includes feature');
  assertEqual(enabled.length, 2, 'Exactly 2 features enabled');

  // Clear features
  abRunner.clearFeatures();
  assertEqual(abRunner.isFeatureEnabled('test_feature'), false, 'Features cleared');
  assertEqual(abRunner.getEnabledFeatures().length, 0, 'All features cleared');
});

test('Statistical functions - mean', function() {
  assertApprox(abRunner.mean([1, 2, 3, 4, 5]), 3, 0.001, 'Mean of [1,2,3,4,5]');
  assertApprox(abRunner.mean([10]), 10, 0.001, 'Mean of single element');
  assertApprox(abRunner.mean([]), 0, 0.001, 'Mean of empty array');
});

test('Statistical functions - stddev', function() {
  // stddev of [1,2,3,4,5] = sqrt(2.5) ≈ 1.581
  assertApprox(abRunner.stddev([1, 2, 3, 4, 5]), 1.581, 0.01, 'Stddev of [1,2,3,4,5]');
  assertApprox(abRunner.stddev([5, 5, 5]), 0, 0.001, 'Stddev of constant array');
});

test('Statistical functions - median', function() {
  assertApprox(abRunner.median([1, 2, 3, 4, 5]), 3, 0.001, 'Median of [1,2,3,4,5]');
  assertApprox(abRunner.median([1, 2, 3, 4]), 2.5, 0.001, 'Median of [1,2,3,4]');
  assertApprox(abRunner.median([42]), 42, 0.001, 'Median of single element');
});

test('Statistical functions - percentile', function() {
  const data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  assertApprox(abRunner.percentile(data, 0), 1, 0.001, '0th percentile');
  assertApprox(abRunner.percentile(data, 50), 5.5, 0.001, '50th percentile (median)');
  assertApprox(abRunner.percentile(data, 100), 10, 0.001, '100th percentile');
  assertApprox(abRunner.percentile(data, 25), 3.25, 0.1, '25th percentile');
});

test('Welch t-test - identical samples', function() {
  const sample = [1, 2, 3, 4, 5];
  const result = abRunner.welchTTest(sample, sample);
  assertApprox(result.t_statistic, 0, 0.001, 'T-statistic for identical samples');
  assertApprox(result.p_value, 1, 0.001, 'P-value for identical samples');
  assertEqual(result.significant, false, 'Identical samples not significant');
});

test('Welch t-test - different samples', function() {
  const sample1 = [1, 2, 3, 4, 5];
  const sample2 = [6, 7, 8, 9, 10];
  const result = abRunner.welchTTest(sample1, sample2);
  assert(result.p_value < 0.05, 'Different samples are significant (p < 0.05)');
  assertEqual(result.significant, true, 'Significant flag set');
});

test("Welch t-test - insufficient samples", function() {
  const result = abRunner.welchTTest([1], [2]);
  assert(result.warning === 'insufficient_samples', 'Warning for insufficient samples');
});

test('Cohen d effect size - no difference', function() {
  const sample = [1, 2, 3, 4, 5];
  const result = abRunner.cohensD(sample, sample);
  assertApprox(result.d, 0, 0.001, 'Cohens d for identical samples');
  assertEqual(result.magnitude, 'negligible', 'Magnitude is negligible');
});

test('Cohen d effect size - magnitude classification', function() {
  // Create samples with known difference
  const small = [0, 0.1, 0.2, 0.3, 0.4];
  const medium = [1, 1.2, 1.4, 1.6, 1.8];
  const result = abRunner.cohensD(small, medium);
  assert(result.magnitude === 'large', 'Large effect size detected');
  assert(Math.abs(result.d) > 0.8, 'Cohen d > 0.8 for large effect');
});

test('Bootstrap confidence interval - single value', function() {
  const data = [5, 5, 5, 5, 5];
  const ci = abRunner.bootstrapCI(data, 0.95, 100);
  assertApprox(ci.lower, 5, 0.1, 'CI lower bound');
  assertApprox(ci.upper, 5, 0.1, 'CI upper bound');
});

test('Bootstrap confidence interval - range', function() {
  const data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const ci = abRunner.bootstrapCI(data, 0.95, 1000);
  assert(ci.lower < ci.upper, 'CI lower < upper');
  assert(ci.lower >= 1, 'CI lower >= min');
  assert(ci.upper <= 10, 'CI upper <= max');
});

test('Synthetic handler - baseline', function() {
  abRunner.clearFeatures();
  const result = abRunner.syntheticHandler(0, []);
  assert(result.quality >= 0 && result.quality <= 1, 'Quality in [0,1]');
  assert(result.latency_ms > 0, 'Latency positive');
  assert(result.cost_usd >= 0, 'Cost non-negative');
});

test('Synthetic handler - thompson_sampling feature', function() {
  // Run multiple iterations to smooth out randomness
  let baselineQuality = 0;
  let baselineLatency = 0;
  let thompsonQuality = 0;
  let thompsonLatency = 0;
  const runs = 10;

  for (let i = 0; i < runs; i++) {
    abRunner.clearFeatures();
    const baseline = abRunner.syntheticHandler(i, []);
    baselineQuality += baseline.quality;
    baselineLatency += baseline.latency_ms;

    const withThompson = abRunner.syntheticHandler(i, ['thompson_sampling']);
    thompsonQuality += withThompson.quality;
    thompsonLatency += withThompson.latency_ms;
  }

  baselineQuality /= runs;
  baselineLatency /= runs;
  thompsonQuality /= runs;
  thompsonLatency /= runs;

  assert(
    thompsonQuality > baselineQuality,
    'Thompson sampling improves quality (avg over ' + runs + ' runs)'
  );
  assert(
    thompsonLatency > baselineLatency,
    'Thompson sampling increases latency (avg over ' + runs + ' runs)'
  );
});

test('Synthetic handler - adversarial_verification feature', function() {
  abRunner.clearFeatures();
  const baseline = abRunner.syntheticHandler(0, []);
  const withAdv = abRunner.syntheticHandler(0, ['adversarial_verification']);
  assert(
    withAdv.quality > baseline.quality,
    'Adversarial verification improves quality'
  );
  assert(
    withAdv.latency_ms > baseline.latency_ms,
    'Adversarial verification increases latency'
  );
});

test('Synthetic handler - caching feature', function() {
  abRunner.clearFeatures();
  const baseline = abRunner.syntheticHandler(0, []);
  const withCache = abRunner.syntheticHandler(0, ['caching']);
  assert(
    withCache.latency_ms < baseline.latency_ms,
    'Caching reduces latency'
  );
  assert(
    withCache.cost_usd < baseline.cost_usd,
    'Caching reduces cost'
  );
});

test('Synthetic handler - consensus feature', function() {
  abRunner.clearFeatures();
  const baseline = abRunner.syntheticHandler(0, []);
  const withConsensus = abRunner.syntheticHandler(0, ['consensus']);
  assert(
    withConsensus.quality > baseline.quality,
    'Consensus improves quality'
  );
  assert(
    withConsensus.latency_ms > baseline.latency_ms,
    'Consensus increases latency'
  );
  assert(
    withConsensus.cost_usd > baseline.cost_usd,
    'Consensus increases cost'
  );
});

test('Synthetic handler - combined features', function() {
  abRunner.clearFeatures();
  const combined = abRunner.syntheticHandler(0, [
    'thompson_sampling',
    'adversarial_verification',
    'caching',
  ]);
  assert(combined.quality >= 0 && combined.quality <= 1, 'Quality clamped to [0,1]');
  assert(combined.latency_ms >= 10, 'Latency has minimum bound');
  assert(combined.cost_usd >= 0, 'Cost non-negative');
});

// Storage for async tests
let asyncTestsPending = [];

function testAsync(name, fn) {
  console.log('# ' + name);
  asyncTestsPending.push(fn());
}

testAsync('A/B test runner - basic execution', async function() {
  const configs = [
    { name: 'baseline', features: [] },
    { name: 'variant_a', features: ['thompson_sampling'] },
  ];

  try {
    const results = await abRunner.runABTest('test_exp', configs, {
      iterations_per_variant: 5,
      warmup_iterations: 1,
    });

    assert(results.winner !== null, 'Winner determined');
    assert(results.statistics.status === 'success', 'Statistics computed');
    assert(results.report.includes('A/B Test Report'), 'Report generated');
    assert(results.raw.variants.baseline !== undefined, 'Baseline variant exists');
    assert(results.raw.variants.variant_a !== undefined, 'Variant A exists');
  } catch (err) {
    failCount++;
    console.log('not ok - Async test error: ' + err.message);
  }
});

testAsync('A/B test runner - measurements collected', async function() {
  const configs = [
    { name: 'baseline', features: [] },
  ];

  try {
    const results = await abRunner.runABTest('test_measurements', configs, {
      iterations_per_variant: 10,
      warmup_iterations: 0,
    });

    const baseline = results.raw.variants.baseline;
    assertEqual(baseline.measurements.length, 10, 'Correct number of measurements');
    assert(baseline.measurements[0].quality !== undefined, 'Quality recorded');
    assert(baseline.measurements[0].latency_ms !== undefined, 'Latency recorded');
    assert(baseline.measurements[0].cost_usd !== undefined, 'Cost recorded');
    assert(baseline.measurements[0].timestamp !== undefined, 'Timestamp recorded');
  } catch (err) {
    failCount++;
    console.log('not ok - Async test error: ' + err.message);
  }
});

testAsync('A/B test runner - custom handler', async function() {
  let handlerCalls = 0;
  const configs = [
    {
      name: 'custom',
      features: ['test_feature'],
      handler: async function(iteration, features) {
        handlerCalls++;
        return {
          quality: 0.95,
          latency_ms: 100,
          cost_usd: 0.02,
        };
      },
    },
  ];

  try {
    const results = await abRunner.runABTest('test_custom', configs, {
      iterations_per_variant: 5,
      warmup_iterations: 2,
    });

    const custom = results.raw.variants.custom;
    assertEqual(custom.measurements.length, 5, 'Correct measurements count');
    assert(handlerCalls > 5, 'Handler called for warmup + measurements');
    assertApprox(custom.measurements[0].quality, 0.95, 0.001, 'Custom quality value');
  } catch (err) {
    failCount++;
    console.log('not ok - Async test error: ' + err.message);
  }
});

testAsync('A/B test runner - timeout handling', async function() {
  const configs = [
    {
      name: 'slow',
      features: [],
      handler: async function() {
        return new Promise(function(resolve) {
          setTimeout(function() {
            resolve({ quality: 0.5, latency_ms: 5000, cost_usd: 0.01 });
          }, 100);
        });
      },
    },
  ];

  try {
    const results = await abRunner.runABTest('test_timeout', configs, {
      iterations_per_variant: 3,
      warmup_iterations: 0,
      timeout_ms: 50,
    });

    const slow = results.raw.variants.slow;
    assert(slow.errors.length > 0, 'Errors recorded for timeouts');
    assert(slow.errors[0].error.includes('Timeout'), 'Timeout error message');
  } catch (err) {
    failCount++;
    console.log('not ok - Async test error: ' + err.message);
  }
});

test('Compute statistics - insufficient variants', function() {
  const results = {
    variants: {
      baseline: {
        measurements: [
          { quality: 0.7, latency_ms: 500, cost_usd: 0.01 },
          { quality: 0.8, latency_ms: 450, cost_usd: 0.01 },
        ],
        errors: [],
      },
    },
  };

  const stats = abRunner.computeStatistics(results);
  assert(stats.status === 'insufficient_variants', 'Insufficient variants detected');
  assert(stats.message !== undefined, 'Error message provided');
});

test('Compute statistics - multiple variants', function() {
  const results = {
    variants: {
      a: {
        measurements: [
          { quality: 0.6, latency_ms: 500, cost_usd: 0.01 },
          { quality: 0.7, latency_ms: 550, cost_usd: 0.01 },
          { quality: 0.8, latency_ms: 450, cost_usd: 0.02 },
        ],
        errors: [],
      },
      b: {
        measurements: [
          { quality: 0.75, latency_ms: 400, cost_usd: 0.015 },
          { quality: 0.85, latency_ms: 420, cost_usd: 0.015 },
          { quality: 0.8, latency_ms: 430, cost_usd: 0.016 },
        ],
        errors: [],
      },
    },
  };

  const stats = abRunner.computeStatistics(results);
  assert(stats.status === 'success', 'Statistics computed');
  assert(stats.winner !== null, 'Winner selected');
  assert(stats.pairwise['a_vs_b'] !== undefined, 'Pairwise comparison');
  assert(stats.pairwise['a_vs_b'].quality !== undefined, 'Quality comparison');
});

test('Generate report - basic structure', function() {
  const results = {
    variants: {
      baseline: {
        measurements: [
          { quality: 0.7, latency_ms: 500, cost_usd: 0.01 },
          { quality: 0.75, latency_ms: 510, cost_usd: 0.01 },
        ],
        errors: [],
      },
      variant_b: {
        measurements: [
          { quality: 0.6, latency_ms: 600, cost_usd: 0.02 },
          { quality: 0.65, latency_ms: 590, cost_usd: 0.02 },
        ],
        errors: [],
      },
    },
  };

  const stats = abRunner.computeStatistics(results);
  const report = abRunner.generateReport(stats, 'test_experiment');

  assert(report.includes('A/B Test Report'), 'Report title');
  assert(report.includes('Winner'), 'Winner section');
  assert(report.includes('Variant Summaries'), 'Summaries section');
  assert(report.includes('Confidence Intervals'), 'CI section');
  assert(report.includes('Tradeoff'), 'Tradeoff section');
});

test('Generate report - includes metrics', function() {
  const results = {
    variants: {
      a: {
        measurements: [
          { quality: 0.8, latency_ms: 400, cost_usd: 0.01 },
          { quality: 0.85, latency_ms: 420, cost_usd: 0.01 },
        ],
        errors: [],
      },
      b: {
        measurements: [
          { quality: 0.6, latency_ms: 500, cost_usd: 0.02 },
          { quality: 0.65, latency_ms: 480, cost_usd: 0.02 },
        ],
        errors: [],
      },
    },
  };

  const stats = abRunner.computeStatistics(results);
  const report = abRunner.generateReport(stats, 'test_metrics');

  assert(report.includes('quality'), 'Quality metric');
  assert(report.includes('latency'), 'Latency metric');
  assert(report.includes('cost'), 'Cost metric');
  assert(report.includes('p-value'), 'P-value');
  assert(report.includes('Effect Size'), 'Effect size');
});

test('Default config constants', function() {
  const config = abRunner.DEFAULT_CONFIG;
  assertEqual(config.iterations_per_variant, 30, 'Iterations per variant');
  assertEqual(config.warmup_iterations, 3, 'Warmup iterations');
  assertEqual(config.timeout_ms, 30000, 'Timeout');
  assertEqual(config.confidence_level, 0.95, 'Confidence level');
  assertEqual(config.bootstrap_iterations, 1000, 'Bootstrap iterations');
});

test('Feature state isolation between tests', function() {
  abRunner.enableFeatures(['feature_a']);
  assertEqual(abRunner.isFeatureEnabled('feature_a'), true, 'Feature A enabled');

  abRunner.enableFeatures(['feature_b']);
  assertEqual(
    abRunner.isFeatureEnabled('feature_a'),
    false,
    'Feature A disabled when enabling Feature B'
  );
  assertEqual(abRunner.isFeatureEnabled('feature_b'), true, 'Feature B enabled');

  abRunner.clearFeatures();
  assertEqual(abRunner.isFeatureEnabled('feature_b'), false, 'Feature B cleared');
});

test('Tradeoff score calculation', function() {
  const results = {
    variants: {
      expensive: {
        measurements: [
          { quality: 0.95, latency_ms: 1000, cost_usd: 0.10 },
          { quality: 0.94, latency_ms: 1050, cost_usd: 0.10 },
        ],
        errors: [],
      },
      cheap: {
        measurements: [
          { quality: 0.7, latency_ms: 100, cost_usd: 0.01 },
          { quality: 0.72, latency_ms: 110, cost_usd: 0.01 },
        ],
        errors: [],
      },
    },
  };

  const stats = abRunner.computeStatistics(results);
  assert(stats.summaries.expensive.tradeoff_score.score > 0, 'Tradeoff score > 0');
  assert(
    stats.summaries.expensive.tradeoff_score.score <= 1,
    'Tradeoff score <= 1'
  );
  assert(stats.winner !== undefined, 'Winner determined by tradeoff');
});

// ============================================================================
// RESULTS
// ============================================================================

// Wait for all async tests to complete before printing results
Promise.all(asyncTestsPending).then(function() {
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
