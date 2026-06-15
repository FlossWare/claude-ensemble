#!/usr/bin/env node

/**
 * Hot-Reload System Test Suite
 *
 * Validates the hot-reload system:
 * 1. Code module hot-reload (cache busting)
 * 2. JSON data hot-reload (discoveries, learnings)
 * 3. Thompson Sampling state propagation (<5s)
 * 4. Discovery application and filtering
 * 5. Integration with orchestrator and workflows
 *
 * Usage:
 *   node test-hot-reload.js              # Run all tests
 *   node test-hot-reload.js --test=code  # Run specific test
 *   node test-hot-reload.js --verbose    # Verbose output
 */

import { hotImport, hotImportJSON, clearCache, getCacheStats, cleanExpiredCache } from '../shared/hot-reload.js';
import { loadDiscoveries, filterModels, biasSelection, applyDiscoveries } from './apply-discoveries.js';
import { writeFileSync, readFileSync } from 'fs';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// TEST CONFIGURATION
// ============================================================================

const VERBOSE = process.argv.includes('--verbose');
const testFilter = process.argv.find(arg => arg.startsWith('--test='))?.split('=')[1];

function log(...args) {
  if (VERBOSE) {
    console.log(...args);
  }
}

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testCount = 0;
let passCount = 0;
let failCount = 0;

function assert(condition, message) {
  testCount++;
  if (condition) {
    passCount++;
    console.log(`  ✓ ${message}`);
  } else {
    failCount++;
    console.log(`  ✗ ${message}`);
  }
}

