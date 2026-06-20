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

**Problem:** Neo4j sync has `enableNeo4j: true` flag but sync is disabled (TODO comment).

**Current behavior:**
- Line 92-95 of `workflow-completion-hook.js` has TODO comment
- No graph relationships created
- No knowledge graph visualization
- No relationship-based queries

**Expected behavior:**
- CREATE Workflow nodes
- CREATE Phase nodes → CONTAINS relationships
- CREATE Worker nodes → EXECUTES relationships
- CREATE Learning nodes → PRODUCED relationships
- CREATE RELATED_TO relationships between similar learnings (using embedding similarity)

**Files to modify:**
- `learning/workflow-graph-sync.js` - implement `Neo4jSyncService` class
- `learning/workflow-completion-hook.js` - uncomment line 92-95, call sync

**Environment:**
```bash
export NEO4J_URI=bolt://laptop-01:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=<password>
```

**Test:**
```cypher
// Query workflow graph
MATCH (w:Workflow {name: 'code-review'})-[:CONTAINS]->(p:Phase)
RETURN w.id, p.name, p.duration_ms
ORDER BY p.order;

// Find related learnings
MATCH (l1:Learning)-[r:RELATED_TO]-(l2:Learning)
WHERE r.similarity > 0.8
RETURN l1.description, l2.description, r.similarity;
```

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

## Summary

| Component | Status | Issue # |
|-----------|--------|---------|
| PostgreSQL storage | ✅ Working | - |
| Embeddings (Google AI) | ✅ Working | - |
| Chunking | ❌ Missing | #1 |
| Neo4j sync | ❌ Missing | #2 |
| deep-research learnings | ❌ Missing | #3 |
| code-review learnings | ❌ Missing | #4 |
