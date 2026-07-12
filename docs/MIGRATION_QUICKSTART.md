# PostgreSQL to Redis Migration - Quick Start Guide

**Date:** 2026-07-11  
**Items to Migrate:** 3,026 pending + 75 processing  
**Estimated Time:** 2-4 hours

---

## Pre-Migration Checklist

- [ ] Read full strategy: `docs/POSTGRESQL_TO_REDIS_MIGRATION_STRATEGY.md`
- [ ] Verify PostgreSQL has 3,026 pending items
- [ ] Verify Redis is empty and has sufficient memory (~7MB needed)
- [ ] Stop auto-scraper deployment
- [ ] Wait for 75 processing items to complete (or mark as dead_letter)
- [ ] Create PostgreSQL backup
- [ ] Team availability confirmed

---

## Quick Commands

### 1. Check Current State

```bash
# PostgreSQL pending count
psql -h aio-01 -p 5433 -U sfloess -d learning -t -c \
  "SELECT COUNT(*) FROM queue.store WHERE status = 'pending';"

# Redis queue lengths (should be 0 before migration)
ssh claude@aio-01 "redis-cli -h localhost LLEN redis:queue:store:high"
ssh claude@aio-01 "redis-cli -h localhost LLEN redis:queue:store:medium"
ssh claude@aio-01 "redis-cli -h localhost LLEN redis:queue:store:low"

# Processing items count
psql -h aio-01 -p 5433 -U sfloess -d learning -t -c \
  "SELECT 'chunk' as queue, COUNT(*) FROM queue.chunk WHERE status = 'processing'
   UNION ALL SELECT 'embed', COUNT(*) FROM queue.embed WHERE status = 'processing'
   UNION ALL SELECT 'graph', COUNT(*) FROM queue.graph WHERE status = 'processing';"
```

### 2. Stop Incoming Writes

```bash
# Stop auto-scraper
curl -X POST http://aio-01:5000/fleet/auto-deploy/stop

# Verify stopped
curl -s http://aio-01:5000/fleet/auto-deploy/status | jq
```

### 3. Create Backup

```bash
# Export PostgreSQL queue (to aio-01:/tmp/)
ssh claude@aio-01 "psql -h localhost -p 5433 -U sfloess -d learning -c \
  \"COPY (SELECT * FROM queue.store WHERE status = 'pending') \
   TO '/tmp/store_queue_backup_$(date +%Y%m%d_%H%M%S).csv' CSV HEADER;\""

# Verify backup
ssh claude@aio-01 "wc -l /tmp/store_queue_backup_*.csv"
# Should show ~3,027 lines (3,026 + 1 header)
```

### 4. Dry Run Migration (Preview)

```bash
# Preview what will be migrated
python3 scripts/migrate-pg-to-redis.py --dry-run
```

Expected output:
```
Checking prerequisites...
✓ PostgreSQL connection OK
✓ Redis connection OK
✓ Redis queues are empty
✓ Found 3,026 pending items in PostgreSQL
✓ Redis memory: 45.2 MB used
  Estimated needed: 5.9 MB

[DRY RUN] Starting migration...
Batch size: 1000

Batch 1 (offset 0)...
[DRY RUN] Would migrate 1000 items (offset 0)
  - ID 7636, priority 5 → redis:queue:store:medium
  - ID 7638, priority 5 → redis:queue:store:medium
  - ID 7637, priority 5 → redis:queue:store:medium
  ... and 997 more
...
```

### 5. Execute Migration

```bash
# Run migration (will prompt for confirmation)
python3 scripts/migrate-pg-to-redis.py

# Or with custom batch size
python3 scripts/migrate-pg-to-redis.py --batch-size 500
```

Expected output:
```
Checking prerequisites...
✓ All checks passed

WARNING: This will migrate data to Redis
Continue with migration? (yes/no): yes

Starting migration...
Batch 1 (offset 0)...
  Migrated: 1000 items
  Total progress: 1000/3026 (33.0%)

Batch 2 (offset 1000)...
  Migrated: 1000 items
  Total progress: 2000/3026 (66.1%)

Batch 3 (offset 2000)...
  Migrated: 1000 items
  Total progress: 3000/3026 (99.1%)

Batch 4 (offset 3000)...
  Migrated: 26 items
  Total progress: 3026/3026 (100.0%)

Running verification...
PostgreSQL pending: 3026
Redis total: 3026
  - high: 0
  - medium: 3026
  - low: 0
✓ Counts match!

Verifying sample items...
  ✓ Item 7636 verified
  ✓ Item 7638 verified
  ...

✓ Migration completed successfully!
```

### 6. Verify Migration

```bash
# Run verification only
python3 scripts/migrate-pg-to-redis.py --verify
```

### 7. Deploy Redis Workers

```bash
# Deploy workers to pull from Redis queues
./scripts/deploy-redis-workers.sh deploy

# Check worker status
./scripts/deploy-redis-workers.sh status

# View logs
./scripts/deploy-redis-workers.sh logs server-01
```

### 8. Monitor Queue Consumption

```bash
# Watch Redis queues drain
watch -n 5 'echo "Redis Queues:"; \
  redis-cli -h aio-01 LLEN redis:queue:store:high; \
  redis-cli -h aio-01 LLEN redis:queue:store:medium; \
  redis-cli -h aio-01 LLEN redis:queue:store:low'
```

### 9. Re-enable Auto-Scraper

```bash
# Once queue is draining successfully
curl -X POST http://aio-01:5000/fleet/auto-deploy/start

# Verify
curl -s http://aio-01:5000/fleet/auto-deploy/status | jq
```

