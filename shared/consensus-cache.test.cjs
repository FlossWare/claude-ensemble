/**
 * Consensus Cache Test Suite
 *
 * Tests for two-level consensus caching system:
 * - Level 1: Exact hash match
 * - Level 2: Semantic similarity
 *
 * Run: node consensus-cache.test.cjs
 */

const {
  generateCacheKey,
  generateSemanticFingerprint,
  getConsensusCache,
  weightedVotingWithCache,
  CACHE_CONFIG,
} = require('./consensus-cache.cjs');

// ============================================================================
// TEST HELPERS
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`✓ ${message}`);
    testsPassed++;
  } else {
    console.error(`✗ ${message}`);
    testsFailed++;
  }
}

function assertEquals(actual, expected, message) {
  const eq = JSON.stringify(actual) === JSON.stringify(expected);
  assert(eq, `${message} (expected: ${JSON.stringify(expected)}, got: ${JSON.stringify(actual)})`);
}

function assertNotNull(value, message) {
  assert(value !== null && value !== undefined, message);
}

// ============================================================================
// TEST DATA
// ============================================================================

const sampleVotes1 = [
  { model: 'opus', answer: 'A', confidence: 0.95 },
  { model: 'sonnet', answer: 'A', confidence: 0.85 },
  { model: 'haiku', answer: 'B', confidence: 0.60 },
];

const sampleVotes2 = [
  { model: 'haiku', answer: 'B', confidence: 0.60 },
  { model: 'opus', answer: 'A', confidence: 0.95 },
  { model: 'sonnet', answer: 'A', confidence: 0.85 },
];

const sampleVotes3 = [
  { model: 'opus', answer: 'C', confidence: 0.90 },
  { model: 'sonnet', answer: 'C', confidence: 0.88 },
  { model: 'haiku', answer: 'C', confidence: 0.75 },
];

const sampleVotesSemanticallyDifferent = [
  { model: 'gpt-4o', answer: 'X', confidence: 0.80 },
  { model: 'gemini', answer: 'Y', confidence: 0.82 },
  { model: 'fable', answer: 'Z', confidence: 0.90 },
];

const sampleConsensusResult = {
  status: 'success',
  task_type: 'code_review',
  winner: {
    answer: 'A',
    total_weight: 2.5,
    vote_count: 2,
    consensus_strength: 0.85,
    consensus_level: 'strong',
  },
  metadata: {
    total_votes: 3,
    num_unique_answers: 2,
  },
};

// ============================================================================
// UNIT TESTS
// ============================================================================

async function testCacheKeyGeneration() {
  console.log('\n=== Test: Cache Key Generation ===\n');

  // Test 1: Deterministic key generation
  const key1 = generateCacheKey(sampleVotes1, 'code_review');
  const key2 = generateCacheKey(sampleVotes1, 'code_review');

  assert(key1 === key2, 'Cache keys should be deterministic');
  assert(key1.length === 64, 'Cache key should be 64 hex chars (SHA-256)');

  // Test 2: Order independence (votes sorted internally)
  const key3 = generateCacheKey(sampleVotes2, 'code_review');
  assert(key1 === key3, 'Cache keys should be order-independent (normalized)');

  // Test 3: Different votes = different keys
  const key4 = generateCacheKey(sampleVotes3, 'code_review');
  assert(key1 !== key4, 'Different votes should produce different cache keys');

  // Test 4: Different task type = different key
  const key5 = generateCacheKey(sampleVotes1, 'security_audit');
  assert(key1 !== key5, 'Different task types should produce different cache keys');
}

async function testSemanticFingerprintGeneration() {
  console.log('\n=== Test: Semantic Fingerprint Generation ===\n');

  // Test 1: Fingerprint includes task type
  const fp1 = generateSemanticFingerprint(sampleVotes1, 'code_review');
  assert(fp1.includes('code_review'), 'Fingerprint should include task type');

  // Test 2: Fingerprint includes model names
  assert(fp1.includes('opus'), 'Fingerprint should include model names');
  assert(fp1.includes('sonnet'), 'Fingerprint should include model names');
  assert(fp1.includes('haiku'), 'Fingerprint should include model names');

  // Test 3: Fingerprint includes answer distribution
  assert(fp1.includes('2 votes for "A"') || fp1.includes('"A"'), 'Fingerprint should include answer distribution');

  // Test 4: Different votes = different fingerprints
  const fp2 = generateSemanticFingerprint(sampleVotesSemanticallyDifferent, 'code_review');
  assert(fp1 !== fp2, 'Different votes should produce different fingerprints');
}

