/**
 * PostgreSQL Adapter for Learning System
 * Drop-in replacement for SQLite database access
 *
 * Migrates all learning, monitoring, and cost tracking to PostgreSQL
 */

const { Client, Pool } = require('pg');

// Connection pool (reuse connections)
// Connect to PostgreSQL (defaults to aio-01:5433, configurable via env vars)
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD, // Optional: use .pgpass if not set
  max: 10,
  idleTimeoutMillis: 30000,
});

// Handle pool errors
pool.on('error', (err) => {
  console.error('PostgreSQL pool error:', err.message);
});

// Standardized outcome values to prevent inconsistency across layers
// CRITICAL: Always use these constants when recording outcomes to prevent
// queries from missing records due to inconsistent casing/naming.
// All code must use OUTCOMES.SUCCESS, OUTCOMES.FAILED, or OUTCOMES.ERROR
// (never 'pass', 'fail', 'failure', 'ERROR', or any other variant)
const OUTCOMES = {
  SUCCESS: 'success',  // Request succeeded
  FAILED: 'failed',    // Request failed (not 'failure')
  ERROR: 'error'       // System error (not 'ERROR')
};

/**
 * Learning System Database Adapter
 * Compatible with old SQLite code
 */
class LearningDB {
  constructor() {
    this.pool = pool;
  }

  /**
   * Execute a query
   * @param {string} sql - SQL query
   * @param {Array} params - Query parameters
   * @returns {Promise<Array>} Query results
   */
  async query(sql, params = []) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(sql, params);
      return result.rows;
    } finally {
      client.release();
    }
  }

  /**
   * Execute a query and return first row
   */
  async get(sql, params = []) {
    const rows = await this.query(sql, params);
    return rows[0] || null;
  }

  /**
   * Execute a query and return all rows
   */
  async all(sql, params = []) {
    return await this.query(sql, params);
  }

  /**
   * Execute an INSERT/UPDATE/DELETE
   */
  async run(sql, params = []) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(sql, params);
      return {
        changes: result.rowCount,
        lastID: result.rows[0]?.id,
      };
    } finally {
      client.release();
    }
  }

  /**
   * Execute a transaction (prevents race conditions)
   * @param {Function} callback - async function that receives a client
   * @returns {Promise<any>} Result from callback
   */
  async transaction(callback) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Close connection pool
   */
  async close() {
    await this.pool.end();
  }
}

/**
 * Strategy Performance (Thompson Sampling Bandit)
 */
class StrategyPerformance {
  constructor(db) {
    this.db = db || new LearningDB();
  }

  async getStrategy(strategy) {
    return await this.db.get(
      'SELECT * FROM workflow.strategy_performance WHERE strategy = $1',
      [strategy]
    );
  }

  async updateStrategy(strategy, data) {
    const { successes, failures, alpha, beta, total_reward, avg_reward } = data;
    await this.db.run(
      `INSERT INTO workflow.strategy_performance
       (strategy, successes, failures, alpha, beta, total_reward, avg_reward, last_updated)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
       ON CONFLICT (strategy) DO UPDATE SET
         successes = EXCLUDED.successes,
         failures = EXCLUDED.failures,
         alpha = EXCLUDED.alpha,
         beta = EXCLUDED.beta,
         total_reward = EXCLUDED.total_reward,
         avg_reward = EXCLUDED.avg_reward,
         last_updated = NOW()`,
      [strategy, successes, failures, alpha, beta, total_reward, avg_reward]
    );
  }

  async getAllStrategies() {
    return await this.db.all(
      'SELECT * FROM workflow.strategy_performance ORDER BY avg_reward DESC'
    );
  }

  /**
   * Get statistics for a strategy (for Thompson Sampling)
   * Returns { alpha, beta, successes, failures, avg_reward }
   */
  async getStats(strategy) {
    return await this.getStrategy(strategy);
  }

  /**
   * Record an outcome and update Thompson Sampling parameters
   * @param {string} strategy - Strategy name
   * @param {boolean} success - Whether the task succeeded
   * @param {number} reward - Reward value (0.0 to 1.0)
   */
  async record(strategy, success, reward) {
    const existing = await this.getStrategy(strategy);

    if (!existing) {
      // New strategy: initialize with uniform prior (alpha=1, beta=1)
      const successes = success ? 1 : 0;
      const failures = success ? 0 : 1;
      const alpha = 1 + successes;  // Uniform prior + successes
      const beta = 1 + failures;    // Uniform prior + failures
      const total_reward = reward;
      const avg_reward = reward;

      await this.updateStrategy(strategy, {
        successes,
        failures,
        alpha,
        beta,
        total_reward,
        avg_reward,
      });
    } else {
      // Update existing strategy
      // IMPORTANT: Parse NUMERIC fields (pg returns them as strings)
      const successes = parseInt(existing.successes) + (success ? 1 : 0);
      const failures = parseInt(existing.failures) + (success ? 0 : 1);
      const alpha = 1 + successes;  // Uniform prior + successes
      const beta = 1 + failures;    // Uniform prior + failures
      const total_reward = parseFloat(existing.total_reward) + parseFloat(reward);
      const trials = successes + failures;
      const avg_reward = total_reward / trials;

      await this.updateStrategy(strategy, {
        successes,
        failures,
        alpha,
        beta,
        total_reward,
        avg_reward,
      });
    }
  }

