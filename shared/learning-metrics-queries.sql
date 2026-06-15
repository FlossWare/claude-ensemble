-- Learning Metrics Database Queries
-- Ready-to-use SQL for metrics calculation
-- Note: Replace ? with parameter values from your application

-- ============================================================================
-- METRIC 1: Learning Intelligence Score (LIS) Component Queries
-- ============================================================================

-- Get model/task aggregated statistics for LIS calculation
-- Used to compute quality, cost, and speed percentiles
SELECT
  model,
  task_type,
  COUNT(*) as sample_count,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  AVG(cost_usd) as avg_cost,
  STDDEV(cost_usd) as cost_stddev,
  AVG(duration_ms) as avg_duration,
  STDDEV(duration_ms) as duration_stddev,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as success_rate
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY model, task_type
HAVING COUNT(*) >= 10;

-- Get recent trend data (last 10 samples) for bonus calculations
WITH recent_samples AS (
  SELECT
    model,
    task_type,
    quality_score,
    cost_usd,
    duration_ms,
    ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND quality_score IS NOT NULL
  LIMIT 10
)
SELECT
  model,
  task_type,
  rn,
  quality_score,
  cost_usd,
  duration_ms
FROM recent_samples
ORDER BY rn;

-- Consistency calculation: Coefficient of variation
SELECT
  model,
  task_type,
  COUNT(*) as samples,
  AVG(quality_score) as mean_quality,
  STDDEV(quality_score) as stddev_quality,
  STDDEV(quality_score) / NULLIF(AVG(quality_score), 0) as quality_cv,
  AVG(cost_usd) as mean_cost,
  STDDEV(cost_usd) as stddev_cost,
  STDDEV(cost_usd) / NULLIF(AVG(cost_usd), 0) as cost_cv
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY model, task_type
ORDER BY quality_cv ASC;

-- ============================================================================
-- METRIC 2: Quality Trend Analysis
-- ============================================================================

-- Split data into older and recent periods for trend analysis
WITH time_split AS (
  SELECT
    model,
    task_type,
    quality_score,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period,
    ROW_NUMBER() OVER (
      PARTITION BY model, task_type
      ORDER BY timestamp DESC
    ) as rn
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND quality_score IS NOT NULL
)
SELECT
  model,
  task_type,
  period,
  COUNT(*) as n,
  AVG(quality_score) as mean,
  STDDEV(quality_score) as stddev,
  MIN(quality_score) as min_quality,
  MAX(quality_score) as max_quality,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY quality_score) as median
FROM time_split
GROUP BY model, task_type, period;

-- Calculate linear trend for recent samples (for t-test)
WITH ranked_quality AS (
  SELECT
    model,
    task_type,
    quality_score,
    ROW_NUMBER() OVER (ORDER BY timestamp DESC) - 1 as x
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND quality_score IS NOT NULL
  ORDER BY timestamp DESC
  LIMIT 20
)
SELECT
  model,
  task_type,
  COUNT(*) as n,
  SUM(x) as sum_x,
  SUM(quality_score) as sum_y,
  SUM(x * x) as sum_x2,
  SUM(x * quality_score) as sum_xy,
  -- Slope = (n*sum_xy - sum_x*sum_y) / (n*sum_x2 - (sum_x)^2)
  (COUNT(*) * SUM(x * quality_score) - SUM(x) * SUM(quality_score)) /
  (COUNT(*) * SUM(x * x) - SUM(x) * SUM(x)) as slope
FROM ranked_quality
GROUP BY model, task_type;

-- Quality trend over daily intervals
SELECT
  DATE(timestamp) as date,
  model,
  task_type,
  COUNT(*) as run_count,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  MIN(quality_score) as min_quality,
  MAX(quality_score) as max_quality
FROM execution_log
WHERE model = ? AND task_type = ?
  AND quality_score IS NOT NULL
GROUP BY DATE(timestamp), model, task_type
ORDER BY DATE(timestamp) DESC
LIMIT 30;

-- ============================================================================
-- METRIC 3: Cost Efficiency Analysis
-- ============================================================================

