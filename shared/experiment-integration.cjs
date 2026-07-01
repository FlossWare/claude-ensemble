/**
 * Experiment Manager Integration Layer
 *
 * Wires experiment-manager.cjs into active components:
 * 1. Model rotation (canary rollout experiments)
 * 2. Weighted voting (algorithm comparison)
 * 3. Learning system (formal A/B tests)
 *
 * This layer provides high-level experiment patterns that map
 * real system behaviors to the experiment framework.
 *
 * Created: 2026-07-01
 * Issue: #267
 */

const { runExperiment, compareResults, recordExperiment, getExperimentHistory } = require('./experiment-manager.cjs');
const { applyRotationPolicy, recordExecution, getRotationStatus } = require('./model-rotation.cjs');
const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');

// ============================================================================
// CONFIGURATION
// ============================================================================

const EXPERIMENT_TYPES = {
  MODEL_ROLLOUT: 'model_rollout',
  VOTING_ALGORITHM: 'voting_algorithm',
  ROUTING_STRATEGY: 'routing_strategy',
  QUALITY_THRESHOLD: 'quality_threshold',
};

// ============================================================================
// MODEL ROLLOUT EXPERIMENTS
// ============================================================================

/**
 * Run A/B experiment comparing two rollout strategies
 *
 * Baseline: Current canary → ramp → full progression
 * Treatment: Alternative progression (e.g., faster rollout)
 *
 * @param {Object} config
 * @param {string} config.model - Model to test
 * @param {Object} config.baseline - Baseline rollout config
 * @param {Object} config.treatment - Treatment rollout config
 * @param {number} config.samples - Number of executions to collect per arm
 * @returns {Promise<Object>} Experiment result with verdict
 *
 * Example:
 *   const result = await runRolloutExperiment({
 *     model: 'opus-3.5',
 *     baseline: { stage: 'canary', duration_days: 3 },
 *     treatment: { stage: 'canary', duration_days: 1 },
 *     samples: 20
 *   });
 */
async function runRolloutExperiment(config) {
  const { model, baseline, treatment, samples = 20 } = config;

  const collector = async (rolloutConfig) => {
    // Simulate executions under this rollout config
    // In production, this would collect real execution metrics
    const metrics = [];

    for (let i = 0; i < samples; i++) {
      // Mock execution: quality score varies by rollout aggressiveness
      const qualityVariance = rolloutConfig.duration_days < 2 ? 0.05 : 0.02;
      const quality = 0.75 + (Math.random() * qualityVariance * 2 - qualityVariance);

      metrics.push(quality);

      // Record in rotation tracker
      await recordExecution(model, quality >= 0.70, quality);
    }

    return metrics;
  };

  const result = await runExperiment({
    name: `rollout_${model}_${Date.now()}`,
    hypothesis: `Faster rollout (${treatment.duration_days}d) maintains quality vs baseline (${baseline.duration_days}d)`,
    metric: 'quality_score',
    baseline,
    treatment,
    collector,
    success_criteria: {
      min_improvement_pct: 0, // We accept no degradation
      alpha: 0.05,
    },
    metadata: {
      model,
      experiment_type: EXPERIMENT_TYPES.MODEL_ROLLOUT,
    },
  });

  return result;
}

// ============================================================================
// VOTING ALGORITHM EXPERIMENTS
// ============================================================================

/**
 * Compare baseline weighted voting vs treatment algorithm
 *
 * @param {Object} config
 * @param {Array<Object>} config.votes - Test votes to evaluate
 * @param {string} config.taskType - Task type for voting
 * @param {Object} config.baselineOptions - Baseline voting options
 * @param {Object} config.treatmentOptions - Treatment voting options
 * @param {number} config.iterations - Number of voting iterations per arm
 * @returns {Promise<Object>} Experiment result with verdict
 *
 * Example:
 *   const result = await runVotingExperiment({
 *     votes: [{ model: 'opus', output: 'A', confidence: 0.9 }, ...],
 *     taskType: 'code_review',
 *     baselineOptions: { algorithm: 'standard' },
 *     treatmentOptions: { algorithm: 'with_disagreement_detection' },
 *     iterations: 30
 *   });
 */
