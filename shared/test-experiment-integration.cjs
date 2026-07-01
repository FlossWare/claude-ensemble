#!/usr/bin/env node

/**
 * Test: Experiment Integration
 *
 * Tests experiment-integration.cjs functions
 *
 * Usage:
 *   node test-experiment-integration.cjs
 *
 * Created: 2026-07-01
 * Issue: #267
 */

const assert = require('assert');
const {
  EXPERIMENT_TYPES,
  runRolloutExperiment,
  runVotingExperiment,
  runRoutingExperiment,
  runQualityThresholdExperiment,
  getExperimentsByType,
  generateExperimentSummary,
} = require('./experiment-integration.cjs');

// Test utilities
let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  process.stdout.write(`Testing ${name}... `);
  try {
    fn();
    console.log('✓');
    testsPassed++;
  } catch (error) {
    console.log('✗');
    console.error(`  Error: ${error.message}`);
    testsFailed++;
  }
}

async function asyncTest(name, fn) {
  process.stdout.write(`Testing ${name}... `);
  try {
    await fn();
    console.log('✓');
    testsPassed++;
  } catch (error) {
    console.log('✗');
    console.error(`  Error: ${error.message}`);
    console.error(error.stack);
    testsFailed++;
  }
}

// ============================================================================
// TESTS
// ============================================================================

async function runTests() {
  console.log('\n🧪 Running experiment-integration.cjs tests\n');

  // Test 1: EXPERIMENT_TYPES constant
  test('EXPERIMENT_TYPES defined', () => {
    assert(EXPERIMENT_TYPES.MODEL_ROLLOUT === 'model_rollout');
    assert(EXPERIMENT_TYPES.VOTING_ALGORITHM === 'voting_algorithm');
    assert(EXPERIMENT_TYPES.ROUTING_STRATEGY === 'routing_strategy');
    assert(EXPERIMENT_TYPES.QUALITY_THRESHOLD === 'quality_threshold');
  });

  // Test 2: runRolloutExperiment
  await asyncTest('runRolloutExperiment returns valid result', async () => {
    const result = await runRolloutExperiment({
      model: 'test-model',
      baseline: { stage: 'canary', duration_days: 3 },
      treatment: { stage: 'canary', duration_days: 1 },
      samples: 5,
    });

    assert(result.name, 'Should have experiment name');
    assert(result.verdict, 'Should have verdict');
    assert(typeof result.baseline_mean === 'number', 'Should have baseline mean');
    assert(typeof result.treatment_mean === 'number', 'Should have treatment mean');
    assert(typeof result.p_value === 'number', 'Should have p-value');
    assert(['keep', 'remove', 'inconclusive'].includes(result.verdict), 'Verdict should be valid');
  });

  // Test 3: runVotingExperiment
  await asyncTest('runVotingExperiment returns valid result', async () => {
    const mockVotes = [
      { model: 'opus', output: 'A', confidence: 0.9, quality_score: 0.85 },
      { model: 'sonnet', output: 'A', confidence: 0.8, quality_score: 0.80 },
    ];

    const result = await runVotingExperiment({
      votes: mockVotes,
      taskType: 'test_task',
      baselineOptions: {},
      treatmentOptions: {},
      iterations: 5,
    });

    assert(result.name, 'Should have experiment name');
    assert(result.verdict, 'Should have verdict');
    assert(result.metadata.experiment_type === EXPERIMENT_TYPES.VOTING_ALGORITHM);
  });

  // Test 4: runRoutingExperiment
  await asyncTest('runRoutingExperiment returns valid result', async () => {
    const mockTasks = [
      { language: 'java', prompt: 'test' },
      { language: 'python', prompt: 'test' },
    ];

    const baselineRouter = (task) => 'opus';
    const treatmentRouter = (task) => task.language === 'java' ? 'deepseek' : 'opus';

    const result = await runRoutingExperiment({
      taskType: 'code_gen',
      baselineRouter,
      treatmentRouter,
      tasks: mockTasks,
    });

    assert(result.name, 'Should have experiment name');
    assert(result.verdict, 'Should have verdict');
    assert(result.metadata.experiment_type === EXPERIMENT_TYPES.ROUTING_STRATEGY);
  });

  // Test 5: runQualityThresholdExperiment
  await asyncTest('runQualityThresholdExperiment returns valid result', async () => {
    const mockSamples = [
      { quality: 0.72, correct: true },
      { quality: 0.68, correct: false },
      { quality: 0.80, correct: true },
      { quality: 0.65, correct: false },
      { quality: 0.78, correct: true },
    ];

    const result = await runQualityThresholdExperiment({
      baselineThreshold: 0.70,
      treatmentThreshold: 0.75,
      samples: mockSamples,
    });

    assert(result.name, 'Should have experiment name');
    assert(result.verdict, 'Should have verdict');
    assert(result.metadata.experiment_type === EXPERIMENT_TYPES.QUALITY_THRESHOLD);
  });

  // Test 6: generateExperimentSummary
  await asyncTest('generateExperimentSummary returns valid structure', async () => {
    const summary = await generateExperimentSummary();

    assert(typeof summary.total_experiments === 'number', 'Should have total count');
    assert(typeof summary.overall_success_rate === 'number', 'Should have success rate');
    assert(summary.by_type, 'Should have by_type breakdown');
    assert(Array.isArray(summary.recent_wins), 'Should have recent_wins array');
  });

  // Test 7: getExperimentsByType
  await asyncTest('getExperimentsByType filters correctly', async () => {
    // Run a test experiment first
    await runRolloutExperiment({
      model: 'filter-test',
      baseline: { stage: 'canary', duration_days: 3 },
      treatment: { stage: 'canary', duration_days: 1 },
      samples: 3,
    });

    const experiments = await getExperimentsByType(EXPERIMENT_TYPES.MODEL_ROLLOUT, 5);
    assert(Array.isArray(experiments), 'Should return array');

    // Verify all returned experiments match the type filter
    if (experiments.length > 0) {
      experiments.forEach(exp => {
        const metadata = typeof exp.metadata === 'string'
          ? JSON.parse(exp.metadata)
          : exp.metadata;
        assert(
          metadata.experiment_type === EXPERIMENT_TYPES.MODEL_ROLLOUT,
          'All experiments should match filter type'
        );
      });
    }
  });

  // Test 8: Experiment result structure validation
  await asyncTest('Experiment results include all required fields', async () => {
    const result = await runRolloutExperiment({
      model: 'structure-test',
      baseline: { stage: 'canary', duration_days: 3 },
      treatment: { stage: 'canary', duration_days: 1 },
      samples: 3,
    });

    // Required fields
    const requiredFields = [
      'name',
      'hypothesis',
      'metric',
      'baseline_mean',
      'treatment_mean',
      'improvement_pct',
      'p_value',
      'ci_lower',
      'ci_upper',
      'effect_size',
      'verdict',
      'reason',
    ];

    requiredFields.forEach(field => {
      assert(result.hasOwnProperty(field), `Result should have ${field} field`);
    });
  });

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log(`Tests passed: ${testsPassed}`);
  console.log(`Tests failed: ${testsFailed}`);
  console.log('='.repeat(60));

  if (testsFailed === 0) {
    console.log('\n✅ All tests passed!\n');
    process.exit(0);
  } else {
    console.log(`\n❌ ${testsFailed} test(s) failed\n`);
    process.exit(1);
  }
}

// Run tests
if (require.main === module) {
  runTests().catch(error => {
    console.error('Test runner failed:', error);
    process.exit(1);
  });
}

module.exports = { runTests };
