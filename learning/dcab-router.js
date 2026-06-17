/**
 * DCAB Router - Layer 2: Core Routing (Multi-Objective Thompson Sampling)
 *
 * Implements Thompson Sampling with 4 objectives per model:
 * - Success rate (0.5 weight)
 * - Quality score (0.3 weight)
 * - Speed (0.2 weight)
 * - Cost (informational, used for Pareto frontier)
 *
 * Database: learning.model_performance
 * Columns: model, success_alpha, success_beta, quality_alpha, quality_beta,
 *          speed_alpha, speed_beta, cost_alpha, cost_beta
 */

const { getDB } = require('./postgres-adapter');

class MultiObjectiveThompsonSampling {
  constructor(db = null) {
    this.db = db || getDB();
    this.weights = {
      success: 0.5,
      quality: 0.3,
      speed: 0.2
    };
    this.paretoBonus = 0.2;
  }

  /**
   * Sample from Beta distribution using Gamma ratio trick
   * Beta(α, β) = Gamma(α, 1) / (Gamma(α, 1) + Gamma(β, 1))
   */
  async sampleBeta(alpha, beta) {
    // Handle edge cases
    if (alpha <= 0 || beta <= 0) {
      return 0.5; // Uniform prior fallback
    }

    const gammaA = this._sampleGamma(alpha, 1);
    const gammaB = this._sampleGamma(beta, 1);

    return gammaA / (gammaA + gammaB);
  }

  /**
   * Sample from Gamma distribution using Marsaglia and Tsang's method
   * Gamma(α, θ) where θ is scale parameter (1 in our case)
   */
  _sampleGamma(alpha, theta) {
    // Special case for alpha < 1
    if (alpha < 1) {
      return this._sampleGamma(alpha + 1, theta) * Math.pow(Math.random(), 1 / alpha);
    }

    // Marsaglia and Tsang's method for alpha >= 1
    const d = alpha - 1/3;
    const c = 1 / Math.sqrt(9 * d);

    while (true) {
      let x, v, u;

      do {
        x = this._randomNormal(0, 1);
        v = 1 + c * x;
      } while (v <= 0);

      v = v * v * v;
      u = Math.random();

      const x2 = x * x;
      if (u < 1 - 0.0331 * x2 * x2) {
        return d * v * theta;
      }

      if (Math.log(u) < 0.5 * x2 + d * (1 - v + Math.log(v))) {
        return d * v * theta;
      }
    }
  }

  /**
   * Box-Muller transform for sampling from normal distribution
   */
  _randomNormal(mean, stddev) {
    const u1 = Math.random();
    const u2 = Math.random();
    const z0 = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    return z0 * stddev + mean;
  }

  /**
   * Get Beta distribution parameters for a model from database
   */
  async getModelPerformance(model) {
    const query = `
      SELECT
        success_alpha, success_beta,
        quality_alpha, quality_beta,
        speed_alpha, speed_beta,
        cost_alpha, cost_beta,
        total_samples
      FROM learning.model_performance
      WHERE model = $1
    `;

    const result = await this.db.query(query, [model]);

    if (result.rows.length === 0) {
      // Initialize with uniform prior (Beta(1, 1) for all objectives)
      return {
        success_alpha: 1, success_beta: 1,
        quality_alpha: 1, quality_beta: 1,
        speed_alpha: 1, speed_beta: 1,
        cost_alpha: 1, cost_beta: 1,
        total_samples: 0
      };
    }

    return result.rows[0];
  }

  /**
   * Compute Pareto frontier from sampled scores
   * A model is on the frontier if no other model dominates it on ALL objectives
   */
  _computeParetoFrontier(modelScores) {
    const frontier = [];

    for (const candidate of modelScores) {
      let isDominated = false;

      for (const other of modelScores) {
        if (candidate.model === other.model) continue;

        // Check if other dominates candidate
        // (other is better or equal on all objectives, strictly better on at least one)
        const dominatesSuccess = other.samples.success >= candidate.samples.success;
        const dominatesQuality = other.samples.quality >= candidate.samples.quality;
        const dominatesSpeed = other.samples.speed >= candidate.samples.speed;
        const dominatesCost = other.samples.cost <= candidate.samples.cost; // Lower is better

        const strictlyBetterSuccess = other.samples.success > candidate.samples.success;
        const strictlyBetterQuality = other.samples.quality > candidate.samples.quality;
        const strictlyBetterSpeed = other.samples.speed > candidate.samples.speed;
        const strictlyBetterCost = other.samples.cost < candidate.samples.cost;

        if (dominatesSuccess && dominatesQuality && dominatesSpeed && dominatesCost &&
            (strictlyBetterSuccess || strictlyBetterQuality || strictlyBetterSpeed || strictlyBetterCost)) {
          isDominated = true;
          break;
        }
      }

      if (!isDominated) {
        frontier.push(candidate.model);
      }
    }

    return frontier;
  }

