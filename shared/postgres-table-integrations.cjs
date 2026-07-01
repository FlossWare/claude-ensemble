/**
 * PostgreSQL Table Integration Wrappers
 *
 * Wires unused PostgreSQL tables into the appropriate integration points:
 * - learning.diversity_violations: Model selection diversity enforcement
 * - learning.procedural_rules: Pattern/rule extraction from executions
 * - monitoring.execution_log: Detailed task execution tracking
 * - monitoring.model_tuning: Model parameter tuning history
 *
 * Created: 2026-07-01 (Issue #251-254)
 */

const { Pool } = require('pg');

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

// ============================================================================
// DIVERSITY VIOLATIONS
// Integration point: Model selection/routing
// ============================================================================

/**
 * Record diversity violation when model usage exceeds quotas
 *
 * Call this from model selection logic (multi-model-router, contextual-bandits, etc.)
 *
 * @param {Object} violation
 * @param {string} violation.violation_type - 'floor_breach', 'ceiling_breach', 'entropy_collapse'
 * @param {string} violation.model - Model that violated quota
 * @param {number} violation.current_usage_pct - Current usage percentage (0-100)
 * @param {number} violation.quota_limit_pct - Quota limit that was breached (0-100)
 * @param {number} [violation.diversity_entropy] - Shannon entropy of current distribution
 * @param {string} violation.action_taken - Action: 'forced_rotation', 'banned_temporarily', 'warning_only'
 *
 * @example
 * // In model selection:
 * const distribution = calculateModelDistribution();
 * if (distribution['opus'] > 70) {
 *   await recordDiversityViolation({
 *     violation_type: 'ceiling_breach',
 *     model: 'opus',
 *     current_usage_pct: 72,
 *     quota_limit_pct: 70,
 *     diversity_entropy: 0.45,
 *     action_taken: 'forced_rotation'
 *   });
 * }
 */
async function recordDiversityViolation(violation) {
  const {
    violation_type,
    model,
    current_usage_pct,
    quota_limit_pct,
    diversity_entropy,
    action_taken
  } = violation;

  try {
    await pool.query(`
      INSERT INTO learning.diversity_violations
      (violation_type, model, current_usage_pct, quota_limit_pct, diversity_entropy, action_taken)
      VALUES ($1, $2, $3, $4, $5, $6)
    `, [violation_type, model, current_usage_pct, quota_limit_pct, diversity_entropy, action_taken]);
  } catch (err) {
    console.error('Failed to record diversity violation:', err.message);
  }
}

/**
 * Query recent diversity violations for monitoring
 *
 * @param {Object} [filters]
 * @param {string} [filters.model] - Filter by specific model
 * @param {string} [filters.violation_type] - Filter by violation type
 * @param {number} [filters.limit=20] - Max violations to return
 * @returns {Promise<Array>} Recent violations
 *
 * @example
 * const recentViolations = await queryDiversityViolations({ model: 'opus', limit: 10 });
 * recentViolations.forEach(v => {
 *   console.log(`${v.timestamp}: ${v.model} ${v.violation_type} (${v.current_usage_pct}%)`);
 * });
 */
async function queryDiversityViolations(filters = {}) {
  const { model, violation_type, limit = 20 } = filters;

  let query = 'SELECT * FROM learning.diversity_violations WHERE 1=1';
  const params = [];

  if (model) {
    params.push(model);
    query += ` AND model = $${params.length}`;
  }

  if (violation_type) {
    params.push(violation_type);
    query += ` AND violation_type = $${params.length}`;
  }

  params.push(limit);
  query += ` ORDER BY timestamp DESC LIMIT $${params.length}`;

  try {
    const result = await pool.query(query, params);
    return result.rows;
  } catch (err) {
    console.error('Failed to query diversity violations:', err.message);
    return [];
  }
}

