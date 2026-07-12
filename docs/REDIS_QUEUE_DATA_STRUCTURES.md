# Redis Queue Data Structures - AUTHORITATIVE REFERENCE

**Last Updated:** 2026-07-11  
**Status:** FIXED - All queues now use correct data structures

---

## Overview

The Redis queue system uses a **HYBRID architecture** with two data structure types:

1. **Sorted Sets (ZSET)** - For priority-based queues (initial stage)
2. **Lists (LIST)** - For FIFO queues (processing pipeline stages)

---

## Queue Types by Stage

### Initial Storage Queues (SORTED SETS)

**Queue Names:**
- `redis:queue:store:high` → ZSET (priority 8-10)
- `redis:queue:store:medium` → ZSET (priority 4-7)
- `redis:queue:store:low` → ZSET (priority 1-3)

**Operations:**
- **Add:** `ZADD <queue> <score> <task_json>`
  - Score formula: `(10 - priority) * 1e13 + timestamp_ms`
  - Higher priority = LOWER score (pops FIRST)
  - Within same priority: older timestamp = lower score (FIFO)
- **Pop:** `ZPOPMIN <queue>` (returns lowest score = highest priority)
- **Count:** `ZCARD <queue>`
- **Peek:** `ZRANGE <queue> 0 -1` (all items) or `ZRANGE <queue> 0 0` (first item)

**Why ZSET?**
- Supports priority-based ordering
- Maintains FIFO within same priority level
- Allows inspection without claiming

**Example:**
```python
# Priority 10 task @ t=1000
score = (10 - 10) * 1e13 + 1000 = 1000 (pops FIRST)

# Priority 5 task @ t=1000
score = (10 - 5) * 1e13 + 1000 = 50000000000001000 (pops AFTER priority 10)

# Priority 10 task @ t=2000
score = (10 - 10) * 1e13 + 2000 = 2000 (pops AFTER t=1000 task, FIFO ✓)
```

---

### Processing Pipeline Queues (LISTS)

**Queue Names:**
- `redis:queue:chunk` → LIST (FIFO)
- `redis:queue:embed` → LIST (FIFO)
- `redis:queue:index` → LIST (FIFO)

**Operations:**
- **Add:** `LPUSH <queue> <task_json>` (push to left/head)
- **Pop:** `RPOP <queue>` or `BRPOP <queue> <timeout>` (pop from right/tail = FIFO)
- **Count:** `LLEN <queue>`
- **Peek:** `LRANGE <queue> 0 -1` (all items) or `LRANGE <queue> -1 -1` (next item to pop)

**Why LIST?**
- Simple FIFO ordering (no priority needed after initial stage)
- Efficient blocking pop with `BRPOP` (workers can wait)
- Lower overhead than ZSET

**Example:**
```python
# Tasks pushed in order A, B, C
LPUSH redis:queue:chunk A
LPUSH redis:queue:chunk B
LPUSH redis:queue:chunk C

# Queue state: [C, B, A]

# Workers pop in order:
RPOP → A (FIRST in, FIRST out ✓)
RPOP → B
RPOP → C
```

---

## Migration from PostgreSQL

### Queue Mapping

| PostgreSQL Priority | Redis Queue | Data Structure |
|---------------------|-------------|----------------|
| 8-10 | `redis:queue:store:high` | ZSET |
| 4-7 | `redis:queue:store:medium` | ZSET |
| 1-3 | `redis:queue:store:low` | ZSET |

**Migration Script:** `scripts/migrate-pg-to-redis.py`

**Operations:**
- Reads pending items from `queue.store` table
- Calculates priority score using `(10 - priority) * 1e13 + timestamp_ms`
- Uses `ZADD` to add to sorted sets
- Stores idempotency keys in `redis:idempotency:store` hash

**Verification:**
- Count: `ZCARD` vs `SELECT COUNT(*)`
- Sample: Random items checked for data integrity
- Idempotency: Keys verified in hash

---

## Worker Task Flow

### 1. Claim Task (Initial Stage)

**From ZSET:**
```python
from redis_atomic_operations import RedisAtomicOps

ops = RedisAtomicOps(host='aio-01')

# Claim from priority queue (ZSET)
task = ops.claim_task(
    'redis:queue:store:high',
    worker_id='worker-1',
    queue_mode='zset'  # ZPOPMIN
)
```

**Lua Script Operations:**
- `ZPOPMIN redis:queue:store:high` → Get highest priority task
- `HSET redis:processing:store:high <task_id> <task_json>` → Store full task data
- `HSET redis:processing:store:high:metadata <task_id> <metadata>` → Store worker metadata
- `HSET redis:heartbeat:store:high <task_id> <worker:timestamp>` → Track heartbeat

