-- Model Performance Drift Detection Schema
-- Tracks 30-day rolling performance and alerts on >10% degradation
--
-- Usage:
--   psql -h aio-01 -p 5433 -U $USER -d learning -f monitoring/schema-drift-detection.sql

-- Create monitoring schema
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Model drift alerts table (historical log of detected regressions)
CREATE TABLE IF NOT EXISTS monitoring.drift_alerts (
    id SERIAL PRIMARY KEY,
    model VARCHAR(64) NOT NULL,
    task_type VARCHAR(255),
    detection_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Performance metrics
    current_7day_avg REAL NOT NULL,
    historical_30day_avg REAL NOT NULL,
    performance_drop_pct REAL NOT NULL, -- Percentage drop (negative = improvement)

    -- Sample sizes
    current_sample_count INTEGER NOT NULL,
    historical_sample_count INTEGER NOT NULL,

    -- Statistical significance
    stddev_current REAL,
    stddev_historical REAL,

    -- Alert status
    severity VARCHAR(32) NOT NULL DEFAULT 'warning', -- 'warning' | 'critical'
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by VARCHAR(255),

    -- Deduplication tracking
    times_alerted INTEGER DEFAULT 1,
    last_alerted TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_severity CHECK (severity IN ('warning', 'critical'))
);

-- Index for model lookup
CREATE INDEX IF NOT EXISTS idx_drift_alerts_model
ON monitoring.drift_alerts(model);

-- Index for task type lookup
CREATE INDEX IF NOT EXISTS idx_drift_alerts_task_type
ON monitoring.drift_alerts(task_type);

-- Index for unacknowledged alerts
CREATE INDEX IF NOT EXISTS idx_drift_alerts_unacknowledged
ON monitoring.drift_alerts(acknowledged) WHERE acknowledged = FALSE;

-- Index for detection date (for time-series queries)
CREATE INDEX IF NOT EXISTS idx_drift_alerts_detection_date
ON monitoring.drift_alerts(detection_date DESC);

-- Unique index for alert deduplication (one alert per model+task+day)
CREATE UNIQUE INDEX IF NOT EXISTS idx_drift_alerts_unique_daily
ON monitoring.drift_alerts(model, COALESCE(task_type, ''), DATE(detection_date));

-- Materialized view: Model performance by week
-- Aggregates confidence scores, cost, and sample counts
-- Refresh daily via cron
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.model_drift AS
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

-- Index for model + task_type lookup on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_model_drift_unique
ON monitoring.model_drift(model, COALESCE(task_type, ''), week_start);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_model_drift_week
ON monitoring.model_drift(week_start DESC);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION monitoring.refresh_drift_view()
RETURNS void AS $$
BEGIN
    -- Use CONCURRENTLY if unique index exists, otherwise regular refresh
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.model_drift;
    EXCEPTION WHEN OTHERS THEN
        -- Fallback to non-concurrent refresh if CONCURRENTLY fails
        REFRESH MATERIALIZED VIEW monitoring.model_drift;
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to detect drift (>10% drop in confidence)
-- Returns models with performance regression
CREATE OR REPLACE FUNCTION monitoring.detect_model_drift(
    drift_threshold REAL DEFAULT 0.10, -- 10% drop threshold
    min_samples INTEGER DEFAULT 20     -- Minimum samples required (raised from 5)
)
RETURNS TABLE(
    model VARCHAR(64),
    task_type VARCHAR(255),
    current_7day_avg REAL,
    historical_30day_avg REAL,
    performance_drop_pct REAL,
    current_sample_count INTEGER,
    historical_sample_count INTEGER,
    severity VARCHAR(32)
) AS $$
BEGIN
    RETURN QUERY
    WITH current_7day AS (
        SELECT
            md.model,
            md.task_type,
            AVG(md.avg_quality) as avg_qual,
            SUM(md.execution_count) as sample_count,
            STDDEV(md.avg_quality) as stddev_qual
        FROM monitoring.model_drift md
        WHERE md.week_start >= NOW() - INTERVAL '7 days'
        GROUP BY md.model, md.task_type
        HAVING SUM(md.execution_count) >= min_samples
    ),
    historical_30day AS (
        SELECT
            md.model,
            md.task_type,
            AVG(md.avg_quality) as avg_qual,
            SUM(md.execution_count) as sample_count,
            STDDEV(md.avg_quality) as stddev_qual
        FROM monitoring.model_drift md
        WHERE md.week_start >= NOW() - INTERVAL '30 days'
            AND md.week_start < NOW() - INTERVAL '7 days'
        GROUP BY md.model, md.task_type
        HAVING SUM(md.execution_count) >= min_samples
    )
    SELECT
        c.model,
        c.task_type,
        c.avg_qual as current_7day_avg,
        h.avg_qual as historical_30day_avg,
        ((c.avg_qual - h.avg_qual) / h.avg_qual) * 100 as performance_drop_pct,
        c.sample_count::INTEGER as current_sample_count,
        h.sample_count::INTEGER as historical_sample_count,
        CASE
            WHEN ((h.avg_qual - c.avg_qual) / h.avg_qual) > 0.20 THEN 'critical'::VARCHAR(32)
            ELSE 'warning'::VARCHAR(32)
        END as severity
    FROM current_7day c
    INNER JOIN historical_30day h
        ON c.model = h.model
        AND (c.task_type = h.task_type OR (c.task_type IS NULL AND h.task_type IS NULL))
    WHERE c.avg_qual < (h.avg_qual * (1.0 - drift_threshold))
        AND c.sample_count >= min_samples
        AND h.sample_count >= min_samples
    ORDER BY ((h.avg_qual - c.avg_qual) / h.avg_qual) DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to log drift alerts (with deduplication via check-then-insert)
