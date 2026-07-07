-- Resource Estimation Learning Schema (Issue #109)
-- Purpose: Track actual resource usage and learn optimal estimates
-- Created: 2026-07-07
-- Compatible with: PostgreSQL 10+

-- ============================================================================
-- 1. RESOURCE ESTIMATION LOG
-- ============================================================================
-- Records actual vs estimated resource usage for all agent jobs
CREATE TABLE IF NOT EXISTS monitoring.resource_estimation_log (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  prompt_length INT NOT NULL,
  model VARCHAR(255) NOT NULL,
  schema_complexity INT DEFAULT 0,
  job_type VARCHAR(255) NOT NULL,
  estimated_duration INT NOT NULL,
  estimated_ram NUMERIC(5, 2) NOT NULL,
  actual_duration INT NOT NULL,
  actual_ram NUMERIC(5, 2) NOT NULL,
  duration_error NUMERIC(5, 4) NOT NULL,
  ram_error NUMERIC(5, 4) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resource_estimation_timestamp
  ON monitoring.resource_estimation_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_resource_estimation_model
  ON monitoring.resource_estimation_log(model, job_type);
CREATE INDEX IF NOT EXISTS idx_resource_estimation_error
  ON monitoring.resource_estimation_log(duration_error DESC, ram_error DESC);

-- ============================================================================
-- 2. RESOURCE ESTIMATION COEFFICIENTS
-- ============================================================================
-- Stores learned regression coefficients from Haiku-based training
CREATE TABLE IF NOT EXISTS monitoring.resource_estimation_coefficients (
  id SERIAL PRIMARY KEY,
  trained_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  job_count INT NOT NULL,
  coefficients JSONB NOT NULL,
  duration_mae NUMERIC(10, 2),
  duration_rmse NUMERIC(10, 2),
  ram_mae NUMERIC(5, 4),
  ram_rmse NUMERIC(5, 4),
  improvement_pct NUMERIC(5, 2),
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resource_coefficients_trained_at
  ON monitoring.resource_estimation_coefficients(trained_at DESC);

-- ============================================================================
-- VERIFY INSTALLATION
-- ============================================================================
SELECT 'Resource estimation tables created successfully' as status;

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

-- View recent jobs with high error rates
-- SELECT timestamp, model, job_type, duration_error, ram_error
-- FROM monitoring.resource_estimation_log
-- WHERE duration_error > 0.5 OR ram_error > 0.5
-- ORDER BY timestamp DESC
-- LIMIT 20;

-- View training history
-- SELECT trained_at, job_count, duration_mae, ram_mae, improvement_pct
-- FROM monitoring.resource_estimation_coefficients
-- ORDER BY trained_at DESC;

-- Average error rates by model
-- SELECT
--   model,
--   COUNT(*) as jobs,
--   AVG(duration_error) as avg_duration_error,
--   AVG(ram_error) as avg_ram_error
-- FROM monitoring.resource_estimation_log
-- GROUP BY model
-- ORDER BY avg_duration_error DESC;
