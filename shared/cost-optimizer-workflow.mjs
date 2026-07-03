#!/usr/bin/env node
/**
 * Cost Optimizer Workflow Integration
 *
 * Wraps worker spawning to predict cost and suggest cheaper alternatives.
 *
 * Usage in workflows:
 *
 *   import { optimizedAgent, optimizedParallel } from './shared/cost-optimizer-workflow.mjs';
 *
 *   // Single agent (auto-suggests cheaper model)
 *   const result = await optimizedAgent({
 *     task: 'Fix authentication bug',
 *     preferredModel: 'opus',
 *     autoAcceptThreshold: 50  // Auto-accept if >50% savings
 *   }, async (model) => {
 *     return await agent(model, { ... });
 *   });
 *
 *   // Parallel workers (optimizes each worker)
 *   const results = await optimizedParallel([
 *     { task: 'Worker 1', model: 'opus' },
 *     { task: 'Worker 2', model: 'haiku' },
 *     { task: 'Worker 3', model: 'sonnet' }
 *   ], async (worker, optimizedModel) => {
 *     return await agent(optimizedModel, { prompt: worker.task });
 *   });
 */

import { execSync } from 'child_process';
import { readFileSync, appendFileSync, existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const HOME = homedir();
const PATTERNS_PATH = join(HOME, '.claude/learning/cost_optimizer_patterns.json');
const SAVINGS_LOG_PATH = join(HOME, '.claude/learning/cost_optimizer_savings_log.jsonl');

// Load patterns
const patterns = JSON.parse(readFileSync(PATTERNS_PATH, 'utf-8'));
const modelCosts = patterns.model_costs;
const substitutions = patterns.substitutions;

/**
 * Predict cost using historical averages.
 */
function predictCost(taskDescription, model) {
  if (!(model in modelCosts)) {
    return 0.01; // Default fallback
  }
  return modelCosts[model].avg_cost_per_exec;
}

/**
 * Suggest cheaper alternative model if available.
 */
function suggestCheaperAlternative(taskDescription, preferredModel) {
  const preferredCost = predictCost(taskDescription, preferredModel);

  let bestAlternative = null;
  let bestSavings = 0.0;

  for (const sub of substitutions) {
    if (sub.expensive_model === preferredModel) {
      const cheapModel = sub.cheap_model;
      const cheapCost = predictCost(taskDescription, cheapModel);
      const savings = preferredCost - cheapCost;
      const savingsPct = preferredCost > 0 ? (savings / preferredCost * 100) : 0;

      // Only suggest if significant savings (>10%)
      if (savingsPct > 10 && savings > bestSavings) {
        bestSavings = savings;
        bestAlternative = {
          model: cheapModel,
          cost: cheapCost,
          savings_usd: savings,
          savings_pct: savingsPct,
          historical_savings_pct: sub.savings_pct
        };
      }
    }
  }

  return {
    preferred_model: preferredModel,
    preferred_cost: preferredCost,
    alternative: bestAlternative
  };
}

/**
 * Predict cost and suggest cheaper alternative.
 */
function predictAndSuggest(taskDescription, preferredModel, autoAcceptThreshold = 50.0) {
  const suggestion = suggestCheaperAlternative(taskDescription, preferredModel);

  if (suggestion.alternative) {
    const alt = suggestion.alternative;
    const autoAccept = alt.savings_pct >= autoAcceptThreshold;

    return {
      predicted_cost: suggestion.preferred_cost,
      suggested_model: alt.model,
      savings: alt.savings_usd,
      savings_pct: alt.savings_pct,
      auto_accept: autoAccept,
      reason: `Historical pattern: ${alt.historical_savings_pct.toFixed(1)}% savings`
    };
  } else {
    return {
      predicted_cost: suggestion.preferred_cost,
      suggested_model: preferredModel,
      savings: 0.0,
      savings_pct: 0.0,
      auto_accept: false,
      reason: 'No cheaper alternative found'
    };
  }
}

/**
 * Log savings achieved.
 */
function logSavings(taskDescription, originalModel, usedModel, actualCost, predictedCost = null) {
  const wouldHaveCost = predictCost(taskDescription, originalModel);
  const savings = wouldHaveCost - actualCost;
  const savingsPct = wouldHaveCost > 0 ? (savings / wouldHaveCost * 100) : 0;

  let predictionError = null;
  let predictionErrorPct = null;
  if (predictedCost !== null) {
    predictionError = Math.abs(predictedCost - actualCost);
    predictionErrorPct = actualCost > 0 ? (predictionError / actualCost * 100) : 0;
  }

  const entry = {
    timestamp: new Date().toISOString(),
    task_description: taskDescription,
    original_model: originalModel,
    used_model: usedModel,
    would_have_cost: wouldHaveCost,
    actual_cost: actualCost,
    savings_usd: savings,
    savings_pct: savingsPct,
    predicted_cost: predictedCost,
    prediction_error: predictionError,
    prediction_error_pct: predictionErrorPct
  };

  appendFileSync(SAVINGS_LOG_PATH, JSON.stringify(entry) + '\n');
  return entry;
}

/**
 * Optimized single agent spawning.
 *
 * @param {Object} config - { task, preferredModel, autoAcceptThreshold }
 * @param {Function} agentFn - async (model) => result
 * @returns {Object} { result, optimization }
 */
export async function optimizedAgent(config, agentFn) {
  const { task, preferredModel, autoAcceptThreshold = 50 } = config;

  // Predict and suggest
  const prediction = predictAndSuggest(task, preferredModel, autoAcceptThreshold);

  const modelToUse = prediction.auto_accept ? prediction.suggested_model : preferredModel;
  const optimization = {
    preferred_model: preferredModel,
    used_model: modelToUse,
    predicted_cost: prediction.predicted_cost,
    savings: prediction.savings,
    savings_pct: prediction.savings_pct,
    auto_accepted: prediction.auto_accept,
    reason: prediction.reason
  };

  // Log decision
  if (modelToUse !== preferredModel) {
    console.log(`[COST OPTIMIZER] ${preferredModel} → ${modelToUse} (saves $${prediction.savings.toFixed(4)}, ${prediction.savings_pct.toFixed(1)}%)`);
  }

  // Execute
  const startTime = Date.now();
  const result = await agentFn(modelToUse);
  const duration = Date.now() - startTime;

  // Extract actual cost from result if available
  let actualCost = prediction.predicted_cost; // Default to prediction
  if (result && typeof result === 'object') {
    if (result.cost) actualCost = result.cost;
    if (result.cost_usd) actualCost = result.cost_usd;
  }

  // Log savings
  const savingsEntry = logSavings(task, preferredModel, modelToUse, actualCost, prediction.predicted_cost);

  optimization.actual_cost = actualCost;
  optimization.actual_savings = savingsEntry.savings_usd;
  optimization.actual_savings_pct = savingsEntry.savings_pct;

  return { result, optimization };
}

/**
 * Optimized parallel agent spawning.
 *
 * @param {Array} workers - [{ task, model }, ...]
 * @param {Function} agentFn - async (worker, optimizedModel) => result
 * @param {Object} options - { autoAcceptThreshold }
 * @returns {Object} { results, totalOptimization }
 */
export async function optimizedParallel(workers, agentFn, options = {}) {
  const { autoAcceptThreshold = 50 } = options;

  // Predict for all workers
  const predictions = workers.map(w => ({
    worker: w,
    prediction: predictAndSuggest(w.task, w.model, autoAcceptThreshold)
  }));

  // Calculate total potential savings
  const totalPredictedCost = predictions.reduce((sum, p) => sum + p.prediction.predicted_cost, 0);
  const totalPredictedSavings = predictions.reduce((sum, p) => sum + p.prediction.savings, 0);
  const avgSavingsPct = predictions.reduce((sum, p) => sum + p.prediction.savings_pct, 0) / predictions.length;

  console.log(`[COST OPTIMIZER] Parallel workers: ${workers.length}`);
  console.log(`[COST OPTIMIZER] Predicted cost: $${totalPredictedCost.toFixed(4)}`);
  console.log(`[COST OPTIMIZER] Potential savings: $${totalPredictedSavings.toFixed(4)} (${avgSavingsPct.toFixed(1)}%)`);

  // Execute in parallel
  const startTime = Date.now();
  const results = await Promise.all(
    predictions.map(async ({ worker, prediction }) => {
      const modelToUse = prediction.auto_accept ? prediction.suggested_model : worker.model;

      if (modelToUse !== worker.model) {
        console.log(`[COST OPTIMIZER] Worker "${worker.task.substring(0, 50)}..." ${worker.model} → ${modelToUse}`);
      }

      const result = await agentFn(worker, modelToUse);

      // Extract actual cost
      let actualCost = prediction.predicted_cost;
      if (result && typeof result === 'object') {
        if (result.cost) actualCost = result.cost;
        if (result.cost_usd) actualCost = result.cost_usd;
      }

      // Log savings
      const savingsEntry = logSavings(worker.task, worker.model, modelToUse, actualCost, prediction.predicted_cost);

      return {
        worker,
        result,
        optimization: {
          preferred_model: worker.model,
          used_model: modelToUse,
          predicted_cost: prediction.predicted_cost,
          actual_cost: actualCost,
          savings: savingsEntry.savings_usd,
          savings_pct: savingsEntry.savings_pct
        }
      };
    })
  );

  const totalDuration = Date.now() - startTime;

  // Calculate actual totals
  const totalActualCost = results.reduce((sum, r) => sum + r.optimization.actual_cost, 0);
  const totalActualSavings = results.reduce((sum, r) => sum + r.optimization.savings, 0);
  const actualAvgSavingsPct = results.reduce((sum, r) => sum + r.optimization.savings_pct, 0) / results.length;

  console.log(`[COST OPTIMIZER] Actual cost: $${totalActualCost.toFixed(4)}`);
  console.log(`[COST OPTIMIZER] Actual savings: $${totalActualSavings.toFixed(4)} (${actualAvgSavingsPct.toFixed(1)}%)`);
  console.log(`[COST OPTIMIZER] Duration: ${(totalDuration / 1000).toFixed(1)}s`);

  return {
    results: results.map(r => r.result),
    totalOptimization: {
      workers: workers.length,
      total_predicted_cost: totalPredictedCost,
      total_actual_cost: totalActualCost,
      total_savings: totalActualSavings,
      avg_savings_pct: actualAvgSavingsPct,
      duration_ms: totalDuration
    }
  };
}

/**
 * Get total savings summary.
 */
export function getTotalSavings(days = null) {
  if (!existsSync(SAVINGS_LOG_PATH)) {
    return {
      total_executions: 0,
      total_savings_usd: 0.0,
      avg_savings_pct: 0.0,
      total_would_have_cost: 0.0,
      total_actual_cost: 0.0
    };
  }

  const entries = [];
  let cutoffTime = null;
  if (days) {
    cutoffTime = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  }

  const lines = readFileSync(SAVINGS_LOG_PATH, 'utf-8').split('\n').filter(l => l.trim());
  for (const line of lines) {
    const entry = JSON.parse(line);
    const entryTime = new Date(entry.timestamp);

    if (!cutoffTime || entryTime >= cutoffTime) {
      entries.push(entry);
    }
  }

  if (entries.length === 0) {
    return {
      total_executions: 0,
      total_savings_usd: 0.0,
      avg_savings_pct: 0.0,
      total_would_have_cost: 0.0,
      total_actual_cost: 0.0
    };
  }

  const totalSavings = entries.reduce((sum, e) => sum + e.savings_usd, 0);
  const avgSavingsPct = entries.reduce((sum, e) => sum + e.savings_pct, 0) / entries.length;
  const totalWouldHaveCost = entries.reduce((sum, e) => sum + e.would_have_cost, 0);
  const totalActualCost = entries.reduce((sum, e) => sum + e.actual_cost, 0);

  return {
    total_executions: entries.length,
    total_savings_usd: totalSavings,
    avg_savings_pct: avgSavingsPct,
    total_would_have_cost: totalWouldHaveCost,
    total_actual_cost: totalActualCost,
    days_analyzed: days
  };
}
