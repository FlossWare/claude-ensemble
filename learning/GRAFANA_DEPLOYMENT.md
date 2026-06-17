# Grafana Dashboard Deployment Instructions

## Overview

This document provides complete deployment instructions for the Autonomous AI Learning System Grafana dashboard with Prometheus datasource.

**Components:**
1. **Prometheus Exporter** (`prometheus-exporter.js`) - Exposes metrics from `learning.db` on port 9090
2. **Grafana Dashboard** (`grafana-dashboard.json`) - 21-panel dashboard with 7 rows
3. **Systemd Service** (`ai-learning-exporter.service`) - Runs exporter as system service
4. **CLI Dashboard** (`scripts/dashboard-cli.sh`) - Terminal-based alternative for non-Grafana users

---

## Prerequisites

### Required Software
- Node.js (v14+)
- SQLite3
- Grafana (v9.0+)
- Prometheus (optional, if using remote Prometheus server)

### Install Dependencies
```bash
cd ~/.claude/learning
npm install sqlite3
```

---

## Deployment Steps

### 1. Start Prometheus Exporter

#### Option A: Foreground (Testing)
```bash
cd ~/.claude/learning
node prometheus-exporter.js
```

Output:
```
✓ Connected to database: /home/sfloess/.claude/learning/db/learning.db
✓ Prometheus exporter listening on http://localhost:9090/metrics
  Health check: http://localhost:9090/health
  Cache TTL: 10000ms
```

#### Option B: Background (systemd Service)

**Install systemd service:**
```bash
# Copy service file to systemd directory
sudo cp ~/.claude/learning/ai-learning-exporter.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable ai-learning-exporter

# Start service
sudo systemctl start ai-learning-exporter

# Check status
sudo systemctl status ai-learning-exporter
```

**View logs:**
```bash
# Real-time logs
sudo journalctl -u ai-learning-exporter -f

# Last 100 lines
sudo journalctl -u ai-learning-exporter -n 100
```

**Manage service:**
```bash
# Stop
sudo systemctl stop ai-learning-exporter

# Restart
sudo systemctl restart ai-learning-exporter

# Disable (prevent auto-start)
sudo systemctl disable ai-learning-exporter
```

#### Verify Exporter
```bash
# Check health
curl http://localhost:9090/health

# View metrics
curl http://localhost:9090/metrics | head -50
```

---

### 2. Configure Grafana Datasource

#### Access Grafana
- Local: `http://localhost:3000`
- Fleet server: `http://server-01:3001` (assuming Grafana on port 3001)

#### Add Prometheus Datasource
1. Navigate to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - **Name:** `Prometheus`
   - **URL:** `http://localhost:9090`
   - **Access:** `Server (default)` or `Browser` (if accessing from different host)
5. Click **Save & Test**

**Expected metrics prefix:** `ai_learning_*`

---

### 3. Import Dashboard

#### Import from JSON
1. Navigate to **Dashboards → Import**
2. Click **Upload JSON file**
3. Select: `/home/sfloess/.claude/learning/grafana-dashboard.json`
4. Configure:
   - **Name:** `Autonomous AI Learning System` (default)
   - **Folder:** Select or create folder
   - **UID:** `ai-learning-prometheus` (default)
   - **Datasource:** Select the Prometheus datasource created in Step 2
5. Click **Import**

#### Manual Import (Alternative)
```bash
# Copy JSON content
cat ~/.claude/learning/grafana-dashboard.json

# Paste into Grafana: Dashboards → Import → Import via panel json
```

---

### 4. Access Dashboard

**URL:** `http://localhost:3000/d/ai-learning-prometheus/autonomous-ai-learning-system`

**Fleet server:** `http://server-01:3001/d/ai-learning-prometheus/autonomous-ai-learning-system`

**Template Variables:**
- `$datasource` - Prometheus datasource (multi-select, default: all)
- `$model` - AI model filter (multi-select, default: all)
- `$task_type` - Task type filter (multi-select, default: all)
- `$workflow` - Workflow filter (multi-select, default: all)

**Time Range:** Default 7 days, options: 7d, 30d, 90d, 1y

**Auto-refresh:** 30 seconds

---

## Dashboard Panels Summary

### Row 1: Executive Summary (y=0)
1. **LIS Score** (gauge) - Learning Intelligence Score 0-100
2. **LIS Score Trend** (timeseries) - LIS over time with GrYlRd gradient
3. **Quality Improvement** (timeseries) - Per-model quality with ALL_MODELS overlay

### Row 2: Cost & Speed (y=8)
4. **Cost Savings** (timeseries) - Dual-axis: daily cost + avg cost/exec
5. **Speed Improvement** (timeseries) - Dual-axis: avg duration + cumulative seconds saved
6. **Learning Sessions** (timeseries bars) - Executions by workflow