/**
 * Calculate diversity entropy from model usage distribution
 * Returns Shannon entropy (higher = more diverse)
 *
 * @param {Object} distribution - Model usage counts { 'opus': 50, 'sonnet': 30, 'haiku': 20 }
 * @returns {number} Entropy value (0 = all one model, higher = more diverse)
 *
 * @example
 * const entropy = calculateDiversityEntropy({ opus: 70, sonnet: 20, haiku: 10 });
 * // entropy ~= 0.96 (low diversity)
 *
 * const betterEntropy = calculateDiversityEntropy({ opus: 33, sonnet: 33, haiku: 34 });
 * // betterEntropy ~= 1.58 (high diversity)
 */
function calculateDiversityEntropy(distribution) {
  const total = Object.values(distribution).reduce((sum, count) => sum + count, 0);
  if (total === 0) return 0;

  let entropy = 0;
  Object.values(distribution).forEach(count => {
    if (count > 0) {
      const p = count / total;
      entropy -= p * Math.log2(p);
    }
  });

  return entropy;
}

// ============================================================================
// PROCEDURAL RULES
// Integration point: Pattern/rule extraction from successful executions
// ============================================================================

/**
 * Extract and store procedural rule from successful execution
 *
 * Call this after successful task completion to learn patterns.
 *
 * @param {Object} rule
 * @param {Object} rule.condition - Condition that triggered this rule (JSONB)
 * @param {string} rule.action - Action to take when condition matches
 * @param {number} rule.confidence - Confidence score (0-1)
 * @param {number} [rule.evidence_count=1] - Number of times this pattern observed
 *
 * @example
 * // After successful Java code generation:
 * await recordProceduralRule({
 *   condition: {
 *     task_type: 'code_generation',
 *     language: 'java',
 *     framework: 'maven',
 *     input_tokens_range: [1000, 5000]
 *   },
 *   action: 'use_deepseek_coder',
 *   confidence: 0.92,
 *   evidence_count: 5
 * });
 */
async function recordProceduralRule(rule) {
  const { condition, action, confidence, evidence_count = 1 } = rule;

  // Create deterministic hash of condition for deduplication
  const conditionHash = require('crypto')
    .createHash('sha256')
    .update(JSON.stringify(condition))
    .digest('hex')
    .substring(0, 16);

  try {
    await pool.query(`
      INSERT INTO learning.procedural_rules
      (condition_hash, condition, action, confidence, evidence_count)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (condition_hash, action) DO UPDATE SET
        confidence = GREATEST(procedural_rules.confidence, EXCLUDED.confidence),
        evidence_count = procedural_rules.evidence_count + EXCLUDED.evidence_count,
        last_updated = NOW()
    `, [conditionHash, JSON.stringify(condition), action, confidence, evidence_count]);
  } catch (err) {
    console.error('Failed to record procedural rule:', err.message);
  }
}

/**
 * Query procedural rules matching condition
 *
 * @param {Object} condition - Condition to match
 * @param {number} [minConfidence=0.7] - Minimum confidence threshold
 * @returns {Promise<Array>} Matching rules sorted by confidence
 *
 * @example
 * const rules = await queryProceduralRules({
 *   task_type: 'code_generation',
 *   language: 'java'
 * }, 0.8);
 *
 * if (rules.length > 0) {
 *   console.log(`Recommended action: ${rules[0].action} (confidence: ${rules[0].confidence})`);
 * }
 */
async function queryProceduralRules(condition, minConfidence = 0.7) {
  try {
    // Exact hash match first
    const conditionHash = require('crypto')
      .createHash('sha256')
      .update(JSON.stringify(condition))
      .digest('hex')
      .substring(0, 16);

    const exactMatch = await pool.query(`
      SELECT condition, action, confidence, evidence_count, last_updated
      FROM learning.procedural_rules
      WHERE condition_hash = $1 AND confidence >= $2
      ORDER BY confidence DESC, evidence_count DESC
    `, [conditionHash, minConfidence]);

    if (exactMatch.rows.length > 0) {
      return exactMatch.rows.map(row => ({
        ...row,
        condition: typeof row.condition === 'string' ? JSON.parse(row.condition) : row.condition
      }));
    }

    // Fallback: JSONB containment (partial match)
    const partialMatch = await pool.query(`
      SELECT condition, action, confidence, evidence_count, last_updated
      FROM learning.procedural_rules
      WHERE condition @> $1::jsonb AND confidence >= $2
      ORDER BY confidence DESC, evidence_count DESC
      LIMIT 10
    `, [JSON.stringify(condition), minConfidence]);

    return partialMatch.rows.map(row => ({
      ...row,
      condition: typeof row.condition === 'string' ? JSON.parse(row.condition) : row.condition
    }));

  } catch (err) {
    console.error('Failed to query procedural rules:', err.message);
    return [];
  }
}

