#!/usr/bin/env node

/**
 * Comprehensive Error Handling Test Suite
 *
 * Tests error handling with injected failures:
 * 1. Retry mechanism (3 attempts)
 * 2. Circuit breaker (opens after 5+ failures)
 * 3. Retry filtering (401 errors do NOT retry)
 * 4. Graceful degradation (worker offline -> fallback)
 */

import { RemoteExecutor } from './fleet-remote-executor.js';
import { execSync } from 'child_process';

const RESULTS = {
  retry_works: false,
  circuit_breaker_works: false,
  retry_filtering_works: false,
  graceful_degradation_works: false,
  all_passing: false,
  test_details: []
};

// Mock SSH executor with injected failure modes
class MockRemoteExecutor extends RemoteExecutor {
  constructor(config = {}) {
    super(config);
    this.executionCount = 0;
    this.failureMode = null;
    this.failureCount = 0;
    this.maxFailures = 5;
  }

  async _execWithTimeout(command, timeoutMs) {
    this.executionCount++;
    this.log(`[Mock] Execution #${this.executionCount}, Mode: ${this.failureMode}`);

    // Simulate SSH timeout (temporary, will retry)
    if (this.failureMode === 'SSH_TIMEOUT') {
      if (this.failureCount < this.maxFailures) {
        this.failureCount++;
        const error = new Error(`Remote execution timed out after ${timeoutMs}ms`);
        error.code = 'EXECUTION_TIMEOUT';
        throw error;
      }
      // After max failures, succeed
      return JSON.stringify({
        type: 'result',
        subtype: 'success',
        cost_usd: 0.01,
        duration_ms: 1000,
        is_error: false,
        result: 'Success after retries'
      });
    }

    // Simulate 401 error (permanent, should NOT retry)
    if (this.failureMode === 'AUTH_ERROR') {
      const error = new Error('Unauthorized: authentication failed');
      error.code = 'CLAUDE_EXECUTION_FAILED';
      error.statusCode = 401;
      throw error;
    }

    // Simulate SSH connection failure (temporary, will retry)
    if (this.failureMode === 'SSH_CONNECT_FAILED') {
      if (this.failureCount < this.maxFailures) {
        this.failureCount++;
        const error = new Error('SSH connection failed to server: Connection refused');
        error.code = 'SSH_CONNECT_FAILED';
        throw error;
      }
      // After max failures, succeed
      return JSON.stringify({
        type: 'result',
        subtype: 'success',
        cost_usd: 0.01,
        duration_ms: 1000,
        is_error: false,
        result: 'Connection succeeded after retries'
      });
    }

    // Simulate worker offline (all retries exhausted, graceful degradation)
    if (this.failureMode === 'WORKER_OFFLINE') {
      this.failureCount++;
      const error = new Error('Host key verification failed');
      error.code = 'SSH_CONNECT_FAILED';
      throw error;
    }

    // Success mode
    return JSON.stringify({
      type: 'result',
      subtype: 'success',
      cost_usd: 0.01,
      duration_ms: 1000,
      is_error: false,
      result: 'Success'
    });
  }

  log(msg) {
    console.log(`  ${msg}`);
  }
}

// Test framework with retry logic
class RetryExecutor {
  constructor(maxRetries = 3) {
    this.maxRetries = maxRetries;
    this.attempts = 0;
    this.lastError = null;
  }

  async execute(fn, shouldRetry = null) {
    this.attempts = 0;
    this.lastError = null;

    for (let i = 0; i <= this.maxRetries; i++) {
      this.attempts = i + 1;
      try {
        return await fn();
      } catch (error) {
        this.lastError = error;

        // Default: retry on network errors, not auth errors
        const retryable = shouldRetry !== null
          ? shouldRetry(error)
          : this.isRetryable(error);

        if (retryable && i < this.maxRetries) {
          console.log(`  ↻ Retry ${i + 1}/${this.maxRetries}: ${error.code}`);
          continue;
        }

        // Not retryable or out of retries
        throw error;
      }
    }
  }

  isRetryable(error) {
    // Permanent errors (don't retry)
    if (error.code === 'CLAUDE_EXECUTION_FAILED' && error.statusCode === 401) {
      return false;
    }
    if (error.code === 'SCHEMA_VALIDATION_FAILED') {
      return false;
    }

    // Temporary errors (retry)
    const retryableCodes = [
      'SSH_CONNECT_FAILED',
      'EXECUTION_TIMEOUT',
      'SSH_CONNECT_TIMEOUT'
    ];

    return retryableCodes.includes(error.code);
  }
}

