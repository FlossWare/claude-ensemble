# Redis Queue Naming Convention

**Date:** 2026-07-11  
**Status:** AUTHORITATIVE

## Standard Naming Convention

**ALL Redis queues MUST use the `redis:queue:` prefix.**

### Queue Name Format

```
redis:queue:<stage>:<priority>     # For priority-based queues (ZSET)
redis:queue:<stage>                # For FIFO queues (LIST)
```

### Examples

**Pipeline Queues (4-stage processing):**
```
redis:queue:store:high      # ZSET - Priority 8-10 documents
redis:queue:store:medium    # ZSET - Priority 4-7 documents  
redis:queue:store:low       # ZSET - Priority 1-3 documents
redis:queue:chunk           # LIST - FIFO processing
redis:queue:embed           # LIST - FIFO processing
redis:queue:graph           # LIST - FIFO processing
```

**Scraping Queues (category-based):**
```
redis:queue:performance:high   # High-priority performance content
redis:queue:ai:medium          # Medium-priority AI content
redis:queue:ml:medium          # Medium-priority ML content
redis:queue:ga:low             # Low-priority general articles
```

**Dead Letter Queues:**
```
redis:dlq:store
redis:dlq:chunk
redis:dlq:embed
redis:dlq:graph
```

**Processing Tracking:**
```
redis:processing:store     # SET - In-flight tasks with metadata
redis:processing:chunk
redis:processing:embed
redis:processing:graph
```

**Worker Heartbeats:**
```
redis:heartbeat:store      # HASH - task_id -> worker_id:timestamp
redis:heartbeat:chunk
redis:heartbeat:embed
redis:heartbeat:graph
```

**Completed Tasks:**
```
redis:completed:store      # HASH - 24h TTL
redis:completed:chunk
redis:completed:embed
redis:completed:graph
```

**Idempotency Tracking:**
```
redis:idempotency:store    # HASH - idempotency_key -> item_id
redis:idempotency:chunk
redis:idempotency:embed
redis:idempotency:graph
```

## Rationale

### Why `redis:` prefix?

1. **Namespace isolation** - Separates Redis keys from other systems
2. **Visual clarity** - Immediately identifies Redis-related keys
3. **Consistency** - All Redis keys use same prefix pattern
4. **Tool support** - Redis clients can filter by prefix (e.g., `KEYS redis:*`)

### Why `queue:` component?

1. **Type identification** - Distinguishes queues from other Redis structures
2. **Pattern matching** - Easy to find all queues with `redis:queue:*`
3. **Convention** - Follows Redis naming best practices

## Anti-Patterns

### ❌ WRONG - Missing `redis:` prefix

```python
# BAD
QUEUES = [
    "queue:performance:high",
    "queue:ai:medium",
]
```

### ✅ CORRECT - Full prefix

```python
# GOOD
QUEUES = [
    "redis:queue:performance:high",
    "redis:queue:ai:medium",
]
```

### ❌ WRONG - Inconsistent naming

```python
# BAD - Mixed conventions
QUEUES = [
    "redis:queue:store:high",    # Good
    "queue:ai:medium",            # Missing redis: prefix
    "redis:ai:medium",            # Missing queue: component
]
```

### ✅ CORRECT - Consistent naming

```python
# GOOD - All follow convention
QUEUES = [
    "redis:queue:store:high",
    "redis:queue:ai:medium",
    "redis:queue:ml:medium",
]
```

## Implementation Files

**Python Scripts:**
- `scripts/redis-queue-worker.py` - Scraping worker (uses scraping queues)
- `scripts/redis-worker-with-atomic-ops.py` - Pipeline worker (uses store queues)
- `scripts/migrate-pg-to-redis.py` - Migration script (creates queues)
- `scripts/redis-atomic-operations.py` - Atomic operations library

**Deployment Scripts:**
- `scripts/deploy-redis-workers.sh` - Deploys scraping workers

**Documentation:**
- `docs/POSTGRESQL_TO_REDIS_MIGRATION_STRATEGY.md` - Migration plan
- `docs/REDIS_BUG_FIXES_COMPLETE.md` - Bug fix summary

## Verification

**Check queue naming consistency:**

```bash
# List all queue keys
redis-cli --scan --pattern "redis:queue:*"

# Expected output:
redis:queue:store:high
redis:queue:store:medium
redis:queue:store:low
redis:queue:chunk
redis:queue:embed
redis:queue:graph
redis:queue:performance:high
redis:queue:ai:medium
redis:queue:ml:medium
redis:queue:ga:low
```

**Check for non-standard queues:**

```bash
# Should return nothing (all queues should have redis: prefix)
redis-cli --scan --pattern "queue:*" | grep -v "^redis:"
```

## Migration from Old Convention

If you find queues without the `redis:` prefix:

1. **Check for data** - `redis-cli LLEN queue:old:name` or `ZCARD queue:old:name`
2. **Rename if empty** - `redis-cli DEL queue:old:name`
3. **Migrate if populated** - Use `RENAME queue:old:name redis:queue:new:name`
4. **Update code** - Change all references to use new name
5. **Verify** - Test with new queue names

**Example migration:**

```bash
# Check current state
redis-cli LLEN queue:performance:high

# If has data, rename
redis-cli RENAME queue:performance:high redis:queue:performance:high

# If empty, just delete old key (new key will be created on first use)
redis-cli DEL queue:performance:high
```

## Related Documentation

- [[POSTGRESQL_TO_REDIS_MIGRATION_STRATEGY]] - Migration plan and queue design
- [[REDIS_BUG_FIXES_COMPLETE]] - Bug fixes including priority score formula
- [[reference_scraper_architecture_AUTHORITATIVE]] - How scrapers use queues

---

**Remember:** ALL Redis queue keys MUST start with `redis:queue:` - no exceptions!
