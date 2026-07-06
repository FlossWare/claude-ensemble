/**
 * Auto-Optimizer for Workflow Configuration
 *
 * Uses ML predictions to automatically optimize workflow parameters:
 * - Worker count (cost vs quality tradeoff)
 * - Model selection (based on task complexity)
 * - Timeout values (based on predicted duration)
 * - Resource allocation (based on predicted load)
 *
 * Integrates with prediction-wrapper.cjs for ML-powered decisions.
 *
 * Created: 2026-07-05
 */

const { predictWorkflow } = require('./prediction-wrapper.cjs');

/**
 * Optimize worker count for cost-quality tradeoff
 *
 * @param {Object} config - Base workflow configuration
 * @param {Object} options - Optimization options
 * @param {string} options.objective - 'cost' | 'quality' | 'balanced' (default: 'balanced')
 * @param {number} options.minWorkers - Minimum workers (default: 2)
 * @param {number} options.maxWorkers - Maximum workers (default: 8)
 * @param {number} options.targetQuality - Minimum quality threshold (default: 0.8)
 * @param {number} options.maxCost - Maximum cost threshold (default: Infinity)
 * @returns {Promise<Object>} Optimized configuration
 */
async function optimizeWorkerCount(config, options = {}) {
  const {
    objective = 'balanced',
    minWorkers = 2,
    maxWorkers = 8,
    targetQuality = 0.8,
    maxCost = Infinity,
  } = options;

  const candidates = [];

  // Evaluate worker counts from min to max
  for (let workers = minWorkers; workers <= maxWorkers; workers++) {
    const testConfig = { ...config, total_workers: workers };

    try {
      const prediction = await predictWorkflow(testConfig);

      // Calculate score based on objective
      let score;
      if (objective === 'cost') {
        // Minimize cost while meeting quality threshold
        score =
          prediction.predicted.quality_score >= targetQuality
            ? -prediction.predicted.cost_usd
            : -Infinity;
      } else if (objective === 'quality') {
        // Maximize quality while staying under cost threshold
        score =
          prediction.predicted.cost_usd <= maxCost
            ? prediction.predicted.quality_score
            : -Infinity;
      } else {
        // Balanced: maximize quality per dollar
        const qualityPerDollar =
          prediction.predicted.cost_usd > 0
            ? prediction.predicted.quality_score / prediction.predicted.cost_usd
            : 0;
        score = qualityPerDollar;
      }

      candidates.push({
        workers,
        prediction,
        score,
      });
    } catch (err) {
      console.error(
        `Failed to predict for ${workers} workers: ${err.message}`
      );
    }
  }

  if (candidates.length === 0) {
    throw new Error('No valid worker count candidates found');
  }

  // Find best candidate
  const best = candidates.reduce((prev, current) =>
    current.score > prev.score ? current : prev
  );

  return {
    recommended_workers: best.workers,
    predicted_duration_ms: best.prediction.predicted.duration_ms,
    predicted_cost_usd: best.prediction.predicted.cost_usd,
    predicted_quality: best.prediction.predicted.quality_score,
    confidence: best.prediction.predicted.confidence,
    objective,
    candidates: candidates.map((c) => ({
      workers: c.workers,
      cost: c.prediction.predicted.cost_usd,
      quality: c.prediction.predicted.quality_score,
      score: c.score,
    })),
  };
}

/**
 * Select optimal models based on task complexity
 *
 * @param {Object} config - Workflow configuration
 * @param {Object} options - Selection options
 * @param {string[]} options.availableModels - Available model list (default: all)
 * @param {number} options.maxModels - Max models to select (default: 3)
 * @param {number} options.minQuality - Minimum quality threshold (default: 0.8)
 * @returns {Promise<Object>} Recommended model configuration
 */
async function selectOptimalModels(config, options = {}) {
  const {
    availableModels = [
      'opus',
      'sonnet',
      'haiku',
      'gpt4o',
      'gemini',
      'fable',
      'automl',
    ],
    maxModels = 3,
    minQuality = 0.8,
  } = options;

  // Task complexity heuristics
  const taskLength = config.task_description?.length || 0;
  const isComplex = taskLength > 500 || /research|analyze|reverse.?engineer/i.test(config.task_description);

  // Model tier selection based on complexity
  let recommendedModels;

  if (isComplex) {
    // High complexity: prefer powerful models
    recommendedModels = availableModels
      .filter((m) => ['opus', 'gpt4o', 'sonnet', 'gemini'].includes(m))
      .slice(0, maxModels);

    if (recommendedModels.length === 0) {
      recommendedModels = availableModels.slice(0, maxModels);
    }
  } else {
    // Low complexity: prefer efficient models
    recommendedModels = availableModels
      .filter((m) => ['haiku', 'fable', 'automl', 'sonnet'].includes(m))
      .slice(0, maxModels);

    if (recommendedModels.length === 0) {
      recommendedModels = availableModels.slice(0, maxModels);
    }
  }

  // Verify with prediction
  const testConfig = {
    ...config,
    models: recommendedModels,
  };

  const prediction = await predictWorkflow(testConfig);

  // Fallback to more powerful models if quality too low
  if (prediction.predicted.quality_score < minQuality && !isComplex) {
    const upgradedModels = availableModels
      .filter((m) => ['opus', 'gpt4o', 'sonnet'].includes(m))
      .slice(0, maxModels);

    const upgradedConfig = {
      ...config,
      models: upgradedModels,
    };

    const upgradedPrediction = await predictWorkflow(upgradedConfig);

    return {
      recommended_models: upgradedModels,
      predicted_quality: upgradedPrediction.predicted.quality_score,
      predicted_cost_usd: upgradedPrediction.predicted.cost_usd,
      confidence: upgradedPrediction.predicted.confidence,
      reason: 'upgraded_for_quality',
      task_complexity: 'high',
    };
  }

  return {
    recommended_models: recommendedModels,
    predicted_quality: prediction.predicted.quality_score,
    predicted_cost_usd: prediction.predicted.cost_usd,
    confidence: prediction.predicted.confidence,
    reason: isComplex ? 'high_complexity' : 'low_complexity',
    task_complexity: isComplex ? 'high' : 'low',
  };
}

