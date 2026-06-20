-- Test Database Schema Setup for Workflow Storage Integration Tests
-- Creates all required tables with constraints and indices

-- Create schemas
CREATE SCHEMA IF NOT EXISTS workflow;
CREATE SCHEMA IF NOT EXISTS learning;
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS costs;

-- ============================================================================
-- Workflow Execution Tracking
-- ============================================================================

-- Main workflow execution records
CREATE TABLE IF NOT EXISTS workflow.executions (
  id SERIAL PRIMARY KEY,
  workflow_id VARCHAR(64) NOT NULL UNIQUE,
  workflow_name VARCHAR(255) NOT NULL,
  task_description TEXT NOT NULL,
  task_embedding VECTOR(384),
  total_workers INTEGER NOT NULL,
  total_duration_ms BIGINT NOT NULL,
  outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('success', 'failed', 'error')),
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_outcome ON workflow.executions(outcome);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_name ON workflow.executions(workflow_name);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_created_at ON workflow.executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_embedding ON workflow.executions USING ivfflat (task_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Worker Results
-- ============================================================================

-- Individual worker outputs
CREATE TABLE IF NOT EXISTS workflow.worker_results (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
  worker_id VARCHAR(64) NOT NULL,
  model VARCHAR(64) NOT NULL,
  task_assigned TEXT NOT NULL,
  result TEXT,
  result_embedding VECTOR(384),
  confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  duration_ms BIGINT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd NUMERIC(10,4),
  outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('success', 'failed', 'error')),
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_results_execution_id ON workflow.worker_results(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_worker_results_model ON workflow.worker_results(model);
CREATE INDEX IF NOT EXISTS idx_worker_results_outcome ON workflow.worker_results(outcome);
CREATE INDEX IF NOT EXISTS idx_worker_results_embedding ON workflow.worker_results USING ivfflat (result_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Arbiter Decisions
-- ============================================================================

-- Arbiter synthesis results
CREATE TABLE IF NOT EXISTS workflow.arbiter_decisions (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
  arbiter_model VARCHAR(64) NOT NULL,
  worker_result_ids INTEGER[] NOT NULL,
  decision TEXT NOT NULL,
  decision_embedding VECTOR(384),
  reasoning TEXT,
  confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  duration_ms BIGINT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd NUMERIC(10,4),
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_execution_id ON workflow.arbiter_decisions(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_embedding ON workflow.arbiter_decisions USING ivfflat (decision_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Phase Tracking
-- ============================================================================

-- Phase execution tracking
CREATE TABLE IF NOT EXISTS workflow.phases (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
  phase_name VARCHAR(255) NOT NULL,
  phase_order INTEGER NOT NULL,
  duration_ms BIGINT NOT NULL,
  outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('success', 'failed', 'error')),
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phases_execution_id ON workflow.phases(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_phases_name ON workflow.phases(phase_name);

-- ============================================================================
-- Feedback
-- ============================================================================

-- Quality feedback on workflows
CREATE TABLE IF NOT EXISTS workflow.feedback (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
  feedback_type VARCHAR(64) NOT NULL,
  quality_score NUMERIC(3,2) NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
  feedback_text TEXT,
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_execution_id ON workflow.feedback(workflow_execution_id);

-- ============================================================================
-- Learnings
-- ============================================================================

-- Extracted learnings from workflows
CREATE TABLE IF NOT EXISTS workflow.learnings (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
  learning_type VARCHAR(64) NOT NULL CHECK (learning_type IN ('pattern', 'failure', 'optimization')),
  description TEXT NOT NULL,
  actionable_insight TEXT NOT NULL,
  learning_embedding VECTOR(384),
  importance NUMERIC(3,2) CHECK (importance IS NULL OR (importance >= 0.0 AND importance <= 1.0)),
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learnings_execution_id ON workflow.learnings(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_learnings_type ON workflow.learnings(learning_type);
CREATE INDEX IF NOT EXISTS idx_learnings_importance ON workflow.learnings(importance DESC);
CREATE INDEX IF NOT EXISTS idx_learnings_embedding ON workflow.learnings USING ivfflat (learning_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Thompson Sampling Bandit
-- ============================================================================

-- Thompson Sampling bandit state
CREATE TABLE IF NOT EXISTS learning.strategy_performance (
  id SERIAL PRIMARY KEY,
  strategy VARCHAR(255) NOT NULL UNIQUE,
  successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0,
  alpha NUMERIC(8,4) NOT NULL DEFAULT 1.0,
  beta NUMERIC(8,4) NOT NULL DEFAULT 1.0,
  total_reward NUMERIC(8,4) NOT NULL DEFAULT 0.0,
  avg_reward NUMERIC(5,4) NOT NULL DEFAULT 0.0,
  last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_perf_avg_reward ON learning.strategy_performance(avg_reward DESC);

-- ============================================================================
-- Experience Memory
-- ============================================================================

-- Continual learning experience memory
CREATE TABLE IF NOT EXISTS learning.experiences (
  id SERIAL PRIMARY KEY,
  problem_type VARCHAR(255) NOT NULL,
  problem_hash VARCHAR(16),
  context JSONB,
  embedding VECTOR(128),
  strategy VARCHAR(255),
  success BOOLEAN NOT NULL,
  reward NUMERIC(5,4) NOT NULL,
  novelty_score NUMERIC(3,2),
  importance NUMERIC(3,2),
  timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiences_problem_type ON learning.experiences(problem_type);
CREATE INDEX IF NOT EXISTS idx_experiences_success ON learning.experiences(success);
CREATE INDEX IF NOT EXISTS idx_experiences_embedding ON learning.experiences USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Execution Monitoring
-- ============================================================================

-- Execution monitoring logs
CREATE TABLE IF NOT EXISTS monitoring.execution_summary (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
  model VARCHAR(64) NOT NULL,
  workflow VARCHAR(255),
  task_type VARCHAR(255),
  quality_score NUMERIC(3,2),
  input_tokens BIGINT,
  output_tokens BIGINT,
  cost_usd NUMERIC(10,4),
  duration_ms BIGINT,
  outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('success', 'failed', 'error')),
  metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_execution_summary_model ON monitoring.execution_summary(model);
CREATE INDEX IF NOT EXISTS idx_execution_summary_timestamp ON monitoring.execution_summary(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_execution_summary_workflow ON monitoring.execution_summary(workflow);

-- ============================================================================
-- Cost Tracking
-- ============================================================================

-- Cost tracking
CREATE TABLE IF NOT EXISTS costs.entries (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
  model VARCHAR(64) NOT NULL,
  input_tokens BIGINT,
  output_tokens BIGINT,
  total_cost NUMERIC(10,4) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_costs_model ON costs.entries(model);
CREATE INDEX IF NOT EXISTS idx_costs_timestamp ON costs.entries(timestamp DESC);

-- ============================================================================
-- Grant permissions to test user
-- ============================================================================

GRANT ALL PRIVILEGES ON SCHEMA workflow, learning, monitoring, costs TO test_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA workflow, learning, monitoring, costs TO test_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA workflow, learning, monitoring, costs TO test_user;
