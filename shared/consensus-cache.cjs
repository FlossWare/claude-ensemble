/**
 * Consensus Caching System
 *
 * Two-level caching for weighted voting consensus results:
 * - Level 1: Exact hash match (cryptographic hash of votes)
 * - Level 2: Semantic similarity (pgvector cosine distance < 0.1)
 *
 * Architecture:
 * - PostgreSQL table: workflow.consensus_cache
 * - pgvector embeddings: 1024-dim (all-mpnet-base-v2)
 * - TTL: 7 days (configurable)
 * - Target: <10ms cache hits
 *
 * Integration:
 * - Used by weighted-voting.cjs before consensus calculation
 * - Stores winning answer + metadata for reuse
 * - Reduces API costs by avoiding redundant consensus calculations
 *
 * Updated: 2026-06-29 (Building Block #4 - vote-based caching)
 */

const crypto = require('crypto');
const { Pool } = require('pg');

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Cache configuration
 */
const CACHE_CONFIG = {
  // Time-to-live for cache entries (7 days)
  ttl_days: 7,

  // Semantic similarity threshold (cosine distance < 0.1 = ~99% similar)
  semantic_threshold: 0.1,

  // Maximum votes to include in cache key (prevent huge cache keys)
  max_votes_for_key: 100,

  // Enable/disable semantic search fallback
  enable_semantic_search: true,
};

// Legacy config (backward compatibility)
const DEFAULT_CACHE_TTL_MS = CACHE_CONFIG.ttl_days * 24 * 60 * 60 * 1000;
const DEFAULT_SIMILARITY_THRESHOLD = 1.0 - CACHE_CONFIG.semantic_threshold; // Convert distance to similarity
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
        question_embedding vector(1024), -- For semantic similarity
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
 * Generate deterministic cache key from votes
 *
 * Creates SHA-256 hash of normalized vote data:
 * - Sorted by model name (deterministic order)
 * - Includes: model, answer, confidence
 * - Excludes: metadata, timestamps, IDs (non-deterministic)
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} taskType - Task type
 * @returns {string} SHA-256 hash (64 hex chars)
 */
function generateCacheKey(votes, taskType) {
  if (!votes || votes.length === 0) {
    throw new Error('Cannot generate cache key: empty votes array');
  }

  // Normalize votes for hashing (deterministic order + fields)
  const normalizedVotes = votes
    .map(v => ({
      model: v.model || 'unknown',
      answer: v.answer,
      confidence: v.confidence || 0,
    }))
    .sort((a, b) => {
      // Sort by model name first (deterministic)
      const modelCmp = a.model.localeCompare(b.model);
      if (modelCmp !== 0) return modelCmp;

      // Then by answer (JSON stringify for comparison)
      const answerCmp = JSON.stringify(a.answer).localeCompare(JSON.stringify(b.answer));
      if (answerCmp !== 0) return answerCmp;

      // Finally by confidence
      return a.confidence - b.confidence;
    });

  // Truncate if too many votes (prevent huge cache keys)
  const votesToHash = normalizedVotes.slice(0, CACHE_CONFIG.max_votes_for_key);

  // Create deterministic JSON representation
  const cachePayload = {
    task_type: taskType,
    votes: votesToHash,
    version: MODEL_WEIGHT_VERSION,
  };

  const payloadStr = JSON.stringify(cachePayload);

  // SHA-256 hash (64 hex chars)
  return crypto.createHash('sha256').update(payloadStr).digest('hex');
}

/**
 * Generate semantic fingerprint from votes
 *
 * Creates natural language summary of votes for semantic similarity:
 * - Task type
 * - Models involved
 * - Answer distribution
 *
 * Used for Level 2 semantic search.
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} taskType - Task type
 * @returns {string} Natural language summary
 */
function generateSemanticFingerprint(votes, taskType) {
  if (!votes || votes.length === 0) {
    return `Task: ${taskType}. No votes.`;
  }

  // Group by answer
  const answerGroups = {};
  votes.forEach(v => {
    const answerKey = JSON.stringify(v.answer);
    if (!answerGroups[answerKey]) {
      answerGroups[answerKey] = {
        answer: v.answer,
        models: [],
        count: 0,
      };
    }
    answerGroups[answerKey].models.push(v.model);
    answerGroups[answerKey].count += 1;
  });

  // Sort by vote count (descending)
  const sortedGroups = Object.values(answerGroups)
    .sort((a, b) => b.count - a.count);

  // Build semantic description
  const models = [...new Set(votes.map(v => v.model))].sort().join(', ');
  const answerDescriptions = sortedGroups.map(g =>
    `${g.count} votes for ${JSON.stringify(g.answer)} from [${g.models.join(', ')}]`
  ).join('; ');

  return `Task type: ${taskType}. Models: ${models}. Votes: ${answerDescriptions}.`;
}

