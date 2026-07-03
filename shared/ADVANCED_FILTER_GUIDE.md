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

## Usage Examples

### Basic WHERE Clauses

#### Simple Equality Check
```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success');

const { sql, params } = filter.build();
// sql: "outcome = $1"
// params: ['success']

const results = await client.query(
  `SELECT * FROM workflow.worker_results WHERE ${sql}`,
  params
);
```

#### Multiple Conditions (AND)
```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .where('confidence', '>', 0.8)
  .where('model', '=', 'opus');

const { sql, params } = filter.build();
// sql: "outcome = $1 AND confidence > $2 AND model = $3"
// params: ['success', 0.8, 'opus']
```

#### Comparison Operators
```javascript
const filter = new AdvancedFilter('workflow.worker_results');

// Greater than
filter.where('duration_ms', '>', 1000);  // Slow tasks

// Less than or equal
filter.where('cost_usd', '<=', 0.10);    // Cheap tasks

// Not equal
filter.where('outcome', '!=', 'error');  // Non-errors

// Greater than or equal
filter.where('confidence', '>=', 0.75);  // Good confidence
```

### Complex AND/OR/NOT Logic

#### OR Conditions
```javascript
// Find results from any of three models
const filter = new AdvancedFilter('workflow.worker_results')
  .or([
    { field: 'model', op: '=', value: 'opus' },
    { field: 'model', op: '=', value: 'sonnet' },
    { field: 'model', op: '=', value: 'haiku' }
  ]);

const { sql, params } = filter.build();
// sql: "(model = $1 OR model = $2 OR model = $3)"
// params: ['opus', 'sonnet', 'haiku']
```

#### Combining AND with OR
```javascript
// Success OR high confidence, AND not errors
const filter = new AdvancedFilter('workflow.worker_results')
  .or([
    { field: 'outcome', op: '=', value: 'success' },
    { field: 'confidence', op: '>', value: 0.95 }
  ])
  .where('outcome', '!=', 'error');

const { sql, params } = filter.build();
// sql: "(outcome = $1 OR confidence > $2) AND outcome != $3"
// params: ['success', 0.95, 'error']
```

#### NOT Conditions
```javascript
// Exclude certain models
const filter = new AdvancedFilter('workflow.worker_results')
  .not('model', 'IN', ['test-model', 'debug-model']);

const { sql, params } = filter.build();
// sql: "NOT (model IN ($1, $2))"
// params: ['test-model', 'debug-model']
```

#### Complex Nested Example
```javascript
// High confidence OR fast, success outcome, but exclude test models, not expensive
const filter = new AdvancedFilter('workflow.worker_results')
  .or([
    { field: 'confidence', op: '>', value: 0.95 },
    { field: 'duration_ms', op: '<', value: 500 }
  ])
  .where('outcome', '=', 'success')
  .not('model', 'IN', ['test-model', 'debug-model'])
  .where('cost_usd', '<', 1.0);

const { sql, params } = filter.build();
// sql: "(confidence > $1 OR duration_ms < $2) AND outcome = $3 AND NOT (model IN ($4, $5)) AND cost_usd < $6"
// params: [0.95, 500, 'success', 'test-model', 'debug-model', 1.0]
```

### Range Filters

#### Numeric Ranges
```javascript
// Tasks between 1-5 seconds
const filter = new AdvancedFilter('workflow.worker_results')
  .range('duration_ms', 1000, 5000);

const { sql, params } = filter.build();
// sql: "duration_ms >= $1 AND duration_ms <= $2"
// params: [1000, 5000]
```

#### Date Ranges
```javascript
// Tasks from last 7 days
const now = new Date();
const sevenDaysAgo = new Date(now.getTime() - 7*24*60*60*1000);

const filter = new AdvancedFilter('workflow.worker_results')
  .range('created_at', sevenDaysAgo, now);

const { sql, params } = filter.build();
// sql: "created_at >= $1 AND created_at <= $2"
// params: [sevenDaysAgo, now]
```

#### Cost Ranges
```javascript
// Moderately expensive tasks ($0.10 - $1.00)
const filter = new AdvancedFilter('workflow.worker_results')
  .range('cost_usd', 0.10, 1.00);

const { sql, params } = filter.build();
// sql: "cost_usd >= $1 AND cost_usd <= $2"
// params: [0.10, 1.00]
```

#### Confidence Ranges with Success Filter
```javascript
// Good confidence (70-90%) successful tasks
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .range('confidence', 0.7, 0.9);

const { sql, params } = filter.build();
// sql: "outcome = $1 AND confidence >= $2 AND confidence <= $3"
// params: ['success', 0.7, 0.9]
```

### Metadata Filtering

#### Simple Metadata Match
```javascript
// Find retried tasks that succeeded
const filter = new AdvancedFilter('workflow.worker_results')
  .metadata({ retried: true, outcome: 'success' });

const { sql, params } = filter.build();
// sql: "metadata @> '{\"retried\": true, \"outcome\": \"success\"}'::jsonb"
// params: []
```

#### Nested Metadata (Config)
```javascript
// Find tasks with specific parallelism setting
const filter = new AdvancedFilter('workflow.executions')
  .metadata({ 'config.parallelism': 4, 'config.timeout': 60 });

const { sql, params } = filter.build();
// sql: "metadata @> '{\"config\": {\"parallelism\": 4, \"timeout\": 60}}'::jsonb"
// params: []
```

#### Metadata with Other Conditions
```javascript
// High-priority tasks that were cached
const filter = new AdvancedFilter('workflow.executions')
  .where('outcome', '=', 'success')
  .metadata({ cached: true })
  .where('confidence', '>', 0.8);

const { sql, params } = filter.build();
// sql: "outcome = $1 AND metadata @> '{\"cached\": true}'::jsonb AND confidence > $2"
// params: ['success', 0.8]
```

