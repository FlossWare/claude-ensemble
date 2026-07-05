# Workflow Resource Monitor

Track memory and CPU usage during workflow execution. Automatically samples resource usage every 1 second and logs aggregated statistics to PostgreSQL.

**Created:** 2026-07-04  
**Location:** `shared/workflow-resource-monitor.cjs`  
**Database:** PostgreSQL `learning` on `aio-01:5433`  
**Table:** `monitoring.resource_usage`

---

## Features

- **Auto-sampling**: Collects memory/CPU metrics every 1 second (configurable)
- **Aggregated statistics**: Peak/avg/min memory, avg/max/min CPU
- **PostgreSQL storage**: Persistent storage with indexed queries
- **Execution linking**: Optional link to workflow execution IDs
- **History queries**: Retrieve past resource usage by workflow or execution ID
- **Aggregated reports**: System-wide statistics across all workflows

---

## Quick Start

```javascript
const { startMonitoring, stopMonitoring } = require('./shared/workflow-resource-monitor.cjs');

// Start monitoring
const workflowId = 'my-workflow-' + Date.now();
startMonitoring(workflowId);

// ... workflow execution ...

// Stop monitoring and get stats
const stats = await stopMonitoring(workflowId);
console.log(`Duration: ${stats.duration_ms}ms`);
console.log(`Peak Memory: ${stats.peak_memory_mb}MB`);
console.log(`Avg CPU: ${stats.avg_cpu_percent}%`);
```

---

## API Reference

### `startMonitoring(workflowId, options)`

Begin tracking resource usage for a workflow.

**Parameters:**
- `workflowId` (string) - Workflow identifier
- `options` (object, optional)
  - `sampleIntervalMs` (number) - Sampling interval in milliseconds (default: 1000)

**Example:**
```javascript
startMonitoring('wf-12345');
startMonitoring('wf-67890', { sampleIntervalMs: 500 }); // Sample every 500ms
```

---

### `stopMonitoring(workflowId, options)`

Stop tracking and return aggregated statistics. Automatically stores to PostgreSQL.

**Parameters:**
- `workflowId` (string) - Workflow identifier
- `options` (object, optional)
  - `workflowExecutionId` (number) - Optional workflow execution ID to link in database

**Returns:** Promise\<Object\> - Aggregated resource usage statistics

**Example:**
```javascript
const stats = await stopMonitoring('wf-12345');
// => {
//   workflow_id: 'wf-12345',
//   duration_ms: 45000,
//   peak_memory_mb: 245.3,
//   avg_memory_mb: 210.5,
//   min_memory_mb: 195.2,
//   avg_cpu_percent: 32.5,
//   max_cpu_percent: 85.3,
//   min_cpu_percent: 5.2,
//   sample_count: 45,
//   start_time: '2026-07-04T10:15:30.000Z',
//   end_time: '2026-07-04T10:16:15.000Z'
// }

// With execution ID
const statsWithExecId = await stopMonitoring('wf-12345', { workflowExecutionId: 12345 });
```

---

### `getResourceHistory(workflowId, options)`

Retrieve resource usage history for a workflow.

**Parameters:**
- `workflowId` (string) - Workflow identifier
- `options` (object, optional)
  - `limit` (number) - Maximum number of records to return (default: 100)

**Returns:** Promise\<Array\> - Resource usage records

**Example:**
```javascript
const history = await getResourceHistory('wf-12345');
const recent = await getResourceHistory('wf-12345', { limit: 10 });
```

---

### `getResourceByExecutionId(workflowExecutionId)`

Retrieve resource usage statistics by workflow execution ID.

**Parameters:**
- `workflowExecutionId` (number) - Workflow execution ID

**Returns:** Promise\<Object|null\> - Resource usage record or null if not found

**Example:**
```javascript
const stats = await getResourceByExecutionId(12345);
if (stats) {
  console.log(`Peak Memory: ${stats.peak_memory_mb}MB`);
}
```

---

### `getAggregatedStats(options)`

Get aggregated resource usage statistics across all workflows.

**Parameters:**
- `options` (object, optional)
  - `since` (string) - ISO timestamp to filter records after (e.g., '2026-07-01T00:00:00Z')
  - `limit` (number) - Maximum number of records to analyze (default: 1000)

