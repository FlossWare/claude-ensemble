#!/usr/bin/env node
/**
 * Workflow Integration Example: Using UCB Exploration in Real Workflows
 *
 * Demonstrates how to integrate exploration strategies into actual workflows
 * that route tasks to different AI models.
 *
 * Usage: node learning/workflow-integration-example.js
 */

const { getStrategyPerformance, getExecutionMonitor } = require('./postgres-adapter');

// Mock workflow task runner (replace with actual API calls)
async function runTaskWithModel(modelName, task) {
  // Simulate API call with realistic performance characteristics
  const models = {
    'claude-opus': { successRate: 0.85, avgReward: 0.9, latency: 800 },
    'claude-sonnet': { successRate: 0.80, avgReward: 0.75, latency: 400 },
    'claude-haiku': { successRate: 0.60, avgReward: 0.5, latency: 150 },
    'gpt-4o': { successRate: 0.82, avgReward: 0.85, latency: 600 },
    'gemini-pro': { successRate: 0.78, avgReward: 0.7, latency: 500 },
  };

  const model = models[modelName] || { successRate: 0.5, avgReward: 0.5, latency: 500 };

  // Simulate latency
  await new Promise(resolve => setTimeout(resolve, model.latency * Math.random()));

  // Simulate success/failure based on model's success rate
  const success = Math.random() < model.successRate;

  // Simulate reward (quality score)
  const reward = success
    ? model.avgReward + (Math.random() * 0.2 - 0.1) // ±0.1 variance
    : model.avgReward * 0.5; // Lower reward on failure

  return {
    success,
    reward: Math.max(0, Math.min(1, reward)), // Clamp to [0, 1]
    output: `Result from ${modelName}: ${success ? 'success' : 'failed'}`,
    latency: model.latency
  };
}

async function runWorkflow(taskDescription, explorationMethod = 'thompson') {
  const sp = getStrategyPerformance();
  const monitor = getExecutionMonitor();

  console.log(`\n=== Running workflow: "${taskDescription}" ===`);
  console.log(`Exploration method: ${explorationMethod}`);

  // Select model using exploration strategy
  const startSelection = Date.now();
  const selected = await sp.select(explorationMethod, {
    explorationConstant: 2.0, // UCB parameter
    epsilon: 0.1 // Epsilon-Greedy parameter
  });
  const selectionTime = Date.now() - startSelection;

  if (!selected) {
    console.log('No strategies available. Recording baseline data...');

    // Bootstrap with default models
    for (const model of ['claude-opus', 'claude-sonnet', 'claude-haiku']) {
      const result = await runTaskWithModel(model, taskDescription);
      await sp.record(model, result.success, result.reward);
      console.log(`  Bootstrapped ${model}: ${result.success ? '✓' : '✗'} (reward: ${result.reward.toFixed(2)})`);
    }

    // Retry selection
    const selected = await sp.select(explorationMethod);
    if (!selected) {
      throw new Error('Failed to select strategy after bootstrap');
    }
  }

  console.log(`Selected model: ${selected.strategy} (selection took ${selectionTime}ms)`);

  // Show selection reasoning
  if (explorationMethod === 'ucb' && selected.ucb_score) {
    console.log(`  UCB score: ${selected.ucb_score.toFixed(3)} (exploitation: ${selected.exploitation_score.toFixed(3)}, exploration bonus: ${selected.exploration_bonus.toFixed(3)})`);
  } else if (explorationMethod === 'thompson') {
    console.log(`  Thompson: α=${parseFloat(selected.alpha).toFixed(1)}, β=${parseFloat(selected.beta).toFixed(1)} (${(100 * parseFloat(selected.alpha) / (parseFloat(selected.alpha) + parseFloat(selected.beta))).toFixed(1)}% estimated success)`);
  }

  // Execute task with selected model
  const startExec = Date.now();
  const result = await runTaskWithModel(selected.strategy, taskDescription);
  const execTime = Date.now() - startExec;

  console.log(`Result: ${result.success ? '✅ SUCCESS' : '❌ FAILED'} (reward: ${result.reward.toFixed(3)}, latency: ${execTime}ms)`);

  // Record outcome
  await sp.record(selected.strategy, result.success, result.reward);
  console.log('Recorded outcome to strategy performance database');

  // Log to execution monitor
  await monitor.logExecution({
    model: selected.strategy,
    workflow: 'example-workflow',
    task_type: 'code-review',
    quality_score: result.reward,
    input_tokens: 1500,
    output_tokens: 800,
    cost_usd: 0.05,
    duration_ms: execTime,
    outcome: result.success ? 'success' : 'failed',
    metadata: {
      exploration_method: explorationMethod,
      selection_time_ms: selectionTime
    }
  });
  console.log('Logged execution to monitoring database');

  return result;
}

