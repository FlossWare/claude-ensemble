# Workflow Result Storage System Design

## Overview

Automatic, multi-layer persistence system for workflow execution data with:
- PostgreSQL (vectorDB) for semantic search + analytics
- Neo4j for workflow dependency graphs + relationship analysis
- Automatic hook integration (no manual instrumentation required)
- 384-dim embeddings for semantic search (via OpenAI text-embedding-3-small)

**System Target:** Store ALL workflow outputs after completion
- Worker outputs (quality scores, token usage, reasoning)
- Arbiter decisions (consensus votes, final reasoning)
- Workflow metadata (duration, cost, dependencies)
- Aggregated metrics (family metrics, synergy scores)

---

## Part 1: PostgreSQL Schema (vectorDB + Analytics)

### 1.1 Core Tables

#### `workflows.executions` (Main Execution Records)
Stores complete workflow run metadata.

```sql
CREATE SCHEMA workflows;

CREATE TABLE workflows.executions (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  execution_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
  parent_execution_id UUID,  -- For nested/chained workflows
  workflow_name VARCHAR(255) NOT NULL,  -- e.g., 'ai-consensus-debate'
  
  -- Timing
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP WITH TIME ZONE,
  duration_ms BIGINT,
  
  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'in_progress',  -- in_progress, success, failed, timeout
  error_message TEXT,
  error_stack TEXT,
  
  -- Task Context
  task_description TEXT,
  task_type VARCHAR(100),  -- e.g., 'code-review', 'deep-research'
  parameters JSONB,  -- Input parameters (embeddings skipped)
  
  -- Results Summary
  worker_count INT,
  arbiter_model VARCHAR(100),
  final_quality_score NUMERIC(5,4),  -- 0.0000 to 1.0000
  final_confidence NUMERIC(5,4),
  
  -- Costs & Tokens
  total_cost_usd NUMERIC(10,6),
  total_input_tokens INT,
  total_output_tokens INT,
  
  -- Metrics
  synergy_score NUMERIC(5,4),  -- How well workers complement arbiter
  diversity_score NUMERIC(5,4),  -- Model variety effectiveness
  consistency_score NUMERIC(5,4),  -- Agreement among workers
  
  -- Embedding (for semantic search)
  summary_embedding vector(384),  -- Summarized task + results
  
  -- Metadata
  tags JSONB DEFAULT '{}'::jsonb,  -- Custom tags: {environment, branch, version}
  metadata JSONB DEFAULT '{}'::jsonb,
  
  CONSTRAINT valid_status CHECK (status IN ('in_progress', 'success', 'failed', 'timeout'))
);

CREATE INDEX idx_workflows_executions_workflow ON workflows.executions(workflow_name);
CREATE INDEX idx_workflows_executions_status ON workflows.executions(status);
CREATE INDEX idx_workflows_executions_started ON workflows.executions(started_at DESC);
CREATE INDEX idx_workflows_executions_parent ON workflows.executions(parent_execution_id) WHERE parent_execution_id IS NOT NULL;
CREATE INDEX idx_workflows_executions_embedding ON workflows.executions USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists=100);
```

#### `workflows.worker_results` (Individual Worker Outputs)
Stores each worker's contribution in a multi-AI consensus workflow.

```sql
CREATE TABLE workflows.worker_results (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
  worker_id UUID NOT NULL DEFAULT gen_random_uuid(),
  sequence INT NOT NULL,  -- Order in workflow (1, 2, 3...)
  
  -- Model Info
  model_name VARCHAR(100) NOT NULL,  -- e.g., 'opus', 'sonnet'
  model_provider VARCHAR(50),  -- 'anthropic', 'openai', 'google', etc.
  model_role VARCHAR(20) NOT NULL DEFAULT 'worker',  -- worker, arbiter, validator
  
  -- Execution
  phase VARCHAR(100),  -- e.g., 'Proposal', 'Rebuttal', 'Final'
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP WITH TIME ZONE,
  duration_ms BIGINT,
  
  -- Quality Metrics
  quality_score NUMERIC(5,4),  -- Worker's output quality
  confidence NUMERIC(5,4),  -- Worker's stated confidence
  was_selected BOOLEAN DEFAULT FALSE,  -- Did arbiter select this output?
  selection_reason TEXT,  -- Why selected (or not)
  
  -- Tokens & Cost
  input_tokens INT NOT NULL DEFAULT 0,
  output_tokens INT NOT NULL DEFAULT 0,
  cost_usd NUMERIC(10,6),
  
  -- Output Content
  output_text TEXT,  -- Actual worker output (reasonings, analysis)
  output_summary TEXT,  -- Short summary
  output_embedding vector(384),  -- Full output semantic vector
  
  -- Comparison to Final
  divergence_from_final NUMERIC(5,4),  -- How different from arbiter's final?
  alignment_score NUMERIC(5,4),  -- Agreement with other workers
  
  -- Error Handling
  status VARCHAR(20) DEFAULT 'success',  -- success, error, timeout, invalid
  error_message TEXT,
  
  metadata JSONB DEFAULT '{}'::jsonb,
  
  CONSTRAINT valid_role CHECK (model_role IN ('worker', 'arbiter', 'validator'))
);

CREATE INDEX idx_worker_results_execution ON workflows.worker_results(execution_id);
CREATE INDEX idx_worker_results_model ON workflows.worker_results(model_name);
CREATE INDEX idx_worker_results_phase ON workflows.worker_results(phase);
CREATE INDEX idx_worker_results_embedding ON workflows.worker_results USING ivfflat (output_embedding vector_cosine_ops) WITH (lists=100);
```

#### `workflows.arbiter_decisions` (Consensus Logic)
Records how the arbiter made its final decision.

