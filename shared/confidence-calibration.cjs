/**
 * Confidence Calibration System
 *
 * Tracks model confidence vs actual accuracy to detect "lying" models.
 *
 * Problem:
 *   - Model reports 90% confidence, but is only 60% accurate
 *   - Or model reports 50% confidence, but is 85% accurate (sandbagging)
 *
 * Solution:
 *   - Track (model, reported_confidence, actual_outcome) over time
 *   - Calculate calibration error: |reported - actual|
 *   - Apply penalty to models with consistent overconfidence/underconfidence
 *
 * Integration:
 *   - Called by weighted-voting.cjs during weight calculation
 *   - Stores calibration data in PostgreSQL (workflow.confidence_calibration)
 *   - Penalty applied when mismatch > 20% (configurable)
 *
 * Created: 2026-06-28
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Calibration error thresholds
 */
const CALIBRATION_THRESHOLDS = {
  CRITICAL: 0.30,  // >30% error = severe penalty (0.25× weight)
  MAJOR: 0.20,     // >20% error = major penalty (0.50× weight)
  MINOR: 0.10,     // >10% error = minor penalty (0.75× weight)
  // <10% error = no penalty
};

/**
 * Minimum observations required before calibration kicks in
 * (prevents small-sample bias)
 */
const MIN_OBSERVATIONS = 5;

/**
 * Local cache path (fallback if PostgreSQL unavailable)
 */
const CACHE_PATH = path.join(
  process.env.HOME,
  '.claude',
  'learning',
  'confidence-calibration-cache.json'
);

// ============================================================================
// POSTGRESQL STORAGE
// ============================================================================

/**
 * Store calibration observation in PostgreSQL
 *
 * Schema:
 *   CREATE TABLE workflow.confidence_calibration (
 *     id SERIAL PRIMARY KEY,
 *     model TEXT NOT NULL,
 *     reported_confidence NUMERIC NOT NULL,  -- 0.0-1.0
 *     actual_outcome NUMERIC NOT NULL,       -- 0.0 (wrong) or 1.0 (correct)
 *     task_type TEXT,
 *     workflow_execution_id TEXT,
 *     created_at TIMESTAMP DEFAULT NOW()
 *   );
 *
 * @param {Object} observation
 * @param {string} observation.model - Model name
 * @param {number} observation.reported_confidence - Reported confidence (0-1)
 * @param {number} observation.actual_outcome - Actual outcome (0 or 1)
 * @param {string} observation.task_type - Task type
 * @param {string} observation.workflow_execution_id - Workflow ID (optional)
 * @returns {Promise<void>}
 */
async function storeObservation(observation) {
  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Create table if not exists (idempotent)
    await db.pool.query(`
      CREATE TABLE IF NOT EXISTS workflow.confidence_calibration (
        id SERIAL PRIMARY KEY,
        model TEXT NOT NULL,
        reported_confidence NUMERIC NOT NULL,
        actual_outcome NUMERIC NOT NULL,
        task_type TEXT,
        workflow_execution_id TEXT,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // Insert observation
    await db.pool.query(`
      INSERT INTO workflow.confidence_calibration
      (model, reported_confidence, actual_outcome, task_type, workflow_execution_id)
      VALUES ($1, $2, $3, $4, $5)
    `, [
      observation.model,
      observation.reported_confidence,
      observation.actual_outcome,
      observation.task_type || null,
      observation.workflow_execution_id || null,
    ]);
  } catch (err) {
    console.warn(`[confidence-calibration] Could not store to PostgreSQL: ${err.message}`);
    // Fallback to local cache
    storeObservationLocal(observation);
  }
}

/**
 * Store observation in local JSON cache (fallback)
 */
function storeObservationLocal(observation) {
  try {
    const cacheDir = path.dirname(CACHE_PATH);
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }

    let cache = { observations: [] };
    if (fs.existsSync(CACHE_PATH)) {
      cache = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    }

    cache.observations.push({
      ...observation,
      timestamp: new Date().toISOString(),
    });

    fs.writeFileSync(CACHE_PATH, JSON.stringify(cache, null, 2));
  } catch (err) {
    console.warn(`[confidence-calibration] Could not store to local cache: ${err.message}`);
  }
}

/**
 * Get calibration statistics for a model
 *
 * Returns:
 *   - avg_reported: Average reported confidence
 *   - avg_actual: Average actual accuracy
 *   - calibration_error: |avg_reported - avg_actual|
 *   - num_observations: Number of observations
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type (optional filter)
 * @returns {Promise<Object>} Calibration stats
 */
async function getCalibrationStats(model, taskType = null) {
  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Check if table exists
    const tableCheck = await db.pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'workflow'
        AND table_name = 'confidence_calibration'
      )
    `);

    if (!tableCheck.rows[0].exists) {
      // Table doesn't exist - use local cache
      return getCalibrationStatsLocal(model, taskType);
    }

    // Query calibration data
    let query = `
      SELECT
        AVG(reported_confidence) as avg_reported,
        AVG(actual_outcome) as avg_actual,
        COUNT(*) as num_observations
      FROM workflow.confidence_calibration
      WHERE model = $1
    `;

    const params = [model];

    if (taskType) {
      query += ` AND task_type = $2`;
      params.push(taskType);
    }

    const result = await db.pool.query(query, params);

    if (result.rows.length === 0 || result.rows[0].num_observations === '0') {
      return {
        avg_reported: null,
        avg_actual: null,
        calibration_error: null,
        num_observations: 0,
      };
    }

    const row = result.rows[0];
    const avgReported = parseFloat(row.avg_reported);
    const avgActual = parseFloat(row.avg_actual);

    return {
      avg_reported: avgReported,
      avg_actual: avgActual,
      calibration_error: Math.abs(avgReported - avgActual),
      num_observations: parseInt(row.num_observations),
    };
  } catch (err) {
    console.warn(`[confidence-calibration] PostgreSQL query failed: ${err.message}`);
    return getCalibrationStatsLocal(model, taskType);
  }
}

