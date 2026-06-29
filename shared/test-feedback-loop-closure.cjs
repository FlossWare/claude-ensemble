#!/usr/bin/env node
/**
 * Tests for Human Feedback Loop Closure
 *
 * Tests the closeHumanFeedbackLoop function and related analytics.
 *
 * Scenarios:
 * 1. Weighted voting correct, human agrees
 * 2. Weighted voting incorrect, human corrects
 * 3. Model confidence overconfident (high conf but wrong)
 * 4. Model confidence underconfident (low conf but correct)
 * 5. Mixed model correctness (some correct, some wrong)
 *
 * Created: 2026-06-28
 */

const {
  storeInReviewQueue,
  updateReviewWithVerdict,
  closeHumanFeedbackLoop,
  getHumanAgreementRates,
  getCalibrationMetrics,
  pool,
} = require('./disagreement-detector.cjs');

// Test data generator
function generateTestVotes(scenario) {
  const scenarios = {
    // Scenario 1: All models agree, high confidence, correct
    'all_agree_correct': [
      { model: 'opus', answer: 'A', confidence: 0.95, strategy: 'opus' },
      { model: 'sonnet', answer: 'A', confidence: 0.92, strategy: 'sonnet' },
      { model: 'haiku', answer: 'A', confidence: 0.88, strategy: 'haiku' },
    ],

    // Scenario 2: Weighted voting wrong, human corrects
    'weighted_wrong': [
      { model: 'opus', answer: 'A', confidence: 0.75, strategy: 'opus' },
      { model: 'sonnet', answer: 'A', confidence: 0.70, strategy: 'sonnet' },
      { model: 'haiku', answer: 'B', confidence: 0.60, strategy: 'haiku' },  // Correct but low weight
    ],

    // Scenario 3: Overconfident wrong prediction
    'overconfident_wrong': [
      { model: 'opus', answer: 'A', confidence: 0.98, strategy: 'opus' },  // Very confident but wrong
      { model: 'sonnet', answer: 'A', confidence: 0.95, strategy: 'sonnet' },
      { model: 'haiku', answer: 'B', confidence: 0.30, strategy: 'haiku' },  // Correct but not confident
    ],

    // Scenario 4: Underconfident correct prediction
    'underconfident_correct': [
      { model: 'opus', answer: 'A', confidence: 0.55, strategy: 'opus' },  // Correct but low confidence
      { model: 'sonnet', answer: 'A', confidence: 0.60, strategy: 'sonnet' },
      { model: 'haiku', answer: 'B', confidence: 0.45, strategy: 'haiku' },
    ],

    // Scenario 5: Mixed correctness
    'mixed_correctness': [
      { model: 'opus', answer: 'A', confidence: 0.80, strategy: 'opus' },  // Correct
      { model: 'sonnet', answer: 'B', confidence: 0.65, strategy: 'sonnet' },  // Wrong
      { model: 'haiku', answer: 'A', confidence: 0.70, strategy: 'haiku' },  // Correct
      { model: 'gpt4o', answer: 'B', confidence: 0.55, strategy: 'gpt4o' },  // Wrong
    ],
  };

  return scenarios[scenario] || scenarios.all_agree_correct;
}

function generateWeightedWinner(votes) {
  // Simple weighted voting simulation (sum confidence scores per answer)
  const answerWeights = {};
  for (const vote of votes) {
    const answer = JSON.stringify(vote.answer);
    answerWeights[answer] = (answerWeights[answer] || 0) + vote.confidence;
  }

  const winner = Object.entries(answerWeights).sort((a, b) => b[1] - a[1])[0];
  return {
    answer: JSON.parse(winner[0]),
    confidence: winner[1],
  };
}

