-- Migration 026: Model Capability Matrix
-- Creates monitoring.model_capabilities table for dynamic capability learning
--
-- Purpose:
-- - Store learned capability scores per model/task combination
-- - Track execution count for confidence scoring
-- - Enable dynamic model routing based on actual performance
--
-- Integration:
-- - Updates from monitoring.execution_summary quality scores
-- - Uses EWMA (Exponentially Weighted Moving Average)
-- - Minimum 10 executions before updating baseline scores
--
-- Created: 2026-06-29

-- Create model_capabilities table
CREATE TABLE IF NOT EXISTS monitoring.model_capabilities (
  id SERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  task_type TEXT NOT NULL,
  capability_score NUMERIC(5,4) NOT NULL CHECK (capability_score >= 0.0 AND capability_score <= 1.0),
  executions INTEGER DEFAULT 0 CHECK (executions >= 0),
  avg_quality NUMERIC(5,4),
  stddev_quality NUMERIC(5,4),
  min_quality NUMERIC(5,4),
  max_quality NUMERIC(5,4),
  baseline_score NUMERIC(5,4),
  last_updated TIMESTAMP DEFAULT NOW(),
  UNIQUE(model, task_type)
);

-- Create index for fast lookups (used by selectModelsByCapability)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_lookup
ON monitoring.model_capabilities(model, task_type);

-- Create index for task type queries (used by selectModelsByCapability)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_task
ON monitoring.model_capabilities(task_type, capability_score DESC);

-- Create index for confidence filtering (used by getCapabilityScoreWithConfidence)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_executions
ON monitoring.model_capabilities(executions DESC) WHERE executions >= 10;

-- Add comment
COMMENT ON TABLE monitoring.model_capabilities IS 'Learned model capability scores per task type, updated from execution_summary quality metrics using EWMA';

-- Materialized view: Top models per task type
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.model_capabilities_top AS
SELECT DISTINCT ON (task_type)
  task_type,
  ARRAY_AGG(model ORDER BY capability_score DESC) FILTER (WHERE capability_score >= 0.7) AS top_models,
  ARRAY_AGG(capability_score ORDER BY capability_score DESC) FILTER (WHERE capability_score >= 0.7) AS top_scores,
  MAX(last_updated) AS last_updated
FROM monitoring.model_capabilities
GROUP BY task_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_capabilities_top_task
ON monitoring.model_capabilities_top(task_type);

COMMENT ON MATERIALIZED VIEW monitoring.model_capabilities_top IS 'Pre-computed top models per task type (refreshed on updates)';

-- Refresh function (called after updates)
CREATE OR REPLACE FUNCTION monitoring.refresh_model_capabilities_top()
RETURNS VOID AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.model_capabilities_top;
END;
$$ LANGUAGE plpgsql;

-- Function: Calculate confidence from execution count
-- Uses sigmoid function: confidence = 1 / (1 + exp(-0.05 * (executions - 50)))
CREATE OR REPLACE FUNCTION monitoring.capability_confidence(executions INTEGER)
RETURNS NUMERIC AS $$
BEGIN
  RETURN 1.0 / (1.0 + EXP(-0.05 * (executions - 50)));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION monitoring.capability_confidence IS 'Calculate confidence score (0-1) from execution count using sigmoid function';

-- Function: Get capability score with confidence
CREATE OR REPLACE FUNCTION monitoring.get_capability_with_confidence(
  p_model TEXT,
  p_task_type TEXT
)
RETURNS TABLE(
  score NUMERIC,
  confidence NUMERIC,
  executions INTEGER,
  source TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    capability_score AS score,
    monitoring.capability_confidence(model_capabilities.executions) AS confidence,
    model_capabilities.executions,
    'database'::TEXT AS source
  FROM monitoring.model_capabilities
  WHERE model = p_model AND task_type = p_task_type;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION monitoring.get_capability_with_confidence IS 'Get capability score with confidence interval for a model/task combination';

-- View: Model capabilities with confidence
CREATE OR REPLACE VIEW monitoring.model_capabilities_with_confidence AS
SELECT
  model,
  task_type,
  capability_score,
  monitoring.capability_confidence(executions) AS confidence,
  executions,
  avg_quality,
  stddev_quality,
  last_updated,
  CASE
    WHEN executions < 10 THEN 'low_sample'
    WHEN executions < 50 THEN 'moderate_sample'
    WHEN executions < 100 THEN 'good_sample'
    ELSE 'high_sample'
  END AS confidence_level
FROM monitoring.model_capabilities;

COMMENT ON VIEW monitoring.model_capabilities_with_confidence IS 'Model capabilities augmented with confidence scores and levels';

-- Trigger: Auto-refresh materialized view on update
CREATE OR REPLACE FUNCTION monitoring.trigger_refresh_capabilities_top()
RETURNS TRIGGER AS $$
BEGIN
  -- Refresh asynchronously (don't block inserts)
  PERFORM monitoring.refresh_model_capabilities_top();
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_model_capabilities_refresh
AFTER INSERT OR UPDATE OR DELETE ON monitoring.model_capabilities
FOR EACH STATEMENT
EXECUTE FUNCTION monitoring.trigger_refresh_capabilities_top();

-- Initial population from execution_summary (optional - run if data exists)
-- Minimum 10 executions required
INSERT INTO monitoring.model_capabilities (
  model,
  task_type,
  capability_score,
  executions,
  avg_quality,
  stddev_quality,
  min_quality,
  max_quality,
  baseline_score
)
SELECT
  model,
  task_type,
  AVG(quality_score) AS capability_score,
  COUNT(*) AS executions,
  AVG(quality_score) AS avg_quality,
  STDDEV(quality_score) AS stddev_quality,
  MIN(quality_score) AS min_quality,
  MAX(quality_score) AS max_quality,
  0.5 AS baseline_score  -- Default baseline, will be updated by EWMA
FROM monitoring.execution_summary
WHERE quality_score IS NOT NULL
  AND task_type IS NOT NULL
GROUP BY model, task_type
HAVING COUNT(*) >= 10
ON CONFLICT (model, task_type) DO NOTHING;

-- Initial materialized view population
REFRESH MATERIALIZED VIEW monitoring.model_capabilities_top;

-- Verification query
SELECT
  COUNT(*) AS total_capabilities,
  COUNT(DISTINCT model) AS unique_models,
  COUNT(DISTINCT task_type) AS unique_task_types,
  AVG(executions) AS avg_executions,
  AVG(capability_score) AS avg_capability_score
FROM monitoring.model_capabilities;

-- Example queries
COMMENT ON TABLE monitoring.model_capabilities IS 'Example queries:

-- Top models for code_review
SELECT model, capability_score, executions
FROM monitoring.model_capabilities
WHERE task_type = ''code_review''
ORDER BY capability_score DESC
LIMIT 5;

-- Models with high confidence (100+ executions)
SELECT model, task_type, capability_score, monitoring.capability_confidence(executions) AS confidence
FROM monitoring.model_capabilities
WHERE executions >= 100
ORDER BY capability_score DESC;

-- Model performance across all tasks
SELECT
  model,
  COUNT(*) AS num_tasks,
  AVG(capability_score) AS avg_score,
  SUM(executions) AS total_executions
FROM monitoring.model_capabilities
GROUP BY model
ORDER BY avg_score DESC;

-- Tasks with low model coverage
SELECT task_type, COUNT(*) AS num_models
FROM monitoring.model_capabilities
GROUP BY task_type
HAVING COUNT(*) < 3
ORDER BY num_models;
';