```sql
CREATE TABLE workflows.arbiter_decisions (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
  arbiter_id UUID NOT NULL DEFAULT gen_random_uuid(),
  
  -- Arbiter Info
  arbiter_model VARCHAR(100) NOT NULL,
  arbiter_provider VARCHAR(50),
  phase VARCHAR(100) DEFAULT 'Final',  -- Which phase arbiter ran
  
  -- Decision Making
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP WITH TIME ZONE,
  duration_ms BIGINT,
  
  -- Evaluation
  consensus_score NUMERIC(5,4),  -- How strong is consensus?
  agreement_ratio NUMERIC(5,4),  -- Fraction of workers who agree
  num_workers_evaluated INT,
  
  -- Selected Output
  selected_worker_id UUID,  -- Which worker (if any) was selected
  combined_output_text TEXT,  -- Synthesized output
  combined_output_summary TEXT,
  combined_output_embedding vector(384),
  
  -- Reasoning
  decision_reasoning TEXT,  -- Arbiter's explanation
  quality_rationale TEXT,  -- Why this quality score
  confidence_rationale TEXT,
  
  -- Scoring
  quality_score NUMERIC(5,4),
  confidence NUMERIC(5,4),
  
  -- Tokens
  input_tokens INT DEFAULT 0,
  output_tokens INT DEFAULT 0,
  cost_usd NUMERIC(10,6),
  
  -- Comparison metrics
  worker_scores JSONB,  -- {model_name -> quality_score} for ranking
  dissent_identified JSONB,  -- Which workers disagreed + why
  
  status VARCHAR(20) DEFAULT 'success',
  error_message TEXT,
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_arbiter_decisions_execution ON workflows.arbiter_decisions(execution_id);
CREATE INDEX idx_arbiter_decisions_model ON workflows.arbiter_decisions(arbiter_model);
CREATE INDEX idx_arbiter_decisions_embedding ON workflows.arbiter_decisions USING ivfflat (combined_output_embedding vector_cosine_ops) WITH (lists=100);
```

#### `workflows.model_combinations` (Synergy Tracking)
Records how specific model combinations performed together.

```sql
CREATE TABLE workflows.model_combinations (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
  combination_id UUID NOT NULL DEFAULT gen_random_uuid(),
  
  -- Model Set
  worker_models TEXT[] NOT NULL,  -- ARRAY of model names
  arbiter_model VARCHAR(100) NOT NULL,
  task_type VARCHAR(100),
  
  -- Frequency
  combination_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256(sorted_models + arbiter)
  num_uses INT DEFAULT 1,
  
  -- Performance
  last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  avg_quality_score NUMERIC(5,4),
  avg_consensus_score NUMERIC(5,4),
  
  -- Synergy
  synergy_score NUMERIC(5,4),  -- How well these models work together
  diversity_bonus NUMERIC(5,4),  -- Credit for architectural diversity
  consistency_across_runs NUMERIC(5,4),  -- Variance in quality
  
  -- Cost Efficiency
  total_cost_usd NUMERIC(10,6),
  avg_cost_per_execution NUMERIC(10,6),
  cost_per_quality_point NUMERIC(10,6),  -- cost / quality_score
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_combinations_hash ON workflows.model_combinations(combination_hash);
CREATE INDEX idx_combinations_task ON workflows.model_combinations(task_type);
CREATE INDEX idx_combinations_synergy ON workflows.model_combinations(synergy_score DESC);
```

#### `workflows.execution_phases` (Multi-Phase Tracking)
For workflows with explicit phases (scope → search → verify → synthesize).

```sql
CREATE TABLE workflows.execution_phases (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
  phase_name VARCHAR(100) NOT NULL,  -- e.g., 'scope', 'search', 'verify'
  
  -- Timing
  sequence INT NOT NULL,
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP WITH TIME ZONE,
  duration_ms BIGINT,
  
  -- Phase Output
  output_text TEXT,
  output_summary TEXT,
  output_embedding vector(384),
  
  -- Phase Metrics
  status VARCHAR(20) NOT NULL DEFAULT 'success',
  quality_score NUMERIC(5,4),
  confidence NUMERIC(5,4),
  
  -- Agents Involved
  models_used TEXT[] DEFAULT '{}',
  worker_count INT,
  
  -- Cost
  input_tokens INT DEFAULT 0,
  output_tokens INT DEFAULT 0,
  cost_usd NUMERIC(10,6),
  
  error_message TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  
  CONSTRAINT phases_must_be_ordered UNIQUE (execution_id, phase_name)
);

CREATE INDEX idx_phases_execution ON workflows.execution_phases(execution_id);
CREATE INDEX idx_phases_name ON workflows.execution_phases(phase_name);
CREATE INDEX idx_phases_embedding ON workflows.execution_phases USING ivfflat (output_embedding vector_cosine_ops) WITH (lists=100);
```

#### `workflows.feedback` (Outcome Recording)
Links workflow outputs to subsequent quality signals (user feedback, bug fixes, etc.).

```sql
CREATE TABLE workflows.feedback (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  feedback_id UUID NOT NULL DEFAULT gen_random_uuid(),
  execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
  
  -- Feedback Source
  feedback_type VARCHAR(50) NOT NULL,  -- manual_rating, automated_test, user_bug_report, code_execution_result
  feedback_source VARCHAR(100),  -- Which system provided feedback
  
  -- Timing
  collected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  relates_to_phase VARCHAR(100),
  
  -- Signal
  rating NUMERIC(5,4),  -- 0-1 score
  success BOOLEAN,  -- Did the output actually work?
  notes TEXT,
  
  -- Improvement Tracking
  was_useful BOOLEAN,
  led_to_bug_fix BOOLEAN DEFAULT FALSE,
  issue_url TEXT,  -- Link to bug/issue if applicable
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_feedback_execution ON workflows.feedback(execution_id);
CREATE INDEX idx_feedback_type ON workflows.feedback(feedback_type);
CREATE INDEX idx_feedback_collected ON workflows.feedback(collected_at DESC);
```

### 1.2 Aggregation & Analytics Tables

#### `workflows.daily_metrics` (Rollups)
Pre-computed aggregates for performance dashboards.

```sql
CREATE TABLE workflows.daily_metrics (
  date DATE NOT NULL PRIMARY KEY,
  
  -- Volume
  execution_count INT,
  success_count INT,
  failure_count INT,
  
  -- Quality
  avg_quality_score NUMERIC(5,4),
  avg_consensus_score NUMERIC(5,4),
  p95_quality_score NUMERIC(5,4),
  
  -- Cost
  total_cost_usd NUMERIC(10,6),
  avg_cost_per_execution NUMERIC(10,6),
  
  -- Efficiency
  avg_duration_ms BIGINT,
  total_input_tokens BIGINT,
  total_output_tokens BIGINT,
  
  -- Model Usage
  model_usage JSONB,  -- {model_name -> {count, avg_quality}}
  
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_daily_metrics_date ON workflows.daily_metrics(date DESC);
```

