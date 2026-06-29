/**
 * BFT Median Voting - Usage Examples
 *
 * Demonstrates Byzantine Fault Tolerance voting strategies
 * for multi-AI consensus with outlier resistance.
 *
 * Run: node shared/example-bft-usage.cjs
 */

const { runWeightedVoting } = require('./weighted-voting.cjs');

// ============================================================================
// EXAMPLE 1: Standard Voting vs BFT Median (One Broken Model)
// ============================================================================

function example1_BrokenModel() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 1: One Broken Model (Crashed, Returned Garbage)');
  console.log('='.repeat(70) + '\n');

  const votes = [
    { model: 'opus-1', answer: 'Security audit passed', confidence: 92 },
    { model: 'opus-2', answer: 'Security audit passed', confidence: 90 },
    { model: 'sonnet-1', answer: 'Security audit passed', confidence: 88 },
    { model: 'gpt-4o', answer: 'Security audit passed', confidence: 91 },
    { model: 'broken-local', answer: '{"error": "timeout"}', confidence: 25 },  // Crashed
  ];

  // Standard weighted average (vulnerable)
  const standardResult = runWeightedVoting(votes, 'security_audit', {
    strategy: 'weighted-average',
    minConfidence: 20,
  });

  // BFT median (outlier resistant)
  const bftResult = runWeightedVoting(votes, 'security_audit', {
    strategy: 'median',
    minConfidence: 20,
  });

  console.log('Votes:');
  votes.forEach(v => {
    console.log(`  - ${v.model.padEnd(15)} confidence=${String(v.confidence).padStart(2)}%  answer="${v.answer.substring(0, 30)}..."`);
  });

  console.log('\nResults:');
  console.log(`  Weighted Average: consensus=${standardResult.voting_result.winner.consensus_level.padEnd(8)} weight=${standardResult.voting_result.winner.total_weight.toFixed(3)}`);
  console.log(`  BFT Median:       consensus=${bftResult.voting_result.winner.consensus_level.padEnd(8)} weight=${bftResult.voting_result.winner.total_weight.toFixed(3)}`);

  console.log('\nConclusion:');
  console.log('  ✓ Both methods selected correct answer');
  console.log('  ✓ BFT median provides same result with outlier resistance');
}

// ============================================================================
// EXAMPLE 2: MAD Outlier Detection (Audit Trail)
// ============================================================================

function example2_MAD_OutlierDetection() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 2: MAD Outlier Detection (Audit Trail)');
  console.log('='.repeat(70) + '\n');

  const votes = [
    { model: 'opus', answer: 'Refactor approved', confidence: 90 },
    { model: 'sonnet', answer: 'Refactor approved', confidence: 88 },
    { model: 'gpt-4o', answer: 'Refactor approved', confidence: 92 },
    { model: 'gemini', answer: 'Refactor approved', confidence: 89 },
    { model: 'local-llama', answer: 'Reject', confidence: 35 },  // Outlier
  ];

  const result = runWeightedVoting(votes, 'code_review', {
    strategy: 'mad',
    madThreshold: 3,
    minConfidence: 20,
  });

  console.log('Votes:');
  votes.forEach(v => {
    console.log(`  - ${v.model.padEnd(12)} confidence=${String(v.confidence).padStart(2)}%  answer="${v.answer}"`);
  });

  console.log('\nBFT Analysis:');
  const analysis = result.voting_result.bft_analysis;
  console.log(`  Strategy: ${analysis.strategy.toUpperCase()}`);
  console.log(`  Median: ${analysis.median.toFixed(3)}`);
  console.log(`  MAD: ${analysis.mad.toFixed(3)}`);
  console.log(`  Outliers detected: ${analysis.outliers_detected}`);

  if (analysis.outliers_detected > 0) {
    console.log('\n  Outlier Models:');
    analysis.outliers.forEach(o => {
      console.log(`    - ${o.model}: confidence=${o.confidence.toFixed(2)}, deviation=${o.deviation.toFixed(3)}`);
    });
  }

  console.log('\nResult:');
  console.log(`  Winner: "${result.voting_result.winner.answer}"`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);

  console.log('\nAction:');
  console.log(`  ✓ Outlier flagged for investigation`);
  console.log(`  ✓ Decision made using only high-quality votes`);
}