### Text Search

#### Case-Insensitive Pattern Match
```javascript
// Find tasks mentioning firmware
const filter = new AdvancedFilter('workflow.worker_results')
  .where('task_assigned', 'ILIKE', '%firmware%');

const { sql, params } = filter.build();
// sql: "task_assigned ILIKE $1"
// params: ['%firmware%']
```

#### CONTAINS Helper (case-insensitive substring)
```javascript
// Tasks containing "java" (matches "Java", "JAVA", etc.)
const filter = new AdvancedFilter('workflow.worker_results')
  .where('task_assigned', 'CONTAINS', 'java');

const { sql, params } = filter.build();
// sql: "task_assigned::text ILIKE '%' || $1 || '%'"
// params: ['java']
```

#### STARTS_WITH Helper
```javascript
// Tasks starting with "Analyze"
const filter = new AdvancedFilter('workflow.worker_results')
  .where('task_assigned', 'STARTS_WITH', 'Analyze');

const { sql, params } = filter.build();
// sql: "task_assigned::text ILIKE $1 || '%'"
// params: ['Analyze']
```

#### Full-Text Search
```javascript
// Search across multiple fields
const filter = new AdvancedFilter('workflow.worker_results')
  .fullTextSearch('retry algorithm', 'result');

const { sql, params } = filter.build();
// sql: "result::text ILIKE '%' || $1 || '%'"
// params: ['retry algorithm']
```

### Real-World Examples

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

### Example 5: Model Performance Comparison

```javascript
// Find successful results from premium models (last 30 days)
const thirtyDaysAgo = new Date(Date.now() - 30*24*60*60*1000);

const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .where('model', 'IN', ['opus', 'sonnet', 'gpt-4o'])
  .range('created_at', thirtyDaysAgo, new Date())
  .where('confidence', '>', 0.75);

const { sql, params } = filter.buildQuery(
  'model, COUNT(*) as executions, AVG(confidence) as avg_confidence, SUM(cost_usd) as total_cost',
  'total_cost DESC'
);
// Group results by model to compare performance and cost
const results = await client.query(sql, params);
```

### Example 6: Identify Expensive Failures

```javascript
// Find failed expensive tasks that may need investigation
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', 'IN', ['error', 'failed'])
  .where('cost_usd', '>', 0.50)
  .not('model', 'IN', ['test-model'])
  .metadata({ retried: false });  // Not retried yet

const { sql, params } = filter.buildQuery(
  'model, task_assigned, cost_usd, created_at',
  'cost_usd DESC, created_at DESC',
  50
);
const expensiveFailures = await client.query(sql, params);
```

### Example 7: Optimize for Speed and Cost

```javascript
// Find quick, cheap, successful tasks (good for parallelization)
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .range('duration_ms', 100, 2000)      // 100ms - 2 seconds
  .range('cost_usd', 0, 0.05)           // Less than $0.05
  .where('confidence', '>=', 0.85)
  .or([
    { field: 'model', op: '=', value: 'haiku' },
    { field: 'model', op: '=', value: 'sonnet' }
  ]);

const { sql, params } = filter.buildQuery(
  'id, model, duration_ms, cost_usd',
  'duration_ms ASC',
  100
);
const fastCheapTasks = await client.query(sql, params);
```

### Example 8: Vector Similarity with Metadata Context

```javascript
// Find similar successful tasks from the past
const queryEmbedding = [0.15, -0.22, 0.58, ...];  // 384-dim embedding

const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .where('confidence', '>', 0.8)
  .vectorSimilarity('result_embedding', queryEmbedding, 0.80)
  .metadata({ context_used: true })
  .range('created_at', new Date('2026-05-01'), new Date('2026-06-30'));

const { sql, params } = filter.buildQuery(
  'id, model, result, confidence, created_at',
  'distance ASC',
  10
);
const similarTasks = await client.query(sql, params);
```

### Example 9: Workflow Health Check

```javascript
// Monitor workflow execution health
const lastHour = new Date(Date.now() - 60*60*1000);

const filter = new AdvancedFilter('workflow.executions')
  .range('created_at', lastHour, new Date())
  .or([
    { field: 'outcome', op: '=', value: 'success' },
    { field: 'outcome', op: '=', value: 'error' }
  ]);

const { sql, params } = filter.buildQuery(
  'outcome, COUNT(*) as count, AVG(total_duration_ms) as avg_duration',
  'outcome'
);

const health = await client.query(sql, params);
// Returns success/error counts for health dashboard
```

### Example 10: Clean Up Old Test Data (with safeguards)

```javascript
// Find and delete test executions older than 90 days
const ninetyDaysAgo = new Date(Date.now() - 90*24*60*60*1000);

const filter = new AdvancedFilter('workflow.executions')
  .metadata({ is_test: true })
  .range('created_at', new Date('2000-01-01'), ninetyDaysAgo)
  .where('outcome', 'IN', ['success', 'error']);

const { sql, params } = filter.buildDelete();
// sql: "DELETE FROM workflow.executions WHERE metadata @> '{\"is_test\": true}'::jsonb AND created_at >= $1 AND created_at <= $2 AND outcome IN ($3, $4)"
// params: [new Date('2000-01-01'), ninetyDaysAgo, 'success', 'error']

// ALWAYS review before executing
console.log(`Will delete: ${sql}`);
const { rows: [{ count }] } = await client.query(
  `SELECT COUNT(*) as count FROM workflow.executions WHERE ${sql.replace('DELETE FROM workflow.executions WHERE', '')}`,
  params
);
console.log(`Deleting ${count} rows. Proceed? [y/N]: `);
// Get user confirmation before delete
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
