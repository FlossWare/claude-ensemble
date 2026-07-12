# Deployment Guide

**Last Updated:** 2026-07-11  
**Target:** Web scraper + queue processing system  
**Fleet:** 8 worker nodes + 1 orchestrator (aio-01)

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Deployment Steps](#deployment-steps)
- [Verification](#verification)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Infrastructure

**Required nodes:**
- aio-01 (orchestrator + controller)
- 8 worker nodes (server-01/02/03, laptop-01, desktop-ap, server-ap, pi-01/02)

**Services running:**
- PostgreSQL (aio-01:5433)
- Redis Sentinel (3 nodes)
- OrientDB (aio-01:2424)
- Flask API (aio-01:5000)

### Software Dependencies

**On orchestrator (aio-01):**
```bash
# Python 3.13+
python3 --version

# Redis CLI
redis-cli --version

# PostgreSQL client
psql --version

# Flask + dependencies
pip3 install flask redis psycopg2-binary orientdb
```

**On workers:**
```bash
# Python 3.13+
# requests, beautifulsoup4, feedparser
pip3 install requests beautifulsoup4 feedparser redis psycopg2-binary
```

### File Structure

```
/mnt/aio-01/claude-orchestrator/
├── api/
│   ├── application.py          # Main Flask app
│   ├── embedding_fallback.py   # 5-provider fallback
│   └── requirements-orchestrator.txt
├── tools/
│   └── scrapers/
│       ├── wikipedia/
│       ├── arxiv/
│       ├── medium/
│       └── ...
├── scraped-data/
│   └── raw/                    # Raw JSON files
│       ├── programming/
│       ├── science/
│       └── ...
└── scripts/
    ├── redis-queue-worker.py
    └── deploy-redis-workers.sh
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ Deployment Flow                                         │
│                                                         │
│  1. Deploy scrapers (HTTP clients)                     │
│  2. Verify /store endpoint working                     │
│  3. Deploy queue workers (4 stages)                    │
│  4. Monitor queue depth + worker health                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Scrapers (13-30 workers)                                │
│  - Fetch from web                                       │
│  - POST to aio-01:5000/store                           │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│ Orchestrator API (aio-01:5000)                         │
│  - Write to /mnt/aio-01/.../scraped-data/raw/          │
│  - Queue to Redis                                       │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│ Queue Workers (16 total)                                │
│  - 2 store workers                                      │
│  - 4 chunk workers                                      │
│  - 8 embed workers                                      │
│  - 2 graph workers                                      │
└─────────────────────────────────────────────────────────┘
```

---

## Deployment Steps

### Step 1: Verify Prerequisites

```bash
# Check orchestrator API
curl http://aio-01:5000/health

# Check PostgreSQL
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1"

# Check Redis
redis-cli -h aio-01 ping

# Check OrientDB
curl http://aio-01:2424/

# Check NFS mount
ls /mnt/aio-01/claude-orchestrator/
```

### Step 2: Deploy Database Schema

```bash
# Create queue tables
psql -h aio-01 -p 5433 -U sfloess -d learning <<EOF
-- Queue audit log
CREATE TABLE IF NOT EXISTS workflow.queue_audit (
    id SERIAL PRIMARY KEY,
    queue_name VARCHAR(50),
    task_data JSONB,
    status VARCHAR(20),
    worker_node VARCHAR(50),
    queued_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error_message TEXT
);

-- Failed tasks (DLQ)
CREATE TABLE IF NOT EXISTS workflow.failed_tasks (
    id SERIAL PRIMARY KEY,
    queue_name VARCHAR(50),
    task_data JSONB,
    error_reason TEXT,
    failed_at TIMESTAMP DEFAULT NOW(),
    retry_count INTEGER DEFAULT 0
);

-- Quarantined tasks (poison messages)
CREATE TABLE IF NOT EXISTS workflow.quarantined_tasks (
    id SERIAL PRIMARY KEY,
    task_data JSONB,
    retry_count INTEGER,
    quarantined_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_queue_audit_status ON workflow.queue_audit(status);
CREATE INDEX IF NOT EXISTS idx_queue_audit_queue_name ON workflow.queue_audit(queue_name);
CREATE INDEX IF NOT EXISTS idx_failed_tasks_queue ON workflow.failed_tasks(queue_name);
EOF
```

### Step 3: Deploy Scrapers

**Use orchestrator API (not direct SSH):**

```bash
# Deploy Wikipedia scrapers (3 workers)
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "scraper",
    "source": "wikipedia",
    "categories": ["programming", "science", "technology"],
    "count": 3,
    "workers": ["server-01", "server-02", "laptop-01"]
  }'

# Deploy arXiv scrapers (2 workers)
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "scraper",
    "source": "arxiv",
    "categories": ["cs", "physics", "math"],
    "count": 2,
    "workers": ["server-03", "desktop-ap"]
  }'

# Deploy Medium scrapers (2 workers)
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "scraper",
    "source": "medium",
    "categories": ["programming", "ai", "devops"],
    "count": 2,
    "workers": ["pi-01", "pi-02"]
  }'

# Verify deployment
curl http://aio-01:5000/fleet/scrapers

# Expected response:
# {
#   "scrapers": [
#     {"node": "server-01", "source": "wikipedia", "pid": 12345, "status": "running"},
#     {"node": "server-02", "source": "wikipedia", "pid": 12346, "status": "running"},
#     ...
#   ],
#   "total": 7
# }
```

### Step 4: Verify /store Endpoint

```bash
# Test scraping flow
curl -X POST http://aio-01:5000/store/test/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/test",
    "source": "test",
    "category": "test",
    "title": "Test Document",
    "content": "This is test content for the scraper system. It should be at least 100 characters long to pass validation checks.",
    "metadata": {
      "author": "Test User",
      "published": "2026-07-11T10:00:00Z"
    }
  }'

# Expected response (202 Accepted):
# {
#   "stored": true,
#   "path": "/mnt/aio-01/.../raw/test/abc123.json",
#   "hash": "abc123",
#   "queued": true
# }

# Verify file written
ssh claude@aio-01 "cat /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/abc123.json"

# Check queue depth
redis-cli -h aio-01 llen store_queue

# Expected: 1 (or more if scrapers already running)
```

### Step 5: Deploy Queue Workers

**Use deployment script:**

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Deploy all queue workers
./scripts/deploy-redis-workers.sh

# Or deploy manually via API:
curl -X POST http://aio-01:5000/fleet/deploy-queue-workers \
  -H "Content-Type: application/json" \
  -d '{
    "store_workers": 2,
    "chunk_workers": 4,
    "embed_workers": 8,
    "graph_workers": 2
  }'

# Expected response:
# {
#   "deployed": {
#     "store": 2,
#     "chunk": 4,
#     "embed": 8,
#     "graph": 2
#   },
#   "workers": [
#     {"node": "server-01", "stage": "store", "pid": 23456},
#     {"node": "server-02", "stage": "store", "pid": 23457},
#     {"node": "server-01", "stage": "chunk", "pid": 23458},
#     ...
#   ]
# }
```

### Step 6: Monitor Initial Processing

```bash
# Watch queue depth
watch -n 2 'redis-cli -h aio-01 llen store_queue && redis-cli -h aio-01 llen chunk_queue && redis-cli -h aio-01 llen embed_queue && redis-cli -h aio-01 llen graph_queue'

# Expected behavior:
# store_queue: slowly decreasing
# chunk_queue: filling up as store workers process
# embed_queue: filling up as chunk workers process
# graph_queue: filling up as embed workers process

# Check worker logs
ssh claude@server-01 "tail -f /tmp/queue-worker-store.log"
ssh claude@server-02 "tail -f /tmp/queue-worker-chunk.log"

# Check PostgreSQL data
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT COUNT(*) FROM knowledge.scraped_data"

# Should increase over time as chunk workers insert data
```

---

## Verification

### End-to-End Test

```bash
# 1. POST test document
curl -X POST http://aio-01:5000/store/test/test123 \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/test123",
    "source": "test",
    "category": "test",
    "title": "End-to-End Test",
    "content": "This is a comprehensive end-to-end test of the scraper pipeline. The content must be long enough to generate multiple chunks during processing. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
    "metadata": {"test": true}
  }'

