-- Schema for workflow learnings storage
-- Stores extracted learnings from ai-extract-learning workflow
-- Links back to execution_summary via execution_id

CREATE SCHEMA IF NOT EXISTS workflows;

-- Main learnings table
CREATE TABLE IF NOT EXISTS workflows.learnings (
  id SERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,                    -- Unique workflow run identifier
  execution_id INTEGER,                     -- Foreign key to monitoring.execution_summary
  workflow_name TEXT NOT NULL,              -- Which workflow generated these learnings
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- User patterns (structured JSONB)
  user_preferences JSONB,                   -- Array of preference strings
  expertise_levels JSONB,                   -- Map of domain -> level
  workflow_usage JSONB,                     -- Array of usage patterns

  -- Code patterns (structured JSONB)
  common_bugs JSONB,                        -- Array of bug pattern strings
  architecture_insights JSONB,              -- Array of insights
  tech_stack JSONB,                         -- Array of technologies
  quality_trends JSONB,                     -- Array of trend observations

  -- Recommendations and memory
  recommendations JSONB,                    -- Array of recommendation strings
  memory_suggestions JSONB,                 -- Array of {type, content, priority}

  -- Full learning object (for queryability)
  learnings JSONB NOT NULL,                 -- Complete learning extraction result

  -- Vector embedding for similarity search
  embedding vector(768),                    -- Sentence embedding of learnings

  -- Metadata
  strategy TEXT,                            -- Strategy used for extraction
  quality_score FLOAT,                      -- Optional quality score

  CONSTRAINT fk_execution
    FOREIGN KEY (execution_id)
    REFERENCES monitoring.execution_summary(id)
    ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_learnings_run_id ON workflows.learnings(run_id);
CREATE INDEX IF NOT EXISTS idx_learnings_workflow ON workflows.learnings(workflow_name);
CREATE INDEX IF NOT EXISTS idx_learnings_timestamp ON workflows.learnings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_learnings_execution_id ON workflows.learnings(execution_id);

-- HNSW index for vector similarity search (O(log n))
CREATE INDEX IF NOT EXISTS idx_learnings_embedding
  ON workflows.learnings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- GIN indexes for JSONB querying
CREATE INDEX IF NOT EXISTS idx_learnings_user_prefs
  ON workflows.learnings
  USING gin (user_preferences);

CREATE INDEX IF NOT EXISTS idx_learnings_tech_stack
  ON workflows.learnings
  USING gin (tech_stack);

CREATE INDEX IF NOT EXISTS idx_learnings_full
  ON workflows.learnings
  USING gin (learnings);

-- View for easy querying of recent learnings
CREATE OR REPLACE VIEW workflows.recent_learnings AS
SELECT
  l.id,
  l.run_id,
  l.workflow_name,
  l.timestamp,
  l.user_preferences,
  l.expertise_levels,
  l.recommendations,
  l.quality_score,
  e.model,
  e.outcome
FROM workflows.learnings l
LEFT JOIN monitoring.execution_summary e ON l.execution_id = e.id
ORDER BY l.timestamp DESC;

-- View for learning statistics by workflow
CREATE OR REPLACE VIEW workflows.learning_stats AS
SELECT
  workflow_name,
  COUNT(*) as total_learnings,
  COUNT(DISTINCT run_id) as unique_runs,
  AVG(quality_score) as avg_quality,
  MAX(timestamp) as last_learning,
  jsonb_agg(DISTINCT jsonb_array_elements(tech_stack)) FILTER (WHERE tech_stack IS NOT NULL) as all_tech_stack
FROM workflows.learnings
GROUP BY workflow_name;

COMMENT ON TABLE workflows.learnings IS 'Extracted learnings from workflow executions, queryable and searchable';
COMMENT ON COLUMN workflows.learnings.embedding IS 'Sentence embedding for semantic similarity search';
COMMENT ON COLUMN workflows.learnings.execution_id IS 'Links back to the workflow execution that generated this learning';
