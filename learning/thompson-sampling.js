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
 * State persists to ~/.claude/learning/bandit-state.json
 *
 * Usage:
 *   import { selectModel, updateModel, getModelStats } from './thompson-sampling.js';
 *
 *   const model = selectModel(['haiku', 'opus', 'sonnet']);
 *   // ... execute with model ...
 *   updateModel(model, qualityScore);
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { randomBytes } from 'crypto';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const STATE_PATH = join(HOME, '.claude', 'learning', 'bandit-state.json');
const QUALITY_THRESHOLD = 0.7;  // Success threshold for quality scores

// Prior parameters (uniform prior: Beta(1, 1))
const PRIOR_ALPHA = 1;
const PRIOR_BETA = 1;

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let _state = null;
let _lastLoadTime = 0;
const RELOAD_INTERVAL_MS = 5000; // Reload every 5s for hot-swap support

/**
 * Load bandit state from disk, with caching.
 */
function loadState() {
  const now = Date.now();

  // Use cached state if recently loaded
  if (_state && (now - _lastLoadTime) < RELOAD_INTERVAL_MS) {
    return _state;
  }

  try {
    if (existsSync(STATE_PATH)) {
      const data = readFileSync(STATE_PATH, 'utf-8');
      _state = JSON.parse(data);
      _lastLoadTime = now;
      return _state;
    }
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[thompson-sampling] Failed to load state: ${err.message}`);
    }
  }

  // Initialize with uniform priors if no state file
  _state = {
    version: 1,
    created: new Date().toISOString(),
    updated: new Date().toISOString(),
    models: {},
    notes: 'Thompson Sampling bandit state',
  };
  _lastLoadTime = now;
  return _state;
}

/**
 * Save bandit state to disk.
 */
function saveState(state) {
  try {
    state.updated = new Date().toISOString();
    writeFileSync(STATE_PATH, JSON.stringify(state, null, 2), 'utf-8');
    _state = state;
    _lastLoadTime = Date.now();
    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[thompson-sampling] Failed to save state: ${err.message}`);
    }
    return false;
  }
}

/**
 * Get or initialize model state.
 */
function getModelState(state, model) {
  if (!state.models[model]) {
    state.models[model] = {
      alpha: PRIOR_ALPHA,
      beta: PRIOR_BETA,
      total: 0,
      avg_quality: 0,
    };
  }
  return state.models[model];
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
 * @returns {string} Selected model name
 */
export function selectModel(candidates, options = {}) {
  if (!candidates || candidates.length === 0) {
    throw new Error('selectModel requires at least one candidate model');
  }

  const state = loadState();
  const samples = {};
  let maxSample = -Infinity;
  let selectedModel = candidates[0];

  // Sample from each candidate's posterior distribution
  for (const model of candidates) {
    const modelState = getModelState(state, model);
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
 * @param {object} options - Update options
 * @param {boolean} options.persist - Save state immediately (default: true)
 * @returns {object} Updated model state
 */
export function updateModel(model, qualityScore, options = {}) {
  if (typeof qualityScore !== 'number' || qualityScore < 0 || qualityScore > 1) {
    throw new Error(`Invalid quality score: ${qualityScore} (must be 0-1)`);
  }

  const state = loadState();
  const modelState = getModelState(state, model);

  // Update Beta parameters
  const isSuccess = qualityScore >= QUALITY_THRESHOLD;
  if (isSuccess) {
    modelState.alpha += 1;
  } else {
    modelState.beta += 1;
  }

  // Update running statistics
  const oldTotal = modelState.total;
  const oldAvg = modelState.avg_quality || 0;
  modelState.total = oldTotal + 1;
  modelState.avg_quality = (oldAvg * oldTotal + qualityScore) / modelState.total;

  // Persist by default
  const persist = options.persist !== false;
  if (persist) {
    saveState(state);
  }

  return { ...modelState };
}

/**
 * Get statistics for a model.
 *
 * @param {string} model - Model name
 * @returns {object} Model statistics including alpha, beta, total, avg_quality, success_rate, uncertainty
 */
export function getModelStats(model) {
  const state = loadState();
  const modelState = getModelState(state, model);

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
 * @returns {object[]} Array of model statistics
 */
export function getAllModelStats() {
  const state = loadState();
  return Object.keys(state.models).map(model => getModelStats(model));
}

/**
 * Reset a model's state to uniform prior.
 *
 * @param {string} model - Model name
 * @param {boolean} persist - Save state immediately (default: true)
 * @returns {boolean} Success
 */
export function resetModel(model, persist = true) {
  const state = loadState();

  state.models[model] = {
    alpha: PRIOR_ALPHA,
    beta: PRIOR_BETA,
    total: 0,
    avg_quality: 0,
  };

  if (persist) {
    return saveState(state);
  }

  _state = state;
  return true;
}

/**
 * Bootstrap state from execution database.
 * This is typically run once to initialize from historical data.
 *
 * @param {object} db - Database module instance
 * @param {number} qualityThreshold - Success threshold (default: 0.7)
 * @returns {object} Bootstrapped state
 */
export async function bootstrapFromDatabase(db, qualityThreshold = QUALITY_THRESHOLD) {
  const models = db.query(`
    SELECT
      model,
      COUNT(*) as total,
      SUM(CASE WHEN quality_score >= ? THEN 1 ELSE 0 END) as successes,
      SUM(CASE WHEN quality_score < ? THEN 1 ELSE 0 END) as failures,
      AVG(quality_score) as avg_quality
    FROM execution_log
    WHERE quality_score IS NOT NULL
    GROUP BY model
    ORDER BY total DESC
  `, [qualityThreshold, qualityThreshold]);

  const state = {
    version: 1,
    created: new Date().toISOString(),
    updated: new Date().toISOString(),
    models: {},
    notes: `Beta priors bootstrapped from ${models.reduce((sum, m) => sum + m.total, 0)} executions. Success threshold: quality_score >= ${qualityThreshold}`,
  };

  for (const row of models) {
    // Add prior to avoid zero probabilities
    state.models[row.model] = {
      alpha: row.successes + PRIOR_ALPHA,
      beta: row.failures + PRIOR_BETA,
      total: row.total,
      avg_quality: row.avg_quality,
    };
  }

  saveState(state);
  return state;
}

/**
 * Export current state for inspection/backup.
 *
 * @returns {object} Current state
 */
export function exportState() {
  return loadState();
}

/**
 * Import state from object or JSON string.
 *
 * @param {object|string} data - State data
 * @param {boolean} persist - Save immediately (default: true)
 * @returns {boolean} Success
 */
export function importState(data, persist = true) {
  try {
    const state = typeof data === 'string' ? JSON.parse(data) : data;

    // Validate structure
    if (!state.version || !state.models) {
      throw new Error('Invalid state structure');
    }

    if (persist) {
      return saveState(state);
    }

    _state = state;
    _lastLoadTime = Date.now();
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
