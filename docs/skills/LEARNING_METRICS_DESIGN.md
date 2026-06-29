# Learning Metrics Calculation System

## Overview

This document describes the complete metrics system for measuring AI model learning and improvement. The system tracks four primary metrics that aggregate into a single Learning Intelligence Score (LIS).

### Key Principles

1. **Multi-dimensional**: Combines quality, cost, speed, and consistency
2. **Trend-aware**: Detects improvement vs. decline with statistical significance
3. **Comparative**: Ranks models against peers
4. **Practical**: Weights metrics by business value (quality > cost > speed)

---

## Metric 1: Learning Intelligence Score (LIS)

**Purpose**: Single 0-100 score showing overall improvement trajectory

### Formula

```
LIS = 35 × QualityScore + 25 × CostScore + 20 × SpeedScore + 20 × ConsistencyScore

Where each component ∈ [0, 100]
```

### Component Weights (Justification)

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Quality | 35% | Output quality is paramount for AI |
| Cost | 25% | Important for production viability |
| Speed | 20% | Improves user experience |
| Consistency | 20% | Enables reliable automation |

### Quality Score Calculation

```
BaseQualityScore = percentile_rank(avg_quality_score, all_models) × 100

RecentTrendBonus = max(0, linear_trend(recent_10_samples) × 10)

QualityScore = min(100, BaseQualityScore + RecentTrendBonus) / 1.1

Where:
- percentile_rank ∈ [0, 1]: Where model ranks vs all competitors
- Bonus ∈ [0, 10]: Recent improvement boost
- Division by 1.1: Normalization cap
```

**Example**:
- Model has 0.85 avg quality (75th percentile) = 75 points
- Recent quality trend improving at 0.02/sample = +5 bonus
- Final Quality = min(100, 80) / 1.1 = 72.7

### Cost Score Calculation

```
BaseCostScore = (1 - percentile_rank(avg_cost_usd, all_costs)) × 100
# Inverted: lower cost = higher score

RecentTrendBonus = max(0, -linear_trend(recent_10_costs) × 15)
# Negative trend (decreasing cost) is good

CostScore = min(100, BaseCostScore + RecentTrendBonus) / 1.15
```

**Example**:
- Model costs $0.025 per run (25th percentile = cheapest 25%) = 75 points
- Cost trend improving at -$0.0002/call = +12 bonus
- Final Cost = min(100, 87) / 1.15 = 75.7

### Speed Score Calculation

```
BaseSpeedScore = (1 - percentile_rank(avg_duration_ms, all_durations)) × 100
# Inverted: lower duration = higher score

RecentTrendBonus = max(0, -linear_trend(recent_10_durations) × 10)
# Negative trend (faster) is good

SpeedScore = min(100, BaseSpeedScore + RecentTrendBonus) / 1.1
```

**Example**:
- Model executes in 2500ms (90th percentile = fast) = 10 points
- Duration trend improving at -50ms/call = +8 bonus
- Final Speed = min(100, 18) / 1.1 = 16.4

### Consistency Score Calculation

```
QualityCV = stddev(recent_quality_samples) / mean(recent_quality_samples)
CostCV = stddev(recent_cost_samples) / mean(recent_cost_samples)

QualityCVScore = max(0, 100 - QualityCV × 200)
CostCVScore = max(0, 100 - CostCV × 200)

ConsistencyScore = (QualityCVScore + CostCVScore) / 2

Where:
- CV > 0.5: Penalized heavily (volatile)
- CV < 0.2: Excellent (stable)
- CV = 0.3: ~65 points (good)
```

**Example**:
- Quality CV = 0.15 (consistent) = 70 points
- Cost CV = 0.25 (stable) = 50 points
- Final Consistency = (70 + 50) / 2 = 60

### SQL Query: LIS Components

```sql
-- Get aggregated stats for quality/cost/speed
SELECT
  model,
  task_type,
  COUNT(*) as sample_count,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  AVG(cost_usd) as avg_cost,
  STDDEV(cost_usd) as cost_stddev,
  AVG(duration_ms) as avg_duration,
  STDDEV(duration_ms) as duration_stddev
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY model, task_type
HAVING sample_count >= 10;

-- Get recent trend (last 10 samples)
SELECT
  model,
  task_type,
  quality_score,
  ROW_NUMBER() OVER (ORDER BY timestamp DESC) as recency
FROM execution_log
WHERE model = ? AND task_type = ?
  AND quality_score IS NOT NULL
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Metric 2: Quality Trend

**Purpose**: Detect statistical improvement, decline, or stability

### Formula

```
Improvement% = ((recent_mean - older_mean) / older_mean) × 100

