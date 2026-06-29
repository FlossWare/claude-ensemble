#!/usr/bin/env node
/**
 * Retry utilities with exponential backoff, jitter, total timeout tracking,
 * non-retryable error filtering, and circuit breaker with atomic counters
 *
 * Features:
 * - Skip retrying non-retryable HTTP errors (401, 403, 400, 404, 405, 409, 422)
 * - Exponential backoff with configurable jitter (0-100%)
 * - Total timeout tracking across all retry attempts
 * - Circuit breaker with atomic state transitions (epoch-guarded, no race conditions)
 * - Configurable retry predicate for custom filtering
 * - Detailed attempt logging with elapsed time
 */

'use strict';

// ---------- Non-retryable status codes ----------

const NON_RETRYABLE_STATUS_CODES = new Set([
  400, // Bad Request - malformed input won't fix itself
  401, // Unauthorized - missing/invalid credentials
  403, // Forbidden - permission denied
  404, // Not Found - resource doesn't exist
  405, // Method Not Allowed
  409, // Conflict - needs client-side resolution
  422, // Unprocessable Entity - validation error
]);

/**
 * Determine whether an error is retryable.
 * Returns false for 400, 401, 403, 404, 405, 409, 422 errors.
 *
 * @param {Error} error
 * @returns {boolean}
 */
function isRetryable(error) {
  // Explicit statusCode / status on the error object
  const status = error.statusCode || error.status;

  if (typeof status === 'number' && NON_RETRYABLE_STATUS_CODES.has(status)) {
    return false;
  }

  // HTTP response attached to the error (e.g. axios, got, node-fetch wrappers)
  if (error.response && typeof error.response.status === 'number') {
    if (NON_RETRYABLE_STATUS_CODES.has(error.response.status)) {
      return false;
    }
  }

  // String code check for network errors (always retryable)
  const code = error.code;
  if (typeof code === 'string') {
    const retryableNetworkCodes = new Set([
      'ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT', 'EPIPE',
      'EHOSTUNREACH', 'ENETUNREACH', 'EAI_AGAIN',
    ]);
    if (retryableNetworkCodes.has(code)) {
      return true;
    }
  }

  // Default: retryable (transient errors, 5xx, timeouts, etc.)
  return true;
}

/**
 * Extract a human-readable status from an error for logging.
 * @param {Error} error
 * @returns {string|number}
 */
function getErrorStatus(error) {
  return error.statusCode || error.status ||
         (error.response && error.response.status) || 'unknown';
}

// ---------- Circuit Breaker with Atomic Counters ----------

const CB_CLOSED = 'closed';
const CB_OPEN = 'open';
const CB_HALF_OPEN = 'half_open';

class CircuitBreaker {
  /**
   * @param {Object} options
   * @param {number} options.failureThreshold  - Failures before opening (default 5)
   * @param {number} options.resetTimeoutMs    - Time before half-open probe (default 60000)
   * @param {number} options.successThreshold  - Successes in half-open to close (default 2)
   */
  constructor(options = {}) {
    this.failureThreshold = options.failureThreshold || 5;
    this.resetTimeoutMs = options.resetTimeoutMs || 60000;
    this.successThreshold = options.successThreshold || 2;

    // --- Atomic state ---
    // All mutations go through _transition() which bumps a monotonic epoch.
    // Concurrent callers that read a stale epoch get a no-op because
    // _transition captures the epoch *before* the mutation.
    this._state = CB_CLOSED;
    this._failures = 0;
    this._successes = 0;
    this._openedAt = null;
    this._halfOpenProbeActive = false;
    this._epoch = 0;
  }

  get state() { return this._state; }
  get failures() { return this._failures; }

  /**
   * Atomic state transition.  Captures epoch before mutation; concurrent
   * callers that started with a different epoch become stale.
   *
   * Returns false if the epoch changed between the caller's snapshot and
   * the mutation (stale -- the mutation was skipped).
   *
   * @param {Function} mutator  (currentEpoch) => void  -- must be synchronous
   * @param {number|null} expectedEpoch  If provided, only mutate if epoch matches
   * @returns {boolean} Whether the mutation was applied
   */
  _transition(mutator, expectedEpoch = null) {
    if (expectedEpoch !== null && this._epoch !== expectedEpoch) {
      return false; // Stale -- another transition happened first
    }
    mutator(this._epoch);
    this._epoch++;
    return true;
  }

