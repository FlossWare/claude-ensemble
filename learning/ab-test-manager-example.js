#!/usr/bin/env node

/**
 * A/B Test Manager - Complete Example
 *
 * Demonstrates full A/B testing workflow:
 * 1. Plan test
 * 2. Execute with early stopping
 * 3. Analyze results (multi-metric + Bayesian)
 * 4. Deploy with gradual rollout
 * 5. Monitor and rollback if needed
 *
 * Example: Compare Thompson Sampling vs Random routing
 */

const { ABTestManager } = require('./ab-test-manager.js');
const { getStrategyPerformance } = require('./postgres-adapter.js');

// ============================================================================
// EXAMPLE 1: Simple Feature Comparison
// ============================================================================

async function example1_SimpleComparison() {
  console.log('\n════════════════════════════════════════════════════════════════');
  console.log('  EXAMPLE 1: Simple Feature Comparison');
  console.log('  Thompson Sampling vs Random Routing');
  console.log('════════════════════════════════════════════════════════════════\n');

  const manager = new ABTestManager();

  // Phase 1: Plan Test
  console.log('📋 Phase 1: Planning test...');
  const plan = await manager.planTest({
    name: 'thompson_vs_random_routing',
    hypothesis: 'Thompson Sampling improves routing quality by >5% with <10% cost increase',
    variants: [
      { name: 'random', features: [] },
      { name: 'thompson', features: ['thompson_sampling'] },
    ],
    metrics: ['quality', 'latency_ms', 'cost_usd'],
    success_criteria: {
      min_improvement_pct: 5,
      alpha: 0.05,
      min_samples: 30,
    },
  });

  console.log(`✅ Test planned: ${plan.name}\n`);

  // Phase 2: Execute Test
  console.log('🔬 Phase 2: Executing test with early stopping...');

  // Mock handler that simulates routing behavior
  const handler = async (iteration, features) => {
    // Simulate Thompson Sampling (better quality, slightly higher cost)
    if (features.includes('thompson_sampling')) {
      return {
        quality: 0.80 + Math.random() * 0.15,    // 0.80-0.95 quality
        latency_ms: 1200 + Math.random() * 300,  // 1200-1500ms
        cost_usd: 0.025 + Math.random() * 0.01,  // $0.025-$0.035
      };
    }

    // Random routing (lower quality, lower cost)
    return {
      quality: 0.70 + Math.random() * 0.15,    // 0.70-0.85 quality
      latency_ms: 1000 + Math.random() * 300,  // 1000-1300ms
      cost_usd: 0.020 + Math.random() * 0.01,  // $0.020-$0.030
    };
  };

  const result = await manager.executeTest('thompson_vs_random_routing', handler, {
    min_samples: 10,      // Start with 10 samples
    max_samples: 50,      // Max 50 samples
    alpha: 0.01,          // Early stop if p < 0.01
  });

  console.log(`✅ Test executed: winner = ${result.winner}\n`);

  // Phase 3: Analyze Results
  console.log('📊 Phase 3: Analyzing results...');
  const analysis = await manager.analyzeTest(result);

  console.log('\nComposite Scores:');
  for (const [variant, scores] of Object.entries(analysis.scores)) {
    console.log(`  ${variant}:`);
    console.log(`    Quality:    ${scores.quality.toFixed(3)}`);
    console.log(`    Latency:    ${scores.latency.toFixed(3)}`);
    console.log(`    Cost:       ${scores.cost.toFixed(3)}`);
    console.log(`    Composite:  ${scores.composite.toFixed(3)}`);
  }

  console.log('\nBayesian Posteriors:');
  for (const [variant, posterior] of Object.entries(analysis.posteriors)) {
    console.log(`  ${variant}:`);
    console.log(`    Mean:       ${posterior.mean.toFixed(3)}`);
    console.log(`    Variance:   ${posterior.variance.toFixed(5)}`);
    console.log(`    Samples:    ${posterior.samples}`);
  }

  console.log('\nInsights:');
  for (const insight of analysis.insights) {
    console.log(`  [${insight.type}] ${insight.message}`);
    if (insight.action) {
      console.log(`    → ${insight.action}`);
    }
  }

  console.log('\nRecommendation:');
  console.log(`  Action: ${analysis.recommendation.action}`);
  console.log(`  Reason: ${analysis.recommendation.reason}`);
  if (analysis.recommendation.plan) {
    console.log(`  Plan:   ${analysis.recommendation.plan}`);
  }

  // Phase 4: Deploy (if safe)
  if (analysis.recommendation.action === 'DEPLOY') {
    console.log('\n🚀 Phase 4: Deploying winner...');
    const deployment = await manager.deployWinner(
      'thompson_vs_random_routing',
      result.winner,
      {
        gradual: true,
        monitor_window_hours: 1,  // 1h monitoring (normally 24h)
      }
    );

    console.log(`✅ Gradual rollout started: ${result.winner}`);
    console.log(`   Traffic steps: ${deployment.steps.map(s => s.traffic_pct + '%').join(' → ')}`);
  } else if (analysis.recommendation.action === 'GRADUAL_ROLLOUT') {
    console.log('\n⚠️  Phase 4: Deploying with caution (gradual rollout)...');
    const deployment = await manager.deployWinner(
      'thompson_vs_random_routing',
      result.winner,
      {
        gradual: true,
        monitor_window_hours: 2,  // Extended monitoring
      }
    );

    console.log(`✅ Gradual rollout started with extended monitoring`);
  } else {
    console.log('\n❌ Phase 4: Deployment blocked due to high risks');
    for (const risk of analysis.risks) {
      console.log(`   [${risk.severity}] ${risk.description}`);
    }
  }

  console.log('\n════════════════════════════════════════════════════════════════\n');
}

