-- Migration 011: Create workflow.worker_results table for dashboard
-- Purpose: Store worker task execution results for performance dashboard
-- Created: 2026-09-25
-- Status: Required for Model Performance Dashboard Phase 1

-- Drop table if exists (for fresh schema deployment)
DROP TABLE IF EXISTS workflow.worker_results CASCADE;

-- ============================================================================
-- WORKER RESULTS TABLE (required by performance_dashboard.py)
-- ============================================================================
CREATE TABLE workflow.worker_results (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(255) NOT NULL,
    worker_id VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    task_assigned TEXT NOT NULL,
    outcome VARCHAR(50) NOT NULL,  -- 'success', 'error', 'timeout'
    quality_score NUMERIC(5, 4),   -- 0-1 scale (from Thompson sampling)
    duration_ms INTEGER,            -- Execution time in milliseconds
    input_tokens INTEGER,           -- Token counts
    output_tokens INTEGER,
    cost_usd NUMERIC(10, 6),        -- Cost in USD
    ttft_ms INTEGER,                -- Time to first token
    queue_wait_ms INTEGER,          -- Queue wait time
    retry_overhead_ms INTEGER,      -- Total retry overhead
    cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for dashboard queries
CREATE INDEX idx_worker_results_created_at
    ON workflow.worker_results(created_at DESC);
CREATE INDEX idx_worker_results_model_created
    ON workflow.worker_results(model, created_at DESC);
CREATE INDEX idx_worker_results_worker_id
    ON workflow.worker_results(worker_id);
CREATE INDEX idx_worker_results_task_type
    ON workflow.worker_results(task_assigned);
CREATE INDEX idx_worker_results_outcome
    ON workflow.worker_results(outcome, created_at DESC);

-- ============================================================================
-- HOURLY PERFORMANCE AGGREGATES (for peak hours analysis)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow.hourly_performance (
    id SERIAL PRIMARY KEY,
    measurement_date DATE NOT NULL,
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day < 24),
    executions INTEGER DEFAULT 0,
    successes INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    avg_duration_ms NUMERIC(10, 2),
    success_rate NUMERIC(5, 4),
    period_type VARCHAR(50),  -- 'peak' or 'off_peak'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(measurement_date, hour_of_day)
);

CREATE INDEX idx_hourly_perf_date
    ON workflow.hourly_performance(measurement_date DESC);
CREATE INDEX idx_hourly_perf_hour
    ON workflow.hourly_performance(hour_of_day);

-- ============================================================================
-- MODEL REGRESSION ANALYSIS TABLE (for consensus replay results)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow.replays (
    id SERIAL PRIMARY KEY,
    original_workflow_id VARCHAR(255) NOT NULL,
    replayed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verdict VARCHAR(100),  -- 'SIGNIFICANT_IMPROVEMENT', 'MODERATE_IMPROVEMENT', 'DEGRADATION', 'STABLE'
    avg_confidence_delta NUMERIC(10, 6),  -- Average confidence change
    arbiter_confidence_delta NUMERIC(10, 6),  -- Arbiter confidence change
    total_cost_delta NUMERIC(10, 6),  -- Cost change in USD
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_replays_replayed_at
    ON workflow.replays(replayed_at DESC);
CREATE INDEX idx_replays_verdict
    ON workflow.replays(verdict);

-- ============================================================================
-- SCHEMA VERSION TABLE (for validation checks)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow.schema_version (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- Insert current migration version
INSERT INTO workflow.schema_version (migration_name, description)
VALUES ('011_dashboard_worker_results', 'Worker results table for performance dashboard')
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();

-- Grant permissions (adjust user as needed)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA workflow TO claude;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA workflow TO claude;

COMMIT;
