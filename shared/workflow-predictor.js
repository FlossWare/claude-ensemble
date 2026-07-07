/**
 * Workflow Predictor - ML-driven workflow execution predictions
 *
 * Wraps workflow execution with predictive analytics:
 * - Cost prediction (token usage, API costs)
 * - Duration prediction (total execution time)
 * - Quality prediction (expected output quality)
 * - Success prediction (probability of successful completion)
 * - Model selection (best model for task type)
 *
 * Integrates with:
 * - model-loader.js (dynamic model selection)
 * - PostgreSQL monitoring.prediction_accuracy (learning from feedback)
 * - Multiple ML predictors (intent, build time, network, etc.)
 *
 * Usage:
 *   import { executeWithPrediction } from './shared/workflow-predictor.js';
 *
 *   const result = await executeWithPrediction(myWorkflow, {
 *     taskDescription: 'Research firmware reverse engineering',
 *     workerCount: 6,
 *     qualityThreshold: 0.8,
 *     askUserApproval: true  // Show prediction, prompt Y/N
 *   });
 *
 * Created: 2026-07-04
 */

import { Pool } from 'pg';
import { execSync, execFile } from 'child_process';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import readline from 'readline';

// Use actual exports from model-loader.cjs
import {
  predict as mlPredict,
  predictCost as mlPredictCost,
  predictWorkerCount as mlPredictWorkerCount,
  predictResourceUsage as mlPredictResourceUsage,
  predictIntent as mlPredictIntent,
  predictBugRisk as mlPredictBugRisk,
  AVAILABLE_MODELS
} from './model-loader.cjs';

// Input validation
import {
  sanitizeTaskDescription,
  validateWorkerCount,
  sanitizeModelName,
  ValidationError
} from './input-validation.cjs';

// PostgreSQL connection pool (reuse from model-loader)
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER || 'claude',
  password: process.env.PGPASSWORD,
  max: 5,
  idleTimeoutMillis: 30000,
});

// Mutex for getUserApproval to prevent concurrent readline interface creation
let userApprovalLock = Promise.resolve();

pool.on('error', (err) => {
  console.error('[workflow-predictor] PostgreSQL pool error:', err.message);
});

/**
 * Check if prediction_accuracy table exists (gracefully handle permission issues)
 */
async function ensurePredictionTable() {
  try {
    const { rows } = await pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'monitoring'
        AND table_name = 'prediction_accuracy'
      )
    `);

    if (rows[0].exists) {
      // Table already exists, just return
      return;
    }

    // Table doesn't exist, try to create it
    console.log('[workflow-predictor] Creating monitoring.prediction_accuracy table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS monitoring.prediction_accuracy (
        id SERIAL PRIMARY KEY,
        workflow_id VARCHAR(64) NOT NULL,
        workflow_name VARCHAR(255) NOT NULL,
        task_description TEXT NOT NULL,

        -- Predictions
        predicted_cost_usd NUMERIC(10, 4),
        predicted_duration_ms BIGINT,
        predicted_quality NUMERIC(3, 2),
        predicted_success_prob NUMERIC(3, 2),
        predicted_best_model VARCHAR(64),

        -- Actuals
        actual_cost_usd NUMERIC(10, 4),
        actual_duration_ms BIGINT,
        actual_quality NUMERIC(3, 2),
        actual_success BOOLEAN,
        actual_model_used VARCHAR(64),

        -- Errors (absolute and percentage)
        cost_error_pct NUMERIC(5, 2),
        duration_error_pct NUMERIC(5, 2),
        quality_error_pct NUMERIC(5, 2),
        model_match BOOLEAN,

        -- Metadata
        predictor_version VARCHAR(32) DEFAULT '1.0',
        prediction_confidence NUMERIC(3, 2),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_workflow_id
        ON monitoring.prediction_accuracy(workflow_id);
      CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_created_at
        ON monitoring.prediction_accuracy(created_at DESC);
      CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_errors
        ON monitoring.prediction_accuracy(cost_error_pct, duration_error_pct);
    `);
    console.log('[workflow-predictor] Table created successfully');
  } catch (err) {
    // Gracefully handle permission errors - table might exist but owned by different user
    if (err.message.includes('must be owner') || err.message.includes('permission denied')) {
      console.warn('[workflow-predictor] Table exists but cannot modify (owned by different user) - continuing anyway');
      return;
    }
    console.error('[workflow-predictor] Failed to ensure prediction table:', err.message);
    throw err;
  }
}

