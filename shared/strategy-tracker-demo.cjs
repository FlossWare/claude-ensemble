/**
 * Strategy Tracker Demo
 * Demonstrates the strategy tracking system with real examples
 */

const {
  recordStrategyResult,
  getStrategyPerformance,
  getBestStrategy,
  close
} = require('./strategy-tracker.cjs');

async function demo() {
  console.log('=== Strategy Tracker Demo ===\n');

  // Scenario: Track different code review strategies
  console.log('1. Recording code review strategy results...');
  
  await recordStrategyResult(
    {
      name: 'chain-of-thought-parallel-consensus',
      promptTemplateId: 'chain-of-thought',
      orchestrationPattern: 'parallel',
      verificationMethod: 'multi-ai-consensus',
      reasoningSequence: 'analyze -> identify issues -> propose fixes -> verify'
    },
    'code-review',
    { success: true, reward: 0.92 }
  );

  await recordStrategyResult(
    {
      name: 'few-shot-sequential-self-critique',
      promptTemplateId: 'few-shot',
      orchestrationPattern: 'sequential',
      verificationMethod: 'self-critique',
      reasoningSequence: 'review -> critique -> improve'
    },
    'code-review',
    { success: true, reward: 0.78 }
  );

  await recordStrategyResult(
    {
      name: 'zero-shot-hierarchical-adversarial',
      promptTemplateId: 'zero-shot',
      orchestrationPattern: 'hierarchical',
      verificationMethod: 'adversarial',
      reasoningSequence: 'attack -> defend -> synthesize'
    },
    'code-review',
    { success: true, reward: 0.88 }
  );

  console.log('   ✓ 3 strategies recorded\n');

  // Get all parallel strategies
  console.log('2. Finding parallel orchestration strategies...');
  const parallelStrategies = await getStrategyPerformance({
    orchestrationPattern: 'parallel'
  });
  console.log(`   Found ${parallelStrategies.length} parallel strategies:`);
  parallelStrategies.forEach(s => {
    console.log(`   - ${s.strategy}: avg_reward=${s.avgReward}`);
  });
  console.log('');

  // Get best strategy with constraints
  console.log('3. Selecting best strategy for code-review (using Thompson Sampling)...');
  const best = await getBestStrategy('code-review', {
    minSamples: 1
  });
  console.log(`   Best: ${best.strategy}`);
  console.log(`   - Average reward: ${best.avgReward}`);
  console.log(`   - Sampled reward: ${best.sampledReward.toFixed(3)}`);
  console.log(`   - Confidence: ${best.confidence.toFixed(3)}`);
  console.log(`   - Prompt template: ${best.promptTemplateId}`);
  console.log(`   - Orchestration: ${best.orchestrationPattern}`);
  console.log(`   - Verification: ${best.verificationMethod}`);
  console.log('');

  // Record more results for the best strategy
  console.log('4. Recording additional results for top strategy...');
  for (let i = 0; i < 5; i++) {
    await recordStrategyResult(
      {
        name: best.strategy,
        promptTemplateId: best.promptTemplateId,
        orchestrationPattern: best.orchestrationPattern,
        verificationMethod: best.verificationMethod
      },
      'code-review',
      { success: true, reward: 0.90 + Math.random() * 0.05 }
    );
  }
  console.log('   ✓ 5 more executions recorded\n');

  // Get updated performance
  console.log('5. Updated performance for best strategy...');
  const updated = await getStrategyPerformance({ orchestrationPattern: best.orchestrationPattern });
  const topStrategy = updated[0];
  console.log(`   ${topStrategy.strategy}:`);
  console.log(`   - Successes: ${topStrategy.successes}`);
  console.log(`   - Failures: ${topStrategy.failures}`);
  console.log(`   - Average reward: ${topStrategy.avgReward}`);
  console.log(`   - Alpha: ${topStrategy.alpha}, Beta: ${topStrategy.beta}`);
  console.log('');

  console.log('=== Demo Complete ===\n');
  
  await close();
}

demo().catch(err => {
  console.error('Demo failed:', err);
  process.exit(1);
});