  /**
   * Select best model using multi-objective Thompson Sampling
   *
   * @param {string[]} eligibleModels - Models to choose from
   * @param {object} options - { logScores: boolean }
   * @returns {object} { model, score, samples, allScores, paretoFrontier }
   */
  async selectModel(eligibleModels, options = {}) {
    const { logScores = true } = options;

    if (eligibleModels.length === 0) {
      throw new Error('No eligible models provided');
    }

    const modelScores = [];

    // Sample from Beta distributions for each model
    for (const model of eligibleModels) {
      const perf = await this.getModelPerformance(model);

      const samples = {
        success: await this.sampleBeta(perf.success_alpha, perf.success_beta),
        quality: await this.sampleBeta(perf.quality_alpha, perf.quality_beta),
        speed: await this.sampleBeta(perf.speed_alpha, perf.speed_beta),
        cost: await this.sampleBeta(perf.cost_alpha, perf.cost_beta)
      };

      // Scalarization: weighted sum of success, quality, speed
      const baseScore =
        this.weights.success * samples.success +
        this.weights.quality * samples.quality +
        this.weights.speed * samples.speed;

      modelScores.push({
        model,
        samples,
        baseScore,
        totalSamples: perf.total_samples
      });
    }

    // Compute Pareto frontier
    const paretoFrontier = this._computeParetoFrontier(modelScores);

    // Apply Pareto bonus
    for (const entry of modelScores) {
      entry.finalScore = entry.baseScore;
      if (paretoFrontier.includes(entry.model)) {
        entry.finalScore += this.paretoBonus;
        entry.onParetoFrontier = true;
      } else {
        entry.onParetoFrontier = false;
      }
    }

    // Select model with highest final score
    modelScores.sort((a, b) => b.finalScore - a.finalScore);
    const winner = modelScores[0];

    if (logScores) {
      console.log('[DCAB Layer 2] Thompson Sampling Results:');
      console.log('Pareto Frontier:', paretoFrontier);
      for (const entry of modelScores) {
        console.log(`  ${entry.model}: base=${entry.baseScore.toFixed(3)}, final=${entry.finalScore.toFixed(3)}, ` +
                    `pareto=${entry.onParetoFrontier}, samples=${entry.totalSamples}`);
        console.log(`    success=${entry.samples.success.toFixed(3)}, quality=${entry.samples.quality.toFixed(3)}, ` +
                    `speed=${entry.samples.speed.toFixed(3)}, cost=${entry.samples.cost.toFixed(3)}`);
      }
      console.log(`Selected: ${winner.model} (score=${winner.finalScore.toFixed(3)})`);
    }

    return {
      model: winner.model,
      score: winner.finalScore,
      baseScore: winner.baseScore,
      samples: winner.samples,
      onParetoFrontier: winner.onParetoFrontier,
      allScores: modelScores,
      paretoFrontier
    };
  }

  /**
   * Update model performance after task completion
   *
   * @param {string} model - Model that was used
   * @param {object} metrics - { success: boolean, quality: number, speed: number, cost: number }
   */
  async updatePerformance(model, metrics) {
    const { success, quality, speed, cost } = metrics;

    // Beta distribution update rule:
    // Success observation: α += 1 if success, β += 1 if failure
    // Quality/speed/cost (continuous [0,1]): α += observation, β += (1 - observation)

    const query = `
      INSERT INTO learning.model_performance (
        model,
        success_alpha, success_beta,
        quality_alpha, quality_beta,
        speed_alpha, speed_beta,
        cost_alpha, cost_beta,
        total_samples
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 1)
      ON CONFLICT (model) DO UPDATE SET
        success_alpha = learning.model_performance.success_alpha + $2,
        success_beta = learning.model_performance.success_beta + $3,
        quality_alpha = learning.model_performance.quality_alpha + $4,
        quality_beta = learning.model_performance.quality_beta + $5,
        speed_alpha = learning.model_performance.speed_alpha + $6,
        speed_beta = learning.model_performance.speed_beta + $7,
        cost_alpha = learning.model_performance.cost_alpha + $8,
        cost_beta = learning.model_performance.cost_beta + $9,
        total_samples = learning.model_performance.total_samples + 1,
        last_updated = NOW()
    `;

    const params = [
      model,
      success ? 1 : 0,           // success_alpha increment
      success ? 0 : 1,           // success_beta increment
      quality,                   // quality_alpha increment
      1 - quality,               // quality_beta increment
      speed,                     // speed_alpha increment
      1 - speed,                 // speed_beta increment
      cost,                      // cost_alpha increment
      1 - cost                   // cost_beta increment
    ];

    await this.db.query(query, params);

    console.log(`[DCAB Layer 2] Updated performance for ${model}:`, {
      success,
      quality: quality.toFixed(3),
      speed: speed.toFixed(3),
      cost: cost.toFixed(3)
    });
  }

  /**
   * Get current performance statistics for a model
   */
  async getStats(model) {
    const perf = await this.getModelPerformance(model);

    // Mean of Beta(α, β) = α / (α + β)
    return {
      model,
      totalSamples: perf.total_samples,
      expectedSuccess: perf.success_alpha / (perf.success_alpha + perf.success_beta),
      expectedQuality: perf.quality_alpha / (perf.quality_alpha + perf.quality_beta),
      expectedSpeed: perf.speed_alpha / (perf.speed_alpha + perf.speed_beta),
      expectedCost: perf.cost_alpha / (perf.cost_alpha + perf.cost_beta),
      // Variance of Beta(α, β) = αβ / ((α+β)²(α+β+1))
      successVariance: this._betaVariance(perf.success_alpha, perf.success_beta),
      qualityVariance: this._betaVariance(perf.quality_alpha, perf.quality_beta),
      speedVariance: this._betaVariance(perf.speed_alpha, perf.speed_beta),
      costVariance: this._betaVariance(perf.cost_alpha, perf.cost_beta)
    };
  }

  _betaVariance(alpha, beta) {
    const sum = alpha + beta;
    return (alpha * beta) / (sum * sum * (sum + 1));
  }
}

module.exports = { MultiObjectiveThompsonSampling };
