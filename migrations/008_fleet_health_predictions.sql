-- Migration: Fleet Health Predictions Table
-- GitLab Issue: #108
-- Purpose: Store AI-based predictive health analysis results
-- Run: psql -h aio-01 -p 5433 -U claude -d learning -f migrations/008_fleet_health_predictions.sql

-- Create monitoring schema if not exists
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Drop table if exists (for clean reinstall)
-- DROP TABLE IF EXISTS monitoring.health_predictions CASCADE;

-- Create health_predictions table
CREATE TABLE IF NOT EXISTS monitoring.health_predictions (
  id SERIAL PRIMARY KEY,
  hostname TEXT NOT NULL,
  degradation_probability REAL NOT NULL CHECK (degradation_probability >= 0.0 AND degradation_probability <= 1.0),
  primary_risk TEXT,
  time_to_failure_hours REAL,
  validated_probability REAL CHECK (validated_probability IS NULL OR (validated_probability >= 0.0 AND validated_probability <= 1.0)),
  validation_confidence REAL CHECK (validation_confidence IS NULL OR (validation_confidence >= 0.0 AND validation_confidence <= 1.0)),
  decision_action TEXT,
  decision_urgency TEXT,
  evidence JSONB,
  reasoning TEXT,
  predicted_at TIMESTAMP NOT NULL DEFAULT NOW(),

  -- Constraints
  CONSTRAINT valid_primary_risk CHECK (
    primary_risk IN ('memory_leak', 'cpu_thermal', 'disk_saturation', 'load_spike', 'none', 'unknown', 'error')
  ),
  CONSTRAINT valid_decision_action CHECK (
    decision_action IN ('migrate_immediately', 'schedule_migration', 'monitor_closely', 'no_action', 'error', 'no_prediction')
  ),
  CONSTRAINT valid_decision_urgency CHECK (
    decision_urgency IN ('critical', 'high', 'medium', 'low', 'unknown')
  )
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_health_predictions_hostname_predicted
  ON monitoring.health_predictions (hostname, predicted_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_predictions_degradation
  ON monitoring.health_predictions (degradation_probability DESC)
  WHERE degradation_probability >= 0.70;

CREATE INDEX IF NOT EXISTS idx_health_predictions_recent
  ON monitoring.health_predictions (predicted_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_predictions_critical
  ON monitoring.health_predictions (decision_urgency)
  WHERE decision_urgency IN ('critical', 'high');

-- Create view for latest predictions per server
CREATE OR REPLACE VIEW monitoring.latest_health_predictions AS
SELECT DISTINCT ON (hostname)
  hostname,
  degradation_probability,
  primary_risk,
  time_to_failure_hours,
  validated_probability,
  validation_confidence,
  decision_action,
  decision_urgency,
  predicted_at,
  CASE
    WHEN degradation_probability >= 0.95 THEN 'failing'
    WHEN degradation_probability >= 0.85 THEN 'critical'
    WHEN degradation_probability >= 0.70 THEN 'degraded'
    WHEN degradation_probability >= 0.50 THEN 'at_risk'
    ELSE 'healthy'
  END as health_status
FROM monitoring.health_predictions
ORDER BY hostname, predicted_at DESC;

-- Create view for degraded servers (requires action)
CREATE OR REPLACE VIEW monitoring.degraded_servers AS
SELECT *
FROM monitoring.latest_health_predictions
WHERE degradation_probability >= 0.70
ORDER BY degradation_probability DESC;

-- Grant permissions
GRANT SELECT, INSERT ON monitoring.health_predictions TO claude;
GRANT USAGE, SELECT ON SEQUENCE monitoring.health_predictions_id_seq TO claude;
GRANT SELECT ON monitoring.latest_health_predictions TO claude;
GRANT SELECT ON monitoring.degraded_servers TO claude;

-- Example queries
COMMENT ON TABLE monitoring.health_predictions IS 'AI-based predictive server failure detection results from fleet-health-predictor (Issue #108)';
COMMENT ON VIEW monitoring.latest_health_predictions IS 'Latest prediction for each server with derived health_status';
COMMENT ON VIEW monitoring.degraded_servers IS 'Servers requiring action (degradation >= 70%)';

-- Insert test data
INSERT INTO monitoring.health_predictions (
  hostname,
  degradation_probability,
  primary_risk,
  time_to_failure_hours,
  validated_probability,
  validation_confidence,
  decision_action,
  decision_urgency,
  evidence,
  reasoning
) VALUES
(
  'test-server',
  0.85,
  'memory_leak',
  24.0,
  0.87,
  0.92,
  'schedule_migration',
  'high',
  '{"haiku_evidence": ["Memory RSS growing 15% per day", "Swap usage increasing"], "sonnet_reasoning": "Confirmed memory leak pattern", "opus_reasoning": "Schedule migration within 12 hours"}',
  'Memory leak detected with high confidence - recommend migration within 12 hours'
);

-- Verify installation
SELECT
  'Table created' as status,
  COUNT(*) as test_rows
FROM monitoring.health_predictions;

SELECT
  'Latest predictions view' as status,
  COUNT(*) as servers
FROM monitoring.latest_health_predictions;

SELECT
  'Degraded servers view' as status,
  COUNT(*) as degraded_count
FROM monitoring.degraded_servers;

-- Cleanup test data (optional)
-- DELETE FROM monitoring.health_predictions WHERE hostname = 'test-server';

\echo ''
\echo 'Migration 008 completed successfully!'
\echo 'Table: monitoring.health_predictions'
\echo 'Views: monitoring.latest_health_predictions, monitoring.degraded_servers'
\echo ''
