# Redis HYBRID Architecture

**Last Updated:** 2026-07-11  
**Status:** Production  
**Related Files:**
- `scripts/migrate-pg-to-redis.py` - Migration to initial queues
- `scripts/redis-atomic-operations.py` - Atomic queue operations
- `scripts/redis-worker-with-atomic-ops.py` - Worker implementation

---

## Overview

The Redis queue system uses a **HYBRID architecture** combining two data structures for optimal performance:

1. **Sorted Sets (ZADD/ZPOPMIN)** - For priority-based initial queues
2. **Lists (LPUSH/RPOP)** - For FIFO processing pipeline queues

This design balances priority handling with processing efficiency.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: INITIAL QUEUES (Sorted Sets - Priority + FIFO)        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  redis:queue:store:high     (ZSET) ─┐                         │
│  redis:queue:store:medium   (ZSET) ─┼─→ ZPOPMIN (atomic)      │
│  redis:queue:store:low      (ZSET) ─┘                         │
│                                                                 │
│  - Structure: Sorted set with scores                           │
│  - Score formula: (10 - priority) * 1e13 + timestamp_ms       │
│  - Pop method: ZPOPMIN (lowest score first)                    │
│  - Priority: High priority = LOW score = pops FIRST            │
│  - FIFO: Within same priority, older timestamp = lower score   │
│                                                                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
                  Worker
                  claims &
                  processes
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2+: PROCESSING PIPELINE (Lists - Simple FIFO)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  redis:queue:chunk    (LIST) ─┐                               │
│  redis:queue:embed    (LIST) ─┼─→ RPOP/BLPOP (atomic)        │
│  redis:queue:index    (LIST) ─┘                               │
│                                                                 │
│  - Structure: Simple list (no scores)                          │
│  - Push method: LPUSH (left/head)                             │
│  - Pop method: RPOP/BLPOP (right/tail - FIFO)                │
│  - No priority: All items equal priority                       │
│  - Simpler: O(1) operations, no score calculations            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why HYBRID?

### Why Sorted Sets for Initial Queues?

**Problem:** Tasks arrive with different priorities (1-10). High-priority tasks must be processed first.

**Solution:** Sorted sets with score-based ordering.

**Benefits:**
- **Priority handling:** Score formula ensures high priority → low score → pops first
- **FIFO within priority:** Timestamp in score ensures FIFO ordering for same priority
- **Atomic operations:** ZPOPMIN is atomic (no race conditions)
- **Flexible:** Can adjust priority formula without data migration

**Drawbacks:**
- **Complexity:** Score calculation required
- **Memory:** Slightly more memory than lists (stores scores)

### Why Lists for Processing Pipeline?

**Problem:** After initial stage, all tasks have equal priority. Sorted sets are overkill.

**Solution:** Simple lists with LPUSH/RPOP.

**Benefits:**
- **Simplicity:** No score calculations needed
- **Performance:** O(1) push/pop operations
- **Memory:** More memory-efficient than sorted sets
- **Blocking:** BLPOP allows workers to wait for tasks (no polling)

**Drawbacks:**
- **No priority:** All items treated equally (acceptable for processing stages)

---

## Data Structures

### Sorted Set (Initial Queues)

**Structure:**
```redis
redis:queue:store:high (ZSET)
  Member: {"id": 123, "data": {...}, "priority": 10, ...}
  Score: 1000  # (10 - 10) * 1e13 + 1000 = 1000
```

**Operations:**
```python
# Add task (migration)
score = (10 - priority) * 1e13 + timestamp_ms
redis.zadd('redis:queue:store:high', {json.dumps(task): score})

# Claim task (worker)
result = redis.zpopmin('redis:queue:store:high', 1)  # Atomic pop
task_json, score = result[0]
task = json.loads(task_json)
```

**Score Formula:**
```python
score = (10 - priority) * 1e13 + timestamp_ms

# Examples:
# Priority 10 @ t=1000: (10-10)*1e13 + 1000 = 1000        (pops FIRST)
# Priority 10 @ t=2000: (10-10)*1e13 + 2000 = 2000        (pops SECOND - FIFO ✓)
# Priority 5  @ t=1000: (10-5)*1e13 + 1000  = 5e13 + 1000 (pops AFTER priority 10)
# Priority 1  @ t=1000: (10-1)*1e13 + 1000  = 9e13 + 1000 (pops LAST)
```

**Why invert priority?**
- ZPOPMIN pops **LOWEST** score first
- High priority (10) should pop **BEFORE** low priority (1)
- Therefore: high priority → **LOW** score
- Inversion: `(10 - priority)` converts priority 10 → score 0, priority 1 → score 9

### List (Processing Pipeline)

**Structure:**
```redis
redis:queue:chunk (LIST)
  [0]: {"id": 123, "chunks": [...], ...}  # Newest (LPUSH)
  [1]: {"id": 122, "chunks": [...], ...}
  ...
  [-1]: {"id": 100, "chunks": [...], ...} # Oldest (RPOP pops this)
```

