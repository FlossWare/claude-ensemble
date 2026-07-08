# API Blueprint Reference - Complete Route Map

**Version:** 1.0.0  
**Last Updated:** 2026-07-07  
**Base URL:** `http://aio-01:5000`

---

## Architecture Overview

The orchestrator API uses **Flask Blueprints** for modular organization:

```
application.py (main Flask app on port 5000)
    ↓
app/blueprints/ (22 modular APIs)
    ├─ admin.py
    ├─ fleet.py
    ├─ workflows.py
    ├─ ... (19 more)
    └─ Each blueprint = self-contained API domain
```

**Total Blueprints:** 22  
**Total Routes:** ~150+  
**Request Format:** JSON  
**Response Format:** JSON

---

## Complete Blueprint Map

### 1. Admin API
**Prefix:** `/api/admin`  
**Purpose:** System administration, database management, maintenance

**Routes:**
- `GET /api/admin/status` - System status and health
- `POST /api/admin/database/vacuum` - Database maintenance
- `POST /api/admin/database/backup` - Create backup
- `POST /api/admin/database/cleanup` - Remove old data
- `GET /api/admin/logs/tail` - Recent log entries
- `POST /api/admin/maintenance/reindex` - Rebuild indexes
- `POST /api/admin/fleet/sync` - Sync fleet state
- `POST /api/admin/cache/clear-all` - Clear all caches
- `GET /api/admin/diagnostics` - System diagnostics

---

### 2. Chunker API
**Prefix:** `/api/chunker` (or root)  
**Purpose:** Universal text/code chunking and embedding

**Routes:**
- `POST /api/chunker/text` - Chunk plain text
- `POST /api/chunker/code` - Chunk source code (language-aware)
- `POST /api/chunker/file` - Chunk file (auto-detect type)
- `GET /api/chunker/status` - Chunker health
- `GET /api/chunker/config` - Current configuration

**Example:**
```json
POST /api/chunker/code
{
  "content": "def hello():\n    print('world')",
  "language": "python",
  "max_chunk_size": 512,
  "overlap": 50
}
```

---

### 3. Config API
**Prefix:** `/api/config`  
**Purpose:** System configuration, feature flags, settings

**Routes:**
- `GET /api/config/` - Get all configuration
- `POST /api/config/set` - Update configuration
- `GET /api/config/get/<key>` - Get specific config value
- `GET /api/config/fleet` - Fleet configuration
- `GET /api/config/models` - Model configuration
- `GET /api/config/features` - Feature flags (list all)
- `POST /api/config/features/<name>` - Toggle feature flag
- `GET /api/config/permissions` - Permission settings
- `GET /api/config/env` - Environment variables (safe list)
- `GET /api/config/env/<var_name>` - Get specific env var

---

### 4. Costs API
**Prefix:** `/api/costs`  
**Purpose:** Cost tracking and analytics for LLM usage

**Routes:**
- `POST /api/costs/log` - Log API cost
- `GET /api/costs/total` - Total costs (all time)
- `GET /api/costs/by-model` - Costs grouped by model
- `GET /api/costs/recent` - Recent cost entries
- `GET /api/costs/by-provider` - Costs grouped by provider
- `GET /api/costs/daily` - Daily cost breakdown
- `GET /api/costs/workflow/<workflow_id>` - Costs for specific workflow
- `GET /api/costs/pricing` - Current pricing table
- `GET /api/costs/health` - Cost tracking health

**Example:**
```json
POST /api/costs/log
{
  "model": "opus",
  "input_tokens": 1500,
  "output_tokens": 800,
  "cost_usd": 0.05
}
```

---

### 5. Embeddings API
**Prefix:** `/api/embeddings`  
**Purpose:** Vector embeddings generation, similarity search, clustering

**Routes:**
- `POST /api/embeddings/generate` - Generate single embedding
- `POST /api/embeddings/batch` - Generate batch of embeddings
- `POST /api/embeddings/search` - Similarity search
- `POST /api/embeddings/store` - Store embedding in database
- `POST /api/embeddings/cluster` - Cluster embeddings
- `POST /api/embeddings/create` - Create embedding collection