-- Cost per quality point calculations
WITH cost_quality AS (
  SELECT
    model,
    task_type,
    timestamp,
    cost_usd,
    quality_score,
    cost_usd / NULLIF(quality_score, 0) as cost_per_quality
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND cost_usd > 0 AND quality_score > 0
)
SELECT
  model,
  task_type,
  COUNT(*) as samples,
  AVG(cost_per_quality) as mean_cost_per_quality,
  STDDEV(cost_per_quality) as stddev_cost_per_quality,
  MIN(cost_per_quality) as best_efficiency,
  MAX(cost_per_quality) as worst_efficiency,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cost_per_quality) as median
FROM cost_quality
GROUP BY model, task_type;

-- Daily cost efficiency trend
SELECT
  DATE(timestamp) as date,
  model,
  task_type,
  COUNT(*) as run_count,
  AVG(cost_usd) as avg_cost,
  AVG(quality_score) as avg_quality,
  AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality,
  STDDEV(cost_usd / NULLIF(quality_score, 0)) as stddev_cost_per_quality
FROM execution_log
WHERE model = ? AND task_type = ?
  AND cost_usd > 0 AND quality_score > 0
GROUP BY DATE(timestamp), model, task_type
ORDER BY DATE(timestamp) DESC
LIMIT 30;

-- Efficiency leaderboard: cost per quality across all models
WITH efficiency AS (
  SELECT
    model,
    task_type,
    COUNT(*) as samples,
    AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality,
    AVG(cost_usd) as avg_cost,
    AVG(quality_score) as avg_quality
  FROM execution_log
  WHERE cost_usd > 0 AND quality_score > 0
  GROUP BY model, task_type
  HAVING COUNT(*) >= 10
)
SELECT
  model,
  task_type,
  cost_per_quality,
  avg_cost,
  avg_quality,
  samples,
  PERCENT_RANK() OVER (ORDER BY cost_per_quality ASC) as efficiency_percentile
FROM efficiency
ORDER BY cost_per_quality ASC;

-- ============================================================================
-- METRIC 4: Speed Improvement Analysis
-- ============================================================================

-- Speed by time period
WITH periods AS (
  SELECT
    model,
    task_type,
    duration_ms,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND duration_ms > 0
)
SELECT
  model,
  task_type,
  period,
  COUNT(*) as n,
  AVG(duration_ms) as mean_duration,
  STDDEV(duration_ms) as stddev_duration,
  MIN(duration_ms) as fastest,
  MAX(duration_ms) as slowest,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_ms) as p25,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_ms) as p75,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_ms) as p90
FROM periods
GROUP BY model, task_type, period;

-- Linear trend for recent speeds
WITH ranked_duration AS (
  SELECT
    model,
    task_type,
    duration_ms,
    ROW_NUMBER() OVER (ORDER BY timestamp DESC) - 1 as x
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND duration_ms > 0
  ORDER BY timestamp DESC
  LIMIT 20
)
SELECT
  model,
  task_type,
  COUNT(*) as n,
  (COUNT(*) * SUM(x * duration_ms) - SUM(x) * SUM(duration_ms)) /
  (COUNT(*) * SUM(x * x) - SUM(x) * SUM(x)) as slope_ms_per_sample
FROM ranked_duration
GROUP BY model, task_type;

-- Daily speed metrics
SELECT
  DATE(timestamp) as date,
  model,
  task_type,
  COUNT(*) as run_count,
  AVG(duration_ms) as avg_duration,
  MIN(duration_ms) as fastest,
  MAX(duration_ms) as slowest,
  STDDEV(duration_ms) as stddev_duration
FROM execution_log
WHERE model = ? AND task_type = ?
  AND duration_ms > 0
GROUP BY DATE(timestamp), model, task_type
ORDER BY DATE(timestamp) DESC
LIMIT 30;