  /**
   * Select strategy using Thompson Sampling (current default)
   * Samples from Beta(alpha, beta) distribution for each strategy
   * Returns strategy with highest sample
   *
   * @returns {Promise<Object>} Selected strategy with stats
   */
  async selectThompson() {
    // Get all strategies
    const strategies = await this.getAllStrategies();

    if (strategies.length === 0) {
      return null;
    }

    // Thompson Sampling: sample from Beta(alpha, beta) for each strategy
    // Select strategy with highest sample
    let bestStrategy = null;
    let bestSample = -Infinity;

    for (const strategy of strategies) {
      // Beta distribution sampling via Gamma distribution
      // Beta(alpha, beta) = Gamma(alpha, 1) / (Gamma(alpha, 1) + Gamma(beta, 1))
      const sample = this._sampleBeta(parseFloat(strategy.alpha), parseFloat(strategy.beta));

      if (sample > bestSample) {
        bestSample = sample;
        bestStrategy = strategy;
      }
    }

    return bestStrategy;
  }

  /**
   * Select strategy using UCB (Upper Confidence Bound)
   * Adds exploration bonus to prevent getting stuck on local optima
   *
   * Formula: exploitation_score + C * sqrt(ln(total_trials) / trials)
   * Where:
   * - exploitation_score = alpha / (alpha + beta) (success rate)
   * - C = exploration constant (default 2.0)
   * - total_trials = sum of all strategy trials
   * - trials = this strategy's trial count
   *
   * @param {number} explorationConstant - Exploration constant C (default 2.0)
   * @returns {Promise<Object>} Selected strategy with UCB score
   */
  async selectUCB(explorationConstant = 2.0) {
    const sql = `
      WITH totals AS (
        SELECT COALESCE(SUM(alpha + beta - 2), 0) as total_trials
        FROM workflow.strategy_performance
      )
      SELECT
        sp.strategy,
        sp.alpha,
        sp.beta,
        sp.successes,
        sp.failures,
        sp.total_reward,
        sp.avg_reward,
        sp.alpha / NULLIF(sp.alpha + sp.beta, 0) as exploitation_score,
        $1 * SQRT(LN(GREATEST(NULLIF(t.total_trials, 0), 1)) / GREATEST(sp.alpha + sp.beta - 2, 1)) as exploration_bonus,
        (sp.alpha / NULLIF(sp.alpha + sp.beta, 0)) +
        ($1 * SQRT(LN(GREATEST(NULLIF(t.total_trials, 0), 1)) / GREATEST(sp.alpha + sp.beta - 2, 1))) as ucb_score
      FROM workflow.strategy_performance sp
      CROSS JOIN totals t
      WHERE sp.alpha + sp.beta > 2
      ORDER BY ucb_score DESC NULLS LAST
      LIMIT 1
    `;

    const result = await this.db.query(sql, [explorationConstant]);

    if (result.length === 0) {
      // No strategies with trials yet - fallback to random selection
      const all = await this.getAllStrategies();
      return all.length > 0 ? all[0] : null;
    }

    const row = result[0];
    return {
      strategy: row.strategy,
      alpha: parseFloat(row.alpha),
      beta: parseFloat(row.beta),
      successes: parseInt(row.successes),
      failures: parseInt(row.failures),
      total_reward: parseFloat(row.total_reward),
      avg_reward: parseFloat(row.avg_reward),
      exploitation_score: parseFloat(row.exploitation_score || 0),
      exploration_bonus: parseFloat(row.exploration_bonus || 0),
      ucb_score: parseFloat(row.ucb_score || 0)
    };
  }

  /**
   * Select strategy using Epsilon-Greedy
   * With probability epsilon: explore (random choice from strategies with ≥minTrials)
   * With probability 1-epsilon: exploit (best known from strategies with ≥minTrials)
   *
   * @param {number} epsilon - Exploration probability (default 0.1 = 10%)
   * @param {number} minTrials - Minimum trials before considering (default 3, prevents wasting exploration on untested strategies)
   * @returns {Promise<Object>} Selected strategy
   */
  async selectEpsilonGreedy(epsilon = 0.1, minTrials = 3) {
    // Validate epsilon
    if (epsilon < 0 || epsilon > 1) {
      throw new Error('epsilon must be between 0 and 1');
    }

    // Validate minTrials
    if (minTrials < 0 || !Number.isInteger(minTrials)) {
      throw new Error('minTrials must be a non-negative integer');
    }

    // Filter strategies by minTrials (applies to both explore AND exploit)
    const trialFilter = `WHERE (alpha + beta - 2) >= $1`;

    if (Math.random() < epsilon) {
      // Explore: Random selection (with min trials filter)
      const sql = `
        SELECT * FROM workflow.strategy_performance
        ${trialFilter}
        ORDER BY RANDOM()
        LIMIT 1
      `;
      const result = await this.db.query(sql, [minTrials]);

      if (result.length === 0) {
        // Fallback to pure exploit if no strategies meet minTrials
        // This prevents exploration from getting stuck when all strategies are untested
        return this.selectEpsilonGreedy(0, minTrials); // Pure exploit (epsilon=0)
      }

      return this._normalizeStrategy(result[0]);
    } else {
      // Exploit: Best average reward (with min trials filter)
      const sql = `
        SELECT * FROM workflow.strategy_performance
        ${trialFilter}
        ORDER BY avg_reward DESC
        LIMIT 1
      `;
      const result = await this.db.query(sql, [minTrials]);

      if (result.length === 0) {
        // Fallback to any strategy if no strategies meet minTrials
        const anySql = `SELECT * FROM workflow.strategy_performance ORDER BY avg_reward DESC LIMIT 1`;
        const anyResult = await this.db.query(anySql);
        return anyResult.length > 0 ? this._normalizeStrategy(anyResult[0]) : null;
      }

      return this._normalizeStrategy(result[0]);
    }
  }

