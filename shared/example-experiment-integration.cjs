#!/usr/bin/env node

/**
 * Example: Experiment Integration Usage
 *
 * Demonstrates how to use experiment-integration.cjs to run
 * A/B tests on system components.
 *
 * Usage:
 *   node example-experiment-integration.cjs [--type TYPE]
 *
 * Types: rollout, voting, routing, threshold, summary
 *
 * Created: 2026-07-01
 * Issue: #267
 */

const {
  EXPERIMENT_TYPES,
  runRolloutExperiment,
  runVotingExperiment,
  runRoutingExperiment,
  runQualityThresholdExperiment,
  generateExperimentSummary,
} = require('./experiment-integration.cjs');

// ============================================================================
// EXAMPLE 1: MODEL ROLLOUT EXPERIMENT
// ============================================================================

async function exampleRolloutExperiment() {
  console.log('\n' + '='.repeat(80));
  console.log('EXAMPLE 1: Model Rollout Experiment');
  console.log('='.repeat(80));

  console.log('\nHypothesis: Faster canary rollout (1 day) maintains quality vs baseline (3 days)');
  console.log('Metric: Quality score (0.0-1.0)');
  console.log('Sample size: 20 executions per arm\n');

  const result = await runRolloutExperiment({
    model: 'opus-3.5',
    baseline: { stage: 'canary', duration_days: 3 },
    treatment: { stage: 'canary', duration_days: 1 },
    samples: 20,
  });

  console.log('\n--- RESULTS ---');
  console.log(`Baseline mean: ${result.baseline_mean.toFixed(4)}`);
  console.log(`Treatment mean: ${result.treatment_mean.toFixed(4)}`);
  console.log(`Improvement: ${result.improvement_pct.toFixed(2)}%`);
  console.log(`p-value: ${result.p_value.toFixed(4)}`);
  console.log(`Effect size (Cohen's d): ${result.effect_size.toFixed(3)}`);
  console.log(`95% CI: [${result.ci_lower.toFixed(4)}, ${result.ci_upper.toFixed(4)}]`);
  console.log(`\nVerdict: ${result.verdict.toUpperCase()}`);
  console.log(`Reason: ${result.reason}`);

  return result;
}

// ============================================================================
// EXAMPLE 2: VOTING ALGORITHM EXPERIMENT
// ============================================================================

async function exampleVotingExperiment() {
  console.log('\n' + '='.repeat(80));
  console.log('EXAMPLE 2: Voting Algorithm Experiment');
  console.log('='.repeat(80));

  console.log('\nHypothesis: Disagreement detection improves consensus quality');
  console.log('Metric: Winner confidence (0.0-1.0)');
  console.log('Sample size: 30 voting iterations per arm\n');

  // Mock votes for testing
  const mockVotes = [
    { model: 'opus', output: 'Solution A', confidence: 0.92, quality_score: 0.88 },
    { model: 'sonnet', output: 'Solution A', confidence: 0.87, quality_score: 0.85 },
    { model: 'haiku', output: 'Solution B', confidence: 0.65, quality_score: 0.70 },
    { model: 'fable', output: 'Solution A', confidence: 0.90, quality_score: 0.86 },
  ];

  const result = await runVotingExperiment({
    votes: mockVotes,
    taskType: 'code_review',
    baselineOptions: { algorithm: 'standard' },
    treatmentOptions: { algorithm: 'with_disagreement_detection' },
    iterations: 30,
  });

  console.log('\n--- RESULTS ---');
  console.log(`Baseline mean: ${result.baseline_mean.toFixed(4)}`);
  console.log(`Treatment mean: ${result.treatment_mean.toFixed(4)}`);
  console.log(`Improvement: ${result.improvement_pct.toFixed(2)}%`);
  console.log(`p-value: ${result.p_value.toFixed(4)}`);
  console.log(`\nVerdict: ${result.verdict.toUpperCase()}`);
  console.log(`Reason: ${result.reason}`);

  return result;
}

// ============================================================================
// EXAMPLE 3: ROUTING STRATEGY EXPERIMENT
// ============================================================================

async function exampleRoutingExperiment() {
  console.log('\n' + '='.repeat(80));
  console.log('EXAMPLE 3: Routing Strategy Experiment');
  console.log('='.repeat(80));

  console.log('\nHypothesis: Task-specific routing (deepseek-coder for Java) improves quality');
  console.log('Metric: Task completion quality (0.0-1.0)');
  console.log('Sample size: 15 tasks per arm\n');

  // Mock tasks
  const mockTasks = [
    { language: 'java', prompt: 'Generate Spring controller' },
    { language: 'java', prompt: 'Write Maven POM' },
    { language: 'python', prompt: 'Generate Flask route' },
    { language: 'java', prompt: 'Create JUnit test' },
    { language: 'javascript', prompt: 'Write React component' },
    { language: 'java', prompt: 'Implement Salesforce API client' },
    { language: 'python', prompt: 'Write pandas dataframe transform' },
    { language: 'java', prompt: 'Generate JPA entity' },
    { language: 'javascript', prompt: 'Create Express middleware' },
    { language: 'java', prompt: 'Write Lombok model' },
    { language: 'python', prompt: 'Generate pytest fixture' },
    { language: 'java', prompt: 'Implement service layer' },
    { language: 'javascript', prompt: 'Write Vue component' },
    { language: 'java', prompt: 'Create DTO mapper' },
    { language: 'python', prompt: 'Write SQLAlchemy model' },
  ];

  // Baseline: always use opus
  const baselineRouter = (task) => 'opus';

  // Treatment: use deepseek-coder for Java, opus for others
  const treatmentRouter = (task) => task.language === 'java' ? 'deepseek-coder' : 'opus';

  const result = await runRoutingExperiment({
    taskType: 'code_generation',
    baselineRouter,
    treatmentRouter,
    tasks: mockTasks,
  });

  console.log('\n--- RESULTS ---');
  console.log(`Baseline mean: ${result.baseline_mean.toFixed(4)}`);
  console.log(`Treatment mean: ${result.treatment_mean.toFixed(4)}`);
  console.log(`Improvement: ${result.improvement_pct.toFixed(2)}%`);
  console.log(`p-value: ${result.p_value.toFixed(4)}`);
  console.log(`\nVerdict: ${result.verdict.toUpperCase()}`);
  console.log(`Reason: ${result.reason}`);

  return result;
}

