# Learning Intelligence Score (LIS) Dashboard

Comprehensive dashboard for visualizing and tracking AI learning progress across all models and tasks.

## Overview

The LIS Dashboard provides a single-score metric (0-100) that aggregates multiple performance dimensions:

- **Quality improvement**: 40% weight
- **Cost efficiency**: 30% weight  
- **Speed improvement**: 20% weight
- **Consistency**: 10% weight

## Components

### 1. Core Calculator (`learning/calculate-lis.js`)

Standalone module that computes LIS and related metrics:

```javascript
import { computeLIS, computeLeaderboard } from './learning/calculate-lis.js';

// Get LIS for specific model/task
const lis = computeLIS('opus', 'code_review');
console.log(lis.score); // 0-100

// Get ranked leaderboard
const leaderboard = computeLeaderboard({ minSamples: 10 });
```

**Functions:**
- `computeLIS(model, taskType)` - Calculate weighted LIS score
- `computeQualityTrend(model, taskType)` - Statistical improvement detection via Welch's t-test
- `computeCostEfficiency(model, taskType)` - Cost per quality point with trend
- `computeSpeedImprovement(model, taskType)` - Execution time reduction
- `computeAllMetrics(model, taskType)` - All four metrics in one call
- `computeLeaderboard()` - Ranked list of all model/task combinations
- `recomputeModelPerformance()` - Background recomputation for caching

### 2. Dashboard CLI (`scripts/learning-dashboard.sh`)

Interactive terminal dashboard with rich visualizations.

**Usage:**
```bash
# Standard view
./scripts/learning-dashboard.sh

# Filtered by model
./scripts/learning-dashboard.sh --model opus

# Filtered by task
./scripts/learning-dashboard.sh --task code_review

# Custom time window
./scripts/learning-dashboard.sh --days 7

# Compact view
./scripts/learning-dashboard.sh --compact

# JSON export
./scripts/learning-dashboard.sh --json > lis-data.json

# Export to file
./scripts/learning-dashboard.sh --export dashboard.json

# Combined
./scripts/learning-dashboard.sh --model opus --days 14 --compact
```

**Options:**
- `--model <name>` - Filter by specific model
- `--task <type>` - Filter by task type
- `--days <N>` - Show trend for last N days (default: 30)
- `--json` - Output raw JSON data
- `--export <file>` - Export dashboard data to file
- `--compact` - Show compact view
- `-h, --help` - Show help message

### 3. Test Suite (`scripts/test-lis-dashboard.sh`)

Automated test script that:
1. Creates sample data if needed (50 executions across 30 days)
2. Tests standard dashboard view
3. Tests compact view
4. Tests 7-day trend window
5. Tests JSON export functionality

**Usage:**
```bash
./scripts/test-lis-dashboard.sh
```

## Dashboard Sections

### 1. Current LIS Score

Shows global LIS (average across all model/task combinations):
- Visual score indicator (★ Excellent, ◆ Good, ● Fair, ○ Poor, ✗ Very Poor)
- Progress bar (0-100)
- Weighted component breakdown
- Sample count

**Score Ratings:**
- 90-100: ★ Excellent (green)
- 75-89: ◆ Good (green)
- 60-74: ● Fair (yellow)
- 40-59: ○ Poor (yellow)
- 0-39: ✗ Very Poor (red)

### 2. Trend Graph

Sparkline visualizations of last N days:
- Quality trend (avg quality score)
- Cost trend (scaled for visibility)
- Speed trend (inverse - faster is better)

Uses Unicode block characters: `▁▂▃▄▅▆▇█`

### 3. Top Improvements

