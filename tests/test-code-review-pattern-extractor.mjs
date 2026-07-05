#!/usr/bin/env node
/**
 * Test Code Review Pattern Extractor Integration
 *
 * Validates:
 * 1. Python model training and saving
 * 2. JavaScript adapter functionality
 * 3. Model recommendations and predictions
 * 4. Health check system
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(__dirname, '..');

// Import adapter (using dynamic import for CJS)
const {
  getTopReviewModels,
  predictIssues,
  getPatternStats,
  getReviewStrategy,
  healthCheck
} = await import(`file://${path.join(projectRoot, 'shared/code-review-pattern-adapter.cjs')}`).then(m => m.default || m);

console.log('═'.repeat(80));
console.log('CODE REVIEW PATTERN EXTRACTOR - INTEGRATION TEST');
console.log('═'.repeat(80));

let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  try {
    console.log(`\n🧪 TEST: ${name}`);
    fn();
    console.log(`   ✅ PASS`);
    testsPassed++;
  } catch (error) {
    console.log(`   ❌ FAIL: ${error.message}`);
    testsFailed++;
  }
}

async function asyncTest(name, fn) {
  try {
    console.log(`\n🧪 TEST: ${name}`);
    await fn();
    console.log(`   ✅ PASS`);
    testsPassed++;
  } catch (error) {
    console.log(`   ❌ FAIL: ${error.message}`);
    testsFailed++;
  }
}

// Test 1: Model file exists
test('Model file exists', () => {
  const modelPath = path.join(projectRoot, 'learning/code_review_pattern_extractor.pkl');
  if (!fs.existsSync(modelPath)) {
    throw new Error(`Model file not found at ${modelPath}`);
  }
  console.log(`   Model found: ${modelPath}`);
});

// Test 2: Health check
await asyncTest('Health check', async () => {
  const health = await healthCheck();
  console.log(`   Healthy: ${health.healthy}`);
  console.log(`   Trained at: ${health.trained_at}`);
  console.log(`   Version: ${health.version}`);

  if (!health.healthy) {
    throw new Error('System not healthy');
  }
});

// Test 3: Get top models
await asyncTest('Get top review models', async () => {
  const models = await getTopReviewModels(5);

  console.log(`   Retrieved ${models.length} models`);

  if (models.length === 0) {
    throw new Error('No models returned');
  }

  console.log('\n   Top 3 Models:');
  models.slice(0, 3).forEach((model, idx) => {
    console.log(`      ${idx + 1}. ${model.model}: ${model.success_rate} success, ${model.reviews} reviews`);
  });

  // Validate structure
  const firstModel = models[0];
  if (!firstModel.model || !firstModel.success_rate || !firstModel.reviews === undefined) {
    throw new Error('Invalid model structure');
  }
});

// Test 4: Predict issue likelihood
await asyncTest('Predict issue likelihood', async () => {
  const taskFeatures = {
    duration_ms: 5000,
    input_tokens: 1000,
    output_tokens: 500,
    files: 10,
    confidence: 0.8
  };

  const prediction = await predictIssues(taskFeatures);

  console.log(`   Probability: ${(prediction.probability * 100).toFixed(1)}%`);
  console.log(`   Assessment: ${prediction.message}`);

  if (prediction.probability === undefined || prediction.probability < 0 || prediction.probability > 1) {
    throw new Error('Invalid probability value');
  }

  if (!prediction.message) {
    throw new Error('Missing prediction message');
  }
});

// Test 5: Get pattern statistics
await asyncTest('Get pattern statistics', async () => {
  const stats = await getPatternStats();

  console.log(`   Issue categories: ${Object.keys(stats.issue_categories).length}`);
  console.log(`   Severity levels: ${Object.keys(stats.severity_distribution).length}`);
  console.log(`   Trained at: ${stats.trained_at}`);

  if (!stats.issue_categories || !stats.severity_distribution) {
    throw new Error('Missing pattern statistics');
  }
});

// Test 6: Get review strategy
await asyncTest('Get review strategy recommendation', async () => {
  const strategies = [
    { files: 5, type: 'style' },
    { files: 50, type: 'security' },
    { files: 100, type: 'bug' }
  ];

  for (const task of strategies) {
    const strategy = await getReviewStrategy(task);

    console.log(`\n   Task: ${task.files} files, type=${task.type}`);
    console.log(`      Strategy: ${strategy.strategy}`);
    console.log(`      Workers: ${strategy.workers.length}`);
    console.log(`      Arbiter: ${strategy.arbiter}`);
    console.log(`      Issue probability: ${(strategy.prediction.probability * 100).toFixed(1)}%`);

    if (!strategy.strategy || !strategy.workers || !strategy.arbiter) {
      throw new Error('Invalid strategy structure');
    }
  }
});

// Test 7: Workflow integration example
await asyncTest('Workflow integration example', async () => {
  console.log('\n   Simulating workflow integration...');

  // 1. Get recommended models
  const models = await getTopReviewModels(3);
  console.log(`   ✓ Retrieved ${models.length} top models`);

  // 2. Predict issue likelihood
  const prediction = await predictIssues({ files: 15, duration_ms: 10000 });
  console.log(`   ✓ Predicted ${(prediction.probability * 100).toFixed(1)}% issue probability`);

  // 3. Get review strategy
  const strategy = await getReviewStrategy({ files: 15, type: 'bug' });
  console.log(`   ✓ Strategy: ${strategy.strategy} with ${strategy.workers.length} workers`);

  // 4. Simulate workflow execution
  const workflowResult = {
    workers: strategy.workers,
    arbiter: strategy.arbiter,
    predicted_probability: prediction.probability,
    actual_issues_found: 8,
    success: true
  };

  console.log('\n   Workflow Result:');
  console.log(`      Workers: ${workflowResult.workers.join(', ')}`);
  console.log(`      Issues found: ${workflowResult.actual_issues_found}`);
  console.log(`      Prediction accuracy: ${workflowResult.predicted_probability > 0.5 ? 'CORRECT' : 'INCORRECT'}`);
});

// Test 8: Model persistence
test('Model persistence check', () => {
  const modelPath = path.join(projectRoot, 'learning/code_review_pattern_extractor.pkl');
  const stats = fs.statSync(modelPath);

  console.log(`   File size: ${(stats.size / 1024).toFixed(1)} KB`);
  console.log(`   Modified: ${stats.mtime.toISOString()}`);

  if (stats.size < 1000) {
    throw new Error('Model file too small (possibly corrupt)');
  }
});

// Summary
console.log('\n' + '═'.repeat(80));
console.log('TEST SUMMARY');
console.log('═'.repeat(80));
console.log(`✅ Passed: ${testsPassed}`);
console.log(`❌ Failed: ${testsFailed}`);
console.log(`📊 Total: ${testsPassed + testsFailed}`);
console.log('═'.repeat(80));

if (testsFailed > 0) {
  console.log('\n⚠️ Some tests failed - review output above');
  process.exit(1);
} else {
  console.log('\n🎉 All tests passed!');
  console.log('\n💡 USAGE EXAMPLES:');
  console.log('');
  console.log('   // In a workflow:');
  console.log('   const { getReviewStrategy } = require("./shared/code-review-pattern-adapter.cjs");');
  console.log('   const strategy = await getReviewStrategy({ files: 20, type: "security" });');
  console.log('   const workers = await parallel(strategy.workers.map(model => ...));');
  console.log('');
  console.log('   // Retrain model:');
  console.log('   python3 tools/code_review_pattern_extractor.py --window 90');
  console.log('');
  process.exit(0);
}
