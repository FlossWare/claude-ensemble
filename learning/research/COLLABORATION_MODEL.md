# Claude Code Multi-Agent Collaboration Model

**Status:** Production Architecture  
**Version:** 2.0  
**Date:** 2026-06-13  
**Author:** Claude Code Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Core Patterns](#core-patterns)
4. [Fleet Distribution](#fleet-distribution)
5. [Workflow Execution](#workflow-execution)
6. [Error Recovery](#error-recovery)
7. [Learning Patterns](#learning-patterns)
8. [Coordination Strategies](#coordination-strategies)
9. [Examples](#examples)

---

## Executive Summary

Claude Code implements a sophisticated multi-agent collaboration model that combines:

- **Orchestrator-Agent coordination** for task delegation
- **Multi-AI consensus** (arbiter/worker pattern) for decision quality
- **Fleet distribution** across multiple machines for parallel execution
- **Autonomous workflows** with error recovery and learning
- **Multi-model diversity** (6+ AI models) for comprehensive coverage

**Key Philosophy:** Quality over cost. Maximum model coverage by default.

---

## Architecture Overview

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLAUDE CODE ORCHESTRATOR                     │
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Session    │───▶│   Workflow   │───▶│    Fleet     │          │
│  │   Manager    │    │   Engine     │    │  Dispatcher  │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                    │                    │                  │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              Multi-Agent Coordination Layer           │          │
│  │                                                        │          │
│  │  • Task Assignment      • Model Selection             │          │
│  │  • Dependency Tracking  • Resource Allocation         │          │
│  │  • Progress Monitoring  • Error Recovery              │          │
│  └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT EXECUTION LAYER                         │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │   Worker    │  │   Worker    │  │   Worker    │  │   Worker    ││
│  │   Agent 1   │  │   Agent 2   │  │   Agent 3   │  │   Agent 4   ││
│  │  (Fable)    │  │   (Opus)    │  │  (Sonnet)   │  │  (Haiku)    ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘│
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐                                   │
│  │   Worker    │  │   Arbiter   │                                   │
│  │   Agent 5   │  │   Agent     │                                   │
│  │  (GPT-4o)   │  │  (Gemini)   │                                   │
│  └─────────────┘  └─────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DISTRIBUTED FLEET LAYER                         │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  aio-01 (Controller)                                         │   │
│  │  • Orchestration    • NFS Server    • Job Queue             │   │
│  │  • Caching Proxy    • Prometheus    • 2 CPU / 7 GB          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  server-01   │  │  server-02   │  │  server-03   │              │
│  │  (Worker)    │  │  (Worker)    │  │  (Worker)    │              │
│  │  8C / 15GB   │  │  8C / 31GB   │  │  8C / 31GB   │              │
│  │              │  │  High-Memory │  │  High-Memory │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  pi-02 (Sentinel)                                            │   │
│  │  • Health Monitoring  • Log Aggregation  • File Watcher     │   │
│  │  • Always-On Watchdog • 4 CPU (ARM64) / 1 GB                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Roles

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| **Orchestrator** | Task coordination, workflow execution, session management | Claude Code main process |
| **Workers** | Execute tasks in parallel, propose solutions independently | Multi-model AI agents (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) |
| **Arbiter** | Synthesize worker proposals, select best solution, resolve conflicts | Rotating AI model (typically Fable/Opus) |
| **Fleet** | Distribute work across machines, optimize resource usage | aio-01 (controller) + server-01/02/03 (workers) + pi-02 (sentinel) |
| **Learning System** | Extract patterns, store learnings, improve over time | SQLite + RAG + active learning |

---

## Core Patterns

### 1. Arbiter/Worker Pattern

**Purpose:** Multi-AI consensus for high-quality decisions

**Architecture:**

```
                        ┌─────────────────────────────────────┐
                        │      ORCHESTRATOR                   │
                        │  Distributes task to workers        │
                        └─────────────┬───────────────────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
                ▼                     ▼                     ▼
        ┌───────────────┐     ┌───────────────┐    ┌───────────────┐
        │   Worker 1    │     │   Worker 2    │    │   Worker 3    │
        │   (Fable)     │     │    (Opus)     │    │   (Sonnet)    │
        │               │     │               │    │               │
        │  Proposes     │     │  Proposes     │    │  Proposes     │
        │  Solution A   │     │  Solution B   │    │  Solution C   │
        └───────┬───────┘     └───────┬───────┘    └───────┬───────┘
                │                     │                     │
                └─────────────────────┼─────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────┐
                        │       ARBITER           │
                        │     (Gemini/Opus)       │
                        │                         │
                        │  Evaluates proposals:   │
                        │  • Correctness          │
                        │  • Completeness         │
                        │  • Risk assessment      │
                        │  • Selects best         │
                        └─────────┬───────────────┘
                                  │
                                  ▼
                        ┌─────────────────────────┐
                        │   ROLE SWAP VALIDATION  │
                        │                         │
                        │  Arbiter → Worker       │
                        │  Workers → Arbiters     │
                        │                         │
                        │  Skeptical review +     │
                        │  Multi-arbiter vote     │
                        └─────────┬───────────────┘
                                  │
                                  ▼
                        ┌─────────────────────────┐
                        │   CONSENSUS CHECK       │
                        │                         │
                        │  ✓ Consensus reached?   │
                        │    → Apply solution     │
                        │  ✗ No consensus?        │
                        │    → Iterate with       │
                        │      refinements        │
                        └─────────────────────────┘
```

**Execution Flow:**

```
Phase 1: PARALLEL WORKER PROPOSALS
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Fable   │  │   Opus   │  │  Sonnet  │  │  Haiku   │  │  GPT-4o  │  │  Gemini  │
│ Worker   │  │  Worker  │  │  Worker  │  │  Worker  │  │  Worker  │  │  Worker  │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │             │             │
     │ Proposal A  │ Proposal B  │ Proposal C  │ Proposal D  │ Proposal E  │ Proposal F
     │             │             │             │             │             │
     └─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
                                      │
                                      ▼
Phase 2: ARBITER SELECTION
                          ┌─────────────────────┐
                          │  Arbiter (Fable)    │
                          │                     │
                          │  Reviews 6 proposals│
                          │  Selects best: C    │
                          │  Reasoning: ...     │
                          │  Confidence: 85%    │
                          └──────────┬──────────┘
                                     │
                                     ▼
Phase 3: ROLE SWAP
     
     Old Arbiter (Fable) ────────────▶ New Worker (Skeptical Review)
     
     Old Workers (Opus, Sonnet,   ───▶ New Arbiters (Vote on proposal)
                  Haiku, GPT-4o,
                  Gemini - except 
                  selected Sonnet)
                                     │
                                     ▼
Phase 4: VALIDATION
     
     New Worker Review: ✓ Approved
     New Arbiter Votes: 4 approve, 1 reject (80% consensus)
     
     Overall Consensus: ✓ REACHED
                                     │
                                     ▼
Phase 5: APPLICATION
     
     Apply selected solution (Proposal C from Sonnet)
     Track attribution for all 6 models
```

**Critical Rules:**

1. **Always use different models** for workers (diversity = better coverage)
2. **Different arbiters** for different phases (review ≠ solve ≠ verify)
3. **Always use parallel()** for worker proposals (independence critical)
4. **Role swap required** for validation (prevents bias)
5. **Maximum iterations: 10** (prevent infinite loops)
6. **Default: 6 models** (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)

**Code Example:**

```javascript
// Phase 1: Workers propose in parallel
const WORKER_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const ARBITER_MODEL = 'fable'

log(`🔄 ${WORKER_MODELS.length} workers proposing in parallel...`)

const proposals = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose solution for bug X', {
    label: `${model} Proposal`,
    model: model,
    schema: PROPOSAL_SCHEMA
  })
))

log(`✅ Received ${proposals.filter(Boolean).length} proposals`)

// Phase 2: Arbiter selects
const decision = await agent('Select best proposal', {
  model: ARBITER_MODEL,
  schema: DECISION_SCHEMA
})

// Phase 3-5: Role swap validation
const consensus = await validateWithRoleSwap(decision, ARBITER_MODEL, WORKER_MODELS)
```

---

### 2. Multi-Phase Pattern (Review → Solve → Verify)

**Purpose:** Complex workflows requiring multiple sequential stages

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-PHASE WORKFLOW                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
     ┌────────────────────────┼────────────────────────┐
     │                        │                        │
     ▼                        ▼                        ▼
┌──────────┐            ┌──────────┐            ┌──────────┐
│  PHASE 1 │            │  PHASE 2 │            │  PHASE 3 │
│  REVIEW  │───────────▶│  SOLVE   │───────────▶│  VERIFY  │
│          │            │          │            │          │
│ Arbiter: │            │ Arbiter: │            │ Arbiter: │
│  Fable   │            │   Opus   │            │  Sonnet  │
│          │            │          │            │          │
│ Workers: │            │ Workers: │            │ Workers: │
│ O,S,H,G  │            │ F,S,H,G  │            │ F,O,H,G  │
└────┬─────┘            └────┬─────┘            └────┬─────┘
     │                       │                       │
     │ Findings              │ Solutions             │ Validation
     │                       │                       │
     ▼                       ▼                       ▼
┌──────────┐            ┌──────────┐            ┌──────────┐
│ Role Swap│            │ Role Swap│            │ Role Swap│
│ Validate │            │ Validate │            │ Validate │
└────┬─────┘            └────┬─────┘            └────┬─────┘
     │                       │                       │
     │ ✓ Consensus           │ ✓ Consensus           │ ✓ Consensus
     │                       │                       │
     └───────────────────────┴───────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  FINAL RESULT    │
                    │                  │
                    │  • Verified bugs │
                    │  • Tested fixes  │
                    │  • Attribution   │
                    └──────────────────┘
```

**Key Principle:** **NEVER use same arbiter for consecutive phases**

Why? Same arbiter would favor their own previous decisions (bias).

**Example:**

```javascript
// PHASE 1: REVIEW (Arbiter: Fable)
const reviewWorkers = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const reviewArbiter = 'fable'

const findings = await parallel(reviewWorkers.map(model =>
  () => agent('Find bugs', { model, schema: FINDING_SCHEMA })
))

const reviewDecision = await agent('Select best findings', {
  model: reviewArbiter,
  schema: ARBITER_SCHEMA
})

const reviewConsensus = await validateWithRoleSwap(
  reviewDecision, reviewArbiter, reviewWorkers
)

// PHASE 2: SOLVE (Arbiter: Opus - DIFFERENT!)
const solveWorkers = ['fable', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const solveArbiter = 'opus'  // ⚠️ MUST be different

const fixes = await parallel(solveWorkers.map(model =>
  () => agent('Propose fix', { model, schema: FIX_SCHEMA })
))

const solveDecision = await agent('Select best fix', {
  model: solveArbiter,
  schema: ARBITER_SCHEMA
})

const solveConsensus = await validateWithRoleSwap(
  solveDecision, solveArbiter, solveWorkers
)

// PHASE 3: VERIFY (Arbiter: Sonnet - DIFFERENT!)
const verifyWorkers = ['fable', 'opus', 'haiku', 'gpt-4o', 'gemini']
const verifyArbiter = 'sonnet'  // ⚠️ MUST be different

// ... similar pattern
```

---

## Fleet Distribution

### Fleet Topology

```
                    ┌──────────────────────────────────────┐
                    │         INTERNET / CLOUD             │
                    │                                      │
                    │  ┌────────────┐  ┌────────────┐    │
                    │  │  Anthropic │  │   OpenAI   │    │
                    │  │    API     │  │    API     │    │
                    │  └─────┬──────┘  └─────┬──────┘    │
                    │        │                │           │
                    │  ┌─────┴──────┐  ┌──────┴──────┐   │
                    │  │   Google   │  │   Ollama    │   │
                    │  │   Gemini   │  │  (laptop)   │   │
                    │  └─────┬──────┘  └──────┬──────┘   │
                    └────────┼─────────────────┼──────────┘
                             │                 │
                             ▼                 ▼
        ┌────────────────────────────────────────────────────────┐
        │            LOCAL NETWORK (192.168.1.0/24)              │
        │                                                         │
        │  ┌──────────────────────────────────────────────────┐ │
        │  │  aio-01 (Controller / Orchestrator)              │ │
        │  │  • Task Distribution                             │ │
        │  │  • NFS Server (shared /home/sfloess/Development) │ │
        │  │  • Job Queue (Redis)                             │ │
        │  │  • Metrics (Prometheus)                          │ │
        │  │  • Caching Proxy                                 │ │
        │  │  Resources: 2 CPU, 7 GB RAM                      │ │
        │  └─────────────────────┬────────────────────────────┘ │
        │                        │                               │
        │         ┌──────────────┼──────────────┐               │
        │         │              │              │               │
        │         ▼              ▼              ▼               │
        │  ┌──────────┐   ┌──────────┐   ┌──────────┐         │
        │  │server-01 │   │server-02 │   │server-03 │         │
        │  │ (Worker) │   │ (Worker) │   │ (Worker) │         │
        │  │          │   │          │   │          │         │
        │  │ 8C/15GB  │   │ 8C/31GB  │   │ 8C/31GB  │         │
        │  │          │   │High-Mem  │   │High-Mem  │         │
        │  │          │   │          │   │          │         │
        │  │ Tasks:   │   │ Tasks:   │   │ Tasks:   │         │
        │  │ • Build  │   │ • Heavy  │   │ • Heavy  │         │
        │  │ • Test   │   │   Models │   │   Models │         │
        │  │ • Light  │   │ • Large  │   │ • Large  │         │
        │  │   Models │   │   Builds │   │   Builds │         │
        │  └──────────┘   └──────────┘   └──────────┘         │
        │                                                        │
        │  ┌──────────────────────────────────────────────────┐ │
        │  │  pi-02 (Sentinel - ARM64 Raspberry Pi)           │ │
        │  │  • Health Monitoring (all machines)              │ │
        │  │  • Log Aggregation                               │ │
        │  │  • File Watcher (NFS changes)                    │ │
        │  │  • DNS / Network Services                        │ │
        │  │  • Always-On Watchdog (2-3W power)               │ │
        │  │  Resources: 4 CPU (ARM), 1 GB RAM                │ │
        │  └──────────────────────────────────────────────────┘ │
        └────────────────────────────────────────────────────────┘

                    ┌──────────────────────────┐
                    │  SHARED STORAGE (NFS)    │
                    │  /home/sfloess/Development│
                    │                          │
                    │  • Source Code           │
                    │  • Build Artifacts       │
                    │  • Shared Cache          │
                    │  • Logs & Metrics        │
                    └──────────────────────────┘
```

### Fleet Distribution Strategy

**Model → Machine Mapping:**

```
┌───────────────────────────────────────────────────────────────┐
│                    FLEET DISTRIBUTION LOGIC                    │
└───────────────────────────────────────────────────────────────┘

INPUT: 6 AI Models needing execution
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│  Fable   │   Opus   │  Sonnet  │  Haiku   │  GPT-4o  │  Gemini  │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
      │          │          │          │          │          │
      │          │          │          │          │          │
      ▼          ▼          ▼          ▼          ▼          ▼

DISTRIBUTION ALGORITHM:
  1. Sort machines by: available CPU > available RAM > network latency
  2. Round-robin assign models to machines
  3. Heavy models (Opus, GPT-4o) → high-memory machines (server-02/03)
  4. Light models (Haiku, Gemini) → standard machines (server-01)
  5. Fast models (Fable, Sonnet) → any available machine

OUTPUT: Model-Machine Assignment
┌──────────────────────────────────────────────────────────────────┐
│  Fable  → server-02  (8C/31GB)  [Available: 6C/25GB]             │
│  Opus   → server-03  (8C/31GB)  [Available: 7C/28GB]             │
│  Sonnet → server-01  (8C/15GB)  [Available: 5C/10GB]             │
│  Haiku  → server-01  (8C/15GB)  [Available: 5C/10GB - shared]    │
│  GPT-4o → server-02  (8C/31GB)  [Available: 6C/25GB - shared]    │
│  Gemini → server-03  (8C/31GB)  [Available: 7C/28GB - shared]    │
└──────────────────────────────────────────────────────────────────┘

EXECUTION:
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  server-01   │       │  server-02   │       │  server-03   │
│              │       │              │       │              │
│  Sonnet ───┐ │       │  Fable ────┐ │       │  Opus ────┐ │
│  Haiku  ───┤ │       │  GPT-4o ───┤ │       │  Gemini ──┤ │
│            │ │       │            │ │       │           │ │
└────────────┼─┘       └────────────┼─┘       └───────────┼─┘
             │                      │                     │
             │ Results              │ Results             │ Results
             │                      │                     │
             └──────────────────────┴─────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  aio-01          │
                          │  (Controller)    │
                          │                  │
                          │  Collects all    │
                          │  6 results       │
                          │                  │
                          │  Sends to        │
                          │  Arbiter         │
                          └──────────────────┘
```

### Resource Allocation Rules

| Machine | Max Concurrent Models | Priority Models | Restrictions |
|---------|----------------------|----------------|--------------|
| **aio-01** | 1 (controller overhead) | Arbiter only | CPU < 60% (preserve NFS) |
| **server-01** | 2-3 | Light models (Haiku, Gemini, Sonnet) | General purpose |
| **server-02** | 2-3 | Heavy models (Opus, Fable, GPT-4o) | High-memory tasks |
| **server-03** | 2-3 | Heavy models (Opus, Fable, GPT-4o) | High-memory tasks |
| **pi-02** | 0 (monitoring only) | None | Never use for compute (1GB RAM) |

### Fleet Communication Protocol

```
Agent Request Flow:
─────────────────────

1. ORCHESTRATOR (aio-01) receives task
   ↓
2. Check fleet health status (from pi-02 sentinel)
   ↓
3. Query available workers via Redis job queue
   ↓
4. Distribute model assignments
   ↓
5. Send RPC calls to each worker via SSH + fleet-utils.js
   ↓
6. Workers execute agent() calls with assigned models
   ↓
7. Workers return results via Redis
   ↓
8. Orchestrator collects results (waits for all with timeout)
   ↓
9. Forward to arbiter for synthesis
   ↓
10. Return final result

Health Check Protocol:
─────────────────────

pi-02 (Sentinel) continuously monitors:
  • Ping all machines every 30s
  • Check CPU/memory via SSH every 60s
  • Monitor NFS mount status every 120s
  • Aggregate logs from all machines
  • Alert orchestrator if any machine unhealthy

Cache Strategy:
──────────────

aio-01 runs caching proxy for:
  • API responses (Anthropic, OpenAI, Google)
  • Common model outputs
  • NFS file metadata
  • Build artifacts

TTL: 15 minutes (configurable)
```

---

## Workflow Execution

### Workflow Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      WORKFLOW LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────┘

1. REGISTRATION
   ┌──────────────────────────────────────────────┐
   │ Workflow file: /workflows/my-workflow.js     │
   │                                              │
   │ export const meta = {                        │
   │   name: 'my-workflow',                       │
   │   description: '...',                        │
   │   phases: [...]                              │
   │ }                                            │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Workflow Engine validates:                   │
   │ • meta block present?                        │
   │ • phases defined?                            │
   │ • no syntax errors?                          │
   │ • dependencies available?                    │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Add to workflow registry                     │
   │ Skill: /my-workflow now callable             │
   └──────────────────────────────────────────────┘

2. INVOCATION
   ┌──────────────────────────────────────────────┐
   │ User: /my-workflow arg1 arg2                 │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Workflow Engine:                             │
   │ 1. Parse args                                │
   │ 2. Create execution context                  │
   │ 3. Initialize phase tracker                  │
   │ 4. Setup error recovery                      │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼

3. PHASE EXECUTION
   ┌──────────────────────────────────────────────┐
   │ Phase 1: Discovery                           │
   │ phase('Discovery')                           │
   │ • UI shows progress spinner                  │
   │ • Logs collected                             │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Phase 2: Multi-Model Response                │
   │ phase('Multi-Model Response')                │
   │                                              │
   │ Parallel execution:                          │
   │   Worker 1 (Fable)   ─┐                     │
   │   Worker 2 (Opus)    ─┤                     │
   │   Worker 3 (Sonnet)  ─┼─▶ Fleet Dispatch   │
   │   Worker 4 (Haiku)   ─┤                     │
   │   Worker 5 (GPT-4o)  ─┤                     │
   │   Worker 6 (Gemini)  ─┘                     │
   │                                              │
   │ • Progress bar: 6 workers                    │
   │ • Real-time updates from fleet               │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Phase 3: Arbiter Synthesis                   │
   │ phase('Arbiter Synthesis')                   │
   │ • Arbiter (Fable) reviews proposals          │
   │ • Selects best solution                      │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Phase 4: Validation                          │
   │ phase('Validation')                          │
   │ • Role swap                                  │
   │ • Consensus check                            │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼

4. COMPLETION
   ┌──────────────────────────────────────────────┐
   │ Workflow completes successfully              │
   │                                              │
   │ Return:                                      │
   │ {                                            │
   │   status: 'success',                         │
   │   result: {...},                             │
   │   attribution: {...},                        │
   │   execution_time: 45.2,                      │
   │   phases_completed: 4                        │
   │ }                                            │
   └──────────────┬───────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────┐
   │ Learning System:                             │
   │ • Extract patterns                           │
   │ • Store in SQLite                            │
   │ • Update model performance metrics           │
   │ • Generate learnings file                    │
   └──────────────────────────────────────────────┘
```

### Parallel vs Pipeline Execution

```
PARALLEL EXECUTION (Default for Workers)
────────────────────────────────────────

Purpose: Independent work, maximum parallelism
When: Workers proposing solutions, analyzing independently

┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Worker1 │   │ Worker2 │   │ Worker3 │   │ Worker4 │
│ (Fable) │   │ (Opus)  │   │(Sonnet) │   │ (Haiku) │
└────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘
     │             │             │             │
     │ Start: 0s   │ Start: 0s   │ Start: 0s   │ Start: 0s
     │             │             │             │
     │ Work...     │ Work...     │ Work...     │ Work...
     │             │             │             │
     │ End: 10s    │ End: 12s    │ End: 9s     │ End: 8s
     │             │             │             │
     └─────────────┴─────────────┴─────────────┘
                        │
           Total Time: 12s (max of all workers)
                        │
                        ▼
           All results collected together

Code:
const results = await parallel(
  WORKER_MODELS.map(model =>
    () => agent('Task', { model })
  )
)


PIPELINE EXECUTION (For Sequential Dependencies)
─────────────────────────────────────────────────

Purpose: Multi-stage processing, each stage depends on previous
When: Each item needs multiple dependent analysis stages

Items: [A, B, C]

Stage 1: Analyze
┌───────┐  ┌───────┐  ┌───────┐
│ A→A1  │  │ B→B1  │  │ C→C1  │
└───┬───┘  └───┬───┘  └───┬───┘
    │          │          │
    │ 5s       │ 5s       │ 5s
    │          │          │
    ▼          ▼          ▼
Stage 2: Propose Fix
┌───────┐  ┌───────┐  ┌───────┐
│ A1→A2 │  │ B1→B2 │  │ C1→C2 │
└───┬───┘  └───┬───┘  └───┬───┘
    │          │          │
    │ 8s       │ 8s       │ 8s
    │          │          │
    ▼          ▼          ▼
Stage 3: Verify
┌───────┐  ┌───────┐  ┌───────┐
│ A2→A3 │  │ B2→B3 │  │ C2→C3 │
└───────┘  └───────┘  └───────┘
    │          │          │
    │ 3s       │ 3s       │ 3s
    
Total Time: 16s (sum of longest path through stages)

Items process independently, but each item goes through
all stages in sequence.

Code:
const results = await pipeline(
  items,
  item => agent('Analyze', {...}),
  (analysis, item) => agent('Fix', {...}),
  (fix, item) => agent('Verify', {...})
)


WHEN TO USE WHICH
─────────────────

✅ Use parallel() when:
  • Workers proposing independent solutions
  • No dependencies between tasks
  • Want maximum speed
  • Example: 6 models analyzing same code for bugs

✅ Use pipeline() when:
  • Multiple sequential stages
  • Each stage depends on previous
  • Processing multiple items through same stages
  • Example: [File1, File2, File3] each needing: analyze → fix → verify
```

---

## Error Recovery

### Error Handling Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ERROR RECOVERY SYSTEM                        │
└─────────────────────────────────────────────────────────────────┘

ERROR DETECTION
───────────────

┌──────────────────────────────────────────────────────────────┐
│  Execution Monitor (Continuous)                              │
│                                                              │
│  Watches for:                                                │
│  • Agent timeout (> 2 min default)                           │
│  • API errors (rate limit, auth, network)                    │
│  • Fleet worker unreachable                                  │
│  • Model refusal / safety filter                             │
│  • Invalid schema response                                   │
│  • Out of memory                                             │
│  • Unexpected exceptions                                     │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       │ Error Detected
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Error Classifier                                            │
│                                                              │
│  Categorizes error:                                          │
│  • TRANSIENT (retry likely to succeed)                       │
│    - Network timeout                                         │
│    - Rate limit                                              │
│    - Temporary API outage                                    │
│                                                              │
│  • PERMANENT (retry won't help)                              │
│    - Invalid API key                                         │
│    - Model doesn't exist                                     │
│    - Schema incompatible                                     │
│                                                              │
│  • DEGRADED (partial success possible)                       │
│    - One worker failed, others succeeded                     │
│    - Fleet machine down, can run locally                     │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
   TRANSIENT      PERMANENT      DEGRADED


RECOVERY STRATEGY: TRANSIENT ERRORS
────────────────────────────────────

┌──────────────────────────────────────────────┐
│ Retry with Exponential Backoff              │
│                                              │
│ Attempt 1: Immediate retry                  │
│ Attempt 2: Wait 2s, retry                   │
│ Attempt 3: Wait 4s, retry                   │
│ Attempt 4: Wait 8s, retry                   │
│ Attempt 5: Wait 16s, retry (max)            │
│                                              │
│ If all retries fail → PERMANENT             │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│ Model Fallback Chain                        │
│                                              │
│ Opus failed? → Try Sonnet                   │
│ Sonnet failed? → Try Haiku                  │
│ Haiku failed? → Try local Ollama            │
│ All Claude failed? → Try GPT-4o             │
│ All commercial failed? → Try Gemini         │
└──────────────────────────────────────────────┘


RECOVERY STRATEGY: PERMANENT ERRORS
────────────────────────────────────

┌──────────────────────────────────────────────┐
│ Graceful Degradation                         │
│                                              │
│ 1. Log error details                         │
│ 2. Skip failed worker                        │
│ 3. Continue with remaining workers           │
│ 4. Adjust consensus threshold                │
│                                              │
│ Example:                                     │
│   6 workers planned                          │
│   1 worker has permanent error               │
│   → Continue with 5 workers                  │
│   → Consensus threshold: 3/5 instead of 4/6  │
└──────────────────────────────────────────────┘


RECOVERY STRATEGY: DEGRADED ERRORS
───────────────────────────────────

┌──────────────────────────────────────────────┐
│ Partial Success Strategy                     │
│                                              │
│ Scenario: 6 workers, 2 failed                │
│                                              │
│ Option 1: Continue with 4 results            │
│   ✓ Faster completion                        │
│   ✗ Lower confidence                         │
│                                              │
│ Option 2: Spawn 2 replacement workers        │
│   ✓ Full coverage maintained                 │
│   ✗ Slower (wait for new workers)            │
│                                              │
│ Decision logic:                              │
│   IF remaining_workers >= MIN_THRESHOLD (3)  │
│     → Continue with partial                  │
│   ELSE                                       │
│     → Spawn replacements                     │
└──────────────────────────────────────────────┘


FLEET-SPECIFIC RECOVERY
───────────────────────

┌──────────────────────────────────────────────┐
│ Worker Unreachable                           │
│                                              │
│ 1. Detect: SSH connection failed             │
│ 2. Check: pi-02 sentinel health status       │
│ 3. Decide:                                   │
│                                              │
│    Machine temporarily down?                 │
│    → Redistribute tasks to other workers     │
│    → Mark machine as unavailable             │
│    → Alert admin                             │
│                                              │
│    Network partition?                        │
│    → Fallback to local execution             │
│    → Log warning (slower performance)        │
│                                              │
│    Permanent failure?                        │
│    → Remove from fleet pool                  │
│    → Update fleet.json status                │
└──────────────────────────────────────────────┘
```

### Error Recovery Example

```javascript
// Example: Robust worker execution with error recovery

async function executeWorkersWithRecovery(task, workerModels) {
  const MAX_RETRIES = 3
  const MIN_WORKERS = 3
  const results = []
  const failed = []
  
  log(`🔄 Executing ${workerModels.length} workers...`)
  
  // Phase 1: Initial execution (parallel)
  const initialResults = await parallel(
    workerModels.map(model => async () => {
      try {
        return await agentWithRetry(task, model, MAX_RETRIES)
      } catch (error) {
        log(`⚠️  Worker ${model} failed: ${error.message}`)
        failed.push({ model, error })
        return null
      }
    })
  )
  
  // Collect successful results
  initialResults.forEach((result, idx) => {
    if (result) {
      results.push({ model: workerModels[idx], result })
    }
  })
  
  log(`✅ ${results.length}/${workerModels.length} workers succeeded`)
  
  // Phase 2: Recovery if needed
  if (results.length < MIN_WORKERS) {
    log(`⚠️  Only ${results.length} workers succeeded, need ${MIN_WORKERS}`)
    log('🔄 Spawning replacement workers...')
    
    // Try fallback models
    const fallbackModels = ['gpt-4o', 'gemini', 'ollama:qwen2.5-coder']
    const needed = MIN_WORKERS - results.length
    
    const replacements = await parallel(
      fallbackModels.slice(0, needed).map(model => async () => {
        try {
          return await agentWithRetry(task, model, MAX_RETRIES)
        } catch (error) {
          log(`⚠️  Fallback ${model} also failed`)
          return null
        }
      })
    )
    
    replacements.forEach((result, idx) => {
      if (result) {
        results.push({ model: fallbackModels[idx], result })
      }
    })
  }
  
  // Phase 3: Final check
  if (results.length < MIN_WORKERS) {
    throw new Error(
      `Failed to get minimum ${MIN_WORKERS} worker results. ` +
      `Got ${results.length}. Failed workers: ${failed.map(f => f.model).join(', ')}`
    )
  }
  
  log(`✅ Recovery complete: ${results.length} workers`)
  
  return { results, failed }
}

async function agentWithRetry(task, model, maxRetries) {
  let lastError
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await agent(task, { model, timeout: 120000 })
    } catch (error) {
      lastError = error
      
      // Check if error is retryable
      if (isTransientError(error) && attempt < maxRetries) {
        const delay = Math.pow(2, attempt) * 1000 // Exponential backoff
        log(`⚠️  ${model} attempt ${attempt} failed, retrying in ${delay}ms...`)
        await sleep(delay)
        continue
      }
      
      // Permanent error or max retries reached
      throw error
    }
  }
  
  throw lastError
}

function isTransientError(error) {
  const transientPatterns = [
    /timeout/i,
    /rate limit/i,
    /network/i,
    /503/,
    /429/,
    /connection/i
  ]
  
  return transientPatterns.some(pattern => pattern.test(error.message))
}
```

---

## Learning Patterns

### Learning System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      LEARNING SYSTEM                             │
└─────────────────────────────────────────────────────────────────┘

CONTINUOUS LEARNING LOOP
────────────────────────

    ┌──────────────────────────────────────────┐
    │  1. EXECUTION                            │
    │  • Workflows run                         │
    │  • Decisions made                        │
    │  • Results produced                      │
    └────────────┬─────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────┐
    │  2. OBSERVATION                          │
    │  • What worked?                          │
    │  • What failed?                          │
    │  • Which models performed best?          │
    │  • What patterns emerged?                │
    └────────────┬─────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────┐
    │  3. EXTRACTION                           │
    │  • Extract patterns                      │
    │  • Identify learnings                    │
    │  • Measure performance                   │
    │  • Collect attribution                   │
    └────────────┬─────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────┐
    │  4. STORAGE                              │
    │  • SQLite database (structured)          │
    │  • Markdown files (human-readable)       │
    │  • Vector embeddings (RAG search)        │
    └────────────┬─────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────┐
    │  5. RETRIEVAL                            │
    │  • Query similar situations              │
    │  • Load relevant context                 │
    │  • Apply learned patterns                │
    └────────────┬─────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────┐
    │  6. APPLICATION                          │
    │  • Adjust strategies                     │
    │  • Select better models                  │
    │  • Optimize resource allocation          │
    │  • Improve decision quality              │
    └────────────┬─────────────────────────────┘
                 │
                 └──────────────┐
                                │
                ┌───────────────┘
                │
                ▼
    ┌──────────────────────────────────────────┐
    │  BACK TO EXECUTION (improved)            │
    └──────────────────────────────────────────┘


LEARNING STORAGE STRUCTURE
───────────────────────────

/home/sfloess/.claude/learning/
├── MEMORY.md (main index)
├── feedback_*.md (user preferences)
├── project_*.md (project-specific learnings)
├── reference_*.md (technical references)
├── learnings/ (auto-extracted patterns)
│   ├── arbiter-worker-pattern.md
│   ├── code-review-may-2026.md
│   └── ...
└── db/
    ├── performance.db (SQLite)
    │   ├── model_performance table
    │   ├── workflow_execution table
    │   ├── decision_quality table
    │   └── resource_usage table
    └── embeddings.db (vector store)


MODEL PERFORMANCE TRACKING
──────────────────────────

For each model execution, track:

┌──────────────────────────────────────────────────────────────┐
│ Model: Opus                                                  │
│ Task: Bug finding                                            │
│ Timestamp: 2026-06-13 14:32:15                              │
│                                                              │
│ Performance Metrics:                                         │
│ • Execution time: 45.2s                                      │
│ • Token usage: 15,234 tokens                                 │
│ • Cost: $0.23                                                │
│ • Success: ✓                                                 │
│ • Confidence: 85%                                            │
│                                                              │
│ Quality Metrics:                                             │
│ • Bugs found: 3                                              │
│ • False positives: 0                                         │
│ • Severity: 2 high, 1 medium                                 │
│ • Arbiter selected: Yes (chosen as best)                     │
│ • Consensus approval: 5/5 arbiters approved                  │
│                                                              │
│ Context:                                                     │
│ • File type: JavaScript                                      │
│ • File size: 1,234 lines                                     │
│ • Complexity: High                                           │
│ • Domain: Web backend                                        │
└──────────────────────────────────────────────────────────────┘

Storage: SQLite table `model_performance`

INSERT INTO model_performance (
  model, task_type, timestamp,
  execution_time_ms, tokens, cost,
  success, confidence,
  quality_metrics, context
) VALUES (
  'opus', 'bug-finding', '2026-06-13 14:32:15',
  45200, 15234, 0.23,
  1, 85,
  '{"bugs_found": 3, "false_positives": 0, ...}',
  '{"file_type": "javascript", ...}'
)


PATTERN EXTRACTION
──────────────────

After N executions (N = 10), extract patterns:

Example: "Opus excels at finding security bugs in JavaScript"

Evidence:
• 10 executions on JavaScript files
• 8/10 times Opus found critical security issues
• 6/10 times Opus solution selected by arbiter
• 0 false positives in security category
• Average confidence: 87%

Action: Increase Opus priority for security reviews in JS files

Storage: learnings/opus-javascript-security.md


ACTIVE LEARNING
───────────────

Identify gaps in model coverage:

┌──────────────────────────────────────────────┐
│ Task: Review Python async/await code         │
│                                              │
│ Historical Performance:                      │
│ • Opus: 70% accuracy                         │
│ • Sonnet: 65% accuracy                       │
│ • Haiku: 60% accuracy                        │
│                                              │
│ Gap Detected: All models struggle with       │
│               Python async patterns          │
│                                              │
│ Learning Action:                             │
│ 1. Generate training examples                │
│ 2. Add to prompt context                     │
│ 3. Test improvement                          │
│ 4. Measure new accuracy                      │
└──────────────────────────────────────────────┘


META-LEARNING
─────────────

Learn about learning itself:

Observation:
"When we add code examples to prompts for Haiku,
 accuracy improves by 15% on average"

Meta-Pattern:
"Haiku benefits more from few-shot examples than Opus"

Application:
• Automatically include 2-3 examples in Haiku prompts
• Opus can work with zero-shot
• Store in meta-learning table

Result:
• Haiku performance improved
• Token usage optimized (fewer retries)
• Cost reduced
```

### Learning File Format

```markdown
---
name: pattern-name
description: Brief description
metadata:
  node_type: memory
  type: feedback|project|reference|learning
  originSessionId: session-id
---

# Pattern Name

**Concept**: What this pattern achieves

**Why**: Why this pattern matters

**How to apply**: When and where to use it

## Core Pattern

[Detailed explanation with code examples]

## Examples

[Real-world examples]

## Related Memories

- [[other-pattern-1]]
- [[other-pattern-2]]

---

**Status**: Production|Experimental|Deprecated
**Date**: YYYY-MM-DD
**Applications**: Where this pattern applies
```

---

## Coordination Strategies

### Strategy 1: QualityFirst (Default)

Maximum model coverage, quality over cost.

```
Configuration:
• Workers: 6 models (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)
• Arbiter: Fable (rotates)
• Consensus threshold: 80%
• Max iterations: 10
• Fleet distribution: Enabled

Cost: $$$$$ (highest)
Quality: ⭐⭐⭐⭐⭐ (highest)
Speed: Moderate (parallel execution helps)

Use when:
• Critical decisions
• High-risk changes
• Security reviews
• Production code
```

### Strategy 2: CostOptimized

Minimize cost while maintaining quality.

```
Configuration:
• Workers: 3 models (Sonnet, Haiku, Gemini)
• Arbiter: Sonnet
• Consensus threshold: 66%
• Max iterations: 5
• Fleet distribution: Optional

Cost: $$ (low)
Quality: ⭐⭐⭐ (good)
Speed: Fast (fewer workers)

Use when:
• Non-critical changes
• Exploratory work
• Documentation
• Low-risk tasks
```

### Strategy 3: Balanced

Balance cost, quality, and speed.

```
Configuration:
• Workers: 4 models (Fable, Opus, Sonnet, Haiku)
• Arbiter: Opus (rotates with Fable)
• Consensus threshold: 75%
• Max iterations: 7
• Fleet distribution: Enabled

Cost: $$$ (moderate)
Quality: ⭐⭐⭐⭐ (high)
Speed: Good (parallel + moderate count)

Use when:
• Normal development work
• Code reviews
• Refactoring
• Testing
```

### Strategy 4: Quantized (Local Models)

Use local Ollama models, zero API cost.

```
Configuration:
• Workers: 4+ models (qwen2.5-coder, deepseek-r1, starcoder2, codestral)
• Arbiter: deepseek-r1
• Consensus threshold: 75%
• Max iterations: 10
• Fleet distribution: Required (models run on laptop-01 Ollama server)

Cost: $ (zero API, only compute)
Quality: ⭐⭐⭐⭐ (very good, approaching Claude)
Speed: Depends on fleet (can be very fast with proper distribution)

Use when:
• Cost-sensitive work
• High-volume tasks
• Experimentation
• Private/sensitive code
```

---

## Examples

### Example 1: Code Review with Multi-AI Consensus

```javascript
// /workflows/code-review-multi-ai.js

export const meta = {
  name: 'code-review-multi-ai',
  description: 'Multi-model code review with arbiter consensus',
  phases: [
    { title: 'Discovery', detail: 'Find changed files' },
    { title: 'Review', detail: 'Multi-model bug finding', model: 'fable' },
    { title: 'Synthesis', detail: 'Arbiter selects findings' },
    { title: 'Validation', detail: 'Consensus check' },
  ],
}

// PHASE 1: Discovery
phase('Discovery')

const diff = await bash('git diff HEAD')
const files = parseDiffFiles(diff)

log(`Found ${files.length} changed files`)

// PHASE 2: Review (Multi-Model Workers)
phase('Review')

const WORKER_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const REVIEW_ARBITER = 'fable'

log(`🔄 ${WORKER_MODELS.length} workers reviewing in parallel...`)

const reviewSchema = {
  type: 'object',
  properties: {
    model: { type: 'string' },
    bugs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          description: { type: 'string' },
          recommendation: { type: 'string' }
        }
      }
    },
    confidence: { type: 'number' }
  }
}

const reviews = await parallel(WORKER_MODELS.map(model =>
  () => agent(`Review this code for bugs, security issues, and improvements:

${diff}

Find all issues, categorize by severity.`, {
    label: `${model} Review`,
    model: model,
    schema: reviewSchema
  })
))

const successCount = reviews.filter(Boolean).length
log(`✅ Received ${successCount}/${WORKER_MODELS.length} reviews`)

// Aggregate all bugs found
const allBugs = reviews.flatMap((review, idx) => {
  if (!review) return []
  return review.bugs.map(bug => ({
    ...bug,
    found_by: WORKER_MODELS[idx],
    confidence: review.confidence
  }))
})

log(`Total bugs found: ${allBugs.length}`)

// PHASE 3: Arbiter Synthesis
phase('Synthesis')

const arbiterSchema = {
  type: 'object',
  properties: {
    selected_bugs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          severity: { type: 'string' },
          description: { type: 'string' },
          recommendation: { type: 'string' },
          found_by: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'number' }
        }
      }
    },
    reasoning: { type: 'string' },
    false_positives: {
      type: 'array',
      items: { type: 'string' }
    }
  }
}

log(`🧠 Arbiter (${REVIEW_ARBITER}) synthesizing findings...`)

const synthesis = await agent(`You are an arbiter reviewing ${reviews.length} code reviews.

Each review found bugs. Your job:
1. Identify real bugs (exclude false positives)
2. Merge duplicates (same bug found by multiple models)
3. Prioritize by severity
4. Provide clear, actionable recommendations

Reviews:
${JSON.stringify(reviews, null, 2)}

Return deduplicated, validated bugs only.`, {
  model: REVIEW_ARBITER,
  schema: arbiterSchema
})

log(`Arbiter selected ${synthesis.selected_bugs.length} real bugs`)
log(`False positives filtered: ${synthesis.false_positives.length}`)

// PHASE 4: Validation (Role Swap)
phase('Validation')

// Former arbiter becomes skeptical worker
const skepticModel = REVIEW_ARBITER
// Other workers become arbiters
const validatorModels = WORKER_MODELS.filter(m => m !== REVIEW_ARBITER)

log(`🔍 ${skepticModel} performing skeptical review...`)

const skepticReview = await agent(`Review these bugs skeptically. Are they real?

${JSON.stringify(synthesis.selected_bugs, null, 2)}

For each bug, confirm it's legitimate or mark as false positive.`, {
  model: skepticModel,
  schema: {
    type: 'object',
    properties: {
      approved: { type: 'boolean' },
      concerns: { type: 'array', items: { type: 'string' } },
      confidence: { type: 'number' }
    }
  }
})

log(`Skeptic review: ${skepticReview.approved ? '✅ APPROVED' : '⚠️ CONCERNS'}`)

if (skepticReview.approved) {
  log('')
  log('=' .repeat(60))
  log('🎉 CODE REVIEW COMPLETE')
  log('='.repeat(60))
  log(`Bugs found: ${synthesis.selected_bugs.length}`)
  synthesis.selected_bugs.forEach(bug => {
    log(`\n${bug.severity.toUpperCase()}: ${bug.file}:${bug.line}`)
    log(`  ${bug.description}`)
    log(`  Recommendation: ${bug.recommendation}`)
    log(`  Found by: ${bug.found_by.join(', ')}`)
  })
  log('='.repeat(60))
}

return {
  status: 'success',
  bugs: synthesis.selected_bugs,
  false_positives: synthesis.false_positives,
  attribution: {
    workers: reviews.map((r, idx) => ({
      model: WORKER_MODELS[idx],
      bugs_found: r?.bugs.length || 0,
      confidence: r?.confidence || 0
    })),
    arbiter: {
      model: REVIEW_ARBITER,
      selected: synthesis.selected_bugs.length,
      filtered: synthesis.false_positives.length
    },
    validator: {
      model: skepticModel,
      approved: skepticReview.approved,
      concerns: skepticReview.concerns
    }
  }
}
```

**Execution Timeline:**

```
Time    Phase           Activity                           Models
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0:00    Discovery       Git diff, parse files              -
0:02    Review          6 workers analyze in parallel      Fable, Opus, Sonnet,
                        (distributed across fleet)         Haiku, GPT-4o, Gemini
0:45    Review          Workers complete                   -
0:45    Synthesis       Arbiter deduplicates & validates   Fable
0:55    Validation      Role swap: skeptical review        Fable (as skeptic)
1:00    Complete        Return results                     -

Total: 60 seconds
Workers: 6 models
Fleet machines: 3 (server-01, server-02, server-03)
Bugs found: 7
False positives: 2
Final bugs: 5
```

---

### Example 2: Fleet-Distributed Learning

```javascript
// /workflows/ai-web-learn-fleet.js

export const meta = {
  name: 'ai-web-learn-fleet',
  description: 'Web research with fleet-distributed learning',
  phases: [
    { title: 'Fleet Discovery', detail: 'Find available workers' },
    { title: 'Web Research', detail: 'Parallel source gathering' },
    { title: 'Multi-Model Learning', detail: 'Extract insights' },
    { title: 'Synthesis', detail: 'Combine knowledge' },
  ],
}

const query = args?.join(' ') || 'Latest React patterns 2026'

// PHASE 1: Fleet Discovery
phase('Fleet Discovery')

const workers = await getFleetWorkers(args, { skipHealthCheck: false })
const useFleet = workers.length > 0

log(`Fleet: ${useFleet ? `✅ ${workers.length} workers` : '⚠️  local only'}`)

// PHASE 2: Web Research
phase('Web Research')

log('🔍 Searching web sources...')

const sources = [
  'https://react.dev',
  'https://stackoverflow.com',
  'https://github.com/trending',
  'https://dev.to',
  'https://medium.com'
]

const research = await parallel(sources.map(url =>
  () => webFetch(url, `Extract information about: ${query}`)
))

log(`✅ Researched ${research.filter(Boolean).length}/${sources.length} sources`)

// PHASE 3: Multi-Model Learning
phase('Multi-Model Learning')

const MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

// Distribute models across fleet
const distribution = useFleet
  ? distributeModels(MODELS, workers)
  : MODELS.map(model => ({ model, hostname: 'localhost' }))

log('Distribution:')
distribution.forEach(d => log(`  ${d.model} → ${d.hostname}`))

log(`🔄 ${MODELS.length} models learning in parallel...`)

const learningSchema = {
  type: 'object',
  properties: {
    model: { type: 'string' },
    insights: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          concept: { type: 'string' },
          explanation: { type: 'string' },
          examples: { type: 'array', items: { type: 'string' } },
          source: { type: 'string' }
        }
      }
    },
    confidence: { type: 'number' }
  }
}

const learnings = await parallel(MODELS.map((model, idx) =>
  () => agent(`Analyze this research and extract key learnings about: ${query}

Research:
${JSON.stringify(research, null, 2)}

Extract:
• Core concepts
• Best practices
• Examples
• Recommendations`, {
    label: `${model} Learning`,
    model: model,
    schema: learningSchema,
    // Fleet distribution hint
    _fleet_hint: distribution[idx]
  })
))

log(`✅ ${learnings.filter(Boolean).length}/${MODELS.length} models completed`)

// PHASE 4: Synthesis
phase('Synthesis')

const ARBITER = 'fable'

log(`🧠 Arbiter (${ARBITER}) synthesizing knowledge...`)

const synthesisSchema = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    key_concepts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          supported_by: { type: 'array', items: { type: 'string' } }
        }
      }
    },
    best_practices: { type: 'array', items: { type: 'string' } },
    recommendations: { type: 'array', items: { type: 'string' } }
  }
}

