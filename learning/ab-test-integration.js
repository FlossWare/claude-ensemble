#!/usr/bin/env node

/**
 * A/B Test Integration for Learning System
 *
 * Wires shared/ab-runner.cjs into the active learning system.
 * Provides high-level A/B testing for multi-AI system improvements.
 *
 * Features:
 * 1. runABTestFromPlan(experiment) - Execute A/B test from learning plan
 * 2. runFeatureComparisonTest(baseline, treatment, samples) - Compare features
 * 3. recordABTestResult(result) - Store in PostgreSQL
 * 4. getABTestHistory(filters) - Query past A/B tests
 *
 * Integration points:
 * - shared/ab-runner.cjs (statistical framework)
 * - shared/experiment-manager.cjs (PostgreSQL storage)
 * - learning/experiment-executor.js (experiment orchestration)
 * - shared/experiment-integration.cjs (system-specific experiments)
 *
 * Usage:
 *   const { runABTestFromPlan } = require('./ab-test-integration.js');
 *   const result = await runABTestFromPlan(learningPlanExperiment);
 *
 * Created: 2026-07-01
 * Issue: #262
 */

const { runABTest, computeStatistics, generateReport } = require('../shared/ab-runner.cjs');
const { recordExperiment, getExperimentHistory } = require('../shared/experiment-manager.cjs');
const path = require('path');
const fs = require('fs');

// ============================================================================
// CONFIGURATION
// ============================================================================

const AB_TEST_CONFIG = {
  /** Default samples per variant */
  default_samples: 30,

  /** Default warmup iterations */
  default_warmup: 3,

  /** Default timeout per iteration (30s) */
  default_timeout_ms: 30000,

  /** Minimum samples for valid results */
  min_samples: 5,

  /** Report output directory */
  reports_dir: path.join(process.env.HOME || '/root', '.claude', 'learning', 'ab-test-reports'),
};

// ============================================================================
// CORE API
// ============================================================================

/**
 * Run A/B test from a learning plan experiment specification
 *
 * @param {Object} experiment - Learning plan experiment object
 * @param {string} experiment.opportunity - Description of what's being tested
 * @param {string} experiment.type - Experiment type
 * @param {Array<Object>} experiment.variants - Variant configurations
 * @param {Function} experiment.handler - async (iteration, features) => { quality, latency_ms, cost_usd }
 * @param {Object} [options] - Override defaults
 * @returns {Promise<Object>} { winner, statistics, report, raw, stored }
 *
 * Example:
 *   const result = await runABTestFromPlan({
 *     opportunity: 'Compare Thompson Sampling vs Random routing',
 *     type: 'routing_strategy',
 *     variants: [
 *       { name: 'baseline', features: [] },
 *       { name: 'thompson', features: ['thompson_sampling'] }
 *     ],
 *     handler: async (iteration, features) => {
 *       // Execute routing with features enabled
 *       return { quality: 0.85, latency_ms: 1500, cost_usd: 0.02 };
 *     }
 *   });
 */
async function runABTestFromPlan(experiment, options = {}) {
  const {
    opportunity,
    type,
    variants,
    handler,
  } = experiment;

  if (!opportunity || !type || !variants || !handler) {
    throw new Error('Missing required fields: opportunity, type, variants, handler');
  }

  if (!Array.isArray(variants) || variants.length < 2) {
    throw new Error('Need at least 2 variants for A/B testing');
  }

  // Validate variants have required fields
  for (const variant of variants) {
    if (!variant.name || !Array.isArray(variant.features)) {
      throw new Error(`Variant missing required fields: ${JSON.stringify(variant)}`);
    }
  }

  // Add handler to each variant config
  const configs = variants.map(v => ({
    ...v,
    handler,
  }));

  // Run A/B test
  const experimentName = `${type}_${opportunity.replace(/\s+/g, '_').toLowerCase()}`;
  const result = await runABTest(experimentName, configs, {
    iterations_per_variant: options.samples || AB_TEST_CONFIG.default_samples,
    warmup_iterations: options.warmup || AB_TEST_CONFIG.default_warmup,
    timeout_ms: options.timeout_ms || AB_TEST_CONFIG.default_timeout_ms,
  });

  // Store in PostgreSQL
  let stored = null;
  try {
    stored = await recordABTestResult(experimentName, opportunity, result);
  } catch (error) {
    console.warn(`[ab-test-integration] Failed to record result: ${error.message}`);
    result.storage_error = error.message;
  }

  // Save markdown report
  try {
    await saveReport(experimentName, result.report);
  } catch (error) {
    console.warn(`[ab-test-integration] Failed to save report: ${error.message}`);
  }

  return {
    ...result,
    stored,
  };
}

