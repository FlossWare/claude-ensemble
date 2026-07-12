# Scraper System API Reference

**Last Updated:** 2026-07-11  
**Base URL:** `http://aio-01:5000`  
**Version:** 1.0

---

## Table of Contents

- [Scraper Endpoints](#scraper-endpoints)
- [Queue Management](#queue-management)
- [Fleet Management](#fleet-management)
- [Monitoring](#monitoring)
- [Data Models](#data-models)

---

## Scraper Endpoints

### POST /store/:source/:id

Store scraped document to filesystem and queue for processing.

**This is the primary endpoint scrapers should use.**

**Parameters:**
- `source` (string, path) - Source system (e.g., "wikipedia", "arxiv", "medium")
- `id` (string, path) - Unique document identifier (hash or ID from source)

**Request Body:**

```json
{
  "url": "https://example.com/article",
  "source": "wikipedia",
  "category": "programming",
  "title": "How to Build Web Scrapers",
  "content": "Full article text (5000+ chars)...",
  "metadata": {
    "author": "Jane Doe",
    "published": "2026-07-11T10:00:00Z",
    "tags": ["scraping", "python", "web"]
  }
}
```

**Required Fields:**
- `url` (string) - Original URL of the document
- `category` (string) - Content category (e.g., "programming", "science")
- `content` (string) - Full text content (minimum 100 chars)

**Optional Fields:**
- `source` (string) - Source system (defaults to path param)
- `title` (string) - Document title
- `metadata` (object) - Additional metadata

**Response (202 Accepted):**

```json
{
  "stored": true,
  "path": "/mnt/aio-01/.../raw/programming/abc123def456.json",
  "hash": "abc123def456",
  "size": 1234,
  "queued": true,
  "queue": "store_queue"
}
```

**Error Responses:**

```json
// 400 Bad Request - Missing required field
{
  "error": "Missing required field: content"
}

// 400 Bad Request - Content too short
{
  "error": "Content must be at least 100 characters"
}

// 500 Internal Server Error
{
  "error": "Failed to write file: [details]"
}
```

**Example:**

```bash
curl -X POST http://aio-01:5000/store/wikipedia/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://en.wikipedia.org/wiki/Python",
    "category": "programming",
    "title": "Python (programming language)",
    "content": "Python is a high-level, general-purpose programming language..."
  }'
```

**Python Example:**

```python
import requests
import hashlib

def store_document(url, category, title, content, metadata=None):
    # Generate ID from URL
    doc_id = hashlib.md5(url.encode()).hexdigest()

    data = {
        "url": url,
        "category": category,
        "title": title,
        "content": content,
        "metadata": metadata or {}
    }

    response = requests.post(
        f"http://aio-01:5000/store/wikipedia/{doc_id}",
        json=data,
        timeout=10
    )

    return response.json()
```

---

### POST /web-content (Deprecated)

**⚠️ DEPRECATED:** Use `/store/:source/:id` instead.

This endpoint performs synchronous embedding, which is the bottleneck (599 docs/hour).

**Reason for deprecation:** Mixing scraping and embedding in one request is slow. Use the async pipeline instead.

---

## Queue Management

### GET /queue/stats

Get queue depth and processing metrics.

**Response (200 OK):**

```json
{
  "queues": {
    "store_queue": 1234,
    "chunk_queue": 567,
    "embed_queue": 89,
    "graph_queue": 12
  },
  "total_pending": 1902,
  "throughput_per_hour": 4700,
  "estimated_completion_minutes": 24
}
```

**Example:**

```bash
curl http://aio-01:5000/queue/stats
```

---

### POST /queue/retry-failed

Retry failed tasks from DLQ.

**Request Body:**

```json
{
  "queue": "embed_queue",  // Optional: specific queue
  "hours": 1,              // Optional: only retry from last N hours
  "limit": 100             // Optional: max tasks to retry
}
```

**Response (200 OK):**

```json
{
  "retried": 42,
  "failed": 3,
  "errors": [
    "Task 123: Invalid JSON"
  ]
}
```

**Example:**

```bash
curl -X POST http://aio-01:5000/queue/retry-failed \
  -H "Content-Type: application/json" \
  -d '{"queue": "embed_queue", "hours": 1}'
```

---

### GET /queue/circuit-breaker/status

Check circuit breaker status for each queue.

**Response (200 OK):**

```json
{
  "store_queue": "CLOSED",
  "chunk_queue": "CLOSED",
  "embed_queue": "OPEN",     // High error rate, paused
  "graph_queue": "HALF_OPEN"  // Testing if errors resolved
}
```

---

### POST /queue/circuit-breaker/reset

Manually reset circuit breaker for a queue.

**Request Body:**

```json
{
  "queue": "embed_queue"
}
```

**Response (200 OK):**

```json
{
  "reset": true,
  "queue": "embed_queue",
  "new_state": "CLOSED"
}
```

---

## Fleet Management

### POST /fleet/deploy

Deploy scrapers to worker nodes.

**Request Body:**

```json
{
  "worker_type": "scraper",
  "source": "wikipedia",
  "categories": ["programming", "science", "technology"],
  "count": 3,
  "workers": ["server-01", "server-02", "laptop-01"]  // Optional
}
```

**Response (200 OK):**

```json
{
  "deployed": 3,
  "workers": [
    {
      "node": "server-01",
      "source": "wikipedia",
      "pid": 12345,
      "status": "running",
      "log_file": "/tmp/scraper-wikipedia-12345.log"
    },
    {
      "node": "server-02",
      "source": "wikipedia",
      "pid": 12346,
      "status": "running",
      "log_file": "/tmp/scraper-wikipedia-12346.log"
    },
    {
      "node": "laptop-01",
      "source": "wikipedia",
      "pid": 12347,
      "status": "running",
      "log_file": "/tmp/scraper-wikipedia-12347.log"
    }
  ]
}
```

**Example:**

```bash
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "scraper",
    "source": "wikipedia",
    "count": 3
  }'
```

---

### POST /fleet/deploy-queue-workers

Deploy queue processing workers.

**Request Body:**

```json
{
  "store_workers": 2,
  "chunk_workers": 4,
  "embed_workers": 8,
  "graph_workers": 2
}
```

**Response (200 OK):**

```json
{
  "deployed": {
    "store": 2,
    "chunk": 4,
    "embed": 8,
    "graph": 2
  },
  "workers": [
    {
      "node": "server-01",
      "stage": "store",
      "pid": 23456,
      "log_file": "/tmp/queue-worker-store-23456.log"
    },
    // ... more workers
  ],
  "total": 16
}
```

**Example:**

```bash
curl -X POST http://aio-01:5000/fleet/deploy-queue-workers \
  -H "Content-Type: application/json" \
  -d '{
    "store_workers": 2,
    "chunk_workers": 4,
    "embed_workers": 8,
    "graph_workers": 2
  }'
```

---

### GET /fleet/scrapers

List all running scrapers.

**Response (200 OK):**

```json
{
  "scrapers": [
    {
      "node": "server-01",
      "source": "wikipedia",
      "pid": 12345,
      "status": "running",
      "uptime": "2h 15m",
      "docs_scraped": 523
    },
    {
      "node": "server-02",
      "source": "arxiv",
      "pid": 12346,
      "status": "running",
      "uptime": "1h 45m",
      "docs_scraped": 342
    }
  ],
  "total": 13,
  "total_docs_scraped": 4523
}
```

---

### GET /fleet/queue-workers

List all running queue workers.

**Response (200 OK):**

```json
{
  "workers": [
    {
      "node": "server-01",
      "stage": "store",
      "pid": 23456,
      "status": "running",
      "tasks_processed": 1523,
      "uptime": "2h 30m"
    },
    {
      "node": "server-02",
      "stage": "chunk",
      "pid": 23457,
      "status": "running",
      "tasks_processed": 1201,
      "uptime": "2h 30m"
    }
  ],
  "total": 16,
  "by_stage": {
    "store": 2,
    "chunk": 4,
    "embed": 8,
    "graph": 2
  }
}
```

---

### DELETE /fleet/worker/:node/:pid

Stop a specific worker.

**Parameters:**
- `node` (string, path) - Worker node (e.g., "server-01")
- `pid` (integer, path) - Process ID

**Response (200 OK):**

```json
{
  "stopped": true,
  "node": "server-01",
  "pid": 12345
}
```

**Example:**

```bash
curl -X DELETE http://aio-01:5000/fleet/worker/server-01/12345
```

---

## Monitoring

### GET /health

Health check endpoint.

**Response (200 OK):**

```json
{
  "status": "healthy",
  "services": {
    "postgresql": "up",
    "redis": "up",
    "orientdb": "up",
    "nfs": "up"
  },
  "uptime": "3d 12h 45m"
}
```

---

### GET /metrics

Prometheus metrics endpoint.

**Response (200 OK):**

```
# HELP scraper_docs_total Total documents scraped
# TYPE scraper_docs_total counter
scraper_docs_total{source="wikipedia"} 1234
scraper_docs_total{source="arxiv"} 567

# HELP queue_depth Current queue depth
# TYPE queue_depth gauge
queue_depth{queue="store_queue"} 1234
queue_depth{queue="chunk_queue"} 567
queue_depth{queue="embed_queue"} 89
queue_depth{queue="graph_queue"} 12

# HELP worker_tasks_processed_total Tasks processed by workers
# TYPE worker_tasks_processed_total counter
worker_tasks_processed_total{stage="store"} 5432
worker_tasks_processed_total{stage="chunk"} 4321
worker_tasks_processed_total{stage="embed"} 3210
worker_tasks_processed_total{stage="graph"} 2109
```

---

## Data Models

### Document (Raw JSON)

Stored in `/mnt/aio-01/claude-orchestrator/scraped-data/raw/{category}/{hash}.json`

```json
{
  "url": "https://example.com/article",
  "source": "wikipedia",
  "category": "programming",
  "title": "How to Build Web Scrapers",
  "content": "Full article text...",
  "metadata": {
    "author": "Jane Doe",
    "published": "2026-07-11T10:00:00Z",
    "tags": ["scraping", "python", "web"]
  },
  "scraped_at": "2026-07-11T14:30:00Z",
  "hash": "abc123def456"
}
```

---

### Chunk (PostgreSQL)

Table: `knowledge.scraped_data`

```sql
CREATE TABLE knowledge.scraped_data (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100),
    source_file TEXT,          -- Path to raw JSON
    file_hash VARCHAR(64),     -- md5(url)
    chunk_index INTEGER,       -- 0, 1, 2, ...
    chunk_text TEXT,           -- 500-1500 chars
    embedding vector(384),     -- pgvector
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example:**

```
id  | category    | file_hash       | chunk_index | chunk_text           | embedding
----|-------------|-----------------|-------------|----------------------|----------
123 | programming | abc123def456    | 0           | "Python is a high-..." | [0.123, ...]
124 | programming | abc123def456    | 1           | "...level program..." | [0.456, ...]
```

---

### Queue Task (Redis)

Stored in Redis lists: `store_queue`, `chunk_queue`, `embed_queue`, `graph_queue`

**Store/Chunk/Graph task:**

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

**Embed task:**

```json
{
  "chunk_id": 123,
  "chunk_text": "Python is a high-level programming language...",
  "url_hash": "abc123def456",
  "category": "programming",
  "queued_at": "2026-07-11T10:30:15Z"
}
```

---

### Audit Log (PostgreSQL)

Table: `workflow.queue_audit`

```sql
CREATE TABLE workflow.queue_audit (
    id SERIAL PRIMARY KEY,
    queue_name VARCHAR(50),
    task_data JSONB,
    status VARCHAR(20),        -- 'queued', 'processing', 'completed', 'failed'
    worker_node VARCHAR(50),
    queued_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error_message TEXT
);
```

---

### Failed Task (PostgreSQL DLQ)

Table: `workflow.failed_tasks`

```sql
CREATE TABLE workflow.failed_tasks (
    id SERIAL PRIMARY KEY,
    queue_name VARCHAR(50),
    task_data JSONB,
    error_reason TEXT,
    failed_at TIMESTAMP DEFAULT NOW(),
    retry_count INTEGER DEFAULT 0
);
```

---

## Rate Limits

| Endpoint | Rate Limit | Notes |
|----------|------------|-------|
| POST /store | 1000/min | Per source |
| GET /queue/stats | 60/min | - |
| POST /fleet/deploy | 10/min | - |
| GET /metrics | 120/min | Prometheus scrape |

**Rate limit exceeded response (429):**

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Authentication

**Current:** No authentication required (internal network only)

**Future:** API key authentication planned

```bash
curl -X POST http://aio-01:5000/store/wikipedia/abc123 \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '...'
```

---

## Error Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Success |
| 202 | Accepted | Async operation queued |
| 400 | Bad Request | Missing field, invalid JSON |
| 404 | Not Found | Invalid endpoint |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Database down, filesystem error |
| 503 | Service Unavailable | Redis down, queue full |

---

## Related Documentation

- [[SCRAPER_ARCHITECTURE.md]] - System architecture
- [[QUEUE_SYSTEM_ARCHITECTURE.md]] - Queue design
- [[DEPLOYMENT_GUIDE.md]] - Deployment instructions
- [[README.md]] - Project overview
