# ML Models Performance Dashboard

**Dashboard File:** `grafana-ml-models-dashboard.json`  
**Data Source:** PostgreSQL (monitoring schema)  
**Update Frequency:** 30 seconds  
**Time Range:** 7 days default (customizable)

---

## Overview

This Grafana dashboard provides comprehensive monitoring and visualization of ML model performance across your infrastructure. It tracks prediction accuracy, resource usage, retraining history, and workflow execution metrics.

### Dashboard UID
```
ml-models-dashboard
```

---

## Panel Details

### 1. Prediction Accuracy Over Time (Line Chart)
**Location:** Top-left  
**Dimensions:** 12w × 8h  
**Data Source:** `monitoring.prediction_accuracy` (PostgreSQL)

**Metrics Displayed:**
- **MAE** (Mean Absolute Error) - Lower is better
- **R²** (R-squared) - Higher is better (0-1 range)
- **RMSE** (Root Mean Square Error) - Lower is better

**Query:**
```sql
SELECT
  date_trunc('hour', measurement_time) as time,
  model_name,
  AVG(COALESCE(mae, 0)) as mae,
  AVG(COALESCE(r_squared, 0)) as r_squared,
  AVG(COALESCE(rmse, 0)) as rmse
FROM monitoring.prediction_accuracy
WHERE measurement_time >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1 DESC
```

**Use Case:** Identify accuracy trends, detect model degradation, compare models side-by-side

---

### 2. Model Usage Distribution (Pie Chart)
**Location:** Top-right  
**Dimensions:** 12w × 8h  
**Data Source:** `monitoring.execution_summary` (PostgreSQL)

**Shows:**
- Percentage of workflow executions per model
- Count of executions per model (last 7 days)

**Query:**
```sql
SELECT
  model_name as metric,
  COUNT(*) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY model_name
ORDER BY value DESC
```

**Use Case:** Understand model utilization, detect underutilized models, verify load balancing

---

### 3. Prediction Error Distribution (Histogram)
**Location:** Middle-left  
**Dimensions:** 12w × 8h  
**Data Source:** `monitoring.prediction_accuracy` (PostgreSQL)

**Error Buckets:**
- 0.0-0.1 (Excellent)
- 0.1-0.2 (Very Good)
- 0.2-0.3 (Good)
- 0.3-0.5 (Fair)
- 0.5-1.0 (Poor)
- >1.0 (Critical)

**Query:**
```sql
WITH error_bins AS (
  SELECT
    CASE
      WHEN COALESCE(mae, 0) < 0.1 THEN '0.0-0.1'
      WHEN COALESCE(mae, 0) < 0.2 THEN '0.1-0.2'
      WHEN COALESCE(mae, 0) < 0.3 THEN '0.2-0.3'
      WHEN COALESCE(mae, 0) < 0.5 THEN '0.3-0.5'
      WHEN COALESCE(mae, 0) < 1.0 THEN '0.5-1.0'
      ELSE '>1.0'
    END as error_bucket,
    COUNT(*) as count
  FROM monitoring.prediction_accuracy
  WHERE measurement_time >= NOW() - INTERVAL '7 days'
  GROUP BY error_bucket
)
SELECT error_bucket as metric, count as value
FROM error_bins
ORDER BY error_bucket
```

**Use Case:** Assess prediction quality distribution, identify outliers, track error trends

---

### 4. Retraining History (Table)
**Location:** Middle-right  
**Dimensions:** 12w × 8h  
**Data Source:** `monitoring.model_retraining` (PostgreSQL)

**Columns:**
| Column | Description |
|--------|-------------|
| Model | Model name |
| Retraining Date | When retrained |
| Data Points | Training samples used |
| MAE | New mean absolute error |
| RMSE | New root mean square error |
| Improvement % | Performance gain vs previous |
| Notes | Additional context |