**Example:**
```json
POST /api/embeddings/generate
{
  "text": "Quantum computing breakthrough",
  "model": "mistral-embed",
  "dimensions": 1024
}

Response:
{
  "embedding": [0.123, 0.456, ...],
  "dimensions": 1024,
  "model": "mistral-embed"
}
```

---

### 6. External API
**Prefix:** `/api/external`  
**Purpose:** Proxy to external APIs with PostgreSQL tracking

**Routes:**
- `ALL /api/external/github/*` - Proxy to GitHub API
- `ALL /api/external/openai/*` - Proxy to OpenAI API
- `ALL /api/external/anthropic/*` - Proxy to Anthropic API
- `ALL /api/external/arxiv/*` - Proxy to arXiv API
- `ALL /api/external/notion/*` - Proxy to Notion API
- `ALL /api/external/jira/*` - Proxy to Jira API
- `GET /api/external/metrics` - External API usage metrics
- `GET /api/external/costs` - External API costs
- `GET /api/external/rate-limits` - Rate limit status
- `GET /api/external/health` - External proxy health

**Example:**
```bash
# Proxy to GitHub (automatically tracked)
curl http://aio-01:5000/api/external/github/repos/anthropics/anthropic-sdk-python
```

---

### 7. Fleet API
**Prefix:** `/api/fleet`  
**Purpose:** Distributed fleet management, task distribution

**Routes:**
- `GET /api/fleet/nodes` - List all fleet nodes
- `GET /api/fleet/nodes/<node_id>/health` - Node health check
- `POST /api/fleet/tasks/distribute` - Distribute task across fleet
- `GET /api/fleet/utilization` - Fleet resource utilization
- `POST /api/fleet/nodes/<node_id>/execute` - Execute on specific node

**Example:**
```json
POST /api/fleet/tasks/distribute
{
  "task": "Review this code for security issues",
  "workers": 6,
  "strategy": "quality-first"
}

Response:
{
  "task_id": "ft_abc123",
  "workers_assigned": [
    {"node": "server-01", "model": "opus"},
    {"node": "server-02", "model": "sonnet"},
    ...
  ]
}
```

---

### 8. Graph API
**Prefix:** `/api/graph`  
**Purpose:** OrientDB knowledge graph queries

**Routes:**
- `POST /api/graph/query` - Execute graph query
- `GET /api/graph/stats` - Graph statistics
- `POST /api/graph/load-from-postgres` - Sync from PostgreSQL

**Example:**
```json
POST /api/graph/query
{
  "query": "SELECT FROM Infrastructure WHERE type='server'"
}
```

---

### 9. Ingest API
**Prefix:** `/api/ingest`  
**Purpose:** Data ingestion (proxies to service on port 8006)

**Routes:**
- `POST /api/ingest/submit` - Submit data for ingestion
- `GET /api/ingest/status` - Ingestion service health
- `GET /api/ingest/endpoints` - Available ingestion endpoints

**Example:**
```json
POST /api/ingest/submit
{
  "type": "conversation",
  "data": {
    "messages": [...],
    "timestamp": "2026-07-07T12:00:00Z"
  }
}
```

---

### 10. Learning API
**Prefix:** `/api/learning`  
**Purpose:** Continual learning, experience memory, Thompson Sampling

**Routes:**
- `GET /api/learning/experiences` - List experiences
- `POST /api/learning/experiences/similar` - Find similar experiences
- `POST /api/learning/experiences` - Store new experience
- `GET /api/learning/strategies` - List all strategies
- `GET /api/learning/strategies/<name>` - Get strategy details
- `POST /api/learning/strategies/<name>/record` - Record success/failure
- `POST /api/learning/strategies/select` - Select best strategy (Thompson Sampling)
- `GET /api/learning/monitoring/diversity` - Model diversity metrics
- `POST /api/learning/embeddings/generate` - Generate embedding
- `GET /api/learning/health` - Learning system health

**Example:**
```json
POST /api/learning/experiences
{
  "problem_type": "code_review",
  "context": {"language": "python", "complexity": "high"},
  "strategy": "opus_deep_analysis",
  "success": true,
  "reward": 0.92,
  "embedding": [0.123, ...]
}
```

---