// ============================================================================
// EXAMPLE 2: Multi-Variant Test (A/B/C/D)
// ============================================================================

async function example2_MultiVariant() {
  console.log('\n════════════════════════════════════════════════════════════════');
  console.log('  EXAMPLE 2: Multi-Variant Test');
  console.log('  Compare 4 routing strategies');
  console.log('════════════════════════════════════════════════════════════════\n');

  const manager = new ABTestManager();

  console.log('📋 Planning multi-variant test...');
  const plan = await manager.planTest({
    name: 'routing_strategies_multi',
    hypothesis: 'Find best routing strategy among 4 candidates',
    variants: [
      { name: 'random', features: [] },
      { name: 'round_robin', features: ['round_robin'] },
      { name: 'thompson', features: ['thompson_sampling'] },
      { name: 'quality_first', features: ['quality_first_routing'] },
    ],
    metrics: ['quality', 'latency_ms', 'cost_usd'],
  });

  console.log(`✅ Test planned: ${plan.name}\n`);

  console.log('🔬 Executing multi-variant test...');

  const handler = async (iteration, features) => {
    // Different strategies have different characteristics
    if (features.includes('quality_first_routing')) {
      return {
        quality: 0.85 + Math.random() * 0.10,    // Highest quality
        latency_ms: 1500 + Math.random() * 400,  // Slowest
        cost_usd: 0.035 + Math.random() * 0.015, // Most expensive
      };
    } else if (features.includes('thompson_sampling')) {
      return {
        quality: 0.80 + Math.random() * 0.15,    // Good quality
        latency_ms: 1200 + Math.random() * 300,  // Medium latency
        cost_usd: 0.025 + Math.random() * 0.01,  // Medium cost
      };
    } else if (features.includes('round_robin')) {
      return {
        quality: 0.75 + Math.random() * 0.15,    // Medium quality
        latency_ms: 1000 + Math.random() * 200,  // Fast
        cost_usd: 0.020 + Math.random() * 0.01,  // Cheap
      };
    } else {
      return {
        quality: 0.70 + Math.random() * 0.15,    // Lowest quality
        latency_ms: 900 + Math.random() * 200,   // Fastest
        cost_usd: 0.018 + Math.random() * 0.008, // Cheapest
      };
    }
  };

  const result = await manager.executeTest('routing_strategies_multi', handler, {
    min_samples: 15,
    max_samples: 30,
  });

  console.log(`✅ Test executed: winner = ${result.winner}\n`);

  const analysis = await manager.analyzeTest(result);

  console.log('Composite Scores (sorted by score):');
  const sortedScores = Object.entries(analysis.scores)
    .sort((a, b) => b[1].composite - a[1].composite);

  for (const [variant, scores] of sortedScores) {
    console.log(`  ${variant.padEnd(15)} ${scores.composite.toFixed(3)}`);
  }

  console.log('\nBayesian Posteriors (probability of being best):');
  const posteriors = analysis.posteriors;

  // Run 1000 Thompson Sampling trials to estimate probability
  const counts = {};
  for (const variant in posteriors) {
    counts[variant] = 0;
  }

  for (let i = 0; i < 1000; i++) {
    const selected = manager.thompsonSampling(posteriors);
    counts[selected]++;
  }

  for (const [variant, count] of Object.entries(counts).sort((a, b) => b[1] - a[1])) {
    const prob = count / 1000;
    console.log(`  ${variant.padEnd(15)} ${(prob * 100).toFixed(1)}%`);
  }

  console.log('\n════════════════════════════════════════════════════════════════\n');
}

