/**
 * Capability Registry
 *
 * Database and tracking for model capabilities.
 * Maintains a registry of what each model can do well, with quality scores,
 * cost metrics, and latency data. Enables intelligent model selection based
 * on proven performance on specific tasks.
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');

// Connection pool
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('PostgreSQL pool error:', err.message);
});

/**
 * Register a model capability with execution metrics.
 * Updates existing capability or creates new one.
 *
 * @param {string} model - Model name (e.g., 'opus', 'sonnet', 'deepseek-coder')
 * @param {string} capability - Capability type (e.g., 'code_generation', 'research')
 * @param {object} metrics - Execution metrics
 * @param {number} metrics.quality_score - Quality score (0-1)
 * @param {number} metrics.cost_usd - Cost in USD
 * @param {number} metrics.latency_ms - Latency in milliseconds
 * @param {boolean} [metrics.success] - Whether execution succeeded (default: true)
 * @returns {Promise<{id: number}>} Capability ID
 *
 * @example
 *   const cap = await registerCapability('opus', 'code_generation', {
 *     quality_score: 0.92,
 *     cost_usd: 0.05,
 *     latency_ms: 2500,
 *     success: true
 *   });
 *   console.log(cap.id); // 1
 */
async function registerCapability(model, capability, metrics) {
  try {
    const result = await pool.query(
      `SELECT learning.register_capability($1, $2, $3, $4, $5, $6) as id`,
      [
        model,
        capability,
        metrics.quality_score,
        metrics.cost_usd,
        metrics.latency_ms,
        metrics.success !== false
      ]
    );
    return { id: result.rows[0].id };
  } catch (error) {
    console.error('registerCapability error:', error);
    throw error;
  }
}

/**
 * Get models capable of handling a specific capability with quality requirements.
 * Returns models sorted by quality score (highest first).
 *
 * @param {string} capability - Capability type (e.g., 'code_generation')
 * @param {object} [requirements] - Filter requirements
 * @param {number} [requirements.min_quality] - Minimum quality score (0-1)
 * @param {number} [requirements.min_confidence] - Minimum confidence (0-1)
 * @param {number} [requirements.max_cost] - Maximum cost per execution in USD
 * @param {number} [requirements.max_latency_ms] - Maximum latency in milliseconds
 * @returns {Promise<Array>} List of capable models with metrics
 *
 * @example
 *   const models = await getCapableModels('code_generation', {
 *     min_quality: 0.85,
 *     max_cost: 0.10
 *   });
 *   // [{ model: 'opus', quality_score: 0.92, ... }]
 */
async function getCapableModels(capability, requirements = {}) {
  try {
    const {
      min_quality = 0,
      min_confidence = 0,
      max_cost = Infinity,
      max_latency_ms = Infinity
    } = requirements;

    const query = `
      SELECT
        model,
        capability,
        quality_score,
        avg_cost,
        avg_latency_ms,
        executions,
        success_count,
        confidence,
        ROUND(100.0 * success_count / executions, 1) AS success_rate,
        updated_at
      FROM learning.model_capabilities
      WHERE capability = $1
        AND quality_score >= $2
        AND confidence >= $3
        AND avg_cost <= $4
        AND avg_latency_ms <= $5
      ORDER BY quality_score DESC, confidence DESC
    `;

    const result = await pool.query(query, [
      capability,
      min_quality,
      min_confidence,
      max_cost,
      max_latency_ms
    ]);

    return result.rows;
  } catch (error) {
    console.error('getCapableModels error:', error);
    throw error;
  }
}

/**
 * Update capability metrics after execution completion.
 * Recalculates averages and confidence based on new result.
 *
 * @param {number} capabilityId - Capability ID (from registerCapability)
 * @param {object} result - Execution result
 * @param {number} result.quality_score - Quality score (0-1)
 * @param {number} result.cost_usd - Cost in USD
 * @param {number} result.latency_ms - Latency in milliseconds
 * @param {boolean} [result.success] - Whether execution succeeded (default: true)
 * @param {string} [result.error_message] - Error message if failed
 * @returns {Promise<void>}
 *
 * @example
 *   await updateCapabilityMetrics(1, {
 *     quality_score: 0.95,
 *     cost_usd: 0.052,
 *     latency_ms: 2450,
 *     success: true
 *   });
 */
