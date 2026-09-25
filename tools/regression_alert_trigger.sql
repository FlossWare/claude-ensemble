-- Regression Alert Trigger - Blocker #1 Fix
--
-- Detects quality drops > 5% and fires alerts
-- Compatible with PostgreSQL 10+
--
-- Install:
--   psql -U postgres -d learning -f tools/regression_alert_trigger.sql

-- ============================================================================
-- 1. REGRESSION ALERTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow.regression_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,  -- 'quality_drop', 'latency_increase', 'error_rate_spike'
    model_name VARCHAR(64),
    baseline_metric FLOAT,             -- 7-day average (before)
    current_metric FLOAT,              -- Current measurement
    degradation_pct FLOAT,             -- (baseline - current) / baseline * 100
    severity VARCHAR(20),              -- 'low', 'medium', 'high', 'critical'
    threshold_exceeded FLOAT,          -- Alert threshold (e.g., 5.0 for 5%)
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    webhook_fired BOOLEAN DEFAULT FALSE,
    webhook_response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_regression_alerts_created_at
    ON workflow.regression_alerts(created_at DESC);
CREATE INDEX idx_regression_alerts_model_type
    ON workflow.regression_alerts(model_name, alert_type, created_at DESC);
CREATE INDEX idx_regression_alerts_acknowledged
    ON workflow.regression_alerts(is_acknowledged, created_at DESC);

