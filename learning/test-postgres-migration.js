#!/usr/bin/env node
/**
 * Test Script: PostgreSQL Migration Verification
 *
 * Validates that thompson-sampling.js correctly uses PostgreSQL adapter
 * instead of legacy JSON file I/O.
 *
 * Usage:
 *   node learning/test-postgres-migration.js
 */

import { selectModel, updateModel, getModelStats, getAllModelStats, resetModel, exportState } from './thompson-sampling.js';
import { getStrategyPerformance } from './postgres-adapter.js';

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✓ ${message}`);
    testsPassed++;
  } else {
    console.error(`  ✗ ${message}`);
    testsFailed++;
    throw new Error(`Assertion failed: ${message}`);
  }
}

function assertAlmostEqual(a, b, tolerance, message) {
  const diff = Math.abs(a - b);
  if (diff <= tolerance) {
    console.log(`  ✓ ${message} (${a} ≈ ${b})`);
    testsPassed++;
  } else {
    console.error(`  ✗ ${message} (${a} != ${b}, diff=${diff})`);
    testsFailed++;
    throw new Error(`Assertion failed: ${message}`);
  }
}

// ============================================================================
// TESTS
// ============================================================================

async function testPostgreSQLConnection() {
  console.log('\n=== Test 1: PostgreSQL Connection ===\n');

  const sp = getStrategyPerformance();
  assert(sp !== null, 'PostgreSQL adapter initialized');

  const allStrategies = await sp.getAllStrategies();
  console.log(`  Found ${allStrategies.length} strategies in PostgreSQL`);
  assert(allStrategies.length >= 0, 'Can query PostgreSQL');
}

async function testResetModel() {
  console.log('\n=== Test 2: Reset Model ===\n');

  const testModel = 'test-model-' + Date.now();

  // Reset (should create with uniform prior)
  await resetModel(testModel);
  console.log(`  Reset ${testModel}`);

  // Verify state
  const stats = await getModelStats(testModel);
  assert(stats.alpha === 1, 'Alpha initialized to 1');
  assert(stats.beta === 1, 'Beta initialized to 1');
  assert(stats.total === 0, 'Total initialized to 0');
  assert(stats.avg_quality === 0, 'Avg quality initialized to 0');
}

async function testUpdateModel() {
  console.log('\n=== Test 3: Update Model ===\n');

  const testModel = 'test-model-' + Date.now();

  // Reset first
  await resetModel(testModel);

  // Update with success (quality >= 0.7)
  await updateModel(testModel, 0.85);
  console.log(`  Updated ${testModel} with quality=0.85`);

  // Verify state
  let stats = await getModelStats(testModel);
  assert(stats.alpha === 2, 'Alpha incremented (success)');
  assert(stats.beta === 1, 'Beta unchanged (success)');
  assert(stats.total === 1, 'Total incremented');
  assertAlmostEqual(stats.avg_quality, 0.85, 0.01, 'Avg quality updated');

  // Update with failure (quality < 0.7)
  await updateModel(testModel, 0.5);
  console.log(`  Updated ${testModel} with quality=0.5`);

  // Verify state
  stats = await getModelStats(testModel);
  assert(stats.alpha === 2, 'Alpha unchanged (failure)');
  assert(stats.beta === 2, 'Beta incremented (failure)');
  assert(stats.total === 2, 'Total incremented');
  assertAlmostEqual(stats.avg_quality, 0.675, 0.01, 'Avg quality updated');
}

async function testSelectModel() {
  console.log('\n=== Test 4: Select Model ===\n');

  const testModel1 = 'test-model-a-' + Date.now();
  const testModel2 = 'test-model-b-' + Date.now();
  const testModel3 = 'test-model-c-' + Date.now();

  // Reset all
  await resetModel(testModel1);
  await resetModel(testModel2);
  await resetModel(testModel3);

  // Give model2 better stats
  await updateModel(testModel1, 0.5);  // Failure
  await updateModel(testModel2, 0.9);  // Success
  await updateModel(testModel2, 0.8);  // Success
  await updateModel(testModel3, 0.6);  // Failure

  // Select model (should favor model2)
  const selections = {};
  for (let i = 0; i < 100; i++) {
    const selected = await selectModel([testModel1, testModel2, testModel3]);
    selections[selected] = (selections[selected] || 0) + 1;
  }

  console.log(`  Selection distribution (100 trials):`);
  console.log(`    ${testModel1}: ${selections[testModel1] || 0}`);
  console.log(`    ${testModel2}: ${selections[testModel2] || 0}`);
  console.log(`    ${testModel3}: ${selections[testModel3] || 0}`);

  // Model2 should be selected most (but not always due to Thompson Sampling exploration)
  assert(selections[testModel2] > selections[testModel1], 'Best model selected more often');
  assert(selections[testModel2] > selections[testModel3], 'Best model selected more often');
  assert(selections[testModel1] > 0 || selections[testModel3] > 0, 'Exploration still occurs');
}

async function testGetAllModelStats() {
  console.log('\n=== Test 5: Get All Model Stats ===\n');

  const allStats = await getAllModelStats();
  console.log(`  Found ${allStats.length} models`);
  assert(allStats.length >= 0, 'Can retrieve all model stats');

  if (allStats.length > 0) {
    const firstModel = allStats[0];
    assert(typeof firstModel.model === 'string', 'Model has name');
    assert(typeof firstModel.alpha === 'number', 'Model has alpha');
    assert(typeof firstModel.beta === 'number', 'Model has beta');
    assert(typeof firstModel.total === 'number', 'Model has total');
    assert(typeof firstModel.avg_quality === 'number', 'Model has avg_quality');
    assert(typeof firstModel.success_rate === 'number', 'Model has success_rate');
    assert(typeof firstModel.uncertainty === 'number', 'Model has uncertainty');
  }
}

async function testExportState() {
  console.log('\n=== Test 6: Export State ===\n');

  const state = await exportState();
  console.log(`  Exported state version ${state.version}`);

  assert(state.version === 1, 'State has version');
  assert(typeof state.created === 'string', 'State has created timestamp');
  assert(typeof state.updated === 'string', 'State has updated timestamp');
  assert(typeof state.models === 'object', 'State has models object');
  assert(state.notes.includes('PostgreSQL'), 'State notes indicate PostgreSQL source');

  const modelCount = Object.keys(state.models).length;
  console.log(`  Exported ${modelCount} models`);
  assert(modelCount >= 0, 'State contains models');
}

async function testConcurrentUpdates() {
  console.log('\n=== Test 7: Concurrent Updates (Race Condition) ===\n');

  const testModel = 'test-model-concurrent-' + Date.now();

  // Reset
  await resetModel(testModel);

  // Concurrent updates (10 parallel)
  const updates = [];
  for (let i = 0; i < 10; i++) {
    updates.push(updateModel(testModel, 0.75 + (i * 0.01)));
  }

  await Promise.all(updates);
  console.log(`  Completed 10 concurrent updates`);

  // Verify state (should have all 10 updates)
  const stats = await getModelStats(testModel);
  assert(stats.total === 10, 'All concurrent updates recorded (no lost writes)');
  console.log(`  Alpha: ${stats.alpha}, Beta: ${stats.beta}, Total: ${stats.total}`);
}

async function testDataConsistency() {
  console.log('\n=== Test 8: Data Consistency Check ===\n');

  const sp = getStrategyPerformance();

  // Query directly from PostgreSQL
  const pgModels = await sp.getAllStrategies();

  // Query via thompson-sampling API
  const tsModels = await getAllModelStats();

  console.log(`  PostgreSQL: ${pgModels.length} models`);
  console.log(`  Thompson Sampling: ${tsModels.length} models`);

  assert(pgModels.length === tsModels.length, 'Model count consistent');

  // Verify each model matches
  for (const pgModel of pgModels) {
    const tsModel = tsModels.find(m => m.model === pgModel.strategy);
    assert(tsModel !== undefined, `Model ${pgModel.strategy} found in both`);

    if (tsModel) {
      assertAlmostEqual(tsModel.alpha, parseFloat(pgModel.alpha), 0.01, `Alpha matches for ${pgModel.strategy}`);
      assertAlmostEqual(tsModel.beta, parseFloat(pgModel.beta), 0.01, `Beta matches for ${pgModel.strategy}`);
    }
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║  PostgreSQL Migration Tests                                  ║');
  console.log('╚══════════════════════════════════════════════════════════════╝');

  try {
    await testPostgreSQLConnection();
    await testResetModel();
    await testUpdateModel();
    await testSelectModel();
    await testGetAllModelStats();
    await testExportState();
    await testConcurrentUpdates();
    await testDataConsistency();

    console.log('\n╔══════════════════════════════════════════════════════════════╗');
    console.log('║  Test Results                                                ║');
    console.log('╚══════════════════════════════════════════════════════════════╝');
    console.log(`\n✓ Passed: ${testsPassed}`);
    console.log(`✗ Failed: ${testsFailed}`);

    if (testsFailed === 0) {
      console.log('\n✓ All tests passed! PostgreSQL migration successful.\n');
      process.exit(0);
    } else {
      console.log(`\n✗ ${testsFailed} test(s) failed. Review output above.\n`);
      process.exit(1);
    }
  } catch (err) {
    console.error(`\n✗ Test suite failed: ${err.message}`);
    if (process.env.LEARNING_DEBUG) {
      console.error(err.stack);
    }
    console.log(`\n✓ Passed: ${testsPassed}`);
    console.log(`✗ Failed: ${testsFailed + 1}`);
    process.exit(1);
  }
}

main();
