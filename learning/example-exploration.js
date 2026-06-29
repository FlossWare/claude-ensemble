#!/usr/bin/env node
/**
 * Example: Using UCB Exploration with Thompson Sampling
 *
 * Demonstrates:
 * 1. Recording strategy outcomes
 * 2. Selecting strategies with different exploration methods
 * 3. Comparing Thompson Sampling vs UCB vs Epsilon-Greedy
 *
 * Usage: node learning/example-exploration.js
 */

const { getStrategyPerformance } = require('./postgres-adapter');

async function main() {
  const sp = getStrategyPerformance();

  console.log('=== Exploration Strategies Example ===\n');

  // Clean up old example data
  const db = sp.db;
  await db.query(`DELETE FROM workflow.strategy_performance WHERE strategy LIKE 'example_%'`);

  // Simulate some model executions
  console.log('1. Recording outcomes for different models...\n');

  // Opus: High quality, high cost
  for (let i = 0; i < 20; i++) {
    await sp.record('example_opus', true, 0.9);
  }
  for (let i = 0; i < 5; i++) {
    await sp.record('example_opus', false, 0.3);
  }

  // Sonnet: Medium quality, medium cost
  for (let i = 0; i < 30; i++) {
    await sp.record('example_sonnet', true, 0.7);
  }
  for (let i = 0; i < 10; i++) {
    await sp.record('example_sonnet', false, 0.4);
  }

  // Haiku: Lower quality, low cost
  for (let i = 0; i < 15; i++) {
    await sp.record('example_haiku', true, 0.5);
  }
  for (let i = 0; i < 25; i++) {
    await sp.record('example_haiku', false, 0.2);
  }

  // New model: Very few trials (high uncertainty)
  await sp.record('example_gemini', true, 0.85);
  await sp.record('example_gemini', true, 0.9);
  await sp.record('example_gemini', false, 0.3);

  // Show current stats
  console.log('Current strategy performance:');
  const strategies = await sp.getAllStrategies();
  for (const s of strategies.filter(x => x.strategy.startsWith('example_'))) {
    const trials = parseInt(s.successes) + parseInt(s.failures);
    const successRate = (parseInt(s.successes) / trials * 100).toFixed(1);
    console.log(`  ${s.strategy.replace('example_', '')}: ${s.successes}/${trials} successes (${successRate}%), avg_reward=${parseFloat(s.avg_reward).toFixed(3)}`);
  }

  console.log('\n2. Selecting strategies with different methods...\n');

  // Thompson Sampling (default)
  console.log('Thompson Sampling (Bayesian):');
  for (let i = 0; i < 5; i++) {
    const selected = await sp.selectThompson();
    const alpha = parseFloat(selected.alpha);
    const beta = parseFloat(selected.beta);
    console.log(`  Trial ${i+1}: ${selected.strategy.replace('example_', '')} (α=${alpha.toFixed(1)}, β=${beta.toFixed(1)})`);
  }

  // UCB (deterministic exploration bonus)
  console.log('\nUCB (C=2.0, exploration bonus):');
  for (let i = 0; i < 5; i++) {
    const selected = await sp.selectUCB(2.0);
    console.log(`  Trial ${i+1}: ${selected.strategy.replace('example_', '')} (ucb=${selected.ucb_score.toFixed(3)}, bonus=${selected.exploration_bonus.toFixed(3)})`);
  }

  // Epsilon-Greedy (random exploration)
  console.log('\nEpsilon-Greedy (ε=0.2, 20% random):');
  for (let i = 0; i < 5; i++) {
    const selected = await sp.selectEpsilonGreedy(0.2);
    console.log(`  Trial ${i+1}: ${selected.strategy.replace('example_', '')} (avg_reward=${selected.avg_reward.toFixed(3)})`);
  }

  console.log('\n3. Comparison: Which method selected the underexplored Gemini?\n');

  // Run 100 trials with each method
  const counts = {
    thompson: { example_opus: 0, example_sonnet: 0, example_haiku: 0, example_gemini: 0 },
    ucb: { example_opus: 0, example_sonnet: 0, example_haiku: 0, example_gemini: 0 },
    epsilon: { example_opus: 0, example_sonnet: 0, example_haiku: 0, example_gemini: 0 }
  };

  for (let i = 0; i < 100; i++) {
    const t = await sp.selectThompson();
    counts.thompson[t.strategy]++;

    const u = await sp.selectUCB(2.0);
    counts.ucb[u.strategy]++;

    const e = await sp.selectEpsilonGreedy(0.2);
    counts.epsilon[e.strategy]++;
  }

  console.log('Thompson Sampling (100 trials):');
  for (const [strategy, count] of Object.entries(counts.thompson)) {
    console.log(`  ${strategy.replace('example_', '')}: ${count}%`);
  }

  console.log('\nUCB (100 trials):');
  for (const [strategy, count] of Object.entries(counts.ucb)) {
    console.log(`  ${strategy.replace('example_', '')}: ${count}%`);
  }

  console.log('\nEpsilon-Greedy (100 trials):');
  for (const [strategy, count] of Object.entries(counts.epsilon)) {
    console.log(`  ${strategy.replace('example_', '')}: ${count}%`);
  }

  console.log('\n4. Key Insights:\n');
  console.log(`  - Thompson Sampling: Exploits proven strategies (Opus/Sonnet), rarely explores Gemini`);
  console.log(`  - UCB: Gives Gemini exploration bonus due to few trials (${counts.ucb.example_gemini}%)`);
  console.log(`  - Epsilon-Greedy: Random exploration, may waste trials on bad strategies (Haiku)`);

  console.log('\n5. Recommendation:\n');
  if (counts.ucb.example_gemini > counts.thompson.example_gemini) {
    console.log('  ✅ Use UCB when you suspect API improvements or want to retry underexplored models');
  }
  if (counts.thompson.example_opus + counts.thompson.example_sonnet > 80) {
    console.log('  ✅ Use Thompson Sampling for production (exploits known-good strategies)');
  }
  if (counts.epsilon.example_haiku > 10) {
    console.log('  ⚠️  Epsilon-Greedy wastes exploration on low-quality strategies');
  }

  // Clean up
  await db.query(`DELETE FROM workflow.strategy_performance WHERE strategy LIKE 'example_%'`);
  console.log('\nCleaned up example data.');

  process.exit(0);
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
