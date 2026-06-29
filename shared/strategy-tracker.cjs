/**
 * Strategy Tracker (Phase 2 - Extended)
 *
 * Multi-dimensional strategy tracking for fleet orchestration
 * Extends learning.strategy_performance with:
 * - Task type tracking (code-review, general, research, etc.)
 * - Prompt template performance (chain-of-thought, few-shot, zero-shot)
 * - Orchestration pattern performance (parallel, sequential, hierarchical, debate)
 * - Verification method performance (multi-ai-consensus, adversarial, self-critique)
 * - Reasoning sequence tracking (for complex multi-step tasks)
 * - Performance tier classification (HIGH_PERFORMER, MODERATE_PERFORMER, etc.)
 *
 * Created: 2026-06-28
 * Phase 2 Extensions: Task type dimensions, performance tiers, comparative analysis
 */

const { Pool } = require('pg');

// Connection pool
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 20,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('[strategy-tracker] PostgreSQL pool error:', err.message);
});

/**
 * Record the result of a strategy execution.
 * Updates Thompson Sampling parameters (alpha, beta) and average reward.
 *
 * @param {object} strategy - Strategy configuration
 * @param {string} strategy.name - Unique strategy name
 * @param {string} [strategy.promptTemplateId] - Prompt template identifier
 * @param {string} [strategy.orchestrationPattern] - Orchestration pattern
 * @param {string} [strategy.verificationMethod] - Verification method
 * @param {string} [strategy.reasoningSequence] - Reasoning sequence description
 * @param {string} taskType - Type of task (for context)
 * @param {object} outcome - Execution outcome
 * @param {boolean} outcome.success - Whether execution succeeded
 * @param {number} outcome.reward - Reward score (0-1)
 * @returns {Promise<{id: number, alpha: number, beta: number, avgReward: number}>}
 *
 * @example
 *   const result = await recordStrategyResult({
 *     name: 'chain-of-thought-parallel-consensus',
 *     promptTemplateId: 'chain-of-thought',
 *     orchestrationPattern: 'parallel',
 *     verificationMethod: 'multi-ai-consensus'
 *   }, 'code-review', { success: true, reward: 0.85 });
 */
/**
 * PHASE 2: Record strategy result with task type dimension
 * Extends strategy tracking to include task_type as a key dimension
 */
async function recordStrategyResult(strategy, taskType, outcome) {
  const { name, promptTemplateId, orchestrationPattern, verificationMethod, reasoningSequence } = strategy;
  const { success, reward, cost = 0, duration_ms = 0 } = outcome;

  if (!name) {
    throw new Error('strategy.name is required');
  }

  if (!taskType) {
    throw new Error('taskType is required');
  }

  if (typeof success !== 'boolean') {
    throw new Error('outcome.success must be boolean');
  }

  if (typeof reward !== 'number' || reward < 0 || reward > 1) {
    throw new Error('outcome.reward must be a number between 0 and 1');
  }

  const successes = success ? 1 : 0;
  const failures = success ? 0 : 1;

  try {
    const result = await pool.query(`
      INSERT INTO learning.strategy_performance
        (strategy, task_type, prompt_template_id, orchestration_pattern, verification_method,
         reasoning_sequence, successes, failures, alpha, beta, total_reward, avg_reward, cost_usd, duration_ms, last_updated)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW())
      ON CONFLICT (strategy, task_type) DO UPDATE SET
        prompt_template_id = COALESCE(EXCLUDED.prompt_template_id, learning.strategy_performance.prompt_template_id),
        orchestration_pattern = COALESCE(EXCLUDED.orchestration_pattern, learning.strategy_performance.orchestration_pattern),
        verification_method = COALESCE(EXCLUDED.verification_method, learning.strategy_performance.verification_method),
        reasoning_sequence = COALESCE(EXCLUDED.reasoning_sequence, learning.strategy_performance.reasoning_sequence),
        successes = learning.strategy_performance.successes + EXCLUDED.successes,
        failures = learning.strategy_performance.failures + EXCLUDED.failures,
        alpha = learning.strategy_performance.alpha + CASE WHEN EXCLUDED.successes = 1 THEN 1 ELSE 0 END,
        beta = learning.strategy_performance.beta + CASE WHEN EXCLUDED.failures = 1 THEN 1 ELSE 0 END,
        total_reward = learning.strategy_performance.total_reward + EXCLUDED.total_reward,
        avg_reward = (learning.strategy_performance.total_reward + EXCLUDED.total_reward) /
                     NULLIF(learning.strategy_performance.successes + learning.strategy_performance.failures +
                            EXCLUDED.successes + EXCLUDED.failures, 0),
        cost_usd = learning.strategy_performance.cost_usd + EXCLUDED.cost_usd,
        duration_ms = learning.strategy_performance.duration_ms + EXCLUDED.duration_ms,
        last_updated = NOW()
      RETURNING id, alpha, beta, avg_reward, successes, failures
    `, [
      name,
      taskType,
      promptTemplateId || null,
      orchestrationPattern || null,
      verificationMethod || null,
      reasoningSequence || null,
      successes,
      failures,
      1.0 + successes,  // alpha = 1 + successes (Beta prior)
      1.0 + failures,   // beta = 1 + failures
      reward,
      reward,
      cost,
      duration_ms
    ]);

    return {
      id: result.rows[0].id,
      alpha: parseFloat(result.rows[0].alpha),
      beta: parseFloat(result.rows[0].beta),
      avgReward: parseFloat(result.rows[0].avg_reward),
      totalExecutions: parseInt(result.rows[0].successes) + parseInt(result.rows[0].failures)
    };
  } catch (error) {
    console.error('[strategy-tracker] Failed to record strategy result:', error.message);
    throw error;
  }
}

