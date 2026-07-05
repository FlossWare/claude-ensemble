#!/usr/bin/env node

/**
 * Test script for disagreement-driven active learning
 *
 * Tests:
 * 1. Disagreement analysis (coefficient of variation)
 * 2. Human review queue storage
 * 3. Weighted voting integration
 *
 * Usage: node test-disagreement-detection.js
 */

const { analyzeDisagreement, detectAndQueue, fetchPendingReviews, updateReviewWithVerdict } = require('../shared/disagreement-detector.cjs');
const { runWeightedVotingWithDisagreementDetection } = require('../shared/weighted-voting.cjs');

async function testDisagreementAnalysis() {
  console.log('\n=== Test 1: Disagreement Analysis ===\n');

  // Low disagreement (models agree)
  const lowDisagreementVotes = [
    { model: 'opus', answer: 'PostgreSQL', confidence: 90 },
    { model: 'sonnet', answer: 'PostgreSQL', confidence: 88 },
    { model: 'haiku', answer: 'PostgreSQL', confidence: 85 },
    { model: 'fable', answer: 'PostgreSQL', confidence: 92 },
  ];

  const lowAnalysis = analyzeDisagreement(lowDisagreementVotes);
  console.log('Low disagreement (models agree):');
  console.log(`  CV: ${lowAnalysis.disagreement_score.toFixed(3)}`);
  console.log(`  Level: ${lowAnalysis.disagreement_level}`);
  console.log(`  Needs review: ${lowAnalysis.needs_human_review}`);
  console.log(`  Priority: ${lowAnalysis.priority}`);
  console.log('');

  // High disagreement (models split)
  const highDisagreementVotes = [
    { model: 'opus', answer: 'PostgreSQL', confidence: 92 },
    { model: 'sonnet', answer: 'PostgreSQL', confidence: 88 },
    { model: 'haiku', answer: 'MongoDB', confidence: 45 },
    { model: 'fable', answer: 'Redis', confidence: 52 },
    { model: 'gpt-4o', answer: 'PostgreSQL', confidence: 85 },
    { model: 'gemini', answer: 'MongoDB', confidence: 48 },
  ];

  const highAnalysis = analyzeDisagreement(highDisagreementVotes);
  console.log('High disagreement (models split):');
  console.log(`  CV: ${highAnalysis.disagreement_score.toFixed(3)}`);
  console.log(`  Level: ${highAnalysis.disagreement_level}`);
  console.log(`  Needs review: ${highAnalysis.needs_human_review}`);
  console.log(`  Priority: ${highAnalysis.priority}`);
  console.log('');

  return { lowAnalysis, highAnalysis };
}

async function testQueueStorage() {
  console.log('\n=== Test 2: Queue Storage ===\n');

  const votes = [
    { model: 'opus', answer: 'PostgreSQL', confidence: 92 },
    { model: 'sonnet', answer: 'PostgreSQL', confidence: 88 },
    { model: 'haiku', answer: 'MongoDB', confidence: 45 },
    { model: 'fable', answer: 'Redis', confidence: 52 },
  ];

  const analysis = analyzeDisagreement(votes);

  const context = {
    workflow_execution_id: `test_${Date.now()}`,
    workflow_name: 'test-disagreement',
    task_description: 'What database should we use for high-throughput writes?',
    votes: votes,
    weighted_winner: { answer: 'PostgreSQL' },
    winner_confidence: 0.85,
    runner_up: { answer: 'MongoDB' },
  };

  const result = await detectAndQueue(votes, { winner: { answer: 'PostgreSQL', total_weight: 2.5 }, runner_up: { answer: 'MongoDB', total_weight: 0.9 } }, context, { review_threshold: 0.20 });

  console.log('Queue storage result:');
  console.log(`  Status: ${result.queue_result?.status || 'N/A'}`);
  console.log(`  Queue ID: ${result.queue_result?.queue_id || 'N/A'}`);
  console.log(`  Disagreement: ${result.disagreement_score?.toFixed(3) || 'N/A'}`);
  console.log(`  Level: ${result.disagreement_level || 'N/A'}`);
  console.log('');

  return result;
}

