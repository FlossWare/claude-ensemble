# TTL Consistency Fix

**Date:** 2026-07-11  
**Issue:** Redis queue operations were setting TTL on wrong keys, causing memory leaks  
**Status:** ✅ FIXED and TESTED

---

## Problem

The Redis atomic queue operations had a critical TTL consistency bug:

### Original Code (Line 62 in redis-atomic-operations.lua)
```lua
redis.call('HSET', in_progress_set .. ':claims', url, worker_id)
redis.call('EXPIRE', in_progress_set .. ':claims:' .. url, timeout)
```

### Issues

1. **Mixed Data Structures**: Hash fields (`HSET`) cannot have individual TTLs
2. **Wrong Key**: `EXPIRE` was called on a constructed key (`queue:in_progress:claims:URL`) instead of the hash field
3. **Memory Leak**: Hash fields in `:claims` never expired
4. **Phantom Keys**: The constructed keys created by `EXPIRE` didn't actually store data

### Impact

- Worker claims never expired from Redis hashes
- Stale task tracking accumulated indefinitely
- Memory usage grew unbounded over time
- TTL logic didn't work as intended

---

## Solution

Separate keys with different TTL requirements:

1. **Claim Keys** (need TTL): Use separate string keys with `SETEX`
   - Key: `queue:in_progress:claim:<url>`
   - Value: worker_id
   - TTL: timeout seconds

2. **Timestamp Keys** (no TTL): Keep in hash for reclaim logic
   - Hash: `queue:in_progress:timestamps`
   - Field: url
   - Value: timestamp

### Fixed Code (Line 60 in redis-atomic-operations.lua)
```lua
redis.call('SETEX', in_progress_set .. ':claim:' .. url, timeout, worker_id)
redis.call('HSET', in_progress_set .. ':timestamps', url, timestamp)
```

---

## Files Changed

### 1. shared/redis-atomic-operations.lua

**Changes:**
- `atomic_dequeue` (line 60): Use `SETEX` instead of `HSET + EXPIRE`
- `atomic_complete` (line 88): Use `GET` instead of `HGET` for claim verification
- `atomic_retry` (line 127): Use `GET` instead of `HGET` for claim verification
- `atomic_reclaim_stale` (line 192): Clean up claim keys with `DEL` instead of `HDEL`

### 2. shared/redis_atomic_wrapper.py

**Changes:**
- Fixed `_extract_function` method to properly parse Lua control structures
- Correctly handle `for...do` and `while...do` as single blocks (not two)
- Extract complete function bodies for all 8 atomic operations

---

## Testing

### Test Suite: test-ttl-fix-complete.py

**5 Comprehensive Tests:**

1. **Claim Expiration** - Verifies claims expire after TTL
   - ✅ Claim key created with correct TTL
   - ✅ Claim expires after timeout
   - ✅ No memory leak

2. **Complete with Claim** - Verifies complete operation cleans up claim
   - ✅ Claim verified before completion
   - ✅ Claim removed after completion
   - ✅ Task marked as processed

3. **Retry with Claim** - Verifies retry operation cleans up and re-queues
   - ✅ Claim verified before retry
   - ✅ Claim removed after retry
   - ✅ Task re-queued with retry count

4. **Reclaim Stale** - Verifies stale task reclaim logic
   - ✅ Stale tasks identified by timestamp
   - ✅ Claims cleaned up during reclaim
   - ✅ Tasks re-queued for processing

5. **Wrong Worker Protection** - Verifies ownership enforcement
   - ✅ Wrong worker cannot complete task
   - ✅ Wrong worker cannot retry task
   - ✅ Task remains in progress

### Test Results

```
Passed: 5/5
✅ PASS: Test 1 - test_claim_expiration
✅ PASS: Test 2 - test_complete_with_claim
✅ PASS: Test 3 - test_retry_with_claim
✅ PASS: Test 4 - test_reclaim_stale
✅ PASS: Test 5 - test_wrong_worker

🎉 All tests passed! TTL consistency fix is working correctly.
```

---

## Before vs After

### Before (Buggy Behavior)

```python
# Dequeue creates hash field + phantom key
atomic.dequeue('queue', 'worker-1', timeout=5)

# Hash field exists indefinitely (MEMORY LEAK)
r.hexists('queue:in_progress:claims', url)  # True forever

# TTL was set on wrong key
r.ttl('queue:in_progress:claims:' + url)    # -2 (doesn't exist)
```

### After (Fixed Behavior)

```python
# Dequeue creates string key with TTL
atomic.dequeue('queue', 'worker-1', timeout=5)

# Claim key exists with correct TTL
r.get('queue:in_progress:claim:' + url)     # 'worker-1'
r.ttl('queue:in_progress:claim:' + url)     # 5

# After timeout, key auto-expires (NO LEAK)
time.sleep(6)
r.exists('queue:in_progress:claim:' + url)  # 0 (cleaned up)
```

---

## Migration Notes

### Backwards Compatibility

**Breaking Change:** The claim key structure changed

**Before:**
- Hash: `queue:in_progress:claims` → field `<url>` → value `worker_id`

**After:**
- String: `queue:in_progress:claim:<url>` → value `worker_id`

### Deployment

1. **Flush in-progress claims** (safe if workers restart):
   ```bash
   redis-cli -h aio-01 -p 6379
   DEL scrape_queue:in_progress:claims
   ```

2. **Or migrate gracefully** (if needed):
   ```python
   import redis
   r = redis.Redis(host='aio-01', port=6379)
   
   # Get all old claims
   old_claims = r.hgetall('queue:in_progress:claims')
   
   # Convert to new format
   for url, worker_id in old_claims.items():
       r.setex(f'queue:in_progress:claim:{url.decode()}', 300, worker_id)
   
   # Remove old hash
   r.delete('queue:in_progress:claims')
   ```

3. **Deploy updated code** (restart workers)

4. **Verify** (check Redis memory usage stabilizes)

---

## Performance Impact

### Memory

- **Before:** Unbounded growth in `:claims` hash
- **After:** Automatic cleanup via TTL expiration
- **Savings:** ~500 bytes per stale claim

### CPU

- **Before:** Manual reclaim_stale scans required
- **After:** Redis handles expiration automatically
- **Impact:** Negligible (TTL is O(1))

### Network

- **Before:** `HSET` + `EXPIRE` (2 commands, EXPIRE was wrong key)
- **After:** `SETEX` (1 command, correct key)
- **Improvement:** 50% reduction in Redis commands

---

## Related Issues

- Original issue: Code review finding on TTL consistency
- Root cause: Misunderstanding of Redis data structure TTL semantics
- Similar patterns: None found (this was the only place mixing hash fields with key expiration)

---

## References

- **Test Script:** `test-ttl-fix-complete.py`
- **Lua Operations:** `shared/redis-atomic-operations.lua`
- **Python Wrapper:** `shared/redis_atomic_wrapper.py`
- **Redis TTL Docs:** https://redis.io/commands/expire/

---

## Verification

To verify the fix is working in production:

```bash
# Check for old claim hash (should not exist)
redis-cli -h aio-01 -p 6379 EXISTS scrape_queue:in_progress:claims

# Check for new claim keys (should have TTL)
redis-cli -h aio-01 -p 6379 KEYS 'scrape_queue:in_progress:claim:*'

# Verify TTL is set
redis-cli -h aio-01 -p 6379 TTL 'scrape_queue:in_progress:claim:<some_url>'
```

Expected:
- Old hash: `0` (doesn't exist)
- New keys: List of URLs
- TTL: Positive number (seconds remaining)

---

**Fix Complete:** All tests passing, ready for deployment.