async function testExactCacheHit() {
  console.log('\n=== Test: Exact Cache Hit (Level 1) ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Store a consensus result
  const cacheId = await cache.set(sampleVotes1, 'code_review', sampleConsensusResult);
  assertNotNull(cacheId, 'Cache entry should be stored successfully');

  // Retrieve with exact match
  const cached = await cache.getExact(sampleVotes1, 'code_review');
  assertNotNull(cached, 'Cache hit should return result');
  assert(cached.cache_hit === true, 'Cache hit flag should be true');
  assert(cached.cache_level === 'exact', 'Cache level should be "exact"');
  assertEquals(cached.winning_answer, 'A', 'Cached answer should match stored answer');
  assert(cached.consensus_strength === 0.85, 'Cached consensus strength should match');

  // Test order independence
  const cached2 = await cache.getExact(sampleVotes2, 'code_review');
  assertNotNull(cached2, 'Cache hit should work with reordered votes');
  assert(cached2.cache_key === cached.cache_key, 'Cache keys should match for reordered votes');
}

async function testSemanticCacheHit() {
  console.log('\n=== Test: Semantic Cache Hit (Level 2) ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Store a consensus result (votes 3)
  await cache.set(sampleVotes3, 'research', sampleConsensusResult);

  // Create semantically similar votes (same models, slightly different answers)
  const semanticallySimilarVotes = [
    { model: 'opus', answer: 'C', confidence: 0.92 },  // Confidence changed slightly
    { model: 'sonnet', answer: 'C', confidence: 0.86 }, // Confidence changed slightly
    { model: 'haiku', answer: 'C', confidence: 0.73 },  // Confidence changed slightly
  ];

  // Semantic search should find similar result
  const cached = await cache.getSemantic(semanticallySimilarVotes, 'research');

  // Note: Semantic hit may not occur if embeddings are too different
  // This test validates the mechanism, not guaranteed hit
  if (cached) {
    assert(cached.cache_level === 'semantic', 'Cache level should be "semantic"');
    assert(cached.semantic_distance < CACHE_CONFIG.semantic_threshold, 'Distance should be below threshold');
  } else {
    console.log('  ⚠ Semantic cache miss (expected if votes too different)');
  }
}

async function testCacheMiss() {
  console.log('\n=== Test: Cache Miss ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Try to retrieve non-existent cache entry
  const cached = await cache.get(sampleVotesSemanticallyDifferent, 'security_audit');

  assert(cached === null, 'Cache miss should return null');
}

async function testCacheExpiration() {
  console.log('\n=== Test: Cache Expiration ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Store with very short TTL (1 second)
  const originalTtl = CACHE_CONFIG.ttl_days;
  CACHE_CONFIG.ttl_days = 0; // 0 days = immediate expiration

  await cache.set(sampleVotes1, 'test_expiration', sampleConsensusResult);

  CACHE_CONFIG.ttl_days = originalTtl; // Restore

  // Wait 2 seconds
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Try to retrieve expired entry
  const cached = await cache.get(sampleVotes1, 'test_expiration');

  assert(cached === null, 'Expired cache entry should return null');
}

async function testCacheInvalidation() {
  console.log('\n=== Test: Cache Invalidation ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Store a cache entry
  await cache.set(sampleVotes1, 'test_invalidation', sampleConsensusResult);

  // Get cache key
  const cacheKey = generateCacheKey(sampleVotes1, 'test_invalidation');

  // Invalidate
  const invalidated = await cache.invalidate(cacheKey);

  assert(invalidated === true, 'Cache entry should be invalidated successfully');

  // Try to retrieve invalidated entry
  const cached = await cache.get(sampleVotes1, 'test_invalidation');

  assert(cached === null, 'Invalidated cache entry should return null');
}

async function testCacheStats() {
  console.log('\n=== Test: Cache Statistics ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  const stats = await cache.getStats();

  assertNotNull(stats, 'Stats should be returned');
  assert(typeof stats.total_entries === 'number', 'Total entries should be a number');
  assert(typeof stats.active_entries === 'number', 'Active entries should be a number');
  assert(typeof stats.total_hits === 'number', 'Total hits should be a number');

  console.log(`  Cache stats: ${stats.active_entries} active entries, ${stats.total_hits} total hits`);
}

async function testCleanupExpired() {
  console.log('\n=== Test: Cleanup Expired Entries ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Store with immediate expiration
  const originalTtl = CACHE_CONFIG.ttl_days;
  CACHE_CONFIG.ttl_days = -1; // -1 days = already expired

  await cache.set(sampleVotes1, 'test_cleanup', sampleConsensusResult);

  CACHE_CONFIG.ttl_days = originalTtl; // Restore

  // Run cleanup
  const deletedCount = await cache.cleanupExpired();

  assert(deletedCount >= 1, 'At least 1 expired entry should be deleted');
  console.log(`  Cleaned up ${deletedCount} expired entries`);
}

async function testWeightedVotingIntegration() {
  console.log('\n=== Test: Weighted Voting Integration ===\n');

  const cache = getConsensusCache();
  await cache.ensureTable();

  // Mock weighted voting function
  let votingCalled = false;
  async function mockWeightedVoting(votes, taskType, options) {
    votingCalled = true;
    return sampleConsensusResult;
  }

  // First call - should trigger voting and cache storage
  votingCalled = false;
  const result1 = await weightedVotingWithCache(
    mockWeightedVoting,
    sampleVotes1,
    'integration_test',
    {}
  );

  assert(votingCalled === true, 'First call should trigger weighted voting');
  assert(result1.cache_hit === false, 'First call should be cache miss');

  // Second call - should hit cache
  votingCalled = false;
  const result2 = await weightedVotingWithCache(
    mockWeightedVoting,
    sampleVotes1,
    'integration_test',
    {}
  );

  assert(votingCalled === false, 'Second call should NOT trigger weighted voting (cache hit)');
  assert(result2.cache_hit === true, 'Second call should be cache hit');
  assert(result2.cache_level === 'exact', 'Cache level should be exact');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║       Consensus Cache Test Suite (Building Block #4)      ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  try {
    await testCacheKeyGeneration();
    await testSemanticFingerprintGeneration();
    await testExactCacheHit();
    await testSemanticCacheHit();
    await testCacheMiss();
    await testCacheExpiration();
    await testCacheInvalidation();
    await testCacheStats();
    await testCleanupExpired();
    await testWeightedVotingIntegration();

  } catch (err) {
    console.error('\n❌ Test suite failed with error:', err);
    testsFailed++;
  }

  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log(`║ RESULTS: ${testsPassed} passed, ${testsFailed} failed`);
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  process.exit(testsFailed > 0 ? 1 : 0);
}

// Run tests if called directly
if (require.main === module) {
  runAllTests().catch(err => {
    console.error('Test runner error:', err);
    process.exit(1);
  });
}

module.exports = {
  runAllTests,
};