-- Speed percentiles across all models (for comparison)
SELECT
  model,
  task_type,
  COUNT(*) as samples,
  AVG(duration_ms) as mean,
  STDDEV(duration_ms) as stddev,
  MIN(duration_ms) as fastest,
  MAX(duration_ms) as slowest,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_ms) as p25,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_ms) as p75,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_ms) as p90
FROM execution_log
WHERE duration_ms > 0
GROUP BY model, task_type
HAVING COUNT(*) >= 10
ORDER BY mean ASC;

-- ============================================================================
-- COMPOSITE QUERIES
-- ============================================================================

-- Leaderboard: All models ranked by LIS components
WITH quality_rank AS (
  SELECT
    model,
    task_type,
    AVG(quality_score) as avg_quality,
    PERCENT_RANK() OVER (ORDER BY AVG(quality_score) DESC) as quality_percentile
  FROM execution_log
  WHERE quality_score IS NOT NULL
  GROUP BY model, task_type
  HAVING COUNT(*) >= 10
),
cost_rank AS (
  SELECT
    model,
    task_type,
    AVG(cost_usd) as avg_cost,
    PERCENT_RANK() OVER (ORDER BY AVG(cost_usd)) as cost_percentile
  FROM execution_log
  WHERE cost_usd > 0
  GROUP BY model, task_type
  HAVING COUNT(*) >= 10
),
speed_rank AS (
  SELECT
    model,
    task_type,
    AVG(duration_ms) as avg_duration,
    PERCENT_RANK() OVER (ORDER BY AVG(duration_ms)) as speed_percentile
  FROM execution_log
  WHERE duration_ms > 0
  GROUP BY model, task_type
  HAVING COUNT(*) >= 10
)
SELECT
  q.model,
  q.task_type,
  q.avg_quality,
  c.avg_cost,
  s.avg_duration,
  ROUND(q.quality_percentile * 35 +
        (1 - c.cost_percentile) * 25 +
        (1 - s.speed_percentile) * 20, 1) as lis_estimate
FROM quality_rank q
LEFT JOIN cost_rank c ON q.model = c.model AND q.task_type = c.task_type
LEFT JOIN speed_rank s ON q.model = s.model AND q.task_type = s.task_type
ORDER BY lis_estimate DESC;

-- Model synergy analysis: compare combinations vs individual models
SELECT
  mc.task_type,
  mc.worker_models,
  mc.arbiter_model,
  mc.avg_quality as combo_quality,
  mc.avg_cost_usd as combo_cost,
  mc.synergy_score,
  mc.diversity_score,
  mc.usage_count,
  -- Compare to best individual model performance
  (SELECT MAX(avg_quality)
   FROM model_tuning mt
   WHERE mt.task_type = mc.task_type
  ) as best_individual_quality,
  mc.avg_quality - (SELECT MAX(avg_quality)
                    FROM model_tuning mt
                    WHERE mt.task_type = mc.task_type) as quality_gain_over_best
FROM model_combinations mc
ORDER BY mc.synergy_score DESC;

-- ============================================================================
-- REGRESSION DETECTION QUERIES
-- ============================================================================

-- Detect quality regression (recent vs older)
WITH period_stats AS (
  SELECT
    model,
    task_type,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period,
    quality_score
  FROM execution_log
  WHERE quality_score IS NOT NULL
),
aggregated AS (
  SELECT
    model,
    task_type,
    period,
    AVG(quality_score) as mean_quality,
    COUNT(*) as n
  FROM period_stats
  GROUP BY model, task_type, period
)
SELECT
  o.model,
  o.task_type,
  o.mean_quality as older_mean,
  r.mean_quality as recent_mean,
  ((r.mean_quality - o.mean_quality) / o.mean_quality) * 100 as change_percent,
  CASE
    WHEN r.mean_quality < o.mean_quality THEN 'DECLINING'
    WHEN r.mean_quality > o.mean_quality THEN 'IMPROVING'
    ELSE 'STABLE'
  END as trend
FROM (SELECT * FROM aggregated WHERE period = 'older') o
JOIN (SELECT * FROM aggregated WHERE period = 'recent') r
  ON o.model = r.model AND o.task_type = r.task_type