**Query:**
```sql
SELECT
  model_name as "Model",
  retrain_date as "Retraining Date",
  data_points_used as "Data Points",
  new_mae as "MAE",
  new_rmse as "RMSE",
  COALESCE(improvement_pct, 0)::numeric(5,2) as "Improvement %",
  COALESCE(notes, 'N/A') as "Notes"
FROM monitoring.model_retraining
WHERE retrain_date >= NOW() - INTERVAL '90 days'
ORDER BY retrain_date DESC
LIMIT 10
```

**Use Case:** Track retraining events, measure improvement, validate training data quality

---

### 5. Resource Usage Trends (Multi-Line Chart)
**Location:** Bottom-left  
**Dimensions:** 12w × 8h  
**Data Source:** `monitoring.resource_usage` (PostgreSQL)

**Metrics:**
- **CPU Usage** (%)
- **Memory Usage** (%)
- **Disk Usage** (%)

**Query:**
```sql
SELECT
  date_trunc('5 minutes', measurement_time) as time,
  'CPU Usage' as metric,
  AVG(cpu_usage_percent) as value
FROM monitoring.resource_usage
WHERE measurement_time >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
UNION ALL
SELECT
  date_trunc('5 minutes', measurement_time) as time,
  'Memory Usage' as metric,
  AVG(memory_usage_percent) as value
FROM monitoring.resource_usage
WHERE measurement_time >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
UNION ALL
SELECT
  date_trunc('5 minutes', measurement_time) as time,
  'Disk Usage' as metric,
  AVG(disk_usage_percent) as value
FROM monitoring.resource_usage
WHERE measurement_time >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY 1 DESC
```

**Use Case:** Capacity planning, identify resource bottlenecks, optimize infrastructure

---

### 6. Workflow Success Rate (Gauge)
**Location:** Bottom-right  
**Dimensions:** 12w × 8h  
**Data Source:** `monitoring.execution_summary` (PostgreSQL)

**Thresholds:**
- Red: < 50%
- Yellow: 50-85%
- Green: ≥ 85%

**Query:**
```sql
SELECT
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / 
  NULLIF(COUNT(*), 0) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
```

**Use Case:** Overall system health indicator, SLA compliance tracking

---

### 7. Workflow Execution Outcomes (Stacked Bar Chart)
**Location:** Full-width (bottom)  
**Dimensions:** 24w × 8h  
**Data Source:** `monitoring.execution_summary` (PostgreSQL)

**Outcomes Tracked:**
- success
- error
- timeout
- partial

**Query:**
```sql
SELECT
  date_trunc('hour', timestamp) as time,
  outcome,
  COUNT(*) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY 1 DESC
```

**Use Case:** Identify error patterns, track failure rates, detect anomalies

---

## Quick Stats Row (Row 8-11)

### Failed Executions (24h) - Stat
Threshold: Green (0), Yellow (1+), Orange (3+), Red (5+)
```sql
SELECT COUNT(*) as value
FROM monitoring.execution_summary
WHERE outcome = 'error' AND timestamp >= NOW() - INTERVAL '24 hours'
```

### Active Models (24h) - Stat
Count of distinct models in use over last 24 hours
```sql
SELECT COUNT(DISTINCT model) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
```

### Total Cost (24h) - Stat
Cumulative cost in USD
```sql
SELECT SUM(COALESCE(cost_usd, 0)) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
```

### Avg Execution Time (24h) - Stat
Average duration in milliseconds
```sql
SELECT AVG(COALESCE(duration_ms, 0)) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
  AND duration_ms IS NOT NULL
```

---

### 12. Model Quality Score Trends (Line Chart)
**Location:** Full-width  
**Dimensions:** 24w × 8h  
**Data Source:** `monitoring.execution_summary` (PostgreSQL)

**Metrics:**
- Quality score per model (hourly average)
- 30-day history

