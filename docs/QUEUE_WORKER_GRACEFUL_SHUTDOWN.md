# Queue Worker Graceful Shutdown

## Overview

The queue worker system implements graceful shutdown to ensure tasks are not lost when workers are stopped. When a worker receives SIGTERM or SIGINT, it:

1. Stops claiming new tasks
2. Releases currently processing tasks back to the queue
3. Closes database connections cleanly
4. Exits with code 0

## Features

### Atomic Task Claiming
- Uses PostgreSQL `SELECT FOR UPDATE SKIP LOCKED` for lock-free claiming
- Batch claiming for efficiency (configurable batch size)
- Worker affinity (prefers tasks from same worker for cache locality)
- Priority-aware task selection

### Heartbeat Updates
- Workers send heartbeat updates every 30 seconds (configurable)
- Tasks have timeout protection (default 5 minutes)
- Timed-out tasks are automatically reclaimed by other workers

### Graceful Shutdown
- Handles SIGTERM and SIGINT signals
- Releases claimed tasks atomically
- Prevents duplicate signal handling
- Shutdown timeout protection (default 60 seconds)

### Task Processing Pipeline

```
queue.tasks → chunk worker → queue.chunk → embed worker → queue.store → store worker → knowledge.scraped_data
```

Each stage processes tasks independently with automatic retry and timeout recovery.

## Usage

### Starting a Worker

```bash
# Chunk worker
node shared/queue-worker.mjs --type=chunk --worker=laptop-01 --batch=10

# Embed worker
node shared/queue-worker.mjs --type=embed --worker=server-01 --batch=5

# Store worker
node shared/queue-worker.mjs --type=store --worker=pi-01 --batch=20
```

### Environment Variables

```bash
# Database connection
export DB_HOST=aio-01
export DB_PORT=5433
export DB_NAME=learning
export DB_USER=sfloess

# API endpoint
export API_URL=http://aio-01:5000

# Worker configuration
export WORKER_TYPE=chunk
export WORKER_ID=laptop-01
export BATCH_SIZE=10

# Timing
export POLL_INTERVAL=5000        # Poll every 5 seconds
export HEARTBEAT_INTERVAL=30000  # Heartbeat every 30 seconds
export SHUTDOWN_TIMEOUT=60000    # Force exit after 60 seconds

# Start worker
node shared/queue-worker.mjs
```

### Stopping a Worker

```bash
# Graceful shutdown (recommended)
kill -SIGTERM <pid>

# Or use Ctrl+C
^C

# Force kill (not recommended, may lose tasks)
kill -9 <pid>
```

## Worker Types

### chunk
- Reads from: `queue.tasks`
- Processes: File chunking via `/documents/chunk` API
- Writes to: `queue.chunk`
- Typical batch size: 10

### embed
- Reads from: `queue.chunk`
- Processes: Text embedding via `/documents/embed` API
- Writes to: `queue.store`
- Typical batch size: 5

### store
- Reads from: `queue.store`
- Processes: Database insertion
- Writes to: `knowledge.scraped_data`
- Typical batch size: 20

## Testing

### Run Graceful Shutdown Test

```bash
cd test
node test-queue-worker-shutdown.mjs
```

This test:
1. Creates 20 test tasks in `queue.tasks`
2. Starts a worker process
3. Waits for worker to claim tasks
4. Sends SIGTERM to worker
5. Verifies tasks are released
6. Checks worker exits cleanly
7. Cleans up test data

### Expected Output

```
=== Queue Worker Graceful Shutdown Test ===

✓ Inserted 20 test tasks
Initial queue state: { pending: 20, processing: 0, completed: 0 }

Starting worker process...
[Worker] info: Worker starting
[Worker] info: Claimed 5 tasks

Waiting 10s for worker to claim tasks...
Queue state before shutdown: { pending: 15, processing: 5, completed: 0 }
✓ Worker has claimed 5 tasks

Sending SIGTERM to worker...
[Worker] info: Received SIGTERM, initiating graceful shutdown
[Worker] info: Releasing 5 tasks back to queue
[Worker] info: Released 5 tasks
[Worker] info: Graceful shutdown complete
Worker exited with code 0, signal null

Queue state after shutdown: { pending: 18, processing: 0, completed: 2 }

=== Test Results ===
✓ Test 1: Tasks released (5 → 0)
✓ Test 2: Worker shut down cleanly (code: 0, signal: null)
✓ Test 3: Tasks completed (2 completed)

=== Summary: 3/3 tests passed ===
✓ All tests passed!
```

