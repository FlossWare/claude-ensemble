# Autonomous Learning System - Real-Time Transparency Dashboard

Complete visibility into everything the autonomous AI learning system is doing, deciding, and learning.

## Overview

The transparency dashboard provides **full auditability** of the autonomous learning system with two interfaces:

1. **Grafana Dashboard** - Web-based, full-featured monitoring with historical data
2. **CLI Dashboard** - Terminal-based, real-time monitoring for command-line users

## What You Can See

### 1. Real-Time Activity (What's Happening NOW)
- **Active executions**: Which AI models are working on what tasks right now
- **Fleet distribution**: Which servers are doing what work
- **Workflow pipeline**: Live view of workflow stages and dependencies
- **Current load**: Execution rate, active workflows, fleet utilization

### 2. Decision Transparency (HOW & WHY)
- **Autonomous decisions**: All decisions made by the system with rationale
- **Model selection**: Why each model was chosen for each task
- **Strategy selection**: Which consensus/workflow strategy was used and why
- **Parameter choices**: All configuration decisions logged with context

### 3. Fleet Activity (WHO & WHERE)
- **Fleet activity map**: Which AI on which server solving which task
- **Work distribution**: How work is balanced across fleet nodes
- **Server workload**: CPU, memory, network usage per server
- **Model assignments**: Which models are running on which servers

### 4. Learning Progress (WHAT'S BEING LEARNED)
- **Learning Intelligence Score (LIS)**: 0-100 aggregate improvement metric
- **Quality trends**: Statistical improvement over time
- **Cost efficiency**: Cost per quality point trending
- **Speed improvements**: Execution time reduction tracking
- **Discovery timeline**: What was learned when

### 5. Model Performance (WHO'S BEST AT WHAT)
- **Model comparison**: Which models excel at which tasks
- **Combination synergy**: Which model combinations work best together
- **Prompt patterns**: Which prompt strategies work best per model
- **Performance leaderboard**: Rankings by LIS, quality, cost, speed

### 6. Issues & Quality (WHAT WENT WRONG)
- **Issue tracker**: Open/closed/in-progress issues
- **Failure analysis**: Why executions failed
- **Anomaly detection**: Performance degradation alerts
- **Quality regressions**: When quality drops below baseline

### 7. Cost Tracking (HOW MUCH)
- **Real-time spend**: Current burn rate
- **Cost per model**: Which models cost most/least
- **Cost efficiency**: Cost per quality point
- **Budget tracking**: Session and workflow budget status

### 8. Historical Trends (OVER TIME)
- **Quality improvements**: Before/after learning curves
- **Cost optimization**: Cost reduction over time
- **Speed improvements**: Latency reduction trends
- **Model evolution**: How each model improves over time

### 9. Research Activity (WHAT'S BEING RESEARCHED)
- **Learning sessions**: Active research workflows
- **Web research**: What's being fetched and why
- **Code analysis**: What code is being studied
- **PDF analysis**: Which documents are being verified

### 10. Complete Audit Trail (EVERYTHING)
- **Full execution log**: Every execution with full context
- **Parameter tracking**: All parameters for every execution
- **Input/output hashes**: Reproducibility tracking
- **Timestamp precision**: Microsecond-level timing
- **Error tracking**: Full error messages and stack traces

## Setup

### Prerequisites

```bash
# Install dependencies
npm install better-sqlite3 blessed blessed-contrib

# Initialize learning database
sqlite3 ~/.claude/learning/db/learning.db < ~/.claude/learning/init-learning-db.sql

# (Optional) Install Grafana + Prometheus for web dashboard
# See: monitoring/deploy-fleet-prometheus.js
```

### Grafana Dashboard (Web UI)

```bash
# 1. Import the dashboard configuration
grafana-cli admin import-dashboard monitoring/autonomous-transparency-dashboard.json

# 2. Configure data sources:
#    - Prometheus: For system metrics (CPU, memory, network)
#    - SQLite: For learning database (execution log, tuning, combinations)

# 3. Access at: http://localhost:3000/d/autonomous-transparency
```

