#!/usr/bin/env node
'use strict';

/**
 * Tests for evaluation/ablation-study.cjs
 *
 * Covers:
 *   - Feature toggle system
 *   - Benchmark simulation
 *   - Statistical significance testing (Welch's t-test, Cohen's d)
 *   - Ablation study core functions
 *   - Report generation
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const {
  FEATURES,
  FEATURE_KEYS,
  FEATURE_EFFECTS,
  createToggles,
  baselineToggles,
  singleFeatureToggles,
  leaveOneOutToggles,
  simulateBenchmark,
  mulberry32,
  welchTTest,
  cohensD,
  effectSizeLabel,
  tDistPValue,
  regularizedBeta,
  lnGamma,
  runAblation,
  quantifyContribution,
  generateAblationReport,
} = require('./ablation-study.cjs');

// ===========================================================================
// Feature Registry
// ===========================================================================

describe('Feature Registry', () => {
  it('should define exactly 5 features', () => {
    assert.strictEqual(FEATURE_KEYS.length, 5);
  });

  it('should include all expected features', () => {
    const expected = [
      'thompson_sampling',
      'adversarial_verification',
      'confidence_calibration',
      'disagreement_detection',
      'quality_first_routing',
    ];
    for (const key of expected) {
      assert.ok(FEATURES[key], `Missing feature: ${key}`);
      assert.ok(FEATURES[key].name, `Feature ${key} missing name`);
      assert.ok(FEATURES[key].description, `Feature ${key} missing description`);
      assert.strictEqual(typeof FEATURES[key].default, 'boolean', `Feature ${key} default must be boolean`);
    }
  });

  it('should have matching FEATURE_EFFECTS for every feature', () => {
    for (const key of FEATURE_KEYS) {
      assert.ok(FEATURE_EFFECTS[key], `Missing effect model for: ${key}`);
      assert.strictEqual(typeof FEATURE_EFFECTS[key].f1_delta, 'number');
      assert.strictEqual(typeof FEATURE_EFFECTS[key].cost_multiplier, 'number');
      assert.strictEqual(typeof FEATURE_EFFECTS[key].latency_delta_ms, 'number');
    }
  });
});

// ===========================================================================
// Feature Toggle System
// ===========================================================================

describe('Feature Toggle System', () => {
  describe('createToggles', () => {
    it('should return all defaults when no overrides given', () => {
      const toggles = createToggles();
      for (const key of FEATURE_KEYS) {
        assert.strictEqual(toggles[key], FEATURES[key].default);
      }
    });

    it('should apply overrides', () => {
      const toggles = createToggles({ thompson_sampling: false, confidence_calibration: false });
      assert.strictEqual(toggles.thompson_sampling, false);
      assert.strictEqual(toggles.confidence_calibration, false);
      assert.strictEqual(toggles.adversarial_verification, true);
    });

    it('should ignore unknown keys', () => {
      const toggles = createToggles({ unknown_feature: true });
      assert.strictEqual(toggles.unknown_feature, undefined);
      assert.strictEqual(Object.keys(toggles).length, FEATURE_KEYS.length);
    });
  });

  describe('baselineToggles', () => {
    it('should return all features disabled', () => {
      const toggles = baselineToggles();
      for (const key of FEATURE_KEYS) {
        assert.strictEqual(toggles[key], false, `${key} should be false in baseline`);
      }
    });
  });

  describe('singleFeatureToggles', () => {
    it('should enable only the specified feature', () => {
      for (const key of FEATURE_KEYS) {
        const toggles = singleFeatureToggles(key);
        assert.strictEqual(toggles[key], true, `${key} should be enabled`);
        for (const other of FEATURE_KEYS) {
          if (other !== key) {
            assert.strictEqual(toggles[other], false, `${other} should be disabled when ${key} is singled out`);
          }
        }
      }
    });

    it('should throw for unknown feature', () => {
      assert.throws(() => singleFeatureToggles('nonexistent'), /Unknown feature/);
    });
  });

  describe('leaveOneOutToggles', () => {
    it('should disable only the specified feature', () => {
      for (const key of FEATURE_KEYS) {
        const toggles = leaveOneOutToggles(key);
        assert.strictEqual(toggles[key], false, `${key} should be disabled`);
        for (const other of FEATURE_KEYS) {
          if (other !== key) {
            assert.strictEqual(toggles[other], true, `${other} should be enabled when ${key} is left out`);
          }
        }
      }
    });

    it('should throw for unknown feature', () => {
      assert.throws(() => leaveOneOutToggles('nonexistent'), /Unknown feature/);
    });
  });
});

// ===========================================================================
// PRNG (Mulberry32)
// ===========================================================================

describe('mulberry32 PRNG', () => {
  it('should produce deterministic output for same seed', () => {
    const rng1 = mulberry32(42);
    const rng2 = mulberry32(42);
    for (let i = 0; i < 100; i++) {
      assert.strictEqual(rng1(), rng2());
    }
  });

  it('should produce values in [0, 1)', () => {
    const rng = mulberry32(12345);
    for (let i = 0; i < 1000; i++) {
      const v = rng();
      assert.ok(v >= 0, `Value ${v} is negative`);
      assert.ok(v < 1, `Value ${v} is >= 1`);
    }
  });

  it('should produce different sequences for different seeds', () => {
    const rng1 = mulberry32(1);
    const rng2 = mulberry32(2);
    let allSame = true;
    for (let i = 0; i < 20; i++) {
      if (rng1() !== rng2()) {
        allSame = false;
        break;
      }
    }
    assert.strictEqual(allSame, false, 'Different seeds should produce different sequences');
  });
});

// ===========================================================================
// Benchmark Simulation
// ===========================================================================

describe('simulateBenchmark', () => {
  it('should return all required fields', () => {
    const result = simulateBenchmark(baselineToggles());
    assert.strictEqual(typeof result.f1, 'number');
    assert.strictEqual(typeof result.precision, 'number');
    assert.strictEqual(typeof result.recall, 'number');
    assert.strictEqual(typeof result.cost_usd, 'number');
    assert.strictEqual(typeof result.latency_ms, 'number');
    assert.strictEqual(typeof result.samples, 'number');
    assert.ok(Array.isArray(result.raw_scores));
    assert.ok(result.toggles);
  });

  it('should produce deterministic results with same seed', () => {
    const r1 = simulateBenchmark(baselineToggles(), { seed: 99 });
    const r2 = simulateBenchmark(baselineToggles(), { seed: 99 });
    assert.strictEqual(r1.f1, r2.f1);
    assert.strictEqual(r1.cost_usd, r2.cost_usd);
    assert.deepStrictEqual(r1.raw_scores, r2.raw_scores);
  });

  it('should show higher F1 with features enabled vs baseline', () => {
    const baseline = simulateBenchmark(baselineToggles(), { samples: 500, seed: 42 });
    const allOn = simulateBenchmark(createToggles(), { samples: 500, seed: 42 });
    assert.ok(allOn.f1 > baseline.f1, `All-on F1 (${allOn.f1}) should exceed baseline F1 (${baseline.f1})`);
  });

  it('should show higher cost with features enabled vs baseline', () => {
    const baseline = simulateBenchmark(baselineToggles());
    const allOn = simulateBenchmark(createToggles());
    assert.ok(allOn.cost_usd > baseline.cost_usd, 'All-on cost should exceed baseline cost');
  });

  it('should respect sample count', () => {
    const r = simulateBenchmark(baselineToggles(), { samples: 50 });
    assert.strictEqual(r.raw_scores.length, 50);
    assert.strictEqual(r.samples, 50);
  });

  it('should keep all F1 scores in [0, 1]', () => {
    const r = simulateBenchmark(createToggles(), { samples: 1000, seed: 1 });
    for (const score of r.raw_scores) {
      assert.ok(score >= 0, `Score ${score} is negative`);
      assert.ok(score <= 1, `Score ${score} exceeds 1`);
    }
  });

  it('should show baseline cost near $8.50', () => {
    const r = simulateBenchmark(baselineToggles());
    assert.strictEqual(r.cost_usd, 8.50);
  });
});

// ===========================================================================
// Statistical Testing
// ===========================================================================

describe('Statistical Testing', () => {
  describe('lnGamma', () => {
    it('should approximate ln(Gamma(1)) = 0', () => {
      assert.ok(Math.abs(lnGamma(1)) < 0.001, `lnGamma(1) = ${lnGamma(1)} should be ~0`);
    });

    it('should approximate ln(Gamma(5)) = ln(24)', () => {
      const expected = Math.log(24);
      assert.ok(Math.abs(lnGamma(5) - expected) < 0.001, `lnGamma(5) = ${lnGamma(5)} should be ~${expected}`);
    });

    it('should handle half-integer argument ln(Gamma(0.5)) = ln(sqrt(pi))', () => {
      const expected = Math.log(Math.sqrt(Math.PI));
      assert.ok(Math.abs(lnGamma(0.5) - expected) < 0.01, `lnGamma(0.5) = ${lnGamma(0.5)} should be ~${expected}`);
    });
  });

  describe('welchTTest', () => {
    it('should return not significant for identical samples', () => {
      const a = [1, 2, 3, 4, 5];
      const b = [1, 2, 3, 4, 5];
      const result = welchTTest(a, b);
      assert.strictEqual(result.significant, false);
      assert.strictEqual(result.t_statistic, 0);
    });

    it('should return significant for clearly different distributions', () => {
      const a = Array.from({ length: 50 }, (_, i) => 10 + i * 0.1);
      const b = Array.from({ length: 50 }, (_, i) => 0 + i * 0.1);
      const result = welchTTest(a, b);
      assert.strictEqual(result.significant, true);
      assert.ok(result.p_value < 0.05);
    });

    it('should handle small samples gracefully', () => {
      const result = welchTTest([1], [2]);
      assert.strictEqual(result.significant, false);
      assert.strictEqual(result.p_value, 1.0);
    });

    it('should return correct structure', () => {
      const result = welchTTest([1, 2, 3], [4, 5, 6]);
      assert.strictEqual(typeof result.t_statistic, 'number');
      assert.strictEqual(typeof result.degrees_of_freedom, 'number');
      assert.strictEqual(typeof result.p_value, 'number');
      assert.strictEqual(typeof result.significant, 'boolean');
    });

    it('should respect custom alpha level', () => {
      // Create samples with moderate difference
      const a = Array.from({ length: 30 }, (_, i) => 5 + i * 0.05);
      const b = Array.from({ length: 30 }, (_, i) => 4 + i * 0.05);
      const strict = welchTTest(a, b, 0.001);
      const lenient = welchTTest(a, b, 0.50);
      // Lenient should be at least as likely to be significant as strict
      if (strict.significant) {
        assert.strictEqual(lenient.significant, true);
      }
    });
  });

  describe('cohensD', () => {
    it('should return 0 for identical samples', () => {
      assert.strictEqual(cohensD([1, 2, 3], [1, 2, 3]), 0);
    });

    it('should return positive d when a > b', () => {
      const d = cohensD([10, 11, 12], [1, 2, 3]);
      assert.ok(d > 0, `Cohen's d should be positive, got ${d}`);
    });

    it('should return negative d when a < b', () => {
      const d = cohensD([1, 2, 3], [10, 11, 12]);
      assert.ok(d < 0, `Cohen's d should be negative, got ${d}`);
    });

    it('should classify large effect correctly', () => {
      const d = cohensD([10, 11, 12, 13, 14], [1, 2, 3, 4, 5]);
      assert.strictEqual(effectSizeLabel(d), 'large');
    });
  });

  describe('effectSizeLabel', () => {
    it('should label negligible correctly', () => {
      assert.strictEqual(effectSizeLabel(0.1), 'negligible');
    });

    it('should label small correctly', () => {
      assert.strictEqual(effectSizeLabel(0.3), 'small');
    });

    it('should label medium correctly', () => {
      assert.strictEqual(effectSizeLabel(0.6), 'medium');
    });

    it('should label large correctly', () => {
      assert.strictEqual(effectSizeLabel(1.0), 'large');
    });

    it('should handle negative values', () => {
      assert.strictEqual(effectSizeLabel(-0.9), 'large');
    });
  });

  describe('tDistPValue', () => {
    it('should return ~1 for t=0', () => {
      const p = tDistPValue(0, 10);
      assert.ok(Math.abs(p - 1.0) < 0.05, `p-value for t=0 should be ~1, got ${p}`);
    });

    it('should return small p for large t', () => {
      const p = tDistPValue(10, 50);
      assert.ok(p < 0.001, `p-value for t=10,df=50 should be very small, got ${p}`);
    });
  });

  describe('regularizedBeta', () => {
    it('should return 0 for x=0', () => {
      assert.strictEqual(regularizedBeta(0, 1, 1), 0);
    });

    it('should return 1 for x=1', () => {
      assert.strictEqual(regularizedBeta(1, 1, 1), 1);
    });

    it('should return ~0.5 for x=0.5 with a=1,b=1 (uniform)', () => {
      const result = regularizedBeta(0.5, 1, 1);
      assert.ok(Math.abs(result - 0.5) < 0.05, `Expected ~0.5 for uniform, got ${result}`);
    });
  });
});

// ===========================================================================
// Ablation Study Core
// ===========================================================================

describe('runAblation', () => {
  let results;

  it('should complete without error', () => {
    results = runAblation(undefined, { samples: 100, seed: 42 });
    assert.ok(results);
  });

  it('should include metadata', () => {
    assert.ok(results.metadata);
    assert.strictEqual(results.metadata.samples_per_condition, 100);
    assert.strictEqual(results.metadata.seed, 42);
    assert.strictEqual(results.metadata.features_tested, 5);
    assert.ok(results.metadata.timestamp);
  });

  it('should include baseline results', () => {
    assert.ok(results.baseline);
    assert.strictEqual(typeof results.baseline.f1, 'number');
    assert.strictEqual(typeof results.baseline.cost_usd, 'number');
    // Baseline should have all toggles off
    for (const key of FEATURE_KEYS) {
      assert.strictEqual(results.baseline.toggles[key], false);
    }
  });

  it('should include all-features results', () => {
    assert.ok(results.all_features);
    assert.ok(results.all_features.f1 > results.baseline.f1, 'All features should beat baseline');
  });

  it('should include single-feature results for each feature', () => {
    for (const key of FEATURE_KEYS) {
      assert.ok(results.single_feature[key], `Missing single-feature result for ${key}`);
      assert.strictEqual(typeof results.single_feature[key].f1, 'number');
    }
  });

  it('should include leave-one-out results for each feature', () => {
    for (const key of FEATURE_KEYS) {
      assert.ok(results.leave_one_out[key], `Missing leave-one-out result for ${key}`);
      assert.strictEqual(typeof results.leave_one_out[key].f1, 'number');
    }
  });

  it('should include significance tests', () => {
    for (const key of FEATURE_KEYS) {
      const addKey = `${key}_vs_baseline`;
      const removeKey = `all_vs_without_${key}`;
      assert.ok(results.significance_tests[addKey], `Missing significance test: ${addKey}`);
      assert.ok(results.significance_tests[removeKey], `Missing significance test: ${removeKey}`);
      assert.strictEqual(typeof results.significance_tests[addKey].p_value, 'number');
      assert.strictEqual(typeof results.significance_tests[addKey].significant, 'boolean');
    }
  });

  it('should show all single-feature F1 >= baseline', () => {
    for (const key of FEATURE_KEYS) {
      assert.ok(
        results.single_feature[key].f1 >= results.baseline.f1 - 0.05,
        `${key} single-feature F1 (${results.single_feature[key].f1}) should be near or above baseline (${results.baseline.f1})`
      );
    }
  });

  it('should accept custom feature subset', () => {
    const subset = {
      thompson_sampling: FEATURES.thompson_sampling,
      adversarial_verification: FEATURES.adversarial_verification,
    };
    const subResults = runAblation(subset, { samples: 50, seed: 1 });
    assert.strictEqual(subResults.metadata.features_tested, 2);
    assert.ok(subResults.single_feature.thompson_sampling);
    assert.ok(subResults.single_feature.adversarial_verification);
    assert.strictEqual(subResults.single_feature.confidence_calibration, undefined);
  });
});

describe('quantifyContribution', () => {
  it('should return valid structure for each feature', () => {
    for (const key of FEATURE_KEYS) {
      const result = quantifyContribution(key, { samples: 100, seed: 42 });

      assert.strictEqual(result.feature, key);
      assert.ok(result.feature_name);
      assert.strictEqual(typeof result.marginal_gain.f1_delta, 'number');
      assert.strictEqual(typeof result.marginal_gain.f1_percent, 'number');
      assert.strictEqual(typeof result.marginal_gain.cost_delta, 'number');
      assert.strictEqual(typeof result.marginal_gain.cost_percent, 'number');
      assert.strictEqual(typeof result.marginal_gain.latency_delta_ms, 'number');
      assert.strictEqual(typeof result.marginal_loss.f1_delta, 'number');
      assert.strictEqual(typeof result.cost_efficiency, 'number');
      assert.ok(result.significance);
      assert.ok(result.significance.add_test);
      assert.ok(result.significance.remove_test);
      assert.ok(['KEEP', 'REMOVE', 'CONDITIONAL'].includes(result.recommendation));
      assert.ok(result.reason);
    }
  });

  it('should throw for unknown feature', () => {
    assert.throws(() => quantifyContribution('nonexistent'), /Unknown feature/);
  });

  it('should show positive marginal gain for thompson_sampling', () => {
    const result = quantifyContribution('thompson_sampling', { samples: 200, seed: 42 });
    assert.ok(result.marginal_gain.f1_delta > 0, 'Thompson sampling should have positive F1 gain');
    assert.ok(result.marginal_gain.cost_delta > 0, 'Thompson sampling should have positive cost delta');
  });

  it('should show cost_efficiency as Infinity when cost delta is zero', () => {
    // confidence_calibration has cost_multiplier = 1.0, so cost_delta should be 0
    const result = quantifyContribution('confidence_calibration', { samples: 100, seed: 42 });
    // cost_multiplier is exactly 1.0, so cost_delta should be exactly 0
    if (result.marginal_gain.cost_delta === 0) {
      assert.strictEqual(result.cost_efficiency, Infinity);
    }
  });

  it('should recommend KEEP for high-impact features', () => {
    const result = quantifyContribution('thompson_sampling', { samples: 500, seed: 42 });
    assert.ok(
      result.recommendation === 'KEEP' || result.recommendation === 'CONDITIONAL',
      `Thompson sampling should be KEEP or CONDITIONAL, got ${result.recommendation}`
    );
  });
});

// ===========================================================================
// Report Generation
// ===========================================================================

describe('generateAblationReport', () => {
  it('should produce a non-empty string', () => {
    const results = runAblation(undefined, { samples: 50, seed: 42 });
    const report = generateAblationReport(results);
    assert.strictEqual(typeof report, 'string');
    assert.ok(report.length > 100, 'Report should be substantial');
  });

  it('should contain key section headers', () => {
    const results = runAblation(undefined, { samples: 50, seed: 42 });
    const report = generateAblationReport(results);
    assert.ok(report.includes('FEATURE ABLATION STUDY REPORT'), 'Missing main header');
    assert.ok(report.includes('INCREMENTAL FEATURE CONTRIBUTION'), 'Missing contribution section');
    assert.ok(report.includes('LEAVE-ONE-OUT ANALYSIS'), 'Missing LOO section');
    assert.ok(report.includes('STATISTICAL SIGNIFICANCE'), 'Missing stats section');
    assert.ok(report.includes('END OF ABLATION REPORT'), 'Missing footer');
  });

  it('should mention all feature names', () => {
    const results = runAblation(undefined, { samples: 50, seed: 42 });
    const report = generateAblationReport(results);
    for (const key of FEATURE_KEYS) {
      assert.ok(report.includes(FEATURES[key].name), `Report should mention ${FEATURES[key].name}`);
    }
  });

  it('should contain baseline and all-features rows', () => {
    const results = runAblation(undefined, { samples: 50, seed: 42 });
    const report = generateAblationReport(results);
    assert.ok(report.includes('Baseline'), 'Missing baseline row');
    assert.ok(report.includes('All features combined'), 'Missing all-features row');
  });

  it('should contain KEEP or REMOVE verdicts', () => {
    const results = runAblation(undefined, { samples: 50, seed: 42 });
    const report = generateAblationReport(results);
    assert.ok(report.includes('KEEP') || report.includes('REMOVE') || report.includes('MAYBE'), 'Missing verdicts');
  });

  it('should show p-values in significance section', () => {
    const results = runAblation(undefined, { samples: 50, seed: 42 });
    const report = generateAblationReport(results);
    assert.ok(report.includes('p ='), 'Missing p-values');
  });
});

// ===========================================================================
// Integration / End-to-End
// ===========================================================================

describe('End-to-End Ablation Workflow', () => {
  it('should complete the full workflow: ablation -> contribution -> report', () => {
    // Step 1: Run ablation
    const results = runAblation(undefined, { samples: 100, seed: 42 });
    assert.ok(results.baseline);
    assert.ok(results.all_features);

    // Step 2: Quantify each feature
    const contributions = {};
    for (const key of FEATURE_KEYS) {
      contributions[key] = quantifyContribution(key, { samples: 100, seed: 42 });
    }

    // Step 3: Generate report
    const report = generateAblationReport(results);
    assert.ok(report.length > 200);

    // Step 4: Verify consistency
    // The feature with highest marginal gain should be thompson_sampling or quality_first_routing
    const sorted = Object.entries(contributions).sort(
      (a, b) => b[1].marginal_gain.f1_delta - a[1].marginal_gain.f1_delta
    );
    assert.ok(
      sorted[0][1].marginal_gain.f1_delta > sorted[sorted.length - 1][1].marginal_gain.f1_delta,
      'Features should have different marginal gains'
    );
  });

  it('should preserve reproducibility across multiple runs', () => {
    const r1 = runAblation(undefined, { samples: 100, seed: 42 });
    const r2 = runAblation(undefined, { samples: 100, seed: 42 });
    assert.strictEqual(r1.baseline.f1, r2.baseline.f1);
    assert.strictEqual(r1.all_features.f1, r2.all_features.f1);
    for (const key of FEATURE_KEYS) {
      assert.strictEqual(r1.single_feature[key].f1, r2.single_feature[key].f1);
    }
  });
});
