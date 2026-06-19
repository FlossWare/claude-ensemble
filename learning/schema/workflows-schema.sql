-- PostgreSQL Schema for Workflow Learning System
-- Database: learning (laptop-01)
-- Purpose: Store workflow execution data, multi-AI results, and learnings

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Create workflows schema
CREATE SCHEMA IF NOT EXISTS workflows;

-- =============================================================================
-- Core Execution Tables
-- =============================================================================

-- Main workflow executions table
CREATE TABLE IF NOT EXISTS workflows.executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_name VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT,
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'timeout')),
    total_workers INTEGER DEFAULT 0,
    successful_workers INTEGER DEFAULT 0,
    failed_workers INTEGER DEFAULT 0,
    arbiter_model VARCHAR(100),
    final_decision TEXT,
    final_confidence DECIMAL(5,4),
    input_prompt TEXT,
    input_context JSONB,
    output_result TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_executions_workflow ON workflows.executions(workflow_name);
CREATE INDEX IF NOT EXISTS idx_executions_status ON workflows.executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_started ON workflows.executions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_metadata ON workflows.executions USING gin(metadata);

-- Worker results table (one row per worker per execution)
CREATE TABLE IF NOT EXISTS workflows.worker_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    worker_id VARCHAR(255) NOT NULL,
    model VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT,
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'timeout')),
    output TEXT,
    confidence DECIMAL(5,4),
    quality_score DECIMAL(5,4),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10,6),
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_results_execution ON workflows.worker_results(execution_id);
CREATE INDEX IF NOT EXISTS idx_worker_results_model ON workflows.worker_results(model);
CREATE INDEX IF NOT EXISTS idx_worker_results_status ON workflows.worker_results(status);
CREATE INDEX IF NOT EXISTS idx_worker_results_quality ON workflows.worker_results(quality_score DESC NULLS LAST);

-- Arbiter decisions table (one row per arbiter per execution)
CREATE TABLE IF NOT EXISTS workflows.arbiter_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    arbiter_model VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT,
    decision TEXT NOT NULL,
    confidence DECIMAL(5,4),
    rationale TEXT,
    selected_workers TEXT[], -- Array of worker_ids that contributed
    rejected_workers TEXT[], -- Array of worker_ids that were rejected
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10,6),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_execution ON workflows.arbiter_decisions(execution_id);
CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_model ON workflows.arbiter_decisions(arbiter_model);
CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_confidence ON workflows.arbiter_decisions(confidence DESC NULLS LAST);

-- =============================================================================
-- Execution Phases (for multi-phase workflows)
-- =============================================================================