**Operations:**
```python
# Push task (complete_task in redis-atomic-operations.py)
redis.lpush('redis:queue:chunk', json.dumps(task))

# Pop task (worker)
task_json = redis.rpop('redis:queue:chunk')  # FIFO
# OR blocking:
task_json = redis.brpop('redis:queue:chunk', timeout=5)  # Wait 5s
task = json.loads(task_json)
```

**FIFO Ordering:**
- LPUSH: Add to **left** (head) of list
- RPOP: Pop from **right** (tail) of list
- Result: Oldest item (tail) pops first (FIFO)

---

## Migration Flow

### PostgreSQL → Redis Migration

**Input:** 3,026 pending items in `queue.store` (PostgreSQL)

**Output:** 3 sorted sets in Redis:
- `redis:queue:store:high` (priority 8-10)
- `redis:queue:store:medium` (priority 4-7)
- `redis:queue:store:low` (priority 1-3)

**Process:**

1. **Read from PostgreSQL:**
   ```sql
   SELECT id, data, priority, created_at, ...
   FROM queue.store
   WHERE status = 'pending'
   ORDER BY priority DESC, created_at ASC
   ```

2. **Determine queue:**
   ```python
   if priority >= 8:
       queue = 'redis:queue:store:high'
   elif priority >= 4:
       queue = 'redis:queue:store:medium'
   else:
       queue = 'redis:queue:store:low'
   ```

3. **Calculate score:**
   ```python
   timestamp_ms = int(created_at.timestamp() * 1000)
   score = (10 - priority) * 1e13 + timestamp_ms
   ```

4. **Push to Redis (ZADD):**
   ```python
   pipeline.zadd(queue, {json.dumps(item): score})
   pipeline.execute()
   ```

5. **Mark migrated in PostgreSQL:**
   ```sql
   UPDATE queue.store
   SET status = 'migrated', migrated_at = NOW()
   WHERE status = 'pending'
   ```

### Worker Processing Flow

**Stage 1: Claim from sorted set (ZPOPMIN)**

```python
# Atomic claim from sorted set
result = redis.zpopmin('redis:queue:store:high', 1)
task_json, score = result[0]
task = json.loads(task_json)

# Store in processing hash
redis.hset('redis:processing:store', task['id'], task_json)
```

**Stage 2: Process & complete**

```python
# Process task
result = process_store_stage(task)

# Complete atomically (removes from processing, pushes to next queue)
ops.complete_task(
    task_id=task['id'],
    worker_id='worker-1',
    result=json.dumps(result),
    next_queue='redis:queue:chunk'  # ← LIST queue (LPUSH)
)
```

**Stage 3: Next worker claims from list (RPOP)**

```python
# Claim from list (FIFO)
task_json = redis.rpop('redis:queue:chunk')
task = json.loads(task_json)

# Process chunks
chunks = process_chunk_stage(task)

# Push to next stage
ops.complete_task(
    task_id=task['id'],
    worker_id='worker-2',
    result=json.dumps(chunks),
    next_queue='redis:queue:embed'  # ← Another LIST queue
)
```

---

## Atomic Operations

All claim/complete/fail operations use **Lua scripts** for atomicity (no race conditions).

### Claim Task (Sorted Set)

```lua
-- redis-atomic-operations.py: LUA_CLAIM_TASK
local result = redis.call('ZPOPMIN', KEYS[1])  -- Atomic pop
if not result or #result == 0 then
    return nil
end

local task_json = result[1]
local task_id = cjson.decode(task_json)['id']

-- Store in processing hash
redis.call('HSET', KEYS[2], task_id, task_json)

-- Store metadata
redis.call('HSET', KEYS[2] .. ':metadata', task_id, metadata_json)

return task_json
```

**Atomicity:** ZPOPMIN + HSET in single Lua script = no race condition.

### Complete Task (Push to List)

```lua
-- redis-atomic-operations.py: LUA_COMPLETE_TASK (line 104-118)
-- Remove from processing
redis.call('HDEL', KEYS[1], task_id)

-- Merge result into task
local task = cjson.decode(task_json)
local result = cjson.decode(ARGV[3])
for key, value in pairs(result) do
    task[key] = value
end

-- Push to next queue (LIST with LPUSH)
if KEYS[4] and KEYS[4] ~= '' then
    redis.call('LPUSH', KEYS[4], cjson.encode(task))  -- ← LPUSH!
end

return 'OK'
```

**Atomicity:** HDEL + LPUSH in single Lua script = no race condition.

### Fail Task (Requeue to Sorted Set)

```lua
-- redis-atomic-operations.py: LUA_FAIL_TASK (line 159-170)
local task = cjson.decode(task_json)
local retries = tonumber(task['retries']) or 0

task['retries'] = retries + 1

if task['retries'] <= max_retries then
    -- Requeue to sorted set with new score
    local priority = tonumber(task['priority']) or 5
    local timestamp_ms = tonumber(ARGV[4])
    local score = (10 - priority) * 1e13 + timestamp_ms  -- Same formula
    redis.call('ZADD', KEYS[2], score, cjson.encode(task))  -- ← ZADD!
    return 'REQUEUED'
else
    -- Dead letter queue (list)
    redis.call('LPUSH', KEYS[3], cjson.encode(task))
    return 'DEAD_LETTER'
end
```

