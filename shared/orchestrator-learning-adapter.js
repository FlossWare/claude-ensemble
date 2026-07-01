/**
 * Orchestrator Learning Adapter
 *
 * Connects orchestrator to PostgreSQL learning database for:
 * 1. Thompson Sampling model selection (AI-driven routing)
 * 2. Quality feedback recording (learning from outcomes)
 * 3. Adaptive routing (improves over time)
 */

import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

export class OrchestratorLearningAdapter {
  constructor() {
    this.pool = null;
    this.connected = false;
    this._adapterLoaded = false;
  }

  /**
   * Lazily load the CommonJS postgres-adapter using dynamic import
   */
  async _loadAdapter() {
    if (this._adapterLoaded) return;

    try {
      const adapterPath = path.join(os.homedir(), '.claude', 'learning', 'postgres-adapter.js');
      const adapter = await import(adapterPath);
      // CommonJS modules via dynamic import: exports are on .default or directly on adapter
      this.pool = adapter.default?.pool || adapter.pool;

      // Verify pool was successfully loaded
      if (!this.pool) {
        throw new Error('postgres-adapter.js does not export pool - check module.exports structure');
      }

      this._adapterLoaded = true;
    } catch (error) {
      console.error('[orchestrator-learning] Failed to load postgres-adapter:', error.message);
      throw error;
    }
  }

  /**
   * Connect to learning database (now a no-op, pool auto-connects)
   */
  async connect() {
    if (this.connected) return;

    try {
      // Ensure adapter is loaded
      await this._loadAdapter();

      // Test connection by running a simple query
      await this.pool.query('SELECT 1');
      this.connected = true;
      console.log('[orchestrator-learning] Connected to learning database pool');
    } catch (error) {
      console.error('[orchestrator-learning] Connection failed:', error.message);
      this.connected = false;
    }
  }

  /**
   * Get model performance via Thompson Sampling
   *
   * Queries learning.strategy_performance for model quality stats,
   * then samples from Beta(alpha, beta) distribution for exploration/exploitation
   *
   * @param {string} taskType - Type of task (code-review, general, etc.)
   * @param {Array<string>} availableModels - Models to choose from
   * @param {number} count - How many models to select (default 3)
   * @returns {Promise<Array<string>>} Selected models ranked by sampled quality
   */
  async selectModelsThompson(taskType, availableModels, count = 3) {
    if (!this.connected) await this.connect();
    if (!this.connected) {
      // Fallback: random selection if DB unavailable
      return this._randomSelect(availableModels, count);
    }

    try {
      // Query strategy performance for each available model
      const modelStats = await Promise.all(
        availableModels.map(async (model) => {
          const result = await this.pool.query(`
            SELECT
              strategy,
              successes,
              failures,
              alpha,
              beta,
              avg_reward
            FROM learning.strategy_performance
            WHERE strategy = $1
          `, [model]);

          if (result.rows.length === 0) {
            // No history: use uniform prior Beta(1, 1)
            return {
              model,
              alpha: 1,
              beta: 1,
              sample: this._sampleBeta(1, 1),
              avgReward: 0
            };
          }

          const stats = result.rows[0];
          const sample = this._sampleBeta(stats.alpha, stats.beta);

          return {
            model,
            alpha: stats.alpha,
            beta: stats.beta,
            sample,
            avgReward: parseFloat(stats.avg_reward) || 0
          };
        })
      );

      // Sort by Thompson sample (exploration/exploitation balance)
      modelStats.sort((a, b) => b.sample - a.sample);

      // Return top N models
      const selected = modelStats.slice(0, count).map(m => m.model);

      console.log('[orchestrator-learning] Thompson Sampling selected:', selected);
      return selected;
    } catch (error) {
      console.error('[orchestrator-learning] Thompson Sampling failed:', error.message);
      return this._randomSelect(availableModels, count);
    }
  }

  /**
   * Sample from Beta distribution using Johnk's algorithm
   *
   * @param {number} alpha - Beta parameter (successes + 1)
   * @param {number} beta - Beta parameter (failures + 1)
   * @returns {number} Sample in [0, 1]
   */
  _sampleBeta(alpha, beta) {
    let u, v, x, y;
    do {
      u = Math.max(Math.random(), Number.EPSILON);
      v = Math.max(Math.random(), Number.EPSILON);
      x = Math.pow(u, 1 / alpha);
      y = Math.pow(v, 1 / beta);
    } while (x + y > 1);

    return x / (x + y);
  }

