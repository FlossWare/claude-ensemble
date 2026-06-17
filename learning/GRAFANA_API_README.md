# Grafana JSON Datasource API

A Node.js HTTP API server that exposes AI Learning System metrics in Grafana-compatible JSON format. Serves real-time data from the SQLite learning database.

## Quick Start

```bash
# Install dependencies (if not already installed)
npm install sqlite3

# Start the API server
node /home/sfloess/.claude/learning/grafana-api.js

# Server listens on http://localhost:3000
```

## Features

- **Grafana JSON Datasource Plugin Compatible** - Works with Grafana's native JSON plugin
- **REST API Endpoints** - Direct HTTP access for custom integrations
- **Real-time Metrics** - Pulls live data from learning.db SQLite database
- **CORS Enabled** - Safe for browser-based access
- **Health Check** - `/health` endpoint for monitoring

## API Endpoints

### Grafana Plugin Endpoints (POST)

These endpoints implement the Grafana JSON Datasource protocol:

```
POST /search
  Returns list of available metrics for metric selection dropdown

POST /query
  Main data endpoint. Accepts query object with targets array.
```

### REST API Endpoints (GET)

Direct HTTP access to metric families:

```
GET /metrics/lis
  Returns:
  {
    current: { lis_score, quality_pct, success_rate_pct, avg_cost_usd, avg_duration_sec, samples },
    trend: [ { date, timestamp, lis_score }, ... ]
  }

GET /metrics/quality
  Returns:
  {
    by_model: [ { timestamp, model, quality, executions }, ... ],
    overall: [ { timestamp, quality, min_quality, max_quality, samples }, ... ]
  }

GET /metrics/cost
  Returns:
  {
    daily: [ { timestamp, date, daily_cost, executions, avg_cost_per_exec }, ... ],
    baseline: { baseline_cost_per_exec, baseline_daily_cost },
    summary: { total_7day, avg_daily }
  }

GET /metrics/discoveries
  Returns:
  {
    tuning: [ { model, task_type, quality, cost_usd, sample_count, ... }, ... ],
    combinations: [ { task_type, worker_models, arbiter_model, synergy, ... }, ... ],
    stats: { total_tuned, total_combos, best_quality, best_combo }
  }

GET /health
  Returns:
  { status: "ok", db: "connected" }
```

## Grafana Setup

### 1. Add JSON Datasource Plugin

Most Grafana installations have the JSON plugin built-in. If not:

```bash
grafana-cli plugins install grafana-simple-json-datasource
systemctl restart grafana-server
```

### 2. Configure Data Source

1. Navigate to **Grafana > Configuration > Data Sources**
2. Click **Add data source**
3. Choose **JSON API** (or search for "JSON")
4. Set URL to `http://localhost:3000`
5. Click **Save & Test**

Expected response:
```
HTTP 200 response from http://localhost:3000/health
```

### 3. Create Dashboard Panels

Example: LIS Score Gauge

```json
{
  "datasource": "JSON API",
  "targets": [
    {
      "target": "lis_score"
    }
  ],
  "type": "gauge",
  "title": "LIS Score"
}
```

Example: Quality Trend Line

```json
{
  "datasource": "JSON API",
  "targets": [
    {
      "target": "quality_score"
    }
  ],
  "type": "timeseries",
  "title": "Quality Over Time"
}
```

## Query Response Format

The API returns data in Grafana-compatible JSON format:

### Time Series Format
```json
[
  {
    "target": "LIS Score",
    "datapoints": [
      [75.5, 1686700800000],
      [76.2, 1686787200000]
    ]
  }
]
```

### Table Format
```json
[
  {
    "target": "Recent Learnings",
    "type": "table",
    "rows": [
      ["Model", "Task", "Quality", "Cost", "Samples"],
      ["claude-opus", "code-review", 0.92, 0.0045, 150],
      ["claude-sonnet", "summarization", 0.88, 0.0025, 200]
    ]
  }
]
```

## Metrics Definition

### LIS Score (Learning Intelligence Score)

Composite metric (0-100) calculated as:
- Quality Score (40%) - Average output quality/correctness
- Success Rate (20%) - % of executions that completed successfully
- Cost Efficiency (20%) - 1 - (avg_cost / baseline_cost)
- Speed (20%) - 1 - (avg_duration / baseline_duration)

Formula:
```
LIS = (quality * 40) + (success_rate * 20) + (cost_efficiency * 20) + (speed * 20)
```

### Quality Score

0-1 scale rating of output correctness, measured by:
- Automated evaluators
- User feedback
- Consensus among multi-model arbiters
- Baseline comparison

### Cost Metrics

- `daily_cost` - Total USD spent per calendar day
- `avg_cost_per_exec` - Average cost per individual execution
- `baseline` - 7-day rolling baseline for comparison
- `savings` - (baseline_cost - actual_cost) per day

### Discoveries

Parameter tuning and model combination learnings:
- **model_tuning**: Optimal parameters found for model/task pairs
  - temperature, top_p, max_tokens
  - quality impact and success rates
  - selection rate (how often this combo is chosen by arbiter)

- **model_combinations**: Best worker model + arbiter pairs
  - synergy_score - How well models work together
  - diversity_score - Model diversity in worker set
  - consensus - Arbiter agreement rate

## Example Usage

### cURL Tests