t-statistic = (recent_mean - older_mean) / sqrt(s₁²/n₁ + s₂²/n₂)

p-value = P(T > |t|) using t-distribution with df = n₁ + n₂ - 2

Trend = {
  'improving' if p < 0.05 AND improvement > 0
  'declining' if p < 0.05 AND improvement < 0
  'stable' otherwise
}

Confidence = 1 - p-value (for significant trends)
```

### Interpretation

| Metric | Meaning |
|--------|---------|
| trend | Statistically significant direction |
| improvementPercent | Magnitude of change |
| confidence | Statistical reliability (0-1) |
| recentTrendSlope | Rate of change (last 10 samples) |
| recentTrendR² | How well linear model fits recent data |

### Example Output

```json
{
  "trend": "improving",
  "improvementPercent": 8.5,
  "pValue": 0.032,
  "confidence": 0.968,
  "recentTrendSlope": 0.015,
  "recentTrendR2": 0.78,
  "samples": 42,
  "mean": 0.87,
  "stdDev": 0.05
}
```

### SQL Query: Quality Trend

```sql
-- Split executions by time period
WITH time_periods AS (
  SELECT
    model,
    task_type,
    quality_score,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND quality_score IS NOT NULL
)
SELECT
  period,
  COUNT(*) as n,
  AVG(quality_score) as mean,
  STDDEV(quality_score) as stddev,
  MIN(quality_score) as min,
  MAX(quality_score) as max
FROM time_periods
GROUP BY period
ORDER BY period;

-- Recent linear trend (last 10 samples for regression)
WITH recent AS (
  SELECT
    quality_score,
    ROW_NUMBER() OVER (ORDER BY timestamp DESC) - 1 as x
  FROM execution_log
  WHERE model = ? AND task_type = ?
    AND quality_score IS NOT NULL
  ORDER BY timestamp DESC
  LIMIT 10
)
SELECT
  (COUNT(*) * SUM(x * quality_score) - SUM(x) * SUM(quality_score)) /
  (COUNT(*) * SUM(x*x) - SUM(x) * SUM(x)) as slope,
  (SUM(quality_score) - slope * SUM(x)) / COUNT(*) as intercept
FROM recent;
```

---

## Metric 3: Cost Efficiency

**Purpose**: Track cost-per-quality improvement

### Formula

```
CostPerQualityPoint = avg_cost_usd / avg_quality_score

EfficiencyPercentile = percentile_rank(cost_per_quality, all_models)
# 0 = most expensive, 1 = most efficient

EfficiencyScore = (1 - percentile_rank) × 100

EfficiencyTrend = linear_slope(recent_cost_per_quality)
# Negative slope = improving (costs down)
```

### Interpretation

| Component | Target |
|-----------|--------|
| CostPerQualityPoint | Minimize (lower is better) |
| EfficiencyPercentile | Maximize (higher is better) |
| EfficiencyTrend | Negative slope (costs declining) |

### Example Output

```json
{
  "costPerQualityPoint": 0.0185,
  "stdDev": 0.0025,
  "trendSlope": -0.0003,
  "trendR2": 0.62,
  "percentileRank": 0.72,
  "costEfficiencyScore": 72,
  "samples": 35
}
```

### SQL Query: Cost Efficiency

```sql
-- Cost per quality point, daily
SELECT
  DATE(timestamp) as date,
  model,
  task_type,
  COUNT(*) as run_count,
  AVG(cost_usd) as avg_cost,
  AVG(quality_score) as avg_quality,
  AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality,
  STDDEV(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality_stddev
FROM execution_log
WHERE cost_usd > 0 AND quality_score > 0
GROUP BY DATE(timestamp), model, task_type
ORDER BY DATE(timestamp) DESC
LIMIT 30;

-- Efficiency ranking across all models
WITH efficiency AS (
  SELECT
    model,
    task_type,
    AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality,
    COUNT(*) as sample_count
  FROM execution_log
  WHERE cost_usd > 0 AND quality_score > 0
  GROUP BY model, task_type
  HAVING sample_count >= 10
)
SELECT
  model,
  task_type,
  cost_per_quality,
  PERCENT_RANK() OVER (ORDER BY cost_per_quality) as efficiency_percentile,
  sample_count
FROM efficiency
ORDER BY cost_per_quality ASC;
```

---

## Metric 4: Speed Improvement

**Purpose**: Track execution time reduction

### Formula

```
OldMean = mean(execution_times from first_half)
RecentMean = mean(execution_times from recent_half)

SpeedImprovement% = ((OldMean - RecentMean) / OldMean) × 100

SpeedTrend = linear_slope(recent_10_durations)
# Negative slope = getting faster

PercentFasterRuns = count(duration < old_mean) / total_recent × 100
```

### Interpretation

| Metric | Meaning |
|--------|---------|
| speedImprovement | Overall improvement % |
| oldMean | Baseline execution time |
| recentMean | Current execution time |
| recentTrendSlope | Change rate (ms/call) |
| percentageImprovedRuns | % of recent calls faster than baseline |

### Example Output

```json
{
  "speedImprovement": 12.5,
  "oldMean": 3200,
  "recentMean": 2800,
  "recentTrendSlope": -35,
  "recentTrendR2": 0.58,
  "percentageImprovedRuns": 68,
  "samples": 40
}
```

### SQL Query: Speed Improvement

```sql
-- Speed stats by time period
WITH periods AS (
  SELECT
    duration_ms,
    CASE
      WHEN timestamp < datetime('now', '-15 days') THEN 'older'
      ELSE 'recent'
    END as period
  FROM execution_log
  WHERE model = ? AND task_type = ? AND duration_ms > 0
)
SELECT
  period,
  COUNT(*) as n,
  AVG(duration_ms) as mean_duration,
  STDDEV(duration_ms) as stddev,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_ms) as p25,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_ms) as p75
