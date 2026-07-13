# Queue Ownership Verification - Changes Summary

**Date:** 2026-07-11  
**Status:** Ready for deployment and testing

---

## Problem Statement

Multiple workers processing the same PostgreSQL queue had race conditions:

1. **Duplicate Fetches**: Two workers could fetch the same item
2. **Cross-Worker Completion**: Worker A could complete Worker B's item
3. **Heartbeat Conflicts**: Workers could heartbeat items they don't own
4. **Data Corruption**: Inconsistent state from concurrent modifications

**Root Cause:** No ownership verification in queue operations.

---

## Solution

Added ownership verification to ALL queue operations:

1. **Atomic Ownership Assignment**: `FOR UPDATE SKIP LOCKED` in fetch
2. **Ownership Verification in Updates**: `WHERE worker_id = %s` in complete/heartbeat
3. **Worker Isolation**: Each worker can only modify items it owns
4. **Crash Recovery**: Heartbeat timeout detection with automatic re-queuing

---

## Files Created

### 1. Worker Implementation
**File:** `tools/postgres_queue_worker_with_ownership.py`

**Features:**
- QueueWorker class with ownership verification
- Automatic heartbeat support
- Worker isolation
- Processor functions for all queue stages (store, chunk, embed, graph)

**Usage:**
```bash
export WORKER_ID="$(hostname)-$$"
python3 tools/postgres_queue_worker_with_ownership.py store
```

### 2. API Endpoints
**File:** `api/queue_endpoints_with_ownership.py`

**Endpoints:**
- `POST /queue/add` - Add items to queue
- `POST /queue/fetch/:queue_name` - Fetch items with ownership lock
- `POST /queue/complete/:queue_name/:item_id` - Complete with verification
- `POST /queue/heartbeat/:queue_name/:item_id` - Heartbeat with verification
- `GET /queue/stats/:queue_name` - Queue statistics

**Key SQL Patterns:**
```sql
-- Fetch with atomic ownership
UPDATE queue.store
SET status='processing', worker_id=%s
WHERE id IN (
  SELECT id FROM queue.store
  WHERE status='pending'
  FOR UPDATE SKIP LOCKED
)
RETURNING *

-- Complete with ownership verification
UPDATE queue.store
SET status='completed', result=%s
WHERE id=%s AND worker_id=%s
```

### 3. Tests
**File:** `tests/test_queue_ownership_verification.py`

**Test Cases:**
1. Basic ownership flow (fetch → complete with verification)
2. Heartbeat ownership (only owner can heartbeat)
3. Race condition prevention (3 workers, 10 items, no overlap)
4. Worker isolation (workers can't complete each other's items)
5. Queue statistics

**Run:**
```bash
python3 tests/test_queue_ownership_verification.py
```

### 4. Deployment Script
**File:** `scripts/deploy_ownership_verification.sh`

**Steps:**
1. Backup existing API
2. Copy new queue endpoints
3. Integrate into application.py
4. Restart API service
5. Run health check

**Run:**
```bash
./scripts/deploy_ownership_verification.sh
```

### 5. Documentation
**File:** `docs/QUEUE_OWNERSHIP_VERIFICATION.md`

**Contents:**
- How ownership verification works
- API endpoint documentation
- Worker implementation patterns
- Race condition prevention scenarios
- Testing guide
- Deployment guide
- Common pitfalls and best practices

---

## How It Works

### 1. Fetch Items (Atomic Ownership)

**Request:**
```json
POST /queue/fetch/store
{
  "worker_id": "server-01-12345",
  "limit": 10
}
```

**Database Operation:**
```sql
UPDATE queue.store
SET
  status = 'processing',
  worker_id = 'server-01-12345',
  started_at = NOW(),
  heartbeat = NOW()
WHERE id IN (
  SELECT id FROM queue.store
  WHERE status = 'pending'
  ORDER BY priority DESC, created_at ASC
  LIMIT 10
  FOR UPDATE SKIP LOCKED  -- Critical: Atomic lock
)
RETURNING id, payload, worker_id, created_at, priority
```

**Result:**
- Locks rows atomically
- Sets worker_id to claim ownership
- Skips items already locked by other workers
- Returns ONLY items this worker now owns

### 2. Complete Item (Ownership Verification)

**Request:**
```json
POST /queue/complete/store/123
{
  "worker_id": "server-01-12345",
  "result": {"done": true}
}
```

**Database Operation:**
```sql
UPDATE queue.store
SET
  status = 'completed',
  completed_at = NOW(),
  result = '{"done": true}'
WHERE id = 123 AND worker_id = 'server-01-12345'
```

**Result:**
- `AND worker_id = %s` ensures we only update items WE own
- If another worker owns it, UPDATE affects 0 rows
- Returns `updated: false` if ownership verification fails

### 3. Heartbeat (Ownership Verification)

**Request:**
```json
POST /queue/heartbeat/store/123
{
  "worker_id": "server-01-12345"
}
```

**Database Operation:**
```sql
UPDATE queue.store
SET heartbeat = NOW()
WHERE id = 123 AND worker_id = 'server-01-12345' AND status = 'processing'
```

**Result:**
- Updates heartbeat only if we own the item
- Returns `updated: false` if ownership lost
- Worker can detect timeout and stop processing

---

## Race Condition Prevention

### Scenario: Two Workers Fetch Simultaneously

