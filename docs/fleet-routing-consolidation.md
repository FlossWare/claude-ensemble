# Fleet Routing Consolidation

**Date:** 2026-06-28 (updated 2026-06-29)
**Status:** Active -- canonical routing architecture documented below

## Overview

This document describes the fleet routing system, how distributed workflows operate, and how agents are distributed across workers. It consolidates three previously competing fleet abstractions into a single canonical architecture.

---

## 1. Fleet Topology

### Node Inventory

The fleet consists of 1 infrastructure orchestrator and 8 API-only workers, all accessed via SSH user `claude`.

| Hostname    | Role          | Architecture | CPU Cores | RAM      | Tier   | Notes                                     |
|-------------|---------------|--------------|-----------|----------|--------|--------------------------------------------|
| aio-01      | Orchestrator  | x86_64       | --        | --       | --     | Infrastructure only (PostgreSQL, OrientDB, Redis, routing). NOT a worker. |
| server-01   | Worker        | x86_64       | 8         | high     | heavy  | API-only, 8 cores, high RAM                |
| server-02   | Worker        | x86_64       | 8         | high     | heavy  | API-only, 8 cores, high RAM                |
| server-03   | Worker        | x86_64       | 8         | high     | heavy  | API-only, 8 cores, high RAM                |
| laptop-01   | Worker + Dev  | x86_64       | 8         | 28 GB    | heavy  | Development node, API keys for paid APIs   |
| pi-01       | Worker        | aarch64      | 4         | 424 MB   | light  | Lightweight tasks only                     |
| pi-02       | Worker        | aarch64      | 4         | 365 MB   | light  | Lightweight tasks only                     |
| desktop-ap  | Worker        | x86_64       | unknown   | unknown  | medium | API-only                                   |
| server-ap   | Worker        | x86_64       | unknown   | unknown  | medium | API-only                                   |

**Total capacity:** 44+ cores across 8 workers.

**Local models:** Dormant (not deleted). The fleet operates in API-only mode -- all LLM inference is performed via API calls, not local model execution.

### Configuration Files

| File | Purpose |
|------|---------|
| `shared/fleet-topology.js` | Single source of truth for node definitions (hostnames, roles, hardware specs) |
| `lib/fleet-api-policy.json` | API provider restrictions per node (free vs paid, allowed models) |
| `~/.claude/fleet.json` | SSH connectivity and node discovery for `shared/fleet-utils.js` |

---

## 2. Routing Architecture

### Canonical Module Stack

The routing system is layered. Higher-level modules delegate to lower-level ones:

```
Workflow Code (deep-research.mjs, ai-consensus.js, etc.)
  |
  v
shared/fleet-workflow-wrapper.mjs     <-- Opt-in fleet-aware workflow context
  |
  +-- shared/workflow-agent-orchestrator.mjs  <-- Round-robin distribution + SSH execution
  |     |
  |     +-- shared/execute-on-worker.js       <-- SSH + base64-encoded Node.js execution
  |     +-- shared/fleet_executor.py          <-- Python executor (stdlib-only, all archs)
  |     +-- shared/execute-via-python.sh      <-- Shell wrapper for Python executor
  |
  +-- shared/fleet-utils.js           <-- CANONICAL: SSH primitives, health checks, compliance
  |     |-- getWorkers()              <-- Discover healthy workers via SSH
  |     |-- remoteExec()              <-- Execute shell commands on remote nodes
  |     |-- getFleet()                <-- Full fleet metadata
  |     |-- probeHealth()             <-- Per-node health checking with caching
  |     |-- resolveFleetMode()        <-- Determine if fleet is available
  |     \-- validateCompliance()      <-- Compliance boundary enforcement
  |
  +-- shared/fleet-topology.js        <-- Static node metadata
  |     |-- FLEET_NODES               <-- Array of node objects
  |     \-- FLEET_CAPACITY            <-- Aggregate capacity summary
  |
  +-- lib/fleet-api-policy.json       <-- API access policy per node
  |
  +-- shared/fleet-orchestrator.js    <-- NEW: Higher-level model routing
  |     |-- selectModel(task)         <-- Intelligent model selection
  |     |-- executeOnModel(model, prompt)  <-- Model execution with auto worker selection
  |     |-- selectWorkerForModel()    <-- Policy-aware worker selection
  |     |-- isModelAvailable()        <-- Model availability check
  |     \-- getFleetInfo()            <-- Fleet summary
  |
  +-- ai-task-router.js               <-- Task classification + model scoring
  |     |-- classifyTask()            <-- Keyword-based task categorization
  |     \-- selectWorkers()           <-- Score and select optimal models for task
  |
  +-- fleet-agent-dispatcher.js       <-- Agent dispatch with job type detection
  |     |-- dispatchViaFleet()        <-- Fleet-aware agent execution
  |     |-- createFleetAgent()        <-- Wrapper that falls back to direct agent()
  |     \-- detectJobType()           <-- Heuristic job classification
  |
  +-- shared/quality-first-routing.cjs  <-- Quality-only routing (no cost weights)
  +-- shared/role-based-routing.cjs     <-- Capability-based model selection
  +-- shared/weighted-voting.cjs        <-- Weighted consensus with cost/quality tradeoffs
  \-- fleet-remote-executor.js          <-- SSH + claude -p execution engine
```

