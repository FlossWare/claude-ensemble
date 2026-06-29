/**
 * Consensus Caching System
 *
 * Caches weighted voting consensus results to avoid redundant computation.
 * Reduces API costs and latency for identical/similar questions.
 *
 * Features:
 * 1. Exact match cache (hash-based, 1-hour TTL)
 * 2. Semantic similarity cache (vector embeddings, >95% cosine similarity)
 * 3. Cache invalidation on model weight changes
 * 4. Cache hit rate tracking (PostgreSQL)
 *
 * Storage: PostgreSQL workflow.consensus_cache table
 *
 * Created: 2026-06-28
 */

const crypto = require('crypto');
const { Pool } = require('pg');

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Cache TTL (Time To Live)
 */
const DEFAULT_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

/**
 * Semantic similarity threshold (cosine similarity)
 * Only use cached result if similarity >= threshold
 */
const DEFAULT_SIMILARITY_THRESHOLD = 0.95; // 95% similar

/**
 * Model weight version (increment when MODEL_TIER_WEIGHTS or CAPABILITY_MATRIX changes)
 * Forces cache invalidation when voting weights change
 */
const MODEL_WEIGHT_VERSION = 1;

// ============================================================================
// DATABASE CONNECTION
// ============================================================================

// Reuse connection pool from postgres-adapter.js
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
  console.error('[consensus-cache] PostgreSQL pool error:', err.message);
});

// ============================================================================
// SCHEMA INITIALIZATION
// ============================================================================

/**
 * Initialize consensus_cache table (idempotent)
 * Run once on first use
 */
async function initializeSchema() {
  const client = await pool.connect();
  try {
    // Create table first (safe if exists)
    try {
      await client.query(`
        CREATE TABLE IF NOT EXISTS workflow.consensus_cache (
        id SERIAL PRIMARY KEY,

        -- Cache key (SHA256 hash of normalized query)
        cache_key TEXT NOT NULL UNIQUE,

        -- Original query data
        question TEXT NOT NULL,
        question_embedding vector(384), -- For semantic similarity
        task_type TEXT NOT NULL,

        -- Cached consensus result
        consensus_result JSONB NOT NULL, -- Full voting_result from weighted-voting

        -- Cache metadata
        model_weight_version INTEGER NOT NULL,
        cache_hit_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL,
        last_hit_at TIMESTAMP
      )
      `);
    } catch (err) {
      if (err.code !== '42P07') throw err; // Ignore "relation already exists" errors
    }

    // Create indexes separately (ignore duplicate errors)
    try {
      await client.query(`
        CREATE INDEX IF NOT EXISTS idx_consensus_cache_expires
        ON workflow.consensus_cache(expires_at)
      `);
    } catch (err) {
      if (err.code !== '23505') throw err; // Ignore duplicate key errors
    }

    try {
      await client.query(`
        CREATE INDEX IF NOT EXISTS idx_consensus_cache_key
        ON workflow.consensus_cache(cache_key)
      `);
    } catch (err) {
      if (err.code !== '23505') throw err;
    }

    // Create vector index (HNSW for fast similarity search)
    try {
      await client.query(`
        CREATE INDEX IF NOT EXISTS idx_consensus_cache_embedding
        ON workflow.consensus_cache
        USING hnsw (question_embedding vector_cosine_ops)
      `);
    } catch (err) {
      if (err.code !== '23505') throw err;
    }

    // Create cache hit statistics table
    try {
      await client.query(`
        CREATE TABLE IF NOT EXISTS workflow.consensus_cache_stats (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL DEFAULT CURRENT_DATE,
        total_lookups INTEGER DEFAULT 0,
        exact_hits INTEGER DEFAULT 0,
        semantic_hits INTEGER DEFAULT 0,
        misses INTEGER DEFAULT 0,
        hit_rate NUMERIC DEFAULT 0.0,
        avg_similarity NUMERIC DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),

        -- Unique constraint on date (one row per day)
        UNIQUE(date)
      )
      `);
    } catch (err) {
      if (err.code !== '42P07') throw err; // Ignore "relation already exists" errors
    }

    console.log('[consensus-cache] Schema initialized');
  } finally {
    client.release();
  }
}

// Initialize schema on module load (async, non-blocking)
initializeSchema().catch(err => {
  console.error('[consensus-cache] Schema initialization failed:', err.message);
});

// ============================================================================
// CACHE KEY GENERATION
// ============================================================================

