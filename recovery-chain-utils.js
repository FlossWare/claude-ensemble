/**
 * Error Recovery Chain Utilities
 *
 * Provides reusable components for implementing the error recovery chain pattern
 * across the Claude Code global skills ecosystem.
 *
 * Usage:
 *   const { tryFallbackChain, ServiceHealthCheck, TimeoutError } = require('./recovery-chain-utils.js')
 */

// ============================================================================
// CUSTOM ERROR CLASSES
// ============================================================================

class RecoveryError extends Error {
  constructor(message, context = {}) {
    super(message);
    this.name = this.constructor.name;
    this.context = context;
    this.stage = context.stage || 'unknown';
    this.recoverable = context.recoverable !== false;
    this.timestamp = Date.now();
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      stage: this.stage,
      recoverable: this.recoverable,
      timestamp: this.timestamp,
      context: this.context
    };
  }
}

class TimeoutError extends RecoveryError {
  constructor(message, operationMs) {
    super(message, { stage: 'timeout', recoverable: true });
    this.operationMs = operationMs;
  }
}

class ValidationError extends RecoveryError {
  constructor(message, fields) {
    super(message, { stage: 'validation', recoverable: false });
    this.fields = fields;
  }
}

class InsufficientResults extends RecoveryError {
  constructor(message, details) {
    super(message, { stage: 'aggregation', recoverable: true });
    this.results = details.results;
    this.errors = details.errors;
    this.minRequired = details.minRequired;
  }
}

class AllAttemptsFailedError extends RecoveryError {
  constructor(message, attempts) {
    super(message, { stage: 'fallback-chain', recoverable: false });
    this.attempts = attempts;
  }
}

class RateLimitError extends RecoveryError {
  constructor(message, retryAfterMs) {
    super(message, { stage: 'rate-limit', recoverable: true });
    this.retryAfterMs = retryAfterMs;
  }
}

class CircuitBreakerOpen extends RecoveryError {
  constructor(service, resetAtMs) {
    super(`Circuit breaker open for ${service}`, { stage: 'circuit-breaker', recoverable: true });
    this.service = service;
    this.resetAtMs = resetAtMs;
  }
}

// ============================================================================
// TIMEOUT UTILITIES
// ============================================================================

async function executeWithTimeout(fn, timeoutMs = 30000) {
  const controller = new AbortController();
  let timeoutId;

  try {
    return await Promise.race([
      fn(controller.signal),
      new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
          controller.abort();
          reject(new TimeoutError(
            `Operation exceeded ${timeoutMs}ms timeout`,
            timeoutMs
          ));
        }, timeoutMs);
      })
    ]);
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

class WorkerTimeoutTracker {
  constructor(defaultTimeoutMs = 30000) {
    this.defaultTimeoutMs = defaultTimeoutMs;
    this.overrides = new Map();
    this.history = [];
  }

  getTimeout(model) {
    if (this.overrides.has(model)) {
      return this.overrides.get(model);
    }

    // Default timeouts per model (slower models get more time)
    const defaults = {
      'opus': 45000,
      'gpt-4o': 45000,
      'sonnet': 30000,
      'haiku': 20000,
      'fable': 30000,
      'gemini': 30000
    };

    return defaults[model] || this.defaultTimeoutMs;
  }

  recordTimeout(model, actualMs, exceeded) {
    this.history.push({ model, actualMs, exceeded, timestamp: Date.now() });

    // Adjust future timeouts based on actual performance
    if (this.history.length % 10 === 0) {
      this.recalibrateTimeout(model);
    }
  }

  recalibrateTimeout(model) {
    const recent = this.history
      .filter(h => h.model === model)
      .slice(-10);

    if (recent.length === 0) return;

    const avgMs = recent.reduce((sum, h) => sum + h.actualMs, 0) / recent.length;
    const maxObserved = Math.max(...recent.map(h => h.actualMs));

    // Set timeout to 1.5x max observed (with bounds)
    const adjusted = Math.min(
      Math.max(maxObserved * 1.5, this.getTimeout(model) * 0.9),
      this.getTimeout(model) * 2
    );

    this.overrides.set(model, adjusted);
  }

