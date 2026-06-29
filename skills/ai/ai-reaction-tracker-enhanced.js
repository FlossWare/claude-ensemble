/**
 * Enhanced AI Reaction Tracker with PostgreSQL Integration
 *
 * This is a drop-in replacement for ai-reaction-tracker.js that:
 * 1. Maintains all existing functionality
 * 2. Automatically persists reaction signals to workflows.learnings table
 * 3. Provides run_id traceability
 *
 * To use: Import from this file instead of ai-reaction-tracker.js
 */

// Import base ai-reaction-tracker functions
const reactionTracker = require('./ai-reaction-tracker.js');
const { getWorkflowsLearning, OUTCOMES } = require('../learning/postgres-adapter');
const { randomBytes } = require('crypto');

// Re-export all base functionality
module.exports = reactionTracker;

// Store the original export function
const originalExport = module.exports;

/**
 * Enhanced workflow wrapper that persists to PostgreSQL
 *
 * This wraps the ai-reaction-tracker workflow to automatically
 * persist reaction signals and task difficulty to the database
 */
async function enhancedReactionTrackerWorkflow(args) {
  // Generate run_id for traceability
  const run_id = args.run_id || `reaction_${Date.now()}_${randomBytes(4).toString('hex')}`;
  const workflow_name = args.workflow || 'ai-reaction-tracker';

  // Get workflows learning tracker
  const workflowsLearning = getWorkflowsLearning();

  // Record workflow start
  await workflowsLearning.recordRun({
    run_id: run_id,
    workflow_name: workflow_name,
    status: 'running',
    input_args: args
  });

  let result;
  let outcome = OUTCOMES.SUCCESS;
  let error_message = null;
  const startTime = Date.now();

  try {
    // Execute the base ai-reaction-tracker workflow
    // This returns the original result (unchanged)
    result = await originalExport(args);

    // Determine outcome from result
    if (result.error) {
      outcome = OUTCOMES.ERROR;
      error_message = result.error;
    }

  } catch (error) {
    outcome = OUTCOMES.ERROR;
    error_message = error.message;
    result = { error: error.message };
  }

  const duration_ms = Date.now() - startTime;

  // Record workflow completion
  await workflowsLearning.recordRun({
    run_id: run_id,
    workflow_name: workflow_name,
    status: outcome === OUTCOMES.SUCCESS ? 'completed' : 'failed',
    output_result: result,
    error_message: error_message,
    duration_ms: duration_ms
  });

  // Persist to workflows.learnings if action was 'record'
  if (args.action === 'record' && result.status === 'recorded' && !result.error) {
    await persistReactionLearning({
      run_id: run_id,
      workflow_name: workflow_name,
      result: result,
      args: args,
      duration_ms: duration_ms,
      outcome: outcome
    });
  }

  // Add run_id to result for traceability
  result.run_id = run_id;

  return result;
}

/**
 * Persist reaction learning to PostgreSQL
 */
async function persistReactionLearning(params) {
  const { run_id, workflow_name, result, args, duration_ms, outcome } = params;

  const workflowsLearning = getWorkflowsLearning();

  // Extract data from ai-reaction-tracker result
  const reactionSignals = {
    avg_composite_score: result.aggregate?.avg_composite_score,
    avg_uncertainty: result.aggregate?.avg_uncertainty,
    total_self_corrections: result.aggregate?.total_self_corrections,
    estimated_difficulty: result.aggregate?.estimated_difficulty,
    model_count: result.aggregate?.model_count
  };

  const taskDifficulty = result.task_assessment?.difficulty || result.aggregate?.estimated_difficulty;
  const modelCount = result.aggregate?.model_count;
  const polarizationIndex = result.disagreement?.polarization_index;
  const behavioralAgreement = result.disagreement?.behavioral_agreement;

  // Calculate estimated cost (rough estimate based on model count and duration)
  // In real usage, this should come from actual cost tracking
  const estimatedCost = modelCount ? (modelCount * 0.0014) : null;

  // Record to workflows.learnings
  await workflowsLearning.recordLearning({
    run_id: run_id,
    workflow_name: workflow_name,
    learning_type: 'model_behavior',
    reaction_signals: reactionSignals,
    task_difficulty: taskDifficulty,
    task_type: args.task_type || 'unknown',
    task_summary: args.task || '',
    quality_score: null, // Could be derived from avg_composite_score
    outcome: outcome,
    model_count: modelCount,
    polarization_index: polarizationIndex,
    behavioral_agreement: behavioralAgreement,
    duration_ms: duration_ms,
    cost_usd: estimatedCost,
    metadata: {
      calibration: result.calibration,
      learning_signals: result.learning_signals,
      task_assessment: result.task_assessment,
      record_id: result.record_id
    }
  });
}

/**
 * Override the default export to use enhanced version
 * This makes the enhanced version a drop-in replacement
 */
module.exports = enhancedReactionTrackerWorkflow;

// Preserve original metadata
module.exports.meta = originalExport.meta;
