-- Tool Validation Schema
-- Stores results of pre-tool validation checks
-- Created: 2026-07-01 (ECC issue #235)

-- Create workflow schema if not exists
CREATE SCHEMA IF NOT EXISTS workflow;

-- Tool validations table
CREATE TABLE IF NOT EXISTS workflow.tool_validations (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER REFERENCES workflow.executions(id) ON DELETE CASCADE,
    tool_name VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL,
    valid BOOLEAN NOT NULL,
    errors TEXT[],
    warnings TEXT[],
    dry_run BOOLEAN DEFAULT false,
    permission_check BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tool_validations_workflow_id
    ON workflow.tool_validations(workflow_execution_id);

CREATE INDEX IF NOT EXISTS idx_tool_validations_tool_name
    ON workflow.tool_validations(tool_name);

CREATE INDEX IF NOT EXISTS idx_tool_validations_valid
    ON workflow.tool_validations(valid);

CREATE INDEX IF NOT EXISTS idx_tool_validations_created_at
    ON workflow.tool_validations(created_at DESC);

-- Materialized view for validation statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS workflow.validation_stats AS
SELECT
    tool_name,
    COUNT(*) as total_validations,
    SUM(CASE WHEN valid THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN NOT valid THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN valid THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate,
    ARRAY_AGG(DISTINCT unnested_error) FILTER (WHERE unnested_error IS NOT NULL) as common_errors
FROM workflow.tool_validations
CROSS JOIN LATERAL unnest(errors) AS unnested_error
GROUP BY tool_name
ORDER BY total_validations DESC;

-- Refresh materialized view function
CREATE OR REPLACE FUNCTION refresh_validation_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW workflow.validation_stats;
END;
$$ LANGUAGE plpgsql;

-- Comments
COMMENT ON TABLE workflow.tool_validations IS 'Pre-tool validation results for Bash, Read, Write, Edit calls';
COMMENT ON COLUMN workflow.tool_validations.workflow_execution_id IS 'Parent workflow execution (NULL if standalone validation)';
COMMENT ON COLUMN workflow.tool_validations.tool_name IS 'Tool being validated (Bash, Read, Write, Edit)';
COMMENT ON COLUMN workflow.tool_validations.parameters IS 'Tool parameters (JSON)';
COMMENT ON COLUMN workflow.tool_validations.valid IS 'True if validation passed, false if errors detected';
COMMENT ON COLUMN workflow.tool_validations.errors IS 'Validation errors (blocks execution)';
COMMENT ON COLUMN workflow.tool_validations.warnings IS 'Validation warnings (non-blocking)';
COMMENT ON COLUMN workflow.tool_validations.dry_run IS 'True if validation was dry-run only';
COMMENT ON COLUMN workflow.tool_validations.permission_check IS 'True if file permission checks were performed';