// ============================================================================
// EMBEDDING GENERATION
// ============================================================================

/**
 * Generate embedding for question (1024-dim)
 * Uses shared embedding generator from workflow-storage-adapter
 *
 * @param {string} question - Question text
 * @returns {Promise<Array<number>|null>} 1024-dim embedding or null
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
 * Get cached consensus result (Level 1: exact match)
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} taskType - Task type
 * @returns {Promise<Object|null>} Cached result or null
 */
async function getExact(votes, taskType) {
  const cacheKey = generateCacheKey(votes, taskType);
  const now = new Date();

  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT * FROM workflow.consensus_cache
       WHERE cache_key = $1
         AND expires_at > $2
       LIMIT 1`,
      [cacheKey, now]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const cached = result.rows[0];

    // Update hit count and last hit timestamp
    await client.query(
      `UPDATE workflow.consensus_cache
       SET cache_hit_count = cache_hit_count + 1,
           last_hit_at = NOW()
       WHERE id = $1`,
      [cached.id]
    );

    console.log(`[consensus-cache] EXACT HIT: cache_key=${cacheKey.substring(0, 16)}..., age=${Math.floor((now - cached.created_at) / 1000 / 60)}min`);

    return {
      cache_hit: true,
      cache_level: 'exact',
      cache_key: cacheKey,
      cache_id: cached.id,
      hit_count: cached.cache_hit_count + 1,
      age_minutes: Math.floor((now - cached.created_at) / 1000 / 60),

      // Consensus result
      winning_answer: cached.winning_answer,
      consensus_level: cached.consensus_level,
      consensus_strength: parseFloat(cached.consensus_strength),
      total_weight: parseFloat(cached.total_weight),
      vote_count: cached.vote_count,

      // Metadata
      vote_summary: cached.vote_summary,
      created_at: cached.created_at,
    };

  } catch (err) {
    console.warn(`[consensus-cache] Exact lookup failed: ${err.message}`);
    return null;
  } finally {
    client.release();
  }
}

/**
 * Get cached consensus result (Level 2: semantic similarity)
 *
 * Falls back to semantic search if exact match not found.
 * Uses cosine distance < 0.1 threshold (very similar).
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} taskType - Task type
 * @returns {Promise<Object|null>} Cached result or null
 */
async function getSemantic(votes, taskType) {
  if (!CACHE_CONFIG.enable_semantic_search) {
    return null;
  }

  const semanticFingerprint = generateSemanticFingerprint(votes, taskType);
  const embedding = await generateEmbedding(semanticFingerprint);

  if (!embedding) {
    console.warn('[consensus-cache] Semantic search failed: embedding unavailable');
    return null;
  }

  const now = new Date();

  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT *,
              semantic_embedding <=> $1::vector as distance
       FROM workflow.consensus_cache
       WHERE task_type = $2
         AND expires_at > $3
         AND semantic_embedding IS NOT NULL
       ORDER BY semantic_embedding <=> $1::vector
       LIMIT 1`,
      [JSON.stringify(embedding), taskType, now]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const cached = result.rows[0];
    const distance = parseFloat(cached.distance);

    // Check if similarity meets threshold
    if (distance > CACHE_CONFIG.semantic_threshold) {
      console.log(`[consensus-cache] SEMANTIC MISS: closest distance=${distance.toFixed(3)} > threshold=${CACHE_CONFIG.semantic_threshold}`);
      return null;
    }

    // Update hit count and last hit timestamp
    await client.query(
      `UPDATE workflow.consensus_cache
       SET cache_hit_count = cache_hit_count + 1,
           last_hit_at = NOW()
       WHERE id = $1`,
      [cached.id]
    );

    console.log(`[consensus-cache] SEMANTIC HIT: distance=${distance.toFixed(3)}, cache_key=${cached.cache_key.substring(0, 16)}..., age=${Math.floor((now - cached.created_at) / 1000 / 60)}min`);

    return {
      cache_hit: true,
      cache_level: 'semantic',
      cache_key: cached.cache_key,
      cache_id: cached.id,
      semantic_distance: distance,
      hit_count: cached.cache_hit_count + 1,
      age_minutes: Math.floor((now - cached.created_at) / 1000 / 60),

      // Consensus result
      winning_answer: cached.winning_answer,
      consensus_level: cached.consensus_level,
      consensus_strength: parseFloat(cached.consensus_strength),
      total_weight: parseFloat(cached.total_weight),
      vote_count: cached.vote_count,

      // Metadata
      vote_summary: cached.vote_summary,
      created_at: cached.created_at,
    };

  } catch (err) {
    console.warn(`[consensus-cache] Semantic lookup failed: ${err.message}`);
    return null;
  } finally {
    client.release();
  }
}