# 2. Wait 30 seconds for processing
sleep 30

# 3. Check raw file exists
ssh claude@aio-01 "test -f /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/test123.json && echo 'File exists' || echo 'File missing'"

# 4. Check chunks in PostgreSQL
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT chunk_index, LENGTH(chunk_text), embedding IS NOT NULL AS has_embedding
  FROM knowledge.scraped_data
  WHERE file_hash LIKE 'test123%'
  ORDER BY chunk_index
"

# Expected:
#  chunk_index | length | has_embedding
# -------------+--------+---------------
#            0 |    512 | t
#            1 |    487 | t

# 5. Test vector search
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT chunk_text, 1 - (embedding <=> 
    (SELECT embedding FROM knowledge.scraped_data WHERE file_hash LIKE 'test123%' LIMIT 1)
  ) AS similarity
  FROM knowledge.scraped_data
  WHERE file_hash LIKE 'test123%'
  ORDER BY similarity DESC
  LIMIT 3
"

# 6. Check OrientDB vertices
curl http://aio-01:2424/query/learning/sql/SELECT%20*%20FROM%20Document%20WHERE%20url_hash%20LIKE%20%27test123%25%27

# All steps should succeed
```

### Performance Test

```bash
# Deploy 20 scrapers
for i in {1..20}; do
  curl -X POST http://aio-01:5000/fleet/deploy \
    -H "Content-Type: application/json" \
    -d "{
      \"worker_type\": \"scraper\",
      \"source\": \"wikipedia\",
      \"count\": 1
    }"
