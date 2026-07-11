---
name: workers-never-hit-postgres
description: Workers NEVER hit PostgreSQL - they POST to aio-01:5000 REST API only
metadata:
  type: feedback
  date: 2026-07-10
---

# Workers Never Hit PostgreSQL Directly

**User feedback:** "what cant hit postgres? no worker should be hitting postgres!"

## Architecture (CORRECT)

```
Workers → HTTP POST aio-01:5000/store → API writes to disk
                                      ↓
                           (later) Queue processors → PostgreSQL
```

## What I Got Wrong

When I saw "connection to PostgreSQL failed", I thought workers needed it.

**Reality:** Only **aio-01** (orchestrator) needs PostgreSQL for:
- /health endpoint (checking connection pools)
- /monitoring endpoints (querying metrics)
- Queue processors (chunk → embed → vector → graph)

**Note:** aio-01 can hit PostgreSQL because it runs the API and queue processors. The other 8 workers (server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap) CANNOT.

## Workers ONLY Do This

1. Run scrapers (Python scripts)
2. POST JSON to `http://aio-01:5000/store`
3. Receive 201 response
4. Continue scraping

**No PostgreSQL, no direct database access, just HTTP.**

## Why This Matters

- Workers don't need PostgreSQL credentials
- Workers don't need psycopg2 installed
- Workers don't care if PostgreSQL is down (scraping continues)
- API /store endpoint doesn't use database (just writes files)

**The /health endpoint failing is irrelevant to scrapers.**

## How to Apply

- NEVER configure workers with PostgreSQL connection
- NEVER check PostgreSQL health from workers
- API /store endpoint = stateless file writer (no database)
- Database queries = separate concern (queue processors)

---

**Remember:** Scraping and processing are DECOUPLED by design.
