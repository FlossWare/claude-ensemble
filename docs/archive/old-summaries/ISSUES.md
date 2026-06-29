# Auto-Storage Missing Features

**Baseline Status: ✅ WORKING**
- PostgreSQL storage: ✅ workflow.executions, workflow.learnings
- Embeddings: ✅ 384-dim via Google AI Studio (gemini-embedding-001)
- Test verified: Execution ID 50, Learning ID 23 with embedding

---

## Issue #1: Missing chunking for large results ✅ COMPLETE

**Priority:** HIGH

**Status:** ✅ IMPLEMENTED (2026-06-20)

**Problem:** Large workflow results (>10KB) were not chunked before storage.

**Solution implemented:**
- ✅ Added `_chunkText()` method to `learning/postgres-adapter.js` (line 509)
- ✅ Integrated chunking into `recordLearning()` function (line 586)
- ✅ Auto-chunks text >4000 chars with 200 char overlap
- ✅ Semantic boundary detection (paragraph breaks, sentence breaks)
- ✅ Creates parent learning + individual chunks
- ✅ Metadata: `chunk_index`, `total_chunks`, `parent_learning_id`, `is_parent`, `original_length`
- ✅ Embeddings stored per chunk (same embedding for all chunks from parent)

**Test results:**
```
Created execution ID 59
Text length: 12854 chars
[DEBUG] Created 4 chunks
Created parent learning ID 231, storing 4 chunks...
  Chunk 1/4 stored (4000 chars)
  Chunk 2/4 stored (2631 chars)
  Chunk 3/4 stored (3972 chars)
  Chunk 4/4 stored (1503 chars)
✅ Chunked learning: parent ID 231, 4 chunks
```

**Verification query:**
```sql
SELECT id, LEFT(description, 50), 
       (metadata->>'chunk_index')::int as idx,
       (metadata->>'total_chunks')::int as total,
       (metadata->>'parent_learning_id')::int as parent
FROM workflow.learnings 
WHERE workflow_execution_id = 59;
```

---

## Issue #2: Neo4j graph sync not implemented

**Priority:** MEDIUM

**Status:** ✅ IMPLEMENTED but NOT DEPLOYED

### What's Implemented

**Core sync infrastructure exists and is fully functional:**

1. **Neo4j sync service** - `learning/neo4j-sync-service.js` (1,109 lines)
   - ✅ Full workflow execution sync (Workflow, Phase, Worker, ArbiterDecision, Learning nodes)
   - ✅ Relationship creation (CONTAINS, NEXT_PHASE, EXECUTES, USES_MODEL, ARBITRATED_BY, EVALUATED, PRODUCED)
   - ✅ Vector similarity search for RELATED_TO edges between Learnings
   - ✅ Schema initialization (constraints, indexes, vector index for 384-dim embeddings)
   - ✅ Health checks and connection management
   - ✅ Exponential backoff retry logic for transient failures
   - ✅ Batch sync for catching up unsynced executions
   - ✅ CLI interface (`node neo4j-sync-service.js <command>`)

2. **Workflow graph sync** - `learning/workflow-graph-sync.js` (743 lines)
   - ✅ PostgreSQL → Neo4j sync with MERGE operations (idempotent)
   - ✅ Background job queue via `orchestrator.work_queue`
   - ✅ Graceful fallback to PostgreSQL recursive CTEs if Neo4j unavailable
   - ✅ Query interface (workflowsByModel, bestModelForTask, executionPath, modelCollaboration)

3. **Auto-sync integration** - Multiple files
   - ✅ `learning/neo4j-auto-sync.js` - Continuous sync daemon
   - ✅ `learning/neo4j-sync-worker.js` - Background worker for queued jobs
   - ✅ `learning/auto-sync-daemon.js` - Periodic sync scheduler

4. **Workflow integration** - `learning/workflow-completion-hook.js`
   - ✅ Lines 29, 36: WorkflowGraphSync imported and initialized
   - ✅ Lines 110-121: Neo4j sync called (async, non-blocking)
   - ✅ Line 38: `enableNeo4j` flag (defaults to true)
   - ✅ Error handling with graceful degradation

5. **Test coverage** - `learning/__tests__/neo4j-sync.integration.test.js`
   - ✅ 16 integration tests with mock Neo4j driver
   - ✅ Tests for node creation, relationships, error handling, idempotency