### 11. Monitoring API
**Prefix:** `/api/monitoring`  
**Purpose:** System health, metrics, performance, alerts

**Routes:**
- `GET /api/monitoring/health` - Overall system health
- `GET /api/monitoring/metrics` - Prometheus-compatible metrics
- `GET /api/monitoring/executions/stats` - Execution statistics
- `GET /api/monitoring/alerts` - Active alerts
- `GET /api/monitoring/costs` - Cost monitoring
- `GET /api/monitoring/performance/models` - Model performance metrics
- `GET /api/monitoring/logs/recent` - Recent log entries

**Example:**
```json
GET /api/monitoring/executions/stats

Response:
{
  "total_executions": 1523,
  "success_rate": 0.94,
  "avg_duration_ms": 3421,
  "models": {
    "opus": {"count": 523, "success_rate": 0.96},
    "sonnet": {"count": 498, "success_rate": 0.93}
  }
}
```

---

### 12. Notifications API
**Prefix:** `/api/notifications`  
**Purpose:** Alerts, webhooks, event streaming

**Routes:**
- `POST /api/notifications/subscribe` - Subscribe to events
- `POST /api/notifications/unsubscribe` - Unsubscribe from events
- `POST /api/notifications/send` - Send notification
- `GET /api/notifications/recent` - Recent notifications
- `POST /api/notifications/alerts/create` - Create alert rule
- `GET /api/notifications/stream` - Server-sent events stream
- `GET /api/notifications/webhooks` - List webhooks
- `POST /api/notifications/test` - Test notification
- `GET /api/notifications/stats` - Notification statistics
- `POST /api/notifications/alerts/acknowledge` - Acknowledge alert

**Example:**
```json
POST /api/notifications/subscribe
{
  "event_type": "workflow_completed",
  "webhook_url": "https://example.com/hook",
  "filters": {
    "workflow_name": "deep-research"
  }
}
```

---

### 13. Proxy API
**Prefix:** `/api/proxy`  
**Purpose:** LLM API routing with caching (minimal implementation)

**Routes:**
- `GET /api/proxy/health` - Proxy health

---

### 14. Queue API
**Prefix:** `/queue`  
**Purpose:** Multi-stage document processing pipeline

**Routes:**
- `POST /queue/add` - Add item to queue
- `GET /queue/status` - Queue status
- `POST /queue/fetch/<queue_name>` - Claim next item
- `POST /queue/complete/<queue_name>/<item_id>` - Mark item complete
- `POST /queue/fail/<queue_name>/<item_id>` - Mark item failed
- `GET /queue/item/<queue_name>/<item_id>` - Get item details
- `POST /queue/retry-failed/<queue_name>` - Retry all failed items
- `POST /queue/purge/<queue_name>` - Clear queue

**Queues:**
- `chunk` - Files needing chunking
- `embed` - Chunks needing embeddings
- `graph` - Items needing graph insertion

**Example:**
```json
POST /queue/add
{
  "queue_name": "chunk",
  "data": {
    "file_path": "/path/to/document.pdf",
    "priority": 5
  }
}
```

---

### 15. Routing API
**Prefix:** `/api/routing`  
**Purpose:** Thompson Sampling, model selection, strategy tracking

**Routes:**
- `GET /api/routing/strategies` - List all strategies
- `POST /api/routing/select` - Select best strategy
- `POST /api/routing/feedback` - Provide feedback on strategy
- `GET /api/routing/models` - Model performance data
- `POST /api/routing/select-model` - Select best model for task

**Example:**
```json
POST /api/routing/select-model
{
  "task_type": "code_review",
  "context": {
    "language": "python",
    "complexity": "high"
  }
}

Response:
{
  "model": "opus",
  "confidence": 0.87,
  "reason": "Highest capability score (0.94) for code_review tasks"
}
```

---

### 16. Scraping API
**Prefix:** `/api/scraping`  
**Purpose:** Web scraping, content extraction, link analysis

**Routes:**
- `POST /api/scraping/fetch` - Fetch and extract from URL
- `POST /api/scraping/batch` - Batch URL fetching (up to 10 concurrent)
- `GET /api/scraping/cache/stats` - Cache statistics
- `POST /api/scraping/cache/clear` - Clear cache (all or by domain)
- `POST /api/scraping/extract/links` - Extract links from URL

