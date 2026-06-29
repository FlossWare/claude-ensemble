/**
 * Tests for recovery-chain-utils.js
 *
 * Run with: jest recovery-chain-utils.test.js
 */

const {
  TimeoutError,
  ValidationError,
  InsufficientResults,
  AllAttemptsFailedError,
  executeWithTimeout,
  WorkerTimeoutTracker,
  ServiceHealthCheck,
  tryFallbackChain,
  getFallbackChain,
  gatherResultsWithPartialAcceptance,
  AdaptiveWorkerSelection,
  ErrorLearningTracker,
  CircuitBreaker
} = require('./recovery-chain-utils.js');

describe('Error Recovery Chain Utils', () => {
  // ========================================================================
  // TIMEOUT TESTS
  // ========================================================================

  describe('executeWithTimeout', () => {
    test('completes successfully within timeout', async () => {
      const fn = (signal) => Promise.resolve('success');
      const result = await executeWithTimeout(fn, 1000);
      expect(result).toBe('success');
    });

    test('throws TimeoutError on timeout', async () => {
      const fn = (signal) => new Promise(r => setTimeout(r, 5000));
      await expect(executeWithTimeout(fn, 100))
        .rejects
        .toThrow(TimeoutError);
    });

    test('provides abort signal to function', async () => {
      let signalReceived = null;
      const fn = (signal) => {
        signalReceived = signal;
        return Promise.resolve('ok');
      };
      await executeWithTimeout(fn, 1000);
      expect(signalReceived).toBeTruthy();
      expect(signalReceived.aborted).toBe(false);
    });

    test('aborts signal on timeout', async () => {
      let signal = null;
      const fn = (s) => {
        signal = s;
        return new Promise(r => setTimeout(r, 5000));
      };
      try {
        await executeWithTimeout(fn, 100);
      } catch (e) {
        expect(signal.aborted).toBe(true);
      }
    });
  });

  describe('WorkerTimeoutTracker', () => {
    test('returns default timeout for unknown model', () => {
      const tracker = new WorkerTimeoutTracker(30000);
      expect(tracker.getTimeout('unknown-model')).toBe(30000);
    });

    test('returns model-specific timeouts', () => {
      const tracker = new WorkerTimeoutTracker();
      expect(tracker.getTimeout('opus')).toBe(45000);
      expect(tracker.getTimeout('haiku')).toBe(20000);
    });

    test('tracks timeout metrics', () => {
      const tracker = new WorkerTimeoutTracker();
      tracker.recordTimeout('opus', 40000, false);
      tracker.recordTimeout('opus', 50000, true); // exceeded

      const metrics = tracker.getMetrics('opus');
      expect(metrics.attempts).toBe(2);
      expect(metrics.timeouts).toBe(1);
      expect(metrics.timeoutRate).toBeCloseTo(0.5);
    });

    test('recalibrates timeout after history', () => {
      const tracker = new WorkerTimeoutTracker();

      // Record 10 attempts
      for (let i = 0; i < 10; i++) {
        tracker.recordTimeout('sonnet', 25000 + (i * 100), false);
      }

      // Should have adjusted timeout
      const adjusted = tracker.getTimeout('sonnet');
      expect(adjusted).toBeGreaterThan(30000);
    });
  });

  // ========================================================================
  // HEALTH CHECK TESTS
  // ========================================================================

  describe('ServiceHealthCheck', () => {
    test('records successful health check', async () => {
      const health = new ServiceHealthCheck();
      const checkFn = () => Promise.resolve(true);

      const result = await health.checkHealth('service-a', checkFn);
      expect(result).toBe(true);
      expect(health.getScore('service-a')).toBe(100);
    });

    test('records failed health check', async () => {
      const health = new ServiceHealthCheck();
      const checkFn = () => Promise.reject(new Error('down'));

      const result = await health.checkHealth('service-b', checkFn);
      expect(result).toBe(false);
      expect(health.getScore('service-b')).toBe(80);
    });

    test('implements circuit breaker with backoff', async () => {
      const health = new ServiceHealthCheck({
        backoffs: [10, 50, 100]
      });

      const checkFn = () => Promise.reject(new Error('down'));

      // First failure: wait 10ms
      await health.checkHealth('service', checkFn);
      expect(health.getState('service').failCount).toBe(1);

      // Within backoff: should skip check
      const cached = await health.checkHealth('service', async () => {
        throw new Error('should not reach');
      });
      expect(cached).toBe(false); // Returns cached false
    });

    test('degrades score with failures', () => {
      const health = new ServiceHealthCheck();

      health.recordFailure('service');
      expect(health.getScore('service')).toBe(80);

      health.recordFailure('service');
      expect(health.getScore('service')).toBe(60);

      health.recordFailure('service');
      expect(health.getScore('service')).toBe(40);
    });

    test('recovers on success', () => {
      const health = new ServiceHealthCheck();

      health.recordFailure('service');
      health.recordFailure('service');
      expect(health.getScore('service')).toBe(60);

      health.recordSuccess('service');
      expect(health.getScore('service')).toBe(100);
    });
  });

  // ========================================================================
  // FALLBACK CHAIN TESTS
  // ========================================================================

  describe('tryFallbackChain', () => {
    test('returns result from first successful attempt', async () => {
      const attempts = [
        { label: 'a', fn: () => Promise.reject(new Error('fail')), retryable: true },
        { label: 'b', fn: () => Promise.resolve('success'), retryable: true },
        { label: 'c', fn: () => Promise.resolve('should-not-reach'), retryable: true }
      ];

      const result = await tryFallbackChain(attempts);
      expect(result).toBe('success');
    });

    test('throws on non-retryable error', async () => {
      const attempts = [
        { label: 'a', fn: () => Promise.reject(new Error('fail')), retryable: false }
      ];

      await expect(tryFallbackChain(attempts))
        .rejects
        .toThrow('fail');
    });

    test('throws AllAttemptsFailedError when all fail', async () => {
      const attempts = [
        { label: 'a', fn: () => Promise.reject(new Error('fail-a')), retryable: true },
        { label: 'b', fn: () => Promise.reject(new Error('fail-b')), retryable: true }
      ];

      await expect(tryFallbackChain(attempts))
        .rejects
        .toThrow(AllAttemptsFailedError);
    });

    test('supports custom logging', async () => {
      const logs = [];
      const logFn = (msg) => logs.push(msg);

      const attempts = [
        { label: 'test', fn: () => Promise.resolve('ok'), retryable: true }
      ];

      await tryFallbackChain(attempts, { logFn });
      expect(logs.some(l => l.includes('Attempt'))).toBe(true);
      expect(logs.some(l => l.includes('Success'))).toBe(true);
    });
  });

  describe('getFallbackChain', () => {
    test('returns fallback chain for gpt-4o', () => {
      const chain = getFallbackChain('gpt-4o');
      expect(chain).toHaveLength(3);
      expect(chain[0].model).toBe('gpt-4o');
      expect(chain[1].model).toBe('opus');
      expect(chain[2].model).toBe('sonnet');
    });

    test('returns fallback chain for opus', () => {
      const chain = getFallbackChain('opus');
      expect(chain[0].model).toBe('opus');
      expect(chain[1].model).toBe('sonnet');
      expect(chain[2].model).toBe('haiku');
    });

    test('returns minimal chain for haiku', () => {
      const chain = getFallbackChain('haiku');
      expect(chain).toHaveLength(1);
      expect(chain[0].model).toBe('haiku');
    });

    test('defaults to sonnet for unknown models', () => {
      const chain = getFallbackChain('unknown');
      expect(chain[0].model).toBe('sonnet');
    });
  });

  // ========================================================================
  // PARTIAL RESULTS TESTS
  // ========================================================================

  describe('gatherResultsWithPartialAcceptance', () => {
    test('accepts results with sufficient count', async () => {
      const workers = [
        { model: 'a', fn: async () => ({ answer: '1' }) },
        { model: 'b', fn: async () => ({ answer: '2' }) },
        { model: 'c', fn: async () => ({ answer: '3' }) }
      ];

      const result = await gatherResultsWithPartialAcceptance(workers, {
        minResults: 2
      });

      expect(result.results).toHaveLength(3);
      expect(result.coverage).toBe(1.0);
      expect(result.degradationLevel).toBe(0.0);
    });

    test('accepts partial results', async () => {
      const workers = [
        { model: 'a', fn: async () => ({ answer: '1' }) },
        { model: 'b', fn: async () => { throw new Error('fail'); } },
        { model: 'c', fn: async () => ({ answer: '3' }) }
      ];

      const result = await gatherResultsWithPartialAcceptance(workers, {
        minResults: 2
      });

      expect(result.results).toHaveLength(2);
      expect(result.errors).toHaveLength(1);
      expect(result.coverage).toBeCloseTo(2/3);
      expect(result.degradationLevel).toBeCloseTo(1/3);
    });

    test('throws on insufficient results', async () => {
      const workers = [
        { model: 'a', fn: async () => { throw new Error('fail'); } },
        { model: 'b', fn: async () => { throw new Error('fail'); } }
      ];

      await expect(gatherResultsWithPartialAcceptance(workers, {
        minResults: 2
      }))
        .rejects
        .toThrow(InsufficientResults);
    });

    test('validates results with custom function', async () => {
      const validateFn = (r) => {
        if (!r.answer) throw new Error('Missing answer');
      };

      const workers = [
        { model: 'a', fn: async () => ({ answer: 'ok' }) },
        { model: 'b', fn: async () => ({ answer: null }) },
        { model: 'c', fn: async () => ({ answer: 'ok' }) }
      ];

      const result = await gatherResultsWithPartialAcceptance(workers, {
        minResults: 2,
        validateFn
      });

      expect(result.results).toHaveLength(2);
      expect(result.errors).toHaveLength(1);
    });

    test('enforces timeout per worker', async () => {
      const workers = [
        { model: 'a', fn: async () => new Promise(r => setTimeout(r, 5000)) }
      ];

      await expect(gatherResultsWithPartialAcceptance(workers, {
        minResults: 1,
        timeoutMs: 100
      }))
        .rejects
        .toThrow();
    });
  });

  // ========================================================================
  // ADAPTIVE SELECTION TESTS
  // ========================================================================

  describe('AdaptiveWorkerSelection', () => {
    test('selects workers based on failure rate', () => {
      const selection = new AdaptiveWorkerSelection(['a', 'b', 'c', 'd']);

      // No failures: prefer preferred count
      const workers1 = selection.selectWorkers(['a', 'b', 'c', 'd'], 0.0);
      expect(workers1.length).toBe(3);

      // 50% failure rate: scale back
      const workers2 = selection.selectWorkers(['a', 'b', 'c', 'd'], 0.5);
      expect(workers2.length).toBeLessThan(3);
    });

    test('maintains minimum worker count', () => {
      const selection = new AdaptiveWorkerSelection(['a']);
      const workers = selection.selectWorkers(['a'], 0.9, { minWorkers: 1 });
      expect(workers.length).toBe(1);
    });

    test('prefers fast models on high failure rate', () => {
      const selection = new AdaptiveWorkerSelection([
        'gpt-4o',  // slow: 4
        'opus',    // slow: 3
        'sonnet',  // mid: 2
        'haiku'    // fast: 1
      ]);

      const workers = selection.selectWorkers(
        ['gpt-4o', 'opus', 'sonnet', 'haiku'],
        0.6
      );

      // Should prefer haiku and sonnet
      expect(workers[0]).toBe('haiku');
    });

    test('builds degraded schema on high degradation', () => {
      const selection = new AdaptiveWorkerSelection();
      const fullSchema = {
        type: 'object',
        properties: {
          answer: { type: 'string' },
          confidence: { type: 'number' },
          extra: { type: 'string' }
        },
        required: ['answer', 'confidence']
      };

      const degraded = selection.buildDegradedSchema(fullSchema, 0.7);

      // Should keep only required fields
      expect(Object.keys(degraded.properties)).toEqual(['answer', 'confidence']);
    });
  });

  // ========================================================================
  // LEARNING TRACKER TESTS
  // ========================================================================

  describe('ErrorLearningTracker', () => {
    test('records failures', () => {
      const tracker = new ErrorLearningTracker();
      tracker.recordFailure({
        model: 'opus',
        stage: 'worker',
        error: 'timeout'
      });

      expect(tracker.failures).toHaveLength(1);
      expect(tracker.failures[0].resolved).toBe(false);
    });

    test('records resolution', () => {
      const tracker = new ErrorLearningTracker();
      tracker.recordFailure({
        model: 'opus',
        stage: 'worker',
        error: 'timeout'
      });

      const failureId = tracker.failures[0].id;
      tracker.recordResolution(failureId, 'fallback-to-sonnet', true);

      expect(tracker.failures[0].resolved).toBe(true);
      expect(tracker.failures[0].resolution).toBe('fallback-to-sonnet');
    });

    test('calculates model reliability', () => {
      const tracker = new ErrorLearningTracker();

      tracker.recordFailure({ model: 'opus', stage: 'worker' });
      tracker.recordFailure({ model: 'opus', stage: 'worker' });
      tracker.recordFailure({ model: 'opus', stage: 'worker' });

      const reliability = tracker.getModelReliability('opus', Infinity);
      expect(reliability.attempts).toBe(3);
      expect(reliability.failures).toBe(3);
      expect(reliability.reliability).toBe(0);
    });

    test('filters by time window', () => {
      const tracker = new ErrorLearningTracker();

      tracker.recordFailure({ model: 'opus', stage: 'worker' });
      tracker.failures[0].timestamp = Date.now() - 1000000; // old

      tracker.recordFailure({ model: 'opus', stage: 'worker' });

      const reliability = tracker.getModelReliability('opus', 100000); // 100s window
      expect(reliability.attempts).toBe(1); // only recent
    });

    test('generates metrics', () => {
      const tracker = new ErrorLearningTracker();

      tracker.recordFailure({ model: 'opus', stage: 'worker' });
      tracker.recordFailure({ model: 'sonnet', stage: 'arbiter' });

      const metrics = tracker.getMetrics();
      expect(metrics.totalFailures).toBe(2);
      expect(metrics.byModel['opus']).toBe(1);
      expect(metrics.byStage['worker']).toBe(1);
    });
  });

  // ========================================================================
  // CIRCUIT BREAKER TESTS
  // ========================================================================

  describe('CircuitBreaker', () => {
    test('executes function in closed state', async () => {
      const breaker = new CircuitBreaker();
      const fn = jest.fn().mockResolvedValue('success');

      const result = await breaker.execute('service', fn);
      expect(result).toBe('success');
    });

    test('trips breaker on failure threshold', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 3 });
      const fn = jest.fn().mockRejectedValue(new Error('fail'));

      // Fail 3 times
      for (let i = 0; i < 3; i++) {
        try {
          await breaker.execute('service', fn);
        } catch (e) {}
      }

      const state = breaker.getState('service');
      expect(state.status).toBe('open');
    });

    test('rejects while breaker is open', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 1, resetMs: 1000 });
      const fn = jest.fn().mockRejectedValue(new Error('fail'));

      // Trip the breaker
      try {
        await breaker.execute('service', fn);
      } catch (e) {}

      // Should throw immediately without calling fn
      fn.mockClear();
      await expect(breaker.execute('service', fn))
        .rejects
        .toThrow('Circuit breaker open');
      expect(fn).not.toHaveBeenCalled();
    });

    test('transitions to half-open after reset window', async () => {
      const breaker = new CircuitBreaker({
        failureThreshold: 1,
        resetMs: 10
      });
      const fn = jest.fn().mockRejectedValue(new Error('fail'));

      // Trip breaker
      try {
        await breaker.execute('service', fn);
      } catch (e) {}

      // Wait for reset window
      await new Promise(r => setTimeout(r, 20));

      const state = breaker.getState('service');
      expect(state.status).toBe('half-open');
    });

    test('closes breaker on successful retry', async () => {
      const breaker = new CircuitBreaker({
        failureThreshold: 1,
        resetMs: 10
      });
      let fn = jest.fn().mockRejectedValue(new Error('fail'));

      // Trip breaker
      try {
        await breaker.execute('service', fn);
      } catch (e) {}

      // Wait for reset
      await new Promise(r => setTimeout(r, 20));

      // Succeed (should close breaker)
      fn = jest.fn().mockResolvedValue('success');
      await breaker.execute('service', fn);

      const state = breaker.getState('service');
      expect(state.status).toBe('closed');
    });

    test('can reset manually', () => {
      const breaker = new CircuitBreaker();
      breaker.recordFailure('service');
      expect(breaker.getState('service').failCount).toBe(1);

      breaker.reset('service');
      expect(breaker.getState('service').failCount).toBe(0);
    });
  });
});
