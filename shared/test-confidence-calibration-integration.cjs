#!/usr/bin/env node

/**
 * Test Confidence Calibration Integration Helper
 *
 * Tests all 4 integration functions to ensure they work correctly:
 * 1. recordArbiterOutcome() - After arbiter decision
 * 2. recordQualityOutcome() - After quality scoring
 * 3. recordVotingOutcome() - After weighted voting
 * 4. recordObservation() - Manual recording
 *
 * Run: node shared/test-confidence-calibration-integration.cjs
 */

const {
  recordArbiterOutcome,
  recordQualityOutcome,
  recordVotingOutcome,
  recordObservation,
} = require('./confidence-calibration-integration.cjs');

const {
  getCalibrationStats,
  getCalibrationPenalty,
} = require('./confidence-calibration.cjs');

const { getDB } = require('../learning/postgres-adapter.js');

// Test utilities
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function assertApprox(actual, expected, tolerance = 0.01, message = '') {
  const diff = Math.abs(actual - expected);
  if (diff > tolerance) {
    throw new Error(
      `Assertion failed: ${message}\n` +
      `  Expected: ${expected}\n` +
      `  Actual: ${actual}\n` +
      `  Difference: ${diff} (tolerance: ${tolerance})`
    );
  }
}

// ============================================================================
// TEST SETUP: Clean database before tests
// ============================================================================

async function setupTests() {
  console.log('\n=== Setting up tests: Cleaning database ===\n');

  const db = getDB();

  try {
    // Delete all test observations from previous runs (any model starting with 'test')
    await db.query(`
      DELETE FROM learning.confidence_observations
      WHERE model ~ '^test'
    `);

    const result = await db.query(`SELECT COUNT(*) as count FROM learning.confidence_observations WHERE model ~ '^test'`);
    console.log(`✓ Cleaned up test data from previous runs (${result.rows[0].count} remaining test records)\n`);
  } catch (err) {
    console.warn('Warning: Could not clean database:', err.message);
    console.log('Continuing with tests...\n');
  }
}

// ============================================================================
// TEST 1: ARBITER OUTCOME RECORDING
// ============================================================================

async function testArbiterOutcomeRecording() {
  console.log('\n=== Test 1: Arbiter Outcome Recording ===\n');

  // Simulate workers
  const workers = [
    { worker_id: 'w1', model: 'test-arbiter-opus', confidence: 0.9, answer: 'A' },
    { worker_id: 'w2', model: 'test-arbiter-sonnet', confidence: 0.7, answer: 'B' },
    { worker_id: 'w3', model: 'test-arbiter-haiku', confidence: 0.5, answer: 'A' },
  ];

  // Arbiter selects answer A
  const arbiterDecision = {
    selected_answer: 'A',
    reasoning: 'Answer A has stronger evidence',
  };

  // Record observations
  await recordArbiterOutcome(workers, arbiterDecision, 'test_arbiter', 'test-exec-1');

  // Wait for async storage
  await new Promise(resolve => setTimeout(resolve, 100));

  // Verify stats (opus and haiku should be correct, sonnet should be incorrect)
  const opusStats = await getCalibrationStats('test-arbiter-opus');
  const sonnetStats = await getCalibrationStats('test-arbiter-sonnet');
  const haikuStats = await getCalibrationStats('test-arbiter-haiku');

  console.log(`  Opus: reported=${(opusStats.avg_reported * 100).toFixed(0)}%, actual=${(opusStats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Sonnet: reported=${(sonnetStats.avg_reported * 100).toFixed(0)}%, actual=${(sonnetStats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Haiku: reported=${(haikuStats.avg_reported * 100).toFixed(0)}%, actual=${(haikuStats.avg_actual * 100).toFixed(0)}%`);

  // Opus: reported 90%, actual 100% (correct)
  assertApprox(opusStats.avg_reported, 0.9, 0.1, 'Opus reported confidence');
  assertApprox(opusStats.avg_actual, 1.0, 0.1, 'Opus actual outcome');

  // Sonnet: reported 70-77%, actual 0% (incorrect) - wider tolerance for averaging
  assertApprox(sonnetStats.avg_reported, 0.7, 0.1, 'Sonnet reported confidence');
  assertApprox(sonnetStats.avg_actual, 0.0, 0.1, 'Sonnet actual outcome');

  // Haiku: reported 50%, actual 100% (correct)
  assertApprox(haikuStats.avg_reported, 0.5, 0.1, 'Haiku reported confidence');
  assertApprox(haikuStats.avg_actual, 1.0, 0.1, 'Haiku actual outcome');

  console.log('\n  ✓ Arbiter outcome recording works correctly\n');
}