/**
 * Predict workflow cost based on task description and worker count
 *
 * Uses:
 * - Historical data from workflow.executions
 * - Model costs from api_models table
 * - Intent prediction for task type
 *
 * @param {Object} config - { taskDescription, workerCount, models }
 * @returns {Promise<number>} Predicted cost in USD
 */
async function predictCost(config) {
  const { taskDescription, workerCount = 5, models = [] } = config;

  try {
    // Select models (use provided models or default to sonnet/haiku mix)
    const selectedModels = models.length > 0 ? models :
      Array(workerCount).fill(null).map((_, i) => i % 2 === 0 ? 'sonnet' : 'haiku');

    // Model pricing (from OpenRouter/Anthropic pricing)
    const modelPricing = {
      'opus': { costIn: 0.015, costOut: 0.075 },
      'sonnet': { costIn: 0.003, costOut: 0.015 },
      'haiku': { costIn: 0.00025, costOut: 0.00125 },
      'fable': { costIn: 0.00025, costOut: 0.00125 },
      'gpt-4o': { costIn: 0.0025, costOut: 0.01 },
      'automl': { costIn: 0.0005, costOut: 0.0015 }
    };

    // Estimate tokens per worker (based on historical data)
    const { rows: historicalData } = await pool.query(`
      SELECT AVG(wr.input_tokens) as avg_input, AVG(wr.output_tokens) as avg_output
      FROM workflow.worker_results wr
      JOIN workflow.executions we ON wr.workflow_execution_id = we.id
      WHERE we.outcome = 'success'
      AND we.created_at > NOW() - INTERVAL '30 days'
    `);

    const avgInput = historicalData[0]?.avg_input || 2000;
    const avgOutput = historicalData[0]?.avg_output || 1000;

    // Calculate cost per model
    let totalCost = 0;
    for (const modelName of selectedModels) {
      const pricing = modelPricing[modelName] || modelPricing['haiku']; // Default to cheapest
      const inputCost = (avgInput / 1000) * pricing.costIn;
      const outputCost = (avgOutput / 1000) * pricing.costOut;
      totalCost += inputCost + outputCost;
    }

    // Add arbiter cost (20% more tokens than worker, use opus for arbiter)
    const arbiterPricing = modelPricing['opus'];
    const arbiterInputCost = (avgInput * 1.2 / 1000) * arbiterPricing.costIn;
    const arbiterOutputCost = (avgOutput * 1.2 / 1000) * arbiterPricing.costOut;
    totalCost += arbiterInputCost + arbiterOutputCost;

    return parseFloat(totalCost.toFixed(4));
  } catch (err) {
    console.error('[workflow-predictor] Cost prediction failed:', err.message);
    // Fallback estimate: $0.10 per worker
    return workerCount * 0.10;
  }
}

/**
 * Predict workflow duration based on task type and complexity
 *
 * Uses:
 * - Historical execution times from workflow.executions
 * - Network latency predictions
 * - Build time predictions (if applicable)
 *
 * @param {Object} config - { taskDescription, workerCount }
 * @returns {Promise<number>} Predicted duration in milliseconds
 */
async function predictDuration(config) {
  const { taskDescription, workerCount = 5 } = config;

  try {
    // Query historical data for similar workflows
    const { rows: similar } = await pool.query(`
      SELECT AVG(total_duration_ms) as avg_duration
      FROM workflow.executions
      WHERE outcome = 'success'
      AND total_workers = $1
      AND created_at > NOW() - INTERVAL '30 days'
      LIMIT 100
    `, [workerCount]);

    const baselineDuration = similar[0]?.avg_duration || 45000; // 45s default

    // Adjust for task complexity (simple heuristic based on description length)
    const complexityFactor = Math.min(2.0, taskDescription.length / 100);

    // Adjust for parallelism (more workers = faster, but diminishing returns)
    const parallelismFactor = Math.max(0.5, 1.0 - (workerCount * 0.05));

    const predicted = baselineDuration * complexityFactor * parallelismFactor;

    return Math.round(predicted);
  } catch (err) {
    console.error('[workflow-predictor] Duration prediction failed:', err.message);
    // Fallback: 30s + 5s per worker
    return 30000 + (workerCount * 5000);
  }
}

