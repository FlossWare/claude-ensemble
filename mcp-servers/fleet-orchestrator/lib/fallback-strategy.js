#!/usr/bin/env node
'use strict';

/**
 * Fallback Strategy for Fleet Orchestrator
 *
 * Decides the fallback path when operations fail.
 * Three tiers of fallback:
 *   1. Provider fallback  - Try a different API provider
 *   2. Worker fallback    - Route to a different fleet worker
 *   3. Local fallback     - Execute locally when fleet is unavailable
 *
 * Design principles (from fleet evidence: 84% reward with fallback, 24% with skip):
 *   - NEVER skip. Exhausting all fallbacks is always better than skipping.
 *   - Prefer graceful degradation over total failure.
 *   - Track which fallbacks succeed to improve future routing.
 *
 * Usage:
 *   const { FallbackStrategy, gracefulFallback } = require('./fallback-strategy');
 *   const strategy = new FallbackStrategy({ providers: [...] });
 *   const result = await gracefulFallback(error, context, strategy);
 */

/**
 * Error classification for determining the right fallback path.
 * @enum {string}
 */
const ErrorCategory = Object.freeze({
  PROVIDER_ERROR: 'PROVIDER_ERROR',       // API key invalid, quota exceeded, model unavailable
  NETWORK_ERROR: 'NETWORK_ERROR',         // Connection refused, timeout, DNS failure
  WORKER_ERROR: 'WORKER_ERROR',           // Worker node down, SSH failure, OOM
  RATE_LIMIT: 'RATE_LIMIT',              // 429 Too Many Requests
  AUTH_ERROR: 'AUTH_ERROR',               // 401/403 from provider
  VALIDATION_ERROR: 'VALIDATION_ERROR',   // Bad input, schema mismatch
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',         // Everything else
});

/**
 * Fallback action types.
 * @enum {string}
 */
const FallbackAction = Object.freeze({
  RETRY_SAME_PROVIDER: 'RETRY_SAME_PROVIDER',
  TRY_NEXT_PROVIDER: 'TRY_NEXT_PROVIDER',
  TRY_NEXT_WORKER: 'TRY_NEXT_WORKER',
  EXECUTE_LOCALLY: 'EXECUTE_LOCALLY',
  DEGRADE_QUALITY: 'DEGRADE_QUALITY',
  FAIL: 'FAIL',
});

/**
 * Default provider priority list. Lower index = higher priority.
 * Matches the fleet's API-only configuration.
 */
const DEFAULT_PROVIDERS = [
  { name: 'anthropic', models: ['claude-sonnet-4-20250514', 'claude-haiku-4-20250414'] },
  { name: 'openai', models: ['gpt-4o', 'gpt-4o-mini'] },
  { name: 'google', models: ['gemini-2.0-flash', 'gemini-2.5-pro'] },
  { name: 'openrouter', models: ['meta-llama/llama-3-70b-instruct'] },
];

/**
 * Classify an error into a category for fallback routing.
 *
 * @param {Error} error - The error to classify
 * @returns {string} ErrorCategory value
 */
function classifyError(error) {
  if (!error) return ErrorCategory.UNKNOWN_ERROR;

  const msg = (error.message || '').toLowerCase();
  const code = error.code || '';
  const status = error.statusCode || error.status || 0;

  // Auth errors
  if (status === 401 || status === 403 || /unauthorized|forbidden|invalid.?api.?key/i.test(msg)) {
    return ErrorCategory.AUTH_ERROR;
  }

  // Rate limiting
  if (status === 429 || /rate.?limit|too many requests|throttl|quota/i.test(msg)) {
    return ErrorCategory.RATE_LIMIT;
  }

  // Validation errors (not retryable via fallback)
  if (status === 400 || status === 422 || /invalid.*param|schema|validation|bad request/i.test(msg)) {
    return ErrorCategory.VALIDATION_ERROR;
  }

  // Network errors
  if (['ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT', 'ENOTFOUND', 'EPIPE', 'EAI_AGAIN'].includes(code)) {
    return ErrorCategory.NETWORK_ERROR;
  }
  if (/timeout|timed?\s*out|socket hang up|network/i.test(msg)) {
    return ErrorCategory.NETWORK_ERROR;
  }

  // Worker errors
  if (/worker|node|ssh|oom|out of memory|killed|segfault/i.test(msg)) {
    return ErrorCategory.WORKER_ERROR;
  }

  // Provider errors (5xx from APIs, model not found, etc.)
  if (status >= 500 || /model.*not.*found|service.*unavailable|internal.*error|overloaded/i.test(msg)) {
    return ErrorCategory.PROVIDER_ERROR;
  }

  return ErrorCategory.UNKNOWN_ERROR;
}

/**
 * Determine the recommended fallback actions for a given error category.
 *
 * Returns an ordered list of actions to try. The caller should attempt
 * each action in sequence until one succeeds.
 *
 * @param {string} category - ErrorCategory value
 * @param {Object} context - Execution context
 * @param {string} [context.currentProvider] - Current provider name
 * @param {string} [context.currentWorker] - Current worker ID
 * @param {string[]} [context.triedProviders] - Already-tried providers
 * @param {string[]} [context.triedWorkers] - Already-tried workers
 * @param {boolean} [context.localExecutionAvailable] - Whether local execution is possible
 * @returns {string[]} Ordered list of FallbackAction values
 */
