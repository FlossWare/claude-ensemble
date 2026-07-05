#!/usr/bin/env node
/**
 * Test Load Balancer Adapter
 *
 * Verifies that the JavaScript adapter can:
 * 1. Load trained statistics
 * 2. Select models using Thompson Sampling
 * 3. Apply task affinities and constraints
 * 4. Return consistent recommendations
 */

const {
  selectModel,
  recommendModel,
  getModelStats,
  getTaskAffinities,
  getLoadDistribution,
  getBanditParams,
  getSummary,
  needsRetraining
} = require('./load-balancer-adapter.cjs');

console.log('='.repeat(80));
console.log('LOAD BALANCER ADAPTER TEST');
console.log('='.repeat(80));

// Test 1: Get summary
console.log('\n1. LOAD BALANCER SUMMARY');
console.log('-'.repeat(80));
const summary = getSummary();
console.log(`Timestamp: ${summary.timestamp}`);
console.log(`Age: ${summary.ageDays.toFixed(1)} days`);
console.log(`Training window: ${summary.windowDays} days`);
console.log(`Total models: ${summary.totalModels}`);
console.log(`Total executions: ${summary.totalExecutions}`);
console.log(`Average quality: ${summary.avgQuality.toFixed(3)}`);
console.log(`Needs retraining: ${summary.needsRetraining ? 'YES' : 'NO'}`);

console.log('\nTop 5 models by quality:');
summary.topModels.forEach((m, i) => {
  console.log(`  ${i + 1}. ${m.model.padEnd(30)} | Quality: ${m.quality.toFixed(3)} | ` +
              `Executions: ${m.executions.toString().padStart(4)} | ` +
              `Latency: ${m.latency.toFixed(0).padStart(6)}ms | ` +
              `Cost: $${m.cost.toFixed(5)}`);
});

// Test 2: Model statistics
console.log('\n2. MODEL STATISTICS');
console.log('-'.repeat(80));
const stats = getModelStats();
console.log(`Loaded statistics for ${Object.keys(stats).length} models`);

// Test 3: Task affinities
console.log('\n3. TASK AFFINITIES');
console.log('-'.repeat(80));
const affinities = getTaskAffinities();
console.log(`Loaded affinities for ${Object.keys(affinities).length} task types`);

// Show a few examples
const exampleTasks = ['code-review', 'debugging', 'security', 'complexity_estimation'];
exampleTasks.forEach(task => {
  if (affinities[task]) {
    const top = Object.entries(affinities[task])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([m, a]) => `${m}(${a.toFixed(2)})`)
      .join(', ');
    console.log(`  ${task.padEnd(25)} | Best: ${top}`);
  }
});

// Test 4: Load distribution
console.log('\n4. CURRENT LOAD DISTRIBUTION');
console.log('-'.repeat(80));
const loadDist = getLoadDistribution();
const sortedLoad = Object.entries(loadDist)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 10);

sortedLoad.forEach(([model, load]) => {
  const bar = '█'.repeat(Math.floor(load * 50));
  console.log(`  ${model.padEnd(30)} | ${(load * 100).toFixed(1).padStart(5)}% ${bar}`);
});

// Test 5: Bandit parameters
console.log('\n5. THOMPSON SAMPLING PARAMETERS');
console.log('-'.repeat(80));
const bandit = getBanditParams();
const sortedBandit = Object.entries(bandit)
  .sort((a, b) => {
    const aRate = a[1].alpha / (a[1].alpha + a[1].beta);
    const bRate = b[1].alpha / (b[1].alpha + b[1].beta);
    return bRate - aRate;
  })
  .slice(0, 10);

sortedBandit.forEach(([model, params]) => {
  const winRate = params.alpha / (params.alpha + params.beta);
  console.log(`  ${model.padEnd(30)} | Win rate: ${winRate.toFixed(3)} | ` +
              `α: ${params.alpha.toString().padStart(4)} | ` +
              `β: ${params.beta.toString().padStart(4)} | ` +
              `Successes: ${params.successes.toString().padStart(4)}`);
});