Test health:
```bash
curl http://localhost:3000/health
```

Get LIS metrics:
```bash
curl http://localhost:3000/metrics/lis | jq
```

Get cost breakdown:
```bash
curl http://localhost:3000/metrics/cost | jq '.summary'
```

Get recent discoveries:
```bash
curl http://localhost:3000/metrics/discoveries | jq '.stats'
```

### Node.js Integration

```javascript
const api = require('./grafana-api.js');

// Use functions directly
const lisMetrics = await api.getLISMetrics();
console.log('Current LIS Score:', lisMetrics.current.lis_score);

const discoveries = await api.getDiscoveries();
console.log('Best quality tuning:', discoveries.stats.best_quality);
```

### JavaScript Browser Integration

```javascript
async function fetchLISScore() {
  const response = await fetch('http://localhost:3000/metrics/lis');
  const data = await response.json();
  console.log('LIS Score:', data.current.lis_score);
  return data;
}

// Refresh every 30 seconds
setInterval(fetchLISScore, 30000);
```

## Performance Considerations

### Query Time
- `/metrics/lis` - ~50ms (cached aggregations)
- `/metrics/quality` - ~100ms (multi-model rollup)
- `/metrics/cost` - ~150ms (30-day history)
- `/metrics/discoveries` - ~200ms (tuning + combinations)

### Database Indexes
The learning.db schema includes indexes on:
- `execution_log(timestamp, model)`
- `execution_log(quality_score)`
- `model_tuning(updated_at)`
- `model_combinations(synergy_score)`

### Optimization Tips
1. **Grafana Caching**: Set dashboard refresh to 30s or higher
2. **Time Range**: Queries use `datetime('now', '-7 days')` by default
3. **Filtering**: Excludes test models (`test-model`, `unknown`, `test`)
4. **Aggregation**: Daily/hourly buckets to reduce row count

## Troubleshooting

### "Cannot find sqlite3"
```bash
npm install sqlite3
# or if global
npm install -g sqlite3
```

### "ENOENT learning.db"
Ensure the database file exists:
```bash
ls -la /home/sfloess/.claude/learning/db/learning.db
```

### Grafana "Health check failed"
1. Check server is running: `ps aux | grep grafana-api`
2. Test endpoint: `curl http://localhost:3000/health`
3. Check firewall: `sudo firewall-cmd --add-port=3000/tcp`
4. Check logs: `tail -f /var/log/grafana/grafana.log`

### Slow Queries
- Check database: `sqlite3 learning.db ".stat"`
- Rebuild indexes: Run `VACUUM; ANALYZE;` on learning.db
- Monitor server: `node --prof grafana-api.js`

## Dashboard Examples

### KPI Summary Row
```
[LIS Score] [Avg Quality] [Total Cost] [Models Active] [Success Rate]
```

### Trend Analysis (7-day)
```
LIS Score Trend      | Quality Improvement   | Cost Savings       | Speed Gain
(line graph)         | (stacked area)        | (bar chart)        | (right axis)
```

### Model Comparison
```
Model x Task Matrix (Heatmap)
- Rows: Models (Opus, Sonnet, Haiku, etc.)
- Cols: Task Types (code-review, summarization, etc.)
- Values: Quality scores (color-coded)
```

### Recent Discoveries
```
Model Tuning Table              | Model Combinations Table
- Model                         | - Workers + Arbiter
- Task Type                     | - Synergy Score
- Quality (color bars)          | - Consensus Rate
- Optimal Temperature/top_p     | - Recent Updates
```

## Integration with CI/CD

Use this API for automated monitoring:

```bash
#!/bin/bash
# Check if LIS score dropped below threshold
SCORE=$(curl -s http://localhost:3000/metrics/lis | jq '.current.lis_score')
if [ $(echo "$SCORE < 60" | bc) -eq 1 ]; then
  echo "ALERT: LIS Score $SCORE is below 60" | mail -s "AI Learning Alert" team@example.com
fi
```

## Architecture

```
HTTP Request
     |
     v
Grafana JSON Plugin  OR  REST Client
     |
     v
/query, /search, /metrics/*
     |
     v
Request Router
     |
     +-- /query ---> Query Parser
     |               |
     |               v
     |               getLISMetrics(), getQualityMetrics(),
     |               getCostMetrics(), getDiscoveries()
     |               |
     |               v
     |               SQLite Queries (learning.db)
     |               |
     |               v
     |               JSON Formatting (Grafana format)
     |
     +-- /metrics/* -> Direct REST responses
     |
     +-- /health -----> Status check
     |
     v
JSON Response
     |
     v
HTTP 200 + CORS Headers
```

## Future Enhancements

- [ ] WebSocket support for live metric streaming
- [ ] Prometheus format endpoint (for other monitoring tools)
- [ ] Custom time aggregation (hourly/daily/weekly selector)
- [ ] Model filtering by name pattern
- [ ] Export to CSV/Parquet for analysis
- [ ] Caching layer with Redis
- [ ] Authentication (OAuth2/API key)
- [ ] Rate limiting per datasource

## License

Part of the Autonomous AI Learning System. See parent project LICENSE.

## Support

Database schema questions: See `/home/sfloess/.claude/learning/db/init-learning-db.sql`
Dashboard templates: See `/home/sfloess/.claude/learning/grafana-dashboard.json`