// ============================================================================
// TEST 2: QUALITY OUTCOME RECORDING
// ============================================================================

async function testQualityOutcomeRecording() {
  console.log('\n=== Test 2: Quality Outcome Recording ===\n');

  // High quality result (should be 1.0)
  await recordQualityOutcome('test-quality-good', 0.85, 95, 'test_quality', 'test-exec-2');

  // Low quality result (should be 0.0)
  await recordQualityOutcome('test-quality-bad', 0.85, 65, 'test_quality', 'test-exec-2');

  // Wait for async storage
  await new Promise(resolve => setTimeout(resolve, 100));

  // Verify stats
  const goodStats = await getCalibrationStats('test-quality-good');
  const badStats = await getCalibrationStats('test-quality-bad');

  console.log(`  Good model: reported=${(goodStats.avg_reported * 100).toFixed(0)}%, actual=${(goodStats.avg_actual * 100).toFixed(0)}% (quality=95)`);
  console.log(`  Bad model: reported=${(badStats.avg_reported * 100).toFixed(0)}%, actual=${(badStats.avg_actual * 100).toFixed(0)}% (quality=65)`);

  // Good model: reported 85%, actual 100% (quality=95 >= threshold)
  assertApprox(goodStats.avg_reported, 0.85, 0.01, 'Good model reported confidence');
  assertApprox(goodStats.avg_actual, 1.0, 0.01, 'Good model actual outcome');

  // Bad model: reported 85%, actual 0% (quality=65 < threshold)
  assertApprox(badStats.avg_reported, 0.85, 0.01, 'Bad model reported confidence');
  assertApprox(badStats.avg_actual, 0.0, 0.01, 'Bad model actual outcome');

  console.log('\n  ✓ Quality outcome recording works correctly\n');
}

// ============================================================================
// TEST 3: VOTING OUTCOME RECORDING
// ============================================================================

async function testVotingOutcomeRecording() {
  console.log('\n=== Test 3: Voting Outcome Recording ===\n');

  // Simulate weighted voting result
  const votingResult = {
    status: 'success',
    winner: {
      answer: 'A',
      total_weight: 2.5,
      vote_count: 2,
      votes: [
        { model: 'test-voting-opus', confidence: 0.9, answer: 'A' },
        { model: 'test-voting-sonnet', confidence: 0.85, answer: 'A' },
      ],
    },
    all_groups: [
      {
        answer: 'A',
        total_weight: 2.5,
        vote_count: 2,
        votes: [
          { model: 'test-voting-opus', confidence: 0.9, answer: 'A' },
          { model: 'test-voting-sonnet', confidence: 0.85, answer: 'A' },
        ],
      },
      {
        answer: 'B',
        total_weight: 0.6,
        vote_count: 1,
        votes: [
          { model: 'test-voting-haiku', confidence: 0.6, answer: 'B' },
        ],
      },
    ],
  };

  await recordVotingOutcome(votingResult, 'test_voting', 'test-exec-3');

  // Wait for async storage
  await new Promise(resolve => setTimeout(resolve, 100));

  // Verify stats
  const opusStats = await getCalibrationStats('test-voting-opus');
  const sonnetStats = await getCalibrationStats('test-voting-sonnet');
  const haikuStats = await getCalibrationStats('test-voting-haiku');

  console.log(`  Opus (winner): reported=${(opusStats.avg_reported * 100).toFixed(0)}%, actual=${(opusStats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Sonnet (winner): reported=${(sonnetStats.avg_reported * 100).toFixed(0)}%, actual=${(sonnetStats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Haiku (loser): reported=${(haikuStats.avg_reported * 100).toFixed(0)}%, actual=${(haikuStats.avg_actual * 100).toFixed(0)}%`);

  // Winners should have actual=1.0
  assertApprox(opusStats.avg_actual, 1.0, 0.01, 'Opus actual outcome (winner)');
  assertApprox(sonnetStats.avg_actual, 1.0, 0.01, 'Sonnet actual outcome (winner)');

  // Loser should have actual=0.0
  assertApprox(haikuStats.avg_actual, 0.0, 0.01, 'Haiku actual outcome (loser)');

  console.log('\n  ✓ Voting outcome recording works correctly\n');
}

