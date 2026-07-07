#!/usr/bin/env node
/**
 * Test Resource Estimation Learning System (Issue #109)
 *
 * Demonstrates:
 * 1. Recording actual resource usage
 * 2. Triggering automatic retraining
 * 3. Getting learned estimates
 * 4. Comparing heuristic vs learned estimates
 *
 * Usage:
 *   node tools/test-resource-estimation.js
 */

const {
  learnFromExecution,
  getLearnedEstimate,
  getLearningStats,
  forceRetrain
} = require('../shared/resource-estimation-learner.cjs');

// Simulate realistic job executions
const testJobs = [
  // Short prompts, simple jobs
  { prompt_length: 100, model: 'haiku', schema_complexity: 0, job_type: 'agent', actual_duration: 12, actual_ram: 0.6 },
  { prompt_length: 150, model: 'haiku', schema_complexity: 2, job_type: 'data-extraction', actual_duration: 8, actual_ram: 0.5 },
  { prompt_length: 200, model: 'sonnet', schema_complexity: 0, job_type: 'agent', actual_duration: 18, actual_ram: 0.8 },

  // Medium prompts, moderate complexity
  { prompt_length: 800, model: 'sonnet', schema_complexity: 5, job_type: 'code-review', actual_duration: 35, actual_ram: 1.2 },
  { prompt_length: 900, model: 'sonnet', schema_complexity: 8, job_type: 'ai-heavy', actual_duration: 42, actual_ram: 1.5 },
  { prompt_length: 1000, model: 'opus', schema_complexity: 3, job_type: 'agent', actual_duration: 48, actual_ram: 1.8 },
  { prompt_length: 1200, model: 'opus', schema_complexity: 10, job_type: 'code-review', actual_duration: 55, actual_ram: 2.1 },
  { prompt_length: 1500, model: 'sonnet', schema_complexity: 0, job_type: 'code-execute', actual_duration: 65, actual_ram: 1.6 },

  // Long prompts, complex jobs
  { prompt_length: 2500, model: 'opus', schema_complexity: 15, job_type: 'ai-heavy', actual_duration: 85, actual_ram: 2.8 },
  { prompt_length: 3000, model: 'opus', schema_complexity: 20, job_type: 'ai-consensus', actual_duration: 95, actual_ram: 3.2 },
  { prompt_length: 3500, model: 'gpt-4o', schema_complexity: 12, job_type: 'code-review', actual_duration: 78, actual_ram: 2.5 },
  { prompt_length: 4000, model: 'sonnet', schema_complexity: 8, job_type: 'ai-heavy', actual_duration: 92, actual_ram: 2.2 },
  { prompt_length: 4500, model: 'opus', schema_complexity: 25, job_type: 'code-execute', actual_duration: 110, actual_ram: 3.5 },
  { prompt_length: 5000, model: 'opus', schema_complexity: 30, job_type: 'ai-consensus', actual_duration: 125, actual_ram: 3.8 },

  // Very long prompts
  { prompt_length: 6000, model: 'opus', schema_complexity: 35, job_type: 'ai-heavy', actual_duration: 145, actual_ram: 4.0 },
];

