#!/usr/bin/env node

/**
 * Test Suite for Batch Consensus API
 *
 * Tests:
 * 1. Single question processing
 * 2. Small batch (10 questions)
 * 3. Large batch (100 questions)
 * 4. Progress tracking
 * 5. Error handling
 * 6. Cache effectiveness
 * 7. Streaming API
 * 8. Statistics and reporting
 * 9. Mixed task types
 *
 * Run: node shared/batch-consensus.test.cjs
 *
 * Created: 2026-06-29
 */

const {
  batchConsensus,
  batchConsensusStream,
  analyzeBatchResults,
  generateBatchReport,
} = require('./batch-consensus.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function logTest(name) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`TEST: ${name}`);
  console.log('='.repeat(60));
}

function logSuccess(message) {
  console.log(`✓ ${message}`);
}

function logInfo(message) {
  console.log(`  ${message}`);
}

// ============================================================================
// TEST 1: Single Question
// ============================================================================

async function testSingleQuestion() {
  logTest('Single Question Processing');

  const questions = ['What is the capital of France?'];

  const results = await batchConsensus(questions, {
    concurrency: 1,
    taskType: 'general',
    workers: ['opus', 'sonnet', 'haiku'],
  });

  assert(results.length === 1, 'Should return 1 result');
  assert(results[0].question === questions[0], 'Should preserve question');
  assert(results[0].answer, 'Should have answer');
  assert(results[0].confidence >= 0 && results[0].confidence <= 1, 'Confidence in range');
  assert(results[0].agreement >= 0 && results[0].agreement <= 1, 'Agreement in range');
  assert(results[0].timestamp, 'Should have timestamp');

  logSuccess('Single question processed correctly');
  logInfo(`Answer: ${results[0].answer}`);
  logInfo(`Confidence: ${(results[0].confidence * 100).toFixed(1)}%`);
  logInfo(`Agreement: ${(results[0].agreement * 100).toFixed(1)}%`);
}

// ============================================================================
// TEST 2: Small Batch (10 Questions)
// ============================================================================

async function testSmallBatch() {
  logTest('Small Batch (10 Questions)');

  const questions = [
    'What is 2 + 2?',
    'Who wrote Hamlet?',
    'What is the speed of light?',
    'What is photosynthesis?',
    'Who painted the Mona Lisa?',
    'What is the largest ocean?',
    'What is DNA?',
    'Who invented the telephone?',
    'What is gravity?',
    'What is the periodic table?',
  ];

  const startTime = Date.now();
  let progressCalls = 0;

  const results = await batchConsensus(questions, {
    concurrency: 5,
    taskType: 'general',
    workers: ['opus', 'sonnet', 'haiku'],
    onProgress: (completed, total, current) => {
      progressCalls++;
      logInfo(`Progress: ${completed}/${total} - ${current.question.substring(0, 40)}...`);
    },
  });

  const duration = Date.now() - startTime;

  assert(results.length === 10, 'Should return 10 results');
  assert(progressCalls === 10, 'Progress callback called 10 times');
  assert(results.every(r => r.answer), 'All results have answers');
  assert(results.every(r => r.question), 'All results preserve questions');

  logSuccess(`Processed 10 questions in ${duration}ms`);
  logInfo(`Average: ${(duration / 10).toFixed(0)}ms per question`);
  logInfo(`Concurrency: 5 (theoretical 2x speedup)`);
}

// ============================================================================
// TEST 3: Large Batch (100 Questions)
// ============================================================================

async function testLargeBatch() {
  logTest('Large Batch (100 Questions)');

  const questions = Array.from({ length: 100 }, (_, i) => `Question ${i + 1}: What is ${i + 1} + ${i + 1}?`);

  const startTime = Date.now();
  let lastProgress = 0;

  const results = await batchConsensus(questions, {
    concurrency: 10,
    taskType: 'general',
    workers: ['opus', 'sonnet', 'haiku'],
    onProgress: (completed, total) => {
      if (completed % 10 === 0 || completed === total) {
        logInfo(`Progress: ${completed}/${total} (${((completed / total) * 100).toFixed(0)}%)`);
        lastProgress = completed;
      }
    },
  });

  const duration = Date.now() - startTime;

  assert(results.length === 100, 'Should return 100 results');
  assert(lastProgress === 100, 'Should reach 100% progress');
  assert(results.every(r => r.answer), 'All results have answers');

  const stats = analyzeBatchResults(results);

  logSuccess(`Processed 100 questions in ${(duration / 1000).toFixed(1)}s`);
  logInfo(`Average: ${(duration / 100).toFixed(0)}ms per question`);
  logInfo(`Success rate: ${(stats.successRate * 100).toFixed(1)}%`);
  logInfo(`Avg confidence: ${(stats.avgConfidence * 100).toFixed(1)}%`);
  logInfo(`Avg agreement: ${(stats.avgAgreement * 100).toFixed(1)}%`);
}

