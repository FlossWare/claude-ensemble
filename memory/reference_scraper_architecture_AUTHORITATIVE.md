---
name: scraper-architecture-authoritative
description: "AUTHORITATIVE: How scrapers work - POST to aio-01 REST API, aio-01 writes to disk (not local filesystems)"
metadata:
  type: reference
  priority: CRITICAL
  date: 2026-07-10
---

# Scraper Architecture - AUTHORITATIVE

## How Scrapers Work

**Scrapers run on workers, write via REST API to aio-01:**

```
┌─────────────────────────────────────────────────────────────┐
│ Workers (server-01, server-02, laptop-01, pi-01, etc.)     │
│                                                             │
│  Scraper process:                                          │
│   1. Download from web (Wikipedia, arXiv, etc.)           │
│   2. HTTP POST to http://aio-01:5000/store                │
│      Body: {"url": "...", "source": "...", "content": ...}│
│   3. Wait for 202 response                                 │
│   4. Continue scraping                                     │
│                                                             │
│  ❌ NO local filesystem writes                             │
│  ❌ NO direct file access                                  │
│  ✅ Only HTTP POST to aio-01                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP POST
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ aio-01 (Orchestrator)                                       │
│                                                             │
│  REST API (port 5000):                                     │
│   POST /store endpoint receives JSON                       │
│                                                             │
│  Processing:                                               │
│   1. Generate hash = md5(url)                             │
│   2. Extract category from JSON                           │
│   3. Write to filesystem:                                 │
│      /mnt/aio-01/claude-orchestrator/scraped-data/raw/   │
│      {category}/{hash}.json                               │
│   4. Return 202 Accepted                                  │
│                                                             │
│  ✅ aio-01 does ALL filesystem writes                      │
│  ✅ Centralized storage                                    │
└─────────────────────────────────────────────────────────────┘
```

## Key Points

**Workers:**
- Run scraper Python processes
- HTTP clients only
- No direct filesystem access to scraped-data/
- May have NFS mount for code/tools, but don't write scraped data locally

**aio-01:**
- Runs REST API (Flask app on port 5000)
- Receives POST /store with JSON body
- Writes raw files to `/mnt/aio-01/claude-orchestrator/scraped-data/raw/`
- Returns immediately (no processing, just storage)

**Why This Architecture:**
- ✅ Centralized storage (all raw data in one place)
- ✅ Network separation (workers can be anywhere)
- ✅ No NFS write conflicts (only aio-01 writes)
- ✅ REST API provides validation, deduplication
- ✅ Easy to monitor (one API endpoint)

## Example Flow

**Scraper on server-01:**
```python
import requests

data = {
    "url": "https://en.wikipedia.org/wiki/Python",
    "source": "wikipedia",
    "category": "programming",
    "title": "Python (programming language)",
    "content": "Python is a high-level..."
}

response = requests.post(
    "http://aio-01:5000/store",
    json=data,
    timeout=10
)

# response.json():
# {
#   "stored": true,
#   "path": "/store/programming/abc123...",
#   "hash": "abc123...",
#   "size": 1234
# }
```

**On aio-01:**
```bash
ls -lh /mnt/aio-01/claude-orchestrator/scraped-data/raw/programming/
# -rw-r--r-- 1 claude claude 1.2K Jul 10 20:21 abc123....json
```

## Common Mistake

**WRONG:** Thinking scrapers write to their local filesystems
```
❌ server-01:/tmp/scraped/wikipedia/article.json  # NO!
❌ laptop-01:/var/data/scraped/arxiv/paper.json   # NO!
```

**CORRECT:** Scrapers POST to aio-01, aio-01 writes centrally
```
✅ HTTP POST → aio-01:5000/store
✅ aio-01 writes → /mnt/aio-01/.../scraped-data/raw/{category}/{hash}.json
```

## Related

- [[session_2026-07-10_scraper_fix_COMPLETE]] - How we fixed the /store endpoint
- [[feedback_scrape_then_process]] - Scrape fast, process async
- [[reference_fleet_architecture_AUTHORITATIVE]] - Fleet node roles

---

**REMEMBER:** Scrapers are HTTP clients. aio-01 is the storage server. Workers never write scraped data locally.
