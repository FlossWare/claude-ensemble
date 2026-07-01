/**
 * Confidence Calibration Integration Helper
 *
 * Provides easy integration points for recording confidence observations
 * when actual outcomes are determined.
 *
 * Integration Points:
 * 1. After arbiter decision (compare worker confidence vs arbiter selection)
 * 2. After quality scoring (compare worker confidence vs quality score)
 * 3. After weighted voting (compare worker confidence vs vote weight)
 *
 * Usage:
 *   const { recordWorkerOutcome, recordArbiterOutcome } = require('./confidence-calibration-integration.cjs');
 *
 *   // After arbiter decides
 *   await recordArbiterOutcome(workerResults, arbiterDecision, taskType);
 *
 *   // After quality scoring
 *   await recordQualityOutcome(model, reportedConfidence, qualityScore, taskType);
 *
 * Created: 2026-07-01 (Issue #264)
 */

const { storeObservation } = require('./confidence-calibration.cjs');

/**
 * Record confidence observation after arbiter decision
 *
 * Compares worker's reported confidence against arbiter's selection.
 * Workers whose answers were selected by arbiter = correct (1.0)
 * Workers whose answers were rejected = incorrect (0.0)
 *
 * @param {Array<Object>} workerResults - Worker results
 * @param {Array<number>} workerResults[].worker_id - Worker ID
 * @param {string} workerResults[].model - Model name
 * @param {number} workerResults[].confidence - Reported confidence (0-1 or 0-100)
 * @param {*} workerResults[].answer - Worker's answer
 * @param {Object} arbiterDecision - Arbiter decision
 * @param {*} arbiterDecision.selected_answer - Answer selected by arbiter
 * @param {string} taskType - Task type for calibration tracking
 * @param {string} workflowExecutionId - Workflow execution ID (optional)
 * @returns {Promise<void>}
 */
async function recordArbiterOutcome(workerResults, arbiterDecision, taskType, workflowExecutionId = null) {
  if (!workerResults || workerResults.length === 0) {
    console.warn('[confidence-calibration] No worker results to record');
    return;
  }

  if (!arbiterDecision || !arbiterDecision.selected_answer) {
    console.warn('[confidence-calibration] No arbiter decision to compare against');
    return;
  }

  const selectedAnswer = arbiterDecision.selected_answer;

  // Record observations for each worker
  for (const worker of workerResults) {
    if (!worker.model || worker.confidence == null) {
      continue; // Skip workers without model or confidence
    }

    // Normalize confidence to 0-1 range
    let normalizedConfidence = parseFloat(worker.confidence);
    if (normalizedConfidence > 1.0) {
      normalizedConfidence = normalizedConfidence / 100.0;
    }

    // Determine if worker was correct (deep equality check)
    const isCorrect = JSON.stringify(worker.answer) === JSON.stringify(selectedAnswer);
    const actualOutcome = isCorrect ? 1.0 : 0.0;

    try {
      await storeObservation({
        model: worker.model,
        reported_confidence: normalizedConfidence,
        actual_outcome: actualOutcome,
        task_type: taskType,
        workflow_execution_id: workflowExecutionId,
      });
    } catch (err) {
      console.warn(`[confidence-calibration] Failed to store observation for ${worker.model}: ${err.message}`);
    }
  }

  console.log(`[confidence-calibration] Recorded ${workerResults.length} observations for task type '${taskType}'`);
}

/**
 * Record confidence observation after quality scoring
 *
 * Converts quality score (0-100) to binary outcome:
 * - Quality >= 80: correct (1.0)
 * - Quality < 80: incorrect (0.0)
 *
 * @param {string} model - Model name
 * @param {number} reportedConfidence - Reported confidence (0-1 or 0-100)
 * @param {number} qualityScore - Quality score (0-100)
 * @param {string} taskType - Task type
 * @param {string} workflowExecutionId - Workflow execution ID (optional)
 * @param {number} qualityThreshold - Quality threshold for "correct" (default: 80)
 * @returns {Promise<void>}
 */
