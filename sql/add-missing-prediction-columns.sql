-- ============================================================================
-- Add Missing Columns for Workflow Predictions
-- ============================================================================
-- Purpose: Add quality_score and circuit_breaker_state columns to enable
--          accurate workflow predictions instead of using fallback defaults
--
-- Created: 2026-07-04
-- Database: learning (aio-01:5433)
-- Tables Modified:
--   - monitoring.execution_summary
--   - workflow.executions
-- ============================================================================

-- Begin transaction for atomicity
BEGIN;

-- ============================================================================
-- 1. Add missing columns to monitoring.execution_summary
-- ============================================================================

-- Add quality_score column (0.0 to 1.0 scale, default 0.75)
ALTER TABLE monitoring.execution_summary
ADD COLUMN IF NOT EXISTS quality_score NUMERIC(3,2) DEFAULT 0.75
CHECK (quality_score >= 0.0 AND quality_score <= 1.0);

COMMENT ON COLUMN monitoring.execution_summary.quality_score IS
'Quality score of execution output (0.0-1.0 scale). Used for predictions and trend analysis.';

-- Add circuit_breaker_state column (closed/half_open/open states)
ALTER TABLE monitoring.execution_summary
ADD COLUMN IF NOT EXISTS circuit_breaker_state VARCHAR(32) DEFAULT 'closed'
CHECK (circuit_breaker_state IN ('closed', 'half_open', 'open'));

COMMENT ON COLUMN monitoring.execution_summary.circuit_breaker_state IS
'Circuit breaker state for fault tolerance (closed=normal, half_open=testing, open=failing)';

-- ============================================================================
-- 2. Add missing columns to workflow.executions
-- ============================================================================

-- Add quality_score column (0.0 to 1.0 scale, default 0.75)
ALTER TABLE workflow.executions
ADD COLUMN IF NOT EXISTS quality_score NUMERIC(3,2) DEFAULT 0.75
CHECK (quality_score >= 0.0 AND quality_score <= 1.0);

COMMENT ON COLUMN workflow.executions.quality_score IS
'Overall quality score of workflow execution (0.0-1.0 scale). Aggregated from worker results.';

-- ============================================================================
-- 3. Create performance indexes
-- ============================================================================

-- Index on execution_summary quality_score for filtering and aggregation
CREATE INDEX IF NOT EXISTS idx_execution_quality
ON monitoring.execution_summary(quality_score);

-- Index on execution_summary circuit_breaker_state for monitoring
CREATE INDEX IF NOT EXISTS idx_execution_circuit_breaker
ON monitoring.execution_summary(circuit_breaker_state);

-- Composite index for quality + outcome queries
CREATE INDEX IF NOT EXISTS idx_execution_quality_outcome
ON monitoring.execution_summary(quality_score, outcome);

-- Index on workflow.executions quality_score for filtering
CREATE INDEX IF NOT EXISTS idx_workflow_quality
ON workflow.executions(quality_score);

-- Composite index for quality + outcome queries
CREATE INDEX IF NOT EXISTS idx_workflow_quality_outcome
ON workflow.executions(quality_score, outcome);

-- ============================================================================
-- 4. Update existing records with intelligent defaults
-- ============================================================================

-- Update quality_score based on outcome (better than global default)
UPDATE monitoring.execution_summary
SET quality_score = CASE
  WHEN outcome = 'success' THEN 0.85
  WHEN outcome = 'partial' THEN 0.65
  WHEN outcome = 'error' THEN 0.40
  ELSE 0.75
END
WHERE quality_score = 0.75;  -- Only update records that still have default

-- Update circuit_breaker_state based on recent failures
WITH recent_failures AS (
  SELECT model, workflow, task_type,
         COUNT(*) FILTER (WHERE outcome = 'error') as error_count,
         COUNT(*) as total_count
  FROM monitoring.execution_summary
  WHERE timestamp > NOW() - INTERVAL '1 hour'
  GROUP BY model, workflow, task_type
)
UPDATE monitoring.execution_summary es
SET circuit_breaker_state = CASE
  WHEN rf.error_count::FLOAT / NULLIF(rf.total_count, 0) > 0.5 THEN 'open'
  WHEN rf.error_count::FLOAT / NULLIF(rf.total_count, 0) > 0.3 THEN 'half_open'
  ELSE 'closed'
