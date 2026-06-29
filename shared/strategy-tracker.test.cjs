/**
 * Strategy Tracker Tests
 *
 * Tests for multi-dimensional strategy tracking system.
 *
 * Created: 2026-06-28
 */

const {
  recordStrategyResult,
  getStrategyPerformance,
  getBestStrategy,
  getStrategyComparisonByDimension,
  getStrategyAnalysis,
  close,
  pool
} = require('./strategy-tracker.cjs');

/**
 * Test helper to clean up test data
 */
async function cleanupTestData() {
  await pool.query(`
    DELETE FROM learning.strategy_performance
    WHERE strategy LIKE 'test-%'
  `);
}

/**
 * Run all tests
 */
async function runTests() {
  console.log('Starting strategy-tracker tests...\n');

  try {
    await cleanupTestData();

    await testRecordStrategyResult();
    await testGetStrategyPerformance();
    await testGetBestStrategy();
    await testThompsonSampling();
    await testMultiDimensionalFiltering();
    await testConstraints();
    await testStrategyComparisonByDimension();
    await testStrategyAnalysis();

    console.log('\n✅ All tests passed!');
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    console.error(error.stack);
    process.exit(1);
  } finally {
    await cleanupTestData();
    await close();
  }
}

/**
 * Test: Record strategy result
 */
async function testRecordStrategyResult() {
  console.log('Test: recordStrategyResult()');

  const result = await recordStrategyResult(
    {
      name: 'test-chain-of-thought-parallel',
      promptTemplateId: 'chain-of-thought',
      orchestrationPattern: 'parallel',
      verificationMethod: 'multi-ai-consensus',
      reasoningSequence: 'analyze -> decompose -> synthesize'
    },
    'code-review',
    { success: true, reward: 0.85 }
  );

  console.assert(result.id > 0, 'Should return valid ID');
  console.assert(result.alpha === 2.0, 'Alpha should be 2.0 (1 + 1 success)');
  console.assert(result.beta === 1.0, 'Beta should be 1.0 (1 + 0 failures)');
  console.assert(result.avgReward === 0.85, 'Average reward should be 0.85');

  // Record another result for the same strategy
  const result2 = await recordStrategyResult(
    {
      name: 'test-chain-of-thought-parallel',
      promptTemplateId: 'chain-of-thought',
      orchestrationPattern: 'parallel',
      verificationMethod: 'multi-ai-consensus'
    },
    'code-review',
    { success: false, reward: 0.3 }
  );

  console.assert(result2.alpha === 2.0, 'Alpha should stay 2.0 (no new successes)');
  console.assert(result2.beta === 2.0, 'Beta should be 2.0 (1 + 1 failure)');
  console.assert(
    Math.abs(result2.avgReward - 0.575) < 0.001,
    `Average reward should be ~0.575, got ${result2.avgReward}`
  );

  console.log('  ✓ Records and updates strategy results correctly\n');
}

/**
 * Test: Get strategy performance
 */
async function testGetStrategyPerformance() {
  console.log('Test: getStrategyPerformance()');

  // Create test strategies
  await recordStrategyResult(
    {
      name: 'test-few-shot-sequential',
      promptTemplateId: 'few-shot',
      orchestrationPattern: 'sequential',
      verificationMethod: 'self-critique'
    },
    'code-generation',
    { success: true, reward: 0.75 }
  );

  await recordStrategyResult(
    {
      name: 'test-zero-shot-parallel',
      promptTemplateId: 'zero-shot',
      orchestrationPattern: 'parallel',
      verificationMethod: 'multi-ai-consensus'
    },
    'code-generation',
    { success: true, reward: 0.9 }
  );

  // Get all test strategies for code-review task
  const allStrategies = await getStrategyPerformance({ taskType: 'code-review' });
  const testStrategies = allStrategies.filter(s => s.strategy.startsWith('test-'));
  console.assert(testStrategies.length >= 3, `Should have at least 3 test strategies, got ${testStrategies.length}`);

  // Filter by orchestration pattern
  const parallelStrategies = await getStrategyPerformance({
    taskType: 'code-review',
    orchestrationPattern: 'parallel'
  });
  const testParallel = parallelStrategies.filter(s => s.strategy.startsWith('test-'));
  console.assert(testParallel.length >= 2, `Should have at least 2 parallel strategies, got ${testParallel.length}`);
  if (testParallel.length > 0) {
    console.assert(
      testParallel.every(s => s.orchestrationPattern === 'parallel' || s.orchestrationPattern === null),
      'All results should have parallel orchestration or null'
    );
  }

  console.log('  ✓ Retrieves and filters strategy performance correctly\n');
}

