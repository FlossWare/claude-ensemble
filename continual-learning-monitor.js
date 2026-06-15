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

  if (result.rows.length === 0) {
    return {
      totalRequests: 0,
      successRate: 0.0,
      avgQualityScore: 0.0,
      avgDurationMs: 0.0,
      totalCostUsd: 0.0
    };
  }

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
}

// Export all functions
export default {
  getRecentUsage,
  enforceQuotas,
  getQualityMetrics,
  getDiversityStatus,
  generateReport,
  recordRequest,
  CONFIG
};
