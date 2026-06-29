/**
 * Circuit Breaker Tests
 *
 * Comprehensive test suite covering all circuit breaker scenarios.
 * Tests state transitions, failure detection, recovery, and integration.
 *
 * Run: node circuit-breaker.test.cjs
 *
 * Created: 2026-06-28
 */

const {
  CircuitBreaker,
  getCircuitBreaker,
  withCircuitBreaker,
  CircuitState,
  FailureType,
  getCircuitBreakerDB,
} = require('./circuit-breaker.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testCounter = 0;
let passedTests = 0;
let failedTests = 0;

function test(name, fn) {
  testCounter++;
  const testNum = testCounter;
  process.stdout.write(`Test ${testNum}: ${name}... `);

  return fn()
    .then(() => {
      console.log('✓ PASS');
      passedTests++;
    })
    .catch((err) => {
      console.log('✗ FAIL');
      console.error(`  Error: ${err.message}`);
      if (err.stack) {
        console.error(`  Stack: ${err.stack.split('\n').slice(1, 3).join('\n')}`);
      }
      failedTests++;
    });
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================================
// TEST SETUP
// ============================================================================

let circuitBreaker;
let db;
const TEST_MODEL = 'test-model-' + Date.now();
const TEST_MODEL_2 = 'test-model-2-' + Date.now();

async function setup() {
  console.log('\n=== Circuit Breaker Test Suite ===\n');

  // Get singleton instances
  circuitBreaker = getCircuitBreaker();
  db = getCircuitBreakerDB();

  // Initialize database
  await db.initialize();

  console.log('Database initialized\n');
}

async function cleanup() {
  console.log('\n--- Cleanup ---');

  // Clean up test data
  try {
    const client = await db.pool.connect();
    try {
      await client.query(
        `DELETE FROM workflow.circuit_breaker_state WHERE model LIKE 'test-model%'`
      );
      console.log('Test data cleaned up');
    } finally {
      client.release();
    }
  } catch (err) {
    console.warn(`Cleanup warning: ${err.message}`);
  }

  // Close connection pool
  await db.close();
  console.log('Database connection closed');
}

// ============================================================================
// TESTS: BASIC STATE TRANSITIONS
// ============================================================================

async function testInitialState() {
  // New model should be available (closed circuit)
  const status = await circuitBreaker.isAvailable(TEST_MODEL);

  assert(status.available === true, 'New model should be available');
  assertEqual(status.state, CircuitState.CLOSED, 'Initial state should be CLOSED');
  assertEqual(status.reason, 'no_history', 'Reason should be no_history');
}

async function testSuccessRecording() {
  // Record a success
  await circuitBreaker.recordSuccess(TEST_MODEL, { test: 'success_1' });

  // Check state
  const state = await circuitBreaker.getState(TEST_MODEL);

  assert(state !== null, 'State should exist after recording success');
  assertEqual(state.state, CircuitState.CLOSED, 'State should remain CLOSED');
  assertEqual(state.success_count, 1, 'Success count should be 1');
  assertEqual(state.failure_count, 0, 'Failure count should be 0');

  const callHistory = Array.isArray(state.call_history) ? state.call_history : [];
  assertEqual(callHistory.length, 1, 'Call history should have 1 entry');
  assert(callHistory[0].success === true, 'Call should be marked as success');
}

async function testFailureRecording() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL);

  // Record a failure
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR, { test: 'failure_1' });

  // Check state
  const state = await circuitBreaker.getState(TEST_MODEL);

  assert(state !== null, 'State should exist after recording failure');
  assertEqual(state.state, CircuitState.CLOSED, 'State should remain CLOSED after 1 failure');
  assertEqual(state.failure_count, 1, 'Failure count should be 1');

  const callHistory = Array.isArray(state.call_history) ? state.call_history : [];
  assertEqual(callHistory.length, 1, 'Call history should have 1 entry');
  assert(callHistory[0].success === false, 'Call should be marked as failure');
  assertEqual(callHistory[0].failure_type, FailureType.API_ERROR, 'Failure type should be API_ERROR');
}

