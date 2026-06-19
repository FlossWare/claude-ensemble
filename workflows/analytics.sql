-- ============================================================================
-- Deep Research Workflow Analytics
-- ============================================================================
-- Common queries for dashboard/analytics, performance analysis, and monitoring
-- Compatible with PostgreSQL + pgvector (laptop-01:5432/learning)
--
-- Usage:
--   psql -h laptop-01 -U sfloess -d learning -f workflows/analytics.sql
--
-- Materialized views are auto-refreshed by workflow-storage-adapter.js
-- For manual refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY <view_name>
-- ============================================================================

-- ============================================================================
-- 1. TOP-PERFORMING MODEL COMBINATIONS
-- ============================================================================

-- Top 10 model combinations by quality score (last 30 days)
-- Shows which models excel at specific task types
CREATE OR REPLACE VIEW monitoring.top_model_combinations AS
SELECT
  model,
  task_type,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  AVG(duration_ms / 1000.0) as avg_duration_sec,
  SUM(cost_usd) as total_cost,
  AVG(cost_usd) as avg_cost,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY model, task_type
HAVING COUNT(*) >= 3  -- Minimum 3 executions for statistical significance
ORDER BY avg_quality DESC, success_rate DESC
LIMIT 10;

-- Best model per task type (champion selector)
CREATE OR REPLACE VIEW monitoring.model_champions AS
WITH ranked_models AS (
  SELECT
    task_type,
    model,
    AVG(quality_score) as avg_quality,
    COUNT(*) as executions,
    AVG(duration_ms / 1000.0) as avg_duration_sec,
    AVG(cost_usd) as avg_cost,
    ROW_NUMBER() OVER (PARTITION BY task_type ORDER BY AVG(quality_score) DESC) as rank
  FROM monitoring.execution_summary
  WHERE outcome = 'success'
    AND timestamp >= NOW() - INTERVAL '30 days'
  GROUP BY task_type, model
  HAVING COUNT(*) >= 3
)
SELECT
  task_type,
  model as champion_model,
  avg_quality,
  executions,
  avg_duration_sec,
  avg_cost
FROM ranked_models
WHERE rank = 1
ORDER BY task_type;


-- ============================================================================
-- 2. COST-QUALITY TRADEOFF ANALYSIS
-- ============================================================================

-- Pareto frontier: models with best quality per dollar
-- Identifies models on the cost-quality efficiency frontier
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.cost_quality_frontier AS
SELECT
  model,
  task_type,
  AVG(quality_score) as avg_quality,
  AVG(cost_usd) as avg_cost,
  AVG(quality_score / NULLIF(cost_usd, 0)) as quality_per_dollar,
  AVG(duration_ms / 1000.0) as avg_duration_sec,
  COUNT(*) as executions
FROM monitoring.execution_summary
WHERE outcome = 'success'
  AND cost_usd > 0
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY model, task_type
HAVING COUNT(*) >= 3
ORDER BY quality_per_dollar DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cost_quality_frontier_key
ON monitoring.cost_quality_frontier(model, task_type);

-- Cost-quality tradeoff by workflow
CREATE OR REPLACE VIEW monitoring.workflow_cost_quality AS
SELECT
  workflow,
  COUNT(*) as total_executions,
  AVG(quality_score) as avg_quality,
  SUM(cost_usd) as total_cost,
  AVG(cost_usd) as avg_cost_per_run,
  AVG(quality_score / NULLIF(cost_usd, 0)) as avg_quality_per_dollar,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
  AVG(duration_ms / 1000.0) as avg_duration_sec
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY workflow
ORDER BY avg_quality_per_dollar DESC;

-- Daily cost breakdown with quality correlation
CREATE OR REPLACE VIEW monitoring.daily_cost_quality AS
SELECT
  DATE(timestamp) as date,
  workflow,
  COUNT(*) as executions,
  SUM(cost_usd) as total_cost,
  AVG(quality_score) as avg_quality,
  SUM(input_tokens) as total_input_tokens,
  SUM(output_tokens) as total_output_tokens
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp), workflow
ORDER BY date DESC, workflow;


