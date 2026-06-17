/**
 * PostgreSQL Adapter for Learning System
 * Drop-in replacement for SQLite database access
 *
 * Migrates all learning, monitoring, and cost tracking to PostgreSQL
 */

const { Client, Pool } = require('pg');

// Connection pool (reuse connections)
// Use Unix socket for peer authentication (no password needed)
const pool = new Pool({
  host: '/var/run/postgresql', // Unix socket directory
  database: 'learning',
  user: process.env.USER,
  max: 10,
  idleTimeoutMillis: 30000,
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
      'SELECT * FROM learning.strategy_performance WHERE strategy = $1',
      [strategy]
    );
  }

  async updateStrategy(strategy, data) {
    const { successes, failures, alpha, beta, total_reward, avg_reward } = data;
    await this.db.run(
      `INSERT INTO learning.strategy_performance
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
      'SELECT * FROM learning.strategy_performance ORDER BY avg_reward DESC'
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
      const successes = existing.successes + (success ? 1 : 0);
      const failures = existing.failures + (success ? 0 : 1);
      const alpha = 1 + successes;  // Uniform prior + successes
      const beta = 1 + failures;    // Uniform prior + failures
      const total_reward = existing.total_reward + reward;
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

    await this.db.run(
      `INSERT INTO monitoring.execution_summary
       (timestamp, model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome, metadata)
       VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
      [normalizedModel, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, normalizedOutcome, metadata ? JSON.stringify(metadata) : null]
    );
  }

  async getExecutionStats(model, workflow = null) {
    if (workflow) {
      return await this.db.all(
        `SELECT * FROM monitoring.execution_summary
         WHERE model = $1 AND workflow = $2
         ORDER BY timestamp DESC LIMIT 100`,
        [model, workflow]
      );
    } else {
      return await this.db.all(
        `SELECT * FROM monitoring.execution_summary
         WHERE model = $1
         ORDER BY timestamp DESC LIMIT 100`,
        [model]
      );
    }
  }

  async getRecentExecutions(limit = 100) {
    return await this.db.all(
      `SELECT * FROM monitoring.execution_summary
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
        FROM monitoring.execution_summary
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
      `INSERT INTO costs.entries (timestamp, model, input_tokens, output_tokens, total_cost)
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
       FROM costs.entries
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
       FROM costs.entries
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
      `SELECT SUM(total_cost)::float as total_cost FROM costs.entries
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
      `INSERT INTO learning.experiences
       (problem_type, problem_hash, context, embedding, strategy, success, reward, novelty_score, importance)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [problem_type, problem_hash, JSON.stringify(context), embedding, strategy, success, reward, novelty_score, importance]
    );
  }

  async findSimilar(embedding, limit = 10, filters = {}) {
    let sql = `SELECT *, embedding <=> $1::vector as distance
               FROM learning.experiences
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
      `SELECT * FROM learning.experiences ORDER BY timestamp DESC LIMIT $1`,
      [limit]
    );
  }
}

// Singleton instances
let _db = null;
let _strategyPerf = null;
let _execMonitor = null;
let _costTracker = null;
let _experienceMemory = null;

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

module.exports = {
  LearningDB,
  StrategyPerformance,
  ExecutionMonitor,
  CostTracker,
  ExperienceMemory,
  getDB,
  getStrategyPerformance,
  getExecutionMonitor,
  getCostTracker,
  getExperienceMemory,
  pool,
  OUTCOMES,  // Export standardized outcome values for consistency across layers
};