async function updateCapabilityMetrics(capabilityId, result) {
  try {
    // Get current metrics
    const current = await pool.query(
      `SELECT quality_score, avg_cost, avg_latency_ms, executions, success_count, failure_count
       FROM learning.model_capabilities WHERE id = $1`,
      [capabilityId]
    );

    if (current.rows.length === 0) {
      throw new Error(`Capability ${capabilityId} not found`);
    }

    const {
      quality_score: curr_quality,
      avg_cost: curr_cost,
      avg_latency_ms: curr_latency,
      executions: curr_executions,
      success_count: curr_success,
      failure_count: curr_failure
    } = current.rows[0];

    // Calculate new metrics
    const new_executions = curr_executions + 1;
    const new_success = curr_success + (result.success !== false ? 1 : 0);
    const new_failure = curr_failure + (result.success === false ? 1 : 0);
    const new_quality = (curr_quality * curr_executions + result.quality_score) / new_executions;
    const new_cost = (curr_cost * curr_executions + result.cost_usd) / new_executions;
    const new_latency = (curr_latency * curr_executions + result.latency_ms) / new_executions;
    const new_confidence = Math.min(1.0, new_executions / 10.0);

    // Update capability metrics
    await pool.query(
      `UPDATE learning.model_capabilities
       SET quality_score = $2,
           avg_cost = $3,
           avg_latency_ms = $4,
           executions = $5,
           success_count = $6,
           failure_count = $7,
           confidence = $8,
           last_executed_at = NOW(),
           updated_at = NOW()
       WHERE id = $1`,
      [
        capabilityId,
        new_quality,
        new_cost,
        new_latency,
        new_executions,
        new_success,
        new_failure,
        new_confidence
      ]
    );

    // Record execution in history
    await pool.query(
      `INSERT INTO learning.capability_executions (capability_id, quality_score, cost_usd, latency_ms, success, error_message)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        capabilityId,
        result.quality_score,
        result.cost_usd,
        result.latency_ms,
        result.success !== false,
        result.error_message || null
      ]
    );
  } catch (error) {
    console.error('updateCapabilityMetrics error:', error);
    throw error;
  }
}

/**
 * Get all capabilities for a specific model.
 *
 * @param {string} model - Model name
 * @returns {Promise<Array>} List of capabilities with metrics
 *
 * @example
 *   const caps = await getModelCapabilities('opus');
 *   // [{ capability: 'code_generation', quality_score: 0.92, ... }]
 */
async function getModelCapabilities(model) {
  try {
    const result = await pool.query(
      `SELECT
         capability,
         quality_score,
         avg_cost,
         avg_latency_ms,
         executions,
         success_count,
         confidence,
         ROUND(100.0 * success_count / executions, 1) AS success_rate,
         updated_at
       FROM learning.model_capabilities
       WHERE model = $1
       ORDER BY quality_score DESC`,
      [model]
    );

    return result.rows;
  } catch (error) {
    console.error('getModelCapabilities error:', error);
    throw error;
  }
}

/**
 * Get summary of all available models and their capabilities.
 *
 * @returns {Promise<Array>} Summary of models
 *
 * @example
 *   const summary = await getModelSummary();
 *   // [{ model: 'opus', num_capabilities: 5, avg_quality: 0.89, ... }]
 */
async function getModelSummary() {
  try {
    const result = await pool.query(
      `SELECT
         model,
         COUNT(DISTINCT capability) AS num_capabilities,
         ROUND(AVG(quality_score)::numeric, 3) AS avg_quality,
         ROUND(AVG(avg_cost)::numeric, 6) AS avg_cost,
         ROUND(AVG(avg_latency_ms)::numeric, 2) AS avg_latency_ms,
         SUM(executions) AS total_executions,
         SUM(success_count) AS total_successes,
         ROUND(100.0 * SUM(success_count) / NULLIF(SUM(executions), 0)::numeric, 1) AS overall_success_rate,
         MAX(updated_at) AS last_updated
       FROM learning.model_capabilities
       GROUP BY model
       ORDER BY avg_quality DESC`
    );

    return result.rows;
  } catch (error) {
    console.error('getModelSummary error:', error);
    throw error;
  }
}

/**
 * Get coverage of capabilities across available models.
 *
 * @param {string} [capability] - Optional specific capability
 * @returns {Promise<Array>} Capability coverage
 *
 * @example
 *   const coverage = await getCapabilityCoverage();
 *   // [{ capability: 'code_generation', num_models: 8, avg_quality: 0.85, ... }]
 */
async function getCapabilityCoverage(capability = null) {
  try {
    let query = `
      SELECT
        capability,
        COUNT(DISTINCT model) AS num_models,
        ROUND(AVG(quality_score)::numeric, 3) AS avg_quality,
        MAX(quality_score) AS best_quality,
        MIN(quality_score) AS worst_quality,
        ROUND(AVG(avg_cost)::numeric, 6) AS avg_cost,
        SUM(executions) AS total_executions,
        MAX(updated_at) AS last_updated
      FROM learning.model_capabilities
    `;

    const params = [];

    if (capability) {
      query += ` WHERE capability = $1`;
      params.push(capability);
    }

    query += ` GROUP BY capability ORDER BY total_executions DESC`;

    const result = await pool.query(query, params);
    return result.rows;
  } catch (error) {
    console.error('getCapabilityCoverage error:', error);
    throw error;
  }
}

/**
 * Find best model for a specific capability with requirements.
 * Returns the highest-scoring model that meets all requirements.
 *
 * @param {string} capability - Capability type
 * @param {object} [requirements] - Filter requirements
 * @returns {Promise<object|null>} Best matching model or null if none found
 *
 * @example
 *   const best = await findBestModel('code_generation', {
 *     min_quality: 0.85,
 *     max_cost: 0.10
 *   });
 *   // { model: 'opus', quality_score: 0.92, ... }
 */
async function findBestModel(capability, requirements = {}) {
  const models = await getCapableModels(capability, requirements);
  return models.length > 0 ? models[0] : null;
}

/**
 * Get execution history for a specific capability.
 *
 * @param {number} capabilityId - Capability ID
 * @param {number} [limit] - Number of recent executions to return (default: 50)
 * @returns {Promise<Array>} Recent execution records
 *
 * @example
 *   const history = await getExecutionHistory(1, 20);
 *   // [{ quality_score: 0.92, cost_usd: 0.05, latency_ms: 2500, ... }]
 */
async function getExecutionHistory(capabilityId, limit = 50) {
  try {
    const result = await pool.query(
      `SELECT
         quality_score,
         cost_usd,
         latency_ms,
         success,
         error_message,
         executed_at
       FROM learning.capability_executions
       WHERE capability_id = $1
       ORDER BY executed_at DESC
       LIMIT $2`,
      [capabilityId, limit]
    );

    return result.rows;
  } catch (error) {
    console.error('getExecutionHistory error:', error);
    throw error;
  }
}

/**
 * Get capability by model and capability name.
 *
 * @param {string} model - Model name
 * @param {string} capability - Capability type
 * @returns {Promise<object|null>} Capability record or null if not found
 *
 * @example
 *   const cap = await getCapability('opus', 'code_generation');
 *   // { id: 1, model: 'opus', capability: 'code_generation', ... }
 */
async function getCapability(model, capability) {
  try {
    const result = await pool.query(
      `SELECT * FROM learning.model_capabilities
       WHERE model = $1 AND capability = $2`,
      [model, capability]
    );

    return result.rows.length > 0 ? result.rows[0] : null;
  } catch (error) {
    console.error('getCapability error:', error);
    throw error;
  }
}

/**
 * Auto-populate capability registry from execution history.
 * Analyzes workflow execution logs and creates capability records.
 *
 * @param {object} [options] - Population options
 * @param {string} [options.from_date] - Start date (default: 7 days ago)
 * @param {number} [options.min_executions] - Minimum executions per capability (default: 1)
 * @returns {Promise<{created: number, updated: number}>} Statistics
 *
 * @example
 *   const stats = await autoPopulateFromHistory({
 *     from_date: '2026-06-20',
 *     min_executions: 5
 *   });
 *   // { created: 12, updated: 8 }
 */
async function autoPopulateFromHistory(options = {}) {
  try {
    const {
      from_date = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      min_executions = 1
    } = options;

    // Query workflow execution summary to build capability map
    const result = await pool.query(
      `WITH capability_stats AS (
         SELECT
           model,
           CASE
             WHEN task_type LIKE '%code_gen%' THEN 'code_generation'
             WHEN task_type LIKE '%review%' THEN 'code_review'
             WHEN task_type LIKE '%research%' THEN 'research'
             WHEN task_type LIKE '%analysis%' THEN 'analysis'
             WHEN task_type LIKE '%debug%' THEN 'debugging'
             ELSE task_type
           END as capability,
           COUNT(*) as executions,
           SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
           ROUND(AVG(quality_score)::numeric, 4) as avg_quality,
           ROUND(AVG(cost_usd)::numeric, 6) as avg_cost,
           ROUND(AVG(duration_ms)::numeric, 2) as avg_latency_ms
         FROM monitoring.execution_summary
         WHERE created_at >= $1::timestamp
           AND model IS NOT NULL
           AND task_type IS NOT NULL
         GROUP BY model, capability
         HAVING COUNT(*) >= $2
       )
       INSERT INTO learning.model_capabilities
         (model, capability, quality_score, avg_cost, avg_latency_ms, executions, success_count, confidence)
       SELECT
         model,
         capability,
         avg_quality,
         avg_cost,
         avg_latency_ms,
         executions,
         successes,
         LEAST(1.0, executions::numeric / 10.0)
       FROM capability_stats
       ON CONFLICT (model, capability) DO UPDATE SET
         quality_score = EXCLUDED.quality_score,
         avg_cost = EXCLUDED.avg_cost,
         avg_latency_ms = EXCLUDED.avg_latency_ms,
         executions = EXCLUDED.executions,
         success_count = EXCLUDED.success_count,
         confidence = EXCLUDED.confidence,
         updated_at = NOW()
       RETURNING (xmax = 0) as created`,
      [from_date, min_executions]
    );

    const created = result.rows.filter(r => r.created).length;
    const updated = result.rows.length - created;

    return { created, updated };
  } catch (error) {
    console.error('autoPopulateFromHistory error:', error);
    throw error;
  }
}

/**
 * Clear old execution history to manage storage.
 *
 * @param {object} [options] - Cleanup options
 * @param {number} [options.days_to_keep] - Days of history to keep (default: 90)
 * @returns {Promise<{deleted: number}>} Number of deleted records
 *
 * @example
 *   const stats = await cleanupExecutionHistory({ days_to_keep: 30 });
 *   // { deleted: 1250 }
 */
async function cleanupExecutionHistory(options = {}) {
  try {
    const { days_to_keep = 90 } = options;

    const result = await pool.query(
      `DELETE FROM learning.capability_executions
       WHERE executed_at < NOW() - INTERVAL '1 day' * $1
       RETURNING id`,
      [days_to_keep]
    );

    return { deleted: result.rows.length };
  } catch (error) {
    console.error('cleanupExecutionHistory error:', error);
    throw error;
  }
}

/**
 * Export capability registry to JSON.
 *
 * @returns {Promise<string>} JSON string representation of registry
 *
 * @example
 *   const json = await exportRegistry();
 *   fs.writeFileSync('registry.json', json);
 */
async function exportRegistry() {
  try {
    const capabilities = await pool.query(
      `SELECT * FROM learning.model_capabilities ORDER BY model, capability`
    );

    return JSON.stringify(capabilities.rows, null, 2);
  } catch (error) {
    console.error('exportRegistry error:', error);
    throw error;
  }
}

module.exports = {
  registerCapability,
  getCapableModels,
  updateCapabilityMetrics,
  getModelCapabilities,
  getModelSummary,
  getCapabilityCoverage,
  findBestModel,
  getExecutionHistory,
  getCapability,
  autoPopulateFromHistory,
  cleanupExecutionHistory,
  exportRegistry
  // NOTE: pool is no longer exported to prevent unauthorized database access
};