// ============================================================================
// EXAMPLE 3: Rollback Scenario
// ============================================================================

async function example3_Rollback() {
  console.log('\n════════════════════════════════════════════════════════════════');
  console.log('  EXAMPLE 3: Rollback Scenario');
  console.log('  Simulate quality degradation');
  console.log('════════════════════════════════════════════════════════════════\n');

  const manager = new ABTestManager({
    rollback_quality_drop_pct: 10,  // Rollback if quality drops >10%
  });

  console.log('📋 Planning test with potential rollback...');
  const plan = await manager.planTest({
    name: 'rollback_test',
    hypothesis: 'New routing strategy improves performance',
    variants: [
      { name: 'baseline', features: [] },
      { name: 'experimental', features: ['experimental_routing'] },
    ],
    metrics: ['quality', 'latency_ms', 'cost_usd'],
  });

  console.log(`✅ Test planned: ${plan.name}\n`);

  console.log('🔬 Executing test...');

  const handler = async (iteration, features) => {
    if (features.includes('experimental_routing')) {
      // Experimental routing: faster and cheaper, but WORSE quality
      return {
        quality: 0.60 + Math.random() * 0.10,    // 0.60-0.70 (low!)
        latency_ms: 800 + Math.random() * 200,   // 800-1000ms (fast)
        cost_usd: 0.015 + Math.random() * 0.005, // $0.015-$0.020 (cheap)
      };
    } else {
      return {
        quality: 0.80 + Math.random() * 0.10,    // 0.80-0.90 (good)
        latency_ms: 1200 + Math.random() * 300,  // 1200-1500ms
        cost_usd: 0.025 + Math.random() * 0.01,  // $0.025-$0.035
      };
    }
  };

  const result = await manager.executeTest('rollback_test', handler, {
    min_samples: 20,
    max_samples: 20,
  });

  console.log(`✅ Test executed: winner = ${result.winner}\n`);

  const analysis = await manager.analyzeTest(result);

  console.log('Risks Detected:');
  if (analysis.risks.length === 0) {
    console.log('  None');
  } else {
    for (const risk of analysis.risks) {
      console.log(`  [${risk.severity.toUpperCase()}] ${risk.type}`);
      console.log(`    ${risk.description}`);
      console.log(`    Action: ${risk.action}`);
    }
  }

  console.log('\nRecommendation:');
  console.log(`  Action: ${analysis.recommendation.action}`);
  console.log(`  Reason: ${analysis.recommendation.reason}`);

  if (analysis.recommendation.action === 'DO_NOT_DEPLOY') {
    console.log('\n⚠️  Deployment blocked - would trigger rollback');

    // Simulate rollback
    console.log('🔄 Simulating rollback...');
    const rollback = await manager.rollback('rollback_test', 'Quality degradation detected (15% drop)');
    console.log(`✅ Rollback completed: ${rollback.status}`);
    console.log(`   Reason: ${rollback.reason}`);
  }

  console.log('\n════════════════════════════════════════════════════════════════\n');
}