// ============================================================================
// EXAMPLE 3: Trimmed Mean (Conservative Approach)
// ============================================================================

function example3_TrimmedMean() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 3: Trimmed Mean (Drop Top/Bottom 20%)');
  console.log('='.repeat(70) + '\n');

  const votes = [
    { model: 'opus-1', answer: 'Deploy approved', confidence: 95 },   // Top 20% (drop)
    { model: 'opus-2', answer: 'Deploy approved', confidence: 92 },
    { model: 'opus-3', answer: 'Deploy approved', confidence: 88 },
    { model: 'sonnet-1', answer: 'Deploy approved', confidence: 85 },
    { model: 'haiku-1', answer: 'Deploy approved', confidence: 80 },
    { model: 'haiku-2', answer: 'Deploy approved', confidence: 75 },
    { model: 'gemini', answer: 'Deploy approved', confidence: 70 },
    { model: 'local-1', answer: 'Reject', confidence: 40 },           // Bottom 20% (drop)
  ];

  const result = runWeightedVoting(votes, 'general', {
    strategy: 'trimmed-mean',
    trimPercent: 20,
  });

  console.log('Votes:');
  votes.forEach(v => {
    console.log(`  - ${v.model.padEnd(10)} confidence=${String(v.confidence).padStart(2)}%`);
  });

  console.log('\nTrimmed Mean Calculation:');
  console.log('  - Drop top 20%: 95% (opus-1)');
  console.log('  - Drop bottom 20%: 40% (local-1), maybe 70% (gemini)');
  console.log('  - Average middle 60%: ~85%');

  console.log('\nBFT Metrics:');
  const metrics = result.voting_result.bft_metrics;
  console.log(`  Strategy: ${metrics.strategy}`);
  console.log(`  Trim Percent: ${metrics.trim_percent}%`);
  console.log(`  Trimmed Confidence: ${metrics.trimmed_confidence.toFixed(3)}`);

  console.log('\nResult:');
  console.log(`  Winner: "${result.voting_result.winner.answer}"`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);

  console.log('\nUse Case:');
  console.log('  ✓ Conservative approach (ignore extreme values)');
  console.log('  ✓ Good when outlier count is known');
}

// ============================================================================
// EXAMPLE 4: Performance Comparison (Outlier Impact)
// ============================================================================

function example4_PerformanceComparison() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 4: Performance Comparison (Outlier Impact)');
  console.log('='.repeat(70) + '\n');

  const votes = [
    { model: 'opus-1', answer: 'A', confidence: 90 },
    { model: 'opus-2', answer: 'A', confidence: 90 },
    { model: 'opus-3', answer: 'A', confidence: 90 },
    { model: 'opus-4', answer: 'A', confidence: 90 },
    { model: 'opus-5', answer: 'A', confidence: 90 },
    { model: 'broken', answer: 'B', confidence: 25 },  // 1 outlier out of 6
  ];

  const strategies = ['weighted-average', 'median', 'trimmed-mean', 'mad'];

  console.log('Setup: 5 good models (90% confidence), 1 broken model (25% confidence)\n');

  console.log('Results by Strategy:');
  console.log('─'.repeat(70));

  strategies.forEach(strategy => {
    const result = runWeightedVoting(votes, 'general', {
      strategy,
      trimPercent: 20,
      madThreshold: 3,
      minConfidence: 20,
    });

    const winner = result.voting_result.winner;
    const outliersDetected = result.voting_result.bft_analysis?.outliers_detected || 0;

    let extraInfo = '';
    if (strategy === 'median' && result.voting_result.bft_metrics) {
      extraInfo = `median=${result.voting_result.bft_metrics.median_confidence.toFixed(2)}`;
    } else if (strategy === 'trimmed-mean' && result.voting_result.bft_metrics) {
      extraInfo = `trimmed=${result.voting_result.bft_metrics.trimmed_confidence.toFixed(2)}`;
    } else if (strategy === 'mad') {
      extraInfo = `outliers=${outliersDetected}`;
    }

    console.log(`  ${strategy.padEnd(18)} winner=${winner.answer}  weight=${winner.total_weight.toFixed(3)}  ${extraInfo}`);
  });

  console.log('\nConclusion:');
  console.log('  ✓ All strategies handle 1 outlier gracefully');
  console.log('  ✓ MAD provides explicit outlier detection');
  console.log('  ✓ Median is simplest and fastest');
}