  /**
   * Record a successful call.  Resets failure count (closed) or increments
   * success count toward closing (half-open).
   */
  recordSuccess() {
    const snapshot = this._epoch;
    this._transition(() => {
      if (this._state === CB_HALF_OPEN) {
        this._successes++;
        if (this._successes >= this.successThreshold) {
          this._state = CB_CLOSED;
          this._failures = 0;
          this._successes = 0;
          this._halfOpenProbeActive = false;
          this._openedAt = null;
        }
      } else if (this._state === CB_CLOSED) {
        // Gradual recovery: decrement failure count on success
        this._failures = Math.max(0, this._failures - 1);
      }
    }, snapshot);
  }

  /**
   * Record a failed call.  Increments failure count and opens the breaker
   * if threshold is exceeded.
   */
  recordFailure() {
    const snapshot = this._epoch;
    this._transition(() => {
      if (this._state === CB_HALF_OPEN) {
        // Probe failed -- reopen
        this._state = CB_OPEN;
        this._openedAt = Date.now();
        this._successes = 0;
        this._halfOpenProbeActive = false;
      } else {
        this._failures++;
        if (this._failures >= this.failureThreshold) {
          this._state = CB_OPEN;
          this._openedAt = Date.now();
        }
      }
    }, snapshot);
  }

  /**
   * Check whether a call is allowed through the breaker.
   * @returns {boolean}
   */
  allowRequest() {
    if (this._state === CB_CLOSED) {
      return true;
    }

    if (this._state === CB_OPEN) {
      const elapsed = Date.now() - (this._openedAt || 0);
      if (elapsed >= this.resetTimeoutMs) {
        // Transition to half-open atomically -- only one probe at a time
        if (!this._halfOpenProbeActive) {
          const snapshot = this._epoch;
          const applied = this._transition(() => {
            this._state = CB_HALF_OPEN;
            this._successes = 0;
            this._halfOpenProbeActive = true;
          }, snapshot);
          return applied;
        }
        return false; // Another probe is already in flight
      }
      return false;
    }

    // CB_HALF_OPEN: allow only if no other probe is active
    if (!this._halfOpenProbeActive) {
      const snapshot = this._epoch;
      return this._transition(() => {
        this._halfOpenProbeActive = true;
      }, snapshot);
    }
    return false;
  }

  /**
   * Force-reset the breaker to closed state.
   */
  reset() {
    this._transition(() => {
      this._state = CB_CLOSED;
      this._failures = 0;
      this._successes = 0;
      this._openedAt = null;
      this._halfOpenProbeActive = false;
    });
  }

  toJSON() {
    return {
      state: this._state,
      failures: this._failures,
      successes: this._successes,
      openedAt: this._openedAt,
      epoch: this._epoch,
    };
  }
}

// ---------- RetryWithTimeout (enhanced with filtering + circuit breaker) ----------

