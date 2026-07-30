# Architecture Guide

**Version**: 13 | **Last Updated**: 2026-07-28 | **Status**: Production

---

## Stability Markers

Every section in this document carries a maturity label. Read them before building on an assumption.

| Marker | Meaning |
|--------|---------|
| `Stable Principle` | Architectural decision expected to hold for years. Changing it would require rearchitecting. |
| `Validated` | Measured in production or benchmarks. The numbers are real. |
| `Experimental` | Under active evaluation. Implementation details will change; the problem it solves will not. |
| `Proposed` | Design intent, not yet implemented. May never ship. |

---

## Table of Contents

- [System Overview](#system-overview)
- [Core Principles](#core-principles)
- [Fleet Architecture](#fleet-architecture)
- [Data Architecture](#data-architecture)
- [Multi-AI Consensus](#multi-ai-consensus)
- [Knowledge Pipeline](#knowledge-pipeline)
- [Optimization Techniques](#optimization-techniques)
- [GA Meta-Optimizer](#ga-meta-optimizer)
- [Learning System](#learning-system)
- [Monitoring and Operations](#monitoring-and-operations)
- [Architecture Decision Records](#architecture-decision-records)
- [Known Limitations](#known-limitations)
- [Cross-References](#cross-references)

---

## System Overview

FlossWare is a distributed LLM orchestration framework. It coordinates 200+ pre-trained AI models across an 11-machine fleet to perform software engineering tasks with multi-model consensus and adversarial verification.

**What this system is:**
- A distributed control system over pre-trained LLMs
- Multi-model orchestration with feedback-driven routing
- Fleet-based task distribution (11 machines: 1 controller, 5-7 workers, 2 monitoring hosts, 2 dev workstations)
- Consensus-based evaluation (multi-model voting with adversarial review)

**What this system is not:**
- Not a training system (no model weight updates)
- Not self-improving AI (same model capabilities throughout)
- Not emergent intelligence (orchestration improvements ≠ reasoning gains)

All improvements are attributable to: routing efficiency, task decomposition, iterative retry logic, and evolutionary configuration optimization. Not to model intelligence gains.

**Three primary functions:**

1. **Full SDLC Automation** — Code review, issue solving, testing, PR review, security auditing, documentation generation, orchestrated with multi-AI consensus.

2. **Multi-AI Consensus** — Every meaningful decision is verified by multiple AI models from multiple providers to reduce false positives, catch blind spots, and produce higher-confidence results.

3. **Distributed Processing** — A fleet of heterogeneous machines parallelizes bulk processing (scraping, embedding, code review) with SSH-based orchestration.

---

## Core Principles

`Stable Principle` — These decisions define the system's identity. Changing any one would require rearchitecting.

### Orchestration over Training

This system orchestrates pre-trained models. It does not fine-tune, distill, or modify model weights. Model capabilities remain identical to what the provider ships. System behavior improves through better routing, decomposition, and configuration — not through model improvement.

**Why:** CPU fine-tuning is 50-100x slower than GPU. API fine-tuning costs $30-50 per run. Neither is justified when routing optimization yields comparable gains at zero marginal cost. Local model infrastructure was archived 2026-06-28 after the cost analysis showed API-only was strictly superior for this fleet's hardware.

**Tradeoff acknowledged:** We depend entirely on provider model quality. If all providers degrade simultaneously, we have no fallback. This is acceptable because provider competition makes simultaneous regression unlikely.

### Provider Independence

No single provider owns any decision. Every consensus operation uses models from at least 2 providers. Review and meta-review panels have zero model overlap.

**Why:** Same-provider models share training biases, leading to ~60-70% error correlation. Cross-provider correlation drops to ~35-50%, achieving approximately 94% blind spot coverage with 6+ models.

**Tradeoff acknowledged:** More providers means more API keys, more failure modes, more latency variance. We accept this complexity because correlated errors are worse than uncorrelated failures.

### Workers Never Touch Databases

Fleet workers (server-01, server-02, server-03, pi-01, pi-02, cabin-laptop-01, cabin-laptop-02) never connect directly to PostgreSQL, OrientDB, or any persistent store. All persistence goes through the REST API on aio-01:5000.

**Why:** Workers are ephemeral and heterogeneous. Direct database connections from 8+ machines create connection pool exhaustion, schema version skew, and make it impossible to audit data flow. A single REST gateway enforces validation, rate limiting, and audit logging in one place.

**Tradeoff acknowledged:** Every persistence operation adds one network hop (~1-5ms). For a system where LLM API calls take 2-30 seconds, this overhead is negligible.

### REST API as Single Gateway

All database access goes through `aio-01:5000`. No direct PostgreSQL connections (port 5433), no direct Redis connections (port 6379), no direct OrientDB connections (port 2424). The REST API is the only authorized path to persistent state.

**Why:** Single point of validation, logging, and access control. When something goes wrong with data, there is exactly one place to look: the API server logs.

**Tradeoff acknowledged:** Single point of failure. If the API goes down, the entire system stops persisting. Mitigated by: the API is a lightweight Flask app on aio-01 (the most reliable node), and workers gracefully degrade (they continue processing and retry storage).

### Independent Adversarial Review

Every review pipeline uses two panels with zero model overlap. The review panel finds issues. The meta-review panel adversarially validates those findings. Models that generate cannot evaluate their own output.

**Why:** Self-evaluation bias is the single largest quality risk in multi-model systems. A model rating its own output produces systematically inflated scores. Zero overlap between panels eliminates this correlation.

**Tradeoff acknowledged:** Two panels means twice the API calls per review cycle. We accept this cost because catching one false positive is worth more than saving one API call.

---

## Fleet Architecture

`Stable Principle` — The topology and SSH orchestration are stable. Node count may change; the pattern will not.

### Topology

```
                         ┌─────────────┐
                         │   aio-01    │  Controller / Orchestrator
                         │  2C, 8GB   │  REST API, PostgreSQL, Redis, OrientDB
                         │  Port 5000  │  NEVER runs worker tasks
                         └──────┬──────┘
                                │
          ┌─────────┬───────────┼───────────┬─────────┐
          │         │           │           │         │
     ┌────┴────┐ ┌──┴───┐ ┌────┴────┐ ┌────┴───┐ ┌──┴────┐
     │server-01│ │server│ │server-03│ │  pi-01 │ │ pi-02 │
     │ 8C,15GB │ │  -02 │ │ 8C,32GB │ │  ARM   │ │  1GB  │
     └─────────┘ │8C,32G│ └─────────┘ └────────┘ └───────┘
                 └──────┘
          Workers (always-on when home network active)

     ┌────────────┐  ┌────────────┐
     │cabin-      │  │cabin-      │  Workers (192.168.2.x network)
     │laptop-01   │  │laptop-02   │  Active when at cabin
     │ 4C, 32GB   │  │ 4C, 32GB   │  Also run embedding services
     └────────────┘  └────────────┘

     ┌────────────┐  ┌────────────┐
     │ desktop-ap │  │ server-ap  │  Low-resource workers
     │   1GB      │  │   1GB      │  (always-on)
     └────────────┘  └────────────┘
```

**laptop-01 / laptop-02**: Development workstations (4C/8T, 32GB). NOT fleet workers. Run Claude Code sessions, embedding services, and development tools.

**cabin-laptop-01 / cabin-laptop-02**: Remote cabin fleet workers and dev workstations (192.168.2.x network). Registered as fleet workers 2026-07-25. Reach aio-01 via SSH ProxyJump through pi-01. Also run embedding services.

**desktop-ap / server-ap**: Low-resource always-on workers (1GB RAM each). Limited to lightweight tasks (scraping, health checks). Cannot run Claude Code sessions or embedding services.

### Fleet Composition is Location-Dependent

The active fleet varies by physical location:

| Location | Active Workers | Dev Workstations |
|----------|---------------|-----------------|
| **Home** | server-01/02/03, pi-01/02, desktop-ap, server-ap (7 workers) | laptop-01/02 |
| **Cabin** | cabin-laptop-01/02, pi-01/02, desktop-ap, server-ap (6 workers) | cabin-laptop-01/02 |

pi-01, pi-02, desktop-ap, and server-ap are always reachable regardless of location.

### SSH over Kubernetes

**Decision:** SSH-based fleet orchestration, not Kubernetes.

**Why:** 9 heterogeneous machines (x86_64 and ARM, 1GB to 31GB RAM, different OS versions). Kubernetes requires: container runtime on every node, etcd cluster, control plane, networking overlay, persistent volume provisioner. For 9 machines, this is more infrastructure than application. SSH requires: key-based auth and `sshd`. Already present on every machine.

**Tradeoff acknowledged:** No automatic rescheduling, no health-based pod migration, no declarative desired state. If a worker dies, we notice via monitoring and restart manually. Threshold to reconsider: ~15+ machines or if we need automatic failover.

**Alternatives considered:**
- Kubernetes: Too heavy for 9 heterogeneous nodes
- Ansible: Good for provisioning, wrong abstraction for real-time task dispatch
- Message queue (RabbitMQ/Kafka): Adds a broker dependency; SSH is already a reliable transport
- HTTP-based dispatch: Would require an agent on every worker; SSH is already there

### Controller/Worker Separation

aio-01 is the controller and orchestrator. It runs the REST API, databases, and coordination logic. It **never** runs worker tasks (embedding, scraping, code review). This separation exists because controller overload cascades into system-wide failures — if the API becomes unresponsive because the machine is saturated with worker tasks, every other worker loses its persistence path.

---

## Data Architecture

`Stable Principle` — The triple-store pattern and REST gateway are stable. Individual database choices could change; the separation of concerns will not.

### Triple-Store Architecture

| Store | Technology | Purpose | Access |
|-------|-----------|---------|--------|
| **Relational + Vector** | PostgreSQL + pgvector | Structured data, embeddings, similarity search | REST API :5000 |
| **Queue + Cache** | Redis 8.0 | Task queues, rate limiting, ephemeral state | REST API :5000 |
| **Graph** | OrientDB | Infrastructure relationships, knowledge graph | REST API :5000 |

**PostgreSQL schemas:**
- `learning.*` — Model capabilities, strategy performance, experiences, embeddings
- `workflow.*` — Workflow executions, worker results, arbiter decisions
- `monitoring.*` — Execution logs, diversity alerts, cost tracking
- `costs.*` — API cost accounting

**Why three stores:** Each store serves a different query pattern. PostgreSQL handles structured queries and vector similarity. Redis handles ordered queues and atomic operations (embedding queue, rate limits). OrientDB handles graph traversal (entity relationships, infrastructure topology). Using one store for all three would mean suboptimal performance in at least two dimensions.

**Tradeoff acknowledged:** Three databases means three things to back up, monitor, and keep running. Operational burden is real but bounded — all three run on aio-01, backed up daily to NFS.

### REST API Gateway

```
Workers / Clients
       │
       ▼
  aio-01:5000 (Flask)
       │
       ├── PostgreSQL (learning, workflow, monitoring, costs)
       ├── Redis (queues, cache, rate limiting)
       └── OrientDB (graph relationships)
```

All database operations are exposed as REST endpoints. Workers POST data, GET results, and never see a connection string.

**Key endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health (PG, Redis, OrientDB status) |
| `/secrets/{name}` | GET | API key retrieval |
| `/knowledge/search` | POST | Hybrid search (fulltext + vector) |
| `/pipeline/chunks/store-embeddings` | POST | Store computed embeddings |
| `/pipeline/embedding-queue/fetch` | POST | Fetch batch from embedding queue (lpop) |
| `/pipeline/embedding-queue/status` | GET | Embedding queue length |
| `/pipeline/embedding-queue/enqueue` | POST | Push chunks to embedding queue |
| `/pipeline/embedding-queue/requeue` | POST | Re-queue failed items |
| `/learning/bandits/select` | POST | Thompson Sampling model selection |
| `/learning/strategies/select-nonstationary` | POST | LinUCB contextual routing |
| `/cascade/query` | POST | LLM cascade execution |
| `/moa/query` | POST | Mixture of Agents execution |
| `/rag/corrective-search` | POST | Corrective RAG search |
| `/graph-rag/query` | POST | Graph-augmented RAG |
| `/ga/convergence` | POST | Store GA convergence data |
| `/ga/strategies` | POST | Register evolved strategies |

---

## Knowledge Pipeline

`Validated` — 381K+ documents scraped, chunked, and searchable. Pipeline throughput measured at 4,700 docs/hour.

### Pipeline Stages

```
Scrapers (69 configs, 12 domains)
       │
       ▼
  POST /pipeline/documents/store  →  PostgreSQL (raw docs)
       │
       ▼
  Rechunker (aio-01)  →  PostgreSQL (chunks)
       │                  POST /pipeline/embedding-queue/enqueue
       ▼
  Redis embedding_queue (LIST, ~2.9M items)
       │
       ▼
  Embed Workers (laptop-class machines)
       │  POST /pipeline/embedding-queue/fetch  (batch of 50)
       │  Embed locally with all-mpnet-base-v2
       │  POST /pipeline/chunks/store-embeddings
       ▼
  Searchable via POST /knowledge/search (hybrid: fulltext + pgvector)
```

**Scraper fleet:** 69 scraper configurations across 12 knowledge domains (AI/ML, Linux kernel, networking, firmware, language docs, framework docs). Workers scrape in parallel, POST documents to the REST API. Documents are stored in PostgreSQL with metadata (URL, title, category, scrape timestamp).

**Rechunker:** Runs on aio-01. Reads documents, splits into chunks (512 tokens, 37% overlap), stores chunks in PostgreSQL. Enqueues chunk IDs + content to the Redis embedding queue via `POST /pipeline/embedding-queue/enqueue`. Current corpus: 381K+ documents.

**Embed workers:** Run on laptop-class machines (cabin-laptop-01, cabin-laptop-02). REST-only — zero direct Redis or PostgreSQL connections. Fetch batches from the embedding queue via `POST /pipeline/embedding-queue/fetch`, embed locally with `all-mpnet-base-v2` (768-dim), store embeddings via `POST /pipeline/chunks/store-embeddings`. On failure, items are requeued via `POST /pipeline/embedding-queue/requeue`. Batch size ceiling: 50 chunks per request (larger batches timeout on CPU). Workers use per-instance stop flags and exponential backoff on empty queues.

**Why not embed on fleet workers:** Each embedding service instance uses ~2GB RSS (~7.5GB virtual) and ~320% CPU. Fleet workers (pi-01, pi-02) have 1GB RAM — insufficient. Embedding is restricted to laptop-class machines (4+ cores, 32GB RAM).

---

## Multi-AI Consensus

`Stable Principle` — The arbiter-worker pattern and zero-overlap review panels are stable. Model lists within panels may change.

### Arbiter-Worker Pattern

Every decision-making phase uses this pattern:

1. **Workers** (4-6 models): Each independently analyzes the same input. Different models catch different issues due to different training data and architectures.
2. **Arbiter** (1 model, rotated): Reviews all worker outputs, selects the best or synthesizes a combined answer, assigns confidence.
3. **Graceful degradation**: Failed models return `null`, filtered with `.filter(Boolean)`. The workflow continues with available models.

### Zero-Overlap Review Panels

```
REVIEW PANEL (find issues)          META-REVIEW PANEL (adversarially validate)
├── opus                            ├── fable
├── sonnet                          ├── hermes-3-llama-3.1-405b
├── deepseek-chat                   ├── nemotron-3-ultra-550b
└── qwen3-coder                     └── qwen3-next-80b

REVIEW ARBITER: opus                META-REVIEW ARBITER: sonnet
SOLVE ARBITER: fable                VERIFY ARBITER: haiku
```

**Zero overlap is non-negotiable.** If a model that generated a finding also validates it, you have circular confirmation, not adversarial review. The meta-review panel must contain no models from the review panel.

### Review → Meta-Review → Fix → Verify Pipeline

```
1. REVIEW: 4 models independently find issues
       │
       ▼
2. META-REVIEW: 4 different models adversarially challenge each finding
       │          "Try to refute this. Default to refuted if uncertain."
       ▼
3. FIX: Apply only findings that survived adversarial challenge
       │
       ▼
4. VERIFY: Confirm fixes are correct, no regressions introduced
```

This four-stage pipeline exists because single-pass review has a ~15-25% false positive rate. The adversarial meta-review kills false positives before they become wasted engineering effort.

---

## Optimization Techniques

`Experimental` — These techniques are implemented and registered on the aio-01 API. Their parameters and interactions are under active GA optimization. Current implementations are reference implementations subject to evolution.

### Technique Inventory

| # | Technique | Endpoint | Status | What It Does |
|---|-----------|----------|--------|-------------|
| 1 | Non-stationary Thompson Sampling | `/learning/bandits/select` | `Experimental` | Online model selection with decay for changing performance |
| 2 | LinUCB Contextual Bandits | `/learning/strategies/select-nonstationary` | `Experimental` | Context-aware model routing using 15-dim feature vectors |
| 3 | LLM Cascading | `/cascade/query` | `Experimental` | Tiered model escalation (free_small → free_large → paid) |
| 4 | Mixture of Agents | `/moa/query` | `Experimental` | Multi-model proposal + aggregation + arbiter synthesis |
| 5 | Corrective RAG | `/rag/corrective-search` | `Experimental` | Grade retrieved docs, reformulate if low quality |
| 6 | Graph RAG | `/graph-rag/query` | `Experimental` | Entity extraction + OrientDB graph traversal |
| 7 | Contextual Retrieval | `/pipeline/contextual-retrieval/start` | `Experimental` | Enrich chunks with surrounding context before retrieval |
| 8 | EvoPrompt | `/evolution/start` | `Experimental` | LLM-guided prompt evolution via GA |
| 9 | MAP-Elites | `/evolution/map-elites/start` | `Experimental` | Quality-diversity optimization across behavior niches |

Each technique has published academic validation (source papers). None have been validated in this system yet — that is the purpose of the GA meta-optimizer.

### Why These Nine

Each addresses a different failure mode in multi-model orchestration:

- **Thompson/LinUCB**: Model selection is a multi-armed bandit problem. Hand-picking models per task doesn't scale.
- **Cascade**: Most queries don't need expensive models. Escalate only when confidence is low.
- **MoA**: Diverse perspectives catch things single models miss. Aggregation filters noise.
- **CRAG**: Standard RAG returns irrelevant documents ~30% of the time. Grading and reformulation fix this.
- **Graph RAG**: Entity relationships aren't captured by vector similarity alone.
- **Contextual Retrieval**: Chunks lose meaning without their document context.
- **EvoPrompt**: Prompt engineering is manual and doesn't scale. Let evolution find better prompts.
- **MAP-Elites**: Single-objective optimization converges to one config. Quality-diversity finds optimal configs per niche.

---

## GA Meta-Optimizer

`Experimental` — Implemented but not yet run. Pending validation.

### The Insight

Each of the 9 techniques has dozens of configurable parameters. Combined: ~65 dimensions. The interaction effects between techniques (does CRAG + Graph RAG together outperform either alone? does a low cascade threshold waste MoA?) are impossible to discover by manual tuning. This is a combinatorial optimization problem — exactly what genetic algorithms solve.

### Pipeline Chromosome

A single chromosome encodes a complete pipeline configuration:

- **9 activation booleans**: Which techniques are active
- **~20 technique parameters**: Decay factors, thresholds, limits, pool sizes
- **1 routing strategy**: cascade_first, bandit_first, or complexity_route
- **3 model pool parameters**: Pool size, free preference, diversity weight

Total: ~65 genes per chromosome.

### Evolution Strategy

- **Population**: 30 chromosomes (5 seeded + 25 random)
- **Generations**: 100
- **Selection**: Tournament (k=5) + elitism (top 20%)
- **Crossover**: Uniform per-gene
- **Mutation**: Adaptive (0.1-0.4, increases during stagnation)
- **Fitness**: Real evaluation via 30 benchmark tasks graded by 3-model judge panel

### MAP-Elites Integration

The GA maintains a quality-diversity archive across three dimensions:
- **Cost** (free-only → paid-heavy)
- **Latency** (fast → thorough)
- **Technique count** (minimal → full)

Result: not one winner, but an archive of optimal configs per niche (fast+cheap, quality+expensive, balanced).

### Thompson Sampling Bridge

Best evolved configurations become named strategies in `learning.strategy_performance`. LinUCB then routes incoming tasks to the right evolved config based on query features. This creates the meta-learning loop: GA evolves → Thompson learns → LinUCB routes → outcomes feed GA.

### Files

| File | Purpose |
|------|---------|
| `tools/ga_pipeline_optimizer.py` | PipelineChromosome, GA loop, MAP-Elites, Thompson Sampling bridge |
| `tools/ga_pipeline_runner.py` | Configures and executes techniques per chromosome via REST API |
| `tools/ga_benchmark_suite.py` | 30 benchmark tasks with reference answers + 3-model judge panel |

---

## Learning System

`Validated` — Thompson Sampling and LinUCB are running in production. GA components are implemented but awaiting first evolution run.

This is a learning system at the orchestration layer — not model training. No model weights are updated, but the system learns which models to route to, which configurations perform best, and which technique combinations to use.

### Three Forms of Learning

| Form | Mechanism | Textbook Classification |
|------|-----------|------------------------|
| **Online learning** | Thompson Sampling (Beta distributions), LinUCB (contextual bandits) | Multi-armed bandit / reinforcement learning |
| **Evolutionary learning** | GA pipeline optimizer, MAP-Elites, EvoPrompt | Evolutionary computation |
| **Experience-based learning** | PostgreSQL experience storage with pgvector similarity search | Case-based reasoning |

**What this learning is NOT:** Model training. No weights are updated. No gradients are computed. The models remain identical to what providers ship. Learning occurs in the orchestration layer — which models to use, how to configure them, which technique combinations work.

---

## Monitoring and Operations

`Validated` — Monitoring deployed to two locations. Backup strategy is stable.

### Monitoring Stack

| Component | Primary (aio-01) | Secondary (installed, not always active) |
|-----------|-----------------|----------------------------------------|
| Prometheus | aio-01:9090 (active) | server-ap `~/bin/prometheus` (installed) |
| Alertmanager | aio-01 (active) | server-ap `~/bin/alertmanager` (installed) |
| Grafana | aio-01:3000 (active, v13.1.0) | desktop-ap `~/grafana/` (installed) |

Monitoring was redistributed to server-ap and desktop-ap (2026-07-13) to offload aio-01, but the originals on aio-01 were never stopped. As of 2026-07-28, aio-01 instances are active; server-ap/desktop-ap instances are installed but not running.

### Feedback Loop Monitoring

Automated detection and prevention of self-referential feedback loops. Runs every 6 hours via `~/bin/monitor-feedback-loops.sh`.

**Four detection layers:**
1. **Model dominance**: One model >70% of selections → diversity alert
2. **Evaluator-generator coupling**: Models evaluating own outputs >40% → bias alert
3. **Reward hacking**: Quality scores increasing + diversity decreasing → convergence alert
4. **Concept collapse**: Output embedding similarity >0.90 → homogeneity alert

### Backups

- **Schedule**: Daily at 2 AM (cron)
- **Location**: `server-ap:/exports/backups/laptop-01-learning/`
- **Retention**: 30 days
- **Script**: `~/bin/backup-learning-db.sh`

---

## Architecture Decision Records

### ADR-1: "Fleet" Terminology Instead of "Cluster"

**Context**: Heterogeneous personal computers (1GB to 31GB RAM, x86_64 and ARM, different roles).

**Decision**: Use "fleet" — a collection of diverse vessels, not a uniform compute cluster.

### ADR-2: Unified Skills with Auto-Detection

**Context**: Previously required creating 2-3 files per skill (-bulk, -fleet variants).

**Decision**: Fleet-awareness built into parent skills with auto-detection. `--fleet` and `--local` flags for explicit control.

### ADR-3: Multi-Session SSH Orchestration

**Context**: Claude Code's `parallel()` shares one API rate limit.

**Decision**: SSH to launch independent sessions on separate machines. Each session has its own rate limit, memory, and CPU.

### ADR-4: Static Configuration

**Context**: 9 machines is a small fleet.

**Decision**: Static JSON configuration, version-controlled. Threshold to reconsider: ~15+ machines.

### ADR-5: Path-Based Compliance

**Context**: Red Hat proprietary code must not leave controlled infrastructure.

**Decision**: Two-layer system: (1) fleet blocking by directory path, (2) model restrictions per path. Red Hat internal code reviewed with Claude/Anthropic only — never third-party LLMs.

### ADR-6: Cross-Provider Model Diversity

**Context**: Same-provider models share training biases.

**Decision**: Models from 3+ providers for all consensus decisions. Zero overlap between review and meta-review panels.

### ADR-7: API-Only Fleet (2026-06-28)

**Context**: Local model hosting (Ollama) required significant RAM, produced lower quality than API models, and made the fleet hardware-constrained.

**Decision**: Remove all local model infrastructure. Access 200+ models via API (OpenRouter, Anthropic, Google, Groq, Cerebras, DeepSeek).

**Why**: API models are higher quality, always up-to-date, and eliminate model download/management overhead. Free tiers across 78+ providers mean most operations cost nothing.

**Tradeoff acknowledged**: Complete dependency on internet connectivity and provider availability. No offline capability. Acceptable because the fleet's value proposition is multi-model consensus, which inherently requires network access.

### ADR-8: REST-Only Database Access (2026-06-15)

**Context**: Workers were connecting directly to PostgreSQL, causing connection pool exhaustion and making data flow impossible to audit.

**Decision**: All database access goes through the REST API on aio-01:5000. No direct database connections from any worker.

**Why**: Single point of validation, logging, and rate limiting. Connection pool managed by one process, not 8+ competing workers.

### ADR-9: Triple-Store Architecture (2026-06-15)

**Context**: ChromaDB was the original vector store. It had persistence bugs and limited query capabilities.

**Decision**: Replace with PostgreSQL + pgvector (2x faster for simple similarity, 5x faster for filtered queries) + Redis (queues, cache) + OrientDB (graph relationships).

**Why**: Each store serves its optimal query pattern. Benchmarks showed pgvector outperformed ChromaDB on every metric that mattered.

### ADR-10: Embeddings on Laptops Only (2026-07-26)

**Context**: `sentence-transformers` with `all-mpnet-base-v2` uses ~320% CPU and ~2GB RSS per service instance (model file is ~420MB; Python + PyTorch + tokenizer + batch buffers total ~2GB physical memory).

**Decision**: Embedding services run only on laptop-class machines: laptop-01, laptop-02, cabin-laptop-01, cabin-laptop-02 (4C+ CPUs, 32GB RAM). Never on fleet workers (pi-01, pi-02, desktop-ap, server-ap — 1GB RAM).

**Tradeoff acknowledged**: Embedding throughput is capped by available laptop capacity (~0.7-1.2 embeddings/second per machine with batch=50). Accepted because embedding is a batch operation, not latency-sensitive.

---

## Known Limitations

1. **Embedding throughput**: ~0.4/s per worker with batch=50 (2 workers on cabin-laptop-01 = ~0.8/s combined). Queue of ~2.9M items takes weeks to drain. Larger batches timeout (>120s for 100+ real chunks on CPU).

2. **aio-01 is a single point of failure**: All persistence routes through one machine. If it goes down, workers continue processing but cannot persist results.

3. **No offline capability**: API-only architecture means no functionality without internet. Acceptable for the use case but worth noting.

4. **GA meta-optimizer not yet validated**: Pipeline chromosome and benchmark suite are implemented but no evolution run has completed. Technique interaction effects are theoretical until measured.

5. **Knowledge base partially unsearchable during rechunking**: Old embeddings are deleted before new ones are generated. During the rechunk cycle, search quality is degraded.

6. **SSH tunnel fragility**: Remote cabin laptops reach aio-01 via SSH tunnels through pi-01. Tunnel drops require manual reconnection (no autossh configured).

7. **Pi-02 excluded from compute**: 1GB RAM prevents running Claude Code sessions or embedding services. Limited to monitoring.

---

## Cross-References

- **[COLLABORATION_MODEL.md](COLLABORATION_MODEL.md)** — Multi-AI collaboration roles, consensus strategies
- **[QUEUE_SYSTEM_ARCHITECTURE.md](QUEUE_SYSTEM_ARCHITECTURE.md)** — Redis queue system, 4-stage async pipeline
- **[SCRAPER_ARCHITECTURE.md](SCRAPER_ARCHITECTURE.md)** — Web scraper design, centralized API storage
- **[FLEET_ARCHITECTURE_DIAGRAM.md](FLEET_ARCHITECTURE_DIAGRAM.md)** — ASCII diagrams of fleet topology and data flow
- **[OPERATIONS.md](OPERATIONS.md)** — Deployment, monitoring, troubleshooting
- **[API_REFERENCE.md](API_REFERENCE.md)** — Complete REST API documentation
- **[FEEDBACK_LOOP_OPTIMIZER.md](FEEDBACK_LOOP_OPTIMIZER.md)** — Feedback loop detection and prevention
- **[GA-QUICKSTART.md](GA-QUICKSTART.md)** — Genetic algorithm quick start guide
- **[docs/adr/](adr/)** — Formal Architecture Decision Records
