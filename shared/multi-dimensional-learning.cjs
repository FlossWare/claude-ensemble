/**
 * Multi-Dimensional Learning System
 *
 * Implements Thompson Sampling across multiple dimensions:
 * - capability (code_generation, research, analysis, etc.)
 * - task_type (bug_fix, new_feature, refactoring, etc.)
 * - strategy (model selection, tool usage, decomposition, etc.)
 *
 * Enables intelligent routing of work based on learned performance across
 * (capability, task_type, strategy) tuples.
 *
 * Architecture:
 * - PostgreSQL: Strategy performance tracking (Thompson Sampling bandits)
 * - pgvector: Experience embeddings for similarity-based learning
 * - In-memory: Fast bandit state cache for real-time decisions
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');
const crypto = require('crypto');

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
 * In-memory cache for bandit states
 * Structure:
 * {
 *   "capability|task_type|strategy": {
 *     alpha: number,
 *     beta: number,
 *     successes: number,
 *     failures: number,
 *     total_reward: number,
 *     last_updated: Date,
 *     loaded: boolean
 *   },
 *   ...
 * }
 */
const banditCache = {};
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minute cache

/**
 * Create a cache key from dimensions
 * @param {string} capability
 * @param {string} taskType
 * @param {string} strategy
 * @returns {string}
 */
function makeCacheKey(capability, taskType, strategy) {
  return `${capability}|${taskType}|${strategy}`;
}

/**
 * Generate a Thompson sample from Beta distribution
 * Using numerical approximation for Beta(alpha, beta)
 * @param {number} alpha
 * @param {number} beta
 * @returns {number} Sample in [0, 1]
 */
function sampleBeta(alpha, beta) {
  // Simplified Beta sampling using ratio of Gammas (numerical approximation)
  // For production, use dedicated library or Box-Muller approximation
  const x = alpha / (alpha + beta);
  const variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1));
  const stddev = Math.sqrt(variance);

  // Add normally distributed noise (Box-Muller)
  const u1 = Math.random();
  const u2 = Math.random();
  const z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);

  const sample = x + z * stddev;
  return Math.max(0, Math.min(1, sample)); // Clamp to [0, 1]
}

/**
 * Load bandit state from database or cache
 * @private
 * @param {string} capability
 * @param {string} taskType
 * @param {string} strategy
 * @returns {Promise<{alpha: number, beta: number, successes: number, failures: number, total_reward: number}>}
 */
async function _loadBanditState(capability, taskType, strategy) {
  const key = makeCacheKey(capability, taskType, strategy);

  // Check cache
  if (banditCache[key]) {
    const cached = banditCache[key];
    if (Date.now() - cached.last_updated < CACHE_TTL_MS) {
      return cached;
    }
  }

  try {
    const result = await pool.query(
      `SELECT alpha, beta, successes, failures, total_reward
       FROM learning.strategy_performance_multi
       WHERE capability = $1
         AND task_type = $2
         AND strategy = $3`,
      [capability, taskType, strategy]
    );

    let state;
    if (result.rows.length > 0) {
      const row = result.rows[0];
      // Convert NUMERIC strings to numbers
      state = {
        alpha: parseFloat(row.alpha),
        beta: parseFloat(row.beta),
        successes: parseInt(row.successes, 10),
        failures: parseInt(row.failures, 10),
        total_reward: parseFloat(row.total_reward)
      };
    } else {
      // Initialize new bandit with weak priors
      // Beta(1, 1) = uniform, then update with initial belief
      state = {
        alpha: 1,
        beta: 1,
        successes: 0,
        failures: 0,
        total_reward: 0
      };
    }

    // Cache with timestamp
    banditCache[key] = {
      ...state,
      last_updated: Date.now(),
      loaded: true
    };

    return state;
  } catch (error) {
    console.error('Error loading bandit state:', error);
    // Return default uniform distribution
    return {
      alpha: 1,
      beta: 1,
      successes: 0,
      failures: 0,
      total_reward: 0
    };
  }
}

