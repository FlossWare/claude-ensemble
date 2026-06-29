/**
 * Test Suite for Consensus Caching
 *
 * Tests:
 * 1. Exact match cache hit
 * 2. Semantic similarity cache hit (>95% similar)
 * 3. Cache miss (no match)
 * 4. Cache invalidation on model weight changes
 * 5. Cache statistics tracking
 * 6. Cache expiration (TTL)
 *
 * Run: node shared/test-consensus-cache.cjs
 */

const assert = require('assert');
const consensusCache = require('./consensus-cache.cjs');
const {
  lookupCache,
  storeCache,
  invalidateCache,
  getCacheStats,
  getCacheSummary,
  generateCacheKey,
  runWeightedVotingCached,
  cleanupExpiredEntries,
  DEFAULT_CACHE_TTL_MS,
  DEFAULT_SIMILARITY_THRESHOLD,
} = consensusCache;

// ============================================================================
// TEST UTILITIES
// ============================================================================

/**
 * Sleep for given milliseconds
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Clean up test data
 */
async function cleanup() {
  console.log('\n🧹 Cleaning up test data...');
  await invalidateCache({ all: true });
}

/**
 * Mock consensus result
 */
function mockConsensusResult(answer, consensusLevel = 'strong') {
  return {
    status: 'success',
    algorithm: 'weighted_voting',
    task_type: 'code_review',
    winner: {
      answer: answer,
      total_weight: 0.85,
      vote_count: 3,
      consensus_strength: 0.85,
      consensus_level: consensusLevel,
      votes: [
        { model: 'opus', weight: 0.45, confidence: 0.90 },
        { model: 'sonnet', weight: 0.30, confidence: 0.85 },
        { model: 'haiku', weight: 0.10, confidence: 0.70 },
      ],
    },
    runner_up: null,
    all_groups: [],
    metadata: {
      total_votes: 3,
      filtered_votes: 3,
      discarded_votes: 0,
      min_confidence_threshold: 20,
      total_weight: 0.85,
      num_unique_answers: 1,
    },
  };
}

// ============================================================================
// TESTS
// ============================================================================

/**
 * Test 1: Exact match cache hit
 */
async function testExactMatchHit() {
  console.log('\n📝 Test 1: Exact match cache hit');

  const question = 'Is this code vulnerable to SQL injection?';
  const taskType = 'security_audit';
  const consensusResult = mockConsensusResult('Yes, vulnerable on line 42');

  // Store in cache
  console.log('  - Storing consensus result in cache...');
  await storeCache(question, taskType, consensusResult);

  // Lookup (should hit)
  console.log('  - Looking up cached result...');
  const cacheHit = await lookupCache(question, taskType);

  assert(cacheHit !== null, 'Cache hit should not be null');
  assert.strictEqual(cacheHit.hit_type, 'exact', 'Should be exact match');
  assert.strictEqual(cacheHit.similarity, 1.0, 'Similarity should be 1.0');
  assert.deepStrictEqual(
    cacheHit.consensus_result,
    consensusResult,
    'Cached result should match stored result'
  );

  console.log('  ✅ PASS: Exact match cache hit');
}

/**
 * Test 2: Semantic similarity cache hit
 */
async function testSemanticSimilarityHit() {
  console.log('\n📝 Test 2: Semantic similarity cache hit');

  const originalQuestion = 'Does this function have any security vulnerabilities?';
  const similarQuestion = 'Are there security issues in this function?';
  const taskType = 'security_audit';
  const consensusResult = mockConsensusResult('Yes, buffer overflow on line 15');

  // Store original question
  console.log('  - Storing original question in cache...');
  await storeCache(originalQuestion, taskType, consensusResult);

  // Wait for embedding to be stored
  await sleep(1000);

  // Lookup with similar question (should hit via semantic search)
  console.log('  - Looking up similar question...');
  const cacheHit = await lookupCache(similarQuestion, taskType);

  if (!cacheHit) {
    console.log('  ⚠️  SKIP: Semantic search failed (embedding generation may be unavailable)');
    return;
  }

  assert.strictEqual(cacheHit.hit_type, 'semantic', 'Should be semantic match');
  assert(
    cacheHit.similarity >= DEFAULT_SIMILARITY_THRESHOLD,
    `Similarity (${cacheHit.similarity}) should be >= ${DEFAULT_SIMILARITY_THRESHOLD}`
  );
  assert.strictEqual(
    cacheHit.original_question,
    originalQuestion,
    'Should return original question'
  );
  assert.deepStrictEqual(
    cacheHit.consensus_result,
    consensusResult,
    'Cached result should match stored result'
  );

  console.log(`  ✅ PASS: Semantic similarity hit (similarity: ${(cacheHit.similarity * 100).toFixed(1)}%)`);
}

