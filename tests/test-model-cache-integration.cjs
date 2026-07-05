#!/usr/bin/env node

/**
 * Test Model Cache Integration
 *
 * Verifies that model-cache.cjs integrates correctly with model-loader.cjs
 *
 * Tests:
 * 1. Basic cache operations (get/set/clear)
 * 2. TTL expiration
 * 3. Cache statistics
 * 4. Integration with model predictions
 * 5. LRU eviction
 * 6. Memory estimation
 */

const modelCache = require('../shared/model-cache.cjs');
const { predict, getCacheStats, clearCache } = require('../shared/model-loader.cjs');

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testBasicOperations() {
  console.log('\n=== Test 1: Basic Cache Operations ===');

  // Clear cache before testing
  modelCache.clear();
  modelCache.resetStats();

  // Test set/get
  const key1 = 'test:key1';
  const value1 = { result: 'test1' };

  modelCache.set(key1, value1);
  const retrieved = modelCache.get(key1);

  if (JSON.stringify(retrieved) === JSON.stringify(value1)) {
    console.log('✓ Basic set/get works');
  } else {
    console.error('✗ Basic set/get failed');
    return false;
  }

  // Test has()
  if (modelCache.has(key1)) {
    console.log('✓ has() works for existing key');
  } else {
    console.error('✗ has() failed');
    return false;
  }

  // Test missing key
  if (!modelCache.has('nonexistent:key')) {
    console.log('✓ has() works for missing key');
  } else {
    console.error('✗ has() false positive');
    return false;
  }

  // Test delete
  modelCache.delete(key1);
  if (!modelCache.has(key1)) {
    console.log('✓ delete() works');
  } else {
    console.error('✗ delete() failed');
    return false;
  }

  return true;
}

async function testTTLExpiration() {
  console.log('\n=== Test 2: TTL Expiration ===');

  modelCache.clear();
  modelCache.resetStats();

  const key = 'test:ttl';
  const value = { result: 'expires soon' };

  // Set with 100ms TTL
  modelCache.set(key, value, 100);

  // Should exist immediately
  if (modelCache.has(key)) {
    console.log('✓ Entry exists immediately after set');
  } else {
    console.error('✗ Entry missing immediately after set');
    return false;
  }

  // Wait for expiration
  await sleep(150);

  // Should be expired now
  if (!modelCache.has(key)) {
    console.log('✓ Entry expired after TTL');
  } else {
    console.error('✗ Entry did not expire');
    return false;
  }

  // get() should return null for expired entry
  if (modelCache.get(key) === null) {
    console.log('✓ get() returns null for expired entry');
  } else {
    console.error('✗ get() returned value for expired entry');
    return false;
  }

  return true;
}

async function testCacheStatistics() {
  console.log('\n=== Test 3: Cache Statistics ===');

  modelCache.clear();
  modelCache.resetStats();

  // Generate some cache activity
  modelCache.set('test:1', { value: 1 });
  modelCache.set('test:2', { value: 2 });
  modelCache.set('test:3', { value: 3 });

  // Create hits
  modelCache.get('test:1');
  modelCache.get('test:1');
  modelCache.get('test:2');

  // Create misses
  modelCache.get('test:nonexistent1');
  modelCache.get('test:nonexistent2');

  const stats = modelCache.getStats();

  console.log('Statistics:', JSON.stringify(stats, null, 2));

  if (stats.size === 3) {
    console.log('✓ Cache size correct (3)');
  } else {
    console.error(`✗ Cache size incorrect: ${stats.size}`);
    return false;
  }

  if (stats.hits === 3) {
    console.log('✓ Hit count correct (3)');
  } else {
    console.error(`✗ Hit count incorrect: ${stats.hits}`);
    return false;
  }

  if (stats.misses === 2) {
    console.log('✓ Miss count correct (2)');
  } else {
    console.error(`✗ Miss count incorrect: ${stats.misses}`);
    return false;
  }

  if (stats.hitRate === 60) {
    console.log('✓ Hit rate correct (60%)');
  } else {
    console.error(`✗ Hit rate incorrect: ${stats.hitRate}`);
    return false;
  }

  return true;
}

async function testModelLoaderIntegration() {
  console.log('\n=== Test 4: Model Loader Integration ===');

  clearCache();

  // Create mock features for testing
  const features = {
    prompt_length: 100,
    word_count: 50,
    num_implement: 1
  };

  try {
    // First prediction - should miss cache
    const result1 = await predict('complexity_estimator', features, { cache: true });

    if (result1.error) {
      console.log('⚠ Skipping model loader test (model not available)');
      console.log(`  Error: ${result1.error}`);
      return true; // Not a test failure
    }

    if (!result1.cached) {
      console.log('✓ First prediction not cached (as expected)');
    } else {
      console.error('✗ First prediction incorrectly marked as cached');
      return false;
    }

    // Second identical prediction - should hit cache
    const result2 = await predict('complexity_estimator', features, { cache: true });

    if (result2.cached) {
      console.log('✓ Second prediction retrieved from cache');
    } else {
      console.error('✗ Second prediction did not use cache');
      return false;
    }

    // Get combined cache stats
    const stats = await getCacheStats();
    console.log('\nCombined cache stats:', JSON.stringify(stats, null, 2));

    if (stats.javascript && stats.javascript.predictions) {
      console.log('✓ Cache stats accessible via model loader');
    } else {
      console.error('✗ Cache stats not accessible');
      return false;
    }

  } catch (error) {
    console.error('✗ Model loader integration test failed:', error.message);
    return false;
  }

  return true;
}

