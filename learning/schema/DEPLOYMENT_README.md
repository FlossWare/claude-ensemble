# Workflows Schema Deployment Guide

## Step 1: PostgreSQL Schema Creation (COMPLETED)

**Status:** Schema DDL file created ✅  
**Location:** `/home/sfloess/.claude/learning/schema/workflows-schema.sql`  
**Target Database:** `learning` on `laptop-01`  
**Estimated Time:** 5 minutes

## What Was Created

### 1. Schema File (workflows-schema.sql)

Complete PostgreSQL DDL script containing:

**Tables: 10**
1. `workflows.executions` - Main workflow execution records
2. `workflows.worker_results` - Individual worker outputs
3. `workflows.arbiter_decisions` - Arbiter final decisions
4. `workflows.execution_phases` - Multi-phase workflow tracking
5. `workflows.feedback` - User feedback on results
6. `workflows.model_combinations` - Successful model combinations
7. `workflows.learnings` - Extracted learnings with embeddings
8. `workflows.execution_embeddings` - Vector embeddings for similarity search

**Materialized Views: 2**
1. `workflows.summary` - Workflow performance metrics
2. `workflows.model_performance` - Per-model statistics

**Vector Indexes (HNSW): 4**
1. `idx_learnings_embedding` - Semantic search on learnings (768-dim)
2. `idx_execution_embeddings_input` - Search by input prompt
3. `idx_execution_embeddings_output` - Search by output result
4. `idx_execution_embeddings_context` - Search by combined context

**Helper Functions: 5**
1. `refresh_views()` - Update materialized views
2. `find_similar_executions()` - Semantic search for similar workflows
3. `find_relevant_learnings()` - Find learnings by embedding similarity
4. `get_best_combination()` - Get optimal model combinations
5. Auto-update triggers (4 triggers for duration/summary calculations)

**Features:**
- pgvector extension for 768-dimensional embeddings (sentence-transformers)
- HNSW indexes for O(log n) similarity search
- Auto-calculation of durations, summaries, and worker counts
- Cascading deletes for data integrity
- JSONB for flexible metadata storage
- Prepared for multi-user scenarios (permissions granted)

### 2. Verification Script (verify-schema.sh)

**Location:** `/home/sfloess/.claude/learning/schema/verify-schema.sh`  
**Purpose:** Automated deployment and verification

## Manual Deployment Instructions

If the verification script didn't run automatically, deploy manually:

### Option 1: Direct psql (if on laptop-01)

```bash
psql -U sfloess -d learning -f /home/sfloess/.claude/learning/schema/workflows-schema.sql
```

### Option 2: Remote psql (if on different host)

```bash
psql -h laptop-01 -U sfloess -d learning -f /home/sfloess/.claude/learning/schema/workflows-schema.sql
```

### Option 3: Using the verification script

```bash
chmod +x /home/sfloess/.claude/learning/schema/verify-schema.sh
/home/sfloess/.claude/learning/schema/verify-schema.sh
```

## Verification Queries

After deployment, verify the schema:

### Check pgvector extension
```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

### Check schema exists
```sql
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'workflows';
```

### List all tables
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'workflows' 
ORDER BY table_name;
```

Expected output:
- arbiter_decisions
- execution_embeddings
- execution_phases
- executions
- feedback
- learnings
- model_combinations
- worker_results

### List materialized views
```sql
SELECT matviewname 
FROM pg_matviews 
WHERE schemaname = 'workflows' 
ORDER BY matviewname;
```

Expected output:
- model_performance
- summary

### Check HNSW indexes
```sql
SELECT indexname, tablename 
FROM pg_indexes 
WHERE schemaname = 'workflows' 
  AND indexname LIKE '%embedding%' 
ORDER BY indexname;
```

Expected output:
- idx_execution_embeddings_context
- idx_execution_embeddings_input
- idx_execution_embeddings_output
- idx_learnings_embedding

### List helper functions
```sql
SELECT proname 
FROM pg_proc 
WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'workflows') 
ORDER BY proname;
```

Expected output:
- find_relevant_learnings
- find_similar_executions
- get_best_combination
- refresh_views
- update_arbiter_duration
- update_execution_summary
- update_phase_duration
- update_worker_duration

## Usage Examples

### Insert a workflow execution
```sql
INSERT INTO workflows.executions (
    workflow_name, 
    status, 
    input_prompt,
    input_context
) VALUES (
    'code-review',
    'running',
    'Review the authentication module',
    '{"repo": "claude-global-skills", "files": ["auth.js"]}'::jsonb
) RETURNING execution_id;
```

### Insert worker results
```sql
INSERT INTO workflows.worker_results (
    execution_id,
    worker_id,
    model,
    status,
    output,
    confidence,
    quality_score,
    input_tokens,
    output_tokens,
    cost_usd
) VALUES (
    'execution-uuid-here',
    'worker-1',
    'claude-sonnet-4.5',
    'completed',
    'The authentication module looks secure...',
    0.85,
    0.90,
    1500,
    800,
    0.0045
);
```

### Find similar executions (semantic search)
```sql
SELECT * FROM workflows.find_similar_executions(
    query_embedding := '[0.1, 0.2, ...]'::vector(768),
    similarity_threshold := 0.7,
    max_results := 10
);
```

### Get best model combination for a workflow
```sql
SELECT * FROM workflows.get_best_combination(
    p_workflow_name := 'code-review',
    min_executions := 3
);
```

### Refresh materialized views
```sql
SELECT workflows.refresh_views();
```

### View workflow summary
```sql
SELECT * FROM workflows.summary WHERE workflow_name = 'code-review';
```

### View model performance
```sql
SELECT * FROM workflows.model_performance ORDER BY avg_quality_score DESC;
```

## Integration Points

The workflows schema integrates with:

1. **Existing learning database** - Uses same PostgreSQL instance
2. **pgvector extension** - Already enabled (verified in existing setup)
3. **sentence-transformers** - 768-dim embeddings (all-mpnet-base-v2)
4. **Thompson Sampling** - Via model_combinations table
5. **Cost tracking** - Integrated with existing costs.entries
6. **Execution monitoring** - Compatible with monitoring.execution_summary

## Next Steps

After successful deployment:

1. ✅ Create PostgreSQL schema (CURRENT STEP - COMPLETED)
2. ⏳ Build workflow completion hook (Step 2)
3. ⏳ Add embedding generation (Step 3)
4. ⏳ Integrate into existing orchestrator (Step 4)

## Files Created

1. `/home/sfloess/.claude/learning/schema/workflows-schema.sql` - Complete DDL
2. `/home/sfloess/.claude/learning/schema/verify-schema.sh` - Verification script
3. `/home/sfloess/.claude/learning/schema/DEPLOYMENT_README.md` - This file

## Troubleshooting

### pgvector not found
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Permission denied
```sql
GRANT USAGE ON SCHEMA workflows TO sfloess;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA workflows TO sfloess;
```

### Triggers not firing
Check that the tables exist first:
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'workflows';
```

### Materialized views need refresh
```sql
SELECT workflows.refresh_views();
```

---

**Created:** 2026-06-19  
**Step:** 1 of 4  
**Status:** Schema DDL and verification scripts READY  
**Action Required:** Execute DDL on laptop-01 PostgreSQL database
