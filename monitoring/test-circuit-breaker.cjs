#!/usr/bin/env node
/**
 * Test Suite for Circuit Breaker
 *
 * Tests:
 * 1. Normal operation (CLOSED state)
 * 2. Failure threshold triggers OPEN
 * 3. Timeout triggers HALF_OPEN
 * 4. Recovery closes circuit
 * 5. Failure in HALF_OPEN reopens circuit
 *
 * Usage: node monitoring/test-circuit-breaker.cjs
 *
 * Created: 2026-06-28
 */

const circuitBreaker = require('../shared/circuit-breaker.cjs');

console.log('================================================================================');
console.log('CIRCUIT BREAKER - TEST SUITE');
console.log('================================================================================\n');

async function runTests() {
  let passCount = 0;
  let failCount = 0;

  const testModel = 'test-model';

  // Test 1: Normal Operation (CLOSED)
  console.log('=== Test 1: Normal Operation (CLOSED) ===');
  try {
    circuitBreaker.reset(testModel);

    const result = await circuitBreaker.execute(testModel, async () => {
      return 'success';
    });

    if (result === 'success' && !circuitBreaker.isOpen(testModel)) {
      console.log('✅ Test 1 PASSED: Circuit is CLOSED, call succeeded\n');
      passCount++;
    } else {
      console.log('❌ Test 1 FAILED: Unexpected state\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 1 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 2: Failure Threshold Triggers OPEN
  console.log('=== Test 2: Failure Threshold Triggers OPEN ===');
  try {
    circuitBreaker.reset(testModel);

    // Record 5 failures (default threshold)
    for (let i = 0; i < 5; i++) {
      await circuitBreaker.recordFailure(testModel, `Test failure ${i + 1}`);
    }

    const state = circuitBreaker.getCircuitState(testModel);

    if (state.state === 'open' && circuitBreaker.isOpen(testModel)) {
      console.log('✅ Test 2 PASSED: Circuit is OPEN after 5 failures\n');
      passCount++;
    } else {
      console.log('❌ Test 2 FAILED: Circuit should be OPEN\n');
      console.log('State:', state);
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 2 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 3: OPEN State Rejects Calls
  console.log('=== Test 3: OPEN State Rejects Calls ===');
  try {
    // Circuit should already be OPEN from Test 2

    let callRejected = false;
    try {
      await circuitBreaker.execute(testModel, async () => {
        return 'should not execute';
      });
    } catch (err) {
      if (err.message.includes('Circuit breaker OPEN')) {
        callRejected = true;
      }
    }

    if (callRejected) {
      console.log('✅ Test 3 PASSED: Call rejected when circuit is OPEN\n');
      passCount++;
    } else {
      console.log('❌ Test 3 FAILED: Call should have been rejected\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 3 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 4: Timeout Triggers HALF_OPEN (simulated)
  console.log('=== Test 4: Timeout Triggers HALF_OPEN ===');
  try {
    circuitBreaker.reset(testModel);

    // Manually trigger OPEN state
    for (let i = 0; i < 5; i++) {
      await circuitBreaker.recordFailure(testModel, 'Test failure');
    }

    // Manually set timeout to past
    const state = circuitBreaker.getCircuitState(testModel);
    state.last_failure_time = Date.now() - 31000; // 31 seconds ago (> 30s timeout)

    // Check if circuit transitions to HALF_OPEN
    const isOpenNow = circuitBreaker.isOpen(testModel);
    const stateAfter = circuitBreaker.getCircuitState(testModel);

    if (stateAfter.state === 'half_open' && !isOpenNow) {
      console.log('✅ Test 4 PASSED: Circuit transitioned to HALF_OPEN after timeout\n');
      passCount++;
    } else {
      console.log('❌ Test 4 FAILED: Circuit should be HALF_OPEN\n');
      console.log('State:', stateAfter);
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 4 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 5: Success in HALF_OPEN Closes Circuit
  console.log('=== Test 5: Success in HALF_OPEN Closes Circuit ===');
  try {
    // Circuit should be HALF_OPEN from Test 4

    // Record 2 successes (default threshold to close)
    circuitBreaker.recordSuccess(testModel);
    circuitBreaker.recordSuccess(testModel);

    const state = circuitBreaker.getCircuitState(testModel);

    if (state.state === 'closed') {
      console.log('✅ Test 5 PASSED: Circuit CLOSED after successful recovery\n');
      passCount++;
    } else {
      console.log('❌ Test 5 FAILED: Circuit should be CLOSED\n');
      console.log('State:', state);
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 5 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 6: Failure in HALF_OPEN Reopens Circuit
  console.log('=== Test 6: Failure in HALF_OPEN Reopens Circuit ===');
  try {
    circuitBreaker.reset(testModel);

    // Trigger OPEN
    for (let i = 0; i < 5; i++) {
      await circuitBreaker.recordFailure(testModel, 'Test failure');
    }

    // Force HALF_OPEN
    const state1 = circuitBreaker.getCircuitState(testModel);
    state1.last_failure_time = Date.now() - 31000;
    circuitBreaker.isOpen(testModel); // Trigger transition

    // Record failure in HALF_OPEN
    await circuitBreaker.recordFailure(testModel, 'Failed recovery test');

    const state2 = circuitBreaker.getCircuitState(testModel);

    if (state2.state === 'open') {
      console.log('✅ Test 6 PASSED: Circuit reopened after HALF_OPEN failure\n');
      passCount++;
    } else {
      console.log('❌ Test 6 FAILED: Circuit should be OPEN\n');
      console.log('State:', state2);
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 6 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 7: Get All States
  console.log('=== Test 7: Get All States ===');
  try {
    const allStates = circuitBreaker.getAllStates();
    console.log('All states:', JSON.stringify(allStates, null, 2));

    if (allStates && allStates[testModel]) {
      console.log('✅ Test 7 PASSED: getAllStates returns data\n');
      passCount++;
    } else {
      console.log('❌ Test 7 FAILED: getAllStates should return data\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 7 FAILED:', err.message, '\n');
    failCount++;
  }

  // Summary
  console.log('================================================================================');
  console.log('TEST SUMMARY');
  console.log('================================================================================');
  console.log(`Total: ${passCount + failCount}`);
  console.log(`Passed: ${passCount} ✅`);
  console.log(`Failed: ${failCount} ❌`);

  if (failCount === 0) {
    console.log('\n🎉 ALL TESTS PASSED!\n');
  } else {
    console.log('\n⚠️  SOME TESTS FAILED\n');
  }

  console.log('================================================================================\n');

  // Cleanup
  await circuitBreaker.close();
}

runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
