#!/usr/bin/env node
/**
 * Test for race condition fix in disagreement-detector.cjs
 *
 * Simulates concurrent workers analyzing the same workflow
 * and verifies that advisory locks prevent race conditions.
 *
 * Expected behavior:
 * - All concurrent inserts succeed (no errors)
 * - Final priority = HIGHEST priority from all workers
 * - Final disagreement_score = HIGHEST score from all workers
 * - No lost updates (last writer doesn't overwrite higher priority)
 */

const { Pool } = require('pg');
const {
  analyzeDisagreement,
  storeInReviewQueue,
  hashCode,
} = require('../shared/disagreement-detector.cjs');

// PostgreSQL connection
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});

/**
 * Clean up test data
 */
async function cleanup(workflowId) {
  const client = await pool.connect();
  try {
    await client.query(
      `DELETE FROM workflow.human_review_queue WHERE workflow_execution_id = $1`,
      [workflowId]
    );
    console.log('[cleanup] Deleted test data');
  } finally {
    client.release();
  }
}

/**
 * Simulate a worker analyzing the same workflow
 */
async function simulateWorker(workerId, workflowId, priority, disagreementScore) {
  // Create fake votes with high disagreement to ensure needs_human_review = true
  const votes = [
    { model: 'opus', answer: 'A', confidence: 90 },
    { model: 'sonnet', answer: 'B', confidence: 20 },
    { model: 'haiku', answer: 'A', confidence: 85 },
  ];

  // Analyze disagreement (force review by setting low threshold)
  const analysis = analyzeDisagreement(votes, { review_threshold: 0.01 });

  // Override priority and score for testing
  analysis.priority = priority;
  analysis.disagreement_score = disagreementScore;
  analysis.needs_human_review = true; // Force review

  console.log(`[worker-${workerId}] Priority: ${priority}, CV: ${disagreementScore.toFixed(3)}`);

  // Store in queue (this is where race condition could occur)
  const result = await storeInReviewQueue(analysis, {
    workflow_execution_id: workflowId,
    workflow_name: 'race-condition-test',
    task_description: 'Test concurrent updates',
    votes: votes,
    weighted_winner: { answer: 'A' },
    winner_confidence: 0.85,
    runner_up: { answer: 'B' },
  });

  return result;
}

/**
 * Run concurrent worker simulation
 */
async function testConcurrentUpdates() {
  const workflowId = `test-race-${Date.now()}`;

  console.log('\n=== Race Condition Test ===');
  console.log(`Workflow ID: ${workflowId}`);
  console.log(`Hash Code: ${hashCode(workflowId)}\n`);

  try {
    // Simulate 5 workers analyzing same workflow concurrently
    // Worker priorities: 10, 7, 9, 5, 8 (worker-1 has highest)
    // Disagreement scores: 0.50, 0.30, 0.45, 0.20, 0.35 (worker-1 has highest)
    const workers = [
      { id: 1, priority: 10, score: 0.50 },
      { id: 2, priority: 7, score: 0.30 },
      { id: 3, priority: 9, score: 0.45 },
      { id: 4, priority: 5, score: 0.20 },
      { id: 5, priority: 8, score: 0.35 },
    ];

    console.log('Starting 5 concurrent workers...\n');

    // Launch all workers concurrently
    const results = await Promise.all(
      workers.map(w => simulateWorker(w.id, workflowId, w.priority, w.score))
    );

    console.log('\n=== Results ===');
    results.forEach((r, i) => {
      console.log(`Worker ${i + 1}: ${r.status} (Queue ID: ${r.queue_id || 'N/A'})`);
    });

    // Verify final state
    const client = await pool.connect();
    try {
      const final = await client.query(
        `SELECT priority, disagreement_score FROM workflow.human_review_queue WHERE workflow_execution_id = $1`,
        [workflowId]
      );

      if (final.rows.length === 0) {
        console.error('\n❌ FAIL: No row found in queue');
        return false;
      }

      const { priority, disagreement_score } = final.rows[0];

      // Convert to number if needed
      const scoreNum = parseFloat(disagreement_score);

      console.log('\n=== Final State ===');
      console.log(`Priority: ${priority}`);
      console.log(`Disagreement Score: ${scoreNum}`);

      // Expected: GREATEST() should preserve highest values
      const expectedPriority = 10; // Worker 1 has highest priority
      const expectedScore = 0.50; // Worker 1 has highest score

      const priorityCorrect = priority === expectedPriority;
      const scoreCorrect = Math.abs(scoreNum - expectedScore) < 0.01;

      console.log('\n=== Validation ===');
      console.log(`Priority correct: ${priorityCorrect} (expected ${expectedPriority}, got ${priority})`);
      console.log(`Score correct: ${scoreCorrect} (expected ${expectedScore.toFixed(2)}, got ${scoreNum.toFixed(2)})`);

      if (priorityCorrect && scoreCorrect) {
        console.log('\n✅ PASS: Race condition prevented, highest values preserved');
        return true;
      } else {
        console.log('\n❌ FAIL: Race condition detected, values were overwritten');
        return false;
      }

    } finally {
      client.release();
    }

  } catch (err) {
    console.error('\n❌ ERROR:', err.message);
    console.error(err.stack);
    return false;
  } finally {
    // Cleanup
    await cleanup(workflowId);
  }
}

/**
 * Test hashCode consistency
 */
function testHashCode() {
  console.log('\n=== Hash Code Tests ===');

  const testStrings = [
    'workflow-123',
    'workflow-456',
    'workflow-123', // Duplicate
    '',
    'a',
    'very-long-workflow-execution-id-with-lots-of-characters-1234567890',
  ];

  testStrings.forEach(s => {
    const hash = hashCode(s);
    const isPositive = hash >= 0;
    const isInt32 = Number.isInteger(hash) && hash <= 2147483647;
    console.log(`"${s}" → ${hash} (${isPositive && isInt32 ? '✅' : '❌'})`);
  });

  // Test consistency
  const h1 = hashCode('workflow-123');
  const h2 = hashCode('workflow-123');
  const consistent = h1 === h2;

  console.log(`\nConsistency test: ${consistent ? '✅' : '❌'} (${h1} === ${h2})`);

  return consistent;
}

/**
 * Main test runner
 */
async function main() {
  console.log('Starting disagreement-detector race condition tests...\n');

  // Test 1: Hash code consistency
  const hashOk = testHashCode();

  // Test 2: Concurrent updates
  const raceOk = await testConcurrentUpdates();

  // Summary
  console.log('\n=== Test Summary ===');
  console.log(`Hash Code: ${hashOk ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Race Condition: ${raceOk ? '✅ PASS' : '❌ FAIL'}`);

  const allPassed = hashOk && raceOk;
  console.log(`\nOverall: ${allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);

  await pool.end();
  process.exit(allPassed ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
