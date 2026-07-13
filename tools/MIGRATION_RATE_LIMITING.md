# Migration with Rate Limiting

## Overview

The migration script with rate limiting ensures that document processing doesn't overwhelm the system by:

1. **Checking rate limits** before queueing documents
2. **Respecting queue size limits** to prevent memory exhaustion
3. **Waiting for capacity** when limits are reached
4. **Tracking migration progress** in PostgreSQL

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL (aio-01:5433)                                    │
│                                                             │
│  web_content.raw_documents:                                │
│   - url, category, title, content                          │
│   - processed = false                                      │
│   - queued_at = NULL                                       │
│                                                             │
│  Query: Get unprocessed documents                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ SELECT WHERE processed=false
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Migration Manager                                           │
│                                                             │
│  For each document:                                        │
│   1. Check rate limit (token bucket)                       │
│   2. Check queue size                                      │
│   3. Wait if needed                                        │
│   4. Queue to Redis                                        │
│   5. Mark as queued in PostgreSQL                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ RPUSH if allowed
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Redis (aio-01:6379)                                         │
│                                                             │
│  queue:store → [doc1, doc2, doc3, ...]                     │
│                                                             │
│  rate_limit:queue:store → sorted set with timestamps       │
│                                                             │
│  Limits:                                                   │
│   - Rate: 100 docs/min (configurable)                     │
│   - Queue size: 200 max (configurable)                    │
└─────────────────────────────────────────────────────────────┘
```

## Rate Limiting Algorithm

### Token Bucket with Redis Sorted Sets

```python
def check_rate_limit(queue_name, rate_limit=100, window=60):
    """
    Token bucket algorithm using Redis sorted sets.
    
    Key: rate_limit:{queue_name}
    Value: Sorted set of timestamps
    
    Algorithm:
    1. Remove entries older than window
    2. Count remaining entries
    3. If count < rate_limit, allow
    4. Return (allowed, remaining)
    """
    key = f"rate_limit:{queue_name}"
    current_time = int(time.time())
    window_start = current_time - window
    
    # Remove old entries
    redis.zremrangebyscore(key, 0, window_start)
    
    # Count current entries
    current_count = redis.zcard(key)
    
    if current_count >= rate_limit:
        return False, 0
    
    remaining = rate_limit - current_count
    return True, remaining
```

### Queue Size Check

```python
def check_queue_size(queue_name, max_size=200):
    """
    Check if queue size is under limit.
    
    Uses Redis LLEN to get current queue size.
    """
    current_size = redis.llen(queue_name)
    allowed = current_size < max_size
    return allowed, current_size
