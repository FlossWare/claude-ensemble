# Fleet Workflow Wrapper

**Fleet-aware workflow execution with automatic PostgreSQL tracking**

## Overview

Transparently distributes workflow `agent()` and `parallel()` calls across the 8-worker API-only fleet with automatic storage tracking and host distribution monitoring.

### Architecture

- **Workers**: 8 nodes (server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap)
- **SSH User**: `claude` (all nodes)
- **Distribution**: Round-robin with health checks
- **Storage**: PostgreSQL `workflow.*` tables
- **Fallback**: Local execution if all workers fail

### Files

- `shared/fleet-workflow-wrapper.mjs` - Main implementation (950 lines)
- `shared/fleet-workflow-wrapper.test.mjs` - Test suite
- `shared/fleet-utils.js` - SSH execution utilities
- `shared/fleet-topology.js` - Fleet configuration
- `shared/workflow-storage-adapter.js` - PostgreSQL storage

---

## Quick Start

### Basic Usage (Opt-In Pattern)

```javascript
// workflows/my-workflow.mjs
import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, parallel, phase, complete } = createFleetWorkflow(
    'my-workflow',
    args.query,
    {
      enableFleet: true,      // Enable fleet distribution
      enableStorage: true,    // Enable PostgreSQL storage
      fleetStrategy: 'round-robin'
    }
  );

  // Same API as before, but now fleet-aware
  const result = await agent('Analyze this code', {
    model: 'claude-opus-4',
    type: 'code-analysis'
  });

  return complete(result, 0.85);
}
```

### Parallel Execution

```javascript
const tasks = [
  { prompt: 'Task 1', model: 'claude-sonnet-4', type: 'search' },
  { prompt: 'Task 2', model: 'claude-opus-4', type: 'analysis' },
  { prompt: 'Task 3', model: 'claude-haiku-4', type: 'summary' }
];

// Distributes across 8 workers automatically
const results = await parallel(tasks, { maxConcurrency: 8 });
```

### Phase Tracking

```javascript
await phase('Search', async () => {
  // Phase logic here
  const searchResults = await parallel(searchTasks);
  return searchResults;
});

await phase('Analysis', async () => {
  // Next phase
  const analysis = await agent('Analyze results');
  return analysis;
});
```

---

## Configuration Options

```javascript
createFleetWorkflow(workflowName, taskDescription, {
  enableFleet: true,          // Enable fleet distribution (default: true)
  enableStorage: true,         // Enable PostgreSQL storage (default: true)
  fleetStrategy: 'round-robin', // Distribution strategy (default: 'round-robin')
  sshUser: 'claude',           // SSH username (default: 'claude')
  timeout: 300000,             // Agent timeout in ms (default: 5 min)
  maxRetries: 2,               // Max retry attempts (default: 2)
  fallbackToLocal: true        // Fallback to local on failure (default: true)
});
```

### Fleet Strategies

1. **round-robin** (default)
   - Simple sequential distribution
   - Skips workers with recent failures
   - Best for balanced workloads

2. **cost-optimized**
   - Prefers Pi nodes for lightweight tasks (<1000 tokens)
   - Falls back to x86_64 servers for heavy tasks
   - Best for mixed workloads

3. **load-aware** (TODO)
   - Queries PostgreSQL for least-loaded worker
   - Dynamic distribution based on current load
   - Best for long-running workflows

---

## API Reference

### `createFleetWorkflow(name, description, options)`

Creates a fleet-aware workflow execution context.

**Returns**: `{ agent, parallel, phase, complete, addLearning, trackArbiter, getExecutionStats, config }`

### `agent(prompt, options)`

Execute a single agent task (may use fleet).

**Parameters**:
- `prompt` (string) - Agent prompt
- `options.model` (string) - Model to use (default: 'claude-sonnet-4')
- `options.type` (string) - Task type for tracking (default: 'agent')
- `options.useFleet` (boolean) - Use fleet distribution (default: true)
- `options.cwd` (string) - Working directory

**Returns**: `Promise<string>` - Agent output

**Example**:
```javascript
const result = await agent('Analyze code', {
  model: 'claude-opus-4',
  type: 'code-analysis'
});
```

### `parallel(tasks, options)`

Execute tasks in parallel across fleet.

**Parameters**:
- `tasks` (Array<Object>) - Array of task objects
  - `prompt` (string) - Agent prompt
  - `model` (string) - Model to use
  - `type` (string) - Task type
- `options.maxConcurrency` (number) - Max concurrent tasks (default: 8)

**Returns**: `Promise<Array<string>>` - Array of outputs

**Example**:
```javascript
const results = await parallel([
  { prompt: 'Task 1', model: 'claude-sonnet-4', type: 'search' },
  { prompt: 'Task 2', model: 'claude-opus-4', type: 'analysis' }
], { maxConcurrency: 8 });
```

### `phase(name, fn)`

Track a workflow phase.

