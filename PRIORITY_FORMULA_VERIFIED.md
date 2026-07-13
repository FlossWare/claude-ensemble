# Priority Formula Verification - PASSED ✅

**Date:** 2026-07-11  
**Status:** All tests passed  
**Formula:** `score = (10 - priority) * 1e13 + timestamp_ms`

---

## Summary

The priority formula in `redis-atomic-operations.py` is **correct** and working as designed.

**Key findings:**
- ✅ ZPOPMIN pops **lowest score first** = **highest priority first**
- ✅ Formula inverts priority correctly: `priority 10 → score ~0`, `priority 1 → score ~9e13`
- ✅ FIFO ordering preserved within same priority level (timestamp tiebreaker)
- ✅ Live Redis tests confirm expected behavior

---

## How It Works

### Formula Design

```python
score = (10 - priority) * 1e13 + timestamp_ms
```

**Priority levels (1-10, where 10 = highest):**
- Priority 10 (Urgent) → score = 0 * 1e13 + timestamp ≈ 1.78e12
- Priority 8 (High) → score = 2 * 1e13 + timestamp ≈ 2.18e13
- Priority 5 (Medium) → score = 5 * 1e13 + timestamp ≈ 5.18e13
- Priority 3 (Low) → score = 7 * 1e13 + timestamp ≈ 7.18e13
- Priority 1 (Lowest) → score = 9 * 1e13 + timestamp ≈ 9.18e13

### ZPOPMIN Behavior

Redis `ZPOPMIN` command:
- Pops the member with the **lowest score** from the sorted set
- This means **highest priority tasks** (lowest scores) are popped first

### FIFO Within Priority

The `+ timestamp_ms` component ensures:
- Tasks with the **same priority** are ordered by timestamp
- Older tasks (lower timestamp) → lower score → popped first
- This creates **FIFO ordering within each priority level**

---

## Test Results

### Test 1: Formula Calculation ✅

**Pop order (ZPOPMIN - lowest score first):**
1. Urgent - Old (Priority 10, Score 1.78e12)
2. Urgent - New (Priority 10, Score 1.78e12)
3. High - Old (Priority 8, Score 2.18e13)
4. High - New (Priority 8, Score 2.18e13)
5. Medium - Old (Priority 5, Score 5.18e13)
6. Medium - New (Priority 5, Score 5.18e13)
7. Low - Old (Priority 3, Score 7.18e13)
8. Low - New (Priority 3, Score 7.18e13)
9. Lowest - Old (Priority 1, Score 9.18e13)
10. Lowest - New (Priority 1, Score 9.18e13)

**Result:** Tasks ordered correctly (high priority → low, FIFO within priority)

### Test 2: Live Redis ZPOPMIN ✅

Added 5 tasks to Redis sorted set with priorities: 10, 8, 5, 3, 1

**ZPOPMIN pop order:**
1. Urgent (Priority 10)
2. High (Priority 8)
3. Medium (Priority 5)
4. Low (Priority 3)
5. Lowest (Priority 1)

**Result:** ZPOPMIN popped tasks in correct priority order

### Test 3: FIFO Within Priority ✅

Added 5 tasks with **same priority (5)** but different timestamps (1 second apart)

**ZPOPMIN pop order:**
1. Task 0 (oldest)
2. Task 1
3. Task 2
4. Task 3
5. Task 4 (newest)

**Result:** Tasks with same priority popped in FIFO order (oldest first)

---

## Code Locations

### Python Implementation

**File:** `scripts/redis-atomic-operations.py`

**Locations where formula is used:**

1. **LUA_COMPLETE_TASK** (Line 139):
   ```lua
   local priority = tonumber(task['priority']) or 5
   local timestamp_ms = tonumber(ARGV[4])
   local score = (10 - priority) * 1e13 + timestamp_ms
   redis.call('ZADD', KEYS[4], score, merged_task_json)
   ```

2. **LUA_FAIL_TASK** (Line 190):
   ```lua
   local priority = tonumber(task['priority']) or 5
   local timestamp_ms = tonumber(ARGV[4])
   local score = (10 - priority) * 1e13 + timestamp_ms
   redis.call('ZADD', KEYS[2], score, cjson.encode(task))
   ```

3. **LUA_RECOVER_STUCK** (Line 329):
   ```lua
   local priority = tonumber(task['priority']) or 5
   local score = (10 - priority) * 1e13 + current_time
   redis.call('ZADD', KEYS[2], score, cjson.encode(task))
   ```

---

## Verification Script

**File:** `test-priority-formula.py`

Run comprehensive tests:
```bash
python3 test-priority-formula.py
```

Tests performed:
1. Formula calculation (mathematical verification)
2. Live Redis ZPOPMIN (real Redis sorted set operations)
3. FIFO within priority (timestamp tiebreaker verification)

---

## Conclusion

**NO CHANGES NEEDED** - The priority formula is correct and working as designed.

The formula successfully:
- ✅ Inverts priority (high priority = low score)
- ✅ Ensures ZPOPMIN pops highest priority tasks first
- ✅ Maintains FIFO ordering within same priority level
- ✅ Passes all comprehensive tests (formula calculation, live Redis, FIFO)

**Recommendation:** Mark this issue as resolved. The system is operating correctly.

---

## References

- Redis `ZPOPMIN` documentation: https://redis.io/commands/zpopmin/
- Redis sorted sets: https://redis.io/docs/data-types/sorted-sets/
- Atomic operations: `scripts/redis-atomic-operations.py`
- Verification script: `test-priority-formula.py`