### Deprecated Modules

| File | Status | Reason |
|------|--------|--------|
| `fleet-utils.js` (root) | DEPRECATED | Depends on pi-02:3004 dispatcher HTTP service; duplicates SSH from `shared/fleet-utils.js`; uses non-standard `multi-ai-config.json` |
| `fleet-orchestrator-client.cjs` | DEPRECATED | CJS module; depends on pi-02:8080 brain HTTP service; Ollama auto-detection not needed in API-only architecture |

---

## 3. Task Routing Logic

### Task Classification (ai-task-router.js)

Tasks are classified along two dimensions:

**Category** (detected by keyword matching against task text):

| Category       | Keywords                                                  | Default Complexity |
|----------------|-----------------------------------------------------------|--------------------|
| security       | security, vulnerability, CVE, injection, XSS, auth       | complex            |
| architecture   | architecture, design, pattern, microservice, scalability  | complex            |
| code-review    | review, bug, defect, correctness, lint                    | moderate           |
| refactoring    | refactor, simplify, clean, extract, rename                | moderate           |
| testing        | test, spec, coverage, unit test, integration test, e2e    | moderate           |
| documentation  | document, readme, jsdoc, docstring, comment               | simple             |
| logic          | logic, algorithm, optimize, performance, concurrent       | complex            |
| synthesis      | synthesize, combine, merge, consensus, arbiter            | complex            |
| general        | (fallback)                                                | moderate           |

**Complexity** (overridden by heuristics):
- `simple` -- trivial tasks, formatting, renaming
- `moderate` -- standard development tasks
- `complex` -- security, architecture, distributed systems
- `critical` -- production incidents, multiple complexity signals

### Model Selection Scoring

Each candidate model is scored on a 0-100+ point scale:

| Factor                 | Points   | Description                                       |
|------------------------|----------|---------------------------------------------------|
| Specialization match   | 0-40     | Does the model specialize in this task category?  |
| Complexity fit         | 0-30     | Is the model's tier appropriate for complexity?   |
| Quality score          | 0-20     | Base quality rating of the model                  |
| Preference adjustment  | -10 to +25 | User preference for quality/speed/cost          |
| Historical performance | 0-20     | Thompson Sampling performance data                |

### Model Configuration

| Model   | Provider  | Tier     | Relative Cost | Specializations                                          |
|---------|-----------|----------|---------------|----------------------------------------------------------|
| opus    | Anthropic | flagship | 1.00          | security, architecture, logic, synthesis, complex-reasoning |
| sonnet  | Anthropic | mid      | 0.20          | code-review, refactoring, documentation, testing, general |
| haiku   | Anthropic | fast     | 0.04          | formatting, classification, extraction, simple-qa         |
| gemini  | Google    | mid      | 0.05          | general, summarization, extraction, multimodal            |

