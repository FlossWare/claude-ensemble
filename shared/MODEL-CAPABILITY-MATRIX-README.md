# Model Capability Matrix

Dynamic model routing based on task-specific capability scores learned from execution history.

## Quick Start

```javascript
const { selectModelsByCapability, updateCapabilityScores } = require('./shared/model-capability-matrix.js');

// Get best 5 models for code review
const models = await selectModelsByCapability('code_review', { limit: 5 });
console.log(models);
// [
//   { model: 'opus', score: 0.95 },
//   { model: 'sonnet', score: 0.92 },
//   { model: 'fable', score: 0.93 },
//   { model: 'gpt-4o', score: 0.90 },
//   { model: 'gemini', score: 0.85 }
// ]

// Update scores from execution history (run periodically)
await updateCapabilityScores();
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Capability Score Priority (highest to lowest)              │
├─────────────────────────────────────────────────────────────┤
│  1. PostgreSQL monitoring.model_capabilities                │
│     - Updated from execution_summary quality scores         │
│     - Exponentially weighted moving average (EWMA)          │
│     - Requires minimum 10 executions                        │
│                                                             │
│  2. learning/model-capability-matrix.json                   │
│     - Baseline scores (35+ models, 13 task types)           │
│     - Manually curated initial values                       │
│                                                             │
│  3. shared/weighted-voting.cjs CAPABILITY_MATRIX            │
│     - Fallback for missing models/tasks                     │
│                                                             │
│  4. Default score (0.5)                                     │
│     - Unknown model/task combinations                       │
└─────────────────────────────────────────────────────────────┘
```

## Task Types

Supported task types (with aliases):

| Task Type | Aliases | Description |
|-----------|---------|-------------|
| `code_generation` | `code` | Generate new code from specifications |
| `code_review` | `review` | Review code for quality and correctness |
| `bug_detection` | `bug` | Identify bugs and potential issues |
| `security_audit` | `security` | Security vulnerability analysis |
| `architecture_review` | `architecture` | System design evaluation |
| `research` | `search` | Web research and synthesis |
| `fact_checking` | `verify` | Verify claims and check facts |
| `consensus` | `arbiter` | Arbiter/consensus decision making |
| `routing` | `route` | Fast task routing and classification |
| `math` | - | Mathematical reasoning |
| `reasoning` | - | General logical reasoning |
| `creative_writing` | - | Creative content generation |
| `general` | - | General-purpose tasks |

## API Reference

### `selectModelsByCapability(taskType, options)`

Select best models for a task type, sorted by capability score.

**Parameters:**
- `taskType` (string): Task type or alias
- `options` (object):
  - `limit` (number): Maximum models to return (default: all)
  - `minScore` (number): Minimum capability score 0.0-1.0 (default: 0.0)
  - `excludeModels` (array): Models to exclude (default: [])
  - `onlyModels` (array): Only consider these models (default: all)

**Returns:** `Promise<Array<{ model: string, score: number }>>`

**Example:**
```javascript
// Top 3 models for security audits, excluding haiku
const models = await selectModelsByCapability('security_audit', {
  limit: 3,
  minScore: 0.80,
  excludeModels: ['haiku']
});
```

### `selectDiverseModels(taskType, options)`

Select diverse models balancing capability with model family diversity.

**Parameters:**
- Same as `selectModelsByCapability`, plus:
  - `diversityWeight` (number): Weight for diversity vs capability 0-1 (default: 0.5)

**Returns:** `Promise<Array<{ model: string, score: number, family: string }>>`

**Example:**
```javascript
// Get 5 diverse models (avoid all from same family)
const models = await selectDiverseModels('code_review', {
  limit: 5,
  diversityWeight: 0.7  // Higher = more diversity penalty
});
```

### `getCapabilityScore(model, taskType, options)`

Get capability score for a specific model/task combination.

