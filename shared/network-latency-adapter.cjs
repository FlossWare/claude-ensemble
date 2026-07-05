/**
 * Network Latency Predictor - JavaScript Adapter
 *
 * Provides workflow integration for ML-based network latency prediction.
 *
 * Features:
 * - Predict latency before task assignment
 * - Rank nodes by predicted latency
 * - Fallback to historical averages if ML unavailable
 * - Integration with fleet routing decisions
 *
 * Usage:
 *   const { predictLatency, rankNodesByLatency } = require('./shared/network-latency-adapter.cjs');
 *
 *   // Predict latency for single node
 *   const latency = await predictLatency('server-01');
 *
 *   // Get ranked list of nodes (fastest first)
 *   const ranked = await rankNodesByLatency(['server-01', 'server-02', 'laptop-01']);
 */

const { execSync, exec } = require('child_process');
const { promisify } = require('util');
const path = require('path');
const fs = require('fs');

const execAsync = promisify(exec);

const PREDICTOR_PATH = path.join(
  process.env.HOME,
  'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/network_latency_predictor.py'
);

const STATS_PATH = path.join(
  process.env.HOME,
  'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/network_latency_stats.json'
);

/**
 * Check if ML models are available
 */
function hasModels() {
  const modelPath = path.join(
    process.env.HOME,
    'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/network_latency_models.pkl'
  );
  return fs.existsSync(modelPath);
}

/**
 * Load model statistics
 */