/**
 * Run simple feature comparison A/B test
 *
 * @param {Array<string>} baselineFeatures - Features for baseline variant
 * @param {Array<string>} treatmentFeatures - Features for treatment variant
 * @param {Function} handler - async (iteration, features) => { quality, latency_ms, cost_usd }
 * @param {number} samples - Number of samples per variant
 * @returns {Promise<Object>} A/B test result
 *
 * Example:
 *   const result = await runFeatureComparisonTest(
 *     [],  // baseline: no features
 *     ['thompson_sampling', 'consensus'],  // treatment: with features
 *     async (iteration, features) => ({ quality: 0.80, latency_ms: 2000, cost_usd: 0.03 }),
 *     30
 *   );
 */
async function runFeatureComparisonTest(baselineFeatures, treatmentFeatures, handler, samples = 30) {
  const experiment = {
    opportunity: `Compare features: [${treatmentFeatures.join(', ')}]`,
    type: 'feature_comparison',
    variants: [
      { name: 'baseline', features: baselineFeatures },
      { name: 'treatment', features: treatmentFeatures },
    ],
    handler,
  };

  return runABTestFromPlan(experiment, { samples });
}

/**
 * Run multi-variant A/B test (A/B/C/D...)
 *
 * @param {string} experimentName - Name of experiment
 * @param {Array<Object>} variants - Variant configurations
 * @param {Function} handler - async (iteration, features) => { quality, latency_ms, cost_usd }
 * @param {Object} [options] - Override defaults
 * @returns {Promise<Object>} A/B test result
 *
 * Example:
 *   const result = await runMultiVariantTest('routing_strategies', [
 *     { name: 'random', features: [] },
 *     { name: 'round_robin', features: ['round_robin'] },
 *     { name: 'thompson', features: ['thompson_sampling'] },
 *     { name: 'quality_first', features: ['quality_first_routing'] }
 *   ], handler);
 */
async function runMultiVariantTest(experimentName, variants, handler, options = {}) {
  const experiment = {
    opportunity: experimentName,
    type: 'multi_variant_comparison',
    variants,
    handler,
  };

  return runABTestFromPlan(experiment, options);
}

// ============================================================================
// STORAGE
// ============================================================================

/**
 * Record A/B test result in PostgreSQL
 *
 * Uses experiment-manager.cjs to store in workflow.experiments table.
 * Stores the winner variant as the "treatment" for compatibility.
 *
 * @param {string} name - Experiment name
 * @param {string} hypothesis - What was being tested
 * @param {Object} result - Result from runABTest
 * @returns {Promise<number>} Experiment ID
 */
async function recordABTestResult(name, hypothesis, result) {
  const { winner, statistics, raw } = result;

  if (!statistics || statistics.status !== 'success') {
    throw new Error(`Cannot record incomplete A/B test: ${statistics?.status || 'unknown'}`);
  }

  const winnerStats = statistics.summaries[winner];
  const baselineVariant = Object.keys(statistics.summaries).find(v => v !== winner) || winner;
  const baselineStats = statistics.summaries[baselineVariant];

  // Extract samples for baseline and winner
  const baselineSamples = raw.variants[baselineVariant].measurements.map(m => m.quality);
  const winnerSamples = raw.variants[winner].measurements.map(m => m.quality);

  // Find pairwise comparison (if exists)
  const pairKey = baselineVariant < winner
    ? `${baselineVariant}_vs_${winner}`
    : `${winner}_vs_${baselineVariant}`;
  const pairwise = statistics.pairwise[pairKey] || null;

  const experimentData = {
    metric: 'quality',
    baseline_config: raw.variants[baselineVariant],
    treatment_config: raw.variants[winner],
    baseline_samples: baselineSamples,
    treatment_samples: winnerSamples,
    baseline_mean: baselineStats.quality.mean,
    treatment_mean: winnerStats.quality.mean,
    improvement_pct: pairwise ? pairwise.quality.relative_diff_pct : 0,
    p_value: pairwise ? pairwise.quality.t_test.p_value : 1.0,
    ci_lower: winnerStats.quality.ci.lower,
    ci_upper: winnerStats.quality.ci.upper,
    effect_size: pairwise ? pairwise.quality.effect_size.d : 0,
    verdict: statistics.winner === winner ? 'keep' : 'inconclusive',
    success_criteria: {
      min_improvement_pct: 3,
      alpha: 0.05,
    },
    metadata: {
      ab_test: true,
      variants: Object.keys(raw.variants),
      winner: statistics.winner,
      winner_score: statistics.winner_score,
      experiment_config: raw.config,
    },
  };

  return recordExperiment(name, hypothesis, experimentData);
}

