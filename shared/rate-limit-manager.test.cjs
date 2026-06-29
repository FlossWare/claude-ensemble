/**
 * Test Suite for Rate Limit Manager
 *
 * Tests:
 * 1. Database initialization
 * 2. Rate limit configuration lookup
 * 3. Request recording and counting
 * 4. Sliding window behavior
 * 5. Throttling and wait logic
 * 6. Provider filtering
 * 7. Statistics reporting
 * 8. Cleanup operations
 *
 * Run: node shared/rate-limit-manager.test.cjs
 */

const {
  checkRateLimit,
  recordRequest,
  getRateLimitStats,
  getRequestCount,
  getTimeUntilReset,
  filterAvailableProviders,
  getRateLimitConfig,
  cleanupOldRequests,
  initializeDatabase,
  close,
  RATE_LIMITS,
  WINDOW_DURATION_MS,
} = require('./rate-limit-manager.cjs');

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
  if (actual === expected) {
    console.log(`✓ ${message} (${actual})`);
    testsPassed++;
  } else {
    console.error(`✗ ${message} - Expected: ${expected}, Got: ${actual}`);
    testsFailed++;
  }
}

function assertApprox(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  if (diff <= tolerance) {
    console.log(`✓ ${message} (${actual} ≈ ${expected})`);
    testsPassed++;
  } else {
    console.error(`✗ ${message} - Expected: ${expected} ± ${tolerance}, Got: ${actual}`);
    testsFailed++;
  }
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================================
// TEST SUITE
// ============================================================================

async function runTests() {
  console.log('='.repeat(70));
  console.log('Rate Limit Manager Test Suite');
  console.log('='.repeat(70));
  console.log('');

  // Test 1: Database Initialization
  console.log('[Test 1] Database Initialization');
  try {
    await initializeDatabase();
    assert(true, 'Database tables created successfully');
  } catch (err) {
    assert(false, `Database initialization failed: ${err.message}`);
  }
  console.log('');

  // Test 2: Rate Limit Configuration Lookup
  console.log('[Test 2] Rate Limit Configuration Lookup');

  const groqConfig = getRateLimitConfig('groq');
  assertEquals(groqConfig.rpm, 30, 'Groq RPM configured correctly');
  assertEquals(groqConfig.buffer, 2, 'Groq buffer configured correctly');

  const perplexityConfig = getRateLimitConfig('perplexity');
  assertApprox(perplexityConfig.rpm, 0.083, 0.01, 'Perplexity RPM configured correctly');

  const openrouterConfig = getRateLimitConfig('openrouter/anthropic/claude-3-haiku');
  assertEquals(openrouterConfig.rpm, 10, 'OpenRouter model RPM configured correctly');

  const defaultConfig = getRateLimitConfig('unknown-provider');
  assertEquals(defaultConfig.rpm, 60, 'Default RPM configured correctly');

  const ollamaConfig = getRateLimitConfig('ollama');
  assertEquals(ollamaConfig.rpm, Infinity, 'Ollama has no rate limit');
  console.log('');

  // Test 3: Request Recording and Counting
  console.log('[Test 3] Request Recording and Counting');

  const testProvider = 'test-provider-' + Date.now();

  // Record 5 requests
  for (let i = 0; i < 5; i++) {
    await recordRequest(testProvider, true, { test_id: i });
  }

  await sleep(100); // Allow DB writes to complete

  const count = await getRequestCount(testProvider);
  assertEquals(count, 5, 'Request count matches recorded requests');
  console.log('');

  // Test 4: Sliding Window Behavior
  console.log('[Test 4] Sliding Window Behavior');

  // Get time until reset
  const resetTime = await getTimeUntilReset(testProvider);
  assert(resetTime > 0, `Time until reset is positive (${(resetTime / 1000).toFixed(1)}s)`);
  assert(resetTime <= WINDOW_DURATION_MS, `Time until reset <= window duration (${(resetTime / 1000).toFixed(1)}s <= 60s)`);
  console.log('');

  // Test 5: Throttling and Wait Logic
  console.log('[Test 5] Throttling and Wait Logic');

  // Test provider with very low limit
  const throttleProvider = 'test-throttle-' + Date.now();

  // Manually override rate limit for testing (simulate 3 RPM with buffer=1)
  RATE_LIMITS[throttleProvider] = { rpm: 3, rph: 180, buffer: 1 };

  // Record 2 requests (at limit-buffer)
  await recordRequest(throttleProvider, true);
  await recordRequest(throttleProvider, true);
  await sleep(100);

  // Check rate limit (should throttle)
  const startTime = Date.now();
  const result = await checkRateLimit(throttleProvider, { throwOnLimit: false });
  const elapsed = Date.now() - startTime;

  assert(result.throttled === true, 'Throttling detected when at limit');
  assert(elapsed > 1000, `Wait time enforced (${(elapsed / 1000).toFixed(1)}s)`);

  // Verify we can make a request after waiting
  const afterWait = await getRequestCount(throttleProvider);
  assert(afterWait < 3, 'Request count decreased after window slide');
  console.log('');

  // Test 6: Provider Filtering
  console.log('[Test 6] Provider Filtering');

  const providers = ['ollama', 'groq', throttleProvider];
  const available = await filterAvailableProviders(providers);

  assert(available.includes('ollama'), 'Ollama always available (no limit)');
  assert(available.includes('groq'), 'Groq available (under limit)');
  // throttleProvider may or may not be available depending on timing
  console.log(`Available providers: ${available.join(', ')}`);
  console.log('');

  // Test 7: Statistics Reporting
  console.log('[Test 7] Statistics Reporting');

  const stats = await getRateLimitStats();
  assert(Array.isArray(stats), 'Stats returns array');
  assert(stats.length > 0, `Stats contains entries (${stats.length} providers)`);

  const testProviderStats = stats.find(s => s.provider === testProvider);
  if (testProviderStats) {
    assert(testProviderStats.total_requests >= 5, `Total requests tracked (${testProviderStats.total_requests})`);
    assert(testProviderStats.current_window_count >= 0, `Current window count valid (${testProviderStats.current_window_count})`);
  }
  console.log('');

  // Test 8: Error Handling - Non-existent Provider
  console.log('[Test 8] Error Handling');

  const emptyCheck = await checkRateLimit('never-used-provider-' + Date.now());
  assertEquals(emptyCheck.allowed, true, 'Empty provider allows requests');
  assertEquals(emptyCheck.current_count, 0, 'Empty provider has zero requests');
  console.log('');

  // Test 9: Cleanup Operations
  console.log('[Test 9] Cleanup Operations');

  const deletedCount = await cleanupOldRequests();
  assert(deletedCount >= 0, `Cleanup executed (${deletedCount} records deleted)`);
  console.log('');

  // Test 10: Close Connection Pool
  console.log('[Test 10] Connection Pool Lifecycle');

  try {
    await close();
    assert(true, 'Connection pool closed successfully');
  } catch (err) {
    assert(false, `Failed to close pool: ${err.message}`);
  }
  console.log('');

  // ========================================================================
  // TEST SUMMARY
  // ========================================================================
  console.log('='.repeat(70));
  console.log('Test Summary');
  console.log('='.repeat(70));
  console.log(`Total tests: ${testsPassed + testsFailed}`);
  console.log(`Passed: ${testsPassed} ✓`);
  console.log(`Failed: ${testsFailed} ✗`);
  console.log('');

  if (testsFailed === 0) {
    console.log('🎉 All tests passed!');
    process.exit(0);
  } else {
    console.error(`❌ ${testsFailed} test(s) failed`);
    process.exit(1);
  }
}

// ============================================================================
// RUN TESTS
// ============================================================================

runTests().catch(err => {
  console.error('Fatal error running tests:', err);
  process.exit(1);
});