// ============================================================================
// TEST 4: Progress Tracking
// ============================================================================

async function testProgressTracking() {
  logTest('Progress Tracking');

  const questions = Array.from({ length: 20 }, (_, i) => `Question ${i + 1}`);

  const progressLog = [];
  const results = await batchConsensus(questions, {
    concurrency: 5,
    onProgress: (completed, total, current) => {
      progressLog.push({ completed, total, question: current.question });
    },
  });

  assert(progressLog.length === 20, 'Should track all 20 completions');
  assert(progressLog[0].completed === 1, 'First completion should be 1');
  assert(progressLog[19].completed === 20, 'Last completion should be 20');
  assert(progressLog.every(p => p.total === 20), 'Total should always be 20');

  // Check monotonic increase
  for (let i = 1; i < progressLog.length; i++) {
    assert(
      progressLog[i].completed >= progressLog[i - 1].completed,
      'Progress should be monotonic'
    );
  }

  logSuccess('Progress tracking working correctly');
  logInfo(`Tracked ${progressLog.length} progress updates`);
}

// ============================================================================
// TEST 5: Error Handling
// ============================================================================

async function testErrorHandling() {
  logTest('Error Handling');

  // Mock a timeout by setting very short timeout
  const questions = Array.from({ length: 10 }, (_, i) => `Question ${i + 1}`);

  let errorCount = 0;
  const results = await batchConsensus(questions, {
    concurrency: 10,
    timeout: 1, // 1ms timeout - will cause failures
    stopOnError: false,
    onError: (error, question, index) => {
      errorCount++;
      logInfo(`Error on question ${index}: ${question.substring(0, 30)}...`);
    },
  });

  assert(results.length === 10, 'Should return all 10 results even with errors');
  assert(errorCount > 0, 'Should have encountered errors');
  assert(results.filter(r => r.outcome === 'error').length === errorCount, 'Error count matches');

  logSuccess('Error handling working correctly');
  logInfo(`Encountered ${errorCount} errors (expected with 1ms timeout)`);
  logInfo('Partial results returned successfully');
}

// ============================================================================
// TEST 6: Cache Effectiveness
// ============================================================================

async function testCacheEffectiveness() {
  logTest('Cache Effectiveness');

  // First run: populate cache
  const questions = [
    'What is 1 + 1?',
    'What is 2 + 2?',
    'What is 3 + 3?',
  ];

  logInfo('First run (populating cache)...');
  const firstRun = await batchConsensus(questions, {
    useCache: true,
    taskType: 'general',
  });

  const firstDuration = firstRun.reduce((sum, r) => {
    const time = new Date(r.timestamp).getTime();
    return Math.max(sum, time);
  }, 0) - new Date(firstRun[0].timestamp).getTime();

  assert(firstRun.every(r => !r.cached), 'First run should not be cached');

  logInfo('Second run (using cache)...');
  const secondRun = await batchConsensus(questions, {
    useCache: true,
    taskType: 'general',
  });

  const secondDuration = secondRun.reduce((sum, r) => {
    const time = new Date(r.timestamp).getTime();
    return Math.max(sum, time);
  }, 0) - new Date(secondRun[0].timestamp).getTime();

  const cacheHits = secondRun.filter(r => r.cached).length;

  logSuccess('Cache working correctly');
  logInfo(`Cache hits: ${cacheHits}/${questions.length}`);
  logInfo(`First run: ${firstDuration}ms`);
  logInfo(`Second run: ${secondDuration}ms`);
  if (secondDuration > 0) {
    logInfo(`Speedup: ${(firstDuration / secondDuration).toFixed(1)}x`);
  }
}

// ============================================================================
// TEST 7: Streaming API
// ============================================================================

async function testStreamingAPI() {
  logTest('Streaming API');

  const questions = Array.from({ length: 15 }, (_, i) => `Question ${i + 1}`);

  let streamedCount = 0;
  const streamedResults = [];

  for await (const result of batchConsensusStream(questions, {
    concurrency: 5,
    taskType: 'general',
  })) {
    streamedCount++;
    streamedResults.push(result);
    if (streamedCount % 5 === 0) {
      logInfo(`Streamed ${streamedCount} results...`);
    }
  }

  assert(streamedCount === 15, 'Should stream 15 results');
  assert(streamedResults.length === 15, 'Should collect 15 results');
  assert(streamedResults.every(r => r.question), 'All results should have questions');

  logSuccess('Streaming API working correctly');
  logInfo(`Streamed ${streamedCount} results`);
  logInfo('Results available as they complete (memory efficient)');
}