**Features:**
- **Rate limiting:** 2-second minimum per domain
- **Caching:** 15-minute TTL (configurable)
- **Formats:** markdown, html, text
- **User agent:** Mozilla/5.0 (compatible; FleetBot/1.0)
- **Timeout:** 30 seconds per request

**Example - Fetch URL:**
```json
POST /api/scraping/fetch
{
  "url": "https://example.com/article",
  "extract": "markdown",
  "cache_ttl": 900
}

Response:
{
  "url": "https://example.com/article",
  "content": "# Article Title\n\nContent here...",
  "format": "markdown",
  "cached": false,
  "size_bytes": 12345,
  "timestamp": "2026-07-07T12:00:00Z"
}
```

**Example - Batch Fetch:**
```json
POST /api/scraping/batch
{
  "urls": [
    "https://site1.com",
    "https://site2.com",
    "https://site3.com"
  ],
  "extract": "text",
  "max_concurrent": 5
}

Response:
{
  "total_urls": 3,
  "fetched": 3,
  "results": [
    {"url": "https://site1.com", "success": true, "content": "..."},
    {"url": "https://site2.com", "success": true, "content": "..."},
    {"url": "https://site3.com", "success": false, "error": "timeout"}
  ]
}
```

**Example - Extract Links:**
```json
POST /api/scraping/extract/links
{
  "url": "https://example.com",
  "filter": "internal"
}

Response:
{
  "url": "https://example.com",
  "total_links": 42,
  "filter": "internal",
  "links": ["/about", "/contact", "/blog", ...],
  "timestamp": "2026-07-07T12:00:00Z"
}
```

**Active Scrapers (50+):**

Running continuously via cron/systemd:
- **arXiv** - 6 categories (AI, ML, CV, CL, Robotics, Neural)
- **GitHub** - Code repositories, trending repos
- **Stack Overflow** - Questions, answers, code snippets
- **HackerNews** - Top stories, discussions
- **Slashdot** - Tech news, discussions (deployed 2026-07-07)
- **Dev.to** - Developer articles
- **Medium** - Technical articles
- **Wikipedia** - Knowledge base articles
- **PubMed** - Medical/scientific papers
- **BioRxiv** - Biology preprints
- **MDN** - Web documentation
- **TensorFlow Docs** - ML documentation
- **Python Docs** - Language documentation
- **W3C Specs** - Web standards
- **RFC** - Internet standards
- **Semantic Scholar** - Academic papers
- **Papers with Code** - ML research + code
- **OpenReview** - Peer review platform
- **Reddit** - Tech subreddits
- **Guardian** - News articles
- **Internet Archive** - Historical content
- **Gutenberg** - Books, literature
- **And 28+ more specialized scrapers**

**Collection Pipeline:**
```
Scraper → POST /store/<source>/<id>
    ↓
/mnt/aio-01/claude-orchestrator/scraped-data/raw/
    ↓
Queue (chunk/embed/graph)
    ↓
PostgreSQL + pgvector + OrientDB
```

**Storage Stats:**
- **45,000+ documents** collected
- **51 active data sources**
- **Real-time updates** (hourly/daily)
- **Automatic deduplication**
- **Rate limiting per domain**

---

### 17. Search API
**Prefix:** `/api/search`  
**Purpose:** PostgreSQL full-text search

**Routes:**
- `POST /api/search/query` - Full-text search
- `GET /api/search/documents` - List indexed documents
- `GET /api/search/stats` - Search index statistics
- `GET /api/search/categories` - Document categories

**Example:**
```json
POST /api/search/query
{
  "query": "quantum computing entanglement",
  "limit": 10,
  "filters": {
    "category": "research"
  }
}
```

---

### 18. Secrets API
**Prefix:** `/api/secrets`  
**Purpose:** Secure credential storage

**Routes:**
- `GET /api/secrets/<key>` - Get secret value
- `GET /api/secrets/` - List all secret keys (not values)
- `GET /api/secrets/env/<key>` - Get secret as env var format

---

