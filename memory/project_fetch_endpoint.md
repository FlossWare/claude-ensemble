---
name: fetch-endpoint
description: "POST /fetch on orchestrator - centralized URL content fetcher - DEPLOYED and working"
metadata:
  type: project
  date: 2026-07-11
  status: deployed
---

# Centralized Content Fetch Endpoint — DEPLOYED

**Status:** Live on aio-01:5000/fetch/ since 2026-07-11

## Endpoints

### POST /fetch/
Single URL fetch:
```
POST aio-01:5000/fetch/
{"url": "https://example.com/article"}

→ {"url": "...", "content": "full clean text...", "title": "...",
   "content_length": 8432, "status": "ok", "extractor": "trafilatura",
   "fetch_time_ms": 847, "truncated": false, "http_status": 200}
```

### POST /fetch/batch
Multiple URLs (max 20):
```
POST aio-01:5000/fetch/batch
{"urls": ["https://a.com", "https://b.com"]}

→ {"results": [...], "total": 2, "success_count": 2}
```

## Features
- **Extraction:** trafilatura primary, bs4 fallback
- **SSRF protection:** blocks private IPs (RFC 1918, loopback, link-local)
- **Rate limiting:** 1 req/sec/domain
- **Size limits:** 2MB HTML download, 100K char text, 10s timeout
- **Binary detection:** skips PDFs, images, archives
- **Paywall detection:** flags stub content
- **Status codes:** ok, paywall, too_short, binary_skipped, pdf_skipped, fetch_error, extract_error, timeout, http_error, ssrf_blocked

## How to Apply
- Scrapers call /fetch to get content, then POST to /store with full text
- Other sessions call /fetch directly for any URL content extraction
- Implementation: `/exports/claude-orchestrator/api/app/blueprints/fetch.py`