// Test runner
async function runTest(testName, scenario, humanAnswer, humanConfidence) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`TEST: ${testName}`);
  console.log(`${'='.repeat(80)}`);

  const client = await pool.connect();

  try {
    // 1. Create test workflow execution
    await client.query('BEGIN');

    const execResult = await client.query(`
      INSERT INTO workflow.executions
        (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome)
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING id
    `, [
      `test-${Date.now()}`,
      'feedback-loop-test',
      testName,
      scenario.length,
      1000,  // 1 second duration
      'success',
    ]);

    const execId = execResult.rows[0].id;
    console.log(`  Created workflow execution: ${execId}`);

    // 2. Simulate weighted voting
    const weightedWinner = generateWeightedWinner(scenario);
    console.log(`  Weighted winner: ${JSON.stringify(weightedWinner.answer)} (confidence: ${weightedWinner.confidence.toFixed(3)})`);

    // 3. Store in review queue
    const queueResult = await storeInReviewQueue(
      {
        needs_human_review: true,
        disagreement_score: 0.25,
        disagreement_level: 'moderate',
        num_votes: scenario.length,
        unique_answers: new Set(scenario.map(v => JSON.stringify(v.answer))).size,
        confidence_stats: { mean: 0.75, std_dev: 0.15 },
        priority: 7,
        review_threshold: 0.20,
      },
      {
        workflow_execution_id: execId,
        workflow_name: 'feedback-loop-test',
        task_description: testName,
        votes: scenario,
        weighted_winner: weightedWinner.answer,
        winner_confidence: weightedWinner.confidence,
        runner_up: null,
      }
    );

    console.log(`  Queued for review: ${queueResult.queue_id}`);

    // 4. Simulate human review
    const verdictResult = await updateReviewWithVerdict(queueResult.queue_id, {
      answer: humanAnswer,
      confidence: humanConfidence,
      reviewer: 'test-human',
      notes: `Test scenario: ${testName}`,
    });

    console.log(`  Human verdict: ${JSON.stringify(humanAnswer)} (confidence: ${humanConfidence})`);

    // 5. Close feedback loop
    const loopResult = await closeHumanFeedbackLoop(queueResult.queue_id);

    if (loopResult.status !== 'success') {
      console.error(`  ❌ FAILED: ${loopResult.message}`);
      await client.query('ROLLBACK');
      return false;
    }

    console.log(`  ✅ Feedback loop closed`);
    console.log(`     Weighted correct: ${loopResult.weighted_was_correct}`);
    console.log(`     Calibration error: ${loopResult.calibration_error.toFixed(3)}`);
    console.log(`     Strategy updates: ${loopResult.strategy_updates.length}`);

    // Show per-model results
    for (const update of loopResult.strategy_updates) {
      const symbol = update.was_correct ? '✓' : '✗';
      console.log(`     ${symbol} ${update.model}: reward=${update.reward}, α=${update.updated.alpha}, β=${update.updated.beta}, avg=${parseFloat(update.updated.avg_reward).toFixed(3)}`);
    }

    await client.query('COMMIT');
    return true;

  } catch (err) {
    await client.query('ROLLBACK');
    console.error(`  ❌ ERROR: ${err.message}`);
    return false;
  } finally {
    client.release();
  }
}

// Main test suite
async function main() {
  console.log('Human Feedback Loop Closure Tests');
  console.log('==================================\n');

  const tests = [
    {
      name: 'Scenario 1: All models correct, high confidence',
      scenario: generateTestVotes('all_agree_correct'),
      humanAnswer: 'A',
      humanConfidence: 0.95,
    },
    {
      name: 'Scenario 2: Weighted voting wrong, human corrects',
      scenario: generateTestVotes('weighted_wrong'),
      humanAnswer: 'B',  // Human picks B (minority correct answer)
      humanConfidence: 0.85,
    },
    {
      name: 'Scenario 3: Overconfident wrong prediction',
      scenario: generateTestVotes('overconfident_wrong'),
      humanAnswer: 'B',  // Models were very confident in A, but wrong
      humanConfidence: 0.90,
    },
    {
      name: 'Scenario 4: Underconfident correct prediction',
      scenario: generateTestVotes('underconfident_correct'),
      humanAnswer: 'A',  // Models were correct but not confident
      humanConfidence: 0.88,
    },
    {
      name: 'Scenario 5: Mixed model correctness',
      scenario: generateTestVotes('mixed_correctness'),
      humanAnswer: 'A',  // Opus and Haiku correct, Sonnet and GPT-4o wrong
      humanConfidence: 0.92,
    },
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    const result = await runTest(test.name, test.scenario, test.humanAnswer, test.humanConfidence);
    if (result) {
      passed++;
    } else {
      failed++;
    }
  }

  // Analytics tests
  console.log(`\n${'='.repeat(80)}`);
  console.log('ANALYTICS TESTS');
  console.log(`${'='.repeat(80)}`);

  // Test human agreement rates
  console.log('\n[Human Agreement Rates]');
  const agreementRates = await getHumanAgreementRates({ min_reviews: 1 });
  if (agreementRates.length > 0) {
    console.log('  ✅ Human agreement rates retrieved');
    for (const rate of agreementRates) {
      console.log(`     ${rate.model}: ${(rate.agreement_rate * 100).toFixed(1)}% (${rate.correct_count}/${rate.total_reviews})`);
    }
  } else {
    console.log('  ⚠ No agreement rates found (may need more reviews)');
  }

  // Test calibration metrics
  console.log('\n[Calibration Metrics]');
  const calibration = await getCalibrationMetrics({ min_reviews: 1 });
  if (calibration) {
    console.log('  ✅ Calibration metrics retrieved');
    console.log(`     Total reviews: ${calibration.total_reviews}`);
    console.log(`     Accuracy: ${(calibration.accuracy * 100).toFixed(1)}%`);
    console.log(`     Avg calibration error: ${calibration.avg_calibration_error.toFixed(3)}`);
    console.log(`     Avg confidence when correct: ${calibration.avg_confidence_when_correct.toFixed(3)}`);
    console.log(`     Avg confidence when wrong: ${calibration.avg_confidence_when_wrong.toFixed(3)}`);
  } else {
    console.log('  ⚠ No calibration metrics found (may need more reviews)');
  }

  // Summary
  console.log(`\n${'='.repeat(80)}`);
  console.log('TEST SUMMARY');
  console.log(`${'='.repeat(80)}`);
  console.log(`  Passed: ${passed}/${tests.length}`);
  console.log(`  Failed: ${failed}/${tests.length}`);
  console.log(`  Success rate: ${((passed / tests.length) * 100).toFixed(1)}%`);

  await pool.end();

  process.exit(failed > 0 ? 1 : 0);
}

// Run tests
main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
