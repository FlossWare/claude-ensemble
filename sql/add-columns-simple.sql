-- Quick column addition (minimal version to avoid locks)
ALTER TABLE monitoring.execution_summary ADD COLUMN IF NOT EXISTS quality_score NUMERIC(3,2) DEFAULT 0.75;
ALTER TABLE monitoring.execution_summary ADD COLUMN IF NOT EXISTS circuit_breaker_state VARCHAR(32) DEFAULT 'closed';
ALTER TABLE workflow.executions ADD COLUMN IF NOT EXISTS quality_score NUMERIC(3,2) DEFAULT 0.75;