/**
 * Generate cache key (SHA256 hash)
 *
 * Normalized inputs:
 * - question (trimmed, lowercased)
 * - task_type
 * - model_weight_version
 *
 * @param {string} question - Question/prompt
 * @param {string} taskType - Task type
 * @returns {string} Cache key (SHA256 hex)
 */
function generateCacheKey(question, taskType) {
  const normalized = {
    question: question.trim().toLowerCase(),
    task_type: taskType,
    version: MODEL_WEIGHT_VERSION,
  };

  const hash = crypto.createHash('sha256');
  hash.update(JSON.stringify(normalized));
  return hash.digest('hex');
}

// ============================================================================
// EMBEDDING GENERATION
// ============================================================================

/**
 * Generate embedding for question (384-dim)
 * Uses shared embedding generator from workflow-storage-adapter
 *
 * @param {string} question - Question text
 * @returns {Promise<Array<number>|null>} 384-dim embedding or null
 */
async function generateEmbedding(question) {
  try {
    const { generateEmbedding: genEmbed } = require('./workflow-storage-adapter.cjs');
    return await genEmbed(question);
  } catch (err) {
    console.warn('[consensus-cache] Embedding generation failed:', err.message);
    return null;
  }
}

// ============================================================================
// CACHE LOOKUP
// ============================================================================

/**
 * Lookup consensus result in cache
 *
 * Strategy:
 * 1. Try exact match first (cache_key lookup)
 * 2. If no exact match, try semantic similarity (vector search)
 * 3. Return null if no match found or cache expired
 *
 * @param {string} question - Question/prompt
 * @param {string} taskType - Task type
 * @param {Object} options - Lookup options
 * @param {number} options.similarityThreshold - Minimum cosine similarity (default: 0.95)
 * @param {boolean} options.exactOnly - Skip semantic search (default: false)
 * @returns {Promise<Object|null>} Cached consensus result or null
 */
async function lookupCache(question, taskType, options = {}) {
  const similarityThreshold = options.similarityThreshold || DEFAULT_SIMILARITY_THRESHOLD;
  const exactOnly = options.exactOnly || false;

  const client = await pool.connect();
  try {
    // STEP 1: Exact match lookup
    const cacheKey = generateCacheKey(question, taskType);

    const exactResult = await client.query(
      `SELECT *
       FROM workflow.consensus_cache
       WHERE cache_key = $1
         AND task_type = $2
         AND model_weight_version = $3
         AND expires_at > NOW()`,
      [cacheKey, taskType, MODEL_WEIGHT_VERSION]
    );

    if (exactResult.rows.length > 0) {
      const row = exactResult.rows[0];

      // Update hit statistics
      await client.query(
        `UPDATE workflow.consensus_cache
         SET cache_hit_count = cache_hit_count + 1,
             last_hit_at = NOW()
         WHERE id = $1`,
        [row.id]
      );

      await updateStats('exact_hit', 1.0);

      console.log(`[consensus-cache] EXACT HIT (key: ${cacheKey.substring(0, 12)}...)`);

      return {
        hit_type: 'exact',
        similarity: 1.0,
        consensus_result: row.consensus_result,
        cache_metadata: {
          cache_key: row.cache_key,
          created_at: row.created_at,
          expires_at: row.expires_at,
          hit_count: parseInt(row.cache_hit_count) + 1,
        },
      };
    }

    // STEP 2: Semantic similarity search (if enabled)
    if (!exactOnly) {
      const embedding = await generateEmbedding(question);

      if (!embedding) {
        // Embedding unavailable - skip semantic search
        await updateStats('miss', 0.0);
        return null;
      }

      const semanticResult = await client.query(
        `SELECT *,
                question_embedding <=> $1::vector as distance,
                1 - (question_embedding <=> $1::vector) as similarity
         FROM workflow.consensus_cache
         WHERE task_type = $2
           AND model_weight_version = $3
           AND expires_at > NOW()
           AND question_embedding IS NOT NULL
           AND 1 - (question_embedding <=> $1::vector) >= $4
         ORDER BY question_embedding <=> $1::vector
         LIMIT 1`,
        [JSON.stringify(embedding), taskType, MODEL_WEIGHT_VERSION, similarityThreshold]
      );

      if (semanticResult.rows.length > 0) {
        const row = semanticResult.rows[0];
        const similarity = parseFloat(row.similarity);

        // Update hit statistics
        await client.query(
          `UPDATE workflow.consensus_cache
           SET cache_hit_count = cache_hit_count + 1,
               last_hit_at = NOW()
           WHERE id = $1`,
          [row.id]
        );

        await updateStats('semantic_hit', similarity);

        console.log(
          `[consensus-cache] SEMANTIC HIT (similarity: ${(similarity * 100).toFixed(1)}%, ` +
          `original: "${row.question.substring(0, 50)}...")`
        );

        return {
          hit_type: 'semantic',
          similarity: similarity,
          original_question: row.question,
          consensus_result: row.consensus_result,
          cache_metadata: {
            cache_key: row.cache_key,
            created_at: row.created_at,
            expires_at: row.expires_at,
            hit_count: parseInt(row.cache_hit_count) + 1,
          },
        };
      }
    }

    // No match found
    await updateStats('miss', 0.0);
    return null;

  } finally {
    client.release();
  }
}