function decideFallbackPath(category, context = {}) {
  const { triedProviders = [], triedWorkers = [], localExecutionAvailable = true } = context;

  switch (category) {
    case ErrorCategory.RATE_LIMIT:
      // Rate limited: try another provider first, then another worker
      return [
        FallbackAction.TRY_NEXT_PROVIDER,
        FallbackAction.TRY_NEXT_WORKER,
        FallbackAction.DEGRADE_QUALITY,
        ...(localExecutionAvailable ? [FallbackAction.EXECUTE_LOCALLY] : []),
      ];

    case ErrorCategory.AUTH_ERROR:
      // Auth failures on this provider are permanent: skip to another provider
      return [
        FallbackAction.TRY_NEXT_PROVIDER,
        FallbackAction.TRY_NEXT_WORKER,
        ...(localExecutionAvailable ? [FallbackAction.EXECUTE_LOCALLY] : []),
      ];

    case ErrorCategory.PROVIDER_ERROR:
      // Provider-level errors: retry once, then try others
      return [
        FallbackAction.RETRY_SAME_PROVIDER,
        FallbackAction.TRY_NEXT_PROVIDER,
        FallbackAction.TRY_NEXT_WORKER,
        ...(localExecutionAvailable ? [FallbackAction.EXECUTE_LOCALLY] : []),
      ];

    case ErrorCategory.NETWORK_ERROR:
      // Network issues: try different worker first (different route), then provider
      return [
        FallbackAction.TRY_NEXT_WORKER,
        FallbackAction.RETRY_SAME_PROVIDER,
        FallbackAction.TRY_NEXT_PROVIDER,
        ...(localExecutionAvailable ? [FallbackAction.EXECUTE_LOCALLY] : []),
      ];

    case ErrorCategory.WORKER_ERROR:
      // Worker is down: skip to another worker, then try local
      return [
        FallbackAction.TRY_NEXT_WORKER,
        FallbackAction.TRY_NEXT_PROVIDER,
        ...(localExecutionAvailable ? [FallbackAction.EXECUTE_LOCALLY] : []),
      ];

    case ErrorCategory.VALIDATION_ERROR:
      // Validation errors are not recoverable by changing provider/worker
      // Degrade quality (simpler prompt) is the only option
      return [
        FallbackAction.DEGRADE_QUALITY,
        FallbackAction.FAIL,
      ];

    case ErrorCategory.UNKNOWN_ERROR:
    default:
      // Unknown: try everything in order
      return [
        FallbackAction.RETRY_SAME_PROVIDER,
        FallbackAction.TRY_NEXT_PROVIDER,
        FallbackAction.TRY_NEXT_WORKER,
        FallbackAction.DEGRADE_QUALITY,
        ...(localExecutionAvailable ? [FallbackAction.EXECUTE_LOCALLY] : []),
      ];
  }
}

/**
 * Full fallback strategy manager.
 */
class FallbackStrategy {
  /**
   * @param {Object} [options] - Configuration
   * @param {Object[]} [options.providers] - Provider list with { name, models }
   * @param {string[]} [options.workers] - Available worker IDs
   * @param {Function|null} [options.localExecutor] - async (task) => result for local execution
   * @param {Function|null} [options.degradedExecutor] - async (task) => result for degraded execution
   * @param {Function|null} [options.onFallback] - Callback: (action, context, error) => void
   */
  constructor(options = {}) {
    this.providers = options.providers || [...DEFAULT_PROVIDERS];
    this.workers = options.workers || [];
    this.localExecutor = options.localExecutor || null;
    this.degradedExecutor = options.degradedExecutor || null;
    this.onFallback = options.onFallback || null;

    // Track fallback usage for learning
    this.stats = {
      totalFallbacks: 0,
      actionCounts: {},
      categoryDistribution: {},
      successfulFallbacks: 0,
      failedFallbacks: 0,
    };
  }

  /**
   * Select the next provider to try, excluding already-tried ones.
   *
   * @param {string[]} triedProviders - Provider names already attempted
   * @returns {Object|null} Provider object or null if none available
   */
  selectNextProvider(triedProviders = []) {
    const triedSet = new Set(triedProviders);
    for (const provider of this.providers) {
      if (!triedSet.has(provider.name)) {
        return provider;
      }
    }
    return null;
  }

  /**
   * Select the next worker to try, excluding already-tried ones.
   *
   * @param {string[]} triedWorkers - Worker IDs already attempted
   * @returns {string|null} Worker ID or null if none available
   */
  selectNextWorker(triedWorkers = []) {
    const triedSet = new Set(triedWorkers);
    for (const worker of this.workers) {
      if (!triedSet.has(worker)) {
        return worker;
      }
    }
    return null;
  }

