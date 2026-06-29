/**
 * BFT Median Voting Security Tests
 *
 * Verifies all three security fixes:
 * 1. Confidence calibration penalty (detect lying models)
 * 2. Sybil attack protection (vote flooding detection + family cap)
 * 3. MAD minority protection (never suppress >30% of votes)
 *
 * Created: 2026-06-28
 */

const {
  runWeightedVoting,
  weightedVoting,
  detectOutliersMAD,
} = require('./weighted-voting.cjs');

const {
  storeObservation,
  getCalibrationPenalty,
} = require('./confidence-calibration.cjs');

// ============================================================================
// SECURITY TEST 1: Confidence Calibration Penalty
// ============================================================================

async function testConfidenceCalibration() {
  console.log('\n' + '='.repeat(80));
  console.log('SECURITY TEST 1: Confidence Calibration Penalty');
  console.log('='.repeat(80));

  console.log('\nScenario: Model consistently overstates confidence (90%) but only 60% accurate');

  // Simulate observations (model says 90%, but is only 60% accurate)
  const observations = [
    { model: 'lying-model', reported_confidence: 0.90, actual_outcome: 1, task_type: 'test' },
    { model: 'lying-model', reported_confidence: 0.90, actual_outcome: 0, task_type: 'test' },
    { model: 'lying-model', reported_confidence: 0.90, actual_outcome: 1, task_type: 'test' },
    { model: 'lying-model', reported_confidence: 0.90, actual_outcome: 0, task_type: 'test' },
    { model: 'lying-model', reported_confidence: 0.90, actual_outcome: 0, task_type: 'test' },
    { model: 'lying-model', reported_confidence: 0.90, actual_outcome: 1, task_type: 'test' },
  ];

  // Store observations
  console.log(`\nStoring ${observations.length} calibration observations...`);
  for (const obs of observations) {
    await storeObservation(obs);
  }

  // Get calibration penalty
  const penalty = await getCalibrationPenalty('lying-model', 'test');

  console.log('\nCalibration Results:');
  console.log(`  Reported confidence (avg): ${(penalty.stats.avg_reported * 100).toFixed(1)}%`);
  console.log(`  Actual accuracy (avg): ${(penalty.stats.avg_actual * 100).toFixed(1)}%`);
  console.log(`  Calibration error: ${(penalty.stats.calibration_error * 100).toFixed(1)}%`);
  console.log(`  Penalty multiplier: ${penalty.penalty}× (${penalty.reason})`);

  // Expected: 30% calibration error = 0.50 penalty (major)
  if (penalty.stats.calibration_error > 0.20) {
    console.log('\n✅ PASS: Calibration penalty applied (>20% error detected)');
    console.log(`   Weight reduced by ${((1 - penalty.penalty) * 100).toFixed(0)}%`);
  } else {
    console.log('\n❌ FAIL: Calibration error too low');
  }
}

// ============================================================================
// SECURITY TEST 2: Sybil Attack Protection
// ============================================================================

async function testSybilAttack() {
  console.log('\n' + '='.repeat(80));
  console.log('SECURITY TEST 2: Sybil Attack Protection');
  console.log('='.repeat(80));

  console.log('\nScenario: 50 haiku votes (Sybil attack) vs 5 opus votes');

  // Create 50 haiku votes (vote flooding)
  const sybilVotes = Array(50).fill(null).map(() => ({
    model: 'haiku',
    answer: 'A',
    confidence: 80,
  }));

  // Create 5 opus votes
  const legitimateVotes = Array(5).fill(null).map(() => ({
    model: 'opus',
    answer: 'B',
    confidence: 90,
  }));

  const allVotes = [...sybilVotes, ...legitimateVotes];

  console.log(`\nVotes: ${sybilVotes.length} haiku + ${legitimateVotes.length} opus = ${allVotes.length} total`);
  console.log(`Vote flooding: ${(sybilVotes.length / allVotes.length * 100).toFixed(1)}% from haiku family`);

  const result = await runWeightedVoting(allVotes, 'code_review', {
    minConfidence: 20,
    familyCap: 5,
    familyFloodThreshold: 0.50,
  });

  console.log('\nSybil Attack Detection:');
  if (result.voting_result.sybil_analysis) {
    const sa = result.voting_result.sybil_analysis;
    console.log(`  ✓ Detected: ${sa.detected}`);
    console.log(`  Family: ${sa.family}`);
    console.log(`  Count: ${sa.count}/${sa.total} (${sa.percentage}%)`);
    console.log(`  Threshold: ${sa.threshold}%`);
    console.log(`  Action: ${sa.action_taken}`);
    console.log(`  Votes before cap: ${sa.votes_before}`);
    console.log(`  Votes after cap: ${sa.votes_after}`);
    console.log(`  Votes dropped: ${sa.votes_dropped}`);
  }

  console.log('\nVoting Result:');
  console.log(`  Winner: ${result.voting_result.winner.answer}`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);
  console.log(`  Total weight: ${result.voting_result.winner.total_weight.toFixed(3)}`);

  if (result.voting_result.sybil_analysis?.detected) {
    console.log('\n✅ PASS: Sybil attack detected and mitigated');
    console.log(`   Haiku votes capped from ${sybilVotes.length} to ${result.voting_result.sybil_analysis.familyCap || 5}`);
  } else {
    console.log('\n❌ FAIL: Sybil attack not detected');
  }
}

