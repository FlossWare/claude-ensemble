/**
 * Intelligent Fallback Routing System
 *
 * Quality-aware fallback chains that preserve model capability levels.
 * Prevents degradation by never falling back to lower-quality models.
 *
 * Features:
 * 1. Provider equivalence mapping (Groq Llama-70B ≈ Together Llama-70B)
 * 2. Quality-tier enforcement (70B → 70B, never 70B → 8B)
 * 3. PostgreSQL tracking of fallback success rates
 * 4. Integration with circuit-breaker and weighted-voting
 * 5. Automatic fallback chain construction
 *
 * Example fallback chains:
 *   Groq Llama-70B → Together Llama-70B → DeepInfra Mixtral-8x7B
 *   OpenAI GPT-4 → Anthropic Opus → Google Gemini-Pro
 *   Groq Llama-8B → Together Llama-8B → (no further fallback)
 *
 * Quality tiers (never fall back to lower tier):
 *   - Ultra: GPT-4, Opus, Gemini-Pro (175B+ equivalent)
 *   - High: Llama-70B, Mixtral-8x7B, Sonnet (70B equivalent)
 *   - Medium: Llama-8B, Mistral-7B, Haiku (7-8B)
 *   - Low: Phi-4-mini, Gemini-Flash (2-4B)
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

// ============================================================================
// DATABASE CONNECTION
// ============================================================================

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
  console.error('[IntelligentFallback] PostgreSQL pool error:', err.message);
});

// ============================================================================
// QUALITY TIER DEFINITIONS
// ============================================================================

const QUALITY_TIERS = {
  ULTRA: 'ultra',     // 175B+ equivalent (GPT-4, Opus, Gemini-Pro)
  HIGH: 'high',       // 70B equivalent (Llama-70B, Mixtral-8x7B)
  MEDIUM: 'medium',   // 7-8B (Llama-8B, Mistral-7B)
  LOW: 'low',         // 2-4B (Phi-4-mini, Gemini-Flash)
};

const TIER_HIERARCHY = [
  QUALITY_TIERS.ULTRA,
  QUALITY_TIERS.HIGH,
  QUALITY_TIERS.MEDIUM,
  QUALITY_TIERS.LOW,
];

// ============================================================================
// MODEL CLASSIFICATION
// ============================================================================

/**
 * Map models to their quality tier based on parameter count and capability
 */
const MODEL_TO_TIER = {
  // Ultra tier (175B+ equivalent)
  'gpt-4': QUALITY_TIERS.ULTRA,
  'gpt-4o': QUALITY_TIERS.ULTRA,
  'gpt-4-turbo': QUALITY_TIERS.ULTRA,
  'opus': QUALITY_TIERS.ULTRA,
  'claude-opus': QUALITY_TIERS.ULTRA,
  'gemini-pro': QUALITY_TIERS.ULTRA,
  'gemini-1.5-pro': QUALITY_TIERS.ULTRA,

  // High tier (70B equivalent)
  'llama-70b': QUALITY_TIERS.HIGH,
  'llama-3-70b': QUALITY_TIERS.HIGH,
  'llama-3.1-70b': QUALITY_TIERS.HIGH,
  'mixtral-8x7b': QUALITY_TIERS.HIGH,
  'sonnet': QUALITY_TIERS.HIGH,
  'claude-sonnet': QUALITY_TIERS.HIGH,
  'fable': QUALITY_TIERS.HIGH,

  // Medium tier (7-8B)
  'llama-8b': QUALITY_TIERS.MEDIUM,
  'llama-3-8b': QUALITY_TIERS.MEDIUM,
  'llama-3.1-8b': QUALITY_TIERS.MEDIUM,
  'mistral-7b': QUALITY_TIERS.MEDIUM,
  'haiku': QUALITY_TIERS.MEDIUM,
  'claude-haiku': QUALITY_TIERS.MEDIUM,
  'deepseek-coder': QUALITY_TIERS.MEDIUM,

  // Low tier (2-4B)
  'phi-4-mini': QUALITY_TIERS.LOW,
  'gemini-flash': QUALITY_TIERS.LOW,
  'gemini-1.5-flash': QUALITY_TIERS.LOW,
};