```

### Wait for Capacity

```python
def wait_for_capacity(queue_name, timeout=300):
    """
    Wait for both rate limit and queue size to have capacity.
    
    Polling loop:
    1. Check rate limit
    2. Check queue size
    3. If both allow, return True
    4. Calculate wait time based on constraints
    5. Sleep and retry
    6. Timeout after max duration
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        rate_allowed, rate_remaining = check_rate_limit(queue_name)
        size_allowed, current_size = check_queue_size(queue_name)
        
        if rate_allowed and size_allowed:
            return True
        
        # Wait based on limiting factor
        if not rate_allowed:
            wait_time = min(5, RATE_LIMIT_WINDOW / 10)
        else:
            wait_time = min(10, max_size / (rate_limit / 60))
        
        time.sleep(wait_time)
    
    return False
```

## Usage

### Basic Migration

```bash
# Migrate all unprocessed documents with default settings
python3 tools/migrate_with_rate_limiting.py

# Output:
# Starting migration with rate limit: 100/min, max queue: 200
# 
# --- Batch starting at offset 0 ---
# Queued: https://example.com/doc1 (test)
# Queued: https://example.com/doc2 (test)
# ...
# Batch complete: 100 queued, 0 skipped
# 
# === Migration Complete ===
# Total queued: 1234
# Total skipped: 0
```

### Custom Rate Limits

```bash
# Higher rate limit for faster migration
python3 tools/migrate_with_rate_limiting.py --rate-limit 200 --max-queue 500

# Conservative rate limit for limited resources
python3 tools/migrate_with_rate_limiting.py --rate-limit 50 --max-queue 100

# Small batches for testing
python3 tools/migrate_with_rate_limiting.py --batch-size 10
```

### Check Queue Stats

```bash
# Show current queue statistics without migrating
python3 tools/migrate_with_rate_limiting.py --stats-only

# Output:
# === Queue Statistics ===
# queue:store:
#   Size: 145
#   Rate remaining: 23/100
# queue:chunk:
#   Size: 89
#   Rate remaining: 67/100
# queue:embed:
#   Size: 12
#   Rate remaining: 94/100
# queue:graph:
#   Size: 3
#   Rate remaining: 99/100
```

## Configuration

### Environment Variables

```bash
# Redis connection
export REDIS_HOST="aio-01"
export REDIS_PORT=6379

# PostgreSQL connection
export POSTGRES_HOST="aio-01"
export POSTGRES_PORT=5433
export POSTGRES_DB="learning"
export POSTGRES_USER="sfloess"

# Rate limiting
export RATE_LIMIT=100          # docs per minute
export BURST_LIMIT=200         # max queue size
export RATE_LIMIT_WINDOW=60    # seconds
```

### Command-Line Arguments

```
--batch-size N        Batch size for migration (default: 100)
--rate-limit N        Rate limit in docs/min (default: 100)
--max-queue N         Max queue size (default: 200)
--stats-only          Show stats without migrating
```

## Testing

### Run Unit Tests

```bash
# Install test dependencies
pip3 install pytest pytest-mock

# Run tests
python3 tools/test_migrate_with_rate_limiting.py

# Or with pytest
pytest tools/test_migrate_with_rate_limiting.py -v
```

### Test Coverage

- ✅ Rate limit enforcement (under limit, at limit, over limit)
- ✅ Rate limit window expiration (old entries removed)
- ✅ Queue size limits
- ✅ Wait for capacity (immediate, timeout)
- ✅ Document queueing (success, rate limited)
- ✅ Batch migration
- ✅ Hash generation consistency
- ✅ Payload structure validation

### Manual Testing

```bash
# 1. Check initial state
python3 tools/migrate_with_rate_limiting.py --stats-only

# 2. Migrate small batch
python3 tools/migrate_with_rate_limiting.py --batch-size 10

# 3. Verify queue has items
redis-cli -h aio-01 LLEN queue:store

# 4. Check rate limit tracking
redis-cli -h aio-01 ZCARD rate_limit:queue:store

# 5. Verify PostgreSQL updated
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT COUNT(*) FROM web_content.raw_documents WHERE queued_at IS NOT NULL;"
```

## PostgreSQL Schema

### Required Tables

```sql
-- Raw documents table
CREATE TABLE IF NOT EXISTS web_content.raw_documents (
    url TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    queued_at TIMESTAMP,
    queue_name TEXT
);

-- Index for migration queries
CREATE INDEX IF NOT EXISTS idx_raw_documents_unprocessed 
ON web_content.raw_documents (processed, queued_at)
WHERE processed = false AND queued_at IS NULL;
```

## Redis Data Structures

### Queues

```
queue:store   → List of JSON payloads (RPUSH to add, LPOP to consume)
queue:chunk   → List of chunking tasks
queue:embed   → List of embedding tasks
queue:graph   → List of graph indexing tasks
```

### Rate Limit Tracking

```
rate_limit:queue:store → Sorted set (score=timestamp, member=timestamp string)
rate_limit:queue:chunk → Sorted set
rate_limit:queue:embed → Sorted set
rate_limit:queue:graph → Sorted set
```

### Queue Payload Format

```json
{
  "url": "https://example.com/doc",
  "category": "test",
  "title": "Test Document",
  "content": "Document content...",
  "metadata": {
    "author": "...",
    "date": "..."
  },
  "hash": "abc123...",
  "queued_at": "2026-07-11T00:00:00"
}
```

## Performance

### Benchmarks

| Rate Limit | Queue Size | Docs/Hour | Notes |
|------------|-----------|-----------|-------|
| 100/min | 200 | ~6,000 | Default, balanced |
| 200/min | 500 | ~12,000 | Fast migration |
| 50/min | 100 | ~3,000 | Conservative |

### Monitoring

```bash
# Watch queue sizes
watch -n 1 'redis-cli -h aio-01 LLEN queue:store'

# Monitor rate limit
watch -n 1 'redis-cli -h aio-01 ZCARD rate_limit:queue:store'

# PostgreSQL progress
watch -n 5 'psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT COUNT(*) as queued FROM web_content.raw_documents WHERE queued_at IS NOT NULL;"'
```

## Troubleshooting

### Migration Stuck

**Symptom:** Migration stops making progress

**Diagnosis:**
```bash
# Check if rate limited
python3 tools/migrate_with_rate_limiting.py --stats-only

# Check Redis connection
redis-cli -h aio-01 PING

# Check PostgreSQL connection
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1;"
```

**Fix:**
- Increase rate limit: `--rate-limit 200`
- Increase queue size: `--max-queue 500`
- Check worker consumption rate

### Queue Backing Up

**Symptom:** Queue size grows, doesn't drain

**Diagnosis:**
```bash
# Check worker status
systemctl status queue-worker@store
systemctl status queue-worker@chunk

# Check worker logs
journalctl -u queue-worker@store -f
```

**Fix:**
- Scale up workers (more processes)
- Reduce migration rate limit
- Check for worker errors

### Rate Limit Too Aggressive

**Symptom:** Lots of "waiting for capacity" messages

**Fix:**
```bash
# Increase rate limit
python3 tools/migrate_with_rate_limiting.py --rate-limit 200

# Or let workers catch up first
sleep 300  # Wait 5 minutes
python3 tools/migrate_with_rate_limiting.py
```

## Integration with Existing System

### With Scraper Flow

```
Scrapers → POST /store → Raw files → Migration script → Redis queues → Workers
                                              ↓
                                        Check rate limits
                                              ↓
                                          Queue only if allowed
```

### With Queue Workers

Migration script is the **producer**, queue workers are **consumers**:

```python
# Migration script (producer)
manager = MigrationManager()
manager.migrate_all(rate_limit=100)

# Queue workers (consumers)
while True:
    payload = redis.lpop("queue:store")
    if payload:
        process_document(json.loads(payload))
```

## Future Enhancements

1. **Priority queues** - Process important documents first
2. **Backpressure signaling** - Workers tell migration to slow down
3. **Dynamic rate adjustment** - Adjust based on system load
4. **Dead letter queue** - Handle failed migrations
5. **Progress tracking UI** - Real-time dashboard

## Related Documentation

- [[session_2026-07-10_scraper_fix_COMPLETE]] - Scraper architecture
- [[reference_scraper_architecture_AUTHORITATIVE]] - How scrapers work
- [[feedback_scrape_then_process]] - Separation of concerns
- Redis Queue Design - Queue worker implementation

---

**Status:** ✅ COMPLETE - Rate limiting integration implemented and tested

**Last Updated:** 2026-07-11
