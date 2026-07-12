# Queue Ownership Verification

**Problem:** Multiple workers processing the same queue can have race conditions where:
- Two workers fetch the same item
- Worker A starts processing item, crashes
- Worker B completes the item while Worker A is still processing
- Duplicate work, data corruption, inconsistent state

**Solution:** Ownership verification at every operation

---

## How It Works

### 1. Atomic Item Acquisition

**SQL Pattern:**
```sql
UPDATE queue.store
SET
    status = 'processing',
    worker_id = 'server-01-12345',
    started_at = NOW(),
    heartbeat = NOW()
WHERE id IN (
    SELECT id
    FROM queue.store
    WHERE status = 'pending'
    ORDER BY priority DESC, created_at ASC
    LIMIT 10
    FOR UPDATE SKIP LOCKED
)
RETURNING id, payload, worker_id, ...
```

**Key Points:**
- `FOR UPDATE SKIP LOCKED` locks rows atomically
- Skips items already locked by other transactions
- Sets `worker_id` to claim ownership
- Returns ONLY items this worker now owns

### 2. Ownership Verification on Complete

**SQL Pattern:**
```sql
UPDATE queue.store
SET
    status = 'completed',
    completed_at = NOW(),
    result = '{"done": true}'
WHERE id = 123 AND worker_id = 'server-01-12345'
```

**Key Points:**
- `AND worker_id = %s` in WHERE clause
- If worker_id doesn't match, UPDATE affects 0 rows
- Returns `updated: false` if ownership lost
- Worker knows it lost ownership and can retry

### 3. Heartbeat with Ownership Verification

**SQL Pattern:**
```sql
UPDATE queue.store
SET heartbeat = NOW()
WHERE id = 123 AND worker_id = 'server-01-12345' AND status = 'processing'
```

**Key Points:**
- Updates heartbeat only if we own the item
- Prevents stealing items from other workers
- Returns `updated: false` if ownership lost
- Worker can detect timeout and recover

---

## API Endpoints

### POST /queue/add

Add item to queue.

**Request:**
```json
{
  "queue": "store",
  "payload": {"url": "https://...", "content": "..."},
  "priority": 5
}
```

**Response:**
```json
{
  "queued": true,
  "queue": "store",
  "item_id": 123
}
```

### POST /queue/fetch/:queue_name

Fetch items with ownership lock.

**Request:**
```json
{
  "worker_id": "server-01-12345",
  "limit": 10
}
```

**Response:**
```json
{
  "items": [
    {
      "id": 123,
      "payload": {"url": "...", "content": "..."},
      "worker_id": "server-01-12345",
      "created_at": "2026-07-11T...",
      "priority": 5,
      "started_at": "2026-07-11T..."
    }
  ]
}
```

