# LIS Dashboard Integration Guide

Quick guide for integrating LIS tracking into workflows and scripts.

## Quick Start

### 1. View Current Dashboard

```bash
./scripts/learning-dashboard.sh
```

### 2. Monitor Specific Model

```bash
./scripts/learning-dashboard.sh --model opus --task code_review
```

### 3. Export Data for Analysis

```bash
./scripts/learning-dashboard.sh --json > lis-snapshot.json
```

## Workflow Integration

### Basic Pattern

```javascript
import { computeLIS, recomputeModelPerformance } from './learning/calculate-lis.js';
import { logExecution } from './learning/db.js';

export default {
  meta: {
    name: 'my-workflow',
    version: '1.0.0'
  },

  async run(args) {
    const startTime = Date.now();
    
    try {
      // Your workflow logic here
      const result = await doWork(args);
      
      // Log execution with quality metrics
      logExecution({
        model: 'opus',
        task_type: 'my_workflow',
        quality_score: result.quality || 0.8,
        cost_usd: result.cost || 0.0,
        duration_ms: Date.now() - startTime,
        outcome: 'success'
      });
      
      return result;
      
    } catch (error) {
      // Log failure
      logExecution({
        model: 'opus',
        task_type: 'my_workflow',
        quality_score: 0,
        duration_ms: Date.now() - startTime,
        outcome: 'failed',
        error_message: error.message
      });
      
      throw error;
    }
  }
};
```

### Multi-Model Consensus Pattern

```javascript
import { computeLIS } from './learning/calculate-lis.js';
import { logExecution } from './learning/db.js';

async function runConsensus(taskType, workers, arbiter) {
  const results = [];
  
  // Run workers
  for (const worker of workers) {
    const startTime = Date.now();
    const result = await worker.execute();
    
    logExecution({
      model: worker.model,
      model_role: 'worker',
      task_type: taskType,
      quality_score: result.confidence,
      cost_usd: result.cost,
      duration_ms: Date.now() - startTime,
      outcome: 'success',
      consensus_score: null, // Filled by arbiter
      was_selected: null     // Filled by arbiter
    });
    
    results.push(result);
  }
  
  // Arbiter selection
  const startTime = Date.now();
  const selected = await arbiter.select(results);
  
  logExecution({
    model: arbiter.model,
    model_role: 'arbiter',
    task_type: taskType,
    quality_score: selected.confidence,
    cost_usd: selected.cost,
    duration_ms: Date.now() - startTime,
    outcome: 'success'
  });
  
  // Update worker logs with selection results
  for (let i = 0; i < results.length; i++) {
    // Update execution log with was_selected and consensus_score
    // (implementation depends on your database update mechanism)
  }
  
  return selected;
}
```

### Periodic Recomputation

```javascript
import { recomputeModelPerformance } from './learning/calculate-lis.js';

// In your background task or cron job
async function periodicUpdate() {
  const result = recomputeModelPerformance({
    minSamples: 3
  });
  
  console.log(`Updated ${result.modelsUpdated} models`);
  console.log(`Computed ${result.windowsComputed} time windows`);
}

// Run every 5 minutes
setInterval(periodicUpdate, 5 * 60 * 1000);
```

## Shell Script Integration

### Before Workflow Execution

```bash
#!/usr/bin/env bash

# Show current LIS before making changes
echo "Current LIS scores:"
./scripts/learning-dashboard.sh --compact

# Run your workflow
./my-workflow.sh

# Show updated LIS
echo "Updated LIS scores:"
./scripts/learning-dashboard.sh --compact
```

### Monitoring Loop

```bash
#!/usr/bin/env bash

while true; do
  clear
  ./scripts/learning-dashboard.sh --compact
  sleep 60
done
```

### Conditional Execution