#### `workflows.model_rankings` (Leaderboards)
Auto-updated rankings for model performance.

```sql
CREATE TABLE workflows.model_rankings (
  -- Identity
  id BIGSERIAL PRIMARY KEY,
  update_date DATE DEFAULT CURRENT_DATE,
  
  -- Model Info
  model_name VARCHAR(100) NOT NULL,
  model_provider VARCHAR(50),
  model_category VARCHAR(50),  -- worker, arbiter, all
  task_type VARCHAR(100),
  
  -- Ranking
  rank_position INT,
  
  -- Performance
  avg_quality NUMERIC(5,4),
  median_quality NUMERIC(5,4),
  p95_quality NUMERIC(5,4),
  success_rate NUMERIC(5,4),
  
  -- Usage
  execution_count INT,
  times_selected_by_arbiter INT,
  selection_rate NUMERIC(5,4),
  
  -- Tokens
  avg_input_tokens NUMERIC(10,0),
  avg_output_tokens NUMERIC(10,0),
  
  -- Cost
  total_cost_usd NUMERIC(10,6),
  avg_cost_per_execution NUMERIC(10,6),
  cost_per_quality_unit NUMERIC(10,6),
  
  CONSTRAINT unique_ranking UNIQUE (update_date, model_name, task_type)
);

CREATE INDEX idx_rankings_date_task ON workflows.model_rankings(update_date DESC, task_type);
CREATE INDEX idx_rankings_quality ON workflows.model_rankings(rank_position, task_type);
```

---

## Part 2: Embedding Strategy

### 2.1 What Gets Embedded (384-dim via text-embedding-3-small)

**Execution Summary Embedding** (`workflows.executions.summary_embedding`):
```
[task_description] + [model list] + [phase names] + [final quality] + [key findings]

Example chunk (before embedding):
"Task: Code security review for authentication module using models opus,sonnet,haiku.
Phases: analysis, finding-extraction, remediation.
Final quality: 0.94. Key findings: SQL injection in login, XSS in form validation, timing attack in password check."
```

Chunk size: 1000-2000 tokens (fits well within embedding context)

**Worker Output Embedding** (`workflows.worker_results.output_embedding`):
```
[model name] + [phase] + [output summary]

Example:
"Model: opus, Phase: Proposal, Finding: SQL injection vulnerability in user authentication endpoint, recommendation: parameterized queries"
```

Chunk size: 500-1000 tokens

**Arbiter Decision Embedding** (`workflows.arbiter_decisions.combined_output_embedding`):
```
[arbiter model] + [consensus reasoning] + [selected worker rationale] + [combined output]

Example:
"Arbiter: gemini selected opus for best explanation of SQL injection risk. Consensus: 0.87 agreement on authentication bypass risk. Final recommendation: implement WAF rules plus code refactor."
```

Chunk size: 1000-2000 tokens

**Phase Output Embedding** (`workflows.execution_phases.output_embedding`):
```
[phase name] + [phase output] + [metrics]

Example:
"Phase: verification. Output: Confirmed 3 high-risk vulns via adversarial testing. Metrics: confidence 0.92, 5 test cases passed."
```

### 2.2 Embedding Generation Points

Embeddings inserted at workflow completion via the storage hook (automatic, no manual code needed).

Implementation in `workflow-result-storage.js`:
```javascript
// Generate summary embedding
const summaryText = `Task: ${task.description}
Models: ${workerModels.join(', ')}
Phases: ${phaseNames.join(', ')}
Quality: ${finalQuality}
Key findings: ${extractKeyFindings(outputs)}`;

const summaryEmbedding = await generateEmbedding(summaryText, 384);

// Generate worker embeddings
for (const worker of workers) {
  const workerText = `Model: ${worker.model}
Phase: ${worker.phase}
Output: ${worker.output_summary}`;
  worker.output_embedding = await generateEmbedding(workerText, 384);
}
```

### 2.3 Semantic Search Examples

```sql
-- Find similar past investigations on authentication
SELECT execution_id, workflow_name, final_quality_score
FROM workflows.executions
WHERE summary_embedding <-> (
  SELECT CAST(embedding AS vector) FROM ai.embeddings 
  WHERE text = 'authentication vulnerability research'
) < 0.2  -- Cosine distance < 0.2 = very similar
ORDER BY summary_embedding <-> (...)
LIMIT 10;

-- Find worker outputs similar to current investigation
SELECT worker_id, model_name, output_summary, quality_score
FROM workflows.worker_results
WHERE output_embedding <-> (
  SELECT CAST(embedding AS vector) FROM ai.embeddings 
  WHERE text = 'SQL injection in login endpoint'
) < 0.3
ORDER BY quality_score DESC
LIMIT 5;
```

---

## Part 3: Neo4j Graph Schema

### 3.1 Node Types

```cypher
-- Execution node (workflow run)
CREATE (:Execution {
  executionId: UUID,
  workflowName: String,
  taskType: String,
  status: String,  -- success, failed
  qualityScore: Float,
  consensusScore: Float,
  startedAt: DateTime,
  completedAt: DateTime,
  durationMs: Long,
  totalCostUsd: Float
})

-- Worker node (model in a specific role)
CREATE (:Worker {
  workerId: UUID,
  modelName: String,  -- opus, sonnet, etc.
  modelProvider: String,  -- anthropic, openai, google
  phase: String,  -- Proposal, Rebuttal, Decision
  qualityScore: Float,
  confidence: Float,
  wasSelected: Boolean
})

-- Arbiter node
CREATE (:Arbiter {
  arbiterId: UUID,
  modelName: String,
  consensusScore: Float,
  decisionReasoning: String,
  qualityScore: Float
})

-- ModelCombination node (synergy tracking)
CREATE (:ModelCombination {
  combinationHash: String,  -- SHA256 of sorted models
  workerModels: [String],
  arbiterModel: String,
  taskType: String,
  synergyScore: Float,
  diversityBonus: Float,
  numUses: Int,
  avgQualityScore: Float,
  costPerQualityUnit: Float
})

-- Phase node
CREATE (:Phase {
  phaseId: UUID,
  phaseName: String,  -- scope, search, verify
  sequence: Int,
  duration: Long,
  qualityScore: Float,
  modelsUsed: [String]
})

-- Task node (input domain)
CREATE (:Task {
  taskId: UUID,
  taskType: String,  -- code-review, deep-research
  categoryTag: String,  -- security, performance, documentation
  complexity: String,  -- simple, moderate, complex
  frequency: Int  -- How many times executed
})
```

