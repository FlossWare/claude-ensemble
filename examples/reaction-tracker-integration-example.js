/**
 * Example: Integrating ai-reaction-tracker with PostgreSQL Workflows Learning
 *
 * This demonstrates how to:
 * 1. Run a workflow that uses ai-reaction-tracker
 * 2. Extract reaction signals from the result
 * 3. Persist to workflows.learnings table with run_id traceability
 *
 * Usage:
 *   node reaction-tracker-integration-example.js
 */

const { getWorkflowsLearning } = require('../../learning/postgres-adapter');
const { randomBytes } = require('crypto');

/**
 * Example 1: Record reaction signals from ai-consensus-weighted workflow
 */
async function exampleConsensusWorkflow() {
  console.log('='.repeat(70));
  console.log('Example: ai-consensus-weighted with reaction tracking');
  console.log('='.repeat(70));

  // Simulate a workflow run
  const run_id = `run_${Date.now()}_${randomBytes(4).toString('hex')}`;
  const workflow_name = 'ai-consensus-weighted';

  console.log(`Run ID: ${run_id}`);
  console.log(`Workflow: ${workflow_name}`);
  console.log();

  // Simulate workflow execution result with reaction signals
  // (In real usage, this comes from ai-reaction-tracker)
  const workflowResult = {
    status: 'recorded',
    record_id: 'reaction_2026-06-19T12:34:56_abc123',

    // Aggregate metrics from ai-reaction-tracker
    aggregate: {
      avg_composite_score: 78,
      avg_uncertainty: 32,
      total_self_corrections: 2,
      estimated_difficulty: 'moderate',
      model_count: 3
    },

    // Disagreement analysis
    disagreement: {
      polarization_index: 25,
      behavioral_agreement: 85
    },

    // Per-model calibration data
    calibration: [
      { model: 'opus', reported: 85, behavioral: 82, delta: 3, calibration: 'well_calibrated' },
      { model: 'sonnet', reported: 78, behavioral: 75, delta: 3, calibration: 'well_calibrated' },
      { model: 'haiku', reported: 65, behavioral: 70, delta: -5, calibration: 'underconfident' }
    ],

    // Task assessment
    task_assessment: {
      difficulty: 'moderate',
      ambiguity: 'low',
      trickiness: 'low'
    },

    // Learning signals
    learning_signals: [
      {
        type: 'confidence_ranking',
        task_type: 'code-review',
        ranking: [
          { model: 'opus', score: 82 },
          { model: 'sonnet', score: 75 },
          { model: 'haiku', score: 70 }
        ],
        top_model: 'opus',
        recommendation: 'For code-review tasks, opus shows highest behavioral confidence (82)'
      }
    ]
  };

  // Persist to workflows.learnings table
  const workflowsLearning = getWorkflowsLearning();

  const learning = await workflowsLearning.recordLearning({
    run_id: run_id,
    workflow_name: workflow_name,
    learning_type: 'model_behavior',
    reaction_signals: workflowResult.aggregate,
    task_difficulty: workflowResult.task_assessment.difficulty,
    task_type: 'code-review',
    task_summary: 'Review security vulnerabilities in authentication module',
    quality_score: 0.85,
    outcome: 'success',
    model_count: workflowResult.aggregate.model_count,
    polarization_index: workflowResult.disagreement.polarization_index,
    behavioral_agreement: workflowResult.disagreement.behavioral_agreement,
    duration_ms: 3200,
    cost_usd: 0.0042,
    metadata: {
      calibration: workflowResult.calibration,
      learning_signals: workflowResult.learning_signals,
      task_assessment: workflowResult.task_assessment
    }
  });

  console.log('Learning recorded:');
  console.log(`  ID: ${learning.id}`);
  console.log(`  Created: ${learning.created_at}`);
  console.log(`  Task difficulty: ${workflowResult.task_assessment.difficulty}`);
  console.log(`  Polarization: ${workflowResult.disagreement.polarization_index}`);
  console.log(`  Behavioral agreement: ${workflowResult.disagreement.behavioral_agreement}%`);
  console.log();

  // Record workflow run metadata
  await workflowsLearning.recordRun({
    run_id: run_id,
    workflow_name: workflow_name,
    status: 'completed',
    input_args: { task: 'Review code for security vulnerabilities', models: ['opus', 'sonnet', 'haiku'] },
    output_result: workflowResult,
    duration_ms: 3200
  });

  console.log('Workflow run metadata recorded');
  console.log();

  return run_id;
}

/**
 * Example 2: Query learnings by task difficulty
 */
