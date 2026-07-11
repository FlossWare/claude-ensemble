---
name: store-endpoint-for-scraping
description: "Use POST /store endpoint for storing scraped web pages - don't write files directly"
metadata:
  type: reference
  date: 2026-07-11
---

# /store REST Endpoint for Scraping

**User correction:** "no! there is a store rest end pt"

## What I Did Wrong

**I tried to:**
- Write scraped data directly to filesystem
- Bypass the REST API
- Store files manually in `/exports/claude-orchestrator/scraped-data/raw/`

**What I should have done:**
- Use `POST http://aio-01:5000/store` endpoint
- Let the API handle file storage
- Follow the architecture: scrapers → REST API → filesystem

## The /store Endpoint

**Purpose:** Store scraped web pages and documents

**Endpoint:** `POST http://aio-01:5000/store`

**Request format:**
```json
{
  "url": "https://example.com/article",
  "source": "performance-tuning",
  "category": "linux-optimization",
  "content": "Full HTML content here...",
  "fetched_at": "2026-07-11T00:00:00"
}
```

**Response:**
```json
{
  "stored": true,
  "path": "/store/linux-optimization/abc123...",
  "hash": "abc123...",
  "size": 12345
}
```

## How It Works

**From reference_scraper_architecture_AUTHORITATIVE.md:**

```
Workers → HTTP POST /store → aio-01 writes to filesystem
```

1. Scraper fetches web page
2. POSTs JSON to `http://aio-01:5000/store`
3. API generates hash from URL
4. API writes to `/exports/claude-orchestrator/scraped-data/raw/{category}/{hash}.json`
5. Returns 202 Accepted

## Why This Architecture Exists

**Centralized storage:**
- All writes go through one API
- Consistent file naming (hash-based)
- Deduplication (same URL → same hash)
- No NFS write conflicts

**Workers don't write files directly:**
- Workers are HTTP clients only
- No direct filesystem access
- Can run anywhere (not just NFS-mounted)

## When to Use

**Use /store when:**
- Scraping web pages
- Storing downloaded documents
- Saving fetched API data
- Any scraped content

**Don't write files directly when:**
- The /store endpoint exists
- You're storing scraped data
- Architecture says "use REST API"

## Related

- [[reference_scraper_architecture_AUTHORITATIVE]] - How scrapers work
- [[feedback_always_unified_rest_api]] - Always use REST API
- [[project_2026-07-10_scraping_fleet_deployment]] - 60 scrapers available

---

**Summary:** Scrapers POST to `/store` endpoint - don't write files directly. Let the API handle storage.
