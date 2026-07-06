#!/usr/bin/env node
/**
 * Fallback Chain Simulation Test
 *
 * Tests complete fallback chain with simulated failures:
 * 1. Groq rate limited → falls back to Gemini
 * 2. Gemini timeout → falls back to Cerebras
 * 3. Cerebras down → falls back to DeepInfra
 * 4. DeepInfra works → success
 *
 * Also verifies all 5 providers can be reached independently.
 *
 * Usage: node test-fallback-chain-simulation.mjs
 */

import { executeWithFallback, buildFallbackChain, getModelTier } from './shared/intelligent-fallback.cjs';

// ============================================================================
// MOCK PROVIDER RESPONSES
// ============================================================================

/**
 * Simulated provider states for testing fallback chain
 */
const PROVIDER_STATES = {
  groq: { available: false, error: 'Rate limit exceeded (429)' },
  gemini: { available: false, error: 'Request timeout (504)' },
  cerebras: { available: false, error: 'Service unavailable (503)' },
  deepinfra: { available: true, error: null },
  together: { available: true, error: null },
};

/**
 * Mock execution function that simulates provider behavior
 */
async function mockProviderCall(provider, model) {
  const state = PROVIDER_STATES[provider];

  if (!state) {
    // Unknown provider - simulate as available
    console.log(`  ℹ️  Provider ${provider} not in mock state, treating as available`);
    return {
      provider,
      model,
      response: `Mock response from ${provider}/${model}`,
      timestamp: new Date().toISOString(),
    };
  }

  if (!state.available) {
    throw new Error(state.error);
  }

  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 100));

  return {
    provider,
    model,
    response: `Mock response from ${provider}/${model}`,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Direct provider health check (bypasses fallback logic)
 */
async function checkProviderHealth(provider, model) {
  try {
    const result = await mockProviderCall(provider, model);
    return {
      provider,
      model,
      reachable: true,
      response: result.response,
      timestamp: result.timestamp,
    };
  } catch (error) {
    return {
      provider,
      model,
      reachable: false,
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// ============================================================================
// TEST SCENARIOS
// ============================================================================

/**
 * Test 1: Simulated fallback chain with multiple failures
 */
async function testFallbackChain() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  TEST 1: Simulated Fallback Chain                         ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  console.log('Scenario:');
  console.log('  1. Groq rate limited (429) → fallback');
  console.log('  2. Gemini timeout (504) → fallback');
  console.log('  3. Cerebras unavailable (503) → fallback');
  console.log('  4. DeepInfra available → SUCCESS\n');

  const startModel = 'llama-3.1-70b';
  const startProvider = 'groq';

  console.log(`Starting with: ${startProvider}/${startModel}\n`);

  const result = await executeWithFallback(
    startModel,
    startProvider,
    mockProviderCall,
    { maxRetries: 10, retryDelay: 50 }
  );

  console.log('\n─────────────────────────────────────────────────────────────');
  console.log('RESULTS:');
  console.log('─────────────────────────────────────────────────────────────\n');

  console.log(`✅ Success: ${result.success}`);
  console.log(`📊 Total Attempts: ${result.attempts}`);
  console.log(`🔄 Fallbacks: ${result.fallbacks.length}`);

  if (result.success) {
    console.log(`\n🎯 Final Provider: ${result.provider}/${result.model}`);
    console.log(`📈 Quality Tier: ${result.tier}`);

    if (result.originalProvider) {
      console.log(`\n⚠️  Fallback occurred:`);
      console.log(`   Original: ${result.originalProvider}/${result.originalModel}`);
      console.log(`   Final:    ${result.provider}/${result.model}`);
    }
  } else {
    console.log(`\n❌ All providers failed`);
    console.log(`   Last error: ${result.error?.message || 'Unknown error'}`);
  }

  console.log('\n📋 Fallback History:');
  result.fallbacks.forEach((fb, i) => {
    const status = fb.success ? '✅' : '❌';
    console.log(`   ${i + 1}. ${status} ${fb.to.provider}/${fb.to.model} (${fb.reason})`);
    if (!fb.success) {
      console.log(`      Error: ${fb.error}`);
    }
  });

  return result;
}

/**
 * Test 2: Verify all providers are reachable independently
 */
async function testProviderReachability() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  TEST 2: Provider Reachability Check                      ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const providers = [
    { provider: 'groq', model: 'llama-3.1-70b-versatile' },
    { provider: 'gemini', model: 'gemini-1.5-flash' },
    { provider: 'cerebras', model: 'llama-3.1-70b' },
    { provider: 'deepinfra', model: 'meta-llama/Meta-Llama-3.1-70B-Instruct' },
    { provider: 'together', model: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo' },
  ];

  console.log('Testing 5 providers:\n');

  const results = [];

  for (const { provider, model } of providers) {
    console.log(`Testing ${provider}...`);
    const result = await checkProviderHealth(provider, model);
    results.push(result);

    const status = result.reachable ? '✅ REACHABLE' : '❌ UNREACHABLE';
    console.log(`  ${status} - ${provider}/${model}`);

    if (!result.reachable) {
      console.log(`  Error: ${result.error}`);
    }
    console.log();
  }

  const reachableCount = results.filter(r => r.reachable).length;
  const totalCount = results.length;

  console.log('─────────────────────────────────────────────────────────────');
  console.log('SUMMARY:');
  console.log('─────────────────────────────────────────────────────────────\n');

  console.log(`Reachable: ${reachableCount}/${totalCount} providers`);
  console.log(`Success Rate: ${((reachableCount / totalCount) * 100).toFixed(1)}%\n`);

  results.forEach(r => {
    const icon = r.reachable ? '✅' : '❌';
    console.log(`${icon} ${r.provider.padEnd(12)} - ${r.reachable ? 'OK' : r.error}`);
  });

  return {
    all_reachable: reachableCount === totalCount,
    providers_tested: totalCount,
    providers_reachable: reachableCount,
    results,
  };
}

/**
 * Test 3: Inspect fallback chain structure
 */
async function testFallbackChainStructure() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  TEST 3: Fallback Chain Structure                         ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const testCases = [
    { model: 'llama-3.1-70b', provider: 'groq', description: 'Llama-70B (High Tier)' },
    { model: 'llama-3.1-8b', provider: 'groq', description: 'Llama-8B (Medium Tier)' },
    { model: 'opus', provider: 'anthropic', description: 'Claude Opus (Ultra Tier)' },
  ];

  for (const { model, provider, description } of testCases) {
    console.log(`\n${description}`);
    console.log(`Original: ${provider}/${model}`);
    console.log(`Tier: ${getModelTier(model)}\n`);

    const chain = buildFallbackChain(model, provider);

    if (chain.length === 0) {
      console.log('  ⚠️  No fallback options available');
    } else {
      console.log(`Fallback chain (${chain.length} options):`);
      chain.slice(0, 5).forEach((fb, i) => {
        console.log(`  ${i + 1}. ${fb.provider}/${fb.model}`);
        console.log(`     Tier: ${fb.tier}, Reason: ${fb.reason}`);
      });

      if (chain.length > 5) {
        console.log(`  ... and ${chain.length - 5} more options`);
      }
    }
  }
}

/**
 * Test 4: Quality tier preservation
 */
async function testQualityTierPreservation() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  TEST 4: Quality Tier Preservation                        ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const testModel = 'llama-3.1-70b';
  const testProvider = 'groq';
  const tier = getModelTier(testModel);

  console.log(`Testing: ${testProvider}/${testModel}`);
  console.log(`Quality Tier: ${tier}\n`);

  const chain = buildFallbackChain(testModel, testProvider);

  console.log('Verifying no quality downgrades...\n');

  let allPreserved = true;
  const tierOrder = ['ultra', 'high', 'medium', 'low'];
  const originalTierIndex = tierOrder.indexOf(tier);

  for (const fb of chain) {
    const fbTierIndex = tierOrder.indexOf(fb.tier);
    const preserved = fbTierIndex <= originalTierIndex;

    const icon = preserved ? '✅' : '❌';
    console.log(`${icon} ${fb.provider}/${fb.model}`);
    console.log(`   Tier: ${fb.tier} (${preserved ? 'same or better' : 'DOWNGRADE'})`);

    if (!preserved) {
      allPreserved = false;
    }
  }

  console.log('\n─────────────────────────────────────────────────────────────');

  if (allPreserved) {
    console.log('✅ All fallbacks preserve quality tier');
  } else {
    console.log('❌ Quality downgrades detected in fallback chain');
  }

  return allPreserved;
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║  Fallback Chain Simulation Test Suite                     ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  const startTime = Date.now();

  try {
    // Test 1: Simulated fallback chain
    const fallbackResult = await testFallbackChain();

    // Test 2: Provider reachability
    const reachabilityResult = await testProviderReachability();

    // Test 3: Fallback chain structure
    await testFallbackChainStructure();

    // Test 4: Quality tier preservation
    const qualityPreserved = await testQualityTierPreservation();

    // Final summary
    const duration = Date.now() - startTime;

    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║  FINAL SUMMARY                                             ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

    console.log('✅ Test Results:');
    console.log(`   Fallback chain: ${fallbackResult.success ? 'PASS' : 'FAIL'}`);
    console.log(`   Provider reachability: ${reachabilityResult.providers_reachable}/${reachabilityResult.providers_tested} reachable`);
    console.log(`   Quality preservation: ${qualityPreserved ? 'PASS' : 'FAIL'}`);
    console.log(`\n⏱️  Duration: ${duration}ms\n`);

    // Return structured results
    return {
      all_reachable: reachabilityResult.all_reachable,
      providers_tested: reachabilityResult.providers_tested,
      fallback_success: fallbackResult.success,
      quality_preserved: qualityPreserved,
      duration_ms: duration,
    };

  } catch (error) {
    console.error('\n❌ Test suite error:', error);
    throw error;
  }
}

// ============================================================================
// MAIN
// ============================================================================

if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests()
    .then(results => {
      console.log('\n📊 Structured Results (JSON):');
      console.log(JSON.stringify(results, null, 2));
      process.exit(0);
    })
    .catch(error => {
      console.error('\n❌ Fatal error:', error);
      process.exit(1);
    });
}

export { runAllTests, testFallbackChain, testProviderReachability };
