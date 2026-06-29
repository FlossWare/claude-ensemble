/**
 * Tests for Confidence Calibration System
 *
 * Tests calibration tracking, penalty calculation, and integration
 * with weighted voting.
 */

const {
  storeObservation,
  getCalibrationStats,
  getCalibrationPenalty,
  CALIBRATION_THRESHOLDS,
  MIN_OBSERVATIONS
} = require('./confidence-calibration.cjs');

// Test configuration
const TEST_MODEL = 'test-model-' + Date.now();
const TEST_TASK = 'test_task';

console.log('Testing Confidence Calibration System...\n');
console.log(`Test model: ${TEST_MODEL}`);
console.log(`Min observations: ${MIN_OBSERVATIONS}\n`);

// Helper to run tests sequentially
async function runTests() {
  try {
    // Test 1: Store single observation
    console.log('Test 1: Store single observation');
    await storeObservation({
      model: TEST_MODEL,
      reported_confidence: 0.90,
      actual_outcome: 0.60,  // Overconfident
      task_type: TEST_TASK,
      workflow_execution_id: 'test-wf-1'
    });
    console.log('  ✓ Observation stored\n');

    // Test 2: Get stats (insufficient data)
    console.log('Test 2: Get stats with insufficient data');
    let stats = await getCalibrationStats(TEST_MODEL, TEST_TASK);
    console.log('  Stats:', stats);
    console.assert(stats.num_observations === 1, 'Should have 1 observation');
    console.assert(stats.avg_reported === 0.90, 'Average reported should be 0.90');
    console.assert(stats.avg_actual === 0.60, 'Average actual should be 0.60');
    console.assert(Math.abs(stats.calibration_error - 0.30) < 0.001, 'Calibration error should be 0.30');
    console.log('  ✓ PASSED\n');

    // Test 3: Get penalty (insufficient data - should be 1.0)
    console.log('Test 3: Get penalty with insufficient data');
    let penalty = await getCalibrationPenalty(TEST_MODEL, TEST_TASK);
    console.log('  Penalty:', penalty);
    console.assert(penalty.penalty === 1.0, 'Penalty should be 1.0 (insufficient data)');
    console.assert(penalty.reason.includes('Insufficient data'), 'Reason should mention insufficient data');
    console.log('  ✓ PASSED\n');

    // Test 4: Add more observations (reach MIN_OBSERVATIONS)
    console.log('Test 4: Add observations to reach MIN_OBSERVATIONS');
    for (let i = 0; i < MIN_OBSERVATIONS - 1; i++) {
      await storeObservation({
        model: TEST_MODEL,
        reported_confidence: 0.90,
        actual_outcome: 0.60,
        task_type: TEST_TASK,
        workflow_execution_id: `test-wf-${i + 2}`
      });
    }
    console.log(`  ✓ Added ${MIN_OBSERVATIONS - 1} more observations\n`);

    // Test 5: Get stats (sufficient data)
    console.log('Test 5: Get stats with sufficient data');
    stats = await getCalibrationStats(TEST_MODEL, TEST_TASK);
    console.log('  Stats:', stats);
    console.assert(stats.num_observations === MIN_OBSERVATIONS, `Should have ${MIN_OBSERVATIONS} observations`);
    console.assert(Math.abs(stats.avg_reported - 0.90) < 0.001, 'Average reported should be 0.90');
    console.assert(Math.abs(stats.avg_actual - 0.60) < 0.001, 'Average actual should be 0.60');
    console.assert(Math.abs(stats.calibration_error - 0.30) < 0.001, 'Calibration error should be 0.30');
    console.log('  ✓ PASSED\n');

    // Test 6: Get penalty (critical error - should be 0.25)
    console.log('Test 6: Get penalty with critical error (>30%)');
    penalty = await getCalibrationPenalty(TEST_MODEL, TEST_TASK);
    console.log('  Penalty:', penalty);
    console.assert(penalty.penalty === 0.25, 'Penalty should be 0.25 (critical error)');
    console.assert(penalty.reason.includes('Critical calibration error'), 'Reason should mention critical error');
    console.log('  ✓ PASSED\n');

    // Test 7: Test major penalty tier (20-30% error)
    console.log('Test 7: Test major penalty tier (20-30% error)');
    const TEST_MODEL_MAJOR = TEST_MODEL + '-major';
    for (let i = 0; i < MIN_OBSERVATIONS; i++) {
      await storeObservation({
        model: TEST_MODEL_MAJOR,
        reported_confidence: 0.75,
        actual_outcome: 0.50,  // 25% error
        task_type: TEST_TASK,
        workflow_execution_id: `test-major-${i}`
      });
    }
    penalty = await getCalibrationPenalty(TEST_MODEL_MAJOR, TEST_TASK);
    console.log('  Penalty:', penalty);
    console.assert(penalty.penalty === 0.50, 'Penalty should be 0.50 (major error)');
    console.assert(penalty.reason.includes('Major calibration error'), 'Reason should mention major error');
    console.log('  ✓ PASSED\n');

    // Test 8: Test minor penalty tier (10-20% error)
    console.log('Test 8: Test minor penalty tier (10-20% error)');
    const TEST_MODEL_MINOR = TEST_MODEL + '-minor';
    for (let i = 0; i < MIN_OBSERVATIONS; i++) {
      await storeObservation({
        model: TEST_MODEL_MINOR,
        reported_confidence: 0.70,
        actual_outcome: 0.55,  // 15% error
        task_type: TEST_TASK,
        workflow_execution_id: `test-minor-${i}`
      });
    }
    penalty = await getCalibrationPenalty(TEST_MODEL_MINOR, TEST_TASK);
    console.log('  Penalty:', penalty);
    console.assert(penalty.penalty === 0.75, 'Penalty should be 0.75 (minor error)');
    console.assert(penalty.reason.includes('Minor calibration error'), 'Reason should mention minor error');
    console.log('  ✓ PASSED\n');

    // Test 9: Test well-calibrated (<10% error)
    console.log('Test 9: Test well-calibrated (<10% error)');
    const TEST_MODEL_GOOD = TEST_MODEL + '-good';
    for (let i = 0; i < MIN_OBSERVATIONS; i++) {
      await storeObservation({
        model: TEST_MODEL_GOOD,
        reported_confidence: 0.80,
        actual_outcome: 0.75,  // 5% error
        task_type: TEST_TASK,
        workflow_execution_id: `test-good-${i}`
      });
    }
    penalty = await getCalibrationPenalty(TEST_MODEL_GOOD, TEST_TASK);
    console.log('  Penalty:', penalty);
    console.assert(penalty.penalty === 1.0, 'Penalty should be 1.0 (well-calibrated)');
    console.assert(penalty.reason.includes('Well-calibrated'), 'Reason should mention well-calibrated');
    console.log('  ✓ PASSED\n');

    // Test 10: Test underconfident (negative error - still penalized by absolute value)
    console.log('Test 10: Test underconfident (negative error)');
    const TEST_MODEL_UNDER = TEST_MODEL + '-under';
    for (let i = 0; i < MIN_OBSERVATIONS; i++) {
      await storeObservation({
        model: TEST_MODEL_UNDER,
        reported_confidence: 0.50,
        actual_outcome: 0.90,  // Underconfident (sandbagging)
        task_type: TEST_TASK,
        workflow_execution_id: `test-under-${i}`
      });
    }
    penalty = await getCalibrationPenalty(TEST_MODEL_UNDER, TEST_TASK);
    console.log('  Penalty:', penalty);
    console.assert(penalty.penalty <= 0.25, 'Penalty should be applied for underconfidence too');
    console.log('  ✓ PASSED\n');

    // Test 11: Test task type filtering
    console.log('Test 11: Test task type filtering');
    const TEST_TASK_2 = 'different_task';
    for (let i = 0; i < MIN_OBSERVATIONS; i++) {
      await storeObservation({
        model: TEST_MODEL,
        reported_confidence: 0.60,
        actual_outcome: 0.55,  // Well-calibrated for this task
        task_type: TEST_TASK_2,
        workflow_execution_id: `test-task2-${i}`
      });
    }

    const penalty1 = await getCalibrationPenalty(TEST_MODEL, TEST_TASK);
    const penalty2 = await getCalibrationPenalty(TEST_MODEL, TEST_TASK_2);

    console.log(`  Penalty for ${TEST_TASK}:`, penalty1.penalty);
    console.log(`  Penalty for ${TEST_TASK_2}:`, penalty2.penalty);

    console.assert(penalty1.penalty === 0.25, 'First task should still have critical penalty');
    console.assert(penalty2.penalty === 1.0, 'Second task should be well-calibrated');
    console.log('  ✓ PASSED\n');

    // Test 12: Test overall stats (all tasks combined)
    console.log('Test 12: Test overall stats (all tasks combined)');
    const overallStats = await getCalibrationStats(TEST_MODEL);
    console.log('  Overall stats:', overallStats);
    console.assert(overallStats.num_observations === MIN_OBSERVATIONS * 2, 'Should combine both tasks');
    console.log('  ✓ PASSED\n');

    // Test 13: Test no data for model
    console.log('Test 13: Test no data for model');
    const noDataPenalty = await getCalibrationPenalty('nonexistent-model');
    console.log('  Penalty:', noDataPenalty);
    console.assert(noDataPenalty.penalty === 1.0, 'Should have no penalty for unknown model');
    console.assert(noDataPenalty.stats.num_observations === 0, 'Should have 0 observations');
    console.log('  ✓ PASSED\n');

    // Test 14: Configuration constants
    console.log('Test 14: Verify configuration constants');
    console.log('  CALIBRATION_THRESHOLDS:', CALIBRATION_THRESHOLDS);
    console.assert(CALIBRATION_THRESHOLDS.CRITICAL === 0.30, 'Critical threshold should be 0.30');
    console.assert(CALIBRATION_THRESHOLDS.MAJOR === 0.20, 'Major threshold should be 0.20');
    console.assert(CALIBRATION_THRESHOLDS.MINOR === 0.10, 'Minor threshold should be 0.10');
    console.assert(MIN_OBSERVATIONS === 5, 'Min observations should be 5');
    console.log('  ✓ PASSED\n');

    console.log('═══════════════════════════════════════════════════════');
    console.log('All tests PASSED ✓');
    console.log('═══════════════════════════════════════════════════════');
    console.log('\nCalibration System Summary:');
    console.log('- Well-calibrated (<10% error): penalty = 1.00 (no penalty)');
    console.log('- Minor error (10-20%): penalty = 0.75');
    console.log('- Major error (20-30%): penalty = 0.50');
    console.log('- Critical error (>30%): penalty = 0.25');
    console.log(`- Minimum observations: ${MIN_OBSERVATIONS}`);
    console.log('\nIntegration:');
    console.log('- Call storeObservation() after arbiter validation');
    console.log('- getCalibrationPenalty() automatically called by weighted-voting.cjs');
    console.log('- Penalties applied to vote weights in consensus');

    process.exit(0);
  } catch (err) {
    console.error('\n✗ TEST FAILED:', err);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run all tests
runTests();