### Quality-First vs Cost-Aware Routing

Two routing strategies are available:

**Quality-First** (`shared/quality-first-routing.cjs`):
- Formula: `weight = capability x confidence x history x calibration`
- No cost multiplier -- free API models treated equally with paid models
- Use for critical tasks, research workflows, maximum accuracy

**Weighted Voting** (`shared/weighted-voting.cjs`):
- Includes cost multiplier in weight calculation
- Balances quality against API cost
- Use for routine tasks where cost matters

### API Provider Policy

From `lib/fleet-api-policy.json`:

**Free APIs** (available on all 8 workers, 445+ models across 21 providers):
- OpenRouter (150+ free models)
- Groq (llama-3.3-70b, mixtral-8x7b) -- 30 req/min
- Cerebras (fast inference)
- DeepSeek (deepseek-chat, deepseek-coder)
- Pollinations (no auth required)
- ZeroLimitAI, Eden AI, GitHub Models
- DeepInfra, HuggingFace, Mistral, Cohere, Cloudflare, Jina
- And additional specialized providers

**Paid APIs** (restricted to laptop-01 only):
- Anthropic (claude-opus-4, claude-sonnet-4.5, claude-haiku-4)
- Google (gemini-2.0-flash-exp, gemini-1.5-pro)

---

## 4. Distributed Workflow Execution

### Execution Flow

1. **Workflow starts** on orchestrator (aio-01 or laptop-01)
2. **Fleet wrapper** (`fleet-workflow-wrapper.mjs`) intercepts `agent()` and `parallel()` calls
3. **Worker selection** via round-robin load balancing with per-worker active-task tracking
4. **SSH transport** to selected worker: `ssh -o BatchMode=yes claude@<worker> ...`
5. **Remote execution** via one of two paths:
   - **Node.js path** (`execute-on-worker.js`): Base64-encodes a Node.js script, SSHes to worker, decodes and runs
   - **Python path** (`fleet_executor.py`): stdlib-only Python script, works on all architectures including aarch64 Pi nodes
6. **Result collection** via stdout JSON parsing
7. **Fallback** to local execution if all workers fail

### SSH Security Model

- `BatchMode=yes` -- prevents password prompt hangs
- `StrictHostKeyChecking=accept-new` -- prevents MITM on first connect
- Hostname validation: `/^[a-zA-Z0-9._-]+$/` (same pattern in fleet-utils.js and execute-on-worker.js)
- Task content base64-encoded -- never touches shell parsing
- API keys base64-encoded during SSH transport, decoded on the remote side
- Temp scripts cleaned up even on failure

### Distribution Patterns

**Round-Robin** (default in `fleet-workflow-wrapper.mjs` and `workflow-agent-orchestrator.mjs`):
```
Task 1 -> server-01
Task 2 -> server-02
Task 3 -> server-03
Task 4 -> laptop-01
Task 5 -> pi-01
Task 6 -> pi-02
Task 7 -> desktop-ap
Task 8 -> server-ap
Task 9 -> server-01  (wraps around)
```

**Weighted by Memory** (`fleet-workflow-patterns.js`):
- Workers with more RAM receive proportionally more items
- Heavy-tier workers (server-01/02/03, laptop-01) get the bulk of work

**Item Distribution** (`fleet-workflow-patterns.js`):
- `distributeItems(items, workers)` -- round-robin assignment
- `distributeItemsWeighted(items, workers)` -- memory-weighted assignment

### Error Handling Strategy

| Condition | Action |
|-----------|--------|
| 1 worker fails | Continue with remaining workers, log warning |
| 2+ workers fail | Abort fleet mode, retry entire workload locally |
| SSH connection refused | Error with diagnostic: `Ensure: ssh claude@<worker> echo OK` |
| SSH timeout | Error indicating worker may be overloaded or unreachable |
| Empty stdout | Error with stderr contents |
| Invalid JSON output | Error with first 500 chars of stdout and stderr |