const synthesis = await agent(`Synthesize learnings from ${MODELS.length} models.

Find common themes, validate claims, create comprehensive guide.

Learnings:
${JSON.stringify(learnings, null, 2)}`, {
  model: ARBITER,
  schema: synthesisSchema
})

// Store learning
const learningFile = `/home/sfloess/.claude/learning/research/web-learning-${Date.now()}.md`

await write(learningFile, `# Web Learning: ${query}

**Date:** ${new Date().toISOString()}
**Sources:** ${sources.length}
**Models:** ${MODELS.join(', ')}
**Fleet:** ${useFleet ? 'Yes' : 'No'}

## Summary

${synthesis.summary}

## Key Concepts

${synthesis.key_concepts.map(c => `
### ${c.name}

${c.description}

**Supported by:** ${c.supported_by.join(', ')}
`).join('\n')}

## Best Practices

${synthesis.best_practices.map(bp => `- ${bp}`).join('\n')}

## Recommendations

${synthesis.recommendations.map(r => `- ${r}`).join('\n')}

## Attribution

${learnings.map((l, idx) => `
### ${MODELS[idx]}
- Insights: ${l?.insights.length || 0}
- Confidence: ${l?.confidence || 0}%
- Executed on: ${distribution[idx].hostname}
`).join('\n')}
`)

