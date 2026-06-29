# Consensus Monitoring Dashboard

## Overview

Real-time Grafana dashboard for multi-AI consensus system monitoring.

**Components:**
- 7 visualization panels
- PostgreSQL data source (workflow.*, monitoring.*, learning.*)
- Prometheus exporter for metrics
- 30-second auto-refresh

---

## Panels

### 1. Consensus Decisions Per Minute (Time Series)
**Data Source:** Prometheus  
**Metric:** `rate(consensus_decisions_total[1m])`  
**Purpose:** Track consensus throughput and activity spikes

### 2. Model Performance Trends (Time Series)
**Data Source:** PostgreSQL  
**Query:** 7-day rolling average of quality_score per model  
**Purpose:** Identify model quality drift over time  
**Alert threshold:** < 0.6 (red), 0.6-0.8 (yellow), > 0.8 (green)

### 3. Drift Alerts (Table)
**Data Source:** PostgreSQL  
**Query:** Recent 24h drift detections from `monitoring.model_drift`  
**Columns:** model, drift_type, drift_magnitude, detected_at, status  
**Purpose:** Surface quality degradation for investigation

### 4. Disagreement Score Distribution (Pie Chart)
**Data Source:** PostgreSQL  
**Query:** 7-day histogram of arbiter disagreement scores  
**Ranges:**
- < 0.1: Strong consensus
- 0.1-0.2: Moderate consensus
- 0.2-0.3: Weak consensus
- >= 0.3: Divergent (triggers human review)

### 5. Cost Per Decision (Stacked Bar Chart)
**Data Source:** Prometheus  
**Metric:** `sum by(model) (increase(consensus_cost_usd[1h]))`  
**Purpose:** Track API cost trends and identify expensive models

### 6. Thompson Sampling Weights (Donut Chart)
**Data Source:** PostgreSQL  
**Query:** Strategy success rates from `learning.experiences` (7 days)  
**Purpose:** Visualize bandit exploration/exploitation balance

### 7. Human Review Queue Depth (Stat)
**Data Source:** PostgreSQL  
**Query:** Count of unreviewed items in `workflow.human_review_queue`  
**Alert threshold:** > 50 (red), 10-50 (yellow), < 10 (green)

---

## Installation

### 1. Start Prometheus Exporter

```bash
cd monitoring
node prometheus-exporter.cjs &

# Verify metrics endpoint
curl http://localhost:9101/metrics
```

**Environment Variables:**
- `PROMETHEUS_PORT` (default: 9101)
- `PG_HOST` (default: laptop-01)
- `PG_DATABASE` (default: learning)
- `PG_USER` (default: sfloess)

### 2. Configure Prometheus Scrape Target

Add to `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'consensus-exporter'
    static_configs:
      - targets: ['localhost:9101']
    scrape_interval: 30s
```

Reload Prometheus:
```bash
systemctl reload prometheus
```

### 3. Import Dashboard to Grafana

**Method 1: Web UI**
1. Navigate to Grafana → Dashboards → Import
2. Upload `grafana-dashboard-consensus.json`
3. Select data sources:
   - PostgreSQL: `learning` database on laptop-01
   - Prometheus: Local instance

**Method 2: CLI**
```bash
./import-dashboard.sh grafana-dashboard-consensus.json
```

**Method 3: Provisioning**
Copy to `/etc/grafana/provisioning/dashboards/`:
```bash
sudo cp grafana-dashboard-consensus.json /etc/grafana/provisioning/dashboards/
sudo systemctl restart grafana-server
```

---

## Data Sources Configuration

### PostgreSQL
- **Host:** laptop-01
- **Port:** 5432
- **Database:** learning
- **User:** sfloess
- **SSL Mode:** disable

**Required Schemas:**
- `workflow.*` (executions, worker_results, arbiter_decisions, human_review_queue)
- `monitoring.*` (model_drift)
- `learning.*` (experiences, strategy_performance)

**Test Connection:**
```bash
psql -h laptop-01 -U sfloess -d learning -c "SELECT COUNT(*) FROM workflow.arbiter_decisions"
```

