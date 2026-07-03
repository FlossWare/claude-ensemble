/**
 * Advanced Filter Builder - Test Suite
 *
 * Comprehensive tests demonstrating all filtering capabilities
 * for PostgreSQL queries with JSON operators and pgvector.
 */

import { AdvancedFilter, createFilter, presets } from './advanced-filter.js';

// Test utilities
function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  Error: ${err.message}`);
    process.exitCode = 1;
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

// ==================== TESTS ====================

console.log('\n=== Advanced Filter Tests ===\n');

// Basic WHERE conditions
test('Simple WHERE: outcome = success', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success');

  const { sql, params } = filter.build();
  assert(sql.includes('outcome = $1'), 'SQL should contain outcome condition');
  assertEqual(params[0], 'success', 'Params should contain success value');
});

test('Multiple WHERE conditions (chained)', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success')
    .where('confidence', '>', 0.8);

  const { sql, params } = filter.build();
  assert(sql.includes('outcome = $1'), 'Should have outcome condition');
  assert(sql.includes('confidence > $2'), 'Should have confidence condition');
  assertEqual(params.length, 2, 'Should have 2 parameters');
});

test('IN operator: model IN (opus, sonnet, haiku)', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('model', 'IN', ['opus', 'sonnet', 'haiku']);

  const { sql, params } = filter.build();
  assert(sql.includes('model IN'), 'Should contain IN operator');
  assert(sql.includes('$1, $2, $3'), 'Should have 3 placeholders');
  assertEqual(params.length, 3, 'Should have 3 parameters');
});

test('NOT IN operator', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', 'NOT IN', ['error', 'failed']);

  const { sql, params } = filter.build();
  assert(sql.includes('NOT IN'), 'Should contain NOT IN operator');
  assertEqual(params.length, 2, 'Should have 2 parameters');
});

test('Comparison operators: >, >=, <, <=, !=', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('duration_ms', '>', 100)
    .where('duration_ms', '<', 5000)
    .where('cost_usd', '!=', 0);

  const { sql, params } = filter.build();
  assert(sql.includes('> $1'), 'Should contain > operator');
  assert(sql.includes('< $2'), 'Should contain < operator');
  assert(sql.includes('!= $3'), 'Should contain != operator');
  assertEqual(params.length, 3, 'Should have 3 parameters');
});

test('LIKE and ILIKE for text search', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('task_assigned', 'ILIKE', '%firmware%');

  const { sql, params } = filter.build();
  assert(sql.includes('ILIKE'), 'Should contain ILIKE operator');
  assertEqual(params[0], '%firmware%', 'Parameter should contain wildcards');
});

test('Range queries', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .range('duration_ms', 100, 5000);

  const { sql, params } = filter.build();
  assert(sql.includes('>= $1'), 'Should have >= for min');
  assert(sql.includes('<= $2'), 'Should have <= for max');
  assertEqual(params[0], 100, 'Min parameter should be set');
  assertEqual(params[1], 5000, 'Max parameter should be set');
});

test('Date ranges', () => {
  const startDate = new Date('2026-06-01');
  const endDate = new Date('2026-06-30');

  const filter = new AdvancedFilter('workflow.worker_results')
    .range('created_at', startDate, endDate);

  const { sql, params } = filter.build();
  assert(sql.includes('created_at >= $1'), 'Should check created_at >= start');
  assert(sql.includes('created_at <= $2'), 'Should check created_at <= end');
  assertEqual(params[0].getTime(), startDate.getTime(), 'Start date should match');
  assertEqual(params[1].getTime(), endDate.getTime(), 'End date should match');
});

test('AND group of conditions', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .and([
      { field: 'outcome', op: '=', value: 'success' },
      { field: 'confidence', op: '>', value: 0.8 }
    ]);

  const { sql, params } = filter.build();
  assert(sql.includes('outcome = $1'), 'Should have outcome in AND group');
  assert(sql.includes('confidence > $2'), 'Should have confidence in AND group');
  assert(sql.includes('(') && sql.includes(')'), 'Should be wrapped in parentheses');
});

test('OR group of conditions', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .or([
      { field: 'model', op: '=', value: 'opus' },
      { field: 'model', op: '=', value: 'sonnet' },
      { field: 'model', op: '=', value: 'haiku' }
    ]);

  const { sql, params } = filter.build();
  assert(sql.includes('model = $1'), 'Should have first model');
  assert(sql.includes('OR'), 'Should have OR operator');
  assertEqual(params.length, 3, 'Should have 3 model parameters');
});

test('NOT condition', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .not('outcome', '=', 'error');

  const { sql, params } = filter.build();
  assert(sql.includes('NOT'), 'Should contain NOT operator');
  assert(sql.includes('outcome = $1'), 'Should contain negated condition');
  assertEqual(params[0], 'error', 'Parameter should be set');
});

test('Complex nested conditions: AND/OR/NOT', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success')
    .or([
      { field: 'confidence', op: '>', value: 0.9 },
      { field: 'duration_ms', op: '<', value: 1000 }
    ])
    .not('model', 'IN', ['test-model']);

  const { sql, params } = filter.build();
  assert(sql.includes('outcome = $1'), 'Should have outcome');
  assert(sql.includes('OR'), 'Should have OR group');
  assert(sql.includes('NOT'), 'Should have NOT clause');
  assert(sql.includes('AND'), 'Should join with AND');
});

// JSON metadata filtering
test('JSON containment: metadata @> { retried: true }', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .metadata({ retried: true });

  const { sql, params } = filter.build();
  assert(sql.includes('metadata @>'), 'Should use @> operator');
  assertEqual(typeof params[0], 'object', 'Parameter should be an object');
  assertEqual(params[0].retried, true, 'Parameter should contain retried field');
});

test('JSON nested metadata: metadata.config.model = opus', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('metadata.config.model', '=', 'opus');

  const { sql, params } = filter.build();
  assert(sql.includes("metadata"), 'Should reference metadata');
  assert(sql.includes("config"), 'Should reference config key');
  assert(sql.includes("model"), 'Should reference model key');
  assertEqual(params[0], 'opus', 'Parameter should be model value');
});

test('JSON multi-field containment', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .metadata({ retried: true, outcome: 'success' });

  const { sql, params } = filter.build();
  assert(sql.includes('metadata @>'), 'Should use @> operator');
  assertEqual(params[0].retried, true, 'Should contain retried');
  assertEqual(params[0].outcome, 'success', 'Should contain outcome');
});

test('Full-text search', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .fullTextSearch('firmware reverse engineering');

  const { sql, params } = filter.build();
  assert(sql.includes('ILIKE'), 'Should use ILIKE for text search');
  assertEqual(params[0], 'firmware reverse engineering', 'Parameter should contain search text');
});

test('Full-text search in specific field', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .fullTextSearch('retry', 'description');

  const { sql, params } = filter.build();
  assert(sql.includes('ILIKE'), 'Should use ILIKE');
  assertEqual(params[0], 'retry', 'Parameter should contain search term');
});

test('Vector similarity search (pgvector)', () => {
  const vector = new Array(384).fill(0.5);
  const filter = new AdvancedFilter('workflow.worker_results')
    .vectorSimilarity('result_embedding', vector, 0.85);

  const { sql, params } = filter.build();
  assert(sql.includes('<=>'), 'Should use pgvector distance operator');
  assert(sql.includes('<='), 'Should use <= for threshold');
  assertEqual(params[0], vector, 'First parameter should be vector');
  assertEqual(params[1], 0.85, 'Second parameter should be threshold');
});

test('Combined filtering: outcome + confidence + metadata + vector', () => {
  const vector = new Array(384).fill(0.5);
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success')
    .where('confidence', '>', 0.8)
    .metadata({ retried: false })
    .vectorSimilarity('result_embedding', vector, 0.9);

  const { sql, params } = filter.build();
  assert(params.length === 5, 'Should have 5 parameters (success, confidence, metadata, vector, threshold)');
  assert(sql.includes('AND'), 'Should join with AND operators');
  assert(sql.includes('<=>'), 'Should include vector distance operator');
});

// CUSTOM operators
test('CONTAINS operator for flexible text search', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('task_assigned', 'CONTAINS', 'firmware');

  const { sql, params } = filter.build();
  assert(sql.includes('ILIKE'), 'CONTAINS should expand to ILIKE');
  assert(sql.includes('%'), 'Should add wildcards');
});

test('STARTS_WITH operator', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('task_assigned', 'STARTS_WITH', 'Analyze');

  const { sql, params } = filter.build();
  assert(sql.includes('ILIKE'), 'STARTS_WITH should use ILIKE');
  assertEqual(params[0], 'Analyze', 'Parameter should contain search term');
});

// Raw SQL (escape hatch)
test('Raw SQL condition', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .raw('(confidence > 0.8 AND duration_ms < 5000)');

  const { sql, params } = filter.build();
  assert(sql.includes('(confidence > 0.8'), 'Should include raw SQL as-is');
});

// Full query building
test('buildQuery: SELECT with WHERE, ORDER BY, LIMIT', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success');

  const { sql } = filter.buildQuery(
    'model, COUNT(*)',
    'model ASC',
    10
  );

  assert(sql.includes('SELECT model, COUNT(*)'), 'Should select specified columns');
  assert(sql.includes('FROM workflow.worker_results'), 'Should specify table');
  assert(sql.includes('WHERE'), 'Should include WHERE clause');
  assert(sql.includes('ORDER BY model ASC'), 'Should include ORDER BY');
  assert(sql.includes('LIMIT 10'), 'Should include LIMIT');
});

test('buildDelete: DELETE with WHERE clause', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'error');

  const { sql, params } = filter.buildDelete();
  assert(sql.includes('DELETE FROM'), 'Should be DELETE query');
  assert(sql.includes('WHERE'), 'Should include WHERE clause');
  assertEqual(params[0], 'error', 'Should have error parameter');
});

test('buildDelete: Refuses to DELETE without WHERE', () => {
  const filter = new AdvancedFilter('workflow.worker_results');

  try {
    filter.buildDelete();
    throw new Error('Should have thrown');
  } catch (err) {
    assert(err.message.includes('refuses to delete'), 'Should refuse unguarded delete');
  }
});

test('buildUpdate: UPDATE with WHERE clause', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'error');

  const { sql, params } = filter.buildUpdate({ outcome: 'failed', updated_at: new Date() });
  assert(sql.includes('UPDATE'), 'Should be UPDATE query');
  assert(sql.includes('SET'), 'Should have SET clause');
  assert(sql.includes('WHERE'), 'Should have WHERE clause');
  assertEqual(params.length, 3, 'Should have 3 parameters (2 updates + 1 condition)');
});

test('buildUpdate: Refuses to UPDATE without WHERE', () => {
  const filter = new AdvancedFilter('workflow.worker_results');

  try {
    filter.buildUpdate({ outcome: 'success' });
    throw new Error('Should have thrown');
  } catch (err) {
    assert(err.message.includes('refuses to update'), 'Should refuse unguarded update');
  }
});

// Filter state management
test('reset() clears all conditions', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success')
    .where('confidence', '>', 0.8)
    .reset();

  const { sql, hasConditions } = filter.build();
  assertEqual(hasConditions, false, 'Should have no conditions after reset');
  assertEqual(sql, '', 'SQL should be empty after reset');
});

test('clone() creates independent copy', () => {
  const filter1 = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success');

  const filter2 = filter1.clone()
    .where('confidence', '>', 0.8);

  const { sql: sql1 } = filter1.build();
  const { sql: sql2 } = filter2.build();

  assert(!sql1.includes('confidence'), 'Original should not have confidence condition');
  assert(sql2.includes('confidence'), 'Clone should have confidence condition');
});

test('debug() returns filter state', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success');

  const debug = filter.debug();
  assert(debug.conditions, 'Should have conditions');
  assert(Array.isArray(debug.params), 'Should have params array');
  assert(debug.sql, 'Should have SQL string');
});

// Preset filters
test('Preset: successfulOnly()', () => {
  const filter = presets.successfulOnly('workflow.worker_results');

  const { sql, params } = filter.build();
  assert(sql.includes('outcome = $1'), 'Should filter for success');
  assertEqual(params[0], 'success', 'Should have success parameter');
});

test('Preset: highConfidence()', () => {
  const filter = presets.highConfidence('workflow.worker_results', 0.85);

  const { sql, params } = filter.build();
  assert(sql.includes('confidence > $1'), 'Should filter by confidence');
  assertEqual(params[0], 0.85, 'Should have confidence threshold');
});

test('Preset: recent()', () => {
  const filter = presets.recent('workflow.worker_results', 24);

  const { sql, params } = filter.build();
  assert(sql.includes('created_at > $1'), 'Should filter by date');
  assert(params[0] instanceof Date, 'Parameter should be Date object');
});

test('Preset: byModel()', () => {
  const filter = presets.byModel('workflow.worker_results', ['opus', 'sonnet']);

  const { sql, params } = filter.build();
  assert(sql.includes('model IN'), 'Should filter by model');
  assertEqual(params.length, 2, 'Should have 2 model parameters');
});

test('Preset: byQuickest()', () => {
  const filter = presets.byQuickest('workflow.worker_results', 1000);

  const { sql, params } = filter.build();
  assert(sql.includes('duration_ms <'), 'Should filter by duration');
  assertEqual(params[0], 1000, 'Should have max duration parameter');
});

// createFilter utility
test('createFilter() factory function', () => {
  const filter = createFilter('workflow.executions');

  assert(filter instanceof AdvancedFilter, 'Should return AdvancedFilter instance');
  assertEqual(filter.tableName, 'workflow.executions', 'Should set table name');
});

// Edge cases
test('Empty conditions returns empty WHERE clause', () => {
  const filter = new AdvancedFilter('workflow.worker_results');

  const { sql, hasConditions } = filter.build();
  assertEqual(hasConditions, false, 'Should have no conditions');
  assertEqual(sql, '', 'SQL should be empty string');
});

test('Multiple chained operations with correct parameter ordering', () => {
  const filter = new AdvancedFilter('workflow.worker_results')
    .where('outcome', '=', 'success')
    .where('confidence', '>', 0.8)
    .where('model', 'IN', ['opus', 'sonnet'])
    .range('duration_ms', 100, 5000);

  const { params } = filter.build();
  assertEqual(params[0], 'success', 'First param');
  assertEqual(params[1], 0.8, 'Second param');
  assertEqual(params[2], 'opus', 'Third param (IN)');
  assertEqual(params[3], 'sonnet', 'Fourth param (IN)');
  assertEqual(params[4], 100, 'Fifth param (range min)');
  assertEqual(params[5], 5000, 'Sixth param (range max)');
});

console.log('\n=== All Tests Passed ===\n');