WHERE ((r.mean_quality - o.mean_quality) / o.mean_quality) * 100 < -5
ORDER BY change_percent DESC;

-- Detect cost regression (cost per quality increasing)
WITH period_efficiency AS (
  SELECT
    model,
    task_type,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period,
    cost_usd / NULLIF(quality_score, 0) as cost_per_quality
  FROM execution_log
  WHERE cost_usd > 0 AND quality_score > 0
),
aggregated AS (
  SELECT
    model,
    task_type,
    period,
    AVG(cost_per_quality) as mean_efficiency
  FROM period_efficiency
  GROUP BY model, task_type, period
)
SELECT
  o.model,
  o.task_type,
  o.mean_efficiency as older_efficiency,
  r.mean_efficiency as recent_efficiency,
  ((r.mean_efficiency - o.mean_efficiency) / o.mean_efficiency) * 100 as change_percent,
  CASE
    WHEN r.mean_efficiency > o.mean_efficiency THEN 'COST INCREASE'
    WHEN r.mean_efficiency < o.mean_efficiency THEN 'COST DECREASE'
    ELSE 'STABLE'
  END as trend
FROM (SELECT * FROM aggregated WHERE period = 'older') o
JOIN (SELECT * FROM aggregated WHERE period = 'recent') r
  ON o.model = r.model AND o.task_type = r.task_type
WHERE ((r.mean_efficiency - o.mean_efficiency) / o.mean_efficiency) * 100 > 5
ORDER BY change_percent DESC;

-- Detect speed regression (getting slower)
WITH period_speed AS (
  SELECT
    model,
    task_type,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period,
    duration_ms
  FROM execution_log
  WHERE duration_ms > 0
),
aggregated AS (
  SELECT
    model,
    task_type,
    period,
    AVG(duration_ms) as mean_duration
  FROM period_speed
  GROUP BY model, task_type, period
)
SELECT
  o.model,
  o.task_type,
  o.mean_duration as older_duration,
  r.mean_duration as recent_duration,
  ((r.mean_duration - o.mean_duration) / o.mean_duration) * 100 as change_percent,
  CASE
    WHEN r.mean_duration > o.mean_duration THEN 'SLOWDOWN'
    WHEN r.mean_duration < o.mean_duration THEN 'SPEEDUP'
    ELSE 'STABLE'
  END as trend
FROM (SELECT * FROM aggregated WHERE period = 'older') o
JOIN (SELECT * FROM aggregated WHERE period = 'recent') r
  ON o.model = r.model AND o.task_type = r.task_type
WHERE ((r.mean_duration - o.mean_duration) / o.mean_duration) * 100 > 5
ORDER BY change_percent DESC;

-- ============================================================================
-- DIAGNOSTIC QUERIES
-- ============================================================================

-- Most recent executions with all key metrics
SELECT
  id,
  timestamp,
  model,
  task_type,
  quality_score,
  cost_usd,
  duration_ms,
  confidence,
  outcome,
  was_selected,
  ROUND(cost_usd / NULLIF(quality_score, 0), 4) as cost_per_quality
FROM execution_log
ORDER BY timestamp DESC
LIMIT 50;

-- Summary stats: samples, quality, cost, speed by model
SELECT
  model,
  COUNT(*) as total_executions,
  COUNT(DISTINCT task_type) as task_types,
  AVG(CASE WHEN quality_score IS NOT NULL THEN quality_score END) as avg_quality,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
  ROUND(AVG(cost_usd), 4) as avg_cost,
  ROUND(AVG(duration_ms), 0) as avg_duration,
  MAX(timestamp) as last_execution
FROM execution_log
GROUP BY model
ORDER BY total_executions DESC;

-- Task complexity analysis
SELECT
  task_type,
  COUNT(*) as executions,
  COUNT(DISTINCT model) as models_used,
  AVG(quality_score) as avg_quality,
  AVG(duration_ms) as avg_duration,
  AVG(cost_usd) as avg_cost,
  ROUND(AVG(confidence), 3) as avg_confidence
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY task_type
ORDER BY executions DESC;
