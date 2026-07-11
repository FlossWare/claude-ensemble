---
name: session-2026-07-10-scraper-fix-complete
description: "COMPLETE: How we fixed scrapers to write raw files to disk - scrape first, process later"
metadata:
  type: project
  date: 2026-07-10
  priority: CRITICAL
---

# Scraper Fix - Complete Solution (2026-07-10)

## Problem

**Scrapers were NOT writing to filesystem:**
- 53 scrapers running, POSTing to `/web-content`
- `/web-content` did synchronous embedding (SLOW bottleneck)
- Only wrote to PostgreSQL, not filesystem
- 599 docs/hour (way below 8,000-10,000 target)
- Last raw files written: July 9

## Root Cause

**application.py was changed on July 10 at 16:54:**
- `/web-content` endpoint removed filesystem writes
- Only did PostgreSQL INSERT with embedding
- Scrapers kept POSTing to `/web-content` (expecting filesystem writes)

**Old working scrapers (July 9):**
- Used `/store/<source>/<id>` endpoint
- Wrote 47,995 raw JSON files to `/scraped-data/raw/`
- Current scrapers had wrong endpoint

## Solution

**Added POST `/store` endpoint (without path):**

```python
@store_bp.route('', methods=['POST'])
@store_bp.route('/', methods=['POST'])
def store_document_auto():
    \"\"\"Auto-generate hash and store to filesystem\"\"\"
    data = request.get_json()
    
    # Generate hash from URL
    file_hash = hashlib.md5(data['url'].encode()).hexdigest()
    
    # Get source from JSON body
    source = data.get('category', data['source'])
    
    # Write to /scraped-data/raw/{source}/{hash}.json
    file_path = BASE_PATH / source / f'{file_hash}.json'
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return jsonify({'stored': True, 'path': f'/store/{source}/{file_hash}'})
```

**Key insight:** Scrapers POST JSON body with source/url/content. Endpoint extracts source from body, generates hash, writes file. No scraper changes needed!

## Architecture

**Scrape → Store → Process (async):**

```
Scraper → POST /store → writes raw JSON → returns 202
          |
          v
     /scraped-data/raw/{category}/{hash}.json

Later (async):
Queue workers process: store → chunk → embed → graph
```

## Results

**Before fix:**
- 599 docs/hour
- Synchronous embedding blocking scrapers
- No raw backup

**After fix:**
- 40 scrapers deployed
- 115 files written in 3 minutes (~2,300 docs/hour)
- Raw files preserved for reprocessing
- Fast scraping (no embedding)

**Next step:** Start queue workers to process stored files

## Files Modified

1. `/exports/claude-orchestrator/api/app/blueprints/store.py`
   - Added POST `/store` and POST `/store/` routes
   - Auto-generates hash from URL in JSON body

2. Scrapers (already had correct API_URL)
   - `API_URL = "http://aio-01:5000/store"`
   - POST JSON: `{"url": "...", "source": "...", "content": "..."}`

## Testing

```bash
# Test endpoint
curl -X POST http://aio-01:5000/store \
  -H "Content-Type: application/json" \
  -d '{"url": "http://test.com", "source": "test", "content": "..."}'

# Response:
{"stored": true, "path": "/store/test/abc123...", "hash": "abc123..."}

# Verify file:
cat /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/abc123.json
```

## Related Memories

- [[feedback_scrape_then_process]] - Separate scraping from processing
- [[project_scraper_flow_CURRENT_STATE]] - What was broken
- [[session_2026-07-10_scraper_ulimit_issue]] - Too many open files issue

## Why This Works

**Separation of concerns:**
1. **Scraping** = Download + write to disk (FAST, I/O bound)
2. **Processing** = Chunk + embed + graph (SLOW, CPU/API bound)

**Scalability:**
- Scrapers can run at full speed (no waiting for embedding)
- Queue workers process async (can scale independently)
- Raw data preserved (can reprocess with better models later)

---

**Status:** ✅ FIXED - Scrapers writing to filesystem at ~2,300 docs/hour

**Next:** Start queue workers to process: store → chunk → embed → graph