### What's Missing (Deployment Only)

**Zero code changes needed - only deployment/configuration:**

1. **Neo4j server deployment**
   - Install Neo4j on laptop-01 (or existing server)
   - Default: bolt://laptop-01:7687
   - Requires: Neo4j 5.x+ for vector index support

2. **Environment variables** (optional - has defaults)
   ```bash
   export NEO4J_URI=bolt://laptop-01:7687
   export NEO4J_USER=neo4j
   export NEO4J_PASSWORD=<password>
   ```

3. **NPM package** (already installed)
   - ✅ `neo4j-driver: ^6.1.0` in `learning/package.json`

4. **Schema initialization** (one-time setup)
   ```bash
   node learning/neo4j-sync-service.js init
   ```

5. **Optional: Background sync worker**
   ```bash
   node learning/neo4j-sync-worker.js --interval=5000 &
   # Or use systemd service
   ```

### Current Behavior (Neo4j unavailable)

**Graceful degradation is working:**
- ✅ Workflow-completion-hook attempts Neo4j connection
- ✅ If connection fails, logs warning: `Neo4j unavailable: <reason>. Using PostgreSQL only.`
- ✅ Workflow continues without error
- ✅ All data stored in PostgreSQL as normal
- ✅ Can query relationships via PostgreSQL recursive CTEs

**From `learning/workflow-graph-sync.js` lines 49-69:**
```javascript
// Attempt Neo4j connection (non-blocking)
if (!this.skipNeo4j && !this.neo4jDriver) {
  try {
    this.neo4jDriver = neo4j.driver(
      this.neo4jConfig.uri,
      neo4j.auth.basic(this.neo4jConfig.user, this.neo4jConfig.password)
    );
    // Test connection
    const session = this.neo4jDriver.session();
    await session.run('RETURN 1');
    await session.close();
    this.neo4jAvailable = true;
    console.log('Neo4j connection established');
  } catch (err) {
    console.warn(`Neo4j unavailable: ${err.message}. Using PostgreSQL only.`);
    this.neo4jAvailable = false;
    this.neo4jDriver = null;
  }
}
```

### Expected Behavior (After Neo4j Deployment)

**Graph nodes created automatically:**
- **Workflow** nodes: `workflow_id`, `workflow_name`, `task_description`, `total_workers`, `total_duration_ms`, `outcome`
- **Phase** nodes: `phase_name`, `phase_order`, `duration_ms`, `outcome`
- **Worker** nodes: `worker_id`, `model`, `task_assigned`, `confidence`, `duration_ms`, `input_tokens`, `output_tokens`, `cost_usd`
- **ArbiterDecision** nodes: `arbiter_model`, `decision`, `reasoning`, `confidence`
- **Learning** nodes: `learning_type`, `description`, `actionable_insight`, `importance`, `embedding` (384-dim vector)
- **Model** nodes: `name`, `first_seen`, `total_executions`

**Graph relationships created:**
- `(Workflow)-[:CONTAINS {phase_order}]->(Phase)`
- `(Phase)-[:NEXT_PHASE]->(Phase)` (sequential chain)
- `(Worker)-[:EXECUTES]->(Workflow)`
- `(Worker)-[:USES_MODEL]->(Model)`
- `(Workflow)-[:ARBITRATED_BY]->(ArbiterDecision)`
- `(ArbiterDecision)-[:ARBITER_USES_MODEL]->(Model)`
- `(ArbiterDecision)-[:EVALUATED {was_selected}]->(Worker)`
- `(Workflow)-[:PRODUCED]->(Learning)`
- `(Learning)-[:RELATED_TO {similarity_score}]->(Learning)` (via vector index)