/**
 * Provider equivalence groups (models that can substitute for each other)
 * Format: { model_name: [ equivalent_providers ] }
 */
const PROVIDER_EQUIVALENCE = {
  // Llama-70B providers (high tier)
  'llama-3.1-70b': [
    { provider: 'groq', model: 'llama-3.1-70b-versatile' },
    { provider: 'together', model: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo' },
    { provider: 'deepinfra', model: 'meta-llama/Meta-Llama-3.1-70B-Instruct' },
    { provider: 'fireworks', model: 'accounts/fireworks/models/llama-v3p1-70b-instruct' },
  ],

  // Llama-8B providers (medium tier)
  'llama-3.1-8b': [
    { provider: 'groq', model: 'llama-3.1-8b-instant' },
    { provider: 'together', model: 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo' },
    { provider: 'deepinfra', model: 'meta-llama/Meta-Llama-3.1-8B-Instruct' },
  ],

  // Mixtral-8x7B providers (high tier)
  'mixtral-8x7b': [
    { provider: 'groq', model: 'mixtral-8x7b-32768' },
    { provider: 'together', model: 'mistralai/Mixtral-8x7B-Instruct-v0.1' },
    { provider: 'deepinfra', model: 'mistralai/Mixtral-8x7B-Instruct-v0.1' },
  ],

  // Mistral-7B providers (medium tier)
  'mistral-7b': [
    { provider: 'together', model: 'mistralai/Mistral-7B-Instruct-v0.2' },
    { provider: 'deepinfra', model: 'mistralai/Mistral-7B-Instruct-v0.3' },
  ],

  // Claude models (no equivalents, but tier-aware fallback to similar quality)
  'opus': [
    { provider: 'anthropic', model: ''opus'' },
  ],
  'sonnet': [
    { provider: 'anthropic', model: ''sonnet'' },
  ],
  'haiku': [
    { provider: 'anthropic', model: ''haiku'' },
  ],

  // OpenAI models
  'gpt-4o': [
    { provider: 'openai', model: 'gpt-4o' },
  ],

  // Google models
  'gemini-pro': [
    { provider: 'google', model: 'gemini-1.5-pro' },
  ],
  'gemini-flash': [
    { provider: 'google', model: 'gemini-1.5-flash' },
  ],
};

// ============================================================================
// FALLBACK CHAIN CONSTRUCTION
// ============================================================================

/**
 * Get quality tier for a model
 */
function getModelTier(modelName) {
  // Normalize model name (remove provider prefix)
  const normalized = modelName.toLowerCase()
    .replace(/^(groq|together|deepinfra|fireworks|anthropic|openai|google)[-\/]/, '')
    .replace(/[-_]instruct.*$/, '')
    .replace(/[-_]turbo.*$/, '')
    .replace(/[-_]versatile.*$/, '');

  // Check exact match first
  for (const [model, tier] of Object.entries(MODEL_TO_TIER)) {
    if (normalized.includes(model) || model.includes(normalized)) {
      return tier;
    }
  }

  // Default to medium tier if unknown
  console.warn(`[IntelligentFallback] Unknown model tier for ${modelName}, defaulting to MEDIUM`);
  return QUALITY_TIERS.MEDIUM;
}

/**
 * Build fallback chain for a model
 * Rules:
 * 1. Try all equivalent providers in same tier
 * 2. Never fall back to lower tier
 * 3. Can fall back to higher tier if available
 */
function buildFallbackChain(modelName, currentProvider) {
  const chain = [];
  const tier = getModelTier(modelName);
  const tierIndex = TIER_HIERARCHY.indexOf(tier);

  // Normalize model name to find equivalents
  const baseModel = modelName.toLowerCase()
    .replace(/^(groq|together|deepinfra|fireworks|anthropic|openai|google)[-\/]/, '')
    .replace(/[-_]instruct.*$/, '')
    .replace(/[-_]turbo.*$/, '')
    .replace(/[-_]versatile.*$/, '');

  // Step 1: Add same-tier equivalent providers
  for (const [model, providers] of Object.entries(PROVIDER_EQUIVALENCE)) {
    const providerTier = getModelTier(model);
    if (providerTier === tier && (baseModel.includes(model) || model.includes(baseModel))) {
      // Add all providers except current one and those already in chain
      for (const provider of providers) {
        if (provider.provider !== currentProvider &&
            !chain.some(c => c.provider === provider.provider && c.model === provider.model)) {
          chain.push({
            ...provider,
            tier,
            reason: 'equivalent_provider',
          });
        }
      }
    }
  }

  // Step 2: Add same-tier alternatives (different model, same quality)
  for (const [model, providers] of Object.entries(PROVIDER_EQUIVALENCE)) {
    const providerTier = getModelTier(model);
    if (providerTier === tier && !baseModel.includes(model) && !model.includes(baseModel)) {
      for (const provider of providers) {
        // Exclude current provider and duplicates
        if (provider.provider !== currentProvider &&
            !chain.some(c => c.provider === provider.provider && c.model === provider.model)) {
          chain.push({
            ...provider,
            tier,
            reason: 'same_tier_alternative',
          });
        }
      }
    }
  }

  // Step 3: Add higher-tier models (upgrade path)
  for (let i = tierIndex - 1; i >= 0; i--) {
    const higherTier = TIER_HIERARCHY[i];
    for (const [model, providers] of Object.entries(PROVIDER_EQUIVALENCE)) {
      const providerTier = getModelTier(model);
      if (providerTier === higherTier) {
        for (const provider of providers) {
          // Exclude current provider and duplicates
          if (provider.provider !== currentProvider &&
              !chain.some(c => c.provider === provider.provider && c.model === provider.model)) {
            chain.push({
              ...provider,
              tier: higherTier,
              reason: 'tier_upgrade',
            });
          }
        }
      }
    }
  }

  return chain;
}

// ============================================================================
// FALLBACK EXECUTION
// ============================================================================

/**
 * Execute model call with intelligent fallback
 *
 * @param {string} modelName - Original model name
 * @param {string} provider - Original provider
 * @param {Function} executeFn - Function to execute (receives provider, model)
 * @param {Object} options - Options
 * @param {number} options.maxRetries - Max fallback attempts (default: 3)
 * @param {number} options.retryDelay - Delay between retries in ms (default: 1000)
 * @returns {Promise<Object>} - { success, result, provider, model, attempts, fallbacks }
 */
async function executeWithFallback(modelName, provider, executeFn, options = {}) {
  const {
    maxRetries = 3,
    retryDelay = 1000,
  } = options;

  const fallbackChain = buildFallbackChain(modelName, provider);
  const attempts = [];
  const tier = getModelTier(modelName);

  // Try original provider first
  attempts.push({
    provider,
    model: modelName,
    tier,
    reason: 'original',
    timestamp: new Date().toISOString(),
  });

  try {
    const result = await executeFn(provider, modelName);
    await recordFallbackSuccess(modelName, provider, tier, 0, true);
    return {
      success: true,
      result,
      provider,
      model: modelName,
      tier,
      attempts: 1,
      fallbacks: [],
    };
  } catch (originalError) {
    console.warn(`[IntelligentFallback] Original provider ${provider}/${modelName} failed:`, originalError.message);
    attempts[0].error = originalError.message;
    await recordFallbackAttempt(modelName, provider, tier, originalError.message, false);
  }

  // Try fallback chain
  const fallbacks = [];
  let lastError = null;

  for (let i = 0; i < Math.min(fallbackChain.length, maxRetries); i++) {
    const fallback = fallbackChain[i];

    if (retryDelay > 0 && i > 0) {
      await new Promise(resolve => setTimeout(resolve, retryDelay));
    }

    attempts.push({
      provider: fallback.provider,
      model: fallback.model,
      tier: fallback.tier,
      reason: fallback.reason,
      timestamp: new Date().toISOString(),
    });

    try {
      console.log(`[IntelligentFallback] Trying fallback ${i + 1}/${maxRetries}: ${fallback.provider}/${fallback.model} (${fallback.reason})`);
      const result = await executeFn(fallback.provider, fallback.model);

      fallbacks.push({
        from: { provider, model: modelName },
        to: { provider: fallback.provider, model: fallback.model },
        reason: fallback.reason,
        success: true,
      });

      await recordFallbackSuccess(fallback.model, fallback.provider, fallback.tier, i + 1, true);

      return {
        success: true,
        result,
        provider: fallback.provider,
        model: fallback.model,
        tier: fallback.tier,
        attempts: attempts.length,
        fallbacks,
        originalModel: modelName,
        originalProvider: provider,
      };
    } catch (error) {
      console.warn(`[IntelligentFallback] Fallback ${fallback.provider}/${fallback.model} failed:`, error.message);
      lastError = error;
      attempts[attempts.length - 1].error = error.message;

      fallbacks.push({
        from: { provider, model: modelName },
        to: { provider: fallback.provider, model: fallback.model },
        reason: fallback.reason,
        success: false,
        error: error.message,
      });

      await recordFallbackAttempt(fallback.model, fallback.provider, fallback.tier, error.message, false);
    }
  }

  // All attempts failed
  return {
    success: false,
    error: lastError,
    provider,
    model: modelName,
    tier,
    attempts: attempts.length,
    fallbacks,
    allAttempts: attempts,
  };
}

// ============================================================================
// DATABASE TRACKING
// ============================================================================

/**
 * Record fallback attempt in PostgreSQL
 */
async function recordFallbackAttempt(model, provider, tier, error, success) {
  try {
    await pool.query(`
      INSERT INTO monitoring.fallback_attempts
      (model, provider, tier, error_message, success, timestamp)
      VALUES ($1, $2, $3, $4, $5, NOW())
    `, [model, provider, tier, error, success]);
  } catch (err) {
    console.error('[IntelligentFallback] Failed to record attempt:', err.message);
  }
}

/**
 * Record successful fallback
 */
async function recordFallbackSuccess(model, provider, tier, fallbackDepth, success) {
  try {
    await pool.query(`
      INSERT INTO monitoring.fallback_success
      (model, provider, tier, fallback_depth, success, timestamp)
      VALUES ($1, $2, $3, $4, $5, NOW())
    `, [model, provider, tier, fallbackDepth, success]);
  } catch (err) {
    console.error('[IntelligentFallback] Failed to record success:', err.message);
  }
}

/**
 * Get fallback statistics for a model/provider
 */
async function getFallbackStats(model = null, provider = null, hours = 24) {
  try {
    const params = [];
    let whereClause = 'WHERE timestamp > NOW() - INTERVAL \'1 hour\' * $1';
    params.push(hours);

    if (model) {
      whereClause += ' AND model = $' + (params.length + 1);
      params.push(model);
    }

    if (provider) {
      whereClause += ' AND provider = $' + (params.length + 1);
      params.push(provider);
    }

    const result = await pool.query(`
      SELECT
        model,
        provider,
        tier,
        COUNT(*) as total_attempts,
        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
        SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
      FROM monitoring.fallback_attempts
      ${whereClause}
      GROUP BY model, provider, tier
      ORDER BY total_attempts DESC
    `, params);

    return result.rows;
  } catch (err) {
    console.error('[IntelligentFallback] Failed to get stats:', err.message);
    return [];
  }
}

/**
 * Get best fallback provider for a model based on historical success
 */
async function getBestFallbackProvider(baseModel, hours = 168) {
  try {
    const tier = getModelTier(baseModel);
    const result = await pool.query(`
      SELECT
        provider,
        model,
        COUNT(*) as attempts,
        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate,
        AVG(fallback_depth) as avg_depth
      FROM monitoring.fallback_success
      WHERE tier = $1
        AND timestamp > NOW() - INTERVAL '1 hour' * $2
      GROUP BY provider, model
      HAVING COUNT(*) >= 5
      ORDER BY success_rate DESC, avg_depth ASC
      LIMIT 5
    `, [tier, hours]);

    return result.rows;
  } catch (err) {
    console.error('[IntelligentFallback] Failed to get best provider:', err.message);
    return [];
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Core functionality
  executeWithFallback,
  buildFallbackChain,
  getModelTier,

  // Statistics
  getFallbackStats,
  getBestFallbackProvider,

  // Constants
  QUALITY_TIERS,
  TIER_HIERARCHY,
  MODEL_TO_TIER,
  PROVIDER_EQUIVALENCE,

  // Database
  pool,
};
