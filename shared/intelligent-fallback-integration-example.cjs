#!/usr/bin/env node
/**
 * Integration Example: Intelligent Fallback with Weighted Voting
 *
 * Demonstrates how to integrate intelligent-fallback.cjs with existing
 * weighted-voting.cjs and circuit-breaker.cjs systems.
 *
 * Usage: node shared/intelligent-fallback-integration-example.cjs
 */

const {
  executeWithFallback,
  buildFallbackChain,
  getModelTier,
  getFallbackStats,
  getBestFallbackProvider,
  QUALITY_TIERS,
} = require('./intelligent-fallback.cjs');

// Mock API client (replace with real implementation)
class MockAPIClient {
  constructor() {
    this.failureRate = 0.3; // 30% failure rate for demo
  }

  async callModel(provider, model, prompt) {
    // Simulate random failures
    if (Math.random() < this.failureRate) {
      throw new Error(`Provider ${provider} is temporarily unavailable`);
    }

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 100));

    return {
      provider,
      model,
      response: `Response from ${provider}/${model} for: "${prompt}"`,
      confidence: 0.75 + Math.random() * 0.25,
      timestamp: new Date().toISOString(),
    };
  }
}

// ============================================================================
// INTEGRATION EXAMPLE 1: Basic Fallback
// ============================================================================

async function example1_basicFallback() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Example 1: Basic Fallback                                ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const client = new MockAPIClient();

  const result = await executeWithFallback(
    'llama-3.1-70b',
    'groq',
    async (provider, model) => {
      return await client.callModel(provider, model, 'Write a hello world in Python');
    },
    { maxRetries: 5, retryDelay: 100 }
  );

  if (result.success) {
    console.log('✅ Success!');
    console.log(`   Provider: ${result.provider}`);
    console.log(`   Model: ${result.model}`);
    console.log(`   Attempts: ${result.attempts}`);
    console.log(`   Fallbacks: ${result.fallbacks.length}`);
    if (result.originalProvider) {
      console.log(`   Original: ${result.originalProvider}/${result.originalModel}`);
    }
  } else {
    console.log('❌ All fallbacks exhausted');
    console.log(`   Attempts: ${result.attempts}`);
    console.log(`   Error: ${result.error.message}`);
  }
}

// ============================================================================
// INTEGRATION EXAMPLE 2: Multi-Model Consensus with Fallback
// ============================================================================

async function example2_consensusWithFallback() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Example 2: Multi-Model Consensus with Fallback           ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const client = new MockAPIClient();
  client.failureRate = 0.5; // Higher failure rate

  const workers = [
    { model: 'llama-3.1-70b', provider: 'groq' },
    { model: 'llama-3.1-70b', provider: 'together' },
    { model: 'mixtral-8x7b', provider: 'groq' },
  ];

  const prompt = 'Explain quantum computing in one sentence';
  const results = [];

  for (const worker of workers) {
    const result = await executeWithFallback(
      worker.model,
      worker.provider,
      async (provider, model) => {
        return await client.callModel(provider, model, prompt);
      },
      { maxRetries: 3, retryDelay: 50 }
    );

    if (result.success) {
      results.push({
        model: result.model,
        provider: result.provider,
        tier: result.tier,
        response: result.result.response,
        confidence: result.result.confidence,
        hadFallback: !!result.originalProvider,
      });
    }
  }

  console.log(`Collected ${results.length}/${workers.length} responses:\n`);
  results.forEach((r, i) => {
    console.log(`${i + 1}. ${r.provider}/${r.model} (${r.tier})`);
    console.log(`   Confidence: ${(r.confidence * 100).toFixed(1)}%`);
    console.log(`   Used fallback: ${r.hadFallback ? 'Yes' : 'No'}`);
  });

  // Weighted voting (simple average for demo)
  const avgConfidence = results.reduce((sum, r) => sum + r.confidence, 0) / results.length;
  console.log(`\nConsensus confidence: ${(avgConfidence * 100).toFixed(1)}%`);
}

// ============================================================================
// INTEGRATION EXAMPLE 3: Tier-Aware Task Routing
// ============================================================================

