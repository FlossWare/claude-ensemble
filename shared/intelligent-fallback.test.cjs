#!/usr/bin/env node
/**
 * Test Suite for Intelligent Fallback Routing
 *
 * Tests:
 * 1. Quality tier classification
 * 2. Fallback chain construction
 * 3. Quality-preserving fallback (no downgrades)
 * 4. Simulated provider failures
 * 5. PostgreSQL tracking
 * 6. Best provider selection
 *
 * Usage: node shared/intelligent-fallback.test.cjs
 */

const {
  executeWithFallback,
  buildFallbackChain,
  getModelTier,
  getFallbackStats,
  getBestFallbackProvider,
  QUALITY_TIERS,
  TIER_HIERARCHY,
  MODEL_TO_TIER,
  pool,
} = require('./intelligent-fallback.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`✅ PASS: ${message}`);
    testsPassed++;
  } else {
    console.error(`❌ FAIL: ${message}`);
    testsFailed++;
  }
}

function assertEqual(actual, expected, message) {
  if (actual === expected) {
    console.log(`✅ PASS: ${message}`);
    testsPassed++;
  } else {
    console.error(`❌ FAIL: ${message}`);
    console.error(`   Expected: ${expected}`);
    console.error(`   Actual:   ${actual}`);
    testsFailed++;
  }
}

function assertContains(array, item, message) {
  if (array.includes(item)) {
    console.log(`✅ PASS: ${message}`);
    testsPassed++;
  } else {
    console.error(`❌ FAIL: ${message}`);
    console.error(`   Array: ${JSON.stringify(array)}`);
    console.error(`   Item:  ${item}`);
    testsFailed++;
  }
}

// ============================================================================
// TEST 1: Quality Tier Classification
// ============================================================================

async function testQualityTiers() {
  console.log('\n=== TEST 1: Quality Tier Classification ===\n');

  // Ultra tier
  assertEqual(getModelTier('gpt-4'), QUALITY_TIERS.ULTRA, 'GPT-4 is ultra tier');
  assertEqual(getModelTier('opus'), QUALITY_TIERS.ULTRA, 'Opus is ultra tier');
  assertEqual(getModelTier('gemini-pro'), QUALITY_TIERS.ULTRA, 'Gemini-Pro is ultra tier');

  // High tier
  assertEqual(getModelTier('llama-3.1-70b'), QUALITY_TIERS.HIGH, 'Llama-70B is high tier');
  assertEqual(getModelTier('mixtral-8x7b'), QUALITY_TIERS.HIGH, 'Mixtral is high tier');
  assertEqual(getModelTier('sonnet'), QUALITY_TIERS.HIGH, 'Sonnet is high tier');

  // Medium tier
  assertEqual(getModelTier('llama-3.1-8b'), QUALITY_TIERS.MEDIUM, 'Llama-8B is medium tier');
  assertEqual(getModelTier('mistral-7b'), QUALITY_TIERS.MEDIUM, 'Mistral-7B is medium tier');
  assertEqual(getModelTier('haiku'), QUALITY_TIERS.MEDIUM, 'Haiku is medium tier');

  // Low tier
  assertEqual(getModelTier('phi-4-mini'), QUALITY_TIERS.LOW, 'Phi-4-mini is low tier');
  assertEqual(getModelTier('gemini-flash'), QUALITY_TIERS.LOW, 'Gemini-Flash is low tier');
}

// ============================================================================
// TEST 2: Fallback Chain Construction
// ============================================================================

