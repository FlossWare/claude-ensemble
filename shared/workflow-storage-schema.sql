-- Workflow Storage Schema
-- PostgreSQL + pgvector for multi-AI workflow orchestration
--
-- Usage:
--   psql -h /var/run/postgresql -U $USER -d learning -f workflow-storage-schema.sql

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create workflow schema
CREATE SCHEMA IF NOT EXISTS workflow;

-- Workflow executions (top-level)
CREATE TABLE IF NOT EXISTS workflow.executions (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(64) UNIQUE NOT NULL,
    workflow_name VARCHAR(255) NOT NULL,
    task_description TEXT NOT NULL,
    task_embedding vector(384), -- all-MiniLM-L6-v2 384-dim
    total_workers INTEGER NOT NULL,
    total_duration_ms BIGINT NOT NULL,
    outcome VARCHAR(32) NOT NULL, -- 'success' | 'failed' | 'error'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_outcome CHECK (outcome IN ('success', 'failed', 'error'))
);

-- Index for similarity search
CREATE INDEX IF NOT EXISTS idx_executions_embedding
ON workflow.executions USING ivfflat (task_embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_executions_workflow_id
ON workflow.executions(workflow_id);

-- Index for outcome filtering
CREATE INDEX IF NOT EXISTS idx_executions_outcome
ON workflow.executions(outcome);

-- Worker results
CREATE TABLE IF NOT EXISTS workflow.worker_results (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
    worker_id VARCHAR(64) NOT NULL,
    model VARCHAR(64) NOT NULL,
    task_assigned TEXT NOT NULL,
    result TEXT NOT NULL,
    result_embedding vector(384), -- all-MiniLM-L6-v2 384-dim
    confidence REAL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    duration_ms BIGINT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd NUMERIC(10, 6) NOT NULL,
    outcome VARCHAR(32) NOT NULL, -- 'success' | 'failed' | 'error'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_worker_outcome CHECK (outcome IN ('success', 'failed', 'error'))
);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_worker_results_workflow
ON workflow.worker_results(workflow_execution_id);

-- Index for similarity search
CREATE INDEX IF NOT EXISTS idx_worker_results_embedding
ON workflow.worker_results USING ivfflat (result_embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for model analysis
CREATE INDEX IF NOT EXISTS idx_worker_results_model
ON workflow.worker_results(model);

-- Arbiter decisions
CREATE TABLE IF NOT EXISTS workflow.arbiter_decisions (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
    arbiter_model VARCHAR(64) NOT NULL,
    worker_result_ids INTEGER[] NOT NULL, -- Array of worker result IDs
    decision TEXT NOT NULL,
    decision_embedding vector(384), -- all-MiniLM-L6-v2 384-dim
    reasoning TEXT NOT NULL,
    confidence REAL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    duration_ms BIGINT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd NUMERIC(10, 6) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_workflow
ON workflow.arbiter_decisions(workflow_execution_id);

-- Index for similarity search
CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_embedding
ON workflow.arbiter_decisions USING ivfflat (decision_embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for arbiter model analysis
CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_model
ON workflow.arbiter_decisions(arbiter_model);

-- Workflow phases
CREATE TABLE IF NOT EXISTS workflow.phases (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
    phase_name VARCHAR(255) NOT NULL,
    phase_order INTEGER NOT NULL,
    duration_ms BIGINT NOT NULL,
    outcome VARCHAR(32) NOT NULL, -- 'success' | 'failed' | 'error'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_phase_outcome CHECK (outcome IN ('success', 'failed', 'error'))
);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_phases_workflow
ON workflow.phases(workflow_execution_id);

-- Index for phase ordering
CREATE INDEX IF NOT EXISTS idx_phases_order
ON workflow.phases(workflow_execution_id, phase_order);

-- Feedback on workflow executions
CREATE TABLE IF NOT EXISTS workflow.feedback (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
    feedback_type VARCHAR(32) NOT NULL, -- 'user' | 'automated' | 'adversarial'
    quality_score REAL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    feedback_text TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_feedback_type CHECK (feedback_type IN ('user', 'automated', 'adversarial'))
);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_feedback_workflow
ON workflow.feedback(workflow_execution_id);

-- Index for feedback type filtering
CREATE INDEX IF NOT EXISTS idx_feedback_type
ON workflow.feedback(feedback_type);

-- Learnings extracted from workflows
CREATE TABLE IF NOT EXISTS workflow.learnings (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,
    learning_type VARCHAR(32) NOT NULL, -- 'pattern' | 'failure' | 'optimization'
    description TEXT NOT NULL,
    learning_embedding vector(384), -- all-MiniLM-L6-v2 384-dim
    actionable_insight TEXT NOT NULL,
    importance REAL CHECK (importance >= 0.0 AND importance <= 1.0),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_learning_type CHECK (learning_type IN ('pattern', 'failure', 'optimization'))
);

-- Index for workflow lookup
CREATE INDEX IF NOT EXISTS idx_learnings_workflow
ON workflow.learnings(workflow_execution_id);

-- Index for similarity search
CREATE INDEX IF NOT EXISTS idx_learnings_embedding
ON workflow.learnings USING ivfflat (learning_embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for importance filtering
CREATE INDEX IF NOT EXISTS idx_learnings_importance
ON workflow.learnings(importance DESC);

-- Grant permissions (adjust user as needed)
GRANT USAGE ON SCHEMA workflow TO sfloess;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA workflow TO sfloess;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA workflow TO sfloess;

-- Summary statistics view
CREATE OR REPLACE VIEW workflow.execution_stats AS
SELECT
    workflow_name,
    outcome,
    COUNT(*) as count,
    AVG(total_duration_ms) as avg_duration_ms,
    AVG(total_workers) as avg_workers,
    MIN(created_at) as first_seen,
    MAX(created_at) as last_seen
FROM workflow.executions
GROUP BY workflow_name, outcome;

-- Model performance view
CREATE OR REPLACE VIEW workflow.model_performance AS
SELECT
    model,
    outcome,
    COUNT(*) as executions,
    AVG(confidence) as avg_confidence,
    AVG(duration_ms) as avg_duration_ms,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd
FROM workflow.worker_results
GROUP BY model, outcome;

-- Arbiter effectiveness view
CREATE OR REPLACE VIEW workflow.arbiter_effectiveness AS
SELECT
    arbiter_model,
    COUNT(*) as decisions,
    AVG(confidence) as avg_confidence,
    AVG(duration_ms) as avg_duration_ms,
    SUM(cost_usd) as total_cost_usd
FROM workflow.arbiter_decisions
GROUP BY arbiter_model;

COMMENT ON SCHEMA workflow IS 'Multi-AI workflow orchestration storage (PostgreSQL + pgvector)';
COMMENT ON TABLE workflow.executions IS 'Top-level workflow execution metadata';
COMMENT ON TABLE workflow.worker_results IS 'Individual worker execution results';
COMMENT ON TABLE workflow.arbiter_decisions IS 'Arbiter consensus decisions';
COMMENT ON TABLE workflow.phases IS 'Workflow phase tracking';
COMMENT ON TABLE workflow.feedback IS 'Human/automated feedback on workflows';
COMMENT ON TABLE workflow.learnings IS 'Extracted learnings from workflow execution';