### Prometheus
- **URL:** http://localhost:9090
- **Access:** Server (default)

**Test Connection:**
```bash
curl http://localhost:9090/api/v1/query?query=consensus_decisions_total
```

---

## Metrics Exposed by Exporter

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `consensus_decisions_total` | counter | - | Total consensus decisions (24h) |
| `consensus_cost_usd` | gauge | model | Cost per model (1h window) |
| `consensus_disagreement_score_bucket` | histogram | le | Disagreement distribution (7 days) |
| `consensus_quality_score` | gauge | model | Quality per model (7 day avg) |
| `consensus_drift_alerts_total` | counter | - | Drift alerts (24h) |

**Refresh Rate:** Metrics cached for 30s to reduce PostgreSQL load

---

## Troubleshooting

### Dashboard shows "No data"

1. Check PostgreSQL connection:
   ```bash
   psql -h laptop-01 -U sfloess -d learning -c "\dt workflow.*"
   ```

2. Verify data exists:
   ```bash
   psql -h laptop-01 -U sfloess -d learning -c \
     "SELECT COUNT(*) FROM workflow.arbiter_decisions WHERE created_at >= NOW() - INTERVAL '24 hours'"
   ```

3. Check Grafana data source settings (Configuration → Data Sources)

### Prometheus metrics missing

1. Verify exporter is running:
   ```bash
   curl http://localhost:9101/health
   ```

2. Check Prometheus scrape status:
   ```bash
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="consensus-exporter")'
   ```

3. Tail exporter logs:
   ```bash
   journalctl -u prometheus-exporter -f
   ```

### High PostgreSQL load

- Metrics cache is 30s (configurable in `prometheus-exporter.cjs`)
- Reduce Grafana refresh rate: Dashboard Settings → Time options → Refresh → 1m

---

## Systemd Service (Optional)

Create `/etc/systemd/system/prometheus-exporter.service`:

```ini
[Unit]
Description=Prometheus Consensus Metrics Exporter
After=network.target postgresql.service

[Service]
Type=simple
User=sfloess
WorkingDirectory=/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/monitoring
ExecStart=/usr/bin/node prometheus-exporter.cjs
Restart=always
RestartSec=10

Environment=PG_HOST=laptop-01
Environment=PG_DATABASE=learning
Environment=PG_USER=sfloess
Environment=PROMETHEUS_PORT=9101

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable prometheus-exporter
sudo systemctl start prometheus-exporter
sudo systemctl status prometheus-exporter
```

---

## Alert Rules (Prometheus)

Add to Prometheus alert rules:

```yaml
groups:
  - name: consensus_alerts
    interval: 1m
    rules:
      - alert: HighDisagreementRate
        expr: rate(consensus_disagreement_score_bucket{le="0.3"}[5m]) < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Consensus disagreement rate high (> 30%)"
          
      - alert: HumanReviewQueueBacklog
        expr: consensus_human_review_queue_depth > 50
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Human review queue has {{ $value }} pending items"
          
      - alert: ModelDriftDetected
        expr: increase(consensus_drift_alerts_total[1h]) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "{{ $value }} drift alerts in last hour"
```

---

## Dashboard Access

**Default URL:** http://pi-02:3000/d/consensus-monitoring  
**Credentials:** See `memory/.secrets.md`

**Share Link:** Click dashboard title → Share → Snapshot (expires in 7 days)

---

## Next Steps

1. **Add more panels:**
   - Worker response time (p50/p95/p99)
   - Token usage trends
   - Error rate by model

2. **Create alerts:**
   - Quality drop > 20% in 1h
   - Cost spike > $5/hour
   - Queue depth > 100

3. **Add annotations:**
   - Model updates
   - Configuration changes
   - Deployment events

---

## Files Created

- `monitoring/grafana-dashboard-consensus.json` - Dashboard definition (7 panels)
- `monitoring/prometheus-exporter.cjs` - Metrics exporter (port 9101)
- `monitoring/README-consensus-dashboard.md` - This file

**Total Panels:** 7  
**Data Sources:** PostgreSQL + Prometheus  
**Refresh Rate:** 30 seconds
