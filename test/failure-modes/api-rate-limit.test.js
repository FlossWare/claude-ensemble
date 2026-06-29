/**
 * API Rate Limit Failure Test
 *
 * Tests the system's behavior when API providers return 429 (Too Many Requests).
 * Verifies:
 * - 429 responses are detected and handled
 * - Retry-After header is respected
 * - Exponential backoff is applied
 * - Circuit breaker prevents rapid retry
 * - Alternative models are used when available
 */

import { strict as assert } from 'assert';
import { test } from 'node:test';

// Mock API rate limit error
function simulateRateLimitError(retryAfterSeconds = null) {
  const error = new Error('Rate limit exceeded');
  error.statusCode = 429;
  error.code = 'RATE_LIMIT_EXCEEDED';
  if (retryAfterSeconds) {
    error.retryAfter = retryAfterSeconds;
  }
  throw error;
}

test('API rate limit detection', async (t) => {
  await t.test('should detect 429 status code', () => {
    try {
      simulateRateLimitError();
      assert.fail('Should have thrown rate limit error');
    } catch (error) {
      assert.strictEqual(error.statusCode, 429);
      assert.strictEqual(error.code, 'RATE_LIMIT_EXCEEDED');
      assert.ok(error.message.includes('Rate limit'));
    }
  });

  await t.test('should extract Retry-After header', () => {
    try {
      simulateRateLimitError(60);
      assert.fail('Should have thrown');
    } catch (error) {
      assert.strictEqual(error.retryAfter, 60);
    }
  });
});

test('API rate limit retry logic', async (t) => {
  await t.test('should respect Retry-After header', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 3,
      initialBackoffMs: 100,
      maxBackoffMs: 5000
    });

    let attempts = 0;
    const timestamps = [];

    const rateLimitedAPI = async () => {
      attempts++;
      timestamps.push(Date.now());

      if (attempts === 1) {
        // First call: rate limited with Retry-After
        simulateRateLimitError(1); // 1 second retry
      }

      return { success: true, attempt: attempts };
    };

    const start = Date.now();
    const result = await recovery.execute(rateLimitedAPI, null, {});

    const duration = Date.now() - start;

    assert.ok(result.success, 'Should eventually succeed');
    assert.strictEqual(attempts, 2, 'Should retry after rate limit');
    assert.ok(duration >= 1000, 'Should wait for Retry-After period');
  });

  await t.test('should use exponential backoff without Retry-After', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 3,
      initialBackoffMs: 200,
      maxBackoffMs: 3000
    });

    let attempts = 0;
    const timestamps = [];

    const rateLimitedAPI = async () => {
      attempts++;
      timestamps.push(Date.now());

      if (attempts < 3) {
        simulateRateLimitError(); // No Retry-After header
      }

      return { success: true };
    };

    const result = await recovery.execute(rateLimitedAPI, null, {});

    assert.ok(result.success, 'Should eventually succeed');
    assert.strictEqual(attempts, 3);

    // Verify exponential backoff
    if (timestamps.length >= 3) {
      const gap1 = timestamps[1] - timestamps[0];
      const gap2 = timestamps[2] - timestamps[1];

      assert.ok(gap1 >= 200, 'First backoff should be at least 200ms');
      assert.ok(gap2 >= gap1, 'Second backoff should be >= first');
    }
  });

  await t.test('should cap backoff at maxBackoffMs', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 5,
      initialBackoffMs: 100,
      maxBackoffMs: 500 // Cap at 500ms
    });

    let attempts = 0;
    const timestamps = [];

    const rateLimitedAPI = async () => {
      attempts++;
      timestamps.push(Date.now());

      if (attempts < 4) {
        simulateRateLimitError();
      }

      return { success: true };
    };

    await recovery.execute(rateLimitedAPI, null, {});

    // Later backoffs should not exceed maxBackoffMs
    if (timestamps.length >= 4) {
      const gap3 = timestamps[3] - timestamps[2];
      assert.ok(gap3 <= 700, 'Backoff should be capped at maxBackoffMs + jitter');
    }
  });
});

