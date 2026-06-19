# Deep Research Workflow Analytics

Comprehensive analytics queries and Grafana dashboard for monitoring deep research workflow performance, cost efficiency, and model specialization.

## Quick Start

### 1. Initialize Database Views

```bash
# Connect to PostgreSQL and create all analytics views
psql -h laptop-01 -U sfloess -d learning -f workflows/analytics.sql
```

This creates:
- **10+ materialized views** for fast query performance
- **20+ regular views** for real-time analysis
- **1 refresh function** for manual view updates

### 2. Test Analytics Queries

```bash
# Top performing model combinations
psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM monitoring.top_model_combinations LIMIT 5;"

# Cost-quality frontier (best value models)
psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM monitoring.cost_quality_frontier LIMIT 5;"

# Recent execution summary
psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM monitoring.recent_executions LIMIT 10;"
```

### 3. Deploy Grafana Dashboard

```bash
# Copy dashboard JSON to Grafana dashboards directory
cp workflows/grafana-dashboard.json ~/grafana-dashboards/

# Or import via Grafana UI:
# 1. Navigate to http://pi-02:3000
# 2. Dashboards → Import
# 3. Upload workflows/grafana-dashboard.json
# 4. Select PostgreSQL datasource: laptop-01-learning
```

## Available Analytics Views

### Model Performance

#### `monitoring.top_model_combinations`
Top 10 model/task combinations by quality score (last 30 days). Shows which models excel at specific tasks.

**Columns:** model, task_type, executions, avg_quality, quality_stddev, avg_duration_sec, total_cost, avg_cost, success_rate

**Usage:**
```sql
SELECT * FROM monitoring.top_model_combinations WHERE task_type = 'research_synthesis';
```

#### `monitoring.model_champions`
Best model per task type (champion selector). Use this for automated model routing.

**Columns:** task_type, champion_model, avg_quality, executions, avg_duration_sec, avg_cost

**Usage:**
```sql
-- Get champion model for research synthesis
SELECT champion_model FROM monitoring.model_champions WHERE task_type = 'research_synthesis';
```

#### `monitoring.model_specialization`
Heatmap of model performance across task types with specialization scores. Identifies which models are significantly better than average for each task.

**Columns:** model, task_type, avg_quality, specialization_advantage, executions, avg_cost, success_rate

**Usage:**
```sql
-- Find models with >10% advantage on specific tasks
SELECT * FROM monitoring.model_specialization
WHERE specialization_advantage > 0.10
ORDER BY specialization_advantage DESC;
```

### Cost Analysis

#### `monitoring.cost_quality_frontier`
Pareto-efficient models (best quality per dollar). Use this to optimize cost vs. quality tradeoffs.

**Columns:** model, task_type, avg_quality, avg_cost, quality_per_dollar, avg_duration_sec, executions

**Usage:**
```sql
-- Top 5 most cost-efficient models for research tasks
SELECT model, task_type, quality_per_dollar, avg_quality, avg_cost
FROM monitoring.cost_quality_frontier
WHERE task_type = 'research_synthesis'
ORDER BY quality_per_dollar DESC
LIMIT 5;
```

#### `monitoring.workflow_cost_quality`
Cost-quality analysis by workflow. Shows total cost, average cost per run, and quality-per-dollar for each workflow.

**Columns:** workflow, total_executions, avg_quality, total_cost, avg_cost_per_run, avg_quality_per_dollar, success_rate

**Usage:**
```sql
SELECT * FROM monitoring.workflow_cost_quality ORDER BY avg_quality_per_dollar DESC;
```

#### `monitoring.daily_cost_quality`
Daily cost breakdown with quality correlation (last 30 days).

**Usage:**
```sql
-- Weekly cost summary
SELECT
  DATE_TRUNC('week', date) as week,
  SUM(total_cost) as weekly_cost,
  AVG(avg_quality) as avg_quality
FROM monitoring.daily_cost_quality
GROUP BY week
ORDER BY week DESC;
```

### Consensus & Verification

#### `monitoring.consensus_trends`
Track consensus quality over time for research workflows. Shows claim verification rates and quality scores.

**Columns:** date, workflow, executions, avg_consensus_quality, avg_claims_verified, avg_claims_total, avg_verification_rate, quality_stddev

