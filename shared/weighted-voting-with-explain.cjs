/**
 * Weighted Voting with Explainability Wrapper
 *
 * Thin wrapper around weighted-voting.cjs that adds optional explainability reporting.
 *
 * Usage:
 *   const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');
 *
 *   const result = await runWeightedVotingWithExplain(votes, 'code_review', {
 *     explain: true,
 *     explainFormat: 'markdown',
 *     explainOutputPath: '/tmp/explain-report.md',
 *   });
 *
 *   console.log(result.explainability.markdown);
 *
 * Created: 2026-06-28
 */

const { runWeightedVoting, runWeightedVotingWithDisagreementDetection } = require('./weighted-voting.cjs');
const { explain } = require('./explainability-reporter.cjs');
const { recordVotingOutcome } = require('./confidence-calibration-integration.cjs');

/**
 * Run weighted voting with optional explainability report
 *
 * @param {Array<Object>} votes - Worker votes
 * @param {string} taskType - Task type
 * @param {Object} options - Voting options + explainability options
 * @param {boolean} options.explain - Generate explainability report (default: false)
 * @param {string} options.explainFormat - Format: 'json', 'markdown', 'both' (default: 'json')
 * @param {string} options.explainOutputPath - Optional file path to write report
 * @param {boolean} options.withDisagreementDetection - Use disagreement detection variant (default: false)
 * @returns {Promise<Object>} Voting result with optional explainability
 */
async function runWeightedVotingWithExplain(votes, taskType, options = {}) {
  // Run base weighted voting (choose variant)
  const votingFn = options.withDisagreementDetection
    ? runWeightedVotingWithDisagreementDetection
    : runWeightedVoting;

  const result = await votingFn(votes, taskType, options);

  // Record confidence calibration observations (Issue #264)
  if (result.voting_result?.status === 'success' && !options.skipConfidenceCalibration) {
    try {
      await recordVotingOutcome(
        result.voting_result,
        taskType,
        options.context?.workflow_execution_id || null
      );
    } catch (err) {
      console.warn(`[confidence-calibration] Could not record voting outcome: ${err.message}`);
    }
  }

  // Generate explainability report if requested
  if (options.explain && result.voting_result?.status === 'success') {
    try {
      const explainResult = await explain(result.voting_result, {
        format: options.explainFormat || 'json',
        outputPath: options.explainOutputPath,
        workflowExecutionId: options.context?.workflow_execution_id,
        votingOptions: options,
      });

      result.explainability = explainResult;

      if (explainResult.file_path) {
        console.log(`✓ Explainability report written to ${explainResult.file_path}`);
      }
    } catch (err) {
      console.warn(`[weighted-voting-with-explain] Could not generate explainability report: ${err.message}`);
      result.explainability_error = err.message;
    }
  }

  return result;
}

module.exports = {
  runWeightedVotingWithExplain,
};