async function exampleQueryByDifficulty() {
  console.log('='.repeat(70));
  console.log('Example: Query learnings by task difficulty');
  console.log('='.repeat(70));

  const workflowsLearning = getWorkflowsLearning();

  // Query all moderate difficulty tasks
  const moderateTasks = await workflowsLearning.queryLearnings({
    task_difficulty: 'moderate',
    limit: 10
  });

  console.log(`Found ${moderateTasks.length} moderate difficulty tasks`);

  for (const task of moderateTasks) {
    console.log(`  - ${task.workflow_name} / ${task.task_type}`);
    console.log(`    Quality: ${task.quality_score}`);
    console.log(`    Models: ${task.model_count}`);
    console.log(`    Polarization: ${task.polarization_index}`);
  }

  console.log();
}

/**
 * Example 3: Get task difficulty statistics
 */
async function exampleTaskDifficultyStats() {
  console.log('='.repeat(70));
  console.log('Example: Task difficulty statistics');
  console.log('='.repeat(70));

  const workflowsLearning = getWorkflowsLearning();

  const stats = await workflowsLearning.getTaskDifficultyStats();

  console.log('Task Difficulty Distribution:');
  console.log();

  for (const stat of stats) {
    console.log(`${stat.task_type} / ${stat.task_difficulty}:`);
    console.log(`  Count: ${stat.count}`);
    console.log(`  Avg Quality: ${stat.avg_quality?.toFixed(2) || 'N/A'}`);
    console.log(`  Avg Duration: ${stat.avg_duration_ms?.toFixed(0) || 'N/A'}ms`);
    console.log(`  Avg Models: ${stat.avg_models_used?.toFixed(1) || 'N/A'}`);
    console.log(`  Avg Polarization: ${stat.avg_polarization?.toFixed(0) || 'N/A'}`);
    console.log();
  }
}

/**
 * Example 4: Get workflow performance summary
 */
async function exampleWorkflowPerformance() {
  console.log('='.repeat(70));
  console.log('Example: Workflow performance summary');
  console.log('='.repeat(70));

  const workflowsLearning = getWorkflowsLearning();

  const performance = await workflowsLearning.getWorkflowPerformance();

  console.log('Workflow Performance:');
  console.log();

  for (const perf of performance) {
    console.log(`${perf.workflow_name}:`);
    console.log(`  Total runs: ${perf.total_runs}`);
    console.log(`  Successful: ${perf.successful_runs}`);
    console.log(`  Success rate: ${((perf.successful_runs / perf.total_runs) * 100).toFixed(1)}%`);
    console.log(`  Avg quality: ${perf.avg_quality?.toFixed(2) || 'N/A'}`);
    console.log(`  Avg duration: ${perf.avg_duration_ms?.toFixed(0) || 'N/A'}ms`);
    console.log(`  Avg cost: $${perf.avg_cost_usd?.toFixed(4) || 'N/A'}`);
    console.log(`  Last run: ${perf.last_run}`);
    console.log();
  }
}

/**
 * Example 5: Traceability - Get all learnings for a specific run
 */
async function exampleTraceability(run_id) {
  console.log('='.repeat(70));
  console.log('Example: Traceability via run_id');
  console.log('='.repeat(70));

  const workflowsLearning = getWorkflowsLearning();

  const learnings = await workflowsLearning.getLearningsByRunId(run_id);

  console.log(`Learnings for run_id: ${run_id}`);
  console.log(`Found ${learnings.length} learning record(s)`);
  console.log();

  for (const learning of learnings) {
    console.log(`Learning ID: ${learning.id}`);
    console.log(`  Type: ${learning.learning_type}`);
    console.log(`  Task: ${learning.task_type} / ${learning.task_difficulty}`);
    console.log(`  Quality: ${learning.quality_score}`);
    console.log(`  Outcome: ${learning.outcome}`);
    console.log(`  Models: ${learning.model_count}`);
    console.log(`  Timestamp: ${learning.timestamp}`);
    console.log();
  }
}

/**
 * Main execution
 */
async function main() {
  try {
    // Example 1: Record consensus workflow with reaction tracking
    const run_id = await exampleConsensusWorkflow();

    // Example 2: Query by difficulty
    await exampleQueryByDifficulty();

    // Example 3: Task difficulty statistics
    await exampleTaskDifficultyStats();

    // Example 4: Workflow performance summary
    await exampleWorkflowPerformance();

    // Example 5: Traceability
    await exampleTraceability(run_id);

    console.log('='.repeat(70));
    console.log('All examples completed successfully');
    console.log('='.repeat(70));

    process.exit(0);
  } catch (error) {
    console.error('Error:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run examples if executed directly
if (require.main === module) {
  main();
}

module.exports = {
  exampleConsensusWorkflow,
  exampleQueryByDifficulty,
  exampleTaskDifficultyStats,
  exampleWorkflowPerformance,
  exampleTraceability
};
