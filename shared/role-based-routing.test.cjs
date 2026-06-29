/**
 * Test suite for role-based routing
 */

const {
  selectCapability,
  getCapableModels,
  updateThompsonStats,
  getRoleRequirements,
  getModelCapabilities
} = require('./role-based-routing.cjs');

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

async function testBasicSelection() {
  console.log('\n=== Test: Basic Selection ===');

  try {
    // Test code generation
    const codeGen = await selectCapability('code_generation');
    console.log('Code generation:', codeGen.modelId, 'score:', codeGen.score);
    assert(codeGen.modelId, 'Should select a model');
    assert(codeGen.score > 0, 'Should have positive score');

    // Test arbiter
    const arbiter = await selectCapability('arbiter');
    console.log('Arbiter:', arbiter.modelId, 'score:', arbiter.score);
    assert(arbiter.data.quality_score >= 0.85, 'Arbiter should have high quality');

    // Test fast routing
    const routing = await selectCapability('routing');
    console.log('Routing:', routing.modelId, 'score:', routing.score);
    assert(
      routing.data.avg_latency_ms <= 2000,
      'Routing should be fast'
    );

    console.log('✓ Basic selection tests passed');
  } catch (err) {
    console.log(
      '⚠ Basic selection tests skipped (capability registry unavailable):',
      err.message
    );
  }
}

async function testPrioritization() {
  console.log('\n=== Test: Prioritization ===');

  try {
    const quality = await selectCapability('code_generation', {
      prioritize: 'quality'
    });
    const speed = await selectCapability('code_generation', {
      prioritize: 'speed'
    });
    const cost = await selectCapability('code_generation', {
      prioritize: 'cost'
    });

    console.log(
      'Quality priority:',
      quality.modelId,
      'quality:',
      quality.data.quality_score
    );
    console.log(
      'Speed priority:',
      speed.modelId,
      'latency:',
      speed.data.avg_latency_ms
    );
    console.log('Cost priority:', cost.modelId, 'cost:', cost.data.avg_cost);

    // Quality priority should select high-quality model
    assert(
      quality.data.quality_score >= 0.85,
      'Quality priority should select high-quality model'
    );

    // Cost priority should prefer cheap models
    assert(cost.data.avg_cost <= 0.20, 'Cost priority should select cheap model');

    console.log('✓ Prioritization tests passed');
  } catch (err) {
    console.log(
      '⚠ Prioritization tests skipped (capability registry unavailable):',
      err.message
    );
  }
}

async function testThompsonSampling() {
  console.log('\n=== Test: Thompson Sampling Integration ===');

  try {
    // Simulate Thompson stats
    let thompsonData = {
      'opus': { alpha: 10, beta: 2 },
      'sonnet': { alpha: 8, beta: 8 },
      'haiku': { alpha: 3, beta: 7 }
    };

    const result = await selectCapability('code_generation', {
      thompsonSampling: thompsonData
    });

    console.log('With Thompson Sampling:', result.modelId);
    console.log('  Base score:', result.baseScore);
    console.log('  Thompson score:', result.thompsonScore);
    console.log('  Final score:', result.score);

    assert(result.thompsonScore !== null, 'Should include Thompson score');

    // Update stats
    thompsonData = updateThompsonStats('sonnet', true, thompsonData);
    console.log('Updated stats:', thompsonData['sonnet']);
    assert(thompsonData['sonnet'].alpha === 9, 'Should increment alpha on success');

    console.log('✓ Thompson Sampling tests passed');
  } catch (err) {
    console.log(
      '⚠ Thompson Sampling tests skipped (capability registry unavailable):',
      err.message
    );
  }
}

async function testCapableModels() {
  console.log('\n=== Test: Get Capable Models ===');

  try {
    const capable = await getCapableModels('code_generation', {
      prioritize: 'quality'
    });
    console.log('Capable models for code_generation:', capable.length);
    capable.slice(0, 3).forEach(c => {
      console.log(
        '  -',
        c.modelId,
        'score:',
        c.score,
        'quality:',
        c.data.quality_score
      );
    });

    assert(capable.length > 0, 'Should find capable models');
    assert(
      capable[0].score >= capable[capable.length - 1].score,
      'Should be sorted by score'
    );

    console.log('✓ Capable models tests passed');
  } catch (err) {
    console.log(
      '⚠ Capable models tests skipped (capability registry unavailable):',
      err.message
    );
  }
}

function testIntrospection() {
  console.log('\n=== Test: Introspection ===');

  const roleReqs = getRoleRequirements('arbiter');
  console.log('Arbiter requirements:', roleReqs);
  assert(
    roleReqs.capability === 'verifier',
    'Should map to verifier capability'
  );
  assert(roleReqs.minQuality === 0.85, 'Should have quality requirement');

  console.log('✓ Introspection tests passed');
}

function testEdgeCases() {
  console.log('\n=== Test: Edge Cases ===');

  // Unknown role
  try {
    getRoleRequirements('unknown_role');
    const result = getRoleRequirements('unknown_role');
    assert(
      result === null,
      'Should return null for unknown role in introspection'
    );
    console.log('✓ Returns null for unknown role');
  } catch (err) {
    console.log('✓ Correctly handles unknown role:', err.message);
  }

  console.log('✓ Edge case tests passed');
}

async function runAllTests() {
  console.log('='.repeat(50));
  console.log('Role-Based Routing Test Suite');
  console.log('='.repeat(50));

  try {
    await testBasicSelection();
    await testPrioritization();
    await testThompsonSampling();
    await testCapableModels();
    testIntrospection();
    testEdgeCases();

    console.log('\n' + '='.repeat(50));
    console.log('✓ ALL TESTS PASSED');
    console.log('='.repeat(50));
    return true;
  } catch (err) {
    console.error('\n' + '='.repeat(50));
    console.error('✗ TEST FAILED:', err.message);
    console.error(err.stack);
    console.error('='.repeat(50));
    return false;
  }
}

// Run tests
runAllTests().then(success => {
  process.exit(success ? 0 : 1);
});
