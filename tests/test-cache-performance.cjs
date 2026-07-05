#!/usr/bin/env node

/**
 * Cache Performance Benchmark
 *
 * Compares prediction performance with and without caching
 */

const { predict, clearCache } = require('../shared/model-loader.cjs');

async function benchmark() {
  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  Model Cache Performance Benchmark');
  console.log('═══════════════════════════════════════════════════════\n');

  const features = {
    prompt_length: 500,
    word_count: 250,
    num_implement: 3,
    num_check: 2
  };

  // Test 1: Without cache
  console.log('Test 1: Multiple predictions WITHOUT cache');
  console.log('─────────────────────────────────────────────────────\n');

  clearCache();
  const noCacheTimes = [];

  for (let i = 0; i < 5; i++) {
    const start = Date.now();
    await predict('complexity_estimator', features, { cache: false });
    const duration = Date.now() - start;
    noCacheTimes.push(duration);
    console.log(`  Prediction ${i + 1}: ${duration}ms`);
  }

  const avgNoCache = noCacheTimes.reduce((a, b) => a + b, 0) / noCacheTimes.length;
  console.log(`\nAverage time (no cache): ${avgNoCache.toFixed(2)}ms\n`);

  // Test 2: With cache
  console.log('Test 2: Multiple predictions WITH cache');
  console.log('─────────────────────────────────────────────────────\n');

  clearCache();
  const cacheTimes = [];

  for (let i = 0; i < 5; i++) {
    const start = Date.now();
    const result = await predict('complexity_estimator', features, { cache: true });
    const duration = Date.now() - start;
    cacheTimes.push(duration);
    console.log(`  Prediction ${i + 1}: ${duration}ms ${result.cached ? '(cached)' : '(computed)'}`);
  }

  const avgCache = cacheTimes.reduce((a, b) => a + b, 0) / cacheTimes.length;
  console.log(`\nAverage time (with cache): ${avgCache.toFixed(2)}ms\n`);

  // Test 3: Different predictions (cache misses)
  console.log('Test 3: Different predictions (all cache misses)');
  console.log('─────────────────────────────────────────────────────\n');

  clearCache();
  const differentTimes = [];

  for (let i = 0; i < 5; i++) {
    const start = Date.now();
    await predict('complexity_estimator', {
      prompt_length: 100 + i * 50,
      word_count: 50 + i * 25
    }, { cache: true });
    const duration = Date.now() - start;
    differentTimes.push(duration);
    console.log(`  Prediction ${i + 1}: ${duration}ms`);
  }

  const avgDifferent = differentTimes.reduce((a, b) => a + b, 0) / differentTimes.length;
  console.log(`\nAverage time (different predictions): ${avgDifferent.toFixed(2)}ms\n`);

  // Summary
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Performance Summary');
  console.log('═══════════════════════════════════════════════════════\n');

  console.log(`No cache (5 identical):       ${avgNoCache.toFixed(2)}ms average`);
  console.log(`With cache (5 identical):     ${avgCache.toFixed(2)}ms average`);
  console.log(`Different predictions:        ${avgDifferent.toFixed(2)}ms average\n`);

  const speedup = avgNoCache / avgCache;
  const cacheOverhead = avgDifferent - avgNoCache;

  console.log(`Cache speedup:                ${speedup.toFixed(2)}x`);
  console.log(`Cache overhead:               ${cacheOverhead >= 0 ? '+' : ''}${cacheOverhead.toFixed(2)}ms\n`);

  // Cache hit breakdown
  const firstCall = cacheTimes[0];
  const cachedCalls = cacheTimes.slice(1);
  const avgCachedCall = cachedCalls.reduce((a, b) => a + b, 0) / cachedCalls.length;

  console.log('Cache hit breakdown:');
  console.log(`  First call (miss):          ${firstCall}ms`);
  console.log(`  Subsequent calls (hits):    ${avgCachedCall.toFixed(2)}ms average`);
  console.log(`  Hit speedup:                ${(firstCall / avgCachedCall).toFixed(2)}x\n`);

  console.log('═══════════════════════════════════════════════════════\n');
}

benchmark().catch(error => {
  console.error('Benchmark failed:', error);
  process.exit(1);
});