**Usage:**
```sql
-- Consensus quality last 7 days
SELECT * FROM monitoring.consensus_trends
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;
```

#### `monitoring.model_consensus_quality`
Consensus performance by model (3-vote adversarial review).

**Usage:**
```sql
SELECT model, avg_quality, avg_verification_rate
FROM monitoring.model_consensus_quality
ORDER BY avg_verification_rate DESC;
```

### Phase Analysis

#### `monitoring.phase_durations`
Research workflow phase timing breakdown. Shows average duration for each phase (scope, search, fetch, verify, synthesize).

**Usage:**
```sql
SELECT
  model,
  total_duration_sec,
  avg_verify_sec,
  avg_synthesize_sec
FROM monitoring.phase_durations
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY total_duration_sec DESC;
```

#### `monitoring.phase_bottlenecks`
Identify slowest phases (>50% of total time). Use this to optimize workflow performance.

**Usage:**
```sql
SELECT * FROM monitoring.phase_bottlenecks ORDER BY avg_phase_duration_sec DESC;
```

### Strategy Performance

#### `monitoring.strategy_performance_report`
Thompson Sampling bandit stats for all strategies. Shows success rates, rewards, and Beta distribution parameters.

**Columns:** strategy, successes, failures, total_attempts, empirical_success_rate, avg_reward, alpha, beta, thompson_expected_value, thompson_stddev

**Usage:**
```sql
-- Top 5 strategies by average reward
SELECT strategy, avg_reward, successes, failures
FROM monitoring.strategy_performance_report
ORDER BY avg_reward DESC
LIMIT 5;
```

#### `monitoring.strategy_trends`
Strategy performance over time (last 30 days).

**Usage:**
```sql
SELECT date, strategy, avg_quality, success_rate
FROM monitoring.strategy_trends
WHERE strategy = 'parallel_search'
ORDER BY date DESC;
```

### Failure Analysis

#### `monitoring.failure_patterns`
Failure breakdown by workflow, model, and phase.

**Usage:**
```sql
-- Top failure patterns
SELECT workflow, model, failed_phase, total_failures
FROM monitoring.failure_patterns
ORDER BY total_failures DESC
LIMIT 10;
```

#### `monitoring.common_errors`
Top 20 most common error messages (last 30 days).

**Usage:**
```sql
SELECT error_message, occurrences, last_occurrence
FROM monitoring.common_errors
ORDER BY occurrences DESC;
```

### Real-Time Monitoring

#### `monitoring.recent_executions`
Last 100 executions (24h window).

**Usage:**
```sql
SELECT timestamp, workflow, model, quality_score, outcome
FROM monitoring.recent_executions
ORDER BY timestamp DESC
LIMIT 20;
```

#### `monitoring.hourly_throughput`
Hourly execution counts and quality (last 24h).

**Usage:**
```sql
SELECT hour, workflow, executions, avg_quality, success_rate
FROM monitoring.hourly_throughput
ORDER BY hour DESC;
```

## Materialized View Refresh

Materialized views cache query results for fast performance. They're auto-refreshed by `workflow-storage-adapter.js` after each execution.

### Manual Refresh

```sql
-- Refresh all materialized views
SELECT * FROM monitoring.refresh_all_views();

-- Output shows view_name, status, and duration_ms
```

### Individual View Refresh

```sql
-- Concurrent refresh (doesn't block reads, requires UNIQUE index)
REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.cost_quality_frontier;

-- Blocking refresh (locks view during refresh)
REFRESH MATERIALIZED VIEW monitoring.model_specialization;
```

### Auto-Refresh Schedule

Add to crontab for periodic updates:

```bash
# Refresh every 5 minutes
*/5 * * * * psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM monitoring.refresh_all_views();" > /dev/null 2>&1
```

## Grafana Dashboard

### Dashboard Panels

1. **Model Quality Score Timeseries** - Quality trends over time per model
2. **Workflow Success Rate Gauge** - Success rate (24h) per workflow
3. **Total Cost (24h)** - Total spend in last 24 hours
4. **Executions (24h)** - Total execution count
5. **Avg Cost/Hour** - Current burn rate
6. **Top Model Combinations Table** - Best performing model/task pairs
7. **Quality Distribution Pie Chart** - Quality score histogram (7d)
8. **Consensus Quality Trends** - Verification quality over time
9. **Cost-Quality Frontier Table** - Most cost-efficient models
10. **Hourly Throughput** - Execution volume by hour
11. **Strategy Performance Table** - Thompson Sampling stats
12. **Recent Executions Log** - Last 50 executions

