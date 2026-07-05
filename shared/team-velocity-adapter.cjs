/**
 * Team Velocity Predictor - JavaScript Adapter
 *
 * Provides easy access to team velocity predictions from JavaScript/Node.js workflows.
 * Uses the trained Python model via subprocess execution.
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

/**
 * Predict team velocity metrics for a workflow configuration
 *
 * @param {Object} config - Workflow configuration
 * @param {number} config.num_workers - Number of workers available (1-8)
 * @param {number} config.num_tasks - Number of tasks to execute
 * @param {string} config.task_complexity - 'simple' | 'medium' | 'complex' | 'very_complex'
 * @param {boolean} config.has_dependencies - Whether tasks have dependencies
 * @param {number} config.model_diversity - Number of unique models
 * @param {number} config.parallel_ratio - How many tasks can run in parallel (0-1)
 * @param {number} config.historical_success_rate - Historical success rate (0-1)
 * @param {number} config.avg_worker_latency_ms - Average worker latency in ms
 *
 * @returns {Object} Prediction results
 * {
 *   predicted_duration_ms: number,
 *   predicted_duration_minutes: number,
 *   parallel_efficiency: number (0-1),
 *   resource_utilization: number (0-1),
 *   success_probability: number (0-1),
 *   theoretical_speedup: number,
 *   actual_speedup: number,
 *   efficiency_percent: number
 * }
 */
function predictVelocity(config) {
  // Write config to temp file
  const tmpFile = path.join(os.tmpdir(), `velocity_config_${Date.now()}.json`);
  fs.writeFileSync(tmpFile, JSON.stringify(config, null, 2));

  try {
    // Call Python script
    const scriptPath = path.join(__dirname, '..', 'tools', 'predict_team_velocity.py');
    const result = execSync(`python3 "${scriptPath}" "${tmpFile}"`, {
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024,
    });

    // Parse result
    const prediction = JSON.parse(result);
    return prediction;

  } catch (error) {
    if (error.stdout) {
      // Try to parse JSON from stdout even if exit code != 0
      try {
        return JSON.parse(error.stdout);
      } catch {}
    }
    throw new Error(`Team velocity prediction failed: ${error.message}`);

  } finally {
    // Cleanup temp file
    try {
      fs.unlinkSync(tmpFile);
    } catch {}
  }
}

/**
 * Get optimal worker count for a given task set
 *
 * @param {number} num_tasks - Number of tasks
 * @param {string} complexity - Task complexity
 * @param {boolean} has_dependencies - Whether tasks have dependencies
 * @returns {number} Optimal worker count (1-8)
 */
function getOptimalWorkerCount(num_tasks, complexity, has_dependencies) {
  const maxWorkers = 8;

  // For small task counts, don't exceed task count
  if (num_tasks <= 3) return Math.min(num_tasks, 3);

  // For simple tasks with no dependencies, use more workers
  if (complexity === 'simple' && !has_dependencies) {
    return Math.min(maxWorkers, Math.ceil(num_tasks / 2));
  }

  // For complex tasks or tasks with dependencies, use fewer workers
  if (complexity === 'very_complex' || has_dependencies) {
    return Math.min(6, Math.ceil(num_tasks / 4));
  }

  // Default: medium complexity
  return Math.min(6, Math.ceil(num_tasks / 3));
}

/**
 * Compare multiple workflow configurations
 *
 * @param {Array<Object>} configs - Array of workflow configurations
 * @returns {Array<Object>} Predictions for each config with name
 */
function compareConfigurations(configs) {
  return configs.map(config => ({
    name: config.name || 'Unnamed',
    config: config,
    prediction: predictVelocity(config),
  }));
}

/**
 * Get team velocity summary (from stats file)
 *
 * @returns {Object} Model training statistics
 */
function getModelStats() {
  const statsPath = path.join(os.homedir(), '.claude', 'learning', 'team_velocity_predictor_stats.json');

  if (!fs.existsSync(statsPath)) {
    throw new Error('Team velocity model not trained. Run: python3 tools/team_velocity_predictor.py');
  }

  const stats = JSON.parse(fs.readFileSync(statsPath, 'utf8'));
  return {
    trained_samples: stats.n_train + stats.n_test,
    duration_r2: stats.duration.test_r2,
    efficiency_r2: stats.efficiency.test_r2,
    utilization_r2: stats.utilization.test_r2,
    success_r2: stats.success.test_r2,
    top_features_duration: Object.entries(stats.feature_importance.duration)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([name, importance]) => ({ name, importance })),
  };
}

/**
 * Helper: Estimate workflow config from task description
 *
 * @param {string} taskDescription - Task description text
 * @param {number} num_workers - Number of workers
 * @returns {Object} Estimated workflow configuration
 */
function estimateConfigFromTask(taskDescription, num_workers = 6) {
  const text = taskDescription.toLowerCase();

  // Estimate complexity
  let complexity = 'medium';
  if (text.includes('implement') || text.includes('create') || text.includes('build')) {
    complexity = 'complex';
  }
  if (text.includes('simple') || text.includes('fix typo') || text.includes('update')) {
    complexity = 'simple';
  }
  if (text.includes('entire') || text.includes('complete') || text.includes('full')) {
    complexity = 'very_complex';
  }

  // Estimate task count (rough heuristic)
  const actionWords = ['implement', 'fix', 'create', 'update', 'analyze', 'review', 'test'];
  const num_tasks = Math.max(5, actionWords.filter(w => text.includes(w)).length * 3);

  // Estimate dependencies
  const has_dependencies = text.includes('sequential') || text.includes('depends') ||
                           text.includes('after') || text.includes('before');

  // Estimate parallel ratio
  const parallel_ratio = has_dependencies ? 0.5 : 0.8;

  return {
    num_workers,
    num_tasks,
    task_complexity: complexity,
    has_dependencies,
    model_diversity: Math.min(num_workers, 6),
    parallel_ratio,
    historical_success_rate: 0.80,
    avg_worker_latency_ms: complexity === 'simple' ? 1500 :
                           complexity === 'medium' ? 3000 :
                           complexity === 'complex' ? 5000 : 8000,
  };
}

module.exports = {
  predictVelocity,
  getOptimalWorkerCount,
  compareConfigurations,
  getModelStats,
  estimateConfigFromTask,
};
