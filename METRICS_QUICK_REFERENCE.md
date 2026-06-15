# Learning Metrics - Quick Reference Card

## Four Core Metrics

| Metric | Range | What It Measures | Key Formula |
|--------|-------|------------------|------------|
| **LIS** | 0-100 | Overall improvement | 35×Quality + 25×Cost + 20×Speed + 20×Consistency |
| **Quality Trend** | -∞ to +∞ % | Statistical improvement | ((recent - older) / older) × 100 |
| **Cost Efficiency** | $/quality point | Cost per quality unit | avg_cost / avg_quality |
| **Speed** | % improvement | Execution time reduction | ((old_time - new_time) / old_time) × 100 |

---

## Import & Use (Copy-Paste Ready)

### Get All Metrics
```javascript
import { getComprehensiveMetrics } from './shared/learning-metrics.js';
const m = getComprehensiveMetrics('opus', 'code-review');
console.log(`LIS: ${m.lis.score.toFixed(1)}/100`);
console.log(`Quality: ${m.qualityTrend.trend}`);
console.log(`Cost/Quality: $${m.costEfficiency.costPerQualityPoint.toFixed(4)}`);
console.log(`Speed: ${m.speedImprovement.speedImprovement.toFixed(1)}%`);
```

### Get Leaderboard
```javascript
import { getAllMetricsLeaderboard } from './shared/learning-metrics.js';
const board = getAllMetricsLeaderboard();
board.slice(0, 10).forEach((e, i) => 
  console.log(`${i+1}. ${e.model}/${e.taskType} - LIS ${e.lis.score.toFixed(1)}`)
);
```

### Check for Regression
```javascript
const trend = m.qualityTrend;
if (trend.trend === 'declining' && trend.confidence > 0.90) {
  console.warn(`Quality down ${trend.improvementPercent.toFixed(2)}%`);
}
```

### Log Execution
```javascript
import { logExecution } from './shared/learning-logger.js';
logExecution({
  model: 'opus',
  task_type: 'code-review',
  quality_score: 0.85,
  cost_usd: 0.025,
  duration_ms: 3200,
  outcome: 'success',
});
```

---

## Component Breakdown

### Quality Score (35% of LIS)
- **What**: Percentile rank vs peers + recent improvement bonus
- **Range**: 0-100
- **Good**: > 70
- **Excellent**: > 85

### Cost Score (25% of LIS)
- **What**: Inverse cost percentile + cost reduction bonus
- **Range**: 0-100
- **Good**: > 60 (cheaper than 40% of peers)
- **Excellent**: > 80 (cheaper than 80% of peers)

### Speed Score (20% of LIS)
- **What**: Inverse duration percentile + speedup bonus
- **Range**: 0-100
- **Good**: > 60
- **Excellent**: > 80

### Consistency Score (20% of LIS)
- **What**: Low variance in quality and cost
- **Range**: 0-100
- **CV < 0.2**: Excellent (low variance)
- **CV > 0.5**: Poor (high variance)

---

## Trend Interpretation

### Quality Trend
| Value | Meaning |
|-------|---------|
| `improving` + confidence > 0.90 | Statistically significant improvement |
| `declining` + confidence > 0.90 | Statistically significant decline |
| `stable` | No significant change |
| confidence < 0.80 | Insufficient data (unreliable) |

### Slope Interpretation
| Metric | Positive Slope | Negative Slope |
|--------|---|---|
| Quality | Improving | Declining |
| Cost | Increasing (bad) | Decreasing (good) |
| Speed | Slowing (bad) | Speeding up (good) |

---

## Minimum Data Requirements

| Metric | Min Samples | Window | Notes |
|--------|---|---|---|
| LIS | 10 | Any | Needs quality_score |
| Quality Trend | 5 per period | 30 days | Requires 2 periods |
| Cost Efficiency | 5 | Last 20 | Needs cost_usd > 0 |
| Speed | 5 per period | 30 days | Needs duration_ms > 0 |

---

## Logging Quality Scores by Task

```javascript
// Code Review (0-1 scale)
0.9-1.0  // Found all/most issues
0.7-0.9  // Found major issues
0.5-0.7  // Found some issues
0.0-0.5  // Missed major issues

// Bug Fix (0-1 scale)
0.9-1.0  // Fix works, tests pass
0.7-0.9  // Fix works, mostly passes
0.5-0.7  // Partial fix
0.0-0.5  // Doesn't work

// Architecture (0-1 scale)
0.9-1.0  // Sound design, implementable
0.7-0.9  // Good design, mostly implementable
0.5-0.7  // Acceptable, some concerns
0.0-0.5  // Flawed design
```

