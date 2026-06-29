/**
 * SSH Connection Refused Failure Test
 *
 * Tests the system's behavior when SSH connections are refused.
 * Verifies:
 * - Connection refused is detected immediately
 * - Retry logic activates with appropriate backoff
 * - Circuit breaker opens after threshold
 * - Fallback to alternative workers
 */

import { strict as assert } from 'assert';
import { test } from 'node:test';

// Mock SSH connection refused error
function simulateSSHRefused(hostname = 'server-01') {
  const error = new Error(`ssh: connect to host ${hostname} port 22: Connection refused`);
  error.code = 'ECONNREFUSED';
  error.errno = -111;
  throw error;
}

test('SSH connection refused detection', async (t) => {
  await t.test('should detect connection refused immediately', () => {
    const start = Date.now();
    try {
      simulateSSHRefused('server-02');
      assert.fail('Should have thrown connection refused error');
    } catch (error) {
      const duration = Date.now() - start;
      assert.ok(duration < 100, 'Should fail fast, not wait for timeout');
      assert.strictEqual(error.code, 'ECONNREFUSED');
      assert.ok(error.message.includes('Connection refused'));
    }
  });

  await t.test('should include hostname in error', () => {
    try {
      simulateSSHRefused('laptop-01');
      assert.fail('Should have thrown');
    } catch (error) {
      assert.ok(error.message.includes('laptop-01'), 'Error should include hostname');
      assert.ok(error.message.includes('port 22'), 'Error should include port');
    }
  });
});

test('SSH connection refused retry logic', async (t) => {
  await t.test('should retry with exponential backoff', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 3,
      initialBackoffMs: 100,
      maxBackoffMs: 2000
    });

    let attempts = 0;
    const timestamps = [];

    const failingStrategy = async () => {
      attempts++;
      timestamps.push(Date.now());
      if (attempts < 3) {
        simulateSSHRefused('server-03');
      }
      return { success: true };
    };

    const result = await recovery.execute(failingStrategy, null, {});

    assert.ok(result.success, 'Should eventually succeed');
    assert.strictEqual(attempts, 3, 'Should retry before success');

    // Verify exponential backoff
    if (timestamps.length >= 2) {
      const backoff1 = timestamps[1] - timestamps[0];
      assert.ok(backoff1 >= 100, 'First backoff should be at least 100ms');
    }
  });

  await t.test('should use fallback after primary fails', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0, // Skip retries to test fallback directly
      initialBackoffMs: 50
    });

    let primaryCalled = false;
    let fallbackCalled = false;

    const primary = async () => {
      primaryCalled = true;
      simulateSSHRefused('server-01');
    };

    const fallback = async () => {
      fallbackCalled = true;
      return { worker: 'server-02', result: 'fallback success' };
    };

    const result = await recovery.execute(primary, fallback, {});

    assert.strictEqual(primaryCalled, true, 'Primary should be called first');
    assert.strictEqual(fallbackCalled, true, 'Fallback should be called after primary fails');
    assert.ok(result.success, 'Should succeed via fallback');
    assert.strictEqual(result.strategy, 'fallback');
    assert.strictEqual(result.result.worker, 'server-02');
  });
});

test('SSH connection refused circuit breaker', async (t) => {
  await t.test('should open circuit after repeated connection refused', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    recovery.circuitFailureThreshold = 5;
    recovery.circuitResetMs = 30000;

    const failingStrategy = async () => {
      simulateSSHRefused('pi-01');
    };

    const fallbackStrategy = async () => {
      return { fromFallback: true };
    };

    // Execute until circuit opens
    for (let i = 0; i < 5; i++) {
      await recovery.executeWithCircuitBreaker(failingStrategy, fallbackStrategy, {});
    }

    assert.ok(recovery.circuitOpen, 'Circuit should be open after threshold failures');
    assert.strictEqual(recovery.circuitFailures, 5, 'Should track failure count');
  });

  await t.test('should bypass primary when circuit is open', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    // Open circuit
    recovery.circuitOpen = true;
    recovery.circuitOpenedAt = Date.now();
    recovery.circuitResetMs = 60000;

    let primaryAttempts = 0;
    let fallbackAttempts = 0;

    const primary = async () => {
      primaryAttempts++;
      simulateSSHRefused('server-01');
    };

    const fallback = async () => {
      fallbackAttempts++;
      return { worker: 'alternative' };
    };

    const result = await recovery.executeWithCircuitBreaker(primary, fallback, {});

    assert.strictEqual(primaryAttempts, 0, 'Primary should be bypassed when circuit is open');
    assert.strictEqual(fallbackAttempts, 1, 'Fallback should be used directly');
    assert.ok(result.success);
    assert.strictEqual(result.strategy, 'circuit_breaker_fallback');
  });

  await t.test('should attempt to close circuit after reset period', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    // Open circuit in the past
    recovery.circuitOpen = true;
    recovery.circuitOpenedAt = Date.now() - 61000; // 61 seconds ago
    recovery.circuitResetMs = 60000; // 1 minute

    const primary = async () => {
      return { status: 'recovered' };
    };

    const fallback = async () => {
      return { status: 'fallback' };
    };

    const result = await recovery.executeWithCircuitBreaker(primary, fallback, {});

    assert.strictEqual(recovery.circuitOpen, false, 'Circuit should be closed after reset period');
    assert.strictEqual(result.result.status, 'recovered', 'Primary should be tried again');
  });
});

test('SSH connection refused error messages', async (t) => {
  await t.test('should provide actionable error message', () => {
    try {
      simulateSSHRefused('desktop-ap');
      assert.fail('Should have thrown');
    } catch (error) {
      assert.ok(error.message.includes('desktop-ap'), 'Should include hostname');
      assert.ok(error.message.includes('Connection refused'), 'Should be clear about issue');
      assert.strictEqual(error.code, 'ECONNREFUSED');
    }
  });

  await t.test('should include recovery context when exhausted', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 2,
      initialBackoffMs: 10
    });

    const failing = async () => {
      simulateSSHRefused('server-ap');
    };

    const result = await recovery.execute(failing, null, {});

    assert.strictEqual(result.success, false);
    assert.ok(result.error, 'Should include original error');
    assert.ok(result.error.message.includes('server-ap'), 'Should preserve hostname context');
    assert.ok(result.message.includes('exhausted'), 'Should explain all strategies failed');
    assert.ok(result.attempts >= 3, 'Should report number of attempts');
  });
});

test('SSH connection refused fallback strategies', async (t) => {
  await t.test('should try alternative workers', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => ({ worker: 'laptop-01', result: 'success' }),
        async () => ({ worker: 'pi-02', result: 'success' })
      ]
    });

    const primary = async () => {
      simulateSSHRefused('server-01');
    };

    const result = await recovery.execute(primary, null, {});

    assert.ok(result.success, 'Should succeed via alternative');
    assert.strictEqual(result.strategy, 'alternative_1');
    assert.strictEqual(result.result.worker, 'laptop-01');
  });

  await t.test('should continue to next alternative if first fails', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => { simulateSSHRefused('laptop-01'); },
        async () => ({ worker: 'pi-02', result: 'success' })
      ]
    });

    const primary = async () => {
      simulateSSHRefused('server-01');
    };

    const result = await recovery.execute(primary, null, {});

    assert.ok(result.success, 'Should succeed via second alternative');
    assert.strictEqual(result.strategy, 'alternative_2');
    assert.strictEqual(result.result.worker, 'pi-02');
  });
});
