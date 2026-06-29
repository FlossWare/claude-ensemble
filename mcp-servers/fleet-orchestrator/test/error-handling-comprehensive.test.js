import { test, describe } from 'node:test';
import { strict as assert } from 'node:assert';
import { withRetry } from '../lib/retry.js';
import { CircuitBreaker } from '../lib/circuit-breaker.js';

// =========================================================================
// Test 1: Trigger SSH timeout (invalid worker)
// =========================================================================
describe('SSH timeout with invalid worker', () => {
  test('SSH timeout error triggers retry logic', async () => {
    let attempts = 0;
    const fn = async () => {
      attempts++;
      const err = new Error('ssh: connect to host invalid-worker-999 port 22: Connection timed out');
      err.code = 'ETIMEDOUT';
      throw err;
    };

    try {
      await withRetry(fn, { maxRetries: 3, backoffMs: 10, backoffMultiplier: 1 });
      assert.fail('Should have thrown after all retries exhausted');
    } catch (error) {
      assert.match(error.message, /Connection timed out/);
      assert.equal(attempts, 3, 'Should have attempted exactly 3 times');
    }
  });

  test('SSH timeout on invalid worker eventually succeeds on retry', async () => {
    let attempts = 0;
    const fn = async () => {
      attempts++;
      if (attempts < 3) {
        const err = new Error('ssh: connect to host invalid-worker-999 port 22: Connection timed out');
        err.code = 'ETIMEDOUT';
        throw err;
      }
      return { success: true, worker: 'fallback-worker' };
    };

    const result = await withRetry(fn, { maxRetries: 3, backoffMs: 10, backoffMultiplier: 1 });
    assert.equal(result.success, true);
    assert.equal(attempts, 3);
  });
});

// =========================================================================
// Test 2: Verify retry attempts (should be 3)
// =========================================================================
describe('Retry attempt verification', () => {
  test('withRetry defaults to 3 attempts', async () => {
    let attempts = 0;
    const fn = async () => {
      attempts++;
      const err = new Error('always fails');
      err.code = 'ETIMEDOUT';
      throw err;
    };

    try {
      await withRetry(fn, { backoffMs: 10 });
      assert.fail('Should have thrown');
    } catch (error) {
      assert.equal(attempts, 3, 'Default maxRetries should be 3');
    }
  });

  test('withRetry respects explicit maxRetries=3', async () => {
    let attempts = 0;
    const fn = async () => {
      attempts++;
      const err = new Error('always fails');
      err.code = 'ETIMEDOUT';
      throw err;
    };

    try {
      await withRetry(fn, { maxRetries: 3, backoffMs: 10, backoffMultiplier: 1 });
      assert.fail('Should have thrown');
    } catch (error) {
      assert.equal(attempts, 3, 'Should have attempted exactly 3 times');
      assert.equal(error.message, 'always fails', 'Should throw the last error');
    }
  });

  test('withRetry applies exponential backoff between attempts', async () => {
    const timestamps = [];
    const fn = async () => {
      timestamps.push(Date.now());
      const err = new Error('fails');
      err.code = 'ETIMEDOUT';
      throw err;
    };

    try {
      await withRetry(fn, { maxRetries: 3, backoffMs: 50, backoffMultiplier: 2 });
    } catch (e) { /* expected */ }

    assert.equal(timestamps.length, 3, 'Should record 3 attempts');

    // First retry delay should be ~50ms (backoffMs * 2^0 * jitter = 25-75ms)
    const delay1 = timestamps[1] - timestamps[0];
    assert.ok(delay1 >= 20, `First delay (${delay1}ms) should be >= 20ms (target: 50ms with jitter)`);

    // Second retry delay should be ~100ms (backoffMs * 2^1 * jitter = 50-150ms)
    const delay2 = timestamps[2] - timestamps[1];
    assert.ok(delay2 >= 40, `Second delay (${delay2}ms) should be >= 40ms (target: 100ms with jitter)`);
    assert.ok(delay2 > delay1 * 0.5, 'Second delay should be in the range of exponential backoff');
  });

  test('withRetry returns immediately on first success without extra attempts', async () => {
    let attempts = 0;
    const fn = async () => {
      attempts++;
      return 'immediate-success';
    };

    const result = await withRetry(fn, { maxRetries: 3, backoffMs: 10 });
    assert.equal(result, 'immediate-success');
    assert.equal(attempts, 1, 'Should only attempt once on immediate success');
  });
});

