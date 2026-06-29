/**
 * Experiment Manager - A/B Testing Framework
 *
 * Runs controlled experiments comparing baseline vs treatment configurations,
 * applies statistical significance testing (Welch's t-test + bootstrap),
 * and records results in PostgreSQL for historical analysis.
 *
 * Features:
 * 1. runExperiment(config) - Run baseline vs treatment with metric collection
 * 2. compareResults(baseline, treatment) - Statistical testing (t-test + bootstrap)
 * 3. recordExperiment(name, hypothesis, result) - Store in PostgreSQL
 * 4. getExperimentHistory(filters) - Query past experiments
 *
 * Integration:
 * - PostgreSQL (aio-01:5433, database: learning, schema: workflow)
 * - Uses Welch's t-test for unequal variance comparisons
 * - Bootstrap confidence intervals for effect size
 * - Automatic verdict: keep/remove/inconclusive
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');

// ============================================================================
// CONFIGURATION
// ============================================================================

const EXPERIMENT_CONFIG = {
  /** Default significance level (alpha) */
  alpha: 0.05,

  /** Minimum samples per group for t-test validity */
  min_samples: 5,

  /** Default bootstrap iterations */
  bootstrap_iterations: 1000,

  /** Default confidence level for bootstrap CI */
  bootstrap_confidence: 0.95,

  /** Default minimum improvement percentage to declare success */
  default_min_improvement_pct: 3,

  /** Maximum experiment duration in milliseconds (10 minutes) */
  max_duration_ms: 600000,
};

// ============================================================================
// DATABASE CONNECTION
// ============================================================================

let _pool = null;

/**
 * Get or create the PostgreSQL connection pool.
 * @returns {Pool}
 */
function getPool() {
  if (!_pool) {
    _pool = new Pool({
      host: process.env.PGHOST || 'aio-01',
      port: parseInt(process.env.PGPORT || '5433'),
      database: process.env.PGDATABASE || 'learning',
      user: process.env.PGUSER || 'sfloess',
      password: process.env.PGPASSWORD,
      max: 5,
      idleTimeoutMillis: 30000,
    });

    _pool.on('error', (err) => {
      console.error('[experiment-manager] Pool error:', err.message);
    });
  }
  return _pool;
}

/**
 * Close the connection pool (for cleanup).
 */
async function closePool() {
  if (_pool) {
    await _pool.end();
    _pool = null;
  }
}

// ============================================================================
// SCHEMA MANAGEMENT
// ============================================================================

/**
 * Ensure the experiments table exists. Idempotent.
 */
async function ensureSchema() {
  const pool = getPool();
  await pool.query(`
    CREATE TABLE IF NOT EXISTS workflow.experiments (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      hypothesis TEXT,
      metric TEXT NOT NULL,
      baseline_config JSONB,
      treatment_config JSONB,
      baseline_samples JSONB NOT NULL,
      treatment_samples JSONB NOT NULL,
      baseline_mean NUMERIC,
      treatment_mean NUMERIC,
      improvement_pct NUMERIC,
      p_value NUMERIC,
      ci_lower NUMERIC,
      ci_upper NUMERIC,
      effect_size NUMERIC,
      verdict TEXT NOT NULL,
      success_criteria JSONB,
      metadata JSONB DEFAULT '{}',
      created_at TIMESTAMP DEFAULT NOW()
    )
  `);
}

// ============================================================================
// STATISTICAL FUNCTIONS
// ============================================================================

/**
 * Calculate the arithmetic mean of an array.
 * @param {number[]} arr
 * @returns {number}
 */
function mean(arr) {
  if (arr.length === 0) return 0;
  return arr.reduce((sum, x) => sum + x, 0) / arr.length;
}

/**
 * Calculate the sample variance (Bessel's correction).
 * @param {number[]} arr
 * @returns {number}
 */
function variance(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  return arr.reduce((sum, x) => sum + (x - m) ** 2, 0) / (arr.length - 1);
}

/**
 * Calculate standard deviation.
 * @param {number[]} arr
 * @returns {number}
 */
function stddev(arr) {
  return Math.sqrt(variance(arr));
}

/**
 * Welch's t-test for two independent samples with unequal variances.
 *
 * Returns the t-statistic and approximate p-value using the
 * Welch-Satterthwaite degrees of freedom.
 *
 * @param {number[]} group1 - Baseline samples
 * @param {number[]} group2 - Treatment samples
 * @returns {{ t_stat: number, df: number, p_value: number }}
 */