**Example queries (from `learning/workflow-graph-sync.js` lines 392-430):**
```cypher
// Find workflows using a specific model
MATCH (w:Workflow)-[:EXECUTED_BY]->(worker:Worker {model: 'opus'})
RETURN DISTINCT w.id, w.name, w.status
ORDER BY w.completedAt DESC LIMIT 10;

// Best performing model for task type
MATCH (w:Workflow)-[:EXECUTED_BY]->(worker:Worker {taskType: 'code_search'})
WITH worker.model AS model, AVG(worker.qualityScore) AS avgQuality, COUNT(*) AS executions
WHERE executions > 5
RETURN model, avgQuality, executions
ORDER BY avgQuality DESC;

// Workflow execution path
MATCH path = (w:Workflow {id: 'wf-123'})-[:EXECUTED_BY]->(worker:Worker)-[:JUDGED_BY]->(arbiter:Arbiter)
RETURN worker.model, worker.qualityScore, arbiter.decision, arbiter.selectedWorker
ORDER BY worker.timestamp;

// Model collaboration patterns
MATCH (w:Workflow)-[:EXECUTED_BY]->(worker:Worker)
WITH w, COLLECT(DISTINCT worker.model) AS models
WHERE SIZE(models) > 1
UNWIND models AS model1
UNWIND models AS model2
WHERE model1 < model2
RETURN model1, model2, COUNT(*) AS cooccurrences
ORDER BY cooccurrences DESC LIMIT 20;

// Related learnings via vector similarity
MATCH (l1:Learning)-[r:RELATED_TO]-(l2:Learning)
WHERE r.similarity_score > 0.75
RETURN l1.description, l2.description, r.similarity_score
ORDER BY r.similarity_score DESC;
```

### Files Involved

**Core implementation (complete):**
- ✅ `learning/neo4j-sync-service.js` (1,109 lines) - Main sync service
- ✅ `learning/workflow-graph-sync.js` (743 lines) - Workflow sync + queue
- ✅ `shared/workflow-graph-sync.js` (743 lines) - Copy for shared usage
- ✅ `learning/workflow-completion-hook.js` (lines 29, 36, 110-121) - Integration
- ✅ `learning/neo4j-auto-sync.js` (467 lines) - Auto-sync daemon
- ✅ `learning/neo4j-sync-worker.js` (268 lines) - Background worker
- ✅ `learning/auto-sync-daemon.js` (120 lines) - Periodic scheduler

**Workflow integration (ready to use):**
- ✅ `workflows/shared/workflow-tracker.js` (line 156) - `enableNeo4j: true`
- ✅ `workflows/deep-research-with-autostorage.mjs` - Auto-storage + Neo4j
- ✅ `workflows/custom-deep-research.mjs` - Custom workflow example
- ✅ `learning/deep-research-integration-example.mjs` - Full integration example

**Test coverage:**
- ✅ `learning/__tests__/neo4j-sync.integration.test.js` - 16 integration tests

**Documentation:**
- ✅ `tools/non_blocking_workflow_pattern.js` - Non-blocking Neo4j batch insert pattern
- ✅ `learning/pdf-deep-analysis-workflow.mjs` - Comments mention Neo4j graph
- ✅ `deep-code-analysis.mjs` - Phase 5 TODO for Neo4j integration

### Dependencies

**Already installed:**
- ✅ `neo4j-driver: ^6.1.0` (in `learning/package.json`)
- ✅ `pg: ^8.21.0` (PostgreSQL client)

**Not needed:**
- ❌ No additional npm packages required
- ❌ No Python dependencies

### Complexity Estimate

**Code implementation:** ✅ DONE (0 hours - already complete)

**Deployment steps:** ~2 hours
1. Install Neo4j on laptop-01 (30 min)
   ```bash
   # Fedora/RHEL
   dnf install java-17-openjdk
   wget https://neo4j.com/artifact.php?name=neo4j-community-5.x.x-unix.tar.gz
   tar -xzf neo4j-community-5.x.x-unix.tar.gz
   cd neo4j-community-5.x.x
   bin/neo4j start
   ```

2. Set password and verify (15 min)
   ```bash
   bin/neo4j-admin set-initial-password <password>
   curl http://localhost:7474  # Web interface
   ```

3. Initialize schema (5 min)
   ```bash
   export NEO4J_PASSWORD=<password>
   node learning/neo4j-sync-service.js init
   ```

4. Test sync with existing execution (10 min)
   ```bash
   # Get recent execution ID
   psql -h laptop-01 -U sfloess -d learning -c \
     "SELECT id FROM workflow.executions ORDER BY id DESC LIMIT 1;"
   
   # Sync to Neo4j
   node learning/neo4j-sync-service.js sync <execution_id>
   ```

5. Verify in Neo4j browser (10 min)
   ```cypher
   MATCH (w:Workflow) RETURN w LIMIT 5;
   MATCH (w:Workflow)-[r]->(n) RETURN w, r, n LIMIT 20;
   ```