/**
 * Predict workflow quality (consensus confidence)
 *
 * Uses:
 * - Historical quality scores from workflow.arbiter_decisions
 * - Model capability matrix
 * - Task-model alignment
 *
 * @param {Object} config - { taskDescription, models }
 * @returns {Promise<number>} Predicted quality (0-1)
 */
async function predictQuality(config) {
  const { taskDescription, models = [] } = config;

  try {
    // Get historical quality scores (use confidence instead of quality_score)
    const { rows: historicalQuality } = await pool.query(`
      SELECT AVG(confidence) as avg_quality
      FROM workflow.arbiter_decisions
      WHERE created_at > NOW() - INTERVAL '30 days'
    `);

    const baselineQuality = historicalQuality[0]?.avg_quality || 0.75;

    // Check if we have diverse model selection (diversity improves quality)
    const selectedModels = models.length > 0 ? models :
      ['opus', 'sonnet', 'haiku', 'fable', 'gpt-4o'];

    // Map models to providers
    const modelProviders = {
      'opus': 'anthropic',
      'sonnet': 'anthropic',
      'haiku': 'anthropic',
      'fable': 'anthropic',
      'gpt-4o': 'openai',
      'gemini-2.0-flash-exp': 'google',
      'automl': 'mixed'
    };

    // Count unique providers
    const providers = new Set(selectedModels.map(m => modelProviders[m] || 'unknown'));

    // Diversity bonus: +0.05 quality per unique provider
    const diversityBonus = Math.min(0.15, (providers.size - 1) * 0.05);

    const predictedQuality = Math.min(0.99, baselineQuality + diversityBonus);

    return parseFloat(predictedQuality.toFixed(2));
  } catch (err) {
    console.error('[workflow-predictor] Quality prediction failed:', err.message);
    return 0.75; // Conservative estimate
  }
}

/**
 * Predict workflow success probability
 *
 * Uses:
 * - Historical success rates from workflow.executions
 * - Model reliability scores
 * - Circuit breaker state
 *
 * @param {Object} config - { taskDescription, models }
 * @returns {Promise<number>} Success probability (0-1)
 */
async function predictSuccess(config) {
  const { taskDescription, models = [] } = config;

  try {
    // Overall success rate (last 30 days)
    const { rows: successRate } = await pool.query(`
      SELECT
        COUNT(*) FILTER (WHERE outcome = 'success') * 1.0 / NULLIF(COUNT(*), 0) as success_rate
      FROM workflow.executions
      WHERE created_at > NOW() - INTERVAL '30 days'
    `);

    const baselineSuccess = successRate[0]?.success_rate || 0.85;

    // Check circuit breaker state (degraded = lower success prob)
    const { rows: circuitBreakers } = await pool.query(`
      SELECT COUNT(*) as open_breakers
      FROM monitoring.circuit_breaker_events
      WHERE event = 'open'
      AND created_at > NOW() - INTERVAL '5 minutes'
    `);

    const circuitBreakerPenalty = (circuitBreakers[0]?.open_breakers || 0) * 0.1;

    const predictedSuccess = Math.max(0.5, baselineSuccess - circuitBreakerPenalty);

    return parseFloat(predictedSuccess.toFixed(2));
  } catch (err) {
    console.error('[workflow-predictor] Success prediction failed:', err.message);
    return 0.85; // Optimistic default
  }
}

/**
 * Select best model for task using intent prediction + Thompson Sampling
 *
 * @param {Object} config - { taskDescription }
 * @returns {Promise<string>} Best model name
 */
