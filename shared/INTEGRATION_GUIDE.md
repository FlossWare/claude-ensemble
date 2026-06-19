# Workflow Storage Integration Guide

How to integrate the workflow storage adapter into existing multi-AI workflows.

## Quick Start

### 1. Add Hook at End of Workflow

```javascript
const { onWorkflowComplete } = require('./shared/workflow-completion-hook');

async function runDeepResearch(task) {
  const workflowId = `research-${Date.now()}`;
  const startTime = Date.now();
  
  try {
    // ... existing workflow code ...
    
    // Store workflow execution
    await onWorkflowComplete({
      workflow_id: workflowId,
      workflow_name: 'deep-research',
      task: task,
      workers: workerResults,
      arbiter: arbiterDecision,
      phases: phases,
      duration_ms: Date.now() - startTime,
      outcome: 'success',
      metadata: {
        phase_count: phases.length,
        total_cost: totalCost
      }
    });
    
    return result;
    
  } catch (err) {
    // Store failure
    await onWorkflowComplete({
      workflow_id: workflowId,
      workflow_name: 'deep-research',
      task: task,
      workers: workerResults,
      arbiter: null,
      phases: phases,
      duration_ms: Date.now() - startTime,
      outcome: 'error',
      metadata: {
        error: err.message
      }
    });
    throw err;
  }
}
```

## Detailed Integration Patterns

### Pattern 1: Simple Worker-Arbiter Workflow

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter');

async function simpleWorkflow(task) {
  const storage = getWorkflowStorage();
  const workflowId = `simple-${Date.now()}`;
  
  // Store execution
  const executionId = await storage.storeExecution({
    workflow_id: workflowId,
    workflow_name: 'simple-consensus',
    task_description: task,
    total_workers: 3,
    total_duration_ms: 0, // Update later
    outcome: 'success'
  });
  
  // Run workers
  const workers = ['opus', 'sonnet', 'haiku'];
  const workerResults = [];
  
  for (const model of workers) {
    const result = await runWorker(model, task);
    
    // Store worker result
    const workerId = await storage.storeWorkerResult({
      workflow_execution_id: executionId,
      worker_id: `worker-${model}`,
      model: model,
      task_assigned: task,
      result: result.output,
      confidence: result.confidence,
      duration_ms: result.duration_ms,
      input_tokens: result.input_tokens,
      output_tokens: result.output_tokens,
      cost_usd: result.cost_usd,
      outcome: 'success'
    });
    
    workerResults.push({ id: workerId, ...result });
  }
  
  // Run arbiter
  const arbiterResult = await runArbiter('opus', workerResults);
  
  // Store arbiter decision
  await storage.storeArbiterDecision({
    workflow_execution_id: executionId,
    arbiter_model: 'opus',
    worker_result_ids: workerResults.map(w => w.id),
    decision: arbiterResult.decision,
    reasoning: arbiterResult.reasoning,
    confidence: arbiterResult.confidence,
    duration_ms: arbiterResult.duration_ms,
    input_tokens: arbiterResult.input_tokens,
    output_tokens: arbiterResult.output_tokens,
    cost_usd: arbiterResult.cost_usd
  });
  
  return arbiterResult.decision;
}
```

### Pattern 2: Multi-Phase Workflow

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter');

async function multiPhaseWorkflow(task) {
  const storage = getWorkflowStorage();
  const workflowId = `multi-phase-${Date.now()}`;
  
  const executionId = await storage.storeExecution({
    workflow_id: workflowId,
    workflow_name: 'deep-research',
    task_description: task,
    total_workers: 6,
    total_duration_ms: 0,
    outcome: 'success'
  });
  
  // Phase 1: Search
  const searchStart = Date.now();
  const searchResults = await searchPhase(task, executionId, storage);
  await storage.storePhase({
    workflow_execution_id: executionId,
    phase_name: 'search',
    phase_order: 1,
    duration_ms: Date.now() - searchStart,
    outcome: 'success',
    metadata: { results: searchResults.length }
  });
  
  // Phase 2: Verify
  const verifyStart = Date.now();
  const verifiedResults = await verifyPhase(searchResults, executionId, storage);
  await storage.storePhase({
    workflow_execution_id: executionId,
    phase_name: 'verify',
    phase_order: 2,
    duration_ms: Date.now() - verifyStart,
    outcome: 'success',
    metadata: { verified: verifiedResults.length }
  });
  
  // Phase 3: Synthesize
  const synthesizeStart = Date.now();
  const final = await synthesizePhase(verifiedResults, executionId, storage);
  await storage.storePhase({
    workflow_execution_id: executionId,
    phase_name: 'synthesize',
    phase_order: 3,
    duration_ms: Date.now() - synthesizeStart,
    outcome: 'success'
  });
  
  return final;
}
```

### Pattern 3: Learning from Past Workflows

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter');

