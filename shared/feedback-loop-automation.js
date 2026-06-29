/**
 * Feedback Loop Automation
 *
 * Automatically updates Thompson Sampling strategy performance based on human feedback.
 *
 * Features:
 *   - Reads human reviews from workflow.feedback table
 *   - Updates learning.strategy_performance (alpha/beta parameters)
 *   - Bayesian updates: rating → success weight, (1 - rating) → failure weight
 *   - Runs continuously or on-demand
 *
 * Usage:
 *   import { processFeedbackLoop } from './shared/feedback-loop-automation.js';
 *   await processFeedbackLoop();  // Process all unprocessed feedback
 *
 * Or as a service:
 *   node shared/feedback-loop-automation.js --daemon
 */

import { getDB, getStrategyPerformance } from '../learning/postgres-adapter.js';

export class FeedbackLoopAutomation {
  constructor() {
    this.db = getDB();
    this.strategyPerf = getStrategyPerformance();
  }

  /**
   * Process all unprocessed feedback and update Thompson Sampling
   *
   * @returns {Object} { processed: number, updated_strategies: string[] }
   */
  async processFeedbackLoop() {
    const stats = {
      processed: 0,
      updated_strategies: new Set(),
      errors: []
    };

    try {
      // Get all unprocessed feedback
      const feedbackRows = await this.db.query(`
        SELECT
          f.id,
          f.workflow_execution_id,
          f.rating,
          f.corrections,
          f.created_at,
          e.workflow_name,
          wr.model,
          ad.strategy_used
        FROM workflow.feedback f
        JOIN workflow.executions e ON f.workflow_execution_id = e.id
        LEFT JOIN workflow.worker_results wr ON e.id = wr.workflow_execution_id
        LEFT JOIN workflow.arbiter_decisions ad ON e.id = ad.workflow_execution_id
        WHERE f.processed = FALSE
        ORDER BY f.created_at ASC
      `);

      console.log(`Found ${feedbackRows.length} unprocessed feedback entries`);

      for (const feedback of feedbackRows) {
        try {
          await this.processSingleFeedback(feedback);
          stats.processed++;
          if (feedback.strategy_used) {
            stats.updated_strategies.add(feedback.strategy_used);
          }
        } catch (error) {
          console.error(`Error processing feedback ${feedback.id}:`, error.message);
          stats.errors.push({ feedback_id: feedback.id, error: error.message });
        }
      }

      console.log(`✅ Processed ${stats.processed} feedback entries`);
      console.log(`✅ Updated strategies: ${Array.from(stats.updated_strategies).join(', ')}`);

      return {
        processed: stats.processed,
        updated_strategies: Array.from(stats.updated_strategies),
        errors: stats.errors
      };

    } catch (error) {
      console.error('Feedback loop error:', error);
      throw error;
    }
  }

  /**
   * Process a single feedback entry
   *
   * @param {Object} feedback - Feedback row from database
   */
  async processSingleFeedback(feedback) {
    const { id, rating, strategy_used, workflow_name } = feedback;

    if (!strategy_used) {
      console.warn(`Feedback ${id} has no strategy_used, skipping Thompson Sampling update`);
      await this.markFeedbackProcessed(id);
      return;
    }

    // Convert rating (0-5.0) to success/failure weights
    // rating = 5.0 → full success (alpha += 1.0, beta += 0.0)
    // rating = 2.5 → neutral (alpha += 0.5, beta += 0.5)
    // rating = 0.0 → full failure (alpha += 0.0, beta += 1.0)
    const normalizedRating = Math.max(0, Math.min(5, rating)) / 5.0;
    const successWeight = normalizedRating;
    const failureWeight = 1.0 - normalizedRating;

    console.log(`Processing feedback ${id}: rating=${rating}, strategy=${strategy_used}, success_weight=${successWeight.toFixed(2)}`);

    // Update Thompson Sampling state
    await this.strategyPerf.updateStrategy(
      strategy_used,
      successWeight,   // Add to alpha (successes)
      failureWeight    // Add to beta (failures)
    );

    // Mark feedback as processed
    await this.markFeedbackProcessed(id);

    console.log(`✅ Updated ${strategy_used}: +${successWeight.toFixed(2)} alpha, +${failureWeight.toFixed(2)} beta`);
  }

  /**
   * Mark feedback as processed
   *
   * @param {number} feedbackId - Feedback ID to mark
   */
  async markFeedbackProcessed(feedbackId) {
    await this.db.query(
      `UPDATE workflow.feedback
       SET processed = TRUE, processed_at = NOW()
       WHERE id = $1`,
      [feedbackId]
    );
  }

  /**
   * Get feedback processing statistics
   *
   * @returns {Object} { total: number, processed: number, unprocessed: number }
   */
  async getFeedbackStats() {
    const result = await this.db.query(`
      SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE processed = TRUE) as processed,
        COUNT(*) FILTER (WHERE processed = FALSE) as unprocessed
      FROM workflow.feedback
    `);

    return result[0];
  }

  /**
   * Disconnect from database
   */
  async disconnect() {
    await this.db.disconnect();
  }
}

/**
 * Process all unprocessed feedback (convenience function)
 *
 * @returns {Object} Processing stats
 */
export async function processFeedbackLoop() {
  const automation = new FeedbackLoopAutomation();
  const stats = await automation.processFeedbackLoop();
  await automation.disconnect();
  return stats;
}

/**
 * Daemon mode: process feedback every N minutes
 *
 * @param {number} intervalMinutes - Interval in minutes (default: 5)
 */
export async function runFeedbackLoopDaemon(intervalMinutes = 5) {
  console.log(`Starting feedback loop daemon (interval: ${intervalMinutes} min)`);

  const automation = new FeedbackLoopAutomation();

  // Process immediately on start
  await automation.processFeedbackLoop();

  // Then process on interval
  setInterval(async () => {
    try {
      await automation.processFeedbackLoop();
    } catch (error) {
      console.error('Daemon error:', error);
    }
  }, intervalMinutes * 60 * 1000);

  console.log('Feedback loop daemon running (Ctrl+C to stop)');
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);

  if (args.includes('--daemon')) {
    const interval = parseInt(args.find(a => a.startsWith('--interval='))?.split('=')[1] || '5');
    runFeedbackLoopDaemon(interval);
  } else if (args.includes('--stats')) {
    const automation = new FeedbackLoopAutomation();
    automation.getFeedbackStats()
      .then(stats => {
        console.log('Feedback Stats:', stats);
        return automation.disconnect();
      });
  } else {
    processFeedbackLoop()
      .then(stats => {
        console.log('Processing complete:', stats);
        process.exit(0);
      })
      .catch(error => {
        console.error('Error:', error);
        process.exit(1);
      });
  }
}
