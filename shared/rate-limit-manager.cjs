/**
 * Rate Limit Manager - Per-Provider Request Throttling
 *
 * Tracks requests per provider per minute using sliding window counters.
 * Auto-throttles when approaching limits to prevent 429 errors.
 *
 * Provider Limits (free tiers):
 * - Groq: 30 requests/minute
 * - Perplexity: 5 requests/hour (0.083 requests/minute)
 * - OpenRouter: Various (configurable per model)
 * - Generic: 60 requests/minute (default)
 *
 * Architecture:
 * - PostgreSQL table: monitoring.rate_limits
 * - Sliding window counter (60-second window)
 * - Pre-flight check: if requests >= limit-2, wait until window resets
 * - Integrates with weighted-voting.cjs and circuit-breaker.cjs
 *
 * Usage:
 *   const { checkRateLimit, recordRequest } = require('./rate-limit-manager.cjs');
 *   await checkRateLimit('groq');  // Blocks if rate limit exceeded
 *   const result = await makeAPICall();
 *   await recordRequest('groq', true);  // Record success
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Rate limit configuration per provider
 * Format: { requests_per_minute, requests_per_hour }
 */
const RATE_LIMITS = {
  // Free tier limits
  'groq': { rpm: 30, rph: 1800, buffer: 2 },
  'perplexity': { rpm: 0.083, rph: 5, buffer: 1 },  // 5 requests/hour

  // OpenRouter models (free tier)
  'openrouter/anthropic/claude-3-haiku': { rpm: 10, rph: 100, buffer: 1 },
  'openrouter/google/gemini-flash-1.5': { rpm: 15, rph: 200, buffer: 2 },
  'openrouter/meta-llama/llama-3.1-8b-instruct': { rpm: 20, rph: 300, buffer: 2 },

  // Generic OpenRouter (conservative default)
  'openrouter': { rpm: 10, rph: 100, buffer: 2 },

  // Local models (no limit)
  'ollama': { rpm: Infinity, rph: Infinity, buffer: 0 },

  // Generic (default for unknown providers)
  'default': { rpm: 60, rph: 3600, buffer: 5 },
};

/**
 * Safety buffer (requests to keep below limit)
 * If limit is 30, we throttle at 28 (30 - buffer)
 */
const DEFAULT_BUFFER = 2;

/**
 * Sliding window duration (milliseconds)
 * Default: 60 seconds
 */
const WINDOW_DURATION_MS = 60 * 1000;

/**
 * PostgreSQL connection pool
 */
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
  console.error('[RateLimitManager] PostgreSQL pool error:', err.message);
});

// ============================================================================
// DATABASE INITIALIZATION
// ============================================================================

/**
 * Initialize rate_limits table (idempotent)
 * @returns {Promise<void>}
 */