-- ============================================================================
-- 3. CONSENSUS SCORE TRENDS
-- ============================================================================

-- Track consensus quality over time (research verification phase)
-- Assumes metadata.claims_verified and metadata.claims_total exist
CREATE OR REPLACE VIEW monitoring.consensus_trends AS
SELECT
  DATE(timestamp) as date,
  workflow,
  COUNT(*) as executions,
  AVG(quality_score) as avg_consensus_quality,
  AVG((metadata->>'claims_verified')::numeric) as avg_claims_verified,
  AVG((metadata->>'claims_total')::numeric) as avg_claims_total,
  AVG(
    (metadata->>'claims_verified')::numeric /
    NULLIF((metadata->>'claims_total')::numeric, 0)
  ) as avg_verification_rate,
  STDDEV(quality_score) as quality_stddev
FROM monitoring.execution_summary
WHERE workflow IN ('deep-research', 'ai-pdf-deep-research')
  AND metadata->>'claims_total' IS NOT NULL
  AND timestamp >= NOW() - INTERVAL '90 days'
GROUP BY DATE(timestamp), workflow
ORDER BY date DESC, workflow;

-- Consensus score by model (3-vote adversarial review)
CREATE OR REPLACE VIEW monitoring.model_consensus_quality AS
SELECT
  model,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG((metadata->>'claims_verified')::numeric /
      NULLIF((metadata->>'claims_total')::numeric, 0)) as avg_verification_rate,
  AVG(duration_ms / 1000.0) as avg_duration_sec
FROM monitoring.execution_summary
WHERE workflow IN ('deep-research', 'ai-pdf-deep-research')
  AND metadata->>'claims_total' IS NOT NULL
  AND outcome = 'success'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY model
ORDER BY avg_quality DESC;


-- ============================================================================
-- 4. PHASE DURATION ANALYSIS
-- ============================================================================

-- Research workflow phase timing breakdown
-- Extract phase timings from metadata if available
CREATE OR REPLACE VIEW monitoring.phase_durations AS
SELECT
  DATE(timestamp) as date,
  workflow,
  model,
  AVG(duration_ms / 1000.0) as total_duration_sec,
  AVG((metadata->>'phase_scope_duration_ms')::numeric / 1000.0) as avg_scope_sec,
  AVG((metadata->>'phase_search_duration_ms')::numeric / 1000.0) as avg_search_sec,
  AVG((metadata->>'phase_fetch_duration_ms')::numeric / 1000.0) as avg_fetch_sec,
  AVG((metadata->>'phase_verify_duration_ms')::numeric / 1000.0) as avg_verify_sec,
  AVG((metadata->>'phase_synthesize_duration_ms')::numeric / 1000.0) as avg_synthesize_sec,
  COUNT(*) as executions
FROM monitoring.execution_summary
WHERE workflow = 'deep-research'
  AND outcome = 'success'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp), workflow, model
ORDER BY date DESC;

-- Phase bottleneck detection (slowest phases)
CREATE OR REPLACE VIEW monitoring.phase_bottlenecks AS
SELECT
  workflow,
  model,
  'verify' as bottleneck_phase,
  AVG((metadata->>'phase_verify_duration_ms')::numeric / 1000.0) as avg_phase_duration_sec,
  AVG((metadata->>'phase_verify_duration_ms')::numeric / NULLIF(duration_ms, 0)) as phase_pct_of_total,
  COUNT(*) as executions
FROM monitoring.execution_summary
WHERE workflow = 'deep-research'
  AND metadata->>'phase_verify_duration_ms' IS NOT NULL
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY workflow, model
HAVING AVG((metadata->>'phase_verify_duration_ms')::numeric / NULLIF(duration_ms, 0)) > 0.5  -- >50% of total time
ORDER BY avg_phase_duration_sec DESC;