function welchTTest(group1, group2) {
  const n1 = group1.length;
  const n2 = group2.length;
  const m1 = mean(group1);
  const m2 = mean(group2);
  const v1 = variance(group1);
  const v2 = variance(group2);

  // Handle zero-variance edge case
  if (v1 === 0 && v2 === 0) {
    if (m1 === m2) {
      return { t_stat: 0, df: n1 + n2 - 2, p_value: 1.0 };
    }
    // Infinite t-stat means effectively p=0
    return { t_stat: Infinity, df: n1 + n2 - 2, p_value: 0.0 };
  }

  const se1 = v1 / n1;
  const se2 = v2 / n2;
  const se = Math.sqrt(se1 + se2);

  if (se === 0) {
    return { t_stat: 0, df: n1 + n2 - 2, p_value: 1.0 };
  }

  const tStat = (m2 - m1) / se;

  // Welch-Satterthwaite degrees of freedom
  const dfNum = (se1 + se2) ** 2;
  const dfDen = (se1 ** 2) / (n1 - 1) + (se2 ** 2) / (n2 - 1);
  const df = dfDen > 0 ? dfNum / dfDen : n1 + n2 - 2;

  // Approximate two-tailed p-value using Student's t distribution
  const pValue = tDistPValue(Math.abs(tStat), df);

  return { t_stat: tStat, df, p_value: pValue };
}

/**
 * Approximate the two-tailed p-value for Student's t-distribution.
 *
 * Uses the regularized incomplete beta function approximation.
 * Accurate to ~3 decimal places for typical df values.
 *
 * @param {number} t - Absolute t-statistic
 * @param {number} df - Degrees of freedom
 * @returns {number} Two-tailed p-value
 */
function tDistPValue(t, df) {
  if (!isFinite(t)) return 0.0;
  if (t === 0) return 1.0;
  if (df <= 0) return 1.0;

  // Use the relationship between t-distribution and regularized incomplete beta function:
  // P(|T| > t) = I_{x}(df/2, 1/2) where x = df/(df + t^2)
  const x = df / (df + t * t);
  return regularizedIncompleteBeta(x, df / 2, 0.5);
}

/**
 * Regularized incomplete beta function I_x(a, b) using continued fraction.
 *
 * Uses Lentz's algorithm for the continued fraction representation.
 * Reference: Numerical Recipes in C, Chapter 6.4
 *
 * @param {number} x - Argument (0 <= x <= 1)
 * @param {number} a - First parameter (> 0)
 * @param {number} b - Second parameter (> 0)
 * @returns {number} I_x(a, b)
 */
function regularizedIncompleteBeta(x, a, b) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;

  // Use symmetry transformation when x > (a+1)/(a+b+2)
  if (x > (a + 1) / (a + b + 2)) {
    return 1 - regularizedIncompleteBeta(1 - x, b, a);
  }

  // Compute the continued fraction using Lentz's algorithm
  const lnBeta = lnGamma(a) + lnGamma(b) - lnGamma(a + b);
  const front = Math.exp(
    Math.log(x) * a + Math.log(1 - x) * b - lnBeta
  ) / a;

  // Modified Lentz's algorithm
  const TINY = 1e-30;
  const EPS = 1e-10;
  const MAX_ITER = 200;

  let f = 1 + TINY;
  let c = f;
  let d = 0;

  for (let i = 1; i <= MAX_ITER; i++) {
    let m = Math.floor(i / 2);
    let numerator;

    if (i === 1) {
      numerator = 1;
    } else if (i % 2 === 0) {
      numerator = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m));
    } else {
      numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1));
    }

    d = 1 + numerator * d;
    if (Math.abs(d) < TINY) d = TINY;
    d = 1 / d;

    c = 1 + numerator / c;
    if (Math.abs(c) < TINY) c = TINY;

    const delta = c * d;
    f *= delta;

    if (Math.abs(delta - 1) < EPS) break;
  }

  return front * (f - 1);
}

/**
 * Natural log of the gamma function (Stirling's approximation + Lanczos).
 *
 * @param {number} z
 * @returns {number} ln(Gamma(z))
 */