## Monitoring

### Worker Logs

Workers output structured JSON logs:

```json
{
  "timestamp": "2026-07-11T10:30:45.123Z",
  "level": "info",
  "worker": "laptop-01",
  "type": "chunk",
  "message": "Claimed 10 tasks",
  "taskCount": 10,
  "taskIds": [123, 124, 125, ...]
}
```

Log levels:
- `debug`: Heartbeat updates, empty polls
- `info`: Task claiming, completion, shutdown events
- `warn`: Failed tasks, retries
- `error`: Processing errors, shutdown errors

### Queue Statistics

Query queue status:

```sql
-- Overall queue stats
SELECT
  status,
  COUNT(*) as count,
  COUNT(DISTINCT claimed_by) as active_workers
FROM queue.tasks
GROUP BY status;

-- Worker-specific stats
SELECT
  claimed_by,
  COUNT(*) as tasks,
  AVG(EXTRACT(EPOCH FROM (NOW() - claimed_at))) as avg_claim_age_seconds
FROM queue.tasks
WHERE status = 'processing'
GROUP BY claimed_by;

-- Timeout detection
SELECT
  id,
  claimed_by,
  EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
FROM queue.tasks
WHERE status = 'processing'
  AND timeout_at < NOW();
```

## Architecture Decisions

### Why PostgreSQL Instead of Redis?

1. **Durability**: PostgreSQL persists tasks to disk
2. **Atomicity**: `SELECT FOR UPDATE SKIP LOCKED` provides true atomic claiming
3. **Rich queries**: Can query by priority, age, worker affinity
4. **Existing infrastructure**: No new service to maintain

### Why Batch Claiming?

1. **Efficiency**: Reduces database round-trips
2. **Latency**: Processes multiple tasks before checking queue again
3. **Throughput**: Higher overall throughput with batching

### Why Worker Affinity?

1. **Cache locality**: Same worker may have files/embeddings cached
2. **Connection reuse**: Reduces connection overhead
3. **Load balancing**: Still allows other workers to claim tasks

## Failure Modes

### Worker Crashes Without Graceful Shutdown

- Tasks remain in `processing` state with `timeout_at` timestamp
- Automatic timeout recovery reclaims tasks after 5 minutes
- Other workers can continue processing

### Database Connection Lost

- Worker retries connection (default retry logic)
- If retry fails, worker logs error and exits
- Tasks are reclaimed via timeout mechanism

### API Endpoint Down

- Individual tasks fail and are marked for retry
- Exponential backoff: 1 min, 2 min, 4 min delays
- After 3 retries, task is marked `failed`

### Multiple Workers Claim Same Task

- Prevented by `SELECT FOR UPDATE SKIP LOCKED`
- PostgreSQL guarantees only one worker can claim each task
- No race conditions possible

## Performance Tuning

### Batch Size

- **Small batches (5-10)**: Lower latency, faster shutdown
- **Large batches (20-50)**: Higher throughput, slower shutdown
- **Recommended**: 10 for chunk/embed, 20 for store

### Poll Interval

- **Fast polling (1-2s)**: Lower latency, higher database load
- **Slow polling (10-30s)**: Lower database load, higher latency
- **Recommended**: 5s for production

### Heartbeat Interval

- **Fast heartbeat (10-15s)**: Faster timeout detection, higher database load
- **Slow heartbeat (60s+)**: Lower database load, slower timeout detection
- **Recommended**: 30s for production

## Security Considerations

### Input Validation

- Worker validates task data before processing
- API endpoints validate inputs
- SQL injection prevented via parameterized queries

### Resource Limits

- Shutdown timeout prevents hung workers
- Batch size limits prevent memory exhaustion
- Connection pool limits prevent database overload

### Authentication

- Workers use authenticated API endpoints
- Database credentials via environment variables
- No credentials in logs or code

## Future Enhancements

1. **Metrics Export**: Prometheus metrics for monitoring
2. **Auto-scaling**: Dynamic worker count based on queue depth
3. **Priority Queues**: Multiple priority levels
4. **Dead Letter Queue**: Separate queue for failed tasks
5. **Task Dependencies**: Wait for upstream tasks to complete
6. **Distributed Tracing**: OpenTelemetry integration

## Related Documentation

- [PostgreSQL Queue Batch API](../shared/postgres-queue-batch.js)
- [Queue Worker Implementation](../shared/queue-worker.mjs)
- [Workflow Queue Processing](../workflows/queue-workers.mjs)
- [Database Schema](../migrations/)
