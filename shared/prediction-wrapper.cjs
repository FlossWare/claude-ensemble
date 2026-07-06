/**
 * Workflow Prediction Wrapper
 *
 * Integrates ML-powered workflow prediction service (aio-01:8080) with
 * existing multi-AI orchestration infrastructure.
 *
 * Features:
 * - Predict workflow outcomes before execution (duration, cost, quality)
 * - Execute workflows with automatic prediction logging
 * - Log prediction accuracy to PostgreSQL for model improvement
 * - Graceful fallback when prediction API unavailable
 * - Automatic retry with exponential backoff
 * - Circuit breaker pattern for failing endpoints
 *
 * Created: 2026-07-05
 */

const http = require('http');
const { Pool } = require('pg');

// Reuse PostgreSQL connection pool
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
  console.error('PostgreSQL pool error:', err.message);
});

// Circuit breaker state
const circuitBreaker = {
  failures: 0,
  lastFailureTime: null,
  state: 'CLOSED', // CLOSED, OPEN, HALF_OPEN
  failureThreshold: 5,
  resetTimeout: 60000, // 60s
  halfOpenMaxRequests: 3,
  halfOpenRequests: 0,
};

/**
 * Check if circuit breaker allows request
 * @returns {boolean} True if request allowed
 */
function canMakeRequest() {
  if (circuitBreaker.state === 'CLOSED') {
    return true;
  }

  if (circuitBreaker.state === 'OPEN') {
    const timeSinceFailure = Date.now() - circuitBreaker.lastFailureTime;
    if (timeSinceFailure >= circuitBreaker.resetTimeout) {
      // Try half-open state
      circuitBreaker.state = 'HALF_OPEN';
      circuitBreaker.halfOpenRequests = 0;
      return true;
    }
    return false;
  }

  if (circuitBreaker.state === 'HALF_OPEN') {
    return circuitBreaker.halfOpenRequests < circuitBreaker.halfOpenMaxRequests;
  }

  return false;
}

/**
 * Record successful request
 */
function recordSuccess() {
  if (circuitBreaker.state === 'HALF_OPEN') {
    // Success in half-open state → close circuit
    circuitBreaker.state = 'CLOSED';
    circuitBreaker.failures = 0;
  }
  circuitBreaker.failures = Math.max(0, circuitBreaker.failures - 1);
}

/**
 * Record failed request
 */
function recordFailure() {
  circuitBreaker.failures++;
  circuitBreaker.lastFailureTime = Date.now();

  if (circuitBreaker.state === 'HALF_OPEN') {
    // Failure in half-open state → reopen circuit
    circuitBreaker.state = 'OPEN';
  } else if (circuitBreaker.failures >= circuitBreaker.failureThreshold) {
    circuitBreaker.state = 'OPEN';
  }
}

/**
 * Make HTTP request to prediction API
 * @param {Object} data - Request payload
 * @param {Object} options - Request options
 * @param {number} options.timeout - Request timeout in ms (default: 5000)
 * @returns {Promise<Object>} Response JSON
 */
async function httpRequest(data, options = {}) {
  const { timeout = 5000 } = options;

  return new Promise((resolve, reject) => {
    const postData = JSON.stringify(data);

    const reqOptions = {
      hostname: process.env.PREDICTION_HOST || 'aio-01',
      port: parseInt(process.env.PREDICTION_PORT || '8080'),
      path: '/predict-workflow',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData),
      },
      timeout,
    };

    const req = http.request(reqOptions, (res) => {
      let responseData = '';

      res.on('data', (chunk) => {
        responseData += chunk.toString();
      });

      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const json = JSON.parse(responseData);
            resolve(json);
          } catch (err) {
            reject(new Error(`Invalid JSON response: ${err.message}`));
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${responseData}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(err);
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`Request timeout after ${timeout}ms`));
    });

    req.write(postData);
    req.end();
  });
}

/**
 * Retry with exponential backoff
 * @param {Function} fn - Async function to retry
 * @param {Object} options - Retry options
 * @param {number} options.maxRetries - Max retry attempts (default: 3)
 * @param {number} options.initialDelay - Initial delay in ms (default: 1000)
 * @param {number} options.maxDelay - Max delay in ms (default: 10000)
 * @param {number} options.backoffFactor - Exponential backoff multiplier (default: 2)
 * @returns {Promise<*>} Function result
 */