async function learningWorkflow(task) {
  const storage = getWorkflowStorage();
  
  // Find similar past workflows
  const similar = await storage.findSimilarWorkflows(task, 5);
  
  console.log(`Found ${similar.length} similar workflows`);
  
  if (similar.length > 0 && similar[0].distance < 0.1) {
    // Very similar task - use same strategy
    const past = await storage.getWorkflowComplete(similar[0].workflow_id);
    console.log(`Reusing strategy from ${similar[0].workflow_id}`);
    
    // Extract model choices from past success
    const models = past.workers.map(w => w.model);
    const arbiterModel = past.arbiters[0]?.arbiter_model;
    
    // Run with same configuration
    return await runWithConfig(task, models, arbiterModel);
  } else {
    // New task - use default strategy
    return await runDefault(task);
  }
}
```

### Pattern 4: Feedback Collection

```javascript
const { storeFeedback } = require('./shared/workflow-completion-hook');

async function collectFeedback(workflowId, userRating, comments) {
  await storeFeedback(workflowId, {
    type: 'user',
    score: userRating / 5.0, // Convert 1-5 to 0-1
    text: comments,
    metadata: {
      user_id: getCurrentUser(),
      timestamp: Date.now()
    }
  });
}
```

### Pattern 5: Automated Quality Assessment

```javascript
const { storeFeedback } = require('./shared/workflow-completion-hook');

async function assessQuality(workflowId, result) {
  // Run quality checks
  const qualityScore = await runQualityChecks(result);
  
  await storeFeedback(workflowId, {
    type: 'automated',
    score: qualityScore,
    text: `Automated quality assessment: ${qualityScore.toFixed(2)}`,
    metadata: {
      checks: ['factuality', 'coherence', 'completeness'],
      evaluator: 'quality-checker-v1'
    }
  });
}
```

## Migration Checklist

### Existing Workflows to Update

1. ✅ **deep-research.mjs** - Add onWorkflowComplete hook
2. ✅ **ai-consensus.mjs** - Add storage for consensus decisions
3. ✅ **ai-consensus-debate.mjs** - Store debate rounds
4. ✅ **ai-consensus-hierarchical.mjs** - Store hierarchical structure
5. ✅ **code-solve-auto.mjs** - Store code fix attempts

### Steps

1. **Import the hook**
   ```javascript
   const { onWorkflowComplete } = require('./shared/workflow-completion-hook');
   ```

2. **Collect execution data**
   - Track start time
   - Collect worker results
   - Collect arbiter decisions
   - Track phases
   - Measure duration

3. **Call onWorkflowComplete**
   - At end of successful execution
   - In error handlers for failures

4. **Test integration**
   ```bash
   # Run workflow
   node workflows/your-workflow.mjs
   
   # Verify storage
   psql -d learning -c "SELECT * FROM workflow.executions ORDER BY created_at DESC LIMIT 1;"
   ```

## Database Setup

```bash
# 1. Create schema
psql -h /var/run/postgresql -U $USER -d learning -f shared/workflow-storage-schema.sql

# 2. Verify tables
psql -d learning -c "\dt workflow.*"

# 3. Run test
node shared/test-workflow-storage.js
```

## Monitoring Queries

### Recent Workflow Executions

```sql
SELECT workflow_id, workflow_name, outcome, total_duration_ms, created_at
FROM workflow.executions
ORDER BY created_at DESC
LIMIT 10;
```

### Workflow Success Rate

```sql
SELECT 
  workflow_name,
  COUNT(*) as total,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
  (SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) * 100) as success_rate
FROM workflow.executions
GROUP BY workflow_name;
```

### Model Performance

```sql
SELECT * FROM workflow.model_performance
WHERE outcome = 'success'
ORDER BY avg_confidence DESC;
```

### Cost Analysis

```sql
SELECT 
  workflow_name,
  SUM(total_workers) as total_workers_spawned,
  SUM(total_duration_ms) / 1000.0 as total_seconds,
  COUNT(*) as executions
FROM workflow.executions
GROUP BY workflow_name;
```

### Find Similar Tasks

```javascript
const storage = getWorkflowStorage();
const similar = await storage.findSimilarWorkflows(
  'Your new task description',
  10
);
console.table(similar);
```

## Troubleshooting

### Embedding Generation Fails

```bash
# Install sentence-transformers
pip3 install sentence-transformers

# Test embedding generation
echo "test text" | python3 shared/generate-embedding.py
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
systemctl status postgresql

# Check database exists
psql -d learning -c "SELECT version();"

# Check schema exists
psql -d learning -c "\dn"
```

### Transaction Errors

If you see transaction errors, ensure you're not nesting transactions:

```javascript
// BAD: Nested transactions
await storage.transaction(async (client) => {
  await storage.storeExecution(...); // This starts another transaction!
});

// GOOD: Single transaction
await storage.transaction(async (client) => {
  await client.query('INSERT INTO workflow.executions ...');
  await client.query('INSERT INTO workflow.worker_results ...');
});
```

## Performance Tips

1. **Batch inserts**: Use transactions for multi-insert operations
2. **Limit embedding calls**: Cache embeddings when possible
3. **Use indexes**: The schema includes HNSW indexes for fast similarity search
4. **Monitor pool**: Check connection pool usage with `pool.totalCount`

## Next Steps

1. Integrate into 5 core workflows
2. Build analysis dashboard
3. Add automated learning extraction
4. Create feedback collection UI
5. Monitor for 7 days to validate storage patterns
