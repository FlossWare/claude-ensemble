#!/usr/bin/env node
/**
 * Human Review CLI Tool
 *
 * Interactive command-line interface for reviewing disagreement cases
 * and closing the feedback loop.
 *
 * Usage:
 *   node scripts/human-review-cli.mjs
 *   node scripts/human-review-cli.mjs --auto-close  # Auto-close after review
 *
 * Created: 2026-06-28
 */

import { createInterface } from 'readline';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const {
  fetchPendingReviews,
  updateReviewWithVerdict,
  closeHumanFeedbackLoop,
  getHumanAgreementRates,
  getCalibrationMetrics,
  pool,
} = require('../shared/disagreement-detector.cjs');

// CLI colors
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function colorize(text, color) {
  return `${colors[color]}${text}${colors.reset}`;
}

// Create readline interface
const rl = createInterface({
  input: process.stdin,
  output: process.stdout,
});

function ask(question) {
  return new Promise((resolve) => {
    rl.question(question, resolve);
  });
}

async function displayReview(review, index, total) {
  console.log('\n' + '='.repeat(80));
  console.log(colorize(`Review ${index + 1}/${total} (ID: ${review.id})`, 'bright'));
  console.log('='.repeat(80));
  console.log();
  console.log(colorize('Task:', 'cyan'), review.task_description);
  console.log(colorize('Workflow:', 'dim'), review.workflow_name || 'N/A');
  console.log(colorize('Disagreement:', 'yellow'), `${review.disagreement_score.toFixed(3)} (${review.disagreement_level})`);
  console.log(colorize('Priority:', 'red'), review.priority);
  console.log(colorize('Created:', 'dim'), new Date(review.created_at).toLocaleString());
  console.log();

  // Display votes
  console.log(colorize('Votes:', 'bright'));
  const votes = review.votes_json;
  for (const vote of votes) {
    const conf = (vote.confidence * 100).toFixed(1);
    const answer = typeof vote.answer === 'string' ? vote.answer : JSON.stringify(vote.answer);
    console.log(`  ${colorize(vote.model.padEnd(12), 'cyan')} → ${answer.padEnd(30)} (${conf}% confidence)`);
  }

  console.log();
  console.log(colorize('Weighted Winner:', 'green'), JSON.stringify(review.weighted_winner));
  console.log(colorize('Winner Confidence:', 'green'), review.winner_confidence?.toFixed(3) || 'N/A');

  if (review.runner_up) {
    console.log(colorize('Runner-up:', 'yellow'), JSON.stringify(review.runner_up));
  }

  console.log();
}

async function collectVerdict(review) {
  console.log(colorize('Enter your verdict:', 'bright'));

  // Extract unique answers
  const votes = review.votes_json;
  const uniqueAnswers = [...new Set(votes.map(v => JSON.stringify(v.answer)))];

  console.log('\nOptions:');
  uniqueAnswers.forEach((ans, idx) => {
    console.log(`  ${idx + 1}) ${ans}`);
  });
  console.log(`  ${uniqueAnswers.length + 1}) Custom answer`);
  console.log(`  s) Skip this review`);
  console.log(`  q) Quit`);

  const choice = await ask('\nYour choice: ');

  if (choice.toLowerCase() === 'q') {
    return null;
  }

  if (choice.toLowerCase() === 's') {
    return { skip: true };
  }

  let answer;
  const choiceNum = parseInt(choice);

  if (choiceNum >= 1 && choiceNum <= uniqueAnswers.length) {
    answer = JSON.parse(uniqueAnswers[choiceNum - 1]);
  } else if (choiceNum === uniqueAnswers.length + 1) {
    const custom = await ask('Enter custom answer: ');
    answer = custom;
  } else {
    console.log(colorize('Invalid choice, skipping...', 'red'));
    return { skip: true };
  }

  const confidenceStr = await ask('Your confidence (0-100): ');
  const confidence = parseFloat(confidenceStr) / 100;

  if (isNaN(confidence) || confidence < 0 || confidence > 1) {
    console.log(colorize('Invalid confidence, defaulting to 0.75', 'yellow'));
  }

  const notes = await ask('Notes (optional): ');

  return {
    answer,
    confidence: !isNaN(confidence) && confidence >= 0 && confidence <= 1 ? confidence : 0.75,
    reviewer: process.env.USER || 'human',
    notes: notes || null,
  };
}

