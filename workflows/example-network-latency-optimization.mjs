#!/usr/bin/env node
/**
 * Example Workflow: Network Latency-Optimized Task Assignment
 *
 * Demonstrates how to use the Network Latency Predictor to optimize
 * worker selection in distributed workflows.
 *
 * Usage:
 *   node workflows/example-network-latency-optimization.mjs
 */

import { execSync } from 'child_process';
import {
  predictLatency,
  rankNodesByLatency,
  optimizeWorkerAssignment,
  collectMeasurements,
  hasModels,
  getModelStats
} from '../shared/network-latency-adapter.cjs';

/**
 * Example workflow: Distribute tasks across fleet with latency optimization
 */
async function networkOptimizedWorkflow() {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('Network Latency-Optimized Task Assignment Workflow');
  console.log('═══════════════════════════════════════════════════════════\n');

  // Step 1: Check if ML models are available
  console.log('Step 1: Checking ML model availability...');
  const modelsExist = hasModels();
  console.log(`  Models available: ${modelsExist ? '✓ Yes' : '✗ No (will use fallback)'}\n`);

  if (modelsExist) {
    const stats = getModelStats();
    if (stats) {
      console.log('  Model Statistics:');
      console.log(`    Training samples: ${stats.training_samples}`);
      console.log(`    Trained at: ${stats.trained_at}`);
      console.log(`    R² scores:`);
      for (const [model, perf] of Object.entries(stats.model_performance)) {
        console.log(`      ${model}: ${perf.r2.toFixed(3)}`);
      }
      console.log();
    }
  }

  // Step 2: Define available workers
  const availableWorkers = [
    'server-01',
    'server-02',
    'server-03',
    'laptop-01',
    'pi-02',
    'desktop-ap',
    'server-ap'
  ];

  console.log(`Step 2: Available workers (${availableWorkers.length}):`);
  availableWorkers.forEach(w => console.log(`  - ${w}`));
  console.log();

  // Step 3: Collect current network measurements (optional)
  console.log('Step 3: Collecting current network measurements...');
  try {
    const result = await collectMeasurements();
    if (result.success) {
      console.log('  ✓ Measurements collected\n');
    } else {
      console.log(`  ⚠ Collection failed: ${result.error}\n`);
    }
  } catch (error) {
    console.log(`  ⚠ Collection failed: ${error.message}\n`);
  }

  // Step 4: Rank workers by predicted latency
  console.log('Step 4: Ranking workers by network latency...');
  const ranked = await rankNodesByLatency(availableWorkers);

  console.log('\n  Latency Rankings:');
  console.log('  ─────────────────────────────────────────────────────────');
  console.log('  Rank | Node         | Latency (ms) | Confidence | Source');
  console.log('  ─────────────────────────────────────────────────────────');

  ranked.forEach((r, i) => {
    const rank = (i + 1).toString().padStart(4);
    const node = r.node.padEnd(12);
    const latency = r.predicted_latency_ms.toFixed(2).padStart(12);
    const confidence = r.confidence.toFixed(3).padStart(10);
    const source = r.source.padEnd(18);
    console.log(`  ${rank} | ${node} | ${latency} | ${confidence} | ${source}`);
  });
  console.log('  ─────────────────────────────────────────────────────────\n');

  // Step 5: Optimize worker assignment
  console.log('Step 5: Optimizing worker assignment (top 70%)...');
  const optimized = await optimizeWorkerAssignment(availableWorkers);

  const selectedWorkers = optimized
    .filter(w => w.recommended)
    .map(w => w.hostname);

  console.log(`\n  Selected workers (${selectedWorkers.length}):`);
  optimized.forEach(w => {
    const mark = w.recommended ? '✓' : ' ';
    console.log(`  ${mark} ${w.rank}. ${w.hostname.padEnd(12)} - ${w.predicted_latency_ms.toFixed(2)}ms`);
  });
  console.log();

  // Step 6: Simulate task distribution
  console.log('Step 6: Simulating task distribution...');
  const tasks = [
    'Analyze dataset A',
    'Process logs B',
    'Train model C',
    'Generate report D',
    'Validate results E'
  ];

  console.log(`\n  Tasks (${tasks.length}):`);
  tasks.forEach((task, i) => {
    const worker = selectedWorkers[i % selectedWorkers.length];
    const latency = optimized.find(w => w.hostname === worker).predicted_latency_ms;
    console.log(`    ${i + 1}. ${task.padEnd(20)} → ${worker.padEnd(12)} (${latency.toFixed(2)}ms)`);
  });
  console.log();

  // Step 7: Calculate expected communication overhead
  console.log('Step 7: Calculating expected communication overhead...');

  const totalLatency = tasks.reduce((sum, task, i) => {
    const worker = selectedWorkers[i % selectedWorkers.length];
    const latency = optimized.find(w => w.hostname === worker).predicted_latency_ms;
    return sum + latency;
  }, 0);

  const avgLatency = totalLatency / tasks.length;

  // Compare with random assignment
  const randomLatency = availableWorkers.reduce((sum, worker) => {
    const latency = ranked.find(r => r.node === worker).predicted_latency_ms;
    return sum + latency;
  }, 0) / availableWorkers.length;

  const improvement = ((randomLatency - avgLatency) / randomLatency) * 100;

  console.log(`\n  Optimized assignment:`);
  console.log(`    Total latency: ${totalLatency.toFixed(2)}ms`);
  console.log(`    Average latency: ${avgLatency.toFixed(2)}ms`);
  console.log();
  console.log(`  Random assignment (baseline):`);
  console.log(`    Average latency: ${randomLatency.toFixed(2)}ms`);
  console.log();
  console.log(`  Improvement: ${improvement.toFixed(1)}% reduction in communication overhead\n`);

  // Step 8: Recommendations
  console.log('Step 8: Recommendations');
  console.log('═══════════════════════════════════════════════════════════');

  if (!modelsExist) {
    console.log('  ⚠ ML models not trained. To enable predictions:');
    console.log('    1. Collect measurements: python3 tools/network_latency_predictor.py --collect');
    console.log('    2. Repeat 5-10 times with delays');
    console.log('    3. Train models: python3 tools/network_latency_predictor.py --train\n');
  } else {
    const stats = getModelStats();
    if (stats && stats.training_samples < 100) {
      console.log(`  ⚠ Only ${stats.training_samples} training samples. For better accuracy:`);
      console.log('    - Set up automated collection (cron every 5 min)');
      console.log('    - Target: 100+ samples for production use\n');
    } else {
      console.log('  ✓ System ready for production use\n');
    }
  }

  console.log('  Integration examples:');
  console.log('    - fleet_executor.mjs: Use rankNodesByLatency() before task assignment');
  console.log('    - consensus-replay.mjs: Optimize arbiter selection by latency');
  console.log('    - deep-research workflow: Select workers for parallel search phases\n');

  console.log('═══════════════════════════════════════════════════════════');
  console.log('Workflow complete\n');

  return {
    selectedWorkers,
    ranked,
    totalLatency,
    avgLatency,
    improvement
  };
}