async function testCircuitOpening() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL);

  // Record 3 consecutive failures (should open circuit)
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);

  // Check state
  const state = await circuitBreaker.getState(TEST_MODEL);
  assertEqual(state.state, CircuitState.OPEN, 'Circuit should be OPEN after 3 failures');

  // Check availability
  const status = await circuitBreaker.isAvailable(TEST_MODEL);
  assert(status.available === false, 'Model should be unavailable when circuit OPEN');
  assertEqual(status.state, CircuitState.OPEN, 'Status should show OPEN');
  assert(status.retry_after_ms > 0, 'Should have retry_after_ms');
}

async function testCircuitHalfOpen() {
  // Reset and open circuit
  await circuitBreaker.resetCircuit(TEST_MODEL);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);

  // Manually set last_failure_time to 65 seconds ago (past recovery timeout)
  const client = await db.pool.connect();
  try {
    await client.query(
      `UPDATE workflow.circuit_breaker_state
       SET last_failure_time = NOW() - INTERVAL '65 seconds'
       WHERE model = $1`,
      [TEST_MODEL]
    );
  } finally {
    client.release();
  }

  // Check availability (should transition to half-open)
  const status = await circuitBreaker.isAvailable(TEST_MODEL);
  assert(status.available === true, 'Model should be available in half-open state');
  assertEqual(status.state, CircuitState.HALF_OPEN, 'State should be HALF-OPEN');
  assertEqual(status.reason, 'recovery_test', 'Reason should be recovery_test');

  // Verify state was updated in DB
  const state = await circuitBreaker.getState(TEST_MODEL);
  assertEqual(state.state, CircuitState.HALF_OPEN, 'DB state should be HALF-OPEN');
}

async function testHalfOpenSuccess() {
  // Setup half-open state
  await circuitBreaker.resetCircuit(TEST_MODEL);
  await db.updateState(TEST_MODEL, {
    state: CircuitState.HALF_OPEN,
    failure_count: 3,
    success_count: 0,
  });

  // Record 2 successes (should close circuit)
  await circuitBreaker.recordSuccess(TEST_MODEL);
  await circuitBreaker.recordSuccess(TEST_MODEL);

  // Check state
  const state = await circuitBreaker.getState(TEST_MODEL);
  assertEqual(state.state, CircuitState.CLOSED, 'Circuit should be CLOSED after 2 successes');
  assertEqual(state.failure_count, 0, 'Failure count should reset to 0');
}

async function testHalfOpenFailure() {
  // Setup half-open state
  await circuitBreaker.resetCircuit(TEST_MODEL);
  await db.updateState(TEST_MODEL, {
    state: CircuitState.HALF_OPEN,
    failure_count: 3,
    success_count: 0,
  });

  // Record failure (should reopen circuit)
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);

  // Check state
  const state = await circuitBreaker.getState(TEST_MODEL);
  assertEqual(state.state, CircuitState.OPEN, 'Circuit should be OPEN after half-open failure');
  assert(state.metadata.reopen_reason === 'half-open test failed', 'Should have reopen reason');
}

// ============================================================================
// TESTS: SLIDING WINDOW
// ============================================================================

async function testSlidingWindow() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL);

  // Record 15 calls (window size is 10)
  for (let i = 0; i < 15; i++) {
    if (i % 2 === 0) {
      await circuitBreaker.recordSuccess(TEST_MODEL);
    } else {
      await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
    }
  }

  // Check call history length
  const state = await circuitBreaker.getState(TEST_MODEL);
  const callHistory = Array.isArray(state.call_history) ? state.call_history : [];

  assert(callHistory.length <= 10, 'Call history should not exceed window size');
  assertEqual(callHistory.length, 10, 'Call history should be exactly 10');
}