// ============================================================================
// EXECUTION LOG
// Integration point: Task execution tracking (detailed, not summary)
// ============================================================================

/**
 * Log detailed task execution
 *
 * Call this during/after task execution for detailed tracking.
 * Complements monitoring.execution_summary (which is aggregated).
 *
 * @param {Object} execution
 * @param {string} execution.model - Model used
 * @param {string} [execution.model_role='worker'] - 'worker', 'arbiter', 'verifier'
 * @param {string} [execution.workflow] - Workflow name
 * @param {string} [execution.task_type] - Task category
 * @param {string} [execution.phase] - Execution phase
 * @param {string} [execution.label] - Task label
 * @param {Object} [execution.parameters={}] - Task parameters (JSONB)
 * @param {number} [execution.quality_score] - Quality score (0-1)
 * @param {number} [execution.confidence] - Model confidence (0-1)
 * @param {number} [execution.consensus_score] - Consensus with other models (0-1)
 * @param {boolean} [execution.was_selected=false] - Was this model's output selected?
 * @param {number} [execution.input_tokens=0] - Input token count
 * @param {number} [execution.output_tokens=0] - Output token count
 * @param {number} [execution.cost_usd=0.0] - Cost in USD
 * @param {number} [execution.duration_ms=0] - Duration in milliseconds
 * @param {string} [execution.outcome='unknown'] - 'SUCCESS', 'FAILURE', 'PARTIAL', 'unknown'
 * @param {string} [execution.outcome_notes] - Notes about outcome
 * @param {string} [execution.request_hash] - Hash of request for deduplication
 * @param {string} [execution.response_hash] - Hash of response
 * @param {string} [execution.error] - Error message if failed
 * @param {string} [execution.run_id] - Workflow run identifier
 * @param {string} [execution.execution_id] - Specific execution ID
 *
 * @example
 * // In worker execution:
 * const startTime = Date.now();
 * const result = await executeTask(...);
 * await logExecution({
 *   model: 'opus',
 *   model_role: 'worker',
 *   workflow: 'code-review',
 *   task_type: 'security',
 *   phase: 'analysis',
 *   quality_score: 0.92,
 *   confidence: 0.88,
 *   was_selected: true,
 *   input_tokens: 1500,
 *   output_tokens: 800,
 *   duration_ms: Date.now() - startTime,
 *   outcome: 'SUCCESS'
 * });
 */
