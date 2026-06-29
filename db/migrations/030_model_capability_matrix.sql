-- Migration 030: Model Capability Matrix Table
-- Created: 2026-06-29
-- Purpose: Additional table for model-capability-matrix.cjs integration
--
-- This complements the existing learning.model_capabilities table (021_capability_registry.sql)
-- by adding monitoring-specific tracking and integration with workflow storage.
--
-- Note: The core capability registry is in learning.model_capabilities (migration 021).
-- This migration adds the monitoring.model_capabilities table for dynamic updates
-- from monitoring.execution_summary.

-- ============================================================================
-- Create Monitoring Schema (idempotent)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS monitoring;

-- ============================================================================
-- Model Capabilities Table (monitoring.model_capabilities)
-- ============================================================================

-- This table stores DYNAMICALLY UPDATED capability scores from execution history.
-- It complements learning.model_capabilities (which stores the full registry with metrics).
--
-- Relationship:
-- - learning.model_capabilities: Full capability registry with quality/cost/latency
-- - monitoring.model_capabilities: Simplified scores updated by EWMA from execution_summary
--
-- The model-capability-matrix.cjs uses BOTH:
-- 1. monitoring.model_capabilities (if exists) - for learned scores
-- 2. learning.model_capabilities (if exists) - for full metrics
-- 3. learning/model-capability-matrix.json (fallback) - for baseline scores

CREATE TABLE IF NOT EXISTS monitoring.model_capabilities (
  id SERIAL PRIMARY KEY,
  
  -- Model and task identification
  model TEXT NOT NULL,
  task_type TEXT NOT NULL,
  
  -- Capability score (learned from execution history via EWMA)
  capability_score NUMERIC(5,3) NOT NULL CHECK (capability_score >= 0 AND capability_score <= 1),
  
  -- Execution count (number of times this model executed this task)
  executions INTEGER NOT NULL DEFAULT 0 CHECK (executions >= 0),
  
  -- Last update timestamp
  last_updated TIMESTAMP DEFAULT NOW(),
  
  -- Ensure unique capability per model
  UNIQUE(model, task_type)
);

COMMENT ON TABLE monitoring.model_capabilities IS
  'Dynamically updated model capability scores from execution history (EWMA-based)';

COMMENT ON COLUMN monitoring.model_capabilities.model IS
  'Model name (e.g., opus, sonnet, haiku, gpt-4o, gemini)';

COMMENT ON COLUMN monitoring.model_capabilities.task_type IS
  'Task type (e.g., code_generation, code_review, research)';

COMMENT ON COLUMN monitoring.model_capabilities.capability_score IS
  'EWMA-updated capability score (0.0-1.0) from monitoring.execution_summary';

COMMENT ON COLUMN monitoring.model_capabilities.executions IS
  'Total number of executions for this model/task combination';

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Fast lookup by model + task_type (primary query pattern)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_lookup
ON monitoring.model_capabilities(model, task_type);

-- Fast lookup by task_type (for selectModelsByCapability)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_task
ON monitoring.model_capabilities(task_type, capability_score DESC);

-- Fast lookup by model (for model performance analysis)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_model
ON monitoring.model_capabilities(model, capability_score DESC);

-- Fast lookup by last_updated (for finding stale scores)
CREATE INDEX IF NOT EXISTS idx_model_capabilities_updated
ON monitoring.model_capabilities(last_updated DESC);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function: Update capability score with EWMA
-- This is called by model-capability-matrix.cjs updateCapabilityScores()
--
-- Algorithm:
--   new_score = baseline_score * decay + observed_score * (1 - decay)
--
-- Parameters:
--   p_model: Model name
--   p_task_type: Task type
--   p_observed_score: Observed quality score from execution_summary
--   p_executions: Total executions for this model/task
--   p_baseline_score: Baseline score from JSON file (default 0.5)
--   p_decay_factor: EWMA decay factor (default 0.95)