**Notes:**
- All items have `worker_id` set to your worker_id
- Items are locked (other workers can't fetch them)
- Returns 204 if no items available

### POST /queue/complete/:queue_name/:item_id

Complete item with ownership verification.

**Request:**
```json
{
  "worker_id": "server-01-12345",
  "result": {"done": true},
  "error": null
}
```

**Response (Success):**
```json
{
  "updated": true,
  "item_id": 123
}
```

**Response (Ownership Lost):**
```json
{
  "updated": false,
  "item_id": 123,
  "error": "Ownership verification failed"
}
```

### POST /queue/heartbeat/:queue_name/:item_id

Update heartbeat.

**Request:**
```json
{
  "worker_id": "server-01-12345"
}
```

**Response (Success):**
```json
{
  "updated": true
}
```

**Response (Ownership Lost):**
```json
{
  "updated": false
}
```

### GET /queue/stats/:queue_name

Get queue statistics.

**Response:**
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

---

## Worker Implementation

### Basic Pattern

```python
from postgres_queue_worker_with_ownership import QueueWorker

def my_processor(item):
    """Process item payload"""
    payload = item["payload"]
    # ... do work ...
    return {"done": True, "result": "..."}

worker = QueueWorker("store", my_processor)
worker.run()
```

### With Heartbeat

```python
def long_running_processor(item):
    """Processor with heartbeat for long-running tasks"""
    worker_id = item["worker_id"]
    item_id = item["id"]

    for i in range(100):
        # Do work
        time.sleep(1)

        # Send heartbeat every 10 seconds
        if i % 10 == 0:
            success = worker.heartbeat_item(item_id)
            if not success:
                # Lost ownership, stop processing
                raise Exception("Lost ownership during processing")

    return {"done": True}
```

---

## Race Condition Prevention

### Scenario 1: Two Workers Fetch Simultaneously

**Without Ownership Verification:**
```
Worker-1: SELECT id FROM queue WHERE status='pending' LIMIT 1  -> id=123
Worker-2: SELECT id FROM queue WHERE status='pending' LIMIT 1  -> id=123
Worker-1: UPDATE queue SET status='processing' WHERE id=123
Worker-2: UPDATE queue SET status='processing' WHERE id=123
Both workers process item 123!
```

**With Ownership Verification:**
```
Worker-1: UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED)
          -> Locks id=123, sets worker_id='worker-1'
Worker-2: UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED)
          -> Skips id=123 (locked), gets id=124 instead, sets worker_id='worker-2'
Worker-1 processes item 123
Worker-2 processes item 124
No overlap!
```

### Scenario 2: Worker Completes Wrong Item

**Without Ownership Verification:**
```
Worker-1 fetches item 123
Worker-2 fetches item 123 (race condition)
Worker-1 completes item 123
Worker-2 completes item 123 (overwrites Worker-1's result)
```

**With Ownership Verification:**
```
Worker-1 fetches item 123 (worker_id='worker-1')
Worker-2 fetches item 124 (worker_id='worker-2')
Worker-1: UPDATE ... WHERE id=123 AND worker_id='worker-1'  -> Success
Worker-2: UPDATE ... WHERE id=123 AND worker_id='worker-2'  -> 0 rows, updated=false
Worker-2 logs error: "Ownership verification failed"
```

### Scenario 3: Heartbeat Timeout

**Without Ownership Verification:**
```
Worker-1 fetches item 123, starts processing (5 min task)
Worker-1 heartbeat fails (network issue)
Reaper marks item 123 as 'pending' (heartbeat timeout)
Worker-2 fetches item 123
Both workers processing item 123!
```

**With Ownership Verification:**
```
Worker-1 fetches item 123 (worker_id='worker-1')
Worker-1 heartbeat fails (network issue)
Reaper: UPDATE ... SET status='pending', worker_id=NULL WHERE heartbeat < NOW() - INTERVAL '5 minutes'
Worker-2 fetches item 123 (worker_id='worker-2')
Worker-1: UPDATE ... WHERE id=123 AND worker_id='worker-1'  -> 0 rows (worker_id changed)
Worker-1 detects ownership lost, stops processing
Worker-2 completes successfully
```

---

## Testing

### Run All Tests

```bash
python3 tests/test_queue_ownership_verification.py
```

### Test 1: Basic Ownership Flow

- Add item to queue
- Worker-1 fetches item
- Worker-2 tries to complete (fails)
- Worker-1 completes (succeeds)

### Test 2: Heartbeat Ownership

- Worker-1 fetches item
- Worker-1 heartbeat (succeeds)
- Worker-2 heartbeat (fails)

### Test 3: Race Condition Prevention

- Add 10 items
- 3 workers fetch simultaneously
- Verify NO overlapping items

### Test 4: Worker Isolation

- Worker-1 fetches item A
- Worker-2 fetches item B
- Worker-1 cannot complete item B
- Worker-2 cannot complete item A
- Each completes their own item

### Test 5: Queue Stats

- Get queue statistics
- Verify counts by status
- Verify worker counts

---

## Deployment

### 1. Deploy Ownership Verification

```bash
./scripts/deploy_ownership_verification.sh
```

This:
- Backs up existing API
- Integrates ownership verification endpoints
- Restarts API service
- Shows test command

### 2. Run Tests

```bash
python3 tests/test_queue_ownership_verification.py
```

### 3. Deploy Workers

```bash
# On each worker node
export WORKER_ID="$(hostname)-$$"
export ORCHESTRATOR_API="http://aio-01:5000"

# Start store worker
python3 tools/postgres_queue_worker_with_ownership.py store &

# Start chunk worker
python3 tools/postgres_queue_worker_with_ownership.py chunk &

# Start embed worker
python3 tools/postgres_queue_worker_with_ownership.py embed &

# Start graph worker
python3 tools/postgres_queue_worker_with_ownership.py graph &
```

### 4. Monitor

```bash
# Check queue stats
curl http://aio-01:5000/queue/stats/store | jq

# Check worker activity
curl http://aio-01:5000/queue/stats/store | jq '.workers'

# Check API logs
ssh aio-01 'sudo journalctl -u orchestrator-api -f'
```

---

## Key Benefits

1. **No Race Conditions**
   - `FOR UPDATE SKIP LOCKED` prevents duplicate fetches
   - Atomic ownership assignment

2. **Worker Isolation**
   - Each worker only modifies items it owns
   - Other workers cannot interfere

3. **Crash Recovery**
   - Heartbeat timeout detection
   - Automatic re-queuing of stale items
   - New worker can pick up abandoned work

4. **Audit Trail**
   - `worker_id` tracked for every operation
   - Easy to see which worker processed each item
   - Debugging and monitoring

5. **No Distributed Locks**
   - Database-native locking
   - No Redis/ZooKeeper required
   - Simple, reliable

---

## Common Pitfalls

### ❌ DON'T: Skip worker_id in requests

```python
# BAD - No worker_id
response = requests.post(
    "http://aio-01:5000/queue/fetch/store",
    json={"limit": 10}
)
```

**Why:** Ownership cannot be assigned without worker_id.

### ❌ DON'T: Use wrong worker_id

```python
# BAD - Hardcoded worker_id
response = requests.post(
    "http://aio-01:5000/queue/fetch/store",
    json={"worker_id": "worker-1", "limit": 10}
)
```

**Why:** Multiple workers with same ID will conflict.

### ❌ DON'T: Skip ownership check in complete

```python
# BAD - Ignoring updated field
response = requests.post(
    f"http://aio-01:5000/queue/complete/store/{item_id}",
    json={"worker_id": worker_id, "result": result}
)
# Assumes it worked
```

**Why:** If `updated: false`, you don't own the item. Need to handle.

### ✅ DO: Use unique worker_id

```python
import socket
import os

worker_id = f"{socket.gethostname()}-{os.getpid()}"
```

**Why:** Unique per process, easy to identify.

### ✅ DO: Check ownership verification results

```python
response = requests.post(
    f"http://aio-01:5000/queue/complete/store/{item_id}",
    json={"worker_id": worker_id, "result": result}
)

if response.json().get("updated") == False:
    logger.error(f"Lost ownership of item {item_id}")
    # Handle lost ownership
```

**Why:** Ownership can be lost due to timeout or race condition.

### ✅ DO: Send heartbeats for long tasks

```python
def long_task(item):
    for i in range(100):
        time.sleep(1)

        if i % 10 == 0:
            heartbeat_item(item["id"])
```

**Why:** Prevents timeout and re-queuing while still processing.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Worker-1 (server-01-12345)                                  │
│                                                             │
│  1. POST /queue/fetch/store                                │
│     {"worker_id": "server-01-12345", "limit": 10}          │
│                                                             │
│     Response:                                              │
│     {"items": [                                            │
│       {"id": 123, "worker_id": "server-01-12345", ...},   │
│       {"id": 124, "worker_id": "server-01-12345", ...}    │
│     ]}                                                     │
│                                                             │
│  2. Process items 123, 124                                 │
│                                                             │
│  3. POST /queue/complete/store/123                         │
│     {"worker_id": "server-01-12345", "result": {...}}      │
│                                                             │
│     Response: {"updated": true}                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ aio-01:5000 (Orchestrator API)                              │
│                                                             │
│  /queue/fetch/store endpoint:                              │
│                                                             │
│    UPDATE queue.store                                      │
│    SET status='processing', worker_id='server-01-12345'   │
│    WHERE id IN (                                           │
│      SELECT id FROM queue.store                           │
│      WHERE status='pending'                               │
│      ORDER BY priority DESC                               │
│      LIMIT 10                                             │
│      FOR UPDATE SKIP LOCKED  <- Atomic lock               │
│    )                                                       │
│    RETURNING id, payload, worker_id, ...                  │
│                                                             │
│  /queue/complete/store/:id endpoint:                       │
│                                                             │
│    UPDATE queue.store                                      │
│    SET status='completed', result='...'                   │
│    WHERE id=123 AND worker_id='server-01-12345'          │
│          ^                  ^                             │
│          |                  |                             │
│          Item ID            Ownership verification        │
│                                                             │
│    Returns: {"updated": (rowcount > 0)}                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ PostgreSQL
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL (aio-01:5433)                                    │
│                                                             │
│  queue.store table:                                        │
│                                                             │
│  id | status      | worker_id         | payload | ...      │
│  ---|-------------|-------------------|---------|-----      │
│  123| processing  | server-01-12345   | {...}   | ...      │
│  124| processing  | server-01-12345   | {...}   | ...      │
│  125| processing  | server-02-67890   | {...}   | ...      │
│  126| pending     | NULL              | {...}   | ...      │
│                                                             │
│  Ownership verified by worker_id column                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

**Ownership verification prevents:**
- ✅ Race conditions (FOR UPDATE SKIP LOCKED)
- ✅ Duplicate processing (worker_id in WHERE)
- ✅ Item stealing (heartbeat verification)
- ✅ Data corruption (atomic operations)

**All operations verify worker_id:**
- ✅ Fetch: Sets worker_id atomically
- ✅ Complete: Checks worker_id in WHERE
- ✅ Heartbeat: Checks worker_id in WHERE

**Result:**
- Safe distributed queue processing
- Multiple workers without conflicts
- Crash recovery with no data loss
- Simple, database-native solution