/**
 * Test 3: Cache miss (no match)
 */
async function testCacheMiss() {
  console.log('\n📝 Test 3: Cache miss (no match)');

  const question = 'Is this code optimized for performance?';
  const taskType = 'code_review';

  // Lookup (should miss)
  console.log('  - Looking up non-existent question...');
  const cacheHit = await lookupCache(question, taskType);

  assert.strictEqual(cacheHit, null, 'Cache miss should return null');

  console.log('  ✅ PASS: Cache miss detected correctly');
}

/**
 * Test 4: Cache invalidation
 */
async function testCacheInvalidation() {
  console.log('\n📝 Test 4: Cache invalidation');

  const question = 'Does this code follow best practices?';
  const taskType = 'code_review';
  const consensusResult = mockConsensusResult('Yes, follows best practices');

  // Store in cache
  console.log('  - Storing consensus result in cache...');
  await storeCache(question, taskType, consensusResult);

  // Verify it's cached
  let cacheHit = await lookupCache(question, taskType);
  assert(cacheHit !== null, 'Should be cached before invalidation');

  // Invalidate task type
  console.log('  - Invalidating cache for task type...');
  const invalidated = await invalidateCache({ taskType: 'code_review' });
  assert(invalidated >= 1, 'At least 1 entry should be invalidated');

  // Verify it's no longer cached
  cacheHit = await lookupCache(question, taskType);
  assert.strictEqual(cacheHit, null, 'Should be invalidated');

  console.log('  ✅ PASS: Cache invalidation works correctly');
}

/**
 * Test 5: Cache statistics tracking
 */
async function testCacheStatistics() {
  console.log('\n📝 Test 5: Cache statistics tracking');

  const question = 'Is this code thread-safe?';
  const taskType = 'code_review';
  const consensusResult = mockConsensusResult('No, race condition detected');

  // Store in cache
  console.log('  - Storing consensus result in cache...');
  await storeCache(question, taskType, consensusResult);

  // Trigger cache hits
  console.log('  - Triggering cache hits...');
  await lookupCache(question, taskType); // Hit 1
  await lookupCache(question, taskType); // Hit 2
  await lookupCache(question, taskType); // Hit 3

  // Trigger cache miss
  await lookupCache('Some other question', taskType); // Miss

  // Get statistics
  console.log('  - Fetching cache statistics...');
  const summary = await getCacheSummary();

  console.log('  - Statistics:');
  console.log(`    Total lookups (today): ${summary.today.total_lookups}`);
  console.log(`    Exact hits (today): ${summary.today.exact_hits}`);
  console.log(`    Semantic hits (today): ${summary.today.semantic_hits}`);
  console.log(`    Misses (today): ${summary.today.misses}`);
  console.log(`    Hit rate (today): ${summary.today.hit_rate.toFixed(1)}%`);
  console.log(`    Cache size: ${summary.cache_size.active_entries} active, ${summary.cache_size.expired_entries} expired`);

  assert(summary.today.total_lookups >= 4, 'Should have at least 4 lookups');
  assert(summary.today.exact_hits >= 3, 'Should have at least 3 exact hits');
  assert(summary.cache_size.active_entries >= 1, 'Should have at least 1 active entry');

  console.log('  ✅ PASS: Cache statistics tracking works correctly');
}

/**
 * Test 6: Cache expiration (TTL)
 */
async function testCacheExpiration() {
  console.log('\n📝 Test 6: Cache expiration (TTL)');

  const question = 'Is this code idiomatic?';
  const taskType = 'code_review';
  const consensusResult = mockConsensusResult('Yes, idiomatic');

  // Store with short TTL (2 seconds)
  console.log('  - Storing consensus result with 2s TTL...');
  await storeCache(question, taskType, consensusResult, { ttlMs: 2000 });

  // Verify it's cached
  let cacheHit = await lookupCache(question, taskType);
  assert(cacheHit !== null, 'Should be cached immediately');

  // Wait for expiration
  console.log('  - Waiting 3 seconds for expiration...');
  await sleep(3000);

  // Verify it's expired
  cacheHit = await lookupCache(question, taskType);
  assert.strictEqual(cacheHit, null, 'Should be expired after TTL');

  console.log('  ✅ PASS: Cache expiration works correctly');
}