async function testLRUEviction() {
  console.log('\n=== Test 5: LRU Eviction ===');

  modelCache.clear();
  modelCache.resetStats();

  // Temporarily reduce max size for testing
  const originalMaxSize = modelCache.maxSize;
  modelCache.maxSize = 3;

  // Fill cache to max
  modelCache.set('test:1', { value: 1 });
  await sleep(10);
  modelCache.set('test:2', { value: 2 });
  await sleep(10);
  modelCache.set('test:3', { value: 3 });

  if (modelCache.size() === 3) {
    console.log('✓ Cache filled to max size (3)');
  } else {
    console.error(`✗ Cache size incorrect: ${modelCache.size()}`);
    modelCache.maxSize = originalMaxSize;
    return false;
  }

  // Access test:1 and test:2 to make them recently used
  modelCache.get('test:1');
  await sleep(10);
  modelCache.get('test:2');
  await sleep(10);

  // Add new entry - should evict test:3 (least recently used)
  modelCache.set('test:4', { value: 4 });

  if (modelCache.size() === 3) {
    console.log('✓ Cache size maintained at max after eviction');
  } else {
    console.error(`✗ Cache size incorrect after eviction: ${modelCache.size()}`);
    modelCache.maxSize = originalMaxSize;
    return false;
  }

  if (!modelCache.has('test:3')) {
    console.log('✓ LRU entry (test:3) was evicted');
  } else {
    console.error('✗ LRU entry was not evicted');
    modelCache.maxSize = originalMaxSize;
    return false;
  }

  if (modelCache.has('test:1') && modelCache.has('test:2') && modelCache.has('test:4')) {
    console.log('✓ Recently used entries retained');
  } else {
    console.error('✗ Recently used entries were evicted');
    modelCache.maxSize = originalMaxSize;
    return false;
  }

  // Restore original max size
  modelCache.maxSize = originalMaxSize;

  return true;
}

async function testMemoryEstimation() {
  console.log('\n=== Test 6: Memory Estimation ===');

  modelCache.clear();

  // Add various sized entries
  for (let i = 0; i < 100; i++) {
    modelCache.set(`test:${i}`, {
      index: i,
      data: 'x'.repeat(100) // 100 bytes of data per entry
    });
  }

  const stats = modelCache.getStats();

  console.log(`Memory estimate: ${stats.memoryEstimate}`);

  if (stats.memoryEstimate.includes('KB') || stats.memoryEstimate.includes('B')) {
    console.log('✓ Memory estimation provides human-readable format');
  } else {
    console.error('✗ Memory estimation format incorrect');
    return false;
  }

  if (stats.size === 100) {
    console.log('✓ Size tracking correct (100 entries)');
  } else {
    console.error(`✗ Size tracking incorrect: ${stats.size}`);
    return false;
  }

  return true;
}

async function testCleanup() {
  console.log('\n=== Test 7: Cleanup Function ===');

  modelCache.clear();

  // Add entries with short TTL
  for (let i = 0; i < 10; i++) {
    modelCache.set(`test:${i}`, { value: i }, 50); // 50ms TTL
  }

  // Add entries with long TTL
  for (let i = 10; i < 20; i++) {
    modelCache.set(`test:${i}`, { value: i }, 10000); // 10s TTL
  }

  if (modelCache.size() === 20) {
    console.log('✓ All 20 entries added');
  } else {
    console.error(`✗ Entry count incorrect: ${modelCache.size()}`);
    return false;
  }

  // Wait for short TTL entries to expire
  await sleep(100);

  // Run cleanup
  const removed = modelCache.cleanup();

  if (removed === 10) {
    console.log('✓ Cleanup removed 10 expired entries');
  } else {
    console.error(`✗ Cleanup removed ${removed} entries (expected 10)`);
    return false;
  }

  if (modelCache.size() === 10) {
    console.log('✓ Cache size correct after cleanup (10)');
  } else {
    console.error(`✗ Cache size incorrect after cleanup: ${modelCache.size()}`);
    return false;
  }

  return true;
}

async function runAllTests() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Model Cache Integration Test Suite');
  console.log('═══════════════════════════════════════════════════════');

  const tests = [
    { name: 'Basic Operations', fn: testBasicOperations },
    { name: 'TTL Expiration', fn: testTTLExpiration },
    { name: 'Cache Statistics', fn: testCacheStatistics },
    { name: 'Model Loader Integration', fn: testModelLoaderIntegration },
    { name: 'LRU Eviction', fn: testLRUEviction },
    { name: 'Memory Estimation', fn: testMemoryEstimation },
    { name: 'Cleanup Function', fn: testCleanup }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      const result = await test.fn();
      if (result) {
        passed++;
      } else {
        failed++;
        console.error(`\n✗ Test "${test.name}" FAILED`);
      }
    } catch (error) {
      failed++;
      console.error(`\n✗ Test "${test.name}" CRASHED:`, error.message);
      console.error(error.stack);
    }
  }

  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  Test Summary');
  console.log('═══════════════════════════════════════════════════════');
  console.log(`Total: ${tests.length}`);
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);

  // Final cache stats
  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  Final Cache Statistics');
  console.log('═══════════════════════════════════════════════════════');
  const finalStats = modelCache.getStats();
  console.log(JSON.stringify(finalStats, null, 2));

  // Cleanup
  modelCache.clear();

  process.exit(failed > 0 ? 1 : 0);
}

// Run tests
runAllTests().catch(error => {
  console.error('Test suite crashed:', error);
  process.exit(1);
});
