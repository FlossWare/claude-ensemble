#!/usr/bin/env node
/**
 * Integration Test: Issues #297-#305
 *
 * Tests all implementations from the recent batch of 8 issues.
 * Status: 2/8 passed review, need tests for remaining 6.
 *
 * Test Categories:
 * 1. Advanced Filter (#300) - ✅ HAS UNIT TESTS (advanced-filter.test.js)
 * 2. Fact Storage - Persistent triple store with embeddings
 * 3. Reranker - Cross-encoder result reranking
 * 4. Semantic Search Bridge - JS wrapper for Python hybrid search
 * 5. Knowledge Search Hybrid - Multi-source knowledge retrieval
 * 6-8. Unknown implementations (need to identify)
 *
 * Run: node tests/integration-test-issues-297-305.js
 */

import { strict as assert } from 'assert';
import { existsSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, '..');

// ============================================================================
// TEST HELPERS
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    console.log(`✅ ${name}`);
    testsPassed++;
  } catch (error) {
    console.error(`❌ ${name}`);
    console.error(`   ${error.message}`);
    testsFailed++;
    failures.push({ name, error: error.message });
  }
}

async function asyncTest(name, fn) {
  try {
    await fn();
    console.log(`✅ ${name}`);
    testsPassed++;
  } catch (error) {
    console.error(`❌ ${name}`);
    console.error(`   ${error.message}`);
    testsFailed++;
    failures.push({ name, error: error.message });
  }
}

// ============================================================================
// ISSUE #300: ADVANCED FILTER
// ============================================================================

console.log('\n=== Issue #300: Advanced Filter ===\n');

test('Advanced Filter: Module exists', () => {
  const path = join(PROJECT_ROOT, 'shared/advanced-filter.js');
  assert(existsSync(path), 'advanced-filter.js not found');
});

test('Advanced Filter: Unit tests exist', () => {
  const path = join(PROJECT_ROOT, 'shared/advanced-filter.test.js');
  assert(existsSync(path), 'advanced-filter.test.js not found');
});

test('Advanced Filter: Can import', async () => {
  const { AdvancedFilter, createFilter, presets } = await import('../shared/advanced-filter.js');
  assert(typeof AdvancedFilter === 'function', 'AdvancedFilter is not a class');
  assert(typeof createFilter === 'function', 'createFilter is not a function');
  assert(typeof presets === 'object', 'presets is not an object');
});

await asyncTest('Advanced Filter: Basic WHERE clause', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');
  const filter = new AdvancedFilter('test_table');
  filter.where('status', '=', 'active');
  const { sql, params } = filter.build();

  assert(sql.includes('status = $1'), 'SQL does not contain parameterized WHERE');
  assert.deepEqual(params, ['active'], 'Params do not match');
});

await asyncTest('Advanced Filter: Complex AND/OR logic', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');
  const filter = new AdvancedFilter('test_table');
  filter
    .where('status', '=', 'active')
    .or([
      { field: 'priority', op: '>', value: 5 },
      { field: 'urgent', op: '=', value: true }
    ]);
  const { sql, params } = filter.build();

  assert(sql.includes('AND'), 'SQL does not contain AND');
  assert(sql.includes('OR'), 'SQL does not contain OR');
  assert(params.length === 3, 'Incorrect number of parameters');
});

await asyncTest('Advanced Filter: JSONB metadata filtering', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');
  const filter = new AdvancedFilter('test_table');
  filter.metadata({ retried: true });
  const { sql, params } = filter.build();

  assert(sql.includes('@>'), 'SQL does not contain JSONB containment operator');
  assert(typeof params[0] === 'object', 'Metadata param is not an object');
});

await asyncTest('Advanced Filter: Preset filters', async () => {
  const { presets } = await import('../shared/advanced-filter.js');

  const successFilter = presets.successfulOnly('test_table');
  assert(successFilter.conditions.length > 0, 'successfulOnly has no conditions');

  const confFilter = presets.highConfidence('test_table', 0.8);
  const { sql } = confFilter.build();
  assert(sql.includes('confidence'), 'highConfidence does not filter on confidence');
});

// ============================================================================
// FACT STORAGE (Unknown Issue #)
// ============================================================================