**Before (Race Condition):**
```
Worker-1: SELECT id FROM queue WHERE status='pending'  → id=123
Worker-2: SELECT id FROM queue WHERE status='pending'  → id=123
Worker-1: UPDATE queue SET status='processing' WHERE id=123
Worker-2: UPDATE queue SET status='processing' WHERE id=123
Both workers process item 123! (DUPLICATE WORK)
```

**After (Ownership Verification):**
```
Worker-1: UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED)
          → Locks id=123, sets worker_id='worker-1'
Worker-2: UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED)
          → Skips id=123 (locked), gets id=124, sets worker_id='worker-2'
Worker-1 processes item 123
Worker-2 processes item 124
NO OVERLAP!
```

### Scenario: Worker Completes Wrong Item

**Before (Data Corruption):**
```
Worker-1 fetches item 123
Worker-2 fetches item 123 (race condition)
Worker-1 completes item 123
Worker-2 completes item 123 (overwrites Worker-1's result!)
```

**After (Ownership Verification):**
```
Worker-1 fetches item 123 (worker_id='worker-1')
Worker-2 fetches item 124 (worker_id='worker-2')
Worker-1: UPDATE WHERE id=123 AND worker_id='worker-1'  → Success
Worker-2: UPDATE WHERE id=123 AND worker_id='worker-2'  → 0 rows, updated=false
Worker-2 logs: "Ownership verification failed"
NO DATA CORRUPTION!
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Review `docs/QUEUE_OWNERSHIP_VERIFICATION.md`
- [ ] Backup existing API: `ssh aio-01 'cd /exports/claude-orchestrator/api && tar -czf backup.tar.gz application.py'`
- [ ] Stop existing workers (if any)

### Deployment

- [ ] Run deployment script: `./scripts/deploy_ownership_verification.sh`
- [ ] Verify API started: `curl http://aio-01:5000/health`
- [ ] Check API logs: `ssh aio-01 'sudo journalctl -u orchestrator-api -n 50'`

### Testing

- [ ] Run ownership tests: `python3 tests/test_queue_ownership_verification.py`
- [ ] All 5 tests pass
- [ ] Check queue stats: `curl http://aio-01:5000/queue/stats/store | jq`

### Worker Deployment

- [ ] Deploy workers to fleet nodes
- [ ] Set unique `WORKER_ID` per process
- [ ] Start workers: `python3 tools/postgres_queue_worker_with_ownership.py <queue>`
- [ ] Monitor: `curl http://aio-01:5000/queue/stats/store | jq '.workers'`

### Verification

- [ ] Workers processing items
- [ ] No duplicate processing
- [ ] Queue stats show worker activity
- [ ] API logs show no ownership errors

---

## Monitoring

### Queue Statistics

```bash
curl http://aio-01:5000/queue/stats/store | jq
```

**Output:**
```json
{
  "queue": "store",
  "pending": 100,
  "processing": 5,
  "completed": 1000,
  "failed": 10,
  "workers": {
    "server-01-12345": 2,
    "server-02-67890": 3
  }
}
```

### Worker Activity

```bash
# See which workers are active
curl http://aio-01:5000/queue/stats/store | jq '.workers'

# Count active workers
curl -s http://aio-01:5000/queue/stats/store | jq '.workers | length'
```

### API Logs

```bash
# Live logs
ssh aio-01 'sudo journalctl -u orchestrator-api -f'

# Recent errors
ssh aio-01 'sudo journalctl -u orchestrator-api -p err -n 50'

# Ownership verification failures
ssh aio-01 'sudo journalctl -u orchestrator-api | grep "Ownership verification failed"'
```

---

## Key Benefits

1. **No Race Conditions**
   - `FOR UPDATE SKIP LOCKED` prevents duplicate fetches
   - Atomic ownership assignment
   - Database-native locking

2. **Worker Isolation**
   - Each worker only modifies items it owns
   - Other workers cannot interfere
   - Clear ownership boundaries

3. **Crash Recovery**
   - Heartbeat timeout detection
   - Automatic re-queuing of stale items
   - New worker can pick up abandoned work

4. **Audit Trail**
   - `worker_id` tracked for every operation
   - Easy to debug which worker processed each item
   - Monitoring and alerting

5. **Simple and Reliable**
   - No distributed locks needed
   - No Redis/ZooKeeper dependency
   - Database-native solution

---

## Next Steps

1. **Deploy to Production**
   - Run `./scripts/deploy_ownership_verification.sh`
   - Run tests to verify
   - Monitor for 24 hours

2. **Deploy Workers**
   - Start workers on fleet nodes
   - Monitor queue throughput
   - Scale workers based on queue depth

3. **Monitoring Setup**
   - Add Prometheus metrics for queue depth
   - Alert on stale heartbeats
   - Dashboard for worker activity

4. **Documentation**
   - Update runbooks with ownership verification
   - Train team on new API endpoints
   - Document worker deployment patterns

---

## Questions?

- **Documentation:** `docs/QUEUE_OWNERSHIP_VERIFICATION.md`
- **API Code:** `api/queue_endpoints_with_ownership.py`
- **Worker Code:** `tools/postgres_queue_worker_with_ownership.py`
- **Tests:** `tests/test_queue_ownership_verification.py`

**All operations verify worker_id. All race conditions prevented.**