/**
 * Select best strategy using Thompson Sampling
 *
 * Runs Thompson Sampling across multiple strategies for a (capability, task_type) pair.
 * For each strategy:
 *   1. Sample from Beta(alpha, beta) distribution
 *   2. Return strategy with highest sample (exploration + exploitation)
 *
 * @param {string} capability - Capability type (e.g., 'code_generation')
 * @param {string} taskType - Task type (e.g., 'bug_fix')
 * @param {Array<string>} [candidates] - Candidate strategies to consider
 *                                        If omitted, loads all known strategies
 * @returns {Promise<{strategy: string, alpha: number, beta: number, expected_reward: number}>}
 *          Selected strategy with its bandit parameters
 *
 * @example
 *   const choice = await selectStrategy('code_generation', 'bug_fix', ['model-opus', 'model-sonnet', 'model-haiku']);
 *   console.log(choice.strategy); // 'model-opus'
 *   console.log(choice.expected_reward); // 0.85
 */
async function selectStrategy(capability, taskType, candidates = null) {
  try {
    // Load all candidates
    let strategies;

    if (candidates && candidates.length > 0) {
      strategies = candidates;
    } else {
      // Query database for known strategies
      const result = await pool.query(
        `SELECT DISTINCT strategy
         FROM learning.strategy_performance_multi
         WHERE capability = $1
           AND task_type = $2
         ORDER BY strategy`,
        [capability, taskType]
      );
      strategies = result.rows.map(r => r.strategy);

      // If no strategies found, use a default
      if (strategies.length === 0) {
        strategies = ['default'];
      }
    }

    // Thompson Sampling: sample each strategy
    const samples = [];
    for (const strategy of strategies) {
      const state = await _loadBanditState(capability, taskType, strategy);
      const sample = sampleBeta(state.alpha, state.beta);
      const expectedReward = state.alpha / (state.alpha + state.beta);

      samples.push({
        strategy,
        sample,
        alpha: state.alpha,
        beta: state.beta,
        expected_reward: expectedReward,
        successes: state.successes,
        failures: state.failures,
        total_reward: state.total_reward
      });
    }

    // Select strategy with highest sample (Thompson Sampling)
    const selected = samples.reduce((best, current) =>
      current.sample > best.sample ? current : best
    );

    return {
      strategy: selected.strategy,
      alpha: selected.alpha,
      beta: selected.beta,
      expected_reward: selected.expected_reward,
      successes: selected.successes,
      failures: selected.failures,
      all_candidates: samples
    };
  } catch (error) {
    console.error('selectStrategy error:', error);
    throw error;
  }
}

/**
 * Update strategy performance based on execution result
 *
 * Updates Beta distribution parameters using Bayesian conjugate update:
 *   - alpha += success ? 1 : 0
 *   - beta += success ? 0 : 1
 *   - total_reward += reward
 *
 * @param {string} capability - Capability type
 * @param {string} taskType - Task type
 * @param {string} strategy - Strategy used
 * @param {object} result - Execution result
 * @param {number} result.reward - Numeric reward (0-1)
 * @param {boolean} [result.success] - Whether execution succeeded (default: result.reward > 0.5)
 * @param {object} [result.metadata] - Additional metadata to store
 * @returns {Promise<{alpha: number, beta: number, total_reward: number}>}
 *          Updated bandit parameters
 *
 * @example
 *   const updated = await updateStrategyBandit(
 *     'code_generation',
 *     'bug_fix',
 *     'model-opus',
 *     { reward: 0.92, success: true }
 *   );
 *   console.log(updated.alpha); // 2 (was 1)
 */
