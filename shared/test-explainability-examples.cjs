#!/usr/bin/env node

/**
 * Explainability Reporter - Example Scenarios
 *
 * Demonstrates explainability reports for 3 scenarios:
 * 1. Strong consensus (90% agreement)
 * 2. Controversial decision (close vote, 52% vs 48%)
 * 3. Outlier filtering (MAD excluded 2 faulty models)
 *
 * Created: 2026-06-28
 */

const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');
const fs = require('fs');
const path = require('path');

// ============================================================================
// SCENARIO 1: Strong Consensus
// ============================================================================

async function scenario1_strongConsensus() {
  console.log('\n=== SCENARIO 1: Strong Consensus ===\n');

  const votes = [
    { model: 'opus', answer: 'LGTM - code looks good', confidence: 0.92 },
    { model: 'sonnet', answer: 'LGTM - code looks good', confidence: 0.88 },
    { model: 'haiku', answer: 'LGTM - code looks good', confidence: 0.75 },
    { model: 'fable', answer: 'LGTM - code looks good', confidence: 0.90 },
    { model: 'gpt-4o', answer: 'LGTM - code looks good', confidence: 0.85 },
    { model: 'gemini', answer: 'LGTM - code looks good', confidence: 0.83 },
    { model: 'deepseek-coder', answer: 'Minor issues - fix formatting', confidence: 0.65 },
  ];

  const result = await runWeightedVotingWithExplain(votes, 'code_review', {
    explain: true,
    explainFormat: 'markdown',
    explainOutputPath: '/tmp/explainability-scenario1-strong-consensus.md',
  });

  console.log('Winner:', result.summary.winner_answer);
  console.log('Consensus:', result.summary.consensus_level);
  console.log('Report written to:', result.explainability.file_path);
  console.log('\n--- Markdown Report ---\n');
  console.log(result.explainability.markdown);
}

// ============================================================================
// SCENARIO 2: Controversial Decision (Close Vote)
// ============================================================================

async function scenario2_controversialDecision() {
  console.log('\n=== SCENARIO 2: Controversial Decision ===\n');

  const votes = [
    { model: 'opus', answer: 'Approve merge', confidence: 0.78 },
    { model: 'sonnet', answer: 'Approve merge', confidence: 0.72 },
    { model: 'haiku', answer: 'Approve merge', confidence: 0.65 },
    { model: 'fable', answer: 'Reject - security risk', confidence: 0.85 },
    { model: 'gpt-4o', answer: 'Reject - security risk', confidence: 0.82 },
    { model: 'gemini', answer: 'Reject - security risk', confidence: 0.80 },
    { model: 'deepseek-coder', answer: 'Approve merge', confidence: 0.60 },
  ];

  const result = await runWeightedVotingWithExplain(votes, 'security_audit', {
    explain: true,
    explainFormat: 'markdown',
    explainOutputPath: '/tmp/explainability-scenario2-controversial.md',
  });

  console.log('Winner:', result.summary.winner_answer);
  console.log('Consensus:', result.summary.consensus_level);
  console.log('Report written to:', result.explainability.file_path);
  console.log('\n--- Markdown Report ---\n');
  console.log(result.explainability.markdown);
}

// ============================================================================
// SCENARIO 3: Outlier Filtering (MAD)
// ============================================================================

async function scenario3_outlierFiltering() {
  console.log('\n=== SCENARIO 3: Outlier Filtering (BFT-MAD) ===\n');

  const votes = [
    { model: 'opus', answer: 'Bug confirmed', confidence: 0.85 },
    { model: 'sonnet', answer: 'Bug confirmed', confidence: 0.88 },
    { model: 'haiku', answer: 'Bug confirmed', confidence: 0.82 },
    { model: 'fable', answer: 'Bug confirmed', confidence: 0.90 },
    { model: 'gpt-4o', answer: 'Bug confirmed', confidence: 0.83 },
    { model: 'gemini', answer: 'Bug confirmed', confidence: 0.87 },
    // Two broken models returning garbage
    { model: 'broken-model-1', answer: 'No issue found', confidence: 0.15 },
    { model: 'broken-model-2', answer: 'Cannot determine', confidence: 0.05 },
  ];

  const result = await runWeightedVotingWithExplain(votes, 'bug_detection', {
    explain: true,
    explainFormat: 'markdown',
    explainOutputPath: '/tmp/explainability-scenario3-outliers.md',
    strategy: 'mad',  // Enable BFT outlier filtering
    madThreshold: 3,
  });

  console.log('Winner:', result.summary.winner_answer);
  console.log('Consensus:', result.summary.consensus_level);
  console.log('Outliers detected:', result.voting_result.bft_analysis?.outliers_detected || 0);
  console.log('Report written to:', result.explainability.file_path);
  console.log('\n--- Markdown Report ---\n');
  console.log(result.explainability.markdown);
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  try {
    await scenario1_strongConsensus();
    console.log('\n' + '='.repeat(80) + '\n');

    await scenario2_controversialDecision();
    console.log('\n' + '='.repeat(80) + '\n');

    await scenario3_outlierFiltering();
    console.log('\n' + '='.repeat(80) + '\n');

    console.log('✓ All example scenarios completed');
    console.log('✓ Reports written to /tmp/explainability-scenario*.md');
  } catch (err) {
    console.error('ERROR:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}

module.exports = {
  scenario1_strongConsensus,
  scenario2_controversialDecision,
  scenario3_outlierFiltering,
};
