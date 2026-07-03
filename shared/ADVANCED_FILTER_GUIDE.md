# Advanced Filter Builder - Complete Guide

SQL WHERE clause builder for PostgreSQL with JSON operators, ranges, and pgvector similarity search. All queries use parameterized statements for SQL injection prevention.

## Quick Start

```javascript
import { AdvancedFilter, createFilter } from './advanced-filter.js';

// Create a filter
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .where('confidence', '>', 0.8);

// Build WHERE clause
const { sql, params } = filter.build();

// Use in query
const query = `SELECT * FROM workflow.worker_results WHERE ${sql}`;
client.query(query, params);
```

## Core Features

### 1. Basic WHERE Conditions

All operators use parameterized statements (`$1`, `$2`, etc.) for safety.

```javascript
filter
  .where('outcome', '=', 'success')           // outcome = $1
  .where('confidence', '>', 0.8)              // confidence > $2
  .where('duration_ms', '>=', 100)            // duration_ms >= $3
  .where('cost_usd', '!=', 0)                 // cost_usd != $4
  .where('model', '<>', 'test-model');        // model <> $5
```

**Supported Operators:**
- Comparison: `=`, `!=`, `>`, `>=`, `<`, `<=`, `<>`
- Text: `LIKE`, `ILIKE`
- Arrays: `IN`, `NOT IN`
- JSON: `@>` (contains), `<@` (contained by), `@@` (text search)
- Custom: `CONTAINS`, `STARTS_WITH`, `IS NULL`, `IS NOT NULL`

### 2. IN / NOT IN Operators

```javascript
// Find results from specific models
filter.where('model', 'IN', ['opus', 'sonnet', 'haiku']);
// => model IN ($1, $2, $3)

// Exclude error states
filter.where('outcome', 'NOT IN', ['error', 'failed']);
// => outcome NOT IN ($1, $2)
```

### 3. Text Search

```javascript
// ILIKE for case-insensitive pattern matching
filter.where('task_assigned', 'ILIKE', '%firmware%');
// => task_assigned ILIKE $1

// Custom operators for convenience
filter.where('task_assigned', 'CONTAINS', 'firmware');
// => task_assigned::text ILIKE '%' || $1 || '%'

filter.where('task_assigned', 'STARTS_WITH', 'Analyze');
// => task_assigned::text ILIKE $1 || '%'
```

### 4. Range Queries

```javascript
// Numeric ranges
filter.range('duration_ms', 100, 5000);
// => duration_ms >= $1 AND duration_ms <= $2

// Date ranges
const start = new Date('2026-06-01');
const end = new Date('2026-06-30');
filter.range('created_at', start, end);
// => created_at >= $1 AND created_at <= $2
```

### 5. JSON/JSONB Metadata Filtering

PostgreSQL JSONB operators for flexible metadata queries.

```javascript
// Check for field existence and value
filter.metadata({ retried: true });
// => metadata @> '{"retried": true}'::jsonb

// Multiple fields (all must match)
filter.metadata({ retried: true, outcome: 'success' });
// => metadata @> '{"retried": true, "outcome": "success"}'::jsonb

// Nested metadata paths (converts flat dotted keys to nested object)
filter.where('metadata.config.model', '=', 'opus');
// => metadata->'config'->>'model' = $1

filter.metadata({ 'config.parallelism': 4 });
// => metadata @> '{"config": {"parallelism": 4}}'::jsonb
```

**Available JSON Operators:**
- `@>`: Contains (left contains right)
- `<@`: Contained by (left contained by right)
- `@@`: Text search match

### 6. Full-Text Search

```javascript
// Search across all text columns
filter.fullTextSearch('firmware reverse engineering');
// => (outcome::text || model::text || task_assigned::text) ILIKE '%' || $1 || '%'

// Search specific field
filter.fullTextSearch('retry', 'description');
// => description::text ILIKE '%' || $1 || '%'
```

### 7. Vector Similarity Search (pgvector)

Find embeddings similar to a given vector using PostgreSQL pgvector extension.

```javascript
const queryVector = [0.1, -0.2, 0.5, ...]; // 384-dim vector
const threshold = 0.85; // Cosine distance threshold

filter.vectorSimilarity('result_embedding', queryVector, threshold);
// => (result_embedding <=> $1::vector) <= $2
```

**Parameters:**
- `embeddingField`: Column name (e.g., `'task_embedding'`, `'result_embedding'`)
- `vector`: Array of numbers (embedding vector)
- `threshold`: Similarity threshold (0-1, lower = more similar)

### 8. Combining Conditions: AND/OR/NOT

