# Architecture Summary

**Last Updated:** 2026-07-11  
**Purpose:** Quick reference for key architectural decisions

---

## System Overview

The distributed LLM orchestration framework consists of three major subsystems:

1. **Multi-AI Orchestration** - Route tasks to 204 free models, get consensus
2. **Web Scraper System** - Collect 10,000+ docs/hour from 60+ sources
3. **Continual Learning** - Thompson Sampling bandit improves routing over time

---

## Web Scraper Architecture (2026-07-10)

### Design Principles

**1. Scrape Then Process**

Separate fast scraping (network I/O) from slow embedding (CPU/API bound).

```
❌ WRONG: Scrape + embed synchronously (599 docs/hour)
✅ RIGHT: Scrape fast, process async (4,700 docs/hour, 7.8× improvement)
```

**2. Centralized Storage**

All data written to aio-01, not worker filesystems.

```
Workers → POST to aio-01:5000/store → aio-01 writes → Redis queue
```

**3. Fetch Full Content**

Scrapers fetch full page content (5000+ chars), not just RSS metadata (119 chars).

**4. Orchestrator Brings Up Workers**

Deploy via orchestrator API, not direct SSH.

```bash
# ❌ WRONG
ssh claude@server-01 "nohup python3 scraper.py &"

# ✅ RIGHT
curl -X POST http://aio-01:5000/fleet/deploy -d '{...}'
```

### Data Flow

```
1. Scraper fetches from web
2. POST to aio-01:5000/store/:source/:id
3. Orchestrator writes raw/{category}/{hash}.json
4. Queues path to Redis: store_queue
5. Returns 202 Accepted (fast!)

6. Store worker: Validate, dedupe
7. Chunk worker: Split → 500-1500 char chunks → PostgreSQL
8. Embed worker: Generate vectors → PostgreSQL
9. Graph worker: Create OrientDB relationships
```

### Performance

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Throughput | 599 docs/hr | 4,700 docs/hr | **7.8×** |
| Scrapers | 53 | 13 | More efficient |
| Bottleneck | Sync embedding | Async pipeline | Eliminated |

---

## Queue System Architecture

### Technology Choice: Redis

**Why Redis over PostgreSQL queues?**

| Feature | PostgreSQL | Redis |
|---------|------------|-------|
| Latency | 10-50ms | <1ms |
| Throughput | 1,000/sec | 100,000/sec |
| Complexity | Medium | Low |

**Decision:** Redis for speed, PostgreSQL for durability (hybrid approach).

### Four-Stage Pipeline

```
store_queue → chunk_queue → embed_queue → graph_queue
     ↓             ↓             ↓             ↓
  Validate      Split        Generate      Create
  Dedupe        text         vectors       graph
```

### Error Handling

1. **Dead Letter Queue (DLQ)** - Failed tasks moved to PostgreSQL
2. **Circuit Breaker** - Pause queue if error rate >50%
3. **Poison Message Detection** - Quarantine tasks with >3 failures
4. **Retry Logic** - Manual retry via API

### Scaling

**Recommended workers for 10,000 docs/hour:**

- 2 store workers (fast validation)
- 4 chunk workers (CPU-bound text splitting)
- 8 embed workers (API-bound, parallel calls)
- 2 graph workers (OrientDB bottleneck)

---

## Database Architecture

### PostgreSQL (aio-01:5433)

**Purpose:** Structured data + vector similarity search

**Tables:**
- `knowledge.scraped_data` - Chunked content with 384-dim vectors
- `learning.experiences` - Model performance history (128-dim)
- `workflow.executions` - Multi-AI workflow tracking (384-dim)
- `workflow.queue_audit` - Queue processing audit log
- `workflow.failed_tasks` - Dead letter queue

**Performance:**
- Vector similarity: 0.44ms (2× faster than ChromaDB)
- HNSW index: O(log n) search complexity

### Redis Sentinel (3 nodes)

**Purpose:** Fast queue operations + caching

**Keys:**
- `store_queue`, `chunk_queue`, `embed_queue`, `graph_queue` - Processing pipeline
- Rate limiting keys
- API cache keys

### OrientDB (aio-01:2424)

**Purpose:** Knowledge graph relationships

**Classes:**
- `Document` vertices (documents/chunks)
- `CitedBy`, `RelatedTo` edges (relationships)

---

## Deployment Architecture

### Fleet Topology

