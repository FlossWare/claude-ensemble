#!/usr/bin/env node
/**
 * Test Online Learning Integration
 */

import { OnlineLearningClient, OnlineLearningWorkflow } from './online-learning-integration.js';

async function main() {
  console.log('=== Online Learning Integration Test ===\n');

  const learner = new OnlineLearningClient();

  // Test 1: Select model
  console.log('Test 1: Select model for task');
  const task = 'Debug authentication issue in Salesforce API integration';
  const metadata = { workflow: 'debugging', priority: 0.8 };

  const model = await learner.selectModel(task, metadata);
  console.log(`  Selected model: ${model}\n`);

  // Test 2: Update based on outcome
  console.log('Test 2: Update with feedback');
  const reward = learner.calculateReward({
    outcome: 'success',
    quality_score: 0.85,
    duration_ms: 5000,
    timeout_ms: 10000,
    metadata: { confidence: 0.9 }
  });

  console.log(`  Calculated reward: ${reward.toFixed(3)}`);

  const loss = await learner.update(model, task, reward, metadata);
  console.log(`  Training loss: ${loss.toFixed(4)}\n`);

  // Test 3: Get statistics
  console.log('Test 3: Get statistics');
  const stats = await learner.getStatistics();
  console.log(`  Total updates: ${stats.total_updates}`);
  console.log(`  Best model: ${stats.best_model}`);
  console.log(`  Num models: ${stats.num_models}\n`);

  // Test 4: Get rankings
  console.log('Test 4: Get model rankings (top 5)');
  const rankings = await learner.getModelRankings();
  rankings.slice(0, 5).forEach((r, i) => {
    console.log(`  ${i + 1}. ${r.model.padEnd(30)} - score: ${r.score.toFixed(4)}`);
  });
  console.log();

  // Test 5: Workflow integration
  console.log('Test 5: Workflow integration');
  const workflow = new OnlineLearningWorkflow(learner);

  const workers = await workflow.selectWorkers(task, 3, metadata);
  console.log(`  Selected workers: ${workers.join(', ')}`);

  // Simulate worker results
  const workerResults = workers.map((model, i) => ({
    model,
    outcome: 'success',
    quality_score: 0.7 + Math.random() * 0.2,
    confidence: 0.75 + Math.random() * 0.2,
    duration_ms: 3000 + Math.random() * 2000,
    workflow: 'debugging',
    phase: 'execution'
  }));

  const arbiterDecision = {
    selected_model: workers[Math.floor(Math.random() * workers.length)]
  };

  console.log(`  Arbiter selected: ${arbiterDecision.selected_model}`);

  await workflow.updateFromWorkers(task, workerResults, arbiterDecision);
  console.log(`  Updated ${workerResults.length} worker results\n`);

  // Final statistics
  console.log('=== Final Statistics ===');
  const finalStats = await workflow.getStatistics();
  console.log(`Total updates: ${finalStats.total_updates}`);
  console.log(`Best model: ${finalStats.best_model}`);

  const execLog = workflow.getExecutionLog();
  console.log(`\nExecution log (${execLog.length} entries):`);
  execLog.forEach(entry => {
    console.log(`  ${entry.model.padEnd(20)} - reward: ${entry.reward.toFixed(3)} - selected: ${entry.was_selected ? 'YES' : 'NO'}`);
  });

  console.log('\n✅ All tests passed!');
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