**Query:**
```sql
SELECT
  date_trunc('hour', timestamp) as time,
  model,
  AVG(quality_score) as value
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '30 days'
  AND quality_score IS NOT NULL
GROUP BY 1, 2
ORDER BY 1 DESC
```

**Use Case:** Long-term model performance tracking, detect quality degradation

---

## Database Schema Requirements

### monitoring.prediction_accuracy
```sql
CREATE TABLE monitoring.prediction_accuracy (
  id SERIAL PRIMARY KEY,
  model_name VARCHAR(255),
  measurement_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  mae NUMERIC(10, 6),           -- Mean Absolute Error
  rmse NUMERIC(10, 6),          -- Root Mean Square Error
  r_squared NUMERIC(5, 4),      -- R² coefficient
  prediction_count INT,
  INDEX (model_name, measurement_time)
);
```

### monitoring.model_retraining
```sql
CREATE TABLE monitoring.model_retraining (
  id SERIAL PRIMARY KEY,
  model_name VARCHAR(255),
  retrain_date TIMESTAMP WITH TIME ZONE,
  data_points_used INT,
  new_mae NUMERIC(10, 6),
  new_rmse NUMERIC(10, 6),
  improvement_pct NUMERIC(5, 2),
  notes TEXT,
  INDEX (model_name, retrain_date)
);
```

### monitoring.resource_usage
```sql
CREATE TABLE monitoring.resource_usage (
  id SERIAL PRIMARY KEY,
  measurement_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  cpu_usage_percent NUMERIC(5, 2),
  memory_usage_percent NUMERIC(5, 2),
  disk_usage_percent NUMERIC(5, 2),
  INDEX (measurement_time)
);
```

### monitoring.execution_summary
```sql
CREATE TABLE monitoring.execution_summary (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  model VARCHAR(255),
  workflow VARCHAR(255),
  task_type VARCHAR(255),
  quality_score NUMERIC(5, 4),
  input_tokens INT,
  output_tokens INT,
  cost_usd NUMERIC(10, 6),
  duration_ms INT,
  outcome VARCHAR(50),           -- 'success', 'error', 'timeout', 'partial'
  INDEX (timestamp, model, outcome)
);
```

---

## Import Instructions

### Method 1: Via Grafana UI
1. Open Grafana → **Dashboards** → **Import**
2. Paste JSON content or upload file
3. Select PostgreSQL data source
4. Click **Import**

### Method 2: Via CLI
```bash
# Using the import script
./monitoring/import-dashboard.sh grafana-ml-models-dashboard.json

# Manual curl
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Authorization: Bearer YOUR_GRAFANA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana-ml-models-dashboard.json
```

### Method 3: Copy-Paste
1. Open `grafana-ml-models-dashboard.json` in editor
2. Copy entire JSON content
3. In Grafana, go to **Dashboard** → **New** → **Import**
4. Paste JSON in the editor
5. Configure data source → **Import**

---

## Customization

### Change Time Range
Edit the `time` section:
```json
"time": {
  "from": "now-7d",    // Default: Last 7 days
  "to": "now"
}
```

Options:
- `"now-1h"` - Last hour
- `"now-24h"` - Last 24 hours
- `"now-7d"` - Last 7 days
- `"now-30d"` - Last 30 days

### Modify Refresh Rate
Edit `refresh` field:
```json
"refresh": "30s"    // Update every 30 seconds
```

Common values:
- `"10s"` - 10 seconds
- `"30s"` - 30 seconds
- `"1m"` - 1 minute
- `"5m"` - 5 minutes
- `"off"` - Disable auto-refresh

### Change Data Source
1. Open dashboard in edit mode
2. Click panel title → **Edit**
3. Change "PostgreSQL" to your data source name
4. Update SQL queries if schema differs
5. Save

### Add Alerting Rules
1. Open panel → **Alerts**
2. Configure thresholds and notifications
3. Save

Example alert: Trigger when success rate < 80%

---

## Performance Tips

