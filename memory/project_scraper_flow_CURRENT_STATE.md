---
name: scraper-flow-current-state
description: "CRITICAL: Current scraper flow and what's broken - /web-content does NOT write to filesystem"
metadata:
  type: project
  date: 2026-07-10
  priority: CRITICAL
---

# Scraper Flow - Current State (2026-07-10)

## What I Keep Forgetting

**CURRENT BEHAVIOR (BROKEN):**
- 53 scrapers running across fleet
- POST to `http://aio-01:5000/web-content`
- `/web-content` endpoint:
  - ❌ Does synchronous embedding (SLOW - this is the bottleneck)
  - ❌ Only writes to PostgreSQL `knowledge.scraped_data` table
  - ❌ Does NOT write to filesystem
  - No `open()`, no `json.dump()`, no file writes in the code

**EVIDENCE:**
```python
# /exports/claude-orchestrator/api/application.py line 905-960
@app.route("/web-content", methods=["POST"])
def ingest_web_content():
    # ... validates data ...
    embedding = generate_embedding_with_fallback(data["content"])  # SLOW!
    
    # Only writes to PostgreSQL:
    cursor.execute("""
        INSERT INTO knowledge.scraped_data
        (category, source_file, file_hash, chunk_index, chunk_text, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, ...)
    
    return jsonify({"stored": True, "document_id": document_id}), 200
    
# NO filesystem writes!
```

**FILESYSTEM STATE:**
- `/mnt/aio-01/claude-orchestrator/scraped-data/raw/` has 47,995 JSON files
- Latest files from July 9 (yesterday)
- ZERO files created today (July 10)
- Those files are from OLD scrapers or different code

**THROUGHPUT:**
- Current: ~599 docs/hour with 53 scrapers
- Target: 8,000-10,000 docs/hour
- Bottleneck: Synchronous embedding in `/web-content`

## What SHOULD Happen

**User expectation:** "scrapers do post to aio-01, but that gets written to disk"

This means `/web-content` SHOULD:
1. Write raw JSON to `/scraped-data/raw/{category}/{hash}.json`
2. Queue the file path for async processing
3. Return immediately (no embedding)

**The queue system exists:**
- 4-stage pipeline: `store → chunk → embed → graph`
- Queue tables exist: `queue.store`, `queue.chunk`, `queue.embed`, `queue.graph`
- Queue API exists: `/queue/add`, `/queue/fetch/<name>`, `/queue/complete/<name>/<id>`
- ❌ NO queue workers running to process items

## What Needs to Be Fixed

1. **Fix `/web-content` to write to filesystem:**
   - Write raw JSON to `/scraped-data/raw/{category}/{hash}.json`
   - POST file path to `/queue/add` (store queue)
   - Remove synchronous embedding
   - Return 202 Accepted immediately

2. **Start queue workers:**
   - Store worker: validate, dedupe
   - Chunk worker: read file → chunk → write chunks to PostgreSQL
   - Embed worker: generate vectors → update PostgreSQL
   - Graph worker: create OrientDB relationships

3. **Alternative:** Change scrapers to POST to `/queue/add` directly
   - But user wants them to POST to orchestrator and have it written to disk
   - So fix `/web-content` is the right approach

## Related Issues

- [[session_2026-07-10_scraper_ulimit_issue]] - "Too many open files" from 96 scrapers
- [[feedback_orchestrator_brings_up_workers]] - Use orchestrator for deployment

---

**USER FRUSTRATED:** I keep forgetting that `/web-content` is NOT writing to disk even though user expects it to.

**ACTION:** Fix `/web-content` to write raw files + queue path, then start queue workers.
