-- Confidence Calibration Table Migration
-- Created: 2026-06-29
-- Purpose: Track model confidence vs actual correctness for penalty calculation

-- Table: workflow.confidence_calibration
--
-- Tracks observations of:
-- - Model's reported confidence (0-1)
-- - Actual outcome (0=wrong, 1=correct)
-- - Task type (optional filter)
-- - Workflow ID (optional traceability)
--
-- Used to calculate calibration error and apply penalties to overconfident models

CREATE TABLE IF NOT EXISTS workflow.confidence_calibration (
  id SERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  reported_confidence NUMERIC NOT NULL CHECK (reported_confidence >= 0 AND reported_confidence <= 1),
  actual_outcome NUMERIC NOT NULL CHECK (actual_outcome >= 0 AND actual_outcome <= 1),
  task_type TEXT,
  workflow_execution_id TEXT,
  created_at TIMESTAMP DEFAULT NOW(),

  -- Metadata for debugging
  metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_confidence_calibration_model
ON workflow.confidence_calibration(model);

CREATE INDEX IF NOT EXISTS idx_confidence_calibration_model_task
ON workflow.confidence_calibration(model, task_type);

CREATE INDEX IF NOT EXISTS idx_confidence_calibration_created
ON workflow.confidence_calibration(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_confidence_calibration_workflow
ON workflow.confidence_calibration(workflow_execution_id);

-- Comments for documentation
COMMENT ON TABLE workflow.confidence_calibration IS
'Tracks model confidence vs actual correctness for calibration penalty calculation';

COMMENT ON COLUMN workflow.confidence_calibration.model IS
'Model name (opus, sonnet, haiku, etc.)';

COMMENT ON COLUMN workflow.confidence_calibration.reported_confidence IS
'Model''s self-reported confidence (0.0-1.0)';

COMMENT ON COLUMN workflow.confidence_calibration.actual_outcome IS
'Actual correctness from arbiter validation (0.0=wrong, 1.0=correct, or 0-1 for partial credit)';

COMMENT ON COLUMN workflow.confidence_calibration.task_type IS
'Task type for filtering (code_review, security_audit, etc.)';

COMMENT ON COLUMN workflow.confidence_calibration.workflow_execution_id IS
'Workflow execution ID for traceability';

-- Materialized view for fast stats lookup (optional performance optimization)
CREATE MATERIALIZED VIEW IF NOT EXISTS workflow.confidence_calibration_stats AS
SELECT
  model,
  task_type,
  COUNT(*) as num_observations,
  AVG(reported_confidence) as avg_reported,
  AVG(actual_outcome) as avg_actual,
  ABS(AVG(reported_confidence) - AVG(actual_outcome)) as calibration_error,
  MIN(created_at) as first_observation,
  MAX(created_at) as last_observation
FROM workflow.confidence_calibration
GROUP BY model, task_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_confidence_stats_model_task
ON workflow.confidence_calibration_stats(model, task_type);

COMMENT ON MATERIALIZED VIEW workflow.confidence_calibration_stats IS
'Pre-computed calibration statistics per model/task (refresh periodically for performance)';

-- Example refresh command (run periodically via cron or trigger):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.confidence_calibration_stats;

-- Grant permissions (adjust user as needed)
-- GRANT SELECT, INSERT ON workflow.confidence_calibration TO sfloess;
-- GRANT SELECT ON workflow.confidence_calibration_stats TO sfloess;

-- Example queries:
--
-- 1. Find worst-calibrated models:
-- SELECT * FROM workflow.confidence_calibration_stats
-- WHERE num_observations >= 5
-- ORDER BY calibration_error DESC
-- LIMIT 10;
--
-- 2. Track calibration over time:
-- SELECT
--   model,
--   DATE_TRUNC('day', created_at) as day,
--   COUNT(*) as obs,
--   AVG(reported_confidence) - AVG(actual_outcome) as bias
-- FROM workflow.confidence_calibration
-- GROUP BY model, day
-- ORDER BY model, day DESC;
--
-- 3. Compare models on same task:
-- SELECT
--   model,
--   num_observations,
--   avg_reported,
--   avg_actual,
--   calibration_error
-- FROM workflow.confidence_calibration_stats
-- WHERE task_type = 'code_review' AND num_observations >= 5
-- ORDER BY calibration_error ASC;
