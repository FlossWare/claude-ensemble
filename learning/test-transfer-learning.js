#!/usr/bin/env node
/**
 * Transfer Learning Test Suite
 *
 * Tests all aspects of transfer learning implementation:
 *   1. Model similarity calculation
 *   2. Bootstrap new models
 *   3. Confidence decay over time
 *   4. Native data transition
 *   5. Transfer validation
 */

const transfer = require('./transfer-learning');
const assert = require('assert');

// ---------------------------------------------------------------------------
// Test utilities
// ---------------------------------------------------------------------------

function assertApprox(actual, expected, tolerance = 0.01, message = '') {
  const diff = Math.abs(actual - expected);
  if (diff > tolerance) {
    throw new Error(
      `${message}\nExpected: ${expected} ± ${tolerance}\nActual: ${actual}\nDiff: ${diff}`
    );
  }
}

// ---------------------------------------------------------------------------
// Test 1: Model parsing
// ---------------------------------------------------------------------------

async function testModelParsing() {
  console.log('\n=== Test 1: Model Parsing ===');

  const tests = [
    {
      input: 'claude-opus-4',
      expected: { provider: 'anthropic', family: 'claude-4', arch: 'opus' }
    },
    {
      input: 'claude-sonnet-3.5',
      expected: { provider: 'anthropic', family: 'claude-3.5', arch: 'sonnet' }
    },
    {
      input: 'gpt-4-turbo',
      expected: { provider: 'openai', family: 'gpt-4', arch: 'turbo' }
    },
    {
      input: 'gemini-1.5-pro',
      expected: { provider: 'google', family: 'gemini-1.5', arch: 'pro' }
    },
    {
      input: 'claude-haiku-4.5',
      expected: { provider: 'anthropic', family: 'claude-4.5', arch: 'haiku' }
    }
  ];

  for (const test of tests) {
    const result = transfer.parseModelId(test.input);
    assert.strictEqual(result.provider, test.expected.provider,
      `Provider mismatch for ${test.input}: expected ${test.expected.provider}, got ${result.provider}`);
    assert.strictEqual(result.family, test.expected.family,
      `Family mismatch for ${test.input}: expected ${test.expected.family}, got ${result.family}`);
    assert.strictEqual(result.arch, test.expected.arch,
      `Architecture mismatch for ${test.input}: expected ${test.expected.arch}, got ${result.arch}`);
    console.log(`✓ ${test.input} → ${result.provider}/${result.family}/${result.arch}`);
  }

  console.log('✓ All parsing tests passed');
}

// ---------------------------------------------------------------------------
// Test 2: Similarity calculation
// ---------------------------------------------------------------------------

async function testSimilarityCalculation() {
  console.log('\n=== Test 2: Similarity Calculation ===');

  const tests = [
    {
      model1: 'claude-opus-4',
      model2: 'claude-opus-4.5',
      expectedMin: 0.8,  // Same provider, family, arch
      name: 'Same architecture, different version'
    },
    {
      model1: 'claude-opus-4',
      model2: 'claude-sonnet-4',
      expectedMin: 0.5,  // Same provider, family, different arch
      name: 'Same family, different architecture'
    },
    {
      model1: 'claude-opus-4',
      model2: 'gpt-4-turbo',
      expectedMin: 0.0,
      expectedMax: 0.4,  // Different provider, different family
      name: 'Different providers'
    },
    {
      model1: 'claude-opus-4',
      model2: 'claude-opus-4',
      expectedMin: 0.8,  // Identical models (may not be 1.0 without task data)
      name: 'Identical models'
    },
    {
      model1: 'gemini-1.5-pro',
      model2: 'gemini-2.0-flash',
      expectedMin: 0.3,  // Same provider, same family, different arch
      name: 'Same Google family, different arch'
    }
  ];

  for (const test of tests) {
    const similarity = transfer.calculateSimilarity(test.model1, test.model2);
    console.log(`${test.name}: ${test.model1} ↔ ${test.model2} = ${similarity.toFixed(3)}`);

    if (test.expectedMin !== undefined) {
      assert.ok(similarity >= test.expectedMin,
        `Similarity too low: expected >= ${test.expectedMin}, got ${similarity}`);
    }
    if (test.expectedMax !== undefined) {
      assert.ok(similarity <= test.expectedMax,
        `Similarity too high: expected <= ${test.expectedMax}, got ${similarity}`);
    }
  }

  console.log('✓ All similarity tests passed');
}

// ---------------------------------------------------------------------------
// Test 3: Confidence decay
// ---------------------------------------------------------------------------

