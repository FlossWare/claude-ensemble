-- Workflow Completions Schema
-- Stores workflow execution metadata + embeddings for semantic search

CREATE TABLE IF NOT EXISTS learning.workflow_completions (
  id SERIAL PRIMARY KEY,
  workflow_name TEXT NOT NULL,
  session_id TEXT NOT NULL UNIQUE,
  query TEXT NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  duration_ms INTEGER,
  status TEXT CHECK (status IN ('running', 'completed', 'failed')),
  phases JSONB,
  result_summary TEXT,
  embedding vector(768),  -- 768-dim for sentence-transformers/all-mpnet-base-v2
  embedding_cleared_at TIMESTAMP,  -- Track when embedding was deleted for retention
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast similarity search (O(log n))
CREATE INDEX IF NOT EXISTS idx_workflow_embeddings_hnsw
  ON learning.workflow_completions
  USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL;

-- Index for retention cleanup (find old embeddings)
CREATE INDEX IF NOT EXISTS idx_workflow_completions_completed_at
  ON learning.workflow_completions (completed_at)
  WHERE embedding IS NOT NULL;

-- Index for active workflows
CREATE INDEX IF NOT EXISTS idx_workflow_completions_status
  ON learning.workflow_completions (status, started_at);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON learning.workflow_completions TO postgres;
GRANT USAGE, SELECT ON SEQUENCE learning.workflow_completions_id_seq TO postgres;

COMMENT ON TABLE learning.workflow_completions IS
'Workflow execution tracking with semantic embeddings for search.
Embeddings are cleared after 90 days to save storage (2× overhead due to HNSW index).';

COMMENT ON COLUMN learning.workflow_completions.embedding IS
'768-dim embedding of workflow query + result summary.
Cleared after retention period (90 days) to save 6KB per row (3KB vector + 3KB HNSW index).';
