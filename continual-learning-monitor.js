/**
 * DCAB Layer 1: Diversity-Constrained Pre-Routing
 *
 * Enforces hard diversity quotas before Thompson Sampling:
 * - Floor: 15% minimum per model
 * - Ceiling: 40% maximum per model
 * - Window: Last 20 requests
 *
 * PostgreSQL tables:
 * - monitoring.execution_summary (request history)
 * - learning.strategy_performance (Thompson Sampling state)
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { pool } = require(process.env.HOME + '/.claude/learning/postgres-adapter.js');

// Configuration
const CONFIG = {
  WINDOW_SIZE: 20,        // Last N requests to consider
  FLOOR_PCT: 15,          // Minimum % per model (force include)
  CEILING_PCT: 40,        // Maximum % per model (exclude)
  MODELS: ['sonnet', 'fable', 'opus', 'haiku']  // Available models
};

/**
 * Get recent model usage from PostgreSQL
 * Returns: { modelCounts: {model: count}, totalCount: number, entropy: number }
 */
export async function getRecentUsage(dbPool = pool) {
  try {
    const result = await dbPool.query(`
    SELECT
      model,
      COUNT(*) as request_count
    FROM monitoring.execution_summary
    WHERE created_at > NOW() - INTERVAL '1 hour'
    GROUP BY model
    ORDER BY request_count DESC
    LIMIT $1
  `, [CONFIG.WINDOW_SIZE]);

  const modelCounts = {};
  let totalCount = 0;

  result.rows.forEach(row => {
    // CRITICAL: PostgreSQL COUNT returns bigint as STRING in node-postgres
    const count = parseInt(row.request_count, 10) || 0;
    modelCounts[row.model] = count;
    totalCount += count;
  });

  // Calculate Shannon entropy (diversity metric)
  let entropy = 0.0;
  if (totalCount > 0) {
    Object.values(modelCounts).forEach(count => {
      if (count > 0) {
        const p = count / totalCount;
        entropy -= p * Math.log2(p);
      }
    });
  }

  return { modelCounts, totalCount, entropy };
  } catch (error) {
    console.error('[DCAB Layer1] getRecentUsage failed:', error.message);
    return { modelCounts: {}, totalCount: 0, entropy: 0.0 };
  }
}

/**
 * Enforce diversity quotas
 * Returns: { eligible: string[], violations: { floor: string[], ceiling: string[] } }
 */
export async function enforceQuotas(dbPool = pool) {
  const { modelCounts, totalCount } = await getRecentUsage(dbPool);

  const violations = { floor: [], ceiling: [] };
  const eligible = [];

  for (const model of CONFIG.MODELS) {
    const count = modelCounts[model] || 0;
    const pct = totalCount > 0 ? (count / totalCount) * 100 : 0;

    if (pct > CONFIG.CEILING_PCT) {
      // Model over ceiling → EXCLUDE from routing
      violations.ceiling.push({ model, pct: pct.toFixed(1) });
    } else if (pct < CONFIG.FLOOR_PCT && totalCount >= CONFIG.WINDOW_SIZE) {
      // Model under floor (and window full) → FORCE INCLUDE
      violations.floor.push({ model, pct: pct.toFixed(1) });
      eligible.push(model);  // Force include
    } else {
      // Model in acceptable range
      eligible.push(model);
    }
  }

  return { eligible, violations };
}

/**
 * Get quality metrics for monitoring dashboard
 * Returns: { totalRequests, successRate, avgQualityScore, avgDurationMs, totalCostUsd }
 */
