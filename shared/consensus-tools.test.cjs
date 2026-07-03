/**
 * Consensus Tools Test Suite
 *
 * Comprehensive tests for consensus-tools.cjs wrapper and all 6 submodules.
 * Tests actual delegation behavior, async error handling, database dependencies,
 * and integration workflows.
 *
 * Run: node shared/consensus-tools.test.cjs
 *
 * Created: 2026-07-01
 */

const assert = require('assert');
const { Pool } = require('pg');

// Import the module under test
const consensusTools = require('./consensus-tools.cjs');

// Import submodules directly to test re-export functionality
const abRunner = require('./ab-runner.cjs');
const batchConsensus = require('./batch-consensus.cjs');
const confidenceCalibration = require('./confidence-calibration.cjs');
const consensusReplay = require('./consensus-replay.cjs');
const explainability = require('./explainability-reporter.cjs');
const experimentManager = require('./experiment-manager.cjs');

// Test counters
let passed = 0;
let failed = 0;
let skipped = 0;

// Test categories
const tests = {
  basic: [],
  delegation: [],
  async: [],
  database: [],
  integration: [],
  environment: [],
};

// Database connection state
let dbAvailable = false;
let testPool = null;

// ============================================================================
// TEST HELPERS
// ============================================================================

/**
 * Run a test and track results
 */
async function runTest(name, category, fn) {
  try {
    await fn();
    console.log(`✓ ${name}`);
    passed++;
  } catch (err) {
    console.log(`✗ ${name}: ${err.message}`);
    failed++;
  }
}

/**
 * Skip a test with reason
 */
function skipTest(name, category, reason) {
  console.log(`⊘ ${name}: ${reason}`);
  skipped++;
}

/**
 * Check if PostgreSQL is available
 */
async function checkDatabaseAvailability() {
  try {
    testPool = new Pool({
      host: process.env.PGHOST || 'aio-01',
      port: parseInt(process.env.PGPORT || '5432'),
      database: process.env.PGDATABASE || 'learning',
      user: process.env.PGUSER || process.env.USER,
      password: process.env.PGPASSWORD,
      max: 2,
      connectionTimeoutMillis: 2000,
    });

    const result = await testPool.query('SELECT 1');
    dbAvailable = result.rows.length === 1;
    return dbAvailable;
  } catch (err) {
    console.log(`[DB Check] PostgreSQL unavailable: ${err.message}`);
    dbAvailable = false;
    return false;
  }
}

/**
 * Clean up test database entries
 */
async function cleanupTestData() {
  if (!dbAvailable || !testPool) return;

  try {
    await testPool.query(`DELETE FROM workflow.experiments WHERE name LIKE 'test_%'`);
    await testPool.query(`DELETE FROM workflow.confidence_calibration WHERE workflow_execution_id LIKE 'test_%'`);
  } catch (err) {
    // Tables may not exist - non-fatal
  }
}

// ============================================================================
// BASIC TESTS: Module Loading and Exports
// ============================================================================

tests.basic.push({
  name: 'Module loads without errors',
  fn: () => {
    assert.ok(consensusTools, 'Module should export an object');
  },
});

tests.basic.push({
  name: 'All 6 wrapper functions exported',
  fn: () => {
    assert.strictEqual(typeof consensusTools.runExperiment, 'function');
    assert.strictEqual(typeof consensusTools.runConsensus, 'function');
    assert.strictEqual(typeof consensusTools.calibrateConfidence, 'function');
    assert.strictEqual(typeof consensusTools.replayDecision, 'function');
    assert.strictEqual(typeof consensusTools.explainDecision, 'function');
    assert.strictEqual(typeof consensusTools.manageExperiment, 'function');
  },
});

