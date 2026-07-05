/**
 * Load Balancer Adapter - JavaScript interface to Python load balancer optimizer
 *
 * Provides intelligent model selection based on:
 * - Historical performance (quality, latency, cost)
 * - Task type affinity (which models work best for which tasks)
 * - Thompson Sampling exploration/exploitation
 * - Resource constraints (max latency, max cost)
 *
 * Usage:
 *   const { selectModel, getModelStats } = require('./shared/load-balancer-adapter.cjs');
 *   const selection = await selectModel({ taskType: 'code_review', complexity: 0.6 });
 *   console.log(`Use model: ${selection.model}`);
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Paths
const LEARNING_DIR = path.join(process.env.HOME, 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning');
const TOOLS_DIR = path.join(process.env.HOME, 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools');
const STATS_FILE = path.join(LEARNING_DIR, 'load_balancer_optimizer_stats.json');
const OPTIMIZER_SCRIPT = path.join(TOOLS_DIR, 'load_balancer_optimizer.py');

/**
 * Load cached statistics (fast, no Python execution)
 *
 * @returns {Object} Load balancer state with model statistics
 */
function loadStats() {
  if (!fs.existsSync(STATS_FILE)) {
    throw new Error(`Load balancer stats not found. Run: python3 ${OPTIMIZER_SCRIPT}`);
  }

  const data = fs.readFileSync(STATS_FILE, 'utf-8');
  return JSON.parse(data);
}

/**
 * Get statistics for all models
 *
 * @returns {Object} Model name -> ModelStats
 */
function getModelStats() {
  const state = loadStats();
  return state.model_stats;
}

/**
 * Get task affinities (which models work best for which tasks)
 *
 * @returns {Object} Task type -> Model -> affinity score
 */
function getTaskAffinities() {
  const state = loadStats();
  return state.task_affinities;
}

/**
 * Get current load distribution across models
 *
 * @returns {Object} Model -> load percentage
 */
function getLoadDistribution() {
  const state = loadStats();
  return state.load_distribution;
}

/**
 * Get Thompson Sampling bandit parameters
 *
 * @returns {Object} Model -> {alpha, beta, successes, failures}
 */
function getBanditParams() {
  const state = loadStats();
  return state.bandit_params;
}

/**
 * Select best model using Thompson Sampling with constraints
 *
 * This is a JavaScript implementation of the Python optimizer's select_model()
 * to avoid Python subprocess overhead.
 *
 * @param {Object} options - Selection options
 * @param {string} options.taskType - Type of task (for affinity matching)
 * @param {number} options.complexity - Task complexity [0-1]
 * @param {number} options.maxLatencyMs - Maximum acceptable latency
 * @param {number} options.maxCost - Maximum acceptable cost (USD)
 * @returns {Object} Selection with model, confidence, reasoning, alternatives
 */
function selectModel({
  taskType = null,
  complexity = 0.5,
  maxLatencyMs = null,
  maxCost = null
} = {}) {
  const state = loadStats();
  const { bandit_params, task_affinities, model_stats } = state;

  if (!bandit_params || Object.keys(bandit_params).length === 0) {
    return {
      model: 'haiku',  // Safe default
      confidence: 0.5,
      reasoning: 'No training data, using default',
      alternatives: {}
    };
  }

  // Sample from Thompson Sampling (Beta distribution)
  const samples = {};

  for (const [model, params] of Object.entries(bandit_params)) {
    // Sample from Beta(alpha, beta)
    let sample = betaSample(params.alpha, params.beta);

    // Apply task affinity if available
    if (taskType && task_affinities[taskType]) {
      const affinity = task_affinities[taskType][model] || 0.5;
      sample *= affinity;
    }

    // Apply constraints
    const stats = model_stats[model];
    if (stats) {
      // Latency constraint
      if (maxLatencyMs && stats.p95_latency > maxLatencyMs) {
        sample *= 0.5;  // Penalty for high latency
      }

      // Cost constraint
      if (maxCost && stats.avg_cost > maxCost) {
        sample *= 0.3;  // Heavy penalty for high cost
      }
    }

    samples[model] = sample;
  }

  // Select best
  const sortedModels = Object.entries(samples).sort((a, b) => b[1] - a[1]);
  const [bestModel, confidence] = sortedModels[0];

  // Generate reasoning
  const stats = model_stats[bestModel];
  let reasoning = `Thompson Sampling selected ${bestModel} `;
  if (stats) {
    reasoning += `(quality: ${stats.avg_quality.toFixed(2)}, `;
    reasoning += `latency: ${stats.p95_latency.toFixed(0)}ms, `;
    reasoning += `cost: $${stats.avg_cost.toFixed(5)})`;
  }

  if (taskType && task_affinities[taskType]) {
    const affinity = task_affinities[taskType][bestModel] || 0.0;
    reasoning += ` with ${affinity.toFixed(2)} affinity for ${taskType}`;
  }

  // Top 5 alternatives
  const alternatives = {};
  for (let i = 0; i < Math.min(5, sortedModels.length); i++) {
    const [model, score] = sortedModels[i];
    alternatives[model] = score;
  }

  return {
    model: bestModel,
    confidence: confidence,
    reasoning: reasoning,
    alternatives: alternatives,
    stats: stats
  };
}