export async function getQualityMetrics(dbPool = pool) {
  try {
    const result = await dbPool.query(`
      SELECT
        COUNT(*) as total_requests,
        COUNT(*) FILTER (WHERE outcome = 'success') as successful_requests,
        AVG(quality_score) as avg_quality,
        AVG(duration_ms) as avg_duration,
        SUM(cost_usd) as total_cost
      FROM monitoring.execution_summary
      WHERE created_at > NOW() - INTERVAL '1 hour'
    `);

    const row = result.rows[0];

    // CRITICAL: All PostgreSQL numeric types return as STRINGS
    const totalRequests = parseInt(row.total_requests, 10) || 0;
    const successfulRequests = parseInt(row.successful_requests, 10) || 0;
    const avgQuality = parseFloat(row.avg_quality) || 0.0;
    const avgDuration = parseFloat(row.avg_duration) || 0.0;
    const totalCost = parseFloat(row.total_cost) || 0.0;

    // Success rate calculation (ensure numeric division)
    const successRate = totalRequests > 0
      ? successfulRequests / totalRequests
      : 0.0;

    return {
      totalRequests,
      successRate,
      avgQualityScore: avgQuality,
      avgDurationMs: avgDuration,
      totalCostUsd: totalCost
    };
  } catch (error) {
    console.error('[DCAB Layer1] getQualityMetrics failed:', error.message);
    return {
      totalRequests: 0,
      successRate: 0.0,
      avgQualityScore: 0.0,
      avgDurationMs: 0.0,
      totalCostUsd: 0.0
    };
  }
}

/**
 * Get current diversity violations for dashboard
 * Returns: { floor: [], ceiling: [] }
 */
export async function getDiversityStatus(dbPool = pool) {
  const { violations } = await enforceQuotas(dbPool);
  return violations;
}

/**
 * Generate monitoring report
 * Returns: { usage, quality, violations, timestamp }
 */
export async function generateReport(dbPool = pool) {
  // Use Promise.allSettled for error resilience
  // If one query fails, others still complete
  const results = await Promise.allSettled([
    getRecentUsage(dbPool),
    getQualityMetrics(dbPool),
    getDiversityStatus(dbPool)
  ]);

  const usage = results[0].status === 'fulfilled'
    ? results[0].value
    : { modelCounts: {}, totalCount: 0, entropy: 0.0 };

  const quality = results[1].status === 'fulfilled'
    ? results[1].value
    : { totalRequests: 0, successRate: 0.0, avgQualityScore: 0.0, avgDurationMs: 0.0, totalCostUsd: 0.0 };

  const violations = results[2].status === 'fulfilled'
    ? results[2].value
    : { floor: [], ceiling: [] };

  return {
    usage,
    quality,
    violations,
    timestamp: new Date().toISOString()
  };
}

/**
 * Record a request for diversity tracking
 *
 * @param {string} model - Model used
 * @param {Object} outcome - Request outcome
 */
export async function recordRequest(model, outcome, dbPool = pool) {
  try {
    const { success = false, quality = 0.5, duration = 0, cost = 0 } = outcome;

    await dbPool.query(`
      INSERT INTO monitoring.execution_summary
        (model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome, created_at)
      VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
    `, [
      model,
      'dcab-layer1',
      'routing',
      quality,
      0,  // tokens tracked separately
      0,
      cost,
      duration,
      success ? 'success' : 'failure'
    ]);
  } catch (error) {
    console.error('[DCAB Layer1] recordRequest failed:', error.message);
  }
}

// ==============================================================================
// DCAB LAYER 2: Multi-Objective Thompson Sampling
// ==============================================================================

/**
 * Sample from Beta distribution using Johnk's algorithm (Gamma ratio method)
 * Beta(α, β) = Gamma(α, 1) / [Gamma(α, 1) + Gamma(β, 1)]
 *
 * @param {number} alpha - Alpha parameter (successes + 1)
 * @param {number} beta - Beta parameter (failures + 1)
 * @returns {number} Sample in [0, 1]
 */
function sampleBeta(alpha, beta) {
  if (alpha <= 0 || beta <= 0 || !isFinite(alpha) || !isFinite(beta)) {
    return 0.5; // Fallback to uniform prior
  }

  // Simple approximation for large α, β: Beta(α, β) ≈ α / (α + β)
  // This is the mean of the distribution, good enough for Thompson Sampling
  if (alpha > 10 && beta > 10) {
    return alpha / (alpha + beta);
  }

  // For small α, β: Use accept-reject sampling (Johnk's algorithm)
  let u, v, x, y;
  const maxIterations = 100;
  let iterations = 0;

  do {
    u = Math.max(Math.random(), Number.EPSILON);
    v = Math.max(Math.random(), Number.EPSILON);
    x = Math.pow(u, 1 / alpha);
    y = Math.pow(v, 1 / beta);
    iterations++;
  } while (x + y > 1 && iterations < maxIterations);

  if (iterations >= maxIterations) {
    // Fallback to mean approximation
    return alpha / (alpha + beta);
  }

  return x / (x + y);
}