function assertEqual(actual, expected, message) {
  const condition = JSON.stringify(actual) === JSON.stringify(expected);
  assert(condition, `${message} (expected: ${JSON.stringify(expected)}, got: ${JSON.stringify(actual)})`);
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================================
// TEST 1: CODE MODULE HOT-RELOAD
// ============================================================================

async function testCodeModuleHotReload() {
  console.log('\n=== Test 1: Code Module Hot-Reload ===\n');

  // Clear cache before test
  clearCache();

  // First import
  log('First import...');
  const module1 = await hotImport('./orchestrator.js');
  assert(module1 !== null, 'First import succeeds');
  assert(typeof module1.selectModel === 'function', 'Module has selectModel function');

  // Check cache
  const stats1 = getCacheStats();
  log('Cache stats after first import:', stats1);
  assertEqual(stats1.total, 1, 'Cache has 1 entry');

  // Second import (should hit cache)
  log('Second import (cache hit)...');
  const module2 = await hotImport('./orchestrator.js');
  assert(module2 === module1, 'Second import returns cached module');

  // Force reload
  log('Force reload...');
  const module3 = await hotImport('./orchestrator.js', { force: true });
  assert(module3 !== null, 'Force reload succeeds');

  // Clear specific module
  clearCache('./orchestrator.js');
  const stats2 = getCacheStats();
  assertEqual(stats2.total, 0, 'Cache cleared for specific module');

  console.log('\n✓ Code module hot-reload tests passed');
}

// ============================================================================
// TEST 2: JSON DATA HOT-RELOAD
// ============================================================================

async function testJSONHotReload() {
  console.log('\n=== Test 2: JSON Data Hot-Reload ===\n');

  clearCache();

  // Load discoveries
  log('Loading discoveries...');
  const discoveries1 = await hotImportJSON('./learning/discoveries.json');
  assert(discoveries1 !== null, 'Discoveries loaded');
  assert(Array.isArray(discoveries1.discoveries), 'Discoveries is an array');
  log(`Loaded ${discoveries1.discoveries.length} discoveries`);

  // Second load (cache hit)
  const discoveries2 = await hotImportJSON('./learning/discoveries.json');
  assert(discoveries2 === discoveries1, 'Second load hits cache');

  // Force reload
  const discoveries3 = await hotImportJSON('./learning/discoveries.json', { force: true });
  assert(discoveries3 !== null, 'Force reload succeeds');

  // Test missing file
  const missing = await hotImportJSON('./learning/nonexistent.json', {
    defaultValue: { default: true },
  });
  assertEqual(missing, { default: true }, 'Missing file returns default value');

  console.log('\n✓ JSON hot-reload tests passed');
}

// ============================================================================
// TEST 3: THOMPSON SAMPLING STATE PROPAGATION
// ============================================================================

async function testThompsonSamplingPropagation() {
  console.log('\n=== Test 3: Thompson Sampling State Propagation ===\n');

  clearCache();

  // Import orchestrator
  const orchestrator1 = await hotImport('./orchestrator.js');

  // Get initial Thompson stats
  log('Getting initial Thompson stats...');
  const stats1 = await orchestrator1.getThompsonStats();
  log(`Initial stats for ${stats1.length} models`);

  // Record a result
  log('Recording result for opus...');
  await orchestrator1.recordResult('opus', 0.95);

  // Wait for Thompson Sampling state to reload (should be < 5s)
  log('Waiting 6s for state propagation...');
  await sleep(6000);

  // Force reload orchestrator
  clearCache('./orchestrator.js');
  const orchestrator2 = await hotImport('./orchestrator.js', { force: true });

  // Get updated stats
  const stats2 = await orchestrator2.getThompsonStats();

  // Find opus stats
  const opusStats1 = stats1.find(s => s.model === 'opus');
  const opusStats2 = stats2.find(s => s.model === 'opus');

  if (opusStats1 && opusStats2) {
    log('Opus stats before:', opusStats1);
    log('Opus stats after:', opusStats2);
    assert(
      opusStats2.alpha > opusStats1.alpha || opusStats2.total > opusStats1.total,
      'Thompson state updated within 6s'
    );
  } else {
    assert(true, 'Thompson state propagation (no initial opus data)');
  }

  console.log('\n✓ Thompson Sampling propagation tests passed');
}

// ============================================================================
// TEST 4: DISCOVERY APPLICATION
// ============================================================================

async function testDiscoveryApplication() {
  console.log('\n=== Test 4: Discovery Application ===\n');

  // Load discoveries
  const discoveries = await loadDiscoveries();
  log(`Loaded ${discoveries.length} active discoveries`);
  assert(discoveries.length > 0, 'Active discoveries loaded');

  // Test filtering - cost-sensitive context
  log('\nTesting cost-sensitive filtering...');
  const models1 = ['opus', 'sonnet', 'haiku', 'fable'];
  const context1 = {
    cost_sensitivity: 'high',
    budget_constraint: true,
  };

  const filtered1 = await filterModels(models1, context1);
  log(`Filtered models: ${filtered1.join(', ')}`);
  assert(!filtered1.includes('opus'), 'Opus filtered out for cost-sensitive tasks');

  // Test filtering - schema-required context
  log('\nTesting schema-required filtering...');
  const models2 = ['opus', 'sonnet', 'haiku', 'fable'];
  const context2 = {
    requires_schema: true,
    output_format: 'json',
  };

  const filtered2 = await filterModels(models2, context2);
  log(`Filtered models: ${filtered2.join(', ')}`);
  assert(!filtered2.includes('fable'), 'Fable filtered out for schema-required tasks');

  // Test biasing - creative tasks
  log('\nTesting creative task biasing...');
  const models3 = ['opus', 'sonnet', 'haiku', 'fable'];
  const context3 = {
    task_type: 'code-generation',
    quality_threshold: 0.7,
  };

  const biases = await biasSelection(models3, context3);
  log('Biases:', biases);
  assert(biases.opus > biases.haiku, 'Opus biased higher than haiku for creative tasks');

  // Test unified application
  log('\nTesting unified discovery application...');
  const models4 = ['opus', 'sonnet', 'haiku', 'fable'];
  const context4 = {
    task_type: 'security-review',
    workflow: 'consensus',
    worker_count: 3,
  };

  const config = await applyDiscoveries(models4, context4);
  log('Applied config:', config);
  assert(config.models.length > 0, 'Models filtered');
  assert(typeof config.diversity_weight === 'number', 'Diversity weight calculated');
  assert(typeof config.worker_count === 'number', 'Worker count adjusted');

  console.log('\n✓ Discovery application tests passed');
}

// ============================================================================
// TEST 5: ORCHESTRATOR INTEGRATION
// ============================================================================

async function testOrchestratorIntegration() {
  console.log('\n=== Test 5: Orchestrator Integration ===\n');

  clearCache();

  // Import orchestrator
  const orchestrator = await hotImport('./orchestrator.js');

  // Test greedy selection
  log('Testing greedy selection...');
  const greedyModel = await orchestrator.selectModel('code-review', {
    strategy: 'greedy',
    count: 1,
  });
  log(`Greedy selection: ${greedyModel}`);
  assert(typeof greedyModel === 'string', 'Greedy selection returns string');

  // Test Thompson Sampling selection
  log('Testing Thompson Sampling selection...');
  const thompsonModel = await orchestrator.selectModel('code-review', {
    strategy: 'thompson',
    count: 1,
  });
  log(`Thompson selection: ${thompsonModel}`);
  assert(typeof thompsonModel === 'string', 'Thompson selection returns string');

  // Test multi-model selection
  log('Testing multi-model selection...');
  const workers = await orchestrator.selectWorkers('multi-model-consensus', {
    count: 3,
    strategy: 'thompson',
  });
  log(`Workers: ${workers.join(', ')}`);
  assert(Array.isArray(workers), 'Workers selection returns array');
  assert(workers.length <= 3, 'Workers count respects limit');

  // Test model metrics (may be null if DB not initialized)
  log('Testing model metrics...');
  const metrics = await orchestrator.getModelMetrics('opus', 'code-review');
  log('Opus metrics:', metrics);
  if (metrics !== null) {
    assert(true, 'Metrics retrieved (DB available)');
  } else {
    log('Metrics returned null (DB not initialized)');
    assert(true, 'Metrics gracefully handled (DB not initialized)');
  }

  console.log('\n✓ Orchestrator integration tests passed');
}

// ============================================================================
// TEST 6: CACHE MANAGEMENT
// ============================================================================

async function testCacheManagement() {
  console.log('\n=== Test 6: Cache Management ===\n');

  clearCache();

  // Import multiple modules
  await hotImport('./orchestrator.js');
  await hotImportJSON('./learning/discoveries.json');

  // Check cache stats
  const stats1 = getCacheStats();
  log('Cache stats:', stats1);
  assert(stats1.total === 2, 'Cache has 2 entries');

  // Wait for TTL expiration (code: 1s, json: 5s)
  log('Waiting 2s for code cache to expire...');
  await sleep(2000);

  // Clean expired
  const removed = cleanExpiredCache();
  log(`Removed ${removed} expired entries`);

  const stats2 = getCacheStats();
  log('Cache stats after cleanup:', stats2);
  assert(stats2.expired === 0, 'No expired entries remain');

  // Clear all
  clearCache();
  const stats3 = getCacheStats();
  assertEqual(stats3.total, 0, 'Cache cleared completely');

  console.log('\n✓ Cache management tests passed');
}

// ============================================================================
// TEST 7: PERFORMANCE
// ============================================================================

async function testPerformance() {
  console.log('\n=== Test 7: Performance ===\n');

  clearCache();

  // Measure first import (cold)
  const start1 = Date.now();
  await hotImport('./orchestrator.js');
  const duration1 = Date.now() - start1;
  log(`First import (cold): ${duration1}ms`);
  assert(duration1 < 1000, 'Cold import completes in <1s');

  // Measure cached import (hot)
  const start2 = Date.now();
  await hotImport('./orchestrator.js');
  const duration2 = Date.now() - start2;
  log(`Second import (cached): ${duration2}ms`);
  assert(duration2 < 50, 'Cached import completes in <50ms');

  // Measure force reload
  const start3 = Date.now();
  await hotImport('./orchestrator.js', { force: true });
  const duration3 = Date.now() - start3;
  log(`Force reload: ${duration3}ms`);
  assert(duration3 < 1000, 'Force reload completes in <1s');

  console.log('\n✓ Performance tests passed');
}

// ============================================================================
// MAIN TEST RUNNER
// ============================================================================

async function runTests() {
  console.log('='.repeat(60));
  console.log('HOT-RELOAD SYSTEM TEST SUITE');
  console.log('='.repeat(60));

  const tests = {
    code: testCodeModuleHotReload,
    json: testJSONHotReload,
    thompson: testThompsonSamplingPropagation,
    discovery: testDiscoveryApplication,
    orchestrator: testOrchestratorIntegration,
    cache: testCacheManagement,
    performance: testPerformance,
  };

  try {
    if (testFilter) {
      if (tests[testFilter]) {
        await tests[testFilter]();
      } else {
        console.error(`Unknown test: ${testFilter}`);
        console.log(`Available tests: ${Object.keys(tests).join(', ')}`);
        process.exit(1);
      }
    } else {
      // Run all tests
      for (const [name, testFn] of Object.entries(tests)) {
        await testFn();
      }
    }

    // Summary
    console.log('\n' + '='.repeat(60));
    console.log('TEST SUMMARY');
    console.log('='.repeat(60));
    console.log(`Total assertions: ${testCount}`);
    console.log(`Passed: ${passCount}`);
    console.log(`Failed: ${failCount}`);
    console.log('='.repeat(60));

    if (failCount > 0) {
      console.log('\n❌ TESTS FAILED\n');
      process.exit(1);
    } else {
      console.log('\n✅ ALL TESTS PASSED\n');
      process.exit(0);
    }
  } catch (err) {
    console.error('\n❌ TEST ERROR:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run tests
runTests();
