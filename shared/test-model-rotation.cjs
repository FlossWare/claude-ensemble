/**
 * Model Rotation Policy Tests
 *
 * Test rotation scenarios:
 * 1. New model registration (canary → ramp → full)
 * 2. Forced exploration (stale models)
 * 3. Auto-promotion (quality thresholds)
 * 4. Auto-demotion (quality degradation)
 * 5. Traffic allocation in weighted voting
 *
 * Created: 2026-06-28
 */

const {
  initializeSchema,
  registerModel,
  recordExecution,
  detectStaleModels,
  forceExploration,
  clearExplorationFlag,
  checkAutoPromotion,
  promoteModel,
  demoteModel,
  getTrafficMultiplier,
  applyRotationPolicy,
  getRotationStatus,
  generateRotationReport,
  ROTATION_CONFIG,
  pool,
} = require('./model-rotation.cjs');

// ============================================================================
// TEST HELPERS
// ============================================================================

/**
 * Clean test data from database
 */
async function cleanTestData() {
  const client = await pool.connect();
  try {
    await client.query('DELETE FROM workflow.model_rotation_schedule WHERE model LIKE $1', ['test-%']);
    console.log('✓ Test data cleaned');
  } finally {
    client.release();
  }
}

/**
 * Simulate passage of time (update timestamps)
 */