async function runVotingExperiment(config) {
  const { votes, taskType, baselineOptions = {}, treatmentOptions = {}, iterations = 30 } = config;

  const collector = async (votingOptions) => {
    const qualityScores = [];

    for (let i = 0; i < iterations; i++) {
      // Run voting with this configuration (with explainability for first and last iteration)
      const shouldExplain = i === 0 || i === iterations - 1;
      const result = await runWeightedVotingWithExplain(votes, taskType, {
        ...votingOptions,
        explain: shouldExplain,
        explainFormat: 'json',
      });

      if (result.voting_result?.status === 'success') {
        // Extract quality metric (e.g., confidence score)
        const quality = result.voting_result.winner_confidence || 0;
        qualityScores.push(quality);
      } else {
        // Failed voting = 0 quality
        qualityScores.push(0);
      }
    }

    return qualityScores;
  };

  const result = await runExperiment({
    name: `voting_${taskType}_${Date.now()}`,
    hypothesis: `Treatment voting algorithm improves consensus quality vs baseline`,
    metric: 'winner_confidence',
    baseline: baselineOptions,
    treatment: treatmentOptions,
    collector,
    success_criteria: {
      min_improvement_pct: 3,
      alpha: 0.05,
    },
    metadata: {
      task_type: taskType,
      experiment_type: EXPERIMENT_TYPES.VOTING_ALGORITHM,
    },
  });

  return result;
}

// ============================================================================
// ROUTING STRATEGY EXPERIMENTS
// ============================================================================

/**
 * Compare baseline routing strategy vs treatment
 *
 * @param {Object} config
 * @param {string} config.taskType - Task type for routing
 * @param {Function} config.baselineRouter - Baseline routing function(task) => model
 * @param {Function} config.treatmentRouter - Treatment routing function(task) => model
 * @param {Array<Object>} config.tasks - Test tasks to route
 * @returns {Promise<Object>} Experiment result with verdict
 *
 * Example:
 *   const result = await runRoutingExperiment({
 *     taskType: 'code_generation',
 *     baselineRouter: (task) => 'opus',
 *     treatmentRouter: (task) => task.language === 'java' ? 'deepseek-coder' : 'opus',
 *     tasks: [{ language: 'java', prompt: 'Generate class' }, ...]
 *   });
 */
async function runRoutingExperiment(config) {
  const { taskType, baselineRouter, treatmentRouter, tasks } = config;

  const collector = async (router) => {
    const qualityScores = [];

    for (const task of tasks) {
      const model = router(task);

      // Simulate execution quality for this model+task
      // In production, this would execute the task and measure quality
      const baseQuality = 0.70;
      const modelBonus = model.includes('deepseek') && task.language === 'java' ? 0.15 : 0;
      const quality = Math.min(1.0, baseQuality + modelBonus + (Math.random() * 0.05 - 0.025));

      qualityScores.push(quality);

      // Record execution
      await recordExecution(model, quality >= 0.70, quality);
    }

    return qualityScores;
  };

  const result = await runExperiment({
    name: `routing_${taskType}_${Date.now()}`,
    hypothesis: `Treatment router improves task-specific quality vs baseline`,
    metric: 'task_quality',
    baseline: baselineRouter,
    treatment: treatmentRouter,
    collector,
    success_criteria: {
      min_improvement_pct: 5,
      alpha: 0.05,
    },
    metadata: {
      task_type: taskType,
      experiment_type: EXPERIMENT_TYPES.ROUTING_STRATEGY,
      task_count: tasks.length,
    },
  });

  return result;
}

// ============================================================================
// QUALITY THRESHOLD EXPERIMENTS
// ============================================================================

/**
 * Compare baseline quality threshold vs treatment threshold
 *
 * Tests whether changing acceptance thresholds improves system outcomes.
 *
 * @param {Object} config
 * @param {number} config.baselineThreshold - Baseline threshold (0.0-1.0)
 * @param {number} config.treatmentThreshold - Treatment threshold (0.0-1.0)
 * @param {Array<Object>} config.samples - Sample outputs with quality scores
 * @returns {Promise<Object>} Experiment result with verdict
 *
 * Example:
 *   const result = await runQualityThresholdExperiment({
 *     baselineThreshold: 0.70,
 *     treatmentThreshold: 0.75,
 *     samples: [{ quality: 0.72, correct: true }, ...]
 *   });
 */
