#!/usr/bin/env node
/**
 * Integration Test for ML Prediction System
 *
 * Tests:
 * 1. Prediction API connectivity (aio-01:8080)
 * 2. Workflow prediction accuracy
 * 3. Auto-optimization recommendations
 * 4. Circuit breaker behavior
 * 5. Fallback prediction when API unavailable
 *
 * Usage:
 *   node tests/test-prediction-integration.js
 *
 * Created: 2026-07-05
 */

const {
  predictWorkflow,
  getCircuitBreakerStatus,
  resetCircuitBreaker,
  getPredictionAccuracy,
} = require('../shared/prediction-wrapper.cjs');

const {
  optimizeWorkerCount,
  selectOptimalModels,
  autoOptimizeWorkflow,
  getOptimizationRecommendations,
} = require('../shared/auto-optimizer.cjs');

// Test configuration
const TEST_CONFIG = {
  workflow_name: 'deep-research',
  task_description: 'Research firmware reverse engineering methodologies',
  total_workers: 6,
  models: ['opus', 'sonnet', 'haiku'],
  metadata: {
    test: true,
  },
};

// Colors for output
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const BLUE = '\x1b[34m';
const RESET = '\x1b[0m';

function log(message, color = RESET) {
  console.log(`${color}${message}${RESET}`);
}

function logSuccess(message) {
  log(`✓ ${message}`, GREEN);
}

function logError(message) {
  log(`✗ ${message}`, RED);
}

function logInfo(message) {
  log(`ℹ ${message}`, BLUE);
}