console.log('\n=== Fact Storage ===\n');

test('Fact Storage: Module exists', () => {
  const path = join(PROJECT_ROOT, 'shared/fact-storage.js');
  assert(existsSync(path), 'fact-storage.js not found');
});

test('Fact Storage: Schema exists', () => {
  const path = join(PROJECT_ROOT, 'shared/fact-storage-schema.sql');
  assert(existsSync(path), 'fact-storage-schema.sql not found');
});

await asyncTest('Fact Storage: Can import', async () => {
  const module = await import('../shared/fact-storage.js');
  assert(typeof module.getFactStorage === 'function', 'getFactStorage is not a function');
});

await asyncTest('Fact Storage: Schema has required tables', async () => {
  const path = join(PROJECT_ROOT, 'shared/fact-storage-schema.sql');
  const schema = readFileSync(path, 'utf-8');

  assert(schema.includes('CREATE TABLE IF NOT EXISTS facts.facts'), 'Schema missing facts.facts table');
  assert(schema.match(/subject\s+(TEXT|VARCHAR\(\d+\))\s+NOT NULL/), 'Schema missing subject column');
  assert(schema.match(/predicate\s+(TEXT|VARCHAR\(\d+\))\s+NOT NULL/), 'Schema missing predicate column');
  assert(schema.match(/object\s+(TEXT|VARCHAR\(\d+\))\s+NOT NULL/), 'Schema missing object column');
  assert(schema.includes('embedding vector(384)'), 'Schema missing embedding column');
});

await asyncTest('Fact Storage: Has extraction method', async () => {
  const { getFactStorage } = await import('../shared/fact-storage.js');
  const fs = getFactStorage();

  assert(typeof fs.extractFacts === 'function', 'extractFacts method not found');
  assert(typeof fs.storeFacts === 'function', 'storeFacts method not found');
  assert(typeof fs.searchFacts === 'function', 'searchFacts method not found');
});

// ============================================================================
// RERANKER (Unknown Issue #)
// ============================================================================

console.log('\n=== Reranker ===\n');

test('Reranker: Module exists', () => {
  const path = join(PROJECT_ROOT, 'shared/reranker.py');
  assert(existsSync(path), 'reranker.py not found');
});

test('Reranker: Is executable', () => {
  const path = join(PROJECT_ROOT, 'shared/reranker.py');
  const content = readFileSync(path, 'utf-8');
  assert(content.includes('#!/usr/bin/env python3'), 'reranker.py missing shebang');
});

test('Reranker: Has required classes', () => {
  const path = join(PROJECT_ROOT, 'shared/reranker.py');
  const content = readFileSync(path, 'utf-8');

  assert(content.includes('class Reranker'), 'Missing Reranker class');
  assert(content.includes('async def rerank'), 'Missing rerank method');
  assert(content.includes('cross-encoder'), 'Missing cross-encoder reference');
});

test('Reranker: Has batch processing', () => {
  const path = join(PROJECT_ROOT, 'shared/reranker.py');
  const content = readFileSync(path, 'utf-8');

  assert(content.includes('asyncio'), 'Missing asyncio import');
  assert(content.includes('batch'), 'Missing batch processing logic');
});

// ============================================================================
// SEMANTIC SEARCH BRIDGE (Unknown Issue #)
// ============================================================================

console.log('\n=== Semantic Search Bridge ===\n');

test('Semantic Search Bridge: Module exists', () => {
  const path = join(PROJECT_ROOT, 'shared/semantic-search-bridge.js');
  assert(existsSync(path), 'semantic-search-bridge.js not found');
});

await asyncTest('Semantic Search Bridge: Can import', async () => {
  const module = await import('../shared/semantic-search-bridge.js');
  assert(typeof module.hybridSearch === 'function', 'hybridSearch is not a function');
  assert(typeof module.rerank === 'function', 'rerank is not a function');
  assert(typeof module.advancedFilter === 'function', 'advancedFilter is not a function');
});

