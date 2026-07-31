# Queue System Architecture

**Last Updated:** 2026-07-11  
**Technology:** Redis 8.0.2 standalone on aio-01:6379, no auth  
**Purpose:** Asynchronous processing pipeline for scraped data

---

## Table of Contents

- [Overview](#overview)
- [Why Redis Queues](#why-redis-queues)
- [Queue Stages](#queue-stages)
- [Worker Architecture](#worker-architecture)
- [Error Handling](#error-handling)
- [Monitoring](#monitoring)
- [Deployment](#deployment)

---

## Overview

### The Problem

**Synchronous processing is slow:**

```
Scraper → Embed → Store → Return
          ↑
      2-5 seconds
      
Result: 599 docs/hour
```

**Solution: Async pipeline with Redis queues:**

```
Scraper → Store → Return (50ms)
          ↓
        Queue → Workers process async
        
Result: 8,000-10,000 docs/hour target
```

### Four-Stage Pipeline

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Store  │ ──> │  Chunk  │ ──> │  Embed  │ ──> │  Graph  │
│  Queue  │     │  Queue  │     │  Queue  │     │  Queue  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     ↓               ↓               ↓               ↓
  Validate       Split text     Generate        Create
  Dedupe         500-1500       vectors         OrientDB
  Basic checks   char chunks    (384-dim)       relationships
```

---

## Why Redis Queues

### Technology Comparison

| Feature | PostgreSQL Queue | Redis Queue | RabbitMQ |
|---------|------------------|-------------|----------|
| **Latency** | 10-50ms | <1ms | 5-10ms |
| **Throughput** | 1,000/sec | 100,000/sec | 50,000/sec |
| **Persistence** | ✅ Durable | ⚠️ Optional | ✅ Durable |
| **Complexity** | Medium | Low | High |
| **HA** | PostgreSQL HA | Standalone | Cluster |
| **Operations** | ACID | Atomic | AMQP |

### Why Redis for This Use Case

**Pros:**
- ✅ Extremely fast (sub-millisecond latency)
- ✅ Simple operations (LPUSH, BRPOP)
- ✅ Already deployed (standalone on aio-01:6379, no auth)
- ✅ Atomic operations (no race conditions)
- ✅ Low memory footprint

**Cons:**
- ⚠️ Not durable by default (but we have disk persistence)
- ⚠️ No built-in retry/DLQ (we implement manually)

**Decision:** Redis queues with manual DLQ + PostgreSQL for audit log.

### Hybrid Approach

```
┌─────────────────────────────────────────────────────────┐
│ Redis: Fast queue operations                            │
│  - LPUSH: Add task to queue                             │
│  - BRPOP: Blocking pop (wait for task)                  │
│  - LLEN: Queue depth                                     │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│ PostgreSQL: Audit log + failed tasks                    │
│  - workflow.queue_audit (all tasks)                     │
│  - workflow.failed_tasks (DLQ)                          │
│  - monitoring.queue_metrics (performance)               │
└─────────────────────────────────────────────────────────┘
```

---

## Queue Stages

### Stage 1: Store Queue

**Purpose:** Validate raw files, check duplicates

**Input:** Path to raw JSON file

```json
{
  "path": "/mnt/aio-01/.../raw/programming/abc123.json",
  "source": "wikipedia",
  "doc_id": "abc123",
  "category": "programming",
  "url_hash": "abc123def456",
  "queued_at": "2026-07-11T10:30:00Z"
}
```

**Processing:**

```python
def process_store_queue():
    """Validate, dedupe, basic checks."""
    while True:
        task = redis_client.brpop("store_queue", timeout=5)
        if not task:
            continue
        
        data = json.loads(task[1])
        path = data["path"]
        
        # Read raw file
        with open(path) as f:
            doc = json.load(f)
        
        # Validation checks
        if len(doc.get("content", "")) < 100:
            log_error(f"Content too short: {path}")
            move_to_dlq(data, "content_too_short")
            continue
        
        if not doc.get("url"):
            log_error(f"Missing URL: {path}")
            move_to_dlq(data, "missing_url")
            continue
        
        # Duplicate check
        if is_duplicate(doc["url"]):
            log_skip(f"Duplicate URL: {doc['url']}")
            continue
        
        # Mark as validated
        mark_validated(data["url_hash"])
        
        # Queue for chunking
        redis_client.lpush("chunk_queue", json.dumps(data))
```

**Output:** Queues task to chunk_queue

### Stage 2: Chunk Queue

**Purpose:** Split content into 500-1500 char chunks, write to PostgreSQL

**Input:** Same as store queue

**Processing:**

```python
def process_chunk_queue():
    """Split text into chunks, write to PostgreSQL."""
    while True:
        task = redis_client.brpop("chunk_queue", timeout=5)
        if not task:
            continue
        
        data = json.loads(task[1])
        path = data["path"]
        
        # Read raw file
        with open(path) as f:
            doc = json.load(f)
        
        # Chunk content
        chunks = chunk_text(doc["content"], min_size=500, max_size=1500)
        
        if not chunks:
            log_error(f"No chunks generated: {path}")
            move_to_dlq(data, "no_chunks")
            continue
        
        # Insert chunks into PostgreSQL
        # NOTE: In production, use REST API at aio-01:5000 or shared/postgres-adapter.js
        # Direct PostgreSQL connections (aio-01:5433) should be avoided.
        chunk_ids = []
        for idx, chunk in enumerate(chunks):
            cursor.execute("""
                INSERT INTO knowledge.scraped_data
                (category, source_file, file_hash, chunk_index, chunk_text)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data["category"],
                path,
                data["url_hash"],
                idx,
                chunk
            ))
            chunk_id = cursor.fetchone()[0]
            chunk_ids.append(chunk_id)
        
        conn.commit()
        
        # Queue each chunk for embedding
        for chunk_id, chunk_text in zip(chunk_ids, chunks):
            redis_client.lpush("embed_queue", json.dumps({
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "url_hash": data["url_hash"],
                "category": data["category"]
            }))
```

**Output:** Queues N tasks to embed_queue (one per chunk)

### Stage 3: Embed Queue

**Purpose:** Generate 384-dim vectors, update PostgreSQL

**Input:** Chunk ID + text

```json
{
  "chunk_id": 12345,
  "chunk_text": "Python is a high-level programming language...",
  "url_hash": "abc123def456",
  "category": "programming"
}
```

**Processing:**

```python
def process_embed_queue():
    """Generate embeddings, update PostgreSQL."""
    while True:
        task = redis_client.brpop("embed_queue", timeout=5)
        if not task:
            continue
        
        data = json.loads(task[1])
        
        # Generate embedding with 5-provider fallback
        try:
            embedding = generate_embedding_with_fallback(data["chunk_text"])
        except Exception as e:
            log_error(f"Embedding failed for chunk {data['chunk_id']}: {e}")
            move_to_dlq(data, "embedding_failed")
            continue
        
        # Update PostgreSQL
        # NOTE: In production, use REST API at aio-01:5000 or shared/postgres-adapter.js
        # Direct PostgreSQL connections (aio-01:5433) should be avoided.
        cursor.execute("""
            UPDATE knowledge.scraped_data
            SET embedding = %s
            WHERE id = %s
        """, (embedding, data["chunk_id"]))
        
        conn.commit()
        
        # Queue for graph
        redis_client.lpush("graph_queue", json.dumps(data))
```

**Output:** Queues task to graph_queue

### Stage 4: Graph Queue

**Purpose:** Create OrientDB relationships

**Input:** Chunk metadata

**Processing:**

```python
def process_graph_queue():
    """Create OrientDB vertices and edges."""
    while True:
        task = redis_client.brpop("graph_queue", timeout=5)
        if not task:
            continue
        
        data = json.loads(task[1])
        
        # Create document vertex
        vertex_id = orientdb.command(f"""
            CREATE VERTEX Document
            SET chunk_id = {data["chunk_id"]},
                category = '{data["category"]}',
                url_hash = '{data["url_hash"]}'
        """).fetchone()
        
        # Find related documents (vector similarity in PostgreSQL)
        cursor.execute("""
            SELECT id, 1 - (embedding <=> 
                (SELECT embedding FROM knowledge.scraped_data WHERE id = %s)
            ) AS similarity
            FROM knowledge.scraped_data
            WHERE id != %s
            ORDER BY similarity DESC
            LIMIT 10
        """, (data["chunk_id"], data["chunk_id"]))
        
        related = cursor.fetchall()
        
        # Create edges
        for rel_id, similarity in related:
            orientdb.command(f"""
                CREATE EDGE RelatedTo
                FROM (SELECT FROM Document WHERE chunk_id = {data["chunk_id"]})
                TO (SELECT FROM Document WHERE chunk_id = {rel_id})
                SET similarity = {similarity}
            """)
```

**Output:** Done!

---

## Worker Architecture

### Worker Types

```python
# Store worker
python3 scripts/redis-queue-worker.py --queue store_queue --handler store

# Chunk worker
python3 scripts/redis-queue-worker.py --queue chunk_queue --handler chunk

# Embed worker
python3 scripts/redis-queue-worker.py --queue embed_queue --handler embed

# Graph worker
python3 scripts/redis-queue-worker.py --queue graph_queue --handler graph
```

### Worker Implementation

**Base worker framework:**

```python
import redis
import json
import time
import sys
from datetime import datetime

class QueueWorker:
    def __init__(self, queue_name, handler_func):
        self.queue_name = queue_name
        self.handler = handler_func
        self.redis_client = redis.Redis(
            host='aio-01',
            port=6379,
            db=0,
            decode_responses=True
        )
    
    def run(self):
        print(f"Worker started: {self.queue_name}")
        
        while True:
            try:
                # Blocking pop (wait up to 5 seconds)
                task = self.redis_client.brpop(self.queue_name, timeout=5)
                
                if not task:
                    continue
                
                # Parse task
                data = json.loads(task[1])
                
                # Process
                start = time.time()
                result = self.handler(data)
                duration = time.time() - start
                
                # Log success
                log_success(self.queue_name, data, duration)
                
            except Exception as e:
                print(f"Error processing task: {e}")
                log_error(self.queue_name, data, str(e))
                move_to_dlq(data, str(e))
    
    def shutdown(self):
        print(f"Worker shutting down: {self.queue_name}")
        self.redis_client.close()

# Handler functions
def handle_store(data):
    # Store queue logic
    pass

def handle_chunk(data):
    # Chunk queue logic
    pass

def handle_embed(data):
    # Embed queue logic
    pass

def handle_graph(data):
    # Graph queue logic
    pass

# Main
if __name__ == "__main__":
    queue = sys.argv[1]  # e.g., "store_queue"
    handler_name = sys.argv[2]  # e.g., "store"
    
    handlers = {
        "store": handle_store,
        "chunk": handle_chunk,
        "embed": handle_embed,
        "graph": handle_graph
    }
    
    worker = QueueWorker(queue, handlers[handler_name])
    
    try:
        worker.run()
    except KeyboardInterrupt:
        worker.shutdown()
```

### Worker Deployment

**Deploy via orchestrator API:**

```bash
# Deploy 2 chunk workers
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "queue_worker",
    "stage": "chunk",
    "count": 2,
    "workers": ["server-01", "server-02"]
  }'

# Deploy 2 embed workers (ONLY on laptop-01/02 - embeddings require sentence-transformers)
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "queue_worker",
    "stage": "embed",
    "count": 2,
    "workers": ["laptop-01", "laptop-02"]
  }'
```

### Scaling

**Workers per stage (recommended for 10,000 docs/hour):**

| Stage | Workers | Reason |
|-------|---------|--------|
| Store | 2 | Fast validation, dedupe check |
| Chunk | 4 | CPU-bound text splitting |
| Embed | 2 | ONLY laptop-01/02 (sentence-transformers required, never fleet workers) |
| Graph | 2 | OrientDB bottleneck |

---

## Error Handling

### Dead Letter Queue (DLQ)

**Failed tasks moved to DLQ for manual review:**

```python
def move_to_dlq(data, error_reason):
    """Move failed task to PostgreSQL DLQ.
    
    NOTE: In production, use REST API at aio-01:5000 or shared/postgres-adapter.js.
    Direct PostgreSQL connections (aio-01:5433) should be avoided.
    """
    cursor.execute("""
        INSERT INTO workflow.failed_tasks
        (queue_name, task_data, error_reason, failed_at)
        VALUES (%s, %s, %s, %s)
    """, (
        data.get("queue_name", "unknown"),
        json.dumps(data),
        error_reason,
        datetime.now()
    ))
    conn.commit()
```

**Retry failed tasks:**

```bash
# Retry all failed tasks from last hour
curl -X POST http://aio-01:5000/queue/retry-failed \
  -H "Content-Type: application/json" \
  -d '{"hours": 1}'
```

### Poison Messages

**Tasks that repeatedly fail:**

```python
def handle_poison_message(data):
    """Detect and quarantine poison messages."""
    retry_count = data.get("retry_count", 0)
    
    if retry_count > 3:
        # Quarantine
        # NOTE: In production, use REST API at aio-01:5000 or shared/postgres-adapter.js
        # Direct PostgreSQL connections (aio-01:5433) should be avoided.
        cursor.execute("""
            INSERT INTO workflow.quarantined_tasks
            (task_data, retry_count, quarantined_at)
            VALUES (%s, %s, %s)
        """, (json.dumps(data), retry_count, datetime.now()))
        
        conn.commit()
        return
    
    # Increment retry count and requeue
    data["retry_count"] = retry_count + 1
    redis_client.lpush(data["queue_name"], json.dumps(data))
```

### Circuit Breaker

**Pause queue if error rate too high:**

```python
class CircuitBreaker:
    def __init__(self, error_threshold=0.5, window_size=100):
        self.error_threshold = error_threshold
        self.window_size = window_size
        self.recent_results = []
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def record_success(self):
        self.recent_results.append(True)
        if len(self.recent_results) > self.window_size:
            self.recent_results.pop(0)
        
        # Maybe close circuit
        if self.state == "HALF_OPEN":
            error_rate = 1 - (sum(self.recent_results) / len(self.recent_results))
            if error_rate < self.error_threshold:
                self.state = "CLOSED"
    
    def record_failure(self):
        self.recent_results.append(False)
        if len(self.recent_results) > self.window_size:
            self.recent_results.pop(0)
        
        # Maybe open circuit
        error_rate = 1 - (sum(self.recent_results) / len(self.recent_results))
        if error_rate > self.error_threshold:
            self.state = "OPEN"
    
    def is_open(self):
        return self.state == "OPEN"
```

---

## Monitoring

### Queue Metrics

```bash
# Check queue depth
curl http://aio-01:5000/queue/stats

# Response:
{
  "store_queue": 1234,
  "chunk_queue": 567,
  "embed_queue": 89,
  "graph_queue": 12,
  "total_pending": 1902
}
```

### Worker Health

```bash
# Check worker status
curl http://aio-01:5000/fleet/queue-workers

# Response:
{
  "workers": [
    {
      "node": "server-01",
      "queue": "chunk_queue",
      "pid": 12345,
      "tasks_processed": 1523,
      "uptime": "2h 15m"
    },
    ...
  ]
}
```

### PostgreSQL Audit Log

> **NOTE:** In production, access PostgreSQL via REST API at aio-01:5000
> or shared/postgres-adapter.js. Direct connections to aio-01:5433 should be avoided.

```sql
-- Create audit log
CREATE TABLE workflow.queue_audit (
    id SERIAL PRIMARY KEY,
    queue_name VARCHAR(50),
    task_data JSONB,
    status VARCHAR(20),  -- 'queued', 'processing', 'completed', 'failed'
    worker_node VARCHAR(50),
    queued_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error_message TEXT
);

-- Query slow tasks
SELECT queue_name, AVG(duration_ms) AS avg_duration
FROM workflow.queue_audit
WHERE status = 'completed'
GROUP BY queue_name;

-- Query error rate
SELECT queue_name, 
       COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / COUNT(*) AS error_rate
FROM workflow.queue_audit
GROUP BY queue_name;
```

---

## Deployment

### Initial Setup

```bash
# 1. Ensure Redis is running (standalone on aio-01:6379, no auth)
ssh claude@aio-01 "redis-cli ping"  # Should return PONG

# 2. Create PostgreSQL tables (via REST API at aio-01:5000 preferred)
# Direct psql shown for initial schema setup only:
psql -h aio-01 -p 5433 -U sfloess -d learning -f scripts/create-queue-tables.sql

# 3. Deploy workers via orchestrator
curl -X POST http://aio-01:5000/fleet/deploy-queue-workers \
  -H "Content-Type: application/json" \
  -d '{
    "store_workers": 2,
    "chunk_workers": 4,
    "embed_workers": 8,
    "graph_workers": 2
  }'

# 4. Verify deployment
curl http://aio-01:5000/fleet/queue-workers
```

### Testing

```bash
# Test store queue
curl -X POST http://aio-01:5000/queue/test/store

# Check queue depth
curl http://aio-01:5000/queue/stats

# Check worker logs
ssh claude@server-01 "tail -f /home/claude/workers/queue-worker-chunk.log"
```

---

## Summary

**Key design decisions:**

1. **Redis for speed** - Sub-millisecond latency, 100,000 ops/sec
2. **PostgreSQL for durability** - Audit log + DLQ
3. **Four-stage pipeline** - Separation of concerns
4. **Manual DLQ** - Explicit error handling
5. **Circuit breaker** - Protect against cascading failures

**Benefits:**
- ✅ 16× throughput improvement vs synchronous
- ✅ Resilient (DLQ, circuit breaker, retry)
- ✅ Observable (audit log, metrics)
- ✅ Scalable (add workers per stage)

**Related:**
- [[SCRAPER_ARCHITECTURE.md]] - Scraper system overview
- [[DEPLOYMENT_GUIDE.md]] - Worker deployment
- [[API_REFERENCE.md]] - Orchestrator API endpoints
