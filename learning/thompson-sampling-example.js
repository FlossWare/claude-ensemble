/**
 * Thompson Sampling Model Selection with Diversity Monitoring
 *
 * Complete example showing how to integrate diversity monitoring
 * with Thompson Sampling model selection.
 *
 * Usage:
 *   const { selectModel, recordOutcome } = require('./thompson-sampling-example');
 *   const model = await selectModel();
 *   // ... use model ...
 *   await recordOutcome(model, success, reward);
 */

const { getStrategyPerformance } = require('./postgres-adapter');
const { getDiversityMonitor } = require('./diversity-monitor');

/**
 * Select a model using Thompson Sampling
 * Samples from Beta distribution for each model's performance
 *
 * @param {Array<string>} models - Available models (default: standard set)
 * @returns {Promise<string>} Selected model name
 */
async function selectModel(models = ['opus', 'sonnet', 'haiku', 'fable', 'gpt4o', 'gemini']) {
  const strategyPerf = getStrategyPerformance();

  // Get current Beta distribution parameters for each model
  const performances = await Promise.all(
    models.map(async model => {
      const stats = await strategyPerf.getStats(model);
      if (!stats) {
        // New model: use uniform prior (alpha=1, beta=1)
        return {
          model,
          alpha: 1,
          beta: 1,
        };
      }
      return {
        model,
        alpha: stats.alpha,
        beta: stats.beta,
      };
    })
  );

  // Thompson Sampling: sample from each Beta distribution
  const samples = performances.map(p => ({
    model: p.model,
    sample: sampleBeta(p.alpha, p.beta),
  }));

  // Select model with highest sample (exploitation with exploration)
  samples.sort((a, b) => b.sample - a.sample);
  const selectedModel = samples[0].model;

  // IMPORTANT: Track selection AFTER Thompson Sampling
  const monitor = getDiversityMonitor();
  await monitor.trackSelection(selectedModel);

  return selectedModel;
}

/**
 * Record outcome of model usage
 * Updates Beta distribution parameters
 *
 * @param {string} model - Model that was used
 * @param {boolean} success - Whether the task succeeded
 * @param {number} reward - Reward value (0.0 to 1.0)
 * @returns {Promise<void>}
 */
async function recordOutcome(model, success, reward) {
  const strategyPerf = getStrategyPerformance();

  // Update strategy performance
  await strategyPerf.record(model, success, reward);
}

/**
 * Sample from Beta distribution using Gamma sampling
 * @param {number} alpha - Alpha parameter
 * @param {number} beta - Beta parameter
 * @returns {number} Sample value between 0 and 1
 */
function sampleBeta(alpha, beta) {
  const gammaA = sampleGamma(alpha);
  const gammaB = sampleGamma(beta);
  return gammaA / (gammaA + gammaB);
}

/**
 * Sample from Gamma distribution using Marsaglia and Tsang method
 * @param {number} shape - Shape parameter (alpha)
 * @returns {number} Sample value
 */
function sampleGamma(shape) {
  if (shape < 1) {
    // Use shape augmentation
    return sampleGamma(shape + 1) * Math.pow(Math.random(), 1 / shape);
  }

  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x, v;
    do {
      x = randomNormal(0, 1);
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
 * Sample from standard normal distribution using Box-Muller transform
 * @param {number} mean - Mean
 * @param {number} stddev - Standard deviation
 * @returns {number} Sample value
 */
function randomNormal(mean, stddev) {
  const u1 = Math.random();
  const u2 = Math.random();
  const z0 = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return z0 * stddev + mean;
}

/**
 * Get current diversity distribution
 * @returns {Promise<Object>} Model distribution
 */
async function getCurrentDistribution() {
  const monitor = getDiversityMonitor();
  return await monitor.getCurrentDistribution();
}

/**
 * Get recent diversity alerts
 * @param {number} limit - Max number of alerts
 * @returns {Promise<Array>} Recent alerts
 */
async function getRecentAlerts(limit = 10) {
  const monitor = getDiversityMonitor();
  return await monitor.getRecentAlerts(limit);
}

/**
 * Get rotation priority (least used models first)
 * Use when diversity alert triggers to force rotation
 * @returns {Promise<Array<string>>} Models sorted by priority
 */
async function getRotationPriority() {
  const monitor = getDiversityMonitor();
  return await monitor.getRotationPriority();
}

module.exports = {
  selectModel,
  recordOutcome,
  getCurrentDistribution,
  getRecentAlerts,
  getRotationPriority,
};
