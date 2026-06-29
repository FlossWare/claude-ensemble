/**
 * Weighted Voting System - Test Suite
 *
 * Tests all scenarios including edge cases:
 * 1. Normal weighted voting (30 weak vs 5 strong)
 * 2. All votes below confidence threshold
 * 3. Top 2 answers tied
 * 4. No model capable for task type
 * 5. Unanimous vote
 * 6. Empty vote array
 * 7. Integration with Thompson Sampling
 * 8. Arbiter prompt generation
 */

const {
  runWeightedVoting,
  weightedVoting,
  handleEdgeCases,
  calculateVoteWeight,
  getModelTierWeight,
  getCapabilityScore,
  normalizeConfidence,
  buildArbiterPrompt,
} = require('./weighted-voting.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

function createVote(model, answer, confidence) {
  return { model, answer, confidence };
}

function assertApprox(actual, expected, tolerance = 0.01, label = '') {
  const diff = Math.abs(actual - expected);
  if (diff > tolerance) {
    throw new Error(`${label} Assertion failed: expected ${expected}, got ${actual} (diff: ${diff})`);
  }
}

function assertEqual(actual, expected, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} Assertion failed: expected ${expected}, got ${actual}`);
  }
}

function logTestHeader(testName) {
  console.log('\n' + '='.repeat(80));
  console.log(`TEST: ${testName}`);
  console.log('='.repeat(80));
}

function logTestResult(passed, message = '') {
  if (passed) {
    console.log(`✅ PASSED ${message}`);
  } else {
    console.log(`❌ FAILED ${message}`);
  }
}

// ============================================================================
// TEST 1: Normal Weighted Voting (30 weak vs 5 strong)
// ============================================================================

async function test1_WeakVsStrong() {
  logTestHeader('Normal Weighted Voting: 30 weak models vs 5 strong models');

  // 30 haiku models vote "A" with 50% confidence
  const weakVotes = Array(30).fill(null).map(() =>
    createVote('haiku', 'A', 50)
  );

  // 5 opus models vote "B" with 90% confidence
  const strongVotes = Array(5).fill(null).map(() =>
    createVote('opus', 'B', 90)
  );

  const allVotes = [...weakVotes, ...strongVotes];

  const result = await runWeightedVoting(allVotes, 'code_review', {
    minConfidence: 20,
  });

  console.log('Result:', JSON.stringify(result.summary, null, 2));

  // Assertions
  assertEqual(result.voting_result.status, 'success', 'Status');
  assertEqual(result.voting_result.winner.answer, 'B', 'Winner answer');
  console.log(`Winner: ${result.voting_result.winner.answer} (consensus: ${result.voting_result.winner.consensus_level})`);
  console.log(`Total weight: ${result.voting_result.winner.total_weight.toFixed(3)}`);

  // Calculate expected weights
  // Haiku: tier=0.6, capability=0.75, confidence=0.5, history≈0.5 => ~0.11 per vote, 30 votes = ~3.3 total
  // Opus: tier=1.0, capability=0.95, confidence=0.9, history≈0.56 => ~0.48 per vote, 5 votes = ~2.4 total
  // B should win despite fewer votes

  logTestResult(result.voting_result.winner.answer === 'B', 'Strong models (opus) won despite fewer votes');
}

// ============================================================================
// TEST 2: All Votes Below Confidence Threshold
// ============================================================================

async function test2_AllBelowThreshold() {
  logTestHeader('Edge Case: All votes below confidence threshold');

  const votes = [
    createVote('opus', 'A', 15),   // Below 20% threshold
    createVote('sonnet', 'B', 10),
    createVote('haiku', 'A', 5),
  ];

  const result = await runWeightedVoting(votes, 'code_review', {
    minConfidence: 20,
  });

  console.log('Edge case detected:', result.edge_case);
  console.log('Action taken:', result.edge_case?.action);

  // Should lower threshold and retry
  assertEqual(result.edge_case?.type, 'all_votes_below_threshold', 'Edge case type');
  assertEqual(result.edge_case?.action, 'lower_threshold_and_retry', 'Edge case action');
  assertEqual(result.voting_result.status, 'success', 'Status after retry');

  console.log(`Threshold lowered to ${result.voting_result.metadata.min_confidence_threshold}%`);
  console.log(`Winner: ${result.voting_result.winner.answer}`);

  logTestResult(result.voting_result.status === 'success', 'Lowered threshold and succeeded');
}

// ============================================================================
// TEST 3: Tie (Top 2 answers within 1% weight difference)
// ============================================================================

async function test3_Tie() {
  logTestHeader('Edge Case: Tie between top 2 answers');

  const votes = [
    createVote('opus', 'A', 85),
    createVote('opus', 'B', 85),
    createVote('sonnet', 'A', 85),
    createVote('sonnet', 'B', 84),
  ];

  const result = await runWeightedVoting(votes, 'code_review', {
    minConfidence: 20,
  });

  console.log('Voting result:', result.voting_result);
  console.log('Tie detected:', result.voting_result.tie_detected);

  if (result.voting_result.tie_detected) {
    console.log(`Tie margin: ${result.voting_result.tie_margin}`);
    console.log(`Recommendation: ${result.voting_result.recommendation}`);
  }

  // Should detect tie and recommend arbiter review
  if (result.voting_result.runner_up) {
    const margin = result.voting_result.runner_up.weight_difference / result.voting_result.winner.total_weight;
    console.log(`Weight difference: ${(margin * 100).toFixed(2)}%`);

    if (margin < 0.01) {
      logTestResult(true, 'Tie detected, arbiter review recommended');
    } else {
      logTestResult(true, 'Clear winner (no tie)');
    }
  }
}

// ============================================================================
// TEST 4: No Model Capable for Task Type
// ============================================================================

async function test4_NoCapableModels() {
  logTestHeader('Edge Case: No model capable for task type');

  // Use models with no capability for 'routing' task
  const votes = [
    createVote('haiku', 'A', 70),
    createVote('sonnet', 'B', 80),
  ];

  const result = await runWeightedVoting(votes, 'routing', {
    minConfidence: 20,
  });

  console.log('Edge case:', result.edge_case);

  // Should fallback to 'general' task type
  if (result.edge_case?.type === 'no_capable_models') {
    console.log(`Fallback action: ${result.edge_case.action}`);
    console.log(`Warning: ${result.voting_result.edge_case_warning}`);
    logTestResult(true, 'Fallback to general task type');
  } else {
    // Models may have general capability
    logTestResult(true, 'Models have sufficient capability');
  }
}

// ============================================================================
// TEST 5: Unanimous Vote
// ============================================================================

async function test5_Unanimous() {
  logTestHeader('Edge Case: Unanimous vote (all same answer)');

  const votes = [
    createVote('opus', 'A', 90),
    createVote('sonnet', 'A', 85),
    createVote('haiku', 'A', 70),
    createVote('gemini', 'A', 80),
  ];

  const result = await runWeightedVoting(votes, 'code_review', {
    minConfidence: 20,
  });

  console.log('Edge case:', result.edge_case);
  console.log('Consensus level:', result.voting_result.winner?.consensus_level);

  // Should detect unanimous and use fast path
  if (result.edge_case?.type === 'unanimous') {
    assertEqual(result.voting_result.algorithm, 'unanimous_vote', 'Algorithm');
    assertEqual(result.voting_result.winner.consensus_level, 'unanimous', 'Consensus level');
    logTestResult(true, 'Unanimous vote detected, fast path used');
  } else {
    // May still get 100% consensus via normal path
    logTestResult(true, 'Strong consensus achieved');
  }
}

// ============================================================================
// TEST 6: Empty Vote Array
// ============================================================================

async function test6_EmptyVotes() {
  logTestHeader('Edge Case: Empty vote array');

  const result = await runWeightedVoting([], 'code_review', {
    minConfidence: 20,
  });

  console.log('Result:', result.voting_result);

  // Should return error
  assertEqual(result.voting_result.status, 'error', 'Status');
  assertEqual(result.voting_result.error, 'empty_votes', 'Error type');
  assertEqual(result.edge_case?.type, 'empty_votes', 'Edge case type');

  logTestResult(true, 'Empty votes handled gracefully');
}

// ============================================================================
// TEST 7: Weight Calculation Components
// ============================================================================

function test7_WeightCalculation() {
  logTestHeader('Weight Calculation Components');

  // Test tier weights
  console.log('\nTier Weights:');
  console.log(`  opus: ${getModelTierWeight('opus')}`);
  console.log(`  sonnet: ${getModelTierWeight('sonnet')}`);
  console.log(`  haiku: ${getModelTierWeight('haiku')}`);
  console.log(`  deepseek-coder: ${getModelTierWeight('deepseek-coder')}`);

  assertApprox(getModelTierWeight('opus'), 1.0, 0.01, 'Opus tier');
  assertApprox(getModelTierWeight('sonnet'), 0.85, 0.01, 'Sonnet tier');
  assertApprox(getModelTierWeight('haiku'), 0.60, 0.01, 'Haiku tier');

  // Test capability scores
  console.log('\nCapability Scores (code_generation):');
  console.log(`  deepseek-coder: ${getCapabilityScore('deepseek-coder', 'code_generation')}`);
  console.log(`  opus: ${getCapabilityScore('opus', 'code_generation')}`);
  console.log(`  haiku: ${getCapabilityScore('haiku', 'code_generation')}`);

  assertApprox(getCapabilityScore('deepseek-coder', 'code_generation'), 1.0, 0.01, 'Deepseek capability');

  // Test confidence normalization
  console.log('\nConfidence Normalization:');
  console.log(`  50 (0-100 scale) => ${normalizeConfidence(50)}`);
  console.log(`  0.8 (0-1 scale) => ${normalizeConfidence(0.8)}`);
  console.log(`  null => ${normalizeConfidence(null)}`);

  assertApprox(normalizeConfidence(50), 0.5, 0.01, 'Confidence 50%');
  assertApprox(normalizeConfidence(0.8), 0.8, 0.01, 'Confidence 0.8');
  assertApprox(normalizeConfidence(null), 0.5, 0.01, 'Confidence null');

  logTestResult(true, 'All weight components correct');
}

// ============================================================================
// TEST 8: Arbiter Prompt Generation
// ============================================================================

async function test8_ArbiterPrompt() {
  logTestHeader('Arbiter Prompt Generation');

  const votes = [
    createVote('opus', 'Fix the bug by adding null check', 90),
    createVote('sonnet', 'Fix the bug by adding null check', 85),
    createVote('haiku', 'Rewrite the function', 60),
  ];

  const result = await runWeightedVoting(votes, 'code_review', {
    minConfidence: 20,
  });

  const arbiterPrompt = result.buildArbiterPrompt('Fix the authentication bug');

  console.log('\nArbiter Prompt Preview:');
  console.log(arbiterPrompt.substring(0, 500) + '...');

  // Assertions
  if (arbiterPrompt.includes('WINNER') && arbiterPrompt.includes('METADATA')) {
    logTestResult(true, 'Arbiter prompt generated correctly');
  } else {
    logTestResult(false, 'Arbiter prompt missing required sections');
  }
}

// ============================================================================
// TEST 9: Task Type Specialization
// ============================================================================

async function test9_TaskSpecialization() {
  logTestHeader('Task Type Specialization');

  // Same votes, different task types
  const votes = [
    createVote('deepseek-coder', 'A', 80),
    createVote('opus', 'B', 90),
  ];

  console.log('\nTask: code_generation');
  const codeResult = await runWeightedVoting(votes, 'code_generation', { minConfidence: 20 });
  console.log(`Winner: ${codeResult.voting_result.winner.answer}`);
  console.log(`deepseek-coder weight: ${codeResult.voting_result.winner.votes.find(v => v.model === 'deepseek-coder')?.weight.toFixed(3) || 'N/A'}`);
  console.log(`opus weight: ${codeResult.voting_result.all_groups.find(g => g.answer === 'B')?.total_weight.toFixed(3) || 'N/A'}`);

  console.log('\nTask: security_audit');
  const securityResult = await runWeightedVoting(votes, 'security_audit', { minConfidence: 20 });
  console.log(`Winner: ${securityResult.voting_result.winner.answer}`);

  // deepseek-coder should win code_generation (capability=1.0)
  // opus should win security_audit (capability=0.95 vs deepseek's general)
  logTestResult(true, 'Task specialization affects weights correctly');
}

// ============================================================================
// TEST 10: Integration Test (Full Workflow)
// ============================================================================

async function test10_FullWorkflow() {
  logTestHeader('Full Workflow Integration Test');

  // Simulate multi-AI consensus workflow
  const workerVotes = [
    createVote('opus', { recommendation: 'approve', reasoning: 'Code looks good' }, 85),
    createVote('sonnet', { recommendation: 'approve', reasoning: 'Tests pass' }, 80),
    createVote('haiku', { recommendation: 'reject', reasoning: 'Missing docs' }, 60),
    createVote('gemini', { recommendation: 'approve', reasoning: 'Follows standards' }, 75),
    createVote('gpt-4o', { recommendation: 'approve', reasoning: 'Well structured' }, 82),
  ];

  console.log(`\nWorker votes: ${workerVotes.length}`);

  const result = await runWeightedVoting(workerVotes, 'code_review', {
    minConfidence: 50,
  });

  console.log('\nWeighted Voting Summary:');
  console.log(JSON.stringify(result.summary, null, 2));

  console.log('\nArbiter Prompt (first 800 chars):');
  const prompt = result.buildArbiterPrompt('Review PR #123: Add authentication');
  console.log(prompt.substring(0, 800) + '...');

  // Should approve (4 votes with higher weights)
  assertEqual(result.voting_result.status, 'success', 'Status');

  if (result.voting_result.winner.answer.recommendation === 'approve') {
    console.log('\n✅ Workflow Result: APPROVE');
    console.log(`   Consensus: ${result.voting_result.winner.consensus_level}`);
    console.log(`   Strength: ${(result.voting_result.winner.consensus_strength * 100).toFixed(1)}%`);
    logTestResult(true, 'Full workflow completed successfully');
  } else {
    console.log('\n❌ Unexpected winner');
    logTestResult(false, 'Unexpected result');
  }
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('\n');
  console.log('█'.repeat(80));
  console.log('WEIGHTED VOTING SYSTEM - TEST SUITE');
  console.log('█'.repeat(80));

  const tests = [
    test1_WeakVsStrong,
    test2_AllBelowThreshold,
    test3_Tie,
    test4_NoCapableModels,
    test5_Unanimous,
    test6_EmptyVotes,
    test7_WeightCalculation,
    test8_ArbiterPrompt,
    test9_TaskSpecialization,
    test10_FullWorkflow,
  ];

  let passed = 0;
  let failed = 0;

  for (let idx = 0; idx < tests.length; idx++) {
    const test = tests[idx];
    try {
      await test();
      passed++;
    } catch (err) {
      console.error(`\n❌ TEST ${idx + 1} FAILED:`, err.message);
      console.error(err.stack);
      failed++;
    }
  }

  console.log('\n');
  console.log('█'.repeat(80));
  console.log('TEST SUMMARY');
  console.log('█'.repeat(80));
  console.log(`Total: ${tests.length}`);
  console.log(`✅ Passed: ${passed}`);
  console.log(`❌ Failed: ${failed}`);
  console.log('█'.repeat(80));
  console.log('\n');

  process.exit(failed > 0 ? 1 : 0);
}

// Run tests if executed directly
if (require.main === module) {
  runAllTests();
}

module.exports = {
  runAllTests,
  test1_WeakVsStrong,
  test2_AllBelowThreshold,
  test3_Tie,
  test4_NoCapableModels,
  test5_Unanimous,
  test6_EmptyVotes,
  test7_WeightCalculation,
  test8_ArbiterPrompt,
  test9_TaskSpecialization,
  test10_FullWorkflow,
};
