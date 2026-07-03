# Advanced Filter - Quick Reference

## Import

```javascript
import { AdvancedFilter, createFilter, presets } from './advanced-filter.js';
```

## Create Filter

```javascript
const filter = new AdvancedFilter('table_name');
```

## WHERE Conditions

```javascript
.where('column', '=', value)        // Comparison: =, !=, >, >=, <, <=, <>
.where('column', 'IN', [val1, val2])
.where('column', 'NOT IN', [val1])
.where('column', 'LIKE', '%pattern%')
.where('column', 'ILIKE', '%pattern%')
.where('column', 'CONTAINS', 'text')
.where('column', 'STARTS_WITH', 'prefix')
.where('column', 'IS NULL')
.where('column', 'IS NOT NULL')
```

## Range Queries

```javascript
.range('column', minValue, maxValue)
.range('created_at', startDate, endDate)
```

## JSON Metadata

```javascript
.metadata({ key: value })                    // metadata @> {...}
.metadata({ 'nested.key': value })          // metadata @> {...}
.where('metadata.key', '=', value)          // metadata->'key' = value
```

## Text Search

```javascript
.fullTextSearch('search text')
.fullTextSearch('search text', 'field')
```

## Vector Similarity (pgvector)

```javascript
.vectorSimilarity('embedding_column', vectorArray, threshold)
// threshold: 0-1 (0 = identical, 1 = very different)
```

## Complex Logic

```javascript
.and([
  { field: 'col1', op: '=', value: val1 },
  { field: 'col2', op: '>', value: val2 }
])

.or([
  { field: 'col1', op: '=', value: val1 },
  { field: 'col2', op: '=', value: val2 }
])

.not('column', '=', value)
```

## Build Queries

```javascript
// WHERE clause only
const { sql, params } = filter.build();

// SELECT query
const { sql, params } = filter.buildQuery('SELECT_CLAUSE', 'ORDER BY', LIMIT, OFFSET);

// DELETE (requires WHERE)
const { sql, params } = filter.buildDelete();

// UPDATE (requires WHERE)
const { sql, params } = filter.buildUpdate({ column: value });
```

## State Management

```javascript
filter.reset()                // Clear all conditions
filter.clone()                // Independent copy
filter.debug()                // Inspect state
```

## Presets

```javascript
presets.successfulOnly('table')
presets.highConfidence('table', threshold)
presets.recent('table', hours)
presets.byModel('table', modelArray)
presets.byQuickest('table', maxMs)
```

## Examples

### Simple Filter
```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .where('confidence', '>', 0.8);

const { sql, params } = filter.build();
client.query(`SELECT * FROM workflow.worker_results WHERE ${sql}`, params);
```

### Complex Filter
```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success')
  .range('created_at', startDate, endDate)
  .metadata({ retried: false })
  .or([
    { field: 'model', op: '=', value: 'opus' },
    { field: 'model', op: '=', value: 'sonnet' }
  ]);

const { sql, params } = filter.buildQuery('*', 'created_at DESC', 100);
```

### Vector Search
```javascript
const filter = new AdvancedFilter('workflow.executions')
  .vectorSimilarity('task_embedding', queryVector, 0.85)
  .where('outcome', '=', 'success');

const { sql, params } = filter.buildQuery('*', 'distance ASC', 10);
```

### Aggregation
```javascript
const filter = new AdvancedFilter('workflow.worker_results')
  .where('outcome', '=', 'success');

const { sql, params } = filter.buildQuery(
  'model, COUNT(*) as count, AVG(confidence)',
  'count DESC'
);
```

## Safety Features

- ✅ All values parameterized ($1, $2, ...)
- ✅ DELETE/UPDATE require WHERE clause (throws otherwise)
- ✅ SQL injection prevention via parameterization
- ✅ Type validation for operators (IN requires array, etc.)

## Performance Tips

1. **JSON queries:** Use GIN index on metadata
   ```sql
   CREATE INDEX idx_metadata ON table USING GIN (metadata);
   ```

2. **Vector search:** Use HNSW index on embeddings
   ```sql
   CREATE INDEX idx_emb ON table USING ivfflat (embedding vector_cosine_ops);
   ```

3. **Range queries:** Use BTREE index on timestamps
   ```sql
   CREATE INDEX idx_created_at ON table (created_at);
   ```

## See Also

- `ADVANCED_FILTER_GUIDE.md` - Complete reference
- `advanced-filter.test.js` - 40 comprehensive tests
