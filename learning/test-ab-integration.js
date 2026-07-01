#!/usr/bin/env node

/**
 * Test A/B Test Integration
 *
 * Demonstrates the wired ab-runner integration with the learning system.
 *
 * Usage:
 *   node test-ab-integration.js [--type TYPE]
 *
 * Types: simple, multi-variant, summary
 *
 * Created: 2026-07-01
 * Issue: #262
 */

const {
  runABTestFromPlan,
  runFeatureComparisonTest,
  runMultiVariantTest,
  generateABTestSummary,
} = require('./ab-test-integration.js');

// ============================================================================
// TEST 1: SIMPLE A/B TEST
// ============================================================================

async function testSimpleABTest() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 1: Simple A/B Test (Baseline vs Thompson Sampling)');
  console.log('='.repeat(80));

  const handler = async (iteration, features) => {
    // Simulate execution
    const baseQuality = 0.70;
    const thompsonBonus = features.includes('thompson_sampling') ? 0.12 : 0;
    const quality = baseQuality + thompsonBonus + (Math.random() * 0.05 - 0.025);

    const baseLatency = 1000;
    const thompsonLatency = features.includes('thompson_sampling') ? 150 : 0;
    const latency_ms = baseLatency + thompsonLatency + (Math.random() * 100 - 50);

    const baseCost = 0.01;
    const thompsonCost = features.includes('thompson_sampling') ? 0.003 : 0;
    const cost_usd = baseCost + thompsonCost + (Math.random() * 0.002 - 0.001);

    return {
      quality: Math.max(0, Math.min(1, quality)),
      latency_ms: Math.max(100, latency_ms),
      cost_usd: Math.max(0, cost_usd),
    };
  };

  const result = await runABTestFromPlan({
    opportunity: 'Thompson Sampling vs Random routing',
    type: 'routing_strategy',
    variants: [
      { name: 'baseline', features: [] },
      { name: 'thompson', features: ['thompson_sampling'] },
    ],
    handler,
  }, { samples: 30 });

  console.log('\n--- RESULTS ---');
  console.log(`Winner: ${result.winner}`);
  console.log(`Winner Score: ${result.statistics.winner_score.toFixed(4)}`);
  console.log('\nVariant Summaries:');
  for (const [name, stats] of Object.entries(result.statistics.summaries)) {
    console.log(`\n${name}:`);
    console.log(`  Quality:    ${stats.quality.mean.toFixed(4)} ± ${stats.quality.stddev.toFixed(4)}`);
    console.log(`  Latency:    ${stats.latency_ms.mean.toFixed(1)}ms ± ${stats.latency_ms.stddev.toFixed(1)}ms`);
    console.log(`  Cost:       $${stats.cost_usd.mean.toFixed(5)} ± $${stats.cost_usd.stddev.toFixed(5)}`);
    console.log(`  Tradeoff:   ${stats.tradeoff_score.score.toFixed(4)}`);
  }

  console.log('\nPairwise Comparisons:');
  for (const [pair, comp] of Object.entries(result.statistics.pairwise)) {
    console.log(`\n${pair}:`);
    console.log(`  Quality p-value: ${comp.quality.t_test.p_value.toFixed(4)}`);
    console.log(`  Significant:     ${comp.quality.t_test.significant ? 'YES' : 'no'}`);
    console.log(`  Effect size:     ${comp.quality.effect_size.d.toFixed(3)} (${comp.quality.effect_size.magnitude})`);
  }

  console.log(`\nStored in PostgreSQL: ${result.stored ? 'YES' : 'NO'}`);

  return result;
}

// ============================================================================
// TEST 2: FEATURE COMPARISON TEST
// ============================================================================

async function testFeatureComparison() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 2: Feature Comparison Test');
  console.log('='.repeat(80));

  const handler = async (iteration, features) => {
    const baseQuality = 0.68;
    const qualityBonus = features.reduce((sum, f) => {
      if (f === 'thompson_sampling') return sum + 0.10;
      if (f === 'consensus') return sum + 0.08;
      if (f === 'caching') return sum + 0.02;
      return sum;
    }, 0);

    const baseLatency = 1200;
    const latencyChange = features.reduce((sum, f) => {
      if (f === 'consensus') return sum + 300;
      if (f === 'caching') return sum - 200;
      return sum;
    }, 0);

    const baseCost = 0.015;
    const costChange = features.reduce((sum, f) => {
      if (f === 'consensus') return sum + 0.02;
      if (f === 'caching') return sum - 0.005;
      return sum;
    }, 0);

    return {
      quality: Math.max(0, Math.min(1, baseQuality + qualityBonus + (Math.random() * 0.04 - 0.02))),
      latency_ms: Math.max(200, baseLatency + latencyChange + (Math.random() * 150 - 75)),
      cost_usd: Math.max(0.001, baseCost + costChange + (Math.random() * 0.003 - 0.0015)),
    };
  };

  const result = await runFeatureComparisonTest(
    [],  // baseline: no features
    ['thompson_sampling', 'consensus', 'caching'],  // treatment: all features
    handler,
    25
  );

  console.log('\n--- RESULTS ---');
  console.log(`Winner: ${result.winner}`);
  console.log(`Baseline mean quality: ${result.statistics.summaries.baseline.quality.mean.toFixed(4)}`);
  console.log(`Treatment mean quality: ${result.statistics.summaries.treatment.quality.mean.toFixed(4)}`);
  console.log(`Improvement: ${((result.statistics.summaries.treatment.quality.mean - result.statistics.summaries.baseline.quality.mean) * 100).toFixed(2)}%`);

  return result;
}