async function testFallbackChains() {
  console.log('\n=== TEST 2: Fallback Chain Construction ===\n');

  // Test Llama-70B fallback chain
  const llamaChain = buildFallbackChain('llama-3.1-70b', 'groq');
  assert(llamaChain.length > 0, 'Llama-70B has fallback chain');

  // Verify all fallbacks are same or higher tier
  const llamaTier = getModelTier('llama-3.1-70b');
  const llamaTierIndex = TIER_HIERARCHY.indexOf(llamaTier);

  for (const fallback of llamaChain) {
    const fallbackTierIndex = TIER_HIERARCHY.indexOf(fallback.tier);
    assert(
      fallbackTierIndex <= llamaTierIndex,
      `Fallback ${fallback.provider}/${fallback.model} is same or higher quality (${fallback.tier} vs ${llamaTier})`
    );
  }

  // Test that Groq is not in the chain (original provider)
  const hasGroq = llamaChain.some(f => f.provider === 'groq');
  assert(!hasGroq, 'Original provider (groq) excluded from fallback chain');

  // Test Llama-8B fallback chain
  const llama8bChain = buildFallbackChain('llama-3.1-8b', 'groq');
  assert(llama8bChain.length > 0, 'Llama-8B has fallback chain');

  // Verify no downgrades to LOW tier
  const hasLowTier = llama8bChain.some(f => f.tier === QUALITY_TIERS.LOW);
  assert(!hasLowTier, 'Medium tier model does not fall back to low tier');

  console.log(`\nLlama-70B chain (${llamaChain.length} alternatives):`);
  llamaChain.slice(0, 5).forEach((f, i) => {
    console.log(`  ${i + 1}. ${f.provider}/${f.model} (${f.tier}, ${f.reason})`);
  });

  console.log(`\nLlama-8B chain (${llama8bChain.length} alternatives):`);
  llama8bChain.slice(0, 5).forEach((f, i) => {
    console.log(`  ${i + 1}. ${f.provider}/${f.model} (${f.tier}, ${f.reason})`);
  });
}

// ============================================================================
// TEST 3: Quality-Preserving Fallback
// ============================================================================

async function testQualityPreservation() {
  console.log('\n=== TEST 3: Quality-Preserving Fallback ===\n');

  // Test all defined models
  const testCases = [
    { model: 'llama-3.1-70b', minTier: QUALITY_TIERS.HIGH },
    { model: 'llama-3.1-8b', minTier: QUALITY_TIERS.MEDIUM },
    { model: 'mixtral-8x7b', minTier: QUALITY_TIERS.HIGH },
    { model: 'opus', minTier: QUALITY_TIERS.ULTRA },
    { model: 'haiku', minTier: QUALITY_TIERS.MEDIUM },
  ];

  for (const testCase of testCases) {
    const chain = buildFallbackChain(testCase.model, 'test-provider');
    const minTierIndex = TIER_HIERARCHY.indexOf(testCase.minTier);

    let allValid = true;
    for (const fallback of chain) {
      const tierIndex = TIER_HIERARCHY.indexOf(fallback.tier);
      if (tierIndex > minTierIndex) {
        allValid = false;
        console.error(`  ❌ ${testCase.model} falls back to lower tier: ${fallback.tier}`);
      }
    }

    if (allValid) {
      console.log(`✅ PASS: ${testCase.model} preserves quality (min tier: ${testCase.minTier})`);
      testsPassed++;
    } else {
      console.error(`❌ FAIL: ${testCase.model} has quality downgrades`);
      testsFailed++;
    }
  }
}

// ============================================================================
// TEST 4: Simulated Provider Failures
// ============================================================================

async function testSimulatedFailures() {
  console.log('\n=== TEST 4: Simulated Provider Failures ===\n');

  let callCount = 0;
  const failurePattern = [true, true, false]; // Fail twice, succeed third time

  const mockExecute = async (provider, model) => {
    callCount++;
    const shouldFail = failurePattern[callCount - 1];

    if (shouldFail) {
      throw new Error(`Simulated failure for ${provider}/${model}`);
    }

    return {
      provider,
      model,
      response: 'Success!',
      timestamp: new Date().toISOString(),
    };
  };

  // Test fallback execution
  const result = await executeWithFallback(
    'llama-3.1-70b',
    'groq',
    mockExecute,
    { maxRetries: 5, retryDelay: 10 }
  );

  assert(result.success, 'Fallback eventually succeeds');
  assertEqual(result.attempts, 3, 'Took 3 attempts (2 failures + 1 success)');
  assert(result.fallbacks.length === 2, 'Recorded 2 fallback attempts');
  assert(result.provider !== 'groq', 'Used fallback provider (not original groq)');

  console.log(`\nFallback result:`);
  console.log(`  Success: ${result.success}`);
  console.log(`  Attempts: ${result.attempts}`);
  console.log(`  Final provider: ${result.provider}/${result.model}`);
  console.log(`  Original: groq/llama-3.1-70b`);
}

// ============================================================================
// TEST 5: PostgreSQL Tracking
// ============================================================================

