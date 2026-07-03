/**
 * Get Consensus Models from Orchestrator
 *
 * Helper function for workflows to query orchestrator for optimal model selection.
 * Auto-detects Red Hat proprietary context and adjusts model count accordingly.
 */

import { DEFAULT_MODELS, ANTHROPIC_MODELS } from './model-constants.js';

// Rate limiting for orchestrator calls
let _rlm = null;
function _getRLM() {
  if (_rlm === undefined) return null;
  if (!_rlm) { try { _rlm = require('./rate-limit-manager.cjs'); } catch (_e) { _rlm = undefined; } }
  return _rlm || null;
}

async function rateLimitedFetch(provider, url, options) {
  const rlm = _getRLM();
  if (rlm) { try { await rlm.checkRateLimit(provider); } catch (_e) { /* fail open */ } }
  const start = Date.now();
  try {
    const response = await fetch(url, options);
    if (rlm) { rlm.recordRequest(provider, response.ok, { url, duration_ms: Date.now() - start }).catch(() => {}); }
    return response;
  } catch (error) {
    if (rlm) { rlm.recordRequest(provider, false, { url, error: error.message, duration_ms: Date.now() - start }).catch(() => {}); }
    throw error;
  }
}

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || 'http://pi-02:8888';

// 5-minute cache for orchestrator responses
const CACHE_TTL_MS = 5 * 60 * 1000;
const CACHE_MAX_SIZE = 100;
const cache = new Map();
let callCounter = 0;

/**
 * Evict expired cache entries
 */
function evictExpiredEntries() {
  const now = Date.now();
  for (const [key, value] of cache.entries()) {
    if (now - value.timestamp >= CACHE_TTL_MS) {
      cache.delete(key);
    }
  }
}

/**
 * Enforce LRU eviction when cache exceeds max size
 */
function enforceCacheLimit() {
  if (cache.size > CACHE_MAX_SIZE) {
    // Remove oldest entries (first entries in Map are oldest)
    const toRemove = cache.size - CACHE_MAX_SIZE;
    let removed = 0;
    for (const key of cache.keys()) {
      if (removed >= toRemove) break;
      cache.delete(key);
      removed++;
    }
  }
}

/**
 * Generate cache key from request parameters
 */
function getCacheKey(taskType, modelCount, isRedHat) {
  return `${taskType}:${modelCount}:${isRedHat}`;
}

/**
 * Get models for multi-AI consensus via orchestrator
 *
 * @param {Object} options
 * @param {string} options.taskType - Type of task (code-review, general, etc.)
 * @param {string} options.task - Description of the task
 * @param {number} options.count - Number of models to select
 * @returns {Promise<string[]>} Array of model names
 */
export async function getConsensusModels(options = {}) {
  const {
    taskType = 'general',
    task = '',
    count = null  // Auto-determine based on context
  } = options;

  // Auto-detect Red Hat proprietary context
  const cwd = process.cwd() || '';
  const isRedHat = cwd.includes('/redhat/') || cwd.includes('/rh/');

  // Red Hat: 3 models (compliance), Non-proprietary: 6 models (quality)
  const modelCount = count || (isRedHat ? 3 : 6);

  // Evict expired entries periodically (every 10th call to avoid overhead)
  // Deterministic check for workflow resumption compatibility
  callCounter++;
  if (callCounter > 1000000) callCounter = 0;
  if (callCounter % 10 === 0) {
    evictExpiredEntries();
  }

  // Check cache first
  const cacheKey = getCacheKey(taskType, modelCount, isRedHat);
  const cached = cache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    console.log(`[orchestrator] Using cached models: ${cached.models.join(', ')}`);
    return cached.models;
  }

  try {
    // Query orchestrator Thompson Sampling endpoint
    const response = await rateLimitedFetch('orchestrator', `${ORCHESTRATOR_URL}/route-thompson`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        taskType,
        task,
        count: modelCount,
        constraints: {
          diversity: true,
          onlyAnthropic: isRedHat,  // Red Hat compliance
          maxCost: isRedHat ? 0.10 : 0.30
        }
      }),
      signal: AbortSignal.timeout(5000)  // 5s timeout
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const routing = await response.json();

    if (routing.models && Array.isArray(routing.models) && routing.models.length > 0) {
      console.log(`[orchestrator] Selected ${routing.models.length} models: ${routing.models.join(', ')}`);

      // Cache the successful response
      cache.set(cacheKey, {
        models: routing.models,
        timestamp: Date.now()
      });

      // Enforce cache size limit (LRU eviction)
      enforceCacheLimit();

      return routing.models;
    }

    throw new Error('No models returned from orchestrator');
  } catch (error) {
    // Graceful fallback if orchestrator unavailable
    console.log(`[orchestrator] Unavailable (${error.message}), using defaults`);

    // Use shared constants instead of hardcoded values
    return isRedHat ? ANTHROPIC_MODELS : DEFAULT_MODELS;
  }
}

/**
 * Record feedback to orchestrator after task completion
 *
 * @param {string} model - Model that executed the task
 * @param {Object} feedback - Task outcome
 * @param {boolean} feedback.success - Task succeeded
 * @param {number} feedback.quality - Quality score 0-1
 * @param {number} feedback.cost - Cost in USD
 * @param {number} feedback.duration - Duration in ms
 * @param {string} feedback.taskType - Type of task
 */
export async function recordFeedback(model, feedback) {
  try {
    await rateLimitedFetch('orchestrator', `${ORCHESTRATOR_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, ...feedback }),
      signal: AbortSignal.timeout(3000)
    });
  } catch (error) {
    // Silent failure - don't block workflow if feedback fails
    console.log(`[orchestrator] Feedback failed: ${error.message}`);
  }
}
