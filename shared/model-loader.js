/**
 * Model Loader - Database-driven model selection
 *
 * Loads model performance metrics from PostgreSQL monitoring.execution_summary
 * and provides intelligent model selection for workers and arbiters.
 *
 * Usage:
 *   import { loadModelsFromDB, selectWorkerModels, selectArbiterModel } from './model-loader.js';
 *
 *   // Load all models with performance metrics
 *   const models = await loadModelsFromDB();
 *   // Returns: { all: [], high: [], medium: [], fast: [] }
 *
 *   // Select diverse worker models
 *   const workers = await selectWorkerModels(6, []);
 *   // Returns: ['opus', 'gemini', 'gpt-4o', ...]
 *
 *   // Select high-tier arbiter
 *   const arbiter = await selectArbiterModel(workers);
 *   // Returns: 'opus' (highest quality, not in workers)
 */

import pg from 'pg';
const { Pool } = pg;

// PostgreSQL connection pool
let pool = null;

function getPool() {
  if (!pool) {
    pool = new Pool({
      host: 'aio-01',
      port: 5433,
      user: 'sfloess',
      database: 'learning',
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
  }
  return pool;
}

/**
 * Model tier classification
 */
const MODEL_TIERS = {
  high: [
    'opus', 'sonnet', 'gpt-4o', 'gemini-pro', 'gemini-thinking',
    'llama-70b', 'llama-3.3-70b-versatile', 'mistral-large', 'qwen-72b', 'deepseek-coder'
  ],
  medium: [
    'fable', 'gpt-4o-mini', 'gemini-flash', 'mistral-medium',
    'llama-8b', 'qwen-7b', 'qwen2.5:7b', 'deepseek-chat'
  ],
  fast: [
    'haiku', 'mistral-small', 'gemini', 'gemma2:2b', 'phi3.5:latest', 'automl'
  ]
};

/**
 * Load all models from database with performance metrics
 *
 * @returns {Promise<Object>} { all: [...], high: [...], medium: [...], fast: [...] }
 */
export async function loadModelsFromDB() {
  const db = getPool();

  try {
    // Query for model performance metrics (last 30 days)
    const query = `
      SELECT
        model,
        AVG(quality_score) as avg_quality,
        COUNT(*) as total_usage,
        AVG(duration_ms) as avg_duration,
        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate,
        SUM(cost_usd) as total_cost
      FROM monitoring.execution_summary
      WHERE timestamp > NOW() - INTERVAL '30 days'
        AND model NOT IN ('test', 'test-model', 'concurrent-test', 'unknown', 'numpy-local')
        AND quality_score IS NOT NULL
      GROUP BY model
      HAVING COUNT(*) >= 3
      ORDER BY avg_quality DESC
    `;

    const result = await db.query(query);

    // Create model objects with tier classification
    const models = result.rows.map(row => {
      const tier = getTier(row.model);
      return {
        name: row.model,
        tier,
        avg_quality: parseFloat(row.avg_quality) || 0,
        total_usage: parseInt(row.total_usage) || 0,
        avg_duration: parseFloat(row.avg_duration) || 0,
        success_rate: parseFloat(row.success_rate) || 0,
        total_cost: parseFloat(row.total_cost) || 0,
      };
    });

    // Add models from tier list that aren't in database yet (new models)
    const allKnownModels = [...MODEL_TIERS.high, ...MODEL_TIERS.medium, ...MODEL_TIERS.fast];
    const existingNames = models.map(m => m.name);
    const missingModels = allKnownModels.filter(name => !existingNames.includes(name));

    for (const name of missingModels) {
      const tier = getTier(name);
      models.push({
        name,
        tier,
        avg_quality: getTierDefaultQuality(tier),
        total_usage: 0,
        avg_duration: 0,
        success_rate: 0,
        total_cost: 0,
      });
    }

    // Sort by quality
    models.sort((a, b) => b.avg_quality - a.avg_quality);

    // Group by tier
    const high = models.filter(m => m.tier === 'high');
    const medium = models.filter(m => m.tier === 'medium');
    const fast = models.filter(m => m.tier === 'fast');

    return {
      all: models,
      high,
      medium,
      fast,
    };
  } catch (error) {
    console.error('Error loading models from DB:', error.message);

    // Fallback: return tier-based defaults
    return getFallbackModels();
  }
}

/**
 * Get model tier
 *
 * @param {string} modelName
 * @returns {string} 'high' | 'medium' | 'fast'
 */
function getTier(modelName) {
  if (MODEL_TIERS.high.includes(modelName)) return 'high';
  if (MODEL_TIERS.medium.includes(modelName)) return 'medium';
  if (MODEL_TIERS.fast.includes(modelName)) return 'fast';

  // Heuristic for unknown models
  if (modelName.includes('70b') || modelName.includes('72b')) return 'high';
  if (modelName.includes('8b') || modelName.includes('7b')) return 'medium';
  if (modelName.includes('2b') || modelName.includes('mini')) return 'fast';

  return 'medium'; // Default
}

/**
 * Get default quality score for tier
 *
 * @param {string} tier
 * @returns {number}
 */
function getTierDefaultQuality(tier) {
  if (tier === 'high') return 0.85;
  if (tier === 'medium') return 0.75;
  if (tier === 'fast') return 0.65;
  return 0.70;
}

/**
 * Fallback models if database unavailable
 *
 * @returns {Object}
 */
function getFallbackModels() {
  const models = [];

  for (const [tier, names] of Object.entries(MODEL_TIERS)) {
    for (const name of names) {
      models.push({
        name,
        tier,
        avg_quality: getTierDefaultQuality(tier),
        total_usage: 0,
        avg_duration: 0,
        success_rate: 0,
        total_cost: 0,
      });
    }
  }

  models.sort((a, b) => b.avg_quality - a.avg_quality);

  return {
    all: models,
    high: models.filter(m => m.tier === 'high'),
    medium: models.filter(m => m.tier === 'medium'),
    fast: models.filter(m => m.tier === 'fast'),
  };
}

/**
 * Select worker models with diversity
 *
 * Strategy:
 * 1. Mix of tiers (high, medium, fast)
 * 2. Avoid recently used models (exclude list)
 * 3. Prioritize high quality within each tier
 *
 * @param {number} count - Number of workers to select
 * @param {string[]} exclude - Models to exclude (recently used)
 * @returns {Promise<string[]>} Array of model names
 */
export async function selectWorkerModels(count, exclude = []) {
  const models = await loadModelsFromDB();

  // Filter out excluded models
  const available = models.all.filter(m => !exclude.includes(m.name));

  if (available.length === 0) {
    throw new Error('No models available after exclusions');
  }

  if (available.length <= count) {
    return available.map(m => m.name);
  }

  // Diversity strategy: mix tiers
  const selected = [];
  const tierTargets = calculateTierTargets(count);

  // Select from each tier
  for (const [tier, targetCount] of Object.entries(tierTargets)) {
    const tierModels = available.filter(m => m.tier === tier);

    // Sort by quality within tier
    tierModels.sort((a, b) => b.avg_quality - a.avg_quality);

    const numToSelect = Math.min(targetCount, tierModels.length);
    for (let i = 0; i < numToSelect; i++) {
      selected.push(tierModels[i].name);
    }
  }

  // If we don't have enough, fill from best available
  while (selected.length < count && selected.length < available.length) {
    const remaining = available.filter(m => !selected.includes(m.name));
    remaining.sort((a, b) => b.avg_quality - a.avg_quality);
    if (remaining.length > 0) {
      selected.push(remaining[0].name);
    } else {
      break;
    }
  }

  return selected.slice(0, count);
}

/**
 * Calculate tier distribution targets for worker selection
 *
 * @param {number} count - Total workers needed
 * @returns {Object} { high: X, medium: Y, fast: Z }
 */
function calculateTierTargets(count) {
  // Strategy: 50% high, 30% medium, 20% fast
  return {
    high: Math.ceil(count * 0.5),
    medium: Math.ceil(count * 0.3),
    fast: Math.max(1, Math.floor(count * 0.2)),
  };
}

/**
 * Select arbiter model (highest quality, not in workers)
 *
 * @param {string[]} workers - Worker models to exclude
 * @returns {Promise<string>} Arbiter model name
 */
export async function selectArbiterModel(workers = []) {
  const models = await loadModelsFromDB();

  // Arbiter must be high tier and not in workers
  const candidates = models.high.filter(m => !workers.includes(m.name));

  if (candidates.length === 0) {
    // Fallback: use best medium tier
    const mediumCandidates = models.medium.filter(m => !workers.includes(m.name));
    if (mediumCandidates.length === 0) {
      throw new Error('No available arbiter models');
    }
    return mediumCandidates[0].name;
  }

  // Return highest quality high-tier model
  candidates.sort((a, b) => b.avg_quality - a.avg_quality);
  return candidates[0].name;
}

/**
 * Get model info
 *
 * @param {string} modelName
 * @returns {Promise<Object|null>}
 */
export async function getModelInfo(modelName) {
  const models = await loadModelsFromDB();
  return models.all.find(m => m.name === modelName) || null;
}

/**
 * Cleanup connections
 */
export async function close() {
  if (pool) {
    await pool.end();
    pool = null;
  }
}

// Cleanup on process exit
process.on('exit', () => {
  if (pool) {
    pool.end();
  }
});