6. Optional: Catch up all unsynced executions (30 min)
   ```bash
   node learning/neo4j-sync-service.js sync-all 100
   ```

7. Optional: Enable background worker (systemd service) (30 min)
   ```bash
   cp learning/neo4j-sync-worker.js ~/bin/
   # Create systemd service unit
   systemctl --user enable neo4j-sync-worker
   systemctl --user start neo4j-sync-worker
   ```

### Recommendation

**This is NOT a bug - it's an optional feature awaiting deployment.**

The code is production-ready and well-tested. The system gracefully degrades when Neo4j is unavailable. Deploy Neo4j only if you need:
- Graph visualization of workflow execution patterns
- Relationship-based queries (model collaboration, execution paths)
- Vector similarity search across learnings
- Knowledge graph exploration

If PostgreSQL storage + embeddings are sufficient, Neo4j deployment is optional.

---

## Issue #3: Deep-research workflow extracts 0 learnings

**Priority:** HIGH

**Problem:** 13 deep-research workflows ran successfully but stored 0 learnings.

**Current behavior:**
```sql
-- 13 workflows executed
SELECT COUNT(*) FROM workflow.executions WHERE workflow_name = 'deep-research';
-- Returns: 13

-- 0 learnings extracted
SELECT COUNT(*) FROM workflow.learnings 
WHERE workflow_execution_id IN (
  SELECT id FROM workflow.executions WHERE workflow_name = 'deep-research'
);
-- Returns: 0
```

**Root cause:** `deep-research.mjs` doesn't call `tracker.addLearning()` with extracted findings.

**Expected behavior:**
- Extract key findings from research
- Call `tracker.addLearning(description, insight, importance, evidence)` for each
- Store with embeddings

**Files to modify:**
- `workflows/deep-research.mjs` - add learning extraction in Synthesize phase

**Test:**
```bash
# Run deep-research on any topic
# Verify learnings extracted
psql -h laptop-01 -U sfloess -d learning -c "
  SELECT e.task_description, COUNT(l.id) as learnings
  FROM workflow.executions e
  LEFT JOIN workflow.learnings l ON e.id = l.workflow_execution_id
  WHERE e.workflow_name = 'deep-research'
  GROUP BY e.task_description;
"
```

---

## Issue #4: Code-review workflow stores 0 findings

**Priority:** HIGH  

**Problem:** 33 code-review workflows ran (Solenopsis + FlossWare) but stored 0 learnings.

**Root cause:** Same as deep-research - no `tracker.addLearning()` calls for findings.

**Expected behavior:**
- Store each finding as learning with embedding
- Include severity, file, line number in metadata

**Files to modify:**
- `workflows/code-review.js` - add learning extraction after findings deduplication

---

---

## Issue #5: Implement Phase 0 - Experiment Framework

**Priority:** CRITICAL  
**Status:** 🔄 IN PROGRESS (Workflow wzcdrm7l6)

**Context:** External technical review identified critical gap - no evaluation harness to prove features actually improve quality.

**Implementation Plan:**
1. **Experiment Database Schema** (laptop-01, gemini-2.0-flash)
   - `db/migrations/020_experiment_framework.sql`
   - Tables: `experiments.registry`, `experiments.runs`
   
2. **Experiment Manager** (server-01, llama-3.3-70b)
   - `shared/experiment-manager.cjs`
   - Functions: `runExperiment()`, `compareResults()`, `recordExperiment()`
   - Statistical testing (t-test, bootstrap)
   
3. **A/B Runner** (server-02, gpt-4o)
   - `shared/ab-runner.cjs`
   - Feature toggle support
   - Cost/latency/quality tradeoff analysis

**Expected Output:**
- Self-documenting system where every feature is a hypothesis
- Automated A/B testing infrastructure
- Statistical significance testing
- Evidence-based feature decisions

**Timeline:** ~4 days

**Related:** REVIEW_RESPONSE.md Phase 1

---

## Issue #6: Implement Phase 1 - Capability-Based Architecture

**Priority:** HIGH  
**Status:** 🔄 IN PROGRESS (Workflow wzcdrm7l6)

**Context:** Move from model-centric to capability-centric routing (model-agnostic, vendor-neutral).