```bash
#!/usr/bin/env bash

# Get current LIS as JSON
LIS_DATA=$(./scripts/learning-dashboard.sh --json)

# Parse specific model's score
OPUS_SCORE=$(echo "$LIS_DATA" | jq -r '.leaderboard[] | select(.model == "opus" and .taskType == "code_review") | .lis.score')

if (( $(echo "$OPUS_SCORE < 70" | bc -l) )); then
  echo "⚠️  Opus performance degraded: $OPUS_SCORE"
  echo "Running optimization workflow..."
  ./workflows/optimize-model.sh opus
fi
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Learning Metrics

on:
  workflow_run:
    workflows: ["Main CI"]
    types: [completed]

jobs:
  update-metrics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Update LIS Dashboard
        run: |
          ./scripts/learning-dashboard.sh --json > lis-metrics.json
          
      - name: Check for Regressions
        run: |
          GLOBAL_LIS=$(jq -r '.globalLIS.score' lis-metrics.json)
          echo "Global LIS: $GLOBAL_LIS"
          
          if (( $(echo "$GLOBAL_LIS < 60" | bc -l) )); then
            echo "::error::LIS regression detected: $GLOBAL_LIS < 60"
            exit 1
          fi
          
      - name: Archive Metrics
        uses: actions/upload-artifact@v3
        with:
          name: lis-metrics
          path: lis-metrics.json
```

### GitLab CI

```yaml
learning-metrics:
  stage: report
  script:
    - ./scripts/learning-dashboard.sh --json > lis-metrics.json
    - GLOBAL_LIS=$(jq -r '.globalLIS.score' lis-metrics.json)
    - echo "Global LIS - $GLOBAL_LIS"
    - |
      if [ $(echo "$GLOBAL_LIS < 60" | bc) -eq 1 ]; then
        echo "LIS regression detected"
        exit 1
      fi
  artifacts:
    reports:
      metrics: lis-metrics.json
    paths:
      - lis-metrics.json
```

## Grafana Integration

### Export Prometheus Metrics

```bash
#!/usr/bin/env bash
# export-lis-metrics.sh

METRICS_FILE="/var/lib/node_exporter/textfile_collector/lis_metrics.prom"

# Get current LIS data
LIS_DATA=$(./scripts/learning-dashboard.sh --json)

# Convert to Prometheus format
echo "# HELP lis_score Learning Intelligence Score (0-100)" > "$METRICS_FILE"
echo "# TYPE lis_score gauge" >> "$METRICS_FILE"

echo "$LIS_DATA" | jq -r '.leaderboard[] | 
  "lis_score{model=\"\(.model)\",task=\"\(.taskType)\"} \(.lis.score)"' \
  >> "$METRICS_FILE"

echo "# HELP lis_quality_score Quality component score (0-100)" >> "$METRICS_FILE"
echo "# TYPE lis_quality_score gauge" >> "$METRICS_FILE"

echo "$LIS_DATA" | jq -r '.leaderboard[] | 
  "lis_quality_score{model=\"\(.model)\",task=\"\(.taskType)\"} \(.lis.components.quality)"' \
  >> "$METRICS_FILE"

# Similar for cost, speed, consistency...
```

### Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "Learning Intelligence Score",
    "panels": [
      {
        "title": "Global LIS Trend",
        "targets": [
          {
            "expr": "avg(lis_score)",
            "legendFormat": "Global LIS"
          }
        ]
      },
      {
        "title": "LIS by Model",
        "targets": [
          {
            "expr": "lis_score",
            "legendFormat": "{{model}} - {{task}}"
          }
        ]
      }
    ]
  }
}
```

## Alerting Rules

### Prometheus AlertManager

```yaml
groups:
  - name: learning_intelligence
    interval: 5m
    rules:
      - alert: LISRegression
        expr: avg(lis_score) < 60
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "LIS score below threshold"
          description: "Global LIS is {{ $value }}, below 60"
      
      - alert: QualityDegradation
        expr: avg(lis_quality_score) < 70
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Quality score degraded"
          description: "Quality component at {{ $value }}"
```

### Custom Shell Alert

```bash
#!/usr/bin/env bash
# lis-monitor.sh

THRESHOLD=60
LIS_SCORE=$(./scripts/learning-dashboard.sh --json | jq -r '.globalLIS.score')

if (( $(echo "$LIS_SCORE < $THRESHOLD" | bc -l) )); then
  # Send alert (email, Slack, PagerDuty, etc.)
  curl -X POST https://hooks.slack.com/... \
    -H 'Content-Type: application/json' \
    -d "{\"text\": \"⚠️ LIS Alert: Score dropped to $LIS_SCORE\"}"
