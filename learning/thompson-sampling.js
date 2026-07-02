/**
 * Thompson Sampling for Multi-Armed Bandit Model Selection
 *
 * Implements Bayesian Thompson Sampling using Beta distributions to balance
 * exploration and exploitation when selecting AI models. Each model maintains
 * a Beta(alpha, beta) posterior where:
 * - alpha = number of successes (quality_score >= 0.7)
 * - beta = number of failures (quality_score < 0.7)
 *
 * The algorithm samples from each model's posterior and selects the one with
 * the highest sampled value, naturally balancing exploration (uncertain models
 * get sampled more) and exploitation (high-performing models preferred).
 *
 * MIGRATED: State now persists to PostgreSQL (workflow.strategy_performance)
 * Legacy JSON file support maintained for backwards compatibility
 *
 * Usage:
 *   import { selectModel, updateModel, getModelStats } from './thompson-sampling.js';
 *
 *   const model = selectModel(['haiku', 'opus', 'sonnet']);
 *   // ... execute with model ...
 *   updateModel(model, qualityScore);
 */

import { createRequire } from 'module';
import { randomBytes } from 'crypto';

// ============================================================================
// CONSTANTS
// ============================================================================

const QUALITY_THRESHOLD = 0.7;  // Success threshold for quality scores

// Prior parameters (uniform prior: Beta(1, 1))
const PRIOR_ALPHA = 1;
const PRIOR_BETA = 1;

// ============================================================================
// POSTGRES ADAPTER
// ============================================================================

let _strategyPerformance = null;

/**
 * Get PostgreSQL strategy performance adapter (singleton)
 */
function getStrategyPerformance() {
  if (!_strategyPerformance) {
    try {
      const require = createRequire(import.meta.url);
      const { getStrategyPerformance } = require('./postgres-adapter.js');
      _strategyPerformance = getStrategyPerformance();
    } catch (err) {
      if (process.env.LEARNING_DEBUG) {
        console.error(`[thompson-sampling] PostgreSQL unavailable: ${err.message}`);
      }
      return null;
    }
  }
  return _strategyPerformance;
}

/**
 * Get model state from PostgreSQL
 * @param {string} model - Model name
 * @returns {Promise<object>} Model state with alpha, beta, total, avg_quality
 */
async function getModelState(model) {
  const sp = getStrategyPerformance();
  if (!sp) {
    throw new Error('PostgreSQL unavailable - cannot access model state');
  }

  const stats = await sp.getStrategy(model);

  if (!stats) {
    // Return default state for new model
    return {
      alpha: PRIOR_ALPHA,
      beta: PRIOR_BETA,
      total: 0,
      avg_quality: 0,
    };
  }

  // Parse PostgreSQL NUMERIC fields to JavaScript numbers
  return {
    alpha: parseFloat(stats.alpha),
    beta: parseFloat(stats.beta),
    total: parseInt(stats.successes) + parseInt(stats.failures),
    avg_quality: parseFloat(stats.avg_reward),
  };
}

/**
 * Update model state in PostgreSQL
 * @param {string} model - Model name
 * @param {number} qualityScore - Quality score (0-1)
 * @returns {Promise<boolean>} Success
 */
async function updateModelState(model, qualityScore) {
  const sp = getStrategyPerformance();
  if (!sp) {
    throw new Error('PostgreSQL unavailable - cannot update model state');
  }

  const isSuccess = qualityScore >= QUALITY_THRESHOLD;
  await sp.record(model, isSuccess, qualityScore);
  return true;
}

// ============================================================================
// BETA DISTRIBUTION SAMPLING
// ============================================================================

/**
 * Generate a random sample from Beta(alpha, beta) distribution.
 * Uses the Johnk algorithm for Beta sampling.
 */
function sampleBeta(alpha, beta) {
  // Handle edge cases with very small beta (near-certain success)
  // Beta(a, 0) is undefined, but we treat Beta(a, epsilon) as ~1
  if (beta < 0.01) {
    return 0.95 + randomUniform() * 0.05; // Sample near 1
  }

  // Handle edge cases with very small alpha (near-certain failure)
  if (alpha < 0.01) {
    return randomUniform() * 0.05; // Sample near 0
  }

  // Special case: Beta(1, 1) is uniform [0, 1]
  if (alpha === 1 && beta === 1) {
    return randomUniform();
  }

  // Use Johnk's algorithm for general Beta(alpha, beta)
  // This is numerically stable for alpha, beta > 0
  let u, v, x, y;
  let iterations = 0;
  const maxIterations = 1000;

  do {
    u = randomUniform();
    v = randomUniform();
    x = Math.pow(u, 1 / alpha);
    y = Math.pow(v, 1 / beta);
    iterations++;

    if (iterations > maxIterations) {
      // Fallback: use mean of Beta distribution
      return alpha / (alpha + beta);
    }
  } while (x + y > 1);

  if (x + y === 0) {
    return randomUniform(); // Avoid division by zero
  }

  return x / (x + y);
}

