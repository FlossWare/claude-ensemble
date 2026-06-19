-- Workflow Storage Schema for PostgreSQL
-- Auto-storage of workflow executions with vector embeddings
-- Deployed: 2026-06-19

CREATE SCHEMA IF NOT EXISTS workflows;

CREATE TABLE IF NOT EXISTS workflows.executions (
    id SERIAL PRIMARY KEY,
    workflow_name VARCHAR(255) NOT NULL,
    execution_id VARCHAR(64) NOT NULL UNIQUE,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status VARCHAR(32) NOT NULL CHECK (status IN ('running', 'success', 'failed', 'error', 'timeout')),
    input_prompt TEXT,
    input_args JSONB DEFAULT '{}',
    output_result JSONB,
    error_message TEXT,
    models_used TEXT[],
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10, 6) DEFAULT 0.0,
    execution_trace JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflows_executions_name ON workflows.executions(workflow_name);
CREATE INDEX IF NOT EXISTS idx_workflows_executions_status ON workflows.executions(status);
CREATE INDEX IF NOT EXISTS idx_workflows_executions_started ON workflows.executions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflows_executions_models ON workflows.executions USING GIN(models_used);
CREATE INDEX IF NOT EXISTS idx_workflows_executions_input_args ON workflows.executions USING GIN(input_args);

CREATE TABLE IF NOT EXISTS workflows.embeddings (
    id SERIAL PRIMARY KEY,
    execution_id VARCHAR(64) NOT NULL REFERENCES workflows.executions(execution_id) ON DELETE CASCADE,
    embedding_type VARCHAR(32) NOT NULL CHECK (embedding_type IN ('input', 'output', 'full')),
    embedding vector(768),
    embedded_text TEXT NOT NULL,
    model_name VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflows_embeddings_vector
    ON workflows.embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE MATERIALIZED VIEW IF NOT EXISTS workflows.execution_summary AS
SELECT workflow_name, status, COUNT(*) as execution_count,
       AVG(duration_ms) as avg_duration_ms,
       AVG(total_cost_usd) as avg_cost_usd,
       MIN(started_at) as first_execution,
       MAX(started_at) as last_execution
FROM workflows.executions
WHERE completed_at IS NOT NULL
GROUP BY workflow_name, status;

CREATE OR REPLACE FUNCTION workflows.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_timestamp ON workflows.executions;
CREATE TRIGGER trigger_update_timestamp
    BEFORE UPDATE ON workflows.executions
    FOR EACH ROW
    EXECUTE FUNCTION workflows.update_timestamp();

GRANT USAGE ON SCHEMA workflows TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA workflows TO PUBLIC;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA workflows TO PUBLIC;
