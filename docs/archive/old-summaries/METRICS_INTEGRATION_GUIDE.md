# Learning Metrics Integration Guide

Complete guide for integrating the learning metrics system into workflows and dashboards.

## Quick Start

### 1. Import the Metrics Module

```javascript
import {
  calculateLIS,
  calculateQualityTrend,
  calculateCostEfficiency,
  calculateSpeedImprovement,
  getComprehensiveMetrics,
  getAllMetricsLeaderboard,
  getModelCombinationMetrics,
} from './shared/learning-metrics.js';
```

### 2. Calculate All Metrics for a Model

```javascript
// Get comprehensive metrics for opus on code-review tasks
const metrics = getComprehensiveMetrics('opus', 'code-review');

console.log('Learning Metrics for opus/code-review:');
console.log(`LIS Score: ${metrics.lis.score.toFixed(1)}/100`);
console.log(`  Quality: ${metrics.lis.components.quality.toFixed(0)}`);
console.log(`  Cost: ${metrics.lis.components.cost.toFixed(0)}`);
console.log(`  Speed: ${metrics.lis.components.speed.toFixed(0)}`);
console.log(`  Consistency: ${metrics.lis.components.consistency.toFixed(0)}`);

if (metrics.qualityTrend) {
  console.log(`Quality Trend: ${metrics.qualityTrend.trend}`);
  console.log(`  Improvement: ${metrics.qualityTrend.improvementPercent.toFixed(2)}%`);
  console.log(`  Confidence: ${(metrics.qualityTrend.confidence * 100).toFixed(1)}%`);
}

if (metrics.costEfficiency) {
  console.log(`Cost Per Quality Point: $${metrics.costEfficiency.costPerQualityPoint.toFixed(4)}`);
  console.log(`  Percentile: ${(metrics.costEfficiency.percentileRank * 100).toFixed(0)}th`);
}

if (metrics.speedImprovement) {
  console.log(`Speed Improvement: ${metrics.speedImprovement.speedImprovement.toFixed(1)}%`);
  console.log(`  Faster Runs: ${metrics.speedImprovement.percentageImprovedRuns.toFixed(0)}%`);
}
```

### 3. View Leaderboard

```javascript
const board = getAllMetricsLeaderboard({ minSamples: 10 });

console.log('Model Leaderboard (Top 10):');
board.slice(0, 10).forEach((entry, idx) => {
  const lis = entry.lis;
  console.log(`${idx + 1}. ${entry.model.padEnd(12)} ${entry.taskType.padEnd(20)} LIS: ${lis.score.toFixed(1)}`);
});
```

---

## Integration Examples

### Integration with Workflow Execution

Add metrics tracking to your workflows:

```javascript
// In your workflow
import { logExecution } from './shared/learning-logger.js';
import { getComprehensiveMetrics } from './shared/learning-metrics.js';

export const meta = {
  name: 'code-solve',
  timeout: 300000,
}

export async function workflow(context, { agent, log }) {
  const startTime = Date.now();
  
  // Solve the issue...
  const solution = await agent('Solve the issue...', {
    label: 'code-solve',
    model: 'opus',
    schema: SOLUTION_SCHEMA,
  });

  // Log execution with metrics
  logExecution({
    model: 'opus',
    workflow: 'code-solve',
    task_type: 'bug_fix',
    quality_score: solution.quality || 0.85,  // Rate the solution quality
    confidence: solution.confidence || 0.90,
    input_tokens: solution.usage?.input_tokens || 0,
    output_tokens: solution.usage?.output_tokens || 0,
    cost_usd: calculateCost(solution.usage),
    duration_ms: Date.now() - startTime,
    outcome: solution.successful ? 'success' : 'partial',
    parameters: { temperature: 0.7, max_tokens: 2000 },
  });

  // Check if metrics are improving
  const metrics = getComprehensiveMetrics('opus', 'bug_fix');
  if (metrics.lis && metrics.lis.score < 60) {
    log('⚠ Warning: LIS score is low. Model may need tuning.');
  }

  return solution;
}
```

### Add Metrics Summary to Workflow Output

```javascript
// After main workflow logic
if (finalResult) {
  const metrics = getComprehensiveMetrics(model, taskType);
  
  if (metrics.lis) {
    const summary = `