/**
 * Generate a cryptographically random uniform value in [0, 1].
 */
function randomUniform() {
  // Use crypto.randomBytes for high-quality randomness
  const buffer = randomBytes(4);
  const value = buffer.readUInt32BE(0);
  return value / 0xffffffff;
}

// ============================================================================
// PUBLIC API
// ============================================================================

/**
 * Select a model using Thompson Sampling.
 *
 * @param {string[]} candidates - Array of model names to choose from
 * @param {object} options - Selection options
 * @param {boolean} options.debug - Log selection details
 * @returns {Promise<string>} Selected model name
 */
export async function selectModel(candidates, options = {}) {
  if (!candidates || candidates.length === 0) {
    throw new Error('selectModel requires at least one candidate model');
  }

  const samples = {};
  let maxSample = -Infinity;
  let selectedModel = candidates[0];

  // Sample from each candidate's posterior distribution
  for (const model of candidates) {
    const modelState = await getModelState(model);
    const sample = sampleBeta(modelState.alpha, modelState.beta);
    samples[model] = sample;

    if (sample > maxSample) {
      maxSample = sample;
      selectedModel = model;
    }
  }

  if (options.debug || process.env.LEARNING_DEBUG) {
    console.log('[thompson-sampling] Selection:');
    console.log(`  Candidates: ${candidates.join(', ')}`);
    console.log('  Samples:', JSON.stringify(samples, null, 2));
    console.log(`  Selected: ${selectedModel} (sample=${maxSample.toFixed(4)})`);
  }

  return selectedModel;
}

/**
 * Update a model's state based on execution result.
 *
 * @param {string} model - Model name
 * @param {number} qualityScore - Quality score (0-1)
 * @param {object} options - Update options (ignored, kept for API compatibility)
 * @returns {Promise<object>} Updated model state
 */
export async function updateModel(model, qualityScore, options = {}) {
  if (typeof qualityScore !== 'number' || qualityScore < 0 || qualityScore > 1) {
    throw new Error(`Invalid quality score: ${qualityScore} (must be 0-1)`);
  }

  // Update PostgreSQL
  await updateModelState(model, qualityScore);

  // Return updated state
  return await getModelState(model);
}

/**
 * Get statistics for a model.
 *
 * @param {string} model - Model name
 * @returns {Promise<object>} Model statistics including alpha, beta, total, avg_quality, success_rate, uncertainty
 */
export async function getModelStats(model) {
  const modelState = await getModelState(model);

  // Calculate derived statistics
  const successRate = modelState.alpha / (modelState.alpha + modelState.beta);

  // Uncertainty (variance of Beta distribution)
  const a = modelState.alpha;
  const b = modelState.beta;
  const variance = (a * b) / ((a + b) ** 2 * (a + b + 1));
  const uncertainty = Math.sqrt(variance);

  return {
    model,
    alpha: modelState.alpha,
    beta: modelState.beta,
    total: modelState.total,
    avg_quality: modelState.avg_quality,
    success_rate: successRate,
    uncertainty,
  };
}

/**
 * Get statistics for all models.
 *
 * @returns {Promise<object[]>} Array of model statistics
 */
export async function getAllModelStats() {
  const sp = getStrategyPerformance();
  if (!sp) {
    return [];
  }

  const allStrategies = await sp.getAllStrategies();

  return Promise.all(
    allStrategies.map(async (strategy) => {
      const modelState = {
        alpha: parseFloat(strategy.alpha),
        beta: parseFloat(strategy.beta),
        total: parseInt(strategy.successes) + parseInt(strategy.failures),
        avg_quality: parseFloat(strategy.avg_reward),
      };

      const successRate = modelState.alpha / (modelState.alpha + modelState.beta);
      const a = modelState.alpha;
      const b = modelState.beta;
      const variance = (a * b) / ((a + b) ** 2 * (a + b + 1));
      const uncertainty = Math.sqrt(variance);

      return {
        model: strategy.strategy,
        alpha: modelState.alpha,
        beta: modelState.beta,
        total: modelState.total,
        avg_quality: modelState.avg_quality,
        success_rate: successRate,
        uncertainty,
      };
    })
  );
}

/**
 * Reset a model's state to uniform prior.
 *
 * @param {string} model - Model name
 * @param {boolean} persist - Ignored (kept for API compatibility)
 * @returns {Promise<boolean>} Success
 */
export async function resetModel(model, persist = true) {
  const sp = getStrategyPerformance();
  if (!sp) {
    return false;
  }

  // Reset by updating with uniform prior
  await sp.updateStrategy(model, {
    successes: 0,
    failures: 0,
    alpha: PRIOR_ALPHA,
    beta: PRIOR_BETA,
    total_reward: 0,
    avg_reward: 0,
  });

  return true;
}