async function predictBestModel(config) {
  const { taskDescription } = config;

  try {
    // Try intent predictor if available (non-blocking with 2s timeout)
    const intentScript = join(
      homedir(),
      'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/predict_intent.py'
    );

    if (existsSync(intentScript)) {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Intent prediction timeout')), 2000)
      );

      const execPromise = new Promise((resolve, reject) => {
        execFile('python3', [intentScript, taskDescription, '--json'], {
          encoding: 'utf-8',
          maxBuffer: 1024 * 1024,
          timeout: 2000,
        }, (err, stdout) => {
          if (err) return reject(err);
          resolve(stdout);
        });
      });

      const result = await Promise.race([execPromise, timeoutPromise]);
      const prediction = JSON.parse(result);

      // Map intent to model (simple heuristic)
      const intentModelMap = {
        'code_generation': 'sonnet',
        'code_review': 'opus',
        'research': 'opus',
        'debugging': 'sonnet',
        'data_analysis': 'sonnet',
        'documentation': 'haiku',
        'system_ops': 'haiku',
      };

      const bestModel = intentModelMap[prediction.primary_intent] || 'sonnet';
      return bestModel;
    }
  } catch (err) {
    // Silently fall through to Thompson Sampling
  }

  // Fallback: Thompson Sampling (best performing model from history)
  try {
    const { rows: modelPerf } = await pool.query(`
      SELECT model, AVG(confidence) as avg_quality, COUNT(*) as uses
      FROM workflow.worker_results
      WHERE outcome = 'success'
      AND created_at > NOW() - INTERVAL '30 days'
      GROUP BY model
      ORDER BY avg_quality DESC, uses DESC
      LIMIT 1
    `);

    return modelPerf[0]?.model || 'sonnet';
  } catch (err) {
    console.error('[workflow-predictor] Model selection failed:', err.message);
    return 'sonnet'; // Safe default
  }
}

/**
 * Predict optimal worker count using ML model
 *
 * @param {Object} config - { taskDescription, complexity }
 * @returns {Promise<number>} Optimal worker count
 */
async function predictOptimalWorkers(config) {
  const { taskDescription, complexity = 'medium' } = config;

  try {
    // Use worker_count_optimizer model with timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Worker count prediction timeout')), 2000)
    );

    const result = await Promise.race([
      mlPredictWorkerCount({
        task_description: taskDescription,
        complexity_level: complexity === 'low' ? 1 : complexity === 'medium' ? 2 : 3,
        estimated_subtasks: taskDescription.split(',').length, // Heuristic: count comma-separated items
      }),
      timeoutPromise
    ]);

    if (result.error) {
      console.warn('[workflow-predictor] Worker count prediction unavailable:', result.error);
      return 5; // Default fallback
    }

    return Math.max(1, Math.min(8, Math.round(result.prediction || 5)));
  } catch (err) {
    console.warn('[workflow-predictor] Worker count prediction failed:', err.message);
    return 5;
  }
}

/**
 * Predict workflow pattern (sequential, parallel, fan-out, etc.)
 *
 * @param {Object} config - { taskDescription }
 * @returns {Promise<string>} Recommended pattern
 */
async function predictWorkflowPattern(config) {
  const { taskDescription } = config;

  try {
    // Use intent predictor to determine pattern with timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Pattern prediction timeout')), 2000)
    );

    const intentResult = await Promise.race([
      mlPredictIntent({ query: taskDescription }),
      timeoutPromise
    ]);

    if (intentResult.error) {
      return 'parallel'; // Safe default
    }

    // Map intent to workflow pattern
    const intentPatternMap = {
      'research': 'fan-out-consensus',
      'code_generation': 'sequential-review',
      'debugging': 'parallel-verify',
      'data_analysis': 'map-reduce',
      'system_ops': 'sequential',
    };

    return intentPatternMap[intentResult.primary_intent] || 'parallel';
  } catch (err) {
    console.warn('[workflow-predictor] Pattern prediction failed:', err.message);
    return 'parallel';
  }
}

/**
 * Predict failure modes and risks
 *
 * @param {Object} config - { taskDescription, models }
 * @returns {Promise<Object>} Failure risk assessment
 */
async function predictFailureRisk(config) {
  const { taskDescription, models = [] } = config;

  try {
    // Use error_recovery_classifier if available with timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Failure risk prediction timeout')), 2000)
    );

    const result = await Promise.race([
      mlPredict('error_recovery_classifier', {
        task_type: taskDescription.includes('code') ? 'code' : 'general',
        model_count: models.length || 5,
        task_complexity: taskDescription.length > 200 ? 'high' : 'medium',
      }),
      timeoutPromise
    ]);

    if (result.error) {
      return { risk: 0.2, failureModes: [] };
    }

    return {
      risk: result.prediction || 0.2,
      failureModes: result.failure_modes || [],
      mitigations: result.mitigations || []
    };
  } catch (err) {
    console.warn('[workflow-predictor] Failure risk prediction failed:', err.message);
    return { risk: 0.2, failureModes: [] };
  }
}