/**
 * PHASE 2: Get performance metrics for a strategy configuration
 * Now includes task_type as primary dimension
 *
 * @param {object} strategyDimensions - Strategy dimensions to match
 * @param {string} strategyDimensions.taskType - Task type (REQUIRED)
 * @param {string} [strategyDimensions.promptTemplateId] - Prompt template
 * @param {string} [strategyDimensions.orchestrationPattern] - Orchestration pattern
 * @param {string} [strategyDimensions.verificationMethod] - Verification method
 * @param {object} [options] - Query options
 * @param {number} [options.minExecutions=3] - Minimum executions to include
 * @param {number} [options.limit=20] - Max results
 * @returns {Promise<Array>} Strategy performance records
 *
 * @example
 *   const strategies = await getStrategyPerformance({
 *     taskType: 'code-review',
 *     orchestrationPattern: 'parallel'
 *   }, { minExecutions: 5 });
 */
async function getStrategyPerformance(strategyDimensions, options = {}) {
  const {
    taskType,
    promptTemplateId,
    orchestrationPattern,
    verificationMethod
  } = strategyDimensions;

  const { minExecutions = 3, limit = 20 } = options;

  if (!taskType) {
    throw new Error('taskType is required in strategyDimensions');
  }

  // Build dynamic WHERE clause
  const conditions = [`task_type = $1`];
  const params = [taskType];
  let paramIndex = 2;

  if (promptTemplateId) {
    conditions.push(`prompt_template_id = $${paramIndex++}`);
    params.push(promptTemplateId);
  }

  if (orchestrationPattern) {
    conditions.push(`orchestration_pattern = $${paramIndex++}`);
    params.push(orchestrationPattern);
  }

  if (verificationMethod) {
    conditions.push(`verification_method = $${paramIndex++}`);
    params.push(verificationMethod);
  }

  conditions.push(`(successes + failures) >= $${paramIndex++}`);
  params.push(minExecutions);

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  try {
    params.push(limit);
    const result = await pool.query(`
      SELECT
        strategy,
        task_type,
        prompt_template_id,
        orchestration_pattern,
        verification_method,
        reasoning_sequence,
        successes,
        failures,
        successes + failures as total_executions,
        ROUND(successes::NUMERIC / NULLIF(successes + failures, 0), 4) as success_rate,
        avg_reward,
        alpha,
        beta,
        cost_usd,
        duration_ms,
        last_updated,
        CASE
          WHEN successes + failures < 5 THEN 'INSUFFICIENT_DATA'
          WHEN avg_reward >= 0.8 THEN 'HIGH_PERFORMER'
          WHEN avg_reward >= 0.6 THEN 'MODERATE_PERFORMER'
          WHEN avg_reward >= 0.4 THEN 'LOW_PERFORMER'
          ELSE 'POOR_PERFORMER'
        END as performance_tier
      FROM learning.strategy_performance
      ${whereClause}
      ORDER BY avg_reward DESC, successes + failures DESC
      LIMIT $${paramIndex}
    `, params);

    return result.rows.map(row => ({
      strategy: row.strategy,
      taskType: row.task_type,
      promptTemplateId: row.prompt_template_id,
      orchestrationPattern: row.orchestration_pattern,
      verificationMethod: row.verification_method,
      reasoningSequence: row.reasoning_sequence,
      successes: parseInt(row.successes),
      failures: parseInt(row.failures),
      totalExecutions: parseInt(row.total_executions),
      successRate: parseFloat(row.success_rate),
      avgReward: parseFloat(row.avg_reward),
      alpha: parseFloat(row.alpha),
      beta: parseFloat(row.beta),
      costUsd: parseFloat(row.cost_usd),
      durationMs: parseInt(row.duration_ms),
      performanceTier: row.performance_tier,
      lastUpdated: row.last_updated
    }));
  } catch (error) {
    console.error('[strategy-tracker] Failed to get strategy performance:', error.message);
    throw error;
  }
}

