#!/usr/bin/env node
/**
 * Service Health Monitoring - Test Suite
 *
 * Self-contained tests using InMemoryStore backend.
 * No external dependencies required (no PostgreSQL, no Prometheus).
 *
 * Tests:
 * - InMemoryStore CRUD operations
 * - ServiceHealthMonitor with custom checks
 * - Health scoring and status transitions
 * - Auto-disable unhealthy services
 * - Prometheus metrics format
 * - Scheduler start/stop
 * - Custom check registration
 * - Edge cases and error handling
 *
 * Created: 2026-06-28
 */

'use strict';

const {
  ServiceHealthMonitor,
  InMemoryStore,
  createServiceHealthMonitor,
  config,
  DEFAULT_CONFIG,
} = require('./service-health.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;
let testSections = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  FAIL: ${message}`);
    testsFailed++;
    return false;
  }
  console.log(`  PASS: ${message}`);
  testsPassed++;
  return true;
}

function assertEqual(actual, expected, message) {
  const pass = actual === expected;
  if (!pass) {
    console.error(`  FAIL: ${message} (expected: ${JSON.stringify(expected)}, got: ${JSON.stringify(actual)})`);
    testsFailed++;
  } else {
    console.log(`  PASS: ${message}`);
    testsPassed++;
  }
  return pass;
}

function assertApprox(actual, expected, tolerance, message) {
  const pass = Math.abs(actual - expected) <= tolerance;
  if (!pass) {
    console.error(`  FAIL: ${message} (expected ~${expected}, got ${actual}, tolerance ${tolerance})`);
    testsFailed++;
  } else {
    console.log(`  PASS: ${message}`);
    testsPassed++;
  }
  return pass;
}

function assertGreaterThan(actual, threshold, message) {
  return assert(actual > threshold, `${message} (expected > ${threshold}, got: ${actual})`);
}

function assertIncludes(str, substr, message) {
  return assert(
    typeof str === 'string' && str.includes(substr),
    `${message} (should contain "${substr}")`
  );
}

function section(name) {
  testSections++;
  console.log(`\n=== ${testSections}. ${name} ===`);
}

// ============================================================================
// HELPER: Create a monitor with in-memory store and mock checks
// ============================================================================

function createTestMonitor(customChecks = {}) {
  const store = new InMemoryStore();
  const monitor = createServiceHealthMonitor({
    store,
    config: {
      check_interval_ms: 100,
      health_check_timeout_ms: 1000,
      auto_disable_threshold: 0.50,
      degraded_threshold: 0.75,
      history_window: 20,
    },
    customChecks,
  });
  return { monitor, store };
}

// ============================================================================
// TESTS
// ============================================================================

async function testInMemoryStoreBasics() {
  section('InMemoryStore - Basic Operations');

  const store = new InMemoryStore();

  // Test initial state
  const services = store.getAllServices();
  assertEqual(services.length, 0, 'Empty store should have no services');

  // Test getServiceRecord creates a new record
  const record = store.getServiceRecord('test-service');
  assertEqual(record.service_name, 'test-service', 'Should create record with correct name');
  assertEqual(record.healthy, true, 'New record should default to healthy');
  assertApprox(record.health_score, 1.0, 0.001, 'New record should have health_score 1.0');
  assertEqual(record.status, 'healthy', 'New record should have status healthy');
  assertEqual(record.total_checks, 0, 'New record should have 0 total_checks');

  // Test getAllServices after creation
  const allServices = store.getAllServices();
  assertEqual(allServices.length, 1, 'Should have 1 service after getServiceRecord');
}

async function testInMemoryStoreRecordCheck() {
  section('InMemoryStore - Record Health Checks');

  const store = new InMemoryStore();

  // Record a successful check
  const result1 = store.recordCheck('svc-a', { healthy: true, latency_ms: 15, error: null });
  assertApprox(result1.healthScore, 1.0, 0.001, 'Single success should yield health 1.0');
  assertEqual(result1.status, 'healthy', 'Single success should yield status healthy');

  // Verify record was updated
  const record = store.getServiceRecord('svc-a');
  assertEqual(record.total_checks, 1, 'Should have 1 total check');
  assertEqual(record.successful_checks, 1, 'Should have 1 successful check');
  assertEqual(record.failed_checks, 0, 'Should have 0 failed checks');
  assertEqual(record.last_latency_ms, 15, 'Should record latency');

  // Record a failed check
  const result2 = store.recordCheck('svc-a', { healthy: false, latency_ms: 5000, error: 'Connection refused' });
  assertApprox(result2.healthScore, 0.5, 0.001, 'One pass, one fail should yield health 0.5');
  assertEqual(result2.status, 'degraded', '50% health at threshold boundary should be degraded (>=0.50)');

  // Verify error message is stored
  const updatedRecord = store.getServiceRecord('svc-a');
  assertEqual(updatedRecord.error_message, 'Connection refused', 'Should store error message');
  assertEqual(updatedRecord.total_checks, 2, 'Should have 2 total checks');
}

async function testHealthScoreTransitions() {
  section('InMemoryStore - Health Score Transitions');

  const store = new InMemoryStore();
  const serviceName = 'transition-test';

  // All healthy -> healthy status
  for (let i = 0; i < 5; i++) {
    store.recordCheck(serviceName, { healthy: true, latency_ms: 10, error: null });
  }
  let record = store.getServiceRecord(serviceName);
  assertEqual(record.status, 'healthy', '100% healthy should be healthy status');
  assertApprox(record.health_score, 1.0, 0.001, '100% success rate');

  // Add failures to push to degraded (below 75%)
  for (let i = 0; i < 5; i++) {
    store.recordCheck(serviceName, { healthy: false, latency_ms: 10, error: 'fail' });
  }
  record = store.getServiceRecord(serviceName);
  assertApprox(record.health_score, 0.5, 0.001, '5 pass + 5 fail = 50% health');
  // 50% is >= 0.50 threshold, so it should be degraded (not disabled)
  assertEqual(record.status, 'degraded', '50% health should be degraded');

  // Add more failures to push below auto-disable threshold
  for (let i = 0; i < 10; i++) {
    store.recordCheck(serviceName, { healthy: false, latency_ms: 10, error: 'fail' });
  }
  record = store.getServiceRecord(serviceName);
  // Now we have 5 success + 15 fail = 20 total, last 20 checked
  // 5/20 = 0.25 -> disabled
  assertApprox(record.health_score, 0.25, 0.001, '5 pass + 15 fail out of 20 = 25%');
  assertEqual(record.status, 'disabled', '25% health should be disabled');
}

async function testInMemoryStoreHistory() {
  section('InMemoryStore - History Retrieval');

  const store = new InMemoryStore();

  // Record multiple checks
  for (let i = 0; i < 10; i++) {
    store.recordCheck('hist-svc', { healthy: i % 2 === 0, latency_ms: i * 10, error: null });
  }

  // Get full history
  const history = store.getHistory('hist-svc', 20);
  assertEqual(history.length, 10, 'Should return all 10 checks');

  // Verify ordering (newest first)
  assert(history[0].created_at >= history[1].created_at, 'History should be newest-first');

  // Get limited history
  const limited = store.getHistory('hist-svc', 3);
  assertEqual(limited.length, 3, 'Should respect limit parameter');

  // History for non-existent service
  const empty = store.getHistory('no-such-service', 10);
  assertEqual(empty.length, 0, 'Non-existent service should return empty history');
}

async function testInMemoryStoreDisableUnhealthy() {
  section('InMemoryStore - Disable Unhealthy Services');

  const store = new InMemoryStore();

  // Create a healthy service
  for (let i = 0; i < 5; i++) {
    store.recordCheck('healthy-svc', { healthy: true, latency_ms: 10, error: null });
  }

  // Create an unhealthy service - recordCheck will already mark as disabled
  // because health_score drops below auto_disable_threshold during recording.
  for (let i = 0; i < 5; i++) {
    store.recordCheck('unhealthy-svc', { healthy: false, latency_ms: 5000, error: 'down' });
  }

  // Verify that recordCheck already set it to disabled
  assertEqual(store.getServiceRecord('unhealthy-svc').status, 'disabled',
    'recordCheck should already set disabled status for 0% health');

  // Now manually reset its status to 'degraded' to test disableUnhealthy()
  store.getServiceRecord('unhealthy-svc').status = 'degraded';

  // Create a degraded service
  store.recordCheck('degraded-svc', { healthy: true, latency_ms: 10, error: null });
  store.recordCheck('degraded-svc', { healthy: false, latency_ms: 10, error: 'slow' });
  store.recordCheck('degraded-svc', { healthy: false, latency_ms: 10, error: 'slow' });
  store.recordCheck('degraded-svc', { healthy: true, latency_ms: 10, error: null });
  // 2/4 = 50% -> degraded (at threshold boundary, not disabled)

  // Run auto-disable with 50% threshold
  const disabled = store.disableUnhealthy(0.50);

  // Only the unhealthy service (0% < 50%) should be newly disabled
  assertEqual(disabled.length, 1, 'Should disable 1 service');
  assertEqual(disabled[0], 'unhealthy-svc', 'Should disable the unhealthy service');

  // Verify statuses
  assertEqual(store.getServiceRecord('healthy-svc').status, 'healthy', 'Healthy service stays healthy');
  assertEqual(store.getServiceRecord('unhealthy-svc').status, 'disabled', 'Unhealthy service is disabled');
  assertEqual(store.getServiceRecord('degraded-svc').status, 'degraded', 'Degraded service stays degraded');
}

async function testInMemoryStoreClear() {
  section('InMemoryStore - Clear');

  const store = new InMemoryStore();

  store.recordCheck('svc1', { healthy: true, latency_ms: 10, error: null });
  store.recordCheck('svc2', { healthy: false, latency_ms: 20, error: 'err' });

  assertEqual(store.getAllServices().length, 2, 'Should have 2 services before clear');

  store.clear();

  assertEqual(store.getAllServices().length, 0, 'Should have 0 services after clear');
  assertEqual(store.getHistory('svc1', 10).length, 0, 'History should be empty after clear');
}

async function testServiceHealthMonitorCustomChecks() {
  section('ServiceHealthMonitor - Custom Health Checks');

  const { monitor } = createTestMonitor({
    'custom-healthy': async () => ({ healthy: true, latency_ms: 5, error: null }),
    'custom-unhealthy': async () => ({ healthy: false, latency_ms: 100, error: 'Service down' }),
  });

  try {
    // Check healthy custom service
    const healthyResult = await monitor.checkServiceHealth('custom-healthy');
    assertEqual(healthyResult.healthy, true, 'Custom healthy check should return healthy');
    assertEqual(healthyResult.error, null, 'Custom healthy check should have no error');

    // Check unhealthy custom service
    const unhealthyResult = await monitor.checkServiceHealth('custom-unhealthy');
    assertEqual(unhealthyResult.healthy, false, 'Custom unhealthy check should return unhealthy');
    assertEqual(unhealthyResult.error, 'Service down', 'Custom unhealthy check should have error');

    // Check unknown service
    const unknownResult = await monitor.checkServiceHealth('unknown-service');
    assertEqual(unknownResult.healthy, false, 'Unknown service should be unhealthy');
    assertIncludes(unknownResult.error, 'Unknown service', 'Unknown service should have descriptive error');
  } finally {
    await monitor.close();
  }
}

async function testServiceHealthMonitorCustomCheckThrows() {
  section('ServiceHealthMonitor - Custom Check Error Handling');

  const { monitor } = createTestMonitor({
    'throwing-service': async () => { throw new Error('Connection timeout'); },
  });

  try {
    const result = await monitor.checkServiceHealth('throwing-service');
    assertEqual(result.healthy, false, 'Throwing check should return unhealthy');
    assertEqual(result.error, 'Connection timeout', 'Should capture thrown error message');
    assert(typeof result.latency_ms === 'number', 'Should still measure latency');
  } finally {
    await monitor.close();
  }
}

async function testRegisterUnregisterChecks() {
  section('ServiceHealthMonitor - Register/Unregister Checks');

  const { monitor } = createTestMonitor();

  try {
    // Register a new check
    monitor.registerCheck('redis', async () => ({ healthy: true, latency_ms: 2, error: null }));

    const result = await monitor.checkServiceHealth('redis');
    assertEqual(result.healthy, true, 'Registered check should be callable');

    // Unregister
    monitor.unregisterCheck('redis');

    const result2 = await monitor.checkServiceHealth('redis');
    assertEqual(result2.healthy, false, 'Unregistered check should return unknown service');

    // Register with invalid function should throw
    let threw = false;
    try {
      monitor.registerCheck('bad', 'not a function');
    } catch (err) {
      threw = true;
      assertIncludes(err.message, 'must be a function', 'Should throw descriptive error');
    }
    assert(threw, 'registerCheck with non-function should throw');
  } finally {
    await monitor.close();
  }
}

async function testCheckAllServices() {
  section('ServiceHealthMonitor - Check All Services');

  let callCount = 0;
  const { monitor } = createTestMonitor({
    'postgresql': async () => { callCount++; return { healthy: true, latency_ms: 3 }; },
    'prometheus': async () => { callCount++; return { healthy: true, latency_ms: 5 }; },
    'anthropic': async () => { callCount++; return { healthy: false, latency_ms: 100, error: 'No key' }; },
    'openai': async () => { callCount++; return { healthy: true, latency_ms: 8 }; },
    'google': async () => { callCount++; return { healthy: true, latency_ms: 10 }; },
    'openrouter': async () => { callCount++; return { healthy: false, latency_ms: 200, error: 'Rate limited' }; },
  });

  try {
    const results = await monitor.checkAllServices();

    assertEqual(Object.keys(results).length, 6, 'Should check all 6 default services');
    assertEqual(callCount, 6, 'Should call each check function once');

    assertEqual(results.postgresql.healthy, true, 'PostgreSQL should be healthy');
    assertEqual(results.anthropic.healthy, false, 'Anthropic should be unhealthy');
    assertEqual(results.openrouter.healthy, false, 'OpenRouter should be unhealthy');
    assertEqual(results.openrouter.error, 'Rate limited', 'OpenRouter should have error');
  } finally {
    await monitor.close();
  }
}

async function testRecordAndQuery() {
  section('ServiceHealthMonitor - Record and Query Health');

  const { monitor } = createTestMonitor({
    'db': async () => ({ healthy: true, latency_ms: 2 }),
  });

  try {
    // Record several checks
    await monitor.recordHealthCheck('db', { healthy: true, latency_ms: 2, error: null });
    await monitor.recordHealthCheck('db', { healthy: true, latency_ms: 3, error: null });
    await monitor.recordHealthCheck('db', { healthy: false, latency_ms: 5000, error: 'Timeout' });

    // Query status
    const status = await monitor.getHealthStatus();
    assert(status.length > 0, 'Should have recorded status');

    const dbStatus = status.find(s => s.service_name === 'db');
    assert(dbStatus !== undefined, 'Should find db service');
    assertApprox(dbStatus.health_score, 0.6667, 0.01, '2/3 success = ~66.7%');
    assertEqual(dbStatus.status, 'degraded', '66.7% should be degraded (below 75%)');
    assertEqual(dbStatus.total_checks, 3, 'Should have 3 total checks');
    assertEqual(dbStatus.successful_checks, 2, 'Should have 2 successful checks');
    assertEqual(dbStatus.failed_checks, 1, 'Should have 1 failed check');

    // Query history
    const history = await monitor.getHealthHistory('db', 10);
    assertEqual(history.length, 3, 'Should have 3 history records');
  } finally {
    await monitor.close();
  }
}

async function testRunHealthChecks() {
  section('ServiceHealthMonitor - Run Full Health Check Cycle');

  const { monitor } = createTestMonitor({
    'postgresql': async () => ({ healthy: true, latency_ms: 2 }),
    'prometheus': async () => ({ healthy: true, latency_ms: 5 }),
    'anthropic': async () => ({ healthy: true, latency_ms: 8 }),
    'openai': async () => ({ healthy: true, latency_ms: 10 }),
    'google': async () => ({ healthy: true, latency_ms: 12 }),
    'openrouter': async () => ({ healthy: true, latency_ms: 15 }),
  });

  try {
    const { results, healthy, total } = await monitor.runHealthChecks();

    assertEqual(total, 6, 'Should check 6 services');
    assertEqual(healthy, 6, 'All 6 should be healthy');
    assertEqual(Object.keys(results).length, 6, 'Should return results for all services');

    // Verify status was recorded
    const status = await monitor.getHealthStatus();
    assertEqual(status.length, 6, 'Should have 6 service statuses');

    // All should be healthy
    const allHealthy = status.every(s => s.status === 'healthy');
    assert(allHealthy, 'All services should be healthy');
  } finally {
    await monitor.close();
  }
}

async function testAutoDisableUnhealthy() {
  section('ServiceHealthMonitor - Auto-Disable Unhealthy');

  const { monitor, store } = createTestMonitor({
    'postgresql': async () => ({ healthy: true, latency_ms: 2 }),
    'prometheus': async () => ({ healthy: true, latency_ms: 5 }),
    'anthropic': async () => ({ healthy: true, latency_ms: 8 }),
    'openai': async () => ({ healthy: true, latency_ms: 10 }),
    'google': async () => ({ healthy: true, latency_ms: 12 }),
    'openrouter': async () => ({ healthy: true, latency_ms: 15 }),
  });

  try {
    // Record checks to establish baselines
    for (let i = 0; i < 5; i++) {
      await monitor.recordHealthCheck('good-service', { healthy: true, latency_ms: 5, error: null });
    }
    for (let i = 0; i < 5; i++) {
      await monitor.recordHealthCheck('bad-service', { healthy: false, latency_ms: 5000, error: 'down' });
    }

    // recordCheck already marks bad-service as disabled because health < threshold.
    // Verify that the service was auto-disabled during recording.
    let status = await monitor.getHealthStatus();
    let badStatus = status.find(s => s.service_name === 'bad-service');
    assertEqual(badStatus.status, 'disabled', 'bad-service should already be disabled from recordCheck');

    // Reset to degraded to test autoDisableUnhealthy() explicitly
    store.getServiceRecord('bad-service').status = 'degraded';

    // Run auto-disable
    const disabled = await monitor.autoDisableUnhealthy(0.50);

    assert(disabled.includes('bad-service'), 'bad-service should be disabled by autoDisableUnhealthy');
    assert(!disabled.includes('good-service'), 'good-service should NOT be disabled');

    // Verify via status query
    status = await monitor.getHealthStatus();
    badStatus = status.find(s => s.service_name === 'bad-service');
    assertEqual(badStatus.status, 'disabled', 'bad-service should have disabled status');
  } finally {
    await monitor.close();
  }
}

async function testPrometheusMetrics() {
  section('ServiceHealthMonitor - Prometheus Metrics Format');

  const { monitor } = createTestMonitor({
    'postgresql': async () => ({ healthy: true, latency_ms: 2 }),
    'prometheus': async () => ({ healthy: true, latency_ms: 5 }),
    'anthropic': async () => ({ healthy: true, latency_ms: 8 }),
    'openai': async () => ({ healthy: true, latency_ms: 10 }),
    'google': async () => ({ healthy: true, latency_ms: 12 }),
    'openrouter': async () => ({ healthy: true, latency_ms: 15 }),
  });

  try {
    // Record some checks to have data
    await monitor.recordHealthCheck('postgresql', { healthy: true, latency_ms: 2, error: null });
    await monitor.recordHealthCheck('prometheus', { healthy: false, latency_ms: 5000, error: 'down' });

    const metrics = await monitor.getHealthMetrics();

    assert(typeof metrics === 'string', 'Metrics should be a string');
    assertIncludes(metrics, '# HELP service_health_score', 'Should include HELP for health_score');
    assertIncludes(metrics, '# TYPE service_health_score gauge', 'Should include TYPE for health_score');
    assertIncludes(metrics, 'service_health_score{service="postgresql"', 'Should include postgresql metric');
    assertIncludes(metrics, '# HELP service_health_checks_total', 'Should include HELP for checks_total');
    assertIncludes(metrics, '# TYPE service_health_checks_total counter', 'Should include TYPE counter');
    assertIncludes(metrics, '# HELP service_health_checks_successful', 'Should include successful checks');
    assertIncludes(metrics, '# HELP service_health_checks_failed', 'Should include failed checks');
    assertIncludes(metrics, '# HELP service_health_latency_ms', 'Should include latency metric');
    assertIncludes(metrics, '# HELP service_health_status', 'Should include status metric');
    assertIncludes(metrics, '# TYPE service_health_status gauge', 'Should include status TYPE');

    // Verify status codes (0=healthy, 1=degraded, 2=disabled)
    assertIncludes(metrics, 'service_health_status{service="postgresql"} 0', 'PostgreSQL status should be 0 (healthy)');

    // Check no syntax errors in metric lines (each data line should have a value)
    const dataLines = metrics.split('\n').filter(l => l && !l.startsWith('#'));
    for (const line of dataLines) {
      const parts = line.split(' ');
      assert(parts.length >= 2, `Metric line should have key and value: "${line}"`);
      assert(!isNaN(parseFloat(parts[parts.length - 1])), `Metric value should be numeric: "${line}"`);
    }
  } finally {
    await monitor.close();
  }
}

async function testSchedulerStartStop() {
  section('ServiceHealthMonitor - Scheduler Start/Stop');

  let checkCount = 0;
  const { monitor } = createTestMonitor({
    'postgresql': async () => { checkCount++; return { healthy: true, latency_ms: 1 }; },
    'prometheus': async () => { checkCount++; return { healthy: true, latency_ms: 1 }; },
    'anthropic': async () => { checkCount++; return { healthy: true, latency_ms: 1 }; },
    'openai': async () => { checkCount++; return { healthy: true, latency_ms: 1 }; },
    'google': async () => { checkCount++; return { healthy: true, latency_ms: 1 }; },
    'openrouter': async () => { checkCount++; return { healthy: true, latency_ms: 1 }; },
  });

  try {
    const scheduler = monitor.startScheduler();
    assert(typeof scheduler.stop === 'function', 'Scheduler should return stop function');

    // Wait for initial check to complete
    await new Promise(resolve => setTimeout(resolve, 200));

    assertGreaterThan(checkCount, 0, 'Should have run at least one health check');

    // Stop scheduler
    scheduler.stop();

    const countAfterStop = checkCount;
    await new Promise(resolve => setTimeout(resolve, 300));

    assertEqual(checkCount, countAfterStop, 'No more checks should run after stop');
  } finally {
    await monitor.close();
  }
}

async function testHealthPercentFormatting() {
  section('ServiceHealthMonitor - Health Percent Formatting');

  const { monitor } = createTestMonitor();

  try {
    await monitor.recordHealthCheck('fmt-test', { healthy: true, latency_ms: 5, error: null });
    await monitor.recordHealthCheck('fmt-test', { healthy: true, latency_ms: 5, error: null });
    await monitor.recordHealthCheck('fmt-test', { healthy: false, latency_ms: 5, error: 'err' });

    const status = await monitor.getHealthStatus();
    const svc = status.find(s => s.service_name === 'fmt-test');

    assert(svc !== undefined, 'Should find fmt-test service');
    assertEqual(svc.health_percent, '66.7', 'Health percent should be formatted to 1 decimal');
    assert(typeof svc.health_score === 'number', 'health_score should be a number');
    assertApprox(svc.health_score, 0.6667, 0.01, 'health_score should be ~0.6667');
  } finally {
    await monitor.close();
  }
}

async function testHistoryWindowBound() {
  section('ServiceHealthMonitor - History Window Limit');

  const store = new InMemoryStore();

  // Record more checks than the history window (20)
  for (let i = 0; i < 30; i++) {
    // First 25 are failures, last 5 are successes
    const healthy = i >= 25;
    store.recordCheck('window-test', { healthy, latency_ms: 10, error: healthy ? null : 'fail' });
  }

  const record = store.getServiceRecord('window-test');
  // The rolling window is last 20 checks: 5 successes (indices 25-29) + 15 failures (indices 10-24)
  // But with default history_window=20 from DEFAULT_CONFIG
  // Actually the store uses config.history_window which we set to 20 in tests
  // Checks 10-29 (20 total): 15 failures (10-24) + 5 successes (25-29) = 5/20 = 0.25
  assertApprox(record.health_score, 0.25, 0.01, 'Score should use rolling window (5/20 = 25%)');
  assertEqual(record.total_checks, 30, 'total_checks should count all checks (not windowed)');
}

async function testMultipleServicesIsolation() {
  section('ServiceHealthMonitor - Multiple Services Isolation');

  const { monitor } = createTestMonitor();

  try {
    // Service A: all healthy
    for (let i = 0; i < 5; i++) {
      await monitor.recordHealthCheck('svc-a', { healthy: true, latency_ms: 5, error: null });
    }

    // Service B: all unhealthy
    for (let i = 0; i < 5; i++) {
      await monitor.recordHealthCheck('svc-b', { healthy: false, latency_ms: 5000, error: 'down' });
    }

    const status = await monitor.getHealthStatus();
    const svcA = status.find(s => s.service_name === 'svc-a');
    const svcB = status.find(s => s.service_name === 'svc-b');

    assertApprox(svcA.health_score, 1.0, 0.001, 'svc-a should be 100% healthy');
    assertApprox(svcB.health_score, 0.0, 0.001, 'svc-b should be 0% healthy');
    assertEqual(svcA.status, 'healthy', 'svc-a status should be healthy');
    assertEqual(svcB.status, 'disabled', 'svc-b status should be disabled');

    // Verify they don't affect each other
    const histA = await monitor.getHealthHistory('svc-a', 100);
    const histB = await monitor.getHealthHistory('svc-b', 100);
    assertEqual(histA.length, 5, 'svc-a should have 5 history records');
    assertEqual(histB.length, 5, 'svc-b should have 5 history records');
  } finally {
    await monitor.close();
  }
}

async function testConfigExposure() {
  section('ServiceHealthMonitor - Config Exposure');

  const { monitor } = createTestMonitor();

  try {
    const cfg = monitor.getConfig();
    assert(typeof cfg === 'object', 'getConfig should return an object');
    assert(typeof cfg.auto_disable_threshold === 'number', 'Should expose auto_disable_threshold');
    assert(typeof cfg.history_window === 'number', 'Should expose history_window');
    assert(typeof cfg.check_interval_ms === 'number', 'Should expose check_interval_ms');
  } finally {
    await monitor.close();
  }
}

async function testModuleExports() {
  section('Module Exports - Convenience Functions');

  const mod = require('./service-health.cjs');

  // Verify all expected exports exist
  const expectedExports = [
    'ServiceHealthMonitor',
    'InMemoryStore',
    'PostgresStore',
    'getServiceHealthMonitor',
    'createServiceHealthMonitor',
    'initSchema',
    'checkServiceHealth',
    'checkAllServices',
    'recordHealthCheck',
    'runHealthChecks',
    'autoDisableUnhealthy',
    'getHealthMetrics',
    'startScheduler',
    'getHealthStatus',
    'getHealthHistory',
    'close',
    'config',
    'DEFAULT_CONFIG',
  ];

  for (const name of expectedExports) {
    assert(mod[name] !== undefined, `Should export "${name}"`);
  }

  // Verify types
  assertEqual(typeof mod.ServiceHealthMonitor, 'function', 'ServiceHealthMonitor should be a class/function');
  assertEqual(typeof mod.InMemoryStore, 'function', 'InMemoryStore should be a class/function');
  assertEqual(typeof mod.PostgresStore, 'function', 'PostgresStore should be a class/function');
  assertEqual(typeof mod.createServiceHealthMonitor, 'function', 'createServiceHealthMonitor should be a function');
  assertEqual(typeof mod.getServiceHealthMonitor, 'function', 'getServiceHealthMonitor should be a function');
}

async function testEdgeCaseEmptyMetrics() {
  section('Edge Case - Metrics with No Data');

  const { monitor } = createTestMonitor({
    'postgresql': async () => ({ healthy: true, latency_ms: 1 }),
    'prometheus': async () => ({ healthy: true, latency_ms: 1 }),
    'anthropic': async () => ({ healthy: true, latency_ms: 1 }),
    'openai': async () => ({ healthy: true, latency_ms: 1 }),
    'google': async () => ({ healthy: true, latency_ms: 1 }),
    'openrouter': async () => ({ healthy: true, latency_ms: 1 }),
  });

  try {
    // Generate metrics without any recorded checks
    const metrics = await monitor.getHealthMetrics();
    assert(typeof metrics === 'string', 'Should return string even with no data');
    assertIncludes(metrics, '# HELP', 'Should still have HELP comments');
    assertIncludes(metrics, '# TYPE', 'Should still have TYPE comments');
  } finally {
    await monitor.close();
  }
}

async function testRecoveryFromDisabled() {
  section('ServiceHealthMonitor - Recovery from Disabled');

  const { monitor } = createTestMonitor();

  try {
    // Push service to disabled
    for (let i = 0; i < 10; i++) {
      await monitor.recordHealthCheck('recoverable', { healthy: false, latency_ms: 5000, error: 'down' });
    }
    await monitor.autoDisableUnhealthy(0.50);

    let status = await monitor.getHealthStatus();
    let svc = status.find(s => s.service_name === 'recoverable');
    assertEqual(svc.status, 'disabled', 'Service should be disabled initially');

    // Now send healthy checks to recover (enough to push window above threshold)
    for (let i = 0; i < 15; i++) {
      await monitor.recordHealthCheck('recoverable', { healthy: true, latency_ms: 5, error: null });
    }

    // The recordHealthCheck will recalculate status based on rolling window
    status = await monitor.getHealthStatus();
    svc = status.find(s => s.service_name === 'recoverable');
    // 10 fail + 15 pass = 25 total, window=20 -> last 20: 5 fail + 15 pass = 15/20 = 75%
    assertEqual(svc.status, 'healthy', 'Service should recover to healthy after enough successes');
    assertApprox(svc.health_score, 0.75, 0.01, '15/20 = 75%');
  } finally {
    await monitor.close();
  }
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runTests() {
  console.log('==================================================');
  console.log('Service Health Monitoring - Test Suite');
  console.log('==================================================');
  console.log('Backend: InMemoryStore (self-contained, no external deps)');

  try {
    await testInMemoryStoreBasics();
    await testInMemoryStoreRecordCheck();
    await testHealthScoreTransitions();
    await testInMemoryStoreHistory();
    await testInMemoryStoreDisableUnhealthy();
    await testInMemoryStoreClear();
    await testServiceHealthMonitorCustomChecks();
    await testServiceHealthMonitorCustomCheckThrows();
    await testRegisterUnregisterChecks();
    await testCheckAllServices();
    await testRecordAndQuery();
    await testRunHealthChecks();
    await testAutoDisableUnhealthy();
    await testPrometheusMetrics();
    await testSchedulerStartStop();
    await testHealthPercentFormatting();
    await testHistoryWindowBound();
    await testMultipleServicesIsolation();
    await testConfigExposure();
    await testModuleExports();
    await testEdgeCaseEmptyMetrics();
    await testRecoveryFromDisabled();

    console.log('\n==================================================');
    console.log('Test Results:');
    console.log(`  Sections: ${testSections}`);
    console.log(`  Passed:   ${testsPassed}`);
    console.log(`  Failed:   ${testsFailed}`);
    console.log('==================================================');

    if (testsFailed === 0) {
      console.log('\nALL TESTS PASSED');
      process.exit(0);
    } else {
      console.error(`\n${testsFailed} TEST(S) FAILED`);
      process.exit(1);
    }
  } catch (err) {
    console.error('\nTEST SUITE CRASHED:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

if (require.main === module) {
  runTests();
}

module.exports = { runTests };