async function updateStrategyBandit(capability, taskType, strategy, result) {
  try {
    const success = result.success !== undefined ? result.success : result.reward > 0.5;
    const reward = Math.max(0, Math.min(1, result.reward)); // Clamp to [0, 1]

    // Load current state
    const state = await _loadBanditState(capability, taskType, strategy);

    // Bayesian conjugate update for Beta-Bernoulli
    const newAlpha = state.alpha + (success ? 1 : 0);
    const newBeta = state.beta + (success ? 0 : 1);
    const newTotalReward = state.total_reward + reward;
    const newSuccesses = state.successes + (success ? 1 : 0);
    const newFailures = state.failures + (success ? 0 : 1);

    // Update database
    await pool.query(
      `INSERT INTO learning.strategy_performance_multi
       (capability, task_type, strategy, alpha, beta, successes, failures, total_reward)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT (capability, task_type, strategy)
       DO UPDATE SET
         alpha = $4,
         beta = $5,
         successes = $6,
         failures = $7,
         total_reward = $8,
         updated_at = NOW()`,
      [capability, taskType, strategy, newAlpha, newBeta, newSuccesses, newFailures, newTotalReward]
    );

    // Update cache
    const key = makeCacheKey(capability, taskType, strategy);
    banditCache[key] = {
      alpha: newAlpha,
      beta: newBeta,
      successes: newSuccesses,
      failures: newFailures,
      total_reward: newTotalReward,
      last_updated: Date.now(),
      loaded: true
    };

    return {
      alpha: newAlpha,
      beta: newBeta,
      total_reward: newTotalReward,
      success,
      reward
    };
  } catch (error) {
    console.error('updateStrategyBandit error:', error);
    throw error;
  }
}

/**
 * Get performance summary for a (capability, task_type) pair
 *
 * Returns aggregated statistics across all strategies:
 * - Total executions and success rate
 * - Per-strategy breakdown
 * - Confidence estimates
 *
 * @param {string} capability
 * @param {string} taskType
 * @returns {Promise<{capability: string, task_type: string, total_executions: number, total_successes: number, success_rate: number, strategies: Array}>}
 *
 * @example
 *   const summary = await getPerformanceSummary('code_generation', 'bug_fix');
 *   console.log(summary.success_rate); // 0.87
 *   console.log(summary.strategies[0]); // { strategy: 'model-opus', successes: 25, failures: 3, ... }
 */
async function getPerformanceSummary(capability, taskType) {
  try {
    const result = await pool.query(
      `SELECT
         capability,
         task_type,
         strategy,
         alpha,
         beta,
         successes,
         failures,
         total_reward,
         ROUND((100.0 * successes::float / (successes + failures))::numeric, 1) as success_rate,
         ROUND((alpha::float / (alpha + beta))::numeric, 3) as expected_reward,
         updated_at
       FROM learning.strategy_performance_multi
       WHERE capability = $1
         AND task_type = $2
       ORDER BY alpha / (alpha + beta) DESC`,
      [capability, taskType]
    );

    const strategies = result.rows.map(s => ({
      ...s,
      alpha: parseFloat(s.alpha),
      beta: parseFloat(s.beta),
      total_reward: parseFloat(s.total_reward),
      success_rate: parseFloat(s.success_rate),
      expected_reward: parseFloat(s.expected_reward)
    }));
    const totalExecutions = strategies.reduce((sum, s) => sum + s.successes + s.failures, 0);
    const totalSuccesses = strategies.reduce((sum, s) => sum + s.successes, 0);

    return {
      capability,
      task_type: taskType,
      total_executions: totalExecutions,
      total_successes: totalSuccesses,
      success_rate: totalExecutions > 0 ? Number((totalSuccesses / totalExecutions).toFixed(3)) : 0,
      strategies,
      summary_timestamp: new Date().toISOString()
    };
  } catch (error) {
    console.error('getPerformanceSummary error:', error);
    throw error;
  }
}