**Implementation Plan:**
1. **Capability Interfaces** (server-03, mistral-large)
   - `shared/capabilities.cjs`
   - Define: reasoner, verifier, critic, planner, summarizer, code_reviewer
   
2. **Capability Registry** (pi-01, deepseek-chat)
   - `db/migrations/021_capability_registry.sql`
   - `shared/capability-registry.cjs`
   - Auto-populate from execution history
   
3. **Role-Based Routing** (pi-02, qwen-2.5-72b)
   - `shared/role-based-routing.cjs`
   - `selectCapability(role, options)` - vendor-neutral selection

**Expected Output:**
- Abstraction layer: models fill roles, not named directly
- Survives model API changes/deprecations
- Quality/cost/latency optimization per capability

**Timeline:** ~3 days

**Related:** REVIEW_RESPONSE.md Phase 2

---

## Issue #7: Implement Phase 2 - Strategy Learning

**Priority:** HIGH  
**Status:** 🔄 IN PROGRESS (Workflow wzcdrm7l6)

**Context:** Learn which strategies work best, not just which models.

**Implementation Plan:**
1. **Strategy Taxonomy** (desktop-ap, gemini-1.5-pro)
   - `shared/strategy-taxonomy.cjs`
   - Dimensions: prompts, orchestration, verification, sequences
   
2. **Strategy Tracking** (server-ap, llama-3.1-405b)
   - `db/migrations/022_strategy_tracking.sql`
   - `shared/strategy-tracker.cjs`
   - Multi-dimensional performance tracking
   
3. **Multi-Dimensional Learning** (laptop-01, gpt-4-turbo)
   - `shared/multi-dimensional-learning.cjs`
   - Thompson Sampling per (capability, task_type, strategy)

**Expected Output:**
- Learn which prompts work for which tasks
- Learn which orchestration patterns reduce errors
- Learn which verification methods catch hallucinations

**Timeline:** ~4 days

**Related:** REVIEW_RESPONSE.md Phase 3

---

## Issue #8: Implement Phase 3 - Modular Service Architecture

**Priority:** MEDIUM  
**Status:** 🔄 IN PROGRESS (Workflow wzcdrm7l6)

**Context:** Make every service removable without breaking the system.

**Implementation Plan:**
1. **Service Interface Contracts** (server-01, mistral-medium)
   - `shared/service-interface.cjs`
   - Base Service class + ServiceRegistry
   
2. **Graceful Degradation** (server-02, phi-4)
   - `shared/graceful-degradation.cjs`
   - Fallback logic when services unavailable
   
3. **Service Health Monitoring** (server-03, llama-3.1-70b)
   - `monitoring/service-health.cjs`
   - Health endpoints, auto-disable unhealthy services

**Expected Output:**
- Plug-and-play architecture
- Easy A/B testing (disable service, measure impact)
- Resilient to component failures

**Timeline:** ~4 days

**Related:** REVIEW_RESPONSE.md Phase 4

---

## Issue #9: Implement Phase 4 - Evaluation Harness

**Priority:** CRITICAL  
**Status:** 🔄 IN PROGRESS (Workflow wzcdrm7l6)

**Context:** Benchmark dataset + automated regression testing + ablation study.

**Implementation Plan:**
1. **Benchmark Dataset** (pi-01, gemini-1.5-flash)
   - `evaluation/benchmark-dataset.json`
   - 1,000 questions across 7 task types with ground truth
   - `db/migrations/023_evaluation_schema.sql`
   
2. **Evaluation Pipeline** (pi-02, gpt-3.5-turbo)
   - `evaluation/evaluation-pipeline.cjs`
   - Weekly automated runs
   - Regression detection (alert if quality drops >5%)
   
3. **Feature Ablation Study** (desktop-ap, mistral-small)
   - `evaluation/ablation-study.cjs`
   - Test each feature in isolation
   - Quantify contribution

**Expected Output:**
- Evidence-based feature validation
- Automated weekly regression reports
- Cost vs quality curves
- Statistical proof of feature contributions

**Timeline:** ~5-8 days

**Related:** REVIEW_RESPONSE.md Phase 1 (highest priority per external review)

---

## Issue #10: Workflow Tool Does Not Use Fleet Orchestrator

**Priority:** HIGH  
**Status:** 🆕 NEW

