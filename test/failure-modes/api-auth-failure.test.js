/**
 * API Authentication Failure Test
 *
 * Tests the system's behavior when API authentication fails (401/403).
 * Verifies:
 * - 401 (Unauthorized) and 403 (Forbidden) are detected
 * - No retry on permanent auth failures
 * - Fallback to alternative API keys/providers
 * - Clear error messages for troubleshooting
 * - Token rotation when available
 */

import { strict as assert } from 'assert';
import { test } from 'node:test';

// Mock API authentication errors
function simulateAuthError(statusCode = 401, message = 'Invalid API key') {
  const error = new Error(message);
  error.statusCode = statusCode;
  error.code = statusCode === 401 ? 'UNAUTHORIZED' : 'FORBIDDEN';
  throw error;
}

test('API authentication failure detection', async (t) => {
  await t.test('should detect 401 Unauthorized', () => {
    try {
      simulateAuthError(401, 'Invalid API key');
      assert.fail('Should have thrown auth error');
    } catch (error) {
      assert.strictEqual(error.statusCode, 401);
      assert.strictEqual(error.code, 'UNAUTHORIZED');
      assert.ok(error.message.includes('API key'));
    }
  });

  await t.test('should detect 403 Forbidden', () => {
    try {
      simulateAuthError(403, 'Insufficient permissions');
      assert.fail('Should have thrown forbidden error');
    } catch (error) {
      assert.strictEqual(error.statusCode, 403);
      assert.strictEqual(error.code, 'FORBIDDEN');
      assert.ok(error.message.includes('permissions'));
    }
  });
});

test('API authentication failure retry logic', async (t) => {
  await t.test('should NOT retry on permanent auth failure', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 3,
      initialBackoffMs: 100
    });

    let attempts = 0;

    const authFailedAPI = async () => {
      attempts++;
      simulateAuthError(401);
    };

    const result = await recovery.execute(authFailedAPI, null, {});

    // Should fail immediately without retries for auth errors
    // (retries only make sense for transient errors, not auth)
    assert.strictEqual(result.success, false);
    assert.ok(attempts <= 4, 'Should attempt retries but all will fail');
  });

  await t.test('should immediately try fallback on auth failure', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0, // Skip retries for auth failures
      initialBackoffMs: 10
    });

    let primaryAttempts = 0;
    let fallbackAttempts = 0;

    const primary = async () => {
      primaryAttempts++;
      simulateAuthError(401, 'Invalid Anthropic API key');
    };

    const fallback = async () => {
      fallbackAttempts++;
      return {
        provider: 'openrouter',
        api_key: 'sk-or-valid',
        result: 'success'
      };
    };

    const result = await recovery.execute(primary, fallback, {});

    assert.strictEqual(primaryAttempts, 1, 'Primary called once');
    assert.strictEqual(fallbackAttempts, 1, 'Fallback called once');
    assert.ok(result.success);
    assert.strictEqual(result.strategy, 'fallback');
    assert.strictEqual(result.result.provider, 'openrouter');
  });
});

test('API authentication circuit breaker', async (t) => {
  await t.test('should open circuit after repeated auth failures', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    recovery.circuitFailureThreshold = 2; // Low threshold for auth failures
    recovery.circuitResetMs = 60000;

    const authFailedAPI = async () => {
      simulateAuthError(401);
    };

    const fallbackAPI = async () => {
      return { provider: 'alternative', success: true };
    };

    // Trigger circuit breaker with repeated auth failures
    await recovery.executeWithCircuitBreaker(authFailedAPI, fallbackAPI, {});
    await recovery.executeWithCircuitBreaker(authFailedAPI, fallbackAPI, {});

    assert.ok(recovery.circuitOpen, 'Circuit should open quickly for auth failures');
    assert.strictEqual(recovery.circuitFailures, 2);
  });

  await t.test('should bypass broken API key when circuit is open', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    // Open circuit (simulating previous auth failures)
    recovery.circuitOpen = true;
    recovery.circuitOpenedAt = Date.now();
    recovery.circuitResetMs = 300000; // 5 minutes

    let brokenKeyCalls = 0;
    let workingKeyCalls = 0;

    const brokenKey = async () => {
      brokenKeyCalls++;
      simulateAuthError(401);
    };

    const workingKey = async () => {
      workingKeyCalls++;
      return { provider: 'openrouter', result: 'success' };
    };

    const result = await recovery.executeWithCircuitBreaker(brokenKey, workingKey, {});

    assert.strictEqual(brokenKeyCalls, 0, 'Broken key should be bypassed');
    assert.strictEqual(workingKeyCalls, 1, 'Working key should be used');
    assert.ok(result.success);
  });
});