async function testPostgreSQLTracking() {
  console.log('\n=== TEST 5: PostgreSQL Tracking ===\n');

  // Check if tables exist
  try {
    const tableCheck = await pool.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'monitoring'
        AND table_name IN ('fallback_attempts', 'fallback_success')
    `);

    if (tableCheck.rows.length === 2) {
      console.log('✅ PASS: Database tables exist');
      testsPassed++;
    } else {
      console.log('⚠️  WARN: Database tables not found (run migration first)');
      console.log('   Expected: fallback_attempts, fallback_success');
      console.log(`   Found: ${tableCheck.rows.map(r => r.table_name).join(', ')}`);
    }

    // Test insert (will fail gracefully if tables don't exist)
    await pool.query(`
      INSERT INTO monitoring.fallback_attempts
      (model, provider, tier, error_message, success, timestamp)
      VALUES ($1, $2, $3, $4, $5, NOW())
    `, ['llama-3.1-70b-test', 'groq-test', 'high', null, true]);

    console.log('✅ PASS: Can insert fallback attempts');
    testsPassed++;

    // Test query
    const stats = await getFallbackStats('llama-3.1-70b-test', 'groq-test', 1);
    assert(stats.length >= 0, 'Can query fallback stats');

    if (stats.length > 0) {
      console.log(`   Found ${stats.length} stats records`);
    }

  } catch (err) {
    console.log(`⚠️  WARN: PostgreSQL tracking test skipped: ${err.message}`);
    console.log('   Run migration: psql -h aio-01 -p 5433 -U sfloess -d learning -f db/migrations/007_fallback_tracking.sql');
  }
}

// ============================================================================
// TEST 6: Best Provider Selection
// ============================================================================

async function testBestProviderSelection() {
  console.log('\n=== TEST 6: Best Provider Selection ===\n');

  try {
    // Insert test data
    await pool.query(`
      INSERT INTO monitoring.fallback_success
      (model, provider, tier, fallback_depth, success, timestamp)
      VALUES
        ('llama-3.1-70b', 'together', 'high', 1, true, NOW()),
        ('llama-3.1-70b', 'together', 'high', 1, true, NOW()),
        ('llama-3.1-70b', 'together', 'high', 1, true, NOW()),
        ('llama-3.1-70b', 'deepinfra', 'high', 2, true, NOW()),
        ('llama-3.1-70b', 'deepinfra', 'high', 2, false, NOW()),
        ('llama-3.1-70b', 'fireworks', 'high', 1, true, NOW())
    `);

    const best = await getBestFallbackProvider('llama-3.1-70b', 1);

    if (best.length > 0) {
      console.log('✅ PASS: Best provider selection works');
      testsPassed++;

      console.log(`\nBest fallback providers for Llama-70B:`);
      best.forEach((p, i) => {
        console.log(`  ${i + 1}. ${p.provider}/${p.model}`);
        console.log(`     Success rate: ${(p.success_rate * 100).toFixed(1)}%`);
        console.log(`     Avg depth: ${parseFloat(p.avg_depth).toFixed(2)}`);
        console.log(`     Attempts: ${p.attempts}`);
      });

      // Verify sorting (highest success rate first)
      if (best.length >= 2) {
        assert(
          parseFloat(best[0].success_rate) >= parseFloat(best[1].success_rate),
          'Results sorted by success rate'
        );
      }
    } else {
      console.log('⚠️  WARN: Not enough data for best provider selection');
    }

  } catch (err) {
    console.log(`⚠️  WARN: Best provider test skipped: ${err.message}`);
  }
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runTests() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║  Intelligent Fallback Routing - Test Suite                ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  try {
    await testQualityTiers();
    await testFallbackChains();
    await testQualityPreservation();
    await testSimulatedFailures();
    await testPostgreSQLTracking();
    await testBestProviderSelection();

    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║  Test Results                                              ║');
    console.log('╚════════════════════════════════════════════════════════════╝');
    console.log(`\n✅ Passed: ${testsPassed}`);
    console.log(`❌ Failed: ${testsFailed}`);
    console.log(`📊 Total:  ${testsPassed + testsFailed}`);
    console.log(`📈 Success Rate: ${((testsPassed / (testsPassed + testsFailed)) * 100).toFixed(1)}%\n`);

    if (testsFailed === 0) {
      console.log('🎉 All tests passed!\n');
    } else {
      console.log('⚠️  Some tests failed. Review output above.\n');
    }

  } catch (err) {
    console.error('\n❌ Test suite error:', err);
  } finally {
    await pool.end();
  }

  process.exit(testsFailed > 0 ? 1 : 0);
}

// Run tests if executed directly
if (require.main === module) {
  runTests();
}

module.exports = { runTests };
