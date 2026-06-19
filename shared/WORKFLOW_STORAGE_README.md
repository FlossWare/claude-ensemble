# Workflow Storage Adapter

Persistent storage for multi-AI workflow orchestration results.

## Architecture

- **PostgreSQL**: Relational data (workflow metadata, execution logs, relationships)
- **pgvector**: 384-dim embeddings (all-MiniLM-L6-v2) for similarity search
- **Transaction Support**: Atomic operations prevent race conditions

## Database Schema

### Tables

1. **workflow.executions** - Top-level workflow execution metadata
2. **workflow.worker_results** - Individual worker execution results
3. **workflow.arbiter_decisions** - Arbiter consensus decisions
4. **workflow.phases** - Workflow phase tracking
5. **workflow.feedback** - Human/automated feedback on workflows
6. **workflow.learnings** - Extracted learnings from workflow execution

### Views

1. **workflow.execution_stats** - Workflow execution statistics
2. **workflow.model_performance** - Model performance metrics
3. **workflow.arbiter_effectiveness** - Arbiter effectiveness metrics

## Setup

### 1. Install Dependencies

```bash
# Python dependencies (for embedding generation)
pip3 install sentence-transformers

# Node.js dependencies (already in project)
npm install pg
```

### 2. Create Database Schema

```bash
psql -h /var/run/postgresql -U $USER -d learning -f shared/workflow-storage-schema.sql
```

### 3. Verify Setup

```bash
# Test the adapter
node shared/test-workflow-storage.js
```

## Usage

### Import Module

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter');

const storage = getWorkflowStorage();
```

### Store Workflow Execution

```javascript
const executionId = await storage.storeExecution({
  workflow_id: 'research-2026-06-19-001',
  workflow_name: 'deep-research',
  task_description: 'Research quantum computing advances',
  total_workers: 3,
  total_duration_ms: 45000,
  outcome: 'success',
  metadata: { phase_count: 3 }
});
```

### Store Worker Result

```javascript
const workerId = await storage.storeWorkerResult({
  workflow_execution_id: executionId,
  worker_id: 'worker-1',
  model: 'opus',
  task_assigned: 'Search for research papers',
  result: 'Found 15 papers on quantum error correction',
  confidence: 0.85,
  duration_ms: 12000,
  input_tokens: 500,
  output_tokens: 1200,
  cost_usd: 0.025,
  outcome: 'success',
  metadata: { sources: 15 }
});
```

### Store Arbiter Decision

```javascript
const arbiterId = await storage.storeArbiterDecision({
  workflow_execution_id: executionId,
  arbiter_model: 'opus',
  worker_result_ids: [worker1Id, worker2Id],
  decision: 'Quantum computing made significant progress',
  reasoning: 'Both workers found consistent evidence',
  confidence: 0.88,
  duration_ms: 8000,
  input_tokens: 2700,
  output_tokens: 800,
  cost_usd: 0.020,
  metadata: { consensus_level: 'high' }
});
```

### Store Workflow Phase

```javascript
await storage.storePhase({
  workflow_execution_id: executionId,
  phase_name: 'search',
  phase_order: 1,
  duration_ms: 22000,
  outcome: 'success',
  metadata: { workers_spawned: 2 }
});
```

### Store Feedback

```javascript
await storage.storeFeedback({
  workflow_execution_id: executionId,
  feedback_type: 'automated',
  quality_score: 0.87,
  feedback_text: 'High-quality synthesis',
  metadata: { evaluator: 'quality-checker' }
});
```

### Store Learnings

```javascript
await storage.storeLearnings({
  workflow_execution_id: executionId,
  learning_type: 'pattern',
  description: 'Opus and Sonnet show high consensus on technical topics',
  actionable_insight: 'Use Opus+Sonnet for technical research',
  importance: 0.75,
  metadata: { domain: 'quantum-computing' }
});
```

### Query Similar Workflows

```javascript
const similar = await storage.findSimilarWorkflows(
  'Research advances in quantum computing',
  5 // limit
);

