#!/usr/bin/env node

/**
 * A/B Test Manager
 *
 * Complete A/B testing management system for distributed LLM orchestration.
 * Extends ab-test-integration.js with:
 * - Test lifecycle management (plan → execute → analyze → deploy)
 * - Multi-metric optimization (quality, latency, cost)
 * - Sequential testing with early stopping
 * - Bayesian optimization for multi-armed bandits
 * - Traffic allocation management
 * - Rollback capabilities
 * - Performance dashboards
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────┐
 * │ A/B Test Manager (this file)                    │
 * ├─────────────────────────────────────────────────┤
 * │ - Test Planning & Scheduling                    │
 * │ - Sequential Testing (early stop)               │
 * │ - Bayesian Multi-Armed Bandit                   │
 * │ - Traffic Allocation Control                    │
 * │ - Rollback & Safety Mechanisms                  │
 * └─────────────────────────────────────────────────┘
 *          │
 *          ├─ Depends on: ab-test-integration.js (execution layer)
 *          ├─ Depends on: postgres-adapter.js (storage layer)
 *          └─ Depends on: shared/ab-runner.cjs (statistical framework)
 *
 * Created: 2026-07-03
 * Status: Production-ready
 */

const { getDB, getStrategyPerformance } = require('./postgres-adapter.js');
const {
  runABTestFromPlan,
  runFeatureComparisonTest,
  runMultiVariantTest,
  getABTestHistory,
  generateABTestSummary,
} = require('./ab-test-integration.js');

// ============================================================================
// CONFIGURATION
// ============================================================================

const AB_MANAGER_CONFIG = {
  /** Early stopping threshold (e.g., stop if p < 0.01 after 10 samples) */
  early_stop_alpha: 0.01,
  early_stop_min_samples: 10,

  /** Bayesian optimization priors */
  bayesian_prior_alpha: 1.0,  // Uniform prior
  bayesian_prior_beta: 1.0,

  /** Traffic allocation */
  initial_traffic_pct: 5,     // Start with 5% traffic
  max_traffic_pct: 50,        // Max 50% before full rollout
  traffic_increment: 5,       // Increase by 5% per step

  /** Rollback thresholds */
  rollback_quality_drop_pct: 10,  // Rollback if quality drops >10%
  rollback_latency_increase_pct: 50,  // Rollback if latency increases >50%
  rollback_cost_increase_pct: 30,  // Rollback if cost increases >30%

  /** Multi-metric optimization weights */
  weights: {
    quality: 0.6,    // 60% weight on quality
    latency: 0.2,    // 20% weight on latency (lower is better)
    cost: 0.2,       // 20% weight on cost (lower is better)
  },
};

// ============================================================================
// CORE CLASSES
// ============================================================================

/**
 * A/B Test Manager
 * Manages full lifecycle of A/B tests
 */
class ABTestManager {
  constructor(config = {}) {
    this.config = { ...AB_MANAGER_CONFIG, ...config };
    this.db = getDB();
    this.strategyPerf = getStrategyPerformance();
  }

  // ==========================================================================
  // TEST LIFECYCLE
  // ==========================================================================

  /**
   * Plan A/B test (Phase 1: Planning)
   * Creates test specification and validates configuration
   *
   * @param {Object} spec - Test specification
   * @param {string} spec.name - Test name
   * @param {string} spec.hypothesis - What we're testing
   * @param {Array<Object>} spec.variants - Variant configurations
   * @param {Object} spec.metrics - Metric definitions
   * @param {Object} spec.success_criteria - Success criteria
   * @returns {Promise<Object>} Test plan
   */
  async planTest(spec) {
    const { name, hypothesis, variants, metrics, success_criteria } = spec;

    // Validate inputs
    if (!name || !hypothesis || !variants || variants.length < 2) {
      throw new Error('Invalid test spec: need name, hypothesis, and ≥2 variants');
    }

    // Store test plan in database
    const plan = {
      name,
      hypothesis,
      variants,
      metrics: metrics || ['quality', 'latency_ms', 'cost_usd'],
      success_criteria: success_criteria || {
        min_improvement_pct: 3,
        alpha: 0.05,
        min_samples: 30,
      },
      status: 'planned',
      created_at: new Date().toISOString(),
    };

    await this.db.query(`
      INSERT INTO workflow.ab_test_plans (name, hypothesis, config, status, created_at)
      VALUES ($1, $2, $3, $4, NOW())
      RETURNING id
    `, [name, hypothesis, JSON.stringify(plan), 'planned']);

    console.log(`✅ A/B test planned: ${name}`);
    return plan;
  }