/**
 * Predict memory usage for workflow
 *
 * @param {Object} config - { taskDescription, workerCount }
 * @returns {Promise<number>} Estimated memory in MB
 */
async function predictMemoryUsage(config) {
  const { taskDescription, workerCount = 5 } = config;

  try {
    // With timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Memory prediction timeout')), 2000)
    );

    const result = await Promise.race([
      mlPredictResourceUsage({
        task_description: taskDescription,
        worker_count: workerCount,
        estimated_tokens: taskDescription.length * 2, // Rough estimate
      }),
      timeoutPromise
    ]);

    if (result.error) {
      return workerCount * 100; // 100MB per worker fallback
    }

    return Math.round(result.memory_mb || (workerCount * 100));
  } catch (err) {
    console.warn('[workflow-predictor] Memory prediction failed:', err.message);
    return workerCount * 100;
  }
}

/**
 * Predict bug/issue risk (for git-related workflows)
 *
 * @param {Object} config - { taskDescription, hasGitContext }
 * @returns {Promise<number>} Bug risk (0-1)
 */
async function predictBugProbability(config) {
  const { taskDescription, hasGitContext = false } = config;

  if (!hasGitContext && !taskDescription.match(/\b(code|bug|fix|debug|refactor)\b/i)) {
    return 0; // Not applicable to non-code workflows
  }

  try {
    // With timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Bug risk prediction timeout')), 2000)
    );

    const result = await Promise.race([
      mlPredictBugRisk({
        task_description: taskDescription,
        has_git_context: hasGitContext,
        complexity: taskDescription.length > 200 ? 'high' : 'medium',
      }),
      timeoutPromise
    ]);

    if (result.error) {
      // Fallback: query execution_summary for error rate
      const { rows } = await pool.query(`
        SELECT
          COUNT(*) FILTER (WHERE outcome = 'error') * 1.0 / NULLIF(COUNT(*), 0) as error_rate
        FROM monitoring.execution_summary
        WHERE timestamp > NOW() - INTERVAL '30 days'
        AND task_type LIKE '%code%'
        LIMIT 1000
      `);
      return rows[0]?.error_rate || 0.3;
    }

    return Math.min(1.0, Math.max(0, result.prediction || 0.3));
  } catch (err) {
    console.warn('[workflow-predictor] Bug prediction failed:', err.message);
    return 0.3;
  }
}

/**
 * Generate comprehensive workflow predictions
 *
 * @param {Object} config - Workflow configuration
 * @returns {Promise<Object>} Prediction results
 */
export async function predictWorkflow(config) {
  await ensurePredictionTable();

  // Validate and sanitize inputs
  let taskDescription = config.taskDescription || 'Unknown task';
  let workerCount = config.workerCount || 5;
  let models = config.models || [];
  const hasGitContext = config.hasGitContext || false;

  try {
    taskDescription = sanitizeTaskDescription(taskDescription);
    workerCount = validateWorkerCount(workerCount);
    models = models.map(m => sanitizeModelName(m, { allowUnknown: true }));
  } catch (err) {
    if (err instanceof ValidationError) {
      console.error(`[workflow-predictor] Validation error: ${err.message}`);
      throw err;
    }
    throw err;
  }

  console.log('[workflow-predictor] Generating predictions...');

  const [
    cost,
    duration,
    quality,
    success,
    bestModel,
    optimalWorkers,
    recommendedPattern,
    failureRisk,
    estimatedMemoryMb,
    bugRisk
  ] = await Promise.all([
    predictCost({ taskDescription, workerCount, models }),
    predictDuration({ taskDescription, workerCount }),
    predictQuality({ taskDescription, models }),
    predictSuccess({ taskDescription, models }),
    predictBestModel({ taskDescription }),
    predictOptimalWorkers({ taskDescription }),
    predictWorkflowPattern({ taskDescription }),
    predictFailureRisk({ taskDescription, models }),
    predictMemoryUsage({ taskDescription, workerCount }),
    predictBugProbability({ taskDescription, hasGitContext }),
  ]);

  const prediction = {
    cost: cost,
    duration: duration,
    quality: quality,
    success: success,
    bestModel: bestModel,
    // NEW FIELDS (5 new models)
    optimalWorkers: optimalWorkers,
    recommendedPattern: recommendedPattern,
    failureRisk: failureRisk,
    estimatedMemoryMb: estimatedMemoryMb,
    bugRisk: bugRisk,
    // Overall confidence
    confidence: Math.min(quality, success),
    timestamp: new Date().toISOString(),
  };

  console.log('[workflow-predictor] Predictions:');
  console.log(`  Cost: $${cost.toFixed(4)}`);
  console.log(`  Duration: ${(duration / 1000).toFixed(1)}s`);
  console.log(`  Quality: ${(quality * 100).toFixed(1)}%`);
  console.log(`  Success: ${(success * 100).toFixed(1)}%`);
  console.log(`  Best Model: ${bestModel}`);
  console.log(`  Optimal Workers: ${optimalWorkers}`);
  console.log(`  Recommended Pattern: ${recommendedPattern}`);
  console.log(`  Failure Risk: ${(failureRisk.risk * 100).toFixed(1)}%`);
  console.log(`  Memory Usage: ${estimatedMemoryMb}MB`);
  if (bugRisk > 0) {
    console.log(`  Bug Risk: ${(bugRisk * 100).toFixed(1)}%`);
  }

  return prediction;
}