  /**
   * Select strategy using specified method
   * @param {string} method - 'thompson' (default), 'ucb', or 'epsilon-greedy'
   * @param {Object} options - Method-specific options
   * @param {number} options.explorationConstant - UCB exploration constant (default 2.0)
   * @param {number} options.epsilon - Epsilon-greedy exploration probability (default 0.1)
   * @param {number} options.minTrials - Epsilon-greedy minimum trials before exploring (default 3)
   * @returns {Promise<Object>} Selected strategy with metadata
   */
  async select(method = null, options = {}) {
    // Use environment variable if method not specified
    const selectedMethod = method || process.env.EXPLORATION_METHOD || 'thompson';

    switch (selectedMethod.toLowerCase()) {
      case 'thompson':
        return await this.selectThompson();
      case 'ucb':
        return await this.selectUCB(options.explorationConstant || 2.0);
      case 'epsilon-greedy':
      case 'epsilon':
        return await this.selectEpsilonGreedy(options.epsilon || 0.1, options.minTrials || 3);
      default:
        throw new Error(`Unknown exploration method: ${selectedMethod}. Use 'thompson', 'ucb', or 'epsilon-greedy'`);
    }
  }

  /**
   * Sample from Beta distribution using Gamma distribution
   * Beta(alpha, beta) = Gamma(alpha, 1) / (Gamma(alpha, 1) + Gamma(beta, 1))
   *
   * @param {number} alpha - Alpha parameter
   * @param {number} beta - Beta parameter
   * @returns {number} Sample from Beta(alpha, beta)
   */
  _sampleBeta(alpha, beta) {
    const x = this._sampleGamma(alpha, 1);
    const y = this._sampleGamma(beta, 1);
    return x / (x + y);
  }

  /**
   * Sample from Gamma distribution using Marsaglia & Tsang's method
   * @param {number} alpha - Shape parameter
   * @param {number} beta - Scale parameter
   * @returns {number} Sample from Gamma(alpha, beta)
   */
  _sampleGamma(alpha, beta) {
    // Marsaglia & Tsang's Method for alpha >= 1
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
      // For alpha < 1, use Gamma(alpha+1) and scale
      return this._sampleGamma(alpha + 1, beta) * Math.pow(Math.random(), 1/alpha);
    }
  }

  /**
   * Sample from standard normal distribution using Box-Muller transform
   * @returns {number} Sample from N(0, 1)
   */
  _normalSample() {
    const u1 = Math.random();
    const u2 = Math.random();
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  }

  /**
   * Normalize strategy object (ensure numeric types)
   * @param {Object} row - Raw database row
   * @returns {Object} Normalized strategy
   */
  _normalizeStrategy(row) {
    return {
      strategy: row.strategy,
      alpha: parseFloat(row.alpha),
      beta: parseFloat(row.beta),
      successes: parseInt(row.successes),
      failures: parseInt(row.failures),
      total_reward: parseFloat(row.total_reward),
      avg_reward: parseFloat(row.avg_reward)
    };
  }
}

/**
 * Execution Monitoring
 */
class ExecutionMonitor {
  constructor(db) {
    this.db = db || new LearningDB();
  }