async function retryWithBackoff(fn, options = {}) {
  const {
    maxRetries = 3,
    initialDelay = 1000,
    maxDelay = 10000,
    backoffFactor = 2,
  } = options;

  let lastError;
  let delay = initialDelay;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;

      if (attempt < maxRetries) {
        // Wait before retry
        await new Promise((resolve) => setTimeout(resolve, delay));
        delay = Math.min(delay * backoffFactor, maxDelay);
      }
    }
  }

  throw lastError;
}

/**
 * Predict workflow outcomes using ML model
 *
 * @param {Object} config - Workflow configuration
 * @param {string} config.workflow_name - Workflow identifier (e.g., 'deep-research')
 * @param {string} config.task_description - Task being performed
 * @param {number} [config.total_workers] - Number of workers (optional)
 * @param {string[]} [config.models] - Model names (optional)
 * @param {Object} [config.metadata] - Additional metadata (optional)
 * @param {Object} [options] - Prediction options
 * @param {number} [options.timeout] - Request timeout in ms (default: 5000)
 * @param {boolean} [options.skipRetry] - Skip retry on failure (default: false)
 * @returns {Promise<Object>} Prediction result
 *
 * Returns:
 * {
 *   predicted: {
 *     duration_ms: number,
 *     cost_usd: number,
 *     quality_score: number,
 *     confidence: number
 *   },
 *   metadata: {
 *     model_version: string,
 *     prediction_time_ms: number,
 *     features_used: string[]
 *   }
 * }
 *
 * On failure, returns fallback predictions with confidence: 0.0
 */
async function predictWorkflow(config, options = {}) {
  const { timeout = 5000, skipRetry = false } = options;

  // Validate input
  if (!config || typeof config !== 'object') {
    throw new Error('config must be an object');
  }

  if (!config.workflow_name || typeof config.workflow_name !== 'string') {
    throw new Error('config.workflow_name is required');
  }

  if (!config.task_description || typeof config.task_description !== 'string') {
    throw new Error('config.task_description is required');
  }

  // Check circuit breaker
  if (!canMakeRequest()) {
    console.warn(
      `Prediction API circuit breaker OPEN (${circuitBreaker.failures} failures), using fallback`
    );
    return getFallbackPrediction(config);
  }

  // Increment half-open counter
  if (circuitBreaker.state === 'HALF_OPEN') {
    circuitBreaker.halfOpenRequests++;
  }

  // Prepare request
  const requestData = {
    workflow_name: config.workflow_name,
    task_description: config.task_description,
    total_workers: config.total_workers,
    models: config.models,
    metadata: config.metadata,
  };

  // Make request with retry
  try {
    const makePrediction = async () => {
      return await httpRequest(requestData, { timeout });
    };

    const result = skipRetry
      ? await makePrediction()
      : await retryWithBackoff(makePrediction, { maxRetries: 3 });

    recordSuccess();
    return result;
  } catch (err) {
    recordFailure();
    console.error(`Prediction API error: ${err.message}`);
    return getFallbackPrediction(config);
  }
}

/**
 * Get fallback prediction when API unavailable
 * Uses historical averages from PostgreSQL
 *
 * @param {Object} config - Workflow configuration
 * @returns {Promise<Object>} Fallback prediction
 */
async function getFallbackPrediction(config) {
  try {
    // Query historical data for this workflow type
    const result = await pool.query(
      `
      SELECT
        AVG(total_duration_ms) as avg_duration,
        AVG(
          (SELECT SUM(cost_usd)
           FROM workflow.worker_results wr
           WHERE wr.workflow_execution_id = we.id)
        ) as avg_cost,
        AVG(quality_score) as avg_quality,
        COUNT(*) as sample_size
      FROM workflow.executions we
      WHERE workflow_name = $1
        AND outcome = 'success'
        AND created_at > NOW() - INTERVAL '30 days'
      `,
      [config.workflow_name]
    );

    if (result.rows.length > 0 && result.rows[0].sample_size > 0) {
      const row = result.rows[0];
      const avgDuration = parseFloat(row.avg_duration) || 30000;
      const avgCost = parseFloat(row.avg_cost) || 0.5;
      const avgQuality = parseFloat(row.avg_quality) || 0.8;
      const sampleSize = parseInt(row.sample_size) || 0;

      return {
        predicted: {
          duration_ms: Math.round(avgDuration),
          cost_usd: parseFloat(avgCost.toFixed(4)),
          quality_score: parseFloat(avgQuality.toFixed(2)),
          confidence: Math.min(sampleSize / 10, 0.5), // Max 0.5 confidence for fallback
        },
        metadata: {
          model_version: 'fallback',
          prediction_time_ms: 0,
          features_used: ['historical_average'],
          fallback_reason: 'prediction_api_unavailable',
          sample_size: sampleSize,
        },
      };
    }
  } catch (err) {
    console.error(`Fallback prediction query error: ${err.message}`);
  }

  // Ultimate fallback (no historical data)
  return {
    predicted: {
      duration_ms: 30000,
      cost_usd: 0.5,
      quality_score: 0.8,
      confidence: 0.0,
    },
    metadata: {
      model_version: 'fallback',
      prediction_time_ms: 0,
      features_used: ['default_values'],
      fallback_reason: 'no_historical_data',
    },
  };
}