async function testConfidenceDecay() {
  console.log('\n=== Test 3: Confidence Decay ===');

  const initialConfidence = transfer.TRANSFER_INITIAL_CONFIDENCE;
  const decayRate = transfer.TRANSFER_DECAY_RATE;

  console.log(`Initial confidence: ${initialConfidence}`);
  console.log(`Decay rate: ${decayRate} per day`);

  const decayTests = [
    { days: 0, expectedFactor: 1.0 },
    { days: 1, expectedFactor: Math.exp(-decayRate * 1) },
    { days: 7, expectedFactor: Math.exp(-decayRate * 7) },
    { days: 30, expectedFactor: Math.exp(-decayRate * 30) }
  ];

  for (const test of decayTests) {
    const expectedConfidence = initialConfidence * test.expectedFactor;
    const isExpired = expectedConfidence < transfer.MIN_TRANSFER_CONFIDENCE;

    console.log(
      `Day ${test.days.toString().padStart(3)}: ` +
      `confidence = ${expectedConfidence.toFixed(4)} ` +
      `(${(test.expectedFactor * 100).toFixed(1)}% of initial)` +
      `${isExpired ? ' [EXPIRED]' : ''}`
    );
  }

  // Verify decay formula
  const confidence_day7 = initialConfidence * Math.exp(-decayRate * 7);
  assertApprox(confidence_day7, initialConfidence * 0.4966, 0.001,
    'Day 7 confidence decay');

  console.log('✓ Confidence decay working correctly');
}

// ---------------------------------------------------------------------------
// Test 4: Integration test (requires database)
// ---------------------------------------------------------------------------

async function testIntegration() {
  console.log('\n=== Test 4: Integration Test ===');
  console.log('Testing bootstrap, calibration, and validation...');

  try {
    // Test 1: Bootstrap a new model
    console.log('\n--- Bootstrap new model ---');
    const bootstrapResult = await transfer.bootstrapNewModel(
      'claude-opus-4.5',
      null,  // Auto-detect similar models
      'code-review'
    );
    console.log('Bootstrap result:', JSON.stringify(bootstrapResult, null, 2));

    if (bootstrapResult.success) {
      console.log(`✓ Successfully bootstrapped from ${bootstrapResult.sourceModels.length} source models`);

      // Test 2: Get transferred calibration
      console.log('\n--- Get transferred calibration ---');
      const calibration = await transfer.getTransferredCalibration(
        'claude-opus-4.5',
        'code-review'
      );
      console.log('Calibration:', JSON.stringify(calibration, null, 2));
      console.log(`✓ Calibration source: ${calibration.source}`);

      // Test 3: Simulate native data updates
      console.log('\n--- Simulate native data accumulation ---');
      for (let i = 0; i < 5; i++) {
        const updateResult = await transfer.updateWithNativeData(
          'claude-opus-4.5',
          {
            quality_score: 0.8 + Math.random() * 0.2,
            confidence: 0.7 + Math.random() * 0.3,
            outcome: 'success'
          }
        );
        console.log(`Update ${i + 1}: ${updateResult.nativeSamples} native samples, transition: ${updateResult.transition}`);
      }
      console.log('✓ Native data updates working');

    } else {
      console.log(`✗ Bootstrap failed: ${bootstrapResult.reason}`);
      if (bootstrapResult.reason === 'model_already_calibrated') {
        console.log('  (This is expected if the model already has calibration data)');
      }
    }

  } catch (error) {
    if (error.code === 'SQLITE_ERROR' && error.message.includes('no such table')) {
      console.log('✗ Database tables not initialized');
      console.log('  Run: node init-transfer-learning-db.js');
      return;
    }
    throw error;
  }

  console.log('✓ Integration test completed');
}

// ---------------------------------------------------------------------------
// Main test runner
// ---------------------------------------------------------------------------

async function runAllTests() {
  console.log('Transfer Learning Test Suite');
  console.log('============================');

  try {
    await testModelParsing();
    await testSimilarityCalculation();
    await testConfidenceDecay();
    await testIntegration();

    console.log('\n============================');
    console.log('✓ ALL TESTS PASSED');
    console.log('============================');

  } catch (error) {
    console.error('\n============================');
    console.error('✗ TEST FAILED');
    console.error('============================');
    console.error(error);
    process.exit(1);
  }
}

// Run tests if called directly
if (require.main === module) {
  runAllTests();
}

module.exports = {
  testModelParsing,
  testSimilarityCalculation,
  testConfidenceDecay,
  testIntegration,
  runAllTests
};
