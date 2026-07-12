# Web Scraper Architecture

**Last Updated:** 2026-07-11  
**Status:** Production (as of 2026-07-10)  
**Throughput:** 4,700 docs/hour (13 scrapers operational)

---

## Table of Contents

- [Design Principles](#design-principles)
- [Architecture Overview](#architecture-overview)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Queue System](#queue-system)
- [Deployment](#deployment)
- [Performance](#performance)
- [Common Pitfalls](#common-pitfalls)

---

## Design Principles

### 1. **Separation of Concerns: Scrape Then Process**

**Core principle:** Separate fast scraping from slow processing.

```
❌ WRONG: Scrape + embed synchronously (bottleneck)
Scraper → POST /web-content → embed (SLOW) → PostgreSQL
                               ↑ 599 docs/hour

✅ RIGHT: Scrape fast, process async
Scraper → POST /store → write to disk → return 202
                        ↓
          Queue workers process async (8,000-10,000 docs/hour)
```

**Why this matters:**
- Scraping is network I/O bound (fast)
- Embedding is CPU/API bound (slow)
- Mixing them makes the slowest operation block everything

### 2. **Centralized Storage**

**All scraped data written to aio-01, never to local worker filesystems.**

```
┌─────────────────────────────────────────────────────────┐
│ Workers (server-01, server-02, laptop-01, pi-01, etc.) │
│                                                         │
│  Scraper process:                                      │
│   1. Download from web (Wikipedia, arXiv, etc.)       │
│   2. HTTP POST to http://aio-01:5000/store            │
│   3. Wait for 202 response                             │
│   4. Continue scraping                                 │
│                                                         │
│  ❌ NO local filesystem writes                         │
│  ✅ Only HTTP POST to aio-01                           │
└─────────────────────────────────────────────────────────┘
                     ↓ HTTP POST
┌─────────────────────────────────────────────────────────┐
│ aio-01 (Orchestrator)                                   │
│                                                         │
│  REST API (port 5000):                                 │
│   1. Generate hash = md5(url)                         │
│   2. Extract category from JSON                       │
│   3. Write to filesystem:                             │
│      /mnt/aio-01/claude-orchestrator/scraped-data/raw/│
│      {category}/{hash}.json                           │
│   4. Queue path to Redis queue                        │
│   5. Return 202 Accepted                              │
└─────────────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ Single source of truth
- ✅ No NFS write conflicts
- ✅ Easy to monitor (one endpoint)
- ✅ Network-agnostic (workers can be anywhere)
- ✅ Deduplication via hash

### 3. **Orchestrator Brings Up Workers**

**Never deploy workers via direct SSH. Use orchestrator API.**

```bash
# ❌ WRONG: Direct SSH deployment
ssh claude@server-01 "nohup python3 scraper.py &"

# ✅ RIGHT: Orchestrator API deployment
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "scraper",
    "source": "wikipedia",
    "count": 3
  }'
```

**Why:**
- Orchestrator tracks what's running where
- Centralized management
- Load balancing
- Health monitoring

### 4. **Fetch Full Page Content**

**Scrapers must fetch FULL page content from each URL, not just RSS metadata.**

```python
# ❌ WRONG: Storing only RSS metadata
data = {
    "title": feed_entry.title,
    "url": feed_entry.link,
    "snippet": feed_entry.summary[:200],  # 119-char stub
    "content": ""  # EMPTY!
}

# ✅ RIGHT: Fetch full page content
import requests
from bs4 import BeautifulSoup

page = requests.get(feed_entry.link)
soup = BeautifulSoup(page.content, 'html.parser')

# Extract clean text (no HTML, no nav, no ads)
content = soup.get_text(separator='\n', strip=True)

data = {
    "title": feed_entry.title,
    "url": feed_entry.link,
    "content": content,  # FULL TEXT (5000+ chars)
    "metadata": {
        "author": feed_entry.author,
        "published": feed_entry.published
    }
}
```

**Why:** Without full content, chunking/embedding/search is useless. You can't search 119-character snippets.

---

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│ Scraper Fleet (13 operational, 60 total available)    │
│  - Wikipedia, arXiv, Medium, HackerNews, etc.         │
│  - Each scraper: 1 source, many categories            │
│  - Fetch full page content from each URL              │
└─────────────────────────────────────────────────────────┘
           ↓ HTTP POST with JSON
┌─────────────────────────────────────────────────────────┐
│ aio-01 Orchestrator API (port 5000)                    │
│                                                         │
│  POST /store/<source>/<id>                            │
│   - Validate JSON                                      │
│   - Generate hash = md5(url)                          │
│   - Write raw/{category}/{hash}.json                  │
│   - Queue path to Redis: store_queue                  │
│   - Return 202 Accepted                               │
└─────────────────────────────────────────────────────────┘
           ↓ Write to disk
┌─────────────────────────────────────────────────────────┐
│ Centralized Storage                                     │
│  /mnt/aio-01/claude-orchestrator/scraped-data/         │
│   raw/{category}/{hash}.json                           │
│                                                         │
│  Current: 73,000+ files (many stubs, being replaced)  │
└─────────────────────────────────────────────────────────┘
           ↓ Queue workers (Redis-based)
┌─────────────────────────────────────────────────────────┐
│ Processing Pipeline (4 stages)                         │
│                                                         │
│  1. Store Worker (validate, dedupe)                   │
│  2. Chunk Worker (500-1500 char chunks → PostgreSQL)  │
│  3. Embed Worker (generate vectors → PostgreSQL)      │
│  4. Graph Worker (create OrientDB relationships)      │
└─────────────────────────────────────────────────────────┘
           ↓ Final storage
┌─────────────────────────────────────────────────────────┐
│ Databases                                               │
│  - PostgreSQL: knowledge.scraped_data (chunks+vectors) │
│  - OrientDB: Relationships, citations                  │
└─────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Scrapers

**Location:** `/exports/claude-orchestrator/tools/scrapers/`

**Structure:**
```
scrapers/
├── wikipedia/
│   ├── main.py              # Entry point
│   ├── categories.json      # Category mappings
│   └── requirements.txt
├── arxiv/
│   ├── main.py
│   ├── categories.json
│   └── requirements.txt
├── medium/
├── hackernews/
└── ...
```

**Each scraper:**
- Reads from one source (RSS feed, API, sitemap)
- Fetches full page content from each URL
- Extracts clean text (no HTML, no navigation, no ads)
- POSTs JSON to `http://aio-01:5000/store/<source>/<id>`
- Handles fetch failures gracefully (log error, continue)

**Example scraper implementation:**

```python
import requests
from bs4 import BeautifulSoup
import hashlib

API_BASE = "http://aio-01:5000"

def scrape_source(feed_url, source_name, category):
    feed = feedparser.parse(feed_url)
    
    for entry in feed.entries:
        try:
            # Fetch full page content
            page = requests.get(entry.link, timeout=10)
            soup = BeautifulSoup(page.content, 'html.parser')
            
            # Extract clean text
            content = soup.get_text(separator='\n', strip=True)
            
            # Generate ID
            url_hash = hashlib.md5(entry.link.encode()).hexdigest()
            
            # POST to orchestrator
            data = {
                "url": entry.link,
                "source": source_name,
                "category": category,
                "title": entry.title,
                "content": content,
                "metadata": {
                    "author": getattr(entry, 'author', 'Unknown'),
                    "published": getattr(entry, 'published', '')
                }
            }
            
            response = requests.post(
                f"{API_BASE}/store/{source_name}/{url_hash}",
                json=data,
                timeout=10
            )
            
            if response.status_code == 202:
                print(f"✓ Stored: {entry.title}")
            else:
                print(f"✗ Failed: {response.text}")
                
        except Exception as e:
            print(f"✗ Error fetching {entry.link}: {e}")
            continue

if __name__ == "__main__":
    scrape_source(
        "https://en.wikipedia.org/wiki/Special:NewPages",
        "wikipedia",
        "general"
    )
```

### 2. Orchestrator API

**Location:** `/exports/claude-orchestrator/api/application.py`

**Key endpoint:**

```python
@app.route("/store/<source>/<doc_id>", methods=["POST"])
def store_document(source, doc_id):
    """
    Store raw scraped document to filesystem and queue for processing.
    
    This is the FAST path - just write to disk and queue.
    No embedding, no chunking, no database writes.
    
    Returns 202 Accepted immediately.
    """
    data = request.get_json()
    
    # Validate required fields
    required = ["url", "category", "content"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing {field}"}), 400
    
    # Generate hash from URL
    url_hash = hashlib.md5(data["url"].encode()).hexdigest()
    
    # Write raw JSON to disk
    category = data["category"]
    raw_path = f"/mnt/aio-01/claude-orchestrator/scraped-data/raw/{category}/{url_hash}.json"
    
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    
    with open(raw_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Queue for processing
    redis_client.lpush("store_queue", json.dumps({
        "path": raw_path,
        "source": source,
        "doc_id": doc_id,
        "category": category,
        "url_hash": url_hash,
        "queued_at": datetime.now().isoformat()
    }))
    
    return jsonify({
        "stored": True,
        "path": raw_path,
        "hash": url_hash,
        "queued": True
    }), 202
```

### 3. Queue Workers

**Four-stage pipeline:**

#### Stage 1: Store Worker
```python
# Validate, dedupe, basic checks
def process_store_queue():
    while True:
        task = redis_client.brpop("store_queue", timeout=5)
        if not task:
            continue
            
        data = json.loads(task[1])
        path = data["path"]
        
        # Read file
        with open(path) as f:
            doc = json.load(f)
        
        # Validate
        if len(doc.get("content", "")) < 100:
            log_error(f"Content too short: {path}")
            continue
        
        # Check duplicates
        if is_duplicate(doc["url"]):
            log_skip(f"Duplicate: {doc['url']}")
            continue
        
        # Queue for chunking
        redis_client.lpush("chunk_queue", json.dumps(data))
```

#### Stage 2: Chunk Worker
```python
# Split into 500-1500 char chunks, write to PostgreSQL
def process_chunk_queue():
    while True:
        task = redis_client.brpop("chunk_queue", timeout=5)
        if not task:
            continue
            
        data = json.loads(task[1])
        path = data["path"]
        
        with open(path) as f:
            doc = json.load(f)
        
        # Chunk content
        chunks = chunk_text(doc["content"], min_size=500, max_size=1500)
        
        # Insert chunks into PostgreSQL
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
            
            # Queue for embedding
            redis_client.lpush("embed_queue", json.dumps({
                "chunk_id": chunk_id,
                "chunk_text": chunk
            }))
        
        conn.commit()
```

#### Stage 3: Embed Worker
```python
# Generate vectors, update PostgreSQL
def process_embed_queue():
    while True:
        task = redis_client.brpop("embed_queue", timeout=5)
        if not task:
            continue
            
        data = json.loads(task[1])
        
        # Generate embedding (5-provider fallback)
        embedding = generate_embedding_with_fallback(data["chunk_text"])
        
        # Update PostgreSQL
        cursor.execute("""
            UPDATE knowledge.scraped_data
            SET embedding = %s
            WHERE id = %s
        """, (embedding, data["chunk_id"]))
        
        conn.commit()
        
        # Queue for graph
        redis_client.lpush("graph_queue", json.dumps(data))
```

#### Stage 4: Graph Worker
```python
# Create OrientDB relationships
def process_graph_queue():
    while True:
        task = redis_client.brpop("graph_queue", timeout=5)
        if not task:
            continue
            
        data = json.loads(task[1])
        
        # Create document vertex
        orientdb.command(f"""
            CREATE VERTEX Document
            SET chunk_id = {data["chunk_id"]},
                category = '{data["category"]}',
                url_hash = '{data["url_hash"]}'
        """)
```

---

## Data Flow

### Complete End-to-End Flow

```
1. Scraper fetches from web
   └─> URL: https://en.wikipedia.org/wiki/Python
   └─> Content: 5,000 chars of article text

2. POST to aio-01:5000/store/wikipedia/abc123
   └─> JSON body: {url, source, category, title, content, metadata}

3. Orchestrator writes raw file
   └─> /mnt/aio-01/.../raw/programming/abc123.json
   └─> Returns 202 Accepted (fast!)

4. Redis queue: store_queue
   └─> {"path": "/.../abc123.json", "source": "wikipedia", ...}

5. Store worker validates
   └─> Content length OK? ✓
   └─> Duplicate URL? ✗
   └─> Queue to chunk_queue

6. Chunk worker splits text
   └─> 5,000 chars → 4 chunks (500-1500 chars each)
   └─> INSERT INTO knowledge.scraped_data (4 rows)
   └─> Queue to embed_queue (4 tasks)

7. Embed worker generates vectors
   └─> 4 chunks → 4 embeddings (384-dim each)
   └─> UPDATE knowledge.scraped_data SET embedding = ...
   └─> Queue to graph_queue (4 tasks)

8. Graph worker creates relationships
   └─> CREATE VERTEX Document x4
   └─> CREATE EDGE CitedBy, RelatedTo, etc.

9. Done!
   └─> Searchable via vector similarity
   └─> Discoverable via graph traversal
```

### File Paths

```
Raw storage:
/mnt/aio-01/claude-orchestrator/scraped-data/raw/{category}/{hash}.json

Example:
/mnt/aio-01/claude-orchestrator/scraped-data/raw/programming/abc123def456.json
/mnt/aio-01/claude-orchestrator/scraped-data/raw/science/789ghi012jkl.json
```

### Database Schema

```sql
-- PostgreSQL: Chunked content with vectors
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

-- OrientDB: Relationships
CREATE CLASS Document EXTENDS V
CREATE CLASS CitedBy EXTENDS E
CREATE CLASS RelatedTo EXTENDS E
```

---

## Queue System

### Redis Queue Architecture

**4 queues, 4 worker types:**

```
store_queue   → Store worker   → chunk_queue
chunk_queue   → Chunk worker   → embed_queue
embed_queue   → Embed worker   → graph_queue
graph_queue   → Graph worker   → Done
```

**Queue operations:**

```python
# Producer (orchestrator)
redis_client.lpush("store_queue", json.dumps(task))

# Consumer (worker)
task = redis_client.brpop("store_queue", timeout=5)
if task:
    process(json.loads(task[1]))
    redis_client.lpush("chunk_queue", next_task)
```

**Deployment:**

```bash
# Deploy queue workers via orchestrator
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "queue_worker",
    "stage": "chunk",
    "count": 2
  }'
```

---

## Deployment

### Deploying Scrapers

**Use orchestrator API, not direct SSH:**

```bash
# Deploy Wikipedia scraper to 3 workers
curl -X POST http://aio-01:5000/fleet/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "worker_type": "scraper",
    "source": "wikipedia",
    "categories": ["programming", "science", "technology"],
    "count": 3,
    "workers": ["server-01", "server-02", "laptop-01"]
  }'

# Response:
# {
#   "deployed": 3,
#   "workers": [
#     {"node": "server-01", "pid": 12345, "source": "wikipedia"},
#     {"node": "server-02", "pid": 12346, "source": "wikipedia"},
#     {"node": "laptop-01", "pid": 12347, "source": "wikipedia"}
#   ]
# }
```

### Monitoring

```bash
# Check scraper status
curl http://aio-01:5000/fleet/scrapers

# Check queue depth
curl http://aio-01:5000/queue/stats

# Response:
# {
#   "store_queue": 1234,
#   "chunk_queue": 567,
#   "embed_queue": 89,
#   "graph_queue": 12
# }
```

---

## Performance

### Current Metrics (2026-07-10)

| Metric | Value |
|--------|-------|
| Scrapers operational | 13 of 60 available |
| Throughput | 4,700 docs/hour |
| Target | 8,000-10,000 docs/hour |
| Raw files stored | 73,000+ |
| Storage usage | ~2.5 GB |
| Average doc size | 35 KB |

### Bottleneck Analysis

**Before (synchronous embedding):**
- Scraper → POST /web-content → embed (2-5s) → PostgreSQL
- 599 docs/hour with 53 scrapers
- Bottleneck: Embedding API calls

**After (async pipeline):**
- Scraper → POST /store → write disk (~50ms) → return 202
- 4,700 docs/hour with 13 scrapers
- 7.8× throughput improvement

### Scaling

**To reach 10,000 docs/hour:**
- Deploy 25-30 scrapers
- 4 chunk workers
- 8 embed workers (parallel embedding API calls)
- 2 graph workers

---

## Common Pitfalls

### ❌ Pitfall 1: Storing Only RSS Metadata

**Problem:** 73,000 stub files with no content

```json
{
  "title": "How to Build Microservices",
  "url": "https://medium.com/...",
  "content": "Continue reading on Medium »",  // 119 chars
  "snippet": "In this article, we explore..."
}
```

**Solution:** Fetch full page content

```python
page = requests.get(entry.link)
soup = BeautifulSoup(page.content, 'html.parser')
content = soup.get_text(separator='\n', strip=True)  // 5000+ chars
```

### ❌ Pitfall 2: Synchronous Embedding

**Problem:** Embedding API calls block scraper

```python
# WRONG
data = scrape_page(url)
embedding = generate_embedding(data["content"])  # 2-5 seconds!
store_to_db(data, embedding)
```

**Solution:** Write to disk, queue for async embedding

```python
# RIGHT
data = scrape_page(url)
write_to_disk(data)  # 50ms
queue_for_processing(data)  # Async workers handle embedding
return 202  # Immediate response
```

### ❌ Pitfall 3: Direct Worker Deployment

**Problem:** Orchestrator doesn't track workers deployed via SSH

```bash
# WRONG
ssh claude@server-01 "nohup python3 scraper.py &"
```

**Solution:** Use orchestrator API

```bash
# RIGHT
curl -X POST http://aio-01:5000/fleet/deploy ...
```

### ❌ Pitfall 4: Local Filesystem Writes

**Problem:** Workers writing to their local disks

```python
# WRONG
with open("/tmp/scraped/data.json", 'w') as f:
    json.dump(data, f)
```

**Solution:** POST to orchestrator

```python
# RIGHT
requests.post("http://aio-01:5000/store/source/id", json=data)
```

---

## Testing

### Integration Test

```bash
# Test end-to-end flow
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Run test scraper
python3 tools/scrapers/test/test_scraper.py

# Check queue depth
curl http://aio-01:5000/queue/stats

# Verify file written
ssh claude@aio-01 "ls -lh /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/"
```

### Unit Tests

```bash
npm test
```

---

## Summary

**Key design decisions:**

1. **Scrape then process** - Separate fast scraping from slow embedding
2. **Centralized storage** - All data written to aio-01, not worker filesystems
3. **Orchestrator brings up workers** - Deploy via API, not direct SSH
4. **Fetch full content** - Not just RSS metadata

**Benefits:**
- ✅ 7.8× throughput improvement (599 → 4,700 docs/hour)
- ✅ Single source of truth (aio-01 storage)
- ✅ Centralized monitoring and management
- ✅ Scalable to 10,000+ docs/hour

**Related:**
- [[QUEUE_SYSTEM_ARCHITECTURE.md]] - Redis queue details
- [[DEPLOYMENT_GUIDE.md]] - Worker deployment
- [[API_REFERENCE.md]] - Orchestrator API endpoints
