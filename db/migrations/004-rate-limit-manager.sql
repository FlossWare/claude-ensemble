-- Migration: Rate Limit Manager Tables
-- Created: 2026-06-28
-- Description: Sliding window rate limiting for API providers

-- Create monitoring schema if not exists
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Rate limits summary table
CREATE TABLE IF NOT EXISTS monitoring.rate_limits (
  provider VARCHAR(200) PRIMARY KEY,
  requests_last_minute INT DEFAULT 0,
  requests_last_hour INT DEFAULT 0,
  last_reset TIMESTAMPTZ DEFAULT NOW(),
  last_request TIMESTAMPTZ,
  total_requests BIGINT DEFAULT 0,
  throttled_count INT DEFAULT 0,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_rate_limits_last_reset
ON monitoring.rate_limits(last_reset);

-- Request history table for sliding window
CREATE TABLE IF NOT EXISTS monitoring.rate_limit_requests (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(200) NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  success BOOLEAN DEFAULT TRUE,
  metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for sliding window queries (provider + timestamp)
CREATE INDEX IF NOT EXISTS idx_rlr_provider_timestamp
ON monitoring.rate_limit_requests(provider, timestamp DESC);

-- Grant permissions
GRANT USAGE ON SCHEMA monitoring TO sfloess;
GRANT SELECT, INSERT, UPDATE, DELETE ON monitoring.rate_limits TO sfloess;
GRANT SELECT, INSERT, DELETE ON monitoring.rate_limit_requests TO sfloess;
GRANT USAGE, SELECT ON SEQUENCE monitoring.rate_limit_requests_id_seq TO sfloess;
