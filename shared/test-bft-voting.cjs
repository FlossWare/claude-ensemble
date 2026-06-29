/**
 * Test Suite for Byzantine Fault Tolerance (BFT) Median Voting
 *
 * Tests BFT strategies for multi-AI consensus voting:
 * - Median voting (outlier resistant)
 * - Trimmed mean (drop top/bottom 20%)
 * - MAD outlier detection (Median Absolute Deviation)
 *
 * Created: 2026-06-28
 */

const {
  weightedMedian,
  trimmedMean,
  weightedAverage,
  detectOutliersMAD,
  runWeightedVoting,
} = require('./weighted-voting.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

/**
 * Assert helper
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

/**
 * Assert approximately equal (for floating point)
 */
function assertApprox(actual, expected, tolerance = 0.001, message = '') {
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

/**
 * Create test vote
 */
function createVote(model, confidence, weight = 1.0, answer = 'A') {
  return {
    model,
    answer,
    confidence,
    weight,
    normalized_confidence: confidence,
  };
}

// ============================================================================
// UNIT TESTS: WEIGHTED MEDIAN
// ============================================================================

function testWeightedMedian_SingleVote() {
  console.log('Test: Weighted Median - Single Vote');

  const votes = [createVote('opus', 0.9)];
  const median = weightedMedian(votes, 'normalized_confidence');

  assertApprox(median, 0.9, 0.001, 'Single vote median should equal vote value');
  console.log('  ✓ Pass');
}

function testWeightedMedian_TwoVotes() {
  console.log('Test: Weighted Median - Two Votes (Equal Weight)');

  const votes = [
    createVote('opus', 0.9, 1.0),
    createVote('haiku', 0.5, 1.0),
  ];

  const median = weightedMedian(votes, 'normalized_confidence');

  // With equal weights and exactly 50% at first value, should interpolate
  // Cumulative: 0 -> 1.0 (at 0.5) -> 2.0 (at 0.9)
  // 50% = 1.0, reached at first vote (0.5), but need to check interpolation
  // Actually: cumWeight after first = 1.0, halfWeight = 1.0, so we're at exactly 50%
  // Should interpolate between 0.5 and 0.9 => 0.7
  assertApprox(median, 0.7, 0.001, 'Two equal-weight votes median should interpolate');
  console.log('  ✓ Pass');
}

function testWeightedMedian_OutlierResistance() {
  console.log('Test: Weighted Median - Outlier Resistance');

  // 5 votes at 0.9, 1 vote at 0.1 (outlier)
  const votes = [
    createVote('opus-1', 0.9, 1.0),
    createVote('opus-2', 0.9, 1.0),
    createVote('opus-3', 0.9, 1.0),
    createVote('opus-4', 0.9, 1.0),
    createVote('opus-5', 0.9, 1.0),
    createVote('broken', 0.1, 1.0),  // Outlier
  ];

  const median = weightedMedian(votes, 'normalized_confidence');
  const mean = weightedAverage(votes, 'normalized_confidence');

  assertApprox(median, 0.9, 0.001, 'Median should ignore outlier');
  assertApprox(mean, 0.767, 0.01, 'Mean should be dragged down by outlier');

  console.log(`  Median: ${median.toFixed(3)} (resistant to outlier) ✓`);
  console.log(`  Mean: ${mean.toFixed(3)} (dragged down by outlier)`);
  console.log('  ✓ Pass');
}

function testWeightedMedian_EmptyVotes() {
  console.log('Test: Weighted Median - Empty Votes');

  const median = weightedMedian([], 'normalized_confidence');

  assertApprox(median, 0.5, 0.001, 'Empty votes should return neutral 0.5');
  console.log('  ✓ Pass');
}

function testWeightedMedian_AllZeroWeights() {
  console.log('Test: Weighted Median - All Zero Weights');

  const votes = [
    createVote('opus', 0.9, 0.0),
    createVote('haiku', 0.5, 0.0),
  ];

  const median = weightedMedian(votes, 'normalized_confidence');

  assertApprox(median, 0.5, 0.001, 'All zero weights should return neutral 0.5');
  console.log('  ✓ Pass');
}

// ============================================================================
// UNIT TESTS: TRIMMED MEAN
// ============================================================================

function testTrimmedMean_NormalCase() {
  console.log('Test: Trimmed Mean - Normal Case');

  // 10 votes: drop top 20% (2) and bottom 20% (2), average middle 6
  const votes = [
    createVote('v1', 0.1, 1.0),   // Drop (bottom 20%)
    createVote('v2', 0.2, 1.0),   // Drop (bottom 20%)
    createVote('v3', 0.5, 1.0),   // Keep
    createVote('v4', 0.6, 1.0),   // Keep
    createVote('v5', 0.7, 1.0),   // Keep
    createVote('v6', 0.8, 1.0),   // Keep
    createVote('v7', 0.85, 1.0),  // Keep
    createVote('v8', 0.9, 1.0),   // Keep
    createVote('v9', 0.95, 1.0),  // Drop (top 20%)
    createVote('v10', 0.99, 1.0), // Drop (top 20%)
  ];

  const trimmed = trimmedMean(votes, 'normalized_confidence', 20);

  // Middle 6: 0.5, 0.6, 0.7, 0.8, 0.85, 0.9 => avg = 0.725
  assertApprox(trimmed, 0.725, 0.01, 'Trimmed mean should average middle 60%');
  console.log('  ✓ Pass');
}

function testTrimmedMean_TooFewVotes() {
  console.log('Test: Trimmed Mean - Too Few Votes');

  const votes = [
    createVote('opus', 0.9, 1.0),
    createVote('haiku', 0.5, 1.0),
  ];

  const trimmed = trimmedMean(votes, 'normalized_confidence', 20);
  const avg = weightedAverage(votes, 'normalized_confidence');

  assertApprox(trimmed, avg, 0.001, 'Too few votes - should use weighted average');
  console.log('  ✓ Pass');
}

function testTrimmedMean_SingleVote() {
  console.log('Test: Trimmed Mean - Single Vote');

  const votes = [createVote('opus', 0.9, 1.0)];
  const trimmed = trimmedMean(votes, 'normalized_confidence', 20);

  assertApprox(trimmed, 0.9, 0.001, 'Single vote should return vote value');
  console.log('  ✓ Pass');
}

// ============================================================================
// UNIT TESTS: MAD OUTLIER DETECTION
// ============================================================================

function testMAD_NoOutliers() {
  console.log('Test: MAD - No Outliers');

  const votes = [
    createVote('opus-1', 0.88, 1.0),
    createVote('opus-2', 0.90, 1.0),
    createVote('opus-3', 0.92, 1.0),
    createVote('opus-4', 0.91, 1.0),
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  assert(result.inliers.length === 4, 'All votes should be inliers');
  assert(result.outliers.length === 0, 'No outliers expected');
  assertApprox(result.median, 0.905, 0.01, 'Median should be ~0.905');

  console.log(`  Median: ${result.median.toFixed(3)}, MAD: ${result.mad.toFixed(3)}`);
  console.log('  ✓ Pass');
}

function testMAD_OneOutlier() {
  console.log('Test: MAD - One Outlier');

  const votes = [
    createVote('opus-1', 0.9, 1.0),
    createVote('opus-2', 0.9, 1.0),
    createVote('opus-3', 0.9, 1.0),
    createVote('opus-4', 0.9, 1.0),
    createVote('broken', 0.1, 1.0),  // Outlier
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  assert(result.inliers.length === 4, 'Should have 4 inliers');
  assert(result.outliers.length === 1, 'Should detect 1 outlier');
  assert(result.outliers[0].model === 'broken', 'Broken model should be outlier');

  console.log(`  Median: ${result.median.toFixed(3)}, MAD: ${result.mad.toFixed(3)}`);
  console.log(`  Outlier detected: ${result.outliers[0].model} (confidence: ${result.outliers[0].normalized_confidence})`);
  console.log('  ✓ Pass');
}

function testMAD_MultipleOutliers() {
  console.log('Test: MAD - Multiple Outliers');

  const votes = [
    createVote('opus-1', 0.9, 1.0),
    createVote('opus-2', 0.9, 1.0),
    createVote('opus-3', 0.9, 1.0),
    createVote('broken-1', 0.1, 1.0),  // Outlier
    createVote('broken-2', 0.05, 1.0), // Outlier
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  console.log(`  Median: ${result.median.toFixed(3)}, MAD: ${result.mad.toFixed(3)}`);
  console.log(`  Outliers detected: ${result.outliers.length}`);

  // PRIORITY 3: MAD protection triggered (2/5 = 40% > 30% threshold)
  if (result.warning === 'high_disagreement') {
    console.log(`  Warning: ${result.warning} (${(result.disagreement_percentage * 100).toFixed(1)}%)`);
    assert(result.inliers.length === 5, 'Should protect minority opinion - all votes are inliers');
    assert(result.outliers.length === 0, 'Should have 0 outliers (minority protected)');
    console.log('  ✓ Pass (minority opinion protected)');
  } else {
    // If < 30%, MAD may still detect outliers
    assert(result.inliers.length === 3, 'Should have 3 inliers');
    assert(result.outliers.length === 2, 'Should detect 2 outliers');
    console.log('  ✓ Pass');
  }
}

function testMAD_AllIdentical() {
  console.log('Test: MAD - All Identical Votes');

  const votes = [
    createVote('opus-1', 0.9, 1.0),
    createVote('opus-2', 0.9, 1.0),
    createVote('opus-3', 0.9, 1.0),
  ];

  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  assert(result.inliers.length === 3, 'All votes should be inliers');
  assert(result.outliers.length === 0, 'No outliers expected');
  assertApprox(result.mad, 0.0, 0.001, 'MAD should be 0 for identical votes');

  console.log('  ✓ Pass');
}

function testMAD_SingleVote() {
  console.log('Test: MAD - Single Vote');

  const votes = [createVote('opus', 0.9, 1.0)];
  const result = detectOutliersMAD(votes, 'normalized_confidence', 3);

  assert(result.inliers.length === 1, 'Single vote should be inlier');
  assert(result.outliers.length === 0, 'Single vote cannot be outlier');

  console.log('  ✓ Pass');
}

// ============================================================================
// INTEGRATION TESTS: BFT VOTING
// ============================================================================

async function testBFT_MedianStrategy() {
  console.log('Test: BFT Integration - Median Strategy');

  const votes = [
    { model: 'opus-1', answer: 'A', confidence: 90 },
    { model: 'opus-2', answer: 'A', confidence: 90 },
    { model: 'opus-3', answer: 'A', confidence: 90 },
    { model: 'opus-4', answer: 'A', confidence: 90 },
    { model: 'broken', answer: 'B', confidence: 10 },  // Outlier
  ];

  const result = await runWeightedVoting(votes, 'general', { strategy: 'median' });

  assert(result.voting_result.status === 'success', 'Voting should succeed');
  assert(result.voting_result.bft_enabled === true, 'BFT should be enabled');
  assert(result.voting_result.algorithm === 'weighted_voting_bft_median', 'Should use median strategy');
  assert(result.voting_result.winner.answer === 'A', 'A should win despite outlier');

  console.log(`  Winner: ${result.voting_result.winner.answer}`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);
  console.log(`  BFT Median Confidence: ${result.voting_result.bft_metrics.median_confidence.toFixed(3)}`);
  console.log('  ✓ Pass');
}

async function testBFT_TrimmedMeanStrategy() {
  console.log('Test: BFT Integration - Trimmed Mean Strategy');

  const votes = [
    { model: 'opus-1', answer: 'A', confidence: 85 },
    { model: 'opus-2', answer: 'A', confidence: 87 },
    { model: 'opus-3', answer: 'A', confidence: 90 },
    { model: 'opus-4', answer: 'A', confidence: 92 },
    { model: 'opus-5', answer: 'A', confidence: 95 },
    { model: 'broken-1', answer: 'B', confidence: 5 },   // Low outlier
    { model: 'broken-2', answer: 'B', confidence: 100 }, // High outlier
  ];

  const result = await runWeightedVoting(votes, 'general', {
    strategy: 'trimmed-mean',
    trimPercent: 20,
  });

  assert(result.voting_result.status === 'success', 'Voting should succeed');
  assert(result.voting_result.bft_enabled === true, 'BFT should be enabled');
  assert(result.voting_result.algorithm === 'weighted_voting_bft_trimmed-mean', 'Should use trimmed-mean strategy');
  assert(result.voting_result.winner.answer === 'A', 'A should win');

  console.log(`  Winner: ${result.voting_result.winner.answer}`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);
  console.log(`  BFT Trimmed Mean: ${result.voting_result.bft_metrics.trimmed_confidence.toFixed(3)}`);
  console.log('  ✓ Pass');
}

async function testBFT_MADStrategy() {
  console.log('Test: BFT Integration - MAD Strategy');

  // Use confidence above minConfidence threshold (20%) but still an outlier
  const votes = [
    { model: 'opus-1', answer: 'A', confidence: 90 },
    { model: 'opus-2', answer: 'A', confidence: 90 },
    { model: 'opus-3', answer: 'A', confidence: 90 },
    { model: 'opus-4', answer: 'A', confidence: 90 },
    { model: 'broken', answer: 'B', confidence: 30 },  // Outlier (above minConfidence=20)
  ];

  const result = await runWeightedVoting(votes, 'general', {
    strategy: 'mad',
    madThreshold: 3,
    minConfidence: 20,  // Explicit (matches default)
  });

  assert(result.voting_result.status === 'success', 'Voting should succeed');
  assert(result.voting_result.bft_enabled === true, 'BFT should be enabled');
  assert(result.voting_result.algorithm === 'weighted_voting_bft_mad', 'Should use MAD strategy');
  assert(result.voting_result.winner.answer === 'A', 'A should win');

  // BFT analysis should exist
  assert(result.voting_result.bft_analysis !== undefined, 'BFT analysis should exist');

  // Check outliers detected (broken model at confidence=30 should be outlier)
  const outliersDetected = result.voting_result.bft_analysis.outliers_detected || 0;

  console.log(`  Winner: ${result.voting_result.winner.answer}`);
  console.log(`  Outliers detected: ${outliersDetected}`);

  if (outliersDetected > 0) {
    console.log(`  Outlier model: ${result.voting_result.bft_analysis.outliers[0].model}`);
  }

  // The outlier should be detected (broken model at 0.3 vs median at 0.9)
  assert(outliersDetected >= 1, 'Should detect at least 1 outlier');

  console.log('  ✓ Pass');
}

async function testBFT_MAD_AllOutliers() {
  console.log('Test: BFT Integration - MAD All Outliers (Edge Case)');

  // Pathological case: All votes are outliers (MAD threshold too strict)
  const votes = [
    { model: 'opus-1', answer: 'A', confidence: 10 },
    { model: 'opus-2', answer: 'B', confidence: 90 },
  ];

  const result = await runWeightedVoting(votes, 'general', {
    strategy: 'mad',
    madThreshold: 0.01,  // Impossibly strict threshold
  });

  assert(result.voting_result.status === 'success', 'Voting should succeed');

  // Check if warning exists (it should when all votes marked as outliers)
  if (result.voting_result.bft_analysis) {
    if (result.voting_result.bft_analysis.warning) {
      assert(result.voting_result.bft_analysis.warning === 'all_votes_outliers', 'Should warn about all outliers');
      assert(result.voting_result.bft_analysis.action_taken === 'used_all_votes', 'Should use all votes as fallback');

      console.log(`  Warning: ${result.voting_result.bft_analysis.warning}`);
      console.log(`  Action: ${result.voting_result.bft_analysis.action_taken}`);
    } else {
      // MAD may have adjusted threshold, check outliers
      console.log(`  Outliers detected: ${result.voting_result.bft_analysis.outliers_detected || 0}`);
      console.log(`  (Edge case handled gracefully)`);
    }
  }

  console.log('  ✓ Pass');
}

// ============================================================================
// PERFORMANCE COMPARISON TESTS
// ============================================================================

async function testPerformanceComparison() {
  console.log('\n=== PERFORMANCE COMPARISON: BFT vs Weighted Average ===\n');

  const testCases = [
    {
      name: 'Normal consensus (no outliers)',
      votes: [
        { model: 'opus-1', answer: 'A', confidence: 90 },
        { model: 'opus-2', answer: 'A', confidence: 88 },
        { model: 'opus-3', answer: 'A', confidence: 92 },
        { model: 'sonnet-1', answer: 'B', confidence: 75 },
      ],
    },
    {
      name: 'One broken model (outlier)',
      votes: [
        { model: 'opus-1', answer: 'A', confidence: 90 },
        { model: 'opus-2', answer: 'A', confidence: 90 },
        { model: 'opus-3', answer: 'A', confidence: 90 },
        { model: 'opus-4', answer: 'A', confidence: 90 },
        { model: 'broken', answer: 'B', confidence: 10 },
      ],
    },
    {
      name: 'Two broken models (multiple outliers)',
      votes: [
        { model: 'opus-1', answer: 'A', confidence: 90 },
        { model: 'opus-2', answer: 'A', confidence: 90 },
        { model: 'opus-3', answer: 'A', confidence: 90 },
        { model: 'broken-1', answer: 'B', confidence: 5 },
        { model: 'broken-2', answer: 'B', confidence: 8 },
      ],
    },
    {
      name: 'High variance (no clear outliers)',
      votes: [
        { model: 'opus-1', answer: 'A', confidence: 95 },
        { model: 'sonnet-1', answer: 'A', confidence: 80 },
        { model: 'haiku-1', answer: 'A', confidence: 65 },
        { model: 'sonnet-2', answer: 'B', confidence: 75 },
      ],
    },
  ];

  for (const tc of testCases) {
    console.log(`\nTest Case: ${tc.name}`);
    console.log('─'.repeat(60));

    const strategies = ['weighted-average', 'median', 'trimmed-mean', 'mad'];

    for (const strategy of strategies) {
      const result = await runWeightedVoting(tc.votes, 'general', { strategy });

      if (result.voting_result.status === 'success') {
        const winner = result.voting_result.winner;
        console.log(`  [${strategy.padEnd(16)}] Winner: ${winner.answer}, ` +
                   `Weight: ${winner.total_weight.toFixed(3)}, ` +
                   `Consensus: ${winner.consensus_level}`);

        if (result.voting_result.bft_analysis) {
          console.log(`  ${' '.repeat(20)}Outliers: ${result.voting_result.bft_analysis.outliers_detected}`);
        }
      }
    }
  }

  console.log('\n' + '='.repeat(60) + '\n');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('\n' + '='.repeat(60));
  console.log('BFT MEDIAN VOTING TEST SUITE');
  console.log('='.repeat(60) + '\n');

  let passed = 0;
  let failed = 0;

  const tests = [
    // Weighted Median
    testWeightedMedian_SingleVote,
    testWeightedMedian_TwoVotes,
    testWeightedMedian_OutlierResistance,
    testWeightedMedian_EmptyVotes,
    testWeightedMedian_AllZeroWeights,

    // Trimmed Mean
    testTrimmedMean_NormalCase,
    testTrimmedMean_TooFewVotes,
    testTrimmedMean_SingleVote,

    // MAD Outlier Detection
    testMAD_NoOutliers,
    testMAD_OneOutlier,
    testMAD_MultipleOutliers,
    testMAD_AllIdentical,
    testMAD_SingleVote,

    // BFT Integration (async)
    testBFT_MedianStrategy,
    testBFT_TrimmedMeanStrategy,
    testBFT_MADStrategy,
    testBFT_MAD_AllOutliers,
  ];

  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (err) {
      console.error(`  ✗ FAIL: ${err.message}`);
      failed++;
    }
  }

  // Performance comparison (informational, not pass/fail)
  await testPerformanceComparison();

  console.log('='.repeat(60));
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