Models/tasks showing significant positive trends:
- Quality improvements (via Welch's t-test)
- Speed improvements (>5% faster)
- Confidence indicators (★ stars)
- Sorted by improvement magnitude

### 4. Top Performers

Leaderboard of model/task combinations by LIS:
- Rank, model, task type
- LIS score with visual indicator
- Component scores (Quality, Cost, Speed)
- Top 5 shown by default (--leaderboard for all)

### 5. Recent Learnings

Last N executions (default 10, 5 in compact mode):
- Timestamp
- Model and task type
- Quality score
- Cost (USD)
- Outcome (✓ success, ✗ failed, ? unknown)

## LIS Calculation Details

### Component Scores (0-100 each)

**Quality Score (35% weight):**
- Percentile rank vs all models/tasks
- Trend bonus: up to +10 points for improving quality
- Formula: `(percentileRank * 100 + trendBonus) / 1.1`

**Cost Score (25% weight):**
- Inverse percentile rank (lower cost = higher score)
- Trend bonus: up to +15 points for reducing cost
- Formula: `((1 - percentile) * 100 + trendBonus) / 1.15`

**Speed Score (20% weight):**
- Inverse percentile rank (lower duration = higher score)
- Trend bonus: up to +10 points for improving speed
- Formula: `((1 - percentile) * 100 + trendBonus) / 1.1`

**Consistency Score (20% weight):**
- Based on coefficient of variation (CV)
- Lower CV = more consistent = higher score
- Combines quality CV and cost CV
- Formula: `(100 - qualityCV*200 + 100 - costCV*200) / 2`

### Final LIS
```
LIS = 0.35*quality + 0.25*cost + 0.20*speed + 0.20*consistency
```

Clamped to [0, 100] range.

## Statistical Methods

### Quality Trend Detection (Welch's t-test)

Splits recent quality scores into two halves and tests for significant difference:

1. Calculate means: `recentMean`, `olderMean`
2. Calculate standard deviations
3. Compute pooled standard error
4. Calculate t-score: `(recentMean - olderMean) / pooledStdError`
5. Estimate p-value from t-score and degrees of freedom
6. Classify trend:
   - `p < 0.05` and positive: "improving"
   - `p < 0.05` and negative: "declining"
   - Otherwise: "stable"

**Confidence:** `1 - pValue` (capped at 0.99)

### Linear Regression

For recent trend analysis:

```javascript
slope = (n*sumXY - sumX*sumY) / (n*sumX² - sumX²)
intercept = (sumY - slope*sumX) / n
r² = 1 - (residualSS / totalSS)
```

Used for:
- Quality trend slope
- Cost efficiency trend
- Speed improvement trend

### Cost Efficiency

Cost per quality point:
```
costPerQuality = cost_usd / quality_score
```

Ranked across all model/task combinations (lower is better).

**Efficiency Score:** `(1 - percentile) * 100`

### Speed Improvement

Percentage reduction in execution time:
```
speedImprovement = ((oldMean - recentMean) / oldMean) * 100
```

Positive values indicate faster execution.

## Data Requirements

### Minimum Samples
- **LIS calculation:** 10 samples per model/task (configurable)
- **Trend analysis:** 5 samples minimum
- **Leaderboard:** 5 samples minimum (default)

### Time Windows
- **Dashboard default:** 30 days
- **Configurable:** 1-365 days via `--days` option
- **Background recompute:** Every 5 minutes (cached in `model_performance` table)

## Integration

### With Learning Logger
```javascript
import { logExecution } from './learning/db.js';
import { computeLIS } from './learning/calculate-lis.js';

// Log an execution
logExecution({
  model: 'opus',
  task_type: 'code_review',
  quality_score: 0.85,
  cost_usd: 0.0023,
  duration_ms: 4500,
  outcome: 'success'
});

// Compute updated LIS
const lis = computeLIS('opus', 'code_review');
console.log(`Updated LIS: ${lis.score}`);
```

### With Workflows
```javascript
import { recomputeModelPerformance } from './learning/calculate-lis.js';

// In workflow completion handler
async function onWorkflowComplete() {
  // Recompute all model performance metrics
  const result = recomputeModelPerformance({ minSamples: 3 });
  console.log(`Updated ${result.modelsUpdated} models across ${result.windowsComputed} windows`);
}
```

### JSON Export Format
```json
{
  "globalLIS": {
    "score": 78.3,
    "qualityImprovement": 12.5,
    "costReduction": 68.2,
    "speedImprovement": 8.7,
    "userSatisfaction": 0,
    "sampleCount": 15
  },
  "trendHistory": [
    {
      "day": "2026-05-14",
      "avg_quality": 0.847,
      "avg_cost": 0.0018,
      "avg_duration": 4234,
      "count": 8
    }
  ],
  "topImprovements": [
    {
      "model": "opus",
      "taskType": "code_review",
      "improvement": 15.3,
      "confidence": 0.95,
      "metric": "quality"
    }
  ],
  "recentLearnings": [...],
  "leaderboard": [...],
  "weights": {
    "quality": 0.35,
    "cost": 0.25,
    "speed": 0.20,
    "consistency": 0.20
  },
  "timestamp": "2026-06-13T15:30:00.000Z"
}
```

## Performance

### Caching Strategy
- Background recomputation every 5 minutes
- Results cached in `model_performance` table
- Four time windows: day, week, month, all_time
- On-demand computation for filtered views

### Query Optimization
- Indexed on `(model, task_type, timestamp)`
- Indexed on `quality_score`, `cost_usd`, `duration_ms`
- Recent values limited to last 100 entries
- Percentile calculations on sorted arrays

## Visualizations

### Progress Bars
```
Quality:  ███████████████████████████████████████░░░░░  87.3/100
```

### Sparklines
```
Quality:  ▃▄▅▆▇█████▇▆▅▄▃▂▁▂▃▄▅▆▇████  (avg: 0.847)
```

### Trend Indicators
```
Quality:    ↑ +12.5%  (improving)
Cost:       ↑ +8.2%   (improving - lower is better)
Speed:      → 0.3%    (stable)
```

### Score Indicators
```
★ 92.1    Excellent
◆ 81.5    Good
● 68.3    Fair
○ 52.1    Poor
✗ 28.7    Very Poor
```

## Troubleshooting

### "Database unavailable"
```bash
# Initialize database
./scripts/learning-session.sh code-review
```

### "No metrics available yet"
- Need minimum 5 samples per model/task
- Run workflows to generate data
- Reduce `minSamples` in code if testing

### "Insufficient data for global LIS"
- Need at least one model/task with 5+ samples
- Use `--model` and `--task` filters for partial data

### Empty trend graph
- Check `--days` window (may need to reduce)
- Verify executions within time window
- Use `./scripts/learning-status.sh` to check data

## Future Enhancements

### Planned Features
1. **User satisfaction tracking** - Feedback integration (currently 0% weight)
2. **Model combination synergy** - Multi-model consensus patterns
3. **Prediction confidence** - Forward-looking LIS estimates
4. **Automated alerts** - Notification on significant regressions
5. **Web dashboard** - Browser-based real-time visualization
6. **Grafana integration** - Prometheus metrics export

### Extensibility Points
- Custom weights via config file
- Additional component scores (security, reliability, etc.)
- Pluggable statistical methods
- Custom trend detection algorithms
- Integration with external monitoring systems

## References

- Core implementation: `/learning/calculate-lis.js`
- Database schema: `/learning/init-db.sql`
- Learning logger: `/learning/db.js`
- Dashboard script: `/scripts/learning-dashboard.sh`
- Test suite: `/scripts/test-lis-dashboard.sh`
- Usage guide: `/docs/learning-system.md`