class RetryWithTimeout {
  /**
   * @param {Object} options
   * @param {number}   options.maxRetries        - Max retry attempts (default 3)
   * @param {number}   options.initialBackoffMs  - First backoff delay (default 1000)
   * @param {number}   options.maxBackoffMs      - Backoff ceiling (default 30000)
   * @param {number}   options.totalTimeoutMs    - Total time budget (default 120000)
   * @param {number}   options.jitterPercent     - Jitter 0-100 (default 10)
   * @param {Function} options.isRetryable       - Custom predicate (error) => boolean
   * @param {CircuitBreaker} options.circuitBreaker - Optional shared circuit breaker
   * @param {Object}   options.logger            - Logger with .log/.warn/.error
   */
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || 3;
    this.initialBackoffMs = options.initialBackoffMs || 1000;
    this.maxBackoffMs = options.maxBackoffMs || 30000;
    this.totalTimeoutMs = options.totalTimeoutMs || 120000;
    this.jitterPercent = options.jitterPercent || 10;
    this.retryPredicate = options.isRetryable || isRetryable;
    this.circuitBreaker = options.circuitBreaker || null;
    this.logger = options.logger || console;
  }

  /**
   * Execute function with retry, filtering, circuit breaker, and total timeout
   * @param {Function} fn - Async function to execute
   * @param {Object} context - Context passed to function
   * @returns {Promise<Object>}
   */
  async execute(fn, context = {}) {
    const startTime = Date.now();
    let lastError = null;
    let attempt = 0;

    while (attempt <= this.maxRetries) {
      attempt++;
      const elapsedMs = Date.now() - startTime;

      // Check total timeout BEFORE attempting
      if (elapsedMs >= this.totalTimeoutMs) {
        this.logger.warn(`[Retry] Total timeout (${this.totalTimeoutMs}ms) exceeded after ${elapsedMs}ms and ${attempt - 1} attempts`);
        return {
          success: false,
          result: null,
          attempts: attempt - 1,
          totalElapsedMs: elapsedMs,
          timedOut: true,
          error: lastError || new Error('Total timeout exceeded before attempt'),
          message: `Timeout after ${elapsedMs}ms (limit: ${this.totalTimeoutMs}ms)`
        };
      }

      // Circuit breaker gate
      if (this.circuitBreaker && !this.circuitBreaker.allowRequest()) {
        return {
          success: false,
          result: null,
          attempts: attempt - 1,
          totalElapsedMs: Date.now() - startTime,
          timedOut: false,
          strategy: 'circuit_breaker_rejected',
          error: lastError || new Error('Circuit breaker open'),
          skippedReason: `Circuit breaker ${this.circuitBreaker.state} -- request rejected`,
          message: `Circuit breaker ${this.circuitBreaker.state}`
        };
      }

      try {
        this.logger.log(`[Retry] Attempt ${attempt}/${this.maxRetries + 1} (elapsed: ${elapsedMs}ms)`);
        const result = await fn(context);

        // Success -- record in circuit breaker
        if (this.circuitBreaker) this.circuitBreaker.recordSuccess();

        return {
          success: true,
          result,
          attempts: attempt,
          totalElapsedMs: Date.now() - startTime,
          timedOut: false,
          strategy: attempt === 1 ? 'primary' : 'retry'
        };
      } catch (error) {
        lastError = error;
        const currentElapsed = Date.now() - startTime;
        this.logger.warn(`[Retry] Attempt ${attempt} failed after ${currentElapsed}ms: ${error.message}`);

        // Record failure in circuit breaker
        if (this.circuitBreaker) this.circuitBreaker.recordFailure();

        // --- Retry filtering: skip retrying non-retryable errors ---
        if (!this.retryPredicate(error)) {
          const status = getErrorStatus(error);
          this.logger.warn(
            `[Retry] Non-retryable error (status ${status}): ${error.message} -- skipping remaining retries`
          );
          return {
            success: false,
            result: null,
            attempts: attempt,
            totalElapsedMs: currentElapsed,
            timedOut: false,
            strategy: 'non_retryable',
            error,
            skippedReason: `HTTP ${status} is non-retryable (401/403/400 class)`,
            message: `Non-retryable error: HTTP ${status}`
          };
        }

        // Don't sleep if this was the last attempt or if timeout imminent
        if (attempt <= this.maxRetries) {
          const backoffMs = this.calculateBackoff(attempt);
          const remainingTimeMs = this.totalTimeoutMs - currentElapsed;

          if (backoffMs >= remainingTimeMs) {
            this.logger.warn(`[Retry] Backoff (${backoffMs}ms) would exceed timeout (${remainingTimeMs}ms remaining) - stopping`);
            return {
              success: false,
              result: null,
              attempts: attempt,
              totalElapsedMs: currentElapsed,
              timedOut: true,
              error: lastError,
              message: `Insufficient time for next retry (${remainingTimeMs}ms remaining, need ${backoffMs}ms)`
            };
          }

          this.logger.log(`[Retry] Backing off ${backoffMs}ms (${remainingTimeMs}ms remaining)...`);
          await this.sleep(backoffMs);
        }
      }
    }

    // All retries exhausted
    const finalElapsed = Date.now() - startTime;
    return {
      success: false,
      result: null,
      attempts: this.maxRetries + 1,
      totalElapsedMs: finalElapsed,
      timedOut: false,
      strategy: 'exhausted',
      error: lastError,
      message: `All ${this.maxRetries + 1} attempts exhausted after ${finalElapsed}ms`
    };
  }

  /**
   * Calculate backoff with exponential growth and jitter
   * @param {number} attempt - Current attempt number (1-indexed)
   * @returns {number} Backoff time in milliseconds
   */
  calculateBackoff(attempt) {
    const exponentialMs = this.initialBackoffMs * Math.pow(2, attempt - 1);
    const cappedMs = Math.min(exponentialMs, this.maxBackoffMs);
    const jitterRange = cappedMs * (this.jitterPercent / 100);
    const jitterMs = (Math.random() * 2 - 1) * jitterRange;
    return Math.max(0, Math.round(cappedMs + jitterMs));
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ---------- Standalone retryWithFilter function ----------

/**
 * Execute an async function with retry + circuit breaker (standalone, no class needed).
 *
 * @param {Function} fn                   - Async function to execute
 * @param {Object}   options
 * @param {number}   options.maxRetries        - Max retry attempts (default 3)
 * @param {number}   options.initialBackoffMs  - First backoff delay (default 1000)
 * @param {number}   options.maxBackoffMs      - Backoff ceiling (default 30000)
 * @param {number}   options.jitterFactor      - Jitter 0-1 (default 0.2)
 * @param {Function} options.isRetryable       - Custom predicate (error) => boolean
 * @param {CircuitBreaker} options.circuitBreaker - Optional shared breaker
 * @param {Object}   options.logger            - Logger with .log/.warn/.error
 * @returns {Promise<Object>}
 */
async function retryWithFilter(fn, options = {}) {
  const {
    maxRetries = 3,
    initialBackoffMs = 1000,
    maxBackoffMs = 30000,
    jitterFactor = 0.2,
    isRetryable: retryPredicate = isRetryable,
    circuitBreaker = null,
    logger = console,
  } = options;

  let lastError = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    // Circuit breaker gate
    if (circuitBreaker && !circuitBreaker.allowRequest()) {
      return {
        success: false,
        result: null,
        attempts: attempt,
        strategy: 'circuit_breaker_rejected',
        error: lastError || new Error('Circuit breaker open'),
        skippedReason: `Circuit breaker ${circuitBreaker.state} -- request rejected`,
      };
    }

    // Backoff (skip on first attempt)
    if (attempt > 0) {
      const base = Math.min(initialBackoffMs * Math.pow(2, attempt - 1), maxBackoffMs);
      const jitter = base * jitterFactor * Math.random();
      const delay = Math.round(base + jitter);
      logger.log && logger.log(`[retry] attempt ${attempt + 1}/${maxRetries + 1} after ${delay}ms backoff`);
      await new Promise(r => setTimeout(r, delay));
    }

    try {
      const result = await fn();
      if (circuitBreaker) circuitBreaker.recordSuccess();

      return {
        success: true,
        result,
        attempts: attempt + 1,
        strategy: attempt === 0 ? 'primary' : 'retry',
      };
    } catch (error) {
      lastError = error;
      if (circuitBreaker) circuitBreaker.recordFailure();

      // Check if this error is retryable
      if (!retryPredicate(error)) {
        const status = getErrorStatus(error);
        logger.warn && logger.warn(
          `[retry] non-retryable error (status ${status}): ${error.message} -- skipping remaining retries`
        );
        return {
          success: false,
          result: null,
          attempts: attempt + 1,
          strategy: 'non_retryable',
          error,
          skippedReason: `HTTP ${status} is non-retryable (401/403/400 class)`,
        };
      }

      if (attempt < maxRetries) {
        logger.warn && logger.warn(
          `[retry] attempt ${attempt + 1} failed (retryable): ${error.message}`
        );
      }
    }
  }

  return {
    success: false,
    result: null,
    attempts: maxRetries + 1,
    strategy: 'exhausted',
    error: lastError,
  };
}

