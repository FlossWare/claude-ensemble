-- Validation Statistics Schema
-- Tracks pre-execution validation outcomes for fleet orchestration
-- Part of ECC issue #193 implementation
-- Created: 2026-07-01

-- Create monitoring schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Validation statistics table
CREATE TABLE IF NOT EXISTS monitoring.validation_stats (
  id SERIAL PRIMARY KEY,
  validation_type VARCHAR(100) NOT NULL,  -- 'parallelizability', 'token_budget', 'model_diversity', 'worker_capacity', 'full'
  passed BOOLEAN NOT NULL,                -- Overall validation result (true = passed, false = blockers present)
  blocked BOOLEAN NOT NULL DEFAULT FALSE, -- Execution was blocked due to validation failure
  override_used BOOLEAN NOT NULL DEFAULT FALSE, -- skipPreValidation flag was used to bypass
  timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

  -- Indexes for common queries
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index on timestamp for time-series queries
CREATE INDEX IF NOT EXISTS idx_validation_stats_timestamp ON monitoring.validation_stats(timestamp DESC);

-- Index on validation type for grouping
CREATE INDEX IF NOT EXISTS idx_validation_stats_type ON monitoring.validation_stats(validation_type);

-- Index on passed/blocked for failure analysis
CREATE INDEX IF NOT EXISTS idx_validation_stats_outcome ON monitoring.validation_stats(passed, blocked);

-- Example queries:
--
-- 1. Recent validation failures:
-- SELECT validation_type, COUNT(*) as failures
-- FROM monitoring.validation_stats
-- WHERE NOT passed AND timestamp > NOW() - INTERVAL '24 hours'
-- GROUP BY validation_type
-- ORDER BY failures DESC;
--
-- 2. Override usage rate:
-- SELECT
--   validation_type,
--   COUNT(*) as total,
--   SUM(CASE WHEN override_used THEN 1 ELSE 0 END) as overrides,
--   ROUND(100.0 * SUM(CASE WHEN override_used THEN 1 ELSE 0 END) / COUNT(*), 2) as override_rate_pct
-- FROM monitoring.validation_stats
-- WHERE timestamp > NOW() - INTERVAL '7 days'
-- GROUP BY validation_type;
--
-- 3. Validation effectiveness (blocked vs passed):
-- SELECT
--   DATE(timestamp) as date,
--   COUNT(*) as total_validations,
--   SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
--   SUM(CASE WHEN blocked THEN 1 ELSE 0 END) as blocked,
--   ROUND(100.0 * SUM(CASE WHEN blocked THEN 1 ELSE 0 END) / COUNT(*), 2) as block_rate_pct
-- FROM monitoring.validation_stats
-- WHERE timestamp > NOW() - INTERVAL '30 days'
-- GROUP BY DATE(timestamp)
-- ORDER BY date DESC;

COMMENT ON TABLE monitoring.validation_stats IS 'Pre-execution validation outcomes for fleet orchestration (ECC #193)';
COMMENT ON COLUMN monitoring.validation_stats.validation_type IS 'Type of validation: parallelizability, token_budget, model_diversity, worker_capacity, or full';
COMMENT ON COLUMN monitoring.validation_stats.passed IS 'True if validation passed (no blockers), false if blockers detected';
COMMENT ON COLUMN monitoring.validation_stats.blocked IS 'True if execution was blocked due to validation failure';
COMMENT ON COLUMN monitoring.validation_stats.override_used IS 'True if skipPreValidation flag was used to bypass validation';