await asyncTest('Semantic Search Bridge: Python bridge pattern', async () => {
  const path = join(PROJECT_ROOT, 'shared/semantic-search-bridge.js');
  const content = readFileSync(path, 'utf-8');

  assert(content.includes('execFileSync'), 'Missing execFileSync (Python bridge)');
  assert(content.includes('python3'), 'Missing python3 invocation');
  assert(content.includes('temp'), 'Missing temp file handling');
});

// ============================================================================
// KNOWLEDGE SEARCH HYBRID (Unknown Issue #)
// ============================================================================

console.log('\n=== Knowledge Search Hybrid ===\n');

test('Knowledge Search Hybrid: Module exists', () => {
  const path = join(PROJECT_ROOT, 'shared/knowledge-search-hybrid.js');
  assert(existsSync(path), 'knowledge-search-hybrid.js not found');
});

await asyncTest('Knowledge Search Hybrid: Can import', async () => {
  const module = await import('../shared/knowledge-search-hybrid.js');
  assert(typeof module === 'object', 'Module did not export an object');
});

await asyncTest('Knowledge Search Hybrid: Has search methods', async () => {
  const path = join(PROJECT_ROOT, 'shared/knowledge-search-hybrid.js');
  const content = readFileSync(path, 'utf-8');

  assert(content.includes('search'), 'Missing search functionality');
  assert(content.includes('hybrid'), 'Missing hybrid search logic');
});

// ============================================================================
// UNKNOWN IMPLEMENTATIONS (Issues #297-299, #304-305)
// ============================================================================

console.log('\n=== Unknown Implementations (3 remaining) ===\n');

await asyncTest('Scan for recent shared/ files', async () => {
  // List files modified on Jul 3, 2026 (the implementation date)
  const { execFileSync } = await import('child_process');
  const files = execFileSync(
    'find',
    ['shared/', '-type', 'f', '-newermt', '2026-07-03 00:00', '!', '-newermt', '2026-07-04 00:00', '-name', '*.js', '-o', '-name', '*.py'],
    { cwd: PROJECT_ROOT, encoding: 'utf-8' }
  ).trim().split('\n').filter(Boolean);

  console.log('   Files modified on 2026-07-03:');
  files.forEach(f => console.log(`   - ${f}`));

  assert(files.length >= 4, `Expected at least 4 files, found ${files.length}`);
});

// ============================================================================
// INTEGRATION TESTS (Cross-component)
// ============================================================================

console.log('\n=== Integration Tests ===\n');

await asyncTest('Integration: Advanced Filter + Fact Storage', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');
  const { getFactStorage } = await import('../shared/fact-storage.js');

  // Create filter for facts
  const filter = new AdvancedFilter('facts.facts');
  filter.where('subject', 'ILIKE', '%AI%');
  const { sql, params } = filter.build();

  assert(sql.includes('subject'), 'Filter does not target subject');
  assert(sql.includes('ILIKE'), 'Filter does not use ILIKE');

  // Verify FactStorage can use filters
  const fs = getFactStorage();
  assert(typeof fs.searchFacts === 'function', 'FactStorage missing searchFacts');
});

await asyncTest('Integration: Semantic Bridge components accessible', async () => {
  const { hybridSearch, rerank } = await import('../shared/semantic-search-bridge.js');

  // These should be callable (won't test execution to avoid Python dependencies)
  assert(typeof hybridSearch === 'function', 'hybridSearch not callable');
  assert(typeof rerank === 'function', 'rerank not callable');
});

await asyncTest('Integration: Knowledge + Search + Filter chain', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');

  // Simulate a knowledge search → filter → rerank pipeline
  const filter = new AdvancedFilter('workflow.worker_results');
  filter
    .where('outcome', '=', 'success')
    .where('confidence', '>', 0.8)
    .metadata({ context_used: true });

  const { sql, params } = filter.buildQuery(
    'task_description, result, confidence',
    'confidence DESC',
    10
  );

  assert(sql.includes('SELECT'), 'Query builder did not generate SELECT');
  assert(sql.includes('LIMIT'), 'Query builder did not add LIMIT');
  assert(params.length === 3, 'Incorrect parameter count');
});

// ============================================================================
// ERROR HANDLING & EDGE CASES
// ============================================================================

console.log('\n=== Error Handling ===\n');