-- ============================================================================
-- 2. QUALITY METRICS TABLE (for 7-day baseline calculation)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow.quality_metrics (
    id SERIAL PRIMARY KEY,
    measurement_date DATE NOT NULL,
    model_name VARCHAR(64),
    metric_type VARCHAR(50) NOT NULL,  -- 'quality_score', 'latency_ms', 'error_rate'
    baseline_7day FLOAT,               -- 7-day rolling average
    current_value FLOAT,
    change_pct FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_quality_metrics_model_date
    ON workflow.quality_metrics(model_name, measurement_date DESC);
CREATE INDEX idx_quality_metrics_metric_type
    ON workflow.quality_metrics(metric_type, measurement_date DESC);

-- ============================================================================
-- 3. FUNCTION: Calculate baseline metrics (7-day average)
-- ============================================================================
CREATE OR REPLACE FUNCTION calculate_quality_baseline(
    p_model_name VARCHAR,
    p_days INT DEFAULT 7
)
RETURNS TABLE(
    model VARCHAR,
    avg_quality FLOAT,
    avg_latency FLOAT,
    error_rate FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        wr.model,
        AVG(CASE
            WHEN wr.metadata->>'quality_score' IS NOT NULL
            THEN CAST(wr.metadata->>'quality_score' AS FLOAT)
            ELSE 0.5
        END) as avg_quality,
        AVG(wr.duration_ms) as avg_latency,
        (COUNT(*) FILTER (WHERE wr.outcome != 'success')::FLOAT /
         NULLIF(COUNT(*)::FLOAT, 0) * 100) as error_rate
    FROM workflow.worker_results wr
    WHERE wr.model = p_model_name
    AND wr.created_at > NOW() - (p_days || ' days')::INTERVAL
    GROUP BY wr.model;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. FUNCTION: Detect quality regression
-- ============================================================================
CREATE OR REPLACE FUNCTION detect_quality_regression(
    p_quality_threshold FLOAT DEFAULT 5.0  -- Alert if drop > 5%
)
RETURNS TABLE(
    model_name VARCHAR,
    baseline_quality FLOAT,
    current_quality FLOAT,
    degradation_pct FLOAT,
    needs_alert BOOLEAN
) AS $$
DECLARE
    v_baseline FLOAT;
    v_current FLOAT;
    v_degradation FLOAT;
BEGIN
    -- Get last 24 hours average
    RETURN QUERY
    WITH baseline_metrics AS (
        SELECT
            wr.model,
            AVG(CASE
                WHEN wr.metadata->>'quality_score' IS NOT NULL
                THEN CAST(wr.metadata->>'quality_score' AS FLOAT)
                ELSE 0.5
            END) as avg_quality
        FROM workflow.worker_results wr
        WHERE wr.created_at BETWEEN (NOW() - '8 days'::INTERVAL) AND (NOW() - '1 day'::INTERVAL)
        GROUP BY wr.model
    ),
    current_metrics AS (
        SELECT
            wr.model,
            AVG(CASE
                WHEN wr.metadata->>'quality_score' IS NOT NULL
                THEN CAST(wr.metadata->>'quality_score' AS FLOAT)
                ELSE 0.5
            END) as avg_quality
        FROM workflow.worker_results wr
        WHERE wr.created_at > NOW() - '1 day'::INTERVAL
        GROUP BY wr.model
    )
    SELECT
        cm.model,
        COALESCE(bm.avg_quality, 0.75) as baseline,
        cm.avg_quality as current,
        ((COALESCE(bm.avg_quality, 0.75) - cm.avg_quality) /
         NULLIF(COALESCE(bm.avg_quality, 0.75), 0) * 100) as degradation,
        ((COALESCE(bm.avg_quality, 0.75) - cm.avg_quality) /
         NULLIF(COALESCE(bm.avg_quality, 0.75), 0) * 100) > p_quality_threshold as needs_alert
    FROM current_metrics cm
    LEFT JOIN baseline_metrics bm ON bm.model = cm.model;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. FUNCTION: Fire regression alert (to webhook)
-- ============================================================================
CREATE OR REPLACE FUNCTION fire_regression_alert(
    p_model_name VARCHAR,
    p_baseline FLOAT,
    p_current FLOAT,
    p_degradation FLOAT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_severity VARCHAR(20);
    v_alert_id INT;
BEGIN
    -- Determine severity
    IF ABS(p_degradation) > 20 THEN
        v_severity := 'critical';
    ELSIF ABS(p_degradation) > 10 THEN
        v_severity := 'high';
    ELSIF ABS(p_degradation) > 5 THEN
        v_severity := 'medium';
    ELSE
        v_severity := 'low';
    END IF;

    -- Insert alert record
    INSERT INTO workflow.regression_alerts (
        alert_type, model_name, baseline_metric, current_metric,
        degradation_pct, severity, threshold_exceeded
    ) VALUES (
        'quality_drop', p_model_name, p_baseline, p_current,
        p_degradation, v_severity, 5.0
    )
    RETURNING id INTO v_alert_id;

    -- Log alert
    RAISE NOTICE 'Regression alert fired: % - quality drop %.1f%% (baseline %.2f → current %.2f)',
        p_model_name, p_degradation, p_baseline, p_current;

    RETURN TRUE;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Failed to fire regression alert: %', SQLERRM;
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. TRIGGER: Auto-fire alerts on quality drop
-- ============================================================================
CREATE OR REPLACE FUNCTION trigger_regression_check()
RETURNS TRIGGER AS $$
DECLARE
    v_regressions RECORD;
    v_quality_threshold FLOAT := 5.0;  -- Alert threshold: 5% drop
    v_outcome_count INT;
BEGIN
    -- Count outcomes in last 24 hours
    SELECT COUNT(*) INTO v_outcome_count
    FROM workflow.worker_results
    WHERE created_at > NOW() - '1 day'::INTERVAL;

    -- Only check if we have sufficient data (>10 recent outcomes)
    IF v_outcome_count > 10 THEN
        FOR v_regressions IN
            SELECT * FROM detect_quality_regression(v_quality_threshold)
            WHERE needs_alert = TRUE
        LOOP
            -- Fire alert for each detected regression
            PERFORM fire_regression_alert(
                v_regressions.model_name,
                v_regressions.baseline_quality,
                v_regressions.current_quality,
                v_regressions.degradation_pct
            );
        END LOOP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger fires on worker_results inserts (check every new outcome)
DROP TRIGGER IF EXISTS trg_regression_check ON workflow.worker_results;
CREATE TRIGGER trg_regression_check
AFTER INSERT ON workflow.worker_results
FOR EACH STATEMENT
EXECUTE FUNCTION trigger_regression_check();

-- ============================================================================
-- 7. MATERIALIZED VIEW: Recent regression alerts
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS workflow.recent_regression_alerts AS
SELECT
    id,
    alert_type,
    model_name,
    baseline_metric,
    current_metric,
    degradation_pct,
    severity,
    is_acknowledged,
    created_at,
    AGE(NOW(), created_at) as time_since_alert
FROM workflow.regression_alerts
WHERE created_at > NOW() - '7 days'::INTERVAL
ORDER BY created_at DESC;

CREATE INDEX idx_recent_regression_alerts_severity
    ON workflow.recent_regression_alerts(severity);

-- ============================================================================
-- 8. HELPER: Acknowledge alert
-- ============================================================================
CREATE OR REPLACE FUNCTION acknowledge_regression_alert(
    p_alert_id INT,
    p_acknowledged_by VARCHAR DEFAULT 'system'
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE workflow.regression_alerts
    SET
        is_acknowledged = TRUE,
        acknowledged_by = p_acknowledged_by,
        acknowledged_at = NOW(),
        updated_at = NOW()
    WHERE id = p_alert_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. CONFIGURATION TABLE (for thresholds)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow.alert_thresholds (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL UNIQUE,
    threshold_value FLOAT NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default thresholds
INSERT INTO workflow.alert_thresholds (alert_type, threshold_value, description, enabled)
VALUES
    ('quality_drop', 5.0, 'Alert if quality drops > 5%', TRUE),
    ('latency_increase', 20.0, 'Alert if latency increases > 20%', TRUE),
    ('error_rate_spike', 10.0, 'Alert if error rate increases > 10%', TRUE)
ON CONFLICT (alert_type) DO NOTHING;

-- ============================================================================
-- 10. VERIFY INSTALLATION
-- ============================================================================
-- Run this to verify all objects were created:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'workflow'
-- AND table_name IN ('regression_alerts', 'quality_metrics', 'alert_thresholds')
-- ORDER BY table_name;
