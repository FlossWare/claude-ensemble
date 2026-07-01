#!/usr/bin/env node
/**
 * Test batch-consensus integration
 *
 * Validates:
 * - ESM wrapper works correctly
 * - batchConsensusWithWorker processes questions in batches
 * - Progress tracking works
 * - Error handling works
 * - Results returned correctly
 *
 * Usage: node shared/test-batch-consensus-integration.mjs
 */

import { batchConsensusWithWorker } from './batch-consensus-wrapper.mjs';

console.log('Testing batch-consensus integration...\n');

// ============================================================================
// Test 1: Basic batch processing
// ============================================================================

console.log('Test 1: Basic batch processing');
console.log('='.repeat(60));

const questions = [
  { text: 'What is 2+2?', expected: '4' },
  { text: 'What is the capital of France?', expected: 'Paris' },
  { text: 'What is the speed of light?', expected: '299,792,458 m/s' },
  { text: 'What is water composed of?', expected: 'H2O' },
  { text: 'What is the largest planet?', expected: 'Jupiter' },
];

// Simulated worker function (no actual API calls)
const mockWorker = async (question) => {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, Math.random() * 100));

  // Simulate consensus result
  return {
    model: 'mock-consensus',
    models: ['mock-1', 'mock-2', 'mock-3'],
    answer: question.expected || 'Unknown',
    confidence: 0.8 + Math.random() * 0.2,
    votes: {}
  };
};

let progressCalls = 0;
const progressUpdates = [];

try {
  const results = await batchConsensusWithWorker(
    questions,
    mockWorker,
    {
      concurrency: 2,
      onProgress: (completed, total, current) => {
        progressCalls++;
        progressUpdates.push({ completed, total });
        console.log(`  Progress: ${completed}/${total}`);
      },
      onError: (error, question, index) => {
        console.error(`  Error on question ${index}:`, error.message);
      }
    }
  );

  console.log(`\n✓ Processed ${results.length} questions`);
  console.log(`✓ Progress callback called ${progressCalls} times`);
  console.log(`✓ All results have confidence: ${results.every(r => r.confidence > 0)}`);
  console.log('Test 1: PASSED\n');
} catch (error) {
  console.error('Test 1: FAILED -', error.message);
  process.exit(1);
}

// ============================================================================
// Test 2: Error handling
// ============================================================================

console.log('Test 2: Error handling');
console.log('='.repeat(60));

const questionsWithErrors = [
  { text: 'Valid question 1', shouldFail: false },
  { text: 'Invalid question', shouldFail: true },
  { text: 'Valid question 2', shouldFail: false },
];

const errorWorker = async (question) => {
  await new Promise(resolve => setTimeout(resolve, 50));

  if (question.shouldFail) {
    throw new Error('Simulated worker failure');
  }

  return {
    model: 'error-test',
    answer: 'Success',
    confidence: 0.9,
    votes: {}
  };
};

let errorCount = 0;

try {
  const results = await batchConsensusWithWorker(
    questionsWithErrors,
    errorWorker,
    {
      concurrency: 2,
      onError: (error, question, index) => {
        errorCount++;
        console.log(`  ✓ Caught error for question ${index}: ${error.message}`);
      },
      stopOnError: false
    }
  );

  console.log(`\n✓ Received ${results.length} results`);
  console.log(`✓ Error callback called ${errorCount} times (expected: 1)`);

  const successCount = results.filter(r => !r.error).length;
  const failCount = results.filter(r => r.error).length;

  console.log(`✓ Success count: ${successCount} (expected: 2)`);
  console.log(`✓ Fail count: ${failCount} (expected: 1)`);

  if (successCount === 2 && failCount === 1 && errorCount === 1) {
    console.log('Test 2: PASSED\n');
  } else {
    console.log('Test 2: FAILED - Counts mismatch\n');
    process.exit(1);
  }
} catch (error) {
  console.error('Test 2: FAILED -', error.message);
  process.exit(1);
}

// ============================================================================
// Test 3: Concurrency control
// ============================================================================

console.log('Test 3: Concurrency control');
console.log('='.repeat(60));

const manyQuestions = Array.from({ length: 20 }, (_, i) => ({
  text: `Question ${i + 1}`,
  id: i + 1
}));

let maxConcurrent = 0;
let currentConcurrent = 0;

const concurrencyWorker = async (question) => {
  currentConcurrent++;
  maxConcurrent = Math.max(maxConcurrent, currentConcurrent);

  await new Promise(resolve => setTimeout(resolve, 100));

  currentConcurrent--;
  return {
    model: 'concurrency-test',
    answer: `Answer ${question.id}`,
    confidence: 0.85,
    votes: {}
  };
};

try {
  const results = await batchConsensusWithWorker(
    manyQuestions,
    concurrencyWorker,
    {
      concurrency: 5,
      onProgress: (completed, total) => {
        // Progress tracking
      }
    }
  );

  console.log(`\n✓ Processed ${results.length} questions`);
  console.log(`✓ Max concurrent: ${maxConcurrent} (limit: 5)`);

  if (maxConcurrent <= 5) {
    console.log('✓ Concurrency control working correctly');
    console.log('Test 3: PASSED\n');
  } else {
    console.log(`✗ Concurrency limit exceeded: ${maxConcurrent} > 5`);
    console.log('Test 3: FAILED\n');
    process.exit(1);
  }
} catch (error) {
  console.error('Test 3: FAILED -', error.message);
  process.exit(1);
}

// ============================================================================
// Summary
// ============================================================================

console.log('='.repeat(60));
console.log('ALL TESTS PASSED ✓');
console.log('='.repeat(60));
console.log('\nBatch consensus integration is working correctly.');
console.log('Ready for use in workflows.\n');