### 3.2 Relationship Types

```cypher
-- Execution relationships
(:Execution)-[:RAN_WITH {sequence: 1}]->(:Worker)
(:Execution)-[:USED_ARBITER]->(:Arbiter)
(:Execution)-[:CONTAINED_PHASE {sequence: 1}]->(:Phase)
(:Execution)-[:FOR_TASK]->(:Task)
(:Execution)-[:PARENT_OF]->(:Execution)  -- Nested workflows

-- Worker relationships
(:Worker)-[:PRODUCED_OUTPUT]->(:WorkerOutput {score, embedding})
(:Worker)-[:USED_MODEL]->(:ModelCombination)
(:Worker)-[:AGREED_WITH {alignmentScore: 0.87}]->(:Worker)  -- Consensus links
(:Worker)-[:DISAGREED_WITH {divergence: 0.42}]->(:Worker)  -- Dissent

-- Arbiter relationships
(:Arbiter)-[:SELECTED {reason: "best explanation"}]->(:Worker)
(:Arbiter)-[:EVALUATED {count: 3}]->(:Worker)
(:Arbiter)-[:PRODUCED_DECISION]->(:ArbiterOutput {score, embedding})

-- Phase relationships
(:Phase)-[:EXECUTED_BY]->(:Worker)
(:Phase)-[:USED_MODELS {names: [...]}]->(:ModelCombination)
(:Phase)-[:INPUTTED_TO_NEXT_PHASE]->(:Phase)  -- Sequential phases

-- Quality relationships
(:Execution)-[:SCORED {qualityScore: 0.94, confidence: 0.91}]->(:Task)
(:ModelCombination)-[:PERFORMS_BETTER_THAN {delta: 0.05}]->(:ModelCombination)

-- Cost relationships
(:Execution)-[:COST {usdAmount: 0.15, inputTokens: 1500, outputTokens: 800}]->(:ModelCombination)

-- Feedback relationships
(:Execution)-[:RECEIVED_FEEDBACK {useful: true, leadToBugFix: true}]->(:Feedback)
```

### 3.3 Key Queries

```cypher
-- Find best model combinations for security reviews
MATCH (comb:ModelCombination)-[:PERFORMS_BETTER_THAN]->(:ModelCombination)
WHERE comb.taskType = 'code-review'
RETURN comb.workerModels, comb.arbiterModel, comb.synergyScore
ORDER BY comb.synergyScore DESC
LIMIT 5;

-- Build execution lineage (parent -> child workflows)
MATCH (parent:Execution)-[:PARENT_OF*]->(child:Execution)
WHERE parent.executionId = $executionId
RETURN parent, child, relationships;

-- Find consensus patterns (which workers tend to agree?)
MATCH (w1:Worker)-[agree:AGREED_WITH]->(:Worker)
RETURN w1.modelName, avg(agree.alignmentScore), count(agree)
ORDER BY avg(agree.alignmentScore) DESC;

-- Detect synergy (costly models + cheap models that work well together)
MATCH (combo:ModelCombination)
WHERE combo.costPerQualityUnit < 0.05
  AND combo.synergyScore > 0.80
  AND combo.numUses > 10
RETURN combo.workerModels, combo.arbiterModel
ORDER BY combo.numUses DESC;
```

---

## Part 4: Integration Points (Automatic Hooks)

### 4.1 Hook Location: Orchestrator Service (`orchestrator-service-enhanced.mjs`)

The orchestrator handles workflow completion. Add storage hook AFTER all workers + arbiter finish:

```javascript
// orchestrator-service-enhanced.mjs (existing code at line 357)

// INTEGRATION POINT 1: Import storage module
import { WorkflowResultStorage } from '../shared/workflow-result-storage.js';

class OrchestratorService {
  constructor() {
    this.router = null;
    this.learning = null;
    this.storage = null;  // NEW
    this.lastRefresh = null;
    this.requestCount = 0;
    this.errorCount = 0;
    this.feedbackCount = 0;
  }

  async initialize() {
    // ... existing code ...
    
    // INTEGRATION POINT 2: Initialize storage (lazy-load on first use)
    this.storage = new WorkflowResultStorage();
    console.log('[orchestrator] Workflow result storage initialized');
  }

  // INTEGRATION POINT 3: Store results on completion
  async storeWorkflowResults(workflowResult) {
    // Call after consensus/workflow execution completes
    try {
      const storageResult = await this.storage.store({
        executionId: workflowResult.execution_id,
        workflowName: workflowResult.workflow_name,
        status: workflowResult.status,
        workers: workflowResult.worker_results,
        arbiter: workflowResult.arbiter_decision,
        phases: workflowResult.phases,
        metrics: workflowResult.metrics,
        duration: workflowResult.duration_ms,
        taskDescription: workflowResult.task
      });
      
      this.feedbackCount++;
      return storageResult;
    } catch (err) {
      console.error('[orchestrator] Storage failed:', err.message);
      // Don't throw - graceful degradation
    }
  }
}
```

### 4.2 Hook Location 2: Consensus Workflows (ai-consensus*.js)

Workflows that call the arbiter should auto-save results:

```javascript
// In ai-consensus-debate.js, ai-consensus-weighted.js, etc.
// After arbiter.evaluate() completes:

import { WorkflowResultStorage } from '../shared/workflow-result-storage.js';

async function runConsensusWorkflow(task, workers, arbiter) {
  const storage = new WorkflowResultStorage();
  
  // ... worker execution ...
  const workerResults = await Promise.all(workers.map(w => w.execute(task)));
  
  // ... arbiter evaluation ...
  const arbiterDecision = await arbiter.evaluate(workerResults);
  
  // AUTOMATIC STORAGE (no manual code needed after setup)
  const executionId = crypto.randomUUID();
  await storage.store({
    executionId,
    workflowName: 'ai-consensus-debate',
    status: 'success',
    workers: workerResults,
    arbiter: arbiterDecision,
    metrics: {
      qualityScore: arbiterDecision.quality,
      consensusScore: arbiterDecision.consensus,
      duration: Date.now() - startTime
    }
  });
  
  return arbiterDecision;
}
```