**Atomicity:** HDEL + ZADD/LPUSH in single Lua script = no race condition.

---

## Queue Naming Convention

### Sorted Sets (Initial Stage)
- `redis:queue:store:high` - Priority 8-10
- `redis:queue:store:medium` - Priority 4-7
- `redis:queue:store:low` - Priority 1-3

### Lists (Processing Pipeline)
- `redis:queue:chunk` - Chunking stage
- `redis:queue:embed` - Embedding stage
- `redis:queue:index` - Indexing stage

### Supporting Hashes
- `redis:processing:{stage}` - Tasks currently being processed (hash: task_id → task_json)
- `redis:processing:{stage}:metadata` - Processing metadata (hash: task_id → metadata_json)
- `redis:completed:{stage}` - Completed tasks (hash: task_id → result_json)
- `redis:heartbeat:{stage}` - Worker heartbeats (hash: task_id → worker_id:timestamp)
- `redis:idempotency:{stage}` - Idempotency keys (hash: idempotency_key → task_id)

---

## Performance Characteristics

| Operation | Sorted Set (ZADD/ZPOPMIN) | List (LPUSH/RPOP) |
|-----------|---------------------------|-------------------|
| Add item | O(log N) | O(1) |
| Pop item | O(log N) | O(1) |
| Get count | O(1) - ZCARD | O(1) - LLEN |
| Memory | ~40 bytes per item + score | ~30 bytes per item |
| Priority support | ✅ Yes | ❌ No |
| FIFO guarantee | ✅ Yes (within priority) | ✅ Yes |
| Atomic operations | ✅ ZPOPMIN | ✅ RPOP |
| Blocking pop | ❌ No | ✅ BLPOP |

**When to use Sorted Sets:**
- Need priority-based ordering
- Tasks have varying importance
- Initial stage where priority matters

**When to use Lists:**
- All items have equal priority
- Simple FIFO processing
- Want blocking pops (BLPOP)
- Processing pipeline stages

---

## Testing

### Test Migration Script

```bash
# Dry run (preview only)
python3 scripts/migrate-pg-to-redis.py --dry-run

# Execute migration
python3 scripts/migrate-pg-to-redis.py

# Verify migration
python3 scripts/migrate-pg-to-redis.py --verify
```

### Test Atomic Operations

```bash
# Run verification tests
python3 scripts/verify-redis-migration-fixes.py

# Expected output:
# ✅ PASS - Priority Score Formula
# ✅ PASS - Atomic Operations
# ✅ PASS - Stuck Task Recovery
```

### Test Worker Processing

```bash
# Start worker (processes sorted set → list pipeline)
python3 scripts/redis-worker-with-atomic-ops.py \
  --stage store \
  --next-queue redis:queue:chunk \
  --worker-id worker-1
```

---

## Troubleshooting

### Tasks stuck in sorted set

**Symptom:** `ZCARD redis:queue:store:high` shows items but workers not claiming.

**Debug:**
```bash
# Check sorted set contents
redis-cli ZRANGE redis:queue:store:high 0 10 WITHSCORES

# Check if scores are correct (high priority = low score)
# Priority 10 should have score ≈ timestamp (small)
# Priority 1 should have score ≈ 9e13 + timestamp (large)
```

**Fix:** Verify score calculation in migration script (line 191-192).

### Tasks not appearing in next queue

**Symptom:** Worker completes task but next queue empty.

**Debug:**
```bash
# Check if complete_task is called with next_queue
# Check Lua script LUA_COMPLETE_TASK (line 117)

# Verify next queue is a list
redis-cli TYPE redis:queue:chunk
# Should output: list (not zset)
```

**Fix:** Ensure `complete_task` called with correct `next_queue` parameter.

### Priority inversion (low priority tasks processed first)

**Symptom:** Priority 1 tasks processed before priority 10 tasks.

**Debug:**
```bash
# Check score formula
# Should be: (10 - priority) * 1e13 + timestamp_ms
# NOT: priority * 1e13 + timestamp_ms (old bug)
```

**Fix:** Update score formula in `migrate-pg-to-redis.py` line 191.

---

## Related Documentation

- `scripts/migrate-pg-to-redis.py` - Migration implementation
- `scripts/redis-atomic-operations.py` - Atomic Lua scripts
- `scripts/verify-redis-migration-fixes.py` - Testing & verification
- `docs/API_BLUEPRINT_REFERENCE.md` - REST API for queue operations

---

## Change Log

**2026-07-11:** Initial HYBRID architecture documentation  
**2026-07-10:** Migration script fixed (priority inversion bug)  
**2026-07-09:** Atomic operations implemented with Lua scripts