📊 Metrics Summary:
  LIS Score: ${metrics.lis.score.toFixed(1)}/100
  Trend: ${metrics.qualityTrend?.trend || 'unknown'}
  Efficiency: ${metrics.costEfficiency?.costEfficiencyScore.toFixed(0)}/100
  Speed Gain: ${metrics.speedImprovement?.speedImprovement.toFixed(1)}%
    `;
    log(summary);
  }
}
```

### Real-Time Monitoring in Batch Operations

```javascript
// Monitor metrics during batch processing
import { getComprehensiveMetrics } from './shared/learning-metrics.js';

async function processBatchWithMonitoring(tasks) {
  const results = [];
  
  for (const task of tasks) {
    const result = await processTask(task);
    results.push(result);
    
    // Check metrics every 10 tasks
    if (results.length % 10 === 0) {
      const metrics = getComprehensiveMetrics('opus', 'batch_task');
      if (metrics.qualityTrend?.trend === 'declining') {
        console.warn('⚠ Quality declining! Pausing batch.');
        break;
      }
      console.log(`Progress: ${results.length}/${tasks.length}, LIS: ${metrics.lis?.score.toFixed(1)}`);
    }
  }
  
  return results;
}
```

---

## Dashboard Queries

### Build a Metrics Dashboard

```javascript
export async function getMetricsDashboard() {
  // Get leaderboard
  const leaderboard = getAllMetricsLeaderboard({ minSamples: 10 });
  
  // Get synergy analysis
  const synergies = getModelCombinationMetrics({ minSamples: 3 });
  
  return {
    timestamp: new Date().toISOString(),
    leaderboard: leaderboard.map(entry => ({
      rank: leaderboard.indexOf(entry) + 1,
      model: entry.model,
      taskType: entry.taskType,
      lis: entry.lis.score.toFixed(1),
      quality: entry.lis.components.quality.toFixed(0),
      cost: entry.lis.components.cost.toFixed(0),
      trend: entry.qualityTrend?.trend || 'unknown',
    })),
    topCombinations: synergies
      .filter(s => s.synergy > 0.05)
      .slice(0, 5)
      .map(s => ({
        workers: s.workers.join('+'),
        quality: s.avgQuality.toFixed(3),
        synergy: (s.synergy * 100).toFixed(1) + '%',
      })),
    regressions: detectRegressions(),
  };
}

function detectRegressions() {
  const board = getAllMetricsLeaderboard();
  const regressions = [];
  
  for (const entry of board) {
    if (entry.qualityTrend?.trend === 'declining' && 
        entry.qualityTrend.confidence > 0.90) {
      regressions.push({
        model: entry.model,
        taskType: entry.taskType,
        decline: entry.qualityTrend.improvementPercent.toFixed(2) + '%',
        severity: Math.abs(entry.qualityTrend.improvementPercent) > 10 ? 'HIGH' : 'MEDIUM',
      });
    }
  }
  
  return regressions.sort((a, b) => 
    Math.abs(parseFloat(b.decline)) - Math.abs(parseFloat(a.decline))
  );
}
```

### Display Metrics in Console

```javascript
export function displayMetricsTable() {
  const board = getAllMetricsLeaderboard({ minSamples: 10 });
  
  console.table(board.slice(0, 20).map(entry => ({
    Model: entry.model,
    Task: entry.taskType,
    LIS: entry.lis.score.toFixed(1),
    Quality: entry.lis.components.quality.toFixed(0),
    Cost: entry.lis.components.cost.toFixed(0),
    Speed: entry.lis.components.speed.toFixed(0),
    Consistency: entry.lis.components.consistency.toFixed(0),
    Trend: entry.qualityTrend?.trend || '—',
    Samples: entry.lis.sampleCount,
  })));
}
```

---

## Alerting System

### Quality Regression Alert

```javascript
export function checkQualityRegression(model, taskType, threshold = -5) {
  const trend = calculateQualityTrend(model, taskType);
  
  if (!trend) return null;
  
  if (trend.trend === 'declining' && 
      trend.improvementPercent < threshold &&
      trend.confidence > 0.90) {
    return {
      severity: 'HIGH',
      message: `Quality regression: ${trend.improvementPercent.toFixed(2)}% decline`,
      model,
      taskType,
      confidence: trend.confidence,
      recommendation: 'Review recent changes or reduce model complexity',
    };
  }
  
  return null;
}
```

### Cost Efficiency Alert

