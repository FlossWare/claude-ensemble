/**
 * PostgreSQL Adapter for Learning System
 * Drop-in replacement for SQLite database access
 *
 * Migrates all learning, monitoring, and cost tracking to PostgreSQL
 */

const { Client, Pool } = require('pg');

// Connection pool (reuse connections)
const pool = new Pool({
  host: 'localhost',
  database: 'learning',
  user: process.env.USER,
  // No password needed for local connection
  max: 10,
  idleTimeoutMillis: 30000,
});

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

    await this.db.run(
      `INSERT INTO monitoring.execution_summary
       (timestamp, model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome)
       VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome]
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
    return await this.db.all(
      `SELECT DATE(timestamp) as date, SUM(total_cost) as total_cost, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
       FROM costs.entries
       WHERE timestamp > NOW() - INTERVAL '${days} days'
       GROUP BY DATE(timestamp)
       ORDER BY date DESC`
    );
  }

  async getModelCosts(days = 30) {
    return await this.db.all(
      `SELECT model, SUM(total_cost) as total_cost, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
       FROM costs.entries
       WHERE timestamp > NOW() - INTERVAL '${days} days'
       GROUP BY model
       ORDER BY total_cost DESC`
    );
  }

  async getTotalCost(days = 30) {
    const result = await this.db.get(
      `SELECT SUM(total_cost) as total_cost FROM costs.entries
       WHERE timestamp > NOW() - INTERVAL '${days} days'`
    );
    return result?.total_cost || 0;
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
};