  /**
   * Execute A/B test (Phase 2: Execution)
   * Runs test with early stopping and safety checks
   *
   * @param {string} name - Test name (from plan)
   * @param {Function} handler - async (iteration, features) => metrics
   * @param {Object} options - Execution options
   * @returns {Promise<Object>} Test results
   */
  async executeTest(name, handler, options = {}) {
    // Load test plan
    const planRow = await this.db.query(`
      SELECT * FROM workflow.ab_test_plans
      WHERE name = $1 AND status = 'planned'
      ORDER BY created_at DESC LIMIT 1
    `, [name]);

    if (!planRow || planRow.length === 0) {
      throw new Error(`No planned test found: ${name}`);
    }

    const plan = typeof planRow[0].config === 'string'
      ? JSON.parse(planRow[0].config)
      : planRow[0].config;

    // Execute with early stopping
    const result = await this._executeWithEarlyStopping(plan, handler, options);

    // Update plan status
    await this.db.query(`
      UPDATE workflow.ab_test_plans
      SET status = 'completed', completed_at = NOW()
      WHERE name = $1
    `, [name]);

    console.log(`✅ A/B test executed: ${name}, winner: ${result.winner}`);
    return result;
  }

  /**
   * Analyze A/B test results (Phase 3: Analysis)
   * Performs multi-metric analysis and generates insights
   *
   * @param {Object} result - Result from executeTest
   * @returns {Promise<Object>} Analysis report
   */
  async analyzeTest(result) {
    const { statistics, raw } = result;

    // Multi-metric scoring
    const scores = await this._computeMultiMetricScores(statistics);

    // Bayesian posterior estimation
    const posteriors = await this._computeBayesianPosteriors(raw);

    // Risk analysis
    const risks = await this._analyzeRisks(statistics);

    // Generate insights
    const insights = await this._generateInsights(statistics, scores, risks);

    return {
      scores,
      posteriors,
      risks,
      insights,
      recommendation: this._generateRecommendation(scores, risks),
    };
  }

  /**
   * Deploy winning variant (Phase 4: Deployment)
   * Gradually rolls out winner with traffic ramping
   *
   * @param {string} testName - Test name
   * @param {string} winnerVariant - Winner variant name
   * @param {Object} options - Deployment options
   * @returns {Promise<Object>} Deployment plan
   */
  async deployWinner(testName, winnerVariant, options = {}) {
    const { gradual = true, monitor_window_hours = 24 } = options;

    if (!gradual) {
      // Immediate 100% rollout
      await this._setTrafficAllocation(testName, winnerVariant, 100);
      return { traffic_pct: 100, status: 'deployed' };
    }

    // Gradual rollout with monitoring
    const plan = await this._createGradualRolloutPlan(testName, winnerVariant, monitor_window_hours);

    console.log(`✅ Gradual rollout started: ${testName} → ${winnerVariant}`);
    console.log(`   Traffic ramp: 5% → 10% → 25% → 50% → 100%`);
    console.log(`   Monitor window: ${monitor_window_hours}h per step`);

    return plan;
  }

  /**
   * Rollback A/B test (Safety mechanism)
   * Reverts to baseline if metrics degrade
   *
   * @param {string} testName - Test name
   * @param {string} reason - Rollback reason
   * @returns {Promise<Object>} Rollback result
   */
  async rollback(testName, reason) {
    // Set traffic to 0% for treatment
    await this._setTrafficAllocation(testName, 'treatment', 0);

    // Record rollback
    await this.db.query(`
      INSERT INTO workflow.ab_test_rollbacks (test_name, reason, rolled_back_at)
      VALUES ($1, $2, NOW())
    `, [testName, reason]);

    console.warn(`⚠️  Rollback: ${testName} (reason: ${reason})`);
    return { status: 'rolled_back', reason };
  }

  // ==========================================================================
  // SEQUENTIAL TESTING (EARLY STOPPING)
  // ==========================================================================