### 2. Complete Task (Push to Next Stage)

**To LIST:**
```python
# Complete and push to next queue (LIST)
ops.complete_task(
    task_id=task['id'],
    worker_id='worker-1',
    result_json=json.dumps({'chunks': [...]}),
    stage='store:high',
    next_queue='redis:queue:chunk',
    next_queue_mode='list'  # LPUSH
)
```

**Lua Script Operations:**
- Verify worker ownership
- `HDEL redis:processing:store:high <task_id>` → Remove from processing
- `HDEL redis:processing:store:high:metadata <task_id>` → Remove metadata
- `HSET redis:completed:store:high <task_id> <result>` → Store completion record
- `LPUSH redis:queue:chunk <merged_task>` → Push to next queue (LIST)

**To ZSET (if needed for priority):**
```python
ops.complete_task(
    task_id=task['id'],
    worker_id='worker-1',
    result_json=json.dumps({'chunks': [...]}),
    stage='store:high',
    next_queue='redis:queue:priority-chunk',
    next_queue_mode='zset'  # ZADD with score
)
```

**Lua Script Operations:**
- Same as above, but uses `ZADD` instead of `LPUSH`:
- `ZADD redis:queue:priority-chunk <score> <merged_task>`

### 3. Claim Task (Pipeline Stage)

**From LIST:**
```python
# Claim from FIFO queue (LIST)
task = ops.claim_task(
    'redis:queue:chunk',
    worker_id='worker-2',
    queue_mode='list'  # RPOP
)
```

**Lua Script Operations:**
- `RPOP redis:queue:chunk` → Get next task (FIFO)
- `HSET redis:processing:chunk <task_id> <task_json>` → Store full task data
- `HSET redis:processing:chunk:metadata <task_id> <metadata>` → Store worker metadata
- `HSET redis:heartbeat:chunk <task_id> <worker:timestamp>` → Track heartbeat

---

## Supporting Data Structures

### Processing Hashes

**Purpose:** Store in-flight tasks with full data

**Structure:**
- `redis:processing:<stage>` → Hash of task_id → task_json (FULL task data)
- `redis:processing:<stage>:metadata` → Hash of task_id → metadata_json (worker info)

**Metadata Example:**
```json
{
  "worker_id": "worker-1",
  "claimed_at": "1720742400000",
  "heartbeat_expires_at": 1720742700000
}
```

**Operations:**
- `HSET` to store
- `HGET` to retrieve
- `HDEL` to remove
- `HKEYS` to list all task IDs

### Completed Hashes

**Purpose:** Store completion records (24-hour TTL)

**Structure:**
- `redis:completed:<stage>` → Hash of task_id → completion_json

**Example:**
```json
{
  "id": "12345",
  "worker_id": "worker-1",
  "completed_at": "1720742400000",
  "result": "{\"chunks\": [...]}"
}
```

**TTL:** 86400 seconds (24 hours)

### Heartbeat Hashes

**Purpose:** Track worker heartbeats for stuck task recovery

**Structure:**
- `redis:heartbeat:<stage>` → Hash of task_id → "worker_id:timestamp_ms"

**Example:**
- `redis:heartbeat:store:high` → `{"12345": "worker-1:1720742400000"}`

**TTL:** Updated on each heartbeat (default 300 seconds)

### Idempotency Hash

**Purpose:** Prevent duplicate task processing

**Structure:**
- `redis:idempotency:store` → Hash of idempotency_key → task_id

**Example:**
- `redis:idempotency:store` → `{"doc-abc-123": "12345"}`

**Operations:**
- `HSET` on task creation/migration
- `HEXISTS` to check for duplicates
- `HGET` to retrieve task ID

### Dead Letter Queues (LISTS)

**Purpose:** Store failed tasks after max retries

**Structure:**
- `redis:dlq:<stage>` → List of failed task_json

**Operations:**
- `LPUSH` to add failed task
- `LRANGE` to inspect
- `RPOP` to retry manually

**Example:**
```python
# Failed task after 3 retries
failed_task = {
  "id": "12345",
  "retries": 3,
  "last_error": "Processing timeout",
  "dead_letter_at": "1720742400000"
}

LPUSH redis:dlq:store:high <failed_task>
```

---

## Testing

### Test Scripts

**Hybrid Mode Tests:**
- `scripts/test-hybrid-queue-mode.py` - ZSET vs LIST operations
- `scripts/test-complete-hybrid-mode.py` - `complete_task()` with `next_queue_mode`
- `scripts/test-redis-integration.py` - Full workflow test