/**
 * Store execution experience with (capability, task_type, strategy) context
 *
 * Records learning from a workflow execution with full multidimensional context.
 * Stores embeddings for similarity-based retrieval of similar past experiences.
 *
 * @param {object} experience
 * @param {string} experience.capability - What capability was tested
 * @param {string} experience.task_type - What type of task
 * @param {string} experience.strategy - What strategy was used
 * @param {string} experience.task_description - Task that was performed
 * @param {Array<number>} experience.task_embedding - 1024-dim embedding of task
 * @param {number} experience.reward - Performance metric (0-1)
 * @param {number} experience.duration_ms - Execution time
 * @param {number} experience.cost_usd - Execution cost
 * @param {object} [experience.metadata] - Additional context
 * @returns {Promise<{id: number, capability: string, task_type: string, strategy: string}>}
 *
 * @example
 *   const exp = await storeExperience({
 *     capability: 'code_generation',
 *     task_type: 'bug_fix',
 *     strategy: 'model-opus',
 *     task_description: 'Fix null pointer exception in UserService',
 *     task_embedding: [...], // 1024-dim vector
 *     reward: 0.92,
 *     duration_ms: 5000,
 *     cost_usd: 0.05
 *   });
 */
async function storeExperience(experience) {
  try {
    const {
      capability,
      task_type,
      strategy,
      task_description,
      task_embedding,
      reward,
      duration_ms,
      cost_usd,
      metadata = {}
    } = experience;

    // Validate inputs
    if (!capability || !task_type || !strategy || !task_description) {
      throw new Error('Missing required fields: capability, task_type, strategy, task_description');
    }

    // Validate embedding is 1024-dim array
    let embeddingClause = 'NULL';
    if (task_embedding && Array.isArray(task_embedding) && task_embedding.length === 1024) {
      embeddingClause = `'[${task_embedding.join(',')}]'::vector`;
    }

    const result = await pool.query(
      `INSERT INTO learning.experiences
       (capability, task_type, strategy, task_description, task_embedding, reward, duration_ms, cost_usd, metadata)
       VALUES ($1, $2, $3, $4, ${embeddingClause}, $5, $6, $7, $8)
       RETURNING id`,
      [capability, task_type, strategy, task_description, reward, duration_ms, cost_usd, JSON.stringify(metadata)]
    );

    return {
      id: result.rows[0].id,
      capability,
      task_type,
      strategy
    };
  } catch (error) {
    console.error('storeExperience error:', error);
    throw error;
  }
}

/**
 * Find similar past experiences using vector similarity
 *
 * Searches for past experiences with similar task descriptions.
 * Uses cosine similarity on 1024-dim embeddings.
 *
 * @param {string} taskDescription - Task to find similar experiences for
 * @param {Array<number>} taskEmbedding - 1024-dim embedding of task description
 * @param {object} [filters] - Filter results
 * @param {string} [filters.capability] - Filter by capability
 * @param {string} [filters.task_type] - Filter by task type
 * @param {number} [filters.min_reward] - Minimum reward threshold (0-1)
 * @param {number} [filters.limit] - Number of results (default: 10)
 * @returns {Promise<Array>} Similar experiences with similarity scores
 *
 * @example
 *   const similar = await findSimilarExperiences(
 *     'Fix null pointer exception',
 *     embedding,
 *     { capability: 'code_generation', limit: 5 }
 *   );
 */
async function findSimilarExperiences(taskDescription, taskEmbedding, filters = {}) {
  try {
    const {
      capability = null,
      task_type = null,
      min_reward = 0,
      limit = 10
    } = filters;

    let query = `
      SELECT
        id,
        capability,
        task_type,
        strategy,
        task_description,
        reward,
        duration_ms,
        cost_usd,
        created_at,
        1 - (task_embedding <=> $1::vector) as similarity
      FROM learning.experiences
      WHERE reward >= $2
    `;

    const params = [taskEmbedding, min_reward];
    let paramIndex = 3;

    if (capability) {
      query += ` AND capability = $${paramIndex}`;
      params.push(capability);
      paramIndex++;
    }

    if (task_type) {
      query += ` AND task_type = $${paramIndex}`;
      params.push(task_type);
      paramIndex++;
    }

    query += ` ORDER BY similarity DESC LIMIT $${paramIndex}`;
    params.push(limit);

    const result = await pool.query(query, params);
    return result.rows;
  } catch (error) {
    console.error('findSimilarExperiences error:', error);
    throw error;
  }
}

