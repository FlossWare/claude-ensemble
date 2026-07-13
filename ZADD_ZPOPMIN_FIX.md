# ZADD/ZPOPMIN Fix Summary

**Date:** 2026-07-11  
**Issue:** ZADD/BRPOP mismatch - Migration uses ZADD (sorted sets), worker uses BRPOP (lists)  
**Status:** ✅ FIXED and TESTED

---

## Problem

The migration script (`migrate-pg-to-redis.py`) uses `ZADD` to add items to Redis **sorted sets**:

```python
pipeline.zadd(queue_name, {json.dumps(item): score})
```

But the old worker (`redis-queue-worker.py`) uses `BRPOP` to claim items from **lists**:

```python
result = self.redis_client.brpop(QUEUES, timeout=REDIS_TIMEOUT)
```

**This is incompatible!** BRPOP cannot read from sorted sets.

---

## Solution

Changed the worker from `BRPOP` (lists) to `ZPOPMIN` (sorted sets):

### Before (WRONG):

```python
# BRPOP from queues (blocking, priority order)
result = self.redis_client.brpop(QUEUES, timeout=REDIS_TIMEOUT)

if result:
    queue, item_json = result
    # ...
```

### After (CORRECT):

```python
# ZPOPMIN from queues (priority order - lowest score first)
result = None
queue_name = None

# Try each queue in priority order
for queue in QUEUES:
    # ZPOPMIN returns [(member, score)] or []
    popped = self.redis_client.zpopmin(queue, 1)
    if popped:
        # popped = [(item_json, score)]
        item_json, score = popped[0]
        result = (queue, item_json)
        queue_name = queue
        logger.debug(f"Popped from {queue} with score {score}")
        break

if result:
    queue, item_json = result
    # ...
```

---

## Files Changed

1. **scripts/redis-queue-worker.py**
   - Changed from `BRPOP` to `ZPOPMIN`
   - Updated comments and logging
   - Changed `REDIS_TIMEOUT` to `POLL_INTERVAL` (ZPOPMIN is non-blocking)

---

## Tests Created

1. **tests/test_zadd_zpopmin_fix.py** - Comprehensive test suite:
   - Test 1: ZADD/ZPOPMIN consistency (7 items, 3 priority levels)
   - Test 2: Priority inversion bug fix (10 priorities)
   - Test 3: FIFO within same priority (5 items)

2. **tests/test_worker_zpopmin.py** - Worker integration test:
   - Simulates real worker behavior
   - Verifies processing order across 4 queues

---

## Test Results

### Test 1: ZADD/ZPOPMIN Consistency

```
✓ Counts correct (3 high, 2 medium, 2 low)
✓ Processing order: high → medium → low
✓ FIFO within each priority level
```

### Test 2: Priority Inversion Bug Fix

```
✓ Priorities processed correctly: [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
✓ High priority (10) pops first (lowest score)
✓ Low priority (1) pops last (highest score)
```

### Test 3: FIFO Within Priority

```
✓ Tasks processed in order: [0, 1, 2, 3, 4]
✓ Oldest timestamp pops first
✓ Newest timestamp pops last
```

### Test 4: Worker Integration

```
✓ Worker processes queues in priority order
✓ High priority queue processed first
✓ Medium priority queue processed second
✓ Low priority queue processed last
```

---

## How It Works

### Migration (ZADD)

1. Calculate priority score:
   ```python
   score = (10 - priority) * 1e13 + timestamp_ms
   ```

2. Add to sorted set:
   ```python
   r.zadd(queue_name, {json.dumps(item): score})
   ```

3. Result: Items stored in sorted set, ordered by score

### Worker (ZPOPMIN)

1. Pop lowest score from sorted set:
   ```python
   popped = r.zpopmin(queue, 1)  # Returns [(item_json, score)]
   ```

2. Process item:
   ```python
   item_json, score = popped[0]
   item = json.loads(item_json)
   ```

3. Result: Items processed in priority order (high → low), FIFO within priority

---

## Priority Scoring Formula

**Formula:** `score = (10 - priority) * 1e13 + timestamp_ms`

**Why this works:**

- **High priority (10):** score = 0 × 1e13 + timestamp = **~1e12** (LOWEST score)
- **Low priority (1):** score = 9 × 1e13 + timestamp = **~9e13** (HIGHEST score)
- **ZPOPMIN pops LOWEST score first** → high priority processes first

**FIFO within priority:**

- Same priority → same base score (10 - priority) × 1e13
- Older timestamp → lower total score → pops first
- Example (priority 10):
  - Task A @ t=1000 → score = 0 + 1000 = **1000** (pops FIRST)
  - Task B @ t=2000 → score = 0 + 2000 = **2000** (pops SECOND)

---

## Verified Behavior

1. ✅ Migration uses ZADD (sorted sets)
2. ✅ Worker uses ZPOPMIN (sorted sets)
3. ✅ Priority ordering: high (10) → medium (5) → low (1)
4. ✅ FIFO within priority: oldest → newest
5. ✅ No data loss or corruption
6. ✅ Score calculation correct

---

## Next Steps

1. Deploy updated worker to production
2. Verify with real data migration
3. Monitor queue processing in production
4. Update documentation

---

## Alternative Approach (Not Used)

**Option B:** Change migration to use LPUSH (lists) instead of ZADD (sorted sets)

**Why rejected:**

- Loses priority ordering within queues
- Requires separate queues for each priority level
- Less efficient (requires multiple BRPOP calls)
- Current approach (ZADD + ZPOPMIN) is superior

---

## References

- **Migration script:** `scripts/migrate-pg-to-redis.py`
- **Worker (old):** `scripts/redis-queue-worker.py`
- **Worker (new, atomic):** `scripts/redis-worker-with-atomic-ops.py`
- **Atomic operations:** `scripts/redis-atomic-operations.py`
- **Tests:** `tests/test_zadd_zpopmin_fix.py`, `tests/test_worker_zpopmin.py`

---

**Conclusion:** ZADD/ZPOPMIN mismatch is FIXED. Worker now correctly reads from sorted sets using ZPOPMIN, matching the migration script's ZADD operations.