**Bug Fix Tests:**
- `scripts/test-redis-bug-fixes.py` - Priority inversion, heartbeat, result merging

**Usage:**
```bash
# Test hybrid mode
python3 scripts/test-complete-hybrid-mode.py

# Test bug fixes
python3 scripts/test-redis-bug-fixes.py

# Full integration test
python3 scripts/test-redis-integration.py
```

---

## Common Errors and Fixes

### ERROR: "WRONGTYPE Operation against a key holding the wrong kind of value"

**Cause:** Using LIST operations on ZSET (or vice versa)

**Fix:**
- Initial queues (`redis:queue:store:*`) → Use ZSET operations (`ZADD`, `ZPOPMIN`, `ZCARD`)
- Pipeline queues (`redis:queue:chunk`, etc.) → Use LIST operations (`LPUSH`, `RPOP`, `LLEN`)

**Example:**
```python
# WRONG
redis.rpush('redis:queue:store:high', task_json)  # LIST op on ZSET ✗

# RIGHT
score = (10 - priority) * 1e13 + timestamp_ms
redis.zadd('redis:queue:store:high', {task_json: score})  # ZSET op ✓
```

### ERROR: Priority Inversion (High Priority Tasks Not Processing First)

**Cause:** Score formula was `priority * 1e13 + timestamp_ms` (higher priority = higher score)

**Fix:** Changed to `(10 - priority) * 1e13 + timestamp_ms` (higher priority = LOWER score)

**ZPOPMIN pops LOWEST score first:**
- Priority 10 → score ≈ 0 → pops FIRST ✓
- Priority 1 → score ≈ 9e13 → pops LAST ✓

### ERROR: Heartbeat Not Updating (Tasks Recovered Prematurely)

**Cause:** `update_heartbeat()` only updated `redis:heartbeat:*` hash, not `redis:processing:*:metadata` hash

**Fix:** Lua script now updates BOTH hashes:
- `redis:heartbeat:<stage>` → Worker heartbeat registry
- `redis:processing:<stage>:metadata` → Task metadata with `heartbeat_expires_at`

### ERROR: Result Data Lost Between Stages

**Cause:** `complete_task()` pushed only result to next queue, not merged with original task

**Fix:** Lua script now merges result into original task before pushing:
```lua
-- Merge result into task (preserve original fields)
for key, value in pairs(result) do
    task[key] = value
end

task['previous_worker'] = worker_id
task['previous_stage_completed_at'] = ARGV[4]

LPUSH KEYS[4] cjson.encode(task)  -- Push merged task
```

---

## Performance Characteristics

| Operation | ZSET | LIST |
|-----------|------|------|
| Add | O(log N) | O(1) |
| Pop | O(log N) | O(1) |
| Count | O(1) | O(1) |
| Peek | O(log N) | O(1) |
| Priority Support | ✓ | ✗ |
| Blocking Pop | ✗ | ✓ (`BRPOP`) |

**Recommendation:**
- Use ZSET when priority matters (initial routing)
- Use LIST for simple FIFO (processing pipeline)

---

## Migration Checklist

When migrating to Redis queues:

- [ ] Identify queue type (priority vs FIFO)
- [ ] Use ZSET for priority queues (initial stage)
- [ ] Use LIST for FIFO queues (pipeline stages)
- [ ] Calculate priority score correctly: `(10 - priority) * 1e13 + timestamp_ms`
- [ ] Set `queue_mode='zset'` for `claim_task()` on ZSET queues
- [ ] Set `queue_mode='list'` for `claim_task()` on LIST queues
- [ ] Set `next_queue_mode='list'` for `complete_task()` when pushing to LIST
- [ ] Set `next_queue_mode='zset'` for `complete_task()` when pushing to ZSET
- [ ] Verify with `ZCARD` (ZSET) or `LLEN` (LIST)
- [ ] Test with sample data before full migration

---

## References

**Source Files:**
- `scripts/redis-atomic-operations.py` - Atomic operations with Lua scripts
- `scripts/migrate-pg-to-redis.py` - PostgreSQL to Redis migration
- `scripts/redis-queue-worker.py` - Worker implementation
- `scripts/test-complete-hybrid-mode.py` - Hybrid mode tests

**Documentation:**
- `docs/REDIS_MIGRATION.md` - Migration guide
- `memory/project_2026-07-11_redis_workers_deployed.md` - Deployment notes

---

**Questions? See:**
- Lua scripts in `redis-atomic-operations.py` for implementation details
- Test scripts in `scripts/test-*.py` for usage examples
- Memory files in `memory/` for deployment history
