# ML Models Dashboard - Quick Start

**10-minute setup guide for getting the dashboard running**

---

## Files Created

| File | Purpose |
|------|---------|
| `grafana-ml-models-dashboard.json` | Main dashboard definition (import this) |
| `ML-MODELS-DASHBOARD-GUIDE.md` | Complete documentation |
| `schema-ml-models-monitoring.sql` | Database schema (run once) |
| `validate-ml-models-dashboard.sh` | Validation script |
| `ML-MODELS-DASHBOARD-QUICKSTART.md` | This file |

---

## Step 1: Validate JSON (30 seconds)

```bash
cd monitoring
./validate-ml-models-dashboard.sh
```

Expected output:
```
✓ Dashboard validation complete!
12 panels
PostgreSQL data source configured
```

---

## Step 2: Setup Database (2 minutes)

```bash
# Connect to your PostgreSQL database
psql -U postgres -d learning -f schema-ml-models-monitoring.sql

# Verify tables created
psql -d learning -c "SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'monitoring' ORDER BY table_name;"
```

Expected tables:
- `monitoring.prediction_accuracy`
- `monitoring.model_retraining`
- `monitoring.resource_usage`
- `monitoring.execution_summary`
- `monitoring.model_drift`
- `monitoring.prediction_errors`
- `monitoring.inference_log`

---

## Step 3: Import Dashboard into Grafana (3 minutes)

### Option A: Via Grafana UI (Easiest)
1. Open Grafana: `http://localhost:3000`
2. Go to **Dashboards** → **Import**
3. Upload file: `grafana-ml-models-dashboard.json`
4. Select PostgreSQL data source
5. Click **Import**

### Option B: Via Script
```bash
./import-dashboard.sh grafana-ml-models-dashboard.json
```

### Option C: Via API
```bash
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @grafana-ml-models-dashboard.json
```

---

## Step 4: Populate Test Data (1 minute)

```bash
psql -d learning << 'EOF'
-- Insert sample prediction accuracy data
INSERT INTO monitoring.prediction_accuracy 
(model_name, mae, rmse, r_squared, prediction_count)
VALUES
('model-opus', 0.0245, 0.0312, 0.9450, 1000),
('model-sonnet', 0.0198, 0.0287, 0.9620, 1000),
('model-haiku', 0.0267, 0.0334, 0.9380, 1000);

-- Insert sample resource usage
INSERT INTO monitoring.resource_usage 
(model_name, cpu_usage_percent, memory_usage_percent, disk_usage_percent)
VALUES
('model-opus', 45.2, 62.3, 78.5),
('model-sonnet', 38.1, 55.2, 78.5),
('model-haiku', 22.3, 42.1, 78.5);

-- Insert sample execution summary
INSERT INTO monitoring.execution_summary 
(model, workflow, task_type, quality_score, cost_usd, duration_ms, outcome)
VALUES
('model-opus', 'research', 'analysis', 0.92, 0.15, 2500, 'success'),
('model-sonnet', 'research', 'analysis', 0.88, 0.08, 2100, 'success'),
('model-haiku', 'research', 'analysis', 0.85, 0.04, 1800, 'success');
EOF
```

---

## Step 5: Verify Dashboard (2 minutes)

1. Go to Grafana dashboard: `http://localhost:3000/d/ml-models-dashboard`
2. Verify panels display:
   - ✓ Prediction Accuracy Over Time (should show 3 models)
   - ✓ Model Usage Distribution (pie chart)
   - ✓ Error Distribution (histogram)
   - ✓ Retraining History (table)
   - ✓ Resource Usage Trends (line chart)
   - ✓ Success Rate Gauge
   - ✓ And 6 more panels...

---

## Panel Overview

### Top Row
| Panel | What It Shows |
|-------|--------------|
| Prediction Accuracy | MAE/RMSE/R² trends over 30 days |
| Model Usage | % of workflows using each model |

### Middle Row
| Panel | What It Shows |
|-------|--------------|
| Error Distribution | Histogram of prediction errors |
| Retraining History | Last 10 retraining events |

### Third Row
| Panel | What It Shows |
|-------|--------------|
| Resource Usage | CPU/Memory/Disk trends |
| Success Rate | % of successful workflows (24h) |

### Stats Row
| Panel | What It Shows |
|-------|--------------|
| Failed (24h) | Count of errors |
| Active Models | Distinct models used |
| Total Cost | USD spend in last 24h |
| Avg Time | Average execution duration |

### Bottom Row
| Panel | What It Shows |
|-------|--------------|
| Outcomes | Stacked bar of success/error/timeout |
| Quality Scores | Quality trend per model (30 days) |

---

## Common Queries

### Add More Test Data
```sql
-- Insert execution records for testing
INSERT INTO monitoring.execution_summary 
(model, workflow, timestamp, outcome, quality_score, duration_ms, cost_usd)
SELECT
  arr[floor(random() * 3)::int + 1],                    -- Random model
  arr2[floor(random() * 3)::int + 1],                   -- Random workflow
  NOW() - (INTERVAL '1 day' * random() * 7),            -- Random time in last 7 days
  arr3[floor(random() * 4)::int + 1],                   -- Random outcome
  0.75 + (random() * 0.25),                             -- Quality score 0.75-1.0
  (1000 + random() * 4000)::int,                        -- Duration 1-5 sec
  (0.01 + random() * 0.20)::numeric(10,6)               -- Cost $0.01-0.21
FROM (SELECT ARRAY['model-opus', 'model-sonnet', 'model-haiku'] as arr) a,
     (SELECT ARRAY['research', 'analysis', 'optimization'] as arr2) b,
     (SELECT ARRAY['success', 'success', 'error', 'timeout'] as arr3) c
FOR i IN 1..100;
```

### Check Database Size
```sql
SELECT 
  table_name,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'monitoring'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Refresh Materialized Views
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.hourly_execution_summary;
REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.daily_model_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.model_comparison;
```

---

## Troubleshooting

### Dashboard Shows "No Data"
1. Check PostgreSQL is running: `systemctl status postgresql`
2. Verify data exists: `SELECT COUNT(*) FROM monitoring.execution_summary;`
3. Check time range matches dashboard (default: last 7 days)
4. Verify PostgreSQL data source configured in Grafana

### Dashboard Loads Slowly
1. Reduce time range in dashboard (default is 7 days)
2. Create database indexes (done automatically by schema)
3. Check PostgreSQL CPU: `htop` on database server

### Panels Show Errors
1. Click panel title → **Edit**
2. Check SQL query in **Query** tab
3. Run query manually in psql to debug
4. Check data source configuration

---

## Next Steps

1. **Connect real monitoring**: Point your application to insert data into these tables
2. **Add alerting**: Set thresholds for quality_score, success_rate, cost
3. **Customize time ranges**: Change default time range in dashboard settings
4. **Add more panels**: Duplicate panels, modify queries for custom metrics
5. **Setup retention**: Configure PostgreSQL to auto-clean old data

---

## Reference

- **Full Guide**: `ML-MODELS-DASHBOARD-GUIDE.md`
- **Database Schema**: `schema-ml-models-monitoring.sql`
- **Grafana Docs**: https://grafana.com/docs/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

---

**Status:** ✓ Ready to use  
**Created:** 2026-07-04  
**Version:** 1.0
