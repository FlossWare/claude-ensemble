# Claude Global Skills

**Version**: 12  
**Last Updated**: 2026-06-12  
**Repository**: https://gitlab.cee.redhat.com/sfloess/claude-global-skills  
**License**: GPL-3.0  
**Status**: Production Ready

A comprehensive suite of AI-powered skills, workflows, and fleet-distributed automation for Claude Code. Provides full SDLC coverage (code review, testing, security audit, documentation, release), multi-AI consensus decision-making across 6 models and 3 providers, web and PDF learning, semantic memory (RAG), and distributed bulk processing across a personal fleet of machines.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Fleet Infrastructure](#fleet-infrastructure)
- [Skills Reference](#skills-reference)
  - [AI and Learning Skills](#ai-and-learning-skills)
  - [Code SDLC Skills](#code-sdlc-skills)
  - [Research Skills](#research-skills)
  - [Consensus Skills](#consensus-skills)
  - [Utility Skills](#utility-skills)
- [Workflows](#workflows)
  - [Workflow vs Skill Distinction](#workflow-vs-skill-distinction)
  - [Development Phase Workflows](#development-phase-workflows)
  - [Testing Phase Workflows](#testing-phase-workflows)
  - [PR Review Phase Workflows](#pr-review-phase-workflows)
  - [Security Phase Workflows](#security-phase-workflows)
  - [Documentation Phase Workflows](#documentation-phase-workflows)
  - [Release Phase Workflows](#release-phase-workflows)
  - [Meta-Orchestration Workflows](#meta-orchestration-workflows)
  - [Memory RAG Workflows](#memory-rag-workflows)
  - [Web Learning Workflows](#web-learning-workflows)
  - [Research and Analysis Workflows](#research-and-analysis-workflows)
  - [Deprecated Workflows](#deprecated-workflows)
- [Fleet Processing](#fleet-processing)
  - [How Fleet Distribution Works](#how-fleet-distribution-works)
  - [Multi-Session Orchestration vs Agent Parallelism](#multi-session-orchestration-vs-agent-parallelism)
  - [Break-Even Thresholds](#break-even-thresholds)
  - [Performance Expectations](#performance-expectations)
  - [Fleet Bash Scripts](#fleet-bash-scripts)
- [Shared Libraries](#shared-libraries)
- [Multi-AI Consensus System](#multi-ai-consensus-system)
  - [Arbiter Worker Pattern](#arbiter-worker-pattern)
  - [Consensus Strategies](#consensus-strategies)
  - [Multi-AI Configuration](#multi-ai-configuration)
  - [Adding New Models](#adding-new-models)
- [Configuration](#configuration)
  - [Fleet Configuration](#fleet-configuration-1)
  - [Multi-AI Configuration File](#multi-ai-configuration-file)
  - [Compliance Rules](#compliance-rules)
  - [NFS Setup Requirements](#nfs-setup-requirements)
  - [Environment Variables](#environment-variables)
- [Usage Examples](#usage-examples)
- [Monitoring](#monitoring)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Architecture Decisions](#architecture-decisions)
- [Development Guide](#development-guide)
- [Known Limitations](#known-limitations)
- [Future Enhancements](#future-enhancements)
- [Version History](#version-history)

---

## Project Overview

### What This Project Is

Claude Global Skills is a testing ground and production-ready toolkit for AI-assisted software engineering. It started as a prototype environment for FlossWare AI concepts and has grown into a comprehensive system of 31+ workflows and dozens of supporting skills that automate the entire software development lifecycle.

### Purpose and Goals

1. **Full SDLC Automation** -- Automate code review, issue solving, testing, PR review, security auditing, documentation generation, and release note publishing with zero human interaction when desired.

2. **Multi-AI Consensus** -- Every meaningful decision is verified by multiple AI models from multiple providers (Anthropic, OpenAI, Google) to reduce false positives, catch blind spots, and produce higher-confidence results.

3. **Distributed Processing** -- Leverage a personal fleet of machines to parallelize bulk processing tasks (hundreds of PDFs, thousands of URLs, large codebases) with true multi-session SSH orchestration.

4. **Cross-Session Learning** -- Persist learnings, memory, and knowledge across Claude Code sessions using a memory system backed by ChromaDB vector storage and semantic search.

5. **Concept Proving** -- Prototype AI concepts here, validate them with multi-AI consensus, then port proven patterns to FlossWare AI production libraries (consensus-ai, knowledge-ai, semantic-search-ai, vectordb-ai, skills-ai).

### What Problems It Solves

- Manual code reviews miss bugs that multiple AI models catch through consensus
- Security audits are tedious and incomplete when done by a single reviewer
- Bulk processing (600 PDFs, 1000 URLs) takes hours on a single machine
- Knowledge learned in one Claude session is lost when the session ends
- False positives in AI-generated findings waste developer time
- Switching between interactive and autonomous modes requires different tooling

---

## Architecture

### High-Level Structure

```
claude-global-skills/
|-- skills/              # Executable skill definitions (.md + .sh + .json)
|-- workflows/           # Claude Code workflow implementations (.js)
|-- shared/              # Reusable JavaScript and Python libraries
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
`-- requirements.txt     # Python dependencies (chromadb, sentence-transformers)
```

### Component Interaction

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

## Fleet Infrastructure

### What is the Fleet

The fleet is a set of 5 personal machines connected over a local network with NFS-shared home directories. The term "fleet" was chosen deliberately over "cluster" because these are heterogeneous personal machines, not a uniform compute cluster.

| Machine | Role | CPUs | Memory | Architecture | Purpose |
|---------|------|------|--------|--------------|---------|
| **aio-01** | Controller | 4 | 7 GB | x86_64 | NFS server, Prometheus, Grafana, orchestration |
| **server-01** | Worker | 16 | 32 GB | x86_64 | Primary compute worker |
| **server-02** | Worker | 32 | 64 GB | x86_64 | High-memory worker (gets largest batches in weighted distribution) |
| **server-03** | Worker | 16 | 32 GB | x86_64 | General compute worker |
| **pi-02** | Sentinel | 4 | 1 GB | ARM (Cortex-A53) | Lightweight monitoring, health checks only |

### Machine Roles

- **Controller (aio-01)**: Hosts NFS shares, runs Prometheus/Grafana/Alertmanager, orchestrates fleet operations. Does not participate as a compute worker due to limited resources (7 GB RAM must be shared with NFS and monitoring).

- **Workers (server-01, server-02, server-03)**: Execute bulk processing tasks via independent Claude Code sessions launched over SSH. Each worker processes its assigned batch independently -- no inter-worker coordination is needed.

- **Sentinel (pi-02)**: Runs node_exporter for monitoring but does not participate in compute work. Its 1 GB RAM makes it unsuitable for Claude Code sessions, but ideal for lightweight monitoring.

### NFS-Shared Directories

All machines share `/home/sfloess/Development` via NFS from aio-01. This means:

- Source code is visible to all machines without copying
- Fleet scripts can reference absolute paths that work on any machine
- Results can be written to NFS for collection by the controller
- Workers use local `/tmp` for scratch work to avoid NFS write contention

### How Fleet Auto-Detection Works

The `resolveFleetMode()` function in `shared/fleet-utils.js` implements a three-step decision tree:

1. **Check explicit flags**: `--local` forces local mode. `--fleet` forces fleet mode (throws an error if fleet is unavailable).

2. **Auto-detect fleet**: Reads `~/.claude/fleet.json`, filters machines by role/capabilities/memory, runs SSH health probes (cached for 30 seconds), and returns available workers.

3. **Check break-even threshold**: If the number of items to process is below the skill-specific threshold, local mode is used even when fleet workers are available. This avoids paying SSH overhead for small jobs.

### When Fleet vs Local Mode Is Used

| Scenario | Mode | Reason |
|----------|------|--------|
| 5 PDFs, fleet available | Local | Below 10-PDF threshold |
| 100 PDFs, fleet available | Fleet | Above threshold, workers available |
| 100 PDFs, no fleet.json | Local | Fleet unavailable, graceful fallback |
| Any item count with `--local` | Local | Explicit flag overrides auto-detect |
| Any item count with `--fleet`, no workers | Error | Explicit flag requires fleet |
| Working in Red Hat repo path | Local | Compliance rule blocks fleet |

---

## Skills Reference

Skills are the user-facing entry points. They are invoked with `/skill-name` in Claude Code or `claude run skill-name` from the command line.

### AI and Learning Skills

| Skill | What It Does | Fleet-Aware | File(s) |
|-------|-------------|-------------|---------|
| **ai-web-learn** | Learn from web pages with multi-AI consensus. Fetches URLs, extracts facts, stores in memory. | Yes (20 URLs) | `ai-web-learn.js`, `ai-web-learn.md` |
| **ai-web-learn-mcp** | Production web learning using MCP (Model Context Protocol) tools for fetching. | No | `ai-web-learn-mcp.js`, `ai-web-learn-mcp.md` |
| **ai-web-learn-production** | Production RAG pipeline with ChromaDB embeddings for persistent knowledge storage. | Yes (20 URLs) | `ai-web-learn-production.js`, `ai-web-learn-production.md` |
| **ai-web-learn-universal-ai** | Integration with Universal AI RAG system for cross-platform knowledge sharing. | No | `ai-web-learn-universal-ai.js`, `ai-web-learn-universal-ai.md` |
| **ai-web-code-learn** | Learn from code repositories -- AST parsing, pattern extraction, semantic embeddings. | No | `ai-web-code-learn.js` |
| **ai-pdf-deep-research** | Adversarial PDF claim verification: extract claims from PDFs, challenge each with 3-vote refutation, synthesize findings. Uses 6-model consensus with challenger exclusion (models that proposed a claim cannot vote on it). | Yes (10 PDFs) | `ai-pdf-deep-research.js`, `skills/ai-pdf-deep-research.md` |
| **ai-extract-learning** | Extract learnings from workflow transcripts. Identifies user corrections, preferences, patterns, and best practices from session history. | No | `ai-extract-learning.js`, `ai-extract-learning.md` |
| **ai-chat** | Interactive multi-AI chat session. Maintains conversation context across multiple AI models simultaneously. | No | `ai-chat.js`, `ai-chat.md` |

**ai-web-learn usage:**
```bash
# Learn from web pages (below threshold, runs local)
/ai-web-learn https://docs.example.com/api

# Learn from many URLs (above threshold, auto-fleet if available)
/ai-web-learn urls.txt --fleet
```

**ai-pdf-deep-research usage:**
```bash
# Verify claims in a PDF
/ai-pdf-deep-research /path/to/paper.pdf --topic "machine learning"

# Process many PDFs with fleet
/ai-pdf-deep-research /path/to/pdfs/*.pdf --fleet
```

### Code SDLC Skills

These skills cover the full software development lifecycle. Each has an interactive variant (prompts before actions) and an autonomous variant (auto-creates issues/PRs).

| Skill | What It Does | Interactive | Autonomous | Fleet-Aware |
|-------|-------------|-------------|------------|-------------|
| **code-review** | Find bugs and code quality issues using multi-AI consensus | `code-review` | `code-review-auto` | Yes (30 files) |
| **code-solve** | Fix GitHub/GitLab issues. Analyzes issue, generates fix, creates PR with squash merge. | `code-solve` | `code-solve-auto` | No |
| **code-test** | Comprehensive testing: build verification, UI validation, integration tests, E2E flows, issue reproduction. | `code-test` | `code-test-auto` | No |
| **code-smoke-test** | Quick smoke test: build, launch, basic interaction. 2-3 minutes. | `code-smoke-test` | N/A | No |
| **code-pr-review** | Review pull requests for quality, breaking changes, and cross-codebase impact. | `code-pr-review` | `code-pr-review-auto` | No |
| **code-security** | Security audit: OWASP Top 10, dependency vulnerabilities, hardcoded secrets, license compliance. | `code-security` | `code-security-auto` | Yes (50 files) |
| **code-doc** | Generate missing documentation for exported/public APIs, complex functions, classes. | `code-doc` | `code-doc-auto` | Yes (50 files) |
| **code-release-notes** | Generate and publish release notes from commit history. | `code-release-notes` | `code-release-notes-auto` | No |
| **code-sdlc** | Run entire SDLC pipeline: review, solve, test, PR review, security, docs, release. | `code-sdlc` | `code-sdlc-auto` | No |
| **code-sdlc-auto-continuous** | Continuous loop: run all SDLC phases repeatedly until codebase is clean or max iterations reached. | N/A | `code-sdlc-auto-continuous` | No |

**Interactive vs Autonomous behavior:**

- **Interactive** (`code-review`): Shows findings, asks "Create issues for ALL/HIGH_ONLY/CRITICAL_ONLY/NONE?", waits for user decision.
- **Autonomous** (`code-review-auto`): Auto-creates issues for findings with consensus >= 70%, skips low-confidence findings.

**Auto-Decision Criteria for Autonomous Skills:**

| Skill | Criteria |
|-------|---------|
| code-solve-auto | Confidence >= 85%, no breaking changes, risk <= medium, code compiles |
| code-test-auto | Consensus >= 70%, reproducible, real bug (not test config) |
| code-pr-review-auto | Approve if quality >= 90, consensus >= 85%, no breaking changes, <= 50 files |
| code-security-auto | All CRITICAL vulnerabilities, HIGH with exploitable=true, consensus >= 75% |
| code-doc-auto | All exported/public APIs, high complexity, confidence >= 80% |

**Usage:**
```bash
# Interactive code review
claude run code-review

# Autonomous code review (CI/CD)
claude run code-review-auto

# Full SDLC pipeline
claude run code-sdlc +500k

# Continuous loop until clean
sdlc-loop.sh 5 500k
```

### Research Skills

| Skill | What It Does | Fleet-Aware | File(s) |
|-------|-------------|-------------|---------|
| **deep-research** | Deep research harness: fan-out web searches, fetch sources, adversarially verify claims, synthesize a cited report. | No | `workflows/deep-research-bulk.js` (fleet variant exists) |

### Consensus Skills

These skills implement various multi-AI consensus patterns.

| Skill | What It Does | File(s) |
|-------|-------------|---------|
| **ai-prompt** | Multi-model consensus response to any prompt. Runs the same question across 6 models, arbiter selects best answer. | `ai-prompt.js`, `ai-prompt.md` |
| **ai-consensus** | Reusable multi-AI consensus helper. Internal building block used by other skills. | `ai-consensus.js` |
| **ai-consensus-debate** | Adversarial debate: workers propose, exchange arguments, rebut, arbiter judges. Best for critical analysis. | `ai-consensus-debate.js`, `ai-consensus-debate.md` |
| **ai-consensus-filtered** | Filtered consensus: workers produce solutions, low-confidence ones filtered before arbiter synthesis. | `ai-consensus-filtered.js` |
| **ai-consensus-hierarchical** | Hierarchical consensus: multiple rounds of refinement with progressive quality gates. | `ai-consensus-hierarchical.js`, `ai-consensus-hierarchical.md` |
| **ai-consensus-refinement** | Iterative refinement: workers produce drafts, exchange feedback, refine, arbiter synthesizes. | `ai-consensus-refinement.js`, `ai-consensus-refinement.md` |
| **ai-consensus-weighted** | Weighted voting: workers provide confidence scores, results combined via weighted average. | `ai-consensus-weighted.js` |
| **ai-consensus-disagreement** | Disagreement analysis: identifies and maps areas where models disagree. | `ai-consensus-disagreement.js` |

### Utility Skills

| Skill | What It Does | File(s) |
|-------|-------------|---------|
| **workflow-cleanup** | Clean accumulated workflow transcripts. Extracts learnings first, then clears. | `workflow-cleanup.js`, `workflow-cleanup.md` |
| **workflow-status** | Show real-time status of running workflows, workers, and arbiters. | `workflow-status.js` |
| **add-workflow-logging** | Add log() calls to workflows for real-time status visibility. | `add-workflow-logging.js` |
| **ai-cost-tracker** | Track API costs per model, per workflow. Provides cost breakdowns and projections. | `ai-cost-tracker.js`, `ai-cost-tracker.md` |
| **ai-performance-monitor** | Monitor model performance: latency, accuracy, throughput per model. | `ai-performance-monitor.js`, `ai-performance-monitor.md` |
| **ai-confidence-calibration** | Calibrate model confidence scores using Platt scaling or isotonic regression against actual outcomes. | `ai-confidence-calibration.js` |
| **ai-task-router** | Route tasks to optimal models based on task type, complexity, and model performance history. | `ai-task-router.js`, `ai-task-router.md` |
| **ai-uncertainty-analysis** | Analyze uncertainty in model outputs. Identifies low-confidence areas and suggests verification. | `ai-uncertainty-analysis.js`, `ai-uncertainty-analysis.md` |
| **ai-cross-validation** | Cross-validate findings across models. Identifies agreement, disagreement, and unique findings. | `ai-cross-validation.js`, `ai-cross-validation.md` |
| **detect-local-models** | Detect locally running models (Ollama, LM Studio). Auto-configures for QuantizedStrategy. | `detect-local-models.js`, `detect-local-models.md` |
| **memory-rag-index** | Index all memories in ChromaDB with semantic embeddings for retrieval. | `memory-rag-index.js` |
| **memory-rag-search** | Semantic search across memories using multi-AI consensus relevance analysis. | `memory-rag-search.js` |
| **code-ast-analysis** | AST-level code analysis. Extracts function signatures, complexity metrics, dependency graphs. | `code-ast-analysis.js` |
| **code-semantic-search** | Semantic code search using embeddings. Finds code by meaning, not just text. | `code-semantic-search.js` |
| **get-next-arbiter** | Get next arbiter model in rotation (fable -> opus -> sonnet -> haiku -> gpt-4o -> gemini). Internal helper. | `get-next-arbiter.js` |
| **update-arbiter-state** | Update arbiter rotation state file. Internal helper. | `update-arbiter-state.js` |
| **doc-review** | Documentation review with issue creation for gaps and errors. | `doc-review.js` |
| **doc-review-auto** | Autonomous documentation review -- auto-creates issues. | `doc-review-auto.js` |

---

## Workflows

### Workflow vs Skill Distinction

- A **skill** is the user-facing entry point: a `.md` file (trigger description) plus optionally a `.sh` or `.json` file (execution script). Skills are what users invoke with `/skill-name`.

- A **workflow** is the implementation: a `.js` file that uses Claude Code's workflow API (`phase()`, `parallel()`, `agent()`, `log()`) to orchestrate multi-step operations. Workflows are registered via `export const meta = { ... }` at the top of the file.

Some skills are implemented entirely in their `.md` + `.sh` files without a workflow. Others delegate to a workflow `.js` file for complex multi-phase operations.

### Development Phase Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-review | `code-review.js` | 441 | Interactive code review with multi-AI consensus |
| code-review-auto | `code-review-auto.js` | 603 | Autonomous code review, auto-creates issues |
| code-solve | `code-solve.js` | 975 | Fix GitHub/GitLab issues with impact analysis |
| code-solve-auto | `code-solve-auto.js` | 678 | Autonomous issue resolver, auto-pushes fixes |

### Testing Phase Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-smoke-test | `code-smoke-test.js` | 12,695 | Quick smoke test: build, launch, basic interaction |
| code-test | `code-test.js` | 40,713 | Comprehensive testing: build, UI, integration, E2E |
| code-test-auto | `code-test-auto.js` | 18,804 | Autonomous testing, auto-creates issues for failures |

### PR Review Phase Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-pr-review | `code-pr-review.js` | 638 | Interactive PR review, prompts before approve/reject |
| code-pr-review-auto | `code-pr-review-auto.js` | 643 | Autonomous PR review, auto-approve/reject |

### Security Phase Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-security | `code-security.js` | 523 | OWASP + secrets + dependencies + licenses audit |
| code-security-auto | `code-security-auto.js` | 47 | Autonomous security audit, auto-creates issues |

### Documentation Phase Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-doc | `code-doc.js` | 396 | Generate missing documentation |
| code-doc-auto | `code-doc-auto.js` | 46 | Autonomous doc generation, auto-creates PRs |

### Release Phase Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-release-notes | `code-release-notes.js` | 465 | Generate and publish release notes |
| code-release-notes-auto | `code-release-notes-auto.js` | 43 | Autonomous release publishing |

### Meta-Orchestration Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| code-sdlc | `code-sdlc.js` | 368 | Run entire SDLC pipeline (interactive with decision gates) |
| code-sdlc-auto | `code-sdlc-auto.js` | 85 | Run entire SDLC pipeline (autonomous) |
| code-sdlc-auto-continuous | `code-sdlc-auto-continuous.js` | 321 | Continuous loop until codebase is clean. Delegates to `sdlc-loop.sh`. |

### Memory RAG Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| memory-rag-index | `memory-rag-index.js` | 298 | Index all memories in ChromaDB with semantic embeddings |
| memory-rag-search | `memory-rag-search.js` | 365 | Semantic search across memories with multi-AI consensus relevance analysis |

### Web Learning Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| ai-web-learn | `ai-web-learn.js` | 526 | Learn from web pages with multi-AI consensus |
| ai-web-learn-mcp | `ai-web-learn-mcp.js` | 485 | Production web learning with MCP tools |
| ai-web-learn-production | `ai-web-learn-production.js` | 622 | Production RAG with ChromaDB and embeddings |
| ai-web-learn-universal-ai | `ai-web-learn-universal-ai.js` | 306 | Integration with Universal AI RAG system |

### Research and Analysis Workflows

| Workflow | File | Lines | Description |
|----------|------|-------|-------------|
| deep-research | (varies) | 450 | Deep research harness with web search and adversarial verification |
| ai-pdf-deep-research | `ai-pdf-deep-research.js` | 710 | Adversarial PDF claim verification with 6-model consensus |

### Deprecated Workflows

The following `-bulk` and `-fleet` workflow variants are deprecated. Their functionality has been absorbed into the parent skills via fleet-aware mode (Option A+C architecture). They still exist but are hidden and will be removed in a future release.

| Deprecated Workflow | Replacement | Why Deprecated |
|--------------------|-----------  |----------------|
| ai-pdf-deep-research-bulk | ai-pdf-deep-research (with --fleet) | Unified skill handles both local and fleet |
| ai-web-learn-bulk | ai-web-learn (with --fleet) | Same |
| ai-web-learn-fleet | ai-web-learn (auto-detect) | Same |
| ai-web-code-learn-bulk | ai-web-code-learn (with --fleet) | Same |
| ai-web-code-learn-fleet | ai-web-code-learn (auto-detect) | Same |
| code-security-bulk | code-security (with --fleet) | Same |
| code-security-fleet | code-security (auto-detect) | Same |
| code-review-bulk | code-review (with --fleet) | Same |
| code-doc-bulk | code-doc (with --fleet) | Same |
| deep-research-bulk | deep-research (with --fleet) | Same |
| ai-prompt-fleet | ai-prompt (auto-detect) | Same |
| code-sdlc-fleet | code-sdlc (auto-detect) | Same |
| code-test-fleet | code-test (auto-detect) | Same |

**Why Option A+C (Unified Skills)?** Previously, each fleet-capable skill had 2-3 variants: the base skill, a `-bulk` variant for large batches, and a `-fleet` variant for distributed execution. This caused naming confusion, duplicated logic, and required users to know which variant to invoke. With Option A+C, the parent skill auto-detects fleet availability and item count, choosing the right execution mode transparently. The `--fleet` and `--local` flags provide explicit control when needed.

---

## Fleet Processing

### How Fleet Distribution Works

Fleet distribution follows a consistent pattern across all skills:

1. **Discovery**: Read `~/.claude/fleet.json`, filter machines by role/capabilities, health-check via SSH probe.

2. **Compliance Check**: Verify current working directory is not under a forbidden path (e.g., Red Hat proprietary repositories).

3. **Mode Resolution**: Apply the `resolveFleetMode()` decision tree (explicit flags, then auto-detect with break-even threshold).

4. **Batch Distribution**: Split items across workers using either round-robin (default) or weighted distribution (proportional to worker memory).

5. **Worker Dispatch**: Launch independent Claude Code sessions on each worker via SSH. Each session processes its batch independently.

6. **Progress Monitoring**: Track worker progress via NFS-visible progress files or SSH polling.

7. **Result Collection**: Collect outputs from workers (JSON, markdown, or files).

8. **Result Merging**: Merge and deduplicate results using skill-specific merge strategies.

9. **Fallback**: If too many workers fail (> 50%), fall back to local processing.

### Multi-Session Orchestration vs Agent Parallelism

There are two distinct approaches to parallelism in this project:

**Agent Parallelism (within a single Claude session):**
```javascript
// Uses Claude Code's parallel() API
// All "workers" run in the SAME session
// Labels are cosmetic -- no true distribution
const results = await parallel([
  () => agent(prompt, { model: 'opus', label: 'server-01' }),
  () => agent(prompt, { model: 'sonnet', label: 'server-02' }),
])
```
This is used by consensus skills (ai-prompt, ai-consensus variants). It provides model diversity but not compute distribution. All processing happens on the machine running Claude Code.

**Multi-Session Orchestration (across fleet machines):**
```javascript
// Uses SSH to launch INDEPENDENT Claude sessions
// Each worker is a separate process on a separate machine
// True parallelism with ~2.5-3x speedup
for (const worker of workers) {
  remoteExec(worker.hostname,
    `cd '${projectDir}' && claude -p --dangerously-skip-permissions '${prompt}'`
  )
}
```
This is used by fleet-aware skills for bulk processing. Each worker processes its batch completely independently. There is no inter-worker coordination -- each worker runs its own Claude Code session.

### Break-Even Thresholds

Fleet distribution has overhead: SSH connection setup, batch distribution, result collection, and merging. Below these thresholds, local processing is faster.

| Skill | Threshold | Item Type | Rationale |
|-------|-----------|-----------|-----------|
| ai-pdf-deep-research | 10 PDFs | PDF files | Chunking and 6-model processing justifies distribution overhead |
| ai-web-learn | 20 URLs | URLs | MCP fetching and parallel extraction overhead |
| ai-web-learn-production | 20 URLs | URLs | ChromaDB sync + embeddings overhead |
| code-security | 50 files | Source files | Full codebase scans justify distribution |
| code-review | 30 files | Source files | Multi-AI review per file is expensive |
| code-doc | 50 files | Source files | Doc generation per function is expensive |
| ai-web-code-learn-production | 5 repos | Git repos | AST parsing + semantic embeddings per repo is expensive |

### Performance Expectations

| Skill | Baseline (Local) | Fleet (3 workers) | Speedup |
|-------|------------------|-------------------|---------|
| ai-pdf-deep-research (100 PDFs) | ~8 hours | ~2.5 hours | 3.2x |
| ai-web-learn (100 URLs) | ~45 min | ~18 min | 2.5x |
| code-security (500 files) | ~2 hours | ~40 min | 3x |
| code-review (200 files) | ~1.5 hours | ~35 min | 2.6x |
| code-doc (300 files) | ~2.5 hours | ~50 min | 3x |

**Why not perfect 3x speedup?** Network latency adds 5-10% overhead. SSH connection setup is not free. Some tasks have dependencies that prevent perfect parallelism. Break-even thresholds already account for these costs.

**API-bound vs CPU-bound:** Most skills are API-bound (waiting for Claude API responses), not CPU-bound. Fleet distribution helps because each worker has its own API rate limit. More workers means more concurrent API calls, which is the primary source of speedup.

### Fleet Bash Scripts

Located in `scripts/fleet/`:

| Script | Purpose |
|--------|---------|
| `fleet-bulk-lib.sh` | Common library sourced by all bulk scripts. Provides fleet discovery, batch distribution, worker dispatch, progress monitoring, result merging, and cleanup. 1022 lines. |
| `fleet-distribute.sh` | Standalone item distribution across fleet workers. |
| `bulk-pdf-ingest.sh` | Distribute PDF deep research across fleet. |
| `bulk-url-learn.sh` | Distribute URL learning across fleet. |
| `bulk-security-scan.sh` | Distribute security scanning across fleet. |
| `bulk-code-review.sh` | Distribute code review across fleet. |
| `bulk-code-doc.sh` | Distribute documentation generation across fleet. |
| `bulk-repo-learn.sh` | Distribute repository learning across fleet. |
| `bulk-research.sh` | Distribute deep research across fleet. |
| `test-fleet-aware-skills.sh` | Test suite for fleet-aware skill functionality. |
| `test-fleet.sh` | Basic fleet connectivity and health check tests. |

---

## Shared Libraries

### JavaScript Libraries (shared/)

| Library | Purpose | Key Exports |
|---------|---------|-------------|
| **fleet-utils.js** | Fleet discovery, health checking, remote execution, compliance validation, fleet mode resolution. Core fleet library. | `loadFleetConfig()`, `validateCompliance()`, `probeHealth()`, `getFleet()`, `getWorkers()`, `getController()`, `remoteExec()`, `resolveFleetMode()`, `clearHealthCache()` |
| **fleet-multisession.js** | True multi-session orchestration. Launches independent Claude Code sessions on workers via SSH. | `splitBatches()`, `splitBatchesWeighted()`, `runMultiSession()`, `mergeMarkdownReports()`, `mergeJsonArrays()`, `mergeAndDeduplicateFindings()`, `mergeVectorStoreData()` |
| **fleet-bulk-orchestration.js** | Generic bulk orchestration framework. Used by all `-bulk` workflow variants. | `bulkOrchestrate()`, `mergeMarkdownResults()`, `mergeArrayResults()`, `mergeAndDedupFindings()`, `mergeEmbeddingResults()`, `mergeTestResults()`, `saveBatchFile()`, `loadBatchFile()` |
| **fleet-workflow-patterns.js** | High-level reusable patterns for fleet-distributed workflows. | `distributeAndMerge()`, `parallelPhases()`, `gracefulFallback()`, `distributeItems()`, `distributeItemsWeighted()`, `remoteExecJson()`, `remoteExecWithItems()`, `mergeArrays()`, `deduplicateFindings()`, `mergeTestResults()`, `getFleetSummary()`, `createFleetProgress()`, `workerTempDir()`, `nfsProjectPath()`, `isOnNfs()` |
| **fleet-integration.js** | Workflow-friendly fleet integration with args parsing. | `parseFleetArgs()`, `shouldUseFleet()`, `getFleetWorkers()`, `distributeModels()`, `getExecutionSummary()`, `createFleetAgentPrompts()` |
| **consensus-engine.js** | Core consensus engine for multi-AI patterns. | (Various consensus functions) |
| **smart-consensus.js** | Performance-aware consensus that routes to optimal models. | (Model selection functions) |
| **attribution.js** | Track which AI model said what in consensus outputs. | (Attribution tracking functions) |
| **impact-analysis.js** | Breaking change detection, severity scoring, exploitability analysis. | (Impact analysis functions) |
| **issue-operations.js** | Create/update GitHub/GitLab issues from findings. | (Issue CRUD functions) |
| **learning.js** / **learning-system.js** | Cross-session learning extraction and persistence. | (Learning functions) |
| **quality-scorer.js** | Score code quality across multiple dimensions. | (Scoring functions) |
| **work-coordinator.js** | Coordinate multi-agent work distribution. | (Coordination functions) |
| **workflow-helpers.js** | Common workflow utilities: arbiter patterns, schema definitions. | (Helper functions) |
| **model-compliance.js** | Path-based model restriction enforcement. Filters workers/arbiters per directory compliance rules. | `isModelAllowed()`, `filterAllowedModels()`, `getCompliantWorkers()`, `getCompliantArbiter()`, `hasModelRestrictions()`, `getActiveRestriction()` |
| **model-detection.js** / **model-discovery.js** | Detect available AI models (local Ollama, cloud APIs). | (Detection functions) |
| **model-performance.js** | Track model performance metrics over time. | (Performance tracking) |
| **platform-detector.js** | Detect platform (GitHub/GitLab) from git remote. | (Platform detection) |
| **chunking-utils.js** | Smart document chunking for RAG processing. | (Chunking functions) |
| **clustering-utils.js** | Cluster similar findings for deduplication. | (Clustering functions) |
| **loop-controller.js** | Control loop execution for continuous SDLC. | (Loop control) |
| **schemas.js** | Shared JSON Schema definitions. | (Schema objects) |

### Python Libraries (shared/)

| Library | Purpose |
|---------|---------|
| **rag.py** | RAG with citations: query, retrieve, generate with sources. Hybrid search (semantic + keyword). |
| **semantic-search.py** | Hybrid search with RRF algorithm, reranking (bi-encoder to cross-encoder). |
| **vector-store.py** | ChromaDB vector storage: local embeddings, metadata filtering, semantic retrieval. |

### Shell Libraries

| Library | Purpose |
|---------|---------|
| **skill-helpers.sh** | Common shell utilities for skill scripts. |
| **visual-indicators.sh** | Colored consensus output, progress indicators, model-specific colors. |

---

## Multi-AI Consensus System

### Arbiter Worker Pattern

Every meaningful decision in the system uses the arbiter/worker pattern:

1. **Workers** (6 models by default): Each model independently analyzes the same input. Different models catch different issues due to different training data and architectures.

2. **Arbiter** (1 model, rotated): Reviews all worker outputs, selects the best one (or synthesizes a combined answer), explains its reasoning, and assigns a confidence score.

3. **Cross-Provider Diversity**: Using models from 3 providers (Anthropic: Fable/Opus/Sonnet/Haiku, OpenAI: GPT-4o, Google: Gemini) reduces error correlation from ~60-70% (same-provider) to ~35-50% (cross-provider), achieving ~94% blind spot coverage.

**Standard pattern in code:**
```javascript
// Phase: Workers analyze independently
const workers = await parallel([
  () => agent(prompt, { model: 'fable', label: 'fable-worker', schema }),
  () => agent(prompt, { model: 'opus', label: 'opus-worker', schema }),
  () => agent(prompt, { model: 'sonnet', label: 'sonnet-worker', schema }),
  () => agent(prompt, { model: 'haiku', label: 'haiku-worker', schema }),
  () => agent(prompt, { model: 'gpt-4o', label: 'gpt4o-worker', schema }),
  () => agent(prompt, { model: 'gemini', label: 'gemini-worker', schema }),
])

const validWorkers = workers.filter(Boolean) // Graceful degradation

// Phase: Arbiter synthesizes
const synthesis = await agent(arbiterPrompt, {
  model: 'fable',  // Or next in rotation
  label: 'arbiter',
  schema: arbiterSchema
})
```

### Consensus Strategies

The `consensus-strategies.js` file implements 5 strategies plus auto-selection:

| Strategy | How It Works | When to Use |
|----------|-------------|-------------|
| **Rotating Arbiter** (Democratic) | Each worker takes turns being arbiter. Most thorough. | Critical decisions, maximum quality. Default. |
| **Single Arbiter** (Fast) | One designated arbiter judges all workers. | Speed-sensitive tasks where a single judgment suffices. |
| **Majority Vote** | Simple vote counting, no arbiter overhead. | When solutions are expected to converge (similar answers). |
| **Pairwise Comparison** (Tournament) | Workers compete in elimination pairs. | Diverse or creative solutions where ranking matters. |
| **Weighted Voting** | Workers provide confidence scores, combined via weighted average. | When confidence calibration is available and relevant. |
| **Auto-Select** | Chooses strategy based on context (critical, fast, diverse flags). | When the optimal strategy depends on runtime context. |

Additionally, there are higher-level strategies configured via `multi-ai-config.json`:

| Strategy | Models | Cost Multiplier | Use Case |
|----------|--------|-----------------|----------|
| **Maximum Coverage** (Default) | fable, opus, sonnet, haiku, gpt-4o, gemini | 7x | All decisions. Quality over cost. |
| **Quad Consensus** | opus, sonnet, haiku, gemini | 5x | Good coverage with lower cost |
| **Triple Consensus** | opus, sonnet, haiku | 4x | Minimum for meaningful consensus |
| **Dual Consensus** | opus, sonnet | 3x | Lightweight consensus |
| **Single AI** | (first model only) | 1x | Development/testing only. Not recommended. |
| **Workers Only** | All 6, no arbiter | 6x | Return all perspectives without synthesis |
| **Quantized** (QuantizedStrategy) | Ollama locals + cloud arbiter | ~1x | Zero-cost workers, cloud synthesis. Offline development. |
| **Quintuple Verification** | 5 progressive stages | Very high | Security audits, production releases, critical bugs |

### Multi-AI Configuration

Configuration is in `multi-ai-config.json`:

```json
{
  "enabled": true,
  "default_strategy": "maximum-coverage",
  "workers": {
    "models": ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"],
    "count": 6
  },
  "arbiter": {
    "enabled": true,
    "model": "fable",
    "fallback": ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"]
  }
}
```

The arbiter fallback chain means: try Fable first. If it fails, try Opus. If that fails, try Sonnet. And so on. This ensures workflows succeed even if 3-4 models are temporarily unavailable.

### Adding New Models

Models can be added to any workflow by editing the `WORKERS` array. Models that fail (not configured, not available, network error) return `null` and are automatically filtered out via `.filter(Boolean)`.

**Currently supported:**
- **Always available**: Fable, Opus, Sonnet, Haiku (Claude/Anthropic)
- **Enabled by default**: GPT-4o (OpenAI), Gemini (Google)
- **Available to enable**: Grok (xAI), Ollama local models (llama3, mistral, codellama, deepseek-coder), OpenAI GPT-4/GPT-4-turbo

**To add a model:**
1. Uncomment it in the WORKERS array of the relevant workflow file
2. Configure API keys or local model server
3. Test with `/ai-prompt test <model-name>`

See `ADDING_MODELS.md` for detailed setup instructions per model.

---

## Configuration

### Fleet Configuration

File: `~/.claude/fleet.json`

```json
{
  "machines": [
    {
      "hostname": "aio-01",
      "role": "controller",
      "memory_gb": 7,
      "cpus": 4,
      "priority": 99,
      "tags": ["nfs-server", "monitoring"],
      "capabilities": ["python", "nodejs"]
    },
    {
      "hostname": "server-01",
      "role": "worker",
      "memory_gb": 32,
      "cpus": 16,
      "priority": 1,
      "tags": ["compute"],
      "capabilities": ["python", "nodejs", "docker"]
    },
    {
      "hostname": "server-02",
      "role": "worker",
      "memory_gb": 64,
      "cpus": 32,
      "priority": 2,
      "capabilities": ["python", "nodejs"]
    },
    {
      "hostname": "server-03",
      "role": "worker",
      "memory_gb": 32,
      "cpus": 16,
      "priority": 3,
      "capabilities": ["python", "nodejs"]
    },
    {
      "hostname": "pi-02",
      "role": "sentinel",
      "memory_gb": 1,
      "cpus": 4,
      "priority": 99,
      "tags": ["monitoring"]
    }
  ],
  "policies": {
    "health_check_timeout_ms": 2000,
    "max_parallel_workers": 10
  },
  "compliance": {
    "forbidden_paths": ["/home/sfloess/Development/redhat/"],
    "path_restrictions": [
      {
        "path": "/home/sfloess/Development/redhat/",
        "denied_models": ["gpt-*"],
        "reason": "Red Hat compliance - no OpenAI"
      }
    ],
    "reason": "Red Hat proprietary work must not leave controlled infrastructure"
  }
}
```

**Key fields:**

- `machines[].role`: `controller` (orchestration), `worker` (compute), `sentinel` (monitoring only)
- `machines[].priority`: Lower number = higher priority. Workers sorted by priority for assignment.
- `machines[].capabilities`: Used for filtering (e.g., only workers with Docker for container tests).
- `machines[].tags`: Additional metadata for filtering.
- `policies.health_check_timeout_ms`: SSH probe timeout. 2 seconds is a good default for LAN.
- `policies.max_parallel_workers`: Cap on simultaneous workers regardless of fleet size.
- `compliance.forbidden_paths`: Directories where fleet mode is automatically disabled. Uses `fs.realpathSync()` to prevent symlink bypasses.
- `compliance.path_restrictions`: Fine-grained model restrictions per directory (NEW - IMPLEMENTED). Allows selective deny/allow of model families per path.

### Compliance Rules

The compliance system has two layers protecting proprietary work:

#### Layer 1: Fleet Mode Blocking (All-or-nothing)
- Any directory under `compliance.forbidden_paths` automatically disables fleet mode
- The `fleet-integration.js` module also hardcodes `/home/sfloess/Development/redhat/` as a forbidden path for belt-and-suspenders protection
- Symlink bypasses are prevented by resolving real paths before comparison
- When compliance blocks fleet mode, the skill runs locally with no error -- it just falls back silently

**Why this exists:** Red Hat proprietary source code must not be transmitted to or processed on machines outside the controlled development environment. Fleet workers are personal machines and may not meet Red Hat's security requirements.

#### Layer 2: Model Restrictions (Selective, per-path) ✨ NEW
- `compliance.path_restrictions` allows fine-grained model availability control per directory
- Specific model families can be **denied** (deny-list) or **allowed** (allow-list)
- Wildcard patterns supported: `gpt-*`, `claude-*`, `ollama-*`, `gemini-*`
- Most specific path wins (longest prefix match takes precedence)
- Workflows auto-filter workers and arbiters based on active restrictions

**Examples**:
- `/home/sfloess/Development/redhat/`: Deny `gpt-*` (no OpenAI), allow Anthropic, Google, and local models
- `/home/sfloess/Development/client-work/`: Allow `claude-*` only (Anthropic models only per contract)
- `/home/sfloess/Development/private/`: Allow `ollama-*` only (privacy-sensitive, local models only)

**Implementation**:
- `checkModelCompliance(modelName)` in `fleet-agent-wrapper.js` validates each model at agent creation
- `isModelAllowed(modelName)` in `shared/model-compliance.js` checks if a model is allowed in cwd
- `filterAllowedModels(models)` in `shared/model-compliance.js` auto-filters worker lists
- `getCompliantWorkers(defaults)` in `shared/model-compliance.js` returns compliance-filtered workers
- `getCompliantArbiter(default, fallbacks)` in `shared/model-compliance.js` selects first allowed arbiter
- `getCompliantArbiter(arbiters, cwd)` selects first allowed arbiter from fallback chain
- Clear error messages: "Model gpt-4o not allowed in /path/ - Reason: Red Hat compliance"

See `FEATURE_MODEL_RESTRICTIONS.md` for complete documentation.

### NFS Setup Requirements

For fleet distribution to work:

1. `/home/sfloess/Development` must be NFS-exported from aio-01 to all workers
2. All workers must mount this share at the same path
3. Workers use local `/tmp` for scratch work (not NFS) to avoid write contention
4. Results are collected via SSH `cat` commands, not by reading NFS directly

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `HOME` | User home directory (for `~/.claude/fleet.json` lookup) | Yes (system) |
| `XAI_API_KEY` | Grok/xAI API access | Only if using Grok model |
| `OPENAI_API_KEY` | OpenAI API access (via MCP) | Only if using GPT-4/GPT-4o |
| `GOOGLE_API_KEY` | Google AI API access | Only if using Gemini directly |
| `FLEET_NTFY_TOPIC` | ntfy notification topic for fleet alerts | Optional |
| `DEBUG` | Enable debug logging (`claude:workflows`) | Optional |

---

## Usage Examples

### Basic Skill Invocation

```bash
# Code review (interactive)
/code-review

# Code review (autonomous, in CI)
claude run code-review-auto

# Fix a GitHub issue
/code-solve 42

# Full SDLC pipeline
claude run code-sdlc +500k
```

### Fleet Mode (Auto-Detect)

```bash
# Small batch: runs locally (below threshold)
/ai-pdf-deep-research paper1.pdf paper2.pdf

# Large batch: auto-uses fleet if available
/ai-pdf-deep-research /path/to/600/pdfs/*.pdf
# Output: "Fleet Detection: 3 workers available, 600 items >= 10 threshold"
# Output: "Fleet mode: Distributing 600 PDFs across 3 workers"
```

### Force Local Mode

```bash
# Always run on this machine, even if fleet is available
/ai-pdf-deep-research /path/to/600/pdfs/*.pdf --local

# Useful for:
# - Debugging specific PDFs
# - Testing from a non-fleet machine
# - Avoiding SSH overhead for development
```

### Force Fleet Mode

```bash
# Require fleet distribution -- fail if fleet unavailable
/ai-pdf-deep-research /path/to/pdfs/*.pdf --fleet

# If fleet is unavailable, you get a clear error with troubleshooting steps
```

### Continuous SDLC Loop

```bash
# Run all SDLC phases in a loop until the codebase is clean
sdlc-loop.sh 5 500k
# Argument 1: max iterations (default: 5)
# Argument 2: token budget per iteration (default: 200k)

# Or via workflow
claude run code-sdlc-auto-continuous iterations=5 budget=500k
```

### Multi-AI Prompt

```bash
# Get 6-model consensus on any question
/ai-prompt "What is the best approach to implement rate limiting in Node.js?"
# Returns: arbiter-synthesized answer from 6 independent model responses
```

### Memory RAG

```bash
# Index all memories (first time)
claude run memory-rag-index

# Semantic search by meaning
claude run memory-rag-search query="how to parallelize agents"
```

### Nightly Automation (Crontab)

```bash
# Add to crontab for nightly runs
0 2 * * * cd ~/my-project && claude run code-sdlc-auto +800k
```

### Token Budget Guidelines

| Repo Size | Recommended Budget | What You Get |
|-----------|-------------------|--------------|
| Small (<1k files) | +300k-500k | All phases, moderate depth |
| Medium (1k-5k files) | +500k-800k | All phases, full depth |
| Large (5k+ files) | +800k-1.5M | All phases, maximum thoroughness |

---

## Monitoring

The `monitoring/` directory contains a production-ready Prometheus + node_exporter + Grafana deployment for the fleet.

### Components

- **Prometheus 3.12.0**: Metrics collection with 15-day retention, 3 GB storage cap
- **node_exporter 1.11.1**: System metrics from all 5 machines
- **Alertmanager 0.32.1**: Alert routing with grouping, inhibition, repeat intervals
- **Grafana (latest)**: Dashboards with Node Exporter Full (#1860)

### Alert Rules (21 rules in 7 groups)

- Host availability (HostDown, reboot detection)
- CPU alerts (high usage, critical usage, controller-specific threshold)
- Memory alerts (high usage, critical usage, pi-02 specific threshold for 1 GB RAM)
- Disk alerts (space low, space critical, predictive fill-in-24h, inodes)
- Network alerts (interface down, high errors)
- System health (systemd failures, high load, clock skew, swap usage)
- Prometheus self-monitoring (target down, storage high, config reload failure)

### Deployment

```bash
cd monitoring

# Dry run (verify connectivity)
./deploy-fleet-prometheus.sh --dry-run

# Full deployment
./deploy-fleet-prometheus.sh --ntfy-topic YOUR-UNIQUE-TOPIC

# Access dashboards
# Grafana: http://aio-01:3000
# Prometheus: http://aio-01:9090
# Alertmanager: http://aio-01:9093
```

### Memory Budget (aio-01: 7 GB total)

| Component | MemoryMax | Typical Usage |
|-----------|-----------|---------------|
| Prometheus | 3 GB | ~1.5 GB |
| Grafana | 512 MB | ~300 MB |
| Alertmanager | 256 MB | ~50 MB |
| **Total capped** | **3.75 GB** | **~1.85 GB** |
| OS + NFS + other | - | ~3.25 GB available |

---

## Testing

### Test Suites

| Test | Location | What It Tests |
|------|----------|---------------|
| Fleet connectivity | `scripts/fleet/test-fleet.sh` | SSH access to all workers, health probes |
| Fleet-aware skills | `scripts/fleet/test-fleet-aware-skills.sh` | resolveFleetMode() with various flag/threshold combinations |
| Performance monitor | `ai-performance-monitor.test.js` | Model performance tracking and metrics |
| Ollama integration | `test-ollama.sh` | Local Ollama model connectivity |

### How to Test Fleet Functionality

```bash
# Test fleet connectivity
./scripts/fleet/test-fleet.sh

# Test fleet-aware skill logic
./scripts/fleet/test-fleet-aware-skills.sh

# Test specific workflow syntax
node --check workflows/ai-pdf-deep-research.js
node --check ai-web-learn.js
```

### Dry-Run Mode

All fleet bulk scripts support `--dry-run` which shows the distribution plan without executing:

```bash
./scripts/fleet/bulk-pdf-ingest.sh --dry-run /path/to/pdfs/*.pdf
# Output: Shows which worker gets which PDFs, without launching any sessions
```

---

## Troubleshooting

### Fleet Mode Not Activating

**Symptom:** Fleet mode does not activate even with many items

**Diagnostics:**
```bash
# Check fleet.json exists
cat ~/.claude/fleet.json

# Verify machines are reachable
ssh server-01 echo OK
ssh server-02 echo OK
ssh server-03 echo OK

# Check item count exceeds threshold
ls *.pdf | wc -l
```

**Solutions:**
1. Create `~/.claude/fleet.json` with worker definitions
2. Fix SSH connectivity (ensure key-based auth, BatchMode=yes)
3. Increase item count above break-even threshold
4. Use `--fleet` flag to force fleet mode and see detailed error messages

### Fleet Mode Fails Mid-Execution

**Symptom:** Fleet starts but workers fail

**Diagnostics:**
```bash
# Check worker disk space
ssh server-01 df -h

# Check worker load
ssh server-01 uptime

# Check worker permissions
ssh server-01 ls -la /tmp

# Check Claude Code is installed on workers
ssh server-01 which claude
```

**Solutions:**
1. Free up disk space on workers
2. Wait for workers to become available (high load)
3. Install Claude Code on workers
4. Use `--local` while diagnosing

### Authentication Issues

**Symptom:** SSH connections fail to workers

**Solutions:**
1. Ensure SSH key-based authentication is configured (`ssh-copy-id server-01`)
2. Verify `BatchMode=yes` does not prompt for passwords
3. Check `StrictHostKeyChecking=accept-new` in SSH config
4. Verify hostname resolution (`getent hosts server-01`)

### NFS Mount Problems

**Symptom:** Workers cannot see project files

**Solutions:**
1. Verify NFS export on aio-01: `showmount -e aio-01`
2. Verify NFS mount on workers: `ssh server-01 df -h | grep Development`
3. Check NFS service status: `ssh aio-01 systemctl status nfs-server`
4. Ensure the project path starts with `/home/sfloess/Development`

### ChromaDB/Embeddings Issues

**Symptom:** Memory RAG or web learning workflows fail with package errors

**Solutions:**
1. Install dependencies: `npm install` in the project root
2. Install Python dependencies: `pip install -r requirements.txt`
3. Verify Node.js version >= 18: `node --version`
4. Issues #100-102 fixed subagent isolation problems -- ensure you have the latest code

### Model Failures

**Symptom:** Some models return null in consensus results

**This is expected behavior.** Models that fail (network error, rate limit, misconfiguration) return `null` and are filtered out with `.filter(Boolean)`. The workflow continues with available models. Check logs for warnings like "grok failed: Network error".

---

## Architecture Decisions

### Why "Fleet" Terminology (Not Cluster)

The machines are heterogeneous personal computers with different specs, roles, and capabilities. They are not a uniform compute cluster. "Fleet" conveys a collection of diverse vessels working together, which matches the reality of mixing a Raspberry Pi sentinel with 64 GB compute workers.

### Why Option A+C (Unified Skills, Not -bulk/-fleet Variants)

Previously, adding fleet support to a skill required creating 2-3 new files (skill-bulk, skill-fleet). This caused:
- Naming confusion ("Do I use code-review or code-review-bulk or code-review-fleet?")
- Duplicated logic across variants
- Maintenance burden (3 files to update for any change)

Option A+C adds fleet-awareness to the parent skill itself. The skill auto-detects fleet availability and chooses the right mode. Users never need to think about which variant to use.

### Why Multi-Session Orchestration (Not Single-Session Parallelism)

Claude Code's `parallel()` API runs tasks concurrently within a single session, but all tasks share the same API rate limit and machine resources. Multi-session orchestration launches independent Claude Code sessions on separate machines via SSH. Each session has its own rate limit, memory, and CPU. For embarrassingly parallel workloads (processing independent PDFs or URLs), multi-session is 2.5-3x faster.

### Why Static fleet.json (Not Dynamic Discovery)

At 5 machines, dynamic discovery (Consul, mDNS, etcd) is overkill. A static JSON file is:
- Simpler to understand and debug
- Zero dependencies (no discovery service to maintain)
- Version-controlled (changes are tracked in git)
- Portable (copy one file to set up fleet)

The threshold to reconsider is ~15+ machines, at which point static configuration becomes a burden.

### Why API Rate Limits Matter More Than CPU

Most skills are API-bound, not CPU-bound. They spend most of their time waiting for Claude API responses, not doing local computation. Fleet distribution helps because each worker machine gets its own API rate limit. More workers = more concurrent API calls = faster completion.

### Why Compliance Blocks Are Path-Based

Compliance rules use file system paths (not hostnames or network addresses) because the decision of whether to use fleet processing is fundamentally about what data is being processed, not where it is being processed from. Red Hat proprietary code is identified by its location on disk.

---

## Development Guide

### How to Add a New Fleet-Aware Skill

1. **Add `resolveFleetMode()` at the start of your skill:**

```javascript
import { resolveFleetMode } from './shared/fleet-utils.js';

const BREAK_EVEN_THRESHOLD = 20; // Adjust based on per-item processing cost

// Parse fleet-related args
const fleetArgs = (typeof args === 'string' ? args : '').split(/\s+/);
const fleetDecision = resolveFleetMode(fleetArgs, items.length, BREAK_EVEN_THRESHOLD);

log(`Fleet mode: ${fleetDecision.mode} (${fleetDecision.reason})`);
```

2. **Branch on fleet decision:**

```javascript
if (fleetDecision.mode === 'fleet') {
  // Delegate to bulk script or fleet-multisession
  const result = execSync(
    `${scriptsDir}/fleet/bulk-your-skill.sh ${itemArgs}`,
    { stdio: 'inherit', timeout: 7200000 }
  );
} else {
  // Process locally (existing logic)
  for (const item of items) {
    await processItem(item);
  }
}
```

3. **Create the fleet bash script** in `scripts/fleet/`:

```bash
#!/bin/bash
source "$(dirname "$0")/fleet-bulk-lib.sh"

fleet_discover_workers
fleet_check_compliance
fleet_init_session "your-skill"
fleet_distribute_roundrobin "$items_file"
fleet_dispatch_workers "/your-skill" "$prompt_template"
fleet_wait_workers
fleet_collect_results
fleet_merge_json "$output_file"
fleet_summary "your-skill" "$start_time" "$total_items"
```

4. **Add break-even threshold** to the documentation tables in this README and in `docs/FLEET_AWARE_SKILLS.md`.

### Pattern to Follow

Look at `ai-pdf-deep-research.js` as the canonical example of a fleet-aware skill. It demonstrates:
- `resolveFleetMode()` usage
- Fleet vs local branching
- Break-even threshold constant
- Graceful fallback on fleet failure

### Testing New Skills

```bash
# Syntax check
node --check your-new-skill.js

# Test below threshold (should run local)
/your-skill item1 item2

# Test above threshold without fleet (should run local with message)
/your-skill item1 ... item50

# Test with --local flag
/your-skill item1 ... item50 --local

# Test with --fleet flag (will error if no fleet)
/your-skill item1 ... item50 --fleet
```

---

## Known Limitations

1. **Workflow nesting**: Claude Code workflows cannot directly nest other workflows. The workaround is `sdlc-loop.sh`, which launches each phase as an independent Claude session.

2. **No filesystem access in workflows**: Workflow `.js` files cannot use `fs`, `require`, or other Node.js built-ins directly. They must use `agent()` to spawn subagents that can read files.

3. **Multi-AI config not yet dynamic**: Most workflows still use hardcoded model lists rather than reading from `multi-ai-config.json`. The configuration system is documented and ready but not yet wired into all workflows.

4. **npm vulnerabilities**: 4 security issues exist in the dependency tree (3 high, 1 critical). These are in development dependencies, not runtime. Fix with `npm audit fix --force` if needed.

5. **Arbiter rotation state**: The arbiter rotation tracking (`arbiter-state.json`) is gitignored and per-machine. It does not persist across machines or sessions.

6. **Pi-02 excluded from compute**: The Raspberry Pi 3B (1 GB RAM) cannot run Claude Code sessions. It is limited to monitoring duties.

---

## Future Enhancements

- **Dynamic multi-AI config**: Wire all workflows to read from `multi-ai-config.json` instead of hardcoded model lists.
- **Auto-discovery**: Ping all possible models at startup to auto-detect availability instead of hardcoding.
- **Resume from checkpoint**: Allow interrupted workflows to resume from the last completed phase.
- **Grafana fleet dashboards**: Custom dashboards showing fleet utilization, per-worker throughput, and skill performance.
- **Backend switching for vector storage**: Test ChromaDB vs Qdrant vs Weaviate via vectordb-ai adapter.
- **Port to FlossWare AI**: Migrate proven concepts (attribution, performance tracking, arbiter rotation, RAG) to FlossWare production libraries.
- **CI/CD integration**: GitHub Actions / GitLab CI templates for running autonomous skills in pipelines.
- **Removal of deprecated -bulk/-fleet variants**: Phase 3 of the deprecation timeline.

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| **v12** | 2026-06-12 | ai-pdf-deep-research skill (710 lines, adversarial PDF verification with 6-model consensus, challenger exclusion, arbiter rotation). ChromaDB/embeddings fixes (issues #100-102). 31 total workflows. |
| **v11** | 2026-06-11 | 6-model cross-provider consensus (Fable/Opus/Sonnet/Haiku/GPT-4o/Gemini). QuantizedStrategy (Ollama workers + cloud arbiter). QuintupleVerification (5-stage progressive validation). 20+ new consensus/utility workflows. |
| **v10** | 2026-06-09 | Memory RAG system (ChromaDB + semantic embeddings). Multi-AI consensus in ALL phases. sdlc-loop.sh continuous SDLC. 30 workflows. |
| **v9** | 2026-06-07 | Continuous SDLC loop (code-sdlc-auto-continuous). Enhanced phase entry banners. Fixed Date.now() violations in 9 workflows. 26 workflows. |
| **v8** | 2026-06-06 | Libvirt/VM management permissions. KVM/QEMU infrastructure support. |
| **v7** | 2026-06-06 | Dynamic model detection. Web learning workflows (3 new). Universal AI RAG integration. Gemini support. |
| **v6** | 2026-06-06 | Critical fix: Workflow tool permission. All .js workflows work in dont-ask mode. |
| **v5** | 2026-06-06 | Comprehensive permissions documentation (PERMISSIONS.md, 747 lines). Platform-specific permissions. |
| **v4** | 2026-06-06 | Complete SDLC suite (8 new workflows). Renamed pr-review to code-pr-review, app-test to code-smoke-test. 18 workflows. |
| **v3** | 2026-06-05 | Autonomous workflows (code-review-auto, code-solve-auto, code-test-auto, pr-review-auto). Impact analysis. |

---

## Statistics

- **Total Workflows**: 31 (18 SDLC + 2 Memory RAG + 4 Web Learning + 2 Research + 5 Utilities)
- **Total Skills**: 40+ (including consensus variants, utility skills, and learning skills)
- **Lines of Code**: 14,000+ lines of workflow code
- **Shared Libraries**: 25+ reusable JavaScript modules, 3 Python modules
- **Fleet Scripts**: 11 bash scripts for distributed orchestration
- **Multi-AI Models**: 6 models across 3 providers (Anthropic, OpenAI, Google)
- **Consensus Strategies**: 9 (rotating, single, majority, pairwise, weighted, auto, quantized, quintuple, hierarchical)
- **Platform Support**: GitHub + GitLab (auto-detected)
- **Language Support**: JavaScript/TypeScript, Python, Go, Rust
- **Alert Rules**: 21 Prometheus alert rules across 7 groups
- **Monitoring**: Prometheus + Grafana + Alertmanager + node_exporter on 5 machines

---

## First Time Setup

### Prerequisites

- Node.js >= 18
- Python 3 (for RAG and vector storage)
- SSH key-based access to fleet machines (if using fleet)

### Installation

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies (optional, for RAG features)
pip install -r requirements.txt

# Set up permissions for autonomous execution
./fix-permissions.sh
```

### Permissions

Before running autonomous workflows, set up permissions to prevent interactive prompts:

```bash
# Run the auto-setup script
./fix-permissions.sh
```

See `PERMISSIONS.md` for detailed manual setup or granular control.

---

## Related Projects

- **FlossWare AI**: https://github.com/FlossWare/ -- Production libraries that receive proven concepts from this project
  - consensus-ai: Multi-AI orchestration
  - knowledge-ai: Universal knowledge ingestion
  - semantic-search-ai: Advanced search
  - vectordb-ai: Vector database adapter
  - skills-ai: Executable workflows

---

**Built with Claude** | **Repository**: https://gitlab.cee.redhat.com/sfloess/claude-global-skills