/**
 * PHASE 2: Get the best strategy for a task type with optional constraints
 * Uses Thompson Sampling (Beta distribution sampling) for exploration/exploitation
 *
 * @param {string} taskType - Task type (REQUIRED)
 * @param {object} [constraints] - Optional constraints
 * @param {string} [constraints.promptTemplateId] - Required prompt template
 * @param {string} [constraints.orchestrationPattern] - Required orchestration pattern
 * @param {string} [constraints.verificationMethod] - Required verification method
 * @param {number} [constraints.minSamples=5] - Minimum samples required
 * @param {number} [constraints.minReward=0] - Minimum acceptable reward
 * @returns {Promise<{strategy: string, sampledReward: number, avgReward: number, confidence: number, performanceTier: string}>}
 *
 * @example
 *   const best = await getBestStrategy('code-review', {
 *     orchestrationPattern: 'parallel',
 *     minSamples: 10,
 *     minReward: 0.7
 *   });
 */
async function getBestStrategy(taskType, constraints = {}) {
  if (!taskType) {
    throw new Error('taskType is required');
  }

  const { minSamples = 5, minReward = 0, ...dimensionConstraints } = constraints;

  // Get matching strategies
  const strategies = await getStrategyPerformance(
    { taskType, ...dimensionConstraints },
    { minExecutions: minSamples, limit: 100 }
  );

  if (strategies.length === 0) {
    throw new Error(`No strategies found for taskType="${taskType}" with minSamples=${minSamples}`);
  }

  // Filter by minimum reward
  let filtered = strategies.filter(s => s.avgReward >= minReward);

  if (filtered.length === 0) {
    console.warn(`[strategy-tracker] No strategies with reward >= ${minReward}, using all available`);
    filtered = strategies;
  }

  return selectBestByThompsonSampling(filtered);
}

/**
 * PHASE 2: Select best strategy using Thompson Sampling (Beta distribution)
 * Internal helper function with performance tier information
 *
 * @private
 * @param {Array} strategies - Array of strategy performance records
 * @returns {{strategy: string, sampledReward: number, avgReward: number, confidence: number, performanceTier: string}}
 */
function selectBestByThompsonSampling(strategies) {
  // Sample from Beta(alpha, beta) for each strategy
  const samples = strategies.map(s => ({
    ...s,
    sampledReward: betaSample(s.alpha, s.beta)
  }));

  // Sort by sampled reward (exploration + exploitation)
  samples.sort((a, b) => b.sampledReward - a.sampledReward);

  const best = samples[0];

  // Calculate confidence based on sample count
  const totalSamples = best.successes + best.failures;
  const confidence = Math.min(0.95, totalSamples / (totalSamples + 10));

  return {
    strategy: best.strategy,
    taskType: best.taskType,
    promptTemplateId: best.promptTemplateId,
    orchestrationPattern: best.orchestrationPattern,
    verificationMethod: best.verificationMethod,
    reasoningSequence: best.reasoningSequence,
    sampledReward: parseFloat(best.sampledReward.toFixed(4)),
    avgReward: best.avgReward,
    successRate: best.successRate,
    confidence: parseFloat(confidence.toFixed(4)),
    totalSamples,
    performanceTier: best.performanceTier,
    costUsd: best.costUsd,
    avgDurationMs: best.durationMs ? Math.round(best.durationMs / best.totalExecutions) : 0
  };
}

