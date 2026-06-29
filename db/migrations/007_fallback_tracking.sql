-- Migration: Add fallback tracking tables
-- Created: 2026-06-28
-- Purpose: Track intelligent fallback attempts and success rates

-- Table: fallback_attempts
-- Tracks all fallback attempts (both successes and failures)
CREATE TABLE IF NOT EXISTS monitoring.fallback_attempts (
  id BIGSERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  provider TEXT NOT NULL,
  tier TEXT NOT NULL,  -- ultra, high, medium, low
  error_message TEXT,
  success BOOLEAN NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fallback_attempts
CREATE INDEX IF NOT EXISTS idx_fallback_attempts_model ON monitoring.fallback_attempts(model);
CREATE INDEX IF NOT EXISTS idx_fallback_attempts_provider ON monitoring.fallback_attempts(provider);
CREATE INDEX IF NOT EXISTS idx_fallback_attempts_tier ON monitoring.fallback_attempts(tier);
CREATE INDEX IF NOT EXISTS idx_fallback_attempts_timestamp ON monitoring.fallback_attempts(timestamp);
CREATE INDEX IF NOT EXISTS idx_fallback_attempts_success ON monitoring.fallback_attempts(success);

-- Table: fallback_success
-- Tracks successful completions (original or after fallback)
CREATE TABLE IF NOT EXISTS monitoring.fallback_success (
  id BIGSERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  provider TEXT NOT NULL,
  tier TEXT NOT NULL,
  fallback_depth INTEGER NOT NULL,  -- 0 = original succeeded, 1+ = fallback depth
  success BOOLEAN NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fallback_success
CREATE INDEX IF NOT EXISTS idx_fallback_success_model ON monitoring.fallback_success(model);
CREATE INDEX IF NOT EXISTS idx_fallback_success_provider ON monitoring.fallback_success(provider);
CREATE INDEX IF NOT EXISTS idx_fallback_success_tier ON monitoring.fallback_success(tier);
CREATE INDEX IF NOT EXISTS idx_fallback_success_depth ON monitoring.fallback_success(fallback_depth);
CREATE INDEX IF NOT EXISTS idx_fallback_success_timestamp ON monitoring.fallback_success(timestamp);

-- Materialized view: fallback_summary
-- Aggregated fallback statistics (refreshed every 5 minutes)
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.fallback_summary AS
SELECT
  tier,
  provider,
  model,
  COUNT(*) as total_attempts,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
  SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
  AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate,
  MAX(timestamp) as last_attempt,
  COUNT(CASE WHEN timestamp > NOW() - INTERVAL '1 hour' THEN 1 END) as last_hour_attempts,
  COUNT(CASE WHEN timestamp > NOW() - INTERVAL '24 hours' THEN 1 END) as last_24h_attempts
FROM monitoring.fallback_attempts
GROUP BY tier, provider, model;

-- Index on materialized view
CREATE INDEX IF NOT EXISTS idx_fallback_summary_tier ON monitoring.fallback_summary(tier);
CREATE INDEX IF NOT EXISTS idx_fallback_summary_provider ON monitoring.fallback_summary(provider);
CREATE INDEX IF NOT EXISTS idx_fallback_summary_success_rate ON monitoring.fallback_summary(success_rate DESC);

-- Materialized view: provider_reliability
-- Per-provider reliability scores (refreshed every 5 minutes)
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.provider_reliability AS
SELECT
  provider,
  tier,
  COUNT(*) as total_calls,
  AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as reliability_score,
  AVG(fallback_depth) as avg_fallback_depth,
  COUNT(CASE WHEN fallback_depth = 0 AND success THEN 1 END) as direct_successes,
  COUNT(CASE WHEN fallback_depth > 0 AND success THEN 1 END) as fallback_successes,
  MAX(timestamp) as last_used
FROM monitoring.fallback_success
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY provider, tier
ORDER BY reliability_score DESC, avg_fallback_depth ASC;

-- Index on materialized view
CREATE INDEX IF NOT EXISTS idx_provider_reliability_provider ON monitoring.provider_reliability(provider);
CREATE INDEX IF NOT EXISTS idx_provider_reliability_tier ON monitoring.provider_reliability(tier);
CREATE INDEX IF NOT EXISTS idx_provider_reliability_score ON monitoring.provider_reliability(reliability_score DESC);

-- Function: Refresh materialized views
CREATE OR REPLACE FUNCTION monitoring.refresh_fallback_views()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.fallback_summary;
  REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.provider_reliability;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON monitoring.fallback_attempts TO PUBLIC;
GRANT SELECT ON monitoring.fallback_success TO PUBLIC;
GRANT SELECT ON monitoring.fallback_summary TO PUBLIC;
GRANT SELECT ON monitoring.provider_reliability TO PUBLIC;
GRANT INSERT ON monitoring.fallback_attempts TO PUBLIC;
GRANT INSERT ON monitoring.fallback_success TO PUBLIC;

-- Comments
COMMENT ON TABLE monitoring.fallback_attempts IS 'Tracks all intelligent fallback attempts';
COMMENT ON TABLE monitoring.fallback_success IS 'Tracks successful completions with fallback depth';
COMMENT ON MATERIALIZED VIEW monitoring.fallback_summary IS 'Aggregated fallback statistics by tier/provider/model';
COMMENT ON MATERIALIZED VIEW monitoring.provider_reliability IS 'Provider reliability scores over last 7 days';