  getMetrics(model) {
    const history = this.history.filter(h => h.model === model);
    const timeouts = history.filter(h => h.exceeded).length;

    return {
      attempts: history.length,
      timeouts,
      timeoutRate: history.length > 0 ? timeouts / history.length : 0,
      avgMs: history.reduce((sum, h) => sum + h.actualMs, 0) / history.length || 0
    };
  }
}

// ============================================================================
// SERVICE HEALTH CHECKS
// ============================================================================

class ServiceHealthCheck {
  constructor(config = {}) {
    this.state = new Map(); // service -> { healthy, lastCheck, failCount, resetAt }
    this.defaultConfig = {
      fastFailMs: 3000,
      backoffs: [30000, 120000, 300000, 600000], // 30s, 2m, 5m, 10m
      maxFailCount: 4
    };
    Object.assign(this.defaultConfig, config);
  }

  async checkHealth(service, checkFn, options = {}) {
    const cached = this.state.get(service);

    // Circuit breaker: if recently failed, skip check
    if (cached && !this.shouldRetry(cached)) {
      return cached.healthy;
    }

    try {
      await Promise.race([
        Promise.resolve(checkFn()),
        new Promise((_, reject) =>
          setTimeout(() => reject(new TimeoutError('Health check timeout')),
            options.fastFailMs || this.defaultConfig.fastFailMs)
        )
      ]);

      this.recordSuccess(service);
      return true;
    } catch (err) {
      this.recordFailure(service);
      return false;
    }
  }

  shouldRetry(state) {
    if (state.resetAt && Date.now() < state.resetAt) {
      return false;
    }
    return true;
  }

  recordSuccess(service) {
    this.state.set(service, {
      healthy: true,
      lastCheck: Date.now(),
      failCount: 0,
      resetAt: null
    });
  }

  recordFailure(service) {
    const current = this.state.get(service) || { failCount: 0 };
    const newFailCount = current.failCount + 1;
    const backoff = this.defaultConfig.backoffs[
      Math.min(newFailCount - 1, this.defaultConfig.backoffs.length - 1)
    ];

    this.state.set(service, {
      healthy: false,
      lastCheck: Date.now(),
      failCount: newFailCount,
      resetAt: Date.now() + backoff
    });
  }

  getState(service) {
    return this.state.get(service) || { healthy: true, failCount: 0 };
  }

  getScore(service) {
    const state = this.getState(service);
    if (state.healthy) return 100;

    // Score degrades with each failure: 80, 60, 40, 20, 0
    return Math.max(0, 100 - (state.failCount * 20));
  }
}

// ============================================================================
// FALLBACK CHAIN EXECUTION
// ============================================================================

async function tryFallbackChain(attempts, options = {}) {
  const { logFn = console.log } = options;
  const errors = [];

  for (let i = 0; i < attempts.length; i++) {
    const attempt = attempts[i];

    try {
      logFn(`Attempt ${i + 1}/${attempts.length}: ${attempt.label}`);
      const result = await attempt.fn();
      logFn(`  ✓ Success`);
      return result;
    } catch (err) {
      const errorMsg = err.message || String(err);
      errors.push({ label: attempt.label, error: errorMsg });
      logFn(`  ✗ Failed: ${errorMsg}`);

      // Escalate non-retryable errors immediately
      if (attempt.retryable === false) {
        throw err;
      }

      // Continue to next attempt
      if (i < attempts.length - 1) {
        logFn(`  → Trying fallback...`);
      }
    }
  }

  throw new AllAttemptsFailedError(
    `All ${attempts.length} recovery attempts exhausted`,
    errors
  );
}

function getFallbackChain(model) {
  const chains = {
    'gpt-4o': [
      { label: 'GPT-4o', model: 'gpt-4o', timeout: 45000, retryable: true },
      { label: 'Opus', model: 'opus', timeout: 45000, retryable: true },
      { label: 'Sonnet', model: 'sonnet', timeout: 30000, retryable: false }
    ],
    'opus': [
      { label: 'Opus', model: 'opus', timeout: 45000, retryable: true },
      { label: 'Sonnet', model: 'sonnet', timeout: 30000, retryable: true },
      { label: 'Haiku', model: 'haiku', timeout: 20000, retryable: false }
    ],
    'sonnet': [
      { label: 'Sonnet', model: 'sonnet', timeout: 30000, retryable: true },
      { label: 'Haiku', model: 'haiku', timeout: 20000, retryable: false }
    ],
    'haiku': [
      { label: 'Haiku', model: 'haiku', timeout: 20000, retryable: false }
    ],
    'fable': [
      { label: 'Fable', model: 'fable', timeout: 30000, retryable: true },
      { label: 'Opus', model: 'opus', timeout: 45000, retryable: true },
      { label: 'Sonnet', model: 'sonnet', timeout: 30000, retryable: false }
    ],
    'gemini': [
      { label: 'Gemini', model: 'gemini', timeout: 30000, retryable: true },
      { label: 'Fable', model: 'fable', timeout: 30000, retryable: true },
      { label: 'Sonnet', model: 'sonnet', timeout: 30000, retryable: false }
    ]
  };

  return chains[model] || chains['sonnet'];
}

