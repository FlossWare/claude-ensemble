#!/usr/bin/env node

/**
 * Model Cache Usage Examples
 *
 * Demonstrates how to use model-cache.cjs with model-loader.cjs
 */

const { predict, getCacheStats, clearCache } = require('../shared/model-loader.cjs');
const modelCache = require('../shared/model-cache.cjs');

async function example1_basicCaching() {
  console.log('\n=== Example 1: Basic Prediction Caching ===\n');

  // Clear cache for clean example
  clearCache();

  const features = {
    prompt_length: 500,
    word_count: 250,
    num_implement: 3
  };

  console.log('Making first prediction (will compute)...');
  const start1 = Date.now();
  const result1 = await predict('complexity_estimator', features);
  const time1 = Date.now() - start1;

  console.log(`Result: ${JSON.stringify(result1)}`);
  console.log(`Time: ${time1}ms`);
  console.log(`Cached: ${result1.cached || false}\n`);

  console.log('Making second identical prediction (will use cache)...');
  const start2 = Date.now();
  const result2 = await predict('complexity_estimator', features);
  const time2 = Date.now() - start2;

  console.log(`Result: ${JSON.stringify(result2)}`);
  console.log(`Time: ${time2}ms`);
  console.log(`Cached: ${result2.cached || false}`);
  console.log(`Speedup: ${(time1 / time2).toFixed(2)}x\n`);
}

async function example2_customTTL() {
  console.log('\n=== Example 2: Custom Cache TTL ===\n');

  clearCache();

  const features = { prompt_length: 100 };

  // Cache for only 2 seconds
  console.log('Setting cache TTL to 2 seconds...');
  await predict('complexity_estimator', features, {
    cache: true,
    cacheTTL: 2000 // 2 seconds
  });

  console.log('Prediction cached for 2 seconds');

  // Immediate second call - should hit cache
  const result1 = await predict('complexity_estimator', features);
  console.log(`Immediate retry - Cached: ${result1.cached || false}`);

  // Wait for expiration
  console.log('Waiting 2.5 seconds for cache expiration...');
  await new Promise(resolve => setTimeout(resolve, 2500));

  // Should recompute now
  const result2 = await predict('complexity_estimator', features);
  console.log(`After expiration - Cached: ${result2.cached || false}\n`);
}

async function example3_disableCache() {
  console.log('\n=== Example 3: Disable Cache ===\n');

  const features = { prompt_length: 200 };

  // First with cache enabled
  await predict('complexity_estimator', features, { cache: true });
  console.log('First prediction (cached)');

  // Second with cache disabled (force recompute)
  const result = await predict('complexity_estimator', features, { cache: false });
  console.log(`Second prediction with cache=false - Cached: ${result.cached || false}\n`);
}

async function example4_cacheStats() {
  console.log('\n=== Example 4: Cache Statistics ===\n');

  clearCache();

  // Generate some activity
  const features1 = { prompt_length: 100 };
  const features2 = { prompt_length: 200 };
  const features3 = { prompt_length: 300 };

  await predict('complexity_estimator', features1);
  await predict('complexity_estimator', features1); // cache hit
  await predict('complexity_estimator', features2);
  await predict('complexity_estimator', features2); // cache hit
  await predict('complexity_estimator', features3);

  // Get detailed stats
  const stats = await getCacheStats();

  console.log('Prediction Cache Stats:');
  console.log(JSON.stringify(stats.javascript.predictions, null, 2));

  console.log('\nPython Model Cache:');
  console.log(JSON.stringify(stats.python, null, 2));

  console.log('\nDaemon Status:');
  console.log(JSON.stringify(stats.daemon, null, 2));
}

async function example5_directCacheAccess() {
  console.log('\n=== Example 5: Direct Cache Access ===\n');

  // Clear and reset
  modelCache.clear();
  modelCache.resetStats();

  // Direct cache manipulation
  const key = 'custom:prediction';
  const value = { prediction: 0.85, confidence: 0.92 };

  modelCache.set(key, value, 10000); // 10 second TTL
  console.log('Stored custom value in cache');

  const retrieved = modelCache.get(key);
  console.log(`Retrieved: ${JSON.stringify(retrieved)}`);

  // Check cache stats
  const stats = modelCache.getStats();
  console.log(`\nCache stats: ${stats.size} entries, ${stats.hitRate}% hit rate`);
  console.log(`Memory: ${stats.memoryEstimate}\n`);
}

async function example6_cleanup() {
  console.log('\n=== Example 6: Cache Cleanup ===\n');

  modelCache.clear();

  // Add entries with different TTLs
  console.log('Adding 5 entries with 1s TTL...');
  for (let i = 0; i < 5; i++) {
    modelCache.set(`short:${i}`, { value: i }, 1000);
  }

  console.log('Adding 5 entries with 10s TTL...');
  for (let i = 0; i < 5; i++) {
    modelCache.set(`long:${i}`, { value: i }, 10000);
  }

  console.log(`Initial size: ${modelCache.size()}`);

  // Wait for short TTL to expire
  await new Promise(resolve => setTimeout(resolve, 1500));

  // Manual cleanup
  const removed = modelCache.cleanup();
  console.log(`Cleaned up ${removed} expired entries`);
  console.log(`Size after cleanup: ${modelCache.size()}\n`);
}

async function runExamples() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Model Cache Usage Examples');
  console.log('═══════════════════════════════════════════════════════');

  try {
    await example1_basicCaching();
    await example2_customTTL();
    await example3_disableCache();
    await example4_cacheStats();
    await example5_directCacheAccess();
    await example6_cleanup();

    console.log('═══════════════════════════════════════════════════════');
    console.log('  All examples completed successfully!');
    console.log('═══════════════════════════════════════════════════════\n');

  } catch (error) {
    console.error('Example failed:', error.message);
    console.error(error.stack);
    process.exit(1);
  }

  process.exit(0);
}

// Run examples
runExamples();
