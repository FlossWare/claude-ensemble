/**
 * Model Diversity Monitor
 *
 * Tracks model selection patterns and alerts when one model dominates.
 * Integrates with PostgreSQL for persistent history.
 *
 * Usage:
 *   const monitor = getDiversityMonitor();
 *   const selectedModel = await thompsonSampling();
 *   await monitor.trackSelection(selectedModel);
 *   const dist = await monitor.getCurrentDistribution();
 */

const { getDB } = require('./postgres-adapter');

const DIVERSITY_THRESHOLD = 0.70;
const LOOKBACK_WINDOW = 100; // Last N selections to analyze
const ALERT_COOLDOWN_MS = 60000; // Only log to file once per minute

class DiversityMonitor {
  constructor(db) {
    this.db = db;
    this.lastAlertTime = 0;
    this.initPromise = this._initialize();
  }

  async _initialize() {
    // Create monitoring table if not exists
    await this.db.query(`
      CREATE TABLE IF NOT EXISTS monitoring.model_selections (
        id SERIAL PRIMARY KEY,
        model TEXT NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    // Create index for fast time-based queries
    await this.db.query(`
      CREATE INDEX IF NOT EXISTS idx_model_selections_timestamp
      ON monitoring.model_selections(timestamp DESC)
    `);

    // Create alerts table for persistent alert history
    await this.db.query(`
      CREATE TABLE IF NOT EXISTS monitoring.diversity_alerts (
        id SERIAL PRIMARY KEY,
        model TEXT NOT NULL,
        percentage NUMERIC(5,2) NOT NULL,
        threshold NUMERIC(5,2) NOT NULL,
        window_size INTEGER NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);
  }

  /**
   * Track a model selection (call AFTER Thompson Sampling selects a model)
   * @param {string} selectedModel - The model that was selected
   * @returns {Promise<void>}
   */
  async trackSelection(selectedModel) {
    await this.initPromise;

    // Validate input
    if (typeof selectedModel !== 'string' || selectedModel.length === 0) {
      throw new TypeError(`Invalid model: expected non-empty string, got ${typeof selectedModel}`);
    }

    // Insert selection into database
    await this.db.query(
      'INSERT INTO monitoring.model_selections (model) VALUES ($1)',
      [selectedModel]
    );

    // Check for diversity violations (non-blocking)
    this._checkDiversity().catch(err => {
      console.error('Diversity check failed:', err.message);
    });
  }

  /**
   * Get current model distribution from recent selections
   * @returns {Promise<Object>} Model distribution {model: percentage}
   */
  async getCurrentDistribution() {
    await this.initPromise;

    const result = await this.db.query(`
      SELECT
        model,
        COUNT(*)::FLOAT / $1 AS percentage
      FROM (
        SELECT model
        FROM monitoring.model_selections
        ORDER BY timestamp DESC
        LIMIT $1
      ) recent
      GROUP BY model
      ORDER BY percentage DESC
    `, [LOOKBACK_WINDOW]);

    const distribution = {};
    result.rows.forEach(row => {
      distribution[row.model] = parseFloat(row.percentage);
    });

    return distribution;
  }

  /**
   * Internal: Check for diversity violations and alert if needed
   * @private
   */
  async _checkDiversity() {
    // Get count of recent selections
    const countResult = await this.db.query(`
      SELECT COUNT(*) as count
      FROM monitoring.model_selections
      WHERE timestamp > NOW() - INTERVAL '1 hour'
    `);

    const recentCount = parseInt(countResult.rows[0].count);

    // Only check if we have enough data
    if (recentCount < LOOKBACK_WINDOW) {
      return;
    }

    // Get distribution
    const distribution = await this.getCurrentDistribution();

    // Calculate Shannon entropy
    let entropy = 0.0;
    for (const percentage of Object.values(distribution)) {
      if (percentage > 0) {
        const logValue = Math.log2(percentage);
        if (!isNaN(logValue)) {
          entropy -= percentage * logValue;
        }
      }
    }
    if (isNaN(entropy)) entropy = 0.0;

    // Check for violations
    const violations = [];
    Object.entries(distribution).forEach(([model, percentage]) => {
      if (percentage > DIVERSITY_THRESHOLD) {
        violations.push({ model, percentage });
      }
    });

    if (violations.length === 0) {
      return;
    }

    // Record violations in database
    for (const violation of violations) {
      await this.db.query(`
        INSERT INTO monitoring.diversity_alerts
        (model, percentage, threshold, window_size)
        VALUES ($1, $2, $3, $4)
      `, [
        violation.model,
        (violation.percentage * 100).toFixed(2),
        DIVERSITY_THRESHOLD * 100,
        LOOKBACK_WINDOW
      ]);

      // Also log to learning.diversity_violations table (cross-database integration)
      try {
        await this.db.query(`
          INSERT INTO learning.diversity_violations (
            violation_type, model, current_usage_pct, quota_limit_pct, diversity_entropy, action_taken
          ) VALUES ($1, $2, $3, $4, $5, $6)
        `, [
          'ceiling_breach',
          violation.model,
          violation.percentage * 100,
          DIVERSITY_THRESHOLD * 100,
          entropy,
          `ALERT: Model usage exceeded threshold in monitoring.model_selections`
        ]);
      } catch (err) {
        // Graceful degradation: learning DB might not be available
        if (process.env.LEARNING_DEBUG) {
          console.error(`Failed to log diversity violation to learning DB: ${err.message}`);
        }
      }
    }

    // Log to console always
    const timestamp = new Date().toISOString();
    const message = `[${timestamp}] DIVERSITY ALERT: ${violations.map(v =>
      `${v.model} at ${(v.percentage * 100).toFixed(1)}% (threshold: ${DIVERSITY_THRESHOLD * 100}%)`
    ).join(', ')} over last ${LOOKBACK_WINDOW} selections (entropy: ${entropy.toFixed(2)})`;
    console.warn(message);

    // Log to file with rate limiting
    const now = Date.now();
    if (now - this.lastAlertTime >= ALERT_COOLDOWN_MS) {
      this.lastAlertTime = now;

      // Use async file write to avoid blocking
      const fs = require('fs').promises;
      const logPath = require('path').join(
        process.env.HOME,
        '.claude',
        'learning',
        'diversity-alerts.log'
      );

      try {
        await fs.appendFile(logPath, message + '\n');
      } catch (err) {
        console.error('Failed to write diversity alert log:', err.message);
      }
    }
  }

  /**
   * Get recent alerts from database
   * @param {number} limit - Maximum number of alerts to return
   * @returns {Promise<Array>} Recent alerts
   */
  async getRecentAlerts(limit = 10) {
    await this.initPromise;

    const result = await this.db.query(`
      SELECT model, percentage, threshold, window_size, timestamp
      FROM monitoring.diversity_alerts
      ORDER BY timestamp DESC
      LIMIT $1
    `, [limit]);

    return result.rows;
  }

  /**
   * Clean up old selection history (keep last 1000)
   * Call periodically to prevent unbounded growth
   * @returns {Promise<number>} Number of rows deleted
   */
  async pruneHistory() {
    await this.initPromise;

    const result = await this.db.query(`
      DELETE FROM monitoring.model_selections
      WHERE id NOT IN (
        SELECT id FROM monitoring.model_selections
        ORDER BY timestamp DESC
        LIMIT 1000
      )
    `);

    return result.rowCount;
  }

  /**
   * Force rotation when dominance detected
   * Returns models sorted by least recent usage
   * @returns {Promise<Array<string>>} Models sorted by priority (least used first)
   */
  async getRotationPriority() {
    await this.initPromise;

    const result = await this.db.query(`
      SELECT
        model,
        MAX(timestamp) as last_used,
        COUNT(*) as usage_count
      FROM monitoring.model_selections
      WHERE timestamp > NOW() - INTERVAL '1 hour'
      GROUP BY model
      ORDER BY usage_count ASC, last_used ASC
    `);

    return result.rows.map(row => row.model);
  }
}

// Singleton instance
let instance = null;

/**
 * Get singleton DiversityMonitor instance
 * @returns {DiversityMonitor}
 */
function getDiversityMonitor() {
  if (!instance) {
    const db = getDB();
    instance = new DiversityMonitor(db);
  }
  return instance;
}

module.exports = {
  DiversityMonitor,
  getDiversityMonitor,
  DIVERSITY_THRESHOLD,
  LOOKBACK_WINDOW,
};
