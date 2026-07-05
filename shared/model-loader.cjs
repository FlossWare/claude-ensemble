/**
 * Model Loader - JavaScript interface for all 60 trained .pkl models
 *
 * Usage:
 *   const { predict, predictBatch, listModels, getModelInfo } = require('./shared/model-loader.cjs');
 *
 *   // Single prediction
 *   const result = await predict('complexity_estimator', {
 *     prompt_length: 100,
 *     word_count: 50,
 *     num_implement: 1,
 *     // ... other features
 *   });
 *
 *   // Batch predictions (parallel)
 *   const results = await predictBatch([
 *     { model: 'bug_predictor', features: {...} },
 *     { model: 'cost_optimizer', features: {...} },
 *   ]);
 *
 *   // List all models
 *   const models = await listModels();
 *
 *   // Get model info
 *   const info = await getModelInfo('complexity_estimator');
 */

const { execFileSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const PYTHON_HELPER = path.join(__dirname, 'model-loader-helper.py');
const MODEL_DIR = path.join(require('os').homedir(), '.claude', 'learning');

// In-memory cache for model metadata (not the models themselves - Python loads those)
const modelCache = new Map();
const modelInfoCache = new Map();

// Persistent Python daemon for model caching
let pythonDaemon = null;
let daemonReady = false;
let requestQueue = [];
let requestId = 0;

/**
 * Start the persistent Python daemon
 */
function startDaemon() {
  if (pythonDaemon && !pythonDaemon.killed) {
    return; // Already running
  }

  pythonDaemon = spawn('python3', [PYTHON_HELPER, 'daemon'], {
    stdio: ['pipe', 'pipe', 'pipe']
  });

  let responseBuffer = '';

  pythonDaemon.stdout.on('data', (data) => {
    responseBuffer += data.toString();

    // Process complete JSON lines
    const lines = responseBuffer.split('\n');
    responseBuffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const response = JSON.parse(line);

        // Check if this is the ready signal
        if (response.status === 'ready') {
          daemonReady = true;
          processRequestQueue();
          return;
        }

        // Find waiting request
        const waiting = requestQueue.find(r => r.waiting);
        if (waiting) {
          waiting.waiting = false;
          waiting.resolve(response);
        }
      } catch (e) {
        // Invalid JSON - ignore
      }
    }
  });

  pythonDaemon.stderr.on('data', (data) => {
    console.error('Python daemon error:', data.toString());
  });

  pythonDaemon.on('exit', (code) => {
    daemonReady = false;
    pythonDaemon = null;

    // Reject all pending requests
    for (const req of requestQueue) {
      if (req.waiting) {
        req.reject(new Error(`Python daemon exited with code ${code}`));
      }
    }
    requestQueue = [];
  });
}

/**
 * Process queued requests
 */
function processRequestQueue() {
  if (!daemonReady || !pythonDaemon) return;

  const nextRequest = requestQueue.find(r => !r.sent);
  if (nextRequest) {
    nextRequest.sent = true;
    nextRequest.waiting = true;
    pythonDaemon.stdin.write(JSON.stringify(nextRequest.request) + '\n');
  }
}

/**
 * Send request to daemon
 */
function sendDaemonRequest(request, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const req = {
      request,
      resolve,
      reject,
      sent: false,
      waiting: false,
      id: requestId++
    };

    requestQueue.push(req);

    // Set timeout
    const timer = setTimeout(() => {
      const index = requestQueue.indexOf(req);
      if (index !== -1) {
        requestQueue.splice(index, 1);
        reject(new Error(`Request timeout (>${timeout}ms)`));
      }
    }, timeout);

    // Clear timeout on resolve/reject
    const originalResolve = req.resolve;
    const originalReject = req.reject;

    req.resolve = (value) => {
      clearTimeout(timer);
      const index = requestQueue.indexOf(req);
      if (index !== -1) requestQueue.splice(index, 1);
      processRequestQueue(); // Process next request
      originalResolve(value);
    };

    req.reject = (error) => {
      clearTimeout(timer);
      const index = requestQueue.indexOf(req);
      if (index !== -1) requestQueue.splice(index, 1);
      processRequestQueue(); // Process next request
      originalReject(error);
    };

    // Start daemon if not running
    if (!pythonDaemon) {
      startDaemon();
    } else if (daemonReady) {
      processRequestQueue();
    }
  });
}