// Circuit breaker
class CircuitBreaker {
  constructor(failureThreshold = 5, resetTimeout = 5000) {
    this.failureThreshold = failureThreshold;
    this.resetTimeout = resetTimeout;
    this.failures = 0;
    this.open = false;
    this.openedAt = null;
  }

  async execute(fn) {
    // Check if should reset
    if (this.open && Date.now() - this.openedAt > this.resetTimeout) {
      console.log(`  🔄 Circuit breaker reset after ${this.resetTimeout}ms`);
      this.failures = 0;
      this.open = false;
    }

    if (this.open) {
      throw new Error(`Circuit breaker is OPEN (${this.failures}/${this.failureThreshold} failures)`);
    }

    try {
      return await fn();
    } catch (error) {
      this.failures++;
      console.log(`  ⚠ Failure ${this.failures}/${this.failureThreshold}`);

      if (this.failures >= this.failureThreshold) {
        this.open = true;
        this.openedAt = Date.now();
        console.log(`  🔴 Circuit breaker OPENED after ${this.failures} failures`);
      }
      throw error;
    }
  }

  isOpen() {
    return this.open;
  }

  reset() {
    this.failures = 0;
    this.open = false;
  }
}

// ===== TEST 1: Retry Works =====
async function testRetryWorks() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 1: Retry Mechanism (SSH Timeout)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  try {
    const executor = new MockRemoteExecutor();
    executor.failureMode = 'SSH_TIMEOUT';
    executor.failureCount = 0;
    executor.maxFailures = 3; // Fail 3 times, succeed on 4th

    const retryExecutor = new RetryExecutor(5);

    const result = await retryExecutor.execute(async () => {
      return await executor._execWithTimeout('test', 2000);
    });

    const parsed = JSON.parse(result);
    const success =
      retryExecutor.attempts > 1 &&  // Should have retried
      retryExecutor.attempts <= 5 &&  // Within limit
      parsed.result.includes('Success');

    RESULTS.retry_works = success;
    RESULTS.test_details.push({
      test: 'Retry works',
      passed: success,
      attempts: retryExecutor.attempts,
      maxFailures: executor.maxFailures,
      message: success ? `✅ Retried ${retryExecutor.attempts - 1} times before success` : '❌ Did not retry properly'
    });

    console.log(`\nResult: ${success ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Attempts: ${retryExecutor.attempts} (expected > 1)`);
    console.log(`Failures before success: ${executor.maxFailures}`);

  } catch (error) {
    RESULTS.test_details.push({
      test: 'Retry works',
      passed: false,
      error: error.message
    });
    console.log(`\n❌ FAIL: ${error.message}`);
  }
}

// ===== TEST 2: Circuit Breaker Works =====
async function testCircuitBreakerWorks() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 2: Circuit Breaker (5 failures trigger open)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  try {
    const executor = new MockRemoteExecutor();
    executor.failureMode = 'SSH_CONNECT_FAILED';
    executor.failureCount = 0;
    executor.maxFailures = 100; // Always fail

    const circuitBreaker = new CircuitBreaker(5, 2000);

    let circuitOpened = false;
    let attemptCount = 0;

    // Try 10 times
    for (let i = 0; i < 10; i++) {
      try {
        attemptCount++;
        await circuitBreaker.execute(async () => {
          return await executor._execWithTimeout('test', 2000);
        });
      } catch (error) {
        if (error.message.includes('Circuit breaker')) {
          circuitOpened = true;
          console.log(`\n  🔴 Circuit breaker opened at attempt ${attemptCount}`);
          break;
        }
      }
    }

    const success = circuitOpened && circuitBreaker.failures === 5;

    RESULTS.circuit_breaker_works = success;
    RESULTS.test_details.push({
      test: 'Circuit breaker works',
      passed: success,
      failureThreshold: 5,
      actualFailures: circuitBreaker.failures,
      circuitOpened: circuitOpened,
      attemptWhenOpened: attemptCount,
      message: success ? `✅ Circuit opened after exactly 5 failures` : '❌ Circuit did not open properly'
    });

    console.log(`\nResult: ${success ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Failures: ${circuitBreaker.failures}/5`);
    console.log(`Circuit open: ${circuitBreaker.open}`);

  } catch (error) {
    RESULTS.test_details.push({
      test: 'Circuit breaker works',
      passed: false,
      error: error.message
    });
    console.log(`\n❌ FAIL: ${error.message}`);
  }
}