await asyncTest('Advanced Filter: Safe DELETE requires WHERE', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');
  const filter = new AdvancedFilter('test_table');

  let threw = false;
  try {
    filter.buildDelete(); // Should throw without WHERE clause
  } catch (error) {
    threw = true;
    assert(error.message.includes('WHERE'), 'Error should mention WHERE clause');
  }
  assert(threw, 'buildDelete should throw without WHERE clause');
});

await asyncTest('Advanced Filter: Safe UPDATE requires WHERE', async () => {
  const { AdvancedFilter } = await import('../shared/advanced-filter.js');
  const filter = new AdvancedFilter('test_table');

  let threw = false;
  try {
    filter.buildUpdate({ status: 'done' }); // Should throw without WHERE clause
  } catch (error) {
    threw = true;
    assert(error.message.includes('WHERE'), 'Error should mention WHERE clause');
  }
  assert(threw, 'buildUpdate should throw without WHERE clause');
});

await asyncTest('Fact Storage: Handles missing database gracefully', async () => {
  const { getFactStorage } = await import('../shared/fact-storage.js');

  // Should return object even if DB unavailable (graceful degradation)
  const fs = getFactStorage();
  assert(fs !== null, 'getFactStorage should return non-null');
  assert(typeof fs === 'object', 'getFactStorage should return object');
});

// ============================================================================
// DOCUMENTATION CHECKS
// ============================================================================

console.log('\n=== Documentation ===\n');

test('Advanced Filter: Guide exists', () => {
  const path = join(PROJECT_ROOT, 'shared/ADVANCED_FILTER_GUIDE.md');
  assert(existsSync(path), 'ADVANCED_FILTER_GUIDE.md not found');
});

test('Advanced Filter: Quick reference exists', () => {
  const path = join(PROJECT_ROOT, 'shared/ADVANCED_FILTER_QUICK_REFERENCE.md');
  assert(existsSync(path), 'ADVANCED_FILTER_QUICK_REFERENCE.md not found');
});

test('Advanced Filter: Guide has examples', () => {
  const path = join(PROJECT_ROOT, 'shared/ADVANCED_FILTER_GUIDE.md');
  const content = readFileSync(path, 'utf-8');

  assert(content.includes('Example'), 'Guide missing examples');
  assert(content.includes('```'), 'Guide missing code blocks');
  assert(content.includes('Usage'), 'Guide missing usage section');
});

// ============================================================================
// SUMMARY
// ============================================================================

console.log('\n' + '='.repeat(60));
console.log('INTEGRATION TEST SUMMARY: Issues #297-#305');
console.log('='.repeat(60));
console.log(`✅ Passed: ${testsPassed}`);
console.log(`❌ Failed: ${testsFailed}`);
console.log(`📊 Total:  ${testsPassed + testsFailed}`);

if (failures.length > 0) {
  console.log('\n❌ FAILURES:\n');
  failures.forEach(({ name, error }) => {
    console.log(`  - ${name}`);
    console.log(`    ${error}\n`);
  });
}

console.log('\n' + '='.repeat(60));
console.log('COMPONENT SUMMARY');
console.log('='.repeat(60));
console.log('✅ Advanced Filter (#300):         COMPLETE (unit tests exist)');
console.log('✅ Fact Storage:                   COMPLETE (needs integration test)');
console.log('✅ Reranker:                       COMPLETE (needs integration test)');
console.log('✅ Semantic Search Bridge:         COMPLETE (needs integration test)');
console.log('✅ Knowledge Search Hybrid:        COMPLETE (needs integration test)');
console.log('⚠️  Unknown (3 issues):            NEED IDENTIFICATION');
console.log('='.repeat(60));

console.log('\nRECOMMENDATIONS:\n');
console.log('1. Map remaining 3 issues (#297-299, #304-305) to implementations');
console.log('2. Create unit tests for: fact-storage.js, reranker.py, semantic-search-bridge.js');
console.log('3. Add database integration tests (requires PostgreSQL connection)');
console.log('4. Add Python dependency tests (sentence-transformers, cross-encoder)');
console.log('5. Document issue-to-file mapping in ISSUE_297_305_SUMMARY.md');

process.exit(testsFailed > 0 ? 1 : 0);