async function runTest() {
  console.log('\n🧪 Testing Resource Estimation Learning System (Issue #109)\n');
  console.log('='.repeat(80));

  // Step 1: Show initial state
  console.log('\n--- Step 1: Initial State ---');
  let stats = await getLearningStats();
  console.log(`Total jobs tracked: ${stats.total_jobs}`);
  console.log(`Retrain count: ${stats.retrain_count}`);
  console.log(`Current model MAE: ${stats.current_duration_mae ? stats.current_duration_mae.toFixed(2) + 's' : 'N/A'}`);

  // Step 2: Record training data
  console.log('\n--- Step 2: Recording Training Data ---');
  console.log(`Simulating ${testJobs.length} job executions...`);

  for (let i = 0; i < testJobs.length; i++) {
    const job = testJobs[i];

    // Get heuristic estimate (for comparison)
    const { estimateResources } = await import('../skills/misc/fleet-agent-dispatcher.js');
    const heuristicEst = await estimateResources(
      'x'.repeat(job.prompt_length),
      job.model,
      job.schema_complexity > 0 ? { properties: {} } : null,
      job.job_type
    );

    // Record actual usage
    const result = await learnFromExecution({
      prompt_length: job.prompt_length,
      model: job.model,
      schema_complexity: job.schema_complexity,
      job_type: job.job_type,
      actual_duration: job.actual_duration,
      actual_ram: job.actual_ram,
      estimated_duration: heuristicEst.duration,
      estimated_ram: heuristicEst.ram
    });

    const status = result.high_error ? '⚠️ ' : '✅';
    console.log(`  ${status} Job ${i + 1}/${testJobs.length}: ${job.model}/${job.job_type} (${job.prompt_length} chars) - Error: ${(result.duration_error * 100).toFixed(0)}%`);

    // Small delay to avoid overwhelming the system
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  // Step 3: Check if retraining happened
  console.log('\n--- Step 3: Checking Retraining Status ---');
  stats = await getLearningStats();
  console.log(`Jobs since last retrain: ${stats.jobs_since_retrain}`);
  console.log(`Consecutive high errors: ${stats.consecutive_high_errors}`);

  if (stats.retrain_count === 0) {
    console.log('\n⚠️  Not enough data yet, forcing retrain...');
    await forceRetrain();
  }

  // Step 4: Compare estimates
  console.log('\n--- Step 4: Comparing Heuristic vs Learned Estimates ---');
  console.log('');
  console.log('Test Case                          | Heuristic        | Learned          | Actual           | Improvement');
  console.log('-'.repeat(120));

  const testCases = [
    { prompt_length: 500, model: 'sonnet', schema_complexity: 3, job_type: 'agent', actual_duration: 25, actual_ram: 1.0 },
    { prompt_length: 1500, model: 'opus', schema_complexity: 10, job_type: 'code-review', actual_duration: 58, actual_ram: 2.2 },
    { prompt_length: 3000, model: 'opus', schema_complexity: 20, job_type: 'ai-heavy', actual_duration: 90, actual_ram: 3.0 },
    { prompt_length: 5000, model: 'gpt-4o', schema_complexity: 15, job_type: 'code-execute', actual_duration: 115, actual_ram: 3.3 },
  ];

  for (const testCase of testCases) {
    // Heuristic estimate
    const { estimateResources } = await import('../skills/misc/fleet-agent-dispatcher.js');
    const heuristic = await estimateResources(
      'x'.repeat(testCase.prompt_length),
      testCase.model,
      testCase.schema_complexity > 0 ? { properties: {} } : null,
      testCase.job_type
    );

    // Learned estimate
    const learned = await getLearnedEstimate({
      prompt_length: testCase.prompt_length,
      model: testCase.model,
      schema_complexity: testCase.schema_complexity,
      job_type: testCase.job_type
    });

    const caseDesc = `${testCase.model}/${testCase.job_type} (${testCase.prompt_length})`.padEnd(35);
    const heuristicStr = `${heuristic.duration}s / ${heuristic.ram}GB`.padEnd(17);
    const learnedStr = learned ? `${learned.duration}s / ${learned.ram}GB`.padEnd(17) : 'N/A'.padEnd(17);
    const actualStr = `${testCase.actual_duration}s / ${testCase.actual_ram}GB`.padEnd(17);

    const heuristicError = Math.abs(heuristic.duration - testCase.actual_duration);
    const learnedError = learned ? Math.abs(learned.duration - testCase.actual_duration) : 999;
    const improvement = ((heuristicError - learnedError) / heuristicError * 100).toFixed(0);

    console.log(`${caseDesc} | ${heuristicStr} | ${learnedStr} | ${actualStr} | ${improvement}%`);
  }

  console.log('='.repeat(120));

  // Step 5: Final statistics
  console.log('\n--- Step 5: Final Statistics ---');
  stats = await getLearningStats();
  console.log(`Total jobs tracked: ${stats.total_jobs}`);
  console.log(`Retrain count: ${stats.retrain_count}`);
  console.log(`Current duration MAE: ${stats.current_duration_mae ? stats.current_duration_mae.toFixed(2) + 's' : 'N/A'}`);
  console.log(`Current RAM MAE: ${stats.current_ram_mae ? stats.current_ram_mae.toFixed(3) + 'GB' : 'N/A'}`);
  console.log(`Improvement vs baseline: ${stats.improvement_pct ? stats.improvement_pct.toFixed(1) + '%' : 'N/A'}`);
  console.log(`Avg 7-day duration error: ${(stats.avg_duration_error_7d * 100).toFixed(1)}%`);
  console.log(`Avg 7-day RAM error: ${(stats.avg_ram_error_7d * 100).toFixed(1)}%`);

  console.log('\n✅ Test complete!\n');
  console.log('Next steps:');
  console.log('  - Check stats: node tools/resource-estimation-cli.js stats');
  console.log('  - View recent jobs: node tools/resource-estimation-cli.js recent');
  console.log('  - Check accuracy: node tools/resource-estimation-cli.js accuracy');
  console.log('');
}

runTest()
  .then(() => {
    require('../shared/resource-estimation-learner.cjs').pool.end();
    process.exit(0);
  })
  .catch(error => {
    console.error('\n❌ Test failed:', error);
    console.error(error.stack);
    require('../shared/resource-estimation-learner.cjs').pool.end();
    process.exit(1);
  });