---

## Rollback (If Needed)

### Emergency Rollback

```bash
# Run rollback script
./scripts/rollback-migration.sh
```

This will:
1. Stop Redis workers
2. Flush Redis queues
3. Restore PostgreSQL items to 'pending' status

### Manual Rollback Steps

```bash
# 1. Stop Redis workers
for worker in server-01 server-02 server-03 pi-01; do
  ssh claude@$worker "pkill -f 'redis-queue-worker.py'"
done

# 2. Flush Redis queues
ssh claude@aio-01 "redis-cli -h localhost DEL redis:queue:store:high redis:queue:store:medium redis:queue:store:low redis:idempotency:store"

# 3. Restore PostgreSQL status
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  UPDATE queue.store
  SET status = 'pending', migrated_to_redis = FALSE
  WHERE status = 'migrated';
"

# 4. Verify
psql -h aio-01 -p 5433 -U sfloess -d learning -t -c \
  "SELECT COUNT(*) FROM queue.store WHERE status = 'pending';"
# Should return: 3026
```

---

## Monitoring During Migration

### PostgreSQL Queue

```bash
# Watch pending count decrease
watch -n 5 "psql -h aio-01 -p 5433 -U sfloess -d learning -t -c \
  \"SELECT status, COUNT(*) FROM queue.store GROUP BY status;\""
```

### Redis Queues

```bash
# Watch Redis queues fill and then drain
watch -n 5 'for q in high medium low; do \
  echo "$q: $(redis-cli -h aio-01 LLEN redis:queue:store:$q)"; \
done'
```

### Worker Activity

```bash
# Check active workers
for worker in server-01 server-02 server-03 pi-01; do
  echo "$worker: $(ssh claude@$worker 'pgrep -f redis-queue-worker.py | wc -l') workers"
done
```

### Redis Memory

```bash
# Monitor memory usage
ssh claude@aio-01 "redis-cli -h localhost info memory | grep used_memory_human"
```

---

## Troubleshooting

### Migration Script Fails

**Error:** `PostgreSQL connection failed`
```bash
# Check PostgreSQL is running
ssh claude@aio-01 "systemctl status postgresql"

# Test connection
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1"
```

**Error:** `Redis connection failed`
```bash
# Check Redis is running
ssh claude@aio-01 "redis-cli -h localhost ping"
```

**Error:** `COUNT MISMATCH`
```bash
# Re-run migration (script is idempotent)
python3 scripts/migrate-pg-to-redis.py

# Or rollback and retry
./scripts/rollback-migration.sh
python3 scripts/migrate-pg-to-redis.py
```

### Workers Not Processing

**No items being processed:**
```bash
# Check workers are running
./scripts/deploy-redis-workers.sh status

# Check Redis queues exist
ssh claude@aio-01 "redis-cli -h localhost KEYS 'redis:queue:*'"

# Check worker logs
./scripts/deploy-redis-workers.sh logs server-01
```

**Workers stuck:**
```bash
# Restart workers
./scripts/deploy-redis-workers.sh stop
sleep 5
./scripts/deploy-redis-workers.sh deploy
```

### Processing Items Won't Complete

**Items stuck in 'processing' status:**
```bash
# Check how long they've been processing
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT id, status, started_at, NOW() - started_at as duration
  FROM queue.chunk
  WHERE status = 'processing'
  ORDER BY started_at;
"

# If >5 minutes, mark as dead_letter
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  UPDATE queue.chunk
  SET status = 'dead_letter', error = 'Stalled during migration'
  WHERE status = 'processing' AND started_at < NOW() - INTERVAL '5 minutes';
"
```

---

## Success Criteria

After migration, verify:

- [ ] PostgreSQL queue.store has 0 'pending' items
- [ ] PostgreSQL queue.store has 3,026 'migrated' items
- [ ] Redis queues were filled and are now draining
- [ ] Workers are actively processing from Redis
- [ ] No data loss (verification script passed)
- [ ] Auto-scraper re-enabled
- [ ] New items flow through Redis (not PostgreSQL)

---

## Post-Migration

### Archive PostgreSQL Data

```bash
# After successful migration (wait 1 week)
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  CREATE SCHEMA IF NOT EXISTS archive;
  
  CREATE TABLE archive.queue_store_2026_07_11 AS
  SELECT * FROM queue.store WHERE migrated_to_redis = TRUE;
  
  DELETE FROM queue.store WHERE migrated_to_redis = TRUE;
"
```

### Update Documentation

- [ ] Update `skills/rest_api_endpoints.md`
- [ ] Update worker deployment guides
- [ ] Document Redis queue naming conventions
- [ ] Add memory entry for migration completion

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python3 scripts/migrate-pg-to-redis.py --dry-run` | Preview migration |
| `python3 scripts/migrate-pg-to-redis.py` | Execute migration |
| `python3 scripts/migrate-pg-to-redis.py --verify` | Verify only |
| `./scripts/rollback-migration.sh` | Emergency rollback |
| `./scripts/deploy-redis-workers.sh deploy` | Deploy workers |
| `./scripts/deploy-redis-workers.sh status` | Check worker status |
| `curl -X POST http://aio-01:5000/fleet/auto-deploy/stop` | Stop auto-scraper |
| `curl -X POST http://aio-01:5000/fleet/auto-deploy/start` | Resume auto-scraper |

---

**Full Documentation:** `docs/POSTGRESQL_TO_REDIS_MIGRATION_STRATEGY.md`  
**Last Updated:** 2026-07-11
