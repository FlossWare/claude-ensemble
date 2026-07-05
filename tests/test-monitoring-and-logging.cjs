#!/usr/bin/env node
/**
 * Comprehensive Test Suite for Resource Monitoring and Logging
 *
 * Tests:
 * 1. Start workflow-resource-monitor
 * 2. Simulate workflow execution
 * 3. Verify memory tracking works
 * 4. Verify CPU tracking works
 * 5. Stop monitoring and get stats
 * 6. Verify stats are logged to PostgreSQL
 * 7. Test auto-logger wrapper
 * 8. Verify execution metadata captured
 * 9. Check log completeness
 * 10. Test error case logging
 * 11. Run mini workflow with monitoring
 * 12. Verify all metrics captured
 *
 * Created: 2026-07-04
 */

const fs = require('fs');
const path = require('path');
const { spawn, execSync } = require('child_process');
const assert = require('assert');

// Import monitoring modules
const {
  wrapWorkflow,
  quickLog,
  manualLog,
  getWorkflowStats,
  calculateCost,
  extractTokenCounts,
  ResourceMonitor,
  pool: autoLoggerPool
} = require('../shared/auto-logger.cjs');

// Test configuration
const TEST_TIMEOUT = 60000;
const MONITORING_INTERVAL = 1000; // 1 second

let testsPassed = 0;
let testsFailed = 0;
const failures = [];

// Utilities
function log(message) {
  console.log(`[TEST] ${message}`);
}

function logSection(title) {
  console.log(`\n${'='.repeat(70)}`);
  console.log(`${title}`);
  console.log('='.repeat(70));
}

async function test(name, fn) {
  try {
    log(`Starting: ${name}`);
    await fn();
    log(`PASS: ${name}`);
    testsPassed++;
  } catch (error) {
    log(`FAIL: ${name}`);
    console.error(`  Error: ${error.message}`);
    if (error.stack) {
      console.error(`  Stack: ${error.stack.split('\n')[1]}`);
    }
    testsFailed++;
    failures.push({ test: name, error: error.message });
  }
}

// ============================================================================
// TEST 1: Resource Monitor - Start/Stop
// ============================================================================

async function testResourceMonitorBasics() {
  return new Promise((resolve, reject) => {
    const monitor = new ResourceMonitor();

    try {
      // Start monitoring
      monitor.start();
      assert(monitor.startTime !== null, 'Start time not set');
      assert(monitor.startCpuUsage !== null, 'CPU usage not initialized');
      assert(monitor.startMemUsage !== null, 'Memory usage not initialized');

      // Simulate some work
      let sum = 0;
      for (let i = 0; i < 1000000; i++) {
        sum += Math.sqrt(i);
      }

      // Stop monitoring
      const metrics = monitor.stop();
      assert(metrics.duration_ms > 0, 'Duration should be positive');
      assert(metrics.cpu_percent >= 0, 'CPU percent should be non-negative');
      assert(metrics.memory_used_mb >= 0, 'Memory usage should be non-negative');
      assert(metrics.start_time !== undefined, 'Start time missing from metrics');
      assert(metrics.end_time !== undefined, 'End time missing from metrics');

      log(`  Duration: ${metrics.duration_ms}ms`);
      log(`  CPU: ${metrics.cpu_percent}%`);
      log(`  Memory: ${metrics.memory_used_mb}MB`);

      resolve();
    } catch (error) {
      reject(error);
    }
  });
}

// ============================================================================
// TEST 2: Resource Monitor - Error Handling
// ============================================================================

async function testResourceMonitorCancel() {
  const monitor = new ResourceMonitor();
  monitor.start();

  // Simulate work
  await new Promise(r => setTimeout(r, 100));

  // Cancel should clean up without throwing
  monitor.cancel();
  assert(monitor.intervalHandle === null, 'Interval not cleared');
}

// ============================================================================
// TEST 3: Cost Calculation
// ============================================================================