/**
 * Sample from Beta(alpha, beta) distribution.
 * Uses Gamma distribution approximation for Beta sampling.
 *
 * @private
 * @param {number} alpha - Beta alpha parameter
 * @param {number} beta - Beta beta parameter
 * @returns {number} Sampled value in [0, 1]
 */
function betaSample(alpha, beta) {
  // Beta(alpha, beta) = Gamma(alpha) / (Gamma(alpha) + Gamma(beta))
  const x = gammaSample(alpha);
  const y = gammaSample(beta);
  return x / (x + y);
}

/**
 * Sample from Gamma(shape, scale=1) distribution.
 * Uses Marsaglia and Tsang's method.
 *
 * @private
 * @param {number} shape - Gamma shape parameter
 * @returns {number} Sampled value
 */
function gammaSample(shape) {
  if (shape < 1) {
    // For shape < 1, use gamma(shape + 1) * U^(1/shape)
    return gammaSample(shape + 1) * Math.pow(Math.random(), 1 / shape);
  }

  // Marsaglia and Tsang's method for shape >= 1
  const d = shape - 1/3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x, v;
    do {
      x = randomNormal();
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = Math.random();

    if (u < 1 - 0.0331 * x * x * x * x) {
      return d * v;
    }

    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
      return d * v;
    }
  }
}

/**
 * Generate a random sample from standard normal distribution.
 * Uses Box-Muller transform.
 *
 * @private
 * @returns {number} Standard normal random variable
 */