### Row 3: Discoveries (y=16)
7. **Top Discoveries** (table) - Model tuning + best combos with color-coded quality
8. **Model Performance Heatmap** (table) - Model x task_type quality/win rate/consensus

### Row 4: Research Activity (y=26)
9. **Research Activity** (timeseries) - Research executions over time
10. **Parameter Tuning** (table) - Optimal temperature/top_p/max_tokens

### Row 5: Analysis (y=34)
11. **Temperature vs Quality** (scatter) - XY chart colored by model
12. **Fleet Workload Distribution** (piechart) - Donut with value+percent
13. **Fleet Error Rate** (timeseries) - Per-model error rate with thresholds

### Row 6: KPIs (y=42)
14-19. **KPI Stats** (6 stat panels):
   - Total Executions
   - Models Active
   - Avg Quality
   - Total Cost
   - Tuned Combos
   - Best Synergy

### Row 7: Efficiency (y=46)
20. **Model Combo Effectiveness** (barchart) - Horizontal bars by quality
21. **Cost vs Quality Efficiency** (scatter) - Point size scaled by sample count

---

## Alert Rules

Four alert rules configured (requires alert manager):

1. **Quality Degradation:** Quality < 0.5
2. **Cost Spike:** Cost > 2x 24h average
3. **Error Rate:** Error rate > 20%
4. **Model Timeout:** Duration > 60s

Configure notifications in Grafana → Alerting → Notification channels

---

## CLI Dashboard (Non-Grafana Alternative)

### Usage

```bash
# Show all metrics
~/.claude/learning/scripts/dashboard-cli.sh

# Show LIS score only
~/.claude/learning/scripts/dashboard-cli.sh --lis

# Show model performance
~/.claude/learning/scripts/dashboard-cli.sh --models

# Show model combinations
~/.claude/learning/scripts/dashboard-cli.sh --combos

# Show parameter tuning
~/.claude/learning/scripts/dashboard-cli.sh --tuning

# Show cost analysis
~/.claude/learning/scripts/dashboard-cli.sh --cost

# Quick summary
~/.claude/learning/scripts/dashboard-cli.sh --summary

# Watch mode (refresh every 5 seconds)
~/.claude/learning/scripts/dashboard-cli.sh --watch
~/.claude/learning/scripts/dashboard-cli.sh --watch --models
```

### Example Output

```
╔═══════════════════════════════════════════════════════════════════════════╗
║        Autonomous AI Learning System - CLI Dashboard                     ║
║        Database: learning.db                                              ║
║        2026-06-13 10:30:45                                                ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════
  Learning Intelligence Score (LIS)
═══════════════════════════════════════════════════════════════════

  Overall LIS Score:   0.875 / 100  (87.50%)

  Components:
    Quality (40%):       35.0  (avg quality: 0.875)
    Success (20%):       18.4  (success rate: 0.920)
    Cost Efficiency:     19.2  (avg cost: $0.0040)
    Speed Efficiency:    15.1  (avg duration: 4.9s)

  Total Executions:  1,247
```

---

## Fleet Deployment

### Deploy to Fleet Servers

For distributed fleet (aio-01, server-01/02/03):

```bash
# Deploy exporter to all servers
for server in aio-01 server-01 server-02 server-03; do
  echo "Deploying to $server..."
  scp ~/.claude/learning/prometheus-exporter.js $server:.claude/learning/
  scp ~/.claude/learning/ai-learning-exporter.service $server:.claude/learning/
  ssh $server "sudo cp ~/.claude/learning/ai-learning-exporter.service /etc/systemd/system/"
  ssh $server "sudo systemctl daemon-reload"
  ssh $server "sudo systemctl enable ai-learning-exporter"
  ssh $server "sudo systemctl start ai-learning-exporter"
done
```

### Centralized Grafana Setup

**Option 1:** Run Grafana on one server, configure multiple Prometheus datasources

1. Add datasource for each server:
   - `Prometheus-aio-01` → `http://aio-01:9090`
   - `Prometheus-server-01` → `http://server-01:9090`
   - etc.

2. Duplicate dashboard for each server or use `$datasource` variable

**Option 2:** Federated Prometheus

1. Run Prometheus server that scrapes all exporters
2. Single datasource in Grafana
3. Use labels to filter by server

---

## Prometheus Metrics Reference

### Execution Metrics
- `ai_learning_execution_total{model,workflow,task_type,outcome}` - Counter: total executions
- `ai_learning_quality_score{model,task_type}` - Gauge: average quality score (0-1)
- `ai_learning_duration_seconds{model,task_type}` - Gauge: average duration in seconds
- `ai_learning_success_rate{model,task_type}` - Gauge: success rate (0-1)
- `ai_learning_consensus_score{model,task_type}` - Gauge: consensus score (0-1)

### Cost Metrics
- `ai_learning_cost_usd{model,workflow,aggregation=total|avg}` - Gauge: cost in USD

### Token Metrics
- `ai_learning_token_usage{model,token_type=input|output}` - Counter: total tokens

