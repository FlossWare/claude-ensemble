-- Workflow Storage Verification Queries
-- Run these after executing a test workflow to verify data integrity

-- =========================================
-- STEP 1: Verify Execution Record
-- =========================================
-- Expected: 1 row with workflow_type, prompt, outcome, duration, cost, embedding

SELECT
    execution_id,
    workflow_type,
    LEFT(prompt, 50) || '...' as prompt_preview,
    outcome,
    duration_ms,
    total_cost_usd,
    timestamp,
    CASE
        WHEN embedding IS NULL THEN 'MISSING'
        WHEN array_length(embedding::float[], 1) = 768 THEN 'VALID (768-dim)'
        ELSE 'INVALID (' || array_length(embedding::float[], 1) || '-dim)'
    END as embedding_status
FROM workflows.executions
ORDER BY timestamp DESC
LIMIT 10;

-- =========================================
-- STEP 2: Verify Worker Results
-- =========================================
-- Expected: N rows (one per worker model) with response, confidence, quality_score, embeddings

SELECT
    wr.result_id,
    wr.execution_id,
    wr.model,
    LEFT(wr.response, 40) || '...' as response_preview,
    wr.confidence,
    wr.quality_score,
    wr.input_tokens,
    wr.output_tokens,
    wr.cost_usd,
    wr.duration_ms,
    CASE
        WHEN wr.embedding IS NULL THEN 'MISSING'
        WHEN array_length(wr.embedding::float[], 1) = 768 THEN 'VALID'
        ELSE 'INVALID'
    END as embedding_status
FROM workflows.worker_results wr
JOIN workflows.executions e ON wr.execution_id = e.execution_id
WHERE e.timestamp > NOW() - INTERVAL '1 hour'
ORDER BY wr.execution_id DESC, wr.timestamp;

-- =========================================
-- STEP 3: Verify Arbiter Decision
-- =========================================
-- Expected: 1 row per execution with final_response, confidence, worker_votes, reasoning

SELECT
    ad.decision_id,
    ad.execution_id,
    ad.arbiter_model,
    LEFT(ad.final_response, 50) || '...' as response_preview,
    ad.confidence,
    ad.worker_votes::text as votes,
    LEFT(ad.reasoning, 40) || '...' as reasoning_preview,
    ad.input_tokens,
    ad.output_tokens,
    ad.cost_usd,
    CASE
        WHEN ad.embedding IS NULL THEN 'MISSING'
        WHEN array_length(ad.embedding::float[], 1) = 768 THEN 'VALID'
        ELSE 'INVALID'
    END as embedding_status
FROM workflows.arbiter_decisions ad
JOIN workflows.executions e ON ad.execution_id = e.execution_id
WHERE e.timestamp > NOW() - INTERVAL '1 hour'
ORDER BY ad.timestamp DESC;

-- =========================================
-- STEP 4: Verify Embeddings are Indexed
-- =========================================
-- Expected: HNSW indexes on all embedding columns

SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'workflows'
  AND indexname LIKE '%embedding%'
ORDER BY tablename, indexname;

-- =========================================
-- STEP 5: Verify Materialized Views
-- =========================================
-- Expected: Summary and model_performance views populated

-- Summary view
SELECT * FROM workflows.summary ORDER BY total_executions DESC;

-- Model performance view
SELECT * FROM workflows.model_performance ORDER BY avg_quality_score DESC;

-- =========================================
-- STEP 6: Test Vector Similarity Search
-- =========================================
-- Find similar executions based on prompt embedding

WITH test_execution AS (
    SELECT embedding
    FROM workflows.executions
    ORDER BY timestamp DESC
    LIMIT 1
)
SELECT
    e.execution_id,
    e.workflow_type,
    LEFT(e.prompt, 60) || '...' as prompt_preview,
    e.outcome,
    (e.embedding <=> te.embedding) as distance
FROM workflows.executions e, test_execution te
WHERE e.embedding IS NOT NULL
ORDER BY e.embedding <=> te.embedding
LIMIT 10;

-- =========================================
-- STEP 7: Check for Errors
-- =========================================
-- Expected: No executions with outcome='error'

SELECT
    execution_id,
    workflow_type,
    outcome,
    metadata->>'error' as error_message,
    timestamp
FROM workflows.executions
WHERE outcome = 'error'
ORDER BY timestamp DESC;

-- =========================================
-- STEP 8: Validate Data Integrity
-- =========================================

-- Check for orphaned worker results (no parent execution)
SELECT COUNT(*) as orphaned_workers
FROM workflows.worker_results wr
LEFT JOIN workflows.executions e ON wr.execution_id = e.execution_id
WHERE e.execution_id IS NULL;

-- Check for orphaned arbiter decisions
SELECT COUNT(*) as orphaned_arbiters
FROM workflows.arbiter_decisions ad
LEFT JOIN workflows.executions e ON ad.execution_id = e.execution_id
WHERE e.execution_id IS NULL;

-- Check for executions missing arbiter decisions
SELECT COUNT(*) as missing_arbiters
FROM workflows.executions e
LEFT JOIN workflows.arbiter_decisions ad ON e.execution_id = ad.execution_id
WHERE ad.decision_id IS NULL
  AND e.outcome = 'success'
  AND e.timestamp > NOW() - INTERVAL '1 day';

-- =========================================
-- STEP 9: Performance Metrics
-- =========================================

-- Average execution time by workflow type
SELECT
    workflow_type,
    COUNT(*) as executions,
    AVG(duration_ms) as avg_duration_ms,
    MIN(duration_ms) as min_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as median_duration_ms
FROM workflows.executions
WHERE outcome = 'success'
GROUP BY workflow_type;

-- Cost analysis
SELECT
    workflow_type,
    COUNT(*) as executions,
    SUM(total_cost_usd) as total_cost,
    AVG(total_cost_usd) as avg_cost_per_execution,
    MIN(total_cost_usd) as min_cost,
    MAX(total_cost_usd) as max_cost
FROM workflows.executions
WHERE outcome = 'success'
GROUP BY workflow_type;

-- =========================================
-- STEP 10: Model Usage Distribution
-- =========================================

-- Worker model distribution
SELECT
    model,
    COUNT(*) as times_used,
    AVG(confidence) as avg_confidence,
    AVG(quality_score) as avg_quality,
    SUM(cost_usd) as total_cost
FROM workflows.worker_results
GROUP BY model
ORDER BY times_used DESC;

-- Arbiter model distribution
SELECT
    arbiter_model,
    COUNT(*) as times_used,
    AVG(confidence) as avg_confidence
FROM workflows.arbiter_decisions
GROUP BY arbiter_model
ORDER BY times_used DESC;

-- =========================================
-- Expected Results Summary:
-- =========================================
--
-- ✓ (1) workflows.executions: 1+ rows with valid 768-dim embeddings
-- ✓ (2) worker_results: N rows (one per worker) with embeddings
-- ✓ (3) arbiter_decisions: 1 row per execution with votes and reasoning
-- ✓ (4) embeddings: HNSW indexes created on all embedding columns
-- ✓ (5) materialized views: summary and model_performance populated
-- ✓ (6) no errors: outcome != 'error'
-- ✓ (7) similarity search: Returns ordered results by distance
-- ✓ (8) data integrity: No orphaned records
-- ✓ (9) performance: Reasonable execution times and costs
-- ✓ (10) distribution: Models used according to configuration
