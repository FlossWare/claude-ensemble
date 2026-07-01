/**
 * Consensus Tools Wrapper
 *
 * Wires up 6 unused consensus/experiment components:
 * - ab-runner.cjs (#263)
 * - batch-consensus.cjs (#264)
 * - confidence-calibration.cjs (#266)
 * - consensus-replay.cjs (#265)
 * - explainability-reporter.cjs (#267)
 * - experiment-manager.cjs (#273)
 *
 * Usage:
 *   const { runExperiment, runConsensus } = require('./consensus-tools.js');
 *   const result = await runExperiment('test-experiment', variants);
 *
 * Test:
 *   node shared/consensus-tools.js --test
 */

const abRunner = require('./ab-runner.cjs');
const batchConsensus = require('./batch-consensus.cjs');
const confidenceCalibration = require('./confidence-calibration.cjs');
const consensusReplay = require('./consensus-replay.cjs');
const explainability = require('./explainability-reporter.cjs');
const experimentManager = require('./experiment-manager.cjs');

/**
 * Run an A/B test experiment
 */
async function runExperiment(name, variants, config = {}) {
  return await abRunner.runABTest(name, variants, config);
}

/**
 * Run batch consensus across multiple models
 */
async function runConsensus(tasks, models, config = {}) {
  return await batchConsensus.runBatchConsensus(tasks, models, config);
}

/**
 * Calibrate confidence scores
 */
function calibrateConfidence(predictions, groundTruth) {
  return confidenceCalibration.calibrate(predictions, groundTruth);
}

/**
 * Replay a consensus decision
 */
async function replayDecision(decisionId) {
  return await consensusReplay.replay(decisionId);
}

/**
 * Generate explanation for a decision
 */
function explainDecision(decision) {
  return explainability.generateReport(decision);
}

/**
 * Manage an experiment lifecycle
 */
async function manageExperiment(experimentConfig) {
  return await experimentManager.runExperiment(experimentConfig);
}

// Export all functions
module.exports = {
  runExperiment,
  runConsensus,
  calibrateConfidence,
  replayDecision,
  explainDecision,
  manageExperiment,
  // Re-export submodules for advanced usage
  abRunner,
  batchConsensus,
  confidenceCalibration,
  consensusReplay,
  explainability,
  experimentManager
};

// Test mode
if (require.main === module && process.argv.includes('--test')) {
  console.log('=== Testing Consensus Tools ===\n');

  let passed = 0;
  let failed = 0;

  try {
    console.log('Test 1: Import all modules...');
    if (abRunner && batchConsensus && confidenceCalibration &&
        consensusReplay && explainability && experimentManager) {
      console.log('✓ All modules loaded\n');
      passed++;
    }
  } catch (e) {
    console.log(`✗ Import failed: ${e.message}\n`);
    failed++;
  }

  try {
    console.log('Test 2: Check exports...');
    if (typeof runExperiment === 'function' &&
        typeof runConsensus === 'function' &&
        typeof calibrateConfidence === 'function' &&
        typeof replayDecision === 'function' &&
        typeof explainDecision === 'function' &&
        typeof manageExperiment === 'function') {
      console.log('✓ All functions exported\n');
      passed++;
    }
  } catch (e) {
    console.log(`✗ Export check failed: ${e.message}\n`);
    failed++;
  }

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  if (failed === 0) {
    console.log('✅ ALL TESTS PASSED');
    process.exit(0);
  } else {
    console.log('❌ SOME TESTS FAILED');
    process.exit(1);
  }
}
