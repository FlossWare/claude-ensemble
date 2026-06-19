-- Migration: Create Materialized Views for Workflow Monitoring
-- Date: 2026-06-19
-- Purpose: Add automated view refresh infrastructure for dashboard queries and Thompson Sampling

-- Materialized View 1: Model Performance Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.model_performance_summary AS
SELECT
  model,
  COUNT(*) as total_executions,
  AVG(quality_score) as avg_quality,
  SUM(cost_usd) as total_cost,
  AVG(duration_ms) as avg_duration,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
  MIN(timestamp) as first_execution,
  MAX(timestamp) as last_execution
FROM monitoring.execution_summary
GROUP BY model
WITH DATA;

-- Create unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_model_perf_model
ON monitoring.model_performance_summary(model);

COMMENT ON MATERIALIZED VIEW monitoring.model_performance_summary IS
'Aggregated performance metrics per model for Grafana dashboards';


-- Materialized View 2: Workflow Efficiency
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.workflow_efficiency AS
SELECT
  workflow,
  task_type,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(duration_ms) as avg_duration,
  SUM(cost_usd) as total_cost,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as median_duration,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_summary
GROUP BY workflow, task_type
WITH DATA;

-- Create unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_eff_key
ON monitoring.workflow_efficiency(workflow, task_type);

COMMENT ON MATERIALIZED VIEW monitoring.workflow_efficiency IS
'Workflow performance by task type for optimization insights';


-- Materialized View 3: Cost Analysis (Daily)
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.cost_analysis AS
SELECT
  DATE(timestamp) as date,
  model,
  workflow,
  SUM(cost_usd) as daily_cost,
  SUM(input_tokens) as total_input_tokens,
  SUM(output_tokens) as total_output_tokens,
  COUNT(*) as executions,
  AVG(cost_usd) as avg_cost_per_execution
FROM monitoring.execution_summary
GROUP BY DATE(timestamp), model, workflow
WITH DATA;

-- Create unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_cost_analysis_key
ON monitoring.cost_analysis(date, model, workflow);

COMMENT ON MATERIALIZED VIEW monitoring.cost_analysis IS
'Daily cost tracking per model and workflow for budget monitoring';


-- Materialized View 4: Strategy Rankings (Thompson Sampling)
CREATE MATERIALIZED VIEW IF NOT EXISTS learning.strategy_rankings AS
SELECT
  strategy,
  successes,
  failures,
  avg_reward,
  alpha,
  beta,
  (alpha / (alpha + beta)) as expected_reward,
  RANK() OVER (ORDER BY avg_reward DESC) as rank,
  PERCENT_RANK() OVER (ORDER BY avg_reward DESC) as percentile,
  last_updated
FROM learning.strategy_performance
WHERE successes + failures > 0
WITH DATA;

-- Create unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_rankings_strategy
ON learning.strategy_rankings(strategy);

COMMENT ON MATERIALIZED VIEW learning.strategy_rankings IS
'Ranked strategies for Thompson Sampling bandit selection';


-- Materialized View 5: Recent Activity Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.recent_activity_summary AS
SELECT
  DATE_TRUNC('hour', timestamp) as hour,
  model,
  workflow,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  SUM(cost_usd) as total_cost
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp), model, workflow
WITH DATA;

-- Create unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_recent_activity_key
ON monitoring.recent_activity_summary(hour, model, workflow);

COMMENT ON MATERIALIZED VIEW monitoring.recent_activity_summary IS
'Last 24 hours of activity for real-time monitoring';


-- Function to refresh all views concurrently
CREATE OR REPLACE FUNCTION workflows.refresh_views()
RETURNS TABLE(view_name TEXT, refresh_status TEXT, refresh_time INTERVAL)
LANGUAGE plpgsql
AS $$
DECLARE
  v_start_time TIMESTAMP;
  v_view RECORD;
BEGIN
  FOR v_view IN
    SELECT schemaname || '.' || matviewname as full_name
    FROM pg_matviews
    WHERE schemaname IN ('monitoring', 'learning')
    ORDER BY full_name
  LOOP
    v_start_time := clock_timestamp();

    BEGIN
      -- Try CONCURRENTLY first
      EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || v_view.full_name;
      view_name := v_view.full_name;
      refresh_status := 'CONCURRENT';
      refresh_time := clock_timestamp() - v_start_time;
      RETURN NEXT;

    EXCEPTION WHEN OTHERS THEN
      -- Fallback to blocking refresh
      BEGIN
        EXECUTE 'REFRESH MATERIALIZED VIEW ' || v_view.full_name;
        view_name := v_view.full_name;
        refresh_status := 'BLOCKING';
        refresh_time := clock_timestamp() - v_start_time;
        RETURN NEXT;

      EXCEPTION WHEN OTHERS THEN
        view_name := v_view.full_name;
        refresh_status := 'FAILED: ' || SQLERRM;
        refresh_time := clock_timestamp() - v_start_time;
        RETURN NEXT;
      END;
    END;
  END LOOP;
END;
$$;

COMMENT ON FUNCTION workflows.refresh_views() IS
'Refresh all materialized views with CONCURRENTLY fallback. Call after workflow completion.';


-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO sfloess;
GRANT SELECT ON ALL TABLES IN SCHEMA learning TO sfloess;
GRANT EXECUTE ON FUNCTION workflows.refresh_views() TO sfloess;


-- Verification query
DO $$
BEGIN
  RAISE NOTICE 'Materialized views created:';
  RAISE NOTICE '  - monitoring.model_performance_summary';
  RAISE NOTICE '  - monitoring.workflow_efficiency';
  RAISE NOTICE '  - monitoring.cost_analysis';
  RAISE NOTICE '  - learning.strategy_rankings';
  RAISE NOTICE '  - monitoring.recent_activity_summary';
  RAISE NOTICE '';
  RAISE NOTICE 'Function created: workflows.refresh_views()';
  RAISE NOTICE '';
  RAISE NOTICE 'Run: SELECT * FROM workflows.refresh_views();';
END $$;