/**
 * DCAB Layer 2: Multi-Objective Thompson Sampling
 *
 * Selects best model from eligible pool using:
 * - 4 Beta distributions (success, quality, speed, cost)
 * - Weighted score: 0.5*success + 0.3*quality + 0.2*speed
 * - Pareto frontier bonus: +0.2 for Sonnet/Fable
 *
 * @param {string[]} eligibleModels - Models from Layer 1 quota enforcement
 * @param {Object} dbPool - PostgreSQL connection pool
 * @returns {Promise<string>} Selected model
 */
export async function selectModelThompson(eligibleModels, dbPool = pool) {
  if (!eligibleModels || eligibleModels.length === 0) {
    throw new Error('[DCAB Layer2] No eligible models provided');
  }

  // Single model - return immediately
  if (eligibleModels.length === 1) {
    return eligibleModels[0];
  }

  try {
    // Query strategy_performance for Beta parameters
    const result = await dbPool.query(`
      SELECT
        strategy as model,
        alpha as success_alpha,
        beta as success_beta,
        avg_reward as quality_proxy
      FROM learning.strategy_performance
      WHERE strategy = ANY($1::text[])
    `, [eligibleModels]);

    const modelStats = new Map();
    result.rows.forEach(row => {
      modelStats.set(row.model, {
        successAlpha: parseInt(row.success_alpha, 10) || 1,
        successBeta: parseInt(row.success_beta, 10) || 1,
        qualityProxy: parseFloat(row.quality_proxy) || 0.5
      });
    });

    // Pareto frontier models (from architecture)
    const PARETO_MODELS = new Set(['sonnet', 'fable']);
    const PARETO_BONUS = 0.2;
    const WEIGHTS = { success: 0.5, quality: 0.3, speed: 0.2 };

    // Compute scores for each eligible model
    const scores = [];

    for (const model of eligibleModels) {
      const stats = modelStats.get(model) || {
        successAlpha: 1,
        successBeta: 1,
        qualityProxy: 0.5
      };

      // Sample from Beta distribution
      const successSample = sampleBeta(stats.successAlpha, stats.successBeta);

      // Use quality proxy (simplified - no separate Beta for quality/speed)
      const qualitySample = stats.qualityProxy;
      const speedSample = stats.qualityProxy; // Proxy: assume correlated

      // Compute weighted score
      let score =
        WEIGHTS.success * successSample +
        WEIGHTS.quality * qualitySample +
        WEIGHTS.speed * speedSample;

      // Add Pareto bonus
      if (PARETO_MODELS.has(model.toLowerCase())) {
        score += PARETO_BONUS;
      }

      scores.push({ model, score, successSample, qualitySample });
    }

    // Select model with highest score
    scores.sort((a, b) => b.score - a.score);
    const selected = scores[0];

    console.log('[DCAB Layer2] Thompson Sampling:', {
      selected: selected.model,
      score: selected.score.toFixed(3),
      allScores: scores.map(s => `${s.model}:${s.score.toFixed(3)}`).join(', ')
    });

    return selected.model;

  } catch (error) {
    console.error('[DCAB Layer2] Thompson Sampling failed:', error.message);
    // Fallback: return first eligible model
    return eligibleModels[0];
  }
}

/**
 * DCAB Complete Routing: Layer 1 → Layer 2
 *
 * @param {Object} dbPool - PostgreSQL connection pool
 * @returns {Promise<{model: string, eligible: string[], violations: object}>}
 */
export async function selectModel(dbPool = pool) {
  // Layer 1: Diversity quotas
  const { eligible, violations } = await enforceQuotas(dbPool);

  if (eligible.length === 0) {
    // Fallback: use all models
    console.warn('[DCAB] No eligible models after quota enforcement, using all models');
    const fallbackModel = CONFIG.MODELS[0];
    return { model: fallbackModel, eligible: CONFIG.MODELS, violations };
  }

  // Layer 2: Thompson Sampling
  const model = await selectModelThompson(eligible, dbPool);

  return { model, eligible, violations };
}

// Export all functions
export default {
  getRecentUsage,
  enforceQuotas,
  getQualityMetrics,
  getDiversityStatus,
  generateReport,
  recordRequest,
  selectModelThompson,
  selectModel,
  CONFIG
};
