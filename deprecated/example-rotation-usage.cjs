/**
 * Example: Model Rotation Policy Usage
 *
 * Shows how to integrate rotation policy into weighted voting workflows.
 *
 * Created: 2026-06-28
 */

const {
  runWeightedVoting,
} = require('./weighted-voting.cjs');

const {
  initializeSchema,
  registerModel,
  recordExecution,
  detectStaleModels,
  forceExploration,
  getRotationStatus,
  generateRotationReport,
} = require('./model-rotation.cjs');

// ============================================================================
// EXAMPLE 1: Basic Integration
// ============================================================================

async function exampleBasicIntegration() {
  console.log('=== Example 1: Basic Integration ===\n');

  // Initialize schema (once per deployment)
  await initializeSchema();

  // Register models at different stages
  await registerModel('new-experimental-model', { stage: 'canary' }); // 1% traffic
  await registerModel('proven-model', { stage: 'full' });             // 100% traffic

  // Create mock votes
  const votes = [
    { model: 'new-experimental-model', answer: 'A', confidence: 0.85 },
    { model: 'proven-model', answer: 'B', confidence: 0.90 },
    { model: 'opus', answer: 'B', confidence: 0.92 },
    { model: 'sonnet', answer: 'B', confidence: 0.88 },
  ];

  // Run weighted voting (rotation policy auto-applied)
  const result = await runWeightedVoting(votes, 'code_review');

  console.log('Voting result:', result.voting_result.winner);
  console.log('\nRotation analysis:', result.voting_result.rotation_analysis);

  // Record execution for rotation tracking
  const success = result.voting_result.status === 'success';
  const quality = result.voting_result.winner.consensus_strength;

  for (const vote of votes) {
    await recordExecution(vote.model, success, quality);
  }

  console.log('\n✅ Basic integration complete\n');
}

// ============================================================================
// EXAMPLE 2: Periodic Staleness Check
// ============================================================================

async function exampleStalenessCheck() {
  console.log('=== Example 2: Periodic Staleness Check ===\n');

  // Detect stale models (run daily)
  const staleModels = await detectStaleModels();

  if (staleModels.length > 0) {
    console.log(`Found ${staleModels.length} stale models:`);
    staleModels.forEach(m => {
      console.log(`  - ${m.model}: ${m.days_since_execution} days since last execution`);
    });

    // Force exploration on random stale model
    const exploredModel = await forceExploration();
    console.log(`\n🔍 Forced exploration: ${exploredModel}`);
  } else {
    console.log('No stale models detected');
  }

  console.log('\n✅ Staleness check complete\n');
}

// ============================================================================
// EXAMPLE 3: Rotation Monitoring
// ============================================================================

async function exampleRotationMonitoring() {
  console.log('=== Example 3: Rotation Monitoring ===\n');

  // Get detailed rotation status
  const status = await getRotationStatus();

  console.log('Current rotation status:');
  console.table(status.map(s => ({
    model: s.model,
    stage: s.rollout_stage,
    traffic: s.traffic_percent + '%',
    executions: s.total_executions,
    quality: parseFloat(s.avg_quality).toFixed(2),
    stale: s.is_stale ? 'YES' : 'NO',
  })));

  // Generate summary report
  const report = await generateRotationReport();
  console.log('\nRotation summary:');
  console.log(`  Total models: ${report.total_models}`);
  console.log(`  Canary: ${report.by_stage.canary}`);
  console.log(`  Ramp: ${report.by_stage.ramp}`);
  console.log(`  Full: ${report.by_stage.full}`);
  console.log(`  Stale: ${report.stale_models}`);
  console.log(`  Exploration active: ${report.exploration_active}`);

  console.log('\n✅ Rotation monitoring complete\n');
}

// ============================================================================
// EXAMPLE 4: Cron Job Integration
// ============================================================================

async function exampleCronJob() {
  console.log('=== Example 4: Daily Cron Job ===\n');

  console.log('Daily rotation maintenance tasks:');

  // Task 1: Detect and explore stale models
  console.log('\n1. Checking for stale models...');
  const staleModels = await detectStaleModels();
  if (staleModels.length > 0) {
    console.log(`   Found ${staleModels.length} stale models`);
    const explored = await forceExploration();
    console.log(`   Forced exploration: ${explored}`);
  } else {
    console.log('   No stale models');
  }

  // Task 2: Generate rotation report
  console.log('\n2. Generating rotation report...');
  const report = await generateRotationReport();
  console.log(`   Total models: ${report.total_models}`);
  console.log(`   Stale: ${report.stale_models}`);
  console.log(`   Canary: ${report.by_stage.canary}`);
  console.log(`   Ramp: ${report.by_stage.ramp}`);
  console.log(`   Full: ${report.by_stage.full}`);

  // Task 3: Alert on anomalies
  console.log('\n3. Checking for anomalies...');
  if (report.stale_models > report.total_models * 0.3) {
    console.warn('   ⚠️  WARNING: >30% of models are stale!');
  } else {
    console.log('   No anomalies detected');
  }

  console.log('\n✅ Daily cron job complete\n');
}

// ============================================================================
// RUN EXAMPLES
// ============================================================================

async function runAllExamples() {
  console.log('╔═══════════════════════════════════════════════════════╗');
  console.log('║   Model Rotation Policy Usage Examples               ║');
  console.log('╚═══════════════════════════════════════════════════════╝\n');

  try {
    await exampleBasicIntegration();
    await exampleStalenessCheck();
    await exampleRotationMonitoring();
    await exampleCronJob();

    console.log('╔═══════════════════════════════════════════════════════╗');
    console.log('║   ✅ ALL EXAMPLES COMPLETE                           ║');
    console.log('╚═══════════════════════════════════════════════════════╝\n');

  } catch (err) {
    console.error('❌ Example failed:', err.message);
    console.error(err.stack);
  }
}

// Run if called directly
if (require.main === module) {
  runAllExamples()
    .then(() => process.exit(0))
    .catch(err => {
      console.error('Fatal error:', err);
      process.exit(1);
    });
}

module.exports = {
  exampleBasicIntegration,
  exampleStalenessCheck,
  exampleRotationMonitoring,
  exampleCronJob,
};