  async logExecution(data) {
    const {
      model, workflow, task_type, quality_score,
      input_tokens, output_tokens, cost_usd, duration_ms, outcome
    } = data;

    // FIXED: Validate and normalize outcome values to prevent query mismatches
    // Enforce OUTCOMES constants (success/failed/error) across all layers
    // Common mistakes: 'pass'/'fail' (Layer 3), 'failure' (not 'failed'), 'ERROR' (uppercase)
    let normalizedOutcome = outcome;
    if (outcome && typeof outcome === 'string') {
      const outcomeLower = outcome.toLowerCase();
      if (outcomeLower === 'pass' || outcomeLower === 'success') {
        normalizedOutcome = OUTCOMES.SUCCESS;
      } else if (outcomeLower === 'fail' || outcomeLower === 'failed' || outcomeLower === 'failure') {
        normalizedOutcome = OUTCOMES.FAILED;
      } else if (outcomeLower === 'error') {
        normalizedOutcome = OUTCOMES.ERROR;
      } else {
        // Unknown outcome value - log warning but allow it (for backwards compatibility)
        console.warn(`[postgres-adapter] Unknown outcome value: '${outcome}'. Expected: success, failed, or error. Auto-normalizing to 'failed'.`);
        normalizedOutcome = OUTCOMES.FAILED;
      }
    }

    // FIXED: Prevent comma-separated model values (e.g., 'opus,sonnet,haiku')
    // If model contains commas, it's a multi-model operation (e.g., adversarial verification)
    // Use sentinel value to prevent:
    // 1. Column truncation if model has length constraint
    // 2. Foreign key violations
    // 3. Misleading GROUP BY aggregations
    let normalizedModel = model;
    let metadata = null;

    if (typeof model === 'string' && model.includes(',')) {
      // Multi-model operation detected - use sentinel value
      normalizedModel = 'multi-model-adversarial';
      // Store individual models in metadata for future reference
      metadata = {
        verifier_models: model.split(',').map(m => m.trim()),
        original_value: model
      };
    }

    // Insert into workflow.execution_summary (legacy table)
    await this.db.run(
      `INSERT INTO workflow.execution_summary
       (timestamp, model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome, metadata)
       VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
      [normalizedModel, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, normalizedOutcome, metadata ? JSON.stringify(metadata) : null]
    );
  }

  /**
   * Log detailed execution to monitoring.execution_log
   * This is the comprehensive table for fleet orchestration with full metadata
   *
   * @param {Object} data - Execution log data
   * @param {string} data.model - Model name (worker or arbiter)
   * @param {string} data.model_role - 'worker' or 'arbiter'
   * @param {string} data.workflow - Workflow name
   * @param {string} data.task_type - Task type classification
   * @param {string} data.phase - Current phase name
   * @param {string} data.label - Human-readable label
   * @param {Object} data.parameters - Task parameters (JSON)
   * @param {number} data.quality_score - Quality 0-1
   * @param {number} data.confidence - Confidence 0-1
   * @param {number} data.consensus_score - Consensus score (for workers)
   * @param {boolean} data.was_selected - Selected by arbiter
   * @param {number} data.input_tokens - Input token count
   * @param {number} data.output_tokens - Output token count
   * @param {number} data.cost_usd - Cost in USD
   * @param {number} data.duration_ms - Duration in milliseconds
   * @param {string} data.outcome - 'success', 'failed', or 'error'
   * @param {string} data.outcome_notes - Additional notes
   * @param {string} data.run_id - Workflow run identifier
   * @param {string} data.execution_id - Unique execution identifier
   * @param {string} data.task_description - Task description
   * @param {Array<string>} data.worker_models - Worker models used (for arbiter)
   * @param {string} data.arbiter_model - Arbiter model (for workers)
   * @param {string} data.selected_model - Selected model (for arbiter)
   * @param {string} data.strategy - Strategy used
   * @param {string} data.selection_method - Selection method (static/thompson/contextual_bandit)
   * @returns {Promise<number>} Inserted row ID
   */
  async logExecutionDetailed(data) {
    const {
      model, model_role = 'worker', workflow, task_type, phase, label,
      parameters = {}, quality_score, confidence, consensus_score,
      was_selected = false, input_tokens = 0, output_tokens = 0,
      cost_usd = 0, duration_ms = 0, outcome = 'success', outcome_notes,
      run_id, execution_id, task_description, worker_models = [],
      arbiter_model, selected_model, strategy, selection_method = 'static'
    } = data;

    // Normalize outcome (same logic as logExecution)
    let normalizedOutcome = outcome;
    if (outcome && typeof outcome === 'string') {
      const outcomeLower = outcome.toLowerCase();
      if (outcomeLower === 'pass' || outcomeLower === 'success') {
        normalizedOutcome = 'SUCCESS';
      } else if (outcomeLower === 'fail' || outcomeLower === 'failed' || outcomeLower === 'failure') {
        normalizedOutcome = 'FAILED';
      } else if (outcomeLower === 'error') {
        normalizedOutcome = 'ERROR';
      } else {
        normalizedOutcome = 'FAILED';
      }
    }

    const sql = `
      INSERT INTO monitoring.execution_log (
        model, model_role, workflow, task_type, phase, label,
        parameters, quality_score, confidence, consensus_score, was_selected,
        input_tokens, output_tokens, cost_usd, duration_ms, outcome, outcome_notes,
        run_id, execution_id, task_description, worker_models, arbiter_model,
        selected_model, strategy, selection_method,
        total_input_tokens, total_output_tokens, total_cost_usd
      ) VALUES (
        $1, $2, $3, $4, $5, $6,
        $7, $8, $9, $10, $11,
        $12, $13, $14, $15, $16, $17,
        $18, $19, $20, $21, $22,
        $23, $24, $25,
        $26, $27, $28
      ) RETURNING id
    `;

    const params = [
      model, model_role, workflow, task_type, phase, label,
      JSON.stringify(parameters), quality_score, confidence, consensus_score, was_selected,
      input_tokens, output_tokens, cost_usd, duration_ms, normalizedOutcome, outcome_notes,
      run_id, execution_id, task_description,
      JSON.stringify(worker_models), arbiter_model,
      selected_model, strategy, selection_method,
      input_tokens, output_tokens, cost_usd
    ];

    const result = await this.db.query(sql, params);
    return result[0]?.id;
  }

  async getExecutionStats(model, workflow = null) {
    if (workflow) {
      return await this.db.all(
        `SELECT * FROM workflow.execution_summary
         WHERE model = $1 AND workflow = $2
         ORDER BY timestamp DESC LIMIT 100`,
        [model, workflow]
      );
    } else {
      return await this.db.all(
        `SELECT * FROM workflow.execution_summary
         WHERE model = $1
         ORDER BY timestamp DESC LIMIT 100`,
        [model]
      );
    }
  }

  async getRecentExecutions(limit = 100) {
    return await this.db.all(
      `SELECT * FROM workflow.execution_summary
       ORDER BY timestamp DESC LIMIT $1`,
      [limit]
    );
  }

  /**
   * Get model diversity statistics for last N requests
   * Used for monitoring model distribution and detecting dominance (>70%)
   * Returns percentage distribution of models
   */
  async getModelDiversity(limit = 100) {
    const sql = `
      WITH recent_requests AS (
        SELECT model
        FROM workflow.execution_summary
        WHERE model IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT $1
      )
      SELECT
        model AS metric,
        (COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0))::float AS value
      FROM recent_requests
      GROUP BY model
      ORDER BY value DESC
    `;

    const rows = await this.db.all(sql, [limit]);

    // Ensure value is a JavaScript number (pg returns NUMERIC as string)
    return rows.map(row => ({
      metric: row.metric,
      value: parseFloat(row.value)
    }));
  }

  /**
   * Check if any model dominates (>70% of recent requests)
   * Returns { isDominant: boolean, model: string|null, percentage: number }
   */
  async checkModelDominance(limit = 100, threshold = 70) {
    const distribution = await this.getModelDiversity(limit);

    if (distribution.length === 0) {
      return { isDominant: false, model: null, percentage: 0 };
    }

    const topModel = distribution[0];
    const percentage = parseFloat(topModel.value); // Ensure numeric
    const isDominant = percentage >= threshold;

    return {
      isDominant,
      model: isDominant ? topModel.metric : null,
      percentage: percentage,
      distribution: distribution.map(d => ({
        model: d.metric,
        percentage: parseFloat(d.value) // Ensure numeric
      }))
    };
  }
}

/**
 * Cost Tracking
 */
class CostTracker {
  constructor(db) {
    this.db = db || new LearningDB();
  }

  async logCost(data) {
    const { model, input_tokens, output_tokens, total_cost } = data;

    await this.db.run(
      `INSERT INTO workflow.cost_entries (timestamp, model, input_tokens, output_tokens, total_cost)
       VALUES (NOW(), $1, $2, $3, $4)`,
      [model, input_tokens, output_tokens, total_cost]
    );
  }

  async getDailyCosts(days = 30) {
    const rows = await this.db.query(
      `SELECT DATE(timestamp) as date,
              SUM(total_cost)::float as total_cost,
              SUM(input_tokens)::bigint as input_tokens,
              SUM(output_tokens)::bigint as output_tokens
       FROM workflow.cost_entries
       WHERE timestamp > NOW() - ($1 || ' days')::interval
       GROUP BY DATE(timestamp)
       ORDER BY date DESC`,
      [days]
    );

    // Ensure numeric types (pg may return NUMERIC as string)
    return rows.map(row => ({
      date: row.date,
      total_cost: row.total_cost ? parseFloat(row.total_cost) : 0,
      input_tokens: row.input_tokens ? parseInt(row.input_tokens, 10) : 0,
      output_tokens: row.output_tokens ? parseInt(row.output_tokens, 10) : 0
    }));
  }

  async getModelCosts(days = 30) {
    const rows = await this.db.query(
      `SELECT model,
              SUM(total_cost)::float as total_cost,
              SUM(input_tokens)::bigint as input_tokens,
              SUM(output_tokens)::bigint as output_tokens
       FROM workflow.cost_entries
       WHERE timestamp > NOW() - ($1 || ' days')::interval
       GROUP BY model
       ORDER BY total_cost DESC`,
      [days]
    );

    // Ensure numeric types (pg may return NUMERIC as string)
    return rows.map(row => ({
      model: row.model,
      total_cost: row.total_cost ? parseFloat(row.total_cost) : 0,
      input_tokens: row.input_tokens ? parseInt(row.input_tokens, 10) : 0,
      output_tokens: row.output_tokens ? parseInt(row.output_tokens, 10) : 0
    }));
  }

  async getTotalCost(days = 30) {
    const result = await this.db.get(
      `SELECT SUM(total_cost)::float as total_cost FROM workflow.cost_entries
       WHERE timestamp > NOW() - ($1 || ' days')::interval`,
      [days]
    );
    // Ensure numeric type (pg may return NUMERIC as string)
    return result?.total_cost ? parseFloat(result.total_cost) : 0;
  }
}

/**
 * Experience Memory (Continual Learning)
 */
class ExperienceMemory {
  constructor(db) {
    this.db = db || new LearningDB();
  }

  async addExperience(data) {
    const {
      problem_type, problem_hash, context, embedding,
      strategy, success, reward, novelty_score, importance
    } = data;

    await this.db.run(
      `INSERT INTO workflow.experiences
       (problem_type, problem_hash, context, embedding, strategy, success, reward, novelty_score, importance)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [problem_type, problem_hash, JSON.stringify(context), embedding, strategy, success, reward, novelty_score, importance]
    );
  }

  async findSimilar(embedding, limit = 10, filters = {}) {
    let sql = `SELECT *, embedding <=> $1::vector as distance
               FROM workflow.experiences
               WHERE 1=1`;
    const params = [embedding];
    let paramIdx = 2;

    if (filters.success !== undefined) {
      sql += ` AND success = $${paramIdx}`;
      params.push(filters.success);
      paramIdx++;
    }

    if (filters.min_reward !== undefined) {
      sql += ` AND reward >= $${paramIdx}`;
      params.push(filters.min_reward);
      paramIdx++;
    }

    sql += ` ORDER BY embedding <=> $1::vector LIMIT $${paramIdx}`;
    params.push(limit);

    return await this.db.all(sql, params);
  }

  async getRecentExperiences(limit = 100) {
    return await this.db.all(
      `SELECT * FROM workflow.experiences ORDER BY timestamp DESC LIMIT $1`,
      [limit]
    );
  }
}

