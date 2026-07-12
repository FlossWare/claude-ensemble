# Queue Naming Convention

**Last Updated:** 2026-07-11  
**Status:** Enforced across all queue operations

---

## Standard Format

All Redis queue names **MUST** follow this pattern:

```
redis:queue:{stage}:{priority}
```

### Components

- **`redis:`** - Namespace prefix (always present)
- **`queue:`** - Type identifier (always "queue")
- **`{stage}`** - Processing stage (e.g., `store`, `chunk`, `embed`, `graph`, `scrape`)
- **`{priority}`** - Optional priority level (`high`, `medium`, `low`)

### Examples

**With Priority:**
```
redis:queue:store:high
redis:queue:store:medium
redis:queue:store:low
redis:queue:scrape:high
redis:queue:scrape:medium
redis:queue:scrape:low
```

**Without Priority:**
```
redis:queue:chunk
redis:queue:embed
redis:queue:graph
```

---

## Related Keys

All queue-related keys follow the same naming pattern:

### Processing Keys
```
redis:processing:{stage}:{priority}
```

Stores tasks currently being processed by workers.

**Examples:**
- `redis:processing:store:high`
- `redis:processing:chunk`

### Heartbeat Keys
```
redis:heartbeat:{stage}:{priority}
```

Tracks worker heartbeats for claimed tasks.

**Examples:**
- `redis:heartbeat:store:high`
- `redis:heartbeat:embed`

### Completed Keys
```
redis:completed:{stage}:{priority}
```

Stores completed task records (24-hour TTL by default).

**Examples:**
- `redis:completed:store:high`
- `redis:completed:graph`

### Dead Letter Queue (DLQ) Keys
```
redis:dlq:{stage}:{priority}
```

Stores tasks that exceeded max retries.

**Examples:**
- `redis:dlq:store:high`
- `redis:dlq:chunk`

---

## Stage Parameter Format

When calling `RedisAtomicOps` methods, the **stage parameter** should match the queue's stage and priority:

### For queues WITH priority:

**Queue:** `redis:queue:store:high`  
**Stage parameter:** `store:high`

```python
ops.complete_task(
    task_id,
    worker_id,
    result_json,
    stage='store:high',  # Matches queue name
    next_queue='redis:queue:chunk'
)
```

### For queues WITHOUT priority:

**Queue:** `redis:queue:chunk`  
**Stage parameter:** `chunk`

```python
ops.complete_task(
    task_id,
    worker_id,
    result_json,
    stage='chunk',  # Matches queue name
    next_queue='redis:queue:embed'
)
```

---

## Implementation Examples

### Python (RedisAtomicOps)

```python
from redis_atomic_operations import RedisAtomicOps

ops = RedisAtomicOps(host='aio-01', port=6379)

# Claim from priority queue
task = ops.claim_task('redis:queue:store:high', 'worker-1')

# Complete and forward to next stage
ops.complete_task(
    task['id'],
    'worker-1',
    json.dumps(result),
    stage='store:high',         # Matches queue priority
    next_queue='redis:queue:chunk',  # Next stage (no priority)
    next_queue_mode='list'      # FIFO mode for chunk stage
)

# Fail and requeue
ops.fail_task(
    task['id'],
    'worker-1',
    'Processing error',
    stage='store:high',         # Matches queue priority
    max_retries=3
)
```

### Python (Worker Script)

```python
from redis_atomic_operations import RedisAtomicOps

# Worker for store:high queue
worker = RedisWorker(
    worker_id='worker-1',
    stage='store',  # Stage name
    redis_host='aio-01',
    queue_mode='zset'  # Priority queue mode
)

# Worker internally uses:
# - Queue: redis:queue:store:high
# - Processing: redis:processing:store:high
# - Heartbeat: redis:heartbeat:store:high
```

---

## Queue Modes

Queues use different data structures based on their purpose:

### Priority Queues (ZSET)

**Data Structure:** Redis Sorted Set  
**Operations:** `ZADD`, `ZPOPMIN`, `ZPOPMAX`  
**Use Case:** Priority-based task processing