// ============================================================================
// CACHE STORAGE
// ============================================================================

/**
 * Store consensus result in cache
 *
 * @param {string} question - Question/prompt
 * @param {string} taskType - Task type
 * @param {Object} consensusResult - Consensus result from weighted-voting
 * @param {Object} options - Storage options
 * @param {number} options.ttlMs - Cache TTL in milliseconds (default: 1 hour)
 * @returns {Promise<Object>} Stored cache entry
 */
async function storeCache(question, taskType, consensusResult, options = {}) {
  const ttlMs = options.ttlMs || DEFAULT_CACHE_TTL_MS;

  const client = await pool.connect();
  try {
    const cacheKey = generateCacheKey(question, taskType);
    const embedding = await generateEmbedding(question);
    const expiresAt = new Date(Date.now() + ttlMs);

    const result = await client.query(
      `INSERT INTO workflow.consensus_cache
       (cache_key, question, question_embedding, task_type, consensus_result,
        model_weight_version, expires_at, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
       ON CONFLICT (cache_key) DO UPDATE SET
         consensus_result = EXCLUDED.consensus_result,
         expires_at = EXCLUDED.expires_at,
         cache_hit_count = 0,
         last_hit_at = NULL
       RETURNING id, cache_key, created_at, expires_at`,
      [
        cacheKey,
        question,
        embedding ? JSON.stringify(embedding) : null,
        taskType,
        JSON.stringify(consensusResult),
        MODEL_WEIGHT_VERSION,
        expiresAt,
      ]
    );

    const row = result.rows[0];

    console.log(
      `[consensus-cache] STORED (key: ${cacheKey.substring(0, 12)}..., ` +
      `expires: ${expiresAt.toISOString()}, embedding: ${embedding ? 'yes' : 'no'})`
    );

    return {
      cache_key: row.cache_key,
      created_at: row.created_at,
      expires_at: row.expires_at,
      has_embedding: !!embedding,
    };

  } finally {
    client.release();
  }
}

// ============================================================================
// CACHE INVALIDATION
// ============================================================================

/**
 * Invalidate cache entries
 *
 * Strategies:
 * 1. Invalidate by task_type
 * 2. Invalidate expired entries
 * 3. Invalidate all (full cache clear)
 * 4. Invalidate by model_weight_version (automatic on version change)
 *
 * @param {Object} options - Invalidation options
 * @param {string} options.taskType - Invalidate specific task type
 * @param {boolean} options.expiredOnly - Only invalidate expired entries (default: false)
 * @param {boolean} options.all - Invalidate all entries (default: false)
 * @returns {Promise<number>} Number of entries invalidated
 */
async function invalidateCache(options = {}) {
  const client = await pool.connect();
  try {
    let sql;
    let params = [];

    if (options.all) {
      // Invalidate all entries
      sql = `DELETE FROM workflow.consensus_cache`;
    } else if (options.expiredOnly) {
      // Invalidate expired entries only
      sql = `DELETE FROM workflow.consensus_cache WHERE expires_at <= NOW()`;
    } else if (options.taskType) {
      // Invalidate specific task type
      sql = `DELETE FROM workflow.consensus_cache WHERE task_type = $1`;
      params = [options.taskType];
    } else {
      // Default: invalidate old model weight versions
      sql = `DELETE FROM workflow.consensus_cache WHERE model_weight_version != $1`;
      params = [MODEL_WEIGHT_VERSION];
    }

    const result = await client.query(sql, params);
    const invalidated = result.rowCount;

    console.log(`[consensus-cache] INVALIDATED ${invalidated} entries`);

    return invalidated;

  } finally {
    client.release();
  }
}

// ============================================================================
// STATISTICS TRACKING
// ============================================================================

/**
 * Update cache statistics (daily aggregation)
 *
 * @param {string} resultType - 'exact_hit' | 'semantic_hit' | 'miss'
 * @param {number} similarity - Similarity score (1.0 for exact, 0.0 for miss)
 * @returns {Promise<void>}
 */