### Dashboard Variables

Create Grafana variables for filtering:

```sql
-- Model selector
SELECT DISTINCT model FROM monitoring.execution_summary ORDER BY model

-- Workflow selector
SELECT DISTINCT workflow FROM monitoring.execution_summary ORDER BY workflow

-- Task type selector
SELECT DISTINCT task_type FROM monitoring.execution_summary ORDER BY task_type
```

### Custom Queries

Example Grafana query for custom panel:

```sql
-- Quality vs Cost scatter plot
SELECT
  timestamp as time,
  model,
  quality_score,
  cost_usd,
  duration_ms / 1000.0 as duration_sec
FROM monitoring.execution_summary
WHERE $__timeFilter(timestamp)
  AND outcome = 'success'
ORDER BY timestamp
```

## Common Analysis Workflows

### 1. Find Best Model for a Task

```sql
-- Get champion model for specific task type
SELECT champion_model, avg_quality, avg_cost
FROM monitoring.model_champions
WHERE task_type = 'research_synthesis';

-- Compare top 3 candidates with cost tradeoffs
SELECT model, avg_quality, avg_cost, quality_per_dollar
FROM monitoring.cost_quality_frontier
WHERE task_type = 'research_synthesis'
ORDER BY quality_per_dollar DESC
LIMIT 3;
```

### 2. Optimize Workflow Costs

```sql
-- Identify expensive workflows
SELECT workflow, total_cost, avg_cost_per_run, avg_quality
FROM monitoring.workflow_cost_quality
ORDER BY total_cost DESC;

-- Find cost-saving model alternatives
SELECT
  c.task_type,
  c.model as current_model,
  c.avg_cost as current_cost,
  f.model as alternative_model,
  f.avg_cost as alternative_cost,
  f.avg_quality as alternative_quality,
  (c.avg_cost - f.avg_cost) as cost_savings
FROM monitoring.model_champions c
JOIN monitoring.cost_quality_frontier f ON c.task_type = f.task_type
WHERE f.avg_quality >= c.avg_quality * 0.95  -- Within 5% of champion quality
  AND f.avg_cost < c.avg_cost
ORDER BY cost_savings DESC;
```

### 3. Monitor Quality Degradation

```sql
-- Quality trend (7-day moving average)
SELECT
  date,
  workflow,
  avg_quality,
  AVG(avg_quality) OVER (
    PARTITION BY workflow
    ORDER BY date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) as moving_avg_7d
FROM monitoring.consensus_trends
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC, workflow;

-- Alert if quality drops >10%
WITH baseline AS (
  SELECT workflow, AVG(avg_quality) as baseline_quality
  FROM monitoring.consensus_trends
  WHERE date >= CURRENT_DATE - INTERVAL '30 days'
  GROUP BY workflow
),
recent AS (
  SELECT workflow, AVG(avg_quality) as recent_quality
  FROM monitoring.consensus_trends
  WHERE date >= CURRENT_DATE - INTERVAL '7 days'
  GROUP BY workflow
)
SELECT
  b.workflow,
  b.baseline_quality,
  r.recent_quality,
  (r.recent_quality - b.baseline_quality) / b.baseline_quality as quality_change_pct
FROM baseline b
JOIN recent r ON b.workflow = r.workflow
WHERE r.recent_quality < b.baseline_quality * 0.90  -- >10% drop
ORDER BY quality_change_pct;
```

### 4. Investigate Failures

```sql
-- Failure hotspots
SELECT
  workflow,
  model,
  failed_phase,
  total_failures,
  pct_of_workflow_failures
FROM monitoring.failure_patterns
WHERE total_failures >= 3
ORDER BY pct_of_workflow_failures DESC;

-- Recent errors
SELECT
  error_message,
  occurrences,
  last_occurrence,
  avg_time_to_failure_sec
FROM monitoring.common_errors
WHERE last_occurrence >= NOW() - INTERVAL '24 hours'
ORDER BY occurrences DESC;
```

### 5. Verify Phase Optimization