### 4.3 Hook Location 3: Deep Research Workflow (workflows/deep-research.mjs)

Multi-phase workflows auto-save each phase:

```javascript
// workflows/deep-research.mjs (existing)

import { WorkflowResultStorage } from '../shared/workflow-result-storage.js';

async function executeWorkflow() {
  const storage = new WorkflowResultStorage();
  const executionId = generateUUID();
  
  // Phase 1: Scope
  const scopeResult = await phase1_scope();
  await storage.storePhase(executionId, {
    phaseName: 'scope',
    sequence: 1,
    output: scopeResult
  });
  
  // Phase 2: Search
  const searchResult = await phase2_search(scopeResult);
  await storage.storePhase(executionId, {
    phaseName: 'search',
    sequence: 2,
    output: searchResult
  });
  
  // ... more phases ...
  
  // Final: Store complete execution
  await storage.store({
    executionId,
    workflowName: 'ai-pdf-deep-research',
    status: 'success',
    phases: [scope, search, verify, synthesize],
    metrics: { qualityScore: 0.94, duration: 45000 }
  });
}
```

### 4.4 Hook Location 4: Feedback Recording (orchestrator-service-enhanced.mjs)

When feedback is recorded, link to source execution:

```javascript
// In OrchestratorService.handleFeedback (line 224)

async handleFeedback(req, res) {
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', async () => {
    try {
      const feedback = JSON.parse(body);
      const {
        model,
        execution_id,  // NEW: Link to original execution
        success = false,
        quality = 0.5,
        cost = 0,
        duration = 0,
        taskType = 'general',
        notes = ''  // NEW: User's feedback text
      } = feedback;

      // Record feedback in learning database
      await this.learning.recordFeedback(model, {
        execution_id,  // NEW
        success,
        quality,
        cost,
        duration,
        taskType,
        notes  // NEW
      });

      // INTEGRATION POINT: Store feedback with execution
      if (execution_id && this.storage) {
        await this.storage.storeFeedback({
          executionId: execution_id,
          feedbackType: 'manual_rating',
          rating: quality,
          success,
          notes
        });
      }

      this.feedbackCount++;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'recorded',
        model,
        feedback_count: this.feedbackCount
      }));
    } catch (err) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  });
}
```

---

## Part 5: Implementation: `workflow-result-storage.js`

Location: `/home/sfloess/Development/.../shared/workflow-result-storage.js`

### 5.1 Core Storage Class

```javascript
/**
 * Workflow Result Storage System
 * 
 * Automatically stores all workflow execution data:
 * - PostgreSQL: Vectorized search + analytics
 * - Neo4j: Relationship graphs + synergy detection
 * 
 * Usage:
 *   const storage = new WorkflowResultStorage();
 *   await storage.store({
 *     executionId: UUID,
 *     workflowName: 'ai-consensus-debate',
 *     workers: [...],
 *     arbiter: {...},
 *     metrics: {...}
 *   });
 */

import pg from 'pg';
import neo4j from 'neo4j-driver';
import { generateEmbedding } from './embeddings.js';

export class WorkflowResultStorage {
  constructor(options = {}) {
    this.pgPool = new pg.Pool({
      host: options.pgHost || 'localhost',
      port: options.pgPort || 5432,
      database: options.pgDatabase || 'learning',
      user: options.pgUser || process.env.USER,
      password: options.pgPassword || ''
    });

    this.neo4jDriver = neo4j.driver(
      options.neo4jUri || 'neo4j://localhost:7687',
      neo4j.auth.basic(
        options.neo4jUser || 'neo4j',
        options.neo4jPassword || 'password'
      )
    );

    this.ready = false;
  }

  /**
   * Initialize connections + ensure schema exists
   */
  async initialize() {
    if (this.ready) return;

    try {
      // Test PostgreSQL connection
      await this.pgPool.query('SELECT 1');
      console.log('[storage] PostgreSQL connected');

      // Initialize PostgreSQL schema
      await this._initPgSchema();

      // Test Neo4j connection
      const session = this.neo4jDriver.session();
      await session.run('RETURN 1');
      await session.close();
      console.log('[storage] Neo4j connected');

      // Initialize Neo4j schema (constraints + indexes)
      await this._initNeo4jSchema();

      this.ready = true;
    } catch (err) {
      console.error('[storage] Initialization failed:', err.message);
      // Graceful degradation: continue without storage
      this.ready = false;
    }
  }

  /**
   * Main API: Store complete workflow execution
   */
  async store(data) {
    if (!this.ready) await this.initialize();
    if (!this.ready) return { success: false, error: 'Storage unavailable' };

    const {
      executionId,
      workflowName,
      taskDescription,
      taskType,
      status,
      workers = [],
      arbiter,
      phases = [],
      metrics = {},
      parameters = {}
    } = data;

    try {
      // 1. Store execution + get embedding
      const executionRecord = await this._storeExecution({
        executionId,
        workflowName,
        taskDescription,
        taskType,
        status,
        workers,
        arbiter,
        phases,
        metrics,
        parameters
      });

      // 2. Store worker results
      const workerRecords = await Promise.all(
        workers.map((w, idx) => 
          this._storeWorkerResult(executionId, w, idx)
        )
      );

      // 3. Store arbiter decision
      const arbiterRecord = arbiter 
        ? await this._storeArbiterDecision(executionId, arbiter)
        : null;

      // 4. Store phases
      const phaseRecords = await Promise.all(
        phases.map((p, idx) =>
          this._storePhase(executionId, p, idx)
        )
      );

      // 5. Store model combination synergy
      const combinationRecord = await this._storeModelCombination({
        workerModels: workers.map(w => w.model_name),
        arbiterModel: arbiter?.model_name,
        taskType,
        metrics
      });

      // 6. Record in Neo4j for graph analysis
      await this._storeExecutionGraph({
        executionId,
        workflowName,
        workers,
        arbiter,
        phases,
        taskType,
        metrics
      });

      return {
        success: true,
        executionId,
        records: {
          execution: executionRecord,
          workers: workerRecords,
          arbiter: arbiterRecord,
          phases: phaseRecords,
          combination: combinationRecord
        }
      };
    } catch (err) {
      console.error('[storage] Store failed:', err.message);
      return { success: false, error: err.message };
    }
  }

  /**
   * Store single phase (for streaming/multi-phase workflows)
   */
  async storePhase(executionId, phase, sequence = 0) {
    if (!this.ready) await this.initialize();
    if (!this.ready) return { success: false };

    try {
      return await this._storePhase(executionId, phase, sequence);
    } catch (err) {
      console.error('[storage] storePhase failed:', err.message);
      return { success: false, error: err.message };
    }
  }

  /**
   * Store feedback linked to execution
   */
  async storeFeedback(feedbackData) {
    if (!this.ready) await this.initialize();
    if (!this.ready) return { success: false };

    const {
      executionId,
      feedbackType,
      rating,
      success,
      notes
    } = feedbackData;

    const query = `
      INSERT INTO workflows.feedback (
        execution_id, feedback_type, rating, success, notes
      ) VALUES ($1, $2, $3, $4, $5)
      RETURNING id, feedback_id
    `;

    try {
      const result = await this.pgPool.query(query, [
        executionId,
        feedbackType,
        rating,
        success,
        notes
      ]);

      return {
        success: true,
        feedbackId: result.rows[0].feedback_id
      };
    } catch (err) {
      console.error('[storage] storeFeedback failed:', err.message);
      return { success: false, error: err.message };
    }
  }

  /**
   * PRIVATE: Store execution record + generate embedding
   */
  async _storeExecution(data) {
    const {
      executionId,
      workflowName,
      taskDescription,
      taskType,
      status,
      workers,
      arbiter,
      phases,
      metrics,
      parameters
    } = data;

    // Generate summary embedding
    const summaryText = `