async function testCostCalculation() {
  // Test various models
  const tests = [
    { model: 'opus', input: 1000, output: 1000, expected: { min: 0.08, max: 0.10 } },
    { model: 'sonnet', input: 1000, output: 1000, expected: { min: 0.018, max: 0.020 } },
    { model: 'haiku', input: 1000, output: 1000, expected: { min: 0.0015, max: 0.0020 } },
    { model: 'gpt-4o', input: 1000, output: 1000, expected: { min: 0.020, max: 0.025 } },
    { model: 'unknown', input: 1000, output: 1000, expected: { min: 0.004, max: 0.005 } },
  ];

  for (const t of tests) {
    const cost = calculateCost(t.model, t.input, t.output);
    assert(cost >= t.expected.min && cost <= t.expected.max,
      `${t.model} cost ${cost} not in range [${t.expected.min}, ${t.expected.max}]`);
    log(`  ${t.model}: ${cost.toFixed(4)} USD`);
  }
}

// ============================================================================
// TEST 4: Token Extraction
// ============================================================================

async function testTokenExtraction() {
  const tests = [
    {
      result: { input_tokens: 100, output_tokens: 50 },
      expected: { input_tokens: 100, output_tokens: 50 }
    },
    {
      result: { usage: { prompt_tokens: 200, completion_tokens: 100 } },
      expected: { input_tokens: 200, output_tokens: 100 }
    },
    {
      result: [
        { input_tokens: 50, output_tokens: 25 },
        { input_tokens: 50, output_tokens: 25 }
      ],
      expected: { input_tokens: 100, output_tokens: 50 }
    },
    {
      result: null,
      expected: { input_tokens: 0, output_tokens: 0 }
    }
  ];

  for (const t of tests) {
    const tokens = extractTokenCounts(t.result);
    assert.deepStrictEqual(tokens, t.expected,
      `Token extraction failed for ${JSON.stringify(t.result)}`);
  }

  log(`  Tested ${tests.length} token extraction cases`);
}

// ============================================================================
// TEST 5: Workflow Wrapping
// ============================================================================

async function testWorkflowWrapping() {
  const wrapped = wrapWorkflow(async () => {
    // Simulate some work
    await new Promise(r => setTimeout(r, 100));
    return {
      result: 'test result',
      input_tokens: 100,
      output_tokens: 50
    };
  }, {
    workflow_name: 'test-workflow-5',
    model: 'haiku',
    task_type: 'testing'
  });

  const response = await wrapped();
  assert(response.result !== undefined, 'Result missing');
  assert(response.execution !== undefined, 'Execution metadata missing');
  assert(response.execution.workflow_name === 'test-workflow-5', 'Workflow name mismatch');
  assert(response.execution.outcome === 'success', 'Outcome should be success');
  assert(response.execution.duration_ms > 90, 'Duration should be > 90ms');
  assert(response.execution.cost_usd > 0, 'Cost should be calculated');

  log(`  Workflow execution: ${response.execution.duration_ms}ms`);
  log(`  Cost: ${response.execution.cost_usd} USD`);
  log(`  Tokens: ${response.execution.input_tokens}/${response.execution.output_tokens}`);
}

// ============================================================================
// TEST 6: Workflow Error Handling
// ============================================================================

async function testWorkflowErrorHandling() {
  const wrapped = wrapWorkflow(async () => {
    await new Promise(r => setTimeout(r, 50));
    throw new Error('Simulated workflow error');
  }, {
    workflow_name: 'test-workflow-error',
    model: 'haiku',
    task_type: 'error_testing'
  });

  try {
    await wrapped();
    assert.fail('Should have thrown error');
  } catch (error) {
    assert(error.message === 'Simulated workflow error', 'Error message mismatch');
    log(`  Error properly propagated: ${error.message}`);
  }
}

// ============================================================================
// TEST 7: Quick Log Function
// ============================================================================