```javascript
export function checkCostInefficiency(model, taskType, threshold = 5) {
  const efficiency = calculateCostEfficiency(model, taskType);
  
  if (!efficiency) return null;
  
  if (efficiency.trendSlope > 0 && efficiency.trendR2 > 0.5) {
    const percentChange = (efficiency.trendSlope / efficiency.costPerQualityPoint) * 100;
    if (percentChange > threshold) {
      return {
        severity: 'MEDIUM',
        message: `Cost efficiency declining: cost per quality +${percentChange.toFixed(1)}%`,
        model,
        taskType,
        recommendation: 'Reduce token usage or optimize prompt',
      };
    }
  }
  
  return null;
}
```

### Speed Regression Alert

```javascript
export function checkSpeedRegression(model, taskType, threshold = -5) {
  const speed = calculateSpeedImprovement(model, taskType);
  
  if (!speed) return null;
  
  if (speed.speedImprovement < threshold && 
      speed.percentageImprovedRuns < 40) {
    return {
      severity: 'LOW',
      message: `Speed regression: ${speed.speedImprovement.toFixed(1)}% slower`,
      model,
      taskType,
      recommendation: 'Check infrastructure load or reduce output complexity',
    };
  }
  
  return null;
}
```

### Run All Alerts

```javascript
export function runMetricsAlerts() {
  const board = getAllMetricsLeaderboard({ minSamples: 10 });
  const alerts = [];
  
  for (const entry of board) {
    const qualityAlert = checkQualityRegression(entry.model, entry.taskType);
    if (qualityAlert) alerts.push(qualityAlert);
    
    const costAlert = checkCostInefficiency(entry.model, entry.taskType);
    if (costAlert) alerts.push(costAlert);
    
    const speedAlert = checkSpeedRegression(entry.model, entry.taskType);
    if (speedAlert) alerts.push(speedAlert);
  }
  
  return alerts.sort((a, b) => {
    const severity = { HIGH: 3, MEDIUM: 2, LOW: 1 };
    return severity[b.severity] - severity[a.severity];
  });
}
```

---

## Data Logging Best Practices

### When to Log Execution

Always log when:
1. An AI model is called via `agent()`
2. A consensus workflow completes
3. A model combination is used

```javascript
// ✓ DO: Log after execution completes
const result = await agent(prompt, { model: 'opus' });
const endTime = Date.now();

logExecution({
  model: 'opus',
  task_type: 'analysis',
  quality_score: evaluateQuality(result),
  confidence: result.confidence || 0.5,
  duration_ms: endTime - startTime,
  input_tokens: result.usage?.input_tokens || 0,
  output_tokens: result.usage?.output_tokens || 0,
  cost_usd: estimateCost(result.usage),
  outcome: isValid(result) ? 'success' : 'failed',
});
```

### Quality Score Guidelines

Assign quality scores based on task type:

**Code Review**: 
- 0.9-1.0: Found all/most issues, correct analysis
- 0.7-0.9: Found major issues, some analysis errors
- 0.5-0.7: Found some issues, significant errors
- 0.0-0.5: Missed major issues, poor analysis

**Bug Fix**:
- 0.9-1.0: Fix works, tests pass, no regressions
- 0.7-0.9: Fix works, tests mostly pass
- 0.5-0.7: Partial fix, some tests fail
- 0.0-0.5: Fix doesn't work

**Architecture**:
- 0.9-1.0: Sound design, well-reasoned, implementable
- 0.7-0.9: Good design, mostly implementable
- 0.5-0.7: Acceptable design, some concerns
- 0.0-0.5: Flawed design, major concerns

### Batch Logging

Log multiple executions efficiently:

```javascript
import { logExecutionBatch } from './shared/learning-logger.js';

// Collect batch of results
const batch = results.map(r => ({
  model: 'opus',
  task_type: 'analysis',
  quality_score: r.quality,
  cost_usd: r.cost,
  duration_ms: r.duration,
  outcome: r.success ? 'success' : 'failed',
}));

// Log all at once (faster than individual inserts)
const ids = logExecutionBatch(batch);
console.log(`Logged ${ids.length} executions`);
```

---

## Query Examples

### Find Best Model for a Task

```javascript
import { getDb } from './shared/learning-logger.js';

function getBestModelForTask(taskType) {
  const db = getDb();
  if (!db) return null;
  
  const result = db.prepare(`
    SELECT
      model,
      AVG(quality_score) as avg_quality,
      AVG(cost_usd) as avg_cost,
      COUNT(*) as samples
    FROM execution_log
    WHERE task_type = ? AND quality_score IS NOT NULL
    GROUP BY model
    HAVING COUNT(*) >= 5
    ORDER BY AVG(quality_score) DESC
    LIMIT 1
  `).get(taskType);
  
  return result;
}
```

