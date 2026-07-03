#!/usr/bin/env node
/**
 * Cost Optimizer Quick Start
 *
 * Copy-paste integration code for existing workflows.
 *
 * Add to any workflow:
 *   import { optimizeWorkflow } from './shared/cost-optimizer-quickstart.mjs';
 *   export default optimizeWorkflow(yourWorkflow);
 */

import { optimizedAgent, optimizedParallel, getTotalSavings } from './cost-optimizer-workflow.mjs';
import { readFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

/**
 * Wrap existing workflow to add cost optimization.
 *
 * Usage:
 *   import { optimizeWorkflow } from './shared/cost-optimizer-quickstart.mjs';
 *
 *   async function myWorkflow({ agent, parallel, log }) {
 *     // Your existing workflow code
 *   }
 *
 *   export default optimizeWorkflow(myWorkflow, { threshold: 50 });
 */
export function optimizeWorkflow(workflowFn, options = {}) {
  const {
    threshold = 50,  // Auto-accept if >50% savings
    logSavings = true,  // Log savings to console
    trackTotal = true   // Show total savings at end
  } = options;

  return async function optimizedWorkflowWrapper(context) {
    const { agent: originalAgent, parallel: originalParallel, log } = context;

    // Wrap agent() to add optimization
    const optimizedAgentWrapper = async (model, config) => {
      const task = config.prompt || config.task || 'Unnamed task';

      const { result } = await optimizedAgent(
        { task, preferredModel: model, autoAcceptThreshold: threshold },
        async (optimizedModel) => {
          return await originalAgent(optimizedModel, config);
        }
      );

      return result;
    };

    // Wrap parallel() to add optimization
    const optimizedParallelWrapper = async (tasks) => {
      // Extract model and task from each task
      const workers = tasks.map(t => {
        const model = t.model || 'haiku';  // Default model
        const task = t.prompt || t.task || t.description || 'Unnamed task';
        return { task, model, original: t };
      });

      const { results } = await optimizedParallel(
        workers,
        async (worker, optimizedModel) => {
          return await originalAgent(optimizedModel, worker.original);
        },
        { autoAcceptThreshold: threshold }
      );

      return results;
    };

    // Run workflow with optimized wrappers
    const result = await workflowFn({
      ...context,
      agent: optimizedAgentWrapper,
      parallel: optimizedParallelWrapper
    });

    // Show savings summary
    if (trackTotal) {
      const totals = getTotalSavings();
      if (logSavings && totals.total_executions > 0) {
        log('\n=== Cost Optimization Summary ===');
        log(`Total executions: ${totals.total_executions}`);
        log(`Total saved: $${totals.total_savings_usd.toFixed(4)} (${totals.avg_savings_pct.toFixed(1)}%)`);
        log(`Would have cost: $${totals.total_would_have_cost.toFixed(4)}`);
        log(`Actual cost: $${totals.total_actual_cost.toFixed(4)}`);
      }
    }

    return result;
  };
}

/**
 * Simple wrapper for single agent calls.
 *
 * Usage:
 *   import { cheaperModel } from './shared/cost-optimizer-quickstart.mjs';
 *
 *   const model = cheaperModel('opus', 'Review code');
 *   const result = await agent(model, { ... });
 */
export function cheaperModel(preferredModel, taskDescription, threshold = 50) {
  const patternsPath = join(homedir(), '.claude/learning/cost_optimizer_patterns.json');
  const patterns = JSON.parse(readFileSync(patternsPath, 'utf-8'));

  // Find best substitution
  for (const sub of patterns.substitutions) {
    if (sub.expensive_model === preferredModel && sub.savings_pct >= threshold) {
      console.log(`[COST OPTIMIZER] ${preferredModel} → ${sub.cheap_model} (saves ${sub.savings_pct.toFixed(1)}%)`);
      return sub.cheap_model;
    }
  }

  return preferredModel;
}

/**
 * Before/after cost comparison.
 *
 * Usage:
 *   import { showSavingsPotential } from './shared/cost-optimizer-quickstart.mjs';
 *
 *   showSavingsPotential([
 *     { task: 'Review code', model: 'opus' },
 *     { task: 'Fix bug', model: 'haiku' }
 *   ]);
 */
export function showSavingsPotential(tasks) {
  const patternsPath = join(homedir(), '.claude/learning/cost_optimizer_patterns.json');
  const patterns = JSON.parse(readFileSync(patternsPath, 'utf-8'));
  const modelCosts = patterns.model_costs;

  let totalBefore = 0;
  let totalAfter = 0;

  console.log('\n=== Cost Savings Potential ===\n');

  for (const task of tasks) {
    const beforeCost = modelCosts[task.model]?.avg_cost_per_exec || 0.01;
    totalBefore += beforeCost;

    // Find cheaper alternative
    let afterCost = beforeCost;
    let afterModel = task.model;

    for (const sub of patterns.substitutions) {
      if (sub.expensive_model === task.model) {
        const cheapCost = modelCosts[sub.cheap_model]?.avg_cost_per_exec || 0.01;
        if (cheapCost < afterCost) {
          afterCost = cheapCost;
          afterModel = sub.cheap_model;
        }
      }
    }

    totalAfter += afterCost;

    const savings = beforeCost - afterCost;
    const savingsPct = beforeCost > 0 ? (savings / beforeCost * 100) : 0;

    console.log(`${task.task.substring(0, 40).padEnd(40)} ${task.model} → ${afterModel}`);
    console.log(`  Before: $${beforeCost.toFixed(4)}  After: $${afterCost.toFixed(4)}  Saves: $${savings.toFixed(4)} (${savingsPct.toFixed(1)}%)`);
  }

  const totalSavings = totalBefore - totalAfter;
  const totalSavingsPct = totalBefore > 0 ? (totalSavings / totalBefore * 100) : 0;

  console.log('\n' + '='.repeat(60));
  console.log(`Total before: $${totalBefore.toFixed(4)}`);
  console.log(`Total after:  $${totalAfter.toFixed(4)}`);
  console.log(`Total saves:  $${totalSavings.toFixed(4)} (${totalSavingsPct.toFixed(1)}%)`);
  console.log('='.repeat(60) + '\n');
}

// Example usage
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('Cost Optimizer Quick Start Examples\n');

  // Example 1: Show savings potential
  showSavingsPotential([
    { task: 'Review authentication code', model: 'opus' },
    { task: 'Fix database query bug', model: 'opus' },
    { task: 'Analyze API performance', model: 'haiku' },
    { task: 'Update documentation', model: 'haiku' },
    { task: 'Refactor helper functions', model: 'sonnet' }
  ]);

  // Example 2: Wrapper usage
  console.log('\nExample: Wrap existing workflow\n');
  console.log('Before:');
  console.log('  export default async function({ agent, parallel, log }) { ... }');
  console.log('\nAfter:');
  console.log('  import { optimizeWorkflow } from "./shared/cost-optimizer-quickstart.mjs";');
  console.log('  async function myWorkflow({ agent, parallel, log }) { ... }');
  console.log('  export default optimizeWorkflow(myWorkflow, { threshold: 50 });');
  console.log('\nResult: Automatic cost optimization with no code changes!\n');
}