-- ============================================================================
-- 5. MODEL SPECIALIZATION BY TASK TYPE
-- ============================================================================

-- Model specialization heatmap (quality score by model × task_type)
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.model_specialization AS
SELECT
  model,
  task_type,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  AVG(duration_ms / 1000.0) as avg_duration_sec,
  AVG(cost_usd) as avg_cost,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
  -- Specialization score: how much better than average for this task
  AVG(quality_score) - (
    SELECT AVG(quality_score)
    FROM monitoring.execution_summary e2
    WHERE e2.task_type = e1.task_type
      AND e2.outcome = 'success'
  ) as specialization_advantage
FROM monitoring.execution_summary e1
WHERE outcome = 'success'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY model, task_type
HAVING COUNT(*) >= 2
ORDER BY model, avg_quality DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_specialization_key
ON monitoring.model_specialization(model, task_type);

-- Top specialized models per task (only show significant advantages)
CREATE OR REPLACE VIEW monitoring.top_specialists AS
SELECT
  task_type,
  model,
  avg_quality,
  specialization_advantage,
  executions,
  avg_cost
FROM monitoring.model_specialization
WHERE specialization_advantage > 0.05  -- At least 5% better than average
ORDER BY task_type, specialization_advantage DESC;


-- ============================================================================
-- 6. RESEARCH WORKFLOW SPECIFIC METRICS
-- ============================================================================

-- Deep research quality metrics (claims verification analysis)
CREATE OR REPLACE VIEW monitoring.research_quality_metrics AS
SELECT
  DATE(timestamp) as date,
  COUNT(*) as total_research_runs,
  AVG((metadata->>'angles_count')::numeric) as avg_angles,
  AVG((metadata->>'sources_count')::numeric) as avg_sources,
  AVG((metadata->>'claims_total')::numeric) as avg_total_claims,
  AVG((metadata->>'claims_verified')::numeric) as avg_verified_claims,
  AVG((metadata->>'claims_verified')::numeric /
      NULLIF((metadata->>'claims_total')::numeric, 0)) as avg_verification_rate,
  AVG(quality_score) as avg_quality,
  AVG(duration_ms / 1000.0) as avg_duration_sec,
  SUM(cost_usd) as total_cost
FROM monitoring.execution_summary
WHERE workflow = 'deep-research'
  AND outcome = 'success'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Source quality analysis (correlate source count with outcome quality)
CREATE OR REPLACE VIEW monitoring.source_quality_correlation AS
SELECT
  CASE
    WHEN (metadata->>'sources_count')::numeric < 5 THEN '1-4 sources'
    WHEN (metadata->>'sources_count')::numeric < 10 THEN '5-9 sources'
    WHEN (metadata->>'sources_count')::numeric < 15 THEN '10-14 sources'
    ELSE '15+ sources'
  END as source_bucket,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG((metadata->>'claims_verified')::numeric /
      NULLIF((metadata->>'claims_total')::numeric, 0)) as avg_verification_rate,
  AVG(duration_ms / 1000.0) as avg_duration_sec
FROM monitoring.execution_summary
WHERE workflow = 'deep-research'
  AND metadata->>'sources_count' IS NOT NULL
  AND outcome = 'success'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY source_bucket
ORDER BY
  CASE source_bucket
    WHEN '1-4 sources' THEN 1
    WHEN '5-9 sources' THEN 2
    WHEN '10-14 sources' THEN 3
    ELSE 4
  END;


-- ============================================================================
-- 7. FAILURE ANALYSIS
-- ============================================================================

-- Failure patterns by workflow and model
CREATE OR REPLACE VIEW monitoring.failure_patterns AS
SELECT
  workflow,
  model,
  COUNT(*) as total_failures,
  metadata->>'phase_failed' as failed_phase,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY workflow) as pct_of_workflow_failures,
  AVG(duration_ms / 1000.0) as avg_duration_before_failure_sec