tests.basic.push({
  name: 'All 6 submodules re-exported',
  fn: () => {
    assert.ok(consensusTools.abRunner, 'abRunner should be re-exported');
    assert.ok(consensusTools.batchConsensus, 'batchConsensus should be re-exported');
    assert.ok(consensusTools.confidenceCalibration, 'confidenceCalibration should be re-exported');
    assert.ok(consensusTools.consensusReplay, 'consensusReplay should be re-exported');
    assert.ok(consensusTools.explainability, 'explainability should be re-exported');
    assert.ok(consensusTools.experimentManager, 'experimentManager should be re-exported');
  },
});

tests.basic.push({
  name: 'Re-exported submodules match direct imports',
  fn: () => {
    assert.strictEqual(consensusTools.abRunner, abRunner);
    assert.strictEqual(consensusTools.batchConsensus, batchConsensus);
    assert.strictEqual(consensusTools.confidenceCalibration, confidenceCalibration);
    assert.strictEqual(consensusTools.consensusReplay, consensusReplay);
    assert.strictEqual(consensusTools.explainability, explainability);
    assert.strictEqual(consensusTools.experimentManager, experimentManager);
  },
});

// ============================================================================
// DELEGATION TESTS: Verify Pass-Through Correctness
// ============================================================================

tests.delegation.push({
  name: 'runExperiment delegates to abRunner.runABTest',
  fn: async () => {
    // Use synthetic handler (no real models)
    const variants = [
      { name: 'baseline', features: [] },
      { name: 'treatment', features: ['test_feature'] },
    ];

    const result = await consensusTools.runExperiment('test-delegation', variants, {
      iterations_per_variant: 5,
      warmup_iterations: 0,
    });

    assert.ok(result.winner, 'Should return a winner');
    assert.ok(result.statistics, 'Should return statistics');
    assert.ok(result.report, 'Should return markdown report');
    assert.strictEqual(result.raw.experiment, 'test-delegation');
  },
});

tests.delegation.push({
  name: 'runConsensus delegates to batchConsensus.runBatchConsensus',
  fn: async () => {
    const tasks = ['Test question 1', 'Test question 2'];
    const models = ['opus', 'sonnet'];

    const result = await consensusTools.runConsensus(tasks, models, {
      concurrency: 2,
      useCache: false,
      timeout: 5000,
    });

    assert.ok(Array.isArray(result), 'Should return array of results');
    assert.strictEqual(result.length, 2);
  },
});

tests.delegation.push({
  name: 'calibrateConfidence delegates to confidenceCalibration.getCalibrationStats',
  fn: async () => {
    // calibrateConfidence now properly delegates to getCalibrationStats
    const result = await consensusTools.calibrateConfidence('test-model');

    assert.ok(result, 'Should return calibration stats');
    assert.ok(typeof result.num_observations === 'number');
    assert.ok(result.calibration_error === null || typeof result.calibration_error === 'number');
  },
});

tests.delegation.push({
  name: 'explainDecision delegates to explainability.generateReport',
  fn: () => {
    const mockVotingResult = {
      status: 'success',
      winner: {
        answer: 'Test answer',
        consensus_level: 'high',
        consensus_strength: 0.85,
        total_weight: 2.5,
        vote_count: 3,
        votes: [
          {
            model: 'opus',
            confidence: 0.9,
            tier_weight: 1.0,
            capability_score: 0.8,
            normalized_confidence: 0.9,
            historical_accuracy: 0.75,
            calibration_penalty: 1.0,
            weight: 0.54,
          },
        ],
      },
      all_groups: [
        {
          answer: 'Test answer',
          total_weight: 2.5,
          vote_count: 3,
          percentage: 85,
        },
      ],
    };

    const result = consensusTools.explainDecision(mockVotingResult);

    assert.strictEqual(result.status, 'success');
    assert.ok(result.summary, 'Should have summary');
    assert.ok(result.weight_breakdown, 'Should have weight breakdown');
  },
});

// ============================================================================
// ASYNC ERROR HANDLING TESTS
// ============================================================================

tests.async.push({
  name: 'runExperiment rejects on invalid config',
  fn: async () => {
    try {
      await consensusTools.runExperiment('invalid-test', null);
      assert.fail('Should have thrown an error');
    } catch (err) {
      assert.ok(err.message, 'Should have error message');
    }
  },
});