fi
```

## Data Export Formats

### CSV Export

```bash
./scripts/learning-dashboard.sh --json | \
  jq -r '.leaderboard[] | [.model, .taskType, .lis.score, .lis.components.quality, .lis.components.cost, .lis.components.speed] | @csv' \
  > lis-export.csv
```

### Excel-Ready Format

```bash
./scripts/learning-dashboard.sh --json | \
  jq -r '["Model","Task","LIS","Quality","Cost","Speed"], 
         (.leaderboard[] | [.model, .taskType, .lis.score, .lis.components.quality, .lis.components.cost, .lis.components.speed]) | 
         @tsv' \
  > lis-export.tsv
```

### HTML Report

```bash
#!/usr/bin/env bash

cat > lis-report.html <<EOF
<!DOCTYPE html>
<html>
<head>
  <title>LIS Report</title>
  <style>
    body { font-family: sans-serif; margin: 2em; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #4CAF50; color: white; }
  </style>
</head>
<body>
  <h1>Learning Intelligence Score Report</h1>
  <p>Generated: $(date)</p>
  
  <h2>Leaderboard</h2>
  <table>
    <tr>
      <th>Model</th>
      <th>Task</th>
      <th>LIS</th>
      <th>Quality</th>
      <th>Cost</th>
      <th>Speed</th>
    </tr>
EOF

./scripts/learning-dashboard.sh --json | \
  jq -r '.leaderboard[] | 
    "<tr><td>\(.model)</td><td>\(.taskType)</td><td>\(.lis.score)</td><td>\(.lis.components.quality)</td><td>\(.lis.components.cost)</td><td>\(.lis.components.speed)</td></tr>"' \
  >> lis-report.html

cat >> lis-report.html <<EOF
  </table>
</body>
</html>
EOF

echo "Report generated: lis-report.html"
```

## Best Practices

### 1. Log Every Execution
```javascript
// Always log, even on failure
try {
  const result = await execute();
  logExecution({ outcome: 'success', quality_score: result.quality });
} catch (error) {
  logExecution({ outcome: 'failed', quality_score: 0 });
  throw error;
}
```

### 2. Use Consistent Task Types
```javascript
// Good - consistent naming
logExecution({ task_type: 'code_review' });
logExecution({ task_type: 'code_review' });

// Bad - inconsistent
logExecution({ task_type: 'code_review' });
logExecution({ task_type: 'code-review' });
logExecution({ task_type: 'CodeReview' });
```

### 3. Track Model Roles
```javascript
// Worker execution
logExecution({ model: 'opus', model_role: 'worker' });

// Arbiter execution
logExecution({ model: 'fable', model_role: 'arbiter' });
```

### 4. Include Quality Metrics
```javascript
// Good - meaningful quality score
logExecution({ 
  quality_score: result.testsPass / result.testsTotal,
  confidence: result.confidence
});

// Avoid - arbitrary score
logExecution({ quality_score: 0.8 }); // Why 0.8?
```

### 5. Periodic Dashboard Reviews
```bash
# Daily cron job
0 9 * * * /path/to/scripts/learning-dashboard.sh --export /var/reports/lis-$(date +\%Y\%m\%d).json
```

## Troubleshooting

### Issue: "No data for model/task"
**Solution:** Check minimum sample requirements
```bash
# Reduce minimum samples for testing
# In calculate-lis.js: computeLIS(model, task, { minSamples: 3 })
```

### Issue: "LIS score seems wrong"
**Solution:** Verify component scores individually
```bash
./scripts/learning-dashboard.sh --model opus --task code_review
# Check each component: quality, cost, speed, consistency
```

### Issue: "Trend not showing improvement"
**Solution:** Need more time-separated data
```bash
# Trends require data spread over time
# Run workflows over several days for meaningful trends
```

### Issue: "Dashboard slow to load"
**Solution:** Use compact mode or filters
```bash
./scripts/learning-dashboard.sh --compact --model opus
```

## Examples

See `/scripts/test-lis-dashboard.sh` for complete working examples.

## References

- Main documentation: `/docs/lis-dashboard.md`
- Core implementation: `/learning/calculate-lis.js`
- Database schema: `/learning/init-db.sql`
- Dashboard script: `/scripts/learning-dashboard.sh`