/**
 * Execute workflow with automatic prediction logging
 *
 * @param {Function} workflowFn - Async workflow function to execute
 * @param {Object} config - Workflow configuration (same as predictWorkflow)
 * @param {Object} [options] - Execution options
 * @param {boolean} [options.skipPrediction] - Skip prediction step (default: false)
 * @param {boolean} [options.skipLogging] - Skip accuracy logging (default: false)
 * @returns {Promise<Object>} Execution result with prediction comparison
 *
 * Returns:
 * {
 *   result: <workflow result>,
 *   prediction: { ... },
 *   actual: {
 *     duration_ms: number,
 *     cost_usd: number,
 *     quality_score: number,
 *     outcome: string
 *   },
 *   accuracy: {
 *     duration_error_pct: number,
 *     cost_error_pct: number,
 *     quality_error_abs: number
 *   }
 * }
 */
async function executeWithPrediction(workflowFn, config, options = {}) {
  const { skipPrediction = false, skipLogging = false } = options;

  // Validate input
  if (typeof workflowFn !== 'function') {
    throw new Error('workflowFn must be a function');
  }

  // Predict
  const prediction = skipPrediction
    ? null
    : await predictWorkflow(config).catch((err) => {
        console.error(`Prediction failed: ${err.message}`);
        return null;
      });

  // Execute
  const startTime = Date.now();
  let result;
  let error;
  let actualCost = 0;
  let actualQuality = null;

  try {
    result = await workflowFn();

    // Extract actual metrics from result if available
    if (result && typeof result === 'object') {
      actualCost = result.total_cost_usd || result.cost_usd || 0;
      actualQuality = result.quality_score || result.quality || null;
    }
  } catch (err) {
    error = err;
  }

  const endTime = Date.now();
  const actualDuration = endTime - startTime;

  // Build actual metrics
  const actual = {
    duration_ms: actualDuration,
    cost_usd: actualCost,
    quality_score: actualQuality,
    outcome: error ? 'error' : 'success',
  };

  // Calculate accuracy
  let accuracy = null;
  if (prediction && !error) {
    accuracy = {
      duration_error_pct:
        prediction.predicted.duration_ms > 0
          ? Math.abs(
              ((actualDuration - prediction.predicted.duration_ms) /
                prediction.predicted.duration_ms) *
                100
            )
          : null,
      cost_error_pct:
        prediction.predicted.cost_usd > 0
          ? Math.abs(
              ((actualCost - prediction.predicted.cost_usd) /
                prediction.predicted.cost_usd) *
                100
            )
          : null,
      quality_error_abs:
        actualQuality !== null
          ? Math.abs(actualQuality - prediction.predicted.quality_score)
          : null,
    };
  }

  // Log accuracy
  if (prediction && !skipLogging) {
    await logPredictionAccuracy(config, prediction, actual, accuracy).catch(
      (err) => {
        console.error(`Failed to log prediction accuracy: ${err.message}`);
      }
    );
  }

  // Rethrow error if execution failed
  if (error) {
    throw error;
  }

  return {
    result,
    prediction,
    actual,
    accuracy,
  };
}

/**
 * Log prediction accuracy to PostgreSQL
 *
 * @param {Object} config - Original workflow configuration
 * @param {Object} predicted - Predicted metrics
 * @param {Object} actual - Actual metrics
 * @param {Object} accuracy - Accuracy metrics
 * @returns {Promise<void>}
 */