/**
 * Get learning statistics across all dimensions
 *
 * Returns aggregate statistics grouped by capability, task_type, and/or strategy.
 *
 * @param {object} [grouping] - How to group results
 * @param {boolean} [grouping.by_capability] - Group by capability (default: true)
 * @param {boolean} [grouping.by_task_type] - Group by task type (default: true)
 * @param {boolean} [grouping.by_strategy] - Group by strategy (default: false)
 * @returns {Promise<Array>} Statistics grouped as requested
 *
 * @example
 *   const stats = await getLearningStatistics({ by_capability: true, by_task_type: true });
 *   // [
 *   //   { capability: 'code_generation', task_type: 'bug_fix', executions: 48, avg_reward: 0.87, ... },
 *   //   { capability: 'code_generation', task_type: 'refactoring', executions: 12, avg_reward: 0.75, ... }
 *   // ]
 */
async function getLearningStatistics(grouping = {}) {
  try {
    const {
      by_capability = true,
      by_task_type = true,
      by_strategy = false
    } = grouping;

    let selectClause = '';
    let groupClause = '';

    if (by_capability) {
      selectClause += 'capability, ';
      groupClause += 'capability, ';
    }
    if (by_task_type) {
      selectClause += 'task_type, ';
      groupClause += 'task_type, ';
    }
    if (by_strategy) {
      selectClause += 'strategy, ';
      groupClause += 'strategy, ';
    }

    // Remove trailing comma and space
    if (groupClause) {
      groupClause = groupClause.slice(0, -2);
    }

    const query = `
      SELECT
        ${selectClause}
        COUNT(*) as executions,
        SUM(CASE WHEN reward > 0.5 THEN 1 ELSE 0 END) as successes,
        ROUND(AVG(reward)::numeric, 3) as avg_reward,
        ROUND(MAX(reward)::numeric, 3) as max_reward,
        ROUND(MIN(reward)::numeric, 3) as min_reward,
        ROUND(AVG(duration_ms)::numeric, 0) as avg_duration_ms,
        ROUND(AVG(cost_usd)::numeric, 6) as avg_cost_usd
      FROM learning.experiences
      ${groupClause ? 'GROUP BY ' + groupClause : ''}
      ORDER BY executions DESC
    `;

    const result = await pool.query(query);
    // Parse numeric fields
    return result.rows.map(row => ({
      ...row,
      executions: parseInt(row.executions, 10),
      successes: parseInt(row.successes || 0, 10),
      avg_reward: parseFloat(row.avg_reward),
      max_reward: parseFloat(row.max_reward),
      min_reward: parseFloat(row.min_reward),
      avg_duration_ms: parseFloat(row.avg_duration_ms),
      avg_cost_usd: parseFloat(row.avg_cost_usd)
    }));
  } catch (error) {
    console.error('getLearningStatistics error:', error);
    throw error;
  }
}

/**
 * Check database schema readiness
 * @private
 * @returns {Promise<boolean>} True if schema is initialized
 */