/**
 * Execute Python helper and parse JSON response
 * Uses daemon mode by default for caching, falls back to CLI mode
 */
function runPythonHelper(args, timeout = 30000, useDaemon = true) {
  // Try daemon mode first if enabled
  if (useDaemon) {
    const command = args[0];
    const request = { command };

    if (command === 'predict') {
      request.model_name = args[1];
      request.features = JSON.parse(args[2]);
    } else if (command === 'info') {
      request.model_name = args[1];
    }

    return sendDaemonRequest(request, timeout).catch((error) => {
      // Fallback to CLI mode on daemon error
      console.warn('Daemon mode failed, falling back to CLI:', error.message);
      return runPythonHelperCLI(args, timeout);
    });
  }

  // Use CLI mode
  return runPythonHelperCLI(args, timeout);
}

/**
 * Execute Python helper in CLI mode (one-shot)
 */
function runPythonHelperCLI(args, timeout = 30000) {
  try {
    const result = execFileSync('python3', [PYTHON_HELPER, ...args], {
      encoding: 'utf8',
      timeout,
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer for large responses
    });
    return JSON.parse(result.trim());
  } catch (error) {
    // Check if it's a timeout
    if (error.killed) {
      return { error: `Python helper timeout (>${timeout}ms)` };
    }
    // Parse stderr if available
    const stderr = error.stderr?.toString() || '';
    const stdout = error.stdout?.toString() || '';

    try {
      // Try to parse error as JSON
      const parsed = JSON.parse(stderr || stdout);
      return parsed;
    } catch {
      return {
        error: `Python helper failed: ${error.message}`,
        stderr,
        stdout
      };
    }
  }
}

/**
 * Predict using a trained model
 * @param {string} modelName - Name of the model (without .pkl extension)
 * @param {Object|Array} features - Features as dict or array
 * @param {Object} options - Prediction options
 * @returns {Promise<Object>} Prediction result
 */
async function predict(modelName, features, options = {}) {
  // Validate modelName against allowlist to prevent path traversal
  if (!AVAILABLE_MODELS.includes(modelName)) {
    return {
      error: `Invalid model name: ${modelName}. Must be one of the available models.`,
      availableModels: AVAILABLE_MODELS
    };
  }

  const timeout = options.timeout || 30000;
  const cache = options.cache !== false;

  // Cache key for identical predictions
  const cacheKey = cache ? `${modelName}:${JSON.stringify(features)}` : null;
  if (cacheKey && modelCache.has(cacheKey)) {
    const cached = modelCache.get(cacheKey);
    // Cache for 5 minutes
    if (Date.now() - cached.timestamp < 5 * 60 * 1000) {
      return { ...cached.result, cached: true };
    }
  }

  const result = runPythonHelper(
    ['predict', modelName, JSON.stringify(features)],
    timeout
  );

  if (result.error) {
    return result;
  }

  // Cache successful predictions
  if (cacheKey) {
    modelCache.set(cacheKey, {
      result,
      timestamp: Date.now()
    });
  }

  return result;
}

/**
 * Predict with multiple models in parallel
 * @param {Array<{model: string, features: Object|Array}>} predictions
 * @param {Object} options - Options for all predictions
 * @returns {Promise<Array>} Array of prediction results
 */
async function predictBatch(predictions, options = {}) {
  const maxParallel = options.maxParallel || 8; // Limit concurrent Python processes
  const results = [];

  // Process in batches
  for (let i = 0; i < predictions.length; i += maxParallel) {
    const batch = predictions.slice(i, i + maxParallel);
    const batchResults = await Promise.all(
      batch.map(({ model, features }) => predict(model, features, options))
    );
    results.push(...batchResults);
  }

  return results;
}