### Optimize Query Speed
1. Ensure indexes on:
   - `timestamp`, `model`, `outcome` columns
   - Date fields used in WHERE clauses

2. Use materialized views for aggregations:
```sql
CREATE MATERIALIZED VIEW monitoring.hourly_execution_summary AS
SELECT
  date_trunc('hour', timestamp) as hour,
  model,
  outcome,
  COUNT(*) as count,
  AVG(quality_score) as avg_quality,
  SUM(cost_usd) as total_cost
FROM monitoring.execution_summary
GROUP BY 1, 2, 3
WITH DATA;

CREATE INDEX idx_hourly_summary ON monitoring.hourly_execution_summary(hour, model);

-- Refresh regularly
REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.hourly_execution_summary;
```

3. Set retention policies:
```sql
-- Keep only 90 days of raw data
DELETE FROM monitoring.prediction_accuracy
WHERE measurement_time < NOW() - INTERVAL '90 days';
```

---

## Troubleshooting

### No Data Showing
1. Check PostgreSQL data source connection
2. Verify tables exist and have data:
```bash
psql -c "SELECT COUNT(*) FROM monitoring.prediction_accuracy;"
```
3. Check query time range matches dashboard setting
4. Look for errors in Grafana inspector (Ctrl+Shift+I)

### Slow Dashboard Load
1. Reduce time range (e.g., 7 days → 24 hours)
2. Add database indexes on query columns
3. Use materialized views instead of raw queries
4. Reduce panel refresh frequency

### Data Gaps
1. Verify monitoring services are running:
```bash
systemctl status monitoring-service
```
2. Check for query errors in Prometheus/PostgreSQL logs
3. Ensure NTP time sync: `timedatectl status`

---

## Integration with Monitoring Stack

### Alert Notifications
Add to Grafana notification channels for:
- Slack: `#ml-models-alerts`
- PagerDuty: `ml-models-team`
- Email: `ml-ops@company.com`

### Webhook Notifications
See `monitoring/webhook-config.json` for setup

### Cost Tracking
Dashboard integrates with:
- `monitoring.execution_summary.cost_usd`
- PostgreSQL `costs.*` schema
- Cost analyzer CLI: `./monitoring/transparency-dashboard-cli.js`

---

## Related Dashboards

- **Fleet Activity:** `grafana-dashboard-fleet.json`
- **Consensus Monitoring:** `grafana-dashboard-consensus.json`
- **API Health:** Built-in Prometheus dashboard
- **Drift Detection:** See `monitoring/drift-detection-cron.md`

---

## Quick Reference: SQL Snippets

### Top 5 Most Used Models
```sql
SELECT model, COUNT(*) as uses
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY uses DESC
LIMIT 5;
```

### Average Cost Per Model (24h)
```sql
SELECT model, AVG(cost_usd) as avg_cost
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY avg_cost DESC;
```

### Failed Workflow Types
```sql
SELECT workflow, task_type, COUNT(*) as errors
FROM monitoring.execution_summary
WHERE outcome = 'error' AND timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY workflow, task_type
ORDER BY errors DESC;
```

### Model Quality Comparison (7 days)
```sql
SELECT 
  model,
  AVG(quality_score) as avg_quality,
  MIN(quality_score) as min_quality,
  MAX(quality_score) as max_quality,
  STDDEV(quality_score) as stddev_quality
FROM monitoring.execution_summary
WHERE timestamp >= NOW() - INTERVAL '7 days'
  AND quality_score IS NOT NULL
GROUP BY model
ORDER BY avg_quality DESC;
```

---

## Support

For issues or feature requests:
1. Check logs: `tail -f monitoring/logs/dashboard.log`
2. Run diagnostics: `./monitoring/import-dashboard.sh --validate`
3. Review schema: See database section above
4. Contact: See project README for maintainer info

---

**Last Updated:** 2026-07-04  
**Version:** 1.0  
**Status:** Production Ready