async function testConsecutiveFailureDetection() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL);

  // Record success, then 3 failures
  await circuitBreaker.recordSuccess(TEST_MODEL);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);

  // Circuit should open (3 consecutive failures)
  const state = await circuitBreaker.getState(TEST_MODEL);
  assertEqual(state.state, CircuitState.OPEN, 'Circuit should open after 3 consecutive failures');
}

async function testNonConsecutiveFailures() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL);

  // Record failures interspersed with successes
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordSuccess(TEST_MODEL);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);
  await circuitBreaker.recordSuccess(TEST_MODEL);
  await circuitBreaker.recordFailure(TEST_MODEL, FailureType.API_ERROR);

  // Circuit should remain closed (no 3 consecutive failures)
  const state = await circuitBreaker.getState(TEST_MODEL);
  assertEqual(state.state, CircuitState.CLOSED, 'Circuit should remain closed');
}

// ============================================================================
// TESTS: WRAPPER FUNCTION
// ============================================================================

async function testWithCircuitBreakerSuccess() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL_2);

  // Successful call
  const result = await withCircuitBreaker(TEST_MODEL_2, async () => {
    return { success: true, data: 'test' };
  });

  assert(result.success === true, 'Should return result on success');
  assertEqual(result.data, 'test', 'Should return correct data');

  // Check circuit state
  const state = await circuitBreaker.getState(TEST_MODEL_2);
  assertEqual(state.success_count, 1, 'Should record success');
}

async function testWithCircuitBreakerFailure() {
  // Reset circuit
  await circuitBreaker.resetCircuit(TEST_MODEL_2);

  // Failing call
  try {
    await withCircuitBreaker(TEST_MODEL_2, async () => {
      throw new Error('API timeout');
    });
    throw new Error('Should have thrown error');
  } catch (err) {
    assertEqual(err.message, 'API timeout', 'Should propagate error');
  }

  // Check circuit state
  const state = await circuitBreaker.getState(TEST_MODEL_2);
  assertEqual(state.failure_count, 1, 'Should record failure');
}

async function testWithCircuitBreakerOpenCircuit() {
  // Reset and open circuit
  await circuitBreaker.resetCircuit(TEST_MODEL_2);
  await circuitBreaker.recordFailure(TEST_MODEL_2, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL_2, FailureType.API_ERROR);
  await circuitBreaker.recordFailure(TEST_MODEL_2, FailureType.API_ERROR);

  // Attempt call (should be blocked)
  try {
    await withCircuitBreaker(TEST_MODEL_2, async () => {
      return { success: true };
    });
    throw new Error('Should have thrown CIRCUIT_OPEN error');
  } catch (err) {
    assertEqual(err.code, 'CIRCUIT_OPEN', 'Should throw CIRCUIT_OPEN error');
    assertEqual(err.model, TEST_MODEL_2, 'Error should include model name');
    assert(err.retry_after_ms > 0, 'Error should include retry_after_ms');
  }
}

// ============================================================================
// TESTS: FILTER AVAILABLE MODELS
// ============================================================================