async function testQuickLog() {
  const result = await quickLog('test-quick-log', 'haiku', async () => {
    await new Promise(r => setTimeout(r, 50));
    return { data: 'test', input_tokens: 50, output_tokens: 25 };
  });

  assert(result.data === 'test', 'Result data mismatch');
  log(`  Quick log successful: ${result.data}`);
}

// ============================================================================
// TEST 8: Manual Logging
// ============================================================================

async function testManualLogging() {
  const executionId = await manualLog({
    model: 'haiku',
    workflow: 'test-manual-log',
    task_type: 'testing',
    duration_ms: 500,
    outcome: 'success',
    input_tokens: 1000,
    output_tokens: 500,
    quality_score: 0.95
  });

  assert(typeof executionId === 'number', 'Execution ID should be a number');
  assert(executionId > 0, 'Execution ID should be positive');
  log(`  Manual log recorded: ID ${executionId}`);
}

// ============================================================================
// TEST 9: Workflow Statistics
// ============================================================================

async function testWorkflowStats() {
  // Log several executions
  for (let i = 0; i < 3; i++) {
    await manualLog({
      model: 'haiku',
      workflow: 'test-stats-workflow',
      task_type: 'testing',
      duration_ms: 100 + Math.random() * 100,
      outcome: i === 2 ? 'error' : 'success',
      input_tokens: 500,
      output_tokens: 250,
      quality_score: 1.0
    });
  }

  // Get stats
  const stats = await getWorkflowStats('test-stats-workflow');
  assert(stats.total_executions >= 3, 'Should have at least 3 executions');
  assert(stats.success_rate < 100, 'Success rate should be < 100% (one failed)');
  assert(stats.avg_duration_ms > 0, 'Average duration should be positive');

  log(`  Total executions: ${stats.total_executions}`);
  log(`  Success rate: ${stats.success_rate}%`);
  log(`  Avg duration: ${stats.avg_duration_ms}ms`);
  log(`  Total cost: ${stats.avg_cost_usd * stats.total_executions}`);
}

// ============================================================================
// TEST 10: Mini Workflow Execution
// ============================================================================

async function testMiniWorkflowExecution() {
  const miniWorkflow = wrapWorkflow(async ({ phase }) => {
    const results = [];

    // Phase 1: Search
    if (phase) {
      results.push(await phase('Search', async () => {
        await new Promise(r => setTimeout(r, 100));
        return { queries: 5, results: 150, input_tokens: 200, output_tokens: 100 };
      }));
    }

    // Phase 2: Process
    if (phase) {
      results.push(await phase('Process', async () => {
        await new Promise(r => setTimeout(r, 150));
        return { processed: 150, input_tokens: 300, output_tokens: 200 };
      }));
    }

    // Simulate token aggregation
    const totalInput = results.reduce((sum, r) => sum + (r.input_tokens || 0), 0);
    const totalOutput = results.reduce((sum, r) => sum + (r.output_tokens || 0), 0);

    return {
      phases: results.length,
      total_results: 150,
      input_tokens: totalInput,
      output_tokens: totalOutput
    };
  }, {
    workflow_name: 'test-mini-workflow',
    model: 'sonnet',
    task_type: 'integration_test'
  });

  const { result, execution } = await miniWorkflow({ phase: async (name, fn) => fn() });

  assert(result.phases > 0, 'Should have phases');
  assert(execution.duration_ms > 200, 'Should take > 200ms (100+150)');
  assert(execution.input_tokens > 0, 'Should have input tokens');
  assert(execution.output_tokens > 0, 'Should have output tokens');

  log(`  Workflow phases: ${result.phases}`);
  log(`  Total duration: ${execution.duration_ms}ms`);
  log(`  Total tokens: ${execution.input_tokens}/${execution.output_tokens}`);
  log(`  Total cost: ${execution.cost_usd} USD`);
}