**Panels included:**
- 🔴 Live system status
- 🗺️ Fleet activity map
- 🤖 Active AI workers
- 🧠 Autonomous decisions
- 📊 Learning Intelligence Score (LIS)
- 💰 Cost tracking
- 🎯 Model performance
- 🔍 Issue tracker
- 📚 Learning sessions
- 📈 Quality trends
- ⚡ Discovery timeline
- 🏆 Model combinations
- 🚨 Anomaly detection
- 🔐 Full audit trail

### CLI Dashboard (Terminal UI)

```bash
# Run the CLI dashboard
node monitoring/transparency-dashboard-cli.js

# Options:
node monitoring/transparency-dashboard-cli.js --refresh 10     # 10-second refresh
node monitoring/transparency-dashboard-cli.js --compact        # Compact mode
node monitoring/transparency-dashboard-cli.js --export data.json  # Export data

# Keyboard shortcuts:
#   r      - Refresh dashboard
#   h / ?  - Show help
#   q / ESC - Quit
```

**CLI Views:**
- 🔴 Status bar (live activity summary)
- 🗺️ Fleet activity map (last 5 minutes)
- ⚙️ Active workflows
- 🧠 Learning Intelligence Score gauge
- 🎯 Model performance bar chart
- 💰 Cost distribution donut
- 📈 Quality trend line graph
- 🧠 Autonomous decisions log
- 🔍 Issue tracker table

## Data Sources

### SQLite Learning Database
**Location:** `~/.claude/learning/db/learning.db`

**Tables:**
- `execution_log` - Every execution with full context
- `model_tuning` - Model performance tuning data
- `prompt_patterns` - Prompt strategy effectiveness
- `model_combinations` - Multi-model synergy data
- `learning_metadata` - System metadata

### Prometheus Metrics
**Endpoint:** `http://localhost:9090`

**Metrics:**
- `learning_executions_total` - Total executions (counter)
- `learning_active_workflows` - Active workflows (gauge)
- `learning_lis_score` - Learning Intelligence Score (gauge)
- `fleet_active_nodes` - Active fleet nodes (gauge)
- `learning_quality_score` - Quality scores (histogram)
- `learning_cost_usd` - Costs (histogram)
- `learning_duration_ms` - Execution time (histogram)

## Query Examples

### SQLite Queries

```sql
-- Get recent executions (last hour)
SELECT timestamp, model, workflow, task_type, outcome
FROM execution_log
WHERE timestamp > datetime('now', '-1 hour')
ORDER BY timestamp DESC;

-- Model performance summary
SELECT model, task_type,
       AVG(quality_score) as avg_quality,
       AVG(cost_usd) as avg_cost,
       COUNT(*) as count
FROM execution_log
WHERE quality_score IS NOT NULL
GROUP BY model, task_type
ORDER BY avg_quality DESC;

-- Anomaly detection (quality outliers)
WITH stats AS (
  SELECT model, AVG(quality_score) as avg_q, STDDEV(quality_score) as stddev_q
  FROM execution_log WHERE quality_score IS NOT NULL
  GROUP BY model
)
SELECT e.*, (e.quality_score - s.avg_q) / s.stddev_q as z_score
FROM execution_log e
JOIN stats s ON e.model = s.model
WHERE ABS((e.quality_score - s.avg_q) / s.stddev_q) > 2.5
ORDER BY z_score DESC;

-- Cost efficiency trend
SELECT DATE(timestamp) as date,
       model,
       AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality
FROM execution_log
WHERE quality_score > 0
GROUP BY DATE(timestamp), model
ORDER BY date DESC;
```

### Prometheus Queries