/**
 * Save markdown report to disk
 *
 * @param {string} experimentName - Name of experiment
 * @param {string} report - Markdown report text
 * @returns {Promise<string>} Report file path
 */
async function saveReport(experimentName, report) {
  // Ensure reports directory exists
  if (!fs.existsSync(AB_TEST_CONFIG.reports_dir)) {
    fs.mkdirSync(AB_TEST_CONFIG.reports_dir, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
  const filename = `${experimentName}_${timestamp}.md`;
  const filepath = path.join(AB_TEST_CONFIG.reports_dir, filename);

  fs.writeFileSync(filepath, report, 'utf8');
  console.log(`[ab-test-integration] Report saved to: ${filepath}`);

  return filepath;
}

/**
 * Get A/B test history from PostgreSQL
 *
 * @param {Object} [filters]
 * @param {string} [filters.name] - Filter by experiment name
 * @param {string} [filters.verdict] - Filter by verdict (keep/remove/inconclusive)
 * @param {number} [filters.limit] - Max results (default: 20)
 * @returns {Promise<Array<Object>>} Experiment records
 */
async function getABTestHistory(filters = {}) {
  const experiments = await getExperimentHistory(filters);

  // Filter to only A/B tests
  return experiments.filter(exp => {
    try {
      const metadata = typeof exp.metadata === 'string'
        ? JSON.parse(exp.metadata)
        : exp.metadata;
      return metadata.ab_test === true;
    } catch {
      return false;
    }
  });
}

/**
 * Generate A/B test summary report
 *
 * @param {number} [limit] - Max experiments to analyze
 * @returns {Promise<Object>} Summary statistics
 */
async function generateABTestSummary(limit = 100) {
  const tests = await getABTestHistory({ limit });

  const total = tests.length;
  const byVerdict = {
    keep: tests.filter(t => t.verdict === 'keep').length,
    remove: tests.filter(t => t.verdict === 'remove').length,
    inconclusive: tests.filter(t => t.verdict === 'inconclusive').length,
  };

  const avgImprovement = tests.length > 0
    ? tests.reduce((sum, t) => sum + (t.improvement_pct || 0), 0) / tests.length
    : 0;

  const significantTests = tests.filter(t => t.p_value < 0.05);

  const recentWinners = tests
    .filter(t => t.verdict === 'keep')
    .slice(0, 5)
    .map(t => ({
      name: t.name,
      hypothesis: t.hypothesis,
      improvement_pct: t.improvement_pct,
      p_value: t.p_value,
      effect_size: t.effect_size,
      created_at: t.created_at,
    }));

  return {
    total_tests: total,
    by_verdict: byVerdict,
    success_rate: total > 0 ? byVerdict.keep / total : 0,
    avg_improvement_pct: avgImprovement,
    significant_tests: significantTests.length,
    significance_rate: total > 0 ? significantTests.length / total : 0,
    recent_winners: recentWinners,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Core API
  runABTestFromPlan,
  runFeatureComparisonTest,
  runMultiVariantTest,

  // Storage
  recordABTestResult,
  saveReport,
  getABTestHistory,
  generateABTestSummary,

  // Configuration
  AB_TEST_CONFIG,

  // Re-export ab-runner functions for convenience
  runABTest,
  computeStatistics,
  generateReport,
};
