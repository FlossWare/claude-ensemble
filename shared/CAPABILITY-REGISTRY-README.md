# Capability Registry

Database and tracking for model capabilities with quality metrics, cost, and performance history.

## Overview

The capability registry maintains a centralized database of what each model does well. It stores:

- **Quality scores** (0-1) - Average performance on a task
- **Cost metrics** - USD per execution
- **Latency data** - Milliseconds per execution
- **Execution history** - Success/failure rates
- **Confidence** - How many executions we've tracked (min 10 for high confidence)

This enables intelligent model selection based on proven performance on specific tasks.

## Database Schema

### Tables

**`learning.model_capabilities`** - Capability registry
- `id` - Primary key
- `model` - Model name (opus, sonnet, haiku, deepseek-coder, etc.)
- `capability` - Task type (code_generation, code_review, research, etc.)
- `quality_score` - Average quality (0-1)
- `avg_cost` - Average cost in USD
- `avg_latency_ms` - Average latency in milliseconds
- `executions` - Total execution count
- `success_count` - Successful executions
- `failure_count` - Failed executions
- `confidence` - Metric confidence (0-1, based on execution count)

**`learning.capability_executions`** - Execution history
- Records individual executions
- Enables historical analysis and trend tracking
- Auto-deletes old records (configurable retention)

### Views

**`top_models_per_capability`** - Top performers by task type
```sql
SELECT * FROM learning.top_models_per_capability 
WHERE capability = 'code_generation'
LIMIT 5;
```

**`model_capability_summary`** - Summary of all models
```sql
SELECT * FROM learning.model_capability_summary 
ORDER BY avg_quality DESC;
```

**`capability_coverage`** - Coverage across models
```sql
SELECT * FROM learning.capability_coverage 
ORDER BY total_executions DESC;
```

## JavaScript Usage

```javascript
const {
  registerCapability,
  getCapableModels,
  updateCapabilityMetrics,
  getModelCapabilities,
  getModelSummary,
  getCapabilityCoverage,
  findBestModel,
  getExecutionHistory,
  getCapability,
  autoPopulateFromHistory,
  cleanupExecutionHistory,
  exportRegistry
} = require('./shared/capability-registry.cjs');

// Register a new execution
const cap = await registerCapability('opus', 'code_generation', {
  quality_score: 0.92,
  cost_usd: 0.05,
  latency_ms: 2500,
  success: true
});

// Get capable models for a task
const models = await getCapableModels('code_generation', {
  min_quality: 0.85,
  max_cost: 0.10,
  max_latency_ms: 3000
});

// Find the best model
const best = await findBestModel('code_generation', { min_quality: 0.85 });
console.log(`Best model: ${best.model} (quality: ${best.quality_score})`);

// Get all capabilities for a model
const caps = await getModelCapabilities('opus');

// Get summary of all models
const summary = await getModelSummary();

// Update metrics after execution
await updateCapabilityMetrics(cap.id, {
  quality_score: 0.95,
  cost_usd: 0.052,
  latency_ms: 2450,
  success: true
});

// Get execution history
const history = await getExecutionHistory(cap.id, 20);

// Auto-populate from workflow history
const stats = await autoPopulateFromHistory({
  from_date: '2026-06-20',
  min_executions: 5
});

// Clean up old execution records
const cleanup = await cleanupExecutionHistory({ days_to_keep: 90 });

// Export entire registry
const json = await exportRegistry();
```

## Python Usage

```python
import psycopg2

conn = psycopg2.connect(
    host='aio-01',
    port=5433,
    database='learning',
    user='sfloess'
)

cursor = conn.cursor()

# Find best models for code generation
cursor.execute("""
    SELECT model, quality_score, avg_cost, avg_latency_ms
    FROM learning.top_models_per_capability
    WHERE capability = 'code_generation'
    ORDER BY quality_score DESC
    LIMIT 5
""")

models = cursor.fetchall()
for model, quality, cost, latency in models:
    print(f"{model}: quality={quality}, cost=${cost}, latency={latency}ms")

# Register a capability
cursor.execute("""
    SELECT learning.register_capability(%s, %s, %s, %s, %s)
""", ('model-name', 'capability-type', 0.87, 0.05, 2000))

conn.commit()

cursor.close()
conn.close()
```

## Integration Patterns

### In Workflow Execution

```javascript
import { getWorkflowStorage } = require('./shared/workflow-storage-adapter.js');
import { registerCapability, findBestModel } = require('./shared/capability-registry.cjs');

export default async function({ phase, parallel, agent, log }) {
  // Find best model for task
  const best = await findBestModel('code_review', { min_quality: 0.85 });
  
  const result = await agent(best.model, { task });
  
  // Register result
  await registerCapability(best.model, 'code_review', {
    quality_score: result.quality,
    cost_usd: result.cost,
    latency_ms: result.duration,
    success: result.success
  });
}
```

### Intelligent Router

```javascript
// Select model based on capabilities
async function selectModel(taskType, minQuality = 0.80) {
  const models = await getCapableModels(taskType, {
    min_quality: minQuality,
    min_confidence: 0.5  // At least 5 executions
  });
  
  if (models.length === 0) {
    // Fallback to default
    return 'opus';
  }
  
  // Return highest confidence model
  return models[0].model;
}
```

### Auto-Population from History

```javascript
// Run daily to update capabilities from workflow history
async function updateCapabilityRegistry() {
  const stats = await autoPopulateFromHistory({
    from_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0],
    min_executions: 3
  });
  
  console.log(`Updated: ${stats.created} created, ${stats.updated} updated`);
}
```

## Confidence Levels

The `confidence` field indicates how much data we have for a capability:

- 0.0-0.3: Initial data (1-3 executions) - use with caution
- 0.3-0.7: Developing confidence (3-7 executions) - generally reliable
- 0.7-1.0: High confidence (7+ executions) - very reliable
- 1.0: Max confidence (10+ executions) - statistical significance

Filter by confidence when making critical decisions:

```javascript
const reliableModels = await getCapableModels('code_generation', {
  min_quality: 0.85,
  min_confidence: 0.7  // At least 7 executions
});
```

## Maintenance

### Clean Up Old Execution Records

```javascript
// Keep 90 days of history (default)
await cleanupExecutionHistory({ days_to_keep: 90 });

// Or keep only 30 days
await cleanupExecutionHistory({ days_to_keep: 30 });
```

### View Registry Statistics

```sql
-- Model summary
SELECT * FROM learning.model_capability_summary ORDER BY avg_quality DESC;

-- Coverage by capability
SELECT * FROM learning.capability_coverage ORDER BY total_executions DESC;

-- Top 10 best models
SELECT * FROM learning.top_models_per_capability 
WHERE confidence >= 0.7
ORDER BY quality_score DESC
LIMIT 10;
```

## Testing

Run the test suite:

```bash
npm test -- shared/capability-registry.test.cjs
```

Or with mocha:

```bash
npx mocha shared/capability-registry.test.cjs
```

## Files

- `db/migrations/021_capability_registry.sql` - Database schema
- `shared/capability-registry.cjs` - JavaScript adapter
- `shared/capability-registry.test.cjs` - Test suite
- `shared/CAPABILITY-REGISTRY-README.md` - This file

## Future Enhancements

- [ ] Export/import functionality for registry backup
- [ ] Capability versioning (track changes over time)
- [ ] Model performance trends (regression detection)
- [ ] A/B testing framework (compare models statistically)
- [ ] Capability recommendations (suggest model for new task type)
- [ ] Cost optimization (find cheapest model meeting quality threshold)