done

# Monitor throughput
curl http://aio-01:5000/queue/stats

# Expected:
# {
#   "store_queue": 1200,  # ~10 min of scraping
#   "throughput_per_hour": 7200,
#   "estimated_completion": "15 minutes"
# }
```

---

## Monitoring

### Queue Metrics

```bash
# Queue depth
curl http://aio-01:5000/queue/stats

# Worker health
curl http://aio-01:5000/fleet/queue-workers

# Error rate
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT queue_name, 
         COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / COUNT(*) AS error_rate
  FROM workflow.queue_audit
  WHERE queued_at > NOW() - INTERVAL '1 hour'
  GROUP BY queue_name
"
```

### System Metrics

```bash
# Disk usage
ssh claude@aio-01 "du -sh /mnt/aio-01/claude-orchestrator/scraped-data/raw/"

# Database size
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT pg_size_pretty(pg_total_relation_size('knowledge.scraped_data'))
"

# Redis memory
redis-cli -h aio-01 info memory | grep used_memory_human
```

### Grafana Dashboards

**Access:** http://pi-02:3000

**Dashboards:**
- Scraper Throughput
- Queue Depth
- Worker Health
- Error Rate

---

## Troubleshooting

### Scrapers Not Running

```bash
# Check deployment
curl http://aio-01:5000/fleet/scrapers

# If empty, deploy manually:
ssh claude@server-01
cd /mnt/aio-01/claude-orchestrator/tools/scrapers/wikipedia
nohup python3 main.py > /tmp/wikipedia-scraper.log 2>&1 &

# Check logs
tail -f /tmp/wikipedia-scraper.log
```

### Queue Not Processing

```bash
# Check queue depth
redis-cli -h aio-01 llen store_queue

# If depth not decreasing, check workers:
curl http://aio-01:5000/fleet/queue-workers

# If no workers, deploy:
./scripts/deploy-redis-workers.sh

# Check worker logs
ssh claude@server-01 "tail -f /tmp/queue-worker-*.log"
```

### Embedding Failures

```bash
# Check failed tasks
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT error_reason, COUNT(*)
  FROM workflow.failed_tasks
  WHERE queue_name = 'embed_queue'
  GROUP BY error_reason
"

# Common issues:
# - API rate limit (wait, then retry)
# - Empty content (fix scraper)
# - Network timeout (increase timeout)

# Retry failed tasks
curl -X POST http://aio-01:5000/queue/retry-failed \
  -H "Content-Type: application/json" \
  -d '{"queue": "embed_queue", "hours": 1}'
```

### High Error Rate

```bash
# Check circuit breaker
curl http://aio-01:5000/queue/circuit-breaker/status

# If open, wait 5 minutes or manually close:
curl -X POST http://aio-01:5000/queue/circuit-breaker/reset
```

### Disk Full

```bash
# Check disk usage
ssh claude@aio-01 "df -h /mnt/aio-01"

# If >90%, clean old files:
ssh claude@aio-01 "find /mnt/aio-01/claude-orchestrator/scraped-data/raw/ -type f -mtime +30 -delete"

# Archive to server-ap:/exports/backups/
ssh claude@aio-01 "rsync -avz /mnt/aio-01/claude-orchestrator/scraped-data/raw/ server-ap:/exports/backups/scraped-data-$(date +%Y%m%d)/"
```

---

## Summary

**Deployment checklist:**

- [x] Verify prerequisites (PostgreSQL, Redis, OrientDB, API)
- [x] Deploy database schema (queue tables)
- [x] Deploy scrapers (orchestrator API)
- [x] Verify /store endpoint (test POST)
- [x] Deploy queue workers (4 stages)
- [x] Monitor initial processing (queue depth, logs)
- [x] Run end-to-end test (store → chunk → embed → graph)
- [x] Set up monitoring (Grafana dashboards)

**Expected throughput:**
- 13 scrapers: 4,700 docs/hour (current)
- 25 scrapers: 9,000 docs/hour (target)
- 30 scrapers: 10,800 docs/hour (max)

**Related:**
- [[SCRAPER_ARCHITECTURE.md]] - System architecture
- [[QUEUE_SYSTEM_ARCHITECTURE.md]] - Queue design
- [[API_REFERENCE.md]] - Orchestrator API