/**
 * Workflows Learning (Reaction Tracking + Task Difficulty)
 * Integrates with ai-reaction-tracker to persist model behavior learnings
 */
class WorkflowsLearning {
  constructor(db) {
    this.db = db || new LearningDB();
  }

  /**
   * Record workflow learning
   * @param {Object} data - Learning data
   * @param {number} data.workflow_execution_id - REQUIRED: Integer FK to workflow.executions(id)
   * @param {string} data.learning_type - REQUIRED: 'pattern', 'failure', or 'optimization'
   * @param {string} data.description - REQUIRED: Text description of the learning
   * @param {string} data.actionable_insight - REQUIRED: Actionable insight from the learning
   * @param {number} data.importance - Optional: Importance score (0.0 to 1.0)
   * @param {Array} data.learning_embedding - Optional: 384-dim embedding vector
   * @param {Object} data.metadata - Optional: Additional metadata (stored as JSONB)
   */
  /**
   * Generate 384-dim embedding using sentence-transformers
   * FIXED (#291): Async embedding service with queue fallback
   * @param {string} text - Text to embed
   * @param {Object} options - { async: boolean, timeout: number }
   * @returns {Promise<Array<number>|null>} Embedding vector or null
   */
  async _generateEmbedding(text, options = {}) {
    const { async: useAsync = true, timeout = 5000 } = options;

    if (!text || text.trim().length === 0) {
      return null;
    }

    // Try async embedding service first (non-blocking)
    if (useAsync) {
      try {
        const embedding = await this._asyncEmbeddingService(text, timeout);
        if (embedding) return embedding;
      } catch (error) {
        console.warn('[postgres-adapter] Async embedding failed, falling back to sync:', error.message);
      }
    }

    // Fall back to sync generation (with timeout)
    return this._syncEmbeddingGeneration(text, timeout);
  }