async function simulateTimePassed(model, days) {
  const client = await pool.connect();
  try {
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         stage_started_at = stage_started_at - INTERVAL '${days} days',
         last_execution_at = last_execution_at - INTERVAL '${days} days'
       WHERE model = $1`,
      [model]
    );
    console.log(`  ⏱  Simulated ${days} days passed for ${model}`);
  } finally {
    client.release();
  }
}

/**
 * Assert helper
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

// ============================================================================
// TEST SCENARIOS
// ============================================================================

/**
 * Test 1: New model registration and graduated rollout
 */
async function testGraduatedRollout() {
  console.log('\n=== Test 1: Graduated Rollout ===\n');

  const modelName = 'test-new-model';

  // Step 1: Register as canary
  const reg = await registerModel(modelName, { stage: 'canary' });
  console.log('Step 1: Register canary');
  console.log(reg);
  assert(reg.status === 'registered', 'Registration failed');
  assert(reg.traffic_percent === 1, 'Canary should be 1% traffic');

  // Step 2: Record executions (high quality)
  console.log('\nStep 2: Record 15 high-quality executions');
  for (let i = 0; i < 15; i++) {
    await recordExecution(modelName, true, 0.85);
  }

  // Step 3: Simulate 4 days passing
  await simulateTimePassed(modelName, 4);

  // Step 4: Check auto-promotion
  console.log('\nStep 4: Check auto-promotion eligibility');
  const promoCheck = await checkAutoPromotion(modelName);
  console.log(promoCheck);
  assert(promoCheck.promote === true, 'Should be eligible for promotion');
  assert(promoCheck.to_stage === 'ramp', 'Should promote to ramp');

  // Step 5: Promote to ramp
  console.log('\nStep 5: Promote to ramp');
  const promo = await promoteModel(modelName);
  console.log(promo);
  assert(promo.status === 'promoted', 'Promotion failed');
  assert(promo.to_stage === 'ramp', 'Should be at ramp stage');
  assert(promo.new_traffic_percent === 10, 'Ramp should be 10% traffic');

  // Step 6: Record more executions
  console.log('\nStep 6: Record 20 more high-quality executions');
  for (let i = 0; i < 20; i++) {
    await recordExecution(modelName, true, 0.88);
  }

  // Step 7: Simulate 8 days passing
  await simulateTimePassed(modelName, 8);

  // Step 8: Promote to full
  console.log('\nStep 8: Promote to full');
  const promo2 = await promoteModel(modelName);
  console.log(promo2);
  assert(promo2.status === 'promoted', 'Second promotion failed');
  assert(promo2.to_stage === 'full', 'Should be at full stage');
  assert(promo2.new_traffic_percent === 100, 'Full should be 100% traffic');

  console.log('\n✅ Test 1 PASSED: Graduated rollout canary → ramp → full\n');
}

/**
 * Test 2: Forced exploration of stale models
 */
async function testForcedExploration() {
  console.log('\n=== Test 2: Forced Exploration ===\n');

  const modelName = 'test-stale-model';

  // Step 1: Register and execute once
  console.log('Step 1: Register and execute once');
  await registerModel(modelName, { stage: 'ramp' });
  await recordExecution(modelName, true, 0.75);

  // Step 2: Simulate 8 days of inactivity
  await simulateTimePassed(modelName, 8);

  // Step 3: Detect stale models
  console.log('\nStep 3: Detect stale models');
  const staleModels = await detectStaleModels();
  console.log(staleModels);
  assert(staleModels.length > 0, 'Should detect stale models');
  assert(staleModels.some(m => m.model === modelName), 'test-stale-model should be stale');

  // Step 4: Force exploration
  console.log('\nStep 4: Force exploration');
  const exploredModel = await forceExploration();
  console.log(`Forced exploration on: ${exploredModel}`);

  // Step 5: Check traffic multiplier (should have exploration boost)
  console.log('\nStep 5: Check traffic multiplier with exploration boost');
  const multiplier = await getTrafficMultiplier(exploredModel);
  console.log(`Traffic multiplier: ${multiplier}`);

  // Get the model's stage to determine expected base traffic
  const client = await pool.connect();
  let expectedBase;
  try {
    const result = await client.query(
      `SELECT rollout_stage, traffic_percent FROM workflow.model_rotation_schedule WHERE model = $1`,
      [exploredModel]
    );
    expectedBase = result.rows[0].traffic_percent / 100.0;
    console.log(`  Base traffic for ${result.rows[0].rollout_stage}: ${expectedBase * 100}%`);
  } finally {
    client.release();
  }

  assert(
    multiplier >= expectedBase,
    `Exploration boost should be >= base traffic (${expectedBase})`
  );

  // Step 6: Clear exploration flag
  console.log('\nStep 6: Clear exploration flag');
  await clearExplorationFlag(exploredModel);
  const multiplier2 = await getTrafficMultiplier(exploredModel);
  console.log(`Traffic multiplier after clear: ${multiplier2}`);
  assert(
    multiplier2 === expectedBase,
    `Should revert to base traffic (${expectedBase})`
  );

  console.log('\n✅ Test 2 PASSED: Forced exploration of stale models\n');
}

/**
 * Test 3: Auto-demotion on quality degradation
 */
async function testAutoDemotion() {
  console.log('\n=== Test 3: Auto-Demotion ===\n');

  const modelName = 'test-demote-model';

  // Step 1: Register at full stage
  console.log('Step 1: Register at full stage (simulating previous promotion)');
  await registerModel(modelName, { stage: 'full' });

  // Step 2: Record high-quality executions
  console.log('\nStep 2: Record 10 high-quality executions');
  for (let i = 0; i < 10; i++) {
    await recordExecution(modelName, true, 0.85);
  }

  // Step 3: Record low-quality failures (degradation)
  console.log('\nStep 3: Record 15 low-quality failures');
  for (let i = 0; i < 15; i++) {
    await recordExecution(modelName, false, 0.35);
  }

  // Step 4: Demote to ramp
  console.log('\nStep 4: Demote to ramp');
  const demote = await demoteModel(modelName, 'quality_degradation');
  console.log(demote);
  assert(demote.status === 'demoted', 'Demotion failed');
  assert(demote.to_stage === 'ramp', 'Should demote to ramp');
  assert(demote.new_traffic_percent === 10, 'Ramp should be 10% traffic');

  console.log('\n✅ Test 3 PASSED: Auto-demotion on quality degradation\n');
}

/**
 * Test 4: Traffic allocation in weighted voting
 */
async function testTrafficAllocation() {
  console.log('\n=== Test 4: Traffic Allocation ===\n');

  const models = ['test-canary', 'test-ramp', 'test-full'];

  // Step 1: Register models at different stages
  console.log('Step 1: Register models at different stages');
  await registerModel(models[0], { stage: 'canary' }); // 1%
  await registerModel(models[1], { stage: 'ramp' });   // 10%
  await registerModel(models[2], { stage: 'full' });   // 100%

  // Step 2: Create mock votes
  console.log('\nStep 2: Create mock votes');
  const votes = [
    { model: models[0], weight: 0.8, answer: 'A' },
    { model: models[1], weight: 0.8, answer: 'A' },
    { model: models[2], weight: 0.8, answer: 'A' },
  ];

  // Step 3: Apply rotation policy
  console.log('\nStep 3: Apply rotation policy');
  const rotatedVotes = await applyRotationPolicy(votes);
  console.log(rotatedVotes);

  // Verify traffic multipliers
  assert(rotatedVotes[0].rotation_multiplier === 0.01, 'Canary should be 1%');
  assert(rotatedVotes[1].rotation_multiplier === 0.10, 'Ramp should be 10%');
  assert(rotatedVotes[2].rotation_multiplier === 1.00, 'Full should be 100%');

  // Verify adjusted weights
  assert(
    Math.abs(rotatedVotes[0].rotation_adjusted_weight - 0.008) < 0.001,
    'Canary weight should be 0.8 * 0.01 = 0.008'
  );
  assert(
    Math.abs(rotatedVotes[1].rotation_adjusted_weight - 0.08) < 0.001,
    'Ramp weight should be 0.8 * 0.10 = 0.08'
  );
  assert(
    Math.abs(rotatedVotes[2].rotation_adjusted_weight - 0.8) < 0.001,
    'Full weight should be 0.8 * 1.00 = 0.8'
  );

  console.log('\n✅ Test 4 PASSED: Traffic allocation in weighted voting\n');
}

/**
 * Test 5: Rotation status and reporting
 */
async function testRotationReporting() {
  console.log('\n=== Test 5: Rotation Reporting ===\n');

  // Step 1: Get rotation status
  console.log('Step 1: Get rotation status');
  const status = await getRotationStatus();
  console.log(`Total models tracked: ${status.length}`);
  console.table(status.map(s => ({
    model: s.model,
    stage: s.rollout_stage,
    traffic: s.traffic_percent + '%',
    executions: s.total_executions,
    quality: parseFloat(s.avg_quality).toFixed(2),
    stale: s.is_stale ? 'YES' : 'NO',
  })));

  // Step 2: Generate report
  console.log('\nStep 2: Generate rotation report');
  const report = await generateRotationReport();
  console.log(report);

  console.log('\n✅ Test 5 PASSED: Rotation status and reporting\n');
}

/**
 * Test 6: Edge cases
 */
async function testEdgeCases() {
  console.log('\n=== Test 6: Edge Cases ===\n');

  const modelName = 'test-edge-case';

  // Edge case 1: Promote with insufficient samples
  console.log('Edge case 1: Promote with insufficient samples');
  await registerModel(modelName, { stage: 'canary' });
  await recordExecution(modelName, true, 0.90);
  await simulateTimePassed(modelName, 5);

  const promoCheck = await checkAutoPromotion(modelName);
  console.log(promoCheck);
  assert(promoCheck.promote === false, 'Should not promote with insufficient samples');
  assert(promoCheck.reason === 'insufficient_samples', 'Reason should be insufficient_samples');

  // Edge case 2: Demote canary (should fail)
  console.log('\nEdge case 2: Demote canary (should fail)');
  const demote = await demoteModel(modelName, 'test');
  console.log(demote);
  assert(demote.status === 'cannot_demote', 'Should not demote canary');

  // Edge case 3: Auto-register untracked model
  console.log('\nEdge case 3: Auto-register untracked model');
  const untracked = 'test-untracked';
  await recordExecution(untracked, true, 0.80);
  const multiplier = await getTrafficMultiplier(untracked);
  console.log(`Untracked model traffic: ${multiplier * 100}%`);
  assert(multiplier === 0.01, 'Should auto-register as canary (1%)');

  console.log('\n✅ Test 6 PASSED: Edge cases handled correctly\n');
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runAllTests() {
  console.log('╔═══════════════════════════════════════════════════════╗');
  console.log('║   Model Rotation Policy Test Suite                   ║');
  console.log('╚═══════════════════════════════════════════════════════╝');

  try {
    // Initialize schema
    console.log('\nInitializing schema...');
    await initializeSchema();

    // Clean previous test data
    await cleanTestData();

    // Run tests
    await testGraduatedRollout();
    await testForcedExploration();
    await testAutoDemotion();
    await testTrafficAllocation();
    await testRotationReporting();
    await testEdgeCases();

    console.log('\n╔═══════════════════════════════════════════════════════╗');
    console.log('║   ✅ ALL TESTS PASSED                                ║');
    console.log('╚═══════════════════════════════════════════════════════╝\n');

  } catch (err) {
    console.error('\n❌ TEST FAILED:', err.message);
    console.error(err.stack);
    process.exit(1);
  } finally {
    // Cleanup
    await cleanTestData();
    await pool.end();
  }
}

// Run if called directly
if (require.main === module) {
  runAllTests().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

module.exports = {
  runAllTests,
  testGraduatedRollout,
  testForcedExploration,
  testAutoDemotion,
  testTrafficAllocation,
  testRotationReporting,
  testEdgeCases,
};
