-- Migration script to update model_drift materialized view column names
-- Run as postgres user:
--   psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-model-drift-view.sql

-- Drop existing view
DROP MATERIALIZED VIEW IF EXISTS monitoring.model_drift CASCADE;

-- Recreate with updated column names (confidence → quality)
CREATE MATERIALIZED VIEW monitoring.model_drift AS
WITH weekly_performance AS (
    SELECT
        model,
        metadata->>'task_type' as task_type,
        DATE_TRUNC('week', created_at) as week_start,
        COUNT(*) as execution_count,
        AVG(confidence) as avg_quality,
        STDDEV(confidence) as stddev_quality,
        AVG(cost_usd) as avg_cost,
        SUM(cost_usd) as total_cost,
        AVG(duration_ms) as avg_duration_ms,
        COUNT(CASE WHEN outcome = 'success' THEN 1 END) as success_count,
        COUNT(CASE WHEN outcome = 'error' THEN 1 END) as error_count
    FROM workflow.worker_results
    WHERE created_at >= NOW() - INTERVAL '90 days'
        AND outcome IN ('success', 'error')
    GROUP BY model, metadata->>'task_type', DATE_TRUNC('week', created_at)
)
SELECT
    model,
    task_type,
    week_start,
    execution_count,
    avg_quality,
    stddev_quality,
    avg_cost,
    total_cost,
    avg_duration_ms,
    success_count,
    error_count,
    CASE
        WHEN execution_count > 0 THEN success_count::FLOAT / execution_count
        ELSE 0
    END as success_rate
FROM weekly_performance
ORDER BY model, task_type, week_start DESC;

-- Recreate indexes
CREATE UNIQUE INDEX idx_model_drift_unique
ON monitoring.model_drift(model, COALESCE(task_type, ''), week_start);

CREATE INDEX idx_model_drift_week
ON monitoring.model_drift(week_start DESC);

-- Grant permissions
GRANT SELECT ON monitoring.model_drift TO PUBLIC;

-- Summary
DO $$
BEGIN
    RAISE NOTICE '✅ Model drift view migration complete';
    RAISE NOTICE '- Dropped old materialized view';
    RAISE NOTICE '- Created new view with avg_quality/stddev_quality columns';
    RAISE NOTICE '- Recreated indexes';
    RAISE NOTICE '';
    RAISE NOTICE 'Column changes:';
    RAISE NOTICE '  avg_confidence → avg_quality';
    RAISE NOTICE '  stddev_confidence → stddev_quality';
END $$;

-- Show updated schema
\d monitoring.model_drift