  /**
   * Async embedding service using background worker
   * Uses shared/knowledge-integration.js Python bridge
   */
  async _asyncEmbeddingService(text, timeout) {
    try {
      // Use existing Python bridge for async execution
      const { execFile } = require('child_process');
      const { promisify } = require('util');
      const execFileAsync = promisify(execFile);

      const pythonScript = `
import sys
import json
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
text = sys.stdin.read()
embedding = model.encode(text).tolist()
print(json.dumps(embedding))
`;

      const result = await Promise.race([
        execFileAsync('python3', ['-c', pythonScript], {
          input: text,
          maxBuffer: 10 * 1024 * 1024,
          encoding: 'utf-8'
        }),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), timeout)
        )
      ]);

      return JSON.parse(result.stdout);
    } catch (error) {
      if (error.message === 'Timeout') {
        // Queue for batch processing later
        await this._queueForBatchEmbedding(text);
      }
      return null;
    }
  }

  /**
   * Sync embedding generation (original slow method)
   */
  _syncEmbeddingGeneration(text, timeout) {
    // DISABLED: Model loading still takes >30s
    // Return null for now - embeddings queued for batch backfill
    return null;
  }

  /**
   * Queue text for batch embedding processing
   * Stores in PostgreSQL queue for later batch processing
   */
  async _queueForBatchEmbedding(text) {
    try {
      await this.db.query(`
        INSERT INTO learning.embedding_queue (text, status, queued_at)
        VALUES ($1, 'pending', NOW())
        ON CONFLICT (text) DO NOTHING
      `, [text]);
    } catch (error) {
      // Table might not exist - that's ok, this is optional
      console.debug('[postgres-adapter] Could not queue embedding:', error.message);
    }
  }

  /**
   * Chunk large text into smaller pieces
   * @param {string} text - Text to chunk
   * @param {number} maxChunkSize - Max characters per chunk
   * @param {number} overlap - Character overlap between chunks
   * @returns {Array<string>} Array of text chunks
   */
  _chunkText(text, maxChunkSize = 4000, overlap = 200) {
    if (!text || text.trim().length === 0) {
      return [];
    }
    if (text.length <= maxChunkSize) {
      return [text.trim()];
    }
    // Clamp overlap to prevent infinite loop when overlap >= maxChunkSize
    overlap = Math.min(overlap, maxChunkSize - 1);

    const chunks = [];
    let start = 0;

    while (start < text.length) {
      let end = Math.min(start + maxChunkSize, text.length);

      // Try to break at paragraph or sentence boundary (only if not at end)
      if (end < text.length) {
        const paragraphBreak = text.lastIndexOf('\n\n', end);
        if (paragraphBreak > start + maxChunkSize / 2) {
          end = paragraphBreak + 2;
        } else {
          const sentenceBreak = text.lastIndexOf('. ', end);
          if (sentenceBreak > start + maxChunkSize / 2) {
            end = sentenceBreak + 2;
          }
        }
      }

      const chunk = text.substring(start, end).trim();
      if (chunk.length > 0) {
        chunks.push(chunk);
      }

      // Move to next chunk with overlap, guarantee forward progress
      start = end < text.length ? Math.max(end - overlap, start + 1) : text.length;
    }

    return chunks;
  }

  async recordLearning(data) {
    const {
      workflow_execution_id,
      learning_type,
      description,
      actionable_insight,
      importance = null,
      learning_embedding = null,
      metadata = null
    } = data;

    // Validate required fields
    if (!workflow_execution_id) {
      throw new Error('workflow_execution_id is required (integer FK to workflow.executions)');
    }

    if (!learning_type) {
      throw new Error('learning_type is required (pattern, failure, or optimization)');
    }

    if (!description) {
      throw new Error('description is required');
    }

    if (!actionable_insight) {
      throw new Error('actionable_insight is required');
    }

    // Validate learning_type against CHECK constraint
    const validTypes = ['pattern', 'failure', 'optimization'];
    if (!validTypes.includes(learning_type)) {
      throw new Error(`learning_type must be one of: ${validTypes.join(', ')}`);
    }

    // Validate importance if provided
    if (importance !== null && (importance < 0.0 || importance > 1.0)) {
      throw new Error('importance must be between 0.0 and 1.0');
    }

    const combinedText = description + ' ' + actionable_insight;

    // Generate embedding if not provided (async, non-blocking on failure)
    let embeddingToStore = learning_embedding;
    if (!embeddingToStore) {
      try {
        embeddingToStore = await this._generateEmbedding(combinedText);
      } catch (err) {
        // Don't block storage on embedding failure - store without embedding
        console.warn(`Skipping embedding generation (${err.message})`);
        embeddingToStore = null;
      }
    }

    // Check if chunking needed (>4000 chars)
    if (combinedText.length > 4000) {
      console.log(`Large learning (${combinedText.length} chars), chunking...`);

      console.log(`[DEBUG] Calling _chunkText...`);
      const chunks = this._chunkText(combinedText, 4000, 200);
      console.log(`[DEBUG] Created ${chunks.length} chunks`);

      // Create parent learning first (no embedding, just metadata pointer)
      const parentSql = `
        INSERT INTO workflow.learnings (
          workflow_execution_id,
          learning_type,
          description,
          actionable_insight,
          importance,
          learning_embedding,
          metadata
        ) VALUES ($1, $2, $3, $4, $5, NULL, $6)
        RETURNING id, created_at
      `;

      const parentMetadata = {
        ...(metadata || {}),
        is_parent: true,
        total_chunks: chunks.length,
        original_length: combinedText.length
      };

      // Use a transaction to ensure parent + all chunks are stored atomically
      const client = await this.db.pool.connect();
      let parentId;
      try {
        await client.query('BEGIN');

        const parentResult = await client.query(parentSql, [
          workflow_execution_id,
          learning_type,
          `[CHUNKED ${chunks.length} parts] ${description.substring(0, 200)}...`,
          actionable_insight.substring(0, 200) || 'See chunks',
          importance,
          JSON.stringify(parentMetadata)
        ]);

        parentId = parentResult.rows[0].id;
        console.log(`Created parent learning ID ${parentId}, storing ${chunks.length} chunks...`);

        // Store each chunk with its own embedding (if original had one)
        for (let i = 0; i < chunks.length; i++) {
          const chunkMetadata = {
            ...(metadata || {}),
            chunk_index: i,
            total_chunks: chunks.length,
            parent_learning_id: parentId
          };

          // Use same embedding for all chunks (already in string format from caller)
          await client.query(`
            INSERT INTO workflow.learnings (
              workflow_execution_id,
              learning_type,
              description,
              actionable_insight,
              importance,
              learning_embedding,
              metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
          `, [
            workflow_execution_id,
            learning_type,
            chunks[i],
            '',
            importance,
            embeddingToStore ? JSON.stringify(embeddingToStore) : null,
            JSON.stringify(chunkMetadata)
          ]);

          console.log(`  Chunk ${i + 1}/${chunks.length} stored (${chunks[i].length} chars)`);
        }

        await client.query('COMMIT');
        console.log(`✅ Chunked learning: parent ID ${parentId}, ${chunks.length} chunks`);
        return { id: parentId };
      } catch (error) {
        await client.query('ROLLBACK');
        console.error(`Failed to store chunked learning (rolled back): ${error.message}`);
        throw error;
      } finally {
        client.release();
      }

    } else {
      // Normal single learning
      const sql = `
        INSERT INTO workflow.learnings (
          workflow_execution_id,
          learning_type,
          description,
          actionable_insight,
          importance,
          learning_embedding,
          metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, created_at
      `;

      const result = await this.db.query(sql, [
        workflow_execution_id,
        learning_type,
        description,
        actionable_insight,
        importance,
        embeddingToStore ? JSON.stringify(embeddingToStore) : null,
        metadata ? JSON.stringify(metadata) : null
      ]);

      return result[0];
    }
  }

  /**
   * Query workflow learnings with filters
   */
  async queryLearnings(filters = {}) {
    const {
      workflow_name = null,
      task_type = null,
      task_difficulty = null,
      outcome = null,
      learning_type = null,
      limit = 100
    } = filters;

    let sql = 'SELECT * FROM workflows.learnings WHERE 1=1';
    const params = [];
    let paramIdx = 1;

    if (workflow_name) {
      sql += ` AND workflow_name = $${paramIdx}`;
      params.push(workflow_name);
      paramIdx++;
    }

    if (task_type) {
      sql += ` AND task_type = $${paramIdx}`;
      params.push(task_type);
      paramIdx++;
    }

    if (task_difficulty) {
      sql += ` AND task_difficulty = $${paramIdx}`;
      params.push(task_difficulty);
      paramIdx++;
    }

    if (outcome) {
      sql += ` AND outcome = $${paramIdx}`;
      params.push(outcome);
      paramIdx++;
    }

    if (learning_type) {
      sql += ` AND learning_type = $${paramIdx}`;
      params.push(learning_type);
      paramIdx++;
    }

    sql += ` ORDER BY timestamp DESC LIMIT $${paramIdx}`;
    params.push(limit);

    return await this.db.all(sql, params);
  }

  /**
   * Get task difficulty statistics
   */
  async getTaskDifficultyStats(task_type = null) {
    let sql = 'SELECT * FROM workflows.task_difficulty_stats WHERE 1=1';
    const params = [];

    if (task_type) {
      sql += ' AND task_type = $1';
      params.push(task_type);
    }

    sql += ' ORDER BY task_type, task_difficulty';

    return await this.db.all(sql, params);
  }

  /**
   * Get workflow performance summary
   */
  async getWorkflowPerformance(workflow_name = null) {
    let sql = 'SELECT * FROM workflows.performance_summary WHERE 1=1';
    const params = [];

    if (workflow_name) {
      sql += ' AND workflow_name = $1';
      params.push(workflow_name);
    }

    sql += ' ORDER BY total_runs DESC';

    return await this.db.all(sql, params);
  }

  /**
   * Get learnings for a specific run_id (traceability)
   */
  async getLearningsByRunId(run_id) {
    return await this.db.all(
      'SELECT * FROM workflows.learnings WHERE run_id = $1 ORDER BY timestamp DESC',
      [run_id]
    );
  }

  /**
   * Record workflow execution
   * @param {Object} data - Execution data
   * @param {string} data.workflow_id - REQUIRED: Unique workflow identifier (varchar 64)
   * @param {string} data.workflow_name - REQUIRED: Name of the workflow (varchar 255)
   * @param {string} data.task_description - REQUIRED: Description of the task (text)
   * @param {number} data.total_workers - REQUIRED: Number of workers (integer)
   * @param {number} data.total_duration_ms - REQUIRED: Total duration in milliseconds (bigint)
   * @param {string} data.outcome - REQUIRED: 'success', 'failed', or 'error'
   * @param {Array} data.task_embedding - Optional: 384-dim embedding vector
   * @param {Object} data.metadata - Optional: Additional metadata (stored as JSONB)
   * @returns {Promise<number>} The auto-generated execution id (CRITICAL: needed for recordLearning)
   */
  async recordRun(data) {
    const {
      workflow_id,
      workflow_name,
      task_description,
      total_workers,
      total_duration_ms,
      outcome,
      task_embedding = null,
      metadata = null
    } = data;

    // Validate required fields
    if (!workflow_id) {
      throw new Error('workflow_id is required (unique identifier for this execution)');
    }

    if (!workflow_name) {
      throw new Error('workflow_name is required');
    }

    if (!task_description) {
      throw new Error('task_description is required');
    }

    if (total_workers === null || total_workers === undefined) {
      throw new Error('total_workers is required (integer)');
    }

    if (total_duration_ms === null || total_duration_ms === undefined) {
      throw new Error('total_duration_ms is required (bigint)');
    }

    if (!outcome) {
      throw new Error('outcome is required (success, failed, or error)');
    }

    // Validate outcome against CHECK constraint
    const validOutcomes = ['success', 'failed', 'error'];
    if (!validOutcomes.includes(outcome)) {
      throw new Error(`outcome must be one of: ${validOutcomes.join(', ')}`);
    }

    const sql = `
      INSERT INTO workflow.executions (
        workflow_id,
        workflow_name,
        task_description,
        total_workers,
        total_duration_ms,
        outcome,
        task_embedding,
        metadata
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      RETURNING id, created_at
    `;

    const result = await this.db.query(sql, [
      workflow_id,
      workflow_name,
      task_description,
      total_workers,
      total_duration_ms,
      outcome,
      task_embedding,
      metadata ? JSON.stringify(metadata) : null
    ]);

    // CRITICAL: Return the auto-generated id (needed for recordLearning FK)
    return result[0].id;
  }
}