CREATE TABLE IF NOT EXISTS workflows.execution_phases (
    phase_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    phase_name VARCHAR(255) NOT NULL,
    phase_order INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT,
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    input_data JSONB,
    output_data JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_phases_execution ON workflows.execution_phases(execution_id);
CREATE INDEX IF NOT EXISTS idx_execution_phases_order ON workflows.execution_phases(execution_id, phase_order);

-- =============================================================================
-- Feedback and Learning Tables
-- =============================================================================

-- User feedback on workflow results
CREATE TABLE IF NOT EXISTS workflows.feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('quality', 'correctness', 'usefulness', 'efficiency', 'other')),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    ground_truth TEXT, -- For correctness validation
    corrected_output TEXT, -- User's corrected version
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_execution ON workflows.feedback(execution_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON workflows.feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON workflows.feedback(rating);

-- Model combinations that work well together
CREATE TABLE IF NOT EXISTS workflows.model_combinations (
    combination_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_name VARCHAR(255) NOT NULL,
    worker_models VARCHAR(100)[] NOT NULL, -- Array of model names
    arbiter_model VARCHAR(100) NOT NULL,
    num_executions INTEGER DEFAULT 0,
    avg_confidence DECIMAL(5,4),
    avg_quality DECIMAL(5,4),
    avg_duration_ms BIGINT,
    avg_cost_usd DECIMAL(10,6),
    success_rate DECIMAL(5,4),
    last_used_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(workflow_name, worker_models, arbiter_model)
);

CREATE INDEX IF NOT EXISTS idx_model_combinations_workflow ON workflows.model_combinations(workflow_name);
CREATE INDEX IF NOT EXISTS idx_model_combinations_quality ON workflows.model_combinations(avg_quality DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_model_combinations_success ON workflows.model_combinations(success_rate DESC NULLS LAST);

-- =============================================================================
-- Vector Embeddings for Semantic Search
-- =============================================================================

-- Workflow learnings with vector embeddings (768-dim for sentence-transformers)
CREATE TABLE IF NOT EXISTS workflows.learnings (
    learning_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    workflow_name VARCHAR(255) NOT NULL,
    learning_type VARCHAR(50) NOT NULL CHECK (learning_type IN ('pattern', 'failure', 'optimization', 'insight', 'best_practice')),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    embedding vector(768), -- 768-dim for sentence-transformers/all-mpnet-base-v2
    context JSONB, -- Structured context (models used, params, etc.)
    impact_score DECIMAL(5,4), -- How impactful this learning is
    confidence DECIMAL(5,4), -- Confidence in this learning
    verified BOOLEAN DEFAULT FALSE, -- Has this been validated by user?
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learnings_workflow ON workflows.learnings(workflow_name);
CREATE INDEX IF NOT EXISTS idx_learnings_type ON workflows.learnings(learning_type);
CREATE INDEX IF NOT EXISTS idx_learnings_impact ON workflows.learnings(impact_score DESC NULLS LAST);

-- HNSW index for fast vector similarity search (O(log n))
CREATE INDEX IF NOT EXISTS idx_learnings_embedding ON workflows.learnings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Execution embeddings for similar workflow retrieval
CREATE TABLE IF NOT EXISTS workflows.execution_embeddings (
    execution_id UUID PRIMARY KEY REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    input_embedding vector(768), -- Embedding of input prompt
    output_embedding vector(768), -- Embedding of output result
    context_embedding vector(768), -- Embedding of combined context
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW indexes for all embedding types
CREATE INDEX IF NOT EXISTS idx_execution_embeddings_input ON workflows.execution_embeddings
USING hnsw (input_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_execution_embeddings_output ON workflows.execution_embeddings
USING hnsw (output_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_execution_embeddings_context ON workflows.execution_embeddings
USING hnsw (context_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- Materialized Views for Fast Analytics
-- =============================================================================

-- Summary view: workflow performance metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS workflows.summary AS
SELECT
    e.workflow_name,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE e.status = 'completed') as successful_executions,
    COUNT(*) FILTER (WHERE e.status = 'failed') as failed_executions,
    AVG(e.duration_ms) as avg_duration_ms,
    AVG(e.final_confidence) as avg_confidence,
    AVG(wr.quality_score) as avg_quality_score,
    SUM(wr.input_tokens) as total_input_tokens,
    SUM(wr.output_tokens) as total_output_tokens,
    SUM(wr.cost_usd) as total_cost_usd,
    MAX(e.completed_at) as last_execution_at
FROM workflows.executions e
LEFT JOIN workflows.worker_results wr ON e.execution_id = wr.execution_id
WHERE e.status = 'completed'
GROUP BY e.workflow_name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_summary_workflow ON workflows.summary(workflow_name);

-- Model performance view: per-model statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS workflows.model_performance AS
SELECT
    wr.model,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE wr.status = 'completed') as successful_executions,
    AVG(wr.duration_ms) as avg_duration_ms,
    AVG(wr.confidence) as avg_confidence,
    AVG(wr.quality_score) as avg_quality_score,
    SUM(wr.input_tokens) as total_input_tokens,
    SUM(wr.output_tokens) as total_output_tokens,
    SUM(wr.cost_usd) as total_cost_usd,
    MAX(wr.completed_at) as last_used_at
FROM workflows.worker_results wr
WHERE wr.status = 'completed'
GROUP BY wr.model;

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_performance_model ON workflows.model_performance(model);

-- =============================================================================
-- Triggers for Auto-Update
-- =============================================================================

-- Update execution summary when completed
CREATE OR REPLACE FUNCTION workflows.update_execution_summary()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed') AND OLD.status NOT IN ('completed', 'failed') THEN
        -- Calculate duration
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;

        -- Update worker counts
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE status = 'completed'),
            COUNT(*) FILTER (WHERE status = 'failed')
        INTO NEW.total_workers, NEW.successful_workers, NEW.failed_workers
        FROM workflows.worker_results
        WHERE execution_id = NEW.execution_id;
    END IF;

    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_execution_summary
BEFORE UPDATE ON workflows.executions
FOR EACH ROW
EXECUTE FUNCTION workflows.update_execution_summary();

-- Update worker result duration when completed
CREATE OR REPLACE FUNCTION workflows.update_worker_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed', 'timeout') AND NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_worker_duration
BEFORE UPDATE ON workflows.worker_results
FOR EACH ROW
EXECUTE FUNCTION workflows.update_worker_duration();

-- Update arbiter decision duration when completed
CREATE OR REPLACE FUNCTION workflows.update_arbiter_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_arbiter_duration
BEFORE UPDATE ON workflows.arbiter_decisions
FOR EACH ROW
EXECUTE FUNCTION workflows.update_arbiter_duration();

-- Update execution phase duration when completed
CREATE OR REPLACE FUNCTION workflows.update_phase_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed', 'skipped') AND NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_phase_duration
BEFORE UPDATE ON workflows.execution_phases
FOR EACH ROW
EXECUTE FUNCTION workflows.update_phase_duration();

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Refresh materialized views
CREATE OR REPLACE FUNCTION workflows.refresh_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY workflows.summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY workflows.model_performance;
END;
$$ LANGUAGE plpgsql;

-- Find similar executions by input embedding
CREATE OR REPLACE FUNCTION workflows.find_similar_executions(
    query_embedding vector(768),
    similarity_threshold DECIMAL DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    execution_id UUID,
    workflow_name VARCHAR(255),
    similarity DECIMAL,
    input_prompt TEXT,
    output_result TEXT,
    final_confidence DECIMAL,
    completed_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.execution_id,
        e.workflow_name,
        1 - (ee.input_embedding <=> query_embedding) as similarity,
        e.input_prompt,
        e.output_result,
        e.final_confidence,
        e.completed_at
    FROM workflows.execution_embeddings ee
    JOIN workflows.executions e ON ee.execution_id = e.execution_id
    WHERE 1 - (ee.input_embedding <=> query_embedding) >= similarity_threshold
        AND e.status = 'completed'
    ORDER BY ee.input_embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Find relevant learnings by semantic search
CREATE OR REPLACE FUNCTION workflows.find_relevant_learnings(
    query_embedding vector(768),
    workflow_filter VARCHAR(255) DEFAULT NULL,
    similarity_threshold DECIMAL DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    learning_id UUID,
    workflow_name VARCHAR(255),
    learning_type VARCHAR(50),
    title VARCHAR(500),
    description TEXT,
    similarity DECIMAL,
    impact_score DECIMAL,
    verified BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.learning_id,
        l.workflow_name,
        l.learning_type,
        l.title,
        l.description,
        1 - (l.embedding <=> query_embedding) as similarity,
        l.impact_score,
        l.verified
    FROM workflows.learnings l
    WHERE (workflow_filter IS NULL OR l.workflow_name = workflow_filter)
        AND 1 - (l.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY l.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Get best model combination for a workflow
CREATE OR REPLACE FUNCTION workflows.get_best_combination(
    p_workflow_name VARCHAR(255),
    min_executions INTEGER DEFAULT 3
)
RETURNS TABLE (
    worker_models VARCHAR(100)[],
    arbiter_model VARCHAR(100),
    avg_quality DECIMAL,
    success_rate DECIMAL,
    avg_cost_usd DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        mc.worker_models,
        mc.arbiter_model,
        mc.avg_quality,
        mc.success_rate,
        mc.avg_cost_usd
    FROM workflows.model_combinations mc
    WHERE mc.workflow_name = p_workflow_name
        AND mc.num_executions >= min_executions
    ORDER BY mc.avg_quality DESC, mc.success_rate DESC, mc.avg_cost_usd ASC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Initial Data Setup
-- =============================================================================

-- Grant permissions (assuming user sfloess)
GRANT USAGE ON SCHEMA workflows TO sfloess;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA workflows TO sfloess;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA workflows TO sfloess;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA workflows TO sfloess;

-- Enable row-level security (optional, for future multi-user scenarios)
-- ALTER TABLE workflows.executions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE workflows.worker_results ENABLE ROW LEVEL SECURITY;
-- etc.

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Workflows schema created successfully!';
    RAISE NOTICE 'Tables: 10 (executions, worker_results, arbiter_decisions, execution_phases, feedback, model_combinations, learnings, execution_embeddings)';
    RAISE NOTICE 'Materialized Views: 2 (summary, model_performance)';
    RAISE NOTICE 'Indexes: 15+ including 4 HNSW vector indexes';
    RAISE NOTICE 'Functions: 5 helper functions';
    RAISE NOTICE 'Triggers: 4 auto-update triggers';
    RAISE NOTICE 'Ready for workflow learning system integration!';
END $$;