async function testFilterAvailableModels() {
  // Reset circuits
  await circuitBreaker.resetCircuit('model-a');
  await circuitBreaker.resetCircuit('model-b');
  await circuitBreaker.resetCircuit('model-c');

  // Open circuit for model-b
  await circuitBreaker.recordFailure('model-b', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('model-b', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('model-b', FailureType.API_ERROR);

  // Filter models
  const available = await circuitBreaker.filterAvailableModels(['model-a', 'model-b', 'model-c']);

  assertEqual(available.length, 2, 'Should have 2 available models');
  assert(available.includes('model-a'), 'Should include model-a');
  assert(available.includes('model-c'), 'Should include model-c');
  assert(!available.includes('model-b'), 'Should NOT include model-b');
}

// ============================================================================
// TESTS: MONITORING
// ============================================================================

async function testGetOpenCircuits() {
  // Reset and open multiple circuits
  await circuitBreaker.resetCircuit('open-1');
  await circuitBreaker.resetCircuit('open-2');

  await circuitBreaker.recordFailure('open-1', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('open-1', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('open-1', FailureType.API_ERROR);

  await circuitBreaker.recordFailure('open-2', FailureType.TIMEOUT);
  await circuitBreaker.recordFailure('open-2', FailureType.TIMEOUT);
  await circuitBreaker.recordFailure('open-2', FailureType.TIMEOUT);

  // Get open circuits
  const openCircuits = await circuitBreaker.getOpenCircuits();

  assert(openCircuits.length >= 2, 'Should have at least 2 open circuits');

  const openModels = openCircuits.map(c => c.model);
  assert(openModels.includes('open-1'), 'Should include open-1');
  assert(openModels.includes('open-2'), 'Should include open-2');
}

async function testGetStatistics() {
  // Get statistics
  const stats = await circuitBreaker.getStatistics();

  assert(stats.total > 0, 'Should have total count');
  assert(stats.by_state !== undefined, 'Should have by_state breakdown');

  // Check structure
  if (stats.by_state[CircuitState.OPEN]) {
    assert(stats.by_state[CircuitState.OPEN].count > 0, 'Should have open circuit count');
  }
}

// ============================================================================
// TESTS: MANUAL RESET
// ============================================================================

async function testManualReset() {
  // Open circuit
  await circuitBreaker.resetCircuit('reset-test');
  await circuitBreaker.recordFailure('reset-test', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('reset-test', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('reset-test', FailureType.API_ERROR);

  // Verify open
  let state = await circuitBreaker.getState('reset-test');
  assertEqual(state.state, CircuitState.OPEN, 'Circuit should be open');

  // Manual reset
  await circuitBreaker.resetCircuit('reset-test');

  // Verify closed
  state = await circuitBreaker.getState('reset-test');
  assertEqual(state.state, CircuitState.CLOSED, 'Circuit should be closed after reset');
  assertEqual(state.failure_count, 0, 'Failure count should be 0');
  assertEqual(state.success_count, 0, 'Success count should be 0');

  const callHistory = Array.isArray(state.call_history) ? state.call_history : [];
  assertEqual(callHistory.length, 0, 'Call history should be empty');
}

// ============================================================================
// RUN TESTS
// ============================================================================

async function runTests() {
  await setup();

  try {
    // Basic state transitions
    await test('Initial state (new model)', testInitialState);
    await test('Record success', testSuccessRecording);
    await test('Record failure', testFailureRecording);
    await test('Circuit opening (3 failures)', testCircuitOpening);
    await test('Circuit half-open (after timeout)', testCircuitHalfOpen);
    await test('Half-open → closed (success)', testHalfOpenSuccess);
    await test('Half-open → open (failure)', testHalfOpenFailure);

    // Sliding window
    await test('Sliding window (10 calls max)', testSlidingWindow);
    await test('Consecutive failure detection', testConsecutiveFailureDetection);
    await test('Non-consecutive failures (remain closed)', testNonConsecutiveFailures);

    // Wrapper function
    await test('withCircuitBreaker success', testWithCircuitBreakerSuccess);
    await test('withCircuitBreaker failure', testWithCircuitBreakerFailure);
    await test('withCircuitBreaker open circuit', testWithCircuitBreakerOpenCircuit);

    // Filter available models
    await test('Filter available models', testFilterAvailableModels);

    // Monitoring
    await test('Get open circuits', testGetOpenCircuits);
    await test('Get statistics', testGetStatistics);

    // Manual reset
    await test('Manual reset', testManualReset);

  } finally {
    await cleanup();
  }

  // Print summary
  console.log('\n=== Test Summary ===');
  console.log(`Total: ${testCounter}`);
  console.log(`Passed: ${passedTests} ✓`);
  console.log(`Failed: ${failedTests} ✗`);

  if (failedTests === 0) {
    console.log('\n🎉 All tests passed!');
    process.exit(0);
  } else {
    console.log(`\n❌ ${failedTests} test(s) failed`);
    process.exit(1);
  }
}

// Run tests
runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