/**
 * Calculate optimal timeout based on predicted duration
 *
 * @param {Object} config - Workflow configuration
 * @param {Object} options - Timeout options
 * @param {number} options.safetyFactor - Multiplier for predicted duration (default: 1.5)
 * @param {number} options.minTimeout - Minimum timeout in ms (default: 30000)
 * @param {number} options.maxTimeout - Maximum timeout in ms (default: 600000)
 * @returns {Promise<Object>} Recommended timeout configuration
 */
async function calculateOptimalTimeout(config, options = {}) {
  const {
    safetyFactor = 1.5,
    minTimeout = 30000,
    maxTimeout = 600000,
  } = options;

  const prediction = await predictWorkflow(config);

  // Apply safety factor
  let recommendedTimeout = Math.round(
    prediction.predicted.duration_ms * safetyFactor
  );

  // Clamp to min/max
  recommendedTimeout = Math.max(minTimeout, recommendedTimeout);
  recommendedTimeout = Math.min(maxTimeout, recommendedTimeout);

  return {
    recommended_timeout_ms: recommendedTimeout,
    predicted_duration_ms: prediction.predicted.duration_ms,
    safety_factor: safetyFactor,
    confidence: prediction.predicted.confidence,
  };
}

/**
 * Auto-optimize entire workflow configuration
 *
 * @param {Object} config - Base workflow configuration
 * @param {Object} options - Optimization options
 * @returns {Promise<Object>} Fully optimized configuration
 */
async function autoOptimizeWorkflow(config, options = {}) {
  const {
    optimizeWorkers = true,
    optimizeModels = true,
    optimizeTimeout = true,
    objective = 'balanced',
  } = options;

  const optimizations = {};

  // Optimize worker count
  if (optimizeWorkers) {
    optimizations.workers = await optimizeWorkerCount(config, {
      objective,
      ...options,
    });
  }

  // Optimize model selection
  if (optimizeModels) {
    optimizations.models = await selectOptimalModels(config, options);
  }

  // Optimize timeout
  if (optimizeTimeout) {
    const timeoutConfig = {
      ...config,
      total_workers: optimizations.workers?.recommended_workers || config.total_workers,
      models: optimizations.models?.recommended_models || config.models,
    };
    optimizations.timeout = await calculateOptimalTimeout(
      timeoutConfig,
      options
    );
  }

  // Build optimized configuration
  const optimizedConfig = {
    ...config,
  };

  if (optimizations.workers) {
    optimizedConfig.total_workers = optimizations.workers.recommended_workers;
  }

  if (optimizations.models) {
    optimizedConfig.models = optimizations.models.recommended_models;
  }

  if (optimizations.timeout) {
    optimizedConfig.timeout_ms = optimizations.timeout.recommended_timeout_ms;
  }

  return {
    optimized_config: optimizedConfig,
    optimizations,
    summary: {
      workers: optimizations.workers?.recommended_workers,
      models: optimizations.models?.recommended_models,
      timeout_ms: optimizations.timeout?.recommended_timeout_ms,
      predicted_cost_usd:
        optimizations.workers?.predicted_cost_usd ||
        optimizations.models?.predicted_cost_usd,
      predicted_quality:
        optimizations.workers?.predicted_quality ||
        optimizations.models?.predicted_quality,
    },
  };
}

/**
 * Get optimization recommendations as human-readable text
 *
 * @param {Object} config - Base workflow configuration
 * @param {Object} options - Optimization options
 * @returns {Promise<string>} Recommendations text
 */
async function getOptimizationRecommendations(config, options = {}) {
  const result = await autoOptimizeWorkflow(config, options);

  const lines = [];
  lines.push('🤖 Auto-Optimization Recommendations');
  lines.push('');

  if (result.optimizations.workers) {
    const w = result.optimizations.workers;
    lines.push(
      `Workers: ${w.recommended_workers} (predicted: $${w.predicted_cost_usd.toFixed(4)}, quality: ${(w.predicted_quality * 100).toFixed(1)}%)`
    );
  }

  if (result.optimizations.models) {
    const m = result.optimizations.models;
    lines.push(
      `Models: ${m.recommended_models.join(', ')} (${m.reason}, complexity: ${m.task_complexity})`
    );
  }

  if (result.optimizations.timeout) {
    const t = result.optimizations.timeout;
    lines.push(
      `Timeout: ${(t.recommended_timeout_ms / 1000).toFixed(1)}s (predicted: ${(t.predicted_duration_ms / 1000).toFixed(1)}s × ${t.safety_factor})`
    );
  }

  lines.push('');
  lines.push('Use autoOptimizeWorkflow() to apply these settings.');

  return lines.join('\n');
}

module.exports = {
  optimizeWorkerCount,
  selectOptimalModels,
  calculateOptimalTimeout,
  autoOptimizeWorkflow,
  getOptimizationRecommendations,
};