### NFS Coordination

- Unique temp dirs per worker: `/tmp/fleet-<skill>-<worker>-<timestamp>`
- No lock files needed (NFS read-only for source, workers write to local /tmp)
- Large prompts (>4KB) written to NFS shared file, read by remote worker
- Results collected via SSH stdout after completion

---

## 5. Agent Distribution in Workflows

### Workflow Wrapper API

```javascript
import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, parallel, phase, complete } = createFleetWorkflow(
    'workflow-name',
    'task description',
    { enableFleet: true, enableStorage: true, enableDistributed: true }
  );

  // Single agent call -- automatically routed to next available worker
  const result = await agent('Analyze this code', { model: 'claude-opus-4' });

  // Parallel calls -- distributed across all 8 workers automatically
  const results = await parallel([
    { model: 'gpt-4o-mini', task: 'Analyze aspect A' },
    { model: 'gpt-4o-mini', task: 'Analyze aspect B' },
    { model: 'gpt-4o-mini', task: 'Analyze aspect C' },
  ]);

  return complete(result, 0.85);
}
```

### Orchestrator API

```javascript
import { createOrchestrator } from '../shared/workflow-agent-orchestrator.mjs';

const orch = createOrchestrator();

// Single agent call
const result = await orch.agent({ model: 'gpt-4o-mini', task: 'Summarize X' });

// Parallel agent calls
const results = await orch.parallel([
  { model: 'gpt-4o-mini', task: 'Analyze aspect A' },
  { model: 'gpt-4o-mini', task: 'Analyze aspect B' },
]);

// Worker statistics
const stats = orch.getStats();
```

### Fleet Agent Dispatcher

For wrapping existing `agent()` calls with fleet dispatch and automatic fallback:

```javascript
import { createFleetAgent } from './fleet-agent-dispatcher.js';

// Create fleet-aware agent wrapper
const fleetAgent = createFleetAgent(USE_FLEET_DISPATCHER, originalAgentFn);

// Same API as agent(), but fleet-distributed with fallback
const result = await fleetAgent(prompt, { model: 'opus', schema, label });
```

### Job Type Classification

The dispatcher (`fleet-agent-dispatcher.js`) classifies agent calls into 5 job types for resource estimation:

| Job Type         | Detection Signals                                          | Duration Adj. | RAM Adj. |
|------------------|------------------------------------------------------------|---------------|----------|
| ai-consensus     | worker, consensus, opinion, perspective, arbiter           | baseline      | baseline |
| code-review      | review, audit, quality, complexity, refactor               | baseline      | baseline |
| code-execute     | test, build, execute, run, verify, npm test, pytest        | +20s          | +0.5 GB  |
| data-extraction  | extract, fetch, parse, detect, scan, JSON                  | -10s          | -0.3 GB  |
| ai-heavy         | synthesis, summary, generate, document, report             | +15s          | +0.3 GB  |

### Resource Estimation

Resource estimates are computed from prompt length, model tier, schema complexity, and job type:

| Factor           | Small           | Medium          | Large           |
|------------------|-----------------|-----------------|-----------------|
| Prompt length    | <500 chars: +10s | 500-5K chars: +20-30s | >5K chars: +45s |
| Model tier       | haiku: -10s     | sonnet/gemini: +5s | opus/gpt-4: +15s |
| Schema props     | 1-5 props: +5s  | 5-20 props: +10s | 20+ props: +15s |

---

## 6. Consolidation: Migration from Deprecated Modules

### API Mapping: Root fleet-utils.js to fleet-orchestrator.js

