-- Migration 021: Capability Registry
-- Created: 2026-06-28
-- Purpose: Track model capabilities with quality metrics and performance history
--
-- The capability registry maintains a database of what each model can do well,
-- storing quality scores, cost, and latency metrics per capability. This enables
-- intelligent model selection based on proven performance on specific tasks.

-- ============================================================================
-- Create Schema
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS learning;

-- ============================================================================
-- Capability Registry Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS learning.model_capabilities (
  id SERIAL PRIMARY KEY,

  -- Model and capability identification
  model TEXT NOT NULL,
  capability TEXT NOT NULL,

  -- Performance metrics (empirical data from executions)
  quality_score NUMERIC(5,2) NOT NULL CHECK (quality_score >= 0 AND quality_score <= 1),
  avg_cost NUMERIC(10,6) NOT NULL CHECK (avg_cost >= 0),
  avg_latency_ms NUMERIC(10,2) NOT NULL CHECK (avg_latency_ms >= 0),

  -- Execution history
  executions INTEGER NOT NULL DEFAULT 1 CHECK (executions > 0),
  success_count INTEGER NOT NULL DEFAULT 1 CHECK (success_count >= 0 AND success_count <= executions),
  failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0 AND failure_count <= executions),

  -- Confidence in metrics (0-1: higher = more data points = more confident)
  confidence NUMERIC(5,2) NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),

  -- Additional metadata
  last_executed_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  -- Ensure unique capability per model
  UNIQUE(model, capability),

  -- Index for common queries
  CONSTRAINT model_capability_check CHECK (length(model) > 0 AND length(capability) > 0)
);

COMMENT ON TABLE learning.model_capabilities IS
  'Registry of model capabilities with quality, cost, and latency metrics';

COMMENT ON COLUMN learning.model_capabilities.model IS
  'Model name (e.g., opus, sonnet, haiku, deepseek-coder)';

COMMENT ON COLUMN learning.model_capabilities.capability IS
  'Capability type (e.g., code_generation, code_review, research, analysis)';

COMMENT ON COLUMN learning.model_capabilities.quality_score IS
  'Average quality score (0-1) from all executions of this capability';

COMMENT ON COLUMN learning.model_capabilities.avg_cost IS
  'Average cost in USD per execution';

COMMENT ON COLUMN learning.model_capabilities.avg_latency_ms IS
  'Average latency in milliseconds';

COMMENT ON COLUMN learning.model_capabilities.executions IS
  'Total number of executions for this capability';

COMMENT ON COLUMN learning.model_capabilities.success_count IS
  'Number of successful executions';

COMMENT ON COLUMN learning.model_capabilities.failure_count IS
  'Number of failed executions';

COMMENT ON COLUMN learning.model_capabilities.confidence IS
  'Confidence in metrics: higher with more data points (min 10 for high confidence)';

-- ============================================================================
-- Capability Execution History
-- ============================================================================

