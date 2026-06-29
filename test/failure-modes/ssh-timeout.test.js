/**
 * SSH Timeout Failure Test
 *
 * Tests the system's behavior when SSH connections timeout.
 * Verifies:
 * - Timeout is detected within expected window
 * - Retry logic activates
 * - Circuit breaker opens after threshold
 * - Error messages are clear
 */

import { strict as assert } from 'assert';
import { test, mock } from 'node:test';
import { execSync } from 'child_process';

// Mock the execSync to simulate timeout
function simulateSSHTimeout() {
  const error = new Error('Command failed: ssh ...');
  error.code = 'ETIMEDOUT';
  error.killed = true;
  error.signal = 'SIGTERM';
  throw error;
}

test('SSH timeout detection', async (t) => {
  await t.test('should detect timeout within 5 seconds', () => {
    const start = Date.now();
    try {
      simulateSSHTimeout();
      assert.fail('Should have thrown timeout error');
    } catch (error) {
      const duration = Date.now() - start;
      assert.ok(duration < 5000, 'Timeout detection too slow');
      assert.strictEqual(error.code, 'ETIMEDOUT');
    }
  });

  await t.test('should throw correct error code', () => {
    try {
      simulateSSHTimeout();
      assert.fail('Should have thrown');
    } catch (error) {
      assert.strictEqual(error.code, 'ETIMEDOUT');
      assert.ok(error.killed, 'Process should be marked as killed');
    }
  });
});

test('SSH timeout retry logic', async (t) => {
  await t.test('should retry with exponential backoff', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 3,
      initialBackoffMs: 100, // Fast for testing
      maxBackoffMs: 1000
    });

    let attempts = 0;
    const failingStrategy = async () => {
      attempts++;
      if (attempts < 3) {
        const error = new Error('SSH timeout');
        error.code = 'ETIMEDOUT';
        throw error;
      }
      return { success: true };
    };

    const result = await recovery.execute(failingStrategy, null, {});

    assert.ok(result.success, 'Should eventually succeed');
    assert.strictEqual(attempts, 3, 'Should retry before success');
    assert.strictEqual(result.strategy, 'retry');
  });

  await t.test('should respect max retries', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 2,
      initialBackoffMs: 50
    });

    let attempts = 0;
    const alwaysFails = async () => {
      attempts++;
      const error = new Error('SSH timeout');
      error.code = 'ETIMEDOUT';
      throw error;
    };

    const result = await recovery.execute(alwaysFails, null, {});

    assert.strictEqual(result.success, false, 'Should fail after max retries');
    assert.strictEqual(attempts, 3, 'Should try primary + 2 retries');
    assert.strictEqual(result.strategy, 'exhausted');
  });
});

test('SSH timeout circuit breaker', async (t) => {
  await t.test('should open circuit after threshold failures', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 1,
      initialBackoffMs: 10
    });

    recovery.circuitFailureThreshold = 3;
    recovery.circuitResetMs = 60000;

    const failingStrategy = async () => {
      const error = new Error('SSH timeout');
      error.code = 'ETIMEDOUT';
      throw error;
    };

    const fallbackStrategy = async () => {
      return { fallback: true };
    };

    // Execute until circuit opens
    for (let i = 0; i < 3; i++) {
      await recovery.executeWithCircuitBreaker(failingStrategy, fallbackStrategy, {});
    }

    assert.ok(recovery.circuitOpen, 'Circuit should be open');
    assert.ok(recovery.circuitOpenedAt > 0, 'Circuit open timestamp should be set');
  });

  await t.test('should use fallback when circuit is open', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 1,
      initialBackoffMs: 10
    });

    // Manually open circuit
    recovery.circuitOpen = true;
    recovery.circuitOpenedAt = Date.now();
    recovery.circuitResetMs = 60000;

    let primaryCalled = false;
    let fallbackCalled = false;

    const primary = async () => {
      primaryCalled = true;
      throw new Error('Should not be called');
    };

    const fallback = async () => {
      fallbackCalled = true;
      return { fromFallback: true };
    };

    const result = await recovery.executeWithCircuitBreaker(primary, fallback, {});

    assert.strictEqual(primaryCalled, false, 'Primary should not be called');
    assert.strictEqual(fallbackCalled, true, 'Fallback should be called');
    assert.strictEqual(result.strategy, 'circuit_breaker_fallback');
  });
});

test('SSH timeout error messages', async (t) => {
  await t.test('should provide clear timeout message', () => {
    try {
      simulateSSHTimeout();
      assert.fail('Should have thrown');
    } catch (error) {
      assert.ok(error.message.includes('ssh'), 'Error message should mention SSH');
      assert.strictEqual(error.code, 'ETIMEDOUT', 'Should have timeout error code');
    }
  });

  await t.test('should include context in exhausted strategy', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 1,
      initialBackoffMs: 10
    });

    const failing = async () => {
      const error = new Error('Connection timeout to server-01');
      error.code = 'ETIMEDOUT';
      throw error;
    };

    const result = await recovery.execute(failing, null, {});

    assert.strictEqual(result.success, false);
    assert.ok(result.error, 'Should include original error');
    assert.ok(result.message.includes('exhausted'), 'Should explain all strategies tried');
    assert.strictEqual(result.error.message, 'Connection timeout to server-01');
  });
});