**Returns:** Promise\<Object\> - Aggregated statistics

**Example:**
```javascript
const stats = await getAggregatedStats();
// => {
//   total_workflows: 150,
//   avg_duration_ms: 23456,
//   max_duration_ms: 120000,
//   min_duration_ms: 5000,
//   avg_peak_memory_mb: 512.3,
//   max_peak_memory_mb: 1024.5,
//   avg_cpu_percent: 45.2,
//   max_cpu_percent: 98.5
// }

// Last 24 hours only
const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const recentStats = await getAggregatedStats({ since: yesterday });
```

---

## Database Schema

```sql
CREATE TABLE monitoring.resource_usage (
  id SERIAL PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  workflow_execution_id INTEGER,
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  duration_ms INTEGER NOT NULL,
  peak_memory_mb NUMERIC(10, 2) NOT NULL,
  avg_memory_mb NUMERIC(10, 2) NOT NULL,
  min_memory_mb NUMERIC(10, 2) NOT NULL,
  avg_cpu_percent NUMERIC(5, 2) NOT NULL,
  max_cpu_percent NUMERIC(5, 2) NOT NULL,
  min_cpu_percent NUMERIC(5, 2) NOT NULL,
  sample_count INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_resource_usage_workflow_id ON monitoring.resource_usage(workflow_id);
CREATE INDEX idx_resource_usage_workflow_execution_id ON monitoring.resource_usage(workflow_execution_id);
CREATE INDEX idx_resource_usage_created_at ON monitoring.resource_usage(created_at);
```

---

## Integration Patterns

### Basic Workflow Integration

```javascript
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const { startMonitoring, stopMonitoring } = require('./shared/workflow-resource-monitor.cjs');

export default async function myWorkflow({ phase, parallel, agent }) {
  const workflowId = 'my-workflow-' + Date.now();
  
  // Start monitoring
  startMonitoring(workflowId);
  
  try {
    // Execute workflow phases
    await phase('Process', async () => {
      // ... workflow logic ...
    });
    
    return { success: true };
    
  } catch (error) {
    throw error;
    
  } finally {
    // Always stop monitoring (even on error)
    const stats = await stopMonitoring(workflowId);
    console.log(`Resource usage: ${stats.peak_memory_mb}MB peak, ${stats.avg_cpu_percent}% avg CPU`);
  }
}
```

### Integration with Workflow Storage Adapter

```javascript
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.cjs');
const { startMonitoring, stopMonitoring } = require('./shared/workflow-resource-monitor.cjs');

export default async function myWorkflow({ phase, parallel, agent }) {
  const db = getWorkflowStorage();
  const workflowId = 'my-workflow-' + Date.now();
  
  // Start resource monitoring
  startMonitoring(workflowId);
  
  try {
    // Store workflow execution
    const execId = await db.storeExecution({
      workflow_id: workflowId,
      workflow_name: 'my-workflow',
      task_description: 'Process data',
      total_workers: 3,
      outcome: 'running'
    });
    
    // Execute workflow...
    await phase('Process', async () => {
      // ... workflow logic ...
    });
    
    // Update workflow outcome
    await db.pool.query(
      'UPDATE workflow.executions SET outcome = $1 WHERE id = $2',
      ['success', execId]
    );
    
    // Stop monitoring and link to execution ID
    const resourceStats = await stopMonitoring(workflowId, {
      workflowExecutionId: execId
    });
    
    return { success: true, execId, resourceStats };
    
  } catch (error) {
    await stopMonitoring(workflowId); // Stop even on error
    throw error;
  }
}
```

---

## Common Queries

### Recent workflow failures with high memory usage

```sql
SELECT 
  r.workflow_id,
  r.peak_memory_mb,
  r.avg_cpu_percent,
  r.duration_ms,
  w.outcome
FROM monitoring.resource_usage r
JOIN workflow.executions w ON r.workflow_execution_id = w.id
WHERE w.outcome = 'error'
  AND r.peak_memory_mb > 1000
ORDER BY r.created_at DESC
LIMIT 10;
```

### Workflows with abnormal CPU usage