#### AND Group (all conditions must match)

```javascript
filter.and([
  { field: 'outcome', op: '=', value: 'success' },
  { field: 'confidence', op: '>', value: 0.8 }
]);
// => (outcome = $1 AND confidence > $2)
```

#### OR Group (any condition can match)

```javascript
filter.or([
  { field: 'model', op: '=', value: 'opus' },
  { field: 'model', op: '=', value: 'sonnet' },
  { field: 'model', op: '=', value: 'haiku' }
]);
// => (model = $1 OR model = $2 OR model = $3)
```

#### NOT (negate a condition)

```javascript
filter.not('outcome', '=', 'error');
// => NOT (outcome = $1)
```

#### Complex Nested Example

```javascript
filter
  .where('outcome', '=', 'success')
  .or([
    { field: 'confidence', op: '>', value: 0.9 },
    { field: 'duration_ms', op: '<', value: 1000 }
  ])
  .not('model', 'IN', ['test-model']);
// => outcome = $1 AND (confidence > $2 OR duration_ms < $3) AND NOT (model IN ($4))
```

## Building Queries

### 1. WHERE Clause Only

```javascript
const { sql, params } = filter.build();
// => { 
//      sql: "outcome = $1 AND confidence > $2", 
//      params: ['success', 0.8] 
//    }

const query = `SELECT * FROM workflow.worker_results WHERE ${sql}`;
client.query(query, params);
```

### 2. Full SELECT Query

```javascript
const { sql, params } = filter.buildQuery(
  'outcome, COUNT(*) as count',           // SELECT clause
  'outcome ASC',                           // ORDER BY clause (optional)
  10,                                      // LIMIT (optional)
  0                                        // OFFSET (optional)
);
// => {
//      sql: "SELECT outcome, COUNT(*) as count FROM workflow.worker_results 
//           WHERE outcome = $1 AND confidence > $2 ORDER BY outcome ASC LIMIT 10",
//      params: ['success', 0.8]
//    }
```

### 3. DELETE Query (with safety check)

```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'error');

const { sql, params } = filter.buildDelete();
// => {
//      sql: "DELETE FROM workflow.worker_results WHERE outcome = $1",
//      params: ['error']
//    }
```

**Safety Note:** `buildDelete()` throws an error if no WHERE conditions are set, preventing accidental deletion of entire tables.

### 4. UPDATE Query (with safety check)

```javascript
const { sql, params } = filter.buildUpdate({
  outcome: 'failed',
  updated_at: new Date()
});
// => {
//      sql: "UPDATE workflow.worker_results SET outcome = $1, updated_at = $2 
//           WHERE outcome = $3",
//      params: ['failed', Date, 'error']
//    }
```

**Safety Note:** `buildUpdate()` throws an error if no WHERE conditions are set.

## Preset Filters

Common filter patterns provided as ready-to-use presets:

```javascript
import { presets } from './advanced-filter.js';

// Successful workflows only
presets.successfulOnly('workflow.executions');
// => where outcome = 'success'

// High-confidence results (default: > 0.8)
presets.highConfidence('workflow.worker_results', 0.85);
// => where confidence > 0.85

// Recent executions (default: last 24 hours)
presets.recent('workflow.executions', 48);
// => where created_at > 48 hours ago

// Specific models
presets.byModel('workflow.worker_results', ['opus', 'sonnet']);
// => where model IN ('opus', 'sonnet')

// Quick executions only (default: < 5000ms)
presets.byQuickest('workflow.worker_results', 1000);
// => where duration_ms < 1000
```

## Real-World Examples

### Example 1: Find Recent High-Quality Results

```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .where('confidence', '>', 0.8)
  .range('created_at', 
    new Date(Date.now() - 24*60*60*1000),  // Last 24 hours
    new Date());

const { sql, params } = filter.buildQuery('model, COUNT(*)', 'model DESC');
const results = await client.query(sql, params);
```

### Example 2: Find Similar Tasks Using Vector Search

```javascript
const queryEmbedding = [0.1, -0.2, 0.5, ...]; // 384-dim

const filter = new AdvancedFilter('workflow.executions')
  .where('outcome', '=', 'success')
  .vectorSimilarity('task_embedding', queryEmbedding, 0.85)
  .range('created_at', new Date('2026-06-01'), new Date('2026-06-30'));

const { sql, params } = filter.buildQuery('*, task_embedding <=> $X as distance', 'distance ASC', 10);
const results = await client.query(sql, params);
```

### Example 3: Cost Analysis with Metadata Filtering

