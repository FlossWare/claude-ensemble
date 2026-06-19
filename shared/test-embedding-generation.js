#!/usr/bin/env node
/**
 * Test script for embedding generation
 *
 * Tests:
 * 1. Single text embedding
 * 2. Batch embedding (3 texts)
 * 3. Empty input handling
 * 4. Invalid input handling
 * 5. Graceful fallback when sentence-transformers unavailable
 */

const { _generateEmbedding, generateEmbeddingsBatch } = require('./workflow-storage-adapter.js');

async function testSingleEmbedding() {
  console.log('\n=== Test 1: Single Text Embedding ===');
  const text = "firmware reverse engineering methodology";
  const embedding = await _generateEmbedding(text);

  if (embedding) {
    console.log(`✓ Generated ${embedding.length}-dim embedding`);
    console.log(`  First 5 dims: [${embedding.slice(0, 5).map(x => x.toFixed(3)).join(', ')}]`);
  } else {
    console.log('✗ Failed to generate embedding (sentence-transformers may not be installed)');
  }

  return embedding !== null;
}

async function testBatchEmbedding() {
  console.log('\n=== Test 2: Batch Embedding (3 texts) ===');
  const texts = [
    "deep research workflow orchestration",
    "multi-AI consensus arbiter pattern",
    "PostgreSQL pgvector similarity search"
  ];

  const embeddings = await generateEmbeddingsBatch(texts);

  if (embeddings && embeddings.length === 3) {
    console.log(`✓ Generated ${embeddings.length} embeddings`);
    embeddings.forEach((emb, i) => {
      console.log(`  Text ${i+1}: ${emb.length}-dim [${emb.slice(0, 3).map(x => x.toFixed(3)).join(', ')}...]`);
    });
  } else {
    console.log('✗ Failed to generate batch embeddings');
  }

  return embeddings !== null && embeddings.length === 3;
}

async function testEmptyInput() {
  console.log('\n=== Test 3: Empty Input Handling ===');
  const embedding1 = await _generateEmbedding([]);
  const embedding2 = await _generateEmbedding("");

  if (embedding1 === null && embedding2 === null) {
    console.log('✓ Empty inputs return null (graceful fallback)');
    return true;
  } else {
    console.log('✗ Empty inputs should return null');
    return false;
  }
}

async function testInvalidInput() {
  console.log('\n=== Test 4: Invalid Input Handling ===');
  const embedding1 = await _generateEmbedding([123, 456]); // numbers instead of strings
  const embedding2 = await _generateEmbedding(["valid", "", "text"]); // mixed valid/empty

  if (embedding1 === null && embedding2 === null) {
    console.log('✓ Invalid inputs return null (graceful fallback)');
    return true;
  } else {
    console.log('✗ Invalid inputs should return null');
    return false;
  }
}

async function testArrayVsSingle() {
  console.log('\n=== Test 5: Array vs Single Text Return Format ===');

  const singleResult = await _generateEmbedding("single text");
  const arrayResult = await _generateEmbedding(["text 1", "text 2"]);

  if (singleResult === null) {
    console.log('⚠ Skipping test (embeddings unavailable)');
    return true;
  }

  const isSingleArray = Array.isArray(singleResult) && typeof singleResult[0] === 'number';
  const isNestedArray = Array.isArray(arrayResult) && Array.isArray(arrayResult[0]);

  if (isSingleArray && isNestedArray) {
    console.log('✓ Single text returns 1D array, multiple texts return 2D array');
    console.log(`  Single: [${singleResult.slice(0, 3).map(x => x.toFixed(3)).join(', ')}...]`);
    console.log(`  Array:  [[${arrayResult[0].slice(0, 3).map(x => x.toFixed(3)).join(', ')}...], ...]`);
    return true;
  } else {
    console.log('✗ Return format incorrect');
    console.log(`  Single is 1D array: ${isSingleArray}`);
    console.log(`  Array is 2D array: ${isNestedArray}`);
    return false;
  }
}

async function runTests() {
  console.log('Testing Embedding Generation Implementation');
  console.log('===========================================');

  const results = [];

  results.push(await testSingleEmbedding());
  results.push(await testBatchEmbedding());
  results.push(await testEmptyInput());
  results.push(await testInvalidInput());
  results.push(await testArrayVsSingle());

  const passed = results.filter(r => r).length;
  const total = results.length;

  console.log('\n===========================================');
  console.log(`Results: ${passed}/${total} tests passed`);

  if (passed === total) {
    console.log('✓ All tests passed!');
    process.exit(0);
  } else {
    console.log('✗ Some tests failed');
    process.exit(1);
  }
}

// Run tests
runTests().catch(err => {
  console.error('Test suite error:', err);
  process.exit(1);
});