### Model Selection
- `ai_learning_model_selection_rate{model,task_type}` - Gauge: arbiter selection rate (0-1)

### Parameter Tuning
- `ai_learning_tuning_temperature{model,task_type}` - Gauge: optimal temperature
- `ai_learning_tuning_top_p{model,task_type}` - Gauge: optimal top_p
- `ai_learning_tuning_max_tokens{model,task_type}` - Gauge: optimal max_tokens
- `ai_learning_tuning_quality{model,task_type}` - Gauge: tuned quality score
- `ai_learning_tuning_sample_count{model,task_type}` - Gauge: sample count

### Model Combinations
- `ai_learning_combo_quality{task_type,workers,arbiter}` - Gauge: combination quality
- `ai_learning_combo_synergy{task_type,workers,arbiter}` - Gauge: synergy score
- `ai_learning_combo_consensus{task_type,workers,arbiter}` - Gauge: consensus score
- `ai_learning_combo_diversity{task_type,workers,arbiter}` - Gauge: diversity score
- `ai_learning_combo_usage_count{task_type,workers,arbiter}` - Counter: usage count

### Composite Metrics
- `ai_learning_lis_score` - Gauge: Learning Intelligence Score (0-100)
- `ai_learning_active_models_count` - Gauge: distinct models in last 7 days
- `ai_learning_error_total{model}` - Counter: total errors by model

---

## Troubleshooting

### Exporter Not Starting
```bash
# Check if port 9090 is available
sudo lsof -i :9090

# Check database permissions
ls -la ~/.claude/learning/db/learning.db

# Run in foreground to see errors
node ~/.claude/learning/prometheus-exporter.js
```

### No Data in Grafana
```bash
# Verify exporter is running
curl http://localhost:9090/metrics

# Check Grafana datasource connection
# Grafana UI: Configuration → Data Sources → Prometheus → Save & Test

# Verify metric names
curl http://localhost:9090/metrics | grep ai_learning_
```

### Dashboard Not Importing
- Ensure Grafana version is 9.0+
- Check JSON validity: `jq . < grafana-dashboard.json`
- Verify datasource name matches configuration

### Slow Query Performance
- Check database size: `du -h ~/.claude/learning/db/learning.db`
- Vacuum database: `sqlite3 ~/.claude/learning/db/learning.db "VACUUM;"`
- Reduce cache TTL in exporter: `CACHE_TTL=5000` (5 seconds)

---

## Maintenance

### Database Cleanup
```bash
# Remove old executions (older than 90 days)
sqlite3 ~/.claude/learning/db/learning.db <<EOF
DELETE FROM execution_log WHERE timestamp < datetime('now', '-90 days');
VACUUM;
EOF
```

### Service Logs Rotation
```bash
# Configure journald rotation in /etc/systemd/journald.conf
SystemMaxUse=100M
SystemKeepFree=500M
SystemMaxFileSize=10M
```

### Update Dashboard
```bash
# Export modified dashboard from Grafana UI
# Save to grafana-dashboard.json
# Re-import via Grafana UI: Dashboards → Import
```

---

## Performance Tuning

### Exporter Cache
- Default: 10 seconds (`CACHE_TTL=10000`)
- Increase for lower CPU usage: `CACHE_TTL=30000` (30s)
- Decrease for real-time updates: `CACHE_TTL=5000` (5s)

### Database Indexing
All necessary indexes created by `init-learning-db.sql`. Verify:
```bash
sqlite3 ~/.claude/learning/db/learning.db ".indices execution_log"
```

### Grafana Refresh
- Default: 30s auto-refresh
- Adjust per panel or dashboard-wide
- Disable for static analysis

---

## Security

### Exporter Security
- **Firewall:** Restrict port 9090 to Grafana server IP only
- **Authentication:** Consider nginx reverse proxy with basic auth
- **TLS:** Use nginx/caddy for HTTPS termination

### Grafana Security
- Enable authentication (default admin/admin, change immediately)
- Use read-only datasource for public dashboards
- Configure organization/team permissions

---

## References

- **Prometheus Exporter:** `/home/sfloess/.claude/learning/prometheus-exporter.js`
- **Dashboard JSON:** `/home/sfloess/.claude/learning/grafana-dashboard.json`
- **Systemd Service:** `/home/sfloess/.claude/learning/ai-learning-exporter.service`
- **CLI Dashboard:** `/home/sfloess/.claude/learning/scripts/dashboard-cli.sh`
- **Database Schema:** `/home/sfloess/.claude/learning/init-learning-db.sql`

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review exporter logs: `journalctl -u ai-learning-exporter -n 100`
3. Verify database integrity: `sqlite3 ~/.claude/learning/db/learning.db "PRAGMA integrity_check;"`
4. Test metrics endpoint: `curl http://localhost:9090/metrics`

---

**Last Updated:** 2026-06-13
**Version:** 1.0
