/**
 * Model Performance Drift Detector
 *
 * Tracks 30-day rolling performance and detects >10% degradation in model quality.
 *
 * Architecture:
 * - Data source: workflow.worker_results table
 * - Aggregation: monitoring.model_drift materialized view (90-day window)
 * - Detection: monitoring.detect_model_drift() function (7-day vs 30-day comparison)
 * - Storage: monitoring.drift_alerts table (historical log)
 *
 * Usage:
 *   const { detectDrift, refreshDriftView } = require('./monitoring/drift-detector.cjs');
 *   await refreshDriftView();
 *   const alerts = await detectDrift();
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');

// Database connection pool
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('[DriftDetector] PostgreSQL pool error:', err.message);
});

/**
 * Refresh the materialized view (monitoring.model_drift)
 * Call this before detecting drift to ensure latest data
 *
 * @returns {Promise<void>}
 */
async function refreshDriftView() {
  const client = await pool.connect();
  try {
    const startTime = Date.now();
    await client.query('SELECT monitoring.refresh_drift_view()');
    const duration = Date.now() - startTime;
    console.log(`[DriftDetector] Refreshed model_drift view in ${duration}ms`);
  } catch (err) {
    console.error('[DriftDetector] Failed to refresh drift view:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Detect model performance drift
 *
 * Compares current 7-day average quality vs historical 30-day average.
 * Returns models with >10% performance drop.
 *
 * @param {Object} options - Detection options
 * @param {number} options.driftThreshold - Minimum drop percentage to trigger alert (default: 0.10 = 10%)
 * @param {number} options.minSamples - Minimum samples required (default: 20, raised from 5)
 * @returns {Promise<Array>} Array of drift alerts
 *
 * Example return value:
 * [
 *   {
 *     model: 'opus',
 *     task_type: 'code_review',
 *     current_7day_avg: 0.72,
 *     historical_30day_avg: 0.85,
 *     performance_drop_pct: -15.29,
 *     current_sample_count: 23,
 *     historical_sample_count: 87,
 *     severity: 'warning'
 *   }
 * ]
 */
async function detectDrift(options = {}) {
  const {
    driftThreshold = 0.10, // 10% drop threshold
    minSamples = 20 // Raised from 5 to reduce false positives
  } = options;

  const client = await pool.connect();
  try {
    const startTime = Date.now();

    const result = await client.query(
      'SELECT * FROM monitoring.detect_model_drift($1, $2)',
      [driftThreshold, minSamples]
    );

    const duration = Date.now() - startTime;
    const driftCount = result.rows.length;

    console.log(`[DriftDetector] Detected ${driftCount} drift alerts in ${duration}ms`);

    if (driftCount > 0) {
      console.log('[DriftDetector] Drift alerts:');
      for (const alert of result.rows) {
        const drop = alert.performance_drop_pct.toFixed(2);
        const severity = alert.severity === 'critical' ? '🚨' : '⚠️';
        console.log(
          `  ${severity} ${alert.model} (${alert.task_type || 'all tasks'}): ` +
          `${alert.current_7day_avg.toFixed(3)} → ${alert.historical_30day_avg.toFixed(3)} ` +
          `(${drop}% drop, n=${alert.current_sample_count})`
        );
      }
    }

    return result.rows;
  } catch (err) {
    console.error('[DriftDetector] Failed to detect drift:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Log drift alerts to monitoring.drift_alerts table
 *
 * @param {Array} driftAlerts - Array of drift alerts from detectDrift()
 * @returns {Promise<Array<number>>} Array of inserted alert IDs
 */
async function logDriftAlerts(driftAlerts) {
  if (!driftAlerts || driftAlerts.length === 0) {
    console.log('[DriftDetector] No drift alerts to log');
    return [];
  }

  const client = await pool.connect();
  try {
    const alertIds = [];

    for (const alert of driftAlerts) {
      const result = await client.query(
        `SELECT monitoring.log_drift_alert($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
        [
          alert.model,
          alert.task_type,
          alert.current_7day_avg,
          alert.historical_30day_avg,
          alert.performance_drop_pct,
          alert.current_sample_count,
          alert.historical_sample_count,
          alert.severity,
          JSON.stringify({
            detection_timestamp: new Date().toISOString(),
            threshold_used: 0.10
          })
        ]
      );

      alertIds.push(result.rows[0].log_drift_alert);
    }

    console.log(`[DriftDetector] Logged ${alertIds.length} drift alerts to database`);
    return alertIds;
  } catch (err) {
    console.error('[DriftDetector] Failed to log drift alerts:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Acknowledge a drift alert
 *
 * @param {number} alertId - Alert ID from monitoring.drift_alerts
 * @param {string} acknowledgedBy - User who acknowledged the alert
 * @returns {Promise<boolean>} True if acknowledged successfully
 */
async function acknowledgeDriftAlert(alertId, acknowledgedBy) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      'SELECT monitoring.acknowledge_drift_alert($1, $2)',
      [alertId, acknowledgedBy]
    );

    const success = result.rows[0].acknowledge_drift_alert;

    if (success) {
      console.log(`[DriftDetector] Acknowledged alert #${alertId} by ${acknowledgedBy}`);
    } else {
      console.warn(`[DriftDetector] Failed to acknowledge alert #${alertId} (not found)`);
    }

    return success;
  } catch (err) {
    console.error('[DriftDetector] Failed to acknowledge drift alert:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Get unacknowledged drift alerts
 *
 * @returns {Promise<Array>} Array of unacknowledged alerts
 */
async function getUnacknowledgedAlerts() {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT * FROM monitoring.drift_alerts
       WHERE acknowledged = FALSE
       ORDER BY detection_date DESC`
    );

    console.log(`[DriftDetector] Found ${result.rows.length} unacknowledged alerts`);
    return result.rows;
  } catch (err) {
    console.error('[DriftDetector] Failed to get unacknowledged alerts:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Get drift history for a specific model
 *
 * @param {string} model - Model name
 * @param {number} limit - Max results to return (default: 30)
 * @returns {Promise<Array>} Array of historical drift alerts
 */
async function getModelDriftHistory(model, limit = 30) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT * FROM monitoring.drift_alerts
       WHERE model = $1
       ORDER BY detection_date DESC
       LIMIT $2`,
      [model, limit]
    );

    console.log(`[DriftDetector] Found ${result.rows.length} historical alerts for ${model}`);
    return result.rows;
  } catch (err) {
    console.error('[DriftDetector] Failed to get drift history:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Update Thompson Sampling weights based on drift
 * Temporarily reduces model weight when performance degrades
 *
 * @param {Array} driftAlerts - Array of drift alerts
 * @returns {Promise<void>}
 */
async function updateThompsonSamplingWeights(driftAlerts) {
  if (!driftAlerts || driftAlerts.length === 0) {
    return;
  }

  console.log('[DriftDetector] Updating Thompson Sampling weights...');

  // This is a placeholder - actual implementation depends on your bandit state location
  // For now, just log the recommended actions
  for (const alert of driftAlerts) {
    const penaltyFactor = alert.severity === 'critical' ? 0.5 : 0.8;
    console.log(
      `[DriftDetector] Recommend: Reduce ${alert.model} weight by ${(1 - penaltyFactor) * 100}% ` +
      `for task_type="${alert.task_type || 'all'}"`
    );
  }

  // TODO: Integrate with actual Thompson Sampling bandit state
  // Example: Update ~/.claude/learning/bandit-state.json or PostgreSQL learning.strategy_performance
}

/**
 * Add drift alert to human review queue
 *
 * @param {Array} driftAlerts - Array of drift alerts
 * @returns {Promise<void>}
 */
async function queueHumanReview(driftAlerts) {
  if (!driftAlerts || driftAlerts.length === 0) {
    return;
  }

  const client = await pool.connect();
  try {
    for (const alert of driftAlerts) {
      const message = {
        type: 'model_drift',
        model: alert.model,
        task_type: alert.task_type,
        severity: alert.severity,
        performance_drop_pct: alert.performance_drop_pct,
        current_avg: alert.current_7day_avg,
        historical_avg: alert.historical_30day_avg,
        samples: alert.current_sample_count,
        timestamp: new Date().toISOString()
      };

      // Check if human_review_queue table exists
      const tableExists = await client.query(
        `SELECT EXISTS (
          SELECT FROM information_schema.tables
          WHERE table_schema = 'workflow'
          AND table_name = 'human_review_queue'
        )`
      );

      if (tableExists.rows[0].exists) {
        await client.query(
          `INSERT INTO workflow.human_review_queue
           (review_type, priority, message, metadata, created_at)
           VALUES ($1, $2, $3, $4, NOW())`,
          [
            'model_drift',
            alert.severity === 'critical' ? 1 : 2,
            `Model drift detected: ${alert.model} (${alert.task_type || 'all tasks'})`,
            JSON.stringify(message)
          ]
        );

        console.log(`[DriftDetector] Queued human review for ${alert.model}`);
      } else {
        console.warn('[DriftDetector] workflow.human_review_queue table does not exist, skipping');
      }
    }
  } catch (err) {
    console.error('[DriftDetector] Failed to queue human review:', err.message);
    // Non-blocking - continue even if this fails
  } finally {
    client.release();
  }
}

/**
 * Complete drift detection pipeline
 * 1. Refresh materialized view
 * 2. Detect drift
 * 3. Log alerts
 * 4. Update Thompson Sampling weights
 * 5. Queue human review
 * 6. Send webhook notifications
 *
 * @param {Object} options - Detection options
 * @returns {Promise<Object>} Detection results
 */
async function runDriftDetectionPipeline(options = {}) {
  console.log('[DriftDetector] Starting drift detection pipeline...');
  const startTime = Date.now();

  try {
    // Step 1: Refresh materialized view
    await refreshDriftView();

    // Step 2: Detect drift
    const driftAlerts = await detectDrift(options);

    // Step 3: Log alerts
    const alertIds = await logDriftAlerts(driftAlerts);

    // Step 4: Update Thompson Sampling weights (optional)
    if (options.updateWeights !== false) {
      await updateThompsonSamplingWeights(driftAlerts);
    }

    // Step 5: Queue human review (optional)
    if (options.queueReview !== false) {
      await queueHumanReview(driftAlerts);
    }

    // Step 6: Send webhook notifications (optional)
    if (options.sendWebhooks !== false && driftAlerts.length > 0) {
      await sendDriftNotifications(driftAlerts);
    }

    const totalDuration = Date.now() - startTime;

    const results = {
      success: true,
      drift_alerts: driftAlerts,
      alert_ids: alertIds,
      duration_ms: totalDuration,
      timestamp: new Date().toISOString()
    };

    console.log(`[DriftDetector] Pipeline complete in ${totalDuration}ms`);
    return results;

  } catch (err) {
    console.error('[DriftDetector] Pipeline failed:', err.message);
    return {
      success: false,
      error: err.message,
      duration_ms: Date.now() - startTime,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Send webhook notifications for drift alerts
 *
 * @param {Array} driftAlerts - Array of drift alerts
 * @returns {Promise<void>}
 */
async function sendDriftNotifications(driftAlerts) {
  try {
    const { notifyDrift } = require('./webhook-notifier.cjs');

    for (const alert of driftAlerts) {
      try {
        await notifyDrift(alert);
      } catch (err) {
        console.error(`[DriftDetector] Failed to send webhook for ${alert.model}:`, err.message);
        // Continue with other alerts
      }
    }
  } catch (err) {
    console.error('[DriftDetector] Failed to load webhook notifier:', err.message);
    // Non-blocking - continue even if webhooks unavailable
  }
}

/**
 * Close connection pool
 */
async function close() {
  await pool.end();
}

module.exports = {
  refreshDriftView,
  detectDrift,
  logDriftAlerts,
  acknowledgeDriftAlert,
  getUnacknowledgedAlerts,
  getModelDriftHistory,
  updateThompsonSamplingWeights,
  queueHumanReview,
  runDriftDetectionPipeline,
  close
};