/**
 * Bootstrap state from execution database.
 * This is typically run once to initialize from historical data.
 * NOTE: This now bootstraps INTO PostgreSQL, not JSON file
 *
 * @param {object} db - Database module instance (postgres-adapter LearningDB)
 * @param {number} qualityThreshold - Success threshold (default: 0.7)
 * @returns {Promise<object>} Bootstrap summary
 */
export async function bootstrapFromDatabase(db, qualityThreshold = QUALITY_THRESHOLD) {
  const sp = getStrategyPerformance();
  if (!sp) {
    throw new Error('PostgreSQL unavailable - cannot bootstrap');
  }

  // Query execution logs from PostgreSQL
  const models = await db.query(`
    SELECT
      model,
      COUNT(*) as total,
      SUM(CASE WHEN quality_score >= $1 THEN 1 ELSE 0 END) as successes,
      SUM(CASE WHEN quality_score < $1 THEN 1 ELSE 0 END) as failures,
      AVG(quality_score) as avg_quality
    FROM workflow.execution_summary
    WHERE quality_score IS NOT NULL
    GROUP BY model
    ORDER BY total DESC
  `, [qualityThreshold]);

  const summary = {
    version: 1,
    created: new Date().toISOString(),
    models: {},
    notes: `Beta priors bootstrapped from ${models.reduce((sum, m) => sum + parseInt(m.total), 0)} executions. Success threshold: quality_score >= ${qualityThreshold}`,
  };

  for (const row of models) {
    // Add prior to avoid zero probabilities
    const successes = parseInt(row.successes);
    const failures = parseInt(row.failures);
    const alpha = successes + PRIOR_ALPHA;
    const beta = failures + PRIOR_BETA;
    const total_reward = parseFloat(row.avg_quality) * parseInt(row.total);
    const avg_reward = parseFloat(row.avg_quality);

    // Store in PostgreSQL
    await sp.updateStrategy(row.model, {
      successes,
      failures,
      alpha,
      beta,
      total_reward,
      avg_reward,
    });

    summary.models[row.model] = {
      alpha,
      beta,
      total: parseInt(row.total),
      avg_quality: avg_reward,
    };
  }

  return summary;
}

/**
 * Export current state for inspection/backup.
 * NOTE: This now exports from PostgreSQL, not JSON file
 *
 * @returns {Promise<object>} Current state
 */
export async function exportState() {
  const sp = getStrategyPerformance();
  if (!sp) {
    return {
      version: 1,
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
      models: {},
      notes: 'PostgreSQL unavailable',
    };
  }

  const allStrategies = await sp.getAllStrategies();

  const state = {
    version: 1,
    created: new Date().toISOString(),
    updated: new Date().toISOString(),
    models: {},
    notes: 'Thompson Sampling bandit state (from PostgreSQL)',
  };

  for (const strategy of allStrategies) {
    state.models[strategy.strategy] = {
      alpha: parseFloat(strategy.alpha),
      beta: parseFloat(strategy.beta),
      total: parseInt(strategy.successes) + parseInt(strategy.failures),
      avg_quality: parseFloat(strategy.avg_reward),
    };
  }

  return state;
}

/**
 * Import state from object or JSON string.
 * NOTE: This now imports INTO PostgreSQL, not JSON file
 *
 * @param {object|string} data - State data
 * @param {boolean} persist - Ignored (kept for API compatibility, always persists to PostgreSQL)
 * @returns {Promise<boolean>} Success
 */
export async function importState(data, persist = true) {
  try {
    const state = typeof data === 'string' ? JSON.parse(data) : data;

    // Validate structure
    if (!state.version || !state.models) {
      throw new Error('Invalid state structure');
    }

    const sp = getStrategyPerformance();
    if (!sp) {
      throw new Error('PostgreSQL unavailable - cannot import');
    }

    // Import each model into PostgreSQL
    for (const [model, modelState] of Object.entries(state.models)) {
      await sp.updateStrategy(model, {
        successes: parseInt(modelState.alpha) - PRIOR_ALPHA,
        failures: parseInt(modelState.beta) - PRIOR_BETA,
        alpha: parseFloat(modelState.alpha),
        beta: parseFloat(modelState.beta),
        total_reward: parseFloat(modelState.avg_quality) * parseInt(modelState.total),
        avg_reward: parseFloat(modelState.avg_quality),
      });
    }

    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[thompson-sampling] Import failed: ${err.message}`);
    }
    return false;
  }
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  selectModel,
  updateModel,
  getModelStats,
  getAllModelStats,
  resetModel,
  bootstrapFromDatabase,
  exportState,
  importState,
};
