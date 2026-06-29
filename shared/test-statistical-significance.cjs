/**
 * Test Suite for Statistical Significance Module
 *
 * Tests 5 scenarios:
 * 1. Clear winner (high consensus, narrow CI)
 * 2. Statistical tie (margin <5%, overlapping CIs)
 * 3. Uncertain result (wide CIs, needs more samples)
 * 4. Edge case: insufficient samples (<3 votes)
 * 5. Edge case: unanimous vote (all same answer)
 *
 * Run: node shared/test-statistical-significance.cjs
 */

const {
  analyzeStatisticalSignificance,
  formatStatisticalSignificance,
  bootstrapSample,
  bootstrapCI,
  detectStatisticalTie,
  recommendSampleSize,
} = require('./statistical-significance.cjs');

// ============================================================================
// TEST HELPERS
// ============================================================================

/**
 * Create mock votes with specified distribution
 *
 * @param {Array<Object>} answerDistribution - Array of {answer, count, avgWeight}
 * @returns {Array<Object>} Mock votes
 */
function createMockVotes(answerDistribution) {
  const votes = [];

  answerDistribution.forEach(({ answer, count, avgWeight }) => {
    for (let i = 0; i < count; i++) {
      // Add some variance around avgWeight (±10%)
      const variance = (Math.random() - 0.5) * 0.2;
      const weight = avgWeight * (1 + variance);

      votes.push({
        model: `model-${i}`,
        answer,
        weight: Math.max(0, Math.min(1, weight)), // Clamp to [0, 1]
        confidence: Math.random() * 0.5 + 0.5, // 0.5-1.0
      });
    }
  });

  return votes;
}

/**
 * Create mock voting result from votes
 *
 * @param {Array<Object>} votes - Votes with weight property
 * @returns {Object} Mock voting result
 */
function createMockVotingResult(votes) {
  // Group by answer
  const groups = {};

  votes.forEach(v => {
    const key = JSON.stringify(v.answer);
    if (!groups[key]) {
      groups[key] = {
        answer: v.answer,
        total_weight: 0,
        vote_count: 0,
        votes: [],
      };
    }
    groups[key].total_weight += v.weight;
    groups[key].vote_count += 1;
    groups[key].votes.push(v);
  });

  // Sort by total weight
  const sorted = Object.values(groups).sort((a, b) => b.total_weight - a.total_weight);

  const totalWeight = sorted.reduce((sum, g) => sum + g.total_weight, 0);

  const winner = sorted[0];
  const runnerUp = sorted[1] || null;

  return {
    status: 'success',
    winner: {
      answer: winner.answer,
      total_weight: winner.total_weight,
      vote_count: winner.vote_count,
      consensus_strength: winner.total_weight / totalWeight,
      votes: winner.votes,
    },
    runner_up: runnerUp ? {
      answer: runnerUp.answer,
      total_weight: runnerUp.total_weight,
      vote_count: runnerUp.vote_count,
      weight_difference: winner.total_weight - runnerUp.total_weight,
      votes: runnerUp.votes,
    } : null,
    all_groups: sorted,
  };
}

// ============================================================================
// UNIT TESTS
// ============================================================================

/**
 * Test 1: Bootstrap resampling produces correct distribution
 */
function testBootstrapSample() {
  console.log('TEST 1: Bootstrap Resampling');
  console.log('='.repeat(70));

  const data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

  // Resample 1000 times
  const samples = [];
  for (let i = 0; i < 1000; i++) {
    samples.push(bootstrapSample(data, 10));
  }

  // Check that samples have correct length
  const allCorrectLength = samples.every(s => s.length === 10);
  console.log(`  ✓ All samples have correct length: ${allCorrectLength}`);

  // Check that samples contain values from original data
  const allValidValues = samples.every(s =>
    s.every(v => data.includes(v))
  );
  console.log(`  ✓ All samples contain valid values: ${allValidValues}`);

  // Check that samples vary (not all identical)
  const uniqueSamples = new Set(samples.map(s => JSON.stringify(s))).size;
  console.log(`  ✓ Unique samples: ${uniqueSamples}/1000 (should be high)`);

  console.log('');
}

/**
 * Test 2: Bootstrap CI calculation
 */