// ---------- Exports ----------

module.exports = {
  RetryWithTimeout,
  retryWithFilter,
  CircuitBreaker,
  isRetryable,
  getErrorStatus,
  NON_RETRYABLE_STATUS_CODES,
  CB_CLOSED,
  CB_OPEN,
  CB_HALF_OPEN,
};

// ---------- CLI self-test ----------

if (require.main === module) {
  (async () => {
    let passed = 0;
    let failed = 0;

    function assert(condition, label) {
      if (condition) {
        console.log(`  PASS: ${label}`);
        passed++;
      } else {
        console.log(`  FAIL: ${label}`);
        failed++;
      }
    }

    const silent = { log() {}, warn() {}, error() {} };

    // Test 1: 401 skips retries immediately
    console.log('--- Test 1: 401 skips retries ---');
    const r1 = await retryWithFilter(
      () => { const e = new Error('Unauthorized'); e.statusCode = 401; throw e; },
      { maxRetries: 5, logger: silent }
    );
    assert(r1.attempts === 1, 'Should only attempt once for 401');
    assert(r1.strategy === 'non_retryable', 'Strategy should be non_retryable');

    // Test 2: 403 skips retries
    console.log('--- Test 2: 403 skips retries ---');
    const r2 = await retryWithFilter(
      () => { const e = new Error('Forbidden'); e.statusCode = 403; throw e; },
      { maxRetries: 3, logger: silent }
    );
    assert(r2.attempts === 1, 'Should only attempt once for 403');

    // Test 3: 400 skips retries
    console.log('--- Test 3: 400 skips retries ---');
    const r3 = await retryWithFilter(
      () => { const e = new Error('Bad Request'); e.status = 400; throw e; },
      { maxRetries: 3, logger: silent }
    );
    assert(r3.attempts === 1, 'Should only attempt once for 400');

    // Test 4: 500 retries until exhausted
    console.log('--- Test 4: 500 retries until exhausted ---');
    const r4 = await retryWithFilter(
      () => { const e = new Error('Internal Server Error'); e.statusCode = 500; throw e; },
      { maxRetries: 2, initialBackoffMs: 10, logger: silent }
    );
    assert(r4.attempts === 3, 'Should attempt 3 times (1 + 2 retries)');
    assert(r4.strategy === 'exhausted', 'Strategy should be exhausted');

    // Test 5: circuit breaker opens after threshold
    console.log('--- Test 5: circuit breaker opens ---');
    const cb3 = new CircuitBreaker({ failureThreshold: 2, resetTimeoutMs: 200 });
    cb3.recordFailure();
    cb3.recordFailure();
    assert(cb3.state === CB_OPEN, 'Breaker should be open after 2 failures');
    assert(!cb3.allowRequest(), 'Should reject request when open');

    // Wait for reset timeout
    await new Promise(r => setTimeout(r, 250));
    assert(cb3.allowRequest(), 'Should allow probe after reset timeout');
    assert(cb3.state === CB_HALF_OPEN, 'Should be half-open');

    // Test 6: epoch-based atomicity
    console.log('--- Test 6: epoch-based atomicity ---');
    const cb4 = new CircuitBreaker({ failureThreshold: 3 });
    const epoch0 = cb4._epoch;
    cb4.recordFailure();
    assert(cb4._epoch === epoch0 + 1, 'Epoch should increment on failure');
    cb4.recordSuccess();
    assert(cb4._epoch === epoch0 + 2, 'Epoch should increment on success');
    assert(cb4.failures === 0, 'Failures should decrement to 0 on success');

    // Test 7: error.response.status detection
    console.log('--- Test 7: error.response.status detection ---');
    const r7 = await retryWithFilter(
      () => { const e = new Error('Forbidden'); e.response = { status: 403 }; throw e; },
      { maxRetries: 3, logger: silent }
    );
    assert(r7.attempts === 1, 'Should detect 403 via error.response.status');

    // Test 8: successful call
    console.log('--- Test 8: successful call ---');
    const r8 = await retryWithFilter(() => Promise.resolve('ok'), { logger: silent });
    assert(r8.success === true, 'Should succeed');
    assert(r8.result === 'ok', 'Should return result');
    assert(r8.attempts === 1, 'Should succeed on first attempt');

    // Test 9: RetryWithTimeout class with filtering
    console.log('--- Test 9: RetryWithTimeout class with 401 filtering ---');
    const retry = new RetryWithTimeout({
      maxRetries: 5, initialBackoffMs: 10, totalTimeoutMs: 5000, logger: silent
    });
    const r9 = await retry.execute(() => {
      const e = new Error('Unauthorized');
      e.statusCode = 401;
      throw e;
    });
    assert(r9.attempts === 1, 'RetryWithTimeout should stop on 401');
    assert(r9.strategy === 'non_retryable', 'Strategy should be non_retryable');

    // Test 10: RetryWithTimeout with circuit breaker
    console.log('--- Test 10: RetryWithTimeout with circuit breaker ---');
    const cb10 = new CircuitBreaker({ failureThreshold: 1 });
    cb10.recordFailure(); // Trip the breaker
    const retry10 = new RetryWithTimeout({
      maxRetries: 3, initialBackoffMs: 10, circuitBreaker: cb10, logger: silent
    });
    const r10 = await retry10.execute(() => Promise.resolve('should not reach'));
    assert(r10.strategy === 'circuit_breaker_rejected', 'Should be rejected by circuit breaker');

    // Test 11: stale epoch transition is a no-op
    console.log('--- Test 11: stale epoch is no-op ---');
    const cb11 = new CircuitBreaker({ failureThreshold: 5 });
    const staleEpoch = cb11._epoch;
    cb11.recordFailure(); // Bumps epoch
    // Now try a transition with the stale epoch
    const applied = cb11._transition(() => { cb11._failures = 999; }, staleEpoch);
    assert(!applied, 'Stale epoch transition should be rejected');
    assert(cb11._failures === 1, 'Failures should remain 1 (stale mutation rejected)');

    // Test 12: circuit breaker reset
    console.log('--- Test 12: circuit breaker reset ---');
    const cb12 = new CircuitBreaker({ failureThreshold: 2 });
    cb12.recordFailure();
    cb12.recordFailure();
    assert(cb12.state === CB_OPEN, 'Should be open');
    cb12.reset();
    assert(cb12.state === CB_CLOSED, 'Should be closed after reset');
    assert(cb12.failures === 0, 'Failures should be 0 after reset');

    console.log(`\n--- Results: ${passed} passed, ${failed} failed ---`);
    if (failed > 0) process.exit(1);
  })();
}