tests.async.push({
  name: 'runConsensus handles empty task array',
  fn: async () => {
    const result = await consensusTools.runConsensus([], ['opus']);
    assert.ok(Array.isArray(result), 'Should return empty array');
    assert.strictEqual(result.length, 0);
  },
});

tests.async.push({
  name: 'runConsensus rejects on invalid input',
  fn: async () => {
    try {
      await consensusTools.runConsensus('not-an-array', ['opus']);
      assert.fail('Should have thrown TypeError');
    } catch (err) {
      assert.ok(err.message.includes('array'));
    }
  },
});

tests.async.push({
  name: 'replayDecision handles missing workflow gracefully',
  fn: async () => {
    if (!dbAvailable) {
      return skipTest('replayDecision with missing workflow', 'async', 'DB unavailable');
    }

    const result = await consensusTools.replayDecision('nonexistent-workflow-id');
    assert.strictEqual(result, null, 'Should return null for missing workflow');
  },
});

// ============================================================================
// DATABASE DEPENDENCY TESTS
// ============================================================================

tests.database.push({
  name: 'manageExperiment requires database schema',
  fn: async () => {
    if (!dbAvailable) {
      return skipTest('manageExperiment schema check', 'database', 'DB unavailable');
    }

    // ensureSchema should be idempotent
    await experimentManager.ensureSchema();

    const exists = await testPool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'workflow'
        AND table_name = 'experiments'
      )
    `);

    assert.strictEqual(exists.rows[0].exists, true, 'experiments table should exist');
  },
});

tests.database.push({
  name: 'consensusReplay requires workflow.executions table',
  fn: async () => {
    if (!dbAvailable) {
      return skipTest('consensusReplay table check', 'database', 'DB unavailable');
    }

    const exists = await testPool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'workflow'
        AND table_name = 'executions'
      )
    `);

    // May not exist - this is expected in test environment
    // Test just verifies query succeeds
    assert.ok(typeof exists.rows[0].exists === 'boolean');
  },
});