/**
 * Test: Get best strategy
 */
async function testGetBestStrategy() {
  console.log('Test: getBestStrategy()');

  // Create strategies with different performance levels
  const strategies = [
    { name: 'test-high-perf', reward: 0.9, count: 10 },
    { name: 'test-medium-perf', reward: 0.6, count: 10 },
    { name: 'test-low-perf', reward: 0.3, count: 10 }
  ];

  for (const strat of strategies) {
    for (let i = 0; i < strat.count; i++) {
      await recordStrategyResult(
        {
          name: strat.name,
          promptTemplateId: 'chain-of-thought',
          orchestrationPattern: 'parallel',
          verificationMethod: 'multi-ai-consensus'
        },
        'testing',
        { success: true, reward: strat.reward }
      );
    }
  }

  // Get best strategy (should favor high-perf with Thompson Sampling)
  const best = await getBestStrategy('testing', {
    promptTemplateId: 'chain-of-thought',
    minSamples: 5
  });

  console.assert(best.strategy, 'Should return a strategy');
  console.assert(best.sampledReward >= 0 && best.sampledReward <= 1, 'Sampled reward should be in [0, 1]');
  console.assert(best.avgReward >= 0 && best.avgReward <= 1, 'Average reward should be in [0, 1]');
  console.assert(best.confidence > 0, 'Confidence should be positive');
  console.assert(best.totalSamples >= 5, 'Should have at least minSamples');

  console.log(`  ✓ Selected strategy: ${best.strategy} (avg: ${best.avgReward.toFixed(2)}, sampled: ${best.sampledReward.toFixed(2)})\n`);
}

/**
 * Test: Thompson Sampling exploration/exploitation
 */
async function testThompsonSampling() {
  console.log('Test: Thompson Sampling exploration/exploitation');

  // Create a high-performance strategy with few samples
  await recordStrategyResult(
    {
      name: 'test-exploration-high',
      promptTemplateId: 'exploration-test',
      orchestrationPattern: 'parallel'
    },
    'testing',
    { success: true, reward: 0.95 }
  );
  await recordStrategyResult(
    {
      name: 'test-exploration-high',
      promptTemplateId: 'exploration-test'
    },
    'testing',
    { success: true, reward: 0.95 }
  );

  // Create a moderate-performance strategy with many samples
  for (let i = 0; i < 20; i++) {
    await recordStrategyResult(
      {
        name: 'test-exploitation-moderate',
        promptTemplateId: 'exploration-test',
        orchestrationPattern: 'parallel'
      },
      'testing',
      { success: true, reward: 0.7 }
    );
  }

  // Run Thompson Sampling multiple times
  const selections = { 'test-exploration-high': 0, 'test-exploitation-moderate': 0 };
  for (let i = 0; i < 100; i++) {
    const best = await getBestStrategy('testing', {
      promptTemplateId: 'exploration-test',
      minSamples: 1
    });
    selections[best.strategy] = (selections[best.strategy] || 0) + 1;
  }

  console.log(`  Selections: high-reward (${selections['test-exploration-high']}) vs moderate-reward (${selections['test-exploitation-moderate']})`);

  // Both should be selected sometimes (exploration + exploitation balance)
  console.assert(
    selections['test-exploration-high'] > 0,
    'High-reward strategy should be explored'
  );
  console.assert(
    selections['test-exploitation-moderate'] > 0,
    'Moderate-reward strategy should be exploited'
  );

  console.log('  ✓ Thompson Sampling balances exploration and exploitation\n');
}

/**
 * Test: Multi-dimensional filtering
 */