test('API rate limit circuit breaker', async (t) => {
  await t.test('should open circuit after repeated rate limits', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    recovery.circuitFailureThreshold = 3;
    recovery.circuitResetMs = 30000;

    const rateLimitedAPI = async () => {
      simulateRateLimitError();
    };

    const fallbackAPI = async () => {
      return { provider: 'alternative', success: true };
    };

    // Trigger circuit breaker
    for (let i = 0; i < 3; i++) {
      await recovery.executeWithCircuitBreaker(rateLimitedAPI, fallbackAPI, {});
    }

    assert.ok(recovery.circuitOpen, 'Circuit should be open');
    assert.strictEqual(recovery.circuitFailures, 3);
  });

  await t.test('should use fallback API when circuit is open', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    // Open circuit
    recovery.circuitOpen = true;
    recovery.circuitOpenedAt = Date.now();
    recovery.circuitResetMs = 60000;

    let primaryCalls = 0;
    let fallbackCalls = 0;

    const primary = async () => {
      primaryCalls++;
      simulateRateLimitError();
    };

    const fallback = async () => {
      fallbackCalls++;
      return { model: 'haiku', provider: 'openrouter' };
    };

    const result = await recovery.executeWithCircuitBreaker(primary, fallback, {});

    assert.strictEqual(primaryCalls, 0, 'Primary should be skipped');
    assert.strictEqual(fallbackCalls, 1, 'Fallback should be used');
    assert.ok(result.success);
    assert.strictEqual(result.result.model, 'haiku');
  });
});

test('API rate limit alternative strategies', async (t) => {
  await t.test('should try alternative API providers', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => ({ provider: 'openrouter', model: 'sonnet', result: 'success' }),
        async () => ({ provider: 'local', model: 'llama', result: 'success' })
      ]
    });

    const rateLimitedPrimary = async () => {
      simulateRateLimitError(60);
    };

    const result = await recovery.execute(rateLimitedPrimary, null, {});

    assert.ok(result.success, 'Should succeed via alternative provider');
    assert.strictEqual(result.strategy, 'alternative_1');
    assert.strictEqual(result.result.provider, 'openrouter');
  });

  await t.test('should fallback through multiple providers', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10,
      alternativeStrategies: [
        async () => { simulateRateLimitError(); }, // First alternative also rate limited
        async () => ({ provider: 'local-ollama', model: 'llama', result: 'success' })
      ]
    });

    const rateLimitedPrimary = async () => {
      simulateRateLimitError();
    };

    const result = await recovery.execute(rateLimitedPrimary, null, {});

    assert.ok(result.success, 'Should succeed via second alternative');
    assert.strictEqual(result.strategy, 'alternative_2');
    assert.strictEqual(result.result.provider, 'local-ollama');
  });
});

test('API rate limit error messages', async (t) => {
  await t.test('should provide clear rate limit message', () => {
    try {
      simulateRateLimitError(120);
      assert.fail('Should have thrown');
    } catch (error) {
      assert.ok(error.message.includes('Rate limit'));
      assert.strictEqual(error.statusCode, 429);
      assert.strictEqual(error.retryAfter, 120);
    }
  });

  await t.test('should include retry guidance when exhausted', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;
    const recovery = new ErrorRecovery({
      maxRetries: 2,
      initialBackoffMs: 10
    });

    const alwaysRateLimited = async () => {
      simulateRateLimitError(300);
    };

    const result = await recovery.execute(alwaysRateLimited, null, {});

    assert.strictEqual(result.success, false);
    assert.ok(result.error, 'Should include original error');
    assert.strictEqual(result.error.retryAfter, 300);
    assert.ok(result.message.includes('exhausted'));
    assert.ok(result.attempts >= 3, 'Should report all attempts');
  });
});

test('API rate limit with cost tracking', async (t) => {
  await t.test('should switch to cheaper model when rate limited', async () => {
    const ErrorRecovery = (await import('../../lib/error-recovery-fallback.js')).default;

    // Simulate: opus rate limited → fallback to sonnet
    const recovery = new ErrorRecovery({
      maxRetries: 0,
      initialBackoffMs: 10
    });

    const expensiveModel = async () => {
      simulateRateLimitError();
    };

    const cheaperModel = async () => {
      return {
        model: 'sonnet',
        cost_per_1k_tokens: 0.003,
        result: 'success'
      };
    };

    const result = await recovery.execute(expensiveModel, cheaperModel, {});

    assert.ok(result.success);
    assert.strictEqual(result.strategy, 'fallback');
    assert.strictEqual(result.result.model, 'sonnet');
    assert.ok(result.result.cost_per_1k_tokens < 0.01, 'Should use cheaper model');
  });
});