// ============================================================================
// EXAMPLE 4: QUALITY THRESHOLD EXPERIMENT
// ============================================================================

async function exampleQualityThresholdExperiment() {
  console.log('\n' + '='.repeat(80));
  console.log('EXAMPLE 4: Quality Threshold Experiment');
  console.log('='.repeat(80));

  console.log('\nHypothesis: Raising threshold from 0.70 to 0.75 improves decision accuracy');
  console.log('Metric: Decision accuracy (0.0-1.0)');
  console.log('Sample size: 50 outputs\n');

  // Mock samples: outputs with quality scores and ground truth correctness
  const mockSamples = [];
  for (let i = 0; i < 50; i++) {
    const quality = 0.60 + Math.random() * 0.35; // Range: 0.60-0.95
    const correct = quality >= 0.73; // True correctness threshold (unknown to experiment)
    mockSamples.push({ quality, correct });
  }

  const result = await runQualityThresholdExperiment({
    baselineThreshold: 0.70,
    treatmentThreshold: 0.75,
    samples: mockSamples,
  });

  console.log('\n--- RESULTS ---');
  console.log(`Baseline accuracy: ${result.baseline_mean.toFixed(4)}`);
  console.log(`Treatment accuracy: ${result.treatment_mean.toFixed(4)}`);
  console.log(`Improvement: ${result.improvement_pct.toFixed(2)}%`);
  console.log(`p-value: ${result.p_value.toFixed(4)}`);
  console.log(`\nVerdict: ${result.verdict.toUpperCase()}`);
  console.log(`Reason: ${result.reason}`);

  return result;
}

// ============================================================================
// EXAMPLE 5: EXPERIMENT SUMMARY
// ============================================================================

async function exampleSummary() {
  console.log('\n' + '='.repeat(80));
  console.log('EXAMPLE 5: Experiment Summary');
  console.log('='.repeat(80));

  const summary = await generateExperimentSummary();

  console.log(`\nTotal experiments: ${summary.total_experiments}`);
  console.log(`Overall success rate: ${(summary.overall_success_rate * 100).toFixed(1)}%`);

  console.log('\n--- BY TYPE ---');
  for (const [type, stats] of Object.entries(summary.by_type)) {
    console.log(`\n${type}:`);
    console.log(`  Total: ${stats.total}`);
    console.log(`  Kept: ${stats.kept}`);
    console.log(`  Removed: ${stats.removed}`);
    console.log(`  Inconclusive: ${stats.inconclusive}`);
    console.log(`  Success rate: ${(stats.success_rate * 100).toFixed(1)}%`);
  }

  console.log('\n--- RECENT WINS ---');
  summary.recent_wins.forEach((win, idx) => {
    console.log(`\n${idx + 1}. ${win.name}`);
    console.log(`   Hypothesis: ${win.hypothesis}`);
    console.log(`   Improvement: ${win.improvement_pct?.toFixed(2)}%`);
    console.log(`   p-value: ${win.p_value?.toFixed(4)}`);
    console.log(`   Date: ${win.created_at}`);
  });

  return summary;
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  const typeFlag = args.indexOf('--type');
  const type = typeFlag >= 0 ? args[typeFlag + 1] : 'rollout';

  console.log('\n🧪 EXPERIMENT INTEGRATION EXAMPLES');

  try {
    switch (type) {
      case 'rollout':
        await exampleRolloutExperiment();
        break;
      case 'voting':
        await exampleVotingExperiment();
        break;
      case 'routing':
        await exampleRoutingExperiment();
        break;
      case 'threshold':
        await exampleQualityThresholdExperiment();
        break;
      case 'summary':
        await exampleSummary();
        break;
      case 'all':
        await exampleRolloutExperiment();
        await exampleVotingExperiment();
        await exampleRoutingExperiment();
        await exampleQualityThresholdExperiment();
        await exampleSummary();
        break;
      default:
        console.error(`\nUnknown type: ${type}`);
        console.log('Valid types: rollout, voting, routing, threshold, summary, all');
        process.exit(1);
    }

    console.log('\n✅ Example completed successfully\n');
    process.exit(0);

  } catch (error) {
    console.error('\n❌ Error running example:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  exampleRolloutExperiment,
  exampleVotingExperiment,
  exampleRoutingExperiment,
  exampleQualityThresholdExperiment,
  exampleSummary,
};