async function testFetchPendingReviews() {
  console.log('\n=== Test 3: Fetch Pending Reviews ===\n');

  const reviews = await fetchPendingReviews({ limit: 5, order_by: 'disagreement_score' });

  console.log(`Found ${reviews.length} pending reviews:\n`);

  reviews.forEach((r, i) => {
    console.log(`${i + 1}. ID ${r.id}: ${r.task_description.substring(0, 60)}...`);
    console.log(`   Disagreement: ${parseFloat(r.disagreement_score).toFixed(3)} (${r.disagreement_level})`);
    console.log(`   Votes: ${r.num_votes}, Unique answers: ${r.unique_answers}`);
    console.log(`   Priority: ${r.priority}, Created: ${r.created_at}`);
    console.log('');
  });

  return reviews;
}

async function testWeightedVotingIntegration() {
  console.log('\n=== Test 4: Weighted Voting Integration ===\n');

  const votes = [
    { model: 'opus', answer: 'Option A', confidence: 85 },
    { model: 'sonnet', answer: 'Option A', confidence: 80 },
    { model: 'haiku', answer: 'Option B', confidence: 45 },
    { model: 'fable', answer: 'Option C', confidence: 50 },
    { model: 'gpt-4o', answer: 'Option A', confidence: 88 },
    { model: 'gemini', answer: 'Option B', confidence: 42 },
  ];

  const result = await runWeightedVotingWithDisagreementDetection(votes, 'architecture_review', {
    minConfidence: 20,
    reviewThreshold: 0.20,
    context: {
      workflow_execution_id: `test_weighted_${Date.now()}`,
      workflow_name: 'test-weighted-voting',
      task_description: 'Which architecture pattern should we use?',
    },
  });

  console.log('Weighted voting result:');
  console.log(`  Winner: ${JSON.stringify(result.voting_result.winner?.answer)}`);
  console.log(`  Consensus level: ${result.voting_result.winner?.consensus_level}`);
  console.log(`  Total weight: ${result.voting_result.winner?.total_weight?.toFixed(3)}`);
  console.log('');

  console.log('Disagreement analysis:');
  console.log(`  CV: ${result.disagreement?.disagreement_score?.toFixed(3)}`);
  console.log(`  Level: ${result.disagreement?.disagreement_level}`);
  console.log(`  Needs review: ${result.needs_human_review}`);
  console.log('');

  if (result.human_review_queue?.status === 'queued') {
    console.log('Human review queue:');
    console.log(`  Queue ID: ${result.human_review_queue.queue_id}`);
    console.log(`  Priority: ${result.human_review_queue.priority}`);
  }
  console.log('');

  return result;
}

async function testUpdateVerdict() {
  console.log('\n=== Test 5: Update with Human Verdict ===\n');

  // Fetch first pending review
  const reviews = await fetchPendingReviews({ limit: 1 });

  if (reviews.length === 0) {
    console.log('No pending reviews to update');
    return null;
  }

  const review = reviews[0];
  console.log(`Updating review ${review.id}: ${review.task_description.substring(0, 60)}...`);
  console.log(`  Weighted winner: ${JSON.stringify(review.weighted_winner)}`);
  console.log('');

  const updateResult = await updateReviewWithVerdict(review.id, {
    answer: review.weighted_winner,  // Accept weighted winner
    confidence: 90,
    reviewer: 'test-script',
    notes: 'Automated test: weighted voting result approved',
  });

  console.log('Update result:');
  console.log(`  Status: ${updateResult.status}`);
  console.log(`  Message: ${updateResult.message}`);
  console.log('');

  return updateResult;
}

async function runAllTests() {
  console.log('='.repeat(80));
  console.log('DISAGREEMENT-DRIVEN ACTIVE LEARNING - TEST SUITE');
  console.log('='.repeat(80));

  try {
    await testDisagreementAnalysis();
    await testQueueStorage();
    await testFetchPendingReviews();
    await testWeightedVotingIntegration();
    await testUpdateVerdict();

    console.log('\n' + '='.repeat(80));
    console.log('ALL TESTS COMPLETED SUCCESSFULLY');
    console.log('='.repeat(80));
    console.log('\nVerify in database:');
    console.log('  PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning psql -U sfloess');
    console.log('  SELECT * FROM workflow.human_review_queue ORDER BY created_at DESC LIMIT 5;');
    console.log('');

    process.exit(0);

  } catch (err) {
    console.error('\n' + '='.repeat(80));
    console.error('TEST FAILED');
    console.error('='.repeat(80));
    console.error('Error:', err.message);
    console.error('Stack:', err.stack);
    process.exit(1);
  }
}

// Run tests
runAllTests();