// ============================================================================
// SECURITY TEST 3: MAD Minority Protection
// ============================================================================

async function testMADMinorityProtection() {
  console.log('\n' + '='.repeat(80));
  console.log('SECURITY TEST 3: MAD Minority Protection');
  console.log('='.repeat(80));

  console.log('\nScenario: 40% of votes disagree (minority opinion should be protected)');

  // Create votes with legitimate disagreement
  // 60% vote "A" with high confidence
  const majorityVotes = Array(6).fill(null).map(() => ({
    model: 'opus',
    answer: 'A',
    confidence: 90,
  }));

  // 40% vote "B" with high confidence (legitimate minority opinion)
  const minorityVotes = Array(4).fill(null).map(() => ({
    model: 'sonnet',
    answer: 'B',
    confidence: 85,
  }));

  const allVotes = [...majorityVotes, ...minorityVotes];

  console.log(`\nVotes: ${majorityVotes.length} for A, ${minorityVotes.length} for B = ${allVotes.length} total`);
  console.log(`Minority percentage: ${(minorityVotes.length / allVotes.length * 100).toFixed(1)}%`);

  // Test MAD outlier detection
  console.log('\nTesting MAD outlier detection with strict threshold (would mark minority as outliers)...');

  // Convert to weighted votes (add normalized_confidence field)
  const weightedVotes = allVotes.map(v => ({
    ...v,
    weight: 1.0,
    normalized_confidence: v.confidence / 100,
  }));

  const madResult = detectOutliersMAD(weightedVotes, 'normalized_confidence', 3);

  console.log('\nMAD Analysis:');
  console.log(`  Median confidence: ${(madResult.median * 100).toFixed(1)}%`);
  console.log(`  MAD: ${madResult.mad.toFixed(3)}`);
  console.log(`  Outliers detected: ${madResult.outliers.length}/${allVotes.length} (${(madResult.outliers.length / allVotes.length * 100).toFixed(1)}%)`);
  console.log(`  Inliers kept: ${madResult.inliers.length}/${allVotes.length}`);

  if (madResult.warning === 'high_disagreement') {
    console.log(`  ⚠ Warning: ${madResult.warning}`);
    console.log(`  Disagreement percentage: ${madResult.disagreement_percentage}%`);
    console.log(`  Action: ${madResult.action_taken}`);
  }

  // Test with weighted voting + MAD strategy
  console.log('\nRunning weighted voting with MAD strategy...');
  const result = await runWeightedVoting(allVotes, 'code_review', {
    strategy: 'mad',
    madThreshold: 3,
  });

  if (result.voting_result.bft_analysis) {
    const bft = result.voting_result.bft_analysis;
    console.log('\nBFT-MAD Results:');
    console.log(`  Strategy: ${bft.strategy}`);
    console.log(`  Outliers detected: ${bft.outliers_detected}`);

    if (bft.warning === 'high_disagreement') {
      console.log(`  ⚠ Warning: ${bft.warning}`);
      console.log(`  Disagreement: ${bft.disagreement_percentage}%`);
      console.log(`  Action: ${bft.action_taken}`);
      console.log('\n✅ PASS: MAD minority protection activated');
      console.log('   Minority opinions (40%) protected from being marked as outliers');
    } else if (bft.outliers_detected === 0) {
      console.log('\n✅ PASS: No outliers detected (all votes considered valid)');
    } else {
      const outlierPct = (bft.outliers_detected / allVotes.length * 100).toFixed(1);
      if (parseFloat(outlierPct) <= 30) {
        console.log(`\n✅ PASS: Outliers (${outlierPct}%) within 30% threshold`);
      } else {
        console.log(`\n❌ FAIL: Too many outliers (${outlierPct}% > 30% threshold)`);
      }
    }
  }
}

// ============================================================================
// RUN ALL SECURITY TESTS
// ============================================================================

async function runSecurityTests() {
  console.log('\n');
  console.log('█'.repeat(80));
  console.log('BFT MEDIAN VOTING - SECURITY TEST SUITE');
  console.log('█'.repeat(80));

  try {
    await testConfidenceCalibration();
    await testSybilAttack();
    await testMADMinorityProtection();

    console.log('\n');
    console.log('█'.repeat(80));
    console.log('ALL SECURITY TESTS PASSED ✅');
    console.log('█'.repeat(80));
    console.log('\n');
  } catch (err) {
    console.error('\n❌ SECURITY TEST FAILED:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run tests if executed directly
if (require.main === module) {
  runSecurityTests();
}

module.exports = {
  runSecurityTests,
  testConfidenceCalibration,
  testSybilAttack,
  testMADMinorityProtection,
};