Task: ${taskDescription || 'unspecified'}
Workflow: ${workflowName}
Type: ${taskType}
Models: ${[...workers.map(w => w.model_name), arbiter?.model_name].filter(Boolean).join(', ')}
Phases: ${phases.map(p => p.phase_name).join(', ')}
Quality: ${metrics.quality_score || 0}
Duration: ${metrics.duration_ms}ms
    `.trim();

    const summaryEmbedding = await generateEmbedding(summaryText, 384);

    const query = `
      INSERT INTO workflows.executions (
        execution_id, workflow_name, task_description, task_type,
        status, worker_count, arbiter_model,
        final_quality_score, final_confidence,
        total_cost_usd, total_input_tokens, total_output_tokens,
        synergy_score, diversity_score, consistency_score,
        summary_embedding, parameters
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
      )
      RETURNING id, execution_id
    `;

    const result = await this.pgPool.query(query, [
      executionId,
      workflowName,
      taskDescription,
      taskType,
      status,
      workers.length,
      arbiter?.model_name,
      metrics.quality_score,
      metrics.confidence,
      metrics.total_cost_usd,
      metrics.total_input_tokens,
      metrics.total_output_tokens,
      metrics.synergy_score,
      metrics.diversity_score,
      metrics.consistency_score,
      summaryEmbedding,
      JSON.stringify(parameters)
    ]);

    return result.rows[0];
  }

  /**
   * PRIVATE: Store worker result
   */
  async _storeWorkerResult(executionId, worker, sequence) {
    const outputText = worker.output_text || worker.reasoning || '';
    const outputSummary = (outputText || '').substring(0, 500);

    const outputEmbedding = await generateEmbedding(
      `Model: ${worker.model_name}, Phase: ${worker.phase}, Output: ${outputSummary}`,
      384
    );

    const query = `
      INSERT INTO workflows.worker_results (
        execution_id, sequence, model_name, model_provider, model_role,
        phase, quality_score, confidence, was_selected,
        input_tokens, output_tokens, cost_usd, duration_ms,
        output_text, output_summary, output_embedding, status
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
      )
      RETURNING id, worker_id
    `;

    const result = await this.pgPool.query(query, [
      executionId,
      sequence,
      worker.model_name,
      worker.model_provider || 'anthropic',
      worker.model_role || 'worker',
      worker.phase,
      worker.quality_score || 0,
      worker.confidence || 0,
      worker.was_selected || false,
      worker.input_tokens || 0,
      worker.output_tokens || 0,
      worker.cost_usd || 0,
      worker.duration_ms || 0,
      outputText,
      outputSummary,
      outputEmbedding,
      worker.status || 'success'
    ]);

    return result.rows[0];
  }

  /**
   * PRIVATE: Store arbiter decision
   */
  async _storeArbiterDecision(executionId, arbiter) {
    const combinedText = arbiter.combined_output || arbiter.reasoning || '';
    const combinedSummary = combinedText.substring(0, 500);

    const combinedEmbedding = await generateEmbedding(
      `Arbiter: ${arbiter.model_name}, Decision: ${combinedSummary}`,
      384
    );

    const query = `
      INSERT INTO workflows.arbiter_decisions (
        execution_id, arbiter_model, arbiter_provider,
        consensus_score, agreement_ratio, num_workers_evaluated,
        combined_output_text, combined_output_summary, combined_output_embedding,
        decision_reasoning, quality_score, confidence,
        input_tokens, output_tokens, cost_usd,
        worker_scores, status
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
      )
      RETURNING id, arbiter_id
    `;

    const result = await this.pgPool.query(query, [
      executionId,
      arbiter.model_name,
      arbiter.model_provider || 'anthropic',
      arbiter.consensus_score || 0,
      arbiter.agreement_ratio || 0,
      arbiter.num_workers_evaluated || 0,
      combinedText,
      combinedSummary,
      combinedEmbedding,
      arbiter.decision_reasoning || '',
      arbiter.quality_score || 0,
      arbiter.confidence || 0,
      arbiter.input_tokens || 0,
      arbiter.output_tokens || 0,
      arbiter.cost_usd || 0,
      JSON.stringify(arbiter.worker_scores || {}),
      arbiter.status || 'success'
    ]);

    return result.rows[0];
  }

  /**
   * PRIVATE: Store phase
   */
  async _storePhase(executionId, phase, sequence) {
    const outputText = phase.output || phase.output_text || '';
    const outputSummary = outputText.substring(0, 500);

    const outputEmbedding = await generateEmbedding(
      `Phase: ${phase.phase_name}, Output: ${outputSummary}`,
      384
    );

    const query = `
      INSERT INTO workflows.execution_phases (
        execution_id, phase_name, sequence,
        output_text, output_summary, output_embedding,
        status, quality_score, confidence,
        models_used, worker_count,
        input_tokens, output_tokens, cost_usd
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
      )
      RETURNING id
    `;

    const result = await this.pgPool.query(query, [
      executionId,
      phase.phase_name,
      sequence,
      outputText,
      outputSummary,
      outputEmbedding,
      phase.status || 'success',
      phase.quality_score || 0,
      phase.confidence || 0,
      phase.models_used || [],
      phase.worker_count || 0,
      phase.input_tokens || 0,
      phase.output_tokens || 0,
      phase.cost_usd || 0
    ]);

    return result.rows[0];
  }

  /**
   * PRIVATE: Store/update model combination synergy
   */
  async _storeModelCombination(data) {
    const { workerModels, arbiterModel, taskType, metrics } = data;

    const combinationHash = this._hashCombination(
      [...workerModels, arbiterModel].sort()
    );

    const query = `
      INSERT INTO workflows.model_combinations (
        worker_models, arbiter_model, task_type,
        combination_hash,
        synergy_score, diversity_bonus, num_uses,
        avg_quality_score, total_cost_usd
      ) VALUES (
        $1, $2, $3, $4, $5, $6, 1, $7, $8
      )
      ON CONFLICT (combination_hash) DO UPDATE SET
        num_uses = num_uses + 1,
        avg_quality_score = (avg_quality_score * (num_uses - 1) + $7) / num_uses,
        total_cost_usd = total_cost_usd + $8,
        last_used_at = CURRENT_TIMESTAMP
      RETURNING id
    `;

    const result = await this.pgPool.query(query, [
      workerModels,
      arbiterModel,
      taskType,
      combinationHash,
      metrics.synergy_score || 0,
      metrics.diversity_score || 0,
      metrics.quality_score || 0,
      metrics.total_cost_usd || 0
    ]);

    return result.rows[0];
  }

  /**
   * PRIVATE: Store execution graph in Neo4j
   */
  async _storeExecutionGraph(data) {
    const {
      executionId,
      workflowName,
      workers,
      arbiter,
      phases,
      taskType,
      metrics
    } = data;

    const session = this.neo4jDriver.session();

    try {
      await session.run(`
        CREATE (exec:Execution {
          executionId: $executionId,
          workflowName: $workflowName,
          taskType: $taskType,
          qualityScore: $qualityScore,
          consensusScore: $consensusScore,
          duration: $duration,
          timestamp: timestamp()
        })
      `, {
        executionId,
        workflowName,
        taskType,
        qualityScore: metrics.quality_score || 0,
        consensusScore: metrics.consensus_score || 0,
        duration: metrics.duration_ms || 0
      });

      // Create worker nodes + relationships
      for (const w of workers) {
        await session.run(`
          MATCH (exec:Execution {executionId: $executionId})
          CREATE (worker:Worker {
            modelName: $modelName,
            phase: $phase,
            qualityScore: $qualityScore,
            wasSelected: $wasSelected
          })
          CREATE (exec)-[:RAN_WITH]->(worker)
        `, {
          executionId,
          modelName: w.model_name,
          phase: w.phase,
          qualityScore: w.quality_score || 0,
          wasSelected: w.was_selected || false
        });
      }

      // Create arbiter node + relationship
      if (arbiter) {
        await session.run(`
          MATCH (exec:Execution {executionId: $executionId})
          CREATE (arb:Arbiter {
            modelName: $modelName,
            consensusScore: $consensusScore
          })
          CREATE (exec)-[:USED_ARBITER]->(arb)
        `, {
          executionId,
          modelName: arbiter.model_name,
          consensusScore: arbiter.consensus_score || 0
        });
      }
    } finally {
      await session.close();
    }
  }

  /**
   * PRIVATE: Initialize PostgreSQL schema
   */
  async _initPgSchema() {
    // Check if schema exists
    const check = await this.pgPool.query(
      "SELECT 1 FROM pg_namespace WHERE nspname = 'workflows'"
    );

    if (check.rows.length > 0) return;

    // Execute schema creation (see Part 1 above)
    const schema = require('./workflow-storage-schema.sql');
    await this.pgPool.query(schema);
    console.log('[storage] PostgreSQL schema created');
  }

  /**
   * PRIVATE: Initialize Neo4j schema
   */
  async _initNeo4jSchema() {
    const session = this.neo4jDriver.session();

    try {
      // Create uniqueness constraints
      await session.run('CREATE CONSTRAINT FOR (e:Execution) REQUIRE e.executionId IS UNIQUE');
      await session.run('CREATE CONSTRAINT FOR (c:ModelCombination) REQUIRE c.combinationHash IS UNIQUE');
      
      // Create indexes
      await session.run('CREATE INDEX FOR (e:Execution) ON (e.workflowName)');
      await session.run('CREATE INDEX FOR (w:Worker) ON (w.modelName)');
      await session.run('CREATE INDEX FOR (a:Arbiter) ON (a.modelName)');
      
      console.log('[storage] Neo4j schema initialized');
    } catch (err) {
      // Constraints may already exist - ignore
      if (!err.message.includes('already exists')) {
        throw err;
      }
    } finally {
      await session.close();
    }
  }

  /**
   * PRIVATE: Hash model combination for uniqueness
   */
  _hashCombination(models) {
    const crypto = require('crypto');
    return crypto
      .createHash('sha256')
      .update(models.join(','))
      .digest('hex');
  }
}
```