/**
 * Sample from Beta distribution using Gamma samples
 *
 * @param {number} alpha - Beta alpha parameter
 * @param {number} beta - Beta beta parameter
 * @returns {number} Sample from Beta(alpha, beta)
 */
function betaSample(alpha, beta) {
  // Sample Beta(alpha, beta) using Gamma samples
  // Beta(a, b) = Gamma(a) / (Gamma(a) + Gamma(b))
  const x = gammaSample(alpha);
  const y = gammaSample(beta);
  return x / (x + y);
}

/**
 * Sample from Gamma distribution using Marsaglia-Tsang method
 *
 * @param {number} alpha - Gamma shape parameter
 * @returns {number} Sample from Gamma(alpha, 1)
 */
function gammaSample(alpha) {
  // For alpha < 1, use rejection method
  if (alpha < 1) {
    return gammaSample(alpha + 1) * Math.pow(Math.random(), 1 / alpha);
  }

  // Marsaglia-Tsang method for alpha >= 1
  const d = alpha - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x, v;
    do {
      x = gaussianSample();
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = Math.random();
    const x2 = x * x;

    if (u < 1 - 0.0331 * x2 * x2) {
      return d * v;
    }

    if (Math.log(u) < 0.5 * x2 + d * (1 - v + Math.log(v))) {
      return d * v;
    }
  }
}

/**
 * Sample from standard normal distribution using Box-Muller
 *
 * @returns {number} Sample from N(0, 1)
 */
function gaussianSample() {
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/**
 * Retrain the load balancer with latest data
 *
 * @param {number} windowDays - Training window in days
 * @returns {Object} Training results
 */
function retrain(windowDays = 30) {
  console.log(`Retraining load balancer optimizer (window: ${windowDays} days)...`);

  try {
    const output = execSync(
      `python3 ${OPTIMIZER_SCRIPT} --window ${windowDays}`,
      { encoding: 'utf-8', cwd: TOOLS_DIR }
    );

    console.log('Training output:');
    console.log(output);

    return {
      success: true,
      message: 'Retrained successfully',
      output: output
    };
  } catch (error) {
    return {
      success: false,
      message: error.message,
      output: error.stdout || error.stderr
    };
  }
}

/**
 * Get model recommendation for a specific task
 *
 * Convenience wrapper that includes additional context.
 *
 * @param {string} taskType - Type of task
 * @param {Object} options - Additional selection options
 * @returns {Object} Recommendation with model, reasoning, and full stats
 */
function recommendModel(taskType, options = {}) {
  const selection = selectModel({
    taskType,
    ...options
  });

  const state = loadStats();
  const affinities = state.task_affinities[taskType] || {};

  // Get top 3 models for this task type
  const topModels = Object.entries(affinities)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([model, affinity]) => ({
      model,
      affinity,
      stats: state.model_stats[model]
    }));

  return {
    selected: selection.model,
    confidence: selection.confidence,
    reasoning: selection.reasoning,
    stats: selection.stats,
    alternatives: selection.alternatives,
    taskType: taskType,
    topModelsForTask: topModels
  };
}

/**
 * Check if load balancer needs retraining
 *
 * @returns {boolean} True if stats are stale (>7 days old)
 */
function needsRetraining() {
  if (!fs.existsSync(STATS_FILE)) {
    return true;
  }

  const state = loadStats();
  const timestamp = new Date(state.timestamp);
  const age = Date.now() - timestamp.getTime();
  const sevenDays = 7 * 24 * 60 * 60 * 1000;

  return age > sevenDays;
}

/**
 * Get summary of load balancer state
 *
 * @returns {Object} Summary statistics
 */
function getSummary() {
  const state = loadStats();

  const models = Object.keys(state.model_stats);
  const totalExecutions = Object.values(state.model_stats)
    .reduce((sum, s) => sum + s.executions, 0);

  const avgQuality = Object.values(state.model_stats)
    .reduce((sum, s) => sum + s.avg_quality * s.executions, 0) / totalExecutions;

  const timestamp = new Date(state.timestamp);
  const age = Date.now() - timestamp.getTime();
  const ageDays = age / (24 * 60 * 60 * 1000);

  return {
    timestamp: state.timestamp,
    ageDays: ageDays,
    windowDays: state.window_days,
    totalModels: models.length,
    totalExecutions: totalExecutions,
    avgQuality: avgQuality,
    qualityThreshold: state.quality_threshold,
    costBudget: state.cost_budget,
    needsRetraining: needsRetraining(),
    topModels: Object.entries(state.model_stats)
      .sort((a, b) => b[1].avg_quality - a[1].avg_quality)
      .slice(0, 5)
      .map(([model, stats]) => ({
        model,
        quality: stats.avg_quality,
        executions: stats.executions,
        latency: stats.p95_latency,
        cost: stats.avg_cost
      }))
  };
}

module.exports = {
  // Model selection
  selectModel,
  recommendModel,

  // Statistics access
  getModelStats,
  getTaskAffinities,
  getLoadDistribution,
  getBanditParams,
  getSummary,

  // Training
  retrain,
  needsRetraining,

  // Paths
  LEARNING_DIR,
  STATS_FILE,
  OPTIMIZER_SCRIPT
};