// =========================================================================
// Test 3: Trigger circuit breaker (5+ failures)
// =========================================================================
describe('Circuit breaker triggers after threshold failures', () => {
  test('Circuit breaker opens after 5 consecutive failures (default threshold)', async () => {
    const breaker = new CircuitBreaker({ threshold: 5, resetTimeout: 60000 });
    const worker = 'failing-worker-01';
    const failingFn = async () => { throw new Error('worker down'); };

    // Accumulate 5 failures
    for (let i = 0; i < 5; i++) {
      try {
        await breaker.execute(worker, failingFn);
      } catch (e) {
        assert.equal(e.message, 'worker down', `Failure ${i + 1} should pass through the original error`);
      }
    }

    // 6th call should be blocked by circuit breaker (circuit is open)
    try {
      await breaker.execute(worker, failingFn);
      assert.fail('Should have thrown circuit breaker OPEN error');
    } catch (error) {
      assert.match(error.message, /Circuit breaker OPEN/, 'Should indicate circuit is OPEN');
      assert.match(error.message, /failing-worker-01/, 'Should name the worker');
    }
  });

  test('Circuit breaker does not open before threshold', async () => {
    const breaker = new CircuitBreaker({ threshold: 5, resetTimeout: 60000 });
    const worker = 'partial-fail-worker';
    let callCount = 0;
    const failingFn = async () => {
      callCount++;
      throw new Error('partial failure');
    };

    // 4 failures (below threshold of 5)
    for (let i = 0; i < 4; i++) {
      try { await breaker.execute(worker, failingFn); } catch (e) { /* expected */ }
    }

    // 5th call should still execute the function (not blocked),
    // even though it will fail and THEN open the circuit
    const callCountBefore = callCount;
    try {
      await breaker.execute(worker, failingFn);
    } catch (e) {
      // This 5th failure should be the original error, not a circuit breaker error
      assert.equal(e.message, 'partial failure', '5th call should execute the function');
    }
    assert.equal(callCount, callCountBefore + 1, '5th call should have executed the function');
  });

  test('Circuit breaker tracks workers independently', async () => {
    const breaker = new CircuitBreaker({ threshold: 3, resetTimeout: 60000 });
    const failingFn = async () => { throw new Error('down'); };
    const successFn = async () => 'ok';

    // Trip circuit on worker-A
    for (let i = 0; i < 3; i++) {
      try { await breaker.execute('worker-A', failingFn); } catch (e) { /* expected */ }
    }

    // worker-A should be open
    try {
      await breaker.execute('worker-A', successFn);
      assert.fail('worker-A circuit should be open');
    } catch (error) {
      assert.match(error.message, /Circuit breaker OPEN/);
    }

    // worker-B should still be usable
    const result = await breaker.execute('worker-B', successFn);
    assert.equal(result, 'ok', 'worker-B should not be affected by worker-A failures');
  });
});

// =========================================================================
// Test 4: Verify circuit opens
// =========================================================================
describe('Verify circuit open state behavior', () => {
  test('Open circuit rejects all calls without executing the function', async () => {
    const breaker = new CircuitBreaker({ threshold: 2, resetTimeout: 60000 });
    const worker = 'open-test-worker';
    let executionCount = 0;

    // Trip the circuit
    for (let i = 0; i < 2; i++) {
      try {
        await breaker.execute(worker, async () => { executionCount++; throw new Error('fail'); });
      } catch (e) { /* expected */ }
    }
    assert.equal(executionCount, 2, 'Function should have executed twice to trip the breaker');

    // Now verify the function is NOT executed when circuit is open
    executionCount = 0;
    for (let i = 0; i < 5; i++) {
      try {
        await breaker.execute(worker, async () => {
          executionCount++;
          return 'should-not-reach';
        });
        assert.fail('Should throw circuit breaker error');
      } catch (error) {
        assert.match(error.message, /Circuit breaker OPEN/);
      }
    }
    assert.equal(executionCount, 0, 'Function should NOT have been called when circuit is open');
  });

  test('Open circuit error message identifies the worker', async () => {
    const breaker = new CircuitBreaker({ threshold: 2, resetTimeout: 60000 });
    const worker = 'identified-worker';

    for (let i = 0; i < 2; i++) {
      try { await breaker.execute(worker, async () => { throw new Error('fail'); }); } catch (e) { /* expected */ }
    }

    try {
      await breaker.execute(worker, async () => 'nope');
      assert.fail('Should throw');
    } catch (error) {
      assert.ok(error.message.includes('identified-worker'), `Error should contain worker name. Got: ${error.message}`);
      assert.ok(error.message.includes('Circuit breaker OPEN'), `Error should state circuit is open. Got: ${error.message}`);
    }
  });
});

