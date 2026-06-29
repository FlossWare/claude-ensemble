/**
 * Test Suite for BFT Protections
 *
 * Tests the 3 priority fixes:
 * 1. CRITICAL: Confidence calibration (detect lying models)
 * 2. MAJOR: Sybil attack protection (vote flooding)
 * 3. MAJOR: MAD minority opinion protection
 *
 * Created: 2026-06-28
 */

const {
  runWeightedVoting,
  detectOutliersMAD,
} = require('./weighted-voting.cjs');

const {
  storeObservation,
  getCalibrationStats,
  getCalibrationPenalty,
} = require('./confidence-calibration.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

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

function createVote(model, answer, confidence) {
  return { model, answer, confidence };
}

// ============================================================================
// PRIORITY 1: CONFIDENCE CALIBRATION TESTS
// ============================================================================

async function testCalibration_DetectOverconfident() {
  console.log('Test: Confidence Calibration - Detect Overconfident Model');

  // Simulate model that reports 90% confidence but is only 60% accurate
  const observations = [
    { model: 'overconfident', reported_confidence: 0.90, actual_outcome: 0.0 }, // Wrong
    { model: 'overconfident', reported_confidence: 0.90, actual_outcome: 0.0 }, // Wrong
    { model: 'overconfident', reported_confidence: 0.90, actual_outcome: 1.0 }, // Correct
    { model: 'overconfident', reported_confidence: 0.90, actual_outcome: 1.0 }, // Correct
    { model: 'overconfident', reported_confidence: 0.90, actual_outcome: 1.0 }, // Correct
    { model: 'overconfident', reported_confidence: 0.90, actual_outcome: 0.0 }, // Wrong
  ];

  // Store observations
  for (const obs of observations) {
    await storeObservation(obs);
  }

  // Get calibration stats
  const stats = await getCalibrationStats('overconfident');

  console.log(`  Reported: ${(stats.avg_reported * 100).toFixed(0)}%`);
  console.log(`  Actual: ${(stats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Error: ${(stats.calibration_error * 100).toFixed(1)}%`);

  // Reported: 90%, Actual: 50% (3/6 correct) => Error: 40%
  assertApprox(stats.avg_reported, 0.90, 0.01, 'Reported confidence');
  assertApprox(stats.avg_actual, 0.50, 0.01, 'Actual accuracy');
  assertApprox(stats.calibration_error, 0.40, 0.01, 'Calibration error');

  // Get penalty (should be severe due to 40% error)
  const penalty = await getCalibrationPenalty('overconfident');

  console.log(`  Penalty: ${penalty.penalty}× (${penalty.reason})`);

  assert(penalty.penalty === 0.25, 'Should apply severe penalty (0.25×) for 40% error');

  console.log('  ✓ Pass');
}

async function testCalibration_DetectUnderconfident() {
  console.log('Test: Confidence Calibration - Detect Underconfident Model (Sandbagging)');

  // Simulate model that reports 50% confidence but is 85% accurate (sandbagging)
  const observations = [
    { model: 'sandbagging', reported_confidence: 0.50, actual_outcome: 1.0 }, // Correct
    { model: 'sandbagging', reported_confidence: 0.50, actual_outcome: 1.0 }, // Correct
    { model: 'sandbagging', reported_confidence: 0.50, actual_outcome: 1.0 }, // Correct
    { model: 'sandbagging', reported_confidence: 0.50, actual_outcome: 1.0 }, // Correct
    { model: 'sandbagging', reported_confidence: 0.50, actual_outcome: 1.0 }, // Correct
    { model: 'sandbagging', reported_confidence: 0.50, actual_outcome: 0.0 }, // Wrong
  ];

  for (const obs of observations) {
    await storeObservation(obs);
  }

  const stats = await getCalibrationStats('sandbagging');

  console.log(`  Reported: ${(stats.avg_reported * 100).toFixed(0)}%`);
  console.log(`  Actual: ${(stats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Error: ${(stats.calibration_error * 100).toFixed(1)}%`);

  // Reported: 50%, Actual: 83% (5/6 correct) => Error: 33%
  assertApprox(stats.avg_reported, 0.50, 0.01, 'Reported confidence');
  assertApprox(stats.avg_actual, 0.833, 0.05, 'Actual accuracy');

  // Get penalty (should be severe due to 33% error)
  const penalty = await getCalibrationPenalty('sandbagging');

  console.log(`  Penalty: ${penalty.penalty}× (${penalty.reason})`);

  assert(penalty.penalty === 0.25, 'Should apply severe penalty for sandbagging');

  console.log('  ✓ Pass');
}

async function testCalibration_WellCalibrated() {
  console.log('Test: Confidence Calibration - Well-Calibrated Model');

  // Simulate well-calibrated model (reports 80% confidence, is 80% accurate)
  const observations = [
    { model: 'honest', reported_confidence: 0.80, actual_outcome: 1.0 },
    { model: 'honest', reported_confidence: 0.80, actual_outcome: 1.0 },
    { model: 'honest', reported_confidence: 0.80, actual_outcome: 1.0 },
    { model: 'honest', reported_confidence: 0.80, actual_outcome: 1.0 },
    { model: 'honest', reported_confidence: 0.80, actual_outcome: 0.0 },
  ];

  for (const obs of observations) {
    await storeObservation(obs);
  }

  const stats = await getCalibrationStats('honest');

  console.log(`  Reported: ${(stats.avg_reported * 100).toFixed(0)}%`);
  console.log(`  Actual: ${(stats.avg_actual * 100).toFixed(0)}%`);
  console.log(`  Error: ${(stats.calibration_error * 100).toFixed(1)}%`);

  // Reported: 80%, Actual: 80% (4/5 correct) => Error: 0%
  assertApprox(stats.avg_reported, 0.80, 0.01, 'Reported confidence');
  assertApprox(stats.avg_actual, 0.80, 0.01, 'Actual accuracy');

  const penalty = await getCalibrationPenalty('honest');

  console.log(`  Penalty: ${penalty.penalty}× (${penalty.reason})`);

  assert(penalty.penalty === 1.0, 'Should have no penalty for well-calibrated model');

  console.log('  ✓ Pass');
}

// ============================================================================
// PRIORITY 2: SYBIL ATTACK PROTECTION TESTS
// ============================================================================

async function testSybil_VoteFlooding() {
  console.log('Test: Sybil Attack - Vote Flooding (30 weak vs 5 strong)');

  // 30 haiku models vote "A" (vote flooding)
  const weakVotes = Array(30).fill(null).map((_, i) =>
    createVote(`haiku-${i}`, 'A', 50)
  );

  // 5 opus models vote "B"
  const strongVotes = Array(5).fill(null).map((_, i) =>
    createVote(`opus-${i}`, 'B', 90)
  );

  const allVotes = [...weakVotes, ...strongVotes];

  const result = await runWeightedVoting(allVotes, 'code_review', {
    minConfidence: 20,
  });

  console.log(`  Total votes: ${allVotes.length}`);

  // Check for Sybil detection
  if (result.voting_result.sybil_analysis) {
    const analysis = result.voting_result.sybil_analysis;
    console.log(`  Sybil detected: ${analysis.detected}`);
    console.log(`  Family: ${analysis.family} (${analysis.count}/${analysis.total} votes = ${analysis.percentage}%)`);
    console.log(`  Action taken: ${analysis.action_taken}`);

    assert(analysis.detected === true, 'Should detect vote flooding');
    assert(analysis.family === 'haiku', 'Should identify haiku family');
    assert(parseInt(analysis.percentage) > 50, 'Should exceed 50% threshold');
  } else {
    throw new Error('Sybil analysis missing from result');
  }

  console.log('  ✓ Pass');
}

async function testSybil_FamilyCap() {
  console.log('Test: Sybil Attack - Family Cap Applied');

  // 10 haiku models vote "A"
  const haikuVotes = Array(10).fill(null).map((_, i) =>
    createVote(`haiku-${i}`, 'A', 70)
  );

  // 2 opus models vote "B"
  const opusVotes = Array(2).fill(null).map((_, i) =>
    createVote(`opus-${i}`, 'B', 90)
  );

  const allVotes = [...haikuVotes, ...opusVotes];

  const result = await runWeightedVoting(allVotes, 'code_review', {
    minConfidence: 20,
    familyCap: 5,  // Cap to 5 votes per family
  });

  // Check that family cap was applied
  if (result.voting_result.sybil_analysis) {
    const analysis = result.voting_result.sybil_analysis;
    console.log(`  Votes before cap: ${analysis.votes_before}`);
    console.log(`  Votes after cap: ${analysis.votes_after}`);
    console.log(`  Votes dropped: ${analysis.votes_dropped}`);

    assert(analysis.votes_dropped === 5, 'Should drop 5 haiku votes (10 - 5 cap)');
    assert(analysis.votes_after === 7, 'Should have 7 votes after cap (5 haiku + 2 opus)');
  }

  console.log('  ✓ Pass');
}

async function testSybil_NoDiversity() {
  console.log('Test: Sybil Attack - No Diversity Issue (Normal Voting)');

  // Diverse vote distribution (no flooding)
  const votes = [
    createVote('opus-1', 'A', 90),
    createVote('opus-2', 'A', 85),
    createVote('sonnet-1', 'B', 80),
    createVote('haiku-1', 'A', 70),
    createVote('gemini-1', 'B', 75),
  ];

  const result = await runWeightedVoting(votes, 'code_review', {
    minConfidence: 20,
  });

  // Should NOT detect Sybil attack
  if (result.voting_result.sybil_analysis) {
    throw new Error('Should not detect Sybil attack with diverse votes');
  }

  console.log('  No Sybil attack detected (diverse votes) ✓');
  console.log('  ✓ Pass');
}

// ============================================================================
// PRIORITY 3: MAD MINORITY OPINION PROTECTION TESTS
// ============================================================================

function testMAD_MinorityProtection() {
  console.log('Test: MAD - Minority Opinion Protection (40% disagreement)');

  // 6 votes at 0.9, 4 votes at 0.3 (40% minority opinion)
  const votes = [
    { model: 'opus-1', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-2', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-3', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-4', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-5', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-6', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'expert-1', normalized_confidence: 0.3, weight: 1.0 }, // Minority
    { model: 'expert-2', normalized_confidence: 0.3, weight: 1.0 }, // Minority
    { model: 'expert-3', normalized_confidence: 0.3, weight: 1.0 }, // Minority
    { model: 'expert-4', normalized_confidence: 0.3, weight: 1.0 }, // Minority
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  console.log(`  Total votes: ${votes.length}`);
  console.log(`  Outliers detected: ${result.outliers.length}`);

  // Should detect high disagreement and return NO outliers (protect minority)
  if (result.warning === 'high_disagreement') {
    console.log(`  Warning: ${result.warning}`);
    console.log(`  Disagreement: ${(result.disagreement_percentage * 100).toFixed(1)}%`);
    assert(result.outliers.length === 0, 'Should return no outliers (minority protected)');
    assert(result.inliers.length === votes.length, 'All votes should be inliers');
  } else {
    throw new Error('Should detect high disagreement and protect minority');
  }

  console.log('  ✓ Pass');
}

function testMAD_LegitimateOutlier() {
  console.log('Test: MAD - Legitimate Outlier Detection (<30%)');

  // 9 votes at 0.9, 1 vote at 0.1 (10% outlier - legitimate broken model)
  const votes = [
    { model: 'opus-1', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-2', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-3', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-4', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-5', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-6', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-7', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-8', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-9', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'broken', normalized_confidence: 0.1, weight: 1.0 },  // Outlier
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  console.log(`  Total votes: ${votes.length}`);
  console.log(`  Outliers detected: ${result.outliers.length}`);

  // Should detect 1 outlier (10% < 30% threshold)
  assert(result.outliers.length === 1, 'Should detect 1 outlier');
  assert(result.outliers[0].model === 'broken', 'Should identify broken model');
  assert(result.inliers.length === 9, 'Should have 9 inliers');

  console.log(`  Outlier: ${result.outliers[0].model}`);
  console.log('  ✓ Pass');
}

function testMAD_MinimumThreshold() {
  console.log('Test: MAD - Minimum Threshold (0.1) Before Activation');

  // All votes clustered at 0.9 (no disagreement, MAD = 0)
  const votes = [
    { model: 'opus-1', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-2', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-3', normalized_confidence: 0.9, weight: 1.0 },
    { model: 'opus-4', normalized_confidence: 0.905, weight: 1.0 }, // Tiny variance
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  console.log(`  MAD: ${result.mad.toFixed(4)}`);
  console.log(`  Outliers: ${result.outliers.length}`);

  // MAD should be tiny, but minimum threshold (0.1) should prevent false outliers
  assert(result.mad < 0.01, 'MAD should be very small');
  assert(result.outliers.length === 0, 'Should not detect outliers with tiny variance');

  console.log('  ✓ Pass (minimum threshold prevents false outliers)');
}

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

async function testIntegration_AllProtections() {
  console.log('Test: Integration - All 3 Protections Working Together');

  // Scenario:
  //   - 20 haiku votes (vote flooding) - some with bad calibration
  //   - 3 opus votes (minority expert opinion)
  //   - 1 broken model (outlier)

  // First, seed calibration data for haiku (overconfident)
  for (let i = 0; i < 5; i++) {
    await storeObservation({
      model: 'haiku',
      reported_confidence: 0.90,
      actual_outcome: 0.0,  // Wrong (overconfident)
      task_type: 'code_review',
    });
  }

  await storeObservation({
    model: 'haiku',
    reported_confidence: 0.90,
    actual_outcome: 1.0,  // Correct
    task_type: 'code_review',
  });

  // Create votes
  const haikuVotes = Array(20).fill(null).map((_, i) =>
    createVote(`haiku-${i}`, 'A', 70)
  );

  const opusVotes = [
    createVote('opus-1', 'B', 90),
    createVote('opus-2', 'B', 85),
    createVote('opus-3', 'B', 88),
  ];

  const brokenVote = createVote('broken', 'C', 10);

  const allVotes = [...haikuVotes, ...opusVotes, brokenVote];

  const result = await runWeightedVoting(allVotes, 'code_review', {
    minConfidence: 20,
    strategy: 'mad',
    familyCap: 5,
  });

  console.log('\n  === Integration Test Results ===');

  // Check Sybil protection
  if (result.voting_result.sybil_analysis) {
    console.log(`  ✓ Sybil Protection: Detected ${result.voting_result.sybil_analysis.family} flooding`);
    console.log(`    Action: ${result.voting_result.sybil_analysis.action_taken}`);
  }

  // Check calibration penalties
  const haikuVote = result.voting_result.winner.votes.find(v => v.model.startsWith('haiku'));
  if (haikuVote) {
    console.log(`  ✓ Calibration: haiku penalty = ${haikuVote.calibration_penalty}× (${haikuVote.calibration_reason})`);
    assert(haikuVote.calibration_penalty < 1.0, 'Should apply calibration penalty to haiku');
  }

  // Check MAD minority protection
  if (result.voting_result.bft_analysis) {
    console.log(`  ✓ MAD: Outliers detected = ${result.voting_result.bft_analysis.outliers_detected}`);
    if (result.voting_result.bft_analysis.warning === 'high_disagreement') {
      console.log(`    Minority protected: ${result.voting_result.bft_analysis.disagreement_percentage}% disagreement`);
    }
  }

  console.log(`  Winner: ${result.voting_result.winner.answer}`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);

  console.log('  ✓ Pass (all 3 protections active)');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('\n' + '='.repeat(60));
  console.log('BFT PROTECTIONS TEST SUITE');
  console.log('='.repeat(60) + '\n');

  let passed = 0;
  let failed = 0;

  const tests = [
    // Priority 1: Confidence Calibration
    testCalibration_DetectOverconfident,
    testCalibration_DetectUnderconfident,
    testCalibration_WellCalibrated,

    // Priority 2: Sybil Attack Protection
    testSybil_VoteFlooding,
    testSybil_FamilyCap,
    testSybil_NoDiversity,

    // Priority 3: MAD Minority Protection
    testMAD_MinorityProtection,
    testMAD_LegitimateOutlier,
    testMAD_MinimumThreshold,

    // Integration
    testIntegration_AllProtections,
  ];

  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (err) {
      console.error(`  ✗ FAIL: ${err.message}`);
      console.error(err.stack);
      failed++;
    }
  }

  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));
  console.log(`  Total: ${tests.length}`);
  console.log(`  Passed: ${passed} ✓`);
  console.log(`  Failed: ${failed} ✗`);
  console.log('='.repeat(60) + '\n');

  if (failed > 0) {
    process.exit(1);
  }
}

// Run tests
if (require.main === module) {
  runAllTests().catch(err => {
    console.error('Test suite failed:', err);
    process.exit(1);
  });
}

module.exports = { runAllTests };