console.log(similar[0].workflow_name);
console.log(similar[0].distance); // Cosine distance
```

### Get Complete Workflow Data

```javascript
const complete = await storage.getWorkflowComplete('research-2026-06-19-001');

console.log(complete.execution);  // Main execution record
console.log(complete.workers);    // Worker results
console.log(complete.arbiters);   // Arbiter decisions
console.log(complete.phases);     // Workflow phases
console.log(complete.feedback);   // Feedback records
console.log(complete.learnings);  // Extracted learnings
```

## Transaction Support

All store methods use transactions for atomicity:

```javascript
// Manual transaction example
await storage.transaction(async (client) => {
  const result1 = await client.query('INSERT INTO ...');
  const result2 = await client.query('INSERT INTO ...');
  return result1.rows[0].id;
});
```

## Embedding Generation

Embeddings are generated automatically using `sentence-transformers/all-MiniLM-L6-v2` (384-dim):

- **Task descriptions**: For workflow similarity search
- **Worker results**: For result similarity search
- **Arbiter decisions**: For decision similarity search
- **Learnings**: For learning similarity search

## Performance

- **pgvector HNSW index**: O(log n) similarity search
- **Connection pooling**: Reuses connections (max 10)
- **Batch operations**: Use transactions for multi-insert

## Integration with Existing Systems

### Use with postgres-adapter.js

```javascript
const { getDB } = require('~/.claude/learning/postgres-adapter');
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter');

// Both use the same connection pool
const db = getDB();
const storage = getWorkflowStorage();
```

### Use with Workflow Orchestrators

```javascript
// In deep-research.mjs or similar workflow
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter');

async function runWorkflow(task) {
  const storage = getWorkflowStorage();
  const workflowId = `research-${Date.now()}`;
  
  // Store execution
  const executionId = await storage.storeExecution({
    workflow_id: workflowId,
    workflow_name: 'deep-research',
    task_description: task,
    total_workers: workers.length,
    total_duration_ms: duration,
    outcome: 'success'
  });

  // Store worker results
  for (const worker of workerResults) {
    await storage.storeWorkerResult({
      workflow_execution_id: executionId,
      ...worker
    });
  }

  // Store arbiter decision
  await storage.storeArbiterDecision({
    workflow_execution_id: executionId,
    ...arbiterResult
  });

  return workflowId;
}
```

## Monitoring

### Query Execution Statistics

```sql
SELECT * FROM workflow.execution_stats;
```

### Query Model Performance

```sql
SELECT * FROM workflow.model_performance
WHERE outcome = 'success'
ORDER BY avg_confidence DESC;
```

### Query Arbiter Effectiveness

```sql
SELECT * FROM workflow.arbiter_effectiveness
ORDER BY avg_confidence DESC;
```

### Find High-Quality Learnings

```sql
SELECT * FROM workflow.learnings
WHERE importance > 0.7
ORDER BY importance DESC;
```

## Files

- `workflow-storage-adapter.js` - Main module
- `generate-embedding.py` - Embedding generation script
- `workflow-storage-schema.sql` - Database schema
- `test-workflow-storage.js` - Test suite
- `WORKFLOW_STORAGE_README.md` - This file

## Next Steps

1. Integrate into existing workflows (deep-research.mjs, etc.)
2. Add workflow completion hooks
3. Build dashboards for workflow analysis
4. Add automated learning extraction
5. Implement feedback collection UI

## Truth in Labeling

**What this module DOES:**
- ✅ Persistent storage of workflow execution data
- ✅ Vector similarity search for past workflows
- ✅ Transaction support for atomicity
- ✅ Cost tracking and performance monitoring

**What this module DOES NOT:**
- ✗ Improve AI model intelligence (just stores results)
- ✗ Auto-optimize workflows (requires analysis layer)
- ✗ Replace human judgment (stores feedback, doesn't generate it)
- ✗ Guarantee correctness (garbage in, garbage out)

This is a **storage layer**, not an intelligence layer. Analysis and optimization require separate components.