function testBootstrapCI() {
  console.log('TEST 2: Bootstrap Confidence Interval');
  console.log('='.repeat(70));

  // Simple statistic: mean
  const mean = (data) => data.reduce((sum, x) => sum + x, 0) / data.length;

  // Test data (normal-ish distribution)
  const data = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];

  const result = bootstrapCI(data, mean, { iterations: 1000 });

  console.log(`  Original Estimate: ${result.estimate.toFixed(3)}`);
  console.log(`  95% CI: [${result.ci_lower.toFixed(3)}, ${result.ci_upper.toFixed(3)}]`);
  console.log(`  Std Error: ${result.std_error.toFixed(3)}`);
  console.log(`  Iterations: ${result.iterations}`);

  // Sanity checks
  const estimateInCI = result.estimate >= result.ci_lower && result.estimate <= result.ci_upper;
  console.log(`  ✓ Estimate within CI: ${estimateInCI}`);

  const ciPositiveWidth = result.ci_upper > result.ci_lower;
  console.log(`  ✓ CI has positive width: ${ciPositiveWidth}`);

  console.log('');
}

/**
 * Test 3: Insufficient samples edge case
 */
function testBootstrapCIInsufficientSamples() {
  console.log('TEST 3: Bootstrap CI - Insufficient Samples');
  console.log('='.repeat(70));

  const mean = (data) => data.reduce((sum, x) => sum + x, 0) / data.length;

  // Only 2 samples (below minimum of 3)
  const data = [5, 10];

  const result = bootstrapCI(data, mean, { iterations: 1000 });

  console.log(`  Estimate: ${result.estimate.toFixed(3)}`);
  console.log(`  Warning: ${result.warning}`);
  console.log(`  Message: ${result.message}`);
  console.log(`  ✓ Warning detected: ${result.warning === 'insufficient_samples'}`);

  console.log('');
}

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

/**
 * Scenario 1: Clear winner (high consensus, narrow CI)
 */
function testScenario1ClearWinner() {
  console.log('SCENARIO 1: Clear Winner (High Consensus)');
  console.log('='.repeat(70));

  // 12 votes for "A" with high weight, 3 votes for "B" with low weight
  const votes = createMockVotes([
    { answer: 'A', count: 12, avgWeight: 0.8 },
    { answer: 'B', count: 3, avgWeight: 0.4 },
  ]);

  const votingResult = createMockVotingResult(votes);

  const sigResult = analyzeStatisticalSignificance(votes, votingResult, { iterations: 1000 });

  console.log(formatStatisticalSignificance(sigResult));

  // Assertions
  console.log('ASSERTIONS:');
  console.log(`  ✓ Status success: ${sigResult.status === 'success'}`);
  console.log(`  ✓ No statistical tie: ${!sigResult.tie_analysis.is_tie}`);
  console.log(`  ✓ High consensus (>80%): ${sigResult.consensus_strength_ci.estimate > 0.8}`);
  console.log(`  ✓ No additional samples needed: ${!sigResult.sample_size_recommendation.needs_more_samples}`);

  console.log('');
}

/**
 * Scenario 2: Statistical tie (margin <5%, overlapping CIs)
 */
function testScenario2StatisticalTie() {
  console.log('SCENARIO 2: Statistical Tie');
  console.log('='.repeat(70));

  // 8 votes for "A" with weight 0.75, 7 votes for "B" with weight 0.73
  // Very close margin
  const votes = createMockVotes([
    { answer: 'A', count: 8, avgWeight: 0.75 },
    { answer: 'B', count: 7, avgWeight: 0.73 },
  ]);

  const votingResult = createMockVotingResult(votes);

  const sigResult = analyzeStatisticalSignificance(votes, votingResult, { iterations: 1000 });

  console.log(formatStatisticalSignificance(sigResult));

  // Assertions
  console.log('ASSERTIONS:');
  console.log(`  ✓ Status success: ${sigResult.status === 'success'}`);
  console.log(`  ✓ Statistical tie detected: ${sigResult.tie_analysis.is_tie}`);
  console.log(`  ✓ Margin <5%: ${sigResult.tie_analysis.margin_percent < 5}`);
  console.log(`  ✓ CI overlap >50%: ${sigResult.tie_analysis.ci_overlap_percent > 50}`);

  console.log('');
}

/**
 * Scenario 3: Uncertain result (wide CIs, needs more samples)
 */
