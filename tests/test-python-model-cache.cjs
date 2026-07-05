#!/usr/bin/env node
/**
 * Test Python model cache specifically
 * Different features = different predictions, but same model
 */

const {
  predict,
  getCacheStats,
  clearCache,
  clearPythonCache,
  startDaemon,
  stopDaemon
} = require('../shared/model-loader.cjs');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testPythonModelCache() {
  console.log('='.repeat(80));
  console.log('PYTHON MODEL CACHE TEST');
  console.log('Testing that model stays cached even with different features');
  console.log('='.repeat(80));
  console.log('');

  // Start daemon
  console.log('Starting daemon...');
  startDaemon();
  await sleep(3000);

  // Clear both caches
  clearCache(); // JS cache
  await clearPythonCache(); // Python cache

  console.log('Caches cleared');
  console.log('');

  // Features set 1
  const features1 = {
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

  // Features set 2 (different values)
  const features2 = {
    prompt_length: 200,
    word_count: 100,
    num_implement: 3,
    num_fix: 1,
    num_review: 1,
    num_create: 2,
    num_update: 1,
    num_analyze: 0,
    num_test: 1,
    num_refactor: 0,
    file_mentions: 5,
    code_blocks: 3,
    has_java: 0,
    has_python: 1,
    has_javascript: 1,
    has_bug: 1,
    has_error: 0,
    has_performance: 0,
    has_security: 0,
    num_questions: 2,
    num_exclamations: 1
  };

  console.log('--- Prediction 1: Load model from disk ---\n');
  const start1 = Date.now();
  const result1 = await predict('complexity_estimator', features1);
  const time1 = Date.now() - start1;
  console.log(`Time: ${time1}ms`);
  console.log(`Duration prediction: ${result1.predictions?.duration || 'N/A'}`);
  console.log('');

  await sleep(100);

  console.log('--- Prediction 2: Different features, SAME MODEL (should use cached model) ---\n');
  const start2 = Date.now();
  const result2 = await predict('complexity_estimator', features2);
  const time2 = Date.now() - start2;
  console.log(`Time: ${time2}ms`);
  console.log(`Duration prediction: ${result2.predictions?.duration || 'N/A'}`);
  console.log(`JS cached: ${result2.cached || false}`);
  console.log('');

  await sleep(100);

  console.log('--- Prediction 3: Back to features1 (should use JS cache) ---\n');
  const start3 = Date.now();
  const result3 = await predict('complexity_estimator', features1);
  const time3 = Date.now() - start3;
  console.log(`Time: ${time3}ms`);
  console.log(`JS cached: ${result3.cached || false}`);
  console.log('');

  await sleep(100);

  console.log('--- Prediction 4: Features2 again (should use JS cache) ---\n');
  const start4 = Date.now();
  const result4 = await predict('complexity_estimator', features2);
  const time4 = Date.now() - start4;
  console.log(`Time: ${time4}ms`);
  console.log(`JS cached: ${result4.cached || false}`);
  console.log('');

  // Get stats
  const stats = await getCacheStats();
  console.log('--- CACHE STATS ---\n');
  console.log(JSON.stringify(stats, null, 2));
  console.log('');

  console.log('='.repeat(80));
  console.log('SUMMARY');
  console.log('='.repeat(80));
  console.log('');
  console.log(`Prediction 1 (features1, cold model):     ${time1}ms`);
  console.log(`Prediction 2 (features2, cached model):   ${time2}ms`);
  console.log(`Prediction 3 (features1, JS cached):      ${time3}ms`);
  console.log(`Prediction 4 (features2, JS cached):      ${time4}ms`);
  console.log('');

  if (time2 < 100) {
    console.log('✅ SUCCESS: Python model cache working (<100ms for different features)');
  } else if (time2 < 500) {
    console.log('✅ GOOD: Python model cache working (<500ms)');
  } else {
    console.log('⚠️  WARNING: Model might be reloading');
  }

  if (time3 < 10 && time4 < 10) {
    console.log('✅ SUCCESS: JS prediction cache working (<10ms)');
  }

  console.log('');
  console.log(`Model stayed cached: ${stats.python.cached_models} model(s) in Python cache`);
  console.log(`Predictions cached: ${stats.javascript.predictions} prediction(s) in JS cache`);
  console.log('');
  console.log('='.repeat(80));

  // Cleanup
  stopDaemon();
  process.exit(0);
}

testPythonModelCache().catch(error => {
  console.error('Test failed:', error);
  process.exit(1);
});