function lnGamma(z) {
  // Lanczos approximation coefficients (g=7)
  const c = [
    0.99999999999980993,
    676.5203681218851,
    -1259.1392167224028,
    771.32342877765313,
    -176.61502916214059,
    12.507343278686905,
    -0.13857109526572012,
    9.9843695780195716e-6,
    1.5056327351493116e-7,
  ];

  if (z < 0.5) {
    // Reflection formula
    return Math.log(Math.PI / Math.sin(Math.PI * z)) - lnGamma(1 - z);
  }

  z -= 1;
  let x = c[0];
  for (let i = 1; i < c.length; i++) {
    x += c[i] / (z + i);
  }

  const t = z + c.length - 1.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

/**
 * Bootstrap confidence interval for the difference of means.
 *
 * @param {number[]} baseline - Baseline samples
 * @param {number[]} treatment - Treatment samples
 * @param {Object} options
 * @param {number} options.iterations - Number of bootstrap resamples (default: 1000)
 * @param {number} options.confidence - Confidence level (default: 0.95)
 * @returns {{ ci_lower: number, ci_upper: number, effect_size: number, std_error: number }}
 */
function bootstrapDifference(baseline, treatment, options = {}) {
  const iterations = options.iterations || EXPERIMENT_CONFIG.bootstrap_iterations;
  const confidence = options.confidence || EXPERIMENT_CONFIG.bootstrap_confidence;

  const observed = mean(treatment) - mean(baseline);
  const diffs = [];

  for (let i = 0; i < iterations; i++) {
    // Resample with replacement
    const bSample = [];
    const tSample = [];
    for (let j = 0; j < baseline.length; j++) {
      bSample.push(baseline[Math.floor(Math.random() * baseline.length)]);
    }
    for (let j = 0; j < treatment.length; j++) {
      tSample.push(treatment[Math.floor(Math.random() * treatment.length)]);
    }
    diffs.push(mean(tSample) - mean(bSample));
  }

  diffs.sort((a, b) => a - b);

  const alpha = 1 - confidence;
  const lowerIdx = Math.floor(iterations * (alpha / 2));
  const upperIdx = Math.floor(iterations * (1 - alpha / 2));

  const diffMean = diffs.reduce((s, x) => s + x, 0) / diffs.length;
  const diffVar = diffs.reduce((s, x) => s + (x - diffMean) ** 2, 0) / (diffs.length - 1);

  // Cohen's d effect size
  const pooledStd = Math.sqrt(
    ((baseline.length - 1) * variance(baseline) + (treatment.length - 1) * variance(treatment)) /
    (baseline.length + treatment.length - 2)
  );
  const effectSize = pooledStd > 0 ? observed / pooledStd : 0;

  return {
    ci_lower: diffs[lowerIdx],
    ci_upper: diffs[upperIdx],
    effect_size: effectSize,
    std_error: Math.sqrt(diffVar),
  };
}

// ============================================================================
// CORE API
// ============================================================================

/**
 * Compare baseline and treatment sample arrays with statistical testing.
 *
 * Applies Welch's t-test for significance and bootstrap for effect size CI.
 * Returns a verdict: 'keep' (treatment wins), 'remove' (no improvement),
 * or 'inconclusive' (not enough data or marginal result).
 *
 * @param {number[]} baseline - Array of baseline metric values
 * @param {number[]} treatment - Array of treatment metric values
 * @param {Object} [options]
 * @param {number} [options.alpha] - Significance level (default: 0.05)
 * @param {number} [options.min_improvement_pct] - Minimum improvement to keep (default: 3)
 * @param {number} [options.bootstrap_iterations] - Bootstrap iterations (default: 1000)
 * @param {number} [options.bootstrap_confidence] - Bootstrap CI level (default: 0.95)
 * @returns {{ baseline_mean: number, treatment_mean: number, improvement_pct: number,
 *            t_stat: number, df: number, p_value: number,
 *            ci_lower: number, ci_upper: number, effect_size: number,
 *            significant: boolean, verdict: string, reason: string }}
 */
function compareResults(baseline, treatment, options = {}) {
  const alpha = options.alpha || EXPERIMENT_CONFIG.alpha;
  const minImprovementPct = options.min_improvement_pct != null
    ? options.min_improvement_pct
    : EXPERIMENT_CONFIG.default_min_improvement_pct;

  // Validate inputs
  if (!Array.isArray(baseline) || !Array.isArray(treatment)) {
    return {
      baseline_mean: 0,
      treatment_mean: 0,
      improvement_pct: 0,
      t_stat: 0,
      df: 0,
      p_value: 1.0,
      ci_lower: 0,
      ci_upper: 0,
      effect_size: 0,
      significant: false,
      verdict: 'inconclusive',
      reason: 'Invalid input: baseline and treatment must be arrays',
    };
  }

  if (baseline.length < 2 || treatment.length < 2) {
    return {
      baseline_mean: mean(baseline),
      treatment_mean: mean(treatment),
      improvement_pct: 0,
      t_stat: 0,
      df: 0,
      p_value: 1.0,
      ci_lower: 0,
      ci_upper: 0,
      effect_size: 0,
      significant: false,
      verdict: 'inconclusive',
      reason: `Insufficient samples: baseline=${baseline.length}, treatment=${treatment.length} (need >= 2 each)`,
    };
  }

  // Calculate means
  const bMean = mean(baseline);
  const tMean = mean(treatment);

  // Improvement percentage
  const improvementPct = bMean !== 0
    ? ((tMean - bMean) / Math.abs(bMean)) * 100
    : (tMean > 0 ? 100 : 0);

  // Welch's t-test
  const tTest = welchTTest(baseline, treatment);

  // Bootstrap CI for difference
  const bootstrap = bootstrapDifference(baseline, treatment, {
    iterations: options.bootstrap_iterations,
    confidence: options.bootstrap_confidence,
  });

  // Statistical significance
  const significant = tTest.p_value < alpha;

  // Determine verdict
  let verdict;
  let reason;

  if (baseline.length < EXPERIMENT_CONFIG.min_samples || treatment.length < EXPERIMENT_CONFIG.min_samples) {
    verdict = 'inconclusive';
    reason = `Insufficient samples for reliable testing: baseline=${baseline.length}, treatment=${treatment.length} (recommend >= ${EXPERIMENT_CONFIG.min_samples} each)`;
  } else if (!significant) {
    verdict = 'inconclusive';
    reason = `Not statistically significant: p=${tTest.p_value.toFixed(4)} >= alpha=${alpha}`;
  } else if (improvementPct >= minImprovementPct) {
    verdict = 'keep';
    reason = `Significant improvement: +${improvementPct.toFixed(2)}% (p=${tTest.p_value.toFixed(4)}, effect_size=${bootstrap.effect_size.toFixed(3)})`;
  } else if (improvementPct <= -minImprovementPct) {
    verdict = 'remove';
    reason = `Significant regression: ${improvementPct.toFixed(2)}% (p=${tTest.p_value.toFixed(4)})`;
  } else {
    verdict = 'inconclusive';
    reason = `Significant but improvement (${improvementPct.toFixed(2)}%) below threshold (${minImprovementPct}%)`;
  }

  return {
    baseline_mean: bMean,
    treatment_mean: tMean,
    improvement_pct: improvementPct,
    t_stat: tTest.t_stat,
    df: tTest.df,
    p_value: tTest.p_value,
    ci_lower: bootstrap.ci_lower,
    ci_upper: bootstrap.ci_upper,
    effect_size: bootstrap.effect_size,
    significant,
    verdict,
    reason,
  };
}

/**
 * Run an A/B experiment with baseline and treatment metric collectors.
 *
 * The config object must provide a `collector` function for each arm.
 * The collector is called with the arm's config and must return an array
 * of numeric metric values.
 *
 * @param {Object} config
 * @param {string} config.name - Experiment name
 * @param {string} config.hypothesis - What you expect to happen
 * @param {string} config.metric - Name of the metric being measured
 * @param {Object} config.baseline - Baseline arm configuration
 * @param {Object} config.treatment - Treatment arm configuration
 * @param {Function} config.collector - async (armConfig) => number[]
 * @param {Object} [config.success_criteria]
 * @param {number} [config.success_criteria.min_improvement_pct] - Min improvement to keep (default: 3)
 * @param {number} [config.success_criteria.alpha] - Significance level (default: 0.05)
 * @param {boolean} [config.record] - Whether to record in DB (default: true)
 * @param {Object} [config.metadata] - Additional metadata to store
 * @returns {Promise<Object>} Experiment result with verdict
 */
async function runExperiment(config) {
  const {
    name,
    hypothesis,
    metric,
    baseline: baselineConfig,
    treatment: treatmentConfig,
    collector,
    success_criteria = {},
    record = true,
    metadata = {},
  } = config;

  if (!name || !metric) {
    throw new Error('Experiment name and metric are required');
  }

  if (typeof collector !== 'function') {
    throw new Error('A collector function is required: async (armConfig) => number[]');
  }

  const startTime = Date.now();

  // Collect baseline samples
  let baselineSamples;
  try {
    baselineSamples = await collector(baselineConfig);
    if (!Array.isArray(baselineSamples)) {
      throw new Error('Collector must return an array of numbers');
    }
  } catch (err) {
    throw new Error(`Baseline collection failed: ${err.message}`);
  }

  // Collect treatment samples
  let treatmentSamples;
  try {
    treatmentSamples = await collector(treatmentConfig);
    if (!Array.isArray(treatmentSamples)) {
      throw new Error('Collector must return an array of numbers');
    }
  } catch (err) {
    throw new Error(`Treatment collection failed: ${err.message}`);
  }

  const durationMs = Date.now() - startTime;

  // Compare results
  const comparison = compareResults(baselineSamples, treatmentSamples, {
    alpha: success_criteria.alpha,
    min_improvement_pct: success_criteria.min_improvement_pct,
    bootstrap_iterations: success_criteria.bootstrap_iterations,
    bootstrap_confidence: success_criteria.bootstrap_confidence,
  });

  const result = {
    name,
    hypothesis,
    metric,
    baseline_config: baselineConfig,
    treatment_config: treatmentConfig,
    baseline_samples: baselineSamples,
    treatment_samples: treatmentSamples,
    duration_ms: durationMs,
    ...comparison,
    metadata,
  };

  // Record to database
  if (record) {
    try {
      await recordExperiment(name, hypothesis, result);
    } catch (err) {
      console.warn(`[experiment-manager] Failed to record experiment: ${err.message}`);
      result.recording_error = err.message;
    }
  }

  return result;
}

/**
 * Record an experiment result in PostgreSQL.
 *
 * @param {string} name - Experiment name
 * @param {string} hypothesis - What was being tested
 * @param {Object} result - Experiment result from compareResults or runExperiment
 * @returns {Promise<number>} Inserted row ID
 */
async function recordExperiment(name, hypothesis, result) {
  await ensureSchema();
  const pool = getPool();

  const row = await pool.query(`
    INSERT INTO workflow.experiments
    (name, hypothesis, metric, baseline_config, treatment_config,
     baseline_samples, treatment_samples, baseline_mean, treatment_mean,
     improvement_pct, p_value, ci_lower, ci_upper, effect_size,
     verdict, success_criteria, metadata)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
    RETURNING id
  `, [
    name,
    hypothesis || null,
    result.metric || 'unknown',
    JSON.stringify(result.baseline_config || {}),
    JSON.stringify(result.treatment_config || {}),
    JSON.stringify(result.baseline_samples || []),
    JSON.stringify(result.treatment_samples || []),
    result.baseline_mean,
    result.treatment_mean,
    result.improvement_pct,
    result.p_value,
    result.ci_lower,
    result.ci_upper,
    result.effect_size,
    result.verdict,
    JSON.stringify(result.success_criteria || {}),
    JSON.stringify(result.metadata || {}),
  ]);

  return row.rows[0].id;
}

/**
 * Retrieve past experiment results from the database.
 *
 * @param {Object} [filters]
 * @param {string} [filters.name] - Filter by experiment name (exact match)
 * @param {string} [filters.verdict] - Filter by verdict (keep/remove/inconclusive)
 * @param {string} [filters.metric] - Filter by metric name
 * @param {number} [filters.limit] - Max results (default: 20)
 * @param {string} [filters.order] - 'asc' or 'desc' (default: 'desc' by created_at)
 * @returns {Promise<Object[]>} Array of experiment records
 */
async function getExperimentHistory(filters = {}) {
  await ensureSchema();
  const pool = getPool();

  const conditions = [];
  const params = [];
  let paramIdx = 1;

  if (filters.name) {
    conditions.push(`name = $${paramIdx++}`);
    params.push(filters.name);
  }
  if (filters.verdict) {
    conditions.push(`verdict = $${paramIdx++}`);
    params.push(filters.verdict);
  }
  if (filters.metric) {
    conditions.push(`metric = $${paramIdx++}`);
    params.push(filters.metric);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const order = filters.order === 'asc' ? 'ASC' : 'DESC';
  const limit = filters.limit || 20;

  const result = await pool.query(`
    SELECT * FROM workflow.experiments
    ${where}
    ORDER BY created_at ${order}
    LIMIT $${paramIdx}
  `, [...params, limit]);

  return result.rows;
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Core API
  runExperiment,
  compareResults,
  recordExperiment,
  getExperimentHistory,

  // Statistical functions (exposed for testing)
  mean,
  variance,
  stddev,
  welchTTest,
  bootstrapDifference,
  tDistPValue,
  regularizedIncompleteBeta,
  lnGamma,

  // Database management
  ensureSchema,
  closePool,

  // Configuration (export for customization)
  EXPERIMENT_CONFIG,
};
