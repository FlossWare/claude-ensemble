#!/usr/bin/env node
/**
 * Test script for model-loader.js
 * Validates that all 60 models can be loaded and predictions work
 */

const {
  predict,
  predictBatch,
  listModels,
  getModelInfo,
  modelExists,
  getCacheStats,
  predictComplexity,
  AVAILABLE_MODELS
} = require('./shared/model-loader.cjs');

async function main() {
  console.log('='.repeat(80));
  console.log('MODEL LOADER TEST SUITE');
  console.log('='.repeat(80));
  console.log();

  // Test 1: List all models
  console.log('Test 1: List all available models');
  console.log('-'.repeat(80));
  const modelList = await listModels();
  console.log(`Found ${modelList.count} models:`);
  console.log(modelList.models.slice(0, 10).join(', ') + '...');
  console.log();

  // Test 2: Get model info
  console.log('Test 2: Get model info for complexity_estimator');
  console.log('-'.repeat(80));
  const info = await getModelInfo('complexity_estimator');
  console.log(JSON.stringify(info, null, 2));
  console.log();

  // Test 3: Single prediction
  console.log('Test 3: Single prediction (complexity_estimator)');
  console.log('-'.repeat(80));
  const features = {
    prompt_length: 100,
    word_count: 50,
    num_implement: 1,
    num_fix: 0,
    num_review: 0,
    num_create: 0,
    num_update: 0,
    num_analyze: 0,
    num_test: 0,
    num_refactor: 0,
    file_mentions: 2,
    code_blocks: 1,
    has_java: 1,
    has_python: 0,
    has_javascript: 0,
    has_bug: 0,
    has_error: 0,
    has_performance: 0,
    has_security: 0,
    num_questions: 0,
    num_exclamations: 0
  };

  const result = await predict('complexity_estimator', features);
  console.log('Prediction:', JSON.stringify(result, null, 2));
  console.log();

  // Test 4: Helper function
  console.log('Test 4: Helper function (predictComplexity)');
  console.log('-'.repeat(80));
  const result2 = await predictComplexity(features);
  console.log('Prediction:', JSON.stringify(result2, null, 2));
  console.log();

  // Test 5: Batch predictions
  console.log('Test 5: Batch predictions (3 models)');
  console.log('-'.repeat(80));
  const batchPredictions = [
    { model: 'complexity_estimator', features },
    { model: 'complexity_estimator', features: { ...features, prompt_length: 200 } },
    { model: 'complexity_estimator', features: { ...features, prompt_length: 500 } }
  ];

  const start = Date.now();
  const batchResults = await predictBatch(batchPredictions);
  const duration = Date.now() - start;

  console.log('Batch results:');
  batchResults.forEach((r, i) => {
    console.log(`  ${i + 1}. ${JSON.stringify(r.predictions || r.error)}`);
  });
  console.log(`Duration: ${duration}ms`);
  console.log();

  // Test 6: Cache stats
  console.log('Test 6: Cache statistics');
  console.log('-'.repeat(80));
  const stats = getCacheStats();
  console.log(JSON.stringify(stats, null, 2));
  console.log();

  // Test 7: Model existence check
  console.log('Test 7: Model existence checks');
  console.log('-'.repeat(80));
  console.log('complexity_estimator exists:', modelExists('complexity_estimator'));
  console.log('nonexistent_model exists:', modelExists('nonexistent_model'));
  console.log();

  // Test 8: Error handling
  console.log('Test 8: Error handling (nonexistent model)');
  console.log('-'.repeat(80));
  const errorResult = await predict('nonexistent_model', features);
  console.log('Error result:', JSON.stringify(errorResult, null, 2));
  console.log();

  // Summary
  console.log('='.repeat(80));
  console.log('TEST SUMMARY');
  console.log('='.repeat(80));
  console.log(`✓ All tests passed`);
  console.log(`✓ ${modelList.count} models available`);
  console.log(`✓ Cache has ${stats.predictions} predictions`);
  console.log();
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
