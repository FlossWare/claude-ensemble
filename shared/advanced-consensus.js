/**
 * Advanced Consensus Integration
 * Wires together: batch-consensus, explainability, confidence-calibration, consensus-replay, ab-runner
 *
 * Usage:
 *   const { processWithConsensus } = require('./advanced-consensus.js');
 *
 *   const results = await processWithConsensus({
 *     questions: ['What is X?', 'How does Y work?'],
 *     options: { explain: true, calibrate: true, batch: true }
 *   });
 */

const { batchConsensus } = require('./batch-consensus.cjs');
const { generateExplainabilityReport } = require('./explainability-reporter.cjs');
const { calibrateConfidence, recordObservation } = require('./confidence-calibration.cjs');
const { replayConsensus, getConsensusHistory } = require('./consensus-replay.cjs');
const { runABTest, compareStrategies } = require('./ab-runner.cjs');

/**
 * Process single question or batch with full consensus pipeline
 *
 * @param {Object} options
 * @param {string|string[]} options.questions - Single question or array
 * @param {boolean} [options.explain=false] - Generate explainability report
 * @param {boolean} [options.calibrate=true] - Apply confidence calibration
 * @param {boolean} [options.batch=true] - Use batch processing for arrays
 * @param {number} [options.concurrency=10] - Batch concurrency
 * @param {string[]} [options.workers] - Worker models to use
 * @param {string} [options.taskType='general'] - Task type for capability weighting
 * @returns {Promise<Object>} Results with optional explainability
 */
async function processWithConsensus({
  questions,
  explain = false,
  calibrate = true,
  batch = true,
  concurrency = 10,
  workers = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
  taskType = 'general'
}) {
  const isBatch = Array.isArray(questions);
  const questionArray = isBatch ? questions : [questions];

  // Process with batch consensus
  const consensusOptions = {
    concurrency: batch ? concurrency : 1,
    taskType,
    workers,
    explain,
    explainFormat: 'json',
    useCache: true,
    onProgress: batch ? (completed, total) => {
      console.log(`[advanced-consensus] Progress: ${completed}/${total}`);
    } : null
  };

  const results = await batchConsensus(questionArray, consensusOptions);

  // Apply confidence calibration if requested
  if (calibrate) {
    for (const result of results) {
      if (result.winner && result.winner.confidence) {
        const calibrated = await calibrateConfidence(
          result.winner.model,
          result.winner.confidence,
          taskType
        );
        result.winner.original_confidence = result.winner.confidence;
        result.winner.confidence = calibrated.calibrated_confidence;
        result.winner.calibration_applied = calibrated.adjustment;
      }
    }
  }

  // Generate explainability reports if requested
  if (explain) {
    for (const result of results) {
      if (result.explainability) {
        const report = generateExplainabilityReport(
          result.votes,
          result.winner,
          { format: 'json' }
        );
        result.explainability_report = report;
      }
    }
  }

  return isBatch ? results : results[0];
}

/**
 * Record actual outcome for confidence calibration
 * Call this after you verify if the consensus answer was correct
 *
 * @param {Object} result - Result from processWithConsensus
 * @param {boolean} wasCorrect - Was the consensus answer correct?
 * @returns {Promise<void>}
 */
async function recordOutcome(result, wasCorrect) {
  if (!result.winner) return;

  await recordObservation({
    model: result.winner.model,
    reported_confidence: result.winner.original_confidence || result.winner.confidence,
    actual_outcome: wasCorrect ? 1.0 : 0.0,
    task_type: result.task_type || 'general',
    workflow_execution_id: result.workflow_id || null
  });

  console.log(`[advanced-consensus] Recorded outcome for ${result.winner.model}: ${wasCorrect ? 'CORRECT' : 'INCORRECT'}`);
}

/**
 * Run A/B test comparing two consensus strategies
 *
 * @param {Object} options
 * @param {string[]} options.questions - Test questions
 * @param {Object} options.strategyA - First strategy config
 * @param {Object} options.strategyB - Second strategy config
 * @param {number} [options.iterations=100] - Number of test iterations
 * @returns {Promise<Object>} A/B test results
 */
async function abTestStrategies({ questions, strategyA, strategyB, iterations = 100 }) {
  return await runABTest({
    questions,
    strategyA: () => processWithConsensus({ ...strategyA, questions }),
    strategyB: () => processWithConsensus({ ...strategyB, questions }),
    iterations,
    metric: 'accuracy',
    minSampleSize: Math.min(iterations, 30)
  });
}

/**
 * Replay a past consensus decision for debugging
 *
 * @param {string} workflowId - Workflow execution ID
 * @returns {Promise<Object>} Replay results
 */
async function debugConsensus(workflowId) {
  const history = await getConsensusHistory(workflowId);
  if (!history || history.length === 0) {
    throw new Error(`No consensus history found for workflow ${workflowId}`);
  }

  const replay = await replayConsensus(workflowId);
  return {
    original: history,
    replay,
    differences: compareResults(history[0], replay)
  };
}

function compareResults(original, replay) {
  const diffs = [];

  if (original.winner?.model !== replay.winner?.model) {
    diffs.push({
      type: 'winner_changed',
      original: original.winner?.model,
      replay: replay.winner?.model
    });
  }

  if (Math.abs((original.winner?.confidence || 0) - (replay.winner?.confidence || 0)) > 0.05) {
    diffs.push({
      type: 'confidence_changed',
      original: original.winner?.confidence,
      replay: replay.winner?.confidence
    });
  }

  return diffs;
}

module.exports = {
  processWithConsensus,
  recordOutcome,
  abTestStrategies,
  debugConsensus
};