**Parameters:**
- `model` (string): Model name
- `taskType` (string): Task type or alias
- `options` (object):
  - `dbCapabilities` (object): Pre-loaded DB capabilities (optional)
  - `fileCapabilities` (object): Pre-loaded file capabilities (optional)

**Returns:** `Promise<number>` (0.0-1.0)

**Example:**
```javascript
const score = await getCapabilityScore('opus', 'code_generation');
console.log(score); // 0.95
```

### `getCapabilityScoreWithConfidence(model, taskType)`

Get capability score with confidence interval based on execution count.

**Returns:** `Promise<{ score, confidence, executions, source }>`

**Example:**
```javascript
const result = await getCapabilityScoreWithConfidence('sonnet', 'research');
console.log(result);
// {
//   score: 0.87,
//   confidence: 0.92,  // 92% confidence (based on 150 executions)
//   executions: 150,
//   source: 'database'
// }
```

### `updateCapabilityScores(options)`

Update capability scores from execution history (run periodically).

**Parameters:**
- `options` (object):
  - `minExecutions` (number): Minimum executions to update (default: 10)
  - `decayFactor` (number): EWMA decay factor 0-1 (default: 0.95)

**Returns:** `Promise<{ status, updated, updates }>`

**Example:**
```javascript
const result = await updateCapabilityScores({ minExecutions: 20 });
console.log(result);
// {
//   status: 'success',
//   updated: 47,
//   updates: [
//     {
//       model: 'opus',
//       task_type: 'code_review',
//       baseline_score: 0.95,
//       observed_score: 0.93,
//       new_score: 0.948,  // EWMA: 0.95 * 0.95 + 0.93 * 0.05
//       executions: 234,
//       stddev: 0.08
//     },
//     ...
//   ]
// }
```

## Integration with Weighted Voting

The capability matrix integrates seamlessly with `weighted-voting.cjs`:

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');
const { selectModelsByCapability } = require('./shared/model-capability-matrix.js');

// Select best models for task
const models = await selectModelsByCapability('security_audit', { limit: 8 });

// Use selected models in weighted voting
const votes = await Promise.all(
  models.map(async ({ model }) => {
    const result = await runTaskWithModel(model, task);
    return {
      model,
      answer: result.answer,
      confidence: result.confidence
    };
  })
);

// Weighted voting uses capability scores automatically
const votingResult = await runWeightedVoting(votes, 'security_audit');
```

## PostgreSQL Schema

The capability matrix stores learned scores in `monitoring.model_capabilities`:

```sql
CREATE TABLE monitoring.model_capabilities (
  id SERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  task_type TEXT NOT NULL,
  capability_score NUMERIC NOT NULL,
  executions INTEGER DEFAULT 0,
  last_updated TIMESTAMP DEFAULT NOW(),
  UNIQUE(model, task_type)
);

CREATE INDEX idx_model_capabilities_lookup
ON monitoring.model_capabilities(model, task_type);
```

### Query Examples

```sql
-- Top models for code generation
SELECT model, capability_score, executions
FROM monitoring.model_capabilities
WHERE task_type = 'code_generation'
ORDER BY capability_score DESC
LIMIT 5;

-- Models with high confidence (100+ executions)
SELECT model, task_type, capability_score, executions
FROM monitoring.model_capabilities
WHERE executions >= 100
ORDER BY capability_score DESC;

-- Model performance across all tasks
SELECT
  model,
  COUNT(*) as num_tasks,
  AVG(capability_score) as avg_score,
  SUM(executions) as total_executions
FROM monitoring.model_capabilities
GROUP BY model
ORDER BY avg_score DESC;
```

## EWMA Score Update Algorithm

Exponentially Weighted Moving Average balances baseline scores with observed performance:

```
new_score = baseline_score × decay + observed_score × (1 - decay)

Where:
- baseline_score: Score from learning/model-capability-matrix.json
- observed_score: AVG(quality_score) from monitoring.execution_summary
- decay: 0.95 (default) - higher = more weight to baseline
- new_score: Updated score stored in monitoring.model_capabilities
```

**Example:**
```
Baseline score: 0.90
Observed score: 0.85 (from 50 executions)
Decay: 0.95