/**
 * Lookup consensus result in cache (backward compatibility wrapper)
 *
 * @param {Array<Object>|string} votesOrQuestion - Votes array or question string
 * @param {string} taskType - Task type
 * @param {Object} options - Lookup options
 * @returns {Promise<Object|null>} Cached consensus result or null
 */
async function lookupCache(votesOrQuestion, taskType, options = {}) {
  // Detect if called with old API (question string) or new API (votes array)
  if (typeof votesOrQuestion === 'string') {
    // Old API: question-based caching (deprecated)
    console.warn('[consensus-cache] Question-based caching is deprecated. Use vote-based caching.');
  }
  const cacheKey = crypto.createHash('sha256').update(
    typeof votesOrQuestion === 'string'
      ? votesOrQuestion.trim().toLowerCase() + taskType
      : generateCacheKey(votesOrQuestion, taskType)
  ).digest('hex');

  const client = await pool.connect();
  try {
    // STEP 1: Exact match lookup

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

  // STEP 2: Cache miss - run weighted voting with explainability
  const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');
  const votingResult = await runWeightedVotingWithExplain(votes, taskType, {
    ...options,
    explain: true,  // Always generate explainability reports
    explainFormat: 'json',
    context: { workflow_execution_id: options.workflow_execution_id },
  });

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
    explainability: votingResult.explainability,  // Include explainability report
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

// ============================================================================
// NEW API (Building Block #4 - Vote-based caching)
// ============================================================================

/**
 * Consensus Cache Manager (OO API)
 */
class ConsensusCache {
  constructor() {
    this.pool = pool;
    this._ensureTableCreated = false;
  }

  async ensureTable() {
    if (this._ensureTableCreated) return;
    await initializeSchema();
    this._ensureTableCreated = true;
  }

  async getExact(votes, taskType) {
    return await getExact(votes, taskType);
  }

  async getSemantic(votes, taskType) {
    return await getSemantic(votes, taskType);
  }

  async get(votes, taskType) {
    // Level 1: Exact match (fastest)
    const exactResult = await this.getExact(votes, taskType);
    if (exactResult) {
      return exactResult;
    }

    // Level 2: Semantic similarity (slower, but flexible)
    const semanticResult = await this.getSemantic(votes, taskType);
    return semanticResult;
  }

  async set(votes, taskType, consensusResult) {
    await this.ensureTable();

    if (consensusResult.status !== 'success') {
      console.warn('[consensus-cache] Cannot cache failed consensus result');
      return null;
    }

    const cacheKey = generateCacheKey(votes, taskType);
    const semanticFingerprint = generateSemanticFingerprint(votes, taskType);
    const embedding = await generateEmbedding(semanticFingerprint);

    // Calculate expiration (TTL)
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + CACHE_CONFIG.ttl_days);

    const { winner } = consensusResult;

    // Create vote summary (store lightweight metadata instead of full votes)
    const voteSummary = {
      total_votes: consensusResult.metadata?.total_votes || votes.length,
      unique_models: [...new Set(votes.map(v => v.model))].length,
      unique_answers: consensusResult.metadata?.num_unique_answers || 0,
    };

    try {
      const result = await pool.query(
        `INSERT INTO workflow.consensus_cache
         (cache_key, question, question_embedding, task_type, consensus_result,
          model_weight_version, expires_at, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
         ON CONFLICT (cache_key) DO UPDATE SET
           consensus_result = EXCLUDED.consensus_result,
           expires_at = EXCLUDED.expires_at,
           cache_hit_count = 0,
           last_hit_at = NULL
         RETURNING id`,
        [
          cacheKey,
          semanticFingerprint, // Store fingerprint as "question"
          embedding ? JSON.stringify(embedding) : null,
          taskType,
          JSON.stringify({ winner, vote_summary: voteSummary }), // Store as consensus_result
          MODEL_WEIGHT_VERSION,
          expiresAt,
        ]
      );

      const cacheId = result.rows[0].id;
      console.log(`[consensus-cache] STORED: cache_key=${cacheKey.substring(0, 16)}..., expires_in=${CACHE_CONFIG.ttl_days}d, id=${cacheId}`);

      return cacheId;

    } catch (err) {
      console.warn(`[consensus-cache] Store failed: ${err.message}`);
      return null;
    }
  }

  async invalidate(cacheKey) {
    await this.ensureTable();

    try {
      const result = await pool.query(
        `DELETE FROM workflow.consensus_cache
         WHERE cache_key = $1
         RETURNING id`,
        [cacheKey]
      );

      if (result.rows.length > 0) {
        console.log(`[consensus-cache] INVALIDATED: cache_key=${cacheKey.substring(0, 16)}...`);
        return true;
      }

      return false;
    } catch (err) {
      console.warn(`[consensus-cache] Invalidate failed: ${err.message}`);
      return false;
    }
  }

  async cleanupExpired() {
    await this.ensureTable();

    try {
      const result = await pool.query(
        `DELETE FROM workflow.consensus_cache
         WHERE expires_at < NOW()
         RETURNING id`
      );

      const deletedCount = result.rows.length;

      if (deletedCount > 0) {
        console.log(`[consensus-cache] CLEANUP: ${deletedCount} expired entries deleted`);
      }

      return deletedCount;
    } catch (err) {
      console.warn(`[consensus-cache] Cleanup failed: ${err.message}`);
      return 0;
    }
  }

  async getStats() {
    await this.ensureTable();

    try {
      const result = await pool.query(`
        SELECT
          COUNT(*) as total_entries,
          COUNT(*) FILTER (WHERE expires_at > NOW()) as active_entries,
          COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_entries,
          SUM(cache_hit_count) as total_hits,
          AVG(cache_hit_count) as avg_hits_per_entry,
          MAX(cache_hit_count) as max_hits,
          COUNT(DISTINCT task_type) as unique_task_types,
          MIN(created_at) as oldest_entry,
          MAX(created_at) as newest_entry
        FROM workflow.consensus_cache
      `);

      const stats = result.rows[0];

      return {
        total_entries: parseInt(stats.total_entries),
        active_entries: parseInt(stats.active_entries),
        expired_entries: parseInt(stats.expired_entries),
        total_hits: parseInt(stats.total_hits || 0),
        avg_hits_per_entry: parseFloat(stats.avg_hits_per_entry || 0),
        max_hits: parseInt(stats.max_hits || 0),
        unique_task_types: parseInt(stats.unique_task_types),
        oldest_entry: stats.oldest_entry,
        newest_entry: stats.newest_entry,
      };
    } catch (err) {
      console.warn(`[consensus-cache] Stats failed: ${err.message}`);
      return null;
    }
  }

  get db() {
    return { pool };
  }
}

// Singleton instance
let _consensusCache = null;

function getConsensusCache() {
  if (!_consensusCache) {
    _consensusCache = new ConsensusCache();
  }
  return _consensusCache;
}

/**
 * Wrap weightedVoting with consensus caching
 */
async function weightedVotingWithCache(weightedVotingFn, votes, taskType, options = {}) {
  const cache = getConsensusCache();

  // Check if caching disabled
  if (options.skipCache) {
    const result = await weightedVotingFn(votes, taskType, options);
    return {
      ...result,
      cache_hit: false,
      cache_enabled: false,
    };
  }

  // Check cache
  const cached = await cache.get(votes, taskType);

  if (cached) {
    // Cache hit - return cached result
    return {
      status: 'success',
      algorithm: 'weighted_voting_cached',
      task_type: taskType,
      cache_hit: true,
      cache_level: cached.cache_level,
      cache_age_minutes: cached.age_minutes,
      cache_hit_count: cached.hit_count,

      winner: {
        answer: cached.winning_answer,
        total_weight: cached.total_weight,
        vote_count: cached.vote_count,
        consensus_strength: cached.consensus_strength,
        consensus_level: cached.consensus_level,
      },

      metadata: {
        ...cached.vote_summary,
        cache_metadata: {
          cache_key: cached.cache_key,
          cache_id: cached.cache_id,
          semantic_distance: cached.semantic_distance,
        },
      },
    };
  }

  // Cache miss - run weighted voting
  const result = await weightedVotingFn(votes, taskType, options);

  // Store result in cache (if successful)
  if (result.status === 'success') {
    await cache.set(votes, taskType, result);
  }

  return {
    ...result,
    cache_hit: false,
    cache_level: 'miss',
  };
}

module.exports = {
  // New API (Building Block #4 - vote-based caching)
  ConsensusCache,
  getConsensusCache,
  weightedVotingWithCache,
  generateSemanticFingerprint,
  CACHE_CONFIG,

  // Legacy API (question-based caching - deprecated)
  lookupCache,
  storeCache,
  invalidateCache,
  cleanupExpiredEntries,

  // Statistics
  getCacheStats,
  getCacheSummary,
  updateStats,

  // Integration (legacy)
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
