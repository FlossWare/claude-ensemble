/**
 * Multi-Model Orchestrator
 *
 * Thompson Sampling-based model selection integrated with PostgreSQL
 * model_performance materialized view for win/loss tracking.
 *
 * Replaces SQLite-based getModelMetrics() with PostgreSQL queries.
 */

const { getDB, getExecutionMonitor, OUTCOMES } = require(require('path').join(
  require('os').homedir(),
  '.claude',
  'learning',
  'postgres-adapter.js'
));

/**
 * Model Selection State
 */
class ModelSelector {
  constructor() {
    this.db = null;
    this.monitor = null;
    this.fallbackMode = false;
  }

  /**
   * Initialize database connection
   */
  async initialize() {
    try {
      this.db = getDB();
      this.monitor = getExecutionMonitor();

      // Test connection
      await this.db.query('SELECT 1');

      // Ensure materialized view exists
      await this.ensureModelPerformanceView();

      console.log('[orchestrator] PostgreSQL connection established');
    } catch (err) {
      console.warn('[orchestrator] PostgreSQL unavailable, falling back to simple selection:', err.message);
      this.fallbackMode = true;
    }
  }

  /**
   * Ensure model_performance materialized view exists
   */
  async ensureModelPerformanceView() {
    try {
      // Check if view exists
      const result = await this.db.query(`
        SELECT EXISTS (
          SELECT 1
          FROM pg_matviews
          WHERE schemaname = 'monitoring'
            AND matviewname = 'model_performance'
        ) as exists
      `);

      if (!result[0]?.exists) {
        console.warn('[orchestrator] model_performance view does not exist. Run schema/model_performance_view.sql first.');
        this.fallbackMode = true;
      }
    } catch (err) {
      console.warn('[orchestrator] Failed to check model_performance view:', err.message);
      this.fallbackMode = true;
    }
  }

  /**
   * Select best model using Thompson Sampling
   *
   * Queries monitoring.model_performance materialized view for:
   * - Thompson Sampling parameters (alpha, beta)
   * - Win rate, quality score, cost metrics
   *
   * Samples from Beta(alpha, beta) distribution and picks highest sample.
   *
   * @param {Object} options - Selection options
   * @param {string} options.task_type - Type of task (optional)
   * @param {number} options.max_cost - Max cost per request (optional)
   * @param {string[]} options.exclude_models - Models to exclude (optional)
   * @returns {Promise<string>} Selected model name
   */
  async selectModel(options = {}) {
    const {
      task_type = null,
      max_cost = null,
      exclude_models = []
    } = options;

    // Fallback to simple selection if PostgreSQL unavailable
    if (this.fallbackMode || !this.db) {
      return this.selectModelFallback(options);
    }

    try {
      // Query model_performance view
      let sql = `
        SELECT
          model,
          alpha,
          beta,
          thompson_expected_value,
          win_rate,
          avg_quality,
          cost_per_success,
          total_executions
        FROM monitoring.model_performance
        WHERE total_executions >= 3  -- Minimum 3 executions for statistical validity
      `;
      const params = [];
      let paramIdx = 1;

      // Filter by cost if specified
      if (max_cost !== null) {
        sql += ` AND cost_per_success <= $${paramIdx}`;
        params.push(max_cost);
        paramIdx++;
      }

      // Exclude models
      if (exclude_models.length > 0) {
        sql += ` AND model NOT IN (${exclude_models.map((_, i) => `$${paramIdx + i}`).join(', ')})`;
        params.push(...exclude_models);
        paramIdx += exclude_models.length;
      }

      sql += ' ORDER BY thompson_expected_value DESC';

      const candidates = await this.db.query(sql, params);

      if (candidates.length === 0) {
        console.warn('[orchestrator] No eligible models found, using fallback');
        return this.selectModelFallback(options);
      }

      // Thompson Sampling: sample from Beta(alpha, beta) for each candidate
      const samples = candidates.map(candidate => ({
        model: candidate.model,
        alpha: parseFloat(candidate.alpha),
        beta: parseFloat(candidate.beta),
        sample: this.sampleBeta(parseFloat(candidate.alpha), parseFloat(candidate.beta)),
        expected_value: parseFloat(candidate.thompson_expected_value),
        win_rate: parseFloat(candidate.win_rate),
        avg_quality: parseFloat(candidate.avg_quality),
        total_executions: parseInt(candidate.total_executions, 10)
      }));

      // Sort by sample (Thompson Sampling selection)
      samples.sort((a, b) => b.sample - a.sample);

      const selected = samples[0];

      console.log('[orchestrator] Model selection (Thompson Sampling):');
      console.log(`  Selected: ${selected.model}`);
      console.log(`  Sample: ${selected.sample.toFixed(3)} (α=${selected.alpha}, β=${selected.beta})`);
      console.log(`  Win rate: ${(selected.win_rate * 100).toFixed(1)}%`);
      console.log(`  Avg quality: ${selected.avg_quality.toFixed(3)}`);
      console.log(`  Total executions: ${selected.total_executions}`);

      // Show top 3 candidates for transparency
      if (samples.length > 1) {
        console.log('  Top candidates:');
        samples.slice(0, 3).forEach((s, i) => {
          console.log(`    ${i + 1}. ${s.model} (sample=${s.sample.toFixed(3)}, win_rate=${(s.win_rate * 100).toFixed(1)}%)`);
        });
      }

      return selected.model;
    } catch (err) {
      console.error('[orchestrator] Model selection failed:', err.message);
      console.error('[orchestrator] Falling back to simple selection');
      return this.selectModelFallback(options);
    }
  }