function getModelStats() {
  if (!fs.existsSync(STATS_PATH)) {
    return null;
  }

  try {
    const content = fs.readFileSync(STATS_PATH, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    console.error('Error loading model stats:', error.message);
    return null;
  }
}

/**
 * Predict network latency for a single node
 *
 * @param {string} targetNode - Node hostname
 * @param {Object} options - Options
 * @param {boolean} options.useFallback - Use historical average if ML unavailable (default: true)
 * @returns {Promise<Object>} Prediction result
 */
async function predictLatency(targetNode, options = {}) {
  const { useFallback = true } = options;

  // Check if models exist
  if (!hasModels()) {
    if (!useFallback) {
      throw new Error('ML models not trained. Run: python3 network_latency_predictor.py --train');
    }

    // Fallback to historical average
    return getHistoricalAverage(targetNode);
  }

  try {
    const { stdout } = await execAsync(
      `python3 "${PREDICTOR_PATH}" --predict "${targetNode}"`,
      { timeout: 10000 }
    );

    const result = JSON.parse(stdout);
    return {
      node: targetNode,
      predicted_latency_ms: result.predicted_latency_ms,
      confidence: result.confidence_score,
      actual_latency_ms: result.actual_latency_ms,
      source: 'ml_model',
      timestamp: result.timestamp
    };

  } catch (error) {
    if (useFallback) {
      console.warn(`ML prediction failed for ${targetNode}, using fallback: ${error.message}`);
      return getHistoricalAverage(targetNode);
    }
    throw error;
  }
}

/**
 * Get historical average latency from database
 */
async function getHistoricalAverage(targetNode) {
  try {
    const { stdout } = await execAsync(
      `psql -h aio-01 -p 5433 -U sfloess -d learning -t -c "SELECT AVG(ping_latency_ms) FROM monitoring.network_measurements WHERE target_node = '${targetNode}' AND ping_latency_ms IS NOT NULL AND timestamp > NOW() - INTERVAL '7 days'"`,
      { timeout: 5000 }
    );

    const avg = parseFloat(stdout.trim());

    if (!isNaN(avg) && avg > 0) {
      return {
        node: targetNode,
        predicted_latency_ms: avg,
        confidence: 0.5,
        source: 'historical_average',
        timestamp: new Date().toISOString()
      };
    }

    // Ultimate fallback: rough estimates based on node type
    const fallbackLatencies = {
      'server-01': 1.0,
      'server-02': 1.0,
      'server-03': 1.0,
      'laptop-01': 5.0,
      'pi-02': 2.0,
      'desktop-ap': 1.5,
      'server-ap': 2.0,
      'aio-01': 0.5
    };

    return {
      node: targetNode,
      predicted_latency_ms: fallbackLatencies[targetNode] || 5.0,
      confidence: 0.3,
      source: 'default_estimate',
      timestamp: new Date().toISOString()
    };

  } catch (error) {
    console.warn(`Failed to get historical average for ${targetNode}: ${error.message}`);
    return {
      node: targetNode,
      predicted_latency_ms: 5.0,
      confidence: 0.2,
      source: 'error_fallback',
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Rank nodes by predicted latency (fastest first)
 *
 * @param {string[]} nodes - List of node hostnames
 * @param {Object} options - Options
 * @param {boolean} options.parallel - Predict in parallel (default: true)
 * @returns {Promise<Array>} Ranked nodes with predictions
 */
async function rankNodesByLatency(nodes, options = {}) {
  const { parallel = true } = options;

  let predictions;

  if (parallel) {
    // Predict all nodes in parallel
    predictions = await Promise.all(
      nodes.map(node => predictLatency(node).catch(err => ({
        node,
        predicted_latency_ms: 999,
        confidence: 0,
        source: 'error',
        error: err.message
      })))
    );
  } else {
    // Sequential predictions
    predictions = [];
    for (const node of nodes) {
      try {
        const pred = await predictLatency(node);
        predictions.push(pred);
      } catch (error) {
        predictions.push({
          node,
          predicted_latency_ms: 999,
          confidence: 0,
          source: 'error',
          error: error.message
        });
      }
    }
  }

  // Sort by latency (ascending)
  predictions.sort((a, b) => a.predicted_latency_ms - b.predicted_latency_ms);

  return predictions;
}

/**
 * Select best node for task assignment
 *
 * @param {string[]} availableNodes - Available fleet nodes
 * @param {Object} options - Selection options
 * @param {number} options.maxLatency - Maximum acceptable latency (ms)
 * @param {number} options.minConfidence - Minimum confidence threshold
 * @returns {Promise<Object>} Best node and prediction
 */
async function selectBestNode(availableNodes, options = {}) {
  const { maxLatency = 100, minConfidence = 0.3 } = options;

  const ranked = await rankNodesByLatency(availableNodes);

  // Find first node meeting criteria
  for (const pred of ranked) {
    if (pred.predicted_latency_ms <= maxLatency && pred.confidence >= minConfidence) {
      return {
        selected: true,
        node: pred.node,
        prediction: pred
      };
    }
  }

  // No node meets criteria, return best available
  return {
    selected: true,
    node: ranked[0].node,
    prediction: ranked[0],
    warning: 'No node meets latency/confidence criteria, using best available'
  };
}

/**
 * Collect current network measurements
 */
async function collectMeasurements() {
  try {
    await execAsync(`python3 "${PREDICTOR_PATH}" --collect`, { timeout: 60000 });
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Train ML models
 *
 * @param {Object} options - Training options
 * @param {number} options.days - Days of historical data (default: 30)
 */
async function trainModels(options = {}) {
  const { days = 30 } = options;

  try {
    const { stdout, stderr } = await execAsync(
      `python3 "${PREDICTOR_PATH}" --train --days ${days}`,
      { timeout: 120000 }
    );

    return {
      success: true,
      output: stdout,
      stats: getModelStats()
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      stderr: error.stderr
    };
  }
}

/**
 * Get prediction accuracy stats
 */
async function getPredictionAccuracy() {
  const { Pool } = require('pg');
  const pool = new Pool({
    host: 'aio-01',
    port: 5433,
    database: 'learning',
    user: 'sfloess'
  });

  try {
    const result = await pool.query(`
      SELECT
        COUNT(*) as total_predictions,
        AVG(ABS(predicted_latency_ms - actual_latency_ms)) as mae,
        SQRT(AVG(POWER(predicted_latency_ms - actual_latency_ms, 2))) as rmse,
        AVG(confidence_score) as avg_confidence
      FROM monitoring.network_predictions
      WHERE actual_latency_ms IS NOT NULL
      AND timestamp > NOW() - INTERVAL '7 days'
    `);

    await pool.end();

    return result.rows[0];
  } catch (error) {
    await pool.end();
    throw error;
  }
}

/**
 * Workflow integration: Pre-flight latency check
 *
 * Use this before assigning tasks to workers to optimize for network latency.
 *
 * @param {string[]} workers - Available worker nodes
 * @returns {Promise<Array>} Ranked workers
 */
async function optimizeWorkerAssignment(workers) {
  const ranked = await rankNodesByLatency(workers);

  return ranked.map((pred, index) => ({
    rank: index + 1,
    hostname: pred.node,
    predicted_latency_ms: pred.predicted_latency_ms,
    confidence: pred.confidence,
    recommended: index < Math.ceil(workers.length * 0.7) // Top 70%
  }));
}

module.exports = {
  // Core functions
  predictLatency,
  rankNodesByLatency,
  selectBestNode,

  // Data collection
  collectMeasurements,
  trainModels,

  // Analytics
  getPredictionAccuracy,
  getModelStats,
  hasModels,

  // Workflow integration
  optimizeWorkerAssignment
};
