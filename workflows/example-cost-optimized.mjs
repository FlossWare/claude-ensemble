#!/usr/bin/env node
/**
 * Example: Cost-Optimized Workflow
 *
 * Demonstrates cost optimizer integration in a multi-agent workflow.
 * Shows automatic model substitution for cost savings.
 *
 * Run: node workflows/example-cost-optimized.mjs
 */

import { optimizedAgent, optimizedParallel, getTotalSavings } from '../shared/cost-optimizer-workflow.mjs';

export default async function exampleCostOptimizedWorkflow({ agent, parallel, log }) {
  log('Starting cost-optimized workflow example');

  // Example 1: Single optimized agent
  log('\n=== Example 1: Single Optimized Agent ===');

  const single = await optimizedAgent({
    task: 'Review code for security vulnerabilities',
    preferredModel: 'opus',  // Expensive model
    autoAcceptThreshold: 50  // Auto-accept if >50% savings
  }, async (model) => {
    log(`Executing with model: ${model}`);

    // Simulate agent call
    return {
      model,
      result: 'Security review complete',
      cost_usd: model === 'opus' ? 0.05 : 0.0015
    };
  });

  log('Single agent result:', single.result);
  log('Optimization:', single.optimization);

  // Example 2: Parallel optimized agents
  log('\n=== Example 2: Parallel Optimized Agents ===');

  const workers = [
    { task: 'Analyze authentication flow', model: 'opus' },
    { task: 'Review database queries', model: 'opus' },
    { task: 'Check API endpoints', model: 'haiku' },
    { task: 'Test error handling', model: 'haiku' },
    { task: 'Verify input validation', model: 'sonnet' },
    { task: 'Examine logging practices', model: 'opus' }
  ];

  const parallelResults = await optimizedParallel(
    workers,
    async (worker, optimizedModel) => {
      log(`Worker "${worker.task}" using ${optimizedModel}`);

      // Simulate agent call
      return {
        worker: worker.task,
        model: optimizedModel,
        result: `${worker.task} complete`,
        cost_usd: optimizedModel === 'opus' ? 0.05 :
                  optimizedModel === 'haiku' ? 0.01 :
                  0.0015
      };
    },
    { autoAcceptThreshold: 50 }
  );

  log('Parallel results count:', parallelResults.results.length);
  log('Total optimization:', parallelResults.totalOptimization);

  // Example 3: Show total savings
  log('\n=== Example 3: Total Savings Summary ===');

  const totalSavings = getTotalSavings();
  log('Total savings summary:', totalSavings);

  if (totalSavings.total_executions > 0) {
    const savingsRate = (totalSavings.total_savings_usd / totalSavings.total_would_have_cost * 100).toFixed(1);
    log(`\nSummary: ${totalSavings.total_executions} executions`);
    log(`Would have cost: $${totalSavings.total_would_have_cost.toFixed(4)}`);
    log(`Actual cost: $${totalSavings.total_actual_cost.toFixed(4)}`);
    log(`Total saved: $${totalSavings.total_savings_usd.toFixed(4)} (${savingsRate}%)`);
  }

  log('\nCost-optimized workflow complete!');
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  // Mock functions for standalone execution
  const mockLog = (...args) => console.log(...args);
  const mockAgent = async (model, config) => ({ model, ...config });
  const mockParallel = async (tasks) => Promise.all(tasks.map(t => ({ result: t })));

  exampleCostOptimizedWorkflow({
    agent: mockAgent,
    parallel: mockParallel,
    log: mockLog
  }).catch(console.error);
}