/**
 * Example: Predict latency for specific node
 */
async function exampleSinglePrediction() {
  console.log('\n╔═══════════════════════════════════════════════════════════╗');
  console.log('║  Example: Single Node Latency Prediction                 ║');
  console.log('╚═══════════════════════════════════════════════════════════╝\n');

  const targetNode = 'server-01';

  console.log(`Predicting latency for ${targetNode}...`);
  const prediction = await predictLatency(targetNode);

  console.log('\nPrediction Result:');
  console.log('─────────────────────────────────────────────────────────');
  console.log(`  Node: ${prediction.node}`);
  console.log(`  Predicted latency: ${prediction.predicted_latency_ms.toFixed(2)} ms`);
  console.log(`  Confidence: ${(prediction.confidence * 100).toFixed(1)}%`);
  console.log(`  Source: ${prediction.source}`);

  if (prediction.actual_latency_ms) {
    const error = Math.abs(prediction.predicted_latency_ms - prediction.actual_latency_ms);
    const errorPercent = (error / prediction.actual_latency_ms) * 100;
    console.log(`  Actual latency: ${prediction.actual_latency_ms.toFixed(2)} ms`);
    console.log(`  Prediction error: ${error.toFixed(2)} ms (${errorPercent.toFixed(1)}%)`);
  }

  console.log('─────────────────────────────────────────────────────────\n');
}

/**
 * Main entry point
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--predict')) {
    await exampleSinglePrediction();
  } else if (args.includes('--help')) {
    console.log('Usage:');
    console.log('  node workflows/example-network-latency-optimization.mjs');
    console.log('  node workflows/example-network-latency-optimization.mjs --predict');
    console.log('  node workflows/example-network-latency-optimization.mjs --help');
  } else {
    await networkOptimizedWorkflow();
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error('Error:', error.message);
    process.exit(1);
  });
}

export { networkOptimizedWorkflow, exampleSinglePrediction };