### 19. Storage API
**Prefix:** `/api/storage`  
**Purpose:** Data persistence, caching, vector storage

**Routes:**
- `POST /api/storage/experiences/store` - Store experience
- `POST /api/storage/experiences/search` - Search experiences
- `POST /api/storage/cache/set` - Set cache value
- `GET /api/storage/cache/get/<key>` - Get cache value
- `DELETE /api/storage/cache/delete/<key>` - Delete cache entry
- `GET /api/storage/knowledge/concepts` - List concepts
- `POST /api/storage/knowledge/concepts/add` - Add concept
- `GET /api/storage/knowledge/relationships` - List relationships
- `GET /api/storage/stats` - Storage statistics
- `POST /api/storage/query` - Query storage

---

### 20. Store API
**Prefix:** `/store`  
**Purpose:** Simple document storage (used by scrapers)

**Routes:**
- `POST /store/<source>/<id>` - Store document
- `GET /store/<source>/<id>` - Retrieve document
- `DELETE /store/<source>/<id>` - Delete document

**Example:**
```bash
# Scrapers use this
curl -X POST http://aio-01:5000/store/arxiv/2024.12345 \
  -H "Content-Type: application/json" \
  -d '{"title": "Paper Title", "abstract": "..."}'
```

---

### 21. Tasks API
**Prefix:** `/api/tasks`  
**Purpose:** Task queue management with priority

**Routes:**
- `GET /api/tasks/` - List tasks
- `POST /api/tasks/claim` - Claim next task
- `POST /api/tasks/<task_id>/complete` - Mark complete
- `POST /api/tasks/<task_id>/fail` - Mark failed
- `POST /api/tasks/` - Create new task
- `GET /api/tasks/stats` - Task queue statistics
- `GET /api/tasks/<task_id>` - Get task details
- `DELETE /api/tasks/<task_id>` - Delete task
- `GET /api/tasks/health` - Task system health

---

### 22. Workflows API
**Prefix:** `/api/workflows`  
**Purpose:** Multi-AI workflow tracking and analytics

**Routes:**
- `POST /api/workflows/create` - Create workflow execution
- `GET /api/workflows/executions/<execution_id>` - Get execution details
- `POST /api/workflows/workers/add` - Add worker result
- `POST /api/workflows/complete` - Mark workflow complete
- `GET /api/workflows/summary` - Workflow summary statistics
- `POST /api/workflows/search` - Search workflows (similarity)
- `GET /api/workflows/learnings` - Extract learnings

**Example:**
```json
POST /api/workflows/create
{
  "workflow_id": "wf_abc123",
  "workflow_name": "deep-research",
  "task_description": "Research quantum computing 2026",
  "total_workers": 8
}
```

---

## Common Patterns

### Authentication
Currently: **None** (internal network only)  
Future: JWT tokens via `/api/admin/login`

### Rate Limiting
Handled by Redis Sentinel (aio-01, server-01, server-02)

### Error Responses
```json
{
  "error": "ValidationError",
  "message": "Missing required field: task_description",
  "status": 400
}
```

### Success Responses
```json
{
  "status": "success",
  "data": { ... },
  "metadata": {
    "timestamp": "2026-07-07T12:00:00Z",
    "duration_ms": 123
  }
}
```

---

## Database Backends

| Blueprint | Database | Port |
|-----------|----------|------|
| Learning | PostgreSQL | aio-01:5433 |
| Monitoring | PostgreSQL | server-ap:5432 |
| Costs | PostgreSQL | server-ap:5432 |
| Graph | OrientDB | aio-01:2424 |
| Queue | PostgreSQL | aio-01:5433 |
| Workflows | PostgreSQL | aio-01:5433 |

---

## Integration Notes

**For GitHub export:**
- ✅ This blueprint map is portable
- ✅ API contracts are stable
- ✅ Database schemas documented separately
- ❌ Credentials not included (use env vars)

**For other AI systems:**
- Use this reference to call specific endpoints
- All routes accept/return JSON
- Embed generation available via `/api/embeddings/generate`
- Workflow tracking automatic via `/api/workflows/*`

---

**Last Updated:** 2026-07-07  
**Maintained by:** Orchestrator Development Team
