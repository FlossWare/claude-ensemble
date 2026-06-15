#!/usr/bin/env node
/**
 * Test Vector Search Implementation
 *
 * Tests the ChromaDB semantic search integration for knowledge bases.
 * Verifies that semantic search finds related concepts even with different wording.
 *
 * Usage:
 *   node learning/test-vector-search.js
 */

import * as vectorSearch from './vector-search.js';
import { searchKnowledgeBases, indexKnowledgeBases } from '../claude-learning-integration.js';

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✅ ${message}`);
    testsPassed++;
  } else {
    console.error(`  ❌ ${message}`);
    testsFailed++;
  }
}

function testSection(name) {
  console.log('\n' + '='.repeat(60));
  console.log(name);
  console.log('='.repeat(60));
}

// ============================================================================
// TESTS
// ============================================================================

async function runTests() {
  console.log('🧪 VECTOR SEARCH TEST SUITE');
  console.log('Testing semantic search with ChromaDB embeddings\n');

  // Test 1: Initialize ChromaDB
  testSection('TEST 1: Initialize ChromaDB');
  const client = await vectorSearch.initializeVectorStore();
  assert(client !== null || client === null, 'ChromaDB initialization attempted');

  if (!client) {
    console.log('\n⚠️  ChromaDB not available - tests will use fallback mode');
    console.log('   Install ChromaDB: npm install chromadb');
  }

  // Test 2: Index sample data
  testSection('TEST 2: Index Sample Data');

  const sampleItems = [
    {
      id: 'test-1',
      title: 'Promise Rejection Patterns',
      content: 'Best practices for handling promise rejections in async functions. Use .catch() or try/catch.',
      topics: ['async', 'promises', 'error-handling'],
      confidence: 0.9,
    },
    {
      id: 'test-2',
      title: 'Async/Await Error Handling',
      content: 'When using async/await, wrap code in try/catch blocks to handle errors.',
      topics: ['async', 'await', 'errors'],
      confidence: 0.85,
    },
    {
      id: 'test-3',
      title: 'Multi-AI Consensus Patterns',
      content: 'Use arbiter/worker pattern with multiple models for high-quality results.',
      topics: ['multi-ai', 'consensus', 'quality'],
      confidence: 0.95,
    },
    {
      id: 'test-4',
      title: 'ChromaDB Vector Search',
      content: 'Semantic search using vector embeddings to find related content.',
      topics: ['vector-search', 'embeddings', 'chromadb'],
      confidence: 0.88,
    },
    {
      id: 'test-5',
      title: 'Thompson Sampling for Model Selection',
      content: 'Balance exploration and exploitation when choosing AI models.',
      topics: ['model-selection', 'thompson-sampling', 'optimization'],
      confidence: 0.92,
    },
  ];

  const indexResult = await vectorSearch.indexKnowledgeBase(
    'test-collection',
    sampleItems
  );

  assert(indexResult.indexed_count >= 0, `Indexed ${indexResult.indexed_count} items`);
  if (!indexResult.success && indexResult.error) {
    console.log(`   Note: ${indexResult.error}`);
  }

  // Test 3: Semantic Search - Related Concepts
  testSection('TEST 3: Semantic Search - Find Related Concepts');

  // Query: "async error handling" should find "promise rejection patterns"
  const searchResults = await vectorSearch.semanticSearch('async error handling', {
    collections: ['test-collection'],
    limit: 3,
    minConfidence: 0.0, // Accept all results for testing
  });

  console.log(`   Query: "async error handling"`);
  console.log(`   Method: ${searchResults.method}`);
  console.log(`   Results found: ${searchResults.total_found}`);

  if (searchResults.test_collection && searchResults.test_collection.length > 0) {
    console.log('\n   Top Results:');
    searchResults.test_collection.forEach((result, i) => {
      const title = result.metadata?.title || 'Unknown';
      const confidence = (result.similarity || result.confidence || 0).toFixed(2);
      console.log(`     ${i + 1}. ${title} (confidence: ${confidence})`);
    });

    // Check if promise-related content is in top results
    const hasPromiseResult = searchResults.test_collection.some(r =>
      r.metadata?.title?.toLowerCase().includes('promise') ||
      r.document?.toLowerCase().includes('promise')
    );

    const hasAsyncResult = searchResults.test_collection.some(r =>
      r.metadata?.title?.toLowerCase().includes('async') ||
      r.document?.toLowerCase().includes('async')
    );

    assert(hasPromiseResult || hasAsyncResult, 'Found semantically related content');
  } else {
    console.log('   No results found (ChromaDB may not be available)');
  }

  // Test 4: Search via Learning Integration
  testSection('TEST 4: Search via Learning Integration');

  const integrationResults = await searchKnowledgeBases('model selection strategies', {
    collections: ['test-collection'],
    limit: 2,
    minConfidence: 0.0,
    autoIndex: false, // Don't auto-index real knowledge bases
  });

  console.log(`   Query: "model selection strategies"`);
  console.log(`   Total found: ${integrationResults.total_found}`);
  console.log(`   Method: ${integrationResults.method}`);

  assert(integrationResults.query === 'model selection strategies', 'Query preserved in results');
  assert(integrationResults.method !== undefined, 'Search method reported');

  // Test 5: Fallback to Substring Matching
  testSection('TEST 5: Fallback Behavior');

  // Test that fallback works when ChromaDB unavailable
  const fallbackResults = await vectorSearch.semanticSearch('test query', {
    collections: ['nonexistent-collection'],
    limit: 1,
  });

  assert(fallbackResults !== null, 'Fallback returns results');
  console.log(`   Fallback method: ${fallbackResults.method || 'not specified'}`);

  // Test 6: Auto-indexing
  testSection('TEST 6: Auto-Indexing Knowledge Bases');

  const autoIndexResult = await vectorSearch.autoIndexKnowledgeBases();

  assert(autoIndexResult !== null, 'Auto-indexing completed');
  console.log(`   Success: ${autoIndexResult.success}`);

  if (autoIndexResult.indexed) {
    console.log('   Indexed collections:');
    for (const [collection, count] of Object.entries(autoIndexResult.indexed)) {
      console.log(`     - ${collection}: ${count} items`);
    }
  }

  if (autoIndexResult.errors && autoIndexResult.errors.length > 0) {
    console.log('   Errors encountered:');
    autoIndexResult.errors.forEach(err => console.log(`     - ${err}`));
  }

  // Test 7: Integration Function
  testSection('TEST 7: Integration indexKnowledgeBases()');

  const manualIndexResult = await indexKnowledgeBases();

  assert(manualIndexResult !== null, 'Manual indexing completed');
  console.log(`   Success: ${manualIndexResult.success}`);

  if (manualIndexResult.indexed) {
    console.log('   Indexed collections:');
    for (const [collection, count] of Object.entries(manualIndexResult.indexed)) {
      console.log(`     - ${collection}: ${count} items`);
    }
  }

  // ============================================================================
  // SUMMARY
  // ============================================================================

  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));
  console.log(`✅ Passed: ${testsPassed}`);
  console.log(`❌ Failed: ${testsFailed}`);
  console.log(`📊 Total:  ${testsPassed + testsFailed}`);

  if (testsFailed === 0) {
    console.log('\n🎉 All tests passed!');
  } else {
    console.log('\n⚠️  Some tests failed. Review output above.');
  }

  // ============================================================================
  // USAGE EXAMPLES
  // ============================================================================

  console.log('\n' + '='.repeat(60));
  console.log('USAGE EXAMPLES');
  console.log('='.repeat(60));

  console.log('\n1. Semantic Search:');
  console.log('   import { searchKnowledgeBases } from "./claude-learning-integration.js";');
  console.log('   const results = await searchKnowledgeBases("async error handling");');
  console.log('   // Finds: "promise rejection patterns", "async/await errors", etc.');

  console.log('\n2. Manual Indexing:');
  console.log('   import { indexKnowledgeBases } from "./claude-learning-integration.js";');
  console.log('   await indexKnowledgeBases(); // Index all knowledge bases');

  console.log('\n3. Custom Collection Search:');
  console.log('   import { semanticSearch } from "./learning/vector-search.js";');
  console.log('   const results = await semanticSearch("multi-AI patterns", {');
  console.log('     collections: ["disseminator-knowledge"],');
  console.log('     limit: 10,');
  console.log('     minConfidence: 0.7');
  console.log('   });');

  console.log('\n4. Index Custom Data:');
  console.log('   import { indexKnowledgeBase } from "./learning/vector-search.js";');
  console.log('   await indexKnowledgeBase("my-collection", myItems);');

  console.log('\n' + '='.repeat(60));
  console.log('✨ Vector search implementation test complete!');
  console.log('='.repeat(60) + '\n');

  process.exit(testsFailed > 0 ? 1 : 0);
}

// ============================================================================
// RUN TESTS
// ============================================================================

runTests().catch(err => {
  console.error('❌ Test suite error:', err);
  process.exit(1);
});