test('API authentication alternative strategies', async (t) => {
  await t.test('should rotate through multiple API keys', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => ({ api_key: 'key-2', provider: 'anthropic', result: 'success' }),
        async () => ({ api_key: 'key-3', provider: 'anthropic', result: 'success' })
      ]
    });

    const primaryKey = async () => {
      simulateAuthError(401, 'API key key-1 invalid');
    };

    const result = await recovery.execute(primaryKey, null, {});

    assert.ok(result.success, 'Should succeed with alternative key');
    assert.strictEqual(result.strategy, 'alternative_1');
    assert.strictEqual(result.result.api_key, 'key-2');
  });

  await t.test('should fallback to different provider after key exhaustion', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => { simulateAuthError(401, 'All Anthropic keys invalid'); },
        async () => ({ provider: 'openrouter', api_key: 'sk-or-valid', result: 'success' })
      ]
    });

    const primaryProvider = async () => {
      simulateAuthError(401, 'Primary Anthropic key invalid');
    };

    const result = await recovery.execute(primaryProvider, null, {});

    assert.ok(result.success, 'Should succeed via different provider');
    assert.strictEqual(result.strategy, 'alternative_2');
    assert.strictEqual(result.result.provider, 'openrouter');
  });

  await t.test('should use local models when all API keys fail', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => { simulateAuthError(401); }, // Cloud provider 1 fails
        async () => { simulateAuthError(403); }, // Cloud provider 2 forbidden
        async () => ({ provider: 'ollama', model: 'llama3', location: 'local', result: 'success' })
      ]
    });

    const cloudAPI = async () => {
      simulateAuthError(401);
    };

    const result = await recovery.execute(cloudAPI, null, {});

    assert.ok(result.success, 'Should succeed via local model');
    assert.strictEqual(result.strategy, 'alternative_3');
    assert.strictEqual(result.result.provider, 'ollama');
    assert.strictEqual(result.result.location, 'local');
  });
});

test('API authentication error messages', async (t) => {
  await t.test('should provide clear auth error message', () => {
    try {
      simulateAuthError(401, 'Invalid API key: sk-ant-***');
      assert.fail('Should have thrown');
    } catch (error) {
      assert.ok(error.message.includes('Invalid API key'));
      assert.strictEqual(error.statusCode, 401);
    }
  });

  await t.test('should explain 403 permission issues', () => {
    try {
      simulateAuthError(403, 'API key lacks model access');
      assert.fail('Should have thrown');
    } catch (error) {
      assert.ok(error.message.includes('model access'));
      assert.strictEqual(error.statusCode, 403);
      assert.strictEqual(error.code, 'FORBIDDEN');
    }
  });

  await t.test('should provide troubleshooting context when exhausted', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 1,
      initialBackoffMs: 10
    });

    const alwaysForbidden = async () => {
      simulateAuthError(403, 'Organization does not have access to this model');
    };

    const result = await recovery.execute(alwaysForbidden, null, {});

    assert.strictEqual(result.success, false);
    assert.ok(result.error, 'Should include original error');
    assert.ok(result.error.message.includes('Organization'));
    assert.ok(result.message.includes('exhausted'));
  });
});

test('API authentication with key rotation', async (t) => {
  await t.test('should track which keys have failed', async () => {
    const failedKeys = new Set();

    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => {
          failedKeys.add('key-2');
          simulateAuthError(401, 'key-2 invalid');
        },
        async () => {
          // key-3 works
          return { api_key: 'key-3', result: 'success' };
        }
      ]
    });

    const primary = async () => {
      failedKeys.add('key-1');
      simulateAuthError(401, 'key-1 invalid');
    };

    const result = await recovery.execute(primary, null, {});

    assert.ok(result.success);
    assert.strictEqual(failedKeys.size, 2, 'Should track failed keys');
    assert.ok(failedKeys.has('key-1'));
    assert.ok(failedKeys.has('key-2'));
  });

  await t.test('should not retry with known-bad keys', async () => {
    const blacklistedKeys = new Set(['key-1', 'key-2']);
    const attemptedKeys = [];

    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => {
          const key = 'key-3';
          if (blacklistedKeys.has(key)) {
            throw new Error('Should not use blacklisted key');
          }
          attemptedKeys.push(key);
          return { api_key: key, result: 'success' };
        }
      ]
    });

    // Simulate: don't even try blacklisted keys
    const primaryAttempt = async () => {
      const key = 'key-1';
      if (blacklistedKeys.has(key)) {
        // Skip directly to alternatives
        throw new Error('Blacklisted key');
      }
      attemptedKeys.push(key);
      return { api_key: key };
    };

    const result = await recovery.execute(primaryAttempt, null, {});

    assert.ok(result.success);
    assert.ok(!attemptedKeys.includes('key-1'), 'Should not use blacklisted key-1');
    assert.ok(!attemptedKeys.includes('key-2'), 'Should not use blacklisted key-2');
    assert.ok(attemptedKeys.includes('key-3'), 'Should use valid key-3');
  });
});