async function updateStats(resultType, similarity) {
  const client = await pool.connect();
  try {
    await client.query(`
      INSERT INTO workflow.consensus_cache_stats
      (date, total_lookups, exact_hits, semantic_hits, misses, avg_similarity, updated_at)
      VALUES (
        CURRENT_DATE,
        1,
        CASE WHEN $1 = 'exact_hit' THEN 1 ELSE 0 END,
        CASE WHEN $1 = 'semantic_hit' THEN 1 ELSE 0 END,
        CASE WHEN $1 = 'miss' THEN 1 ELSE 0 END,
        $2,
        NOW()
      )
      ON CONFLICT (date) DO UPDATE SET
        total_lookups = workflow.consensus_cache_stats.total_lookups + 1,
        exact_hits = workflow.consensus_cache_stats.exact_hits +
          CASE WHEN $1 = 'exact_hit' THEN 1 ELSE 0 END,
        semantic_hits = workflow.consensus_cache_stats.semantic_hits +
          CASE WHEN $1 = 'semantic_hit' THEN 1 ELSE 0 END,
        misses = workflow.consensus_cache_stats.misses +
          CASE WHEN $1 = 'miss' THEN 1 ELSE 0 END,
        avg_similarity = (
          (workflow.consensus_cache_stats.avg_similarity * workflow.consensus_cache_stats.total_lookups + $2) /
          (workflow.consensus_cache_stats.total_lookups + 1)
        ),
        hit_rate = (
          (workflow.consensus_cache_stats.exact_hits + workflow.consensus_cache_stats.semantic_hits +
            CASE WHEN $1 != 'miss' THEN 1 ELSE 0 END) * 100.0 /
          (workflow.consensus_cache_stats.total_lookups + 1)
        ),
        updated_at = NOW()
    `, [resultType, similarity]);

  } catch (err) {
    console.warn(`[consensus-cache] Failed to update stats: ${err.message}`);
  } finally {
    client.release();
  }
}

/**
 * Get cache statistics
 *
 * @param {Object} options - Query options
 * @param {number} options.days - Number of days to query (default: 7)
 * @returns {Promise<Array>} Daily statistics
 */