END
FROM recent_failures rf
WHERE es.model = rf.model
  AND es.workflow = rf.workflow
  AND COALESCE(es.task_type, '') = COALESCE(rf.task_type, '')
  AND es.circuit_breaker_state = 'closed';  -- Only update defaults

-- Update workflow quality_score based on worker results average
UPDATE workflow.executions we
SET quality_score = COALESCE(
  (SELECT AVG(confidence)
   FROM workflow.worker_results wr
   WHERE wr.workflow_execution_id = we.id),
  0.75
)
WHERE we.quality_score = 0.75;  -- Only update records that still have default

-- ============================================================================
-- 5. Create helper views for quality monitoring
-- ============================================================================

-- View: Recent quality trends by model
CREATE OR REPLACE VIEW monitoring.quality_trends AS
SELECT
  model,
  workflow,
  DATE_TRUNC('hour', timestamp) as hour,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  COUNT(*) as execution_count,
  COUNT(*) FILTER (WHERE quality_score >= 0.8) as high_quality_count,
  COUNT(*) FILTER (WHERE quality_score < 0.5) as low_quality_count
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY model, workflow, DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC, model;

COMMENT ON VIEW monitoring.quality_trends IS
'Hourly quality score trends by model and workflow for the last 24 hours';

-- View: Circuit breaker status summary
CREATE OR REPLACE VIEW monitoring.circuit_breaker_status AS
SELECT
  model,
  workflow,
  circuit_breaker_state,
  COUNT(*) as count,
  MAX(timestamp) as last_seen,
  AVG(quality_score) as avg_quality
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY model, workflow, circuit_breaker_state
ORDER BY circuit_breaker_state DESC, count DESC;

COMMENT ON VIEW monitoring.circuit_breaker_status IS
'Current circuit breaker state summary by model and workflow';

-- ============================================================================
-- 6. Grant appropriate permissions (if needed)
-- ============================================================================

-- Grant SELECT on new views (adjust role as needed)
-- GRANT SELECT ON monitoring.quality_trends TO your_read_role;
-- GRANT SELECT ON monitoring.circuit_breaker_status TO your_read_role;

-- ============================================================================
-- Commit transaction
-- ============================================================================

COMMIT;

-- ============================================================================
-- Verification queries (run these separately to check results)
-- ============================================================================

-- Check column additions
SELECT
  column_name,
  data_type,
  column_default,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'monitoring'
  AND table_name = 'execution_summary'
  AND column_name IN ('quality_score', 'circuit_breaker_state')
ORDER BY column_name;

SELECT
  column_name,
  data_type,
  column_default,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'workflow'
  AND table_name = 'executions'
  AND column_name = 'quality_score'
ORDER BY column_name;

-- Check index creation
SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname IN ('monitoring', 'workflow')
  AND indexname LIKE 'idx_%quality%'
ORDER BY schemaname, tablename, indexname;

-- Check data distribution after updates
SELECT
  'monitoring.execution_summary' as table_name,
  MIN(quality_score) as min_quality,
  AVG(quality_score) as avg_quality,
  MAX(quality_score) as max_quality,
  COUNT(*) as total_rows,
  COUNT(quality_score) as non_null_count
FROM monitoring.execution_summary
UNION ALL
SELECT
  'workflow.executions' as table_name,
  MIN(quality_score) as min_quality,
  AVG(quality_score) as avg_quality,
  MAX(quality_score) as max_quality,
  COUNT(*) as total_rows,
  COUNT(quality_score) as non_null_count
FROM workflow.executions;

-- Check circuit breaker states
SELECT
  circuit_breaker_state,
  COUNT(*) as count,
  AVG(quality_score) as avg_quality
FROM monitoring.execution_summary
GROUP BY circuit_breaker_state
ORDER BY count DESC;

-- Sample quality trends
SELECT * FROM monitoring.quality_trends LIMIT 20;

-- Sample circuit breaker status
SELECT * FROM monitoring.circuit_breaker_status LIMIT 20;
