-- Consensus Cache Table
--
-- Two-level caching for weighted voting consensus results:
-- - Level 1: Exact hash match (cache_key lookup, <1ms)
-- - Level 2: Semantic similarity (vector search, <10ms)
--
-- TTL: 7 days (configurable)
-- Target: Sub-10ms cache hits
--
-- Created: 2026-06-29

-- Main cache table
CREATE TABLE IF NOT EXISTS workflow.consensus_cache (
  id SERIAL PRIMARY KEY,

  -- Level 1: Exact match fields
  cache_key TEXT NOT NULL UNIQUE,
  task_type TEXT NOT NULL,

  -- Level 2: Semantic similarity fields
  semantic_fingerprint TEXT,
  semantic_embedding VECTOR(384),

  -- Cached consensus result
  winning_answer JSONB NOT NULL,
  consensus_level TEXT NOT NULL CHECK (consensus_level IN ('strong', 'moderate', 'weak', 'no_consensus', 'unanimous')),
  consensus_strength NUMERIC,
  total_weight NUMERIC,
  vote_count INTEGER,

  -- Voting metadata (lightweight summary)
  votes JSONB NOT NULL,
  vote_summary JSONB,

  -- Cache metadata
  hit_count INTEGER DEFAULT 0,
  last_hit_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL
);

-- Index for exact match (Level 1 - fastest)
CREATE INDEX IF NOT EXISTS idx_consensus_cache_key
  ON workflow.consensus_cache(cache_key);

-- Index for task type filtering
CREATE INDEX IF NOT EXISTS idx_consensus_cache_task_type
  ON workflow.consensus_cache(task_type);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_consensus_cache_expires
  ON workflow.consensus_cache(expires_at);

-- HNSW index for semantic similarity (Level 2 - fast vector search)
CREATE INDEX IF NOT EXISTS idx_consensus_semantic_embedding
  ON workflow.consensus_cache
  USING hnsw (semantic_embedding vector_cosine_ops);

-- Comments
COMMENT ON TABLE workflow.consensus_cache IS 'Two-level cache for weighted voting consensus results';
COMMENT ON COLUMN workflow.consensus_cache.cache_key IS 'SHA-256 hash of normalized votes + task type';
COMMENT ON COLUMN workflow.consensus_cache.semantic_fingerprint IS 'Natural language summary of votes for semantic search';
COMMENT ON COLUMN workflow.consensus_cache.semantic_embedding IS '1024-dim embedding (all-mpnet-base-v2) for similarity search';
COMMENT ON COLUMN workflow.consensus_cache.winning_answer IS 'Cached winning answer from consensus';
COMMENT ON COLUMN workflow.consensus_cache.vote_summary IS 'Lightweight vote metadata (total_votes, unique_models, unique_answers)';
COMMENT ON COLUMN workflow.consensus_cache.hit_count IS 'Number of times cache entry was hit';
COMMENT ON COLUMN workflow.consensus_cache.expires_at IS 'Cache expiration timestamp (7-day TTL)';
