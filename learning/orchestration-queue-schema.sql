-- Persistent Orchestration Queue Schema
-- Purpose: Track all fleet work across reboots with chunking + vectorDB + graphDB

CREATE SCHEMA IF NOT EXISTS orchestration;

-- Main task queue with vector embeddings
CREATE TABLE IF NOT EXISTS orchestration.task_queue (
  id SERIAL PRIMARY KEY,
  task_id TEXT UNIQUE NOT NULL,
  task_type TEXT NOT NULL, -- 'code_review', 'deep_research', 'firmware_analysis', etc.
  description TEXT NOT NULL,
  embedding vector(384), -- For semantic similarity search

  -- Assignment
  assigned_worker TEXT, -- NULL = unassigned, or worker hostname
  workflow_run_id TEXT, -- Links to actual workflow execution

  -- Status tracking
  status TEXT NOT NULL DEFAULT 'queued', -- 'queued', 'running', 'completed', 'failed', 'paused'
  priority INTEGER DEFAULT 50, -- 0-100, higher = more urgent

  -- Dependencies
  depends_on INTEGER[], -- Array of task_queue.id that must complete first
  blocks INTEGER[], -- Array of task_queue.id that are waiting on this

  -- Progress tracking
  progress_percent INTEGER DEFAULT 0,
  current_phase TEXT,
  phases_total INTEGER,
  phases_completed INTEGER DEFAULT 0,

  -- Timing
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  estimated_duration_ms BIGINT,
  actual_duration_ms BIGINT,

  -- Resource tracking
  input_tokens BIGINT DEFAULT 0,
  output_tokens BIGINT DEFAULT 0,
  cost_usd NUMERIC(10,6) DEFAULT 0,

  -- Metadata (flexible JSONB)
  metadata JSONB DEFAULT '{}',

  -- Result storage
  result_path TEXT, -- Path to output file
  result_summary TEXT,
  outcome TEXT, -- 'success', 'error', 'timeout', 'user_cancelled'
  error_message TEXT
);

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_task_queue_embedding
  ON orchestration.task_queue
  USING hnsw (embedding vector_cosine_ops);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON orchestration.task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_worker ON orchestration.task_queue(assigned_worker);
CREATE INDEX IF NOT EXISTS idx_task_queue_type ON orchestration.task_queue(task_type);
CREATE INDEX IF NOT EXISTS idx_task_queue_priority ON orchestration.task_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_task_queue_created ON orchestration.task_queue(created_at);

-- Worker heartbeats (detect dead workers)
CREATE TABLE IF NOT EXISTS orchestration.worker_heartbeats (
  worker_id TEXT PRIMARY KEY,
  hostname TEXT NOT NULL,
  last_seen TIMESTAMPTZ DEFAULT NOW(),
  current_task_id TEXT REFERENCES orchestration.task_queue(task_id),
  status TEXT DEFAULT 'idle', -- 'idle', 'busy', 'offline'
  capabilities JSONB DEFAULT '{}', -- Models available, resources, etc.
  metadata JSONB DEFAULT '{}'
);

-- Task progress log (chunked updates)
CREATE TABLE IF NOT EXISTS orchestration.task_progress_log (
  id SERIAL PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES orchestration.task_queue(task_id),
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  phase TEXT,
  message TEXT,
  progress_percent INTEGER,
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_progress_task_time
  ON orchestration.task_progress_log(task_id, timestamp DESC);

-- Task dependencies graph (for Neo4j sync)
CREATE TABLE IF NOT EXISTS orchestration.task_dependencies (
  id SERIAL PRIMARY KEY,
  from_task_id TEXT NOT NULL REFERENCES orchestration.task_queue(task_id),
  to_task_id TEXT NOT NULL REFERENCES orchestration.task_queue(task_id),
  dependency_type TEXT NOT NULL, -- 'blocks', 'prerequisite', 'related'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}',
  UNIQUE(from_task_id, to_task_id, dependency_type)
);

-- Materialized view: Queue summary
CREATE MATERIALIZED VIEW IF NOT EXISTS orchestration.queue_summary AS
SELECT
  status,
  task_type,
  COUNT(*) as count,
  AVG(progress_percent) as avg_progress,
  SUM(input_tokens) as total_input_tokens,
  SUM(output_tokens) as total_output_tokens,
  SUM(cost_usd) as total_cost,
  MIN(created_at) as oldest_task,
  MAX(created_at) as newest_task
FROM orchestration.task_queue
GROUP BY status, task_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_summary_unique
  ON orchestration.queue_summary(status, task_type);

-- Materialized view: Worker utilization
CREATE MATERIALIZED VIEW IF NOT EXISTS orchestration.worker_utilization AS
SELECT
  w.worker_id,
  w.hostname,
  w.status,
  w.last_seen,
  COUNT(t.id) FILTER (WHERE t.status = 'running') as active_tasks,
  COUNT(t.id) FILTER (WHERE t.status = 'completed') as completed_tasks,
  SUM(t.actual_duration_ms) FILTER (WHERE t.status = 'completed') as total_work_ms,
  SUM(t.cost_usd) as total_cost
FROM orchestration.worker_heartbeats w
LEFT JOIN orchestration.task_queue t ON w.worker_id = t.assigned_worker
GROUP BY w.worker_id, w.hostname, w.status, w.last_seen;

CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_util_unique
  ON orchestration.worker_utilization(worker_id);

-- Auto-refresh views every 5 minutes
COMMENT ON MATERIALIZED VIEW orchestration.queue_summary IS
  'Auto-refresh: */5 * * * * (every 5 minutes)';
COMMENT ON MATERIALIZED VIEW orchestration.worker_utilization IS
  'Auto-refresh: */5 * * * * (every 5 minutes)';

-- Grant permissions
GRANT ALL ON SCHEMA orchestration TO sfloess;
GRANT ALL ON ALL TABLES IN SCHEMA orchestration TO sfloess;
GRANT ALL ON ALL SEQUENCES IN SCHEMA orchestration TO sfloess;
GRANT SELECT ON ALL TABLES IN SCHEMA orchestration TO sfloess;