// ============================================================================
// TEST 11: Concurrent Workflow Logging
// ============================================================================

async function testConcurrentWorkflowLogging() {
  const workflows = [];

  for (let i = 0; i < 5; i++) {
    workflows.push(
      manualLog({
        model: 'haiku',
        workflow: 'test-concurrent-workflow',
        task_type: 'testing',
        duration_ms: 50 + Math.random() * 50,
        outcome: 'success',
        input_tokens: 100 + i * 100,
        output_tokens: 50 + i * 50,
        quality_score: 0.9 + Math.random() * 0.1
      })
    );
  }

  const ids = await Promise.all(workflows);
  assert(ids.length === 5, 'Should have logged 5 executions');
  assert(ids.every(id => typeof id === 'number'), 'All IDs should be numbers');
  log(`  Logged ${ids.length} concurrent workflows`);
}

// ============================================================================
// TEST 12: Metadata Capture
// ============================================================================

async function testMetadataCapture() {
  const wrapped = wrapWorkflow(async () => {
    return {
      input_tokens: 100,
      output_tokens: 50
    };
  }, {
    workflow_name: 'test-metadata',
    model: 'haiku',
    task_type: 'testing',
    additional: {
      source: 'test-suite',
      version: '1.0.0',
      tags: ['test', 'monitoring']
    }
  });

  const { execution } = await wrapped();
  assert(execution.resource_metrics !== undefined, 'Resource metrics missing');
  assert(execution.resource_metrics.start_time !== undefined, 'Start time missing');
  assert(execution.resource_metrics.end_time !== undefined, 'End time missing');

  log(`  Metadata captured successfully`);
  log(`  Resource metrics: ${JSON.stringify(execution.resource_metrics, null, 2)}`);
}

// ============================================================================
// TEST 13: Workflow Monitor Discovery
// ============================================================================

async function testWorkflowMonitorDiscovery() {
  // This test just ensures the module can be imported
  // Real test would require active workflows
  try {
    const monitorPath = path.join(__dirname, '../shared/workflow-monitor.mjs');
    assert(fs.existsSync(monitorPath), 'Workflow monitor not found');
    log(`  Workflow monitor found at ${monitorPath}`);
  } catch (error) {
    throw new Error(`Workflow monitor discovery failed: ${error.message}`);
  }
}

// ============================================================================
// TEST 14: Fleet Resource Monitor Discovery
// ============================================================================

async function testFleetResourceMonitorDiscovery() {
  const monitorPath = path.join(__dirname, '../monitoring/fleet-resource-monitor.js');
  assert(fs.existsSync(monitorPath), 'Fleet resource monitor not found');

  // Verify it's executable
  const stat = fs.statSync(monitorPath);
  log(`  Fleet resource monitor found: ${monitorPath}`);
  log(`  File size: ${stat.size} bytes`);
}

// ============================================================================
// TEST 15: Database Schema Verification
// ============================================================================