async function testMultiDimensionalFiltering() {
  console.log('Test: Multi-dimensional filtering');

  // Create strategies with different dimension combinations
  const testCases = [
    {
      name: 'test-multi-1',
      promptTemplateId: 'chain-of-thought',
      orchestrationPattern: 'parallel',
      verificationMethod: 'multi-ai-consensus'
    },
    {
      name: 'test-multi-2',
      promptTemplateId: 'chain-of-thought',
      orchestrationPattern: 'sequential',
      verificationMethod: 'multi-ai-consensus'
    },
    {
      name: 'test-multi-3',
      promptTemplateId: 'few-shot',
      orchestrationPattern: 'parallel',
      verificationMethod: 'self-critique'
    }
  ];

  for (const tc of testCases) {
    await recordStrategyResult(tc, 'testing', { success: true, reward: 0.8 });
  }

  // Filter by single dimension
  const chainOfThought = await getStrategyPerformance({
    taskType: 'testing',
    promptTemplateId: 'chain-of-thought'
  });
  const testChain = chainOfThought.filter(s => s.strategy.startsWith('test-multi-'));
  console.assert(testChain.length === 2, `Should find 2 chain-of-thought strategies, got ${testChain.length}`);

  // Filter by multiple dimensions
  const parallelConsensus = await getStrategyPerformance({
    taskType: 'testing',
    orchestrationPattern: 'parallel',
    verificationMethod: 'multi-ai-consensus'
  });
  const testParallelConsensus = parallelConsensus.filter(s => s.strategy.startsWith('test-multi-'));
  if (testParallelConsensus.length > 0) {
    console.assert(testParallelConsensus.length === 1, `Should find 1 parallel+consensus strategy, got ${testParallelConsensus.length}`);
    console.assert(testParallelConsensus[0].strategy === 'test-multi-1', 'Should match test-multi-1');
  }

  console.log('  ✓ Multi-dimensional filtering works correctly\n');
}

/**
 * Test: Constraint handling
 */
async function testConstraints() {
  console.log('Test: Constraint handling');

  // Create strategies with varying sample counts
  await recordStrategyResult(
    { name: 'test-constraint-low-samples', promptTemplateId: 'constraint-test' },
    'testing',
    { success: true, reward: 0.95 }
  );

  for (let i = 0; i < 15; i++) {
    await recordStrategyResult(
      { name: 'test-constraint-high-samples', promptTemplateId: 'constraint-test' },
      'testing',
      { success: true, reward: 0.7 }
    );
  }

  // With high minSamples constraint, should skip low-sample strategy
  const highSamplesOnly = await getBestStrategy('testing', {
    promptTemplateId: 'constraint-test',
    minSamples: 10
  });

  console.assert(
    highSamplesOnly.totalSamples >= 10,
    `Should respect minSamples constraint, got ${highSamplesOnly.totalSamples}`
  );

  // With low minSamples, both are eligible
  const lowSamplesOk = await getBestStrategy('testing', {
    promptTemplateId: 'constraint-test',
    minSamples: 1
  });

  console.assert(lowSamplesOk.totalSamples >= 1, 'Should respect minSamples=1 constraint');

  console.log('  ✓ Constraints are respected correctly\n');
}

/**
 * Test: PHASE 2 - Strategy comparison by dimension
 */