/**
 * Get user approval for workflow execution
 *
 * Shows predictions and prompts Y/N
 *
 * Uses a mutex to prevent concurrent readline interface creation which causes
 * 'ERR_MULTIPLE_CALLBACK' errors when multiple calls happen simultaneously.
 *
 * @param {Object} prediction - Prediction results from predictWorkflow
 * @param {Object} config - Workflow configuration
 * @returns {Promise<boolean>} User approved (true) or rejected (false)
 */
export async function getUserApproval(prediction, config = {}) {
  const { taskDescription = 'Unknown task', autoApprove = false } = config;

  if (autoApprove) {
    console.log('[workflow-predictor] Auto-approve enabled, skipping user prompt');
    return true;
  }

  // Acquire mutex lock to prevent concurrent readline interface creation
  const previousLock = userApprovalLock;
  let releaseLock;
  userApprovalLock = new Promise((resolve) => {
    releaseLock = resolve;
  });

  try {
    // Wait for any previous getUserApproval calls to complete
    await previousLock;

    console.log('\n' + '='.repeat(80));
    console.log('WORKFLOW EXECUTION PREDICTION');
    console.log('='.repeat(80));
    console.log(`Task: ${taskDescription}`);
    console.log('');
    console.log('Predictions:');
    console.log(`  Estimated Cost:     $${prediction.cost.toFixed(4)}`);
    console.log(`  Estimated Duration: ${(prediction.duration / 1000).toFixed(1)}s (${Math.round(prediction.duration / 60000)} min)`);
    console.log(`  Expected Quality:   ${(prediction.quality * 100).toFixed(1)}%`);
    console.log(`  Success Probability: ${(prediction.success * 100).toFixed(1)}%`);
    console.log(`  Recommended Model:  ${prediction.bestModel}`);
    console.log(`  Overall Confidence: ${(prediction.confidence * 100).toFixed(1)}%`);
    console.log('');
    console.log('='.repeat(80));

    // Create readline interface for user input
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    return await new Promise((resolve) => {
      rl.question('Proceed with workflow execution? (Y/n): ', (answer) => {
        rl.close();
        const approved = !answer || answer.toLowerCase() === 'y' || answer.toLowerCase() === 'yes';
        console.log(approved ? '[workflow-predictor] User approved' : '[workflow-predictor] User rejected');
        resolve(approved);
      });
    });
  } finally {
    // Release the lock when done
    releaseLock();
  }
}

/**
 * Log prediction accuracy (compare predicted vs actual)
 *
 * @param {Object} predicted - Predictions from predictWorkflow
 * @param {Object} actual - Actual results after execution
 * @param {Object} metadata - Additional metadata
 * @returns {Promise<void>}
 */
