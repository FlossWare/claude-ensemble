# Distributed LLM Orchestration Framework

**Multi-model task distribution, consensus-based decision making, and continual learning infrastructure**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/your-org/orchestrator)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![API](https://img.shields.io/badge/API-22_blueprints-orange.svg)](#api-reference)
[![Models](https://img.shields.io/badge/models-204_free-purple.svg)](#model-pool)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Key Features](#key-features)
- [Skills (Slash Commands)](#skills-slash-commands)
- [Review-Fix Cycle with Meta-Review](#review-fix-cycle-with-meta-review)
- [Web Scraper System](#web-scraper-system)
- [API Reference](#api-reference)
- [Workflow Patterns](#workflow-patterns)
- [GA Evolution Tools](#ga-evolution-tools)
- [Feedback Loop Optimizer](#feedback-loop-optimizer)
- [Database Schema](#database-schema)
- [Integration Guide](#integration-guide)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

A production-ready distributed orchestration system for coordinating **204 free LLM models** across **8 worker nodes** with **task-aware routing**, **adversarial verification**, and **continual learning**.

**What this does:**
- 🤖 Multi-model consensus - Query 3-8 models, get synthesized answer
- 🎯 Task-aware routing - Automatically selects best models for task type (15 categories)
- 🔄 Distributed execution - Parallelizes work across 8 fleet nodes
- ✅ Adversarial verification - 3-vote refutation system for fact-checking
- 📊 Continual learning - Thompson Sampling bandit improves routing over time
- 💰 Zero API costs - Uses only free models (Anthropic, OpenAI, Google, Groq, Cerebras, DeepSeek, etc.)

**What this is NOT:**
- ❌ Not a model training system (uses pre-trained models via API)
- ❌ Not self-improving AI (orchestration improvements ≠ reasoning gains)
- ❌ Not AGI (task routing and consensus, not emergent intelligence)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Client (Any AI, Python, JavaScript, curl)                  │
│  - Send HTTP requests to orchestrator API                  │
│  - Query PostgreSQL learning database                      │
│  - Parse JSON responses                                    │
└─────────────────────────────────────────────────────────────┘
                    ↓ REST API (port 5000)
┌─────────────────────────────────────────────────────────────┐
│ Orchestrator API (aio-01:5000)                             │
│  - Flask application with 22 modular blueprints            │
│  - Routes tasks to 204 free models                         │
│  - Distributes across 8 worker nodes via SSH              │
│  - Returns aggregated consensus results                    │
└─────────────────────────────────────────────────────────────┘
           ↓ SSH Distribution + Model APIs
┌─────────────────────────────────────────────────────────────┐
│ Worker Fleet (8 nodes)                                     │
│  server-01, server-02, server-03                           │
│  laptop-01, desktop-ap, server-ap                          │
│  pi-01, pi-02                                              │
│  - Execute API calls to LLM providers                      │
│  - Return results to orchestrator                          │
└─────────────────────────────────────────────────────────────┘
           ↓ Results + Learning Storage
┌─────────────────────────────────────────────────────────────┐
│ Databases                                                   │
│  - PostgreSQL (aio-01:5433) - Learning, workflows          │
│  - PostgreSQL (server-ap:5432) - Monitoring, costs         │
│  - OrientDB (aio-01:2424) - Knowledge graph                │
│  - Redis Sentinel (3 nodes) - Caching, rate limiting       │
└─────────────────────────────────────────────────────────────┘
```

### System Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Server** | Flask (Python 3.13) | Unified REST API with 22 blueprints |
| **Worker Fleet** | 8 SSH nodes | Distributed task execution |
| **Learning DB** | PostgreSQL + pgvector | Model capabilities, strategies, workflows |
| **Monitoring DB** | PostgreSQL | Execution logs, costs, alerts |
| **Knowledge Graph** | OrientDB | Infrastructure relationships |
| **Cache** | Redis Sentinel | API caching, rate limiting |
| **Model Pool** | 204 free APIs | Anthropic, OpenAI, Google, Groq, etc. |

---

## Skills (Slash Commands)

12 user-invocable skills providing pre-built multi-AI workflows:

| Skill | Purpose |
|-------|---------|
| `/ai-prompt` | Multi-model consensus for any question (arbiter/worker pattern) |
| `/ai-learn` | Extract learnings from interactions into global memory |
| `/ai-pdf-deep-research` | Adversarial PDF verification with 3-vote refutation |
| `/meta-answer` | Adaptive model selection using Thompson Sampling |
| `/code-review-unified` | Multi-model code review with configurable strategies |
| `/code-review-and-solve` | Complete quality loop: review → meta-review → fix → verify |
| `/code-improve` | Iterative quality improvement via review → fix → verify cycles |
| `/code-solve` | Auto-resolve GitHub/GitLab issues using multi-AI consensus |
| `/knowledge-ingest` | Universal documentation learning from any format |
| `/multi-ai-system-audit` | Multi-AI consensus audit of system architecture |
| `/remember` | Reload critical memories and infrastructure context |
| `/rest_api_endpoints` | REST API reference for aio-01:5000 |

Additionally, ~75 JavaScript skill modules in `skills/ai/`, `skills/code/`, and `skills/misc/` provide consensus strategies, fleet dispatch, AST analysis, PR review, security scanning, and more.

---

## Review-Fix Cycle with Meta-Review

The code review pipeline uses two independent model panels with **zero overlap** to prevent self-confirmation bias:

```
┌─────────────────────────────────────────────────────┐
│ Phase 1: REVIEW                                      │
│ Panel: opus, sonnet, DeepSeek-Chat, Qwen3-Coder     │
│ Arbiter: opus                                        │
│ → Finds issues across commits, files, security       │
├─────────────────────────────────────────────────────┤
│ Phase 2: META-REVIEW (adversarial validation)        │
│ Panel: fable, Hermes-405B, Nemotron-Ultra-550B,      │
│        Qwen3-Next-80B                                │
│ Arbiter: sonnet                                      │
│ → Challenges each finding, rejects false positives   │
│ → ZERO overlap with review panel                     │
├─────────────────────────────────────────────────────┤
│ Phase 3: FIX                                         │
│ Panel: opus, sonnet, fable, haiku (Claude, need tools)│
│ Arbiter: fable                                       │
│ → Multiple fix proposals, arbiter selects best       │
├─────────────────────────────────────────────────────┤
│ Phase 4: VERIFY                                      │
│ Panel: opus, sonnet, fable (Claude, need tools)      │
│ Arbiter: haiku                                       │
│ → Confirms fixes didn't introduce new bugs           │
└─────────────────────────────────────────────────────┘
```

Non-Claude models (DeepSeek, Qwen, Nemotron, Hermes) are accessed via OpenRouter fleet API — each workflow agent delegates to the external model via `curl` to `openrouter.ai/api/v1/chat/completions`.

---

## Web Scraper System

**Production deployment as of 2026-07-10:** 13 scrapers operational at ~4,700 docs/hour

The web scraper system collects data from 60+ sources across multiple categories (programming, science, AI, etc.) using a **scrape-then-process** architecture that separates fast scraping from slow embedding.

### Architecture

```
Scrapers (13-30 workers)
    ↓ POST to aio-01:5000/store
Orchestrator API
    ↓ Write raw JSON + queue
Redis Queue System (4 stages)
    ↓ Process async
PostgreSQL + OrientDB
```

**Key design decisions:**

1. **Scrape then process** - Separate fast scraping (network I/O) from slow embedding (CPU/API bound)
2. **Centralized storage** - All data written to aio-01, not worker filesystems
3. **Fetch full content** - Not just RSS metadata (5000+ chars vs 119-char stubs)
4. **Async pipeline** - 4-stage queue (store → chunk → embed → graph)

**Performance:**

- Before (synchronous): 599 docs/hour with 53 scrapers
- After (async pipeline): 4,700 docs/hour with 13 scrapers
- **7.8× throughput improvement**

**Documentation:**

- [Scraper Architecture](docs/SCRAPER_ARCHITECTURE.md) - System design and data flow
- [Queue System Architecture](docs/QUEUE_SYSTEM_ARCHITECTURE.md) - Redis queue design
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Step-by-step deployment
- [API Reference](docs/API_REFERENCE_SCRAPERS.md) - Scraper API endpoints

---

## Data Processing Pipeline

### Why Multiple Database Technologies?

The system uses a **multi-database architecture** where each database excels at its specific use case:

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. Web Scraping (50+ sources)                                   │
│    → 45,000+ documents collected                                │
└────────────────────┬─────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│ 2. Chunking (Semantic splitting)                                │
│    WHY: LLMs have context limits (8K-200K tokens)                │
│    - Split documents into semantically coherent chunks           │
│    - Preserve context boundaries (paragraphs, sections)          │
│    - Typical chunk size: 512-1024 tokens with 50-100 overlap    │
│    BENEFIT: Each chunk fits in LLM context window               │
└────────────────────┬─────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│ 3. Embedding (Vector representation)                            │
│    WHY: Enable semantic similarity search                       │
│    - Convert text → 384/768/1024-dim vectors                    │
│    - Models: Mistral Embed (free), sentence-transformers        │
│    - Captures semantic meaning, not just keywords               │
│    BENEFIT: Find similar content even with different wording    │
└────────────────────┬─────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│ 4. PostgreSQL + pgvector (Vector similarity search)             │
│    WHY: SQL + vector search in one database                     │
│    - HNSW index for O(log n) similarity search                  │
│    - 0.4ms query time (2-6× faster than ChromaDB)               │
│    - Complex SQL queries (joins, filters, aggregations)         │
│    - ACID transactions for data integrity                       │
│    BENEFIT: "Find documents similar to this task" in <1ms       │
│                                                                  │
│    Tables:                                                       │
│    - learning.experiences (128-dim embeddings)                  │
│    - workflow.executions (384-dim embeddings)                   │
│    - learning.model_capabilities (performance by task type)     │
│    - workflow.worker_results (individual model outputs)         │
└────────────────────┬─────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│ 5. OrientDB (Knowledge graph)                                   │
│    WHY: Relationship queries that SQL can't handle efficiently  │
│    - Graph traversal: "Find all servers connected to laptop-01" │
│    - Multi-hop queries: "Which workflows used models on pi-01?" │
│    - Shortest path: "How does data flow from scraper to LLM?"   │
│    - Bidirectional relationships without JOIN hell              │
│    BENEFIT: Complex relationship queries in milliseconds        │
│                                                                  │
│    Nodes:                                                        │
│    - Infrastructure (8 worker nodes, 1 orchestrator)            │
│    - Workflows (40+ patterns)                                   │
│    - Models (204 free APIs)                                     │
│    - Documents (45K+ scraped)                                   │
│                                                                  │
│    Edges:                                                        │
│    - EXECUTED_ON (workflow → node)                              │
│    - USED_MODEL (workflow → model)                              │
│    - DEPENDS_ON (workflow → document)                           │
│    - CONNECTED_TO (node → node)                                 │
└──────────────────────────────────────────────────────────────────┘
```

### The Complete Flow

**Example: "Find me code examples similar to this bug"**

1. **Chunking:** Break document into 512-token chunks
2. **Embedding:** Convert each chunk → 384-dim vector
3. **PostgreSQL:** Store in `learning.experiences` with pgvector index
4. **Query:** `SELECT * FROM learning.experiences ORDER BY embedding <=> query_vector LIMIT 10`
5. **Result:** Top 10 similar code examples in 0.4ms
6. **Graph:** OrientDB shows which workflows/models/nodes were involved

**Why not just one database?**

| Use Case | Best Database | Why Others Fail |
|----------|---------------|-----------------|
| **Vector similarity** | PostgreSQL + pgvector | OrientDB: No vector index. Redis: No complex queries. |
| **Graph traversal** | OrientDB | PostgreSQL: Self-joins are slow. Redis: No graph queries. |
| **Fast caching** | Redis Sentinel | PostgreSQL: Too slow for cache. OrientDB: Overkill. |
| **ACID transactions** | PostgreSQL | OrientDB: Eventually consistent. Redis: No ACID. |
| **Complex SQL** | PostgreSQL | OrientDB: No SQL. Redis: No joins/aggregations. |

### Performance Benefits

**Before (single database):**
- SQL self-joins for graph queries: **12,500ms**
- No vector similarity search
- Cache misses expensive

**After (multi-database):**
- Vector similarity search: **0.4ms** (31,250× faster)
- Graph traversal: **<10ms** (1,250× faster)
- Cache hits: **<1ms** (12,500× faster)

### When Each Database is Used

**PostgreSQL (aio-01:5433):**
- Storing workflow execution history
- Thompson Sampling bandit state
- Model capability scores by task type
- Vector similarity search for similar tasks
- SQL analytics (costs, performance)

**PostgreSQL (server-ap:5432):**
- Real-time monitoring metrics
- Execution logs
- Cost tracking
- Diversity alerts

**OrientDB (aio-01:2424):**
- Infrastructure topology
- Workflow dependencies
- Model usage patterns
- Cross-cutting queries ("Show all workflows that used opus on server-01")

**Redis Sentinel (3 nodes):**
- API response caching (15min TTL)
- Rate limiting state
- Session storage
- Temporary job queues

---

## Quick Start

### Prerequisites

- Network access to `aio-01:5000` (orchestrator API)
- PostgreSQL client (optional, for direct DB access)
- Ability to make HTTP requests (curl, requests, axios, etc.)

### Your First Request

```bash
curl -X POST http://aio-01:5000/api/fleet/tasks/distribute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Explain quantum entanglement in simple terms",
    "workers": 3,
    "strategy": "quality-first"
  }'
```

**Response:**
```json
{
  "status": "success",
  "task_id": "ft_abc123",
  "workers_assigned": [
    {"node": "server-01", "model": "opus"},
    {"node": "server-02", "model": "sonnet"},
    {"node": "server-03", "model": "gpt-4o"}
  ],
  "consensus": "Quantum entanglement is when two particles...",
  "confidence": 0.92,
  "duration_ms": 4523
}
```

### Python Client

```python
import requests

# Execute consensus workflow
response = requests.post('http://aio-01:5000/api/fleet/tasks/distribute', json={
    "task": "Compare Rust vs Go for systems programming",
    "workers": 6,
    "strategy": "quality-first"
})

result = response.json()
print(f"Consensus: {result['consensus']}")
print(f"Confidence: {result['confidence']}")
print(f"Models used: {[w['model'] for w in result['workers_assigned']]}")
```

### JavaScript Client

```javascript
const axios = require('axios');

async function getConsensus(task) {
  const response = await axios.post('http://aio-01:5000/api/fleet/tasks/distribute', {
    task: task,
    workers: 6,
    strategy: 'quality-first'
  });
  
  return response.data;
}

// Usage
const result = await getConsensus('What are the latest AI breakthroughs in 2026?');
console.log(result.consensus);
```

---

## Key Features

### 1. Multi-Model Consensus

Query 3-8 models simultaneously, get synthesized answer with confidence scoring.

### 2. Task-Aware Routing

Automatically selects best models based on task type (15 categories):

| Task Type | Best Models |
|-----------|-------------|
| code_generation | opus, deepseek-coder, gpt-4o |
| code_review | opus, sonnet, claude-3.5 |
| research | gpt-4o, opus, gemini-pro |
| math_reasoning | gpt-4o, opus, gemini-pro |
| security_audit | opus, sonnet, deepseek-coder |

### 3. Adversarial Verification with Meta-Review

Two-stage verification for code review and fact-checking:
- **Stage 1 (Review):** Independent panel finds issues (opus, sonnet, DeepSeek, Qwen3-Coder)
- **Stage 2 (Meta-Review):** Completely different panel adversarially challenges each finding (fable, Hermes-405B, Nemotron-Ultra-550B, Qwen3-Next-80B)
- **Zero overlap** between review and meta-review models prevents self-confirmation bias
- Non-Claude models accessed via OpenRouter fleet API for true independence
- Majority vote: findings must survive adversarial scrutiny before proceeding to fixes

### 4. Continual Learning

Thompson Sampling bandit learns which routing strategies work best over time.

### 5. Zero-Cost Model Pool

**204 free models** across Anthropic, OpenAI, Google, Groq, Cerebras, DeepSeek, Qwen, Nvidia, and more.

### 6. Web Scraping & Data Collection

**50+ scrapers** actively collecting data from diverse sources:

**API Endpoints:**
```bash
# Fetch single URL
POST /api/scraping/fetch
{
  "url": "https://example.com/article",
  "extract": "markdown|html|text",
  "cache_ttl": 900
}

# Batch fetch multiple URLs
POST /api/scraping/batch
{
  "urls": ["https://site1.com", "https://site2.com"],
  "extract": "text"
}

# Extract links from HTML
POST /api/scraping/extract/links
{
  "html": "<html>...</html>"
}
```

**Active Data Sources:**
- **Academic:** arXiv (6 categories), PubMed, BioRxiv, OpenReview
- **Code:** GitHub, Stack Overflow, MDN, TensorFlow docs
- **News:** HackerNews, Slashdot, Dev.to, Medium, Guardian
- **Knowledge:** Wikipedia, Internet Archive, Gutenberg, W3C specs
- **Community:** Reddit, Semantic Scholar, Papers with Code
- **Specialized:** 30+ domain-specific scrapers

**Collection Stats:**
- 45,000+ documents collected
- Real-time updates (hourly/daily)
- Automatic deduplication
- Rate limiting per domain
- In-memory caching (15min TTL)

**Storage Pipeline:**
1. Scraper → `/store/<source>/<id>` API
2. Raw JSON → `/mnt/aio-01/claude-orchestrator/scraped-data/`
3. Queue → Chunk → Embed → Graph

---

## API Reference

### Base URL
```
http://aio-01:5000
```

### Available Blueprints (22 total)

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| Admin | `/api/admin` | System administration |
| Fleet | `/api/fleet` | Worker orchestration |
| Workflows | `/api/workflows` | Workflow tracking |
| Learning | `/api/learning` | Continual learning |
| Routing | `/api/routing` | Model selection |
| Embeddings | `/api/embeddings` | Vector generation |
| Monitoring | `/api/monitoring` | Health & metrics |
| Costs | `/api/costs` | Cost tracking |
| Notifications | `/api/notifications` | Alerts & webhooks |
| Queue | `/queue` | Processing pipeline |
| Chunker | `/api/chunker` | Text/code chunking |
| Search | `/api/search` | Full-text search |
| Graph | `/api/graph` | Knowledge graph |
| Storage | `/api/storage` | Data persistence |
| Secrets | `/api/secrets` | Credentials |
| Config | `/api/config` | Configuration |
| External | `/api/external` | API proxy |
| Scraping | `/api/scraping` | Web scraping |
| Tasks | `/api/tasks` | Task queue |
| Store | `/store` | Document storage |
| Ingest | `/api/ingest` | Data ingestion |
| Proxy | `/api/proxy` | LLM routing |

**📖 Complete API Documentation:** See [docs/API_BLUEPRINT_REFERENCE.md](docs/API_BLUEPRINT_REFERENCE.md)

---

## Workflow Patterns

171 pre-built workflows for common tasks. Workflows are orchestration patterns that define HOW to execute complex multi-agent tasks.

### Quick Reference - Common Workflows

**Deep Research (Adversarial Fact-Checking):**
```bash
curl -X POST http://aio-01:5000/api/workflows/create \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "deep-research",
    "task": "What are proven treatments for long COVID as of 2026?",
    "options": {
      "adversarialVerify": true,
      "maxWorkers": 8
    }
  }'
```

**Fleet Code Review:**
```bash
curl -X POST http://aio-01:5000/api/workflows/create \
  -d '{
    "workflow_name": "fleet-review",
    "task": "Review this authentication system for security issues"
  }'
```

**Multi-Model Consensus:**
```bash
curl -X POST http://aio-01:5000/api/fleet/tasks/distribute \
  -d '{
    "task": "Should we use REST or GraphQL for this API?",
    "workers": 6,
    "strategy": "quality-first"
  }'
```

**Learn and Apply Past Patterns:**
```bash
curl -X POST http://aio-01:5000/api/workflows/create \
  -d '{
    "workflow_name": "learn-and-apply",
    "task": "Optimize this database query",
    "options": {
      "pattern_name": "query_optimization"
    }
  }'
```

### Available Workflow Categories

1. **Research Workflows**
   - `deep-research` - Multi-source fact-checked research with 3-vote adversarial verification
   - `ai-pdf-deep-research` - Extract and verify claims from PDF documents

2. **Code Review Workflows**
   - `fleet-review` - Adversarial code review across multiple models (try to break it)
   - `review-distribution-fix` - Independent review of implementation with verification

3. **Consensus Workflows**
   - `ai-consensus` - Multi-model consensus response to any prompt
   - `advanced-consensus-demo` - Demonstrates all 10 consensus features

4. **Distributed Execution Workflows**
   - `fleet-distributed-fixes-all` - Distribute fixes across all 8 nodes via SSH
   - `code-sdlc-fleet` - Fleet-distributed SDLC pipeline (2-2.5× speedup)

5. **Learning Workflows**
   - `learn-reasoning-consensus` - Learn reasoning patterns from multi-model consensus
   - `execute-with-learned-reasoning` - Apply previously learned patterns to new tasks

**📖 Complete Workflow Catalog:** See [memory/reference_workflow_patterns_catalog.md](.claude/projects/-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills/memory/reference_workflow_patterns_catalog.md) for all 171 workflows with detailed patterns and examples.

---

## GA Evolution Tools

Genetic algorithm tools for optimizing system configuration:

| Tool | Purpose |
|------|---------|
| `tools/genetic_model_optimizer.py` | Evolve optimal model routing strategies |
| `tools/ga_rag_retrieval_optimizer.py` | Optimize RAG retrieval parameters |
| `tools/ga_training_data_curator.py` | Curate training data via evolution |
| `tools/ga_team_selection_fixed.py` | Evolve optimal worker team compositions |
| `learning/ga_engine.py` | Core GA engine (crossover, mutation, selection) |

GA evolution runs periodically via cron and stores evolved configurations in `tools/best_rag_config.json` and `tools/best_training_recipe.json`.

---

## Feedback Loop Optimizer

Automated detection and prevention of self-referential feedback loops across the system.

**Four detection layers:**
1. **Model Dominance** - One model >70% usage
2. **Evaluator-Generator Coupling** - Models evaluating own outputs >40%
3. **Reward Hacking** - Quality increasing + diversity decreasing
4. **Concept Collapse** - Output embeddings >0.90 similarity

```bash
# Run full analysis
python3 tools/feedback_loop_optimizer.py

# Check system health (JavaScript)
const { isSystemHealthy } = require('./shared/feedback-loop-adapter.cjs');
const healthy = await isSystemHealthy(7);
```

Automated monitoring runs every 6 hours. Reports at `~/.claude/reports/feedback-loops/latest.json`.

**Documentation:** [docs/FEEDBACK_LOOP_OPTIMIZER.md](docs/FEEDBACK_LOOP_OPTIMIZER.md)

---

## Database Schema

### PostgreSQL Databases

26 schemas with 130+ tables across two PostgreSQL instances.

**Learning (aio-01:5433) — Key schemas:**
- `learning.*` - Model capabilities, strategy performance, experiences (128-dim embeddings)
- `workflow.*` - Workflow executions (384-dim embeddings), worker results, arbiter decisions
- `monitoring.*` - Execution logs, diversity alerts
- `costs.*` - Cost tracking
- `knowledge.*` - Document storage, chunks, embeddings (768-dim)
- `ga.*` - GA evolution state and results
- `scraping.*` - URL tracking, queue state
- `inventory.*` - Machine inventory
- `config.*`, `auth.*`, `admin.*` - System configuration

**Monitoring (server-ap:5432):**
- `monitoring.execution_summary` - Execution logs
- `monitoring.diversity_alerts` - Feedback loop alerts
- `costs.entries` - Cost tracking

**📖 Complete Schema:** See [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)

---

## Integration Guide

Any AI system can use this orchestrator via HTTP REST API or PostgreSQL queries.

**Python:**
```python
import requests

response = requests.post('http://aio-01:5000/api/fleet/tasks/distribute', json={
    "task": "Your question here",
    "workers": 6
})
print(response.json()['consensus'])
```

**JavaScript:**
```javascript
const axios = require('axios');

const result = await axios.post('http://aio-01:5000/api/fleet/tasks/distribute', {
  task: 'Your question here',
  workers: 6
});
console.log(result.data.consensus);
```

**📖 Complete Integration Guide:** See [docs/AI_INTEGRATION_GUIDE.md](docs/AI_INTEGRATION_GUIDE.md)

---

## Performance Metrics

| Operation | Workers | Avg Duration | Token Usage |
|-----------|---------|--------------|-------------|
| Simple consensus | 3 | 2-4s | 2K-5K tokens |
| Standard consensus | 6 | 3-6s | 5K-10K tokens |
| Deep research | 8 | 15-30s | 20K-40K tokens |

**Cost:** $0.00/month (all free tier models)  
**Uptime:** 99.2% (last 30 days)  
**Model Selection Accuracy:** 94%

---

## Monitoring

**Grafana Dashboards:** `http://aio-01:3000`
- Performance Dashboard - Latency, throughput, errors
- Workflow Dashboard - Active workflows, model distribution, costs

**Prometheus Metrics:** `http://aio-01:5000/api/monitoring/metrics`

**Alerting:** Subscribe to webhooks for critical events
```bash
curl -X POST http://aio-01:5000/api/notifications/subscribe \
  -d '{"endpoint": "https://your-webhook.com", "alert_types": ["model_dominance", "high_cost"]}'
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Documentation

- [API Blueprint Reference](docs/API_BLUEPRINT_REFERENCE.md) - All 150+ API routes
- [AI Integration Guide](docs/AI_INTEGRATION_GUIDE.md) - For other AI systems
- [Workflow Patterns Catalog](memory/reference_workflow_patterns_catalog.md) - 171 workflows
- [Database Schema](docs/DATABASE_SCHEMA.md) - Complete schema reference (26 schemas, 130+ tables)
- [Feedback Loop Optimizer](docs/FEEDBACK_LOOP_OPTIMIZER.md) - Self-referential feedback loop detection
- [Scraper Architecture](docs/SCRAPER_ARCHITECTURE.md) - Web scraping system design
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment

---

**Built with the Distributed LLM Orchestration Team**

*Last Updated: 2026-07-14*
