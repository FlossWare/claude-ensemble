# TERMINOLOGY.md -- Auto-Storage System Canonical Terminology

> **Purpose:** Single source of truth for naming conventions across the auto-storage
> subsystem. Every file that touches workflow persistence (adapters, hooks, trackers,
> migration scripts, workflow `.mjs` files) MUST use these terms. When a term
> appears in this document, the canonical form is the ONLY acceptable form.
>
> **Scope:** `learning/postgres-adapter.js`, `learning/workflow-storage-adapter.js`,
> `learning/workflow-completion-hook.js`, `workflows/shared/workflow-tracker.js`,
> `learning/scripts/migrate-completed-workflows.js`,
> `workflows/deep-research-with-autostorage.mjs`, and any future consumer.

---

## Visual Architecture

```
Workflow (.mjs)
  |
  v
WorkflowTracker              <-- orchestrates tracking; JS-layer API
  |
  v
WorkflowCompletionHook       <-- post-completion orchestrator (PostgreSQL + Neo4j)
  |
  +---> WorkflowStorageAdapter   <-- PostgreSQL writes (executions + learnings + strategy)
  |       |
  |       +---> WorkflowLearning (in postgres-adapter.js)
  |       |       |-- recordRun()        --> workflow.executions
  |       |       |-- recordLearning()   --> workflow.learnings
  |       |       +-- _chunkText()       (splits large text before storage)
  |       |
  |       +---> StrategyPerformance      --> learning.strategy_performance
  |       |
  |       +---> generateEmbedding()      (Google AI, 384-dim vectors)
  |
  +---> WorkflowGraphSync       <-- Neo4j writes (planned, not yet implemented)
```

### Data Flow (single workflow execution)

```
Workflow starts
  |
  +-- trackPhase('search', fn)     WorkflowTracker buffers phase data
  +-- trackWorker({model, ...})    WorkflowTracker buffers worker data
  +-- trackArbiter({model, ...})   WorkflowTracker buffers arbiter decision
  +-- addLearning(desc, insight)   WorkflowTracker buffers learning
  |
  v
tracker.complete(result, 0.85)
  |
  v
WorkflowCompletionHook.onWorkflowComplete(workflowData)
  |
  +-- calculateQualityScore()
  +-- WorkflowStorageAdapter.storeExecution()
  |     +-- recordRun()              --> INSERT workflow.executions  (returns executionId)
  |     +-- recordLearning()         --> INSERT workflow.learnings   (FK: executionId)
  |     +-- generateEmbedding()      --> 384-dim vector via Google AI
  |     +-- strategyPerf.record()    --> UPSERT learning.strategy_performance
  |
  +-- [async] WorkflowGraphSync.syncWorkflowExecution()  --> Neo4j (future)
```

---

## 1. Core Concepts

### Auto-Storage

The system that automatically persists workflow execution results to PostgreSQL
(and eventually Neo4j) without requiring workflows to write SQL directly.
Workflows interact through `WorkflowTracker`; the hook and adapter handle
persistence behind the scenes.

