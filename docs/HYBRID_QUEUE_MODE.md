# HYBRID Queue Mode Documentation

**Date:** 2026-07-11  
**Status:** Implemented and tested  
**Files Modified:** 3

---

## Overview

The HYBRID queue mode allows workers to process tasks from either:
- **ZSET (Sorted Set) queues** - Priority-based processing
- **LIST queues** - FIFO (First-In-First-Out) processing

This flexibility enables different processing strategies for different stages of the pipeline.

---

## Queue Modes

### ZSET Mode (Priority Queues)

**Use for:** Tasks that need priority-based processing

**How it works:**
- Tasks stored in Redis sorted sets with priority scores
- Formula: `score = (10 - priority) * 1e13 + timestamp_ms`
- Lower score = higher priority = processes first
- Within same priority: older tasks process first (FIFO)

**Operations:**
- Enqueue: `ZADD queue_name score task_json`
- Dequeue: `ZPOPMIN queue_name` (pops lowest score first)

**Example:**
```python
# High priority task (priority=10) added at t=1000
score = (10 - 10) * 1e13 + 1000 = 1000  # Lowest score, processes FIRST

# Low priority task (priority=3) added at t=1000
score = (10 - 3) * 1e13 + 1000 = 70000000001000  # Higher score, processes LAST
```

**Best for:**
- Store stage (web scraping) - high-value sources first
- Critical vs non-critical tasks
- SLA-based prioritization

---

### LIST Mode (FIFO Queues)

**Use for:** Tasks that need strict ordering

**How it works:**
- Tasks stored in Redis lists
- Oldest task processes first (FIFO)
- No priority - all tasks equal

**Operations:**
- Enqueue: `LPUSH queue_name task_json`
- Dequeue: `RPOP queue_name` (pops oldest)

**Example:**
```python
# Task A added at t=1000
# Task B added at t=2000
# Task C added at t=3000
# Processing order: A → B → C (strict FIFO)
```

**Best for:**
- Chunk stage (document chunking) - preserve order
- Embed stage (embedding generation) - batch efficiency
- Graph stage (knowledge graph updates) - dependency ordering

---

## Usage

### Single Task Claiming

```python
from redis_atomic_operations import RedisAtomicOps

ops = RedisAtomicOps(host='aio-01', port=6379)

# Priority queue (ZSET)
task = ops.claim_task(
    queue_name='redis:queue:store:high',
    worker_id='worker-1',
    queue_mode='zset'  # Priority-based
)

# FIFO queue (LIST)
task = ops.claim_task(
    queue_name='redis:queue:chunk',
    worker_id='worker-1',
    queue_mode='list'  # FIFO
)
```

### Batch Task Claiming

```python
# Batch claim from priority queue
tasks = ops.batch_claim_tasks(
    queue_name='redis:queue:store:high',
    worker_id='worker-1',
    batch_size=10,
    queue_mode='zset'
)

# Batch claim from FIFO queue
tasks = ops.batch_claim_tasks(
    queue_name='redis:queue:chunk',
    worker_id='worker-1',
    batch_size=10,
    queue_mode='list'
)
```

### Worker Script

```bash
# Priority queue worker (store stage)
python3 redis-worker-with-atomic-ops.py \
    --worker-id worker-1 \
    --stage store \
    --queue-mode zset \
    --batch-size 5

# FIFO queue worker (chunk stage)
python3 redis-worker-with-atomic-ops.py \
    --worker-id worker-2 \
    --stage chunk \
    --queue-mode list \
    --batch-size 10
```

---

## Pipeline Configuration

**Recommended setup:**

| Stage | Queue Mode | Reason |
|-------|------------|--------|
| **store** | zset | Priority-based scraping (high-value sources first) |
| **chunk** | list | FIFO processing (preserve document order) |
| **embed** | list | FIFO batch processing (embedding efficiency) |
| **graph** | list | FIFO updates (dependency ordering) |

---

## Implementation Details

### Lua Scripts

Both queue modes are handled by the same atomic Lua scripts:

```lua
-- HYBRID mode support in claim_task
local queue_mode = ARGV[4] or 'zset'

if queue_mode == 'zset' then
    -- Priority queue
    local result = redis.call('ZPOPMIN', KEYS[1])
    task_json = result[1]
else
    -- FIFO queue
    task_json = redis.call('RPOP', KEYS[1])
end
```

### Python Wrapper

```python
def claim_task(self, queue_name: str, worker_id: str,
               heartbeat_ttl_ms: int = 300000,
               queue_mode: str = 'zset') -> Optional[Dict]:
    """
    Atomically claim a task from the queue.

    Args:
        queue_mode: 'zset' for priority, 'list' for FIFO
    """
    result = self.redis.evalsha(
        self.SCRIPTS['claim_task'],
        3,  # numkeys
        queue_name, processing_set, heartbeat_hash,
        worker_id, str(current_time_ms), str(heartbeat_ttl_ms), queue_mode
    )
    return json.loads(result) if result else None
```

