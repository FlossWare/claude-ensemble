-- API Health Monitoring Tables
-- Created: 2026-06-28
-- Purpose: Track API provider health and auto-disable failing providers

CREATE SCHEMA IF NOT EXISTS monitoring;

-- Provider health status (current state)
CREATE TABLE IF NOT EXISTS monitoring.api_health_status (
  provider VARCHAR(100) PRIMARY KEY,
  success_rate NUMERIC(5,4) NOT NULL DEFAULT 1.0,
  total_checks INTEGER NOT NULL DEFAULT 0,
  successful_checks INTEGER NOT NULL DEFAULT 0,
  failed_checks INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'healthy',
  last_check TIMESTAMPTZ,
  last_success TIMESTAMPTZ,
  last_failure TIMESTAMPTZ,
  failure_reason TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'::jsonb,
  CONSTRAINT valid_status CHECK (status IN ('healthy', 'degraded', 'disabled')),
  CONSTRAINT valid_success_rate CHECK (success_rate >= 0.0 AND success_rate <= 1.0)
);

-- Health check history (rolling window)
CREATE TABLE IF NOT EXISTS monitoring.api_health_checks (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(100) NOT NULL,
  success BOOLEAN NOT NULL,
  response_time_ms INTEGER,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_api_health_checks_provider_created
ON monitoring.api_health_checks(provider, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_health_status_status
ON monitoring.api_health_status(status);

-- Comments
COMMENT ON TABLE monitoring.api_health_status IS 'Current health status for each API provider';
COMMENT ON TABLE monitoring.api_health_checks IS 'Historical health check results (last N attempts)';
COMMENT ON COLUMN monitoring.api_health_status.success_rate IS 'Success rate over last 20 checks (0.0-1.0)';
COMMENT ON COLUMN monitoring.api_health_status.status IS 'healthy (>75%), degraded (50-75%), disabled (<50%)';

-- Materialized view for provider analytics (optional)
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.provider_health_summary AS
SELECT
  s.provider,
  s.status,
  s.success_rate,
  s.total_checks,
  s.successful_checks,
  s.failed_checks,
  s.last_check,
  s.last_success,
  s.last_failure,
  COUNT(c.id) FILTER (WHERE c.created_at >= NOW() - INTERVAL '1 hour') as checks_last_hour,
  COUNT(c.id) FILTER (WHERE c.created_at >= NOW() - INTERVAL '1 hour' AND c.success = true) as successes_last_hour,
  AVG(c.response_time_ms) FILTER (WHERE c.created_at >= NOW() - INTERVAL '1 hour' AND c.success = true) as avg_response_time_ms
FROM monitoring.api_health_status s
LEFT JOIN monitoring.api_health_checks c ON s.provider = c.provider
GROUP BY s.provider, s.status, s.success_rate, s.total_checks, s.successful_checks, s.failed_checks,
         s.last_check, s.last_success, s.last_failure;

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_health_summary_provider
ON monitoring.provider_health_summary(provider);

COMMENT ON MATERIALIZED VIEW monitoring.provider_health_summary IS 'Aggregated provider health metrics (refresh every 5 min)';

-- Grant permissions (adjust user as needed)
-- GRANT SELECT, INSERT, UPDATE ON monitoring.api_health_status TO claude;
-- GRANT SELECT, INSERT ON monitoring.api_health_checks TO claude;
-- GRANT SELECT ON monitoring.provider_health_summary TO claude;