async function runQualityThresholdExperiment(config) {
  const { baselineThreshold, treatmentThreshold, samples } = config;

  const collector = async (threshold) => {
    const accuracyScores = [];

    for (const sample of samples) {
      // Apply threshold: accept if quality >= threshold
      const accepted = sample.quality >= threshold;

      // Accuracy = did we make the right decision?
      // If accepted, check correctness; if rejected, inverse correctness
      const accuracy = accepted === sample.correct ? 1 : 0;

      accuracyScores.push(accuracy);
    }

    return accuracyScores;
  };

  const result = await runExperiment({
    name: `threshold_${Date.now()}`,
    hypothesis: `Threshold ${treatmentThreshold} improves accuracy vs ${baselineThreshold}`,
    metric: 'decision_accuracy',
    baseline: baselineThreshold,
    treatment: treatmentThreshold,
    collector,
    success_criteria: {
      min_improvement_pct: 2,
      alpha: 0.05,
    },
    metadata: {
      experiment_type: EXPERIMENT_TYPES.QUALITY_THRESHOLD,
      sample_count: samples.length,
    },
  });

  return result;
}

// ============================================================================
// EXPERIMENT UTILITIES
// ============================================================================

/**
 * Get experiment history filtered by type
 *
 * @param {string} experimentType - One of EXPERIMENT_TYPES
 * @param {number} limit - Max results
 * @returns {Promise<Array<Object>>} Experiment records
 */
async function getExperimentsByType(experimentType, limit = 10) {
  const allExperiments = await getExperimentHistory({ limit: 100 });

  return allExperiments
    .filter(exp => {
      try {
        const metadata = typeof exp.metadata === 'string'
          ? JSON.parse(exp.metadata)
          : exp.metadata;
        return metadata.experiment_type === experimentType;
      } catch {
        return false;
      }
    })
    .slice(0, limit);
}

/**
 * Get experiment success rate by type
 *
 * @param {string} experimentType - One of EXPERIMENT_TYPES
 * @returns {Promise<Object>} Success rate statistics
 */
async function getExperimentSuccessRate(experimentType) {
  const experiments = await getExperimentsByType(experimentType, 100);

  const total = experiments.length;
  const kept = experiments.filter(e => e.verdict === 'keep').length;
  const removed = experiments.filter(e => e.verdict === 'remove').length;
  const inconclusive = experiments.filter(e => e.verdict === 'inconclusive').length;

  return {
    type: experimentType,
    total,
    kept,
    removed,
    inconclusive,
    success_rate: total > 0 ? kept / total : 0,
  };
}

/**
 * Generate experiment summary report
 *
 * @returns {Promise<Object>} Summary of all experiments
 */
async function generateExperimentSummary() {
  const allExperiments = await getExperimentHistory({ limit: 1000 });

  const byType = {};
  for (const type of Object.values(EXPERIMENT_TYPES)) {
    byType[type] = await getExperimentSuccessRate(type);
  }

  const recentWins = allExperiments
    .filter(e => e.verdict === 'keep')
    .slice(0, 5)
    .map(e => ({
      name: e.name,
      hypothesis: e.hypothesis,
      improvement_pct: e.improvement_pct,
      p_value: e.p_value,
      created_at: e.created_at,
    }));

  return {
    total_experiments: allExperiments.length,
    by_type: byType,
    recent_wins: recentWins,
    overall_success_rate: allExperiments.length > 0
      ? allExperiments.filter(e => e.verdict === 'keep').length / allExperiments.length
      : 0,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Experiment types
  EXPERIMENT_TYPES,

  // High-level experiment runners
  runRolloutExperiment,
  runVotingExperiment,
  runRoutingExperiment,
  runQualityThresholdExperiment,

  // Utilities
  getExperimentsByType,
  getExperimentSuccessRate,
  generateExperimentSummary,

  // Re-export core functions for convenience
  runExperiment,
  compareResults,
  recordExperiment,
  getExperimentHistory,
};
