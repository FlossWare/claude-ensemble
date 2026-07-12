# Redis Queue Quick Reference

**Last Updated:** 2026-07-11

---

## TL;DR

- **Initial queues** (`redis:queue:store:*`) → **ZSET** (priority)
- **Pipeline queues** (`redis:queue:chunk`, etc.) → **LIST** (FIFO)

---

## Queue Types

| Queue Name | Type | Add | Pop | Count |
|------------|------|-----|-----|-------|
| `redis:queue:store:high` | ZSET | `ZADD` | `ZPOPMIN` | `ZCARD` |
| `redis:queue:store:medium` | ZSET | `ZADD` | `ZPOPMIN` | `ZCARD` |
| `redis:queue:store:low` | ZSET | `ZADD` | `ZPOPMIN` | `ZCARD` |
| `redis:queue:chunk` | LIST | `LPUSH` | `RPOP/BRPOP` | `LLEN` |
| `redis:queue:embed` | LIST | `LPUSH` | `RPOP/BRPOP` | `LLEN` |
| `redis:queue:index` | LIST | `LPUSH` | `RPOP/BRPOP` | `LLEN` |
| `redis:dlq:*` | LIST | `LPUSH` | `RPOP` | `LLEN` |

---

## Python API

### Claim Task

```python
from redis_atomic_operations import RedisAtomicOps

ops = RedisAtomicOps(host='aio-01')

# From ZSET (priority queue)
task = ops.claim_task(
    'redis:queue:store:high',
    worker_id='worker-1',
    queue_mode='zset'  # Default
)

# From LIST (FIFO queue)
task = ops.claim_task(
    'redis:queue:chunk',
    worker_id='worker-1',
    queue_mode='list'
)
```

### Complete Task

```python
import json

# Complete and push to LIST (FIFO)
ops.complete_task(
    task_id=task['id'],
    worker_id='worker-1',
    result_json=json.dumps({'chunks': 5}),
    stage='store:high',
    next_queue='redis:queue:chunk',
    next_queue_mode='list'  # Default
)

# Complete and push to ZSET (priority)
ops.complete_task(
    task_id=task['id'],
    worker_id='worker-1',
    result_json=json.dumps({'vector_id': 'v123'}),
    stage='chunk',
    next_queue='redis:queue:embed:high',
    next_queue_mode='zset'
)
```

### Fail Task

```python
# Fail and requeue (or DLQ if max retries)
ops.fail_task(
    task_id=task['id'],
    worker_id='worker-1',
    error_msg='Processing timeout',
    stage='store:high',
    max_retries=3
)
```

### Batch Claim

```python
# Claim multiple tasks at once
tasks = ops.batch_claim_tasks(
    'redis:queue:store:high',
    worker_id='worker-1',
    batch_size=10,
    queue_mode='zset'  # or 'list'
)
```

### Heartbeat

```python
# Update heartbeat to prevent recovery
ops.update_heartbeat(
    task_id=task['id'],
    worker_id='worker-1',
    stage='store:high',
    heartbeat_ttl_sec=300  # 5 minutes
)
```

### Recover Stuck Tasks

```python
# Recover tasks with expired heartbeats
recovered = ops.recover_stuck_tasks(
    stage='store:high',
    stuck_threshold_ms=300000  # 5 minutes
)
print(f"Recovered {recovered} stuck tasks")
```

---

## Priority Score Formula

```python
score = (10 - priority) * 1e13 + timestamp_ms
```

**Why inverted?**
- `ZPOPMIN` pops **LOWEST** score first
- Higher priority (10) = LOWER score (0) → pops FIRST ✓
- Lower priority (1) = HIGHER score (9e13) → pops LAST ✓

**FIFO within same priority:**
- Older timestamp (smaller) = lower score → pops first ✓

---

## Common Errors

### WRONGTYPE Operation against a key holding the wrong kind of value

**Cause:** Using LIST ops on ZSET (or vice versa)

**Fix:**
```python
# WRONG
redis.llen('redis:queue:store:high')  # LIST op on ZSET ✗

# RIGHT
redis.zcard('redis:queue:store:high')  # ZSET op ✓
```

### Tasks Not Processing in Priority Order

**Cause:** Wrong score formula

**Fix:**
```python
# WRONG (higher priority = higher score)
score = priority * 1e13 + timestamp_ms  # ✗

# RIGHT (higher priority = LOWER score)
score = (10 - priority) * 1e13 + timestamp_ms  # ✓
```

### Data Lost Between Stages

**Cause:** Not using `next_queue_mode` parameter

**Fix:**
```python
# WRONG (result only, original task lost)
ops.complete_task(task_id, worker_id, result_json, stage='store')

# RIGHT (result merged into original task)
ops.complete_task(
    task_id, worker_id, result_json,
    stage='store:high',
    next_queue='redis:queue:chunk',
    next_queue_mode='list'  # Explicit mode
)
```

---

## Verification Commands

### Check Queue Counts

```bash
# ZSET queues
redis-cli -h aio-01 ZCARD redis:queue:store:high
redis-cli -h aio-01 ZCARD redis:queue:store:medium
redis-cli -h aio-01 ZCARD redis:queue:store:low

# LIST queues
redis-cli -h aio-01 LLEN redis:queue:chunk
redis-cli -h aio-01 LLEN redis:queue:embed
redis-cli -h aio-01 LLEN redis:queue:index
```

### Peek at Queue

```bash
# ZSET (first item)
redis-cli -h aio-01 ZRANGE redis:queue:store:high 0 0 WITHSCORES

# LIST (next item to pop)
redis-cli -h aio-01 LRANGE redis:queue:chunk -1 -1
```

### Check Processing

```bash
# Processing hash
redis-cli -h aio-01 HKEYS redis:processing:store:high

# Processing metadata
redis-cli -h aio-01 HKEYS redis:processing:store:high:metadata

# Heartbeats
redis-cli -h aio-01 HGETALL redis:heartbeat:store:high
```

---

## Testing

```bash
# Test hybrid mode
python3 scripts/test-complete-hybrid-mode.py

# Test bug fixes
python3 scripts/test-redis-bug-fixes.py

# Full integration test
python3 scripts/test-redis-integration.py
```

---

## See Also

- **Full Documentation:** `docs/REDIS_QUEUE_DATA_STRUCTURES.md`
- **Migration Guide:** `docs/REDIS_MIGRATION.md`
- **Source Code:** `scripts/redis-atomic-operations.py`