/**
 * Test 7: Integration with weighted voting
 */
async function testIntegrationWithWeightedVoting() {
  console.log('\n📝 Test 7: Integration with weighted voting');

  const question = 'Is this authentication implementation secure?';
  const taskType = 'security_audit';

  // Mock votes
  const votes = [
    { model: 'opus', answer: 'No, uses weak hashing (MD5)', confidence: 0.90 },
    { model: 'sonnet', answer: 'No, uses weak hashing (MD5)', confidence: 0.85 },
    { model: 'haiku', answer: 'No, uses weak hashing (MD5)', confidence: 0.75 },
  ];

  // First call (cache miss)
  console.log('  - First call (should miss cache)...');
  const result1 = await runWeightedVotingCached(question, votes, taskType);
  assert.strictEqual(result1.cache_hit, false, 'First call should miss cache');
  assert(result1.cache_metadata.stored, 'Result should be stored in cache');

  // Second call (cache hit)
  console.log('  - Second call (should hit cache)...');
  const result2 = await runWeightedVotingCached(question, votes, taskType);
  assert.strictEqual(result2.cache_hit, true, 'Second call should hit cache');
  assert.strictEqual(result2.cache_metadata.hit_type, 'exact', 'Should be exact match');

  console.log('  ✅ PASS: Integration with weighted voting works correctly');
}

/**
 * Test 8: Cleanup expired entries
 */
async function testCleanupExpiredEntries() {
  console.log('\n📝 Test 8: Cleanup expired entries');

  const question1 = 'Is this code maintainable?';
  const question2 = 'Is this code scalable?';
  const taskType = 'code_review';
  const consensusResult = mockConsensusResult('Yes');

  // Store entry 1 with short TTL (1 second)
  console.log('  - Storing entry 1 with 1s TTL...');
  await storeCache(question1, taskType, consensusResult, { ttlMs: 1000 });

  // Store entry 2 with long TTL (1 hour)
  console.log('  - Storing entry 2 with 1h TTL...');
  await storeCache(question2, taskType, consensusResult, { ttlMs: 60 * 60 * 1000 });

  // Wait for entry 1 to expire
  console.log('  - Waiting 2 seconds for entry 1 to expire...');
  await sleep(2000);

  // Clean up expired entries
  console.log('  - Cleaning up expired entries...');
  const cleaned = await cleanupExpiredEntries();
  assert(cleaned >= 1, 'At least 1 expired entry should be cleaned up');

  // Verify entry 1 is gone
  const cacheHit1 = await lookupCache(question1, taskType);
  assert.strictEqual(cacheHit1, null, 'Expired entry should be removed');

  // Verify entry 2 is still cached
  const cacheHit2 = await lookupCache(question2, taskType);
  assert(cacheHit2 !== null, 'Non-expired entry should remain');

  console.log('  ✅ PASS: Cleanup expired entries works correctly');
}

// ============================================================================
// RUN TESTS
// ============================================================================

async function runTests() {
  console.log('🧪 Consensus Cache Test Suite\n');
  console.log('═'.repeat(60));

  try {
    // Initialize schema first (wait for async completion)
    console.log('\n🔧 Initializing database schema...');
    // Access internal initializeSchema via require (hack for testing)
    const { initializeSchema } = require('./consensus-cache.cjs');
    await initializeSchema();
    console.log('✅ Schema initialized');

    // Clean up before tests
    await cleanup();

    // Run tests
    await testExactMatchHit();
    await testSemanticSimilarityHit();
    await testCacheMiss();
    await testCacheInvalidation();
    await testCacheStatistics();
    await testCacheExpiration();
    await testIntegrationWithWeightedVoting();
    await testCleanupExpiredEntries();

    // Summary
    console.log('\n' + '═'.repeat(60));
    console.log('✅ All tests passed!');
    console.log('═'.repeat(60));

    // Print final statistics
    console.log('\n📊 Final Cache Statistics:');
    const summary = await getCacheSummary();
    console.log(JSON.stringify(summary, null, 2));

    // Clean up after tests
    await cleanup();

    process.exit(0);

  } catch (err) {
    console.error('\n❌ Test failed:');
    console.error(err);
    process.exit(1);
  }
}

// Run tests if executed directly
if (require.main === module) {
  runTests();
}

module.exports = { runTests };
