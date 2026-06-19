# Analytics Query Quick Reference

Quick reference for common analytics queries. All queries assume connection to `laptop-01:5432/learning`.

## Connect to Database

```bash
psql -h laptop-01 -U sfloess -d learning
```

## Top 10 Most Useful Queries

### 1. Best Model for a Task

```sql
-- Get the champion model for a specific task type
SELECT champion_model, avg_quality, avg_cost
FROM monitoring.model_champions
WHERE task_type = 'research_synthesis';
```

### 2. Most Cost-Efficient Models

```sql
-- Top 5 models by quality-per-dollar
SELECT
  model,
  task_type,
  ROUND(quality_per_dollar::numeric, 1) as qpd,
  ROUND(avg_quality::numeric, 3) as quality,
  ROUND(avg_cost::numeric, 5) as cost
FROM monitoring.cost_quality_frontier
ORDER BY quality_per_dollar DESC
LIMIT 5;
```

### 3. Today's Execution Summary

```sql
-- Executions, costs, and quality for today
SELECT
  workflow,
  COUNT(*) as runs,
  ROUND(AVG(quality_score)::numeric, 3) as avg_quality,
  ROUND(SUM(cost_usd)::numeric, 4) as total_cost,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes
FROM monitoring.execution_summary
WHERE timestamp::date = CURRENT_DATE
GROUP BY workflow
ORDER BY runs DESC;
```

### 4. Model Performance Comparison

```sql
-- Compare all models on a specific task
SELECT
  model,
  ROUND(avg_quality::numeric, 3) as quality,
  ROUND(avg_duration_sec::numeric, 1) as duration_sec,
  ROUND(avg_cost::numeric, 5) as cost,
  executions
FROM monitoring.top_model_combinations
WHERE task_type = 'research_synthesis'
ORDER BY avg_quality DESC;
```

### 5. Quality Trends (Last 7 Days)

```sql
-- Daily quality trend for deep-research workflow
SELECT
  date,
  ROUND(avg_consensus_quality::numeric, 3) as quality,
  executions,
  ROUND(avg_verification_rate::numeric, 3) as verification_rate
FROM monitoring.consensus_trends
WHERE workflow = 'deep-research'
  AND date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;
```

### 6. Recent Failures

```sql
-- Last 10 failures with error details
SELECT
  timestamp,
  workflow,
  model,
  metadata->>'phase_failed' as failed_phase,
  metadata->>'error' as error_message
FROM monitoring.execution_summary
WHERE outcome = 'failure'
ORDER BY timestamp DESC
LIMIT 10;
```

### 7. Hourly Throughput

```sql
-- Execution volume by hour (last 24h)
SELECT
  DATE_TRUNC('hour', timestamp) as hour,
  workflow,
  COUNT(*) as executions,
  ROUND(AVG(quality_score)::numeric, 3) as avg_quality
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY hour, workflow
ORDER BY hour DESC;
```

### 8. Strategy Performance

```sql
-- Thompson Sampling strategy rankings
SELECT
  strategy,
  successes,
  failures,
  ROUND(avg_reward::numeric, 3) as avg_reward,
  ROUND(thompson_expected_value::numeric, 3) as expected_value
FROM monitoring.strategy_performance_report
ORDER BY avg_reward DESC;
```

### 9. Phase Bottlenecks

```sql
-- Find slowest workflow phases
SELECT
  workflow,
  model,
  bottleneck_phase,
  ROUND(avg_phase_duration_sec::numeric, 1) as duration_sec,
  ROUND(phase_pct_of_total::numeric, 3) as pct_of_total
FROM monitoring.phase_bottlenecks
ORDER BY avg_phase_duration_sec DESC
LIMIT 5;
```

### 10. Cost Burn Rate

