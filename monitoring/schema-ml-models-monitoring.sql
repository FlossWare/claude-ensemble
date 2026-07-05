-- ML Models Monitoring Schema
-- Purpose: Database tables for ML model performance tracking
-- Created: 2026-07-04
-- Compatible with: PostgreSQL 10+

-- Note: Run this as superuser or user with CREATE TABLE privileges
-- psql -U postgres -d learning -f schema-ml-models-monitoring.sql

-- ============================================================================
-- 1. PREDICTION ACCURACY TABLE
-- ============================================================================
-- Stores accuracy metrics for model predictions
CREATE TABLE IF NOT EXISTS monitoring.prediction_accuracy (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    measurement_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    mae NUMERIC(10, 6),                 -- Mean Absolute Error
    rmse NUMERIC(10, 6),                -- Root Mean Square Error
    r_squared NUMERIC(5, 4),            -- Coefficient of determination (0-1)
    mape NUMERIC(8, 4),                 -- Mean Absolute Percentage Error
    prediction_count INT,
    data_source VARCHAR(255),           -- Source of predictions (test, validation, production)
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_prediction_accuracy_model_time
    ON monitoring.prediction_accuracy(model_name, measurement_time DESC);
CREATE INDEX idx_prediction_accuracy_time
    ON monitoring.prediction_accuracy(measurement_time DESC);

-- ============================================================================
-- 2. MODEL RETRAINING TABLE
-- ============================================================================
-- Tracks model retraining events and improvements
CREATE TABLE IF NOT EXISTS monitoring.model_retraining (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    retrain_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    data_points_used INT,
    previous_mae NUMERIC(10, 6),
    new_mae NUMERIC(10, 6),
    previous_rmse NUMERIC(10, 6),
    new_rmse NUMERIC(10, 6),
    previous_r_squared NUMERIC(5, 4),
    new_r_squared NUMERIC(5, 4),
    improvement_pct NUMERIC(5, 2),      -- ((old - new) / old) * 100
    training_duration_seconds INT,
    validation_set_size INT,
    test_set_size INT,
    retraining_reason VARCHAR(255),     -- e.g., 'drift_detected', 'scheduled', 'manual'
    retrainer_user VARCHAR(255),        -- Who initiated the retraining
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_model_retraining_model_date
    ON monitoring.model_retraining(model_name, retrain_date DESC);
CREATE INDEX idx_model_retraining_date
    ON monitoring.model_retraining(retrain_date DESC);

-- ============================================================================
-- 3. RESOURCE USAGE TABLE
-- ============================================================================
-- Tracks system resource utilization during model operations
CREATE TABLE IF NOT EXISTS monitoring.resource_usage (
    id SERIAL PRIMARY KEY,
    measurement_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_name VARCHAR(255),
    cpu_usage_percent NUMERIC(5, 2),    -- 0-100
    memory_usage_percent NUMERIC(5, 2), -- 0-100
    memory_usage_mb BIGINT,
    disk_usage_percent NUMERIC(5, 2),   -- 0-100
    disk_usage_mb BIGINT,
    gpu_usage_percent NUMERIC(5, 2),    -- 0-100, NULL if no GPU
    gpu_memory_mb INT,
    inference_latency_ms NUMERIC(10, 2),
    throughput_qps INT,                 -- Queries per second
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_resource_usage_time
    ON monitoring.resource_usage(measurement_time DESC);
CREATE INDEX idx_resource_usage_model_time
    ON monitoring.resource_usage(model_name, measurement_time DESC);

-- ============================================================================
-- 4. EXECUTION SUMMARY TABLE
-- ============================================================================
-- Aggregated workflow execution metrics (this should exist already)
-- Adding required fields for dashboard if they don't exist
CREATE TABLE IF NOT EXISTS monitoring.execution_summary (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model VARCHAR(255),
    workflow VARCHAR(255),
    task_type VARCHAR(255),
    quality_score NUMERIC(5, 4),        -- 0-1 scale
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10, 6),
    duration_ms INT,
    outcome VARCHAR(50),                -- 'success', 'error', 'timeout', 'partial'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_summary_timestamp_model_outcome
    ON monitoring.execution_summary(timestamp DESC, model, outcome);
CREATE INDEX IF NOT EXISTS idx_execution_summary_timestamp
    ON monitoring.execution_summary(timestamp DESC);

-- ============================================================================
-- 5. MODEL DRIFT TABLE
-- ============================================================================
-- Tracks data drift and concept drift detection
CREATE TABLE IF NOT EXISTS monitoring.model_drift (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    drift_type VARCHAR(50),             -- 'data_drift', 'concept_drift', 'covariate_shift'
    drift_magnitude NUMERIC(8, 4),      -- 0-1 scale, severity
    affected_features TEXT,             -- JSON array of feature names
    reference_window_size INT,
    detection_window_size INT,
    statistical_test VARCHAR(255),      -- e.g., 'kolmogorov_smirnov', 'js_divergence'
    p_value NUMERIC(8, 6),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by VARCHAR(255),
    remediation_action VARCHAR(255),    -- e.g., 'retrain_scheduled', 'manual_review'
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_model_drift_model_date
    ON monitoring.model_drift(model_name, detected_at DESC);
CREATE INDEX idx_model_drift_detected_at
    ON monitoring.model_drift(detected_at DESC);

-- ============================================================================
-- 6. PREDICTION ERRORS TABLE
-- ============================================================================
-- Detailed error logging for failed predictions
CREATE TABLE IF NOT EXISTS monitoring.prediction_errors (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    prediction_id VARCHAR(255),
    error_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    error_type VARCHAR(50),             -- 'nan_output', 'invalid_input', 'timeout', 'out_of_bounds'
    actual_value NUMERIC(20, 6),
    predicted_value NUMERIC(20, 6),
    absolute_error NUMERIC(20, 6),
    relative_error NUMERIC(8, 4),
    input_features JSONB,               -- Store problematic input
    error_message TEXT,
    severity VARCHAR(50),               -- 'low', 'medium', 'high', 'critical'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_prediction_errors_model_date
    ON monitoring.prediction_errors(model_name, error_at DESC);
CREATE INDEX idx_prediction_errors_error_type
    ON monitoring.prediction_errors(error_type);

-- ============================================================================
-- 7. MODEL INFERENCE LOG TABLE
-- ============================================================================
-- Detailed per-request inference logs
CREATE TABLE IF NOT EXISTS monitoring.inference_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    inference_id VARCHAR(255) UNIQUE,
    request_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    input_tokens INT,
    output_tokens INT,
    latency_ms NUMERIC(10, 2),
    status VARCHAR(50),                 -- 'success', 'error', 'timeout'
    output_quality_score NUMERIC(5, 4),
    cost_usd NUMERIC(10, 6),
    cache_hit BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_inference_log_model_time
    ON monitoring.inference_log(model_name, request_time DESC);
CREATE INDEX idx_inference_log_inference_id
    ON monitoring.inference_log(inference_id);

-- ============================================================================
-- MATERIALIZED VIEWS FOR DASHBOARD PERFORMANCE
-- ============================================================================

-- Hourly aggregation of execution metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.hourly_execution_summary AS
SELECT
    date_trunc('hour', timestamp) as hour,
    model,
    outcome,
    COUNT(*) as execution_count,
    AVG(quality_score) as avg_quality,
    MIN(quality_score) as min_quality,
    MAX(quality_score) as max_quality,
    SUM(cost_usd) as total_cost,
    AVG(duration_ms) as avg_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens
FROM monitoring.execution_summary
GROUP BY 1, 2, 3;

CREATE INDEX IF NOT EXISTS idx_hourly_execution_hour_model
    ON monitoring.hourly_execution_summary(hour DESC, model);

-- Daily model performance summary
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.daily_model_performance AS
SELECT
    date_trunc('day', measurement_time) as day,
    model_name,
    AVG(mae) as avg_mae,
    AVG(rmse) as avg_rmse,
    AVG(r_squared) as avg_r_squared,
    MIN(mae) as min_mae,
    MAX(mae) as max_mae,
    COUNT(*) as measurement_count
FROM monitoring.prediction_accuracy
GROUP BY 1, 2;

CREATE INDEX IF NOT EXISTS idx_daily_performance_day_model
    ON monitoring.daily_model_performance(day DESC, model_name);

-- Model comparison view
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.model_comparison AS
SELECT
    model_name,
    COUNT(*) as total_predictions,
    AVG(mae) as avg_mae,
    STDDEV(mae) as stddev_mae,
    AVG(rmse) as avg_rmse,
    AVG(r_squared) as avg_r_squared,
    MAX(measurement_time) as last_measurement,
    date_part('days', NOW() - MAX(measurement_time))::INT as days_since_measurement
FROM monitoring.prediction_accuracy
WHERE measurement_time >= NOW() - INTERVAL '30 days'
GROUP BY model_name;

CREATE INDEX IF NOT EXISTS idx_model_comparison_avg_mae
    ON monitoring.model_comparison(avg_mae);

-- ============================================================================
-- REFRESH SCHEDULE FOR MATERIALIZED VIEWS
-- ============================================================================
-- Run these periodically (e.g., via cron):
-- 0 * * * * psql -d learning -c "REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.hourly_execution_summary;"
-- 0 2 * * * psql -d learning -c "REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.daily_model_performance;"
-- 0 3 * * * psql -d learning -c "REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.model_comparison;"

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Calculate improvement percentage between two metrics
CREATE OR REPLACE FUNCTION calculate_improvement(
    old_value NUMERIC,
    new_value NUMERIC
) RETURNS NUMERIC AS $$
BEGIN
    IF old_value = 0 OR old_value IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN ((old_value - new_value) / ABS(old_value)) * 100;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Get best performing model (lower error is better)
CREATE OR REPLACE FUNCTION get_best_model()
RETURNS TABLE(model_name VARCHAR, avg_mae NUMERIC) AS $$
SELECT
    model_name,
    AVG(mae) as avg_mae
FROM monitoring.prediction_accuracy
WHERE measurement_time >= NOW() - INTERVAL '7 days'
GROUP BY model_name
ORDER BY avg_mae ASC
LIMIT 1;
$$ LANGUAGE SQL;

-- Get recent drift alerts
CREATE OR REPLACE FUNCTION get_recent_drift_alerts(hours INT DEFAULT 24)
RETURNS TABLE(
    model_name VARCHAR,
    drift_type VARCHAR,
    drift_magnitude NUMERIC,
    detected_at TIMESTAMP WITH TIME ZONE,
    acknowledged BOOLEAN
) AS $$
SELECT
    model_name,
    drift_type,
    drift_magnitude,
    detected_at,
    acknowledged_at IS NOT NULL
FROM monitoring.model_drift
WHERE detected_at >= NOW() - (hours || ' hours')::INTERVAL
ORDER BY detected_at DESC;
$$ LANGUAGE SQL;

-- ============================================================================
-- CLEANUP & RETENTION POLICIES
-- ============================================================================
-- Recommendations for data retention (add to cron/maintenance):
--
-- Remove old prediction accuracy records (keep 90 days):
-- DELETE FROM monitoring.prediction_accuracy
-- WHERE measurement_time < NOW() - INTERVAL '90 days';
--
-- Remove old resource usage records (keep 30 days):
-- DELETE FROM monitoring.resource_usage
-- WHERE measurement_time < NOW() - INTERVAL '30 days';
--
-- Remove old inference logs (keep 30 days):
-- DELETE FROM monitoring.inference_log
-- WHERE request_time < NOW() - INTERVAL '30 days';

-- ============================================================================
-- VERIFY INSTALLATION
-- ============================================================================
-- Run this to verify all tables were created:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'monitoring'
-- ORDER BY table_name;

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================
-- Uncomment to load test data:
--
-- INSERT INTO monitoring.prediction_accuracy
-- (model_name, mae, rmse, r_squared, prediction_count)
-- VALUES
-- ('model-v1', 0.0245, 0.0312, 0.9450, 1000),
-- ('model-v2', 0.0198, 0.0287, 0.9620, 1000),
-- ('model-v3', 0.0267, 0.0334, 0.9380, 1000);
