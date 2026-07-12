# PostgreSQL Queue Batch Operations

**Status:** Implemented  
**Date:** 2026-07-11  
**Purpose:** Atomic batch claiming and processing for PostgreSQL queues

---

## Overview

The batch operations system allows workers to claim and process multiple queue tasks atomically, improving throughput and reducing database round-trips.

**Key Features:**
- ✅ Atomic batch claiming using `SELECT FOR UPDATE SKIP LOCKED`
- ✅ Worker affinity (prefer tasks from same worker)
- ✅ Priority-aware batching
- ✅ Automatic retry with exponential backoff
- ✅ Heartbeat updates for long-running batches
- ✅ Timeout handling and reclamation

---

## Architecture

### Atomic Claiming

**Problem:** Multiple workers competing for tasks can cause:
- Lost updates (worker A overwrites worker B's claim)
- Duplicate processing (both workers claim same task)
- Race conditions (task state changes during claim)

**Solution:** PostgreSQL `SELECT FOR UPDATE SKIP LOCKED`

```sql
-- Atomic batch claim (simplified)
WITH available_tasks AS (
  SELECT id
  FROM queue.store
  WHERE status = 'pending'
  ORDER BY priority DESC, created_at ASC
  LIMIT 10
  FOR UPDATE SKIP LOCKED  -- Skip locked rows, no waiting
)
UPDATE queue.store
SET status = 'processing', claimed_by = 'worker-01'
FROM available_tasks
WHERE queue.store.id = available_tasks.id
RETURNING *
```

**Guarantees:**
- Only one worker claims each task
- No deadlocks (SKIP LOCKED prevents waiting)
- Atomic (all or nothing in transaction)

### Worker Affinity

Workers that previously processed tasks from the same source get priority for related tasks.

**Why:** Improves cache locality and reduces context switching.

**Implementation:**
```sql
-- Boost priority for tasks from same worker
CASE
  WHEN last_worker_id = 'worker-01' THEN priority + (0.3 * 100)
  ELSE priority
END AS effective_priority
```

**Example:**
- Task A: priority=50, last_worker_id='worker-01'
- Task B: priority=60, last_worker_id='worker-02'
- Worker-01 claims Task A first (effective priority = 80)

### Retry Strategy

**Exponential Backoff:**
- Retry 1: Wait 1 minute
- Retry 2: Wait 2 minutes
- Retry 3: Wait 4 minutes
- After 3 retries: Mark as failed permanently

**Implementation:**
```sql
scheduled_at = NOW() + (INTERVAL '1 minute' * POWER(2, retry_count))
```

---

## API Reference

### JavaScript API

**File:** `shared/postgres-queue-batch.js`

```javascript
const { getQueueBatch } = require('./shared/postgres-queue-batch');

const queue = getQueueBatch();

// Claim batch
const tasks = await queue.claimBatch('store', 'worker-01', 10, {
  priorityMin: 0,
  priorityMax: 100,
  timeout: 300,
  affinityWeight: 0.3,
});

// Process tasks...
for (const task of tasks) {
  console.log(`Processing: ${task.id}`);
}

// Complete batch
await queue.completeBatch('store', tasks.map(t => t.id), {
  success: true,
});

// Or fail batch
await queue.failBatch('store', tasks.map(t => t.id), 'Error message', true);

// Update heartbeat
await queue.heartbeatBatch('store', tasks.map(t => t.id));

// Get stats
const stats = await queue.getBatchStats('store');
console.log(stats);
```

### Python API

**File:** `tools/postgres_queue_batch.py`

```python
from postgres_queue_batch import get_queue_batch

queue = get_queue_batch()

# Claim batch
tasks = queue.claim_batch('store', 'worker-01', batch_size=10, options={
    'priority_min': 0,
    'priority_max': 100,
    'timeout': 300,
    'affinity_weight': 0.3,
})

# Process tasks...
for task in tasks:
    print(f"Processing: {task['id']}")

# Complete batch
task_ids = [t['id'] for t in tasks]
queue.complete_batch('store', task_ids, {'success': True})

# Or fail batch
queue.fail_batch('store', task_ids, 'Error message', retry=True)

# Update heartbeat
queue.heartbeat_batch('store', task_ids)

# Get stats
stats = queue.get_batch_stats('store')
print(stats)
```

---

## Methods

### `claimBatch(queueName, workerId, batchSize, options)`

Atomically claim multiple tasks from queue.

**Parameters:**
- `queueName` (string): Queue name (store, chunk, embed, graph)
- `workerId` (string): Worker identifier
- `batchSize` (number): Number of tasks to claim (default: 10)
- `options` (object):
  - `priorityMin` (number): Minimum priority (default: 0)
  - `priorityMax` (number): Maximum priority (default: 100)
  - `timeout` (number): Task timeout in seconds (default: 300)
  - `affinityWeight` (number): Worker affinity weight 0-1 (default: 0.3)

**Returns:** Array of task objects

**Task Object:**
```javascript
{
  id: 123,
  data: { url: 'https://...', source: 'wikipedia' },
  priority: 50,
  createdAt: '2026-07-11T12:00:00Z',
  retryCount: 0,
  timeoutAt: '2026-07-11T12:05:00Z',
  queueName: 'store',
  workerId: 'worker-01',
}
```

### `completeBatch(queueName, taskIds, results)`

Complete multiple tasks atomically.

**Parameters:**
- `queueName` (string): Queue name
- `taskIds` (array): Array of task IDs to complete
- `results` (object): Optional results to store

**Returns:** Number of tasks completed

### `failBatch(queueName, taskIds, error, retry)`

Fail multiple tasks atomically.

**Parameters:**
- `queueName` (string): Queue name
- `taskIds` (array): Array of task IDs to fail
- `error` (string): Error message
- `retry` (boolean): Whether to retry (default: true)

**Returns:** Number of tasks failed

**Behavior:**
- If `retry=true` and `retry_count < 3`: Mark as pending with exponential backoff
- Otherwise: Mark as failed permanently

### `heartbeatBatch(queueName, taskIds)`

Update heartbeat for multiple tasks.

**Parameters:**
- `queueName` (string): Queue name
- `taskIds` (array): Array of task IDs

**Returns:** Number of tasks updated

**Why:** Long-running batches should update heartbeat to prevent timeout reclamation.

### `getBatchStats(queueName)`

Get queue statistics.

**Parameters:**
- `queueName` (string): Queue name

**Returns:** Statistics object

**Stats Object:**
```javascript
{
  pending: 1234,
  processing: 45,
  completed: 9876,
  failed: 12,
  active_workers: 8,
  avg_completion_time: 12.5,  // seconds
  avg_retries: 0.3,
}
```

### `reclaimTimedOut(queueName)`

Reclaim timed-out tasks.

**Parameters:**
- `queueName` (string): Queue name

**Returns:** Number of tasks reclaimed

**Behavior:**
- Finds tasks with `timeout_at < NOW()` and `status = 'processing'`
- Marks as pending with incremented retry_count
- Schedules retry with exponential backoff

---

## Usage Examples

### Basic Worker

```javascript
const { getQueueBatch } = require('./shared/postgres-queue-batch');

const queue = getQueueBatch();
const workerId = 'worker-01';
const queueName = 'store';

async function processTask(task) {
  console.log(`Processing task ${task.id}`);
  // ... do work ...
  return { success: true };
}

async function run() {
  while (true) {
    // Claim batch
    const tasks = await queue.claimBatch(queueName, workerId, 10);
    
    if (tasks.length === 0) {
      await new Promise(r => setTimeout(r, 5000)); // Wait 5s
      continue;
    }

    // Process tasks
    const results = await Promise.all(tasks.map(processTask));

    // Complete batch
    const taskIds = tasks.map(t => t.id);
    await queue.completeBatch(queueName, taskIds, { results });

    console.log(`Completed ${tasks.length} tasks`);
  }
}

run().catch(console.error);
```

### Worker with Heartbeat

```javascript
async function processWithHeartbeat(queue, tasks, queueName) {
  const taskIds = tasks.map(t => t.id);
  
  // Start heartbeat interval
  const heartbeatInterval = setInterval(async () => {
    await queue.heartbeatBatch(queueName, taskIds);
    console.log('Heartbeat updated');
  }, 30000); // Every 30s

  try {
    // Process tasks
    const results = await Promise.all(tasks.map(processTask));
    
    // Complete
    await queue.completeBatch(queueName, taskIds, { results });
  } finally {
    clearInterval(heartbeatInterval);
  }
}
```

### Worker with Error Handling

```javascript
async function processWithErrorHandling(queue, tasks, queueName) {
  const successful = [];
  const failed = [];

  for (const task of tasks) {
    try {
      await processTask(task);
      successful.push(task.id);
    } catch (error) {
      console.error(`Task ${task.id} failed:`, error);
      failed.push(task.id);
    }
  }

  // Complete successful tasks
  if (successful.length > 0) {
    await queue.completeBatch(queueName, successful);
  }

  // Fail unsuccessful tasks (with retry)
  if (failed.length > 0) {
    await queue.failBatch(queueName, failed, 'Processing error', true);
  }

  return { successful: successful.length, failed: failed.length };
}
```

### Parallel Workers

```bash
# Start 8 workers in parallel
for i in {1..8}; do
  node worker.js --worker "worker-$i" --queue store &
done

# Wait for all workers
wait
```

---

## Performance Optimization

### Batch Size Selection

**Trade-offs:**

| Batch Size | Pros | Cons |
|------------|------|------|
| 1 | Low latency, simple recovery | High database overhead |
| 10 | Good balance | Moderate recovery time |
| 100 | High throughput | Long recovery on failure |

**Recommendation:** 10-50 tasks per batch for most workloads

### Worker Affinity

**When to use:**
- Tasks have locality (same source, same category)
- Workers have caches (embedding models, parsers)
- Workers have specialization (GPU vs CPU)

**When to skip:**
- Tasks are completely independent
- Workers are homogeneous
- Cache hit rate is low

Set `affinityWeight: 0` to disable.

### Database Connection Pooling

**JavaScript:**
```javascript
const queue = getQueueBatch({
  maxConnections: 20,  // Pool size
});
```

**Python:**
```python
queue = PostgresQueueBatch({
    'max_connections': 20,
})
```

**Recommendation:** 2-4 connections per worker

---

## Monitoring

### Queue Stats

```javascript
const stats = await queue.getBatchStats('store');

console.log(`
  Pending: ${stats.pending}
  Processing: ${stats.processing}
  Completed: ${stats.completed}
  Failed: ${stats.failed}
  Active workers: ${stats.active_workers}
  Avg completion time: ${stats.avg_completion_time}s
  Avg retries: ${stats.avg_retries}
`);
```

### Prometheus Metrics

Export queue stats to Prometheus:

```javascript
const client = require('prom-client');

const pendingGauge = new client.Gauge({
  name: 'queue_pending_tasks',
  help: 'Number of pending tasks',
  labelNames: ['queue'],
});

async function updateMetrics() {
  const stats = await queue.getBatchStats('store');
  pendingGauge.set({ queue: 'store' }, stats.pending);
}

setInterval(updateMetrics, 10000); // Every 10s
```

### Grafana Dashboard

**Query:** Queue depth over time
```sql
SELECT
  time_bucket('1 minute', created_at) AS time,
  COUNT(*) FILTER (WHERE status = 'pending') as pending,
  COUNT(*) FILTER (WHERE status = 'processing') as processing
FROM queue.store
GROUP BY time
ORDER BY time
```

---

## Testing

**File:** `test/postgres-queue-batch.test.js`

Run tests:
```bash
npm test postgres-queue-batch
```

**Test Coverage:**
- ✅ Atomic batch claiming
- ✅ Priority ordering
- ✅ SKIP LOCKED (no conflicts)
- ✅ Worker affinity
- ✅ Batch completion
- ✅ Batch failure with retry
- ✅ Heartbeat updates
- ✅ Timeout reclamation
- ✅ Statistics

---

## Troubleshooting

### No Tasks Claimed

**Possible causes:**
1. All tasks already claimed (check `processing` count)
2. All tasks scheduled for future (check `scheduled_at`)
3. All tasks exceeded retry limit (check `failed` count)

**Debug:**
```sql
SELECT status, COUNT(*)
FROM queue.store
GROUP BY status;
```

### Tasks Stuck in Processing

**Possible causes:**
1. Worker crashed without completing
2. Timeout too long
3. Heartbeat not updating

**Fix:**
```javascript
// Reclaim timed-out tasks
const reclaimed = await queue.reclaimTimedOut('store');
console.log(`Reclaimed ${reclaimed} tasks`);
```

### High Retry Rate

**Possible causes:**
1. Tasks failing repeatedly
2. Worker errors
3. External service unavailable

**Debug:**
```sql
SELECT error, COUNT(*)
FROM queue.store
WHERE status = 'failed' OR retry_count > 0
GROUP BY error;
```

---

## Best Practices

1. **Use appropriate batch sizes** - 10-50 for most workloads
2. **Update heartbeat** - For batches taking >30s
3. **Handle errors gracefully** - Fail individual tasks, not entire batch
4. **Monitor queue depth** - Alert if pending > threshold
5. **Reclaim timeouts** - Run periodically (every 1-5 minutes)
6. **Use worker affinity** - When tasks have locality
7. **Set reasonable timeouts** - 2-5 minutes for most tasks
8. **Log failures** - Include task ID and error in logs

---

## Related Documentation

- `docs/QUEUE_SYSTEM.md` - Overall queue architecture
- `shared/postgres-queue-batch.js` - JavaScript implementation
- `tools/postgres_queue_batch.py` - Python implementation
- `test/postgres-queue-batch.test.js` - Test suite

---

**Last Updated:** 2026-07-11  
**Maintainer:** Development team
