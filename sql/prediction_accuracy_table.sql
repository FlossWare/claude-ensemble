-- ============================================================================
-- Prediction Accuracy Tracking System
-- ============================================================================
-- Tracks predicted vs actual metrics for workflows to measure model accuracy
-- Location: monitoring.prediction_accuracy
-- Related: monitoring.prediction_errors (materialized view)
-- ============================================================================

-- Ensure schema exists
CREATE SCHEMA IF NOT EXISTS monitoring;

-- ============================================================================
-- Table: monitoring.prediction_accuracy
-- ============================================================================
-- Stores individual prediction records for comparison with actual outcomes
CREATE TABLE IF NOT EXISTS monitoring.prediction_accuracy (
    id BIGSERIAL PRIMARY KEY,

    -- Workflow identification
    workflow_name VARCHAR(255) NOT NULL,
    workflow_execution_id BIGINT,

    -- Cost predictions (USD)
    predicted_cost NUMERIC(10, 4),
    actual_cost NUMERIC(10, 4),

    -- Duration predictions (milliseconds)
    predicted_duration_ms INTEGER,
    actual_duration_ms INTEGER,

    -- Quality predictions (0.0-1.0 scale)
    predicted_quality NUMERIC(3, 2),
    actual_quality NUMERIC(3, 2),

    -- Success predictions (boolean)
    predicted_success BOOLEAN,
    actual_success BOOLEAN,

    -- Model information
    model_used VARCHAR(100),
    predictor_model VARCHAR(100),

    -- Additional context
    input_tokens INTEGER,
    output_tokens INTEGER,
    num_workers INTEGER,

    -- Timestamps
    prediction_timestamp TIMESTAMPTZ,
    actual_completion_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at) (
    PARTITION prediction_accuracy_202607 VALUES FROM ('2026-07-01') TO ('2026-08-01'),
    PARTITION prediction_accuracy_202608 VALUES FROM ('2026-08-01') TO ('2026-09-01'),
    PARTITION prediction_accuracy_default VALUES FROM ('2026-09-01') TO (MAXVALUE)
);

-- ============================================================================
-- Indexes on main table
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_workflow_name
    ON monitoring.prediction_accuracy(workflow_name);

CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_timestamp
    ON monitoring.prediction_accuracy(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_model_used
    ON monitoring.prediction_accuracy(model_used);

CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_predictor_model
    ON monitoring.prediction_accuracy(predictor_model);

CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_actual_success
    ON monitoring.prediction_accuracy(actual_success);

CREATE INDEX IF NOT EXISTS idx_prediction_accuracy_composite_query
    ON monitoring.prediction_accuracy(model_used, created_at DESC);

-- ============================================================================
-- Function: monitoring.refresh_prediction_errors()
-- ============================================================================
-- Refreshes the prediction_errors materialized view
CREATE OR REPLACE FUNCTION monitoring.refresh_prediction_errors()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.prediction_errors;
    UPDATE monitoring.view_refresh_log
    SET last_refresh = NOW(), refresh_count = refresh_count + 1
    WHERE view_name = 'prediction_errors';
END;
$$;

-- ============================================================================
-- Materialized View: monitoring.prediction_errors
-- ============================================================================
-- Aggregated error metrics by model (MAE/RMSE)
-- Refreshed every 5 minutes
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.prediction_errors AS
SELECT
    COALESCE(model_used, 'unknown') as model_used,
    COUNT(*) as total_predictions,
    COUNT(CASE WHEN predicted_success = actual_success THEN 1 END) as correct_predictions,

    -- Cost error metrics (MAE, RMSE)
    ROUND(AVG(ABS(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0)))::NUMERIC, 4)
        as cost_mae,
    ROUND(SQRT(AVG(POWER(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0), 2)))::NUMERIC, 4)
        as cost_rmse,
    ROUND(STDDEV_SAMP(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0))::NUMERIC, 4)
        as cost_stddev,
    ROUND(MIN(COALESCE(actual_cost, 0))::NUMERIC, 4) as cost_min,
    ROUND(MAX(COALESCE(actual_cost, 0))::NUMERIC, 4) as cost_max,

    -- Duration error metrics (MAE, RMSE in ms)
    ROUND(AVG(ABS(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0)))::NUMERIC, 2)
        as duration_mae_ms,
    ROUND(SQRT(AVG(POWER(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0), 2)))::NUMERIC, 2)
        as duration_rmse_ms,
    ROUND(STDDEV_SAMP(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0))::NUMERIC, 2)
        as duration_stddev_ms,
    ROUND(MIN(COALESCE(actual_duration_ms, 0))::NUMERIC, 2) as duration_min_ms,
    ROUND(MAX(COALESCE(actual_duration_ms, 0))::NUMERIC, 2) as duration_max_ms,

    -- Quality error metrics (MAE, RMSE on 0-1 scale)
    ROUND(AVG(ABS(COALESCE(predicted_quality, 0) - COALESCE(actual_quality, 0)))::NUMERIC, 4)
        as quality_mae,
    ROUND(SQRT(AVG(POWER(COALESCE(predicted_quality, 0) - COALESCE(actual_quality, 0), 2)))::NUMERIC, 4)
        as quality_rmse,
    ROUND(STDDEV_SAMP(COALESCE(predicted_quality, 0) - COALESCE(actual_quality, 0))::NUMERIC, 4)
        as quality_stddev,

    -- Success prediction accuracy (percentage)
    ROUND(100.0 * COUNT(CASE WHEN predicted_success = actual_success THEN 1 END) / COUNT(*)::NUMERIC, 2)
        as success_accuracy_percent,

    -- Bias detection (under/over-prediction)
    ROUND(AVG(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0))::NUMERIC, 4)
        as cost_bias,
    ROUND(AVG(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0))::NUMERIC, 2)
        as duration_bias_ms,
    ROUND(AVG(COALESCE(predicted_quality, 0) - COALESCE(actual_quality, 0))::NUMERIC, 4)
        as quality_bias,

    -- Temporal info
    MAX(created_at) as last_updated,
    DATE_TRUNC('day', MAX(created_at)) as latest_day,
    COUNT(DISTINCT DATE(created_at)) as days_of_data