  /**
   * Record a fallback event for statistics.
   *
   * @param {string} action - FallbackAction taken
   * @param {string} category - ErrorCategory that triggered it
   * @param {boolean} success - Whether the fallback succeeded
   */
  recordFallback(action, category, success) {
    this.stats.totalFallbacks++;
    this.stats.actionCounts[action] = (this.stats.actionCounts[action] || 0) + 1;
    this.stats.categoryDistribution[category] = (this.stats.categoryDistribution[category] || 0) + 1;

    if (success) {
      this.stats.successfulFallbacks++;
    } else {
      this.stats.failedFallbacks++;
    }
  }

  /**
   * Get fallback statistics.
   *
   * @returns {Object} Fallback usage statistics
   */
  getStats() {
    return {
      ...this.stats,
      successRate: this.stats.totalFallbacks > 0
        ? this.stats.successfulFallbacks / this.stats.totalFallbacks
        : 0,
    };
  }

  /**
   * Reset fallback statistics.
   */
  resetStats() {
    this.stats = {
      totalFallbacks: 0,
      actionCounts: {},
      categoryDistribution: {},
      successfulFallbacks: 0,
      failedFallbacks: 0,
    };
  }
}

/**
 * Top-level graceful fallback function.
 *
 * Classifies the error, determines the fallback path, and returns
 * a decision object describing what to do next.
 *
 * @param {Error} error - The error that triggered the fallback
 * @param {Object} context - Execution context
 * @param {string} [context.currentProvider] - Current provider name
 * @param {string} [context.currentWorker] - Current worker ID
 * @param {string} [context.task] - Task description for local/degraded execution
 * @param {string[]} [context.triedProviders=[]] - Already-tried providers
 * @param {string[]} [context.triedWorkers=[]] - Already-tried workers
 * @param {boolean} [context.localExecutionAvailable=true] - Whether local execution is possible
 * @param {FallbackStrategy|null} [strategy] - Strategy instance (optional, creates default if null)
 * @returns {Object} Decision object with { action, category, nextProvider, nextWorker, actions, recommendation }
 */
function gracefulFallback(error, context = {}, strategy = null) {
  const strat = strategy || new FallbackStrategy();
  const category = classifyError(error);
  const actions = decideFallbackPath(category, context);

  const triedProviders = context.triedProviders || [];
  const triedWorkers = context.triedWorkers || [];

  // Determine the specific next targets
  const nextProvider = strat.selectNextProvider(triedProviders);
  const nextWorker = strat.selectNextWorker(triedWorkers);

  // Find the first viable action
  let recommendedAction = FallbackAction.FAIL;
  for (const action of actions) {
    if (action === FallbackAction.TRY_NEXT_PROVIDER && !nextProvider) continue;
    if (action === FallbackAction.TRY_NEXT_WORKER && !nextWorker) continue;
    if (action === FallbackAction.EXECUTE_LOCALLY && !strat.localExecutor && !context.localExecutionAvailable) continue;
    if (action === FallbackAction.DEGRADE_QUALITY && !strat.degradedExecutor && !context.degradedExecutionAvailable) continue;
    recommendedAction = action;
    break;
  }

  // Build human-readable recommendation
  let recommendation;
  switch (recommendedAction) {
    case FallbackAction.RETRY_SAME_PROVIDER:
      recommendation = `Retry the same provider (${context.currentProvider || 'unknown'}) after a brief delay.`;
      break;
    case FallbackAction.TRY_NEXT_PROVIDER:
      recommendation = `Switch to provider '${nextProvider ? nextProvider.name : 'unknown'}' (models: ${nextProvider ? nextProvider.models.join(', ') : 'none'}).`;
      break;
    case FallbackAction.TRY_NEXT_WORKER:
      recommendation = `Route to worker '${nextWorker || 'unknown'}' instead of '${context.currentWorker || 'unknown'}'.`;
      break;
    case FallbackAction.EXECUTE_LOCALLY:
      recommendation = 'Execute locally on the orchestrator node. Quality may be reduced.';
      break;
    case FallbackAction.DEGRADE_QUALITY:
      recommendation = 'Degrade quality (use simpler prompt or smaller model) to complete the task.';
      break;
    case FallbackAction.FAIL:
      recommendation = 'All fallback options exhausted. Task cannot be completed.';
      break;
    default:
      recommendation = 'Unknown action.';
  }

  const decision = {
    action: recommendedAction,
    category,
    error: error.message,
    nextProvider: nextProvider ? nextProvider.name : null,
    nextProviderModels: nextProvider ? nextProvider.models : [],
    nextWorker,
    actions,
    recommendation,
    triedProviders,
    triedWorkers,
    exhausted: recommendedAction === FallbackAction.FAIL,
  };

  if (typeof strat.onFallback === 'function') {
    strat.onFallback(recommendedAction, context, error);
  }

  return decision;
}

module.exports = {
  FallbackStrategy,
  gracefulFallback,
  classifyError,
  decideFallbackPath,
  ErrorCategory,
  FallbackAction,
  DEFAULT_PROVIDERS,
};
