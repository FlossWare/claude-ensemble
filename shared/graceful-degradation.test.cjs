/**
 * Tests for Graceful Degradation module
 *
 * Run: node shared/graceful-degradation.test.cjs
 */

const assert = require('assert');

// Prevent log file writes during tests
process.env.DEGRADATION_LOG_DIR = '/tmp/graceful-degradation-test-logs';
process.env.DEGRADATION_CACHE_TTL_MS = '50'; // short TTL for tests

const {
  executeWithFallback,
  getServiceOrFallback,
  requireService,
  registerService,
  isServiceAvailable,
  clearAvailabilityCache,
  getPrometheusMetrics,
  getMetrics,
  _internals,
} = require('./graceful-degradation.cjs');

let passed = 0;
let failed = 0;
const failures = [];

async function test(name, fn) {
  try {
    clearAvailabilityCache();
    await fn();
    passed++;
    console.log(`  PASS: ${name}`);
  } catch (err) {
    failed++;
    failures.push({ name, error: err.message });
    console.error(`  FAIL: ${name}`);
    console.error(`        ${err.message}`);
  }
}

async function runTests() {
  console.log('=== Graceful Degradation Tests ===\n');

  // ---- registerService ----

  await test('registerService: registers a service with a check function', async () => {
    registerService('test-svc', {
      check: async () => true,
      description: 'Test service',
    });
    assert.ok(_internals.serviceRegistry['test-svc']);
    assert.strictEqual(_internals.serviceRegistry['test-svc'].description, 'Test service');
  });

  await test('registerService: throws on empty name', async () => {
    let threw = false;
    try { registerService(''); } catch (_) { threw = true; }
    assert.ok(threw);
  });

  // ---- isServiceAvailable ----

  await test('isServiceAvailable: returns true for healthy service', async () => {
    registerService('healthy', { check: async () => true });
    const result = await isServiceAvailable('healthy');
    assert.strictEqual(result, true);
  });

  await test('isServiceAvailable: returns false for unhealthy service', async () => {
    registerService('down', { check: async () => false });
    const result = await isServiceAvailable('down');
    assert.strictEqual(result, false);
  });

  await test('isServiceAvailable: returns false for unregistered service', async () => {
    const result = await isServiceAvailable('nonexistent-xyz');
    assert.strictEqual(result, false);
  });

  await test('isServiceAvailable: returns false when check throws', async () => {
    registerService('broken-check', { check: async () => { throw new Error('boom'); } });
    const result = await isServiceAvailable('broken-check');
    assert.strictEqual(result, false);
  });

  await test('isServiceAvailable: caches results within TTL', async () => {
    let callCount = 0;
    registerService('counted', { check: async () => { callCount++; return true; } });
    await isServiceAvailable('counted');
    await isServiceAvailable('counted');
    assert.strictEqual(callCount, 1); // second call used cache
  });

  await test('clearAvailabilityCache: clears specific service', async () => {
    let callCount = 0;
    registerService('cacheable', { check: async () => { callCount++; return true; } });
    await isServiceAvailable('cacheable');
    clearAvailabilityCache('cacheable');
    await isServiceAvailable('cacheable');
    assert.strictEqual(callCount, 2);
  });

  await test('clearAvailabilityCache: clears all when no arg', async () => {
    registerService('a1', { check: async () => true });
    registerService('a2', { check: async () => true });
    await isServiceAvailable('a1');
    await isServiceAvailable('a2');
    clearAvailabilityCache();
    assert.strictEqual(Object.keys(_internals.availabilityCache).length, 0);
  });

  // ---- executeWithFallback ----

  await test('executeWithFallback: invokes fallback when service unavailable', async () => {
    registerService('down-svc', { check: async () => false });
    const { result, degraded } = await executeWithFallback(
      'down-svc',
      'hello',
      async (input) => `fallback:${input}`
    );
    assert.strictEqual(result, 'fallback:hello');
    assert.strictEqual(degraded, true);
  });

  await test('executeWithFallback: invokes primaryFn when service available', async () => {
    registerService('up-svc', { check: async () => true });
    const { result, degraded } = await executeWithFallback(
      'up-svc',
      42,
      async () => 'fallback',
      { primaryFn: async (input) => `primary:${input}` }
    );
    assert.strictEqual(result, 'primary:42');
    assert.strictEqual(degraded, false);
  });

  await test('executeWithFallback: falls back when primaryFn throws', async () => {
    registerService('flaky', { check: async () => true });
    const { result, degraded } = await executeWithFallback(
      'flaky',
      'data',
      async (input) => `fallback:${input}`,
      { primaryFn: async () => { throw new Error('connection reset'); } }
    );
    assert.strictEqual(result, 'fallback:data');
    assert.strictEqual(degraded, true);
  });

  await test('executeWithFallback: throws when both primary and fallback fail', async () => {
    registerService('total-fail', { check: async () => false });
    let threw = false;
    try {
      await executeWithFallback(
        'total-fail',
        null,
        async () => { throw new Error('fallback also broke'); }
      );
    } catch (err) {
      threw = true;
      assert.ok(err.message.includes('Both total-fail and fallback failed'));
    }
    assert.ok(threw);
  });

  await test('executeWithFallback: throws on empty serviceName', async () => {
    let threw = false;
    try { await executeWithFallback('', {}, async () => {}); } catch (_) { threw = true; }
    assert.ok(threw);
  });

  await test('executeWithFallback: throws on non-function fallbackFn', async () => {
    let threw = false;
    try { await executeWithFallback('svc', {}, 'not-a-function'); } catch (_) { threw = true; }
    assert.ok(threw);
  });

  await test('executeWithFallback: returns available signal when no primaryFn and service up', async () => {
    registerService('signal-svc', { check: async () => true });
    const res = await executeWithFallback('signal-svc', null, async () => 'fb');
    assert.strictEqual(res.degraded, false);
    assert.strictEqual(res.available, true);
  });

  // ---- getServiceOrFallback ----

  await test('getServiceOrFallback: returns primary when available', async () => {
    registerService('primary', { check: async () => true });
    registerService('secondary', { check: async () => true });
    const { service, degraded } = await getServiceOrFallback('primary', 'secondary');
    assert.strictEqual(service, 'primary');
    assert.strictEqual(degraded, false);
  });

  await test('getServiceOrFallback: returns fallback when primary down', async () => {
    registerService('p-down', { check: async () => false });
    registerService('s-up', { check: async () => true });
    const { service, degraded } = await getServiceOrFallback('p-down', 's-up');
    assert.strictEqual(service, 's-up');
    assert.strictEqual(degraded, true);
  });

  await test('getServiceOrFallback: throws when both down', async () => {
    registerService('both-d1', { check: async () => false });
    registerService('both-d2', { check: async () => false });
    let threw = false;
    try {
      await getServiceOrFallback('both-d1', 'both-d2');
    } catch (err) {
      threw = true;
      assert.ok(err.message.includes('Neither'));
    }
    assert.ok(threw);
  });

  await test('getServiceOrFallback: throws on empty serviceName', async () => {
    let threw = false;
    try { await getServiceOrFallback('', 'fb'); } catch (_) { threw = true; }
    assert.ok(threw);
  });

  await test('getServiceOrFallback: throws on empty fallbackService', async () => {
    let threw = false;
    try { await getServiceOrFallback('svc', ''); } catch (_) { threw = true; }
    assert.ok(threw);
  });

  // ---- requireService ----

  await test('requireService: resolves when service available', async () => {
    registerService('required-up', { check: async () => true });
    await requireService('required-up'); // should not throw
  });

  await test('requireService: throws when service unavailable', async () => {
    registerService('required-down', { check: async () => false });
    let threw = false;
    try {
      await requireService('required-down');
    } catch (err) {
      threw = true;
      assert.strictEqual(err.code, 'SERVICE_UNAVAILABLE');
      assert.strictEqual(err.service, 'required-down');
    }
    assert.ok(threw);
  });

  await test('requireService: throws on empty name', async () => {
    let threw = false;
    try { await requireService(''); } catch (_) { threw = true; }
    assert.ok(threw);
  });

  // ---- Prometheus metrics ----

  await test('getPrometheusMetrics: returns valid prometheus format', async () => {
    // Trigger some metrics
    registerService('metrics-down', { check: async () => false });
    await executeWithFallback('metrics-down', null, async () => 'ok');

    const output = getPrometheusMetrics();
    assert.ok(output.includes('graceful_degradation_fallback_invocations_total'));
    assert.ok(output.includes('graceful_degradation_fallback_successes_total'));
    assert.ok(output.includes('graceful_degradation_service_available'));
    assert.ok(output.includes('# HELP'));
    assert.ok(output.includes('# TYPE'));
  });

  await test('getMetrics: returns metrics object', async () => {
    const m = getMetrics();
    assert.ok(m.fallback_invocations_total);
    assert.ok(m.service_available);
  });

  // ---- Integration scenario: Neo4j -> PostgreSQL ----

  await test('integration: Neo4j falls back to PostgreSQL CTEs', async () => {
    registerService('neo4j', { check: async () => false });
    registerService('postgres', { check: async () => true });

    const { result, degraded } = await executeWithFallback(
      'neo4j',
      'MATCH (n) RETURN n',
      async (query) => {
        return { engine: 'postgres-cte', rows: 5, query };
      }
    );

    assert.strictEqual(degraded, true);
    assert.strictEqual(result.engine, 'postgres-cte');
    assert.strictEqual(result.rows, 5);
  });

  // ---- Summary ----

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  if (failures.length > 0) {
    console.log('\nFailures:');
    for (const f of failures) {
      console.log(`  - ${f.name}: ${f.error}`);
    }
  }

  // Cleanup test logs
  try {
    const fs = require('fs');
    fs.rmSync('/tmp/graceful-degradation-test-logs', { recursive: true, force: true });
  } catch (_) {}

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
