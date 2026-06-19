-- ============================================================================
-- Workflows Schema for Learning System
-- Stores workflow execution metadata, learnings, and reaction signals
-- ============================================================================

-- Create workflows schema
CREATE SCHEMA IF NOT EXISTS workflows;

-- ============================================================================
-- workflows.learnings - Stores learnings from workflow executions
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflows.learnings (
  id SERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,                    -- Workflow run identifier (FK for traceability)
  workflow_name TEXT NOT NULL,             -- Name of the workflow (e.g., 'ai-consensus-weighted')
  learning_type TEXT NOT NULL,             -- Type of learning: 'model_behavior', 'task_difficulty', 'routing_decision'
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Model behavior tracking (from ai-reaction-tracker)
  reaction_signals JSONB,                  -- Full reaction signals object from ai-reaction-tracker
  task_difficulty TEXT,                    -- 'easy', 'moderate', 'hard' (from reaction analysis)

  -- Task metadata
  task_type TEXT,                          -- Type of task executed
  task_summary TEXT,                       -- Brief description of the task

  -- Quality metrics
  quality_score FLOAT,                     -- Quality score (0.0 to 1.0)
  outcome TEXT,                            -- 'success', 'failed', 'error'

  -- Consensus/voting metadata
  model_count INTEGER,                     -- Number of models involved
  polarization_index INTEGER,              -- Disagreement level (0-100)
  behavioral_agreement INTEGER,            -- Agreement percentage (0-100)

  -- Performance metrics
  duration_ms INTEGER,                     -- Total execution time
  cost_usd FLOAT,                          -- Total cost in USD

  -- Additional context
  metadata JSONB,                          -- Additional workflow-specific data
  embedding vector(768),                   -- Embedding for semantic search (optional)

  -- Indexes
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_learnings_run_id ON workflows.learnings(run_id);
CREATE INDEX IF NOT EXISTS idx_learnings_workflow ON workflows.learnings(workflow_name);
CREATE INDEX IF NOT EXISTS idx_learnings_type ON workflows.learnings(learning_type);
CREATE INDEX IF NOT EXISTS idx_learnings_task_type ON workflows.learnings(task_type);
CREATE INDEX IF NOT EXISTS idx_learnings_timestamp ON workflows.learnings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_learnings_difficulty ON workflows.learnings(task_difficulty);
CREATE INDEX IF NOT EXISTS idx_learnings_outcome ON workflows.learnings(outcome);

-- HNSW index for vector similarity search (if embedding is used)
CREATE INDEX IF NOT EXISTS idx_learnings_embedding ON workflows.learnings
  USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL;

-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_learnings_reaction_signals ON workflows.learnings
  USING gin (reaction_signals)
  WHERE reaction_signals IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_learnings_metadata ON workflows.learnings
  USING gin (metadata)
  WHERE metadata IS NOT NULL;

-- ============================================================================
-- workflows.runs - Stores workflow run metadata
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflows.runs (
  run_id TEXT PRIMARY KEY,
  workflow_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL,                    -- 'running', 'completed', 'failed', 'error'
  input_args JSONB,                        -- Input arguments to the workflow
  output_result JSONB,                     -- Final result from the workflow
  error_message TEXT,                      -- Error message if failed
  duration_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for workflow runs
CREATE INDEX IF NOT EXISTS idx_runs_workflow ON workflows.runs(workflow_name);
CREATE INDEX IF NOT EXISTS idx_runs_status ON workflows.runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON workflows.runs(started_at DESC);

-- ============================================================================
-- Helper views for common queries
-- ============================================================================

-- View: Recent model behavior learnings
CREATE OR REPLACE VIEW workflows.recent_model_behaviors AS
SELECT
  id,
  run_id,
  workflow_name,
  timestamp,
  task_type,
  task_difficulty,
  quality_score,
  outcome,
  model_count,
  polarization_index,
  behavioral_agreement,
  reaction_signals->>'avg_composite_score' AS avg_composite_score,
  reaction_signals->>'avg_uncertainty' AS avg_uncertainty,
  duration_ms,
  cost_usd
FROM workflows.learnings
WHERE learning_type = 'model_behavior'
  AND reaction_signals IS NOT NULL
ORDER BY timestamp DESC
LIMIT 100;

-- View: Task difficulty distribution
CREATE OR REPLACE VIEW workflows.task_difficulty_stats AS
SELECT
  task_type,
  task_difficulty,
  COUNT(*) AS count,
  AVG(quality_score)::float AS avg_quality,
  AVG(duration_ms)::float AS avg_duration_ms,
  AVG(model_count)::float AS avg_models_used,
  AVG(polarization_index)::float AS avg_polarization
FROM workflows.learnings
WHERE task_difficulty IS NOT NULL
GROUP BY task_type, task_difficulty
ORDER BY task_type, task_difficulty;

-- View: Workflow performance summary
CREATE OR REPLACE VIEW workflows.performance_summary AS
SELECT
  workflow_name,
  COUNT(*) AS total_runs,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS successful_runs,
  AVG(quality_score)::float AS avg_quality,
  AVG(duration_ms)::float AS avg_duration_ms,
  AVG(cost_usd)::float AS avg_cost_usd,
  MAX(timestamp) AS last_run
FROM workflows.learnings
GROUP BY workflow_name
ORDER BY total_runs DESC;

-- ============================================================================
-- Grant permissions
-- ============================================================================
GRANT USAGE ON SCHEMA workflows TO sfloess;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA workflows TO sfloess;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA workflows TO sfloess;
GRANT SELECT ON ALL TABLES IN SCHEMA workflows TO PUBLIC;