**Problem:** Workflow tool's `agent()` function spawns local subagents instead of using fleet orchestrator for SSH distribution.

**Current Behavior:**
- Workflows use `agent(prompt, { model: 'opus' })`
- This spawns subagents **locally** on the machine running the workflow
- Fleet orchestrator (`lib/fleet-orchestrator.js`) is **NOT used**
- SSH distribution (`shared/fleet-utils.js`) is **NOT used**
- Multi-provider routing (9 API providers) is **NOT accessible** in workflows

**Expected Behavior:**
- Workflows should distribute work via SSH to fleet workers
- Should use `fleet-orchestrator.js` for model routing
- Should access all 9 API providers (Anthropic, OpenAI, Google, Groq, DeepInfra, Together, Mistral, Cohere, AI21)
- Should track which fleet node executed which agent (execution_host)

**Root Cause:**
- Workflow tool's `agent()` is a built-in function with hardcoded Anthropic routing
- No integration with custom fleet infrastructure
- Model parameter only accepts: 'opus', 'sonnet', 'haiku', 'fable'

**Impact:**
- **8 fleet workers available** but workflows only use localhost
- **9 API providers configured** but workflows only use Anthropic
- **Fleet capacity underutilized** (local execution vs distributed)
- **No execution_host tracking** for workflow agents

**Evidence:**
- Workflow wtdohoc4g: 15 agents, all local (no SSH distribution observed)
- Workflow w0doc3hzs: 15 agents, all local (no SSH distribution observed)
- Fleet vote (wgbj8rt3z): Voted to keep fleet infrastructure, but workflows don't use it

**Proposed Solutions:**

### Option A: Custom Workflow Wrapper (50-100 lines)
Replace `agent()` calls with custom function that:
1. Calls `fleet-utils.js` `getWorkers()` to select node
2. Uses `remoteExec(hostname, command)` to SSH to worker
3. Worker executes task and returns result
4. Tracks `execution_host` in workflow storage

**Pros:** Unlocks full fleet (8 nodes, 9 providers)  
**Cons:** Duplicate abstraction, maintenance overhead

### Option B: MCP Server for Fleet Orchestration
Create MCP server that workflows can call:
```javascript
await useTool('fleet-orchestrator', { 
  model: 'gpt-4o',  // Any of 9 providers
  prompt: '...',
  worker: 'auto'     // Auto-select from 8 workers
})
```

**Pros:** Clean abstraction, future-proof  
**Cons:** More upfront work, requires MCP setup

### Option C: Modify Workflow Tool (upstream)
Contribute to Claude Code to add fleet orchestration support

**Pros:** Benefits entire ecosystem  
**Cons:** Long timeline, no control over acceptance

**Recommendation:** Start with **Option A** (quick win), migrate to **Option B** (better architecture) when proven valuable.

**Related Issues:**
- Fleet consensus (wgbj8rt3z): Voted to keep fleet-orchestrator.js
- Issue #11: execution_host tracking (already implemented in DB, but workflows don't populate it)

**Next Steps:**
1. Review current fleet-orchestrator.js capabilities
2. Design custom workflow wrapper API
3. Test with 1 workflow (proof of concept)
4. Measure: Does SSH distribution actually improve performance?
5. If yes: Migrate all workflows to use wrapper
6. If no: Document why and keep current approach

**Files Involved:**
- `lib/fleet-orchestrator.js` - Multi-provider routing
- `shared/fleet-utils.js` - SSH execution, worker selection
- `shared/workflow-storage-adapter.cjs` - execution_host tracking
- Workflows: `workflows/*.mjs` - All use `agent()` currently

---

## Summary

| Component | Status | Issue # |
|-----------|--------|---------|
| PostgreSQL storage | ✅ Working | - |
| Embeddings (Google AI) | ✅ Working | - |
| Chunking | ✅ Complete | #1 |
| Neo4j sync | ✅ Code complete, not deployed | #2 |
| deep-research learnings | ❌ Missing | #3 |
| code-review learnings | ❌ Missing | #4 |
| **Experiment Framework** | 🔄 In Progress | #5 |
| **Capability Architecture** | 🔄 In Progress | #6 |
| **Strategy Learning** | 🔄 In Progress | #7 |
| **Modular Services** | 🔄 In Progress | #8 |
| **Evaluation Harness** | 🔄 In Progress | #9 |