---

## Common Queries

### Find Best Model for Task
```sql
SELECT model, AVG(quality_score) as quality, COUNT(*) as n
FROM execution_log
WHERE task_type = 'code-review' AND quality_score IS NOT NULL
GROUP BY model HAVING n >= 5
ORDER BY quality DESC LIMIT 1;
```

### Find Most Cost-Efficient
```sql
SELECT model, AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality, COUNT(*) as n
FROM execution_log
WHERE task_type = 'code-review'
GROUP BY model HAVING n >= 5
ORDER BY cost_per_quality ASC LIMIT 1;
```

### Quality Over Time
```sql
SELECT DATE(timestamp) as date, AVG(quality_score) as quality
FROM execution_log
WHERE model = 'opus' AND task_type = 'code-review'
GROUP BY DATE(timestamp)
ORDER BY DATE(timestamp) DESC LIMIT 30;
```

---

## Alerts to Watch For

| Alert | Threshold | Action |
|-------|-----------|--------|
| Quality Regression | Decline > 5%, confidence > 90% | Review recent changes |
| Cost Spike | Cost/quality +5%, R² > 0.5 | Reduce prompt/output size |
| Speed Slowdown | Duration +5%, <40% of runs faster | Check infrastructure |
| High Variance | CV > 0.5 | Inconsistent performance |

---

## Database Files

| File | Location | Purpose |
|------|----------|---------|
| SQLite DB | `~/.claude/learning/db/learning.db` | Data storage |
| Schema | `~/.claude/learning/init-learning-db.sql` | Tables & indexes |
| Sample data | `~/.claude/learning/decisions.jsonl` | Historical decisions |

---

## File Locations

```
shared/learning-metrics.js          ← Main calculations
shared/learning-metrics-queries.sql ← SQL templates
shared/learning-logger.js           ← Data logging
LEARNING_METRICS_DESIGN.md          ← Formulas & theory
METRICS_INTEGRATION_GUIDE.md        ← Detailed examples
METRICS_SYSTEM_SUMMARY.md           ← Full documentation
```

---

## Examples

### Full Metrics Report
```javascript
import { getComprehensiveMetrics } from './shared/learning-metrics.js';

const m = getComprehensiveMetrics('opus', 'code-review');

console.log(`
LIS Score: ${m.lis.score.toFixed(1)}/100
Components:
  Quality:      ${m.lis.components.quality.toFixed(0)}
  Cost:         ${m.lis.components.cost.toFixed(0)}
  Speed:        ${m.lis.components.speed.toFixed(0)}
  Consistency:  ${m.lis.components.consistency.toFixed(0)}

Trends:
  Quality:      ${m.qualityTrend?.trend || 'N/A'} (${m.qualityTrend?.improvementPercent.toFixed(2)}%)
  Cost/Quality: $${m.costEfficiency?.costPerQualityPoint.toFixed(4)} (${m.costEfficiency?.trendSlope > 0 ? '↑' : '↓'})
  Speed:        ${m.speedImprovement?.speedImprovement.toFixed(1)}% faster
`);
```

### Monitor During Batch
```javascript
for (let i = 0; i < tasks.length; i++) {
  await processTask(tasks[i]);
  
  if ((i + 1) % 10 === 0) {
    const m = getComprehensiveMetrics('opus', 'analysis');
    const lis = m.lis?.score || 0;
    console.log(`${i + 1}/${tasks.length} - LIS: ${lis.toFixed(1)}/100`);
    
    if (m.qualityTrend?.trend === 'declining') {
      console.warn('Quality declining! Stopping.');
      break;
    }
  }
}
```

### Generate Report
```javascript
const board = getAllMetricsLeaderboard({ minSamples: 10 });

console.log('Top 10 Models by LIS:');
console.table(board.slice(0, 10).map((e, i) => ({
  Rank: i + 1,
  Model: e.model,
  Task: e.taskType,
  LIS: e.lis.score.toFixed(1),
  Trend: e.qualityTrend?.trend || '-',
  Samples: e.lis.sampleCount,
})));
```

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| Metrics null | Minimum samples not met (need ≥10) |
| All scores low | Quality scores <0.5 or cost very high |
| Missing trend | Not enough time split data (30+ days) |
| High variance | Inconsistent execution (CV > 0.5) |

---

## Key Insight

**LIS = 100** means:
- ✓ Top percentile quality
- ✓ Low cost relative to quality
- ✓ Fast execution
- ✓ Consistent performance
- ✓ Showing improvement

**LIS < 60** means:
- Review model selection
- Check for regressions
- Consider different approach
- Increase samples for accuracy

---

Last Updated: 2026-06-13