async function getCacheStats(options = {}) {
  const days = options.days || 7;

  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT *
       FROM workflow.consensus_cache_stats
       WHERE date >= CURRENT_DATE - $1
       ORDER BY date DESC`,
      [days]
    );

    return result.rows.map(row => ({
      date: row.date,
      total_lookups: parseInt(row.total_lookups),
      exact_hits: parseInt(row.exact_hits),
      semantic_hits: parseInt(row.semantic_hits),
      misses: parseInt(row.misses),
      hit_rate: parseFloat(row.hit_rate),
      avg_similarity: parseFloat(row.avg_similarity),
      updated_at: row.updated_at,
    }));

  } finally {
    client.release();
  }
}

/**
 * Get overall cache statistics summary
 *
 * @returns {Promise<Object>} Summary statistics
 */
async function getCacheSummary() {
  const client = await pool.connect();
  try {
    // Get today's stats
    const todayResult = await client.query(
      `SELECT * FROM workflow.consensus_cache_stats WHERE date = CURRENT_DATE`
    );

    const today = todayResult.rows[0] || {
      total_lookups: 0,
      exact_hits: 0,
      semantic_hits: 0,
      misses: 0,
      hit_rate: 0.0,
      avg_similarity: 0.0,
    };

    // Get cache size
    const sizeResult = await client.query(
      `SELECT COUNT(*) as total_entries,
              COUNT(*) FILTER (WHERE expires_at > NOW()) as active_entries,
              COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_entries,
              COUNT(*) FILTER (WHERE question_embedding IS NOT NULL) as entries_with_embedding
       FROM workflow.consensus_cache`
    );

    const size = sizeResult.rows[0];

    // Get last 7 days stats
    const weekResult = await client.query(
      `SELECT SUM(total_lookups) as total_lookups,
              SUM(exact_hits) as exact_hits,
              SUM(semantic_hits) as semantic_hits,
              SUM(misses) as misses
       FROM workflow.consensus_cache_stats
       WHERE date >= CURRENT_DATE - 7`
    );

    const week = weekResult.rows[0];
    const weekHitRate = week.total_lookups > 0
      ? ((parseInt(week.exact_hits) + parseInt(week.semantic_hits)) * 100.0 / parseInt(week.total_lookups))
      : 0.0;

    return {
      today: {
        total_lookups: parseInt(today.total_lookups),
        exact_hits: parseInt(today.exact_hits),
        semantic_hits: parseInt(today.semantic_hits),
        misses: parseInt(today.misses),
        hit_rate: parseFloat(today.hit_rate),
        avg_similarity: parseFloat(today.avg_similarity),
      },
      last_7_days: {
        total_lookups: parseInt(week.total_lookups || 0),
        exact_hits: parseInt(week.exact_hits || 0),
        semantic_hits: parseInt(week.semantic_hits || 0),
        misses: parseInt(week.misses || 0),
        hit_rate: weekHitRate,
      },
      cache_size: {
        total_entries: parseInt(size.total_entries),
        active_entries: parseInt(size.active_entries),
        expired_entries: parseInt(size.expired_entries),
        entries_with_embedding: parseInt(size.entries_with_embedding),
        embedding_coverage: size.total_entries > 0
          ? (parseInt(size.entries_with_embedding) * 100.0 / parseInt(size.total_entries))
          : 0.0,
      },
      model_weight_version: MODEL_WEIGHT_VERSION,
    };

  } finally {
    client.release();
  }
}

// ============================================================================
// INTEGRATION WITH WEIGHTED VOTING
// ============================================================================

/**
 * Wrapper for weighted voting with caching
 *
 * Automatically checks cache before running weighted voting.
 * Stores result in cache after voting completes.
 *
 * @param {string} question - Question/prompt
 * @param {Array<Object>} votes - Worker votes
 * @param {string} taskType - Task type
 * @param {Object} options - Weighted voting options + cache options
 * @param {boolean} options.useCache - Enable cache (default: true)
 * @param {boolean} options.cacheExactOnly - Use exact match only (default: false)
 * @param {number} options.cacheTtlMs - Cache TTL (default: 1 hour)
 * @returns {Promise<Object>} Weighted voting result with cache metadata
 */
async function runWeightedVotingCached(question, votes, taskType, options = {}) {
  const useCache = options.useCache !== false; // Default: true
  const cacheExactOnly = options.cacheExactOnly || false;
  const cacheTtlMs = options.cacheTtlMs || DEFAULT_CACHE_TTL_MS;

  // STEP 1: Try cache lookup
  let cacheResult = null;
  if (useCache) {
    cacheResult = await lookupCache(question, taskType, {
      exactOnly: cacheExactOnly,
      similarityThreshold: options.similarityThreshold,
    });
  }

  if (cacheResult) {
    // Cache hit - return cached result
    return {
      ...cacheResult.consensus_result,
      cache_hit: true,
      cache_metadata: {
        hit_type: cacheResult.hit_type,
        similarity: cacheResult.similarity,
        original_question: cacheResult.original_question,
        ...cacheResult.cache_metadata,
      },
    };
  }

  // STEP 2: Cache miss - run weighted voting
  const { runWeightedVoting } = require('./weighted-voting.cjs');
  const votingResult = await runWeightedVoting(votes, taskType, options);

  // STEP 3: Store result in cache
  if (useCache && votingResult.voting_result.status === 'success') {
    try {
      await storeCache(question, taskType, votingResult.voting_result, {
        ttlMs: cacheTtlMs,
      });
    } catch (err) {
      console.warn(`[consensus-cache] Failed to store result: ${err.message}`);
      // Non-fatal - continue
    }
  }

  return {
    ...votingResult.voting_result,
    cache_hit: false,
    cache_metadata: {
      hit_type: 'miss',
      stored: useCache,
    },
  };
}

// ============================================================================
// CLEANUP
// ============================================================================

/**
 * Clean up expired cache entries
 * Run periodically (e.g., daily cron job)
 *
 * @returns {Promise<number>} Number of entries cleaned up
 */
async function cleanupExpiredEntries() {
  return await invalidateCache({ expiredOnly: true });
}

/**
 * Close database connection pool
 */
async function close() {
  await pool.end();
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  lookupCache,
  storeCache,
  invalidateCache,
  cleanupExpiredEntries,

  // Statistics
  getCacheStats,
  getCacheSummary,
  updateStats,

  // Integration
  runWeightedVotingCached,

  // Utilities
  generateCacheKey,
  generateEmbedding,
  initializeSchema, // Export for testing

  // Configuration
  DEFAULT_CACHE_TTL_MS,
  DEFAULT_SIMILARITY_THRESHOLD,
  MODEL_WEIGHT_VERSION,

  // Connection
  pool,
  close,
};