// =========================================================================
// Test 5: Verify recovery after reset timeout
// =========================================================================
describe('Circuit breaker recovery after reset timeout', () => {
  test('Circuit allows calls again after resetTimeout expires', async () => {
    const resetTimeout = 100; // 100ms for fast test
    const breaker = new CircuitBreaker({ threshold: 2, resetTimeout });
    const worker = 'recovery-worker';

    // Trip the circuit
    for (let i = 0; i < 2; i++) {
      try { await breaker.execute(worker, async () => { throw new Error('fail'); }); } catch (e) { /* expected */ }
    }

    // Verify circuit is open
    try {
      await breaker.execute(worker, async () => 'blocked');
      assert.fail('Should be blocked');
    } catch (error) {
      assert.match(error.message, /Circuit breaker OPEN/);
    }

    // Wait for reset timeout to expire
    await new Promise(resolve => setTimeout(resolve, resetTimeout + 50));

    // Now the circuit should allow calls through again
    const result = await breaker.execute(worker, async () => 'recovered');
    assert.equal(result, 'recovered', 'Circuit should allow calls after reset timeout');
  });

  test('Successful call after reset timeout resets failure count', async () => {
    const resetTimeout = 100;
    const breaker = new CircuitBreaker({ threshold: 2, resetTimeout });
    const worker = 'reset-worker';

    // Trip the circuit
    for (let i = 0; i < 2; i++) {
      try { await breaker.execute(worker, async () => { throw new Error('fail'); }); } catch (e) { /* expected */ }
    }

    // Wait for reset
    await new Promise(resolve => setTimeout(resolve, resetTimeout + 50));

    // Successful call should reset the breaker
    await breaker.execute(worker, async () => 'ok');

    // Now we should be able to tolerate 1 failure without tripping (need 2)
    try { await breaker.execute(worker, async () => { throw new Error('single fail'); }); } catch (e) { /* expected */ }

    // Next call should still work (circuit should not be open after just 1 failure)
    const result = await breaker.execute(worker, async () => 'still-ok');
    assert.equal(result, 'still-ok', 'Circuit should not trip after single failure post-reset');
  });

  test('Failed call during recovery re-opens the circuit', async () => {
    const resetTimeout = 100;
    const breaker = new CircuitBreaker({ threshold: 2, resetTimeout });
    const worker = 'reopen-worker';

    // Trip the circuit
    for (let i = 0; i < 2; i++) {
      try { await breaker.execute(worker, async () => { throw new Error('fail'); }); } catch (e) { /* expected */ }
    }

    // Wait for reset
    await new Promise(resolve => setTimeout(resolve, resetTimeout + 50));

    // Fail again during recovery -- this increments failures
    try { await breaker.execute(worker, async () => { throw new Error('fail again'); }); } catch (e) { /* expected */ }

    // The implementation resets on success and increments on failure.
    // After the reset timeout, the openUntil is checked (Date.now() >= openUntil passes)
    // so the call goes through. On failure, count goes up.
    // Since the CircuitBreaker implementation doesn't reset failure count on timeout expiry,
    // we need to check behavior: after timeout expiry + failure, the count is now 3.
    // That means the circuit should be re-opened since 3 >= threshold(2).

    // Verify circuit is open again immediately (no timeout wait)
    try {
      await breaker.execute(worker, async () => 'should-not-reach');
      assert.fail('Circuit should be re-opened after failure during recovery');
    } catch (error) {
      assert.match(error.message, /Circuit breaker OPEN/, 'Circuit should be re-opened');
    }
  });
});

// =========================================================================
// Integration: Retry + Circuit Breaker together
// =========================================================================
describe('Integration: retry + circuit breaker combined', () => {
  test('Retry inside circuit breaker accumulates failures toward threshold', async () => {
    const breaker = new CircuitBreaker({ threshold: 5, resetTimeout: 60000 });
    const worker = 'combined-worker';
    let totalAttempts = 0;

    // First call with retry: 3 failures (using retryable error code)
    try {
      await breaker.execute(worker, async () => {
        return await withRetry(async () => {
          totalAttempts++;
          const err = new Error('always fails');
          err.code = 'ETIMEDOUT';
          throw err;
        }, { maxRetries: 3, backoffMs: 10, backoffMultiplier: 1 });
      });
    } catch (e) { /* expected - retry exhausted, circuit records 1 failure */ }

    // The circuit breaker records 1 failure (the withRetry exhaustion error)
    // We need 5 total circuit-breaker-level failures to open it
    for (let i = 0; i < 4; i++) {
      try {
        await breaker.execute(worker, async () => {
          throw new Error('direct fail');
        });
      } catch (e) { /* expected */ }
    }

    // Now circuit should be open (5 failures total)
    try {
      await breaker.execute(worker, async () => 'should not run');
      assert.fail('Circuit should be open after 5 failures');
    } catch (error) {
      assert.match(error.message, /Circuit breaker OPEN/);
    }

    assert.equal(totalAttempts, 3, 'Retry should have attempted 3 times inside first circuit breaker call');
  });
});