---

## Part 6: Embedding Service (`embeddings.js`)

Lightweight wrapper around OpenAI text-embedding-3-small:

```javascript
import fetch from 'node-fetch';

const EMBEDDING_MODEL = 'text-embedding-3-small';
const EMBEDDING_DIM = 384;
const API_KEY = process.env.OPENAI_API_KEY;

export async function generateEmbedding(text, dimensions = 384) {
  if (!API_KEY) {
    console.warn('[embeddings] No OPENAI_API_KEY - returning zero vector');
    return new Array(dimensions).fill(0);
  }

  try {
    const response = await fetch('https://api.openai.com/v1/embeddings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`
      },
      body: JSON.stringify({
        model: EMBEDDING_MODEL,
        input: text,
        dimensions: dimensions
      })
    });

    if (!response.ok) {
      throw new Error(`OpenAI API error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.data[0].embedding;
  } catch (err) {
    console.error('[embeddings] Generation failed:', err.message);
    // Graceful degradation: return zero vector
    return new Array(dimensions).fill(0);
  }
}
```

---

## Part 7: Query Examples

### 7.1 Find Best Model Combinations

```sql
SELECT 
  worker_models,
  arbiter_model,
  task_type,
  synergy_score,
  num_uses,
  avg_quality_score,
  cost_per_quality_unit
FROM workflows.model_combinations
WHERE task_type = 'code-review'
  AND num_uses > 5
ORDER BY synergy_score DESC
LIMIT 10;
```

### 7.2 Similarity Search

```sql
-- Find similar past research on authentication
WITH query_embedding AS (
  SELECT embedding FROM ai.embeddings 
  WHERE text = 'authentication vulnerability analysis'
)
SELECT e.execution_id, e.workflow_name, e.final_quality_score,
       (e.summary_embedding <-> qe.embedding) as distance
FROM workflows.executions e, query_embedding qe
WHERE distance < 0.2
ORDER BY distance
LIMIT 10;
```

### 7.3 Model Leaderboard

```sql
SELECT 
  model_name,
  task_type,
  rank_position,
  avg_quality,
  success_rate,
  execution_count,
  avg_cost_per_execution
FROM workflows.model_rankings
WHERE update_date = CURRENT_DATE
  AND task_type = 'security-review'
ORDER BY rank_position
LIMIT 20;
```

### 7.4 Execution Lineage (Neo4j)

```cypher
MATCH (parent:Execution)-[:PARENT_OF*]->(child:Execution)
WHERE parent.executionId = $rootExecutionId
RETURN parent, child, relationships
ORDER BY parent.timestamp DESC;
```

### 7.5 Consensus Patterns

```cypher
MATCH (w1:Worker)-[agree:AGREED_WITH]->(:Worker)
RETURN w1.modelName, avg(agree.alignmentScore) as avg_alignment, count(agree) as agreement_count
ORDER BY avg_alignment DESC;
```

---

## Part 8: Maintenance & Operations

### 8.1 Daily Aggregation Job

Runs at 2 AM to compute `workflows.daily_metrics`:

```bash
#!/bin/bash
psql -h localhost -d learning -c "
INSERT INTO workflows.daily_metrics (date, execution_count, success_count, ...)
SELECT 
  DATE(started_at) as date,
  COUNT(*) as execution_count,
  COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
  ...
FROM workflows.executions
WHERE DATE(started_at) = CURRENT_DATE - INTERVAL 1 DAY
GROUP BY DATE(started_at)
ON CONFLICT (date) DO UPDATE SET ...
"
```

### 8.2 Embedding Backfill

For any executions without embeddings:

```bash
node backfill-embeddings.js --date 2026-06-19 --batch-size 100
```

### 8.3 Neo4j Relationship Inference

Periodically compute agreement/disagreement patterns:

```cypher
MATCH (exec:Execution)-[:RAN_WITH]->(w1:Worker), 
      (exec)-[:RAN_WITH]->(w2:Worker)
WHERE w1.modelName < w2.modelName
  AND w1.qualityScore > 0.8
  AND w2.qualityScore > 0.8
CREATE (w1)-[:AGREED_WITH {alignmentScore: 0.85}]->(w2)
```

### 8.4 Monitoring

```sql
-- Check storage health
SELECT 
  'executions' as table,
  COUNT(*) as record_count,
  MAX(started_at) as latest,
  COUNT(CASE WHEN status = 'success' THEN 1 END)::float / COUNT(*) as success_rate
FROM workflows.executions
UNION ALL
SELECT 
  'worker_results',
  COUNT(*),
  MAX(started_at),
  COUNT(CASE WHEN status = 'success' THEN 1 END)::float / COUNT(*)
FROM workflows.worker_results
UNION ALL
SELECT
  'feedback',
  COUNT(*),
  MAX(collected_at),
  COUNT(CASE WHEN was_useful THEN 1 END)::float / COUNT(*)
FROM workflows.feedback;
```

---

## Summary Table

| Component | Technology | Purpose | Key Feature |
|-----------|------------|---------|------------|
| **workflows.executions** | PostgreSQL | Main execution record | 384-dim embedding for similarity search |
| **workflows.worker_results** | PostgreSQL | Individual worker outputs | Tracks consensus alignment + dissent |
| **workflows.arbiter_decisions** | PostgreSQL | Consensus voting | Decision reasoning + worker scoring |
| **workflows.model_combinations** | PostgreSQL | Synergy tracking | Cost-per-quality efficiency analysis |
| **workflows.execution_phases** | PostgreSQL | Multi-phase workflows | Streaming phase-by-phase capture |
| **Execution Nodes** | Neo4j | Graph structure | Relationship between runs |
| **Worker Nodes** | Neo4j | Model behavior | Agreement/disagreement patterns |
| **AGREED_WITH/DISAGREED_WITH** | Neo4j | Consensus patterns | Find complementary models |
| **Storage Hook** | JavaScript | Auto-persistence | Zero manual instrumentation |
| **text-embedding-3-small** | OpenAI | Semantic search | 384-dim vectors, $0.02/1M tokens |

---

## Integration Checklist

- [ ] Create PostgreSQL schema (run SQL from Part 1)
- [ ] Create Neo4j schema (run Cypher from Part 3)
- [ ] Create `workflow-result-storage.js` (Part 5 implementation)
- [ ] Create `embeddings.js` (Part 6)
- [ ] Set `OPENAI_API_KEY` environment variable
- [ ] Hook into orchestrator-service-enhanced.mjs (Part 4.1)
- [ ] Hook into ai-consensus-*.js workflows (Part 4.2)
- [ ] Hook into workflows/deep-research.mjs (Part 4.3)
- [ ] Add feedback linking to handleFeedback (Part 4.4)
- [ ] Set up daily aggregation cron job (Part 8.1)
- [ ] Enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Monitor storage health daily (Part 8.4)