### Find Cost-Optimal Model

```javascript
function getCostOptimalModel(taskType, minQuality = 0.80) {
  const db = getDb();
  if (!db) return null;
  
  const result = db.prepare(`
    SELECT
      model,
      AVG(quality_score) as avg_quality,
      AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality,
      COUNT(*) as samples
    FROM execution_log
    WHERE task_type = ? 
      AND quality_score IS NOT NULL
      AND AVG(quality_score) >= ?
    GROUP BY model
    HAVING COUNT(*) >= 5
    ORDER BY AVG(cost_usd / NULLIF(quality_score, 0)) ASC
    LIMIT 1
  `).get(taskType, minQuality);
  
  return result;
}
```

### Get Performance Percentiles

```javascript
function getModelPercentiles(model, taskType) {
  const db = getDb();
  if (!db) return null;
  
  return db.prepare(`
    SELECT
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY quality_score) as p25_quality,
      PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY quality_score) as p50_quality,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY quality_score) as p75_quality,
      PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY quality_score) as p90_quality,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY cost_usd) as p25_cost,
      PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY cost_usd) as p50_cost,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY cost_usd) as p75_cost,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_ms) as p25_speed,
      PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50_speed,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_ms) as p75_speed
    FROM execution_log
    WHERE model = ? AND task_type = ? AND quality_score IS NOT NULL
  `).get(model, taskType);
}
```

---

## Performance Tuning

### Optimize Queries

For large datasets (>100k executions), use indexes:

```sql
-- Add these indexes for faster metrics queries
CREATE INDEX idx_metrics_model_task_time 
  ON execution_log(model, task_type, timestamp);
  
CREATE INDEX idx_metrics_quality 
  ON execution_log(quality_score) 
  WHERE quality_score IS NOT NULL;
  
CREATE INDEX idx_metrics_cost 
  ON execution_log(cost_usd) 
  WHERE cost_usd > 0;
```

### Cache Metrics

For production use, cache metric calculations:

```javascript
const MetricsCache = {
  store: new Map(),
  ttl: 3600000, // 1 hour
  
  get(key) {
    const entry = this.store.get(key);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > this.ttl) {
      this.store.delete(key);
      return null;
    }
    return entry.value;
  },
  
  set(key, value) {
    this.store.set(key, { value, timestamp: Date.now() });
  },
  
  clear() {
    this.store.clear();
  }
};

// Usage
function getLISCached(model, taskType) {
  const key = `lis:${model}:${taskType}`;
  const cached = MetricsCache.get(key);
  if (cached) return cached;
  
  const value = calculateLIS(model, taskType);
  if (value) MetricsCache.set(key, value);
  return value;
}
```

---

## Troubleshooting

### Metrics Not Updating

1. Check execution logs are being recorded:
```javascript
import { getExecutionCount } from './shared/learning-logger.js';
const count = getExecutionCount();
console.log(`Total executions logged: ${count}`);
```

2. Verify min sample requirements:
```javascript
const stats = getModelTaskStats('opus', 'code-review');
if (!stats) {
  console.log('Not enough samples yet');
} else {
  console.log(`Samples: ${stats.sample_count}`);
}
```

3. Check database connection:
```javascript
import { getDb, isAvailable } from './shared/learning-logger.js';
if (!isAvailable()) {
  console.error('Database unavailable - check file permissions');
}
```

### Metrics Showing Unexpected Values

1. Verify quality scores are 0-1:
```javascript
const recent = getRecentExecutions(10);
recent.forEach(e => {
  if (e.quality_score < 0 || e.quality_score > 1) {
    console.warn(`Invalid quality score: ${e.quality_score}`);
  }
});
```

2. Check for outliers:
```javascript
const trend = calculateQualityTrend('opus', 'code-review');
if (trend.stdDev > 0.3) {
  console.warn('High variance in quality scores - check for outliers');
}
```

---

## References

- **Database Schema**: `/shared/learning-logger.js` (lines 27-201)
- **Metrics Implementation**: `/shared/learning-metrics.js`
- **SQL Queries**: `/shared/learning-metrics-queries.sql`
- **Formula Reference**: `LEARNING_METRICS_DESIGN.md`