// ============================================================================
// EXAMPLE 4: Integration with Strategy Performance
// ============================================================================

async function example4_StrategyPerformance() {
  console.log('\n════════════════════════════════════════════════════════════════');
  console.log('  EXAMPLE 4: Integration with Strategy Performance');
  console.log('  Use Thompson Sampling for variant selection');
  console.log('════════════════════════════════════════════════════════════════\n');

  const manager = new ABTestManager();
  const strategyPerf = getStrategyPerformance();

  // Simulate some historical strategy performance
  console.log('📊 Recording historical strategy performance...');

  await strategyPerf.record('random_routing', true, 0.70);
  await strategyPerf.record('random_routing', true, 0.72);
  await strategyPerf.record('random_routing', false, 0.65);

  await strategyPerf.record('thompson_sampling', true, 0.85);
  await strategyPerf.record('thompson_sampling', true, 0.88);
  await strategyPerf.record('thompson_sampling', true, 0.82);

  console.log('✅ Recorded 6 trials\n');

  // Get all strategies
  const strategies = await strategyPerf.getAllStrategies();

  console.log('Strategy Performance:');
  for (const strategy of strategies) {
    console.log(`  ${strategy.strategy}:`);
    console.log(`    Successes:   ${strategy.successes}`);
    console.log(`    Failures:    ${strategy.failures}`);
    console.log(`    Avg Reward:  ${parseFloat(strategy.avg_reward).toFixed(3)}`);
  }

  console.log('\n🎲 Thompson Sampling selection (10 trials):');

  // Convert to posteriors format
  const posteriors = {};
  for (const strategy of strategies) {
    posteriors[strategy.strategy] = {
      alpha: parseFloat(strategy.alpha),
      beta: parseFloat(strategy.beta),
      mean: parseFloat(strategy.alpha) / (parseFloat(strategy.alpha) + parseFloat(strategy.beta)),
      variance: 0,  // Not needed for Thompson Sampling
      samples: parseFloat(strategy.alpha) + parseFloat(strategy.beta) - 2,
    };
  }

  const counts = {};
  for (const strategy of strategies) {
    counts[strategy.strategy] = 0;
  }

  for (let i = 0; i < 10; i++) {
    const selected = manager.thompsonSampling(posteriors);
    counts[selected]++;
    console.log(`  Trial ${i + 1}: ${selected}`);
  }

  console.log('\nSelection Distribution:');
  for (const [strategy, count] of Object.entries(counts)) {
    console.log(`  ${strategy.padEnd(20)} ${count}/10 (${(count / 10 * 100).toFixed(0)}%)`);
  }

  console.log('\n════════════════════════════════════════════════════════════════\n');
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  const example = args[0] || '1';

  switch (example) {
    case '1':
      await example1_SimpleComparison();
      break;

    case '2':
      await example2_MultiVariant();
      break;

    case '3':
      await example3_Rollback();
      break;

    case '4':
      await example4_StrategyPerformance();
      break;

    case 'all':
      await example1_SimpleComparison();
      await example2_MultiVariant();
      await example3_Rollback();
      await example4_StrategyPerformance();
      break;

    default:
      console.log('Usage:');
      console.log('  node ab-test-manager-example.js 1       - Simple feature comparison');
      console.log('  node ab-test-manager-example.js 2       - Multi-variant test');
      console.log('  node ab-test-manager-example.js 3       - Rollback scenario');
      console.log('  node ab-test-manager-example.js 4       - Strategy performance integration');
      console.log('  node ab-test-manager-example.js all     - Run all examples');
      process.exit(1);
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error('Error:', err.message);
    console.error(err.stack);
    process.exit(1);
  });
}