// ============================================================================
// TEST 3: MULTI-VARIANT TEST
// ============================================================================

async function testMultiVariant() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 3: Multi-Variant Test (A/B/C/D)');
  console.log('='.repeat(80));

  const handler = async (iteration, features) => {
    const strategies = {
      random: { quality: 0.65, latency: 800, cost: 0.008 },
      round_robin: { quality: 0.68, latency: 850, cost: 0.009 },
      thompson: { quality: 0.78, latency: 1100, cost: 0.012 },
      quality_first: { quality: 0.82, latency: 1400, cost: 0.018 },
    };

    let strategy = 'random';
    if (features.includes('round_robin')) strategy = 'round_robin';
    if (features.includes('thompson_sampling')) strategy = 'thompson';
    if (features.includes('quality_first_routing')) strategy = 'quality_first';

    const base = strategies[strategy];

    return {
      quality: Math.max(0, Math.min(1, base.quality + (Math.random() * 0.06 - 0.03))),
      latency_ms: Math.max(200, base.latency + (Math.random() * 100 - 50)),
      cost_usd: Math.max(0.001, base.cost + (Math.random() * 0.002 - 0.001)),
    };
  };

  const result = await runMultiVariantTest('routing_strategies', [
    { name: 'random', features: [] },
    { name: 'round_robin', features: ['round_robin'] },
    { name: 'thompson', features: ['thompson_sampling'] },
    { name: 'quality_first', features: ['quality_first_routing'] },
  ], handler, { samples: 20 });

  console.log('\n--- RESULTS ---');
  console.log(`Winner: ${result.winner}`);
  console.log(`Winner Score: ${result.statistics.winner_score.toFixed(4)}`);

  console.log('\nAll Variants:');
  const sortedVariants = Object.entries(result.statistics.summaries)
    .sort((a, b) => b[1].tradeoff_score.score - a[1].tradeoff_score.score);

  for (const [name, stats] of sortedVariants) {
    const isWinner = name === result.winner;
    console.log(`\n${isWinner ? '🏆 ' : '   '}${name}:`);
    console.log(`     Quality:  ${stats.quality.mean.toFixed(4)}`);
    console.log(`     Latency:  ${stats.latency_ms.mean.toFixed(0)}ms`);
    console.log(`     Cost:     $${stats.cost_usd.mean.toFixed(5)}`);
    console.log(`     Score:    ${stats.tradeoff_score.score.toFixed(4)}`);
  }

  return result;
}

// ============================================================================
// TEST 4: SUMMARY
// ============================================================================

async function testSummary() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 4: A/B Test Summary');
  console.log('='.repeat(80));

  const summary = await generateABTestSummary(100);

  console.log(`\nTotal A/B tests: ${summary.total_tests}`);
  console.log(`Success rate: ${(summary.success_rate * 100).toFixed(1)}%`);
  console.log(`Average improvement: ${summary.avg_improvement_pct.toFixed(2)}%`);
  console.log(`Significant tests: ${summary.significant_tests} / ${summary.total_tests} (${(summary.significance_rate * 100).toFixed(1)}%)`);

  console.log('\nBy Verdict:');
  console.log(`  Keep:         ${summary.by_verdict.keep}`);
  console.log(`  Remove:       ${summary.by_verdict.remove}`);
  console.log(`  Inconclusive: ${summary.by_verdict.inconclusive}`);

  if (summary.recent_winners.length > 0) {
    console.log('\nRecent Winners:');
    summary.recent_winners.forEach((win, idx) => {
      console.log(`\n${idx + 1}. ${win.name}`);
      console.log(`   Hypothesis: ${win.hypothesis}`);
      console.log(`   Improvement: ${win.improvement_pct?.toFixed(2)}%`);
      console.log(`   p-value: ${win.p_value?.toFixed(4)}`);
      console.log(`   Effect size: ${win.effect_size?.toFixed(3)}`);
    });
  }

  return summary;
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  const typeFlag = args.indexOf('--type');
  const type = typeFlag >= 0 ? args[typeFlag + 1] : 'simple';

  console.log('\n🧪 A/B TEST INTEGRATION - WIRED AND ACTIVE');

  try {
    switch (type) {
      case 'simple':
        await testSimpleABTest();
        break;
      case 'features':
        await testFeatureComparison();
        break;
      case 'multi':
        await testMultiVariant();
        break;
      case 'summary':
        await testSummary();
        break;
      case 'all':
        await testSimpleABTest();
        await testFeatureComparison();
        await testMultiVariant();
        await testSummary();
        break;
      default:
        console.error(`\nUnknown type: ${type}`);
        console.log('Valid types: simple, features, multi, summary, all');
        process.exit(1);
    }

    console.log('\n✅ Test completed successfully\n');
    process.exit(0);

  } catch (error) {
    console.error('\n❌ Error running test:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  testSimpleABTest,
  testFeatureComparison,
  testMultiVariant,
  testSummary,
};
