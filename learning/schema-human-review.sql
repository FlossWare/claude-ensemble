-- ============================================================================
-- Disagreement-Driven Active Learning Schema
-- Human Review Queue for Multi-AI Consensus
--
-- Purpose: Flag high-disagreement tasks for human review instead of blindly
--          picking a winner when models vote with high variance.
--
-- Created: 2026-06-28
-- ============================================================================

-- Create workflow schema if not exists
CREATE SCHEMA IF NOT EXISTS workflow;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Human Review Queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow.human_review_queue (
  id SERIAL PRIMARY KEY,

  -- Workflow identification
  workflow_execution_id TEXT NOT NULL,
  workflow_name TEXT,
  task_description TEXT NOT NULL,

  -- Disagreement analysis
  votes_json JSONB NOT NULL,
  disagreement_score NUMERIC NOT NULL,  -- Coefficient of variation (std_dev / mean)
  disagreement_level TEXT CHECK (disagreement_level IN ('low', 'moderate', 'high', 'critical')),

  -- Vote statistics
  num_votes INTEGER NOT NULL,
  unique_answers INTEGER NOT NULL,
  confidence_range JSONB,  -- {min, max, mean, median, std_dev}

  -- Review status
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'resolved', 'dismissed')),
  priority INTEGER DEFAULT 5,  -- 1 (low) to 10 (critical)

  -- Human verdict (filled when reviewed)
  human_verdict JSONB,
  human_reviewer TEXT,
  reviewed_at TIMESTAMP,
  resolution_notes TEXT,

  -- Metadata
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB,  -- Extensible for future use

  -- Audit trail
  weighted_winner JSONB,  -- What weighted voting picked
  winner_confidence NUMERIC,  -- Weighted winner's total confidence
  runner_up JSONB,  -- Second place

  -- Indexes
  CONSTRAINT unique_workflow_task UNIQUE (workflow_execution_id, task_description)
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Query by status (fetch pending reviews)
CREATE INDEX IF NOT EXISTS idx_hrq_status
  ON workflow.human_review_queue(status, disagreement_score DESC);

-- Query by workflow execution
CREATE INDEX IF NOT EXISTS idx_hrq_workflow
  ON workflow.human_review_queue(workflow_execution_id);

-- Query by disagreement level
CREATE INDEX IF NOT EXISTS idx_hrq_disagreement
  ON workflow.human_review_queue(disagreement_level, created_at DESC);

-- Query by priority
CREATE INDEX IF NOT EXISTS idx_hrq_priority
  ON workflow.human_review_queue(status, priority DESC, created_at DESC);

-- GIN index on votes_json for JSONB queries
CREATE INDEX IF NOT EXISTS idx_hrq_votes_gin
  ON workflow.human_review_queue USING GIN (votes_json);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION workflow.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_hrq_updated_at
  BEFORE UPDATE ON workflow.human_review_queue
  FOR EACH ROW
  EXECUTE FUNCTION workflow.update_updated_at_column();

-- ============================================================================
-- Materialized View: Review Queue Dashboard
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS workflow.review_queue_summary AS
SELECT
  status,
  disagreement_level,
  COUNT(*) as count,
  AVG(disagreement_score) as avg_disagreement,
  MIN(created_at) as oldest,
  MAX(created_at) as newest,
  AVG(EXTRACT(EPOCH FROM (COALESCE(reviewed_at, NOW()) - created_at))) as avg_time_to_review_seconds
FROM workflow.human_review_queue
GROUP BY status, disagreement_level
ORDER BY status, disagreement_level;

-- Auto-refresh materialized view (requires pg_cron or manual refresh)
-- Refresh every 5 minutes via cron: SELECT workflow.refresh_review_summary();
CREATE OR REPLACE FUNCTION workflow.refresh_review_summary()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW workflow.review_queue_summary;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Feedback Loop Integration
-- ============================================================================

-- Table: Human review outcomes → Thompson Sampling updates
-- Links human verdicts back to strategy performance for learning
CREATE TABLE IF NOT EXISTS workflow.human_feedback_learning (
  id SERIAL PRIMARY KEY,
  review_queue_id INTEGER REFERENCES workflow.human_review_queue(id) ON DELETE CASCADE,

  -- Original weighted voting result
  weighted_winner TEXT,
  weighted_confidence NUMERIC,

  -- Human verdict
  human_winner TEXT,
  human_confidence NUMERIC,

  -- Disagreement analysis
  weighted_was_correct BOOLEAN,  -- Did weighted voting pick what human chose?
  confidence_calibration_error NUMERIC,  -- How far off was the confidence?

  -- Strategy updates
  strategy_updates JSONB,  -- Which Thompson Sampling strategies to adjust

  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for querying calibration errors
CREATE INDEX IF NOT EXISTS idx_hfl_calibration
  ON workflow.human_feedback_learning(weighted_was_correct, confidence_calibration_error);

-- ============================================================================
-- Example Queries
-- ============================================================================

-- Fetch pending reviews ordered by disagreement score (highest first)
COMMENT ON TABLE workflow.human_review_queue IS
'Example query: SELECT * FROM workflow.human_review_queue WHERE status = ''pending'' ORDER BY disagreement_score DESC LIMIT 10;';

-- Update review status
COMMENT ON COLUMN workflow.human_review_queue.status IS
'Example update: UPDATE workflow.human_review_queue SET status = ''reviewed'', human_verdict = ''{"answer": "..."}''::jsonb, human_reviewer = ''user@example.com'', reviewed_at = NOW() WHERE id = 123;';

-- Dashboard query
COMMENT ON MATERIALIZED VIEW workflow.review_queue_summary IS
'Dashboard summary: SELECT * FROM workflow.review_queue_summary ORDER BY status, disagreement_level;';

-- ============================================================================
-- Grants (adjust as needed for your security model)
-- ============================================================================

-- Grant access to application user (adjust username as needed)
-- GRANT SELECT, INSERT, UPDATE ON workflow.human_review_queue TO learning_app;
-- GRANT USAGE, SELECT ON SEQUENCE workflow.human_review_queue_id_seq TO learning_app;
-- GRANT SELECT, INSERT ON workflow.human_feedback_learning TO learning_app;

-- ============================================================================
-- Schema Version
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow.schema_version (
  component TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  applied_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO workflow.schema_version (component, version)
VALUES ('human_review_queue', 1)
ON CONFLICT (component) DO UPDATE SET version = EXCLUDED.version, applied_at = NOW();