function randomNormal() {
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/**
 * PHASE 2: Get strategy comparison by dimension
 * Analyzes how different strategy dimensions affect performance
 *
 * @param {string} taskType - Type of task
 * @param {string} dimension - Dimension to compare (promptTemplateId, orchestrationPattern, verificationMethod)
 * @param {object} [options] - Query options
 * @param {number} [options.minExecutions=2] - Minimum executions filter
 * @returns {Promise<Array>} Dimension values with performance stats
 *
 * @example
 *   const patterns = await getStrategyComparisonByDimension('code-review', 'orchestrationPattern');
 *   // => [
 *   //   { dimension: 'parallel', avgReward: 0.82, totalExecutions: 15 },
 *   //   { dimension: 'sequential', avgReward: 0.65, totalExecutions: 8 },
 *   // ]
 */
async function getStrategyComparisonByDimension(taskType, dimension, options = {}) {
  const { minExecutions = 2 } = options;

  if (!taskType) {
    throw new Error('taskType is required');
  }

  // Map camelCase to snake_case
  const dimensionMap = {
    promptTemplateId: 'prompt_template_id',
    orchestrationPattern: 'orchestration_pattern',
    verificationMethod: 'verification_method'
  };

  const dbDimension = dimensionMap[dimension];
  if (!dbDimension) {
    throw new Error(`Invalid dimension: ${dimension}. Must be one of: ${Object.keys(dimensionMap).join(', ')}`);
  }

  try {
    const result = await pool.query(`
      SELECT
        ${dbDimension} as dimension_value,
        COUNT(DISTINCT strategy) as num_strategies,
        ROUND(AVG(avg_reward)::NUMERIC, 4) as avg_reward,
        ROUND(MAX(avg_reward)::NUMERIC, 4) as max_reward,
        ROUND(MIN(avg_reward)::NUMERIC, 4) as min_reward,
        SUM(successes + failures) as total_executions,
        ROUND(SUM(successes)::NUMERIC / NULLIF(SUM(successes + failures), 0), 4) as overall_success_rate
      FROM learning.strategy_performance
      WHERE task_type = $1
        AND ${dbDimension} IS NOT NULL
        AND successes + failures >= $2
      GROUP BY ${dbDimension}
      ORDER BY avg_reward DESC
    `, [taskType, minExecutions]);

    return result.rows.map(row => ({
      dimension: row.dimension_value,
      numStrategies: parseInt(row.num_strategies),
      avgReward: parseFloat(row.avg_reward),
      maxReward: parseFloat(row.max_reward),
      minReward: parseFloat(row.min_reward),
      totalExecutions: parseInt(row.total_executions),
      overallSuccessRate: parseFloat(row.overall_success_rate)
    }));
  } catch (error) {
    console.error('[strategy-tracker] Failed to get strategy comparison:', error.message);
    throw error;
  }
}

/**
 * PHASE 2: Get strategy analysis view with performance tiers
 * Returns the learning.strategy_analysis view (pre-computed)
 *
 * @param {object} [filters] - Optional filters
 * @param {string} [filters.taskType] - Filter by task type
 * @param {string} [filters.performanceTier] - Filter by tier (HIGH_PERFORMER, MODERATE_PERFORMER, etc.)
 * @param {number} [filters.limit=20] - Max results to return
 * @returns {Promise<Array>} Strategy analysis records
 *
 * @example
 *   const highPerformers = await getStrategyAnalysis({
 *     taskType: 'code-review',
 *     performanceTier: 'HIGH_PERFORMER',
 *     limit: 10
 *   });
 */
async function getStrategyAnalysis(filters = {}) {
  const { taskType = null, performanceTier = null, limit = 20 } = filters;

  try {
    let query = `
      SELECT
        strategy,
        task_type,
        prompt_template_id,
        orchestration_pattern,
        verification_method,
        successes,
        failures,
        successes + failures as total_executions,
        ROUND(successes::NUMERIC / NULLIF(successes + failures, 0), 4) as success_rate,
        ROUND(avg_reward::NUMERIC, 4) as avg_reward,
        alpha,
        beta,
        CASE
          WHEN successes + failures < 5 THEN 'INSUFFICIENT_DATA'
          WHEN avg_reward >= 0.8 THEN 'HIGH_PERFORMER'
          WHEN avg_reward >= 0.6 THEN 'MODERATE_PERFORMER'
          WHEN avg_reward >= 0.4 THEN 'LOW_PERFORMER'
          ELSE 'POOR_PERFORMER'
        END as performance_tier
      FROM learning.strategy_performance
      WHERE 1=1
    `;

    const params = [];

    if (taskType) {
      query += ` AND task_type = $${params.length + 1}`;
      params.push(taskType);
    }

    if (performanceTier) {
      // Need to repeat the CASE statement in WHERE, or use HAVING
      // For simplicity, fetch all and filter in JS
    }

    query += ` ORDER BY avg_reward DESC LIMIT $${params.length + 1}`;
    params.push(limit);

    const result = await pool.query(query, params);

    // Filter by performanceTier if needed
    let rows = result.rows;
    if (performanceTier) {
      rows = rows.filter(row => {
        const tier = row.successes + row.failures < 5 ? 'INSUFFICIENT_DATA' :
                     row.avg_reward >= 0.8 ? 'HIGH_PERFORMER' :
                     row.avg_reward >= 0.6 ? 'MODERATE_PERFORMER' :
                     row.avg_reward >= 0.4 ? 'LOW_PERFORMER' :
                     'POOR_PERFORMER';
        return tier === performanceTier;
      });
    }

    return rows.map(row => ({
      strategy: row.strategy,
      taskType: row.task_type,
      promptTemplateId: row.prompt_template_id,
      orchestrationPattern: row.orchestration_pattern,
      verificationMethod: row.verification_method,
      successes: parseInt(row.successes),
      failures: parseInt(row.failures),
      totalExecutions: parseInt(row.total_executions),
      successRate: parseFloat(row.success_rate),
      avgReward: parseFloat(row.avg_reward),
      alpha: parseFloat(row.alpha),
      beta: parseFloat(row.beta),
      performanceTier: row.successes + row.failures < 5 ? 'INSUFFICIENT_DATA' :
                       row.avg_reward >= 0.8 ? 'HIGH_PERFORMER' :
                       row.avg_reward >= 0.6 ? 'MODERATE_PERFORMER' :
                       row.avg_reward >= 0.4 ? 'LOW_PERFORMER' :
                       'POOR_PERFORMER'
    }));
  } catch (error) {
    console.error('[strategy-tracker] Failed to get strategy analysis:', error.message);
    throw error;
  }
}

/**
 * Close the database connection pool.
 * Call this when shutting down the application.
 */
async function close() {
  await pool.end();
}

module.exports = {
  recordStrategyResult,
  getStrategyPerformance,
  getBestStrategy,
  getStrategyComparisonByDimension,
  getStrategyAnalysis,
  close,
  pool  // Export for testing
};