```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .metadata({ context_used: true, retried: false })
  .where('cost_usd', '>', 0)
  .or([
    { field: 'model', op: '=', value: 'opus' },
    { field: 'model', op: '=', value: 'gpt-4o' }
  ]);

const { sql, params } = filter.buildQuery(
  'model, SUM(cost_usd) as total_cost, COUNT(*) as count',
  'total_cost DESC'
);
const results = await client.query(sql, params);
```

### Example 4: Quality Assessment with Multiple Filters

```javascript
const filter = new AdvancedFilter('workflow.arbiter_decisions')
  .where('arbiter_model', 'IN', ['opus', 'sonnet'])
  .range('confidence', 0.75, 1.0)
  .range('created_at', new Date('2026-06-01'), new Date('2026-06-30'))
  .not('outcome', '=', 'error')
  .metadata({ reviewed: true });

const { sql, params } = filter.buildQuery(
  'arbiter_model, confidence, decision',
  'confidence DESC',
  20
);
const results = await client.query(sql, params);
```

## State Management

### Clone a Filter

Create an independent copy to branch off alternative filter paths:

```javascript
const filter1 = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success');

// Branch 1: High confidence
const filter2 = filter1.clone().where('confidence', '>', 0.9);

// Branch 2: Low cost
const filter3 = filter1.clone().where('cost_usd', '<', 0.05);

// filter1, filter2, filter3 are independent
```

### Reset a Filter

Clear all conditions and start fresh:

```javascript
filter.reset();
filter.where('outcome', '=', 'failed'); // New conditions
```

### Debug Filter State

Inspect the current filter state:

```javascript
const debug = filter.debug();
// => {
//      conditions: ['outcome = $1', 'confidence > $2'],
//      params: ['success', 0.8],
//      paramIndex: 3,
//      sql: 'outcome = $1 AND confidence > $2'
//    }
```

## Raw SQL Escape Hatch

For complex queries not covered by the builder:

```javascript
filter.raw('(confidence > 0.8 AND duration_ms < 5000)');
// Adds raw SQL condition as-is (caller responsible for SQL injection prevention)
```

**Warning:** Use sparingly. The builder is designed to prevent SQL injection through parameterization.

## Best Practices

1. **Always use parameterized queries** - The builder handles this automatically
2. **Use AND/OR groups for clarity** - Makes complex conditions readable
3. **Clone filters instead of reusing** - Prevents accidental state sharing
4. **Use presets for common patterns** - Reduces boilerplate
5. **Test with buildQuery()** - See full SQL before execution
6. **Validate parameters** - Especially user-supplied values
7. **Use metadata() for JSON fields** - Better than raw operators
8. **Set vector thresholds carefully** - Cosine distance 0-1 (0 = identical)

## Error Handling

The builder throws errors in these cases:

```javascript
// Missing WHERE on DELETE/UPDATE
filter.buildDelete();  // Error: "refuses to delete without WHERE clause"
filter.buildUpdate({outcome: 'success'});  // Error: "refuses to update without WHERE"

// Invalid operators
filter.where('field', 'IN', 'not-an-array');  // Error: "IN operator requires array"

// Missing table name
filter.buildQuery();  // Error: "requires tableName to be set"

// Invalid vector similarity
filter.vectorSimilarity('emb', [], 0.5);  // Error: "requires non-empty vector"
```

## Performance Considerations

1. **Vector Similarity:** Requires pgvector extension with HNSW index
   ```sql
   CREATE INDEX idx_embedding ON table USING ivfflat (embedding vector_cosine_ops);
   ```

2. **JSON Queries:** Use GIN indexes for fast JSONB lookups
   ```sql
   CREATE INDEX idx_metadata ON table USING GIN (metadata);
   ```

3. **Range Queries:** Use BTREE indexes for efficient range scans
   ```sql
   CREATE INDEX idx_created_at ON table (created_at);
   ```

4. **Parameterized Queries:** Benefit from PostgreSQL query plan caching

## Testing

Run the comprehensive test suite:

```bash
node shared/advanced-filter.test.js
```

Tests cover:
- All operators (comparison, text, array, JSON, custom)
- Range and vector similarity queries
- Complex nested AND/OR/NOT conditions
- Query building (SELECT, DELETE, UPDATE)
- State management (clone, reset, debug)
- Preset filters
- Edge cases and error handling

## Changelog

### v1.0.0 (2026-07-03)
- Initial release
- All operators: comparison, text, array, JSON, custom
- AND/OR/NOT logic for complex conditions
- Vector similarity search (pgvector)
- Query builders: SELECT, DELETE, UPDATE
- Preset filters for common patterns
- Comprehensive test suite (40+ tests)
