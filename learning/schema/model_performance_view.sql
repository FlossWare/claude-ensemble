-- Model Performance Materialized View
-- Aggregates model performance metrics for Thompson Sampling routing
-- Refreshed on workflow completion to keep model selection data fresh

CREATE SCHEMA IF NOT EXISTS monitoring;

-- Drop existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS monitoring.model_performance;

-- Create materialized view aggregating model performance
CREATE MATERIALIZED VIEW monitoring.model_performance AS
WITH model_stats AS (
  SELECT
    model,
    COUNT(*) as total_executions,
    SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
    SUM(CASE WHEN outcome IN ('failed', 'error') THEN 1 ELSE 0 END) as failures,
    AVG(CASE WHEN quality_score IS NOT NULL THEN quality_score ELSE 0 END) as avg_quality,
    AVG(CASE WHEN duration_ms IS NOT NULL THEN duration_ms ELSE 0 END) as avg_duration_ms,
    SUM(CASE WHEN input_tokens IS NOT NULL THEN input_tokens ELSE 0 END) as total_input_tokens,
    SUM(CASE WHEN output_tokens IS NOT NULL THEN output_tokens ELSE 0 END) as total_output_tokens,
    SUM(CASE WHEN cost_usd IS NOT NULL THEN cost_usd ELSE 0 END) as total_cost_usd,
    MAX(timestamp) as last_execution,
    -- Thompson Sampling parameters (Beta distribution)
    -- alpha = 1 + successes (uniform prior)
    -- beta = 1 + failures
    (1 + SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)) as alpha,
    (1 + SUM(CASE WHEN outcome IN ('failed', 'error') THEN 1 ELSE 0 END)) as beta
  FROM monitoring.execution_summary
  WHERE model IS NOT NULL
    AND model != 'multi-model-adversarial'  -- Exclude multi-model sentinels
    AND timestamp > NOW() - INTERVAL '30 days'  -- Last 30 days
  GROUP BY model
),
model_scores AS (
  SELECT
    model,
    total_executions,
    successes,
    failures,
    avg_quality,
    avg_duration_ms,
    total_input_tokens,
    total_output_tokens,
    total_cost_usd,
    last_execution,
    alpha,
    beta,
    -- Win rate (for display)
    CASE
      WHEN (successes + failures) > 0
      THEN (successes::float / (successes + failures))
      ELSE 0.5
    END as win_rate,
    -- Cost per success
    CASE
      WHEN successes > 0
      THEN total_cost_usd / successes
      ELSE 0
    END as cost_per_success,
    -- Efficiency score (quality per second per dollar)
    CASE
      WHEN avg_duration_ms > 0 AND total_cost_usd > 0
      THEN avg_quality / (avg_duration_ms / 1000.0) / (total_cost_usd / total_executions)
      ELSE 0
    END as efficiency_score
  FROM model_stats
)
SELECT
  model,
  total_executions,
  successes,
  failures,
  win_rate,
  avg_quality,
  avg_duration_ms,
  total_input_tokens,
  total_output_tokens,
  total_cost_usd,
  cost_per_success,
  efficiency_score,
  last_execution,
  alpha,
  beta,
  -- Thompson Sampling expected value (mean of Beta distribution)
  (alpha::float / (alpha + beta)) as thompson_expected_value
FROM model_scores
ORDER BY thompson_expected_value DESC;

-- Create index for fast lookups by model
CREATE UNIQUE INDEX idx_model_performance_model ON monitoring.model_performance(model);

-- Create index for Thompson Sampling queries
CREATE INDEX idx_model_performance_thompson ON monitoring.model_performance(thompson_expected_value DESC);

-- Add comment
COMMENT ON MATERIALIZED VIEW monitoring.model_performance IS
'Aggregated model performance metrics for Thompson Sampling routing.
Refresh after workflow completion to keep model selection data fresh.
Thompson Sampling uses Beta(alpha, beta) distribution where:
- alpha = 1 + successes (uniform prior)
- beta = 1 + failures
- Expected value = alpha / (alpha + beta)';

-- Initial refresh
REFRESH MATERIALIZED VIEW monitoring.model_performance;
