# Task Queue Quick Reference

One-page reference for the most common task queue operations.

---

## CLI Commands

```bash
# Queue statistics
node shared/task-queue-wrapper.mjs --stats

# Pending tasks
node shared/task-queue-wrapper.mjs --pending

# Enqueue task (priority 8, model opus)
node shared/task-queue-wrapper.mjs --enqueue 8 opus "Analyze code"

# Start worker daemon
node shared/task-queue-wrapper.mjs --worker server-01
```

---

## JavaScript API

```javascript
import {
  enqueueTask,
  enqueueTasks,
  claimNextTask,
  completeTask,
  getQueueStats,
  getPendingTasks,
  createQueuedOrchestrator,
  startWorkerDaemon
} from './shared/task-queue-wrapper.mjs';

// Enqueue single task
const taskId = await enqueueTask(8, 'agent', {
  model: 'opus', task: 'Analyze code'
});

// Enqueue multiple tasks
const taskIds = await enqueueTasks([
  { priority: 10, model: 'opus', task: 'Critical' },
  { priority: 5, model: 'sonnet', task: 'Normal' }
]);

// Queue-aware orchestrator
const orch = createQueuedOrchestrator({ enableQueue: true });
const result = await orch.agent({ 
  model: 'opus', task: 'Analyze', priority: 8 
});

// Worker daemon (runs forever)
await startWorkerDaemon({ 
  workerId: 'server-01', 
  maxConcurrency: 4 
});
```

---

## SQL Queries

```sql
-- Queue depth by priority
SELECT priority, COUNT(*) FROM queue.tasks 
WHERE status = 'pending' GROUP BY priority;

-- Worker utilization
SELECT worker_id, COUNT(*) FROM queue.tasks 
WHERE status = 'in_progress' GROUP BY worker_id;

-- Recent failures
SELECT id, task_type, error_message FROM queue.tasks 
WHERE status = 'failed' AND completed_at > NOW() - INTERVAL '1 hour';

-- Dead letter queue
SELECT id, task_type, error_message FROM queue.tasks 
WHERE status = 'dead_letter' ORDER BY completed_at DESC LIMIT 20;
```

---

## Deployment

```bash
# Deploy to all workers
./scripts/deploy-task-workers.sh --start

# Check status
./scripts/deploy-task-workers.sh --status

# View logs
./scripts/deploy-task-workers.sh --logs

# Restart
./scripts/deploy-task-workers.sh --restart

# Stop
./scripts/deploy-task-workers.sh --stop
```

---

## Priority Levels

| Priority | Use Case |
|----------|----------|
| 10 | Critical (security, production failures) |
| 8 | High (code review, deployments) |
| 5 | Normal (searches, processing) |
| 3 | Low (background tasks) |
| 1 | Deferred (experiments, optimizations) |

---

## Troubleshooting

```bash
# Queue stuck? Check workers
./scripts/deploy-task-workers.sh --status

# Restart all workers
./scripts/deploy-task-workers.sh --restart

# Force release stuck tasks (SQL)
psql -h aio-01 -p 5433 -U claude -d learning -c "
  UPDATE queue.tasks SET status = 'pending', worker_id = NULL 
  WHERE status = 'in_progress' AND claimed_at < NOW() - INTERVAL '1 hour';
"

# Re-queue dead letters (SQL)
psql -h aio-01 -p 5433 -U claude -d learning -c "
  UPDATE queue.tasks SET status = 'pending', retry_count = 0 
  WHERE status = 'dead_letter' AND id IN (1,2,3);
"
```

---

## Testing

```bash
# Unit tests
python3 tools/task_queue_system.py

# Integration tests
node tests/test-task-queue-integration.mjs
```

---

## Documentation

- **Full Guide:** `docs/TASK_QUEUE_INTEGRATION.md`
- **Summary:** `docs/TASK_QUEUE_INTEGRATION_SUMMARY.md`
- **This Card:** `docs/TASK_QUEUE_QUICK_REFERENCE.md`
- **Code:** `shared/task-queue-wrapper.mjs`
