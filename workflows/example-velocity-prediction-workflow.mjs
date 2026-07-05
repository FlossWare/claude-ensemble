#!/usr/bin/env node
/**
 * Example Workflow with Team Velocity Prediction
 *
 * Demonstrates how to integrate team velocity predictions into a real workflow.
 * The workflow:
 * 1. Predicts performance before execution
 * 2. Adjusts worker count based on predictions
 * 3. Executes tasks with optimal configuration
 * 4. Compares actual vs predicted performance
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const {
  predictVelocity,
  getOptimalWorkerCount,
  estimateConfigFromTask,
} = require('../shared/team-velocity-adapter.cjs');

// Example workflow function
async function executeWorkflow({ task, availableWorkers = 8 }) {
  console.log('=' .repeat(70));
  console.log('WORKFLOW EXECUTION WITH VELOCITY PREDICTION');
  console.log('=' .repeat(70));

  console.log(`\nTask: ${task}`);
  console.log(`Available Workers: ${availableWorkers}`);

  // Step 1: Estimate configuration from task description
  console.log('\n📊 STEP 1: Estimate Configuration');
  console.log('-'.repeat(70));

  const estimatedConfig = estimateConfigFromTask(task, availableWorkers);
  console.log('Estimated config:', JSON.stringify(estimatedConfig, null, 2));

  // Step 2: Predict performance
  console.log('\n📊 STEP 2: Predict Performance');
  console.log('-'.repeat(70));

  const prediction = predictVelocity(estimatedConfig);
  console.log(`Predicted Duration: ${prediction.predicted_duration_minutes.toFixed(1)} min`);
  console.log(`Parallel Speedup: ${prediction.actual_speedup.toFixed(1)}x`);
  console.log(`Efficiency: ${prediction.efficiency_percent.toFixed(1)}%`);
  console.log(`Utilization: ${(prediction.resource_utilization * 100).toFixed(1)}%`);
  console.log(`Success Probability: ${(prediction.success_probability * 100).toFixed(1)}%`);

  // Step 3: Optimize worker count if needed
  console.log('\n📊 STEP 3: Optimize Configuration');
  console.log('-'.repeat(70));

  const optimalWorkers = getOptimalWorkerCount(
    estimatedConfig.num_tasks,
    estimatedConfig.task_complexity,
    estimatedConfig.has_dependencies
  );

  console.log(`Current workers: ${estimatedConfig.num_workers}`);
  console.log(`Optimal workers: ${optimalWorkers}`);

  if (optimalWorkers !== estimatedConfig.num_workers) {
    console.log(`⚙️  Adjusting worker count: ${estimatedConfig.num_workers} → ${optimalWorkers}`);

    // Re-predict with optimal workers
    const optimizedConfig = { ...estimatedConfig, num_workers: optimalWorkers };
    const optimizedPrediction = predictVelocity(optimizedConfig);

    console.log('\nOptimized predictions:');
    console.log(`  Duration: ${optimizedPrediction.predicted_duration_minutes.toFixed(1)} min ` +
                `(${prediction.predicted_duration_minutes > optimizedPrediction.predicted_duration_minutes ? '↓' : '↑'} ` +
                `${Math.abs(prediction.predicted_duration_minutes - optimizedPrediction.predicted_duration_minutes).toFixed(1)} min)`);
    console.log(`  Efficiency: ${optimizedPrediction.efficiency_percent.toFixed(1)}% ` +
                `(${optimizedPrediction.efficiency_percent > prediction.efficiency_percent ? '↑' : '↓'} ` +
                `${Math.abs(optimizedPrediction.efficiency_percent - prediction.efficiency_percent).toFixed(1)}%)`);
    console.log(`  Success: ${(optimizedPrediction.success_probability * 100).toFixed(1)}% ` +
                `(${optimizedPrediction.success_probability > prediction.success_probability ? '↑' : '↓'} ` +
                `${Math.abs((optimizedPrediction.success_probability - prediction.success_probability) * 100).toFixed(1)}%)`);

    // Use optimized configuration
    estimatedConfig.num_workers = optimalWorkers;
  } else {
    console.log('✓ Current worker count is already optimal');
  }

  // Step 4: Execute workflow (simulated)
  console.log('\n📊 STEP 4: Execute Workflow (Simulated)');
  console.log('-'.repeat(70));

  const startTime = Date.now();

  // Simulate execution time based on prediction (with some randomness)
  const simulatedDuration = prediction.predicted_duration_ms * (0.9 + Math.random() * 0.2);
  const simulatedSuccess = Math.random() < prediction.success_probability;

  console.log('Executing...');

  // Simulate delay
  await new Promise(resolve => setTimeout(resolve, Math.min(simulatedDuration / 100, 2000)));

  const actualDuration = Date.now() - startTime;

  console.log(`\n✓ Execution ${simulatedSuccess ? 'succeeded' : 'failed'}`);
  console.log(`Actual duration: ${(actualDuration / 60000).toFixed(2)} min (simulated: ${(simulatedDuration / 60000).toFixed(1)} min)`);

  // Step 5: Compare predictions vs actuals
  console.log('\n📊 STEP 5: Prediction Accuracy');
  console.log('-'.repeat(70));

  const durationError = Math.abs(simulatedDuration - prediction.predicted_duration_ms) / prediction.predicted_duration_ms * 100;
  const successMatch = simulatedSuccess === (prediction.success_probability > 0.5);

  console.log(`Duration prediction error: ${durationError.toFixed(1)}%`);
  console.log(`Success prediction: ${successMatch ? '✓ Correct' : '✗ Incorrect'}`);

  if (durationError < 20) {
    console.log('✓ Duration prediction was highly accurate');
  } else if (durationError < 40) {
    console.log('⚠ Duration prediction had moderate error');
  } else {
    console.log('✗ Duration prediction had high error');
  }

  // Step 6: Return results for logging
  return {
    task,
    config: estimatedConfig,
    prediction,
    actual: {
      duration_ms: simulatedDuration,
      success: simulatedSuccess,
    },
    accuracy: {
      duration_error_percent: durationError,
      success_match: successMatch,
    },
  };
}

// Main execution
async function main() {
  const testTasks = [
    'Implement user authentication with OAuth2 and JWT tokens',
    'Fix critical security vulnerability in payment processing',
    'Review code changes across 10 files for style consistency',
  ];

  const results = [];

  for (const task of testTasks) {
    const result = await executeWorkflow({ task, availableWorkers: 8 });
    results.push(result);
    console.log('\n');
  }

  // Summary
  console.log('=' .repeat(70));
  console.log('SUMMARY OF ALL WORKFLOWS');
  console.log('=' .repeat(70));

  const avgError = results.reduce((sum, r) => sum + r.accuracy.duration_error_percent, 0) / results.length;
  const successRate = results.filter(r => r.accuracy.success_match).length / results.length;

  console.log(`\nExecuted ${results.length} workflows`);
  console.log(`Average duration prediction error: ${avgError.toFixed(1)}%`);
  console.log(`Success prediction accuracy: ${(successRate * 100).toFixed(1)}%`);

  console.log('\nDetailed results:');
  results.forEach((r, i) => {
    console.log(`\n${i + 1}. ${r.task.substring(0, 50)}...`);
    console.log(`   Predicted: ${r.prediction.predicted_duration_minutes.toFixed(1)} min, ` +
                `${(r.prediction.success_probability * 100).toFixed(0)}% success`);
    console.log(`   Actual: ${(r.actual.duration_ms / 60000).toFixed(1)} min, ` +
                `${r.actual.success ? 'succeeded' : 'failed'}`);
    console.log(`   Error: ${r.accuracy.duration_error_percent.toFixed(1)}%`);
  });

  console.log('\n' + '=' .repeat(70));
  console.log('✅ WORKFLOW COMPLETE');
  console.log('=' .repeat(70));
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error('❌ Workflow failed:', error);
    process.exit(1);
  });
}

export { executeWorkflow };