/**
 * List all available models
 * @returns {Promise<Object>} {models: string[], count: number}
 */
async function listModels() {
  const result = runPythonHelper(['list']);
  return result;
}

/**
 * Get information about a model
 * @param {string} modelName - Name of the model
 * @returns {Promise<Object>} Model metadata
 */
async function getModelInfo(modelName) {
  // Validate modelName against allowlist to prevent path traversal
  if (!AVAILABLE_MODELS.includes(modelName)) {
    return {
      error: `Invalid model name: ${modelName}. Must be one of the available models.`,
      availableModels: AVAILABLE_MODELS
    };
  }

  // Check cache
  if (modelInfoCache.has(modelName)) {
    const cached = modelInfoCache.get(modelName);
    // Cache model info for 1 hour
    if (Date.now() - cached.timestamp < 60 * 60 * 1000) {
      return { ...cached.info, cached: true };
    }
  }

  const result = runPythonHelper(['info', modelName]);

  if (!result.error) {
    modelInfoCache.set(modelName, {
      info: result,
      timestamp: Date.now()
    });
  }

  return result;
}

/**
 * Check if a model exists
 * @param {string} modelName - Name of the model
 * @returns {boolean}
 */
function modelExists(modelName) {
  const modelPath = path.join(MODEL_DIR, `${modelName}.pkl`);
  return fs.existsSync(modelPath);
}

/**
 * Clear prediction cache (useful after model retraining)
 */
function clearCache() {
  modelCache.clear();
  modelInfoCache.clear();
}

/**
 * Get cache statistics (both JS and Python caches)
 */
async function getCacheStats() {
  const jsStats = {
    predictions: modelCache.size,
    modelInfo: modelInfoCache.size,
    predictionsMemory: JSON.stringify([...modelCache.entries()]).length,
    modelInfoMemory: JSON.stringify([...modelInfoCache.entries()]).length
  };

  // Get Python cache stats
  try {
    const pythonStats = await runPythonHelper(['cache-stats'], 5000);
    return {
      javascript: jsStats,
      python: pythonStats,
      daemon: {
        running: pythonDaemon !== null && !pythonDaemon.killed,
        ready: daemonReady,
        queueLength: requestQueue.length
      }
    };
  } catch (error) {
    return {
      javascript: jsStats,
      python: { error: error.message },
      daemon: {
        running: pythonDaemon !== null && !pythonDaemon.killed,
        ready: daemonReady,
        queueLength: requestQueue.length
      }
    };
  }
}

/**
 * Clear Python model cache
 */
async function clearPythonCache() {
  try {
    return await runPythonHelper(['clear-cache'], 5000);
  } catch (error) {
    return { error: error.message };
  }
}

/**
 * Stop the Python daemon
 */
function stopDaemon() {
  if (pythonDaemon) {
    pythonDaemon.stdin.write(JSON.stringify({ command: 'shutdown' }) + '\n');
    pythonDaemon = null;
    daemonReady = false;
  }
}

/**
 * Restart the Python daemon (useful after model updates)
 */
async function restartDaemon() {
  stopDaemon();
  await clearPythonCache();
  startDaemon();
}

// Specific model prediction helpers (for commonly used models)

/**
 * Estimate code complexity
 */
async function predictComplexity(codeMetrics) {
  return predict('complexity_estimator', codeMetrics);
}

/**
 * Predict bug likelihood
 */
async function predictBugRisk(codeMetrics) {
  return predict('bug_predictor', codeMetrics);
}

/**
 * Optimize cost for a task
 */
async function predictCost(taskMetrics) {
  return predict('cost_optimizer', taskMetrics);
}

/**
 * Optimize worker count
 */
async function predictWorkerCount(taskMetrics) {
  return predict('worker_count_optimizer', taskMetrics);
}

/**
 * Predict optimal worker assignment
 */
async function predictWorker(taskMetrics) {
  return predict('worker_predictor', taskMetrics);
}

/**
 * Predict team velocity
 */
async function predictVelocity(sprintMetrics) {
  return predict('team_velocity_predictor', sprintMetrics);
}