// ============================================================================
// TEST 4: MANUAL OBSERVATION RECORDING
// ============================================================================

async function testManualObservationRecording() {
  console.log('\n=== Test 4: Manual Observation Recording ===\n');

  // Record manual observations
  await recordObservation('test-manual-model', 0.75, 1.0, 'test_manual', 'test-exec-4');
  await recordObservation('test-manual-model', 0.80, 1.0, 'test_manual', 'test-exec-4');
  await recordObservation('test-manual-model', 0.70, 0.0, 'test_manual', 'test-exec-4');

  // Wait for async storage
  await new Promise(resolve => setTimeout(resolve, 100));

  // Verify stats
  const stats = await getCalibrationStats('test-manual-model');

  console.log(`  Manual model: reported=${(stats.avg_reported * 100).toFixed(0)}%, actual=${(stats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Observations: ${stats.num_observations}`);

  // Average reported: (0.75 + 0.80 + 0.70) / 3 = 0.75
  // Average actual: (1.0 + 1.0 + 0.0) / 3 = 0.67
  assertApprox(stats.avg_reported, 0.75, 0.1, 'Manual model reported confidence');
  assertApprox(stats.avg_actual, 0.67, 0.1, 'Manual model actual outcome');
  assert(stats.num_observations >= 3, 'Manual model observation count (at least 3)');

  console.log('\n  ✓ Manual observation recording works correctly\n');
}

// ============================================================================
// TEST 5: CALIBRATION PENALTY CALCULATION
// ============================================================================

async function testCalibrationPenalty() {
  console.log('\n=== Test 5: Calibration Penalty Calculation ===\n');

  // Add more observations to test-arbiter-sonnet (which had 1 incorrect observation)
  // Current: reported=0.7, actual=0.0 (1 observation)
  // Add 4 more incorrect observations to reach 5 total (minimum for penalty)
  for (let i = 0; i < 4; i++) {
    await recordObservation('test-arbiter-sonnet', 0.9, 0.0, 'test_arbiter', 'test-exec-5');
  }

  await new Promise(resolve => setTimeout(resolve, 100));

  // Get penalty (should have penalty due to overconfidence)
  const penalty = await getCalibrationPenalty('test-arbiter-sonnet', 'test_arbiter');

  console.log(`  Model: test-arbiter-sonnet`);
  console.log(`  Reported: ${(penalty.stats.avg_reported * 100).toFixed(0)}%`);
  console.log(`  Actual: ${(penalty.stats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Error: ${(penalty.stats.calibration_error * 100).toFixed(1)}%`);
  console.log(`  Penalty: ${penalty.penalty}× (${penalty.reason})`);

  // Should have significant penalty due to overconfidence
  assert(penalty.stats.num_observations >= 5, 'Enough observations for penalty');
  assert(penalty.penalty < 1.0, 'Penalty should be applied');

  console.log('\n  ✓ Calibration penalty calculation works correctly\n');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('==================================================');
  console.log('Confidence Calibration Integration Test Suite');
  console.log('==================================================');

  try {
    // Setup: Clean database before tests
    await setupTests();

    await testArbiterOutcomeRecording();
    await testQualityOutcomeRecording();
    await testVotingOutcomeRecording();
    await testManualObservationRecording();
    await testCalibrationPenalty();

    console.log('==================================================');
    console.log('✓ All tests passed!');
    console.log('==================================================\n');

    process.exit(0);
  } catch (err) {
    console.error('\n❌ Test failed:');
    console.error(err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run tests if executed directly
if (require.main === module) {
  runAllTests();
}

module.exports = { runAllTests };