async function recordQualityOutcome(
  model,
  reportedConfidence,
  qualityScore,
  taskType,
  workflowExecutionId = null,
  qualityThreshold = 80
) {
  // Normalize confidence to 0-1 range
  let normalizedConfidence = parseFloat(reportedConfidence);
  if (normalizedConfidence > 1.0) {
    normalizedConfidence = normalizedConfidence / 100.0;
  }

  // Convert quality score to binary outcome
  const actualOutcome = qualityScore >= qualityThreshold ? 1.0 : 0.0;

  try {
    await storeObservation({
      model,
      reported_confidence: normalizedConfidence,
      actual_outcome: actualOutcome,
      task_type: taskType,
      workflow_execution_id: workflowExecutionId,
    });

    console.log(
      `[confidence-calibration] Recorded quality outcome for ${model}: ` +
      `confidence=${(normalizedConfidence * 100).toFixed(0)}%, quality=${qualityScore}, outcome=${actualOutcome}`
    );
  } catch (err) {
    console.warn(`[confidence-calibration] Failed to store quality observation: ${err.message}`);
  }
}

/**
 * Record confidence observation after weighted voting
 *
 * Uses consensus strength to determine correctness:
 * - Winner group: correct (1.0)
 * - Loser groups: incorrect (0.0)
 *
 * @param {Object} votingResult - Result from weighted-voting.cjs
 * @param {string} taskType - Task type
 * @param {string} workflowExecutionId - Workflow execution ID (optional)
 * @returns {Promise<void>}
 */
async function recordVotingOutcome(votingResult, taskType, workflowExecutionId = null) {
  if (!votingResult || votingResult.status !== 'success') {
    console.warn('[confidence-calibration] Invalid voting result, skipping observation recording');
    return;
  }

  const { winner, all_groups } = votingResult;

  // Record observations for all votes
  for (const group of all_groups) {
    const isWinner = JSON.stringify(group.answer) === JSON.stringify(winner.answer);
    const actualOutcome = isWinner ? 1.0 : 0.0;

    // Record for each vote in the group
    for (const vote of group.votes || []) {
      if (!vote.model || vote.confidence == null) {
        continue;
      }

      // Normalize confidence
      let normalizedConfidence = parseFloat(vote.confidence);
      if (normalizedConfidence > 1.0) {
        normalizedConfidence = normalizedConfidence / 100.0;
      }

      try {
        await storeObservation({
          model: vote.model,
          reported_confidence: normalizedConfidence,
          actual_outcome: actualOutcome,
          task_type: taskType,
          workflow_execution_id: workflowExecutionId,
        });
      } catch (err) {
        console.warn(`[confidence-calibration] Failed to store voting observation: ${err.message}`);
      }
    }
  }

  const totalVotes = all_groups.reduce((sum, g) => sum + (g.votes?.length || 0), 0);
  console.log(
    `[confidence-calibration] Recorded ${totalVotes} voting observations for task type '${taskType}'`
  );
}

/**
 * Record confidence observation manually (for custom integrations)
 *
 * @param {string} model - Model name
 * @param {number} reportedConfidence - Reported confidence (0-1 or 0-100)
 * @param {number} actualOutcome - Actual outcome (0.0 = wrong, 1.0 = correct)
 * @param {string} taskType - Task type
 * @param {string} workflowExecutionId - Workflow execution ID (optional)
 * @returns {Promise<void>}
 */
async function recordObservation(model, reportedConfidence, actualOutcome, taskType, workflowExecutionId = null) {
  // Normalize confidence to 0-1 range
  let normalizedConfidence = parseFloat(reportedConfidence);
  if (normalizedConfidence > 1.0) {
    normalizedConfidence = normalizedConfidence / 100.0;
  }

  // Validate actualOutcome (must be 0.0 or 1.0)
  if (actualOutcome !== 0.0 && actualOutcome !== 1.0) {
    console.warn(
      `[confidence-calibration] Invalid actualOutcome (${actualOutcome}), must be 0.0 or 1.0. Skipping.`
    );
    return;
  }

  try {
    await storeObservation({
      model,
      reported_confidence: normalizedConfidence,
      actual_outcome: actualOutcome,
      task_type: taskType,
      workflow_execution_id: workflowExecutionId,
    });

    console.log(
      `[confidence-calibration] Recorded observation for ${model}: ` +
      `confidence=${(normalizedConfidence * 100).toFixed(0)}%, outcome=${actualOutcome}`
    );
  } catch (err) {
    console.warn(`[confidence-calibration] Failed to store observation: ${err.message}`);
  }
}

module.exports = {
  recordArbiterOutcome,
  recordQualityOutcome,
  recordVotingOutcome,
  recordObservation,
};
