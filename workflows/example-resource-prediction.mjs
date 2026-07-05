/**
 * Example: Resource Usage Prediction Integration
 *
 * Demonstrates how to use the resource usage predictor in workflows:
 * 1. Pre-flight cost estimation
 * 2. Dynamic model selection based on budget
 * 3. Progress tracking against predictions
 */

import { predictResourceUsage, estimateWorkflowCost, formatWorkflowEstimate } from '../shared/resource-usage-adapter.cjs';

export default async function exampleResourcePrediction({ phase, parallel, agent, log }) {
  // Phase 1: Pre-flight cost estimation
  await phase('Estimate Cost', async () => {
    log('Estimating workflow cost before execution...');

    const tasks = [
      { model: 'opus', workflow: 'deep-research', taskType: 'research', taskDescription: 'Research quantum computing' },
      { model: 'sonnet', workflow: 'deep-research', taskType: 'research', taskDescription: 'Research AI safety' },
      { model: 'haiku', workflow: 'deep-research', taskType: 'synthesis', taskDescription: 'Synthesize research findings' },
      { model: 'fable', workflow: 'deep-research', taskType: 'review', taskDescription: 'Review synthesis quality' }
    ];

    const estimate = await estimateWorkflowCost(tasks);

    log('\n' + formatWorkflowEstimate(estimate));

    // Budget check
    const budget = 0.10; // $0.10 budget
    if (estimate.total_cost_usd > budget) {
      log(`\nWARNING: Estimated cost $${estimate.total_cost_usd.toFixed(4)} exceeds budget $${budget.toFixed(4)}`);
      log('Consider using cheaper models or reducing task count');
    } else {
      log(`\nBudget OK: $${estimate.total_cost_usd.toFixed(4)} / $${budget.toFixed(4)}`);
    }

    return estimate;
  });

  // Phase 2: Dynamic model selection based on budget
  await phase('Select Models', async () => {
    log('Testing model selection for budget optimization...');

    const task = {
      workflow: 'code-review',
      taskType: 'review',
      taskDescription: 'Review Python code for bugs'
    };

    const models = ['opus', 'sonnet', 'haiku', 'fable'];
    const predictions = [];

    for (const model of models) {
      const pred = await predictResourceUsage({ ...task, model });
      predictions.push({ model, ...pred });
    }

    // Sort by cost
    predictions.sort((a, b) => a.cost_usd - b.cost_usd);

    log('\nModel costs (cheapest first):');
    for (const pred of predictions) {
      log(`  ${pred.model.padEnd(10)} $${pred.cost_usd.toFixed(4)}  (${pred.duration_ms}ms, ${pred.input_tokens}/${pred.output_tokens} tokens)`);
    }

    // Select cheapest model under quality threshold
    const minQualityModel = 'sonnet'; // Assume sonnet is minimum quality needed
    const selected = predictions.find(p => p.model === minQualityModel) || predictions[0];

    log(`\nSelected: ${selected.model} (cost: $${selected.cost_usd.toFixed(4)})`);

    return selected;
  });

  // Phase 3: Progress tracking
  await phase('Track Progress', async () => {
    log('Demonstrating progress tracking against predictions...');

    const task = {
      model: 'opus',
      workflow: 'deep-research',
      taskType: 'research',
      taskDescription: 'Research quantum computing applications'
    };

    const prediction = await predictResourceUsage(task);

    log('\nPredicted:');
    log(`  Duration: ${(prediction.duration_ms / 1000).toFixed(1)}s`);
    log(`  Tokens:   ${prediction.input_tokens}/${prediction.output_tokens}`);
    log(`  Cost:     $${prediction.cost_usd.toFixed(4)}`);

    // Simulate execution
    const actualStart = Date.now();

    log('\nExecuting task...');
    await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate work

    const actualDuration = Date.now() - actualStart;
    const actualTokensIn = 1200; // Simulated
    const actualTokensOut = 600;
    const actualCost = 0.018;

    log('\nActual:');
    log(`  Duration: ${(actualDuration / 1000).toFixed(1)}s`);
    log(`  Tokens:   ${actualTokensIn}/${actualTokensOut}`);
    log(`  Cost:     $${actualCost.toFixed(4)}`);

    // Compare
    const durationError = Math.abs(actualDuration - prediction.duration_ms) / prediction.duration_ms * 100;
    const tokenError = Math.abs((actualTokensIn + actualTokensOut) - (prediction.input_tokens + prediction.output_tokens)) /
                       (prediction.input_tokens + prediction.output_tokens) * 100;
    const costError = Math.abs(actualCost - prediction.cost_usd) / prediction.cost_usd * 100;

    log('\nPrediction Error:');
    log(`  Duration: ${durationError.toFixed(1)}%`);
    log(`  Tokens:   ${tokenError.toFixed(1)}%`);
    log(`  Cost:     ${costError.toFixed(1)}%`);

    return {
      prediction,
      actual: { duration_ms: actualDuration, input_tokens: actualTokensIn, output_tokens: actualTokensOut, cost_usd: actualCost },
      errors: { duration: durationError, tokens: tokenError, cost: costError }
    };
  });

  log('\n✓ Resource prediction example complete');
}