async function initializeDatabase() {
  const client = await pool.connect();
  try {
    // Create monitoring schema if not exists
    await client.query(`CREATE SCHEMA IF NOT EXISTS monitoring`);

    // Create rate_limits table
    await client.query(`
      CREATE TABLE IF NOT EXISTS monitoring.rate_limits (
        provider VARCHAR(200) PRIMARY KEY,
        requests_last_minute INT DEFAULT 0,
        requests_last_hour INT DEFAULT 0,
        last_reset TIMESTAMPTZ DEFAULT NOW(),
        last_request TIMESTAMPTZ,
        total_requests BIGINT DEFAULT 0,
        throttled_count INT DEFAULT 0,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);

    // Create index on last_reset for efficient cleanup
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rate_limits_last_reset
      ON monitoring.rate_limits(last_reset)
    `);

    // Create request history table for sliding window
    await client.query(`
      CREATE TABLE IF NOT EXISTS monitoring.rate_limit_requests (
        id SERIAL PRIMARY KEY,
        provider VARCHAR(200) NOT NULL,
        timestamp TIMESTAMPTZ DEFAULT NOW(),
        success BOOLEAN DEFAULT TRUE,
        metadata JSONB DEFAULT '{}'::jsonb
      )
    `);

    // Create index on provider + timestamp for sliding window queries
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rlr_provider_timestamp
      ON monitoring.rate_limit_requests(provider, timestamp DESC)
    `);

    console.log('[RateLimitManager] Database initialized');
  } catch (err) {
    console.error('[RateLimitManager] Database initialization failed:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

// Initialize on module load (async, non-blocking)
initializeDatabase().catch(err => {
  console.error('[RateLimitManager] FATAL: Could not initialize database:', err.message);
});

// ============================================================================
// RATE LIMIT LOGIC
// ============================================================================

/**
 * Get rate limit configuration for a provider
 * @param {string} provider - Provider name (groq, perplexity, openrouter/model, etc.)
 * @returns {Object} Rate limit config { rpm, rph, buffer }
 */
function getRateLimitConfig(provider) {
  // Check exact match first
  if (RATE_LIMITS[provider]) {
    return RATE_LIMITS[provider];
  }

  // Check prefix match (e.g., openrouter/anthropic/claude-3-haiku → openrouter)
  const prefix = provider.split('/')[0];
  if (RATE_LIMITS[prefix]) {
    return RATE_LIMITS[prefix];
  }

  // Default
  return RATE_LIMITS.default;
}

/**
 * Get current request count in sliding window (last 60 seconds)
 * @param {string} provider - Provider name
 * @returns {Promise<number>} Request count in last 60 seconds
 */
async function getRequestCount(provider) {
  const client = await pool.connect();
  try {
    const windowStart = new Date(Date.now() - WINDOW_DURATION_MS);

    // Count requests in last 60 seconds
    const result = await client.query(`
      SELECT COUNT(*) as count
      FROM monitoring.rate_limit_requests
      WHERE provider = $1 AND timestamp >= $2
    `, [provider, windowStart]);

    return parseInt(result.rows[0].count) || 0;
  } catch (err) {
    console.error(`[RateLimitManager] Failed to get request count for ${provider}:`, err.message);
    return 0; // Fail open (don't block on DB errors)
  } finally {
    client.release();
  }
}

/**
 * Get time until rate limit window resets (milliseconds)
 * @param {string} provider - Provider name
 * @returns {Promise<number>} Milliseconds until oldest request expires from window
 */
async function getTimeUntilReset(provider) {
  const client = await pool.connect();
  try {
    const windowStart = new Date(Date.now() - WINDOW_DURATION_MS);

    // Get oldest request in current window
    const result = await client.query(`
      SELECT timestamp
      FROM monitoring.rate_limit_requests
      WHERE provider = $1 AND timestamp >= $2
      ORDER BY timestamp ASC
      LIMIT 1
    `, [provider, windowStart]);

    if (result.rows.length === 0) {
      return 0; // No requests in window - no wait needed
    }

    const oldestRequest = new Date(result.rows[0].timestamp);
    const resetTime = oldestRequest.getTime() + WINDOW_DURATION_MS;
    const now = Date.now();

    return Math.max(0, resetTime - now);
  } catch (err) {
    console.error(`[RateLimitManager] Failed to get reset time for ${provider}:`, err.message);
    return 0; // Fail open
  } finally {
    client.release();
  }
}

/**
 * Check rate limit and wait if necessary (blocking)
 *
 * Pre-flight check before making API call.
 * If requests >= limit-buffer, waits until window resets.
 *
 * @param {string} provider - Provider name
 * @param {Object} options - Options
 * @param {boolean} options.throwOnLimit - Throw error instead of waiting (default: false)
 * @returns {Promise<Object>} { allowed: boolean, wait_ms: number, current_count: number, limit: number }
 */
async function checkRateLimit(provider, options = {}) {
  const config = getRateLimitConfig(provider);
  const limit = config.rpm;
  const buffer = config.buffer || DEFAULT_BUFFER;

  // No limit (local models)
  if (limit === Infinity) {
    return { allowed: true, wait_ms: 0, current_count: 0, limit: Infinity };
  }

  const currentCount = await getRequestCount(provider);
  const effectiveLimit = limit - buffer;

  if (currentCount >= effectiveLimit) {
    const waitMs = await getTimeUntilReset(provider);

    // Update throttled count
    await incrementThrottledCount(provider);

    console.warn(
      `[RateLimitManager] Rate limit approaching for ${provider}: ${currentCount}/${limit} requests. ` +
      `Waiting ${(waitMs / 1000).toFixed(1)}s until window resets...`
    );

    if (options.throwOnLimit) {
      throw new Error(
        `Rate limit exceeded for ${provider}: ${currentCount}/${limit} requests. Wait ${(waitMs / 1000).toFixed(1)}s.`
      );
    }

    // Wait until window resets
    if (waitMs > 0) {
      await new Promise(resolve => setTimeout(resolve, waitMs + 100)); // +100ms buffer
    }

    return {
      allowed: true,
      wait_ms: waitMs,
      current_count: currentCount,
      limit: limit,
      throttled: true,
    };
  }

  return {
    allowed: true,
    wait_ms: 0,
    current_count: currentCount,
    limit: limit,
    throttled: false,
  };
}

/**
 * Record a request (after API call completes)
 * @param {string} provider - Provider name
 * @param {boolean} success - Whether request succeeded
 * @param {Object} metadata - Additional metadata (optional)
 * @returns {Promise<void>}
 */
async function recordRequest(provider, success = true, metadata = {}) {
  const client = await pool.connect();
  try {
    // Insert request record
    await client.query(`
      INSERT INTO monitoring.rate_limit_requests (provider, success, metadata)
      VALUES ($1, $2, $3)
    `, [provider, success, JSON.stringify(metadata)]);

    // Update rate_limits summary table
    await client.query(`
      INSERT INTO monitoring.rate_limits (provider, total_requests, last_request, updated_at)
      VALUES ($1, 1, NOW(), NOW())
      ON CONFLICT (provider) DO UPDATE SET
        total_requests = monitoring.rate_limits.total_requests + 1,
        last_request = NOW(),
        updated_at = NOW()
    `, [provider]);

  } catch (err) {
    console.error(`[RateLimitManager] Failed to record request for ${provider}:`, err.message);
    // Non-fatal - continue
  } finally {
    client.release();
  }
}

/**
 * Increment throttled count (internal)
 * @param {string} provider - Provider name
 * @returns {Promise<void>}
 */
async function incrementThrottledCount(provider) {
  const client = await pool.connect();
  try {
    await client.query(`
      INSERT INTO monitoring.rate_limits (provider, throttled_count, updated_at)
      VALUES ($1, 1, NOW())
      ON CONFLICT (provider) DO UPDATE SET
        throttled_count = monitoring.rate_limits.throttled_count + 1,
        updated_at = NOW()
    `, [provider]);
  } catch (err) {
    console.error(`[RateLimitManager] Failed to increment throttled count:`, err.message);
  } finally {
    client.release();
  }
}

/**
 * Cleanup old request records (older than 1 hour)
 * Run periodically to prevent table bloat
 * @returns {Promise<number>} Number of records deleted
 */
async function cleanupOldRequests() {
  const client = await pool.connect();
  try {
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);

    const result = await client.query(`
      DELETE FROM monitoring.rate_limit_requests
      WHERE timestamp < $1
    `, [oneHourAgo]);

    const deleted = result.rowCount;
    if (deleted > 0) {
      console.log(`[RateLimitManager] Cleaned up ${deleted} old request records`);
    }

    return deleted;
  } catch (err) {
    console.error('[RateLimitManager] Cleanup failed:', err.message);
    return 0;
  } finally {
    client.release();
  }
}

/**
 * Get rate limit statistics for all providers
 * @returns {Promise<Array>} Array of provider stats
 */
async function getRateLimitStats() {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT
        provider,
        total_requests,
        throttled_count,
        last_request,
        updated_at,
        metadata
      FROM monitoring.rate_limits
      ORDER BY total_requests DESC
    `);

    // Enrich with current window count
    const stats = [];
    for (const row of result.rows) {
      const currentCount = await getRequestCount(row.provider);
      const config = getRateLimitConfig(row.provider);

      stats.push({
        provider: row.provider,
        total_requests: parseInt(row.total_requests),
        throttled_count: parseInt(row.throttled_count),
        current_window_count: currentCount,
        limit: config.rpm,
        utilization_percent: config.rpm !== Infinity ? (currentCount / config.rpm * 100).toFixed(1) : 0,
        last_request: row.last_request,
      });
    }

    return stats;
  } catch (err) {
    console.error('[RateLimitManager] Failed to get stats:', err.message);
    return [];
  } finally {
    client.release();
  }
}