  /**
   * Execute test with early stopping
   * Stops test early if statistical significance reached
   *
   * @private
   */
  async _executeWithEarlyStopping(plan, handler, options) {
    const { variants, success_criteria } = plan;
    const { min_samples, alpha } = success_criteria;

    const minSamples = options.min_samples || min_samples || this.config.early_stop_min_samples;
    const earlyStopAlpha = options.alpha || alpha || this.config.early_stop_alpha;

    // Start with small batch
    let currentSamples = minSamples;
    let result = null;

    while (currentSamples <= (options.max_samples || 100)) {
      console.log(`Running ${currentSamples} samples per variant...`);

      // Run A/B test
      result = await runABTestFromPlan({
        ...plan,
        handler,
      }, {
        samples: currentSamples,
      });

      // Check for early stopping
      const { statistics } = result;
      if (this._shouldStopEarly(statistics, earlyStopAlpha)) {
        console.log(`✅ Early stop: p-value < ${earlyStopAlpha} after ${currentSamples} samples`);
        break;
      }

      // Increase sample size
      currentSamples = Math.floor(currentSamples * 1.5);
    }

    return result;
  }

  /**
   * Check if we should stop early
   * @private
   */
  _shouldStopEarly(statistics, alpha) {
    if (!statistics || !statistics.pairwise) return false;

    // Check if any pairwise comparison has p < alpha
    for (const [pair, stats] of Object.entries(statistics.pairwise)) {
      if (stats.quality && stats.quality.t_test && stats.quality.t_test.p_value < alpha) {
        return true;
      }
    }

    return false;
  }

  // ==========================================================================
  // BAYESIAN OPTIMIZATION
  // ==========================================================================

  /**
   * Compute Bayesian posteriors for each variant
   * Uses Beta distribution for success rate modeling
   *
   * @private
   */
  async _computeBayesianPosteriors(raw) {
    const posteriors = {};

    for (const [variant, data] of Object.entries(raw.variants)) {
      const samples = data.measurements.map(m => m.quality);

      // Model as Beta distribution (success rate)
      // Success = quality > threshold (e.g., 0.7)
      const threshold = 0.7;
      const successes = samples.filter(q => q >= threshold).length;
      const failures = samples.length - successes;

      // Bayesian update: posterior = prior + data
      const alpha = this.config.bayesian_prior_alpha + successes;
      const beta = this.config.bayesian_prior_beta + failures;

      posteriors[variant] = {
        alpha,
        beta,
        mean: alpha / (alpha + beta),
        variance: (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1)),
        samples: samples.length,
      };
    }