```promql
# Executions per minute
rate(learning_executions_total[1m])

# Average quality by model
avg by (model) (learning_quality_score)

# P95 latency
histogram_quantile(0.95, learning_duration_ms)

# Cost rate ($/hour)
rate(learning_cost_usd[1h]) * 3600

# Fleet utilization
sum(fleet_active_nodes) / sum(fleet_total_nodes)
```

## Custom Views

### Create Custom Grafana Panels

1. Add a new panel
2. Select data source (SQLite or Prometheus)
3. Write query (see examples above)
4. Choose visualization type
5. Configure thresholds, colors, formatting
6. Save dashboard

### Extend CLI Dashboard

```javascript
// Add a new component to transparency-dashboard-cli.js

const customWidget = grid.set(row, col, height, width, contrib.table, {
  label: 'Custom View',
  border: { type: 'line', fg: 'cyan' },
});

async function updateCustomWidget(data) {
  // Fetch custom data
  const customData = db.prepare('SELECT ...').all();
  
  // Format for widget
  customWidget.setData({
    headers: ['Col1', 'Col2'],
    data: customData.map(row => [row.col1, row.col2]),
  });
}
```

## Export & Reporting

### Export Dashboard Data

```bash
# Export to JSON
node monitoring/transparency-dashboard-cli.js --export dashboard-data.json

# Export from SQLite
sqlite3 ~/.claude/learning/db/learning.db <<EOF
.mode json
.output report.json
SELECT * FROM execution_log WHERE timestamp > datetime('now', '-24 hours');
.quit
EOF

# Export from Prometheus
curl 'http://localhost:9090/api/v1/query?query=learning_executions_total' > metrics.json
```

### Generate Reports

```javascript
// Use ai-performance-monitor.js
import { workflow } from './shared/workflow-helpers.js';

const report = await workflow('ai-performance-monitor', {
  action: 'generateReport',
  time_window_hours: 168,  // 1 week
});

console.log(report.report);  // Formatted text report
```

## Alerts & Notifications

### Grafana Alerts

Configure alert rules in Grafana:

```yaml
# Example: Quality degradation alert
alert: QualityDegradation
expr: avg_over_time(learning_quality_score[5m]) < 0.70
for: 10m
labels:
  severity: warning
annotations:
  summary: "Quality score below threshold"
  description: "Average quality: {{ $value }}"
```

### CLI Alerts

The CLI dashboard automatically highlights:
- ❌ Failed executions (red)
- ⚠️ Quality < 0.70 (yellow)
- 💸 Cost > budget (red)
- 🐌 Latency > 5s (yellow)

## Privacy & Security

### What Gets Logged

✅ **Logged:**
- Model names, workflow IDs, task types
- Quality scores, confidence, cost, duration
- Outcomes (success/failure/retry)
- Parameter configurations
- Input/output token counts
- Request/response hashes (for deduplication)

❌ **NOT Logged:**
- Raw input prompts (unless explicitly enabled)
- Raw output responses (unless explicitly enabled)
- User data or sensitive information
- Credentials or API keys

### Access Control

```bash
# Restrict database access
chmod 600 ~/.claude/learning/db/learning.db

# Require authentication for Grafana
# See: Grafana security settings

# Encrypt exports
gpg --encrypt dashboard-data.json
```

## Troubleshooting

### Dashboard Not Updating

```bash
# Check database connection
sqlite3 ~/.claude/learning/db/learning.db "SELECT COUNT(*) FROM execution_log;"

# Check Prometheus
curl http://localhost:9090/-/healthy

# Restart dashboard
pkill -f transparency-dashboard-cli
node monitoring/transparency-dashboard-cli.js
```

### Missing Data

```bash
# Verify logging is enabled
# Check: shared/learning-logger.js

# Test logging
node -e "import('./shared/learning-logger.js').then(m => {
  m.logExecution({
    model: 'test',
    workflow: 'test',
    quality_score: 0.9
  });
  console.log('Logged!');
})"
```

### Performance Issues