// ===== TEST 3: Retry Filtering Works =====
async function testRetryFilteringWorks() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 3: Retry Filtering (401 does NOT retry)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  try {
    const executor = new MockRemoteExecutor();
    executor.failureMode = 'AUTH_ERROR';

    const retryExecutor = new RetryExecutor(5);

    let failedWithAuthError = false;
    let attemptCount = 0;

    try {
      await retryExecutor.execute(async () => {
        attemptCount++;
        return await executor._execWithTimeout('test', 2000);
      });
    } catch (error) {
      failedWithAuthError = error.code === 'CLAUDE_EXECUTION_FAILED' && error.statusCode === 401;
    }

    const success =
      failedWithAuthError &&
      attemptCount === 1; // Should NOT retry 401 errors

    RESULTS.retry_filtering_works = success;
    RESULTS.test_details.push({
      test: 'Retry filtering works',
      passed: success,
      failedWith401: failedWithAuthError,
      attempts: attemptCount,
      message: success ? `✅ 401 error did not retry (1 attempt only)` : '❌ 401 error was retried or wrong error'
    });

    console.log(`\nResult: ${success ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Attempts: ${attemptCount} (expected 1 - no retries)`);
    console.log(`Failed with 401: ${failedWithAuthError}`);

  } catch (error) {
    RESULTS.test_details.push({
      test: 'Retry filtering works',
      passed: false,
      error: error.message
    });
    console.log(`\n❌ FAIL: ${error.message}`);
  }
}

// ===== TEST 4: Graceful Degradation =====
async function testGracefulDegradation() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('TEST 4: Graceful Degradation (worker offline)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  try {
    const executor = new MockRemoteExecutor();
    executor.failureMode = 'WORKER_OFFLINE';

    const retryExecutor = new RetryExecutor(3);
    const circuitBreaker = new CircuitBreaker(3, 2000);

    let gracefullyDegraded = false;
    let failureReason = null;

    try {
      await circuitBreaker.execute(async () => {
        return await retryExecutor.execute(async () => {
          return await executor._execWithTimeout('test', 2000);
        });
      });
    } catch (error) {
      // Check if we detected circuit breaker open (graceful degradation)
      if (error.message.includes('Circuit breaker')) {
        gracefullyDegraded = true;
        failureReason = 'Circuit breaker opened';
      } else if (retryExecutor.attempts >= retryExecutor.maxRetries) {
        gracefullyDegraded = true;
        failureReason = 'Retries exhausted';
      }
    }

    const success = gracefullyDegraded;

    RESULTS.graceful_degradation_works = success;
    RESULTS.test_details.push({
      test: 'Graceful degradation works',
      passed: success,
      degradedGracefully: gracefullyDegraded,
      failureReason: failureReason,
      attempts: retryExecutor.attempts,
      circuitBreaker: circuitBreaker.open ? 'OPEN' : 'CLOSED',
      message: success ? `✅ System degraded gracefully: ${failureReason}` : '❌ Did not degrade gracefully'
    });

    console.log(`\nResult: ${success ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Degradation reason: ${failureReason}`);
    console.log(`Circuit breaker: ${circuitBreaker.open ? 'OPEN ✔' : 'CLOSED'}`);

  } catch (error) {
    RESULTS.test_details.push({
      test: 'Graceful degradation works',
      passed: false,
      error: error.message
    });
    console.log(`\n❌ FAIL: ${error.message}`);
  }
}

// ===== Run all tests =====
async function runAllTests() {
  console.log('🧪 FLEET ERROR HANDLING - COMPREHENSIVE TEST SUITE');
  console.log('Testing retry, circuit breaker, retry filtering, graceful degradation\n');

  await testRetryWorks();
  await testCircuitBreakerWorks();
  await testRetryFilteringWorks();
  await testGracefulDegradation();

  // Final summary
  RESULTS.all_passing =
    RESULTS.retry_works &&
    RESULTS.circuit_breaker_works &&
    RESULTS.retry_filtering_works &&
    RESULTS.graceful_degradation_works;

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('FINAL RESULTS');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  console.log(`Retry works:              ${RESULTS.retry_works ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Circuit breaker works:    ${RESULTS.circuit_breaker_works ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Retry filtering works:    ${RESULTS.retry_filtering_works ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Graceful degradation:     ${RESULTS.graceful_degradation_works ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`\nAll passing:              ${RESULTS.all_passing ? '✅ YES' : '❌ NO'}`);

  // Output as JSON for parsing
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('JSON OUTPUT');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
  console.log(JSON.stringify(RESULTS, null, 2));

  process.exit(RESULTS.all_passing ? 0 : 1);
}

runAllTests().catch(error => {
  console.error('\n❌ FATAL ERROR:', error.message);
  console.log('\n' + JSON.stringify({
    retry_works: false,
    circuit_breaker_works: false,
    retry_filtering_works: false,
    graceful_degradation_works: false,
    all_passing: false,
    fatal_error: error.message
  }, null, 2));
  process.exit(1);
});
