# API Reference

**Version**: 12 | **Last Updated**: 2026-06-13 | **Status**: Production Ready

Complete API documentation for all shared libraries, workflow APIs, configuration schemas, and JSON Schema definitions in Claude Global Skills.

---

## Table of Contents

- [Workflow API](#workflow-api)
  - [Core Workflow Functions](#core-workflow-functions)
  - [Workflow Registration](#workflow-registration)
  - [Args Parsing Pattern](#args-parsing-pattern)
- [Fleet Utilities API](#fleet-utilities-api)
  - [fleet-utils.js](#fleet-utilsjs)
  - [fleet-multisession.js](#fleet-multisessionjs)
  - [fleet-bulk-orchestration.js](#fleet-bulk-orchestrationjs)
  - [fleet-workflow-patterns.js](#fleet-workflow-patternsjs)
  - [fleet-integration.js](#fleet-integrationjs)
- [Consensus API](#consensus-api)
  - [consensus-strategies.js](#consensus-strategiesjs)
  - [consensus-engine.js](#consensus-enginejs)
  - [smart-consensus.js](#smart-consensusjs)
- [Attribution API](#attribution-api)
  - [AttributionTracker Class](#attributiontracker-class)
- [Analysis APIs](#analysis-apis)
  - [impact-analysis.js](#impact-analysisjs)
  - [quality-scorer.js](#quality-scorerjs)
  - [code-ast-analysis.js](#code-ast-analysisjs)
- [Knowledge and Memory APIs](#knowledge-and-memory-apis)
  - [RAG Pipeline (rag.py)](#rag-pipeline-ragpy)
  - [Semantic Search (semantic-search.py)](#semantic-search-semantic-searchpy)
  - [Vector Store (vector-store.py)](#vector-store-vector-storepy)
  - [Learning System (learning-system.js)](#learning-system-learning-systemjs)
- [Platform and Model APIs](#platform-and-model-apis)
  - [platform-detector.js](#platform-detectorjs)
  - [model-detection.js](#model-detectionjs)
  - [model-performance.js](#model-performancejs)
- [Utility APIs](#utility-apis)
  - [chunking-utils.js](#chunking-utilsjs)
  - [clustering-utils.js](#clustering-utilsjs)
  - [issue-operations.js](#issue-operationsjs)
  - [loop-controller.js](#loop-controllerjs)
  - [schemas.js](#schemasjs)
  - [workflow-helpers.js](#workflow-helpersjs)
- [Configuration Schemas](#configuration-schemas)
  - [fleet.json Schema](#fleetjson-schema)
  - [multi-ai-config.json Schema](#multi-ai-configjson-schema)
  - [JSON Schema Definitions](#json-schema-definitions)
- [Shell APIs](#shell-apis)
  - [fleet-bulk-lib.sh](#fleet-bulk-libsh)
  - [skill-helpers.sh](#skill-helperssh)
  - [visual-indicators.sh](#visual-indicatorssh)
- [Cross-References](#cross-references)

---

## Workflow API

### Core Workflow Functions

These functions are provided by the Claude Code workflow runtime and are available globally in all `.js` workflow files.

#### `phase(name)`

Declares a new workflow phase. Used for organization and progress tracking.

```javascript
phase('Analysis')
// All subsequent code runs in the "Analysis" phase
```

**Parameters**:
- `name` (string): Phase name displayed in progress output

**Returns**: void

---

#### `log(message)`

Logs a message to workflow output. Visible in Claude Code's progress display.

```javascript
log('Processing 42 files...')
log(`Workers completed: ${validWorkers.length}/6`)
```

**Parameters**:
- `message` (string): Message to log

**Returns**: void

---

#### `agent(prompt, options?)`

Spawns a subagent to execute a prompt. The primary mechanism for invoking AI models.

```javascript
const result = await agent('Analyze this code for security issues', {
  model: 'opus',
  label: 'opus-security',
  schema: {
    type: 'object',
    properties: {
      findings: { type: 'array' },
      confidence: { type: 'number' }
    }
  }
})
```

**Parameters**:
- `prompt` (string): The prompt to send to the AI model
- `options` (object, optional):
  - `model` (string): Model to use (`'fable'`, `'opus'`, `'sonnet'`, `'haiku'`, `'gpt-4o'`, `'gemini'`). Default: session's default model.
  - `label` (string): Label for the agent in progress output
  - `schema` (object): JSON Schema for structured output. Forces the model to return JSON matching this schema.
  - `phase` (string): Phase context for the agent

**Returns**: Promise resolving to the model's response. If `schema` is provided, returns a parsed JSON object. If the model fails, may return `null`.

**Important notes**:
- Subagents can read files (via the Read tool), run shell commands, and perform other tool operations
- Workflows cannot use `fs`, `require`, or other Node.js built-ins directly -- use `agent()` to delegate file operations
- Failed agents return `null` -- always use `.filter(Boolean)` on parallel results

---

#### `parallel(thunks)`

Executes multiple agent calls concurrently within the same session.

```javascript
const results = await parallel([
  () => agent('Analyze for bugs', { model: 'opus', schema }),
  () => agent('Analyze for bugs', { model: 'sonnet', schema }),
  () => agent('Analyze for bugs', { model: 'haiku', schema }),
])
// results is an array of 3 responses (some may be null)
```

**Parameters**:
- `thunks` (Array<() => Promise>): Array of zero-argument functions that return promises. Each function is called concurrently.

**Returns**: Promise<Array> resolving to an array of results. Failed thunks produce `null` entries.

**Semantics**: Runs all thunks concurrently (not sequentially). Use `pipeline()` for sequential execution with ordering guarantees.

**Critical note**: `parallel()` means concurrent execution. `pipeline()` means sequential execution. This is the opposite of what the names might suggest in some contexts. See memory note: `feedback_workflow_parallel_vs_pipeline.md`.

---

#### `pipeline(thunks)`

Executes multiple agent calls sequentially, in order.

```javascript
const results = await pipeline([
  () => agent('Step 1: gather data', { schema: step1Schema }),
  () => agent('Step 2: analyze data', { schema: step2Schema }),
  () => agent('Step 3: generate report', { schema: step3Schema }),
])
```

**Parameters**:
- `thunks` (Array<() => Promise>): Array of zero-argument functions executed sequentially

**Returns**: Promise<Array> resolving to an array of results in order

---

### Workflow Registration

Every workflow file must begin with an `export const meta` block:

```javascript
export const meta = {
  name: 'my-workflow',
  description: 'What this workflow does',
  version: '1.0',
}
```

**Requirements**:
- Must be the first meaningful statement (line 1-4)
- Must use `export const meta` (not `module.exports`)
- The `name` field determines how the workflow is invoked

### Args Parsing Pattern

Standard pattern for handling both string and object arguments:

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

---

## Fleet Utilities API

### fleet-utils.js

**Location**: `shared/fleet-utils.js`
**Import**: `import { loadFleetConfig, validateCompliance, probeHealth, getFleet, getWorkers, getController, remoteExec, resolveFleetMode, clearHealthCache } from './shared/fleet-utils.js'`

---

#### `loadFleetConfig()`

Loads fleet configuration from `~/.claude/fleet.json`.

```javascript
const config = loadFleetConfig()
console.log(config.machines)  // Array of machine definitions
```

**Returns**: Object -- Parsed fleet configuration

**Throws**: Error if file not found or invalid JSON

---

#### `validateCompliance(config)`

Checks if the current working directory is under a forbidden path.

```javascript
validateCompliance(config)  // Throws if in forbidden path
```

**Parameters**:
- `config` (Object): Fleet configuration with `compliance.forbidden_paths`

**Throws**: Error with `COMPLIANCE VIOLATION` message if current directory violates compliance rules. Uses `fs.realpathSync()` to prevent symlink bypasses.

---

#### `probeHealth(hostname, timeoutMs?)`

Probes a machine's health via SSH.

```javascript
const isHealthy = probeHealth('server-01', 2000)
```

**Parameters**:
- `hostname` (string): Machine hostname (validated against `[a-zA-Z0-9._-]+`)
- `timeoutMs` (number, optional): Timeout in milliseconds. Default: 2000

**Returns**: boolean -- `true` if machine responds within timeout

**Notes**: Results are cached for 30 seconds to avoid repeated probes.

---

#### `getFleet(options?)`

Returns all fleet machines, optionally filtered.

```javascript
const allMachines = getFleet()
const workers = getFleet({ role: 'worker' })
const highMem = getFleet({ minMemoryGb: 32 })
```

**Parameters**:
- `options` (Object, optional):
  - `role` (string): Filter by role (`'worker'`, `'controller'`, `'sentinel'`)
  - `minMemoryGb` (number): Minimum memory threshold
  - `capabilities` (Array<string>): Required capabilities

**Returns**: Array of machine objects

---

#### `getWorkers(options?)`

Returns fleet worker machines only (shorthand for `getFleet({ role: 'worker' })`).

```javascript
const workers = getWorkers()
const dockerWorkers = getWorkers({ capabilities: ['docker'] })
```

**Parameters**: Same as `getFleet()`

**Returns**: Array of worker machine objects, sorted by priority

---

#### `getController()`

Returns the controller machine.

```javascript
const controller = getController()
console.log(controller.hostname)  // 'aio-01'
```

**Returns**: Machine object with `role: 'controller'`

---

#### `remoteExec(hostname, command, options?)`

Executes a command on a remote machine via SSH.

```javascript
const output = remoteExec('server-01', 'echo "Hello from worker"')
```

**Parameters**:
- `hostname` (string): Target machine (validated for injection prevention)
- `command` (string): Shell command to execute (properly escaped)
- `options` (Object, optional):
  - `timeout` (number): Timeout in milliseconds
  - `stdio` (string): stdio configuration for execSync

**Returns**: string -- Command output (stdout)

**Throws**: Error if command fails or times out

**Security**: Hostnames are validated. Never build SSH commands manually -- always use `remoteExec()`.

---

#### `resolveFleetMode(args, itemCount, breakEvenThreshold)`

Determines whether to use fleet or local processing mode.

```javascript
const decision = resolveFleetMode(['--fleet'], 100, 10)
// { mode: 'fleet', workers: [...], reason: 'Explicit --fleet flag' }

const decision2 = resolveFleetMode([], 5, 10)
// { mode: 'local', workers: [], reason: 'Item count (5) below threshold (10)' }
```

**Parameters**:
- `args` (Array|string): Command-line arguments (checked for `--local`, `--fleet`)
- `itemCount` (number): Number of items to process
- `breakEvenThreshold` (number): Minimum items for fleet to be worthwhile

**Returns**: Object:
- `mode` (string): `'fleet'` or `'local'`
- `workers` (Array): Available worker machines (empty if local mode)
- `reason` (string): Human-readable explanation of the decision

**Decision tree**:
1. `--local` flag -> local mode
2. `--fleet` flag -> fleet mode (throws if fleet unavailable)
3. Auto-detect: fleet available AND itemCount >= threshold -> fleet mode
4. Otherwise -> local mode

---

#### `clearHealthCache()`

Clears the cached health probe results. Useful for testing or when machine availability changes.

```javascript
clearHealthCache()
```

**Returns**: void

---

### fleet-multisession.js

**Location**: `shared/fleet-multisession.js`

#### `splitBatches(items, workerCount)`

Splits items into batches for round-robin distribution.

```javascript
const batches = splitBatches(pdfPaths, 3)
// batches[0] = [pdf1, pdf4, pdf7, ...]
// batches[1] = [pdf2, pdf5, pdf8, ...]
// batches[2] = [pdf3, pdf6, pdf9, ...]
```

**Parameters**:
- `items` (Array): Items to distribute
- `workerCount` (number): Number of workers

**Returns**: Array<Array> -- Array of batches, one per worker

---

#### `splitBatchesWeighted(items, workers)`

Splits items proportionally to worker memory.

```javascript
const batches = splitBatchesWeighted(items, [
  { hostname: 'server-01', memory_gb: 32 },
  { hostname: 'server-02', memory_gb: 64 },
  { hostname: 'server-03', memory_gb: 32 },
])
// server-02 gets 50% of items (64/(32+64+32))
```

**Parameters**:
- `items` (Array): Items to distribute
- `workers` (Array): Worker machine objects with `memory_gb`

**Returns**: Array<Array> -- Weighted batches

---

#### `runMultiSession(workers, batches, command)`

Launches independent Claude Code sessions on workers via SSH.

**Parameters**:
- `workers` (Array): Worker machine objects
- `batches` (Array<Array>): Pre-split batches
- `command` (string|Function): Command template or function generating per-worker commands

**Returns**: Promise<Array> -- Results from each worker

---

#### `mergeMarkdownReports(reports)`

Merges multiple markdown report strings into one.

**Parameters**:
- `reports` (Array<string>): Individual markdown reports

**Returns**: string -- Merged report

---

#### `mergeJsonArrays(arrays)`

Merges multiple JSON arrays into one, with deduplication.

**Parameters**:
- `arrays` (Array<Array>): Individual result arrays

**Returns**: Array -- Merged and deduplicated results

---

#### `mergeAndDeduplicateFindings(findings)`

Merges findings from multiple workers, removing duplicates based on similarity.

**Parameters**:
- `findings` (Array): Combined findings from all workers

**Returns**: Array -- Deduplicated findings

---

### fleet-bulk-orchestration.js

**Location**: `shared/fleet-bulk-orchestration.js`

#### `bulkOrchestrate(items, skillName, options)`

Generic bulk orchestration framework used by all `-bulk` workflow variants.

**Parameters**:
- `items` (Array): Items to process
- `skillName` (string): Name of the skill to invoke on workers
- `options` (Object):
  - `mergeStrategy` (string): `'markdown'`, `'json'`, `'findings'`, `'embeddings'`, `'tests'`
  - `timeout` (number): Per-worker timeout in milliseconds
  - `breakEvenThreshold` (number): Override default threshold

**Returns**: Promise -- Merged results from all workers

---

### fleet-workflow-patterns.js

**Location**: `shared/fleet-workflow-patterns.js`

High-level reusable patterns for fleet-distributed workflows.

#### `distributeAndMerge(items, processFunction, mergeFunction)`

Distribute items across fleet workers, process on each, merge results.

```javascript
const results = await distributeAndMerge(
  pdfPaths,
  (batch) => processBatch(batch),
  (results) => mergeResults(results)
)
```

---

#### `distributeItems(items, workers)`

Round-robin distribution of items across workers.

---

#### `distributeItemsWeighted(items, workers)`

Memory-proportional distribution of items across workers.

---

#### `workerTempDir(workerHostname, skillName)`

Returns the `/tmp` scratch directory path for a worker.

```javascript
const tmpDir = workerTempDir('server-01', 'pdf-research')
// '/tmp/claude-fleet-pdf-research/'
```

---

#### `isOnNfs(path)`

Checks if a path is on the NFS share.

---

### fleet-integration.js

**Location**: `shared/fleet-integration.js`

Workflow-friendly fleet integration with args parsing.

#### `parseFleetArgs(args)`

Parses fleet-related arguments from a command string.

```javascript
const { fleetMode, items, options } = parseFleetArgs('file1.pdf file2.pdf --fleet')
// fleetMode: 'fleet', items: ['file1.pdf', 'file2.pdf']
```

---

#### `shouldUseFleet(itemCount, threshold)`

Determines if fleet mode should be used based on item count.

---

#### `getFleetWorkers(options?)`

Returns available fleet workers with health checks.

---

---

## Consensus API

### consensus-strategies.js

**Location**: Root directory
**Import**: `import { rotatingArbiter, singleArbiter, majorityVote, pairwiseComparison, weightedVoting } from './consensus-strategies.js'`

---

#### `rotatingArbiter(workers, prompt, schema)`

Democratic consensus: each worker judges all others, votes are tallied.

```javascript
const result = await rotatingArbiter(
  [
    { model: 'opus', name: 'opus' },
    { model: 'sonnet', name: 'sonnet' },
    { model: 'haiku', name: 'haiku' },
  ],
  'Analyze this code for bugs',
  bugSchema
)
// result.solution -- winning solution
// result.votes -- vote count for winner
// result.strategy -- 'rotating'
```

**Parameters**:
- `workers` (Array<{model, name}>): Worker definitions
- `prompt` (string): Task prompt
- `schema` (Object): JSON Schema for structured output

**Returns**: Object:
- `solution` -- The winning solution
- `strategy` -- `'rotating'`
- `votes` -- Number of votes for winner
- `total_workers` -- Total number of workers
- `all_solutions` -- All worker solutions
- `all_judgments` -- All arbiter judgments

---

#### `singleArbiter(workers, prompt, schema, arbiterModel?)`

Fast consensus: one designated model judges all workers.

**Parameters**: Same as `rotatingArbiter()` plus:
- `arbiterModel` (string, optional): Model to use as arbiter. Default: `'opus'`

---

#### `majorityVote(workers, prompt, schema)`

Simple vote counting, no arbiter overhead.

---

#### `pairwiseComparison(workers, prompt, schema)`

Tournament-style elimination: workers compete in pairs.

---

#### `weightedVoting(workers, prompt, schema)`

Confidence-based voting: workers provide scores, combined via weighted average.

---

### consensus-engine.js

**Location**: `shared/consensus-engine.js`

Core consensus engine providing building blocks for consensus patterns.

---

### smart-consensus.js

**Location**: `shared/smart-consensus.js`

Performance-aware consensus that routes to optimal models based on task type and historical performance data.

---

## Attribution API

### AttributionTracker Class

**Location**: `shared/attribution.js`
**Import**: `import { AttributionTracker } from './shared/attribution.js'`

Tracks which AI model contributed which findings in consensus workflows.

---

#### `constructor()`

Creates a new attribution tracker.

```javascript
const tracker = new AttributionTracker()
```

---

#### `recordWorker(model, contribution, metadata?)`

Records a contribution from a worker model.

```javascript
tracker.recordWorker('opus', 'SQL injection in login.js line 42', {
  file: 'login.js',
  line: 42,
  severity: 'critical'
})
```

**Parameters**:
- `model` (string): AI model name (`'opus'`, `'sonnet'`, `'gpt4'`, etc.)
- `contribution` (string): Description of what this model contributed
- `metadata` (Object, optional): Additional context (file, line, severity, etc.)

**Returns**: Record object

---

#### `recordArbiter(model, decision, reasoning, metadata?)`

Records the arbiter's decision.

```javascript
tracker.recordArbiter('opus', 'approve', 'Both findings are valid', { confidence: 92 })
```

**Parameters**:
- `model` (string): Arbiter model name
- `decision` (string): Decision made (`'approve'`, `'reject'`, etc.)
- `reasoning` (string): Explanation of the decision
- `metadata` (Object, optional): Additional context

**Returns**: Record object

---

#### `findConsensus(threshold?)`

Finds contributions agreed upon by multiple models.

```javascript
const consensus = tracker.findConsensus(2)  // Findings from 2+ models
```

**Parameters**:
- `threshold` (number, optional): Minimum models that must agree. Default: 2

**Returns**: Array of objects:
- `text` (string): The contribution text
- `models` (Array<string>): Models that contributed this finding
- `count` (number): Number of agreeing models

---

#### `findUnique()`

Finds contributions from only one model (potential false positives or unique insights).

```javascript
const unique = tracker.findUnique()
```

**Returns**: Array of objects:
- `text` (string): The contribution text
- `model` (string): The single model that found this
- `count` (number): Always 1

---

#### `summarize()`

Returns a summary of all tracked attributions.

```javascript
const summary = tracker.summarize()
```

**Returns**: Object:
- `workers` -- Per-worker contribution counts
- `arbiter` -- Arbiter decision details
- `consensus` -- Consensus findings
- `unique` -- Unique findings
- `stats` -- Aggregate statistics (total contributions, consensus rate)

---

#### `toMarkdown()`

Generates a formatted markdown attribution report.

```javascript
const report = tracker.toMarkdown()
// Returns a complete markdown document with workers, arbiter, consensus,
// unique findings, and statistics sections
```

**Returns**: string -- Formatted markdown report

---

## Analysis APIs

### impact-analysis.js

**Location**: `shared/impact-analysis.js`

Breaking change detection, severity scoring, and exploitability analysis.

Key functions:
- **Breaking change detection**: Identifies API changes that break backward compatibility
- **Severity scoring**: Assigns severity levels to findings
- **Exploitability analysis**: Assesses real-world risk of security findings

---

### quality-scorer.js

**Location**: `shared/quality-scorer.js`

Multi-dimensional code quality scoring across:
- Code complexity
- Test coverage
- Documentation completeness
- Security posture
- Maintainability

---

### code-ast-analysis.js

**Location**: Root directory

AST-level code analysis providing:
- Function signature extraction
- Complexity metrics (cyclomatic, cognitive)
- Dependency graph construction
- Dead code detection

---

## Knowledge and Memory APIs

### RAG Pipeline (rag.py)

**Location**: `shared/rag.py`

RAG with citations providing query, retrieve, and generate with sources.

```python
from shared.rag import RAG

rag = RAG(collection='claude-memory')
result = rag.query('How does consensus work?')
# Returns answer with source citations
```

**Key features**:
- Hybrid search (semantic + keyword)
- Reranking for precision
- Source citation tracking
- Cross-session learning

---

### Semantic Search (semantic-search.py)

**Location**: `shared/semantic-search.py`

Hybrid search with RRF (Reciprocal Rank Fusion) algorithm.

```python
from shared.semantic_search import HybridSearch

search = HybridSearch(collection='code-chunks')
results = search.query('async error handling patterns', top_k=10)
```

**Features**:
- Semantic embeddings (Xenova/all-MiniLM, 384 dimensions)
- Keyword matching (BM25)
- RRF algorithm combining both scores
- Reranking (bi-encoder to cross-encoder)
- MongoDB-style metadata filtering

---

### Vector Store (vector-store.py)

**Location**: `shared/vector-store.py`

ChromaDB vector storage abstraction.

```python
from shared.vector_store import VectorStore

store = VectorStore(collection='my-collection')
store.add(documents=['doc1', 'doc2'], metadatas=[{...}, {...}])
results = store.query('search term', n_results=5)
```

**Features**:
- Local ChromaDB with persistent storage
- Semantic embeddings (384-dim vectors)
- Metadata filtering
- Cosine similarity search

---

### Learning System (learning-system.js)

**Location**: `shared/learning-system.js`

Cross-session learning extraction and persistence.

Key exports:
- `extractLearnings(transcript)` -- Extract learnings from a session transcript
- `persistLearning(learning, category)` -- Save a learning to disk
- `queryLearnings(query)` -- Search existing learnings

---

## Platform and Model APIs

### platform-detector.js

**Location**: `shared/platform-detector.js`

Detects the hosting platform (GitHub or GitLab) from git remote URL.

```javascript
import { detectPlatform } from './shared/platform-detector.js'

const platform = detectPlatform()
// 'github' or 'gitlab'

// Use appropriate CLI
if (platform === 'github') {
  execSync('gh issue create ...')
} else {
  execSync('glab issue create ...')
}
```

---

### model-detection.js

**Location**: `shared/model-detection.js`

Detects available AI models (local Ollama, cloud APIs).

```javascript
import { detectAvailableModels } from './shared/model-detection.js'

const models = await detectAvailableModels()
// { ollama: ['llama3', 'mistral'], cloud: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
```

---

### model-performance.js

**Location**: `shared/model-performance.js`

Tracks model performance metrics over time.

```javascript
import { recordPerformance, getBestModel } from './shared/model-performance.js'

// Record a performance observation
recordPerformance('opus', 'security', { accuracy: 0.95, latency: 2.3 })

// Query best model for a task type
const best = getBestModel('security')
// 'opus' (based on historical accuracy)
```

---

## Utility APIs

### chunking-utils.js

**Location**: `shared/chunking-utils.js`

Smart document chunking for RAG processing.

```javascript
import { chunkDocument } from './shared/chunking-utils.js'

const chunks = chunkDocument(text, { maxChunkSize: 8000, overlap: 200 })
```

---

### clustering-utils.js

**Location**: `shared/clustering-utils.js`

Cluster similar findings for deduplication.

```javascript
import { clusterFindings } from './shared/clustering-utils.js'

const clusters = clusterFindings(allFindings, { similarityThreshold: 0.8 })
const deduped = clusters.map(c => c.representative)
```

---

### issue-operations.js

**Location**: `shared/issue-operations.js`

Create and update GitHub/GitLab issues from findings.

Key functions:
- `createIssue(finding, platform)` -- Create a new issue
- `updateIssue(issueNumber, updates, platform)` -- Update an existing issue
- `closeIssue(issueNumber, platform)` -- Close an issue
- `linkIssue(issueNumber, prNumber, platform)` -- Link issue to PR

---

### loop-controller.js

**Location**: `shared/loop-controller.js`

Control loop execution for continuous SDLC.

```javascript
import { LoopController } from './shared/loop-controller.js'

const controller = new LoopController({ maxIterations: 5, budget: '500k' })
while (controller.shouldContinue()) {
  const results = await runSdlcPhase()
  controller.recordIteration(results)
}
```

---

### schemas.js

**Location**: `shared/schemas.js`

Shared JSON Schema definitions used across workflows.

```javascript
import { REVIEW_SCHEMA, SECURITY_SCHEMA, ARBITER_SCHEMA } from './shared/schemas.js'
```

---

### workflow-helpers.js

**Location**: `shared/workflow-helpers.js`

Common workflow utilities including arbiter patterns and schema definitions.

---

## Configuration Schemas

### fleet.json Schema

**Location**: `~/.claude/fleet.json`

```typescript
interface FleetConfig {
  machines: Machine[]
  policies: {
    health_check_timeout_ms: number    // Default: 2000
    max_parallel_workers: number       // Default: 10
  }
  compliance: {
    forbidden_paths: string[]          // Directories where fleet is blocked
    reason: string                     // Human-readable explanation
  }
}

interface Machine {
  hostname: string                     // DNS name or IP
  role: 'controller' | 'worker' | 'sentinel'
  memory_gb: number                    // RAM in GB
  cpus: number                         // CPU core count
  priority: number                     // Lower = higher priority
  tags?: string[]                      // Additional metadata
  capabilities?: string[]             // Required capabilities
}
```

### multi-ai-config.json Schema

**Location**: Project root or `~/.claude/workflows/multi-ai-config.json`

```typescript
interface MultiAIConfig {
  enabled: boolean                     // Master switch for multi-AI
  default_strategy: string             // Preset name
  fleet?: {
    enabled: boolean                   // Fleet-aware model distribution
    dispatcher: string                 // Dispatcher URL
    loadBalance: boolean               // Balance across servers
    autoDistribute: boolean            // Auto-distribute AI calls
  }
  workers: {
    models: (string | ModelSpec)[]     // Model names or specs
    count: number                      // Active worker count
  }
  arbiter: {
    enabled: boolean                   // Use arbiter synthesis
    model: string                      // Primary arbiter model
    server?: string                    // Server assignment
    fallback: (string | ModelSpec)[]   // Fallback chain
  }
  serverCapabilities?: Record<string, ServerSpec>  // Per-server specs
  presets?: Record<string, PresetConfig>            // Named presets
}

interface ModelSpec {
  name: string                         // Model identifier
  server: string                       // Server to run on
  role: string                         // 'heavy' | 'fast' | 'code'
  api?: string                         // API provider
}

interface ServerSpec {
  ram: number                          // RAM in GB
  cpu: number                          // CPU cores
  roles: string[]                      // Server roles
  services?: string[]                  // Running services
  models: string[]                     // Models assigned
  priority: number                     // Lower = higher priority
}
```

### JSON Schema Definitions

**Location**: `schemas/`

| Schema | File | Purpose |
|--------|------|---------|
| Extracted Claims | `extracted-claims.schema.json` | Claims extracted from PDFs |
| Adversarial Verdict | `adversarial-verdict.schema.json` | Refutation voting results |
| Validation | `validation.schema.json` | Claim validation results |
| Synthesized Findings | `synthesized-findings.schema.json` | Final synthesized report |
| Final Report | `final-report.schema.json` | Complete research report |
| Index | `index.json` | Schema index/catalog |

Example (extracted claims):

```json
{
  "type": "object",
  "properties": {
    "claims": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "claim_id": { "type": "string" },
          "text": { "type": "string" },
          "source_page": { "type": "number" },
          "importance": { "type": "string", "enum": ["central", "supporting", "tangential"] },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
        },
        "required": ["claim_id", "text", "importance"]
      }
    }
  }
}
```

---

## Shell APIs

### fleet-bulk-lib.sh

**Location**: `scripts/fleet/fleet-bulk-lib.sh` (1022 lines)

Common library sourced by all fleet bulk scripts. Provides the complete fleet orchestration pipeline.

**Functions**:

| Function | Purpose |
|----------|---------|
| `fleet_discover_workers` | Read fleet.json, filter by role, health check |
| `fleet_check_compliance` | Validate current path against forbidden paths |
| `fleet_init_session` | Initialize fleet session with skill name and timestamp |
| `fleet_distribute_roundrobin` | Distribute items round-robin across workers |
| `fleet_distribute_weighted` | Distribute items proportional to worker memory |
| `fleet_dispatch_workers` | Launch independent Claude Code sessions via SSH |
| `fleet_wait_workers` | Wait for all workers to complete (with progress) |
| `fleet_collect_results` | Collect results from workers via SSH |
| `fleet_merge_json` | Merge JSON results from all workers |
| `fleet_merge_markdown` | Merge markdown reports from all workers |
| `fleet_summary` | Print execution summary |
| `fleet_cleanup` | Clean up temporary files |

**Usage pattern**:
```bash
#!/bin/bash
source "$(dirname "$0")/fleet-bulk-lib.sh"

fleet_discover_workers
fleet_check_compliance
fleet_init_session "my-skill"
fleet_distribute_roundrobin "$items_file"
fleet_dispatch_workers "/my-skill" "$prompt_template"
fleet_wait_workers
fleet_collect_results
fleet_merge_json "$output_file"
fleet_summary "my-skill" "$start_time" "$total_items"
```

---

### skill-helpers.sh

**Location**: `shared/skill-helpers.sh`

Common shell utilities for skill scripts.

---

### visual-indicators.sh

**Location**: `shared/visual-indicators.sh`

Colored consensus output with model-specific colors and progress indicators.

```bash
source shared/visual-indicators.sh

# Show model-colored output
show_model_result "opus" "Found 3 security issues"
show_model_result "sonnet" "Found 2 security issues"

# Show consensus indicator
show_consensus "high" "2/3 models agree"

# Show progress
show_progress 42 100 "Processing files"
```

---

## Cross-References

- **[ARCHITECTURE.md](ARCHITECTURE.md)** -- System design, components, architecture decisions
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** -- How to integrate workflows, migration guide, examples
- **[OPERATIONS.md](OPERATIONS.md)** -- Deployment, monitoring, troubleshooting
- **[MULTI_AI_PATTERN.md](../MULTI_AI_PATTERN.md)** -- Multi-AI consensus pattern template
- **[MULTI_AI_CONFIG.md](../MULTI_AI_CONFIG.md)** -- Multi-AI configuration details
- **[ATTRIBUTION_TRACKING.md](ATTRIBUTION_TRACKING.md)** -- Attribution system deep-dive
- **[shared/README.md](../shared/README.md)** -- Shared library overview