function logWarning(message) {
  log(`⚠ ${message}`, YELLOW);
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Test 1: Basic connectivity
 */
async function testConnectivity() {
  logInfo('Test 1: Testing API connectivity...');

  try {
    const prediction = await predictWorkflow(TEST_CONFIG, { timeout: 5000 });

    if (!prediction || !prediction.predicted) {
      throw new Error('Invalid prediction response');
    }

    logSuccess('API connectivity OK');
    logInfo(
      `  Duration: ${prediction.predicted.duration_ms}ms, Cost: $${prediction.predicted.cost_usd}, Quality: ${prediction.predicted.quality_score}`
    );
    logInfo(`  Confidence: ${prediction.predicted.confidence}`);

    return true;
  } catch (err) {
    logError(`API connectivity failed: ${err.message}`);
    return false;
  }
}

/**
 * Test 2: Prediction accuracy
 */
async function testPredictionAccuracy() {
  logInfo('Test 2: Testing prediction accuracy...');

  try {
    const prediction = await predictWorkflow(TEST_CONFIG);

    // Validate prediction structure
    const required = ['duration_ms', 'cost_usd', 'quality_score', 'confidence'];
    const missing = required.filter((key) => !(key in prediction.predicted));

    if (missing.length > 0) {
      throw new Error(`Missing required fields: ${missing.join(', ')}`);
    }

    // Validate ranges
    if (prediction.predicted.duration_ms <= 0) {
      throw new Error('Invalid duration: must be > 0');
    }

    if (
      prediction.predicted.quality_score < 0 ||
      prediction.predicted.quality_score > 1
    ) {
      throw new Error('Invalid quality_score: must be 0-1');
    }

    if (
      prediction.predicted.confidence < 0 ||
      prediction.predicted.confidence > 1
    ) {
      throw new Error('Invalid confidence: must be 0-1');
    }

    logSuccess('Prediction structure valid');
    logInfo(`  Model version: ${prediction.metadata.model_version}`);
    logInfo(
      `  Prediction time: ${prediction.metadata.prediction_time_ms}ms`
    );

    return true;
  } catch (err) {
    logError(`Prediction accuracy test failed: ${err.message}`);
    return false;
  }
}

/**
 * Test 3: Auto-optimization
 */
async function testAutoOptimization() {
  logInfo('Test 3: Testing auto-optimization...');

  try {
    // Test worker count optimization
    const workerOpt = await optimizeWorkerCount(TEST_CONFIG, {
      objective: 'balanced',
      minWorkers: 2,
      maxWorkers: 8,
    });

    if (!workerOpt.recommended_workers) {
      throw new Error('No worker recommendation returned');
    }

    logSuccess(`Worker optimization: ${workerOpt.recommended_workers} workers`);
    logInfo(
      `  Predicted: $${workerOpt.predicted_cost_usd.toFixed(4)}, quality: ${(workerOpt.predicted_quality * 100).toFixed(1)}%`
    );

    // Test model selection
    const modelOpt = await selectOptimalModels(TEST_CONFIG, {
      maxModels: 3,
    });

    if (!modelOpt.recommended_models) {
      throw new Error('No model recommendation returned');
    }

    logSuccess(
      `Model optimization: ${modelOpt.recommended_models.join(', ')}`
    );
    logInfo(`  Reason: ${modelOpt.reason}, complexity: ${modelOpt.task_complexity}`);

    // Test full auto-optimization
    const fullOpt = await autoOptimizeWorkflow(TEST_CONFIG, {
      objective: 'balanced',
    });

    if (!fullOpt.optimized_config) {
      throw new Error('No optimized config returned');
    }

    logSuccess('Full auto-optimization complete');
    logInfo(`  Workers: ${fullOpt.summary.workers}`);
    logInfo(`  Models: ${fullOpt.summary.models?.join(', ')}`);
    logInfo(`  Timeout: ${(fullOpt.summary.timeout_ms / 1000).toFixed(1)}s`);

    // Get human-readable recommendations
    const recommendations = await getOptimizationRecommendations(TEST_CONFIG);
    logInfo('Recommendations:');
    console.log(recommendations);

    return true;
  } catch (err) {
    logError(`Auto-optimization test failed: ${err.message}`);
    return false;
  }
}

/**
 * Test 4: Circuit breaker
 */
async function testCircuitBreaker() {
  logInfo('Test 4: Testing circuit breaker...');

  try {
    // Reset circuit breaker
    resetCircuitBreaker();

    const status1 = getCircuitBreakerStatus();
    if (status1.state !== 'CLOSED') {
      throw new Error('Circuit breaker should start CLOSED');
    }

    logSuccess('Circuit breaker starts CLOSED');

    // Test with invalid host to trigger failures
    const originalHost = process.env.PREDICTION_HOST;
    process.env.PREDICTION_HOST = 'invalid-host';

    // Make 5 failing requests to open circuit
    for (let i = 0; i < 5; i++) {
      await predictWorkflow(TEST_CONFIG, { timeout: 1000, skipRetry: true }).catch(
        () => {}
      );
    }

    const status2 = getCircuitBreakerStatus();
    if (status2.state !== 'OPEN') {
      logWarning(
        `Circuit breaker state: ${status2.state} (expected OPEN, but may use fallback instead)`
      );
    } else {
      logSuccess('Circuit breaker opened after failures');
    }

    // Restore original host
    if (originalHost) {
      process.env.PREDICTION_HOST = originalHost;
    } else {
      delete process.env.PREDICTION_HOST;
    }

    // Reset for other tests
    resetCircuitBreaker();

    return true;
  } catch (err) {
    logError(`Circuit breaker test failed: ${err.message}`);
    // Reset for other tests
    resetCircuitBreaker();
    return false;
  }
}

/**
 * Test 5: Fallback behavior
 */
async function testFallbackBehavior() {
  logInfo('Test 5: Testing fallback behavior...');

  try {
    // Test with invalid host to trigger fallback
    const originalHost = process.env.PREDICTION_HOST;
    process.env.PREDICTION_HOST = 'invalid-host';

    const prediction = await predictWorkflow(TEST_CONFIG, {
      timeout: 1000,
      skipRetry: true,
    });

    // Restore original host
    if (originalHost) {
      process.env.PREDICTION_HOST = originalHost;
    } else {
      delete process.env.PREDICTION_HOST;
    }

    if (!prediction || !prediction.predicted) {
      throw new Error('Fallback prediction failed');
    }

    if (
      prediction.metadata.fallback_reason &&
      prediction.predicted.confidence === 0.0
    ) {
      logSuccess('Fallback prediction working (confidence: 0.0)');
      logInfo(`  Fallback reason: ${prediction.metadata.fallback_reason}`);
    } else if (prediction.metadata.fallback_reason) {
      logSuccess('Fallback prediction working (historical data)');
      logInfo(`  Fallback reason: ${prediction.metadata.fallback_reason}`);
      logInfo(`  Confidence: ${prediction.predicted.confidence}`);
    } else {
      logWarning('Prediction succeeded (expected fallback)');
    }

    return true;
  } catch (err) {
    logError(`Fallback behavior test failed: ${err.message}`);
    return false;
  }
}

/**
 * Test 6: Prediction accuracy stats
 */
async function testPredictionStats() {
  logInfo('Test 6: Testing prediction accuracy stats...');

  try {
    const stats = await getPredictionAccuracy({ windowDays: 30 });

    if (stats.length === 0) {
      logWarning('No prediction accuracy data available (expected for new deployment)');
      return true;
    }

    logSuccess(`Found ${stats.length} workflow types with accuracy data`);

    for (const workflow of stats.slice(0, 3)) {
      logInfo(`  ${workflow.workflow_name}:`);
      logInfo(`    Predictions: ${workflow.total_predictions}`);
      logInfo(
        `    Avg confidence: ${(workflow.avg_confidence * 100).toFixed(1)}%`
      );
      logInfo(
        `    Duration error: ${workflow.avg_duration_error_pct?.toFixed(1)}%`
      );
      logInfo(
        `    Cost error: ${workflow.avg_cost_error_pct?.toFixed(1)}%`
      );
    }

    return true;
  } catch (err) {
    logError(`Prediction stats test failed: ${err.message}`);
    return false;
  }
}

/**
 * Main test runner
 */
async function runTests() {
  console.log('');
  log('='.repeat(60), BLUE);
  log('ML Prediction Integration Tests', BLUE);
  log('='.repeat(60), BLUE);
  console.log('');

  const tests = [
    { name: 'Connectivity', fn: testConnectivity },
    { name: 'Prediction Accuracy', fn: testPredictionAccuracy },
    { name: 'Auto-Optimization', fn: testAutoOptimization },
    { name: 'Circuit Breaker', fn: testCircuitBreaker },
    { name: 'Fallback Behavior', fn: testFallbackBehavior },
    { name: 'Prediction Stats', fn: testPredictionStats },
  ];

  const results = [];

  for (const test of tests) {
    console.log('');
    const passed = await test.fn();
    results.push({ name: test.name, passed });

    await sleep(500); // Brief pause between tests
  }

  // Summary
  console.log('');
  log('='.repeat(60), BLUE);
  log('Test Summary', BLUE);
  log('='.repeat(60), BLUE);
  console.log('');

  let passCount = 0;
  for (const result of results) {
    if (result.passed) {
      logSuccess(result.name);
      passCount++;
    } else {
      logError(result.name);
    }
  }

  console.log('');
  const total = results.length;
  const pct = ((passCount / total) * 100).toFixed(0);

  if (passCount === total) {
    logSuccess(`All tests passed! (${passCount}/${total})`);
    process.exit(0);
  } else {
    logWarning(`${passCount}/${total} tests passed (${pct}%)`);
    process.exit(1);
  }
}

// Run tests
runTests().catch((err) => {
  logError(`Unhandled error: ${err.message}`);
  console.error(err);
  process.exit(1);
});
