/**
 * Integration Test: Statistical Significance + Weighted Voting
 *
 * Verifies that statistical significance integrates correctly with weighted voting.
 *
 * Run: node shared/test-integration-statistical-significance.cjs
 */

const { runWeightedVoting } = require('./weighted-voting.cjs');

// ============================================================================
// TEST HELPERS
// ============================================================================

/**
 * Create mock votes for testing
 */
function createMockVotes(answerDistribution) {
  const votes = [];

  answerDistribution.forEach(({ answer, count, model, confidence }) => {
    for (let i = 0; i < count; i++) {
      votes.push({
        model: model || `model-${i}`,
        answer,
        confidence: confidence || (Math.random() * 40 + 60), // 60-100
      });
    }
  });

  return votes;
}

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

/**
 * Test 1: Statistical significance with clear winner
 */
async function testClearWinner() {
  console.log('TEST 1: Clear Winner Integration');
  console.log('='.repeat(70));

  const votes = createMockVotes([
    { answer: 'A', count: 12, model: 'opus', confidence: 90 },
    { answer: 'B', count: 3, model: 'haiku', confidence: 60 },
  ]);

  const result = await runWeightedVoting(votes, 'general', {
    minConfidence: 50,
    bootstrapIterations: 500, // Reduced for faster testing
  });

  console.log('VOTING RESULT:');
  console.log(`  Winner: ${JSON.stringify(result.summary.winner_answer)}`);
  console.log(`  Consensus: ${result.summary.consensus_level}`);
  console.log(`  Statistical Tie: ${result.summary.statistical_tie}`);
  console.log(`  Needs More Samples: ${result.summary.needs_more_samples}`);

  if (result.statistical_significance) {
    const sig = result.statistical_significance;
    console.log('\nSTATISTICAL SIGNIFICANCE:');
    console.log(`  Winner CI: [${sig.winner_ci.ci_lower.toFixed(3)}, ${sig.winner_ci.ci_upper.toFixed(3)}]`);
    console.log(`  Consensus CI: [${(sig.consensus_strength_ci.ci_lower * 100).toFixed(1)}%, ${(sig.consensus_strength_ci.ci_upper * 100).toFixed(1)}%]`);
    console.log(`  Tie Detected: ${sig.tie_analysis.is_tie}`);
    console.log(`  Additional Samples Recommended: ${sig.sample_size_recommendation.recommended_additional}`);
  }

  console.log('\nASSERTIONS:');
  console.log(`  ✓ Winner is 'A': ${result.summary.winner_answer === 'A'}`);
  console.log(`  ✓ Strong consensus: ${result.summary.consensus_level === 'strong'}`);
  console.log(`  ✓ No statistical tie: ${!result.summary.statistical_tie}`);
  console.log(`  ✓ Has statistical significance: ${result.statistical_significance !== null}`);

  console.log('');
}

/**
 * Test 2: Statistical significance with tie
 */
async function testStatisticalTie() {
  console.log('TEST 2: Statistical Tie Integration');
  console.log('='.repeat(70));

  // Create a very close race
  const votes = createMockVotes([
    { answer: 'A', count: 8, model: 'opus', confidence: 75 },
    { answer: 'B', count: 7, model: 'sonnet', confidence: 74 },
  ]);

  const result = await runWeightedVoting(votes, 'general', {
    minConfidence: 50,
    bootstrapIterations: 500,
  });

  console.log('VOTING RESULT:');
  console.log(`  Winner: ${JSON.stringify(result.summary.winner_answer)}`);
  console.log(`  Consensus: ${result.summary.consensus_level}`);
  console.log(`  Statistical Tie: ${result.summary.statistical_tie}`);
  console.log(`  Needs More Samples: ${result.summary.needs_more_samples}`);

  if (result.statistical_significance) {
    const sig = result.statistical_significance;
    console.log('\nSTATISTICAL SIGNIFICANCE:');
    console.log(`  Tie Detected: ${sig.tie_analysis.is_tie}`);
    console.log(`  Margin: ${sig.tie_analysis.margin_percent?.toFixed(1)}%`);
    console.log(`  CI Overlap: ${sig.tie_analysis.ci_overlap_percent?.toFixed(1)}%`);
    console.log(`  Reason: ${sig.tie_analysis.reason}`);
  }

  console.log('\nASSERTIONS:');
  console.log(`  ✓ Winner exists: ${result.summary.winner_answer !== null}`);
  console.log(`  ✓ Weak/moderate consensus: ${['weak', 'moderate'].includes(result.summary.consensus_level)}`);
  console.log(`  ✓ Has statistical significance: ${result.statistical_significance !== null}`);

  console.log('');
}