/**
 * Filter available providers based on rate limits
 * Returns only providers that can accept requests now
 * @param {Array<string>} providers - List of provider names
 * @returns {Promise<Array<string>>} Filtered list of available providers
 */
async function filterAvailableProviders(providers) {
  const available = [];

  for (const provider of providers) {
    const check = await checkRateLimit(provider, { throwOnLimit: false });
    if (check.allowed && !check.throttled) {
      available.push(provider);
    }
  }

  return available;
}

/**
 * Close database connection pool
 * @returns {Promise<void>}
 */
async function close() {
  await pool.end();
  console.log('[RateLimitManager] Connection pool closed');
}

// ============================================================================
// SCHEDULED CLEANUP (runs every 10 minutes)
// ============================================================================

setInterval(() => {
  cleanupOldRequests().catch(err => {
    console.error('[RateLimitManager] Scheduled cleanup failed:', err.message);
  });
}, 10 * 60 * 1000); // Every 10 minutes

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  checkRateLimit,
  recordRequest,

  // Statistics
  getRateLimitStats,
  getRequestCount,
  getTimeUntilReset,

  // Utilities
  filterAvailableProviders,
  getRateLimitConfig,
  cleanupOldRequests,

  // Lifecycle
  initializeDatabase,
  close,

  // Configuration (export for testing)
  RATE_LIMITS,
  WINDOW_DURATION_MS,
};