```sql
SELECT 
  workflow_id,
  avg_cpu_percent,
  max_cpu_percent,
  duration_ms,
  created_at
FROM monitoring.resource_usage
WHERE avg_cpu_percent > 80
  OR max_cpu_percent > 95
ORDER BY created_at DESC
LIMIT 10;
```

### Resource usage trends over time

```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_workflows,
  AVG(peak_memory_mb) as avg_peak_memory,
  AVG(avg_cpu_percent) as avg_cpu,
  AVG(duration_ms) as avg_duration
FROM monitoring.resource_usage
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Testing

Run the test suite to verify functionality:

```bash
node shared/test-workflow-resource-monitor.cjs
```

**Tests include:**
- Basic workflow monitoring (5 seconds)
- Workflow with execution ID linking
- Custom sample interval (500ms)
- Query resource history
- Query by execution ID
- Aggregated statistics (all workflows)
- Recent aggregated statistics (24 hours)

---

## Resource Metrics Explained

### Memory Metrics

- **Peak Memory MB**: Maximum memory usage during workflow execution
- **Avg Memory MB**: Average memory usage across all samples
- **Min Memory MB**: Minimum memory usage during workflow execution

Memory is measured as total system memory minus free memory (used memory).

### CPU Metrics

- **Avg CPU Percent**: Average CPU load across all samples (0-100%)
- **Max CPU Percent**: Maximum CPU load during workflow execution
- **Min CPU Percent**: Minimum CPU load during workflow execution

CPU load is calculated from 1-minute load average normalized by CPU count.  
Load of 4.0 on 4 cores = 100% CPU usage.

### Sample Count

Number of resource samples collected during workflow execution.  
Higher sample count = more accurate statistics.

**Default interval:** 1 sample per second  
**5-second workflow:** ~6 samples (including initial + final samples)

---

## Performance Considerations

- **Minimal overhead**: Sampling uses native `os` module (< 1ms per sample)
- **Memory efficient**: Samples stored in-memory array during execution only
- **PostgreSQL storage**: Async insert after workflow completes (non-blocking)
- **Indexing**: Workflow ID, execution ID, and timestamp indexes for fast queries

**Recommended for:**
- Production workflows (< 1% overhead)
- Development debugging (identify resource bottlenecks)
- Long-running workflows (track resource trends over time)

---

## Troubleshooting

### Missing resource usage records

Check that `stopMonitoring()` was called:

```javascript
// BAD: Missing stopMonitoring
startMonitoring('wf-12345');
// ... workflow execution ...
// No record stored!

// GOOD: Always use try/finally
startMonitoring('wf-12345');
try {
  // ... workflow execution ...
} finally {
  await stopMonitoring('wf-12345');
}
```

### PostgreSQL connection errors

Verify database connection:

```bash
PGPASSWORD='' psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1"
```

Check connection pool configuration in `workflow-resource-monitor.cjs`:

```javascript
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});
```

### Inaccurate CPU measurements

CPU load is an approximation based on system load average:

- **Load average**: Smoothed over 1 minute (not real-time)
- **Multi-process**: Measures total system load (not just this workflow)
- **CPU count**: Normalized by number of CPU cores

For more accurate CPU measurement, use process-level monitoring:

```javascript
const startCPU = process.cpuUsage();
// ... work ...
const endCPU = process.cpuUsage(startCPU);
const cpuPercent = 100 * (endCPU.user + endCPU.system) / (duration * 1000);
```

---

## Files

- **`shared/workflow-resource-monitor.cjs`** - Main implementation (400 lines)
- **`shared/test-workflow-resource-monitor.cjs`** - Test suite (200 lines)
- **`shared/example-workflow-with-monitoring.mjs`** - Example integration (150 lines)
- **`shared/WORKFLOW_RESOURCE_MONITOR.md`** - This documentation

---

## See Also

- **Workflow Storage Adapter**: `shared/workflow-storage-adapter.cjs`
- **Feedback Loop Optimizer**: `tools/feedback_loop_optimizer.py`
- **PostgreSQL Adapter**: `~/.claude/learning/postgres-adapter.js`
- **Monitoring Infrastructure**: `docs/MONITORING.md`