```sql
-- Current cost burn rate (last 24h)
SELECT
  ROUND(total_cost_24h::numeric, 2) as total_cost,
  ROUND(avg_cost_per_hour::numeric, 4) as cost_per_hour,
  total_executions_24h as executions,
  ROUND((total_cost_24h / NULLIF(total_executions_24h, 0))::numeric, 5) as cost_per_execution
FROM monitoring.grafana_cost_burn;
```

## Analysis Patterns

### Find Cost Savings Opportunities

```sql
-- Models with >95% quality of champion but lower cost
WITH champions AS (
  SELECT task_type, avg_quality as champion_quality
  FROM monitoring.model_champions
)
SELECT
  f.task_type,
  f.model,
  ROUND(f.avg_quality::numeric, 3) as quality,
  ROUND(f.avg_cost::numeric, 5) as cost,
  ROUND(c.champion_quality::numeric, 3) as champion_quality,
  ROUND((f.avg_quality / c.champion_quality)::numeric, 3) as pct_of_champion
FROM monitoring.cost_quality_frontier f
JOIN champions c ON f.task_type = c.task_type
WHERE f.avg_quality >= c.champion_quality * 0.95
ORDER BY f.quality_per_dollar DESC
LIMIT 10;
```

### Detect Quality Degradation

```sql
-- Alert if last 7 days quality is 10% below 30-day baseline
WITH baseline AS (
  SELECT workflow, AVG(quality_score) as baseline_quality
  FROM monitoring.execution_summary
  WHERE timestamp >= NOW() - INTERVAL '30 days'
    AND outcome = 'success'
  GROUP BY workflow
),
recent AS (
  SELECT workflow, AVG(quality_score) as recent_quality
  FROM monitoring.execution_summary
  WHERE timestamp >= NOW() - INTERVAL '7 days'
    AND outcome = 'success'
  GROUP BY workflow
)
SELECT
  b.workflow,
  ROUND(b.baseline_quality::numeric, 3) as baseline,
  ROUND(r.recent_quality::numeric, 3) as recent,
  ROUND(((r.recent_quality - b.baseline_quality) / b.baseline_quality * 100)::numeric, 1) as change_pct
FROM baseline b
JOIN recent r ON b.workflow = r.workflow
WHERE r.recent_quality < b.baseline_quality * 0.90
ORDER BY change_pct;
```

### Model Specialization Analysis

```sql
-- Find models that excel at specific tasks (>10% better than average)
SELECT
  model,
  task_type,
  ROUND(avg_quality::numeric, 3) as quality,
  ROUND(specialization_advantage::numeric, 3) as advantage,
  executions
FROM monitoring.model_specialization
WHERE specialization_advantage > 0.10
ORDER BY specialization_advantage DESC
LIMIT 10;
```

### Research Workflow Deep Dive

```sql
-- Detailed research metrics for last 7 days
SELECT
  date,
  total_research_runs,
  ROUND(avg_angles::numeric, 1) as avg_angles,
  ROUND(avg_sources::numeric, 1) as avg_sources,
  ROUND(avg_verified_claims::numeric, 1) as avg_verified,
  ROUND(avg_verification_rate::numeric, 3) as verification_rate,
  ROUND(avg_quality::numeric, 3) as quality,
  ROUND(total_cost::numeric, 4) as cost
FROM monitoring.research_quality_metrics
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;
```

### Source Count vs Quality

```sql
-- Correlation between source count and quality
SELECT
  source_bucket,
  executions,
  ROUND(avg_quality::numeric, 3) as quality,
  ROUND(avg_verification_rate::numeric, 3) as verification_rate,
  ROUND(avg_duration_sec::numeric, 1) as duration_sec
FROM monitoring.source_quality_correlation
ORDER BY source_bucket;
```

## Maintenance Queries

### Refresh All Views

```sql
-- Manually refresh all materialized views
SELECT * FROM monitoring.refresh_all_views();
```

### Check View Status