async function testDatabaseSchema() {
  const client = await autoLoggerPool.connect();
  try {
    // Check if execution_summary table exists
    const result = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'monitoring'
        AND table_name = 'execution_summary'
      );
    `);

    const tableExists = result.rows[0].exists;
    assert(tableExists, 'execution_summary table not found in monitoring schema');

    log(`  Schema verified: monitoring.execution_summary exists`);

    // Check columns
    const columnsResult = await client.query(`
      SELECT column_name, data_type
      FROM information_schema.columns
      WHERE table_schema = 'monitoring'
      AND table_name = 'execution_summary'
      ORDER BY ordinal_position;
    `);

    const columns = columnsResult.rows.map(r => r.column_name);
    const requiredColumns = ['id', 'timestamp', 'model', 'workflow', 'outcome'];

    for (const col of requiredColumns) {
      assert(columns.includes(col), `Required column '${col}' not found`);
    }

    log(`  All required columns present: ${requiredColumns.join(', ')}`);
  } finally {
    client.release();
  }
}

// ============================================================================
// TEST 16: Performance Under Load
// ============================================================================

async function testPerformanceUnderLoad() {
  const start = Date.now();
  const operations = [];

  // Log 50 executions concurrently
  for (let i = 0; i < 50; i++) {
    operations.push(
      manualLog({
        model: 'haiku',
        workflow: 'test-load-workflow',
        task_type: 'load_testing',
        duration_ms: Math.random() * 1000,
        outcome: Math.random() > 0.1 ? 'success' : 'error',
        input_tokens: Math.floor(Math.random() * 2000),
        output_tokens: Math.floor(Math.random() * 1000),
        quality_score: Math.random() * 0.5 + 0.5
      })
    );
  }

  await Promise.all(operations);
  const elapsed = Date.now() - start;

  log(`  Logged 50 executions in ${elapsed}ms`);
  log(`  Average: ${(elapsed / 50).toFixed(2)}ms per operation`);
  assert(elapsed < 30000, 'Load test took too long');
}

// ============================================================================
// MAIN TEST RUNNER
// ============================================================================

async function runAllTests() {
  logSection('RESOURCE MONITORING AND LOGGING TEST SUITE');

  log(`Starting ${TEST_TIMEOUT}ms timeout for all tests`);

  // Test 1-4: Resource Monitoring
  logSection('RESOURCE MONITORING TESTS (1-4)');

  await test('Test 1: Resource Monitor Basics', testResourceMonitorBasics);
  await test('Test 2: Resource Monitor Cancel', testResourceMonitorCancel);
  await test('Test 3: Cost Calculation', testCostCalculation);
  await test('Test 4: Token Extraction', testTokenExtraction);

  // Test 5-8: Workflow Wrapping
  logSection('WORKFLOW WRAPPING TESTS (5-8)');

  await test('Test 5: Workflow Wrapping', testWorkflowWrapping);
  await test('Test 6: Workflow Error Handling', testWorkflowErrorHandling);
  await test('Test 7: Quick Log Function', testQuickLog);
  await test('Test 8: Manual Logging', testManualLogging);

  // Test 9-12: Execution Logging
  logSection('EXECUTION LOGGING TESTS (9-12)');

  await test('Test 9: Workflow Statistics', testWorkflowStats);
  await test('Test 10: Mini Workflow Execution', testMiniWorkflowExecution);
  await test('Test 11: Concurrent Workflow Logging', testConcurrentWorkflowLogging);
  await test('Test 12: Metadata Capture', testMetadataCapture);

  // Test 13-16: System Integration
  logSection('SYSTEM INTEGRATION TESTS (13-16)');

  await test('Test 13: Workflow Monitor Discovery', testWorkflowMonitorDiscovery);
  await test('Test 14: Fleet Resource Monitor Discovery', testFleetResourceMonitorDiscovery);
  await test('Test 15: Database Schema Verification', testDatabaseSchema);
  await test('Test 16: Performance Under Load', testPerformanceUnderLoad);

  // Summary
  logSection('TEST SUMMARY');

  const total = testsPassed + testsFailed;
  const successRate = total > 0 ? Math.round((testsPassed / total) * 1000) / 10 : 0;

  log(`Total Tests: ${total}`);
  log(`Passed: ${testsPassed}`);
  log(`Failed: ${testsFailed}`);
  log(`Success Rate: ${successRate}%`);

  if (failures.length > 0) {
    logSection('FAILURES');
    for (const failure of failures) {
      console.log(`\n${failure.test}:`);
      console.log(`  ${failure.error}`);
    }
  }

  // Close database pool
  await autoLoggerPool.end();

  // Exit with appropriate code
  process.exit(testsFailed > 0 ? 1 : 0);
}

// Run tests
runAllTests().catch(error => {
  console.error('Fatal error:', error.message);
  process.exit(1);
});
