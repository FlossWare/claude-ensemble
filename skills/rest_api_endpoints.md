# REST API Endpoints Reference

**Last Updated:** 2026-07-11  
**API Server:** http://aio-01:5000  
**Status:** OPERATIONAL (gunicorn, 4 workers)  
**Restart:** `ssh claude@aio-01 "sudo systemctl restart orchestrator-api"`

---

## Architecture

- ALL database access goes through REST API (aio-01:5000)
- Workers and scrapers POST to API, never connect to PostgreSQL directly
- aio-01 is the ONLY machine that touches PostgreSQL (localhost:5433)
- Embeddings via VoyageAI API (5M tokens/month free), truncated to 384-dim

---

## Content Fetching

### POST /fetch/

Fetch a URL and extract clean text. Uses trafilatura (primary) + bs4 (fallback).
SSRF protection blocks private IPs. Rate limited 1 req/sec/domain.

```bash
curl -s -X POST http://aio-01:5000/fetch/ \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

Response:
```json
{
  "url": "https://example.com/article",
  "content": "Full extracted article text...",
  "title": "Article Title",
  "content_length": 8432,
  "status": "ok",
  "extractor": "trafilatura",
  "fetch_time_ms": 847,
  "truncated": false,
  "http_status": 200
}
```

Status values: `ok`, `paywall`, `too_short`, `binary_skipped`, `pdf_skipped`, `fetch_error`, `extract_error`, `timeout`, `http_error`, `ssrf_blocked`

Optional params: `timeout` (max 30), `max_chars` (max 500000)

### POST /fetch/batch

Fetch multiple URLs (max 20 per request).

```bash
curl -s -X POST http://aio-01:5000/fetch/batch \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://a.com", "https://b.com"]}'
```

Response: `{"results": [...], "total": 2, "success_count": 1}`

---

## Data Storage

### POST /store/{source}/{id}

Store scraped data as JSON file. Returns 200 immediately.

```bash
curl -s -X POST http://aio-01:5000/store/arxiv/2012.12104 \
  -H "Content-Type: application/json" \
  -d '{"title": "Paper Title", "url": "https://...", "content": "Full text...", "source": "arxiv", "category": "ai"}'
```

Files stored at: `/exports/claude-orchestrator/scraped-data/raw/{source}/{id}.json`

**Scraper workflow:** Call `/fetch/` to get content, then `/store/` to save it.

---

## Search

### GET /search/intelligent?q={query}&limit={n}

Adaptive search across PostgreSQL, vector DB, and graph. Classifies query type and prioritizes sources.

```bash
curl -s "http://aio-01:5000/search/intelligent?q=fleet+architecture&limit=5"
```

Query classification:
- **Factual** ("what is", "where is"): PostgreSQL first
- **Semantic** ("similar to", "explain"): Vector search first
- **Relationship** ("depends on", "connected to"): Graph first
- **Mixed**: All three equally weighted

Response:
```json
{
  "query": "fleet architecture",
  "query_type": "factual",
  "search_order": ["postgresql", "vector", "graph"],
  "sources": {
    "postgresql": {"status": "success", "results": [...]},
    "vector": {"status": "success", "results": [...]},
    "graph": {"status": "success", "results": [...]}
  },
  "combined": [{"source": "postgresql", "score": 3.0, "data": {...}}, ...],
  "total_results": 8
}
```

### GET /search/unified?q={query}&limit={n}

Same as intelligent but queries all three sources with equal weight.

---

## Fleet Management

### GET /fleet/status

All workers with CPU, memory, uptime, load.

### GET /fleet/scrapers

List all 60 available scrapers.

### POST /fleet/scrapers/start

Start scrapers on workers.

```bash
curl -s -X POST http://aio-01:5000/fleet/scrapers/start \
  -H "Content-Type: application/json" \
  -d '{"scrapers": ["hackernews_scraper.py"], "workers": ["server-01"]}'
```

### POST /fleet/scrapers/stop

Stop scrapers on specific workers.

### POST /fleet/kill-all

Emergency: kill all scraper processes across fleet.

### GET /fleet/auto-deploy/status

Check auto-deploy loop status.

### POST /fleet/auto-deploy/start / stop

Start/stop automatic scraper deployment across fleet.

---

## Learning & Memory

### GET /learning/memory/search?query={text}&limit={n}&min_similarity={0.3}

Semantic search across stored memories using pgvector cosine similarity.

### POST /learning/memory

Store a memory with auto-generated embedding.

```json
{"memory_type": "feedback", "content": "...", "source_file": "file.md", "metadata": {}}
```

### GET /learning/experiences/similar?text={query}&limit={n}

Find similar past experiences via vector similarity.

### POST /learning/experiences

Store new learning experience.

### GET /learning/strategies

Get Thompson Sampling strategy performance rankings.

### POST /learning/strategies/{name}/record

Record strategy outcome (success/failure + reward).

### POST /learning/embeddings/generate

Generate embeddings via 5-provider cascade (VoyageAI > Jina > Cohere > Google > local).

---

## Secrets

### GET /secrets/{key_name}

Get API key. Example: `curl -s http://aio-01:5000/secrets/GOOGLE_API_KEY | jq -r .value`

### GET /secrets/

List all available secret keys.

21 keys available: PERSONAL_CEREBRAS_API_KEY, PERSONAL_CLOUDFLARE_API_KEY, PERSONAL_COHERE_API_KEY, PERSONAL_DEEPSEEK_API_KEY, GOOGLE_API_KEY, PERSONAL_OPENROUTER_API_KEY, PERSONAL_VOYAGEAI_API_KEY, etc.

---

## Graph Database (OrientDB)

### POST /graph/query

Run OrientDB SQL query.

```bash
curl -s -X POST http://aio-01:5000/graph/query \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT FROM Machine LIMIT 5"}'
```

---

## Monitoring

### GET /health

Service health check.

### GET /monitoring/scrapers

Active scrapers across fleet.

### GET /monitoring/metrics

Prometheus-compatible metrics.

### GET /monitoring/executions/stats?window=24h

Execution statistics.

### GET /monitoring/costs?window=7d&group_by=model

Cost analysis.

---

## Knowledge

### GET /knowledge/scraped_data/stats

Scraping statistics (total docs, last hour, etc.)

---

## Blueprints Location

`/exports/claude-orchestrator/api/app/blueprints/`

Key files: `fetch.py`, `store.py`, `fleet.py`, `intelligent_search.py`, `unified_search.py`, `learning.py`, `secrets.py`, `monitoring.py`, `graph.py`, `knowledge.py`

Main app: `/exports/claude-orchestrator/api/application.py`
WSGI: `/exports/claude-orchestrator/api/wsgi.py`
Service: `orchestrator-api.service` (gunicorn, 4 workers, LimitNOFILE=1048576)