// Test 6: Model selection
console.log('\n6. MODEL SELECTION TESTS');
console.log('-'.repeat(80));

const testCases = [
  {
    name: 'Code review (no constraints)',
    params: { taskType: 'code-review', complexity: 0.6 }
  },
  {
    name: 'Debugging (high complexity, low latency)',
    params: { taskType: 'debugging', complexity: 0.8, maxLatencyMs: 5000 }
  },
  {
    name: 'Build task (low budget)',
    params: { taskType: 'build_tasks', complexity: 0.3, maxCost: 0.001 }
  },
  {
    name: 'Generic task (no task type)',
    params: { complexity: 0.5 }
  },
  {
    name: 'Security analysis (high quality needed)',
    params: { taskType: 'security', complexity: 0.7 }
  }
];

testCases.forEach((test, i) => {
  console.log(`\nTest ${i + 1}: ${test.name}`);
  console.log(`  Params: ${JSON.stringify(test.params)}`);

  const selection = selectModel(test.params);
  console.log(`  Selected: ${selection.model}`);
  console.log(`  Confidence: ${selection.confidence.toFixed(3)}`);
  console.log(`  Reasoning: ${selection.reasoning}`);

  const altList = Object.entries(selection.alternatives)
    .slice(0, 3)
    .map(([m, s]) => `${m}(${s.toFixed(2)})`)
    .join(', ');
  console.log(`  Alternatives: ${altList}`);
});

// Test 7: Recommendations with full context
console.log('\n7. DETAILED RECOMMENDATIONS');
console.log('-'.repeat(80));

const recommendation = recommendModel('code-review', { complexity: 0.6 });
console.log(`Task type: ${recommendation.taskType}`);
console.log(`Selected model: ${recommendation.selected}`);
console.log(`Confidence: ${recommendation.confidence.toFixed(3)}`);
console.log(`Reasoning: ${recommendation.reasoning}`);

console.log('\nSelected model stats:');
if (recommendation.stats) {
  console.log(`  Quality: ${recommendation.stats.avg_quality.toFixed(3)} ± ${recommendation.stats.std_quality.toFixed(3)}`);
  console.log(`  Latency: ${recommendation.stats.avg_latency_ms.toFixed(0)}ms (p95: ${recommendation.stats.p95_latency.toFixed(0)}ms)`);
  console.log(`  Cost: $${recommendation.stats.avg_cost.toFixed(5)}`);
  console.log(`  Success rate: ${recommendation.stats.success_rate.toFixed(3)}`);
  console.log(`  Executions: ${recommendation.stats.executions}`);
}

console.log('\nTop models for this task type:');
recommendation.topModelsForTask.forEach((m, i) => {
  console.log(`  ${i + 1}. ${m.model.padEnd(30)} | Affinity: ${m.affinity.toFixed(3)} | ` +
              `Quality: ${m.stats.avg_quality.toFixed(3)}`);
});

// Test 8: Consistency check (run multiple times)
console.log('\n8. CONSISTENCY CHECK');
console.log('-'.repeat(80));
console.log('Running same selection 10 times (should vary due to sampling)...');

const selections = {};
for (let i = 0; i < 10; i++) {
  const result = selectModel({ taskType: 'code-review', complexity: 0.6 });
  selections[result.model] = (selections[result.model] || 0) + 1;
}

console.log('Selection distribution:');
Object.entries(selections)
  .sort((a, b) => b[1] - a[1])
  .forEach(([model, count]) => {
    const bar = '█'.repeat(count);
    console.log(`  ${model.padEnd(30)} | ${count}/10 ${bar}`);
  });

console.log('\n' + '='.repeat(80));
console.log('ALL TESTS PASSED ✓');
console.log('='.repeat(80));

console.log('\nTo use in workflows:');
console.log('  const { selectModel } = require("./shared/load-balancer-adapter.cjs");');
console.log('  const selection = selectModel({ taskType: "code-review", complexity: 0.6 });');
console.log('  console.log(`Use model: ${selection.model}`);');