async function logPredictionAccuracy(config, predicted, actual, accuracy) {
  try {
    await pool.query(
      `
      INSERT INTO workflow.prediction_accuracy
      (
        workflow_name,
        task_description,
        predicted_duration_ms,
        actual_duration_ms,
        predicted_cost_usd,
        actual_cost_usd,
        predicted_quality,
        actual_quality,
        prediction_confidence,
        duration_error_pct,
        cost_error_pct,
        quality_error_abs,
        outcome,
        model_version,
        metadata
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
      `,
      [
        config.workflow_name,
        config.task_description,
        predicted.predicted.duration_ms,
        actual.duration_ms,
        predicted.predicted.cost_usd,
        actual.cost_usd,
        predicted.predicted.quality_score,
        actual.quality_score,
        predicted.predicted.confidence,
        accuracy ? accuracy.duration_error_pct : null,
        accuracy ? accuracy.cost_error_pct : null,
        accuracy ? accuracy.quality_error_abs : null,
        actual.outcome,
        predicted.metadata.model_version,
        JSON.stringify({
          prediction_metadata: predicted.metadata,
          workflow_metadata: config.metadata,
        }),
      ]
    );
  } catch (err) {
    // Check if table doesn't exist
    if (err.code === '42P01') {
      console.warn(
        'workflow.prediction_accuracy table does not exist, creating schema...'
      );
      await createPredictionAccuracyTable();
      // Retry insert
      await logPredictionAccuracy(config, predicted, actual, accuracy);
    } else {
      throw err;
    }
  }
}

/**
 * Create prediction_accuracy table if it doesn't exist
 * @returns {Promise<void>}
 */
async function createPredictionAccuracyTable() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS workflow.prediction_accuracy (
      id SERIAL PRIMARY KEY,
      workflow_name TEXT NOT NULL,
      task_description TEXT NOT NULL,
      predicted_duration_ms INTEGER,
      actual_duration_ms INTEGER,
      predicted_cost_usd NUMERIC(10,6),
      actual_cost_usd NUMERIC(10,6),
      predicted_quality NUMERIC(4,3),
      actual_quality NUMERIC(4,3),
      prediction_confidence NUMERIC(4,3),
      duration_error_pct NUMERIC(6,2),
      cost_error_pct NUMERIC(6,2),
      quality_error_abs NUMERIC(4,3),
      outcome TEXT NOT NULL,
      model_version TEXT,
      metadata JSONB,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_workflow
      ON workflow.prediction_accuracy(workflow_name, created_at DESC);

    CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_outcome
      ON workflow.prediction_accuracy(outcome);

    CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_created
      ON workflow.prediction_accuracy(created_at DESC);
  `);
}

/**
 * Get prediction accuracy statistics
 *
 * @param {Object} [options] - Query options
 * @param {string} [options.workflowName] - Filter by workflow name
 * @param {number} [options.windowDays] - Analysis window in days (default: 30)
 * @returns {Promise<Object>} Accuracy statistics
 */
async function getPredictionAccuracy(options = {}) {
  const { workflowName, windowDays = 30 } = options;

  const whereClause = workflowName
    ? `WHERE workflow_name = $1 AND created_at > NOW() - INTERVAL '${windowDays} days'`
    : `WHERE created_at > NOW() - INTERVAL '${windowDays} days'`;

  const params = workflowName ? [workflowName] : [];

  const result = await pool.query(
    `
    SELECT
      workflow_name,
      COUNT(*) as total_predictions,
      AVG(prediction_confidence) as avg_confidence,
      AVG(duration_error_pct) as avg_duration_error_pct,
      AVG(cost_error_pct) as avg_cost_error_pct,
      AVG(quality_error_abs) as avg_quality_error_abs,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_error_pct) as median_duration_error_pct,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cost_error_pct) as median_cost_error_pct,
      PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY duration_error_pct) as p90_duration_error_pct,
      PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY cost_error_pct) as p90_cost_error_pct
    FROM workflow.prediction_accuracy
    ${whereClause}
    GROUP BY workflow_name
    ORDER BY total_predictions DESC
    `,
    params
  );

  return result.rows;
}

/**
 * Get circuit breaker status
 * @returns {Object} Circuit breaker state
 */
function getCircuitBreakerStatus() {
  return {
    state: circuitBreaker.state,
    failures: circuitBreaker.failures,
    lastFailureTime: circuitBreaker.lastFailureTime,
    isOpen: circuitBreaker.state === 'OPEN',
  };
}

/**
 * Reset circuit breaker manually
 */
function resetCircuitBreaker() {
  circuitBreaker.state = 'CLOSED';
  circuitBreaker.failures = 0;
  circuitBreaker.lastFailureTime = null;
  circuitBreaker.halfOpenRequests = 0;
}

module.exports = {
  predictWorkflow,
  executeWithPrediction,
  logPredictionAccuracy,
  getPredictionAccuracy,
  getCircuitBreakerStatus,
  resetCircuitBreaker,
  // Internal exports for testing
  _httpRequest: httpRequest,
  _retryWithBackoff: retryWithBackoff,
  _getFallbackPrediction: getFallbackPrediction,
  _createPredictionAccuracyTable: createPredictionAccuracyTable,
};