**Cross-references:** [WorkflowTracker (Section 8)](#classes),
[WorkflowCompletionHook (Section 8)](#classes),
[WorkflowStorageAdapter (Section 8)](#classes)

### Workflow Tracking

The process of buffering phase, worker, arbiter, and learning data during
workflow execution, then flushing it all to PostgreSQL when the workflow
completes via `tracker.complete()`.

**Cross-references:** [Tracking Methods (Section 9)](#tracking-methods-workflowtracker),
[Data Flow diagram (above)](#data-flow-single-workflow-execution)

### Learning (singular) / Learnings (plural)

An observation extracted from a workflow execution. Each learning has a
description, an actionable insight, an importance score, and optionally an
embedding vector.

- **Singular** (`learning`): one individual record in `workflow.learnings`.
- **Plural** (`learnings`): a collection of records, or the table name itself.
- **Class name:** `WorkflowLearning` (canonical; current code says
  `WorkflowsLearning` and must be renamed).

**Cross-references:** [Learning Types (Section 10)](#10-learning-types),
[Class / Function Rename (Section 12)](#class--function-rename),
[Chunking (Section 2)](#chunking)

### Execution

A single completed run of a workflow. Stored in `workflow.executions`. Each
execution has a unique auto-incremented integer primary key (`executionId`) and
a UUID-style external correlation identifier (`workflowId`).

**Cross-references:** [Execution Identifiers (Section 5)](#execution-identifiers),
[Storage Methods (Section 9)](#storage-methods)

---

## 2. Technical Terms

### Chunking

Splitting large text (over a configurable character threshold) into overlapping
segments for individual embedding generation and storage. Two chunking layers
exist:

| Layer | Class | Threshold | Overlap | Location |
|-------|-------|-----------|---------|----------|
| Learning text | `WorkflowLearning._chunkText()` | 4,000 chars | 200 chars | `postgres-adapter.js` |
| Workflow results | `WorkflowStorageAdapter` | 10,000 chars | 500 chars | `workflow-storage-adapter.js` |

Each chunk is stored as a separate `workflow.learnings` row with metadata
linking it to a parent learning record (`parent_learning_id`, `chunk_index`,
`total_chunks`).

**Example:**

```javascript
// A 9,000-char learning description gets split into 3 chunks:
//   Chunk 0: chars 0-4000
//   Chunk 1: chars 3800-7800   (200-char overlap with chunk 0)
//   Chunk 2: chars 7600-9000   (200-char overlap with chunk 1)
// Each chunk gets its own embedding and row in workflow.learnings.
```

**Cross-references:** [Embedding (below)](#embedding),
[WorkflowLearning (Section 8)](#classes),
[Quick Reference Card (Section 13)](#13-quick-reference-card)

### Embedding

A 384-dimensional floating-point vector representing the semantic content of a
text string. Generated via the Google AI Studio API
(`gemini-embedding-001` model, truncated from 768-dim to 384-dim).

- **Generation:** `WorkflowStorageAdapter.generateEmbedding(text)` (synchronous,
  uses `curl` + temp file).
- **Storage format:** PostgreSQL `vector(384)` column via pgvector extension.
- **Similarity search:** Cosine distance operator `<=>` in SQL.
- **Graceful degradation:** If `GOOGLE_API_KEY` is unset or the API call fails,
  the embedding is stored as `NULL` and the workflow continues.

**Example:**

```javascript
const adapter = new WorkflowStorageAdapter();
const vec = adapter.generateEmbedding('Analyze firmware update patterns');
// vec = [0.0123, -0.0456, 0.0789, ...] (384 floats) or null on failure
```

```sql
-- Similarity search: find 10 closest learnings to a query vector
SELECT description, actionable_insight,
       description_embedding <=> $1::vector AS distance
FROM workflow.learnings
WHERE description_embedding IS NOT NULL
ORDER BY description_embedding <=> $1::vector
LIMIT 10;
```

**Cross-references:** [Embedding Methods (Section 9)](#embedding-methods),
[Vector Database (below)](#vector-database-pgvector),
[Field Mapping Table (Section 6)](#field-mapping-table)

### Vector Database (pgvector)

PostgreSQL with the `pgvector` extension, providing HNSW-indexed vector
similarity search. All vector columns use `vector(384)`. The database name is
`learning` on host `laptop-01`.

**Cross-references:** [PostgreSQL Schema Name (Section 4)](#4-postgresql-schema-name),
[Embedding (above)](#embedding)

### Graph Database (Neo4j)

Planned but not yet implemented. `WorkflowGraphSync` is referenced in
`WorkflowCompletionHook` but the sync is async and failure is non-blocking.
Do not depend on Neo4j data being present.

**Cross-references:** [WorkflowGraphSync (Section 8)](#classes),
[Connection Lifecycle (Section 7)](#7-connection-lifecycle)

### Thompson Sampling

The bandit algorithm used to select strategies. State is stored in
`learning.strategy_performance` with Beta distribution parameters (`alpha`,
`beta`). Updated via `StrategyPerformance.record(strategy, success, reward)`.

**Example:**

```javascript
const { getStrategyPerformance } = require('./postgres-adapter.js');
const sp = getStrategyPerformance();

// Record a successful strategy execution
await sp.record('grep_parallel', true, 0.92);

// Internally: alpha += reward, beta += (1 - reward)
// Thompson Sampling draws from Beta(alpha, beta) to rank strategies
```

**Cross-references:** [StrategyPerformance (Section 8)](#classes),
[Singleton Accessors (Section 8)](#singleton-accessors-postgres-adapterjs)

---

## 3. Outcome Values (CRITICAL)

### Canonical Constants

All code MUST use the `OUTCOMES` object exported from `postgres-adapter.js`:

```javascript
const { OUTCOMES } = require('./postgres-adapter.js');

OUTCOMES.SUCCESS  // 'success'  -- workflow completed normally
OUTCOMES.FAILED   // 'failed'   -- workflow failed (NOT 'failure', NOT 'fail')
OUTCOMES.ERROR    // 'error'    -- system-level error (NOT 'ERROR')
```

### Banned Terms

| Banned | Why | Use Instead |
|--------|-----|-------------|
| `'failure'` | Never matches `OUTCOMES.FAILED` | `OUTCOMES.FAILED` (`'failed'`) |
| `'fail'` | Informal variant | `OUTCOMES.FAILED` (`'failed'`) |
| `'pass'` | Informal variant | `OUTCOMES.SUCCESS` (`'success'`) |
| `'ERROR'` | Case mismatch | `OUTCOMES.ERROR` (`'error'`) |

### Normalization

`ExecutionMonitor.logExecution()` in `postgres-adapter.js` normalizes incoming
outcome strings as a safety net. However, callers MUST NOT rely on
normalization. Always pass `OUTCOMES.*` constants directly.

**Example -- correct usage:**

```javascript
const { OUTCOMES } = require('./postgres-adapter.js');

// CORRECT
tracker.complete(result, 0.85, OUTCOMES.SUCCESS);

// WRONG -- will silently mismatch in comparisons
tracker.complete(result, 0.85, 'failure');
```

### Known Bugs (to fix)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `workflow-completion-hook.js` | 40 | JSDoc says `'success' \| 'failure'` | Must say `'success' \| 'failed' \| 'error'` |
| `workflow-completion-hook.js` | 226 | `outcome === 'failure'` | Must check `outcome === OUTCOMES.FAILED` (i.e., `'failed'`) |
| `workflow-tracker.js` | 146 | `outcome = 'success'` (string literal) | Must use `OUTCOMES.SUCCESS` |

**Cross-references:** [Summary of Fixes Required (Section 12)](#outcome-values),
[Quick Reference Card (Section 13)](#13-quick-reference-card)

---

## 4. PostgreSQL Schema Name

### Canonical: `workflow.` (singular)

All SQL statements MUST use the `workflow.` schema prefix. Never `workflows.`.

| Table / View | Schema | Full Name |
|-------------|--------|-----------|
| `executions` | `workflow.` | `workflow.executions` |
| `worker_results` | `workflow.` | `workflow.worker_results` |
| `arbiter_decisions` | `workflow.` | `workflow.arbiter_decisions` |
| `phases` | `workflow.` | `workflow.phases` |
| `learnings` | `workflow.` | `workflow.learnings` |
| `workflow_summary` | `workflow.` | `workflow.workflow_summary` (materialized view) |
| `model_performance` | `workflow.` | `workflow.model_performance` (materialized view) |
| `cost_analysis` | `workflow.` | `workflow.cost_analysis` (materialized view) |

Other schemas in the same database:

| Schema | Purpose |
|--------|---------|
| `learning.` | Experience memory, strategy performance, consciousness research |
| `monitoring.` | Execution summary (model-level execution logs) |
| `costs.` | Cost tracking entries |

**Example -- correct SQL:**

```sql
-- CORRECT
SELECT * FROM workflow.executions WHERE outcome = 'success';

-- WRONG (plural schema name)
SELECT * FROM workflows.executions WHERE outcome = 'success';
```

### Known Bugs (to fix)

All in `postgres-adapter.js`, class `WorkflowsLearning`:

| Line | Current | Fix |
|------|---------|-----|
| 725 | `workflows.learnings` | `workflow.learnings` |
| 769 | `workflows.task_difficulty_stats` | `workflow.task_difficulty_stats` |
| 786 | `workflows.performance_summary` | `workflow.performance_summary` |
| 804 | `workflows.learnings` | `workflow.learnings` |

**Cross-references:** [Summary of Fixes Required (Section 12)](#schema-name),
[Quick Reference Card (Section 13)](#13-quick-reference-card)

---

## 5. Identifier Naming

### Execution Identifiers

Two distinct identifiers exist for every workflow execution:

```
workflow.executions
+----+-------------------------------+-------------------+
| id | workflow_id                   | workflow_name     |
+----+-------------------------------+-------------------+
| 17 | wf-research-1718812345-abc123 | deep-research     |  <-- executionId = 17 (int PK)
| 18 | wf-research-1718812400-def456 | deep-research     |      workflowId = 'wf-research-...' (UUID)
+----+-------------------------------+-------------------+

workflow.learnings
+----+------------------------+-----------------------------+
| id | workflow_execution_id  | description                 |
+----+------------------------+-----------------------------+
| 42 | 17                     | 'Pattern: parallel search'  |  <-- FK references executionId
| 43 | 17                     | 'Optimization: batch embed' |
+----+------------------------+-----------------------------+
```

| Concept | JS Name (camelCase) | SQL Column (snake_case) | Type | Purpose |
|---------|---------------------|------------------------|------|---------|
| Primary key | `executionId` | `id` | `SERIAL` (integer) | Foreign key for child tables (`workflow.learnings`, `workflow.worker_results`, etc.) |
| External correlation ID | `workflowId` | `workflow_id` | `VARCHAR(64)` | UUID-style identifier for external systems and logs |

### Rules

1. **`executionId`** (integer): Always use this name in JavaScript when referring
   to the auto-generated PK returned by `recordRun()` or `storeExecution()`.
   This is the value needed as the FK in `workflow.learnings.workflow_execution_id`.

2. **`workflowId`** (string): Always use this name in JavaScript for the
   UUID-style correlation identifier (e.g., `wf-research-1718812345-abc123`).
   Generated by `WorkflowStorageAdapter.generateRunId()`.

3. **`workflow_execution_id`**: ONLY as the SQL FK column name in child tables.
   Never use this form in JavaScript variable names.

**Example -- correct usage:**

```javascript
// CORRECT
const { executionId } = await storage.storeExecution({ ... });
await learning.recordLearning({
  workflow_execution_id: executionId,  // snake_case only in the SQL-bound object
  description: 'Pattern: parallel search improves throughput'
});

// WRONG -- generic name, unclear which ID
const { id } = await storage.storeExecution({ ... });
```

### Banned Terms

| Banned | Why | Use Instead |
|--------|-----|-------------|
| `run_id` (JS layer) | Ambiguous with `executionId` | `workflowId` for the UUID |
| `execution_id` (JS layer) | Inconsistent casing | `executionId` |
| `id` (as a return value name) | Too generic; caller cannot tell which ID | `executionId` |

**Cross-references:** [Storage Methods (Section 9)](#storage-methods),
[Field Mapping Table (Section 6)](#field-mapping-table)

---

## 6. Case Convention: JavaScript vs. SQL

### Rule

- **JavaScript API boundary:** camelCase
- **SQL column names:** snake_case
- **Metadata objects:** camelCase (they live at the JS layer)

**Example -- mapping across the boundary:**

```javascript
// JavaScript layer (camelCase)
const workerData = {
  qualityScore: 0.92,
  durationMs: 4500,
  inputTokens: 1500,
  outputTokens: 800,
  costUsd: 0.05
};

// When this reaches SQL (snake_case in the INSERT)
// quality_score = 0.92
// duration_ms = 4500
// input_tokens = 1500
// output_tokens = 800
// cost_usd = 0.05
```

### Field Mapping Table

| JavaScript (camelCase) | SQL Column (snake_case) | Notes |
|------------------------|------------------------|-------|
| `qualityScore` | `quality_score` | Never `finalQualityScore` in metadata |
| `taskType` | `task_type` | |
| `durationMs` | `duration_ms` | Individual worker or phase duration |
| `totalDurationMs` | `total_duration_ms` | Workflow-level total duration |
| `inputTokens` | `input_tokens` | |
| `outputTokens` | `output_tokens` | |
| `costUsd` | `cost_usd` | |
| `workflowName` | `workflow_name` | |
| `taskDescription` | `task_description` | |
| `learningType` | `learning_type` | One of: `'pattern'`, `'failure'`, `'optimization'` |
| `actionableInsight` | `actionable_insight` | |
| `noveltyScore` | `novelty_score` | |
| `problemType` | `problem_type` | |
| `problemHash` | `problem_hash` | |
| `learningEmbedding` | `learning_embedding` | `vector(384)` or `NULL` |
| `taskEmbedding` | `task_embedding` | `vector(384)` or `NULL` |
| `resultEmbedding` | `result_embedding` | `vector(384)` or `NULL` |
| `descriptionEmbedding` | `description_embedding` | `vector(384)` or `NULL` |

### Duration Fields (semantic distinction)

| JavaScript | SQL | Scope |
|-----------|-----|-------|
| `durationMs` | `duration_ms` | Single worker, phase, or operation |
| `totalDurationMs` | `total_duration_ms` | Entire workflow execution end-to-end |

Never use `durationMs` for a workflow-level total. Never use `totalDurationMs`
for a single worker.

**Example -- correct duration usage:**

```javascript
// Single worker -- use durationMs
await db.storeWorkerResult({
  durationMs: 4500,  // CORRECT: one worker's time
  // totalDurationMs: 4500  // WRONG: this is not a whole workflow
});

// Whole workflow -- use totalDurationMs
await db.storeExecution({
  totalDurationMs: 45000,  // CORRECT: entire workflow end-to-end
  // durationMs: 45000     // WRONG: this is not a single operation
});
```

**Cross-references:** [Execution Identifiers (Section 5)](#execution-identifiers),
[Quick Reference Card (Section 13)](#13-quick-reference-card)

---

## 7. Connection Lifecycle

### Canonical: `disconnect()`

Use `disconnect()` as the public method name to tear down connections. Internally
this calls `pool.end()`.

```
Process start
  |
  v
First query -----> Pool auto-connects (no explicit connect() call)
  |
  v
...many queries... (pool reused across workflow executions)
  |
  v
Process exit ----> disconnect() called once
                     |
                     +-- WorkflowCompletionHook.disconnect()
                           +-- WorkflowStorageAdapter.disconnect()
                                 +-- LearningDB.close()
                                       +-- pool.end()
```

| Class | Method | Behavior |
|-------|--------|----------|
| `LearningDB` | `close()` | Calls `this.pool.end()` |
| `WorkflowStorageAdapter` | `disconnect()` | Calls `this.db.close()` |
| `WorkflowCompletionHook` | `disconnect()` | Calls `this.storage.disconnect()` and `this.graphSync.disconnect()` |

### Rules

1. Connection pools auto-connect on first query. There is no `connect()` method.
   Never call `this.storage.connect()`.
2. Do not disconnect inside `onWorkflowComplete()`. The pool is reused across
   multiple workflow executions within a session.
3. Call `disconnect()` only at process exit or when the session is done.

**Example -- correct lifecycle:**

```javascript
const hook = new WorkflowCompletionHook();

// Process multiple workflows (pool auto-connects on first query)
await hook.onWorkflowComplete(workflow1);  // pool created here
await hook.onWorkflowComplete(workflow2);  // pool reused
await hook.onWorkflowComplete(workflow3);  // pool reused

// Only disconnect at the very end
await hook.disconnect();
```

### Dead Code (to remove)

The following methods in `workflow-completion-hook.js` reference
`this.storage.connect()` and `this.storage.client`, neither of which exist on
`WorkflowStorageAdapter`. They are dead code from a previous adapter design and
must be removed:

| Lines | Method | Reason |
|-------|--------|--------|
| 126-146 | `storeWorkflowExecution()` | References `this.storage.connect()` and `this.storage.client` which do not exist |
| 151-183 | `storeWorkerResults()` | Same: references non-existent `connect()` / `client` |
| 188-212 | `storeArbiterDecision()` | Same: references non-existent `connect()` / `client` |

The live code path is: `onWorkflowComplete()` --> `this.storage.storeExecution()`
--> `WorkflowStorageAdapter.storeExecution()` --> `WorkflowLearning.recordRun()`
+ `WorkflowLearning.recordLearning()`.

**Cross-references:** [Summary of Fixes Required (Section 12)](#dead-code-removal),
[Component Names (Section 8)](#classes)

---

## 8. Component Names

### Classes

| Canonical Name | File | Purpose |
|---------------|------|---------|
| `LearningDB` | `postgres-adapter.js` | Low-level PostgreSQL pool wrapper (query, get, all, run, transaction, close) |
| `StrategyPerformance` | `postgres-adapter.js` | Thompson Sampling bandit state in `learning.strategy_performance` |
| `ExecutionMonitor` | `postgres-adapter.js` | Model execution logging to `monitoring.execution_summary` |
| `CostTracker` | `postgres-adapter.js` | Cost logging to `costs.entries` |
| `ExperienceMemory` | `postgres-adapter.js` | Continual learning experiences in `learning.experiences` |
| `WorkflowLearning` | `postgres-adapter.js` | Workflow execution + learning storage (canonical name; rename from `WorkflowsLearning`) |
| `WorkflowStorageAdapter` | `workflow-storage-adapter.js` | High-level adapter: generates embeddings, assesses difficulty, delegates to `WorkflowLearning` |
| `WorkflowCompletionHook` | `workflow-completion-hook.js` | Post-completion orchestrator: coordinates PostgreSQL storage, Neo4j sync, strategy updates |
| `WorkflowTracker` | `workflows/shared/workflow-tracker.js` | In-workflow middleware: buffers phases/workers/arbiters/learnings, flushes on `complete()` |
| `WorkflowGraphSync` | `workflow-graph-sync.js` | Neo4j graph sync (planned, not implemented) |

### Class Dependency Diagram

```
WorkflowTracker
  |
  +--uses--> WorkflowCompletionHook
                |
                +--uses--> WorkflowStorageAdapter
                |            |
                |            +--uses--> WorkflowLearning --------+
                |            +--uses--> StrategyPerformance      |
                |            +--uses--> generateEmbedding()      |
                |                                                |
                +--uses--> WorkflowGraphSync (future)            |
                                                                 |
                                                    LearningDB <-+
                                                      (pool)
```

### Singleton Accessors (postgres-adapter.js)

| Function | Returns |
|----------|---------|
| `getDB()` | `LearningDB` instance |
| `getStrategyPerformance()` | `StrategyPerformance` instance |
| `getExecutionMonitor()` | `ExecutionMonitor` instance |
| `getCostTracker()` | `CostTracker` instance |
| `getExperienceMemory()` | `ExperienceMemory` instance |
| `getWorkflowLearning()` | `WorkflowLearning` instance (rename from `getWorkflowsLearning`) |

**Example -- importing singletons:**

```javascript
const {
  getDB,
  getStrategyPerformance,
  getWorkflowLearning,   // CORRECT (canonical)
  // getWorkflowsLearning  // WRONG (current code, to be renamed)
  OUTCOMES
} = require('./postgres-adapter.js');
```

**Cross-references:** [Class / Function Rename (Section 12)](#class--function-rename),
[Connection Lifecycle (Section 7)](#7-connection-lifecycle)

---

## 9. Process Terms (Method Names)

### Storage Methods

| Method | Class | Action | Returns |
|--------|-------|--------|---------|
| `recordRun(data)` | `WorkflowLearning` | INSERT into `workflow.executions` | `executionId` (integer PK) |
| `recordLearning(data)` | `WorkflowLearning` | INSERT into `workflow.learnings` (with optional chunking) | `{ id }` |
| `storeExecution(data)` | `WorkflowStorageAdapter` | Generates embedding, calls `recordRun()` + `recordLearning()` + `strategyPerf.record()` | `{ executionId, workflowId, qualityScore, outcome, difficulty, strategy }` |
| `onWorkflowComplete(workflow)` | `WorkflowCompletionHook` | Calculates quality score, delegates to `storeExecution()`, triggers Neo4j sync | `{ executionId, qualityScore, outcome }` |
| `logExecution(data)` | `ExecutionMonitor` | INSERT into `monitoring.execution_summary` (with outcome normalization) | void |
| `logCost(data)` | `CostTracker` | INSERT into `costs.entries` | void |
| `addExperience(data)` | `ExperienceMemory` | INSERT into `learning.experiences` | void |

**Example -- full storage chain:**

```javascript
// Inside WorkflowTracker.complete():
const result = await this.hook.onWorkflowComplete({
  workflowName: 'deep-research',
  taskDescription: 'Analyze firmware update patterns',
  phases: this.phases,
  workers: this.workers,
  arbiter: this.arbiterDecision,
  learnings: this.learnings,
  totalDurationMs: Date.now() - this.startTime,
  outcome: OUTCOMES.SUCCESS
});

// result = { executionId: 17, qualityScore: 0.85, outcome: 'success' }
```

### Query Methods

| Method | Class | Action |
|--------|-------|--------|
| `queryLearnings(filters)` | `WorkflowLearning` | SELECT from `workflow.learnings` with optional filters |
| `getTaskDifficultyStats(taskType)` | `WorkflowLearning` | SELECT from `workflow.task_difficulty_stats` |
| `getWorkflowPerformance(workflowName)` | `WorkflowLearning` | SELECT from `workflow.performance_summary` |
| `getLearningsByRunId(runId)` | `WorkflowLearning` | SELECT from `workflow.learnings` by `run_id` |
| `findSimilar(embedding, limit, filters)` | `ExperienceMemory` | Vector similarity search on `learning.experiences` |

### Embedding Methods

| Method | Class | Action |
|--------|-------|--------|
| `generateEmbedding(text)` | `WorkflowStorageAdapter` | Calls Google AI API, returns 384-dim array or `null` |
| `_parseEmbeddingResponse(result)` | `WorkflowStorageAdapter` | Parses API JSON, truncates 768-dim to 384-dim |

### Tracking Methods (WorkflowTracker)

| Method | Action |
|--------|--------|
| `trackPhase(phaseName, fn)` | Executes `fn`, records phase timing and status |
| `trackWorker(workerData)` | Buffers worker result for later storage |
| `trackArbiter(arbiterData)` | Buffers arbiter decision for later storage |
| `addLearning(description, insight, importance, evidence)` | Buffers a learning for later storage |
| `trackTokens(inputTokens, outputTokens)` | Accumulates token usage and estimated cost |
| `complete(finalResult, qualityScore, outcome)` | Flushes all buffered data via `WorkflowCompletionHook` |

**Example -- using WorkflowTracker in a workflow:**

```javascript
export default async function({ phase, parallel, agent, log }) {
  const tracker = new WorkflowTracker('deep-research', 'Analyze firmware');

  await tracker.trackPhase('search', async () => {
    // ... search logic ...
  });

  const workers = await parallel([...]);
  for (const w of workers) {
    tracker.trackWorker({
      model: w.model,
      durationMs: w.duration,
      confidence: w.confidence,
      outcome: OUTCOMES.SUCCESS
    });
  }

  tracker.addLearning(
    'Parallel search improves throughput by 3x',
    'Use parallel search for multi-source queries',
    0.85,
    'Observed 3x speedup in 5 consecutive runs'
  );

  await tracker.complete(finalResult, 0.92, OUTCOMES.SUCCESS);
}
```

### Utility Methods

| Method | Class | Action |
|--------|-------|--------|
| `assessTaskDifficulty(qualityScore, outcome)` | `WorkflowStorageAdapter` | Returns `'easy'`, `'moderate'`, or `'hard'` |
| `generateRunId(workflowName)` | `WorkflowStorageAdapter` | Returns UUID v4 string |
| `_chunkText(text, maxChunkSize, overlap)` | `WorkflowLearning` | Splits text at paragraph/sentence boundaries |
| `calculateQualityScore(workflow)` | `WorkflowCompletionHook` | Derives 0.0-1.0 score from phase completion |

**Cross-references:** [Chunking (Section 2)](#chunking),
[Task Difficulty Levels (Section 11)](#11-task-difficulty-levels),
[Execution Identifiers (Section 5)](#execution-identifiers)

---

## 10. Learning Types

The `learning_type` column in `workflow.learnings` has a CHECK constraint
allowing only these values:

| Value | Meaning | When to Use |
|-------|---------|-------------|
| `'pattern'` | A recurring pattern or best practice | Default for task summaries and findings |
| `'failure'` | A failure mode or anti-pattern | When documenting what went wrong |
| `'optimization'` | A performance or efficiency improvement | When documenting how to do something faster/cheaper |

**Example:**

```javascript
// Pattern: a recurring best practice
tracker.addLearning(
  'Multi-source search yields higher confidence',
  'Always query at least 3 sources for research tasks',
  0.90
);
// learning_type = 'pattern' (default)

// Failure: documenting what went wrong
await wl.recordLearning({
  workflow_execution_id: execId,
  learning_type: 'failure',
  description: 'Single-source research missed critical counterevidence',
  actionable_insight: 'Require minimum 3 independent sources'
});

// Optimization: a performance improvement
await wl.recordLearning({
  workflow_execution_id: execId,
  learning_type: 'optimization',
  description: 'Batch embedding generation reduces API calls by 80%',
  actionable_insight: 'Accumulate texts and call generateEmbeddingsBatch()'
});
```

**Cross-references:** [Learning (Section 1)](#learning-singular--learnings-plural),
[Field Mapping Table (Section 6)](#field-mapping-table)

---

## 11. Task Difficulty Levels

Returned by `WorkflowStorageAdapter.assessTaskDifficulty()`:

| Value | Condition |
|-------|-----------|
| `'easy'` | `qualityScore >= 0.8` |
| `'moderate'` | `0.5 <= qualityScore < 0.8` |
| `'hard'` | `qualityScore < 0.5` OR `outcome === OUTCOMES.ERROR` |

**Visual scale:**

```
qualityScore:  0.0          0.5          0.8          1.0
               |---- hard ----|-- moderate --|--- easy ---|
                              ^              ^
               Also hard if   |              |
               outcome=error  |              |
```

**Example:**

```javascript
const difficulty = adapter.assessTaskDifficulty(0.72, OUTCOMES.SUCCESS);
// difficulty = 'moderate' (0.5 <= 0.72 < 0.8)

const difficulty2 = adapter.assessTaskDifficulty(0.95, OUTCOMES.SUCCESS);
// difficulty2 = 'easy' (0.95 >= 0.8)

const difficulty3 = adapter.assessTaskDifficulty(0.60, OUTCOMES.ERROR);
// difficulty3 = 'hard' (outcome is error, regardless of score)
```

**Cross-references:** [Outcome Values (Section 3)](#3-outcome-values-critical),
[Utility Methods (Section 9)](#utility-methods)

---

## 12. Summary of Fixes Required

This section lists every inconsistency that must be corrected to align with
this terminology document. Each item references the specific file and line.

### Outcome Values

| File | Line | Current | Fix |
|------|------|---------|-----|
| `workflow-completion-hook.js` | 40 | `'success' \| 'failure'` in JSDoc | Change to `'success' \| 'failed' \| 'error'` |
| `workflow-completion-hook.js` | 226 | `outcome === 'failure'` | Change to `outcome === OUTCOMES.FAILED` (import `OUTCOMES`) |
| `workflow-tracker.js` | 146 | `outcome = 'success'` (string literal) | Change to `outcome = OUTCOMES.SUCCESS` (import `OUTCOMES`) |

### Schema Name

| File | Line | Current | Fix |
|------|------|---------|-----|
| `postgres-adapter.js` | 725 | `workflows.learnings` | `workflow.learnings` |
| `postgres-adapter.js` | 769 | `workflows.task_difficulty_stats` | `workflow.task_difficulty_stats` |
| `postgres-adapter.js` | 786 | `workflows.performance_summary` | `workflow.performance_summary` |
| `postgres-adapter.js` | 804 | `workflows.learnings` | `workflow.learnings` |

### Class / Function Rename

| File | Line | Current | Fix |
|------|------|---------|-----|
| `postgres-adapter.js` | 486 | `class WorkflowsLearning` | `class WorkflowLearning` |
| `postgres-adapter.js` | 949 | `function getWorkflowsLearning` | `function getWorkflowLearning` |
| `postgres-adapter.js` | 963 | `getWorkflowsLearning` (export) | `getWorkflowLearning` |
| `workflow-storage-adapter.js` | 19 | `import { getWorkflowsLearning }` | `import { getWorkflowLearning }` |
| `workflow-storage-adapter.js` | 26 | `this.workflowsLearning = getWorkflowsLearning()` | `this.workflowLearning = getWorkflowLearning()` |

### Dead Code Removal

| File | Lines | Method | Reason |
|------|-------|--------|--------|
| `workflow-completion-hook.js` | 126-146 | `storeWorkflowExecution()` | References `this.storage.connect()` and `this.storage.client` which do not exist |
| `workflow-completion-hook.js` | 151-183 | `storeWorkerResults()` | Same: references non-existent `connect()` / `client` |
| `workflow-completion-hook.js` | 188-212 | `storeArbiterDecision()` | Same: references non-existent `connect()` / `client` |

**Cross-references:** All fixes derive from canonical terms defined in
[Outcome Values (Section 3)](#3-outcome-values-critical),
[PostgreSQL Schema Name (Section 4)](#4-postgresql-schema-name),
[Component Names (Section 8)](#classes), and
[Connection Lifecycle (Section 7)](#7-connection-lifecycle).

---

## 13. Quick Reference Card

```
OUTCOMES:  SUCCESS = 'success'  |  FAILED = 'failed'  |  ERROR = 'error'
SCHEMA:    workflow.*  (singular, never 'workflows.')
IDs:       executionId (int PK)  |  workflowId (UUID string)
JS CASE:   camelCase  (qualityScore, durationMs, taskType)
SQL CASE:  snake_case (quality_score, duration_ms, task_type)
DURATION:  durationMs (single op)  |  totalDurationMs (whole workflow)
TEARDOWN:  disconnect()  (never connect(); pool auto-connects)
LEARNING:  singular = one record  |  plural = collection/table
CHUNKS:    4,000 chars (learnings)  |  10,000 chars (workflow results)
VECTORS:   384-dim via Google AI  |  stored as vector(384) in pgvector
TYPES:     'pattern' | 'failure' | 'optimization'  (learning_type)
DIFFICULTY: 'easy' (>=0.8) | 'moderate' (0.5-0.8) | 'hard' (<0.5 or error)
CLASS:     WorkflowLearning  (never WorkflowsLearning)
ACCESSOR:  getWorkflowLearning()  (never getWorkflowsLearning)
```