| Old API | New API | Notes |
|---------|---------|-------|
| `selectWorker(jobType)` | `selectModel({ type })` | Returns `{ model, provider }` instead of hostname |
| `selectServerForModel(model)` | `selectWorkerForModel(model, provider)` | Respects API policy constraints |
| `remoteAgent(server, prompt, opts)` | `executeOnModel(model, prompt, opts)` | Auto-selects worker |
| `distributeAgents(prompts, strategy)` | Use `parallel()` with `executeOnModel()` | Workflow `parallel()` preferred |
| `dispatchAgent(model, prompt, opts)` | `executeOnModel(model, prompt)` | No HTTP dispatcher dependency |
| `getFleetTopology()` | `getFleetInfo()` | Structured topology from policy + topology files |
| `loadFleetConfig()` | `loadApiPolicy()` | Reads `fleet-api-policy.json` instead of `multi-ai-config.json` |

### API Mapping: fleet-orchestrator-client.cjs to fleet-orchestrator.js

| Old API | New API | Notes |
|---------|---------|-------|
| `routeRequest(capability)` | `selectModel({ type: capability })` | Purely local, no HTTP call |
| `getModels()` | `getFleetInfo().freeApis` / `.paidApis` | From policy file |
| `getNodes()` | `getWorkers()` | SSH-based discovery |
| `registerNode()` | N/A | Not needed in API-only architecture |
| `sendHeartbeat()` | N/A | Use `probeHealth()` for ad-hoc checks |

### Import Migration

```javascript
// BEFORE (root fleet-utils.js -- DEPRECATED)
import { selectWorker, remoteAgent, distributeAgents } from './fleet-utils.js';

// AFTER
import { selectModel, executeOnModel, getWorkers } from './shared/fleet-orchestrator.js';
```

```javascript
// BEFORE (fleet-orchestrator-client.cjs -- DEPRECATED)
const FleetOrchestratorClient = require('./fleet-orchestrator-client.cjs');
const client = new FleetOrchestratorClient();
const route = await client.routeRequest('coding');

// AFTER
import { selectModel } from './shared/fleet-orchestrator.js';
const route = selectModel({ type: 'code', complexity: 'high' });
```

---

## 7. Monitoring and Storage

### PostgreSQL Workflow Storage

Workflow executions are tracked in PostgreSQL (`learning` database on aio-01):

| Table | Purpose |
|-------|---------|
| `workflow.executions` | Workflow metadata (name, task, duration, outcome) |
| `workflow.worker_results` | Per-worker output (model, confidence, tokens, cost) |
| `workflow.arbiter_decisions` | Arbiter synthesis results |
| `workflow.phases` | Phase tracking (search, analyze, synthesize, etc.) |
| `workflow.feedback` | Quality feedback |
| `workflow.learnings` | Extracted learnings with importance scores |

### Materialized Views (auto-refresh every 5 min)

```sql
SELECT * FROM workflow.workflow_summary;   -- Aggregated workflow stats
SELECT * FROM workflow.model_performance;  -- Per-model metrics
SELECT * FROM workflow.cost_analysis;      -- Cost breakdowns
```

### Worker Execution Stats

The workflow wrapper tracks per-worker execution counts and can report distribution statistics via `getExecutionStats()`.

---

## 8. Key Design Decisions

1. **API-only architecture:** All 8 workers make API calls to external providers. Local models (Ollama, llama.cpp) are dormant, not deleted, and can be re-enabled if needed.

2. **SSH as transport:** All inter-node communication uses SSH with `BatchMode=yes`. No HTTP services required on workers. This eliminates service management complexity.

3. **Base64 encoding for safety:** All task content and API keys are base64-encoded during SSH transport, preventing shell injection and quoting issues.

4. **Python executor for universality:** `fleet_executor.py` uses only Python stdlib, ensuring it works on all architectures including aarch64 Raspberry Pi nodes.

5. **Round-robin as default:** Simple round-robin distributes load evenly. Weighted distribution (by memory) is available for heterogeneous workloads.

6. **Graceful fallback:** If fleet execution fails, workflows fall back to local execution automatically. One worker failure does not abort the workflow.

7. **Paid API restriction:** Anthropic, OpenAI, and Google paid APIs are restricted to laptop-01 only. All workers can use free-tier APIs (Groq, DeepInfra, Together, etc.).