async function demonstrateExplorationComparison() {
  console.log('╔══════════════════════════════════════════════════════╗');
  console.log('║  Workflow Integration Example                        ║');
  console.log('║  Comparing Exploration Methods in Real Workflows     ║');
  console.log('╚══════════════════════════════════════════════════════╝');

  // Clean up old demo data
  const db = (await getStrategyPerformance()).db;
  await db.query(`DELETE FROM workflow.strategy_performance WHERE strategy LIKE 'claude-%' OR strategy LIKE 'gpt-%' OR strategy LIKE 'gemini-%'`);
  await db.query(`DELETE FROM workflow.execution_summary WHERE workflow = 'example-workflow'`);

  // Bootstrap some initial data
  console.log('\n--- Phase 1: Bootstrap Initial Data ---');
  const sp = getStrategyPerformance();

  for (const model of ['claude-opus', 'claude-sonnet', 'claude-haiku']) {
    for (let i = 0; i < 5; i++) {
      const result = await runTaskWithModel(model, 'Bootstrap task');
      await sp.record(model, result.success, result.reward);
    }
  }

  // Add new model with only 1 trial (underexplored)
  const result = await runTaskWithModel('gpt-4o', 'Bootstrap task');
  await sp.record('gpt-4o', result.success, result.reward);

  console.log('Bootstrapped initial data');

  // Show current stats
  const strategies = await sp.getAllStrategies();
  console.log('\nCurrent strategy performance:');
  for (const s of strategies) {
    const trials = parseInt(s.successes) + parseInt(s.failures);
    const successRate = (parseInt(s.successes) / trials * 100).toFixed(1);
    console.log(`  ${s.strategy}: ${s.successes}/${trials} (${successRate}%), avg_reward=${parseFloat(s.avg_reward).toFixed(3)}`);
  }

  // Run workflows with different exploration methods
  console.log('\n--- Phase 2: Thompson Sampling (5 workflows) ---');
  for (let i = 0; i < 5; i++) {
    await runWorkflow(`Code review task ${i+1}`, 'thompson');
  }

  console.log('\n--- Phase 3: UCB (5 workflows) ---');
  for (let i = 0; i < 5; i++) {
    await runWorkflow(`Code review task ${i+6}`, 'ucb');
  }

  console.log('\n--- Phase 4: Epsilon-Greedy (5 workflows) ---');
  for (let i = 0; i < 5; i++) {
    await runWorkflow(`Code review task ${i+11}`, 'epsilon-greedy');
  }

  // Compare results
  console.log('\n--- Phase 5: Results Comparison ---');

  const results = await db.query(`
    SELECT
      metadata->>'exploration_method' as method,
      COUNT(*) as total_runs,
      SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
      AVG(quality_score) as avg_quality,
      AVG(duration_ms) as avg_latency_ms
    FROM workflow.execution_summary
    WHERE workflow = 'example-workflow'
    AND metadata->>'exploration_method' IS NOT NULL
    GROUP BY metadata->>'exploration_method'
    ORDER BY avg_quality DESC
  `);

  console.log('\nMethod Comparison:');
  console.table(results.map(r => ({
    method: r.method,
    runs: r.total_runs,
    success_rate: (parseFloat(r.success_rate) * 100).toFixed(1) + '%',
    avg_quality: parseFloat(r.avg_quality).toFixed(3),
    avg_latency_ms: parseFloat(r.avg_latency_ms).toFixed(0) + 'ms'
  })));

  // Show model usage distribution
  const modelUsage = await db.query(`
    SELECT
      model,
      metadata->>'exploration_method' as method,
      COUNT(*) as selections
    FROM workflow.execution_summary
    WHERE workflow = 'example-workflow'
    GROUP BY model, metadata->>'exploration_method'
    ORDER BY method, selections DESC
  `);

  console.log('\nModel Selection Distribution:');
  const grouped = {};
  for (const row of modelUsage) {
    if (!grouped[row.method]) grouped[row.method] = {};
    grouped[row.method][row.model] = parseInt(row.selections);
  }

  for (const [method, models] of Object.entries(grouped)) {
    console.log(`\n${method}:`);
    for (const [model, count] of Object.entries(models)) {
      console.log(`  ${model}: ${count} selections`);
    }
  }

  // Show exploration effectiveness
  const gpt4oUsage = await db.query(`
    SELECT
      metadata->>'exploration_method' as method,
      COUNT(*) as gpt4o_selections
    FROM workflow.execution_summary
    WHERE workflow = 'example-workflow'
    AND model = 'gpt-4o'
    GROUP BY metadata->>'exploration_method'
  `);

  console.log('\n\nExploration Effectiveness (GPT-4o selections, underexplored model):');
  for (const row of gpt4oUsage) {
    console.log(`  ${row.method}: ${row.gpt4o_selections} selections`);
  }

  console.log('\n--- Recommendations ---');
  console.log('✅ Use Thompson Sampling for production (balances exploration/exploitation)');
  console.log('✅ Use UCB when you suspect API improvements or new models are underexplored');
  console.log('⚠️  UCB may over-explore if exploration constant C is too high');
  console.log('⚠️  Epsilon-Greedy is simple but may waste exploration on bad models');

  // Clean up
  await db.query(`DELETE FROM workflow.strategy_performance WHERE strategy LIKE 'claude-%' OR strategy LIKE 'gpt-%' OR strategy LIKE 'gemini-%'`);
  await db.query(`DELETE FROM workflow.execution_summary WHERE workflow = 'example-workflow'`);
  console.log('\nCleaned up demo data.');

  process.exit(0);
}

// Run demonstration
demonstrateExplorationComparison().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