-- Prevents duplicate alerts per model+task_type+day by checking existing alerts first
CREATE OR REPLACE FUNCTION monitoring.log_drift_alert(
    p_model VARCHAR(64),
    p_task_type VARCHAR(255),
    p_current_7day_avg REAL,
    p_historical_30day_avg REAL,
    p_performance_drop_pct REAL,
    p_current_sample_count INTEGER,
    p_historical_sample_count INTEGER,
    p_severity VARCHAR(32),
    p_metadata JSONB DEFAULT '{}'
)
RETURNS INTEGER AS $$
DECLARE
    alert_id INTEGER;
    existing_id INTEGER;
    p_detection_date TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    -- Check if alert already exists for this model+task_type+day
    SELECT id INTO existing_id
    FROM monitoring.drift_alerts
    WHERE model = p_model
        AND (task_type = p_task_type OR (task_type IS NULL AND p_task_type IS NULL))
        AND DATE(detection_date) = DATE(p_detection_date);

    IF existing_id IS NOT NULL THEN
        -- Update existing alert
        UPDATE monitoring.drift_alerts
        SET times_alerted = times_alerted + 1,
            last_alerted = NOW(),
            current_7day_avg = p_current_7day_avg,
            historical_30day_avg = p_historical_30day_avg,
            performance_drop_pct = p_performance_drop_pct,
            current_sample_count = p_current_sample_count,
            historical_sample_count = p_historical_sample_count,
            severity = p_severity,
            metadata = p_metadata
        WHERE id = existing_id;

        alert_id := existing_id;
    ELSE
        -- Insert new alert
        INSERT INTO monitoring.drift_alerts
            (model, task_type, current_7day_avg, historical_30day_avg,
             performance_drop_pct, current_sample_count, historical_sample_count,
             severity, metadata, detection_date, times_alerted, last_alerted)
        VALUES
            (p_model, p_task_type, p_current_7day_avg, p_historical_30day_avg,
             p_performance_drop_pct, p_current_sample_count, p_historical_sample_count,
             p_severity, p_metadata, p_detection_date, 1, p_detection_date)
        RETURNING id INTO alert_id;
    END IF;

    RETURN alert_id;
END;
$$ LANGUAGE plpgsql;

-- Function to acknowledge drift alert
CREATE OR REPLACE FUNCTION monitoring.acknowledge_drift_alert(
    p_alert_id INTEGER,
    p_acknowledged_by VARCHAR(255)
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE monitoring.drift_alerts
    SET acknowledged = TRUE,
        acknowledged_at = NOW(),
        acknowledged_by = p_acknowledged_by
    WHERE id = p_alert_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Create index on human_review_queue if table exists (for drift detector integration)
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'workflow'
        AND table_name = 'human_review_queue'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_hrq_time_range
        ON workflow.human_review_queue(status, updated_at);
        RAISE NOTICE 'Created index idx_hrq_time_range on workflow.human_review_queue';
    ELSE
        RAISE NOTICE 'Skipped: workflow.human_review_queue table does not exist';
    END IF;
END $$;

-- Grant permissions
GRANT USAGE ON SCHEMA monitoring TO PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO PUBLIC;
GRANT SELECT ON monitoring.model_drift TO PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO PUBLIC;

-- Initial materialized view refresh
SELECT monitoring.refresh_drift_view();

-- Summary
DO $$
BEGIN
    RAISE NOTICE '✅ Drift detection schema created successfully';
    RAISE NOTICE '📊 Materialized view: monitoring.model_drift (90-day rolling window, tracks confidence)';
    RAISE NOTICE '🚨 Alert table: monitoring.drift_alerts (with deduplication)';
    RAISE NOTICE '🔍 Detection function: monitoring.detect_model_drift(drift_threshold, min_samples=20)';
    RAISE NOTICE '📝 Log function: monitoring.log_drift_alert(...) - uses check-then-insert for deduplication';
    RAISE NOTICE '✓ Acknowledge function: monitoring.acknowledge_drift_alert(alert_id, user)';
    RAISE NOTICE '🔄 Refresh function: monitoring.refresh_drift_view()';
    RAISE NOTICE '';
    RAISE NOTICE 'Configuration:';
    RAISE NOTICE '- Minimum samples: 20 (raised from 5 to reduce false positives)';
    RAISE NOTICE '- Deduplication: Check-then-insert per (model, task_type, date)';
    RAISE NOTICE '- Metric tracked: confidence field from workflow.worker_results';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Run: node monitoring/drift-detector.cjs (daily via cron)';
    RAISE NOTICE '2. Add to cron: 0 3 * * * cd /path/to/project && node monitoring/drift-detector.cjs';
    RAISE NOTICE '3. Monitor: SELECT * FROM monitoring.drift_alerts WHERE acknowledged = FALSE';
END $$;