// ============================================================================
// PARTIAL RESULTS AGGREGATION
// ============================================================================

async function gatherResultsWithPartialAcceptance(workers, options = {}) {
  const {
    minResults = 1,
    timeoutMs = 30000,
    validateFn = (r) => true,
    logFn = console.log
  } = options;

  const results = [];
  const errors = [];

  const settled = await Promise.allSettled(
    workers.map(w => executeWithTimeout(w.fn, timeoutMs))
  );

  for (let i = 0; i < settled.length; i++) {
    const outcome = settled[i];
    const worker = workers[i];

    if (outcome.status === 'fulfilled') {
      try {
        validateFn(outcome.value);
        results.push({ model: worker.model, value: outcome.value });
      } catch (err) {
        errors.push({
          model: worker.model,
          error: `Validation: ${err.message}`
        });
      }
    } else {
      errors.push({
        model: worker.model,
        error: outcome.reason.message
      });
    }
  }

  if (results.length < minResults) {
    throw new InsufficientResults(
      `Got ${results.length} valid results, need ≥${minResults}`,
      { results, errors, minRequired: minResults }
    );
  }

  const coverage = results.length / workers.length;
  if (coverage < 1.0) {
    const failedModels = errors.map(e => `${e.model}: ${e.error}`).join('; ');
    logFn(`⚠ Degraded results (${results.length}/${workers.length}): ${failedModels}`);
  }

  return { results, errors, coverage, degradationLevel: 1 - coverage };
}

// ============================================================================
// ADAPTIVE WORKER SELECTION
// ============================================================================

class AdaptiveWorkerSelection {
  constructor(allModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']) {
    this.allModels = allModels;
    this.speeds = {
      'haiku': 1,
      'sonnet': 2,
      'opus': 3,
      'fable': 2,
      'gpt-4o': 4,
      'gemini': 2
    };
  }

  selectWorkers(availableModels, failureRate = 0, options = {}) {
    const { minWorkers = 1, preferredCount = 3 } = options;

    // Scale down worker count on failures
    const targetCount = Math.max(
      minWorkers,
      Math.ceil(availableModels.length * (1 - failureRate))
    );

    // If very high failure rate, prefer fast models
    if (failureRate > 0.5) {
      return availableModels
        .sort((a, b) => this.getSpeed(a) - this.getSpeed(b))
        .slice(0, targetCount);
    }

    // Otherwise prefer balanced selection
    return availableModels.slice(0, Math.min(targetCount, preferredCount));
  }

  getSpeed(model) {
    return this.speeds[model] || 2;
  }

  buildDegradedSchema(fullSchema, degradationLevel) {
    if (degradationLevel < 0.3) return fullSchema;

    // Level 1: Keep only required fields
    if (degradationLevel < 0.6 && fullSchema.required) {
      const props = {};
      fullSchema.required.forEach(field => {
        props[field] = fullSchema.properties[field] || { type: 'string' };
      });

      return {
        ...fullSchema,
        properties: props,
        required: fullSchema.required
      };
    }

    // Level 2: Minimal schema
    return {
      type: 'object',
      properties: {
        answer: { type: 'string', description: 'Your answer' },
        confidence: {
          type: 'number',
          minimum: 0,
          maximum: 100,
          description: 'Your confidence (0-100)'
        }
      },
      required: ['answer', 'confidence']
    };
  }
}

// ============================================================================
// ERROR LEARNING TRACKER
// ============================================================================

class ErrorLearningTracker {
  constructor(options = {}) {
    this.failures = [];
    this.config = {
      maxHistory: 1000,
      metricsWindowMs: 86400000, // 24 hours
      ...options
    };
  }