```
aio-01 (Orchestrator + Controller)
  ↓ SSH to workers
8 Workers:
  - server-01/02/03 (8C, 15-31GB)
  - laptop-01 (4C, 31GB)
  - desktop-ap, server-ap (1GB)
  - pi-01/02 (low-power, 1GB)
```

### Orchestrator Responsibilities

1. Route API requests to workers via SSH
2. Write scraped data to centralized storage
3. Manage Redis queues
4. Track worker health
5. Expose REST API (port 5000)

### Worker Responsibilities

**Scrapers:**
- Fetch from web sources
- POST to orchestrator API
- No local filesystem writes

**Queue Workers:**
- Process Redis queue tasks
- Write to PostgreSQL/OrientDB
- Handle errors → DLQ

---

## Key Endpoints

### Scraper Endpoints

```bash
# Store document (primary endpoint)
POST /store/:source/:id
Body: {url, category, title, content, metadata}
Response: 202 Accepted

# Check queue depth
GET /queue/stats
Response: {store_queue: 1234, chunk_queue: 567, ...}
```

### Fleet Management

```bash
# Deploy scrapers
POST /fleet/deploy
Body: {worker_type: "scraper", source: "wikipedia", count: 3}

# Deploy queue workers
POST /fleet/deploy-queue-workers
Body: {store_workers: 2, chunk_workers: 4, embed_workers: 8, graph_workers: 2}

# List running workers
GET /fleet/scrapers
GET /fleet/queue-workers
```

---

## Common Pitfalls

### ❌ Pitfall 1: Storing Only RSS Metadata

**Problem:** 73,000 stub files with 119-char snippets

**Solution:** Fetch full page content (5000+ chars)

### ❌ Pitfall 2: Synchronous Embedding

**Problem:** Embedding API calls block scraper (599 docs/hour)

**Solution:** Write to disk, queue for async processing (4,700 docs/hour)

### ❌ Pitfall 3: Direct Worker Deployment

**Problem:** Orchestrator doesn't track SSH-deployed workers

**Solution:** Use orchestrator API for deployment

### ❌ Pitfall 4: Local Filesystem Writes

**Problem:** Workers writing to their local disks

**Solution:** POST to orchestrator, which writes centrally

---

## Testing

### Integration Test

```bash
# Run full pipeline test
./scripts/test-scraper-pipeline.sh

# Verifies:
# 1. POST to /store endpoint
# 2. Raw file written
# 3. Queue processing
# 4. PostgreSQL chunks
# 5. Vector embeddings
```

### Unit Tests

```bash
npm test
```

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [SCRAPER_ARCHITECTURE.md](SCRAPER_ARCHITECTURE.md) | Scraper design, data flow, components |
| [QUEUE_SYSTEM_ARCHITECTURE.md](QUEUE_SYSTEM_ARCHITECTURE.md) | Redis queue design, workers, error handling |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Step-by-step deployment, verification |
| [API_REFERENCE_SCRAPERS.md](API_REFERENCE_SCRAPERS.md) | REST API endpoints, request/response formats |
| [README.md](../README.md) | Project overview, system architecture |

---

## Design Rationale

### Why Separate Scraping and Processing?

**Problem:** Mixing I/O-bound and CPU-bound operations causes the slowest to block everything.

**Solution:** Scrape fast (network I/O), process async (CPU/API bound).

**Result:** 7.8× throughput improvement.

### Why Centralized Storage?

**Problem:** Distributed filesystems have write conflicts, no single source of truth.

**Solution:** All scraped data written to aio-01, workers never write locally.

**Result:** No NFS write conflicts, easy monitoring, deduplication.

### Why Redis Over PostgreSQL Queues?

**Problem:** PostgreSQL queue latency is 10-50ms, which adds up at 10,000 docs/hour.

**Solution:** Redis queues (<1ms latency), PostgreSQL for audit log.

**Result:** 50× faster queue operations, durability via PostgreSQL.

### Why 4-Stage Pipeline?

**Problem:** Monolithic processing makes it hard to scale bottlenecks.

**Solution:** Separate validation, chunking, embedding, graph creation into stages.

**Result:** Scale each stage independently (2 store workers, 8 embed workers, etc.).

---

## Future Improvements

1. **Horizontal scaling** - Add more workers per stage
2. **Multi-region deployment** - Deploy scrapers globally
3. **Content deduplication** - MinHash LSH for near-duplicate detection
4. **Smart chunking** - Sentence/paragraph boundaries, not character count
5. **Incremental updates** - Re-scrape only changed content

---

**Last Updated:** 2026-07-11  
**Maintained by:** Development team