    return posteriors;
  }

  /**
   * Thompson Sampling for multi-armed bandit
   * Selects best variant based on Bayesian posteriors
   *
   * @param {Object} posteriors - Bayesian posteriors from _computeBayesianPosteriors
   * @returns {string} Selected variant name
   */
  thompsonSampling(posteriors) {
    let bestVariant = null;
    let bestSample = -Infinity;

    for (const [variant, posterior] of Object.entries(posteriors)) {
      // Sample from Beta(alpha, beta)
      const sample = this._sampleBeta(posterior.alpha, posterior.beta);

      if (sample > bestSample) {
        bestSample = sample;
        bestVariant = variant;
      }
    }

    return bestVariant;
  }

  /**
   * Sample from Beta distribution
   * @private
   */
  _sampleBeta(alpha, beta) {
    // Use Gamma sampling (same as postgres-adapter.js)
    const x = this._sampleGamma(alpha, 1);
    const y = this._sampleGamma(beta, 1);
    return x / (x + y);
  }

  /**
   * Sample from Gamma distribution
   * @private
   */
  _sampleGamma(alpha, beta) {
    // Marsaglia & Tsang's method
    if (alpha >= 1) {
      const d = alpha - 1/3;
      const c = 1 / Math.sqrt(9 * d);

      while (true) {
        let x, v;
        do {
          x = this._normalSample();
          v = 1 + c * x;
        } while (v <= 0);

        v = v * v * v;
        const u = Math.random();
        const xSquared = x * x;

        if (u < 1 - 0.0331 * xSquared * xSquared) {
          return d * v * beta;
        }

        if (Math.log(u) < 0.5 * xSquared + d * (1 - v + Math.log(v))) {
          return d * v * beta;
        }
      }
    } else {
      return this._sampleGamma(alpha + 1, beta) * Math.pow(Math.random(), 1/alpha);
    }
  }

  /**
   * Sample from standard normal distribution
   * @private
   */
  _normalSample() {
    const u1 = Math.random();
    const u2 = Math.random();
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  }

  // ==========================================================================
  // MULTI-METRIC OPTIMIZATION
  // ==========================================================================

  /**
   * Compute multi-metric scores for each variant
   * Combines quality, latency, cost into single score
   *
   * @private
   */
  async _computeMultiMetricScores(statistics) {
    const scores = {};

    for (const [variant, summary] of Object.entries(statistics.summaries)) {
      // Normalize metrics to [0, 1] range
      const qualityScore = summary.quality.mean;  // Already 0-1
      const latencyScore = 1 / (1 + summary.latency_ms.mean / 1000);  // Lower is better
      const costScore = 1 / (1 + summary.cost_usd.mean * 100);  // Lower is better

      // Weighted combination
      const compositeScore =
        this.config.weights.quality * qualityScore +
        this.config.weights.latency * latencyScore +
        this.config.weights.cost * costScore;

      scores[variant] = {
        quality: qualityScore,
        latency: latencyScore,
        cost: costScore,
        composite: compositeScore,
      };
    }

    return scores;
  }

  // ==========================================================================
  // RISK ANALYSIS
  // ==========================================================================

  /**
   * Analyze risks of deploying treatment
   * @private
   */
  async _analyzeRisks(statistics) {
    const risks = [];

    // Get baseline and treatment
    const baseline = statistics.summaries.baseline || statistics.summaries[Object.keys(statistics.summaries)[0]];
    const treatment = statistics.summaries.treatment || statistics.summaries[Object.keys(statistics.summaries)[1]];

    // Quality risk
    const qualityDrop = ((baseline.quality.mean - treatment.quality.mean) / baseline.quality.mean) * 100;
    if (qualityDrop > this.config.rollback_quality_drop_pct) {
      risks.push({
        type: 'quality_degradation',
        severity: 'high',
        description: `Quality drops ${qualityDrop.toFixed(1)}% (threshold: ${this.config.rollback_quality_drop_pct}%)`,
        action: 'DO NOT DEPLOY - quality regression',
      });
    }

    // Latency risk
    const latencyIncrease = ((treatment.latency_ms.mean - baseline.latency_ms.mean) / baseline.latency_ms.mean) * 100;
    if (latencyIncrease > this.config.rollback_latency_increase_pct) {
      risks.push({
        type: 'latency_increase',
        severity: 'medium',
        description: `Latency increases ${latencyIncrease.toFixed(1)}% (threshold: ${this.config.rollback_latency_increase_pct}%)`,
        action: 'Consider gradual rollout with monitoring',
      });
    }

    // Cost risk
    const costIncrease = ((treatment.cost_usd.mean - baseline.cost_usd.mean) / baseline.cost_usd.mean) * 100;
    if (costIncrease > this.config.rollback_cost_increase_pct) {
      risks.push({
        type: 'cost_increase',
        severity: 'medium',
        description: `Cost increases ${costIncrease.toFixed(1)}% (threshold: ${this.config.rollback_cost_increase_pct}%)`,
        action: 'Evaluate cost-benefit tradeoff',
      });
    }

    return risks;
  }

  // ==========================================================================
  // INSIGHTS GENERATION
  // ==========================================================================

  /**
   * Generate actionable insights from test results
   * @private
   */
  async _generateInsights(statistics, scores, risks) {
    const insights = [];

    // Winner insight
    const winner = statistics.winner;
    const winnerScore = scores[winner].composite;
    insights.push({
      type: 'winner',
      message: `Variant "${winner}" won with composite score ${winnerScore.toFixed(3)}`,
    });

    // Metric breakdown
    const winnerStats = statistics.summaries[winner];
    insights.push({
      type: 'metrics',
      message: `Quality: ${winnerStats.quality.mean.toFixed(3)}, Latency: ${winnerStats.latency_ms.mean.toFixed(0)}ms, Cost: $${winnerStats.cost_usd.mean.toFixed(4)}`,
    });

    // Statistical significance
    const pairwise = Object.values(statistics.pairwise)[0];
    if (pairwise && pairwise.quality) {
      insights.push({
        type: 'significance',
        message: `p-value: ${pairwise.quality.t_test.p_value.toFixed(4)}, effect size: ${pairwise.quality.effect_size.d.toFixed(2)}`,
      });
    }

    // Risk warnings
    for (const risk of risks) {
      insights.push({
        type: 'risk',
        severity: risk.severity,
        message: risk.description,
        action: risk.action,
      });
    }

    return insights;
  }

  /**
   * Generate deployment recommendation
   * @private
   */
  _generateRecommendation(scores, risks) {
    const highRisks = risks.filter(r => r.severity === 'high');

    if (highRisks.length > 0) {
      return {
        action: 'DO_NOT_DEPLOY',
        reason: 'High-severity risks detected',
        risks: highRisks,
      };
    }

    const mediumRisks = risks.filter(r => r.severity === 'medium');
    if (mediumRisks.length > 0) {
      return {
        action: 'GRADUAL_ROLLOUT',
        reason: 'Medium-severity risks detected',
        risks: mediumRisks,
        plan: 'Use gradual traffic ramping with monitoring',
      };
    }

    return {
      action: 'DEPLOY',
      reason: 'No significant risks detected',
      plan: 'Safe to deploy with standard monitoring',
    };
  }

  // ==========================================================================
  // TRAFFIC ALLOCATION
  // ==========================================================================

  /**
   * Set traffic allocation for variant
   * @private
   */
  async _setTrafficAllocation(testName, variant, trafficPct) {
    await this.db.query(`
      INSERT INTO workflow.ab_test_traffic (test_name, variant, traffic_pct, updated_at)
      VALUES ($1, $2, $3, NOW())
      ON CONFLICT (test_name, variant) DO UPDATE
      SET traffic_pct = EXCLUDED.traffic_pct, updated_at = NOW()
    `, [testName, variant, trafficPct]);
  }

  /**
   * Create gradual rollout plan
   * @private
   */
  async _createGradualRolloutPlan(testName, variant, monitorWindowHours) {
    const steps = [5, 10, 25, 50, 100];

    const plan = {
      test_name: testName,
      variant,
      steps: steps.map((pct, i) => ({
        step: i + 1,
        traffic_pct: pct,
        monitor_window_hours: monitorWindowHours,
        status: 'pending',
      })),
      created_at: new Date().toISOString(),
    };

    await this.db.query(`
      INSERT INTO workflow.ab_test_rollout_plans (test_name, variant, plan, created_at)
      VALUES ($1, $2, $3, NOW())
    `, [testName, variant, JSON.stringify(plan)]);

    return plan;
  }

  // ==========================================================================
  // DASHBOARD
  // ==========================================================================

  /**
   * Generate A/B testing dashboard
   * Shows active tests, recent results, and recommendations
   *
   * @returns {Promise<Object>} Dashboard data
   */
  async generateDashboard() {
    // Active tests
    const activeTests = await this.db.query(`
      SELECT * FROM workflow.ab_test_plans
      WHERE status IN ('planned', 'running')
      ORDER BY created_at DESC
    `);

    // Recent completions
    const recentTests = await this.db.query(`
      SELECT * FROM workflow.experiments
      WHERE created_at > NOW() - INTERVAL '7 days'
      ORDER BY created_at DESC
      LIMIT 10
    `);

    // Summary statistics
    const summary = await generateABTestSummary(100);

    // Active rollouts
    const activeRollouts = await this.db.query(`
      SELECT * FROM workflow.ab_test_rollout_plans
      WHERE status != 'completed'
      ORDER BY created_at DESC
    `);

    return {
      active_tests: activeTests,
      recent_completions: recentTests,
      summary,
      active_rollouts: activeRollouts,
      generated_at: new Date().toISOString(),
    };
  }

  /**
   * Print dashboard to console
   */
  async printDashboard() {
    const dashboard = await this.generateDashboard();

    console.log('\n════════════════════════════════════════════════════════════════');
    console.log('  A/B TESTING DASHBOARD');
    console.log('════════════════════════════════════════════════════════════════\n');

    console.log('📊 SUMMARY');
    console.log(`   Total tests: ${dashboard.summary.total_tests}`);
    console.log(`   Success rate: ${(dashboard.summary.success_rate * 100).toFixed(1)}%`);
    console.log(`   Avg improvement: ${dashboard.summary.avg_improvement_pct.toFixed(1)}%`);
    console.log(`   Significant tests: ${dashboard.summary.significant_tests}/${dashboard.summary.total_tests}\n`);

    if (dashboard.active_tests.length > 0) {
      console.log('🔬 ACTIVE TESTS');
      for (const test of dashboard.active_tests) {
        const config = typeof test.config === 'string' ? JSON.parse(test.config) : test.config;
        console.log(`   - ${test.name} (${test.status})`);
        console.log(`     ${test.hypothesis}`);
      }
      console.log('');
    }

    if (dashboard.recent_completions.length > 0) {
      console.log('✅ RECENT COMPLETIONS (last 7 days)');
      for (const test of dashboard.recent_completions.slice(0, 5)) {
        const improvement = test.improvement_pct ? parseFloat(test.improvement_pct).toFixed(1) : 'N/A';
        console.log(`   - ${test.name}: ${test.verdict} (improvement: ${improvement}%)`);
      }
      console.log('');
    }

    if (dashboard.active_rollouts.length > 0) {
      console.log('🚀 ACTIVE ROLLOUTS');
      for (const rollout of dashboard.active_rollouts) {
        const plan = typeof rollout.plan === 'string' ? JSON.parse(rollout.plan) : rollout.plan;
        console.log(`   - ${rollout.test_name} → ${rollout.variant}`);
        const currentStep = plan.steps.find(s => s.status === 'active');
        if (currentStep) {
          console.log(`     Current: ${currentStep.traffic_pct}% traffic`);
        }
      }
      console.log('');
    }

    console.log('════════════════════════════════════════════════════════════════\n');
  }
}