**Parameters**:
- `name` (string) - Phase identifier
- `fn` (Function) - Async function to execute

**Returns**: `Promise<any>` - Result from fn

**Example**:
```javascript
const searchResults = await phase('Search', async () => {
  return await parallel(searchTasks);
});
```

### `complete(result, qualityScore, outcome)`

Complete workflow and store all data.

**Parameters**:
- `result` (any) - Final workflow result
- `qualityScore` (number) - Quality score 0-1
- `outcome` (string) - 'success' | 'failed' | 'error' (default: 'success')

**Returns**: `Promise<Object>` - Stored execution data

**Example**:
```javascript
const stored = await complete(finalResult, 0.85, 'success');
// Returns: { result, stored: true, executionId, workflowId, durationMs, costUsd }
```

### `addLearning(description, insight, importance, evidence)`

Add a learning to the workflow.

**Parameters**:
- `description` (string) - Learning description
- `insight` (string) - Actionable insight
- `importance` (number) - Importance score 0-1
- `evidence` (Object) - Supporting evidence

### `getExecutionStats()`

Get execution statistics for this workflow.

**Returns**: `Object` - Per-host statistics

**Example**:
```javascript
const stats = getExecutionStats();
// {
//   'server-01': { total: 5, success: 5, avgDuration: 1234, successRate: 1.0 },
//   'laptop-01': { total: 3, success: 2, avgDuration: 2345, successRate: 0.67 }
// }
```

---

## PostgreSQL Storage

### Tables

All data is automatically stored in PostgreSQL `workflow.*` tables:

- `workflow.executions` - Workflow metadata
- `workflow.worker_results` - Agent execution results
- `workflow.arbiter_decisions` - Arbiter decisions
- `workflow.phases` - Phase tracking
- `workflow.feedback` - Quality feedback
- `workflow.learnings` - Extracted learnings

### Hostname Tracking (Issue #11)

Each worker result includes `metadata.hostname`:

```sql
SELECT
  model,
  metadata->>'hostname' as hostname,
  COUNT(*) as executions,
  AVG(duration_ms) as avg_duration,
  SUM(cost_usd) as total_cost
FROM workflow.worker_results
WHERE workflow_execution_id IN (
  SELECT id FROM workflow.executions
  WHERE workflow_name = 'my-workflow'
)
GROUP BY model, metadata->>'hostname'
ORDER BY executions DESC;
```

### Query Examples

**Find workflows by similarity:**
```javascript
const similar = await db.findSimilarWorkflows('firmware reverse engineering', 10);
```

**Get complete workflow data:**
```javascript
const workflow = await db.getWorkflowComplete('wf-1234567890-abc');
// Returns: { execution, workers, arbiters, phases, feedback, learnings }
```

---

## Integration Examples

### Example 1: Deep Research Workflow

```javascript
// workflows/deep-research.mjs
import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, parallel, phase, complete, addLearning } = createFleetWorkflow(
    'deep-research',
    args.query,
    { enableFleet: true, fleetStrategy: 'round-robin' }
  );

  // Phase 1: Decompose query
  const angles = await phase('Decompose', async () => {
    return await agent('Decompose query into 5 research angles');
  });

  // Phase 2: Parallel search (distributed across 8 workers)
  const searches = await phase('Search', async () => {
    return await parallel(
      angles.map(angle => ({
        prompt: `Search: ${angle}`,
        model: 'claude-sonnet-4',
        type: 'web-search'
      }))
    );
  });

  // Phase 3: Synthesize
  const result = await phase('Synthesize', async () => {
    return await agent('Synthesize all findings', {
      model: 'claude-opus-4',
      type: 'synthesis'
    });
  });

  // Add learning
  addLearning(
    'Multi-angle research improves coverage',
    'Breaking queries into 5+ angles yields 30% more sources',
    0.9,
    { angles: angles.length, sources: searches.length }
  );

  return complete(result, 0.85);
}
```

### Example 2: Issue #11 Workflow (10 Nice-to-Haves)

```javascript
// workflows/implement-nice-to-haves.mjs
import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';
import fs from 'fs';

export default async function({ args }) {
  const { parallel, phase, complete, getExecutionStats } = createFleetWorkflow(
    'implement-nice-to-haves',
    'ISSUES.md improvements',
    { enableFleet: true, fleetStrategy: 'round-robin' }
  );

  // Parse ISSUES.md
  const issues = parseIssuesFromFile('ISSUES.md');
  console.log(`Found ${issues.length} nice-to-have issues`);

  // Phase 1: Parallel implementation across 8 workers
  const implementations = await phase('Implement', () =>
    parallel(
      issues.map(issue => ({
        prompt: `Implement ${issue.title} from ISSUES.md`,
        model: 'claude-sonnet-4',
        type: 'code-implementation',
        estimated_tokens: 5000
      }))
    )
  );

  // Phase 2: Integration
  const integrated = await phase('Integrate', async () => {
    // Apply implementations
    for (let i = 0; i < implementations.length; i++) {
      console.log(`Applying ${issues[i].title}...`);
      // Apply code changes here
    }
    return 'integrated';
  });

  // Get execution stats (Issue #11 tracking)
  const stats = getExecutionStats();
  console.log('\n📊 Execution Distribution:');
  for (const [host, data] of Object.entries(stats)) {
    console.log(`  ${host}: ${data.total} tasks, ${data.successRate * 100}% success`);
  }

  return complete({ implementations, stats }, 0.9);
}

function parseIssuesFromFile(path) {
  const content = fs.readFileSync(path, 'utf-8');
  // Parse ISSUES.md format
  // Return: [{ id, title, description }, ...]
}
```