async function logExecution(execution) {
  const {
    model,
    model_role = 'worker',
    workflow,
    task_type,
    phase,
    label,
    parameters = {},
    quality_score,
    confidence,
    consensus_score,
    was_selected = false,
    input_tokens = 0,
    output_tokens = 0,
    cost_usd = 0.0,
    duration_ms = 0,
    outcome = 'unknown',
    outcome_notes,
    request_hash,
    response_hash,
    error,
    run_id,
    execution_id,
    task_description,
    worker_models,
    arbiter_model,
    model_count = 1,
    strategy,
    diversity_score,
    total_input_tokens,
    total_output_tokens,
    total_cost_usd,
    per_model_costs,
    per_model_durations,
    selected_model,
    session_id,
    parent_execution_id,
    counterfactual_scores,
    selection_method = 'static'
  } = execution;

  try {
    await pool.query(`
      INSERT INTO monitoring.execution_log
      (model, model_role, workflow, task_type, phase, label, parameters,
       quality_score, confidence, consensus_score, was_selected,
       input_tokens, output_tokens, cost_usd, duration_ms, outcome, outcome_notes,
       request_hash, response_hash, error, run_id, execution_id,
       task_description, worker_models, arbiter_model, model_count,
       strategy, diversity_score, total_input_tokens, total_output_tokens,
       total_cost_usd, per_model_costs, per_model_durations, selected_model,
       session_id, parent_execution_id, counterfactual_scores, selection_method)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17,
              $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32,
              $33, $34, $35, $36, $37, $38)
    `, [
      model, model_role, workflow, task_type, phase, label, JSON.stringify(parameters),
      quality_score, confidence, consensus_score, was_selected,
      input_tokens, output_tokens, cost_usd, duration_ms, outcome, outcome_notes,
      request_hash, response_hash, error, run_id, execution_id,
      task_description, worker_models ? JSON.stringify(worker_models) : null,
      arbiter_model, model_count, strategy, diversity_score,
      total_input_tokens || input_tokens, total_output_tokens || output_tokens,
      total_cost_usd || cost_usd,
      per_model_costs ? JSON.stringify(per_model_costs) : null,
      per_model_durations ? JSON.stringify(per_model_durations) : null,
      selected_model, session_id, parent_execution_id,
      counterfactual_scores ? JSON.stringify(counterfactual_scores) : null,
      selection_method
    ]);
  } catch (err) {
    console.error('Failed to log execution:', err.message);
  }
}

/**
 * Query execution log with filters
 *
 * @param {Object} [filters]
 * @param {string} [filters.model] - Filter by model
 * @param {string} [filters.workflow] - Filter by workflow
 * @param {string} [filters.outcome] - Filter by outcome
 * @param {number} [filters.limit=100] - Max results
 * @returns {Promise<Array>} Matching executions
 */
async function queryExecutionLog(filters = {}) {
  const { model, workflow, outcome, limit = 100 } = filters;

  let query = 'SELECT * FROM monitoring.execution_log WHERE 1=1';
  const params = [];

  if (model) {
    params.push(model);
    query += ` AND model = $${params.length}`;
  }

  if (workflow) {
    params.push(workflow);
    query += ` AND workflow = $${params.length}`;
  }

  if (outcome) {
    params.push(outcome);
    query += ` AND outcome = $${params.length}`;
  }

  params.push(limit);
  query += ` ORDER BY timestamp DESC LIMIT $${params.length}`;

  try {
    const result = await pool.query(query, params);
    return result.rows.map(row => {
      // Helper to safely parse JSONB fields
      const parseJsonb = (field) => {
        if (!field) return null;
        if (typeof field === 'object') return field;
        try {
          return JSON.parse(field);
        } catch {
          return field;
        }
      };

      return {
        ...row,
        parameters: parseJsonb(row.parameters),
        worker_models: parseJsonb(row.worker_models),
        per_model_costs: parseJsonb(row.per_model_costs),
        per_model_durations: parseJsonb(row.per_model_durations),
        counterfactual_scores: parseJsonb(row.counterfactual_scores)
      };
    });
  } catch (err) {
    console.error('Failed to query execution log:', err.message);
    return [];
  }
}

// ============================================================================
// MODEL TUNING
// Integration point: Model parameter optimization history
// ============================================================================

/**
 * Record model tuning parameters and performance
 *
 * Call this when updating model parameters (temperature, top_p, etc.)
 * or when tracking performance for specific configurations.
 *
 * @param {Object} tuning
 * @param {string} tuning.model - Model name
 * @param {string} tuning.task_type - Task type being tuned for
 * @param {Object} tuning.optimal_params - Optimal parameters (JSONB)
 * @param {number} [tuning.avg_quality=0.0] - Average quality score
 * @param {number} [tuning.avg_confidence=0.0] - Average confidence
 * @param {number} [tuning.avg_cost_usd=0.0] - Average cost
 * @param {number} [tuning.avg_duration_ms=0.0] - Average duration
 * @param {number} [tuning.sample_count=0] - Sample count for averages
 * @param {number} [tuning.success_rate=0.0] - Success rate (0-1)
 * @param {number} [tuning.selection_rate=0.0] - Selection rate in multi-model scenarios (0-1)
 * @param {Array} [tuning.quality_trend=[]] - Quality trend over time
 * @param {Array} [tuning.cost_trend=[]] - Cost trend over time
 *
 * @example
 * // After parameter sweep:
 * await recordModelTuning({
 *   model: 'opus',
 *   task_type: 'security_review',
 *   optimal_params: {
 *     temperature: 0.3,
 *     top_p: 0.9,
 *     max_tokens: 2000
 *   },
 *   avg_quality: 0.92,
 *   avg_confidence: 0.88,
 *   sample_count: 50,
 *   success_rate: 0.94,
 *   quality_trend: [0.85, 0.87, 0.90, 0.92]
 * });
 */