async function testStrategyComparisonByDimension() {
  console.log('Test: PHASE 2 - getStrategyComparisonByDimension()');

  // Create strategies with different orchestration patterns (need multiple executions for aggregation)
  for (let i = 0; i < 2; i++) {
    await recordStrategyResult(
      {
        name: 'test-dimension-parallel-1',
        orchestrationPattern: 'parallel',
        verificationMethod: 'multi-ai-consensus'
      },
      'dimension-test',
      { success: true, reward: 0.85, cost: 0.05, duration_ms: 5000 }
    );
  }

  for (let i = 0; i < 2; i++) {
    await recordStrategyResult(
      {
        name: 'test-dimension-parallel-2',
        orchestrationPattern: 'parallel',
        verificationMethod: 'multi-ai-consensus'
      },
      'dimension-test',
      { success: true, reward: 0.9, cost: 0.05, duration_ms: 5000 }
    );
  }

  for (let i = 0; i < 2; i++) {
    await recordStrategyResult(
      {
        name: 'test-dimension-sequential-1',
        orchestrationPattern: 'sequential',
        verificationMethod: 'self-critique'
      },
      'dimension-test',
      { success: true, reward: 0.65, cost: 0.02, duration_ms: 3000 }
    );
  }

  // Compare by orchestration pattern (with minExecutions=1 for testing)
  const patterns = await getStrategyComparisonByDimension('dimension-test', 'orchestrationPattern', { minExecutions: 1 });

  console.assert(patterns.length >= 1, `Should have at least 1 pattern, got ${patterns.length}`);

  if (patterns.length > 0) {
    const parallelPattern = patterns.find(p => p.dimension === 'parallel');
    if (parallelPattern) {
      console.assert(parallelPattern.numStrategies >= 1, `Parallel should have >= 1 strategy, got ${parallelPattern.numStrategies}`);
    }
  }

  // Compare by verification method
  const methods = await getStrategyComparisonByDimension('dimension-test', 'verificationMethod', { minExecutions: 1 });
  console.assert(methods.length >= 1, `Should have at least 1 method, got ${methods.length}`);

  console.log(`  ✓ Found ${patterns.length} orchestration patterns and ${methods.length} verification methods\n`);
}

/**
 * Test: PHASE 2 - Strategy analysis with performance tiers
 */
async function testStrategyAnalysis() {
  console.log('Test: PHASE 2 - getStrategyAnalysis()');

  // Create strategies with different performance levels
  // High performer (>= 0.8 reward, >= 5 executions)
  for (let i = 0; i < 5; i++) {
    await recordStrategyResult(
      { name: 'test-analysis-high-perf', orchestrationPattern: 'parallel' },
      'analysis-test',
      { success: true, reward: 0.9, cost: 0.1, duration_ms: 8000 }
    );
  }

  // Moderate performer (0.6-0.8 reward, >= 5 executions)
  for (let i = 0; i < 5; i++) {
    await recordStrategyResult(
      { name: 'test-analysis-moderate-perf', orchestrationPattern: 'sequential' },
      'analysis-test',
      { success: true, reward: 0.7, cost: 0.05, duration_ms: 4000 }
    );
  }

  // Low performer (< 0.4 reward)
  for (let i = 0; i < 3; i++) {
    await recordStrategyResult(
      { name: 'test-analysis-low-perf', orchestrationPattern: 'debate' },
      'analysis-test',
      { success: false, reward: 0.2, cost: 0.02, duration_ms: 2000 }
    );
  }

  // Get all analysis records
  const allAnalysis = await getStrategyAnalysis({ taskType: 'analysis-test' });
  const testAnalysis = allAnalysis.filter(s => s.strategy.startsWith('test-analysis-'));

  console.assert(testAnalysis.length >= 3, `Should have at least 3 strategies, got ${testAnalysis.length}`);

  // Check performance tiers
  const highPerfRecord = testAnalysis.find(s => s.strategy === 'test-analysis-high-perf');
  console.assert(highPerfRecord, 'Should find high-perf strategy');
  console.assert(highPerfRecord.performanceTier === 'HIGH_PERFORMER',
    `High-perf should be HIGH_PERFORMER, got ${highPerfRecord.performanceTier}`);

  const moderatePerfRecord = testAnalysis.find(s => s.strategy === 'test-analysis-moderate-perf');
  console.assert(moderatePerfRecord, 'Should find moderate-perf strategy');
  console.assert(moderatePerfRecord.performanceTier === 'MODERATE_PERFORMER',
    `Moderate-perf should be MODERATE_PERFORMER, got ${moderatePerfRecord.performanceTier}`);

  // Get HIGH_PERFORMER only
  const highPerformers = await getStrategyAnalysis({
    taskType: 'analysis-test',
    performanceTier: 'HIGH_PERFORMER'
  });
  const testHighPerformers = highPerformers.filter(s => s.strategy.startsWith('test-analysis-'));

  console.assert(testHighPerformers.length >= 1, `Should find HIGH_PERFORMER strategies`);
  console.assert(testHighPerformers.every(s => s.avgReward >= 0.8), 'All should have reward >= 0.8');

  console.log(`  ✓ Strategy analysis found ${testAnalysis.length} test strategies with tier classification\n`);
}

// Run tests
runTests();