async function _checkSchema() {
  try {
    // Check if table exists
    const result = await pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'learning'
        AND table_name = 'strategy_performance_multi'
      );
    `);
    return result.rows[0].exists;
  } catch (error) {
    console.error('Schema check error:', error.message);
    return false;
  }
}

/**
 * Initialize database schema for multi-dimensional learning
 *
 * Creates tables if they don't exist:
 * - strategy_performance_multi: Bandit state for (capability, task_type, strategy)
 * - experiences: Recorded experiences with embeddings
 *
 * @returns {Promise<void>}
 */
async function initializeSchema() {
  try {
    // Check if already initialized
    const exists = await _checkSchema();
    if (exists) {
      console.log('Schema already initialized');
      return;
    }

    console.log('Initializing multi-dimensional learning schema...');

    // Create strategy_performance_multi table
    await pool.query(`
      CREATE TABLE IF NOT EXISTS learning.strategy_performance_multi (
        id SERIAL PRIMARY KEY,
        capability VARCHAR(255) NOT NULL,
        task_type VARCHAR(255) NOT NULL,
        strategy VARCHAR(255) NOT NULL,
        alpha NUMERIC(10, 2) DEFAULT 1.0 CHECK (alpha > 0),
        beta NUMERIC(10, 2) DEFAULT 1.0 CHECK (beta > 0),
        successes INTEGER DEFAULT 0,
        failures INTEGER DEFAULT 0,
        total_reward NUMERIC(10, 4) DEFAULT 0,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

        UNIQUE(capability, task_type, strategy),
        CHECK (successes >= 0 AND failures >= 0)
      );
    `);

    // Create index for fast lookups
    await pool.query(`
      CREATE INDEX IF NOT EXISTS idx_strategy_perf_lookup
      ON learning.strategy_performance_multi(capability, task_type, strategy);
    `);

    // Create experiences table if needed
    await pool.query(`
      CREATE TABLE IF NOT EXISTS learning.experiences (
        id SERIAL PRIMARY KEY,
        capability VARCHAR(255) NOT NULL,
        task_type VARCHAR(255) NOT NULL,
        strategy VARCHAR(255) NOT NULL,
        task_description TEXT NOT NULL,
        task_embedding vector(1024),
        reward NUMERIC(5, 4) CHECK (reward >= 0 AND reward <= 1),
        duration_ms BIGINT,
        cost_usd NUMERIC(10, 6),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

        CHECK (reward >= 0 AND reward <= 1)
      );
    `);

    // Create similarity search index
    await pool.query(`
      CREATE INDEX IF NOT EXISTS idx_experiences_embedding
      ON learning.experiences USING ivfflat (task_embedding vector_cosine_ops)
      WITH (lists = 100);
    `);

    // Create filtered lookup index
    await pool.query(`
      CREATE INDEX IF NOT EXISTS idx_experiences_lookup
      ON learning.experiences(capability, task_type, strategy);
    `);

    console.log('Schema initialized successfully');
  } catch (error) {
    console.error('Error initializing schema:', error);
    throw error;
  }
}

/**
 * Clear cache (useful for testing)
 * @private
 */
function _clearCache() {
  Object.keys(banditCache).forEach(key => delete banditCache[key]);
}

// ============================================================================
// EXPERIMENT INTEGRATION (Issue #267)
// ============================================================================

/**
 * Run A/B experiment comparing two strategies before updating Thompson Sampling
 *
 * Tests baseline vs treatment strategy with statistical significance testing,
 * then promotes the winner if improvement is significant.
 *
 * @param {Object} config
 * @param {string} config.capability - Capability dimension (e.g., 'code_generation')
 * @param {string} config.taskType - Task type dimension (e.g., 'bug_fix')
 * @param {string} config.baselineStrategy - Baseline strategy name
 * @param {string} config.treatmentStrategy - Treatment strategy name
 * @param {Function} config.taskExecutor - async (strategy) => quality (0-1)
 * @param {number} [config.samples=20] - Number of samples per arm
 * @param {number} [config.minImprovementPct=5] - Min improvement % to promote
 * @returns {Promise<Object>} Experiment result with verdict
 *
 * Example:
 *   const result = await experimentStrategy({
 *     capability: 'code_generation',
 *     taskType: 'java_class',
 *     baselineStrategy: 'opus',
 *     treatmentStrategy: 'deepseek-coder-java',
 *     taskExecutor: async (strategy) => {
 *       const quality = await runCodeGenerationTask(strategy);
 *       return quality;
 *     },
 *     samples: 30,
 *     minImprovementPct: 5
 *   });
 *
 *   if (result.verdict === 'keep') {
 *     console.log(`✅ Promoting ${treatmentStrategy}`);
 *   }
 */
async function experimentStrategy(config) {
  const {
    capability,
    taskType,
    baselineStrategy,
    treatmentStrategy,
    taskExecutor,
    samples = 20,
    minImprovementPct = 5
  } = config;

  if (!taskExecutor || typeof taskExecutor !== 'function') {
    throw new Error('taskExecutor must be a function: async (strategy) => quality');
  }

  // Import experiment manager (lazy load to avoid circular deps)
  const { runExperiment } = require('./experiment-manager.cjs');

  const collector = async (strategyName) => {
    const qualities = [];

    for (let i = 0; i < samples; i++) {
      try {
        const quality = await taskExecutor(strategyName);

        if (typeof quality !== 'number' || quality < 0 || quality > 1) {
          console.warn(`Invalid quality score from taskExecutor: ${quality}, using 0`);
          qualities.push(0);
        } else {
          qualities.push(quality);
        }

        // Record experience in learning system (skip if schema not ready)
        try {
          await storeExperience({
            capability,
            task_type: taskType,
            strategy: strategyName,
            task_description: `Experiment sample ${i+1}/${samples}`,
            reward: quality,
            duration_ms: 0,
            metadata: {
              experiment: true,
              baseline: baselineStrategy,
              treatment: treatmentStrategy,
              sample_index: i
            }
          });
        } catch (storeError) {
          // Schema may not be initialized yet - non-fatal for experiments
          if (i === 0) {
            console.warn(`[experimentStrategy] Cannot store experiences: ${storeError.message}`);
            console.warn(`  Run initializeSchema() to enable experience tracking`);
          }
        }

      } catch (error) {
        console.error(`Error executing task with strategy ${strategyName}:`, error.message);
        qualities.push(0);
      }
    }

    return qualities;
  };

  const result = await runExperiment({
    name: `strategy_${capability}_${taskType}_${Date.now()}`,
    hypothesis: `${treatmentStrategy} outperforms ${baselineStrategy} for ${taskType}`,
    metric: 'quality_score',
    baseline: baselineStrategy,
    treatment: treatmentStrategy,
    collector,
    success_criteria: {
      min_improvement_pct: minImprovementPct,
      alpha: 0.05,
      bootstrap_iterations: 1000
    },
    metadata: {
      capability,
      task_type: taskType,
      experiment_type: 'strategy_comparison',
      samples,
      integration: 'multi-dimensional-learning'
    }
  });

  // If treatment wins significantly, update Thompson Sampling priors
  if (result.verdict === 'keep') {
    console.log(`✅ [experimentStrategy] Promoting ${treatmentStrategy}`);
    console.log(`   Improvement: ${result.improvement_pct.toFixed(2)}% (p=${result.p_value.toFixed(4)})`);
    console.log(`   Effect size: ${result.effect_size.toFixed(3)} (Cohen's d)`);

    // Boost treatment strategy priors
    // Alpha boost proportional to improvement (1-10 pseudo-observations)
    const boost = Math.min(10, Math.max(1, result.improvement_pct / 5));
    await updateStrategyBandit(capability, taskType, treatmentStrategy, true, result.treatment_mean, boost);

    console.log(`   Updated Thompson Sampling: +${boost.toFixed(1)} pseudo-successes`);
  } else if (result.verdict === 'remove') {
    console.log(`❌ [experimentStrategy] ${treatmentStrategy} underperforms baseline`);
    console.log(`   Regression: ${result.improvement_pct.toFixed(2)}% (p=${result.p_value.toFixed(4)})`);

    // Penalize treatment strategy
    await updateStrategyBandit(capability, taskType, treatmentStrategy, false, result.treatment_mean, 3);
  } else {
    console.log(`⚠️  [experimentStrategy] Inconclusive: ${result.reason}`);
  }

  return result;
}

// Export public API
module.exports = {
  // Core Thompson Sampling
  selectStrategy,
  updateStrategyBandit,

  // Experience tracking
  storeExperience,
  findSimilarExperiences,

  // Analytics
  getPerformanceSummary,
  getLearningStatistics,

  // Schema management
  initializeSchema,

  // Experiment integration (Issue #267)
  experimentStrategy,

  // Testing utilities
  _loadBanditState,
  _clearCache,
  _checkSchema,

  // Utilities
  makeCacheKey,
  sampleBeta,

  // Connection management
  pool
};