CREATE TABLE IF NOT EXISTS learning.capability_executions (
  id SERIAL PRIMARY KEY,

  -- Reference to capability
  capability_id INTEGER NOT NULL REFERENCES learning.model_capabilities(id) ON DELETE CASCADE,

  -- Execution metadata
  workflow_id TEXT,
  task_id TEXT,

  -- Results
  quality_score NUMERIC(5,2) NOT NULL CHECK (quality_score >= 0 AND quality_score <= 1),
  cost_usd NUMERIC(10,6) NOT NULL CHECK (cost_usd >= 0),
  latency_ms NUMERIC(10,2) NOT NULL CHECK (latency_ms >= 0),

  -- Outcome
  success BOOLEAN NOT NULL DEFAULT TRUE,
  error_message TEXT,

  -- Timing
  executed_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE learning.capability_executions IS
  'Individual execution records for each capability';

-- Indexes for execution history
CREATE INDEX IF NOT EXISTS idx_capability_executions_capability_id ON learning.capability_executions(capability_id);
CREATE INDEX IF NOT EXISTS idx_capability_executions_executed_at ON learning.capability_executions(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_capability_executions_workflow_id ON learning.capability_executions(workflow_id);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_model_capabilities_model ON learning.model_capabilities(model);
CREATE INDEX IF NOT EXISTS idx_model_capabilities_capability ON learning.model_capabilities(capability);
CREATE INDEX IF NOT EXISTS idx_model_capabilities_quality ON learning.model_capabilities(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_model_capabilities_updated ON learning.model_capabilities(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_capability_executions_capability_id ON learning.capability_executions(capability_id);
CREATE INDEX IF NOT EXISTS idx_capability_executions_executed_at ON learning.capability_executions(executed_at DESC);

-- ============================================================================
-- Materialized Views
-- ============================================================================

-- View: Top-performing models per capability
CREATE OR REPLACE VIEW learning.top_models_per_capability AS
SELECT
  capability,
  model,
  quality_score,
  confidence,
  avg_cost,
  avg_latency_ms,
  executions,
  success_count,
  ROUND(100.0 * success_count / executions, 1) AS success_rate
FROM learning.model_capabilities
WHERE confidence >= 0.5
ORDER BY capability, quality_score DESC, confidence DESC;

COMMENT ON VIEW learning.top_models_per_capability IS
  'Top-performing models per capability (sorted by quality, filtered by confidence >= 0.5)';

-- View: Model capability summary
CREATE OR REPLACE VIEW learning.model_capability_summary AS
SELECT
  model,
  COUNT(DISTINCT capability) AS num_capabilities,
  ROUND(AVG(quality_score), 3) AS avg_quality,
  ROUND(AVG(avg_cost), 6) AS avg_cost,
  ROUND(AVG(avg_latency_ms), 2) AS avg_latency_ms,
  SUM(executions) AS total_executions,
  SUM(success_count) AS total_successes,
  ROUND(100.0 * SUM(success_count) / NULLIF(SUM(executions), 0), 1) AS overall_success_rate,
  MAX(updated_at) AS last_updated
FROM learning.model_capabilities
GROUP BY model
ORDER BY avg_quality DESC;

COMMENT ON VIEW learning.model_capability_summary IS
  'Summary of all capabilities per model';

-- View: Capability coverage across models
CREATE OR REPLACE VIEW learning.capability_coverage AS
SELECT
  capability,
  COUNT(DISTINCT model) AS num_models,
  ROUND(AVG(quality_score), 3) AS avg_quality,
  MAX(quality_score) AS best_quality,
  MIN(quality_score) AS worst_quality,
  ROUND(AVG(avg_cost), 6) AS avg_cost,
  SUM(executions) AS total_executions,
  MAX(updated_at) AS last_updated
FROM learning.model_capabilities
GROUP BY capability
ORDER BY total_executions DESC;

COMMENT ON VIEW learning.capability_coverage IS
  'Coverage of capabilities across available models';

-- ============================================================================
-- Helper Functions
-- ============================================================================

CREATE OR REPLACE FUNCTION learning.register_capability(
  p_model TEXT,
  p_capability TEXT,
  p_quality_score NUMERIC,
  p_cost_usd NUMERIC,
  p_latency_ms NUMERIC,
  p_success BOOLEAN DEFAULT TRUE
)
RETURNS INTEGER AS $$
DECLARE
  v_capability_id INTEGER;
  v_current_success_count INTEGER;
  v_current_failure_count INTEGER;
  v_current_executions INTEGER;
  v_new_success_count INTEGER;
  v_new_failure_count INTEGER;
  v_new_executions INTEGER;
BEGIN
  -- Get or create capability record
  INSERT INTO learning.model_capabilities (model, capability, quality_score, avg_cost, avg_latency_ms)
  VALUES (p_model, p_capability, p_quality_score, p_cost_usd, p_latency_ms)
  ON CONFLICT (model, capability) DO NOTHING;

  -- Get the capability ID
  SELECT id INTO v_capability_id FROM learning.model_capabilities
  WHERE model = p_model AND capability = p_capability;

  -- Get current metrics
  SELECT success_count, failure_count, executions
  INTO v_current_success_count, v_current_failure_count, v_current_executions
  FROM learning.model_capabilities
  WHERE id = v_capability_id;

  -- Calculate new metrics
  v_new_executions := v_current_executions + 1;
  v_new_success_count := v_current_success_count + (CASE WHEN p_success THEN 1 ELSE 0 END);
  v_new_failure_count := v_current_failure_count + (CASE WHEN NOT p_success THEN 1 ELSE 0 END);

  -- Update capability record with averaged metrics
  UPDATE learning.model_capabilities
  SET
    quality_score = (quality_score * v_current_executions + p_quality_score) / v_new_executions,
    avg_cost = (avg_cost * v_current_executions + p_cost_usd) / v_new_executions,
    avg_latency_ms = (avg_latency_ms * v_current_executions + p_latency_ms) / v_new_executions,
    executions = v_new_executions,
    success_count = v_new_success_count,
    failure_count = v_new_failure_count,
    confidence = LEAST(1.0, v_new_executions / 10.0),
    last_executed_at = NOW(),
    updated_at = NOW()
  WHERE id = v_capability_id;

  -- Record execution in history
  INSERT INTO learning.capability_executions (capability_id, quality_score, cost_usd, latency_ms, success)
  VALUES (v_capability_id, p_quality_score, p_cost_usd, p_latency_ms, p_success);

  RETURN v_capability_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION learning.register_capability IS
  'Register or update a model capability with execution metrics';

-- ============================================================================
-- Sample Data (for testing)
-- ============================================================================

INSERT INTO learning.model_capabilities
  (model, capability, quality_score, avg_cost, avg_latency_ms, executions, success_count, confidence)
VALUES
  ('opus', 'code_generation', 0.92, 0.05, 2500, 50, 48, 0.95),
  ('opus', 'code_review', 0.89, 0.05, 2800, 45, 42, 0.90),
  ('opus', 'research', 0.91, 0.05, 3200, 30, 29, 0.85),
  ('sonnet', 'code_generation', 0.88, 0.02, 1800, 55, 52, 0.95),
  ('sonnet', 'code_review', 0.85, 0.02, 2000, 50, 47, 0.95),
  ('sonnet', 'research', 0.87, 0.02, 2400, 35, 33, 0.90),
  ('haiku', 'code_generation', 0.75, 0.005, 800, 60, 54, 0.95),
  ('haiku', 'code_review', 0.72, 0.005, 900, 55, 48, 0.95),
  ('haiku', 'research', 0.70, 0.005, 1200, 40, 35, 0.90),
  ('deepseek-coder', 'code_generation', 0.94, 0.0, 1500, 40, 39, 0.90),
  ('deepseek-coder', 'code_review', 0.87, 0.0, 1700, 35, 33, 0.85)
ON CONFLICT (model, capability) DO NOTHING;

-- ============================================================================
-- Verify Migration
-- ============================================================================

SELECT
  schemaname,
  tablename,
  tableowner
FROM pg_tables
WHERE schemaname = 'learning'
  AND tablename IN ('model_capabilities', 'capability_executions')
ORDER BY tablename;
