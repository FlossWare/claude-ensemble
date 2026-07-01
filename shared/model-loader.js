/**
 * Model Loader - Load available models from PostgreSQL
 * Replaces hardcoded model lists with dynamic database queries
 * 
 * Created: 2026-07-01
 */

import pkg from 'pg';
const { Pool } = pkg;

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER || 'claude',
  password: process.env.PGPASSWORD,
  max: 5,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('[model-loader] PostgreSQL pool error:', err.message);
});

// Cache models for 5 minutes to avoid constant DB queries
let cachedModels = null;
let cacheTime = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Load all enabled models from PostgreSQL
 * @returns {Promise<Object>} Models grouped by tier
 */
export async function loadModelsFromDB() {
  const now = Date.now();
  
  // Return cached if still valid
  if (cachedModels && (now - cacheTime) < CACHE_TTL) {
    return cachedModels;
  }

  try {
    const { rows } = await pool.query(`
      SELECT model_name, provider, tier, cost_input_per_1k, cost_output_per_1k
      FROM api_models 
      WHERE enabled = true 
      ORDER BY tier, cost_input_per_1k ASC
    `);

    // Group by tier
    const modelsByTier = {
      high: [],
      medium: [],
      fast: [],
      all: rows.map(r => r.model_name)
    };

    rows.forEach(row => {
      const tier = row.tier || 'medium';
      if (modelsByTier[tier]) {
        modelsByTier[tier].push({
          name: row.model_name,
          provider: row.provider,
          costIn: parseFloat(row.cost_input_per_1k),
          costOut: parseFloat(row.cost_output_per_1k)
        });
      }
    });

    // Cache the results
    cachedModels = modelsByTier;
    cacheTime = now;

    console.log(`[model-loader] Loaded ${rows.length} models from PostgreSQL`);
    console.log(`  High: ${modelsByTier.high.length}, Medium: ${modelsByTier.medium.length}, Fast: ${modelsByTier.fast.length}`);

    return modelsByTier;
  } catch (err) {
    console.error('[model-loader] Failed to load from PostgreSQL:', err.message);
    
    // Fallback to hardcoded models
    return {
      high: [
        { name: 'opus', provider: 'anthropic', costIn: 0.015, costOut: 0.075 },
        { name: 'gpt-4o', provider: 'openai', costIn: 0.0025, costOut: 0.01 }
      ],
      medium: [
        { name: 'sonnet', provider: 'anthropic', costIn: 0.003, costOut: 0.015 },
        { name: 'llama-3.3-70b-versatile', provider: 'groq', costIn: 0, costOut: 0 }
      ],
      fast: [
        { name: 'haiku', provider: 'anthropic', costIn: 0.0008, costOut: 0.004 },
        { name: 'gpt-4o-mini', provider: 'openai', costIn: 0.00015, costOut: 0.0006 }
      ],
      all: ['opus', 'gpt-4o', 'sonnet', 'llama-3.3-70b-versatile', 'haiku', 'gpt-4o-mini']
    };
  }
}

/**
 * Select diverse worker models (mix across tiers)
 * @param {number} count - Number of workers needed
 * @param {Array<string>} exclude - Models to exclude
 * @returns {Promise<Array<string>>} Selected worker model names
 */
export async function selectWorkerModels(count = 5, exclude = []) {
  const models = await loadModelsFromDB();
  const selected = [];

  // Strategy: Diverse selection across tiers
  // - 2 high-tier (quality)
  // - 2 medium-tier (balance)
  // - 1 fast-tier (speed)
  
  const addFromTier = (tier, max) => {
    const available = models[tier]
      .filter(m => !exclude.includes(m.name) && !selected.includes(m.name))
      .map(m => m.name);
    
    const toAdd = available.slice(0, max);
    selected.push(...toAdd);
  };

  addFromTier('high', 2);
  addFromTier('medium', 2);
  addFromTier('fast', 1);

  // If we don't have enough, fill from all
  while (selected.length < count) {
    const remaining = models.all.filter(m => !exclude.includes(m) && !selected.includes(m));
    if (remaining.length === 0) break;
    selected.push(remaining[0]);
  }

  return selected.slice(0, count);
}

/**
 * Select arbiter model (always highest tier available)
 * @param {Array<string>} exclude - Models to exclude
 * @returns {Promise<string>} Selected arbiter model name
 */
export async function selectArbiterModel(exclude = []) {
  const models = await loadModelsFromDB();

  // Try high tier first
  const highTier = models.high
    .filter(m => !exclude.includes(m.name))
    .sort((a, b) => b.costOut - a.costOut); // Most expensive = usually best
  
  if (highTier.length > 0) {
    return highTier[0].name;
  }

  // Fallback to medium tier
  const mediumTier = models.medium
    .filter(m => !exclude.includes(m.name))
    .sort((a, b) => b.costOut - a.costOut);
  
  if (mediumTier.length > 0) {
    return mediumTier[0].name;
  }

  // Last resort: fast tier
  const fastTier = models.fast.filter(m => !exclude.includes(m.name));
  return fastTier[0]?.name || 'opus'; // Ultimate fallback
}

/**
 * Clear the cache (useful for testing)
 */
export function clearCache() {
  cachedModels = null;
  cacheTime = 0;
}