---

## Migration Guide

### Before (Manual Storage)

```javascript
import { WorkflowStorageAdapter } from './workflow-storage-adapter.js';

export default async function({ agent, parallel, phase }) {
  const storage = new WorkflowStorageAdapter();

  const result = await agent('Do something');

  await storage.storeExecution({ ... }); // Manual
  await storage.disconnect();

  return result;
}
```

### After (Fleet-Aware)

```javascript
import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, complete } = createFleetWorkflow('workflow-name', args.query);

  const result = await agent('Do something');

  return complete(result, 0.85); // Auto-storage + fleet distribution
}
```

---

## Debugging

### Check Execution History

```javascript
import { getExecutionHistory } from './shared/fleet-workflow-wrapper.mjs';

const history = getExecutionHistory(100);
console.log(JSON.stringify(history, null, 2));
```

### Check Global Stats

```javascript
import { getGlobalExecutionStats } from './shared/fleet-workflow-wrapper.mjs';

const stats = getGlobalExecutionStats();
for (const [host, data] of Object.entries(stats)) {
  console.log(`${host}: ${data.total} tasks, ${data.successRate * 100}% success`);
  console.log('  By workflow:', data.byWorkflow);
}
```

### Clear History (Testing)

```javascript
import { clearExecutionHistory } from './shared/fleet-workflow-wrapper.mjs';

clearExecutionHistory();
```

---

## Performance Characteristics

| Metric | Round-Robin | Cost-Optimized | Local-Only |
|--------|------------|----------------|------------|
| **Distribution fairness** | Perfect | Weighted by task size | N/A |
| **Latency overhead** | +200ms (SSH) | +200ms (SSH) | 0ms |
| **Failure recovery** | 2 retries + fallback | 2 retries + fallback | None |
| **Concurrency limit** | 8 workers | 8 workers | 1 host |

**Expected improvement for 600-agent workflow:**
- Local: 600 sequential agents = ~50 hours
- Fleet (8 workers): 600 / 8 = 75 agents/worker = ~6.25 hours
- **8× speedup** (assuming perfect distribution)

---

## Error Handling

### Three-Layer Fallback

1. **Primary worker** - Try selected worker with retries
2. **Alternate workers** - Try remaining healthy workers
3. **Local fallback** - Execute locally if all workers fail

**Configuration**:
```javascript
createFleetWorkflow('name', 'desc', {
  maxRetries: 2,           // Retry count per worker
  fallbackToLocal: true    // Enable local fallback
});
```

### Error Categories

| Error Type | Detection | Handling |
|------------|-----------|----------|
| SSH unreachable | Connection timeout | Skip to next worker |
| Claude not found | stderr contains "command not found" | Skip to next worker |
| Model API error | stdout contains "API error" | Retry on same worker |
| Timeout | Process timeout | Skip to next worker |
| Parse failure | JSON parse error | Use raw stdout |

---

## Roadmap

### Implemented

- ✅ Round-robin distribution
- ✅ Cost-optimized distribution
- ✅ PostgreSQL storage integration
- ✅ Host tracking (Issue #11)
- ✅ Execution statistics
- ✅ Phase tracking
- ✅ Learning extraction
- ✅ Three-layer fallback

### TODO (Nice-to-Haves)

- ⚠️ Load-aware worker selection (query PostgreSQL for least-loaded)
- ⚠️ Dynamic fleet discovery (auto-detect available workers)
- ⚠️ Queue management for >8 parallel tasks
- ⚠️ Real-time progress dashboard
- ⚠️ Retry with exponential backoff
- ⚠️ Worker health scoring (success rate × latency)
- ⚠️ Cost tracking per workflow
- ⚠️ Neo4j graph integration

---

## Testing

```bash
# Run test suite
node shared/fleet-workflow-wrapper.test.mjs

# Test with actual fleet (requires SSH access)
node shared/fleet-workflow-wrapper.test.mjs --fleet

# Test with storage (requires PostgreSQL)
ENABLE_STORAGE=true node shared/fleet-workflow-wrapper.test.mjs
```

---

## License

MIT (same as parent project)

---

## Support

Issues: https://github.com/[repo]/issues
Contact: See CLAUDE.md for support details