export async function logPredictionAccuracy(predicted, actual, metadata = {}) {
  await ensurePredictionTable();

  try {
    const costError = Math.abs((actual.cost - predicted.cost) / Math.max(predicted.cost, 0.001)) * 100;
    const durationError = Math.abs((actual.duration - predicted.duration) / Math.max(predicted.duration, 1)) * 100;
    const qualityError = Math.abs((actual.quality - predicted.quality) / Math.max(predicted.quality, 0.001)) * 100;
    const modelMatch = actual.modelUsed === predicted.bestModel;

    await pool.query(`
      INSERT INTO monitoring.prediction_accuracy (
        workflow_id, workflow_name, task_description,
        predicted_cost_usd, predicted_duration_ms, predicted_quality,
        predicted_success_prob, predicted_best_model,
        actual_cost_usd, actual_duration_ms, actual_quality,
        actual_success, actual_model_used,
        cost_error_pct, duration_error_pct, quality_error_pct, model_match,
        prediction_confidence, metadata
      ) VALUES (
        $1, $2, $3,
        $4, $5, $6, $7, $8,
        $9, $10, $11, $12, $13,
        $14, $15, $16, $17,
        $18, $19
      )
    `, [
      metadata.workflowId || 'unknown',
      metadata.workflowName || 'unknown',
      metadata.taskDescription || 'unknown',
      predicted.cost,
      predicted.duration,
      predicted.quality,
      predicted.success,
      predicted.bestModel,
      actual.cost,
      actual.duration,
      actual.quality,
      actual.success || false,
      actual.modelUsed || 'unknown',
      costError,
      durationError,
      qualityError,
      modelMatch,
      predicted.confidence,
      JSON.stringify(metadata),
    ]);

    console.log('[workflow-predictor] Prediction accuracy logged:');
    console.log(`  Cost Error: ${costError.toFixed(1)}%`);
    console.log(`  Duration Error: ${durationError.toFixed(1)}%`);
    console.log(`  Quality Error: ${qualityError.toFixed(1)}%`);
    console.log(`  Model Match: ${modelMatch ? 'YES' : 'NO'}`);
  } catch (err) {
    console.error('[workflow-predictor] Failed to log prediction accuracy:', err.message);
  }
}

/**
 * Monitor resource usage during workflow execution
 *
 * @param {number} intervalMs - Sampling interval in milliseconds
 * @returns {Object} Monitor controller { start, stop, getStats }
 */
function createResourceMonitor(intervalMs = 1000) {
  let intervalId = null;
  let samples = [];

  const getMemoryUsage = () => {
    if (typeof process !== 'undefined' && process.memoryUsage) {
      const mem = process.memoryUsage();
      return {
        rss: mem.rss / 1024 / 1024, // MB
        heapUsed: mem.heapUsed / 1024 / 1024,
        heapTotal: mem.heapTotal / 1024 / 1024,
      };
    }
    return null;
  };

  return {
    start() {
      samples = [];
      intervalId = setInterval(() => {
        const mem = getMemoryUsage();
        if (mem) {
          samples.push({
            timestamp: Date.now(),
            ...mem,
          });
        }
      }, intervalMs);
    },

    stop() {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    },

    getStats() {
      if (samples.length === 0) return null;

      const rssValues = samples.map(s => s.rss);
      const heapValues = samples.map(s => s.heapUsed);

      return {
        peakRssMb: Math.max(...rssValues),
        avgRssMb: rssValues.reduce((a, b) => a + b, 0) / rssValues.length,
        peakHeapMb: Math.max(...heapValues),
        avgHeapMb: heapValues.reduce((a, b) => a + b, 0) / heapValues.length,
        sampleCount: samples.length,
      };
    },
  };
}

/**
 * Execute workflow with prediction wrapper
 *
 * Complete flow:
 * 1. Generate predictions
 * 2. Get user approval (optional)
 * 3. Execute workflow with resource monitoring
 * 4. Log prediction accuracy
 *
 * @param {Function} workflowFn - Async workflow function to execute
 * @param {Object} config - Workflow configuration
 * @returns {Promise<Object>} Workflow result + prediction metadata
 */