```bash
# Vacuum database
sqlite3 ~/.claude/learning/db/learning.db "VACUUM;"

# Clear old data (>30 days)
sqlite3 ~/.claude/learning/db/learning.db "DELETE FROM execution_log WHERE timestamp < datetime('now', '-30 days');"

# Reduce refresh rate
node monitoring/transparency-dashboard-cli.js --refresh 30
```

## Integration with Workflows

All autonomous workflows automatically log to the transparency dashboard via `learning-logger.js`:

```javascript
import { logExecution } from './shared/learning-logger.js';

// In your workflow
const rowId = logExecution({
  model: 'opus',
  workflow: 'code-review',
  task_type: 'security',
  quality_score: 0.92,
  confidence: 0.88,
  input_tokens: 1500,
  output_tokens: 800,
  cost_usd: 0.0825,
  duration_ms: 3200,
  outcome: 'success',
  outcome_notes: 'Autonomous decision: Selected Opus for high-stakes security review',
});
```

Everything logged here appears in **both** dashboards immediately.

## Advanced Features

### Time-Travel Debugging

```sql
-- Replay executions from a specific time
SELECT * FROM execution_log
WHERE timestamp BETWEEN '2026-06-13 10:00:00' AND '2026-06-13 11:00:00'
ORDER BY timestamp;

-- Diff quality before/after a change
SELECT model,
       AVG(CASE WHEN timestamp < '2026-06-13 12:00:00' THEN quality_score END) as before,
       AVG(CASE WHEN timestamp >= '2026-06-13 12:00:00' THEN quality_score END) as after
FROM execution_log
GROUP BY model;
```

### Correlation Analysis

```sql
-- Correlation: quality vs cost
SELECT model,
       CORR(quality_score, cost_usd) as quality_cost_correlation
FROM execution_log
WHERE quality_score IS NOT NULL AND cost_usd > 0
GROUP BY model;
```

### Predictive Alerts

```javascript
// Use learning-metrics.js for trend detection
import { calculateQualityTrend } from './shared/learning-metrics.js';

const trend = calculateQualityTrend('opus', 'security');
if (trend && trend.trend === 'declining' && trend.confidence > 0.95) {
  console.warn(`⚠️ Quality declining for opus:security (p=${trend.pValue})`);
}
```

## Comparison: Grafana vs CLI

| Feature | Grafana | CLI |
|---------|---------|-----|
| **Setup** | Complex (Prometheus + Grafana) | Simple (node + SQLite) |
| **Real-time** | 5-30s refresh | 1-5s refresh |
| **Historical data** | ✅ Full history | ⚠️ Last N points |
| **Interactivity** | ✅ Click, zoom, filter | ⚠️ Keyboard only |
| **Alerting** | ✅ Built-in | ❌ Manual |
| **Dashboards** | ✅ Unlimited | ⚠️ Single view |
| **Export** | ✅ JSON, CSV, PNG | ✅ JSON |
| **Remote access** | ✅ Web-based | ❌ SSH only |
| **Resource usage** | High (Grafana + Prometheus) | Low (blessed + SQLite) |

**Recommendation:**
- **Production/team use**: Grafana (full-featured, shareable)
- **Personal/dev use**: CLI (lightweight, fast)
- **Best of both**: Run both (they share the same data)

## Next Steps

1. **Start the CLI dashboard** to see real-time activity
2. **Run some autonomous workflows** to generate data
3. **Explore the Grafana dashboard** for historical analysis
4. **Set up alerts** for quality degradation or budget overruns
5. **Export reports** for review and sharing

---

**Everything is transparent. Everything is auditable. Everything is visible.**

Questions? Check the code:
- Dashboard config: `monitoring/autonomous-transparency-dashboard.json`
- CLI implementation: `monitoring/transparency-dashboard-cli.js`
- Logging: `shared/learning-logger.js`
- Metrics: `shared/learning-metrics.js`