```sql
-- Before/after phase duration comparison
WITH before AS (
  SELECT AVG(avg_verify_sec) as avg_verify_before
  FROM monitoring.phase_durations
  WHERE date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '7 days'
),
after AS (
  SELECT AVG(avg_verify_sec) as avg_verify_after
  FROM monitoring.phase_durations
  WHERE date >= CURRENT_DATE - INTERVAL '7 days'
)
SELECT
  avg_verify_before,
  avg_verify_after,
  (avg_verify_after - avg_verify_before) / avg_verify_before as improvement_pct
FROM before, after;
```

## Integration with Workflows

### Automatic Data Collection

The `WorkflowStorageAdapter` automatically stores execution data and refreshes views:

```javascript
import { WorkflowStorageAdapter } from '~/.claude/learning/workflow-storage-adapter.js';

const storage = new WorkflowStorageAdapter();

await storage.storeExecution({
  workflow: 'deep-research',
  model: 'claude-opus-4',
  task_type: 'research_synthesis',
  quality_score: 0.87,
  input_tokens: 15000,
  output_tokens: 3000,
  cost_usd: 0.045,
  duration_ms: 45000,
  outcome: 'success',
  metadata: {
    session_id: 'research_2026-06-19_abc123',
    angles_count: 5,
    sources_count: 12,
    claims_verified: 45,
    claims_total: 52,
    phase_verify_duration_ms: 20000  // For phase analysis
  }
});

await storage.disconnect();
```

### Query from Workflows

```javascript
const { Client } = require('pg');

const client = new Client({
  host: 'laptop-01',
  database: 'learning',
  user: 'sfloess'
});

await client.connect();

// Get best model for task
const result = await client.query(
  'SELECT champion_model FROM monitoring.model_champions WHERE task_type = $1',
  ['research_synthesis']
);

const bestModel = result.rows[0]?.champion_model || 'claude-sonnet-4';

await client.end();
```

## Performance Notes

### Query Performance

- **Materialized views**: 0.5-2ms (cached results)
- **Regular views**: 10-50ms (real-time query)
- **Complex joins**: 50-200ms (with indexes)

### View Refresh Times

- `model_performance_summary`: ~50ms
- `cost_quality_frontier`: ~100ms
- `model_specialization`: ~150ms

### Optimization Tips

1. **Use materialized views** for dashboards (fast, slightly stale)
2. **Use regular views** for real-time monitoring (slower, current)
3. **Refresh concurrently** during low traffic periods
4. **Add indexes** to execution_summary for custom queries

### Recommended Indexes

```sql
-- Custom indexes for faster analytics
CREATE INDEX IF NOT EXISTS idx_exec_summary_workflow_model
  ON monitoring.execution_summary(workflow, model, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_exec_summary_task_outcome
  ON monitoring.execution_summary(task_type, outcome, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_exec_summary_metadata_gin
  ON monitoring.execution_summary USING GIN (metadata jsonb_path_ops);
```

## Troubleshooting

### Views Not Refreshing

```sql
-- Check last refresh time
SELECT schemaname, matviewname, last_refresh
FROM pg_stat_user_tables
WHERE schemaname IN ('monitoring', 'learning');

-- Manually refresh
SELECT * FROM monitoring.refresh_all_views();
```

### Slow Queries

```sql
-- Enable query timing
\timing on

-- Analyze query plan
EXPLAIN ANALYZE SELECT * FROM monitoring.top_model_combinations;

-- Update table statistics
ANALYZE monitoring.execution_summary;
```

### Missing Data

```sql
-- Check execution count
SELECT COUNT(*) FROM monitoring.execution_summary;

-- Check recent inserts
SELECT COUNT(*) FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '1 hour';

-- Verify workflow-storage-adapter is being used
SELECT DISTINCT workflow FROM monitoring.execution_summary;
```

## Next Steps

1. **Add custom metrics** to metadata field for domain-specific analysis
2. **Create alerts** in Grafana for quality degradation or cost spikes
3. **Export reports** via scheduled SQL queries to CSV/JSON
4. **Integrate with CI/CD** for automated model selection
5. **Build prediction models** using historical performance data

## References

- Database: `laptop-01:5432/learning`
- Schema docs: `~/.claude/learning/workflow-storage-adapter.js`
- Grafana: `http://pi-02:3000`
- CLAUDE.md: Continual learning infrastructure section