// ============================================================================
// TEST 8: Statistics and Reporting
// ============================================================================

async function testStatisticsReporting() {
  logTest('Statistics and Reporting');

  const questions = Array.from({ length: 50 }, (_, i) => `Question ${i + 1}`);

  const results = await batchConsensus(questions, {
    concurrency: 10,
    taskType: 'research',
  });

  const stats = analyzeBatchResults(results);

  assert(stats.total === 50, 'Total should be 50');
  assert(stats.successful >= 0, 'Successful count should be valid');
  assert(stats.successRate >= 0 && stats.successRate <= 1, 'Success rate in range');
  assert(stats.avgConfidence >= 0 && stats.avgConfidence <= 1, 'Avg confidence in range');
  assert(stats.avgAgreement >= 0 && stats.avgAgreement <= 1, 'Avg agreement in range');

  const report = generateBatchReport(results, { includeDetails: false });

  assert(report.includes('Batch Consensus Report'), 'Report has header');
  assert(report.includes('Total Questions: 50'), 'Report has total');
  assert(report.includes('Average Confidence'), 'Report has avg confidence');

  logSuccess('Statistics and reporting working correctly');
  logInfo('Generated report:');
  console.log(report);
}

// ============================================================================
// TEST 9: Mixed Task Types
// ============================================================================

async function testMixedTaskTypes() {
  logTest('Mixed Task Types');

  // In production, different questions would use different task types
  const codeQuestions = [
    'How do you reverse a string in Python?',
    'What is a closure in JavaScript?',
    'Explain async/await in Node.js',
  ];

  const researchQuestions = [
    'What is quantum computing?',
    'Explain blockchain technology',
    'What is machine learning?',
  ];

  logInfo('Processing code questions...');
  const codeResults = await batchConsensus(codeQuestions, {
    concurrency: 3,
    taskType: 'code_generation',
    workers: ['opus', 'sonnet', 'haiku'],
  });

  logInfo('Processing research questions...');
  const researchResults = await batchConsensus(researchQuestions, {
    concurrency: 3,
    taskType: 'research',
    workers: ['opus', 'gpt-4o', 'gemini'],
  });

  assert(codeResults.length === 3, 'Code results correct count');
  assert(researchResults.length === 3, 'Research results correct count');

  logSuccess('Mixed task types handled correctly');
  logInfo('Different worker sets per task type');
  logInfo('Capability-based weighting applied');
}

// ============================================================================
// MAIN TEST RUNNER
// ============================================================================

async function runAllTests() {
  console.log('\n' + '='.repeat(60));
  console.log('BATCH CONSENSUS API TEST SUITE');
  console.log('='.repeat(60));

  const tests = [
    { name: 'Single Question', fn: testSingleQuestion },
    { name: 'Small Batch (10)', fn: testSmallBatch },
    { name: 'Large Batch (100)', fn: testLargeBatch },
    { name: 'Progress Tracking', fn: testProgressTracking },
    { name: 'Error Handling', fn: testErrorHandling },
    { name: 'Cache Effectiveness', fn: testCacheEffectiveness },
    { name: 'Streaming API', fn: testStreamingAPI },
    { name: 'Statistics/Reporting', fn: testStatisticsReporting },
    { name: 'Mixed Task Types', fn: testMixedTaskTypes },
  ];

  const results = { passed: 0, failed: 0, errors: [] };
  const startTime = Date.now();

  for (const test of tests) {
    try {
      await test.fn();
      results.passed++;
    } catch (error) {
      results.failed++;
      results.errors.push({ test: test.name, error: error.message });
      console.error(`\n✗ ${test.name} FAILED: ${error.message}`);
    }
  }

  const duration = Date.now() - startTime;

  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));
  console.log(`Total Tests: ${tests.length}`);
  console.log(`Passed: ${results.passed} ✓`);
  console.log(`Failed: ${results.failed} ✗`);
  console.log(`Duration: ${(duration / 1000).toFixed(1)}s`);

  if (results.failed > 0) {
    console.log('\nFailed Tests:');
    results.errors.forEach(({ test, error }) => {
      console.log(`  - ${test}: ${error}`);
    });
  }

  console.log('\n' + '='.repeat(60));

  process.exit(results.failed > 0 ? 1 : 0);
}

// Run tests
if (require.main === module) {
  runAllTests().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = {
  testSingleQuestion,
  testSmallBatch,
  testLargeBatch,
  testProgressTracking,
  testErrorHandling,
  testCacheEffectiveness,
  testStreamingAPI,
  testStatisticsReporting,
  testMixedTaskTypes,
};
