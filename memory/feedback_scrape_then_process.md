---
name: scrape-then-process
description: "CRITICAL: Separate scraping from processing - scrape fast, write raw, process async"
metadata:
  type: feedback
  priority: CRITICAL
  date: 2026-07-10
---

# Scrape Then Process

**User directive:** "remember we were gonna scrape wll then process"

## Architecture Decision

**Separate concerns:**
1. **Scraping** = Download from web, write to disk (FAST)
2. **Processing** = Chunk, embed, graph (SLOW, async)

**NOT:** Scrape + embed in same request (current broken behavior)

## Implementation

**Scrapers should:**
- Download content from websites
- POST to orchestrator with raw data
- Orchestrator writes to `/scraped-data/raw/{category}/{id}.json`
- Return immediately (202 Accepted)

**Background workers then:**
- Chunk worker: Read file → chunk into 500-1500 char pieces
- Embed worker: Generate vectors for each chunk
- Graph worker: Create OrientDB relationships

## Current vs Correct

**WRONG (current):**
```
Scraper → POST /web-content → embedding (SLOW) → PostgreSQL
                               ↑ bottleneck (599 docs/hour)
```

**RIGHT:**
```
Scraper → POST /store/{source}/{id} → write to disk → return 202
                                       ↓
                              Queue workers process async
                              (store → chunk → embed → graph)
                              
Target: 8,000-10,000 docs/hour
```

## Endpoints

**`/store/<source>/<id>`** (exists, writes to filesystem):
```python
POST /store/arxiv/2012.12104v1
Body: {"title": "...", "content": "...", ...}
Result: Writes to /scraped-data/raw/arxiv/2012.12104v1.json
```

**`/web-content`** (broken, does synchronous embedding):
- Should be deprecated or fixed to use `/store/` + queue

## Queue System (exists but no workers)

Tables: `queue.store`, `queue.chunk`, `queue.embed`, `queue.graph`

Pipeline: store → chunk → embed → graph

**Need to start workers** to process the queue.

## Why This Matters

**Scalability:**
- Scraping is I/O bound (network)
- Embedding is CPU/API bound
- Mixing them = slowest operation blocks everything

**Throughput:**
- Current: 599 docs/hour (synchronous)
- Target: 8,000-10,000 docs/hour (async pipeline)

---

**Action:** Fix scrapers to POST to `/store/` endpoint, then start queue workers.

## CRITICAL UPDATE (2026-07-11)

**Scrapers must fetch FULL PAGE CONTENT from each URL!**

The scrapers were only storing RSS metadata (title, URL, snippet). Content field was empty or just "Continue reading on Medium »". 73,000+ useless stub files.

**User feedback:** "well how will that little data help anything"

**Correct scraper behavior:**
1. Get URLs from RSS/API feed
2. **FETCH the actual page content from each URL**
3. Extract clean text (no HTML, no nav, no ads)
4. POST full content + metadata to /store
5. Handle fetch failures gracefully (store metadata even if content fails)

**Without full content, the pipeline is worthless** — you can't chunk, embed, or search a 119-character snippet.
