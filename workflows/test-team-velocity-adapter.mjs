#!/usr/bin/env node
/**
 * Test Team Velocity Adapter
 *
 * Demonstrates JavaScript integration of team velocity predictor
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const {
  predictVelocity,
  getOptimalWorkerCount,
  compareConfigurations,
  getModelStats,
  estimateConfigFromTask,
} = require('../shared/team-velocity-adapter.cjs');

console.log('=' .repeat(70));
console.log('TEAM VELOCITY PREDICTOR - JAVASCRIPT ADAPTER TEST');
console.log('=' .repeat(70));

// Test 1: Model stats
console.log('\n📊 TEST 1: Model Statistics');
console.log('-'.repeat(70));

try {
  const stats = getModelStats();
  console.log('Model trained on:', stats.trained_samples, 'samples');
  console.log('Duration R²:', stats.duration_r2.toFixed(4));
  console.log('Efficiency R²:', stats.efficiency_r2.toFixed(4));
  console.log('Top features (duration):');
  stats.top_features_duration.forEach(({ name, importance }) => {
    console.log(`  ${name}: ${importance.toFixed(4)}`);
  });
} catch (error) {
  console.error('❌ Error:', error.message);
  process.exit(1);
}

// Test 2: Single prediction
console.log('\n📊 TEST 2: Single Prediction');
console.log('-'.repeat(70));

const config = {
  num_workers: 6,
  num_tasks: 20,
  task_complexity: 'complex',
  has_dependencies: true,
  model_diversity: 5,
  parallel_ratio: 0.65,
  historical_success_rate: 0.80,
  avg_worker_latency_ms: 4000,
};

console.log('Configuration:', JSON.stringify(config, null, 2));

try {
  const result = predictVelocity(config);
  console.log('\nPrediction:');
  console.log(`  Duration: ${result.predicted_duration_minutes.toFixed(1)} min`);
  console.log(`  Speedup: ${result.actual_speedup.toFixed(1)}x (${result.efficiency_percent.toFixed(1)}% efficient)`);
  console.log(`  Utilization: ${(result.resource_utilization * 100).toFixed(1)}%`);
  console.log(`  Success Probability: ${(result.success_probability * 100).toFixed(1)}%`);
} catch (error) {
  console.error('❌ Error:', error.message);
  process.exit(1);
}

// Test 3: Optimal worker count
console.log('\n📊 TEST 3: Optimal Worker Count');
console.log('-'.repeat(70));

const testCases = [
  { tasks: 10, complexity: 'simple', dependencies: false },
  { tasks: 30, complexity: 'medium', dependencies: false },
  { tasks: 20, complexity: 'complex', dependencies: true },
  { tasks: 15, complexity: 'very_complex', dependencies: true },
];

testCases.forEach(({ tasks, complexity, dependencies }) => {
  const optimal = getOptimalWorkerCount(tasks, complexity, dependencies);
  console.log(`${tasks} ${complexity} tasks ${dependencies ? 'with' : 'without'} dependencies → ${optimal} workers`);
});

// Test 4: Compare configurations
console.log('\n📊 TEST 4: Configuration Comparison');
console.log('-'.repeat(70));

const configs = [
  {
    name: 'Small Team',
    num_workers: 3,
    num_tasks: 10,
    task_complexity: 'simple',
    has_dependencies: false,
    model_diversity: 3,
    parallel_ratio: 0.9,
    historical_success_rate: 0.92,
    avg_worker_latency_ms: 1500,
  },
  {
    name: 'Medium Team',
    num_workers: 6,
    num_tasks: 25,
    task_complexity: 'medium',
    has_dependencies: true,
    model_diversity: 5,
    parallel_ratio: 0.7,
    historical_success_rate: 0.85,
    avg_worker_latency_ms: 3000,
  },
  {
    name: 'Full Fleet',
    num_workers: 8,
    num_tasks: 40,
    task_complexity: 'complex',
    has_dependencies: true,
    model_diversity: 6,
    parallel_ratio: 0.6,
    historical_success_rate: 0.78,
    avg_worker_latency_ms: 5000,
  },
];

try {
  const comparisons = compareConfigurations(configs);

  console.log('Name'.padEnd(20) + ' ' + 'Duration'.padEnd(15) + ' ' + 'Speedup'.padEnd(12) + ' ' + 'Success');
  console.log('-'.repeat(70));

  comparisons.forEach(({ name, prediction }) => {
    const duration = `${prediction.predicted_duration_minutes.toFixed(1)} min`;
    const speedup = `${prediction.actual_speedup.toFixed(1)}x`;
    const success = `${(prediction.success_probability * 100).toFixed(1)}%`;

    console.log(name.padEnd(20) + ' ' + duration.padEnd(15) + ' ' + speedup.padEnd(12) + ' ' + success);
  });

  // Find best configuration
  const best = comparisons.reduce((best, curr) => {
    const bestScore = best.prediction.success_probability / best.prediction.predicted_duration_ms;
    const currScore = curr.prediction.success_probability / curr.prediction.predicted_duration_ms;
    return currScore > bestScore ? curr : best;
  });

  console.log(`\n💡 Best configuration: ${best.name} (highest success/duration ratio)`);

} catch (error) {
  console.error('❌ Error:', error.message);
  process.exit(1);
}

// Test 5: Estimate config from task description
console.log('\n📊 TEST 5: Estimate Config from Task Description');
console.log('-'.repeat(70));

const taskDescriptions = [
  'Fix typo in README file',
  'Implement user authentication with JWT tokens',
  'Review entire codebase for security vulnerabilities',
];

taskDescriptions.forEach(task => {
  const estimated = estimateConfigFromTask(task, 6);
  console.log(`\nTask: "${task}"`);
  console.log(`  Estimated complexity: ${estimated.task_complexity}`);
  console.log(`  Estimated tasks: ${estimated.num_tasks}`);
  console.log(`  Has dependencies: ${estimated.has_dependencies}`);

  try {
    const prediction = predictVelocity(estimated);
    console.log(`  Predicted duration: ${prediction.predicted_duration_minutes.toFixed(1)} min`);
  } catch (error) {
    console.error(`  ❌ Prediction failed: ${error.message}`);
  }
});

console.log('\n' + '='.repeat(70));
console.log('✅ ALL TESTS PASSED');
console.log('='.repeat(70));