  /**
   * Random selection fallback
   */
  _randomSelect(models, count) {
    const shuffled = [...models].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, count);
  }

  /**
   * Record feedback from task execution
   *
   * Updates learning.strategy_performance with outcome
   *
   * @param {string} model - Model that executed the task
   * @param {Object} feedback - Task outcome
   * @param {boolean} feedback.success - Task succeeded
   * @param {number} feedback.quality - Quality score 0-1
   * @param {number} feedback.cost - Cost in USD
   * @param {number} feedback.duration - Duration in ms
   * @param {string} feedback.taskType - Type of task
   * @param {number} feedback.confidence - Confidence score 0-1 (optional)
   * @param {Object} feedback.detailed - Optional detailed execution data for execution_log (Issue #252)
   */
  async recordFeedback(model, feedback) {
    if (!this.connected) await this.connect();
    if (!this.connected) {
      console.warn('[orchestrator-learning] Cannot record feedback, DB unavailable');
      return;
    }

    try {
      const { success, quality = 0.5, cost = 0, duration = 0, taskType = 'general', confidence = 0, detailed = null } = feedback;

      // Update strategy performance (Thompson Sampling state)
      await this.pool.query(`
        INSERT INTO learning.strategy_performance
          (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (strategy) DO UPDATE SET
          successes = learning.strategy_performance.successes + EXCLUDED.successes,
          failures = learning.strategy_performance.failures + EXCLUDED.failures,
          alpha = learning.strategy_performance.alpha + EXCLUDED.successes,
          beta = learning.strategy_performance.beta + EXCLUDED.failures,
          total_reward = learning.strategy_performance.total_reward + EXCLUDED.total_reward,
          avg_reward = (learning.strategy_performance.total_reward + EXCLUDED.total_reward) /
                       NULLIF(learning.strategy_performance.successes + learning.strategy_performance.failures +
                              EXCLUDED.successes + EXCLUDED.failures, 0),
          last_updated = NOW()
      `, [
        model,
        success ? 1 : 0,
        success ? 0 : 1,
        success ? 1 : 0,  // alpha increment
        success ? 0 : 1,  // beta increment
        quality,
        quality
      ]);

      // Also record in execution_summary for detailed analytics
      await this.pool.query(`
        INSERT INTO monitoring.execution_summary
          (model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome, timestamp)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
      `, [
        model,
        'orchestrator-routed',
        taskType,
        quality,
        0,  // tokens tracked separately
        0,
        cost,
        duration,
        success ? 'success' : 'failure'
      ]);

      // NEW: Record in monitoring.execution_log if detailed data provided (Issue #252)
      if (detailed) {
        const adapterPath = path.join(os.homedir(), '.claude', 'learning', 'postgres-adapter.js');
        const { getExecutionMonitor } = await import(adapterPath);

        const monitor = getExecutionMonitor();
        await monitor.logExecutionDetailed({
          model,
          model_role: detailed.model_role || 'worker',
          workflow: detailed.workflow || 'orchestrator-routed',
          task_type: taskType,
          phase: detailed.phase || 'execution',
          label: detailed.label || 'Task execution',
          parameters: detailed.parameters || {},
          quality_score: quality,
          confidence: confidence,
          consensus_score: detailed.consensus_score,
          was_selected: detailed.was_selected || false,
          input_tokens: detailed.input_tokens || 0,
          output_tokens: detailed.output_tokens || 0,
          cost_usd: cost,
          duration_ms: duration,
          outcome: success ? 'success' : 'failed',
          outcome_notes: detailed.outcome_notes,
          run_id: detailed.run_id,
          execution_id: detailed.execution_id,
          task_description: detailed.task_description,
          worker_models: detailed.worker_models,
          arbiter_model: detailed.arbiter_model,
          selected_model: detailed.selected_model,
          strategy: detailed.strategy,
          selection_method: detailed.selection_method || 'thompson_sampling'
        });
      }

      console.log(`[orchestrator-learning] Recorded feedback: ${model} ${success ? 'success' : 'failure'} quality=${quality.toFixed(2)}`);

      // Update model_tuning table with aggregated stats (Issue #251)
      await this._updateModelTuning(model, taskType);
    } catch (error) {
      console.error('[orchestrator-learning] Feedback recording failed:', error.message);
    }
  }

  /**
   * Update monitoring.model_tuning table with aggregated performance stats
   *
   * Called after recordFeedback to compute running averages from execution_summary
   *
   * @param {string} model - Model name
   * @param {string} taskType - Task type
   * @private
   */
  async _updateModelTuning(model, taskType) {
    if (!this.connected) return;

    try {
      // Query execution_summary for aggregate stats
      const stats = await this.pool.query(`
        SELECT
          COUNT(*) as sample_count,
          AVG(quality_score) as avg_quality,
          AVG(cost_usd) as avg_cost_usd,
          AVG(duration_ms) as avg_duration_ms,
          SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
          array_agg(quality_score ORDER BY timestamp DESC) FILTER (WHERE quality_score IS NOT NULL) as quality_trend,
          array_agg(cost_usd ORDER BY timestamp DESC) FILTER (WHERE cost_usd IS NOT NULL) as cost_trend
        FROM monitoring.execution_summary
        WHERE model = $1 AND task_type = $2
        GROUP BY model, task_type
      `, [model, taskType]);

      if (stats.rows.length === 0) return;

      const row = stats.rows[0];

      // Limit trend arrays to last 20 entries for performance
      const qualityTrend = (row.quality_trend || []).slice(0, 20);
      const costTrend = (row.cost_trend || []).slice(0, 20);

      // UPSERT into model_tuning
      await this.pool.query(`
        INSERT INTO monitoring.model_tuning
          (model, task_type, optimal_params, avg_quality, avg_confidence, avg_cost_usd, avg_duration_ms, sample_count, success_rate, selection_rate, quality_trend, cost_trend)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (model, task_type) DO UPDATE SET
          updated_at = NOW(),
          optimal_params = EXCLUDED.optimal_params,
          avg_quality = EXCLUDED.avg_quality,
          avg_confidence = EXCLUDED.avg_confidence,
          avg_cost_usd = EXCLUDED.avg_cost_usd,
          avg_duration_ms = EXCLUDED.avg_duration_ms,
          sample_count = EXCLUDED.sample_count,
          success_rate = EXCLUDED.success_rate,
          selection_rate = EXCLUDED.selection_rate,
          quality_trend = EXCLUDED.quality_trend,
          cost_trend = EXCLUDED.cost_trend
      `, [
        model,
        taskType,
        JSON.stringify({}),  // optimal_params (placeholder for now)
        parseFloat(row.avg_quality) || 0.0,
        0.0,  // avg_confidence (not tracked in execution_summary yet)
        parseFloat(row.avg_cost_usd) || 0.0,
        parseFloat(row.avg_duration_ms) || 0.0,
        parseInt(row.sample_count, 10) || 0,
        parseFloat(row.success_rate) || 0.0,
        0.0,  // selection_rate (requires separate tracking)
        JSON.stringify(qualityTrend),
        JSON.stringify(costTrend)
      ]);

      console.log(`[orchestrator-learning] Updated model_tuning: ${model}/${taskType} (${row.sample_count} samples, quality=${parseFloat(row.avg_quality).toFixed(2)})`);
    } catch (error) {
      console.error('[orchestrator-learning] model_tuning update failed:', error.message);
    }
  }

  /**
   * Get model performance stats
   *
   * @param {string} model - Model name
   * @returns {Promise<Object>} Performance stats
   */
  async getModelStats(model) {
    if (!this.connected) await this.connect();
    if (!this.connected) return null;

    try {
      const result = await this.pool.query(`
        SELECT
          strategy as model,
          successes,
          failures,
          alpha,
          beta,
          total_reward,
          avg_reward,
          last_updated
        FROM learning.strategy_performance
        WHERE strategy = $1
      `, [model]);

      if (result.rows.length === 0) return null;

      const stats = result.rows[0];
      return {
        model: stats.model,
        successes: parseInt(stats.successes, 10),
        failures: parseInt(stats.failures, 10),
        totalTasks: parseInt(stats.successes, 10) + parseInt(stats.failures, 10),
        successRate: stats.successes / (stats.successes + stats.failures),
        avgReward: parseFloat(stats.avg_reward),
        lastUpdated: stats.last_updated
      };
    } catch (error) {
      console.error('[orchestrator-learning] Stats query failed:', error.message);
      return null;
    }
  }

  /**
   * Get all model rankings by task type
   *
   * @param {string} taskType - Optional task type filter
   * @returns {Promise<Array>} Models ranked by avg_reward
   */
  async getModelRankings(taskType = null) {
    if (!this.connected) await this.connect();
    if (!this.connected) return [];

    try {
      // If task type specified, filter execution_summary
      // Otherwise, use global strategy_performance rankings
      const result = await this.pool.query(`
        SELECT
          strategy as model,
          avg_reward,
          successes,
          failures,
          (successes::float / NULLIF(successes + failures, 0)) as success_rate
        FROM learning.strategy_performance
        ORDER BY avg_reward DESC
        LIMIT 20
      `);

      return result.rows.map(row => ({
        model: row.model,
        avgReward: parseFloat(row.avg_reward),
        successRate: parseFloat(row.success_rate) || 0,
        totalTasks: parseInt(row.successes, 10) + parseInt(row.failures, 10)
      }));
    } catch (error) {
      console.error('[orchestrator-learning] Rankings query failed:', error.message);
      return [];
    }
  }

  /**
   * Close database connection (no-op for shared pool)
   */
  async close() {
    // Don't close shared pool - it's managed globally
    this.connected = false;
    console.log('[orchestrator-learning] Database adapter closed (pool remains open)');
  }
}
