-- ============================================================================
-- Verification Queries for Prediction Columns
-- ============================================================================
-- Purpose: Verify that quality_score and circuit_breaker_state columns
--          are properly created and populated
--
-- Created: 2026-07-04
-- Database: learning (aio-01:5433)
-- ============================================================================

-- 1. Verify column existence and types
SELECT
  table_schema,
  table_name,
  column_name,
  data_type,
  column_default,
  is_nullable
FROM information_schema.columns
WHERE (table_schema = 'monitoring' AND table_name = 'execution_summary'
       AND column_name IN ('quality_score', 'circuit_breaker_state'))
   OR (table_schema = 'workflow' AND table_name = 'executions'
       AND column_name = 'quality_score')
ORDER BY table_schema, table_name, column_name;

-- 2. Verify indexes
SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname IN ('monitoring', 'workflow')
  AND (indexname LIKE 'idx_%quality%' OR indexname LIKE 'idx_%circuit%')
ORDER BY schemaname, tablename, indexname;

-- 3. Check data distribution
SELECT
  'monitoring.execution_summary' as table_name,
  COUNT(*) as total_rows,
  COUNT(quality_score) as non_null_quality,
  ROUND(MIN(quality_score)::numeric, 2) as min_quality,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  ROUND(MAX(quality_score)::numeric, 2) as max_quality,
  COUNT(*) FILTER (WHERE quality_score >= 0.8) as high_quality_count,
  COUNT(*) FILTER (WHERE quality_score < 0.5) as low_quality_count
FROM monitoring.execution_summary
UNION ALL
SELECT
  'workflow.executions' as table_name,
  COUNT(*) as total_rows,
  COUNT(quality_score) as non_null_quality,
  ROUND(MIN(quality_score)::numeric, 2) as min_quality,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  ROUND(MAX(quality_score)::numeric, 2) as max_quality,
  COUNT(*) FILTER (WHERE quality_score >= 0.8) as high_quality_count,
  COUNT(*) FILTER (WHERE quality_score < 0.5) as low_quality_count
FROM workflow.executions;

-- 4. Check circuit_breaker_state distribution
SELECT
  circuit_breaker_state,
  COUNT(*) as count,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  COUNT(*) FILTER (WHERE outcome = 'error') as error_count,
  COUNT(*) FILTER (WHERE outcome = 'success') as success_count
FROM monitoring.execution_summary
GROUP BY circuit_breaker_state
ORDER BY count DESC;

-- 5. Quality score by outcome
SELECT
  outcome,
  COUNT(*) as count,
  ROUND(MIN(quality_score)::numeric, 2) as min_quality,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  ROUND(MAX(quality_score)::numeric, 2) as max_quality,
  ROUND(STDDEV(quality_score)::numeric, 2) as stddev_quality
FROM monitoring.execution_summary
WHERE quality_score IS NOT NULL
GROUP BY outcome
ORDER BY avg_quality DESC;

-- 6. Quality score by model (top 10)
SELECT
  model,
  COUNT(*) as count,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  ROUND(STDDEV(quality_score)::numeric, 2) as quality_variation,
  COUNT(*) FILTER (WHERE quality_score >= 0.8) as high_quality_count
FROM monitoring.execution_summary
WHERE quality_score IS NOT NULL
GROUP BY model
ORDER BY avg_quality DESC
LIMIT 10;

-- 7. Recent quality trends (last 24 hours)
SELECT
  DATE_TRUNC('hour', timestamp) as hour,
  COUNT(*) as executions,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  COUNT(*) FILTER (WHERE circuit_breaker_state = 'open') as circuit_breaker_open,
  COUNT(*) FILTER (WHERE outcome = 'error') as errors
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC
LIMIT 24;

-- 8. Workflow quality analysis
SELECT
  we.workflow_name,
  COUNT(*) as workflow_count,
  ROUND(AVG(we.quality_score)::numeric, 2) as avg_workflow_quality,
  ROUND(AVG(wr.confidence)::numeric, 2) as avg_worker_confidence,
  COUNT(*) FILTER (WHERE we.outcome = 'success') as successful_runs,
  COUNT(*) FILTER (WHERE we.outcome = 'error') as failed_runs
FROM workflow.executions we
LEFT JOIN workflow.worker_results wr ON wr.workflow_execution_id = we.id
GROUP BY we.workflow_name
ORDER BY workflow_count DESC
LIMIT 10;

-- 9. Sample high-quality executions
SELECT
  model,
  workflow,
  task_type,
  quality_score,
  outcome,
  circuit_breaker_state,
  duration_ms,
  timestamp
FROM monitoring.execution_summary
WHERE quality_score >= 0.9
ORDER BY timestamp DESC
LIMIT 10;

-- 10. Sample low-quality executions
SELECT
  model,
  workflow,
  task_type,
  quality_score,
  outcome,
  circuit_breaker_state,
  duration_ms,
  timestamp
FROM monitoring.execution_summary
WHERE quality_score < 0.3 AND quality_score IS NOT NULL
ORDER BY timestamp DESC
LIMIT 10;
