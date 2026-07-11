---
name: scraper-ulimit-issue
description: "Scrapers overwhelmed API with 'Too many open files' - need controlled deployment"
metadata:
  type: project
  date: 2026-07-10
  severity: high
---

# Scraper Deployment Issue - Too Many Open Files

## What Happened

**Deployed 96 scrapers across fleet** (server-01/02/03, laptop-01, pi-01/02, server-ap, desktop-ap)

**Result:** API crashed with:
```
OSError: [Errno 24] Too many open files
BrokenPipeError: [Errno 32] Broken pipe
```

**Symptoms:**
- Scrapers running but not ingesting (last ingest: 19:19, scrapers deployed ~19:05)
- 10,601 docs in database but **zero new docs in last 5 minutes**
- API logs showing continuous errors
- Database connection pool failing

## Root Cause

**96 scrapers * continuous HTTP POSTs = file descriptor exhaustion**

Each scraper:
1. Opens HTTP connection to aio-01:5000
2. Posts data
3. Gets embedding (another 5 HTTP connections in fallback cascade)
4. Repeat continuously

**96 scrapers × ~6 connections each = ~576 concurrent file descriptors**

Default ulimit: 1024 (insufficient)

## Fix

1. **Killed all scrapers** (pkill -f 'python3.*scraper')
2. **Increased ulimit to 65536** on aio-01
3. **Restarted API** (systemctl restart orchestrator-api)
4. **Controlled restart:** Deploy scrapers gradually, not all at once

## Correct Deployment Strategy

**Use orchestrator API** (not direct SSH):
- Orchestrator controls deployment rate
- Centralized tracking
- Prevents overwhelming the system

**Gradual scaling:**
- Start with 10-20 scrapers
- Monitor API health
- Scale incrementally to 60% CPU target

## Related Memories

- [[feedback_orchestrator_brings_up_workers]] - Use orchestrator for deployment
- [[reference_fleet_architecture_AUTHORITATIVE]] - Fleet configuration

## Action Items

- [ ] Deploy scrapers via orchestrator API (not SSH)
- [ ] Start with 20 scrapers total
- [ ] Monitor for file descriptor issues
- [ ] Scale gradually to target throughput

---

**Lesson learned:** Direct mass deployment bypasses orchestrator's rate limiting and health checks.