async function recordModelTuning(tuning) {
  const {
    model,
    task_type,
    optimal_params,
    avg_quality = 0.0,
    avg_confidence = 0.0,
    avg_cost_usd = 0.0,
    avg_duration_ms = 0.0,
    sample_count = 0,
    success_rate = 0.0,
    selection_rate = 0.0,
    quality_trend = [],
    cost_trend = []
  } = tuning;

  try {
    await pool.query(`
      INSERT INTO monitoring.model_tuning
      (model, task_type, optimal_params, avg_quality, avg_confidence,
       avg_cost_usd, avg_duration_ms, sample_count, success_rate,
       selection_rate, quality_trend, cost_trend)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
      ON CONFLICT (model, task_type) DO UPDATE SET
        optimal_params = EXCLUDED.optimal_params,
        avg_quality = EXCLUDED.avg_quality,
        avg_confidence = EXCLUDED.avg_confidence,
        avg_cost_usd = EXCLUDED.avg_cost_usd,
        avg_duration_ms = EXCLUDED.avg_duration_ms,
        sample_count = EXCLUDED.sample_count,
        success_rate = EXCLUDED.success_rate,
        selection_rate = EXCLUDED.selection_rate,
        quality_trend = EXCLUDED.quality_trend,
        cost_trend = EXCLUDED.cost_trend,
        updated_at = NOW()
    `, [
      model, task_type, JSON.stringify(optimal_params),
      avg_quality, avg_confidence, avg_cost_usd, avg_duration_ms,
      sample_count, success_rate, selection_rate,
      JSON.stringify(quality_trend), JSON.stringify(cost_trend)
    ]);
  } catch (err) {
    console.error('Failed to record model tuning:', err.message);
  }
}

/**
 * Query model tuning history
 *
 * @param {Object} [filters]
 * @param {string} [filters.model] - Filter by model
 * @param {string} [filters.task_type] - Filter by task type
 * @returns {Promise<Array>} Tuning history
 */
async function queryModelTuning(filters = {}) {
  const { model, task_type } = filters;

  let query = 'SELECT * FROM monitoring.model_tuning WHERE 1=1';
  const params = [];

  if (model) {
    params.push(model);
    query += ` AND model = $${params.length}`;
  }

  if (task_type) {
    params.push(task_type);
    query += ` AND task_type = $${params.length}`;
  }

  query += ' ORDER BY updated_at DESC';

  try {
    const result = await pool.query(query, params);
    return result.rows.map(row => {
      // Helper to safely parse JSONB fields
      const parseJsonb = (field) => {
        if (!field) return null;
        if (typeof field === 'object') return field;
        try {
          return JSON.parse(field);
        } catch {
          return field;
        }
      };

      return {
        ...row,
        optimal_params: parseJsonb(row.optimal_params),
        quality_trend: parseJsonb(row.quality_trend),
        cost_trend: parseJsonb(row.cost_trend)
      };
    });
  } catch (err) {
    console.error('Failed to query model tuning:', err.message);
    return [];
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Diversity violations
  recordDiversityViolation,
  queryDiversityViolations,
  calculateDiversityEntropy,

  // Procedural rules
  recordProceduralRule,
  queryProceduralRules,

  // Execution log
  logExecution,
  queryExecutionLog,

  // Model tuning
  recordModelTuning,
  queryModelTuning,

  // Pool access for custom queries
  pool
};