// Singleton instances
let _db = null;
let _strategyPerf = null;
let _execMonitor = null;
let _costTracker = null;
let _experienceMemory = null;
let _workflowsLearning = null;

/**
 * Get singleton database instance
 */
function getDB() {
  if (!_db) _db = new LearningDB();
  return _db;
}

/**
 * Get strategy performance tracker
 */
function getStrategyPerformance() {
  if (!_strategyPerf) _strategyPerf = new StrategyPerformance(getDB());
  return _strategyPerf;
}

/**
 * Get execution monitor
 */
function getExecutionMonitor() {
  if (!_execMonitor) _execMonitor = new ExecutionMonitor(getDB());
  return _execMonitor;
}

/**
 * Get cost tracker
 */
function getCostTracker() {
  if (!_costTracker) _costTracker = new CostTracker(getDB());
  return _costTracker;
}

/**
 * Get experience memory
 */
function getExperienceMemory() {
  if (!_experienceMemory) _experienceMemory = new ExperienceMemory(getDB());
  return _experienceMemory;
}

/**
 * Get workflows learning tracker
 */
function getWorkflowsLearning() {
  if (!_workflowsLearning) _workflowsLearning = new WorkflowsLearning(getDB());
  return _workflowsLearning;
}

module.exports = {
  LearningDB,
  StrategyPerformance,
  ExecutionMonitor,
  CostTracker,
  ExperienceMemory,
  WorkflowsLearning,
  getDB,
  getStrategyPerformance,
  getExecutionMonitor,
  getCostTracker,
  getExperienceMemory,
  getWorkflowsLearning,
  pool,
  OUTCOMES,  // Export standardized outcome values for consistency across layers
};