log(`✅ Learning stored: ${learningFile}`)

return {
  status: 'success',
  synthesis,
  learning_file: learningFile,
  fleet_used: useFleet,
  attribution: {
    sources: sources.length,
    models: MODELS,
    distribution
  }
}
```

---

## Summary

The Claude Code multi-agent collaboration model achieves high-quality outcomes through:

1. **Orchestrator-Agent Coordination**
   - Orchestrator delegates to specialized agents
   - Agents work independently, report back
   - Clear separation of concerns

2. **Multi-AI Consensus (Arbiter/Worker)**
   - 6 models by default (maximum coverage)
   - Workers propose, arbiter selects
   - Role swap validation prevents bias
   - Different arbiters for different phases

3. **Fleet Distribution**
   - 5-machine fleet (1 controller, 3 workers, 1 sentinel)
   - Parallel execution across machines
   - Intelligent load balancing
   - Graceful fallback to local

4. **Error Recovery**
   - Transient: Retry with backoff
   - Permanent: Graceful degradation
   - Degraded: Partial success or replacement
   - Fleet-aware recovery

5. **Continuous Learning**
   - Extract patterns from every execution
   - Store in SQLite + markdown + vectors
   - Retrieve relevant context
   - Apply learned optimizations

6. **Coordination Strategies**
   - QualityFirst: Maximum models (default)
   - CostOptimized: Minimal cost
   - Balanced: Cost/quality balance
   - Quantized: Local models (Ollama)

**Result:** Autonomous, self-improving, distributed AI system that produces high-quality code reviews, solutions, and decisions with full transparency and attribution.

---

**Document Version:** 2.0  
**Last Updated:** 2026-06-13  
**Maintained By:** Claude Code Team  
**Status:** Production