FROM monitoring.prediction_accuracy
WHERE predicted_cost IS NOT NULL
   OR predicted_duration_ms IS NOT NULL
   OR predicted_quality IS NOT NULL
GROUP BY model_used
ORDER BY total_predictions DESC, last_updated DESC;

-- Create indexes on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_errors_model_unique
    ON monitoring.prediction_errors(model_used);

CREATE INDEX IF NOT EXISTS idx_prediction_errors_accuracy
    ON monitoring.prediction_errors(success_accuracy_percent DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_errors_mae
    ON monitoring.prediction_errors(cost_mae DESC);

-- ============================================================================
-- View Refresh Log (for scheduling automation)
-- ============================================================================
CREATE TABLE IF NOT EXISTS monitoring.view_refresh_log (
    view_name VARCHAR(100) PRIMARY KEY,
    last_refresh TIMESTAMPTZ DEFAULT NOW(),
    refresh_count BIGINT DEFAULT 0,
    next_scheduled_refresh TIMESTAMPTZ
);

-- Initialize refresh log
INSERT INTO monitoring.view_refresh_log (view_name, last_refresh, refresh_count)
VALUES ('prediction_errors', NOW(), 0)
ON CONFLICT (view_name) DO NOTHING;

-- ============================================================================
-- Summary View: monitoring.prediction_summary
-- ============================================================================
-- Quick overview of prediction accuracy across all models
CREATE OR REPLACE VIEW monitoring.prediction_summary AS
SELECT
    (SELECT COUNT(*) FROM monitoring.prediction_accuracy) as total_records,
    (SELECT COUNT(DISTINCT model_used) FROM monitoring.prediction_accuracy) as unique_models,
    (SELECT ROUND(AVG(success_accuracy_percent)::NUMERIC, 2)
     FROM monitoring.prediction_errors) as avg_success_accuracy,
    (SELECT ROUND(AVG(cost_mae)::NUMERIC, 4)
     FROM monitoring.prediction_errors) as avg_cost_mae,
    (SELECT ROUND(AVG(duration_mae_ms)::NUMERIC, 2)
     FROM monitoring.prediction_errors) as avg_duration_mae_ms,
    (SELECT MAX(last_updated) FROM monitoring.prediction_errors) as last_update,
    NOW() as query_timestamp;

-- ============================================================================
-- Window Function View: monitoring.prediction_trends
-- ============================================================================
-- Track prediction accuracy trends over time (7-day rolling)
CREATE OR REPLACE VIEW monitoring.prediction_trends AS
SELECT
    model_used,
    DATE_TRUNC('day', created_at)::DATE as prediction_date,
    COUNT(*) as daily_predictions,
    COUNT(CASE WHEN predicted_success = actual_success THEN 1 END)::FLOAT / COUNT(*) as daily_success_rate,
    ROUND(AVG(ABS(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0)))::NUMERIC, 4) as daily_cost_mae,
    ROUND(AVG(ABS(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0)))::NUMERIC, 2) as daily_duration_mae_ms
FROM monitoring.prediction_accuracy
GROUP BY model_used, DATE_TRUNC('day', created_at)
ORDER BY model_used, prediction_date DESC;

