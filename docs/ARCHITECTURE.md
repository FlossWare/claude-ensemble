# Architecture Guide

**Version**: 12 | **Last Updated**: 2026-06-13 | **Status**: Production Ready

Comprehensive system design documentation for Claude Global Skills -- a suite of AI-powered workflows, multi-AI consensus decision-making, and fleet-distributed automation for Claude Code.

---

## Table of Contents

- [System Overview](#system-overview)
- [High-Level Architecture](#high-level-architecture)
- [Component Map](#component-map)
- [Multi-AI Consensus System](#multi-ai-consensus-system)
  - [Arbiter-Worker Pattern](#arbiter-worker-pattern)
  - [Cross-Provider Diversity](#cross-provider-diversity)
  - [Consensus Strategies](#consensus-strategies)
  - [Arbiter Rotation and Fallback](#arbiter-rotation-and-fallback)
  - [Attribution Tracking](#attribution-tracking)
- [Fleet Infrastructure](#fleet-infrastructure)
  - [Fleet Topology](#fleet-topology)
  - [Fleet Mode Resolution](#fleet-mode-resolution)
  - [Multi-Session Orchestration vs Agent Parallelism](#multi-session-orchestration-vs-agent-parallelism)
  - [Compliance Enforcement](#compliance-enforcement)
- [Workflow Engine](#workflow-engine)
  - [Skill vs Workflow Distinction](#skill-vs-workflow-distinction)
  - [Workflow Lifecycle](#workflow-lifecycle)
  - [Interactive vs Autonomous Modes](#interactive-vs-autonomous-modes)
  - [SDLC Pipeline Architecture](#sdlc-pipeline-architecture)
- [Knowledge and Memory System](#knowledge-and-memory-system)
  - [Memory Architecture](#memory-architecture)
  - [RAG Pipeline](#rag-pipeline)
  - [Learning Extraction](#learning-extraction)
- [Shared Libraries](#shared-libraries)
  - [JavaScript Libraries](#javascript-libraries)
  - [Python Libraries](#python-libraries)
  - [Shell Libraries](#shell-libraries)
- [Monitoring Infrastructure](#monitoring-infrastructure)
- [Data Flow Diagrams](#data-flow-diagrams)
- [Architecture Decisions](#architecture-decisions)
- [Security Model](#security-model)
- [Known Limitations](#known-limitations)
- [Cross-References](#cross-references)

---

## System Overview

Claude Global Skills serves three primary purposes:

1. **Full SDLC Automation** -- Code review, issue solving, testing, PR review, security auditing, documentation generation, and release note publishing, all orchestrated with multi-AI consensus and zero human interaction when desired.

2. **Multi-AI Consensus** -- Every meaningful decision is verified by multiple AI models from multiple providers (Anthropic, OpenAI, Google) to reduce false positives, catch blind spots, and produce higher-confidence results.

3. **Distributed Processing** -- A personal fleet of heterogeneous machines parallelizes bulk processing tasks (hundreds of PDFs, thousands of URLs, large codebases) with true multi-session SSH orchestration.

Additionally, the project functions as a **concept proving ground** for FlossWare AI production libraries. Patterns validated here (attribution tracking, arbiter rotation, RAG with citations, semantic search) are migrated to FlossWare AI (consensus-ai, knowledge-ai, semantic-search-ai, vectordb-ai, skills-ai).

---

## High-Level Architecture

```
claude-global-skills/
|-- skills/              # User-facing skill definitions (.md + .sh + .json)
|-- workflows/           # Workflow implementations (.js) using Claude Code API
|-- shared/              # Reusable JavaScript, Python, and shell libraries
|-- scripts/
|   |-- fleet/           # Bash orchestration for fleet distribution
|   |-- commit-learning.sh
|   |-- hybrid-search-code.py
|   `-- populate-code-samples.py
|-- schemas/             # JSON Schema definitions for structured output
|-- templates/           # Configuration templates
|-- memory/              # Global cross-session memory (git tracked)
|-- learnings/           # Extracted learnings and case studies
|-- knowledge/           # Ingested knowledge bases (ANTLR, Solr, etc.)
|-- monitoring/          # Prometheus + Grafana fleet monitoring
|-- plugins/             # Plugin extensions (code-workflows)
|-- docs/                # Extended documentation
|-- multi-ai-config.json # Multi-AI consensus configuration
|-- package.json         # Node.js dependencies (chromadb, transformers)
`-- requirements.txt     # Python dependencies
```

### Component Interaction Flow

```
User invokes a skill (e.g., /code-review)
    |
    v
Skill definition (.md) loaded by Claude Code
    |
    v
Workflow engine (.js) executes phases
    |
    +---> Multi-AI workers (fable, opus, sonnet, haiku, gpt-4o, gemini)
    |         |
    |         v
    |     Arbiter synthesizes best result
    |
    +---> Fleet detection (resolveFleetMode)
    |         |
    |         +--> Below threshold? --> Local processing
    |         +--> Above threshold? --> Fleet distribution via SSH
    |                   |
    |                   v
    |               Worker machines process batches independently
    |                   |
    |                   v
    |               Results merged on controller
    |
    +---> Memory persistence (ChromaDB, learnings files)
    |
    v
Output (issues created, PRs reviewed, reports generated)
```

---

## Component Map

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Skills | `skills/` | User-facing entry points (trigger definitions) |
| Workflows | `workflows/`, root `.js` files | Multi-phase orchestration logic |
| Shared Libraries | `shared/` | Reusable functions for fleet, consensus, attribution |
| Schemas | `schemas/` | JSON Schema for structured AI output |
| Fleet Scripts | `scripts/fleet/` | Bash orchestration for distributed execution |
| Monitoring | `monitoring/` | Prometheus + Grafana deployment |
| Configuration | `multi-ai-config.json`, `~/.claude/fleet.json` | Runtime configuration |

### Statistics

| Metric | Count |
|--------|-------|
| Total Workflows | 31 (18 SDLC + 2 Memory RAG + 4 Web Learning + 2 Research + 5 Utilities) |
| Total Skills | 40+ |
| Lines of Workflow Code | 14,000+ |
| Shared JS Libraries | 25+ |
| Shared Python Libraries | 3 |
| Fleet Scripts | 11 |
| Multi-AI Models | Up to 9 across 3+ providers |
| Consensus Strategies | 9 |
| Alert Rules | 21 across 7 groups |
| Platform Support | GitHub + GitLab (auto-detected) |

---

## Multi-AI Consensus System

### Arbiter-Worker Pattern

The arbiter-worker pattern is the foundational architecture for all decision-making in the system. Every phase that involves analysis, rating, discovery, or validation uses this pattern.

**How it works:**

1. **Workers** (6-9 models by default): Each model independently analyzes the same input. Different models catch different issues due to different training data, architectures, and provider perspectives.

2. **Arbiter** (1 model, rotated): Reviews all worker outputs, selects the best one or synthesizes a combined answer, explains its reasoning, and assigns a confidence score.

3. **Graceful Degradation**: Models that fail (network error, rate limit, misconfiguration) return `null` and are filtered out with `.filter(Boolean)`. The workflow continues with available models.

```javascript
// Standard pattern in workflow code
const workers = await parallel([
  () => agent(prompt, { model: 'fable', label: 'fable-worker', schema }),
  () => agent(prompt, { model: 'opus', label: 'opus-worker', schema }),
  () => agent(prompt, { model: 'sonnet', label: 'sonnet-worker', schema }),
  () => agent(prompt, { model: 'haiku', label: 'haiku-worker', schema }),
  () => agent(prompt, { model: 'gpt-4o', label: 'gpt4o-worker', schema }),
  () => agent(prompt, { model: 'gemini', label: 'gemini-worker', schema }),
])

const validWorkers = workers.filter(Boolean) // Graceful degradation

const synthesis = await agent(arbiterPrompt, {
  model: 'fable',  // Or next in rotation
  label: 'arbiter',
  schema: arbiterSchema
})
```

### Cross-Provider Diversity

Using models from multiple providers is a deliberate architectural choice:

| Provider | Models | Strengths |
|----------|--------|-----------|
| **Anthropic** | Fable, Opus, Sonnet, Haiku | Reasoning, safety, code analysis |
| **OpenAI** | GPT-4o | Code generation, broad knowledge |
| **Google** | Gemini | Long context, multimodal |
| **Free APIs** | Cerebras-120b, Qwen-coder-32b, Llama-70b-fast | Zero cost, high volume |

**Error correlation reduction**: Same-provider models have ~60-70% error correlation (they share training biases). Cross-provider correlation drops to ~35-50%, achieving approximately 94% blind spot coverage with 6+ models.

### Consensus Strategies

The system implements 9 consensus strategies, defined in `consensus-strategies.js` and `multi-ai-config.json`:

| Strategy | Mechanism | When to Use |
|----------|-----------|-------------|
| **Rotating Arbiter** (Democratic) | Each worker judges all others; votes tallied | Critical decisions, maximum quality. Default. |
| **Single Arbiter** (Fast) | One designated model judges all workers | Speed-sensitive tasks |
| **Majority Vote** | Simple vote counting, no arbiter overhead | Solutions expected to converge |
| **Pairwise Comparison** (Tournament) | Workers compete in elimination pairs | Diverse/creative solutions requiring ranking |
| **Weighted Voting** | Workers provide confidence scores, combined via weighted average | When calibration data is available |
| **Auto-Select** | Chooses strategy based on runtime context | When optimal strategy depends on context |
| **Quantized** | Ollama local workers + cloud arbiter | Zero-cost workers, cloud synthesis |
| **Quintuple Verification** | 5 progressive stages with fail-fast filtering | Security audits, production releases |
| **Hierarchical** | Sub-teams with sub-arbiters feed a meta-arbiter | Cross-domain tasks (security + architecture + testing) |

**Configuration presets** in `multi-ai-config.json`:

| Preset | Models | Cost Multiplier | Use Case |
|--------|--------|-----------------|----------|
| maximum-coverage (Default) | 9 models | 10x | All decisions. Quality over cost. |
| fleet-balanced | 6 models | 7x | Balanced fleet usage |
| code-specialist | 4 code-focused models | 5x | Code-heavy tasks |
| fast-consensus | 3 fast models | 4x | Speed-sensitive tasks |
| heavy-analysis | 5 heavy models | 6x | Deep analysis |
| quad-consensus | 4 models | 5x | Good coverage, moderate cost |
| triple-consensus | 3 models | 4x | Minimum meaningful consensus |
| dual-consensus | 2 models | 3x | Lightweight consensus |
| workers-only | 6 models, no arbiter | 6x | Return all perspectives |

### Arbiter Rotation and Fallback

To prevent arbiter bias, the system rotates which model serves as arbiter across workflow phases:

- **Rotation order**: Fable -> Opus -> Sonnet -> Haiku -> GPT-4o -> Gemini
- **State tracking**: `arbiter-state.json` (gitignored, per-machine)
- **Fallback chain**: If the designated arbiter fails, the system tries each fallback model in order

```javascript
// Arbiter fallback pattern
const arbiterFallback = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

for (const model of arbiterFallback) {
  try {
    const decision = await agent(prompt, { model, schema })
    return { decision, usedModel: model }
  } catch (e) {
    log(`${model} arbiter failed: ${e.message}, trying next fallback`)
  }
}
```

### Attribution Tracking

The `AttributionTracker` class (`shared/attribution.js`) records which model contributed which findings, enabling:

- **Consensus identification**: Findings agreed on by 2+ models have higher confidence
- **Unique finding detection**: Findings from only 1 model need additional verification
- **Performance learning**: Track which models excel at which task types over time
- **Transparency**: Full markdown reports showing per-model contributions

```javascript
const tracker = new AttributionTracker()
tracker.recordWorker('opus', 'SQL injection in login.js line 42', { severity: 'critical' })
tracker.recordWorker('sonnet', 'SQL injection in login.js line 42', { severity: 'critical' })
tracker.recordWorker('gpt4', 'XSS in dashboard.js', { severity: 'high' })

const consensus = tracker.findConsensus(2) // Findings agreed by 2+ models
const unique = tracker.findUnique()         // Findings from only 1 model
const report = tracker.toMarkdown()         // Full attribution report
```

**Related issue**: FlossWare/consensus-ai#11 (porting to production)

---

## Fleet Infrastructure

### Fleet Topology

The fleet is a set of heterogeneous personal machines connected over a local network with NFS-shared home directories. The term "fleet" is used deliberately instead of "cluster" because these are diverse machines, not a uniform compute cluster.

| Machine | Role | CPUs | Memory | Architecture | Purpose |
|---------|------|------|--------|--------------|---------|
| **aio-01** | Controller | 4 | 7 GB | x86_64 | NFS server, Prometheus, Grafana, orchestration |
| **server-01** | Worker | 16 | 32 GB | x86_64 | Primary compute worker, fast models |
| **server-02** | Worker | 32 | 64 GB | x86_64 | High-memory worker (gets largest batches) |
| **server-03** | Worker | 16 | 32 GB | x86_64 | General compute, heavy models |
| **pi-02** | Sentinel/Coordinator | 4 | 1 GB | ARM (Cortex-A53) | Monitoring, job dispatch, health checks |
| **laptop-01** | Heavy Worker | 4 | 31 GB | x86_64 | Fable/Opus execution, ChromaDB host |

**Machine roles**:
- **Controller (aio-01)**: Hosts NFS shares, runs Prometheus/Grafana/Alertmanager. Does not participate as compute worker (7 GB RAM shared with monitoring).
- **Workers (server-01, server-02, server-03, laptop-01)**: Execute bulk processing via independent Claude Code sessions over SSH. Each worker processes its assigned batch independently.
- **Sentinel/Coordinator (pi-02)**: Runs node_exporter and job dispatcher. 1 GB RAM makes it unsuitable for AI execution.

**NFS-shared directories**: All machines share `/home/sfloess/Development` via NFS from aio-01. Source code is visible to all machines without copying. Workers use local `/tmp` for scratch work to avoid NFS write contention.

### Fleet Mode Resolution

The `resolveFleetMode()` function in `shared/fleet-utils.js` implements a three-step decision tree:

```
Start
  |
  v
Parse args for --local/--fleet flags
  |
  v
If --local flag --> Use LOCAL mode (explicit override)
  |
  v
If --fleet flag --> Check fleet availability
              --> If available: Use FLEET mode
              --> If unavailable: Throw error with troubleshooting steps
  |
  v
Auto-detect: Load ~/.claude/fleet.json
  |
  v
Filter machines by role/capabilities/memory
  |
  v
Run SSH health probes (cached for 30 seconds)
  |
  v
Fleet workers found? AND Item count >= break-even threshold?
  | YES --> Use FLEET mode, distribute work
  | NO  --> Use LOCAL mode, run sequentially
```

**Break-even thresholds** (below these, local processing is faster due to SSH overhead):

| Skill | Threshold | Item Type |
|-------|-----------|-----------|
| ai-pdf-deep-research | 10 | PDF files |
| ai-web-learn | 20 | URLs |
| ai-web-learn-production | 20 | URLs |
| code-security | 50 | Source files |
| code-review | 30 | Source files |
| code-doc | 50 | Source files |
| ai-web-code-learn-production | 5 | Git repos |

**Performance expectations**:

| Skill (batch size) | Local | Fleet (3 workers) | Speedup |
|-----|-------|-------------------|---------|
| ai-pdf-deep-research (100 PDFs) | ~8 hours | ~2.5 hours | 3.2x |
| ai-web-learn (100 URLs) | ~45 min | ~18 min | 2.5x |
| code-security (500 files) | ~2 hours | ~40 min | 3x |
| code-review (200 files) | ~1.5 hours | ~35 min | 2.6x |
| code-doc (300 files) | ~2.5 hours | ~50 min | 3x |

### Multi-Session Orchestration vs Agent Parallelism

The system uses two distinct parallelism approaches. Understanding the difference is essential for correct usage.

**Agent Parallelism** (within a single Claude session):

```javascript
// Uses Claude Code's parallel() API
// All "workers" run in the SAME session, sharing one API rate limit
const results = await parallel([
  () => agent(prompt, { model: 'opus', label: 'server-01' }),
  () => agent(prompt, { model: 'sonnet', label: 'server-02' }),
])
```

This is used by consensus skills (ai-prompt, ai-consensus variants). It provides model diversity but not compute distribution.

**Multi-Session Orchestration** (across fleet machines):

```javascript
// Launches INDEPENDENT Claude Code sessions via SSH
// Each worker is a separate process on a separate machine
// True parallelism with separate API rate limits
for (const worker of workers) {
  remoteExec(worker.hostname,
    `cd '${projectDir}' && claude -p --dangerously-skip-permissions '${prompt}'`
  )
}
```

This is used by fleet-aware skills for bulk processing. Each worker processes its batch independently. No inter-worker coordination is needed.

**Why multi-session is faster**: Most skills are API-bound (waiting for Claude API responses). Fleet distribution helps because each worker machine gets its own API rate limit, allowing more concurrent API calls.

### Compliance Enforcement

The compliance system prevents fleet distribution of proprietary work:

- **Path-based rules**: Any directory under `compliance.forbidden_paths` in `fleet.json` automatically disables fleet mode
- **Symlink bypass prevention**: Uses `fs.realpathSync()` to resolve real paths before comparison
- **Belt-and-suspenders**: `fleet-integration.js` also hardcodes `/home/sfloess/Development/redhat/` as a forbidden path
- **Silent fallback**: When compliance blocks fleet mode, the skill runs locally with no error

**Rationale**: Red Hat proprietary source code must not be transmitted to or processed on machines outside the controlled development environment.

---

## Workflow Engine

### Skill vs Workflow Distinction

- A **skill** is the user-facing entry point: a `.md` file (trigger description) plus optionally a `.sh` or `.json` file (execution script). Skills are invoked with `/skill-name` in Claude Code or `claude run skill-name` from the command line.

- A **workflow** is the implementation: a `.js` file that uses Claude Code's workflow API (`phase()`, `parallel()`, `agent()`, `log()`) to orchestrate multi-step operations. Workflows are registered via `export const meta = { ... }` at the top of the file.

Some skills are implemented entirely in their `.md` + `.sh` files without a workflow. Others delegate to a workflow `.js` file for complex multi-phase operations.

### Workflow Lifecycle

Every workflow follows a standard lifecycle:

```
1. Registration (export const meta block)
2. Args Parsing (handle string and object args)
3. Configuration Loading (multi-ai-config.json, fleet.json)
4. Fleet Mode Resolution (resolveFleetMode)
5. Phase Execution
   a. Workers analyze independently (parallel)
   b. Arbiter synthesizes (agent)
   c. Result processing
6. Output Generation (issues, PRs, reports)
7. Memory Persistence (learnings, findings)
```

**Registration requirement**: The `export const meta` block must be the first meaningful statement in the file (line 1-4). Claude Code uses this to discover and register workflows.

**Args parsing pattern** (handles both string and object args):

```javascript
let parsedArgs = args
if (typeof args === 'string') {
  const trimmed = args.trim()
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try { parsedArgs = JSON.parse(trimmed) }
    catch (e) { parsedArgs = { query: trimmed } }
  } else {
    parsedArgs = { query: trimmed }
  }
}
```

### Interactive vs Autonomous Modes

Most SDLC skills have two variants:

| Variant | Behavior | Use Case |
|---------|----------|----------|
| **Interactive** (e.g., `code-review`) | Shows findings, asks "Create issues for ALL/HIGH_ONLY/CRITICAL_ONLY/NONE?", waits for user decision | Developer desktop use |
| **Autonomous** (e.g., `code-review-auto`) | Auto-creates issues for findings with consensus >= threshold, skips low-confidence findings | CI/CD pipelines, nightly runs |

**Auto-decision thresholds for autonomous skills**:

| Skill | Criteria |
|-------|---------|
| code-solve-auto | Confidence >= 85%, no breaking changes, risk <= medium, code compiles |
| code-test-auto | Consensus >= 70%, reproducible, real bug (not test config) |
| code-pr-review-auto | Approve if quality >= 90, consensus >= 85%, no breaking changes, <= 50 files |
| code-security-auto | All CRITICAL vulnerabilities, HIGH with exploitable=true, consensus >= 75% |
| code-doc-auto | All exported/public APIs, high complexity, confidence >= 80% |

### SDLC Pipeline Architecture

The full SDLC pipeline (`code-sdlc`) orchestrates all phases in sequence:

```
code-sdlc
  |
  +--> code-review      (find issues)
  |       |
  |       v
  +--> code-solve       (fix issues)
  |       |
  |       v
  +--> code-test        (verify fixes)
  |       |
  |       v
  +--> code-pr-review   (review PRs)
  |       |
  |       v
  +--> code-security    (security audit)
  |       |
  |       v
  +--> code-doc         (generate docs)
  |       |
  |       v
  +--> code-release-notes (publish release)
```

**Continuous mode** (`code-sdlc-auto-continuous`): Runs the entire pipeline in a loop until the codebase is clean or max iterations (default: 5) are reached. Delegates to `sdlc-loop.sh` which launches each phase as an independent Claude Code session (workaround for workflow nesting limitation).

---

## Knowledge and Memory System

### Memory Architecture

```
memory/                              # Git-tracked, cross-session
|-- MEMORY.md                        # Index of all memory files
|-- feedback_*.md                    # User corrections and confirmations
|-- project_*.md                     # Project context and history
|-- reference_*.md                   # External system pointers
`-- (learnings from sessions)

learnings/                           # 148+ categorized learning files
|-- arbiter-worker-pattern.md
|-- coordinator-pattern.md
|-- autonomous-workflow-suite.md
|-- parallel-by-default.md
|-- claude-code-workflows.md
`-- ...

knowledge/                           # Ingested knowledge bases
|-- antlr/
|-- solr/
`-- ...
```

**Memory types**:
- **Feedback**: User corrections and confirmations (highest priority)
- **Project**: Ongoing work context, constraints, versioning policies
- **Reference**: Pointers to external systems, fleet configuration
- **Technical**: Code patterns, architectural decisions
- **Learnings**: Extracted best practices and case studies

### RAG Pipeline

The RAG (Retrieval-Augmented Generation) pipeline provides semantic search across memories:

```
Query
  |
  v
Semantic Search (ChromaDB, 384-dim embeddings via Xenova/all-MiniLM)
  |
  v
Keyword Search (text matching)
  |
  v
Hybrid Ranking (RRF algorithm combining both scores)
  |
  v
Reranking (bi-encoder to cross-encoder)
  |
  v
Context Assembly
  |
  v
Multi-AI Answer Synthesis (arbiter-worker pattern)
  |
  v
Cited Response
```

**Components**:
- `shared/rag.py` -- RAG with citations, hybrid search
- `shared/semantic-search.py` -- Hybrid search with RRF, reranking
- `shared/vector-store.py` -- ChromaDB vector storage
- `memory-rag-index.js` -- Index memories into ChromaDB
- `memory-rag-search.js` -- Search with multi-AI consensus relevance

**Dependencies**: ChromaDB (v1.10.5), @xenova/transformers (v2.17.2)

### Learning Extraction

The `ai-extract-learning` workflow automatically extracts learnings from:

- Session transcripts (user corrections, confirmations, preferences)
- Workflow executions (what worked, what failed)
- Multi-AI consensus decisions (which models excelled where)

Extracted learnings are stored in `memory/` and `learnings/` as markdown files with YAML frontmatter, compatible with the RAG indexing pipeline.

---

## Shared Libraries

### JavaScript Libraries

| Library | Location | Purpose | Key Exports |
|---------|----------|---------|-------------|
| fleet-utils.js | `shared/` | Fleet discovery, health checking, compliance, remote execution | `loadFleetConfig()`, `validateCompliance()`, `probeHealth()`, `getFleet()`, `getWorkers()`, `remoteExec()`, `resolveFleetMode()` |
| fleet-multisession.js | `shared/` | True multi-session orchestration via SSH | `splitBatches()`, `splitBatchesWeighted()`, `runMultiSession()`, `mergeMarkdownReports()`, `mergeJsonArrays()` |
| fleet-bulk-orchestration.js | `shared/` | Generic bulk orchestration framework | `bulkOrchestrate()`, `mergeMarkdownResults()`, `mergeArrayResults()` |
| fleet-workflow-patterns.js | `shared/` | High-level reusable fleet patterns | `distributeAndMerge()`, `parallelPhases()`, `gracefulFallback()` |
| fleet-integration.js | `shared/` | Workflow-friendly fleet integration | `parseFleetArgs()`, `shouldUseFleet()`, `getFleetWorkers()` |
| consensus-engine.js | `shared/` | Core consensus engine for multi-AI patterns | Various consensus functions |
| consensus-strategies.js | root | 5 consensus strategies (rotating, single, majority, pairwise, weighted) | `rotatingArbiter()`, `singleArbiter()`, `majorityVote()`, `pairwiseComparison()`, `weightedVoting()` |
| attribution.js | `shared/` | Track per-model contributions in consensus | `AttributionTracker` class |
| smart-consensus.js | `shared/` | Performance-aware consensus routing | Model selection functions |
| impact-analysis.js | `shared/` | Breaking change detection, severity scoring | Impact analysis functions |
| issue-operations.js | `shared/` | Create/update GitHub/GitLab issues | Issue CRUD functions |
| quality-scorer.js | `shared/` | Multi-dimensional code quality scoring | Scoring functions |
| work-coordinator.js | `shared/` | Multi-agent work distribution | Coordination functions |
| workflow-helpers.js | `shared/` | Common workflow utilities | Arbiter patterns, schema definitions |
| model-detection.js | `shared/` | Detect available AI models | Detection functions |
| model-performance.js | `shared/` | Track model performance metrics | Performance tracking |
| platform-detector.js | `shared/` | Detect GitHub vs GitLab from git remote | Platform detection |
| chunking-utils.js | `shared/` | Smart document chunking for RAG | Chunking functions |
| clustering-utils.js | `shared/` | Cluster similar findings for deduplication | Clustering functions |
| loop-controller.js | `shared/` | Control loop execution for continuous SDLC | Loop control |
| schemas.js | `shared/` | Shared JSON Schema definitions | Schema objects |
| learning.js / learning-system.js | `shared/` | Cross-session learning extraction | Learning functions |

### Python Libraries

| Library | Location | Purpose |
|---------|----------|---------|
| rag.py | `shared/` | RAG with citations: query, retrieve, generate with sources. Hybrid search. |
| semantic-search.py | `shared/` | Hybrid search with RRF algorithm, bi-encoder to cross-encoder reranking. |
| vector-store.py | `shared/` | ChromaDB vector storage: local embeddings, metadata filtering. |

### Shell Libraries

| Library | Location | Purpose |
|---------|----------|---------|
| skill-helpers.sh | `shared/` | Common shell utilities for skill scripts |
| visual-indicators.sh | `shared/` | Colored consensus output, progress indicators, model-specific colors |
| fleet-bulk-lib.sh | `scripts/fleet/` | Common fleet library: discovery, distribution, dispatch, monitoring, merging (1022 lines) |

---

## Monitoring Infrastructure

The `monitoring/` directory contains a production-ready Prometheus stack for fleet observability.

### Components

| Component | Version | Location | Memory Cap |
|-----------|---------|----------|------------|
| Prometheus | 3.12.0 | aio-01 | 3 GB |
| node_exporter | 1.11.1 | All 5 machines | ~15-20 MB RSS |
| Alertmanager | 0.32.1 | aio-01 | 256 MB |
| Grafana | Latest | aio-01 | 512 MB |

### Alert Rules (21 rules in 7 groups)

| Group | Rules | Key Alerts |
|-------|-------|------------|
| host_availability | 2 | HostDown (2m, critical), HostRebootDetected |
| cpu_alerts | 3 | HighCpuUsage (>85%), CriticalCpuUsage (>95%), ControllerCpuTooHigh (>60% on aio-01) |
| memory_alerts | 3 | HighMemoryUsage (>85%), CriticalMemoryUsage (>95%), SentinelMemoryHigh (>70% on pi-02) |
| disk_alerts | 4 | DiskSpaceLow (>80%), DiskSpaceCritical (>90%), DiskWillFillIn24h (predictive), DiskInodesLow |
| network_alerts | 2 | NetworkInterfaceDown, HighNetworkErrors |
| system_health | 4 | SystemdServiceFailed, HighLoadAverage, ClockSkew, HighSwapUsage |
| prometheus_self | 3 | PrometheusTargetDown, PrometheusTsdbStorageHigh, PrometheusConfigReloadFailed |

### Memory Budget (aio-01: 7 GB total)

| Component | MemoryMax | Typical Usage |
|-----------|-----------|---------------|
| Prometheus | 3 GB | ~1.5 GB |
| Grafana | 512 MB | ~300 MB |
| Alertmanager | 256 MB | ~50 MB |
| **Total capped** | **3.75 GB** | **~1.85 GB** |
| OS + NFS + other | - | ~3.25 GB available |

### Architecture Decisions for Monitoring

- **Native binaries over Docker**: pi-02 has only 1 GB RAM; Docker daemon overhead (100-200 MB idle) is unacceptable
- **Static discovery over dynamic**: 5-machine fleet does not justify Consul/mDNS. Threshold to reconsider: ~15+ machines
- **ntfy for alert delivery**: Free, self-hosted, mobile-capable. Two channels: warnings vs critical
- **15-day retention with 3 GB cap**: Conservatively sized for 7 GB controller running NFS and monitoring

---

## Data Flow Diagrams

### Code Review Data Flow

```
git log / git diff
    |
    v
File Discovery (identify changed/target files)
    |
    v
Multi-AI Analysis Phase (per file)
    |
    +-- Worker 1 (Fable): security, logic, performance
    +-- Worker 2 (Opus): architecture, patterns, maintainability
    +-- Worker 3 (Sonnet): bugs, edge cases, error handling
    +-- Worker 4 (Haiku): code style, naming, documentation
    +-- Worker 5 (GPT-4o): code quality, best practices
    +-- Worker 6 (Gemini): dependencies, integration issues
    |
    v
Arbiter Synthesis (select best findings, assign confidence)
    |
    v
Deduplication & Clustering (shared/clustering-utils.js)
    |
    v
Issue Creation (gh issue create / glab issue create)
    |
    v
Attribution Report (shared/attribution.js)
```

### Fleet Distribution Data Flow

```
Skill invoked with N items
    |
    v
resolveFleetMode(args, N, threshold)
    |
    +-- mode: 'local' --> Process sequentially on current machine
    |
    +-- mode: 'fleet'
         |
         v
    Load fleet.json, filter workers, health probe
         |
         v
    Split items across workers (round-robin or weighted by memory)
         |
         v
    SSH dispatch to each worker (independent Claude Code sessions)
         |
         v
    Progress monitoring (NFS-visible files or SSH polling)
         |
         v
    Result collection (JSON, markdown, or files via SSH cat)
         |
         v
    Merge and deduplicate results (skill-specific merge strategy)
         |
         v
    Final output
```

### PDF Deep Research Data Flow

```
Input: PDF files
    |
    v
Smart chunking (20-page segments)
    |
    v
6-model claim extraction (workers extract independently)
    |
    v
Arbiter synthesis (importance ranking: central > supporting > tangential)
    |
    v
3-vote refutation protocol (2/3 refutations kill a claim)
    |
    v
Challenger exclusion (models that proposed a claim cannot vote on it)
    |
    v
Final synthesis (verified claims, refuted claims, confidence scores)
    |
    v
Memory persistence (YAML frontmatter, compatible with RAG index)
```

---

## Architecture Decisions

### ADR-1: "Fleet" Terminology Instead of "Cluster"

**Context**: The machines are heterogeneous personal computers (7 GB to 64 GB RAM, x86_64 and ARM, different roles).

**Decision**: Use "fleet" to convey a collection of diverse vessels, not a uniform compute cluster.

**Rationale**: The term "cluster" implies homogeneity and tight coordination, neither of which applies.

### ADR-2: Unified Skills (Option A+C) Instead of -bulk/-fleet Variants

**Context**: Previously, adding fleet support required creating 2-3 new files per skill (skill-bulk, skill-fleet). This caused naming confusion, duplicated logic, and maintenance burden.

**Decision**: Add fleet-awareness to parent skills with auto-detection. Deprecated -bulk/-fleet variants still exist but are hidden.

**Rationale**: Users never need to think about which variant to use. `--fleet` and `--local` flags provide explicit control when needed.

### ADR-3: Multi-Session Orchestration for Bulk Processing

**Context**: Claude Code's `parallel()` runs tasks concurrently but within a single session sharing one API rate limit.

**Decision**: Use SSH to launch independent Claude Code sessions on separate machines for bulk work.

**Rationale**: Each session has its own rate limit, memory, and CPU. For embarrassingly parallel workloads, this achieves 2.5-3x speedup.

### ADR-4: Static fleet.json Instead of Dynamic Discovery

**Context**: 5 machines is a small fleet.

**Decision**: Static JSON configuration file, version-controlled.

**Rationale**: Zero dependencies, simple to debug, portable. Threshold to reconsider: ~15+ machines.

### ADR-5: Path-Based Compliance Instead of Network-Based

**Context**: Red Hat proprietary code must not leave controlled infrastructure.

**Decision**: Block fleet mode based on filesystem paths (with realpath symlink prevention).

**Rationale**: The decision about fleet processing is fundamentally about what data is being processed, not where the processing request originates.

### ADR-6: Cross-Provider Model Diversity

**Context**: Same-provider models share training biases, leading to correlated errors.

**Decision**: Use models from Anthropic, OpenAI, and Google for all consensus decisions.

**Rationale**: Cross-provider diversity reduces error correlation from ~60-70% to ~35-50%, achieving ~94% blind spot coverage.

### ADR-7: Sandbox Constraints in Workflows

**Context**: Claude Code workflows run in a sandboxed environment without Node.js built-ins (fs, require, etc.).

**Decision**: Use `agent()` to spawn subagents for file system operations and `execSync` from child_process for shell commands.

**Rationale**: This is a platform constraint, not a design choice. The `agent()` call spawns a subagent that can use the Read tool to access files.

---

## Security Model

### Input Validation

- **Issue IDs**: Must be positive integers (1-999999999)
- **Labels**: Alphanumeric + dash/underscore only (prevents shell injection)
- **Hostnames**: Validated against `[a-zA-Z0-9._-]+` pattern, no path traversal
- **Shell commands**: Variables quoted, jq parsing instead of grep for JSON

### SSH Security

- Key-based authentication required (no password prompts)
- `BatchMode=yes` enforced
- `StrictHostKeyChecking=accept-new` for known hosts management
- Commands properly escaped via `remoteExec()`

### Compliance Boundaries

- Path-based forbidden zones prevent proprietary code from reaching fleet workers
- Symlink bypass prevention via `fs.realpathSync()`
- Hardcoded belt-and-suspenders check in `fleet-integration.js`

### Permissions

Two modes available:

1. **dontAsk mode** (recommended for autonomous workflows): Auto-approves all tool invocations
2. **Granular allowlist**: Fine-grained control over which commands are permitted

Setup via `fix-permissions.sh` or manual configuration in `~/.claude/settings.json`. See [OPERATIONS.md](OPERATIONS.md) for detailed setup.

---

## Known Limitations

1. **Workflow nesting**: Claude Code workflows cannot directly nest other workflows. Workaround: `sdlc-loop.sh` launches each phase as an independent Claude Code session.

2. **No filesystem access in workflows**: Workflow `.js` files cannot use `fs`, `require`, or other Node.js built-ins directly. Must use `agent()` to spawn subagents.

3. **Multi-AI config not yet dynamic**: Most workflows still use hardcoded model lists rather than reading from `multi-ai-config.json`. The configuration system is ready but not yet wired into all workflows.

4. **npm vulnerabilities**: 4 security issues in the dependency tree (3 high, 1 critical) in development dependencies.

5. **Arbiter rotation state**: `arbiter-state.json` is gitignored and per-machine. Does not persist across machines or sessions.

6. **Pi-02 excluded from compute**: 1 GB RAM prevents running Claude Code sessions. Limited to monitoring and coordination.

---

## Cross-References

- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** -- How to integrate workflows, migration guide, examples
- **[OPERATIONS.md](OPERATIONS.md)** -- Deployment, monitoring, troubleshooting
- **[API_REFERENCE.md](API_REFERENCE.md)** -- Complete API documentation for shared libraries
- **[README.md](../README.md)** -- Project overview with usage examples
- **[FLEET_AWARE_SKILLS.md](FLEET_AWARE_SKILLS.md)** -- Detailed fleet-aware skill documentation
- **[ATTRIBUTION_TRACKING.md](ATTRIBUTION_TRACKING.md)** -- Attribution system deep-dive