export async function executeWithPrediction(workflowFn, config = {}) {
  const {
    taskDescription = 'Unknown task',
    workerCount = 5,
    models = [],
    askUserApproval = false,
    autoApprove = false,
    workflowId = `wf-${Date.now()}`,
    workflowName = 'unnamed-workflow',
    hasGitContext = false,
    monitorResources = true,
  } = config;

  // Step 1: Generate predictions
  const prediction = await predictWorkflow({
    taskDescription,
    workerCount,
    models,
    hasGitContext,
  });

  // Step 2: Get user approval (if requested)
  if (askUserApproval) {
    const approved = await getUserApproval(prediction, { taskDescription, autoApprove });
    if (!approved) {
      console.log('[workflow-predictor] Execution cancelled by user');
      return {
        cancelled: true,
        prediction,
      };
    }
  }

  // Step 3: Start resource monitoring
  const resourceMonitor = monitorResources ? createResourceMonitor(1000) : null;
  if (resourceMonitor) {
    resourceMonitor.start();
  }

  // Step 4: Execute workflow
  console.log('[workflow-predictor] Starting workflow execution...');
  const startTime = Date.now();
  let result;
  let error = null;

  try {
    result = await workflowFn(config);
  } catch (err) {
    error = err;
    console.error('[workflow-predictor] Workflow execution failed:', err.message);
  } finally {
    // Stop resource monitoring
    if (resourceMonitor) {
      resourceMonitor.stop();
    }
  }

  const actualDuration = Date.now() - startTime;
  const resourceStats = resourceMonitor ? resourceMonitor.getStats() : null;

  // Step 5: Extract actual metrics from result
  const actual = {
    cost: result?.cost || 0,
    duration: actualDuration,
    quality: result?.quality || 0,
    success: !error && result?.success !== false,
    modelUsed: result?.modelUsed || prediction.bestModel,
    // Resource usage
    peakMemoryMb: resourceStats?.peakRssMb || 0,
    avgMemoryMb: resourceStats?.avgRssMb || 0,
  };

  // Step 6: Log prediction accuracy (including new fields)
  await logPredictionAccuracy(prediction, actual, {
    workflowId,
    workflowName,
    taskDescription,
    error: error?.message,
    resourceStats,
  });

  // Log resource prediction accuracy
  if (resourceStats && prediction.estimatedMemoryMb) {
    const memoryError = Math.abs((resourceStats.peakRssMb - prediction.estimatedMemoryMb) / Math.max(prediction.estimatedMemoryMb, 1)) * 100;
    console.log(`[workflow-predictor] Memory prediction error: ${memoryError.toFixed(1)}% (predicted: ${prediction.estimatedMemoryMb}MB, actual: ${resourceStats.peakRssMb.toFixed(1)}MB)`);
  }

  if (error) {
    throw error;
  }

  return {
    ...result,
    prediction,
    actual,
    resourceStats,
    predictionAccuracy: {
      costError: Math.abs((actual.cost - prediction.cost) / Math.max(prediction.cost, 0.001)) * 100,
      durationError: Math.abs((actual.duration - prediction.duration) / Math.max(prediction.duration, 1)) * 100,
      qualityError: Math.abs((actual.quality - prediction.quality) / Math.max(prediction.quality, 0.001)) * 100,
      memoryError: resourceStats ? Math.abs((resourceStats.peakRssMb - prediction.estimatedMemoryMb) / Math.max(prediction.estimatedMemoryMb, 1)) * 100 : null,
    },
  };
}

/**
 * Get prediction accuracy stats (for model improvement)
 *
 * @param {number} days - Number of days to look back (default: 30)
 * @returns {Promise<Object>} Accuracy statistics
 */
export async function getPredictionStats(days = 30) {
  await ensurePredictionTable();

  try {
    const { rows } = await pool.query(`
      SELECT
        COUNT(*) as total_predictions,
        AVG(prediction_error_percent) as avg_prediction_error,
        AVG(ABS(predicted_cost_usd - actual_cost_usd) / NULLIF(predicted_cost_usd, 0) * 100) as avg_cost_error,
        AVG(ABS(predicted_duration_ms - actual_duration_ms) / NULLIF(predicted_duration_ms, 0) * 100) as avg_duration_error
      FROM monitoring.prediction_accuracy
      WHERE created_at > NOW() - INTERVAL '${days} days'
    `);

    const stats = rows[0] || {};

    console.log('\n[workflow-predictor] Prediction Accuracy Statistics:');
    console.log(`  Total Predictions: ${stats.total_predictions || 0}`);
    console.log(`  Avg Cost Error: ${parseFloat(stats.avg_cost_error || 0).toFixed(1)}%`);
    console.log(`  Avg Duration Error: ${parseFloat(stats.avg_duration_error || 0).toFixed(1)}%`);
    console.log(`  Avg Overall Error: ${parseFloat(stats.avg_prediction_error || 0).toFixed(1)}%`);

    return stats;
  } catch (err) {
    console.error('[workflow-predictor] Failed to get prediction stats:', err.message);
    return {};
  }
}

// Export pool for external use
export { pool };