new_score = 0.90 × 0.95 + 0.85 × 0.05
          = 0.855 + 0.0425
          = 0.8975
```

This allows scores to adapt slowly to actual performance while preventing wild swings from outliers.

## Confidence Scoring

Confidence increases with execution count using a sigmoid function:

```
confidence = 1 / (1 + exp(-0.05 × (executions - 50)))

Examples:
- 10 executions  → 0.50 confidence (low)
- 50 executions  → 0.73 confidence (moderate)
- 100 executions → 0.92 confidence (high)
- 200+ executions → 0.95+ confidence (very high)
```

Use confidence to decide when to trust learned scores vs baseline scores.

## Automation

### Periodic Updates

Schedule capability score updates with cron:

```bash
# Update capability scores daily at 2 AM
0 2 * * * cd /path/to/project && node -e "require('./shared/model-capability-matrix.js').updateCapabilityScores().then(r => console.log(r))"
```

### Workflow Integration

Update scores after each workflow execution:

```javascript
const { storeWorkerResult } = require('./shared/workflow-storage-adapter.js');
const { updateCapabilityScores } = require('./shared/model-capability-matrix.js');

// Store execution result
await storeWorkerResult({
  workflow_execution_id: execId,
  model: 'opus',
  task_assigned: 'Code review',
  quality_score: 0.93,
  ...
});

// Update capability scores (debounced - only updates if >1 hour since last)
await updateCapabilityScores();
```

## Migration from weighted-voting.cjs

If you're using `weighted-voting.cjs` directly, migration is optional but recommended for dynamic learning:

**Before (static scores):**
```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');
const result = await runWeightedVoting(votes, 'code_review');
```

**After (learned scores):**
```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');
const { selectModelsByCapability } = require('./shared/model-capability-matrix.js');

// Pre-select best models for task
const models = await selectModelsByCapability('code_review', { limit: 8 });

// Run only selected models (more efficient)
const votes = await runModels(models.map(m => m.model), task);
const result = await runWeightedVoting(votes, 'code_review');
```

## Troubleshooting

### Scores not updating

```javascript
// Check executions in database
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.js');
const db = getWorkflowStorage();

const result = await db.pool.query(`
  SELECT model, task_type, COUNT(*)
  FROM monitoring.execution_summary
  WHERE quality_score IS NOT NULL
  GROUP BY model, task_type
  ORDER BY count DESC
`);

console.log(result.rows);
// If count < 10, not enough executions yet
```

### Unknown task type

```javascript
const { normalizeTaskType, TASK_TYPE_ALIASES } = require('./shared/model-capability-matrix.js');

console.log(TASK_TYPE_ALIASES);
// { code: 'code_generation', review: 'code_review', ... }

const normalized = normalizeTaskType('review');
console.log(normalized); // 'code_review'
```

### Low confidence scores

Increase minimum executions threshold or wait for more data:

```javascript
// Lower threshold temporarily
await updateCapabilityScores({ minExecutions: 5 });

// Check confidence
const result = await getCapabilityScoreWithConfidence('opus', 'research');
if (result.confidence < 0.70) {
  console.warn(`Low confidence (${result.confidence}), need more executions`);
}
```

## Performance

- **DB lookup**: ~0.5ms (indexed query)
- **File load**: ~5ms (cached after first load)
- **selectModelsByCapability**: ~10ms (for 35 models)
- **updateCapabilityScores**: ~500ms (for 100+ model/task pairs)

Memory usage: ~2MB (loaded matrix + DB connection pool)

## See Also

- `shared/weighted-voting.cjs` - Weighted voting algorithm
- `shared/workflow-storage-adapter.js` - PostgreSQL integration
- `learning/model-capability-matrix.json` - Baseline capability scores
- `DISAGREEMENT-DETECTION-README.md` - Human review queue integration