async function reviewLoop(autoClose = false) {
  console.log(colorize('\n📋 Fetching pending reviews...', 'cyan'));

  const reviews = await fetchPendingReviews({ limit: 20, order_by: 'priority' });

  if (reviews.length === 0) {
    console.log(colorize('✅ No pending reviews!', 'green'));
    return true;
  }

  console.log(colorize(`Found ${reviews.length} pending review(s)`, 'bright'));

  for (let i = 0; i < reviews.length; i++) {
    const review = reviews[i];

    await displayReview(review, i, reviews.length);

    const verdict = await collectVerdict(review);

    if (verdict === null) {
      // Quit
      console.log(colorize('\nExiting...', 'yellow'));
      return false;
    }

    if (verdict.skip) {
      console.log(colorize('Skipped.', 'dim'));
      continue;
    }

    // Update review with verdict
    console.log(colorize('\n💾 Saving verdict...', 'cyan'));
    const updateResult = await updateReviewWithVerdict(review.id, verdict);

    if (updateResult.status === 'success') {
      console.log(colorize('✅ Verdict saved', 'green'));

      // Close feedback loop if requested
      if (autoClose) {
        console.log(colorize('🔄 Closing feedback loop...', 'cyan'));
        const loopResult = await closeHumanFeedbackLoop(review.id);

        if (loopResult.status === 'success') {
          console.log(colorize('✅ Feedback loop closed', 'green'));
          console.log(`   Weighted correct: ${loopResult.weighted_was_correct}`);
          console.log(`   Calibration error: ${loopResult.calibration_error.toFixed(3)}`);
          console.log(`   Strategies updated: ${loopResult.strategy_updates.length}`);
        } else {
          console.log(colorize(`❌ Failed to close loop: ${loopResult.message}`, 'red'));
        }
      }
    } else {
      console.log(colorize(`❌ Failed to save verdict: ${updateResult.message}`, 'red'));
    }

    // Continue?
    if (i < reviews.length - 1) {
      const continueChoice = await ask('\nContinue to next review? (y/n): ');
      if (continueChoice.toLowerCase() !== 'y') {
        console.log(colorize('Stopping review session.', 'yellow'));
        break;
      }
    }
  }

  return true;
}

async function showStats() {
  console.log('\n' + '='.repeat(80));
  console.log(colorize('Human Review Statistics', 'bright'));
  console.log('='.repeat(80));

  // Agreement rates
  console.log('\n' + colorize('Model Agreement Rates:', 'cyan'));
  const rates = await getHumanAgreementRates({ min_reviews: 1 });

  if (rates.length > 0) {
    console.log();
    for (const rate of rates) {
      const pct = (rate.agreement_rate * 100).toFixed(1);
      const bar = '█'.repeat(Math.floor(rate.agreement_rate * 40));
      console.log(`  ${rate.model.padEnd(12)} ${bar} ${pct}% (${rate.correct_count}/${rate.total_reviews})`);
    }
  } else {
    console.log('  No data yet.');
  }

  // Calibration metrics
  console.log('\n' + colorize('Calibration Metrics:', 'cyan'));
  const calibration = await getCalibrationMetrics({ min_reviews: 1 });

  if (calibration) {
    console.log();
    console.log(`  Total reviews: ${calibration.total_reviews}`);
    console.log(`  Accuracy: ${(calibration.accuracy * 100).toFixed(1)}%`);
    console.log(`  Avg calibration error: ${calibration.avg_calibration_error.toFixed(3)}`);
    console.log(`  Avg confidence when correct: ${calibration.avg_confidence_when_correct.toFixed(3)}`);
    console.log(`  Avg confidence when wrong: ${calibration.avg_confidence_when_wrong.toFixed(3)}`);
  } else {
    console.log('  No data yet.');
  }

  console.log();
}

async function main() {
  const args = process.argv.slice(2);
  const autoClose = args.includes('--auto-close');

  console.log(colorize('\n╔════════════════════════════════════════════════════════╗', 'bright'));
  console.log(colorize('║          Human Review CLI Tool                         ║', 'bright'));
  console.log(colorize('╚════════════════════════════════════════════════════════╝', 'bright'));

  if (autoClose) {
    console.log(colorize('\n[Auto-close mode enabled]', 'yellow'));
  }

  try {
    while (true) {
      console.log('\n' + colorize('Main Menu:', 'bright'));
      console.log('  1) Review pending cases');
      console.log('  2) Show statistics');
      console.log('  3) Close feedback loops (batch)');
      console.log('  q) Quit');

      const choice = await ask('\nYour choice: ');

      if (choice === '1') {
        const continueLoop = await reviewLoop(autoClose);
        if (!continueLoop) break;
      } else if (choice === '2') {
        await showStats();
      } else if (choice === '3') {
        // Batch close all reviewed but unresolved entries
        console.log(colorize('\n🔄 Finding reviewed entries...', 'cyan'));

        const client = await pool.connect();
        try {
          const result = await client.query(`
            SELECT id FROM workflow.human_review_queue
            WHERE status = 'reviewed'
            ORDER BY reviewed_at DESC
            LIMIT 50
          `);

          if (result.rows.length === 0) {
            console.log(colorize('No reviewed entries to close.', 'green'));
          } else {
            console.log(colorize(`Found ${result.rows.length} reviewed entries.`, 'bright'));
            const confirm = await ask('Close all feedback loops? (y/n): ');

            if (confirm.toLowerCase() === 'y') {
              let closed = 0;
              for (const row of result.rows) {
                const loopResult = await closeHumanFeedbackLoop(row.id);
                if (loopResult.status === 'success') {
                  closed++;
                  console.log(colorize(`  ✅ Closed review ${row.id}`, 'green'));
                } else {
                  console.log(colorize(`  ❌ Failed to close review ${row.id}: ${loopResult.message}`, 'red'));
                }
              }
              console.log(colorize(`\n✅ Closed ${closed}/${result.rows.length} feedback loops`, 'green'));
            }
          }
        } finally {
          client.release();
        }
      } else if (choice.toLowerCase() === 'q') {
        break;
      } else {
        console.log(colorize('Invalid choice.', 'red'));
      }
    }

    console.log(colorize('\n👋 Goodbye!', 'cyan'));

  } catch (err) {
    console.error(colorize(`\n❌ Error: ${err.message}`, 'red'));
  } finally {
    rl.close();
    await pool.end();
  }
}

main();