**Stages:**
- `store` (high/medium/low priority)
- `scrape` (high/medium/low priority)

**Example:**
```python
# Higher priority = lower score (ZPOPMIN gets lowest score first)
priority = 8
timestamp_ms = int(time.time() * 1000)
score = (10 - priority) * 1e13 + timestamp_ms

r.zadd('redis:queue:store:high', {task_json: score})
```

### FIFO Queues (LIST)

**Data Structure:** Redis List  
**Operations:** `LPUSH`, `RPOP`, `BRPOP`  
**Use Case:** Sequential processing, strict ordering

**Stages:**
- `chunk` (no priority)
- `embed` (no priority)
- `graph` (no priority)

**Example:**
```python
# FIFO order (first in, first out)
r.lpush('redis:queue:chunk', task_json)
```

---

## Validation

### Automated Tests

**Convention Test:** `tests/test_queue_naming_convention.py`
- Scans codebase for queue references
- Verifies all queues use `redis:queue:` prefix
- Reports violations with suggested fixes

**Integration Test:** `tests/test_queue_naming_integration.py`
- Tests queue name parsing logic
- Verifies stage parameter handling
- Validates all related key generation

**Run Tests:**
```bash
# Convention test
python3 tests/test_queue_naming_convention.py

# Integration test
python3 tests/test_queue_naming_integration.py
```

### Manual Verification

**Search for non-compliant queue names:**
```bash
# Should return no results
grep -r '"queue:[^r]' . --include="*.py" --include="*.js" --include="*.mjs"
```

**List all queue names in codebase:**
```bash
grep -rho 'redis:queue:[a-z:]*' . --include="*.py" | sort -u
```

---

## Migration Guide

### Old Pattern (Incorrect)

```python
# ❌ WRONG: Missing redis: prefix
ops.claim_task('queue:store:high', 'worker-1')
ops.complete_task(task_id, worker_id, result, stage='store')
```

### New Pattern (Correct)

```python
# ✅ CORRECT: Full redis:queue: prefix
ops.claim_task('redis:queue:store:high', 'worker-1')
ops.complete_task(task_id, worker_id, result, stage='store:high')
```

### Find and Replace

```bash
# Find old patterns
grep -r '"queue:' . --include="*.py" --include="*.js"

# Replace with correct pattern
sed -i 's/"queue:/"redis:queue:/g' filename.py
```

---

## Benefits

1. **Namespace Isolation** - `redis:` prefix prevents key collisions
2. **Consistent Parsing** - Predictable key structure across all operations
3. **Multi-Tenancy Support** - Easy to add environment prefixes (`dev:redis:queue:...`)
4. **Debugging** - Clear key names in Redis CLI
5. **Validation** - Automated tests catch violations early

---

## Common Pitfalls

### ❌ Incorrect

```python
# Missing redis: prefix
ops.claim_task('queue:store:high', 'worker-1')

# Mismatched stage parameter
ops.complete_task(task_id, worker_id, result, 
    stage='store',  # Should be 'store:high'
    queue_name='redis:queue:store:high'
)

# Wrong key generation
processing_key = f'processing:{stage}'  # Missing redis: prefix
```

### ✅ Correct

```python
# Full redis:queue: prefix
ops.claim_task('redis:queue:store:high', 'worker-1')

# Stage matches queue priority
ops.complete_task(task_id, worker_id, result,
    stage='store:high',  # Matches queue name
    next_queue='redis:queue:chunk'
)

# Correct key generation
processing_key = f'redis:processing:{stage}'  # Full prefix
```

---

## Questions?

- **Code:** `scripts/redis-atomic-operations.py`
- **Worker:** `scripts/redis-worker-with-atomic-ops.py`
- **Tests:** `tests/test_queue_naming_*.py`
- **Issues:** Open a GitLab issue with tag `queue-naming`

---

**Last Verified:** 2026-07-11  
**Test Status:** ✅ All tests passing