// ============================================================================
// SCHEMA SETUP (run once to create tables)
// ============================================================================

async function setupSchema() {
  const db = getDB();

  // ab_test_plans table
  await db.query(`
    CREATE TABLE IF NOT EXISTS workflow.ab_test_plans (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      hypothesis TEXT,
      config JSONB NOT NULL,
      status TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT NOW(),
      completed_at TIMESTAMP,
      UNIQUE(name, created_at)
    )
  `);

  // ab_test_rollbacks table
  await db.query(`
    CREATE TABLE IF NOT EXISTS workflow.ab_test_rollbacks (
      id SERIAL PRIMARY KEY,
      test_name TEXT NOT NULL,
      reason TEXT NOT NULL,
      rolled_back_at TIMESTAMP DEFAULT NOW()
    )
  `);

  // ab_test_traffic table
  await db.query(`
    CREATE TABLE IF NOT EXISTS workflow.ab_test_traffic (
      test_name TEXT NOT NULL,
      variant TEXT NOT NULL,
      traffic_pct INTEGER NOT NULL,
      updated_at TIMESTAMP DEFAULT NOW(),
      PRIMARY KEY (test_name, variant)
    )
  `);

  // ab_test_rollout_plans table
  await db.query(`
    CREATE TABLE IF NOT EXISTS workflow.ab_test_rollout_plans (
      id SERIAL PRIMARY KEY,
      test_name TEXT NOT NULL,
      variant TEXT NOT NULL,
      plan JSONB NOT NULL,
      status TEXT DEFAULT 'pending',
      created_at TIMESTAMP DEFAULT NOW()
    )
  `);

  console.log('✅ A/B test manager schema created');
}

// ============================================================================
// CLI
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  const manager = new ABTestManager();

  switch (command) {
    case 'setup':
      await setupSchema();
      break;

    case 'dashboard':
      await manager.printDashboard();
      break;

    case 'plan':
      // Example: node ab-test-manager.js plan "thompson_vs_random" "Compare routing strategies"
      const name = args[1];
      const hypothesis = args[2];
      const plan = await manager.planTest({
        name,
        hypothesis,
        variants: [
          { name: 'baseline', features: [] },
          { name: 'treatment', features: ['thompson_sampling'] },
        ],
        metrics: ['quality', 'latency_ms', 'cost_usd'],
      });
      console.log(JSON.stringify(plan, null, 2));
      break;

    default:
      console.log('Usage:');
      console.log('  node ab-test-manager.js setup           - Create database schema');
      console.log('  node ab-test-manager.js dashboard       - Show A/B test dashboard');
      console.log('  node ab-test-manager.js plan <name> <hypothesis> - Plan new test');
      process.exit(1);
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  ABTestManager,
  AB_MANAGER_CONFIG,
  setupSchema,
};

// Run CLI if invoked directly
if (require.main === module) {
  main().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
  });
}
