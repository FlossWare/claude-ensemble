/**
 * API Health Monitor Tests
 *
 * Test suite for api-health-monitor.cjs
 * Validates health check execution, status tracking, and auto-disable logic
 *
 * Usage: node monitoring/api-health-monitor.test.cjs
 */

const monitor = require('./api-health-monitor.cjs');
const { Pool } = require('pg');

// Test configuration
const TEST_PROVIDERS = ['anthropic', 'openai', 'google'];
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});

// Test helpers
let testResults = {
  passed: 0,
  failed: 0,
  total: 0,
};

async function test(name, fn) {
  testResults.total++;
  try {
    await fn();
    console.log(`✓ ${name}`);
    testResults.passed++;
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  Error: ${err.message}`);
    testResults.failed++;
  }
}

function assertEquals(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function assertGreaterThan(actual, expected, message) {
  if (actual <= expected) {
    throw new Error(`${message}: expected > ${expected}, got ${actual}`);
  }
}

function assertTrue(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// ============================================================================
// TEST SUITE
// ============================================================================

async function runTests() {
  console.log('API Health Monitor Test Suite\n');

  try {
    // Test 1: Schema initialization
    await test('Schema initialization', async () => {
      try {
        await monitor.initSchema();
      } catch (err) {
        // Ignore permission errors (tables may already exist)
        if (!err.message.includes('permission denied')) {
          throw err;
        }
      }

      // Verify tables exist
      const result = await pool.query(`
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'monitoring'
          AND table_name IN ('api_health_status', 'api_health_checks')
      `);

      assertEquals(result.rows.length, 2, 'Expected 2 tables created');
    });

    // Test 2: Clean slate (delete existing test data)
    await test('Clean test data', async () => {
      await pool.query(`DELETE FROM monitoring.api_health_checks WHERE provider = ANY($1)`, [TEST_PROVIDERS]);
      await pool.query(`DELETE FROM monitoring.api_health_status WHERE provider = ANY($1)`, [TEST_PROVIDERS]);

      const result = await pool.query(`SELECT COUNT(*) FROM monitoring.api_health_status WHERE provider = ANY($1)`, [TEST_PROVIDERS]);
      assertEquals(parseInt(result.rows[0].count), 0, 'Test data should be cleared');
    });

    // Test 3: Health check execution (mocked)
    await test('Execute health check (mocked)', async () => {
      // Mock successful health check
      const result = await monitor.executeHealthCheck('anthropic');

      assertTrue(result.hasOwnProperty('success'), 'Result should have success property');
      assertTrue(result.hasOwnProperty('response_time_ms'), 'Result should have response_time_ms');

      if (!result.success) {
        console.warn(`  Note: Health check failed (expected if API keys not set): ${result.error}`);
      }
    });

    // Test 4: Record health check (successful)
    await test('Record successful health check', async () => {
      await monitor.recordHealthCheck('anthropic', {
        success: true,
        response_time_ms: 250,
      });

      const status = await pool.query(`
        SELECT * FROM monitoring.api_health_status WHERE provider = 'anthropic'
      `);

      assertEquals(status.rows.length, 1, 'Status record should exist');
      assertEquals(status.rows[0].status, 'healthy', 'Status should be healthy');
      assertEquals(parseFloat(status.rows[0].success_rate), 1.0, 'Success rate should be 1.0');
      assertEquals(status.rows[0].successful_checks, 1, 'Successful checks should be 1');
    });

    // Test 5: Record health check (failed)
    await test('Record failed health check', async () => {
      await monitor.recordHealthCheck('openai', {
        success: false,
        response_time_ms: 5000,
        error: 'Connection timeout',
      });

      const status = await pool.query(`
        SELECT * FROM monitoring.api_health_status WHERE provider = 'openai'
      `);

      assertEquals(status.rows.length, 1, 'Status record should exist');
      assertEquals(status.rows[0].failed_checks, 1, 'Failed checks should be 1');
      assertEquals(status.rows[0].failure_reason, 'Connection timeout', 'Failure reason should be stored');
    });

    // Test 6: Auto-disable logic (simulate 15 failures)
    await test('Auto-disable after <50% success rate', async () => {
      // Simulate 15 failures, 5 successes (25% success rate)
      for (let i = 0; i < 15; i++) {
        await monitor.recordHealthCheck('google', {
          success: false,
          response_time_ms: 1000,
          error: 'Simulated failure',
        });
      }

      for (let i = 0; i < 5; i++) {
        await monitor.recordHealthCheck('google', {
          success: true,
          response_time_ms: 200,
        });
      }

      const status = await pool.query(`
        SELECT * FROM monitoring.api_health_status WHERE provider = 'google'
      `);

      assertEquals(status.rows[0].status, 'disabled', 'Provider should be disabled');
      assertGreaterThan(status.rows[0].total_checks, 0, 'Should have total_checks > 0');

      const successRate = parseFloat(status.rows[0].success_rate);
      assertTrue(successRate < 0.50, `Success rate should be < 50%, got ${successRate}`);
    });

    // Test 7: Get health status
    await test('Get health status for all providers', async () => {
      const statuses = await monitor.getHealthStatus();

      assertTrue(statuses.length >= 3, 'Should have at least 3 test providers');

      const anthropic = statuses.find(s => s.provider === 'anthropic');
      assertTrue(anthropic !== undefined, 'Anthropic status should exist');
      assertEquals(anthropic.status, 'healthy', 'Anthropic should be healthy');

      const google = statuses.find(s => s.provider === 'google');
      assertTrue(google !== undefined, 'Google status should exist');
      assertEquals(google.status, 'disabled', 'Google should be disabled');
    });

    // Test 8: Get health history
    await test('Get health check history', async () => {
      const history = await monitor.getHealthHistory('google', 10);

      assertTrue(history.length > 0, 'Should have health check history');
      assertGreaterThan(history.length, 5, 'Should have > 5 checks');
    });

    // Test 9: Provider availability
    await test('Get provider availability', async () => {
      const { available, disabled } = await monitor.getProviderAvailability();

      assertTrue(available.length > 0, 'Should have available providers');
      assertTrue(disabled.length > 0, 'Should have disabled providers');

      const googleDisabled = disabled.find(d => d.provider === 'google');
      assertTrue(googleDisabled !== undefined, 'Google should be in disabled list');
      assertTrue(googleDisabled.success_rate < 0.50, 'Disabled provider success rate should be < 50%');
    });

    // Test 10: Reset provider status
    await test('Reset provider status', async () => {
      await monitor.resetProviderStatus('google');

      const status = await pool.query(`
        SELECT * FROM monitoring.api_health_status WHERE provider = 'google'
      `);

      assertEquals(status.rows[0].status, 'healthy', 'Status should be reset to healthy');
      assertEquals(parseFloat(status.rows[0].success_rate), 1.0, 'Success rate should be reset to 1.0');
    });

    // Test 11: Degraded status (50-75% success rate)
    await test('Degraded status at 60% success rate', async () => {
      // Clear test provider
      await pool.query(`DELETE FROM monitoring.api_health_checks WHERE provider = 'test-provider'`);
      await pool.query(`DELETE FROM monitoring.api_health_status WHERE provider = 'test-provider'`);

      // Simulate 12 successes, 8 failures (60% success rate)
      for (let i = 0; i < 12; i++) {
        await monitor.recordHealthCheck('test-provider', {
          success: true,
          response_time_ms: 200,
        });
      }

      for (let i = 0; i < 8; i++) {
        await monitor.recordHealthCheck('test-provider', {
          success: false,
          response_time_ms: 1000,
          error: 'Simulated degradation',
        });
      }

      const status = await pool.query(`
        SELECT * FROM monitoring.api_health_status WHERE provider = 'test-provider'
      `);

      assertEquals(status.rows[0].status, 'degraded', 'Provider should be degraded');

      const successRate = parseFloat(status.rows[0].success_rate);
      assertTrue(successRate >= 0.50 && successRate < 0.75, `Success rate should be 50-75%, got ${successRate}`);
    });

    // Test 12: Circuit breaker extension
    await test('Circuit breaker extension created', async () => {
      monitor.extendCircuitBreaker();

      const fs = require('fs');
      const path = require('path');
      const extensionPath = path.join(__dirname, '../shared/circuit-breaker-provider-extension.cjs');

      assertTrue(fs.existsSync(extensionPath), 'Extension file should be created');

      const content = fs.readFileSync(extensionPath, 'utf8');
      assertTrue(content.includes('filterAvailableModels'), 'Extension should export filterAvailableModels');
    });

  } catch (err) {
    console.error('Test suite failed:', err);
    testResults.failed++;
  } finally {
    // Cleanup
    await monitor.close();
    await pool.end();

    // Print summary
    console.log('\n' + '='.repeat(60));
    console.log('Test Results:');
    console.log(`  Total: ${testResults.total}`);
    console.log(`  Passed: ${testResults.passed}`);
    console.log(`  Failed: ${testResults.failed}`);
    console.log(`  Success Rate: ${((testResults.passed / testResults.total) * 100).toFixed(1)}%`);
    console.log('='.repeat(60));

    // Exit with appropriate code
    process.exit(testResults.failed > 0 ? 1 : 0);
  }
}

// Run tests
runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