function testScenario3Uncertain() {
  console.log('SCENARIO 3: Uncertain Result (Wide CIs)');
  console.log('='.repeat(70));

  // Only 4 votes total, high variance
  const votes = createMockVotes([
    { answer: 'A', count: 2, avgWeight: 0.9 },
    { answer: 'B', count: 2, avgWeight: 0.6 },
  ]);

  const votingResult = createMockVotingResult(votes);

  const sigResult = analyzeStatisticalSignificance(votes, votingResult, { iterations: 1000 });

  console.log(formatStatisticalSignificance(sigResult));

  // Assertions
  console.log('ASSERTIONS:');
  console.log(`  ✓ Status success: ${sigResult.status === 'success'}`);
  console.log(`  ✓ Low sample count: ${sigResult.metadata.total_votes < 5}`);
  console.log(`  ✓ Additional samples recommended: ${sigResult.sample_size_recommendation.needs_more_samples}`);
  console.log(`  ✓ Confidence level low/medium: ${sigResult.sample_size_recommendation.confidence_level !== 'high'}`);

  console.log('');
}

/**
 * Scenario 4: Edge case - insufficient samples (<3 votes)
 */
function testScenario4InsufficientSamples() {
  console.log('SCENARIO 4: Edge Case - Insufficient Samples');
  console.log('='.repeat(70));

  // Only 2 votes (below minimum)
  const votes = createMockVotes([
    { answer: 'A', count: 1, avgWeight: 0.8 },
    { answer: 'B', count: 1, avgWeight: 0.7 },
  ]);

  const votingResult = createMockVotingResult(votes);

  const sigResult = analyzeStatisticalSignificance(votes, votingResult, { iterations: 1000 });

  console.log(formatStatisticalSignificance(sigResult));

  // Assertions
  console.log('ASSERTIONS:');
  console.log(`  ✓ Status success: ${sigResult.status === 'success'}`);
  console.log(`  ✓ Winner CI warning: ${sigResult.winner_ci.warning === 'insufficient_samples'}`);
  console.log(`  ✓ Additional samples recommended: ${sigResult.sample_size_recommendation.needs_more_samples}`);
  console.log(`  ✓ Confidence level very low: ${sigResult.sample_size_recommendation.confidence_level === 'very_low'}`);

  console.log('');
}

/**
 * Scenario 5: Edge case - unanimous vote (all same answer)
 */
function testScenario5Unanimous() {
  console.log('SCENARIO 5: Edge Case - Unanimous Vote');
  console.log('='.repeat(70));

  // All 10 votes for "A"
  const votes = createMockVotes([
    { answer: 'A', count: 10, avgWeight: 0.85 },
  ]);

  const votingResult = createMockVotingResult(votes);

  const sigResult = analyzeStatisticalSignificance(votes, votingResult, { iterations: 1000 });

  console.log(formatStatisticalSignificance(sigResult));

  // Assertions
  console.log('ASSERTIONS:');
  console.log(`  ✓ Status success: ${sigResult.status === 'success'}`);
  console.log(`  ✓ No runner-up: ${sigResult.runner_up_ci === null}`);
  console.log(`  ✓ No statistical tie: ${!sigResult.tie_analysis.is_tie}`);
  console.log(`  ✓ Consensus strength 100%: ${sigResult.consensus_strength_ci.estimate === 1.0}`);

  console.log('');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

function runAllTests() {
  console.log('\n');
  console.log('#'.repeat(70));
  console.log('# STATISTICAL SIGNIFICANCE TEST SUITE');
  console.log('#'.repeat(70));
  console.log('\n');

  // Unit tests
  testBootstrapSample();
  testBootstrapCI();
  testBootstrapCIInsufficientSamples();

  // Integration tests (5 scenarios)
  testScenario1ClearWinner();
  testScenario2StatisticalTie();
  testScenario3Uncertain();
  testScenario4InsufficientSamples();
  testScenario5Unanimous();

  console.log('#'.repeat(70));
  console.log('# ALL TESTS COMPLETE');
  console.log('#'.repeat(70));
  console.log('\n');
}

// Run tests if invoked directly
if (require.main === module) {
  runAllTests();
}

module.exports = {
  createMockVotes,
  createMockVotingResult,
  runAllTests,
};