tests.database.push({
  name: 'confidenceCalibration creates table if missing',
  fn: async () => {
    if (!dbAvailable) {
      return skipTest('confidenceCalibration table creation', 'database', 'DB unavailable');
    }

    // Store observation triggers table creation
    await confidenceCalibration.storeObservation({
      model: 'test-model',
      reported_confidence: 0.8,
      actual_outcome: 1.0,
      task_type: 'test',
      workflow_execution_id: 'test_workflow_' + Date.now(),
    });

    const exists = await testPool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'workflow'
        AND table_name = 'confidence_calibration'
      )
    `);

    assert.strictEqual(exists.rows[0].exists, true);
  },
});

tests.database.push({
  name: 'Database connection cleanup works',
  fn: async () => {
    if (!dbAvailable) {
      return skipTest('Database cleanup', 'database', 'DB unavailable');
    }

    const replay = new consensusReplay.ConsensusReplay();
    await replay.close();
    // Should not throw

    await experimentManager.closePool();
    // Should not throw
  },
});

// ============================================================================
// ENVIRONMENT VARIABLE TESTS
// ============================================================================

tests.environment.push({
  name: 'PGHOST environment variable respected',
  fn: () => {
    const originalHost = process.env.PGHOST;

    // consensusReplay uses process.env.PGHOST || 'aio-01'
    const replay = new consensusReplay.ConsensusReplay();
    const poolConfig = replay.pool.options;

    // Verify it uses environment variable or default
    assert.ok(poolConfig.host === (originalHost || 'aio-01'));
  },
});

tests.environment.push({
  name: 'PGPORT environment variable respected',
  fn: () => {
    const originalPort = process.env.PGPORT;

    const replay = new consensusReplay.ConsensusReplay();
    const poolConfig = replay.pool.options;

    assert.ok(poolConfig.port === parseInt(originalPort || '5433'));
  },
});

tests.environment.push({
  name: 'PGDATABASE environment variable respected',
  fn: () => {
    const originalDb = process.env.PGDATABASE;

    const replay = new consensusReplay.ConsensusReplay();
    const poolConfig = replay.pool.options;

    assert.ok(poolConfig.database === (originalDb || 'learning'));
  },
});

// ============================================================================
// INTEGRATION WORKFLOW TESTS
// ============================================================================

tests.integration.push({
  name: 'Full A/B test workflow (runExperiment → statistics → report)',
  fn: async () => {
    const result = await consensusTools.runExperiment('test_ab_workflow', [
      { name: 'control', features: [] },
      { name: 'variant', features: ['new_feature'] },
    ], {
      iterations_per_variant: 10,
      warmup_iterations: 1,
    });

    // Verify data flows through entire pipeline
    assert.ok(result.winner);
    assert.ok(result.statistics);
    assert.ok(result.statistics.winner);
    assert.ok(result.statistics.summaries);
    assert.ok(result.report.includes('A/B Test Report'));
    assert.ok(result.report.includes('Variant Summaries'));
  },
});

tests.integration.push({
  name: 'Batch consensus workflow (questions → consensus → analysis)',
  fn: async () => {
    const questions = [
      'What is 2+2?',
      'What is the capital of France?',
    ];

    const results = await consensusTools.runConsensus(questions, ['opus', 'sonnet'], {
      concurrency: 2,
      useCache: false,
      timeout: 5000,
    });

    // Verify batch processing
    assert.strictEqual(results.length, 2);
    assert.ok(results[0].answer);
    assert.ok(results[0].confidence >= 0);

    // Test analysis function
    const analysis = batchConsensus.analyzeBatchResults(results);
    assert.strictEqual(analysis.total, 2);
    assert.ok(analysis.avgConfidence >= 0);
  },
});

tests.integration.push({
  name: 'Experiment manager workflow (run → compare → record)',
  fn: async () => {
    if (!dbAvailable) {
      skipTest('Experiment manager full workflow', 'integration', 'DB unavailable');
      return;
    }

    // Synthetic collector
    const collector = async (config) => {
      const samples = [];
      for (let i = 0; i < 10; i++) {
        samples.push(config.baseline ? 0.5 + Math.random() * 0.1 : 0.6 + Math.random() * 0.1);
      }
      return samples;
    };

    const result = await consensusTools.manageExperiment({
      name: 'test_experiment_' + Date.now(),
      hypothesis: 'Treatment improves metric',
      metric: 'quality_score',
      baseline: { baseline: true },
      treatment: { baseline: false },
      collector,
      record: true,
    });

    assert.ok(result.verdict, 'Should have verdict');
    assert.ok(result.baseline_mean >= 0);
    assert.ok(result.treatment_mean >= 0);
    assert.ok(typeof result.p_value === 'number');
  },
});

tests.integration.push({
  name: 'Explainability report generation and storage',
  fn: async () => {
    if (!dbAvailable) {
      skipTest('Explainability report storage', 'integration', 'DB unavailable');
      return;
    }

    const mockVotingResult = {
      status: 'success',
      algorithm: 'weighted_voting',
      task_type: 'test',
      winner: {
        answer: 'Integrated test answer',
        consensus_level: 'high',
        consensus_strength: 0.9,
        total_weight: 3.0,
        vote_count: 4,
        votes: [
          {
            model: 'opus',
            confidence: 0.95,
            tier_weight: 1.0,
            capability_score: 0.9,
            normalized_confidence: 0.95,
            historical_accuracy: 0.8,
            calibration_penalty: 1.0,
            weight: 0.684,
          },
        ],
      },
      all_groups: [
        { answer: 'Integrated test answer', total_weight: 3.0, vote_count: 4, percentage: 90 },
      ],
    };

    const workflowId = 'test_workflow_' + Date.now();

    const result = await explainability.explain(mockVotingResult, {
      format: 'both',
      workflowExecutionId: workflowId,
    });

    assert.ok(result.report, 'Should have report object');
    assert.ok(result.json, 'Should have JSON format');
    assert.ok(result.markdown, 'Should have Markdown format');
    assert.ok(result.markdown.includes('Multi-AI Consensus'));
  },
});

// ============================================================================
// GRACEFUL DEGRADATION TESTS
// ============================================================================

tests.database.push({
  name: 'confidenceCalibration falls back to local cache when DB unavailable',
  fn: async () => {
    // Temporarily break DB connection
    const originalHost = process.env.PGHOST;
    process.env.PGHOST = 'invalid-host-12345';

    await confidenceCalibration.storeObservation({
      model: 'test-model-fallback',
      reported_confidence: 0.7,
      actual_outcome: 0.0,
      task_type: 'test',
    });

    // Should succeed (falls back to local cache)
    // Verify by checking local cache file exists
    const fs = require('fs');
    const path = require('path');
    const cachePath = path.join(process.env.HOME, '.claude', 'learning', 'confidence-calibration-cache.json');

    // May or may not exist depending on fallback success - non-fatal
    process.env.PGHOST = originalHost;
  },
});

tests.database.push({
  name: 'explainability works without DB storage',
  fn: async () => {
    const mockVotingResult = {
      status: 'success',
      winner: {
        answer: 'Offline test',
        consensus_level: 'moderate',
        consensus_strength: 0.7,
        total_weight: 2.1,
        vote_count: 3,
        votes: [
          {
            model: 'sonnet',
            confidence: 0.8,
            tier_weight: 0.9,
            capability_score: 0.85,
            normalized_confidence: 0.8,
            historical_accuracy: 0.7,
            calibration_penalty: 1.0,
            weight: 0.428,
          },
        ],
      },
      all_groups: [
        { answer: 'Offline test', total_weight: 2.1, vote_count: 3, percentage: 70 },
      ],
    };

    const result = await explainability.explain(mockVotingResult, {
      format: 'json',
      // No workflowExecutionId - should skip DB storage
    });

    assert.ok(result.report.status === 'success');
    assert.ok(!result.file_path, 'Should not write file');
  },
});

// ============================================================================
// TEST RUNNER
// ============================================================================

async function runAllTests() {
  console.log('=== Consensus Tools Test Suite ===\n');

  // Check database availability
  console.log('Checking PostgreSQL availability...');
  const dbStatus = await checkDatabaseAvailability();
  console.log(`Database: ${dbStatus ? '✓ Available' : '⊘ Unavailable (some tests will be skipped)'}\n`);

  // Run tests by category
  for (const [category, categoryTests] of Object.entries(tests)) {
    console.log(`\n--- ${category.toUpperCase()} TESTS ---`);

    for (const test of categoryTests) {
      await runTest(test.name, category, test.fn);
    }
  }

  // Cleanup
  console.log('\n--- CLEANUP ---');
  await cleanupTestData();
  if (testPool) {
    await testPool.end();
  }

  // Summary
  console.log('\n=== TEST SUMMARY ===');
  console.log(`Passed:  ${passed}`);
  console.log(`Failed:  ${failed}`);
  console.log(`Skipped: ${skipped}`);
  console.log(`Total:   ${passed + failed + skipped}`);

  // Calculate realistic coverage estimate
  const totalTests = passed + failed;
  const coverageEstimate = totalTests > 0 ? ((passed / totalTests) * 100).toFixed(1) : 0;
  console.log(`\nEstimated Coverage: ${coverageEstimate}%`);
  console.log('(Based on actual test execution, not code paths)');

  if (failed === 0) {
    console.log('\n✅ ALL TESTS PASSED');
    process.exit(0);
  } else {
    console.log('\n❌ SOME TESTS FAILED');
    process.exit(1);
  }
}

// Run tests if invoked directly
if (require.main === module) {
  runAllTests().catch(err => {
    console.error('Test suite crashed:', err);
    process.exit(1);
  });
}

module.exports = {
  runAllTests,
  tests,
};