/**
 * Get calibration stats from local cache (fallback)
 */
function getCalibrationStatsLocal(model, taskType = null) {
  try {
    if (!fs.existsSync(CACHE_PATH)) {
      return {
        avg_reported: null,
        avg_actual: null,
        calibration_error: null,
        num_observations: 0,
      };
    }

    const cache = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    let observations = cache.observations.filter(o => o.model === model);

    if (taskType) {
      observations = observations.filter(o => o.task_type === taskType);
    }

    if (observations.length === 0) {
      return {
        avg_reported: null,
        avg_actual: null,
        calibration_error: null,
        num_observations: 0,
      };
    }

    const avgReported = observations.reduce((sum, o) => sum + o.reported_confidence, 0) / observations.length;
    const avgActual = observations.reduce((sum, o) => sum + o.actual_outcome, 0) / observations.length;

    return {
      avg_reported: avgReported,
      avg_actual: avgActual,
      calibration_error: Math.abs(avgReported - avgActual),
      num_observations: observations.length,
    };
  } catch (err) {
    console.warn(`[confidence-calibration] Could not read local cache: ${err.message}`);
    return {
      avg_reported: null,
      avg_actual: null,
      calibration_error: null,
      num_observations: 0,
    };
  }
}

// ============================================================================
// CALIBRATION PENALTY CALCULATION
// ============================================================================

/**
 * Calculate calibration penalty for a model
 *
 * Returns a multiplier (0.0-1.0) to apply to vote weight:
 *   - 1.0 = no penalty (well-calibrated)
 *   - 0.75 = minor penalty (10-20% error)
 *   - 0.50 = major penalty (20-30% error)
 *   - 0.25 = severe penalty (>30% error)
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type (optional)
 * @returns {Promise<Object>} { penalty: number, reason: string, stats: Object }
 */
async function getCalibrationPenalty(model, taskType = null) {
  const stats = await getCalibrationStats(model, taskType);

  // Not enough data - no penalty
  if (stats.num_observations < MIN_OBSERVATIONS) {
    return {
      penalty: 1.0,
      reason: `Insufficient data (${stats.num_observations} observations, need ${MIN_OBSERVATIONS})`,
      stats,
    };
  }

  const error = stats.calibration_error;

  // Determine penalty tier
  if (error >= CALIBRATION_THRESHOLDS.CRITICAL) {
    return {
      penalty: 0.25,
      reason: `Critical calibration error (${(error * 100).toFixed(1)}% > ${CALIBRATION_THRESHOLDS.CRITICAL * 100}%)`,
      stats,
    };
  } else if (error >= CALIBRATION_THRESHOLDS.MAJOR) {
    return {
      penalty: 0.50,
      reason: `Major calibration error (${(error * 100).toFixed(1)}% > ${CALIBRATION_THRESHOLDS.MAJOR * 100}%)`,
      stats,
    };
  } else if (error >= CALIBRATION_THRESHOLDS.MINOR) {
    return {
      penalty: 0.75,
      reason: `Minor calibration error (${(error * 100).toFixed(1)}% > ${CALIBRATION_THRESHOLDS.MINOR * 100}%)`,
      stats,
    };
  } else {
    return {
      penalty: 1.0,
      reason: `Well-calibrated (${(error * 100).toFixed(1)}% error)`,
      stats,
    };
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  storeObservation,
  getCalibrationStats,
  getCalibrationPenalty,
  CALIBRATION_THRESHOLDS,
  MIN_OBSERVATIONS,
};