  recordFailure(failure) {
    this.failures.push({
      id: Date.now().toString(),
      timestamp: Date.now(),
      ...failure,
      resolved: false,
      resolution: null
    });

    // Trim history
    if (this.failures.length > this.config.maxHistory) {
      this.failures = this.failures.slice(-this.config.maxHistory);
    }
  }

  recordResolution(failureId, resolution, success) {
    const failure = this.failures.find(f => f.id === failureId);
    if (failure) {
      failure.resolved = true;
      failure.resolution = resolution;
      failure.success = success;
      failure.resolutionTime = Date.now() - failure.timestamp;
    }
  }

  getModelReliability(model, windowMs = null) {
    const cutoff = Date.now() - (windowMs || this.config.metricsWindowMs);
    const recent = this.failures.filter(
      f => f.model === model && f.timestamp > cutoff
    );

    if (recent.length === 0) {
      return { attempts: 0, failures: 0, reliability: 1.0 };
    }

    const failed = recent.filter(f => !f.success).length;
    return {
      attempts: recent.length,
      failures: failed,
      reliability: 1 - (failed / recent.length),
      avgResolutionMs: recent
        .filter(f => f.resolutionTime)
        .reduce((sum, f) => sum + f.resolutionTime, 0) /
        recent.filter(f => f.resolutionTime).length || 0
    };
  }

  getMetrics() {
    const byStage = {};
    const byModel = {};

    this.failures.forEach(f => {
      byStage[f.stage] = (byStage[f.stage] || 0) + 1;
      byModel[f.model] = (byModel[f.model] || 0) + 1;
    });

    return {
      totalFailures: this.failures.length,
      resolvedCount: this.failures.filter(f => f.resolved).length,
      resolutionRate: this.failures.filter(f => f.resolved).length /
        Math.max(1, this.failures.length),
      byStage,
      byModel
    };
  }
}

// ============================================================================
// CIRCUIT BREAKER
// ============================================================================

class CircuitBreaker {
  constructor(options = {}) {
    this.config = {
      failureThreshold: 5,
      successThreshold: 2,
      windowMs: 60000,
      resetMs: 300000,
      ...options
    };

    this.state = new Map(); // service -> { status, failCount, successCount, resetAt }
  }

  async execute(service, fn, options = {}) {
    const state = this.getState(service);

    // If open, check if we should retry
    if (state.status === 'open') {
      if (Date.now() < state.resetAt) {
        throw new CircuitBreakerOpen(service, state.resetAt);
      }
      // Move to half-open
      this.setState(service, { status: 'half-open' });
    }

    try {
      const result = await fn();
      this.recordSuccess(service);
      return result;
    } catch (err) {
      this.recordFailure(service);
      throw err;
    }
  }

  getState(service) {
    return this.state.get(service) || {
      status: 'closed',
      failCount: 0,
      successCount: 0,
      resetAt: null
    };
  }

  setState(service, newState) {
    this.state.set(service, { ...this.getState(service), ...newState });
  }

  recordSuccess(service) {
    const state = this.getState(service);

    if (state.status === 'half-open') {
      // Transition to closed after successful retry
      this.setState(service, {
        status: 'closed',
        failCount: 0,
        successCount: 0
      });
    } else if (state.status === 'closed') {
      // Reset failure count on success
      this.setState(service, { failCount: 0 });
    }
  }

  recordFailure(service) {
    const state = this.getState(service);
    const newFailCount = state.failCount + 1;

    if (newFailCount >= this.config.failureThreshold) {
      // Trip the breaker
      this.setState(service, {
        status: 'open',
        failCount: 0,
        resetAt: Date.now() + this.config.resetMs
      });
    } else {
      this.setState(service, { failCount: newFailCount });
    }
  }

  reset(service) {
    this.state.delete(service);
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Errors
  RecoveryError,
  TimeoutError,
  ValidationError,
  InsufficientResults,
  AllAttemptsFailedError,
  RateLimitError,
  CircuitBreakerOpen,

  // Utilities
  executeWithTimeout,
  WorkerTimeoutTracker,
  ServiceHealthCheck,
  tryFallbackChain,
  getFallbackChain,
  gatherResultsWithPartialAcceptance,
  AdaptiveWorkerSelection,
  ErrorLearningTracker,
  CircuitBreaker
};