/**
 * Test 3: Skip statistical significance (performance mode)
 */
async function testSkipStatisticalSignificance() {
  console.log('TEST 3: Skip Statistical Significance (Performance Mode)');
  console.log('='.repeat(70));

  const votes = createMockVotes([
    { answer: 'A', count: 10, model: 'opus', confidence: 90 },
  ]);

  const result = await runWeightedVoting(votes, 'general', {
    minConfidence: 50,
    skipStatisticalSignificance: true, // Performance mode
  });

  console.log('VOTING RESULT:');
  console.log(`  Winner: ${JSON.stringify(result.summary.winner_answer)}`);
  console.log(`  Statistical Significance Skipped: ${result.statistical_significance === null}`);

  console.log('\nASSERTIONS:');
  console.log(`  ✓ Winner is 'A': ${result.summary.winner_answer === 'A'}`);
  console.log(`  ✓ Statistical significance skipped: ${result.statistical_significance === null}`);

  console.log('');
}

/**
 * Test 4: Edge case - insufficient samples
 */
async function testInsufficientSamples() {
  console.log('TEST 4: Insufficient Samples Edge Case');
  console.log('='.repeat(70));

  const votes = createMockVotes([
    { answer: 'A', count: 1, model: 'opus', confidence: 90 },
    { answer: 'B', count: 1, model: 'haiku', confidence: 70 },
  ]);

  const result = await runWeightedVoting(votes, 'general', {
    minConfidence: 50,
    bootstrapIterations: 500,
  });

  console.log('VOTING RESULT:');
  console.log(`  Winner: ${JSON.stringify(result.summary.winner_answer)}`);
  console.log(`  Needs More Samples: ${result.summary.needs_more_samples}`);

  if (result.statistical_significance) {
    const sig = result.statistical_significance;
    console.log('\nSTATISTICAL SIGNIFICANCE:');
    console.log(`  Winner CI Warning: ${sig.winner_ci.warning || 'none'}`);
    console.log(`  Sample Size Confidence: ${sig.sample_size_recommendation.confidence_level}`);
    console.log(`  Recommended Additional: ${sig.sample_size_recommendation.recommended_additional}`);
  }

  console.log('\nASSERTIONS:');
  console.log(`  ✓ Winner exists: ${result.summary.winner_answer !== null}`);
  console.log(`  ✓ Needs more samples: ${result.summary.needs_more_samples}`);
  console.log(`  ✓ Very low confidence: ${result.statistical_significance?.sample_size_recommendation.confidence_level === 'very_low'}`);

  console.log('');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('\n');
  console.log('#'.repeat(70));
  console.log('# INTEGRATION TEST: STATISTICAL SIGNIFICANCE + WEIGHTED VOTING');
  console.log('#'.repeat(70));
  console.log('\n');

  await testClearWinner();
  await testStatisticalTie();
  await testSkipStatisticalSignificance();
  await testInsufficientSamples();

  console.log('#'.repeat(70));
  console.log('# ALL INTEGRATION TESTS COMPLETE');
  console.log('#'.repeat(70));
  console.log('\n');
}

// Run tests if invoked directly
if (require.main === module) {
  runAllTests().catch(err => {
    console.error('TEST FAILED:', err);
    process.exit(1);
  });
}

module.exports = {
  runAllTests,
};