---

## Testing

Run the test suite to verify both modes:

```bash
python3 scripts/test-hybrid-queue-mode.py
```

**Tests:**
1. ✓ ZSET mode: Priority-based processing
2. ✓ LIST mode: FIFO processing
3. ✓ Batch claim (ZSET): Priority order preserved
4. ✓ Batch claim (LIST): FIFO order preserved

**Expected output:**
```
============================================================
HYBRID Queue Mode Test Suite
============================================================
✓ PASS: ZSET Mode (Priority)
✓ PASS: LIST Mode (FIFO)
✓ PASS: Batch Claim ZSET
✓ PASS: Batch Claim LIST

Total: 4/4 tests passed
```

---

## Migration Notes

### From PostgreSQL to Redis

The migration script (`migrate-pg-to-redis.py`) uses ZSET mode by default:

```python
# Priority score calculation
score = (10 - priority) * 1e13 + timestamp_ms

# Push to sorted set
redis.zadd(queue_name, {json.dumps(task): score})
```

### Switching Modes

To switch an existing queue from ZSET to LIST:

```python
import redis
import json

r = redis.Redis(host='aio-01', decode_responses=True)

# Get all tasks from ZSET (sorted by priority)
tasks = r.zrange('redis:queue:store:high', 0, -1)

# Move to LIST (preserving priority order)
for task_json in tasks:
    r.lpush('redis:queue:store:fifo', task_json)

# Remove old ZSET
r.delete('redis:queue:store:high')
```

---

## Performance Characteristics

### ZSET Mode (Priority)

**Pros:**
- ✅ Priority-based processing
- ✅ Dynamic re-prioritization possible
- ✅ SLA-aware task scheduling

**Cons:**
- ❌ Slightly higher memory (scores stored)
- ❌ Marginally slower (O(log N) ZADD vs O(1) LPUSH)

### LIST Mode (FIFO)

**Pros:**
- ✅ Fastest enqueue/dequeue (O(1))
- ✅ Lowest memory overhead
- ✅ Strict ordering guarantees

**Cons:**
- ❌ No priority support
- ❌ No re-ordering without re-queuing

---

## Troubleshooting

### Queue appears stuck

**Check queue mode:**
```python
r = redis.Redis(host='aio-01', decode_responses=True)

# Check if queue is ZSET or LIST
queue_type = r.type('redis:queue:store:high')
print(f"Queue type: {queue_type}")  # 'zset' or 'list'
```

### Worker claiming from wrong mode

**Error:**
```
WRONGTYPE Operation against a key holding the wrong kind of value
```

**Fix:**
```bash
# Check worker's queue_mode parameter
python3 redis-worker-with-atomic-ops.py \
    --worker-id worker-1 \
    --stage store \
    --queue-mode zset  # Must match queue type!
```

### Mixed ZSET and LIST queues

**If you have both:**
```python
# Priority queues (ZSET)
redis:queue:store:high    # zset
redis:queue:store:medium  # zset
redis:queue:store:low     # zset

# Processing queues (LIST)
redis:queue:chunk         # list
redis:queue:embed         # list
redis:queue:graph         # list
```

**Workers must use correct mode:**
```bash
# Store workers use zset
--queue-mode zset

# Processing workers use list
--queue-mode list
```

---

## Files Modified

1. **scripts/redis-atomic-operations.py**
   - Added `queue_mode` parameter to `claim_task()`
   - Added `queue_mode` parameter to `batch_claim_tasks()`
   - Updated embedded Lua scripts with HYBRID support

2. **scripts/redis-worker-with-atomic-ops.py**
   - Added `queue_mode` parameter to `RedisWorker.__init__()`
   - Added `--queue-mode` command-line argument
   - Updated `claim_tasks()` to pass queue_mode to operations

3. **scripts/test-hybrid-queue-mode.py**
   - New test suite for HYBRID queue mode
   - 4 tests covering both modes and batch operations

---

## Related Documentation

- [Redis Migration Fixes Summary](REDIS_MIGRATION_FIXES_SUMMARY.md) - Bug fixes that enabled HYBRID mode
- [PostgreSQL to Redis Migration Strategy](POSTGRESQL_TO_REDIS_MIGRATION_STRATEGY.md) - Migration from PostgreSQL
- [Redis Bug Fixes Complete](REDIS_BUG_FIXES_COMPLETE.md) - All 5 bugs fixed

---

## Future Enhancements

### Potential improvements:

1. **Auto-detection:** Worker detects queue type automatically
2. **Mixed-mode queues:** Support both priority and FIFO in same pipeline
3. **Dynamic switching:** Change queue mode without migration
4. **Priority ranges:** Fine-grained priority levels (0-100)

---

**Status:** ✓ Implemented, tested, and documented  
**Test Results:** 4/4 tests passed  
**Ready for:** Production deployment