```sql
-- Last refresh time for materialized views
SELECT
  schemaname,
  matviewname,
  last_refresh
FROM pg_stat_user_tables
WHERE schemaname IN ('monitoring', 'learning')
  AND relname IN (
    SELECT matviewname::text
    FROM pg_matviews
    WHERE schemaname IN ('monitoring', 'learning')
  )
ORDER BY last_refresh DESC;
```

### View Execution Counts

```sql
-- Count executions by view
SELECT
  schemaname || '.' || viewname as view_name,
  pg_size_pretty(pg_relation_size(schemaname || '.' || viewname)) as size
FROM pg_views
WHERE schemaname IN ('monitoring', 'learning')
ORDER BY pg_relation_size(schemaname || '.' || viewname) DESC;
```

### Database Statistics

```sql
-- Overall database stats
SELECT
  'Total Executions' as metric,
  COUNT(*)::text as value
FROM monitoring.execution_summary
UNION ALL
SELECT 'Success Rate',
  ROUND(SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1)::text || '%'
FROM monitoring.execution_summary
UNION ALL
SELECT 'Total Cost',
  '$' || ROUND(SUM(cost_usd)::numeric, 2)::text
FROM monitoring.execution_summary
UNION ALL
SELECT 'Avg Quality',
  ROUND(AVG(quality_score)::numeric, 3)::text
FROM monitoring.execution_summary
WHERE outcome = 'success'
UNION ALL
SELECT 'Unique Models',
  COUNT(DISTINCT model)::text
FROM monitoring.execution_summary
UNION ALL
SELECT 'Unique Workflows',
  COUNT(DISTINCT workflow)::text
FROM monitoring.execution_summary;
```

## Export Queries

### CSV Export (via psql)

```bash
# Export top model combinations to CSV
psql -h laptop-01 -U sfloess -d learning -c "
  COPY (
    SELECT * FROM monitoring.top_model_combinations
  ) TO STDOUT WITH CSV HEADER
" > top_models.csv

# Export daily costs to CSV
psql -h laptop-01 -U sfloess -d learning -c "
  COPY (
    SELECT * FROM monitoring.daily_cost_quality
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY date DESC
  ) TO STDOUT WITH CSV HEADER
" > daily_costs.csv
```

### JSON Export

```bash
# Export recent executions as JSON
psql -h laptop-01 -U sfloess -d learning -t -c "
  SELECT json_agg(row_to_json(t))
  FROM (
    SELECT * FROM monitoring.recent_executions LIMIT 50
  ) t
" > recent_executions.json
```

## Performance Tips

### Query Optimization

```sql
-- Use materialized views for fast queries
SELECT * FROM monitoring.cost_quality_frontier;  -- Fast (cached)

-- Use regular views for real-time data
SELECT * FROM monitoring.recent_executions;  -- Slower (live query)
```

### Index Usage

```sql
-- Check if indexes are being used
EXPLAIN ANALYZE
SELECT * FROM monitoring.execution_summary
WHERE workflow = 'deep-research'
  AND timestamp >= NOW() - INTERVAL '7 days';
```

### Vacuum and Analyze

```sql
-- Update table statistics for better query planning
ANALYZE monitoring.execution_summary;
VACUUM ANALYZE monitoring.execution_summary;
```

## Keyboard Shortcuts (psql)

- `\dt monitoring.*` - List all tables in monitoring schema
- `\dv monitoring.*` - List all views
- `\dm monitoring.*` - List materialized views
- `\d+ monitoring.execution_summary` - Describe table with details
- `\x` - Toggle expanded display (vertical output)
- `\timing` - Show query execution time
- `\q` - Quit psql

## Quick psql Session

```bash
# Start psql with common settings
psql -h laptop-01 -U sfloess -d learning <<EOF
\timing on
\x auto
SELECT * FROM monitoring.grafana_cost_burn;
SELECT * FROM monitoring.top_model_combinations LIMIT 5;
\q
EOF
```
