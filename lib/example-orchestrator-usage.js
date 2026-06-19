#!/usr/bin/env node

/**
 * Example: Using the Orchestrator with Thompson Sampling Model Selection
 *
 * Demonstrates how to:
 * 1. Select model using Thompson Sampling
 * 2. Execute task with selected model
 * 3. Record execution results
 * 4. Query model performance metrics
 */

const { selectModel, getModelMetrics, recordExecution, OUTCOMES } = require('./orchestrator.js');

/**
 * Example workflow using orchestrator
 */
async function exampleWorkflow() {
  try {
    console.log('=== Example: Thompson Sampling Model Selection ===\n');

    // Step 1: Select best model for task
    console.log('Step 1: Selecting best model...');
    const model = await selectModel({
      task_type: 'research',
      max_cost: 0.10,  // Max $0.10 per request
      exclude_models: []  // No exclusions
    });
    console.log(`\nSelected model: ${model}\n`);

    // Step 2: Get model's current metrics
    console.log('Step 2: Querying model metrics...');
    const metrics = await getModelMetrics(model);
    console.log('Current metrics:', {
      win_rate: `${(metrics.win_rate * 100).toFixed(1)}%`,
      avg_quality: metrics.avg_quality.toFixed(3),
      total_executions: metrics.total_executions,
      thompson_params: `α=${metrics.alpha}, β=${metrics.beta}`
    });
    console.log('');

    // Step 3: Simulate task execution
    console.log('Step 3: Executing task...');
    const startTime = Date.now();

    // [Your actual task execution here]
    // For demo, simulate success
    await new Promise(resolve => setTimeout(resolve, 1000));

    const duration_ms = Date.now() - startTime;
    const quality_score = 0.85;  // Example quality score
    const outcome = OUTCOMES.SUCCESS;

    console.log(`Task completed in ${duration_ms}ms with quality ${quality_score}\n`);

    // Step 4: Record execution result
    console.log('Step 4: Recording execution...');
    await recordExecution({
      model: model,
      workflow: 'example-workflow',
      task_type: 'research',
      quality_score: quality_score,
      input_tokens: 1500,
      output_tokens: 800,
      cost_usd: 0.05,
      duration_ms: duration_ms,
      outcome: outcome,
      metadata: null
    });
    console.log('Execution recorded and model_performance view refreshed\n');

    // Step 5: Show updated metrics
    console.log('Step 5: Querying updated metrics...');
    const updatedMetrics = await getModelMetrics(model);
    console.log('Updated metrics:', {
      win_rate: `${(updatedMetrics.win_rate * 100).toFixed(1)}%`,
      avg_quality: updatedMetrics.avg_quality.toFixed(3),
      total_executions: updatedMetrics.total_executions,
      thompson_params: `α=${updatedMetrics.alpha}, β=${updatedMetrics.beta}`
    });
    console.log('');

    console.log('=== Example Complete ===');
    process.exit(0);
  } catch (err) {
    console.error('Example failed:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

/**
 * Example: Comparing multiple models
 */
async function compareModels() {
  console.log('=== Example: Comparing Model Performance ===\n');

  const models = [
    'claude-opus-4',
    'claude-sonnet-4',
    'claude-haiku-4',
    'gpt-4o'
  ];

  for (const model of models) {
    try {
      const metrics = await getModelMetrics(model);
      console.log(`${model}:`);
      console.log(`  Win rate: ${(metrics.win_rate * 100).toFixed(1)}%`);
      console.log(`  Avg quality: ${metrics.avg_quality.toFixed(3)}`);
      console.log(`  Total executions: ${metrics.total_executions}`);
      console.log(`  Thompson expected value: ${metrics.thompson_expected_value?.toFixed(3) || 'N/A'}`);
      console.log('');
    } catch (err) {
      console.warn(`Failed to get metrics for ${model}:`, err.message);
    }
  }

  process.exit(0);
}

// Run example
const command = process.argv[2] || 'workflow';

if (command === 'workflow') {
  exampleWorkflow();
} else if (command === 'compare') {
  compareModels();
} else {
  console.error('Usage: node example-orchestrator-usage.js [workflow|compare]');
  process.exit(1);
}