-- ============================================================================
-- Anomaly Detection View: monitoring.prediction_anomalies
-- ============================================================================
-- Identify predictions that significantly deviate from baseline
CREATE OR REPLACE VIEW monitoring.prediction_anomalies AS
WITH model_stats AS (
    SELECT
        model_used,
        AVG(ABS(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0))) as cost_mae,
        AVG(ABS(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0))) as duration_mae,
        STDDEV_POP(ABS(COALESCE(predicted_cost, 0) - COALESCE(actual_cost, 0))) as cost_stddev,
        STDDEV_POP(ABS(COALESCE(predicted_duration_ms, 0) - COALESCE(actual_duration_ms, 0))) as duration_stddev
    FROM monitoring.prediction_accuracy
    GROUP BY model_used
)
SELECT
    pa.id,
    pa.workflow_name,
    pa.model_used,
    pa.created_at,
    ABS(COALESCE(pa.predicted_cost, 0) - COALESCE(pa.actual_cost, 0)) as cost_error,
    ABS(COALESCE(pa.predicted_duration_ms, 0) - COALESCE(pa.actual_duration_ms, 0)) as duration_error_ms,
    (ABS(COALESCE(pa.predicted_cost, 0) - COALESCE(pa.actual_cost, 0)) - ms.cost_mae) / NULLIF(ms.cost_stddev, 0) as cost_z_score,
    (ABS(COALESCE(pa.predicted_duration_ms, 0) - COALESCE(pa.actual_duration_ms, 0)) - ms.duration_mae) / NULLIF(ms.duration_stddev, 0) as duration_z_score,
    CASE
        WHEN ABS((ABS(COALESCE(pa.predicted_cost, 0) - COALESCE(pa.actual_cost, 0)) - ms.cost_mae) / NULLIF(ms.cost_stddev, 0)) > 3 THEN 'CRITICAL'
        WHEN ABS((ABS(COALESCE(pa.predicted_cost, 0) - COALESCE(pa.actual_cost, 0)) - ms.cost_mae) / NULLIF(ms.cost_stddev, 0)) > 2 THEN 'HIGH'
        ELSE 'NORMAL'
    END as anomaly_level
FROM monitoring.prediction_accuracy pa
JOIN model_stats ms ON pa.model_used = ms.model_used
WHERE ABS((ABS(COALESCE(pa.predicted_cost, 0) - COALESCE(pa.actual_cost, 0)) - ms.cost_mae) / NULLIF(ms.cost_stddev, 0)) > 2
   OR ABS((ABS(COALESCE(pa.predicted_duration_ms, 0) - COALESCE(pa.actual_duration_ms, 0)) - ms.duration_mae) / NULLIF(ms.duration_stddev, 0)) > 2
ORDER BY created_at DESC;

-- ============================================================================
-- Permissions
-- ============================================================================
GRANT SELECT ON monitoring.prediction_accuracy TO postgres;
GRANT SELECT ON monitoring.prediction_errors TO postgres;
GRANT SELECT ON monitoring.prediction_summary TO postgres;
GRANT SELECT ON monitoring.prediction_trends TO postgres;
GRANT SELECT ON monitoring.prediction_anomalies TO postgres;
GRANT SELECT, INSERT, UPDATE ON monitoring.view_refresh_log TO postgres;

-- ============================================================================
-- Trigger: auto-update updated_at timestamp
-- ============================================================================
CREATE OR REPLACE FUNCTION monitoring.update_prediction_accuracy_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_prediction_accuracy_timestamp
BEFORE UPDATE ON monitoring.prediction_accuracy
FOR EACH ROW
EXECUTE FUNCTION monitoring.update_prediction_accuracy_timestamp();

-- ============================================================================
-- Setup Instructions for Auto-Refresh (via pg_cron)
-- ============================================================================
--
-- To enable automatic refresh every 5 minutes, execute:
--
--   CREATE EXTENSION IF NOT EXISTS pg_cron;
--   SELECT cron.schedule('refresh-prediction-errors', '*/5 * * * *', 'SELECT monitoring.refresh_prediction_errors()');
--
-- To verify scheduled jobs:
--   SELECT * FROM cron.job;
--
-- To unschedule:
--   SELECT cron.unschedule('refresh-prediction-errors');
--
-- ============================================================================

-- ============================================================================
-- Maintenance: Archive Old Data (keep 90 days, archive older)
-- ============================================================================
-- This query can be run periodically to clean up old records
-- (Manual execution recommended - not auto-triggered)
--
-- DELETE FROM monitoring.prediction_accuracy
-- WHERE created_at < NOW() - INTERVAL '90 days';
--
-- ============================================================================
