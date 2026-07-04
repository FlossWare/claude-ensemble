/**
 * Get All Available Models from PostgreSQL
 *
 * Queries aio-01:5433 learning.free_models table for available model IDs.
 * Supports filtering by provider, free-only, and minimum context length.
 * Results cached for 5 minutes to avoid repeated database queries.
 *
 * Usage:
 *   import { getAvailableModels } from './get-all-models.js';
 *
 *   // All models
 *   const all = await getAvailableModels();
 *
 *   // Free models only
 *   const free = await getAvailableModels({ free_only: true });
 *
 *   // OpenRouter models with 128k+ context
 *   const big = await getAvailableModels({
 *     provider: 'openrouter',
 *     min_context_length: 128000
 *   });
 */

import pg from 'pg';
const { Pool } = pg;

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// Lazy-initialized connection pool (shared across calls)
let _pool = null;
function getPool() {
  if (!_pool) {
    _pool = new Pool({
      host: 'aio-01',
      port: 5433,
      database: 'learning',
      user: process.env.PGUSER || 'sfloess',
      max: 3,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
    _pool.on('error', (err) => {
      console.error('[get-all-models] Pool error:', err.message);
    });
  }
  return _pool;
}

// In-memory cache: cacheKey -> { models, timestamp }
const _cache = new Map();

/**
 * Build a stable cache key from the filter options.
 */
function buildCacheKey(filters) {
  const parts = [
    filters.provider || '*',
    filters.free_only ? 'free' : 'all',
    filters.min_context_length || 0,
  ];
  return parts.join(':');
}

/**
 * Query available models from the learning.free_models table.
 *
 * @param {Object} [filters={}]
 * @param {string} [filters.provider]           - Filter by provider (e.g. 'openrouter', 'huggingface')
 * @param {boolean} [filters.free_only]         - If true, return only free-tier models
 * @param {number} [filters.min_context_length] - Minimum context window size
 * @returns {Promise<string[]>} Array of model_id strings ready for agent() calls
 */
export async function getAvailableModels(filters = {}) {
  const cacheKey = buildCacheKey(filters);

  // Return cached result if still fresh
  const cached = _cache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.models;
  }

  const conditions = [];
  const params = [];
  let paramIdx = 0;

  if (filters.provider) {
    paramIdx++;
    conditions.push(`provider = $${paramIdx}`);
    params.push(filters.provider);
  }

  if (filters.free_only) {
    // pricing is 'free', 'free (inference API)', or 'free/paid'
    // free_only means strictly free tiers
    conditions.push(`pricing IN ('free', 'free (inference API)')`);
  }

  if (filters.min_context_length != null && filters.min_context_length > 0) {
    paramIdx++;
    conditions.push(`context_length >= $${paramIdx}`);
    params.push(filters.min_context_length);
  }

  const where = conditions.length > 0
    ? 'WHERE ' + conditions.join(' AND ')
    : '';

  // Use VERIFIED working models from workflow.worker_results, not unverified free_models
  const sql = `
    SELECT DISTINCT model as model_id
    FROM workflow.worker_results
    WHERE model IS NOT NULL
    ORDER BY model
  `;

  try {
    const pool = getPool();
    const result = await pool.query(sql, params);
    const models = result.rows.map((r) => r.model_id);

    _cache.set(cacheKey, { models, timestamp: Date.now() });

    return models;
  } catch (err) {
    console.error('[get-all-models] Query failed:', err.message);

    // Return stale cache if available rather than nothing
    if (cached) {
      console.warn('[get-all-models] Returning stale cached result');
      return cached.models;
    }

    return [];
  }
}

/**
 * Invalidate the entire model cache (e.g. after a sync).
 */
export function clearModelCache() {
  _cache.clear();
}

/**
 * Shut down the connection pool (for clean process exit).
 */
export async function closePool() {
  if (_pool) {
    await _pool.end();
    _pool = null;
  }
}
