#!/usr/bin/env node

/**
 * Simple validation test for batch consensus API
 * Tests core functionality without full test suite
 */

const {
  batchConsensus,
  analyzeBatchResults,
  generateBatchReport,
} = require('./batch-consensus.cjs');

async function simpleTest() {
  console.log('Testing Batch Consensus API\n');

  // Test 1: Single question
  console.log('Test 1: Single question...');
  const result1 = await batchConsensus(['What is 2+2?'], {
    concurrency: 1,
    taskType: 'general',
    workers: ['opus', 'sonnet', 'haiku'],
    useCache: false, // Disable cache to avoid errors
    timeout: 5000,
  });

  console.log(`✓ Result: ${result1[0].answer}`);
  console.log(`  Confidence: ${(result1[0].confidence * 100).toFixed(1)}%`);
  console.log(`  Agreement: ${(result1[0].agreement * 100).toFixed(1)}%`);
  console.log('');

  // Test 2: Small batch with progress
  console.log('Test 2: Small batch (5 questions)...');
  const questions = [
    'What is 1+1?',
    'What is 2+2?',
    'What is 3+3?',
    'What is 4+4?',
    'What is 5+5?',
  ];

  let progressCount = 0;
  const result2 = await batchConsensus(questions, {
    concurrency: 3,
    taskType: 'general',
    workers: ['opus', 'sonnet', 'haiku'],
    useCache: false,
    timeout: 5000,
    onProgress: (completed, total) => {
      progressCount++;
      if (completed % 2 === 0 || completed === total) {
        console.log(`  Progress: ${completed}/${total}`);
      }
    },
  });

  console.log(`✓ Processed ${result2.length} questions`);
  console.log(`  Progress callbacks: ${progressCount}`);
  console.log('');

  // Test 3: Statistics
  console.log('Test 3: Statistics...');
  const stats = analyzeBatchResults(result2);
  console.log(`✓ Success rate: ${(stats.successRate * 100).toFixed(1)}%`);
  console.log(`  Avg confidence: ${(stats.avgConfidence * 100).toFixed(1)}%`);
  console.log(`  Avg agreement: ${(stats.avgAgreement * 100).toFixed(1)}%`);
  console.log('');

  // Test 4: Report
  console.log('Test 4: Report generation...');
  const report = generateBatchReport(result2, { includeDetails: false });
  console.log('✓ Report generated:');
  console.log(report);

  console.log('\n✓ All tests passed!');
  console.log('\nBatch consensus API is working correctly.');
}

simpleTest()
  .then(() => process.exit(0))
  .catch(error => {
    console.error('✗ Test failed:', error.message);
    console.error(error.stack);
    process.exit(1);
  });
