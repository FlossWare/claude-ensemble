#!/usr/bin/env node
/**
 * Test script for model caching implementation
 * Measures performance before/after caching
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

async function testCaching() {
  console.log('='.repeat(80));
  console.log('MODEL CACHING PERFORMANCE TEST');
  console.log('='.repeat(80));
  console.log('');

  // Clear all caches
  console.log('Clearing caches...');
  clearCache();
  await clearPythonCache();

  // Start daemon
  console.log('Starting Python daemon...');
  startDaemon();
  await sleep(2000); // Wait for daemon to be ready

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

  console.log('\n--- TEST 1: First Prediction (Cold Start - No Cache) ---\n');
  const start1 = Date.now();
  const result1 = await predict('complexity_estimator', testFeatures);
  const time1 = Date.now() - start1;

  console.log(`Result: ${JSON.stringify(result1)}`);
  console.log(`Time: ${time1}ms`);
  console.log(`Cached: ${result1.cached || false}`);

  // Wait a bit
  await sleep(500);

  console.log('\n--- TEST 2: Second Prediction (Should Use Cache) ---\n');
  const start2 = Date.now();
  const result2 = await predict('complexity_estimator', testFeatures);
  const time2 = Date.now() - start2;

  console.log(`Result: ${JSON.stringify(result2)}`);
  console.log(`Time: ${time2}ms`);
  console.log(`Cached: ${result2.cached || false}`);

  // Wait a bit
  await sleep(500);

  console.log('\n--- TEST 3: Third Prediction (Should Use Cache) ---\n');
  const start3 = Date.now();
  const result3 = await predict('complexity_estimator', testFeatures);
  const time3 = Date.now() - start3;

  console.log(`Result: ${JSON.stringify(result3)}`);
  console.log(`Time: ${time3}ms`);
  console.log(`Cached: ${result3.cached || false}`);

  // Test different model
  console.log('\n--- TEST 4: Different Model (Bug Predictor) ---\n');
  const bugFeatures = {
    message_length: 50,
    has_bugfix_keywords: 1,
    has_wip_keywords: 0,
    has_tmp_keywords: 0,
    hour_of_day: 14,
    day_of_week: 3,
    files_changed: 2,
    has_tests: 1,
    message_capitalized: 1,
    has_issue_reference: 1
  };

  const start4 = Date.now();
  const result4 = await predict('bug_predictor', bugFeatures);
  const time4 = Date.now() - start4;

  console.log(`Result: ${JSON.stringify(result4)}`);
  console.log(`Time: ${time4}ms`);

  // Test bug predictor again (cached model)
  await sleep(500);

  console.log('\n--- TEST 5: Bug Predictor Again (Cached Model) ---\n');
  const start5 = Date.now();
  const result5 = await predict('bug_predictor', bugFeatures);
  const time5 = Date.now() - start5;

  console.log(`Result: ${JSON.stringify(result5)}`);
  console.log(`Time: ${time5}ms`);

  // Get cache stats
  console.log('\n--- CACHE STATISTICS ---\n');
  const stats = await getCacheStats();
  console.log(JSON.stringify(stats, null, 2));

  // Summary
  console.log('\n' + '='.repeat(80));
  console.log('PERFORMANCE SUMMARY');
  console.log('='.repeat(80));
  console.log('');
  console.log(`First prediction (complexity_estimator):  ${time1}ms (cold start)`);
  console.log(`Second prediction (complexity_estimator): ${time2}ms (cached)`);
  console.log(`Third prediction (complexity_estimator):  ${time3}ms (cached)`);
  console.log(`First prediction (bug_predictor):         ${time4}ms (cold start)`);
  console.log(`Second prediction (bug_predictor):        ${time5}ms (cached)`);
  console.log('');

  const improvement2 = ((time1 - time2) / time1 * 100).toFixed(1);
  const improvement3 = ((time1 - time3) / time1 * 100).toFixed(1);
  const improvement5 = ((time4 - time5) / time4 * 100).toFixed(1);

  console.log(`Cache speedup (complexity #2): ${improvement2}% faster`);
  console.log(`Cache speedup (complexity #3): ${improvement3}% faster`);
  console.log(`Cache speedup (bug #2):        ${improvement5}% faster`);
  console.log('');

  const avgColdStart = (time1 + time4) / 2;
  const avgCached = (time2 + time3 + time5) / 3;
  const avgImprovement = ((avgColdStart - avgCached) / avgColdStart * 100).toFixed(1);

  console.log(`Average cold start time: ${avgColdStart.toFixed(0)}ms`);
  console.log(`Average cached time:     ${avgCached.toFixed(0)}ms`);
  console.log(`Average improvement:     ${avgImprovement}% faster`);
  console.log('');

  if (avgCached < 100) {
    console.log('✅ SUCCESS: Cached predictions < 100ms');
  } else {
    console.log('⚠️  WARNING: Cached predictions still slow');
  }

  console.log('');
  console.log('='.repeat(80));

  // Cleanup
  stopDaemon();
  process.exit(0);
}

// Run test
testCaching().catch(error => {
  console.error('Test failed:', error);
  process.exit(1);
});