/**
 * Quantify technical debt
 */
async function predictTechDebt(codeMetrics) {
  return predict('tech_debt_quantifier', codeMetrics);
}

/**
 * Analyze dependency risks
 */
async function predictDependencyRisk(dependencyMetrics) {
  return predict('dependency_risk_analyzer', dependencyMetrics);
}

/**
 * Predict merge conflict likelihood
 */
async function predictMergeConflict(branchMetrics) {
  return predict('merge_conflict_predictor', branchMetrics);
}

/**
 * Predict resource usage
 */
async function predictResourceUsage(taskMetrics) {
  return predict('resource_usage_predictor', taskMetrics);
}

/**
 * Predict user intent
 */
async function predictIntent(queryMetrics) {
  return predict('intent_predictor', queryMetrics);
}

/**
 * Detect security vulnerabilities
 */
async function predictVulnerability(codeMetrics) {
  return predict('vulnerability_detector', codeMetrics);
}

/**
 * Optimize performance
 */
async function predictPerformance(systemMetrics) {
  return predict('performance_optimizer', systemMetrics);
}

/**
 * Predict test coverage
 */
async function predictTests(codeMetrics) {
  return predict('test_generator', codeMetrics);
}

/**
 * All available models (60 total as of 2026-07-04)
 */
const AVAILABLE_MODELS = [
  'abductive_reasoner',
  'access_pattern_analyzer',
  'active_learning',
  'analogical_reasoning',
  'architecture_reviewer',
  'automl_system',
  'bayesian_reasoner',
  'breaking_change_detector',
  'bug_predictor',
  'causal_inference_expert_category',
  'causal_inference_expert_severity',
  'causal_inference_expert_vectorizer',
  'code_review_pattern_extractor',
  'complexity_estimator',
  'constraint_satisfaction',
  'context_fusion_model',
  'cost_optimizer',
  'counterfactual_reasoner',
  'curriculum_designer',
  'dependency_risk_analyzer',
  'developer_preference_learner',
  'doc_generator',
  'error_recovery_classifier',
  'fedramp_expert',
  'fedramp_expert_vectorizer',
  'formal_verification_expert',
  'gdpr_expert_category',
  'gdpr_expert_severity',
  'gdpr_expert_vectorizer',
  'hyperparameter_optimizer',
  'intent_predictor',
  'issue_correlator_model',
  'knowledge_graph_embeddings',
  'knowledge_transfer_cache',
  'knowledge_transfer_optimizer',
  'load_balancer_optimizer',
  'memory_usage_predictor',
  'merge_conflict_predictor',
  'network_latency_models',
  'novelty_detector_model',
  'performance_optimizer',
  'prompt_patterns',
  'query_optimizer',
  'refactoring_strategist',
  'resource_usage_predictor',
  'secrets_scanner',
  'security_auditor',
  'service_mesh_category_clf',
  'service_mesh_type_clf',
  'service_mesh_vectorizer',
  'symbolic_reasoning_expert',
  'team_velocity_predictor',
  'tech_debt_quantifier',
  'temporal_reasoning_model',
  'test_generator',
  'transfer_learning',
  'verification_predictor',
  'vulnerability_detector',
  'worker_count_optimizer',
  'worker_predictor',
  'worker_reliability_model'
];

module.exports = {
  // Core functions
  predict,
  predictBatch,
  listModels,
  getModelInfo,
  modelExists,
  clearCache,
  getCacheStats,

  // Daemon management
  startDaemon,
  stopDaemon,
  restartDaemon,
  clearPythonCache,

  // Specific helpers
  predictComplexity,
  predictBugRisk,
  predictCost,
  predictWorkerCount,
  predictWorker,
  predictVelocity,
  predictTechDebt,
  predictDependencyRisk,
  predictMergeConflict,
  predictResourceUsage,
  predictIntent,
  predictVulnerability,
  predictPerformance,
  predictTests,

  // Constants
  AVAILABLE_MODELS,
  MODEL_DIR,
};