FROM periods
GROUP BY period;

-- Speed percentiles across all models
SELECT
  model,
  task_type,
  COUNT(*) as samples,
  AVG(duration_ms) as mean,
  MIN(duration_ms) as fastest,
  MAX(duration_ms) as slowest,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_ms) as p90
FROM execution_log
WHERE duration_ms > 0
GROUP BY model, task_type
HAVING COUNT(*) >= 10
ORDER BY mean ASC;
```

---

## Comprehensive Metrics Views

### Leaderboard Query

```sql
-- Top models by LIS score
SELECT
  model,
  task_type,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(cost_usd) as avg_cost,
  AVG(duration_ms) as avg_duration,
  STDDEV(quality_score) as quality_variance,
  -- LIS components (simplified)
  PERCENT_RANK() OVER (ORDER BY AVG(quality_score) DESC) * 35 as quality_component,
  PERCENT_RANK() OVER (ORDER BY AVG(cost_usd)) * 25 as cost_component,
  PERCENT_RANK() OVER (ORDER BY AVG(duration_ms)) * 20 as speed_component
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY model, task_type
HAVING COUNT(*) >= 10
ORDER BY quality_component + cost_component + speed_component DESC;
```

### Model Combination Synergy

```sql
-- Best combinations for each task
SELECT
  mc.task_type,
  mc.worker_models,
  mc.arbiter_model,
  mc.avg_quality,
  mc.avg_cost_usd,
  mc.synergy_score,
  mc.diversity_score,
  mc.usage_count,
  -- Compare to best individual
  MAX(mt.avg_quality) as best_individual_quality,
  mc.avg_quality - MAX(mt.avg_quality) as quality_gain
FROM model_combinations mc
LEFT JOIN model_tuning mt ON mc.task_type = mt.task_type
GROUP BY mc.task_type, mc.worker_models, mc.arbiter_model
ORDER BY mc.synergy_score DESC;
```

---

## Implementation Guidelines

### 1. Data Requirements

Each execution must log:
- `quality_score` (0-1): How good was output quality?
- `cost_usd`: How much did it cost?
- `duration_ms`: How long did it take?
- `confidence`: Model's self-reported confidence
- `outcome`: success/failed/partial

### 2. Minimum Sample Sizes

| Metric | Min Samples | Window |
|--------|-------------|--------|
| LIS | 10 | Last 100 executions |
| Quality Trend | 5 per period | 30 days (split 50/50) |
| Cost Efficiency | 5 | Last 20 executions |
| Speed | 5 per period | 30 days (split 50/50) |

### 3. Update Frequency

- **LIS**: Compute on-demand, cache for 1 hour
- **Trends**: Compute every 4 hours (background job)
- **Leaderboard**: Cache for 6 hours
- **Combinations**: Recompute every 30 seconds

### 4. Outlier Handling

```javascript
// Remove outliers using IQR method
function removeOutliers(values) {
  const sorted = values.sort((a, b) => a - b);
  const q1 = sorted[Math.floor(sorted.length * 0.25)];
  const q3 = sorted[Math.floor(sorted.length * 0.75)];
  const iqr = q3 - q1;
  const lower = q1 - 1.5 * iqr;
  const upper = q3 + 1.5 * iqr;
  return values.filter(v => v >= lower && v <= upper);
}
```

---

## Usage Examples

### Get Overall LIS Score

```javascript
import { calculateLIS } from './shared/learning-metrics.js';