  /**
   * Sample from Beta distribution using Gamma distribution
   * Beta(α, β) = Gamma(α) / (Gamma(α) + Gamma(β))
   *
   * @param {number} alpha - Alpha parameter
   * @param {number} beta - Beta parameter
   * @returns {number} Sample from Beta(alpha, beta)
   */
  sampleBeta(alpha, beta) {
    const gammaAlpha = this.sampleGamma(alpha, 1);
    const gammaBeta = this.sampleGamma(beta, 1);
    return gammaAlpha / (gammaAlpha + gammaBeta);
  }

  /**
   * Sample from Gamma distribution using Marsaglia-Tsang method
   *
   * @param {number} shape - Shape parameter (k)
   * @param {number} scale - Scale parameter (θ)
   * @returns {number} Sample from Gamma(shape, scale)
   */
  sampleGamma(shape, scale) {
    // Handle edge cases
    if (shape < 1) {
      // Use transformation for shape < 1
      return this.sampleGamma(shape + 1, scale) * Math.pow(Math.random(), 1.0 / shape);
    }

    // Marsaglia-Tsang method for shape >= 1
    const d = shape - 1.0 / 3.0;
    const c = 1.0 / Math.sqrt(9.0 * d);

    while (true) {
      let x, v;

      do {
        x = this.randn(); // Standard normal
        v = 1.0 + c * x;
      } while (v <= 0);

      v = v * v * v;
      const u = Math.random();

      // Fast acceptance
      if (u < 1 - 0.0331 * x * x * x * x) {
        return d * v * scale;
      }

      // Slow acceptance
      if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
        return d * v * scale;
      }
    }
  }

  /**
   * Generate standard normal random variable (Box-Muller transform)
   * @returns {number} Sample from N(0, 1)
   */
  randn() {
    const u1 = Math.random();
    const u2 = Math.random();
    return Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  }

  /**
   * Fallback model selection (no PostgreSQL)
   * Uses simple round-robin across known models
   */
  selectModelFallback(options = {}) {
    const models = [
      'claude-opus-4',
      'claude-sonnet-4',
      'claude-haiku-4',
      'gpt-4o',
      'gemini-pro-1.5'
    ];

    const { exclude_models = [] } = options;
    const available = models.filter(m => !exclude_models.includes(m));

    if (available.length === 0) {
      console.warn('[orchestrator] No available models after exclusion, using claude-sonnet-4');
      return 'claude-sonnet-4';
    }

    // Simple random selection
    const selected = available[Math.floor(Math.random() * available.length)];
    console.log(`[orchestrator] Fallback selection: ${selected}`);
    return selected;
  }

  /**
   * Get model metrics (for compatibility with old code)
   *
   * @param {string} model - Model name
   * @returns {Promise<Object>} Model metrics
   */
  async getModelMetrics(model) {
    if (this.fallbackMode || !this.db) {
      return {
        model,
        alpha: 1,
        beta: 1,
        win_rate: 0.5,
        avg_quality: 0.5,
        total_executions: 0
      };
    }

    try {
      const result = await this.db.query(
        'SELECT * FROM monitoring.model_performance WHERE model = $1',
        [model]
      );

      if (result.length === 0) {
        // No data yet, return uniform prior
        return {
          model,
          alpha: 1,
          beta: 1,
          win_rate: 0.5,
          avg_quality: 0.5,
          total_executions: 0
        };
      }

      const row = result[0];
      return {
        model: row.model,
        alpha: parseFloat(row.alpha),
        beta: parseFloat(row.beta),
        win_rate: parseFloat(row.win_rate),
        avg_quality: parseFloat(row.avg_quality),
        avg_duration_ms: parseFloat(row.avg_duration_ms),
        cost_per_success: parseFloat(row.cost_per_success),
        efficiency_score: parseFloat(row.efficiency_score),
        total_executions: parseInt(row.total_executions, 10),
        thompson_expected_value: parseFloat(row.thompson_expected_value)
      };
    } catch (err) {
      console.error('[orchestrator] Failed to get model metrics:', err.message);
      return {
        model,
        alpha: 1,
        beta: 1,
        win_rate: 0.5,
        avg_quality: 0.5,
        total_executions: 0
      };
    }
  }

  /**
   * Record model execution result
   * Updates monitoring.execution_summary and refreshes model_performance view
   *
   * @param {Object} result - Execution result
   */
  async recordExecution(result) {
    if (this.fallbackMode || !this.monitor) {
      console.warn('[orchestrator] Cannot record execution (PostgreSQL unavailable)');
      return;
    }

    try {
      await this.monitor.logExecution(result);

      // Refresh materialized view (async, don't wait)
      this.db.query('REFRESH MATERIALIZED VIEW monitoring.model_performance').catch(err => {
        console.warn('[orchestrator] Failed to refresh model_performance view:', err.message);
      });
    } catch (err) {
      console.error('[orchestrator] Failed to record execution:', err.message);
    }
  }

  /**
   * Close database connection
   */
  async close() {
    if (this.db) {
      await this.db.close();
    }
  }
}

// Singleton instance
let _selector = null;

/**
 * Get singleton model selector instance
 */
async function getModelSelector() {
  if (!_selector) {
    _selector = new ModelSelector();
    await _selector.initialize();
  }
  return _selector;
}

/**
 * Select best model (convenience function)
 */
async function selectModel(options = {}) {
  const selector = await getModelSelector();
  return await selector.selectModel(options);
}

/**
 * Get model metrics (convenience function)
 */
async function getModelMetrics(model) {
  const selector = await getModelSelector();
  return await selector.getModelMetrics(model);
}

/**
 * Record execution (convenience function)
 */
async function recordExecution(result) {
  const selector = await getModelSelector();
  return await selector.recordExecution(result);
}

module.exports = {
  ModelSelector,
  getModelSelector,
  selectModel,
  getModelMetrics,
  recordExecution,
  OUTCOMES
};
