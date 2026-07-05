/**
 * Resource Usage Predictor - JavaScript Adapter
 *
 * Provides easy access to resource usage predictions for workflow planning.
 *
 * Usage:
 *   const { predictResourceUsage, estimateWorkflowCost } = require('./shared/resource-usage-adapter.cjs');
 *
 *   // Single task prediction
 *   const pred = await predictResourceUsage({
 *     model: 'opus',
 *     workflow: 'deep-research',
 *     taskType: 'research',
 *     taskDescription: 'Research quantum computing'
 *   });
 *
 *   // Multi-worker workflow cost estimation
 *   const cost = await estimateWorkflowCost([
 *     { model: 'opus', workflow: 'deep-research', taskType: 'research' },
 *     { model: 'sonnet', workflow: 'deep-research', taskType: 'synthesis' }
 *   ]);
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const PREDICTOR_SCRIPT = path.join(__dirname, '../tools/resource_usage_predictor.py');
const MODEL_PATH = path.join(process.env.HOME, '.claude/learning/resource_usage_predictor.pkl');

/**
 * Check if predictor model is trained
 */
function isModelTrained() {
  return fs.existsSync(MODEL_PATH);
}

/**
 * Train the predictor model (if not already trained)
 */
async function ensureModelTrained() {
  if (!isModelTrained()) {
    console.log('Resource usage predictor not trained, training now...');
    execSync(`python3 ${PREDICTOR_SCRIPT} --retrain`, { stdio: 'inherit' });
  }
}

/**
 * Predict resource usage for a single task
 *
 * @param {Object} options
 * @param {string} options.model - Model name (e.g., 'opus', 'sonnet')
 * @param {string} options.workflow - Workflow name
 * @param {string} options.taskType - Task type
 * @param {string} [options.taskDescription] - Optional task description for better prediction
 * @returns {Promise<Object>} Prediction: {input_tokens, output_tokens, duration_ms, cost_usd}
 */
async function predictResourceUsage({ model, workflow, taskType, taskDescription }) {
  await ensureModelTrained();

  const taskDesc = taskDescription || `${workflow} ${taskType}`;

  const script = `
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / 'Development' / 'redhat' / 'scm' / 'gitlab' / 'cee' / 'sfloess' / 'claude-global-skills' / 'tools'))
from resource_usage_predictor import ResourceUsagePredictor
import json

predictor = ResourceUsagePredictor.load('${MODEL_PATH}')
pred = predictor.predict(
  model='${model}',
  workflow='${workflow}',
  task_type='${taskType}',
  task_description='${taskDesc.replace(/'/g, "\\'")}'
)
print(json.dumps(pred))
`;

  const result = execSync(`python3 -c ${JSON.stringify(script)}`, { encoding: 'utf-8' });
  return JSON.parse(result.trim());
}

/**
 * Estimate total cost for a multi-worker workflow
 *
 * @param {Array<Object>} tasks - Array of task specifications
 * @returns {Promise<Object>} Aggregated estimates: {total_input_tokens, total_output_tokens, total_duration_ms, total_cost_usd}
 */
async function estimateWorkflowCost(tasks) {
  const predictions = await Promise.all(
    tasks.map(task => predictResourceUsage(task))
  );

  const totals = predictions.reduce((acc, pred) => ({
    total_input_tokens: acc.total_input_tokens + pred.input_tokens,
    total_output_tokens: acc.total_output_tokens + pred.output_tokens,
    total_duration_ms: acc.total_duration_ms + pred.duration_ms,
    total_cost_usd: acc.total_cost_usd + pred.cost_usd
  }), {
    total_input_tokens: 0,
    total_output_tokens: 0,
    total_duration_ms: 0,
    total_cost_usd: 0
  });

  totals.estimated_tasks = tasks.length;
  totals.predictions = predictions;

  return totals;
}

/**
 * Get predictor statistics (training metrics)
 */
function getPredictorStats() {
  const statsPath = path.join(process.env.HOME, '.claude/learning/resource_usage_predictor_stats.json');
  if (!fs.existsSync(statsPath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(statsPath, 'utf-8'));
}

/**
 * Format prediction for human-readable output
 */
function formatPrediction(pred) {
  return [
    `Input tokens:  ${pred.input_tokens.toLocaleString()}`,
    `Output tokens: ${pred.output_tokens.toLocaleString()}`,
    `Duration:      ${(pred.duration_ms / 1000).toFixed(1)}s`,
    `Cost:          $${pred.cost_usd.toFixed(4)}`
  ].join('\n');
}

/**
 * Format workflow cost estimate for human-readable output
 */
function formatWorkflowEstimate(estimate) {
  const lines = [
    'Workflow Cost Estimate',
    '='.repeat(60),
    `Tasks:         ${estimate.estimated_tasks}`,
    `Total Tokens:  ${(estimate.total_input_tokens + estimate.total_output_tokens).toLocaleString()} (${estimate.total_input_tokens.toLocaleString()} in, ${estimate.total_output_tokens.toLocaleString()} out)`,
    `Total Duration: ${(estimate.total_duration_ms / 1000).toFixed(1)}s`,
    `Total Cost:    $${estimate.total_cost_usd.toFixed(4)}`,
    '='.repeat(60)
  ];

  if (estimate.predictions) {
    lines.push('\nPer-Task Breakdown:');
    estimate.predictions.forEach((pred, idx) => {
      lines.push(`  Task ${idx + 1}: ${pred.input_tokens}/${pred.output_tokens} tokens, ${(pred.duration_ms / 1000).toFixed(1)}s, $${pred.cost_usd.toFixed(4)}`);
    });
  }

  return lines.join('\n');
}

module.exports = {
  isModelTrained,
  ensureModelTrained,
  predictResourceUsage,
  estimateWorkflowCost,
  getPredictorStats,
  formatPrediction,
  formatWorkflowEstimate
};