FROM monitoring.execution_summary
WHERE outcome = 'failure'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY workflow, model, metadata->>'phase_failed'
ORDER BY total_failures DESC;

-- Error messages aggregation (requires metadata.error field)
CREATE OR REPLACE VIEW monitoring.common_errors AS
SELECT
  workflow,
  metadata->>'error' as error_message,
  COUNT(*) as occurrences,
  MAX(timestamp) as last_occurrence,
  AVG(duration_ms / 1000.0) as avg_time_to_failure_sec
FROM monitoring.execution_summary
WHERE outcome = 'failure'
  AND metadata->>'error' IS NOT NULL
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY workflow, metadata->>'error'
ORDER BY occurrences DESC
LIMIT 20;


-- ============================================================================
-- 8. STRATEGY PERFORMANCE (THOMPSON SAMPLING BANDIT)
-- ============================================================================

-- Current strategy rankings with Thompson Sampling stats
CREATE OR REPLACE VIEW monitoring.strategy_performance_report AS
SELECT
  strategy,
  successes,
  failures,
  successes + failures as total_attempts,
  successes::float / NULLIF(successes + failures, 0) as empirical_success_rate,
  avg_reward,
  alpha,
  beta,
  alpha / NULLIF(alpha + beta, 0) as thompson_expected_value,
  SQRT(
    (alpha * beta) / (POWER(alpha + beta, 2) * (alpha + beta + 1))
  ) as thompson_stddev,
  last_updated
FROM learning.strategy_performance
WHERE successes + failures > 0
ORDER BY avg_reward DESC;

-- Strategy performance over time (join with execution_summary)
CREATE OR REPLACE VIEW monitoring.strategy_trends AS
SELECT
  DATE(e.timestamp) as date,
  e.metadata->>'strategy' as strategy,
  COUNT(*) as executions,
  AVG(e.quality_score) as avg_quality,
  SUM(CASE WHEN e.outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
  AVG(e.duration_ms / 1000.0) as avg_duration_sec
FROM monitoring.execution_summary e
WHERE e.metadata->>'strategy' IS NOT NULL
  AND e.timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(e.timestamp), e.metadata->>'strategy'
ORDER BY date DESC, avg_quality DESC;


-- ============================================================================
-- 9. REAL-TIME MONITORING (LAST 24 HOURS)
-- ============================================================================

-- Recent executions dashboard
CREATE OR REPLACE VIEW monitoring.recent_executions AS
SELECT
  timestamp,
  workflow,
  model,
  task_type,
  quality_score,
  outcome,
  duration_ms / 1000.0 as duration_sec,
  cost_usd,
  metadata->>'session_id' as session_id
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC
LIMIT 100;

-- Hourly throughput (last 24h)
CREATE OR REPLACE VIEW monitoring.hourly_throughput AS
SELECT
  DATE_TRUNC('hour', timestamp) as hour,
  workflow,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  SUM(cost_usd) as total_cost,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp), workflow
ORDER BY hour DESC;


-- ============================================================================
-- 10. GRAFANA DASHBOARD QUERIES
-- ============================================================================

-- Query 1: Model performance timeseries (for Grafana time-series panel)
-- Grafana variables: $__timeFilter(timestamp), $model
CREATE OR REPLACE VIEW monitoring.grafana_model_timeseries AS
SELECT
  timestamp as time,
  model,
  quality_score,
  duration_ms / 1000.0 as duration_sec,
  cost_usd
FROM monitoring.execution_summary
WHERE outcome = 'success'
ORDER BY timestamp;

-- Query 2: Workflow success rate gauge (for Grafana gauge panel)
CREATE OR REPLACE VIEW monitoring.grafana_success_rate AS
SELECT
  workflow,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY workflow;

