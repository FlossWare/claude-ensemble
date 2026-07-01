#!/usr/bin/env node
/**
 * Test knowledge-system-adapter.js integration
 */

import { getKnowledgeSystem, isAvailable, storeWebResearch } from './knowledge-system-adapter.js';

async function main() {
  console.log('============================================================');
  console.log('KNOWLEDGE SYSTEM ADAPTER TEST');
  console.log('============================================================');

  // Check availability
  console.log('\n1. Checking availability...');
  const available = isAvailable();
  console.log(`  ${available ? '✓' : '✗'} Knowledge system ${available ? 'available' : 'NOT available'}`);

  if (!available) {
    console.error('\n❌ Knowledge system not available - check PostgreSQL and dependencies');
    process.exit(1);
  }

  const ks = getKnowledgeSystem();

  // Test storage
  console.log('\n2. Storing knowledge...');
  const entryId = await ks.storeKnowledge({
    content: 'Node.js knowledge system adapter provides seamless PostgreSQL integration with semantic chunking',
    source: 'test-adapter',
    source_type: 'test',
    metadata: {
      topic: 'integration',
      test: true,
      timestamp: new Date().toISOString(),
    },
    actor: 'test-script',
  });
  console.log(`  ✓ Stored entry ${entryId}`);

  // Test semantic search
  console.log('\n3. Semantic search...');
  const results = await ks.semanticSearch('postgresql integration', { limit: 5 });
  console.log(`  ✓ Found ${results.length} results`);
  for (const r of results) {
    console.log(`    - ${r.content.substring(0, 60)}... (similarity: ${r.similarity.toFixed(3)})`);
  }

  // Test provenance
  console.log(`\n4. Provenance for entry ${entryId}...`);
  const provenance = await ks.getProvenance(entryId);
  console.log(`  ✓ Found ${provenance.length} provenance records`);
  for (const p of provenance) {
    console.log(`    - ${p.action} by ${p.actor} at ${p.timestamp}`);
  }

  // Test stats
  console.log('\n5. Statistics...');
  const stats = await ks.getStats();
  console.log(`  ✓ Total entries: ${stats.total_entries}`);
  console.log(`  ✓ By source type:`, stats.by_source_type);

  // Test web research helper
  console.log('\n6. Store web research finding...');
  const webEntryId = await storeWebResearch({
    title: 'pgvector achieves 2x faster similarity search than ChromaDB',
    abstract: 'PostgreSQL pgvector extension with HNSW index provides 0.4ms queries',
    source: 'test-research',
    topics: ['database', 'vector-search', 'postgresql'],
    tags: ['pgvector', 'performance'],
    relevanceScore: 0.95,
    url: 'https://example.com/pgvector-benchmark',
  });
  console.log(`  ✓ Stored web research entry ${webEntryId}`);

  // Search for the web research
  console.log('\n7. Search for web research...');
  const webResults = await ks.semanticSearch('vector search performance', {
    limit: 5,
    source_type: 'web_synthesis',
  });
  console.log(`  ✓ Found ${webResults.length} web research results`);
  for (const r of webResults) {
    const meta = r.metadata || {};
    console.log(`    - ${meta.title || 'Untitled'} (${r.similarity.toFixed(3)})`);
  }

  console.log('\n✅ All tests passed!');
}

main().catch(err => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