async function example3_tierAwareRouting() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Example 3: Tier-Aware Task Routing                       ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const tasks = [
    { type: 'critical', prompt: 'Security audit', requiredTier: QUALITY_TIERS.ULTRA },
    { type: 'standard', prompt: 'Code review', requiredTier: QUALITY_TIERS.HIGH },
    { type: 'simple', prompt: 'Format code', requiredTier: QUALITY_TIERS.MEDIUM },
  ];

  const modelsByTier = {
    [QUALITY_TIERS.ULTRA]: [{ model: 'gpt-4', provider: 'openai' }],
    [QUALITY_TIERS.HIGH]: [
      { model: 'llama-3.1-70b', provider: 'groq' },
      { model: 'sonnet', provider: 'anthropic' },
    ],
    [QUALITY_TIERS.MEDIUM]: [
      { model: 'llama-3.1-8b', provider: 'groq' },
      { model: 'haiku', provider: 'anthropic' },
    ],
  };

  const client = new MockAPIClient();
  client.failureRate = 0.4;

  for (const task of tasks) {
    console.log(`\nTask: ${task.type} (${task.requiredTier} tier)`);
    const options = modelsByTier[task.requiredTier];
    const chosen = options[Math.floor(Math.random() * options.length)];

    const result = await executeWithFallback(
      chosen.model,
      chosen.provider,
      async (provider, model) => {
        return await client.callModel(provider, model, task.prompt);
      },
      { maxRetries: 5, retryDelay: 50 }
    );

    if (result.success) {
      const tierMatches = result.tier === task.requiredTier;
      const tierUpgrade = !tierMatches;

      console.log(`  ✅ Completed with ${result.provider}/${result.model}`);
      console.log(`  Quality: ${result.tier} tier${tierUpgrade ? ' (UPGRADED)' : ''}`);
      console.log(`  Attempts: ${result.attempts}`);
    } else {
      console.log(`  ❌ Failed after ${result.attempts} attempts`);
    }
  }
}

// ============================================================================
// INTEGRATION EXAMPLE 4: Statistics and Monitoring
// ============================================================================

async function example4_statistics() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Example 4: Statistics and Monitoring                     ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  // Get fallback statistics
  const stats = await getFallbackStats(null, null, 24);

  if (stats.length > 0) {
    console.log('Fallback statistics (last 24 hours):\n');
    stats.forEach((s, i) => {
      console.log(`${i + 1}. ${s.provider}/${s.model} (${s.tier} tier)`);
      console.log(`   Attempts: ${s.total_attempts}`);
      console.log(`   Success rate: ${(parseFloat(s.success_rate) * 100).toFixed(1)}%`);
      console.log(`   Successes: ${s.successes}, Failures: ${s.failures}`);
    });
  } else {
    console.log('No fallback statistics available yet.');
    console.log('Run some workflows with fallback to generate data.');
  }

  // Get best providers by tier
  for (const tier of ['high', 'medium']) {
    const best = await getBestFallbackProvider(`test-${tier}`, 168);
    if (best.length > 0) {
      console.log(`\nBest ${tier} tier providers (last 7 days):`);
      best.slice(0, 3).forEach((p, i) => {
        console.log(`  ${i + 1}. ${p.provider}/${p.model}`);
        console.log(`     Success: ${(parseFloat(p.success_rate) * 100).toFixed(1)}%`);
        console.log(`     Avg depth: ${parseFloat(p.avg_depth).toFixed(2)}`);
      });
    }
  }
}

// ============================================================================
// INTEGRATION EXAMPLE 5: Fallback Chain Preview
// ============================================================================

async function example5_chainPreview() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Example 5: Fallback Chain Preview                        ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const testCases = [
    { model: 'llama-3.1-70b', provider: 'groq' },
    { model: 'llama-3.1-8b', provider: 'together' },
    { model: 'mixtral-8x7b', provider: 'groq' },
    { model: 'opus', provider: 'anthropic' },
  ];

  for (const tc of testCases) {
    const tier = getModelTier(tc.model);
    const chain = buildFallbackChain(tc.model, tc.provider);

    console.log(`\n${tc.provider}/${tc.model} (${tier} tier):`);
    console.log(`  Fallback chain (${chain.length} alternatives):`);

    chain.slice(0, 5).forEach((f, i) => {
      console.log(`    ${i + 1}. ${f.provider}/${f.model} (${f.reason})`);
    });

    if (chain.length > 5) {
      console.log(`    ... and ${chain.length - 5} more`);
    }
  }
}

// ============================================================================
// RUN ALL EXAMPLES
// ============================================================================

async function runExamples() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║  Intelligent Fallback - Integration Examples              ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  try {
    await example1_basicFallback();
    await example2_consensusWithFallback();
    await example3_tierAwareRouting();
    await example4_statistics();
    await example5_chainPreview();

    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║  Examples Complete                                         ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

  } catch (err) {
    console.error('\n❌ Example error:', err);
  } finally {
    const { pool } = require('./intelligent-fallback.cjs');
    await pool.end();
  }
}

// Run examples if executed directly
if (require.main === module) {
  runExamples();
}

module.exports = { runExamples };