-- Query 3: Cost burn rate (for Grafana stat panel)
CREATE OR REPLACE VIEW monitoring.grafana_cost_burn AS
SELECT
  SUM(cost_usd) as total_cost_24h,
  SUM(cost_usd) / 24.0 as avg_cost_per_hour,
  COUNT(*) as total_executions_24h
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours';

-- Query 4: Quality distribution histogram (for Grafana histogram panel)
CREATE OR REPLACE VIEW monitoring.grafana_quality_histogram AS
SELECT
  FLOOR(quality_score * 10) / 10 as quality_bucket,
  COUNT(*) as count
FROM monitoring.execution_summary
WHERE outcome = 'success'
  AND timestamp >= NOW() - INTERVAL '7 days'
GROUP BY quality_bucket
ORDER BY quality_bucket;


-- ============================================================================
-- UTILITY: REFRESH ALL MATERIALIZED VIEWS
-- ============================================================================

-- Manual refresh function (call periodically or via cron)
CREATE OR REPLACE FUNCTION monitoring.refresh_all_views()
RETURNS TABLE(view_name TEXT, status TEXT, duration_ms NUMERIC) AS $$
DECLARE
  view_record RECORD;
  start_time TIMESTAMP;
  end_time TIMESTAMP;
BEGIN
  FOR view_record IN
    SELECT schemaname || '.' || matviewname as full_name
    FROM pg_matviews
    WHERE schemaname IN ('monitoring', 'learning')
  LOOP
    BEGIN
      start_time := clock_timestamp();

      -- Try concurrent refresh first (requires UNIQUE index)
      EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || view_record.full_name;

      end_time := clock_timestamp();
      view_name := view_record.full_name;
      status := 'OK (concurrent)';
      duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;
      RETURN NEXT;

    EXCEPTION WHEN OTHERS THEN
      -- Fallback to blocking refresh
      BEGIN
        start_time := clock_timestamp();
        EXECUTE 'REFRESH MATERIALIZED VIEW ' || view_record.full_name;
        end_time := clock_timestamp();

        view_name := view_record.full_name;
        status := 'OK (blocking)';
        duration_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;
        RETURN NEXT;

      EXCEPTION WHEN OTHERS THEN
        view_name := view_record.full_name;
        status := 'FAILED: ' || SQLERRM;
        duration_ms := 0;
        RETURN NEXT;
      END;
    END;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Usage: SELECT * FROM monitoring.refresh_all_views();


-- ============================================================================
-- SAMPLE USAGE QUERIES
-- ============================================================================

-- Example 1: Find best model for a specific task type
/*
SELECT * FROM monitoring.model_champions WHERE task_type = 'research_synthesis';
*/

-- Example 2: Check cost efficiency of recent runs
/*
SELECT * FROM monitoring.cost_quality_frontier
WHERE task_type = 'research_synthesis'
ORDER BY quality_per_dollar DESC
LIMIT 5;
*/

-- Example 3: Monitor consensus quality trends
/*
SELECT * FROM monitoring.consensus_trends
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;
*/

-- Example 4: Identify bottleneck phases
/*
SELECT * FROM monitoring.phase_bottlenecks
WHERE workflow = 'deep-research'
ORDER BY avg_phase_duration_sec DESC;
*/

-- Example 5: Refresh all views manually
/*
SELECT * FROM monitoring.refresh_all_views();
*/

-- Example 6: Get top 3 specialists for each task type
/*
WITH ranked_specialists AS (
  SELECT
    task_type,
    model,
    avg_quality,
    specialization_advantage,
    ROW_NUMBER() OVER (PARTITION BY task_type ORDER BY specialization_advantage DESC) as rank
  FROM monitoring.top_specialists
)
SELECT * FROM ranked_specialists WHERE rank <= 3;
*/

-- ============================================================================
-- END OF ANALYTICS QUERIES
-- ============================================================================