const lis = calculateLIS('opus', 'code-review');
console.log(`LIS: ${lis.score.toFixed(1)}/100`);
console.log(`Components:`, lis.components);
// Output:
// LIS: 76.8/100
// Components: {
//   quality: 82,
//   cost: 71,
//   speed: 45,
//   consistency: 68
// }
```

### Check Quality Trend

```javascript
import { calculateQualityTrend } from './shared/learning-metrics.js';

const trend = calculateQualityTrend('sonnet', 'security');
if (trend.trend === 'improving') {
  console.log(`✓ Improving by ${trend.improvementPercent.toFixed(1)}%`);
  console.log(`  Confidence: ${(trend.confidence * 100).toFixed(0)}%`);
}
```

### Get Leaderboard

```javascript
import { getAllMetricsLeaderboard } from './shared/learning-metrics.js';

const board = getAllMetricsLeaderboard({ minSamples: 10 });
board.forEach((entry, idx) => {
  console.log(`${idx+1}. ${entry.model} (${entry.taskType}): LIS ${entry.lis.score.toFixed(0)}`);
});
```

---

## Monitoring & Alerts

### Quality Regression Alert

```javascript
const trend = calculateQualityTrend(model, taskType);
if (trend.trend === 'declining' && trend.confidence > 0.90) {
  alert(`Quality regression detected for ${model}: ${trend.improvementPercent.toFixed(1)}%`);
}
```

### Cost Spike Alert

```javascript
const efficiency = calculateCostEfficiency(model, taskType);
if (efficiency.trendSlope > 0 && efficiency.trendR2 > 0.7) {
  alert(`Cost efficiency declining for ${model}`);
}
```

### Slowdown Alert

```javascript
const speed = calculateSpeedImprovement(model, taskType);
if (speed.speedImprovement < 0 && speed.percentageImprovedRuns < 30) {
  alert(`Speed regression detected for ${model}`);
}
```

---

## Database Schema Extensions

To fully support metrics, ensure these fields exist:

```sql
-- execution_log fields needed
CREATE TABLE execution_log (
  -- ... existing fields ...
  quality_score REAL,        -- 0.0-1.0
  cost_usd REAL,            -- Cost in dollars
  duration_ms INTEGER,       -- Execution time
  confidence REAL,          -- 0.0-1.0 model confidence
  outcome TEXT,             -- success/failed/partial
  -- New fields for metrics
  cost_per_quality_point REAL,  -- Computed cost/quality
  quality_percentile REAL,      -- Percentile rank (0-1)
  speed_percentile REAL         -- Percentile rank (0-1)
);

-- Aggregate view for faster metrics
CREATE VIEW metric_summary AS
SELECT
  model,
  task_type,
  COUNT(*) as sample_count,
  AVG(quality_score) as avg_quality,
  STDDEV(quality_score) as quality_stddev,
  AVG(cost_usd) as avg_cost,
  AVG(duration_ms) as avg_duration,
  STDDEV(duration_ms) as duration_stddev
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY model, task_type;

-- Indexes for performance
CREATE INDEX idx_metrics_model_task ON execution_log(model, task_type, timestamp);
CREATE INDEX idx_metrics_quality ON execution_log(quality_score) WHERE quality_score IS NOT NULL;
CREATE INDEX idx_metrics_cost ON execution_log(cost_usd) WHERE cost_usd > 0;
```

---

## Testing Metrics System

```javascript
// Test with synthetic data
import { logExecution } from './shared/learning-logger.js';

// Simulate improving quality
for (let i = 0; i < 20; i++) {
  const quality = 0.65 + (i * 0.01);  // Trending up
  const cost = 0.02 - (i * 0.0002);   // Trending down
  
  logExecution({
    model: 'test-model',
    task_type: 'test-task',
    quality_score: quality,
    cost_usd: cost,
    duration_ms: 3000 - (i * 20),
    outcome: quality > 0.80 ? 'success' : 'partial'
  });
}

// Check metrics
const lis = calculateLIS('test-model', 'test-task');
console.log('LIS:', lis.score);  // Should be high (85-95 range)
```

---

## References

- **Statistical Methods**: t-test, linear regression, percentile ranking
- **Performance Metrics**: Coefficient of variation, R-squared
- **Business Metrics**: Cost per quality, efficiency percentiles