CREATE OR REPLACE FUNCTION monitoring.update_capability_score(
  p_model TEXT,
  p_task_type TEXT,
  p_observed_score NUMERIC,
  p_executions INTEGER,
  p_baseline_score NUMERIC DEFAULT 0.5,
  p_decay_factor NUMERIC DEFAULT 0.95
)
RETURNS NUMERIC AS $$
DECLARE
  v_new_score NUMERIC;
BEGIN
  -- Calculate EWMA
  v_new_score := p_baseline_score * p_decay_factor + p_observed_score * (1 - p_decay_factor);
  
  -- Clamp to [0, 1]
  v_new_score := GREATEST(0.0, LEAST(1.0, v_new_score));
  
  -- Upsert into table
  INSERT INTO monitoring.model_capabilities (model, task_type, capability_score, executions, last_updated)
  VALUES (p_model, p_task_type, v_new_score, p_executions, NOW())
  ON CONFLICT (model, task_type) DO UPDATE SET
    capability_score = EXCLUDED.capability_score,
    executions = EXCLUDED.executions,
    last_updated = NOW();
  
  RETURN v_new_score;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION monitoring.update_capability_score IS
  'Update capability score using EWMA (Exponentially Weighted Moving Average)';

-- ============================================================================
-- Materialized View: Top Models Per Task
-- ============================================================================

CREATE OR REPLACE VIEW monitoring.top_models_per_task AS
SELECT
  task_type,
  model,
  capability_score,
  executions,
  last_updated,
  ROW_NUMBER() OVER (PARTITION BY task_type ORDER BY capability_score DESC) as rank
FROM monitoring.model_capabilities
WHERE executions >= 10  -- Only models with sufficient data
ORDER BY task_type, capability_score DESC;

COMMENT ON VIEW monitoring.top_models_per_task IS
  'Top-ranked models per task type (sorted by capability score, min 10 executions)';

-- ============================================================================
-- Materialized View: Model Performance Summary
-- ============================================================================

CREATE OR REPLACE VIEW monitoring.model_performance_summary AS
SELECT
  model,
  COUNT(DISTINCT task_type) as num_tasks,
  ROUND(AVG(capability_score), 3) as avg_capability,
  ROUND(MIN(capability_score), 3) as min_capability,
  ROUND(MAX(capability_score), 3) as max_capability,
  SUM(executions) as total_executions,
  MAX(last_updated) as last_updated
FROM monitoring.model_capabilities
WHERE executions >= 10
GROUP BY model
ORDER BY avg_capability DESC;

COMMENT ON VIEW monitoring.model_performance_summary IS
  'Model performance summary across all tasks';

-- ============================================================================
-- Sample Queries (commented out - for reference)
-- ============================================================================

/*
-- Top 5 models for code generation
SELECT model, capability_score, executions, last_updated
FROM monitoring.model_capabilities
WHERE task_type = 'code_generation'
ORDER BY capability_score DESC
LIMIT 5;

-- Models with high confidence (100+ executions)
SELECT model, task_type, capability_score, executions
FROM monitoring.model_capabilities
WHERE executions >= 100
ORDER BY capability_score DESC;

-- Model performance across all tasks
SELECT model, num_tasks, avg_capability, total_executions
FROM monitoring.model_performance_summary
ORDER BY avg_capability DESC;

-- Stale scores (not updated in 7 days)
SELECT model, task_type, capability_score, executions,
       NOW() - last_updated as age
FROM monitoring.model_capabilities
WHERE last_updated < NOW() - INTERVAL '7 days'
ORDER BY last_updated ASC;

-- Update score with EWMA
SELECT monitoring.update_capability_score(
  'opus',              -- model
  'code_generation',   -- task_type
  0.93,                -- observed_score
  150,                 -- executions
  0.90,                -- baseline_score
  0.95                 -- decay_factor
);
*/

-- ============================================================================
-- Verify Migration
-- ============================================================================

SELECT
  schemaname,
  tablename,
  tableowner
FROM pg_tables
WHERE schemaname = 'monitoring'
  AND tablename = 'model_capabilities'
ORDER BY tablename;