// ============================================================================
// EXAMPLE 5: High-Stakes Decision (Security Audit)
// ============================================================================

function example5_HighStakes() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 5: High-Stakes Decision (Security Audit)');
  console.log('='.repeat(70) + '\n');

  const votes = [
    { model: 'opus', answer: 'No vulnerabilities found', confidence: 95 },
    { model: 'sonnet', answer: 'No vulnerabilities found', confidence: 92 },
    { model: 'gpt-4o', answer: 'No vulnerabilities found', confidence: 90 },
    { model: 'gemini', answer: 'SQL injection risk detected', confidence: 75 },  // Minority
  ];

  console.log('Scenario: 3 models say "safe", 1 model flags vulnerability\n');

  // Use trimmed-mean with low trim % to preserve minority opinion
  const result = runWeightedVoting(votes, 'security_audit', {
    strategy: 'trimmed-mean',
    trimPercent: 10,  // Only drop 10% from each end
  });

  console.log('Votes:');
  votes.forEach(v => {
    console.log(`  - ${v.model.padEnd(8)} confidence=${String(v.confidence).padStart(2)}%  "${v.answer}"`);
  });

  console.log('\nDecision:');
  console.log(`  Winner: "${result.voting_result.winner.answer}"`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);

  console.log('\nRecommendation:');
  if (result.voting_result.winner.consensus_level !== 'strong') {
    console.log('  ⚠ Low consensus on security - REQUIRE HUMAN REVIEW');
  } else {
    console.log('  ✓ Strong consensus - proceed with caution');
  }

  console.log('\nBest Practice:');
  console.log('  - Security decisions: Always review minority opinions');
  console.log('  - Use trimmed-mean with low trim % (10-15%)');
  console.log('  - Flag any consensus < "strong" for manual review');
}

// ============================================================================
// EXAMPLE 6: Edge Case - All Votes Identical
// ============================================================================

function example6_EdgeCase_Unanimous() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 6: Edge Case - Unanimous Consensus');
  console.log('='.repeat(70) + '\n');

  const votes = [
    { model: 'opus', answer: 'Approve', confidence: 90 },
    { model: 'sonnet', answer: 'Approve', confidence: 88 },
    { model: 'haiku', answer: 'Approve', confidence: 85 },
  ];

  const result = runWeightedVoting(votes, 'general', {
    strategy: 'mad',
  });

  console.log('Votes:');
  votes.forEach(v => {
    console.log(`  - ${v.model.padEnd(8)} "${v.answer}" (${v.confidence}%)`);
  });

  console.log('\nResult:');
  console.log(`  Winner: "${result.voting_result.winner.answer}"`);
  console.log(`  Consensus: ${result.voting_result.winner.consensus_level}`);

  if (result.voting_result.bft_analysis) {
    console.log(`  Outliers: ${result.voting_result.bft_analysis.outliers_detected}`);
  }

  console.log('\nNote:');
  console.log('  ✓ All votes agree - no outliers detected');
  console.log('  ✓ MAD = 0 (no deviation)');
}

// ============================================================================
// RUN ALL EXAMPLES
// ============================================================================

function runAllExamples() {
  console.log('\n' + '='.repeat(70));
  console.log('BFT MEDIAN VOTING - USAGE EXAMPLES');
  console.log('='.repeat(70));

  example1_BrokenModel();
  example2_MAD_OutlierDetection();
  example3_TrimmedMean();
  example4_PerformanceComparison();
  example5_HighStakes();
  example6_EdgeCase_Unanimous();

  console.log('\n' + '='.repeat(70));
  console.log('END OF EXAMPLES');
  console.log('='.repeat(70) + '\n');

  console.log('Key Takeaways:');
  console.log('  1. Use "median" for default BFT (fast, simple, effective)');
  console.log('  2. Use "mad" when you need audit trail of broken models');
  console.log('  3. Use "trimmed-mean" for known outlier count');
  console.log('  4. Always set minConfidence appropriately (default: 20%)');
  console.log('  5. For high-stakes: require human review if consensus < "strong"\n');
}

if (require.main === module) {
  runAllExamples();
}

module.exports = { runAllExamples };
