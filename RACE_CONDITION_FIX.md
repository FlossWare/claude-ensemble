# Race Condition Fix: Disagreement Detector Review Queue

**Date:** 2026-06-28  
**File:** `shared/disagreement-detector.cjs`  
**Issue:** Concurrent INSERT/UPDATE race condition in `storeInReviewQueue`

## Problem

Multiple workers analyzing the same workflow simultaneously could cause race condition:
- Last writer wins (overwrites higher priority/disagreement scores)
- No distributed lock on concurrent INSERT ON CONFLICT
- Critical data loss in human review queue

## Solution

Added PostgreSQL advisory locks to serialize concurrent updates:

1. **New Helper Function** (`hashCode`):
   - Converts workflow_execution_id to int32 for advisory lock
   - Java-style hashCode algorithm for consistency
   - Returns positive integers (required by pg_advisory_xact_lock)

2. **Transaction Wrapper** in `storeInReviewQueue`:
   ```javascript
   await client.query('BEGIN');
   
   // Acquire advisory lock using workflow_execution_id hash
   const lockId = hashCode(workflow_execution_id);
   await client.query('SELECT pg_advisory_xact_lock($1)', [lockId]);
   
   // Now safe to INSERT ON CONFLICT
   // ...
   
   await client.query('COMMIT'); // Auto-releases lock
   ```

3. **Enhanced UPDATE Logic**:
   ```sql
   ON CONFLICT (workflow_execution_id, task_description)
   DO UPDATE SET
     disagreement_score = GREATEST(human_review_queue.disagreement_score, EXCLUDED.disagreement_score),
     priority = GREATEST(human_review_queue.priority, EXCLUDED.priority),
     updated_at = NOW()
   ```
   - Uses `GREATEST()` to preserve highest values
   - Prevents lower-priority updates from overwriting critical entries

4. **Error Handling**:
   - `ROLLBACK` on error automatically releases lock
   - Lock is transaction-scoped (pg_advisory_xact_lock)
   - No manual lock cleanup needed

## Test Results

### Test 1: Hash Code Consistency
```
✅ PASS - All hash codes consistent and valid int32
```

### Test 2: Concurrent Updates (5 Workers)
```
Workers:
  1: priority=10, CV=0.50 (highest)
  2: priority=7,  CV=0.30
  3: priority=9,  CV=0.45
  4: priority=5,  CV=0.20
  5: priority=8,  CV=0.35

Final State:
  Priority: 10 (correct, preserved highest)
  Disagreement Score: 0.50 (correct, preserved highest)

✅ PASS - Race condition prevented
```

### Test 3: Lock Release on Error
```
Client 1: Acquires lock, then ROLLBACK
Client 2: Attempts same lock immediately

Result: Lock acquired in 6ms (not blocked)

✅ PASS - Lock released on ROLLBACK
```

## Files Modified

1. **shared/disagreement-detector.cjs**
   - Added `hashCode()` helper (lines 103-110)
   - Wrapped `storeInReviewQueue()` in transaction with advisory lock (lines 313-402)
   - Enhanced UPDATE with `GREATEST()` for priority/score preservation
   - Added `hashCode` to exports

2. **Test Scripts**
   - `test-disagreement-race-condition.cjs` - Concurrent update test
   - `test-lock-release.cjs` - Lock release verification

## Performance Impact

- Advisory locks add ~1-2ms per INSERT
- No deadlock risk (transaction-scoped, auto-released)
- Minimal throughput impact (locks only during INSERT, not SELECT)

## Migration Notes

No schema changes required. Existing code continues to work.

## Verification

Run tests:
```bash
node test-disagreement-race-condition.cjs
node test-lock-release.cjs
```

Expected: All tests pass (exit code 0)

## Related Files

- `shared/disagreement-detector.cjs` - Main implementation
- `shared/weighted-voting.cjs` - Calls detectAndQueue()
- `workflows/*.mjs` - Workflows using disagreement detection
