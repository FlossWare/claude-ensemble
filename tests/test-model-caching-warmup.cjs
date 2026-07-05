#!/usr/bin/env node
/**
 * Test script for model caching with pre-warmed daemon
 * This tests the realistic scenario where daemon is already running
 */

const {
  predict,
  getCacheStats,
  clearPythonCache,
  startDaemon,
  stopDaemon
} = require('../shared/model-loader.cjs');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testCachingWithWarmup() {
  console.log('='.repeat(80));
  console.log('MODEL CACHING TEST - WITH DAEMON WARMUP');
  console.log('='.repeat(80));
  console.log('');

  // Start daemon and wait for it to be ready
  console.log('Starting daemon and warming up...');
  startDaemon();
  await sleep(3000); // Give daemon time to fully initialize

  // Clear Python cache (but keep daemon running)
  await clearPythonCache();
  console.log('Daemon ready, Python cache cleared');
  console.log('');

  // Test features
  const testFeatures = {
    prompt_length: 150,
    word_count: 75,
    num_implement: 2,
    num_fix: 1,
    num_review: 0,
    num_create: 1,
    num_update: 0,
    num_analyze: 0,
    num_test: 0,
    num_refactor: 0,
    file_mentions: 3,
    code_blocks: 2,
    has_java: 1,
    has_python: 0,
    has_javascript: 1,
    has_bug: 0,
    has_error: 0,
    has_performance: 0,
    has_security: 0,
    num_questions: 1,
    num_exclamations: 0
  };

  console.log('--- TEST 1: First Load (Daemon Warm, Model Cold) ---\n');
  const start1 = Date.now();
  const result1 = await predict('complexity_estimator', testFeatures);
  const time1 = Date.now() - start1;

  console.log(`Time: ${time1}ms`);
  console.log(`Result: ${JSON.stringify(result1)}`);
  console.log('');

  await sleep(100);

  console.log('--- TEST 2: Second Load (Model Cached in Python) ---\n');
  const start2 = Date.now();
  const result2 = await predict('complexity_estimator', testFeatures);
  const time2 = Date.now() - start2;

  console.log(`Time: ${time2}ms`);
  console.log(`Result cached in JS: ${result2.cached || false}`);
  console.log('');

  await sleep(100);

  console.log('--- TEST 3: Third Load (Should be instant) ---\n');
  const start3 = Date.now();
  const result3 = await predict('complexity_estimator', testFeatures);
  const time3 = Date.now() - start3;

  console.log(`Time: ${time3}ms`);
  console.log(`Result cached in JS: ${result3.cached || false}`);
  console.log('');

  // Get cache stats
  const stats = await getCacheStats();
  console.log('--- CACHE STATS ---\n');
  console.log(`Python cached models: ${stats.python.cached_models}`);
  console.log(`JS cached predictions: ${stats.javascript.predictions}`);
  console.log('');

  console.log('='.repeat(80));
  console.log('RESULTS');
  console.log('='.repeat(80));
  console.log('');
  console.log(`First load (model load from disk): ${time1}ms`);
  console.log(`Second load (Python cache):        ${time2}ms`);
  console.log(`Third load (JS cache):             ${time3}ms`);
  console.log('');

  const improvement = ((time1 - time2) / time1 * 100).toFixed(1);
  console.log(`Improvement: ${improvement}% faster after first load`);
  console.log('');

  if (time2 < 100) {
    console.log('✅ SUCCESS: Python model caching < 100ms');
  } else if (time2 < 1000) {
    console.log('⚠️  OK: Python model caching < 1s (acceptable)');
  } else {
    console.log('❌ FAIL: Python model caching still slow');
  }

  if (time3 < 10) {
    console.log('✅ SUCCESS: JS prediction caching < 10ms');
  } else {
    console.log('⚠️  WARNING: JS prediction caching slow');
  }

  console.log('');
  console.log('='.repeat(80));

  // Cleanup
  stopDaemon();
  process.exit(0);
}

// Run test
testCachingWithWarmup().catch(error => {
  console.error('Test failed:', error);
  process.exit(1);
});
