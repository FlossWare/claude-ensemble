# Production Monitoring Guide

**System:** Distributed LLM Orchestration Framework  
**Version:** 1.0.0  
**Last Updated:** 2026-07-03  
**Monitoring Team:** Fleet Operations

## Table of Contents

1. [Overview](#overview)
2. [Monitoring Stack](#monitoring-stack)
3. [Key Metrics](#key-metrics)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Alerting Rules](#alerting-rules)
6. [Feedback Loop Monitoring](#feedback-loop-monitoring)
7. [Performance Baselines](#performance-baselines)
8. [Troubleshooting Dashboards](#troubleshooting-dashboards)
9. [Custom Queries](#custom-queries)

---

## Overview

### Monitoring Philosophy

**Four-Layer Monitoring Strategy:**

1. **Infrastructure Layer:** CPU, RAM, disk, network (Prometheus + node_exporter)
2. **Application Layer:** Workflow execution, model performance (PostgreSQL metrics)
3. **Cost Layer:** API usage, token consumption (costs.entries table)
4. **Safety Layer:** Feedback loop detection, model diversity (feedback_loop_optimizer)

### Monitoring Endpoints

| Component | URL | Purpose |
|-----------|-----|---------|
| **Grafana** | http://pi-02:3000 | Dashboard UI |
| **Prometheus** | http://pi-02:9090 | Metrics storage/query |
| **Node Exporters** | http://`<node>`:9100/metrics | System metrics |
| **PostgreSQL** | laptop-01:5432 | Data source |

### Access Credentials

**Grafana:**
- URL: http://pi-02:3000
- Default: admin / admin (change on first login)
- Read-only viewer: viewer / viewer

**PostgreSQL:**
- Host: laptop-01
- Port: 5432
- Database: learning
- User: claude
- Password: (see `~/.claude/memory/.secrets.md`)

---

## Monitoring Stack

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VISUALIZATION LAYER                      │
│  Grafana (pi-02:3000)                                       │
│  - Fleet Overview Dashboard                                 │
│  - Model Performance Dashboard                              │
│  - Cost Analysis Dashboard                                  │
│  - Feedback Loop Safety Dashboard                           │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────────────────────────────────────────┐
│                    METRICS COLLECTION                        │
│  Prometheus (pi-02:9090)                                    │
│  - Scrapes node exporters every 15s                         │
│  - Retention: 30 days                                       │
│  - Storage: /var/lib/prometheus/                            │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                             │
│                                                             │
│  Node Exporters (all fleet nodes)                           │
│  - CPU, RAM, disk, network metrics                          │
│  - Exposed at :9100/metrics                                 │
│                                                             │
│  PostgreSQL (laptop-01:5432)                                │
│  - Workflow executions, model performance                   │
│  - Direct queries via Grafana PostgreSQL datasource         │
│                                                             │
│  Feedback Loop Analyzer (cron every 6h)                     │
│  - Writes to monitoring.diversity_alerts                    │
│  - Reports in ~/.claude/reports/feedback-loops/             │
└─────────────────────────────────────────────────────────────┘
```

### Component Installation

**Prometheus (pi-02):**
```bash
# Install
sudo dnf install -y prometheus

# Configure
sudo vim /etc/prometheus/prometheus.yml
# Add scrape targets (see below)

# Enable and start
sudo systemctl enable prometheus
sudo systemctl start prometheus

# Verify
curl http://localhost:9090/-/healthy
```

**Prometheus Configuration:**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'fleet_nodes'
    static_configs:
      - targets:
        - 'server-01:9100'
        - 'server-02:9100'
        - 'server-03:9100'
        - 'laptop-01:9100'
        - 'pi-01:9100'
        - 'pi-02:9100'
        - 'desktop-ap:9100'
        - 'server-ap:9100'
        - 'aio-01:9100'

  - job_name: 'grafana'
    static_configs:
      - targets: ['localhost:3000']
```

**Node Exporter (all fleet nodes):**
```bash
# Install
sudo dnf install -y golang-github-prometheus-node-exporter

# Enable and start
sudo systemctl enable node_exporter
sudo systemctl start node_exporter

# Verify
curl http://localhost:9100/metrics | head -20
```

**Grafana (pi-02):**
```bash
# Install
sudo dnf install -y grafana

# Enable and start
sudo systemctl enable grafana-server
sudo systemctl start grafana-server

# Verify
curl http://localhost:3000/api/health
```

**Grafana Data Sources:**

1. **Prometheus:**
   - Type: Prometheus
   - URL: http://localhost:9090
   - Access: Server (default)

2. **PostgreSQL:**
   - Type: PostgreSQL
   - Host: laptop-01:5432
   - Database: learning
   - User: claude
   - Password: `<from secrets>`
   - SSL Mode: disable
   - PostgreSQL Version: 16

---

## Key Metrics

### Infrastructure Metrics (Prometheus)

**CPU:**
```promql
# CPU usage per node
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Fleet-wide average CPU
avg(100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))

# High CPU nodes (>80%)
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
```

**Memory:**
```promql
# Memory usage per node
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))

# Fleet-wide memory pressure
avg(100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)))

# Low memory nodes (<1GB available)
node_memory_MemAvailable_bytes < 1073741824
```

**Disk:**
```promql
# Disk usage per node
100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)

# Disk I/O rate
rate(node_disk_io_time_seconds_total[5m])

# High disk usage (>85%)
100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100) > 85
```

**Network:**
```promql
# Network receive rate (MB/s)
rate(node_network_receive_bytes_total{device!="lo"}[5m]) / 1024 / 1024

# Network transmit rate (MB/s)
rate(node_network_transmit_bytes_total{device!="lo"}[5m]) / 1024 / 1024

# Network errors
rate(node_network_receive_errs_total[5m]) + rate(node_network_transmit_errs_total[5m])
```

### Application Metrics (PostgreSQL)

**Workflow Execution:**
```sql
-- Executions last hour
SELECT COUNT(*) as executions_last_hour
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Success rate last 24h
SELECT 
  100.0 * SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) / COUNT(*) as success_rate
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Average execution time
SELECT AVG(total_duration_ms) as avg_duration_ms
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Active workflows (last 5 min)
SELECT COUNT(*) as active_workflows
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '5 minutes'
  AND outcome IS NULL;
```

**Model Performance:**
```sql
-- Executions by model (last 24h)
SELECT 
  model,
  COUNT(*) as executions,
  AVG(duration_ms) as avg_duration_ms,
  AVG(confidence) as avg_confidence
FROM workflow.worker_results
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY executions DESC;

-- Model distribution (prevent dominance)
SELECT 
  model,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY percentage DESC;

-- Slow models (>95th percentile)
SELECT 
  model,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms
FROM workflow.worker_results
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY p95_duration_ms DESC;
```

**Database Health:**
```sql
-- Connection count
SELECT COUNT(*) as connections
FROM pg_stat_activity
WHERE datname = 'learning';

-- Active queries
SELECT COUNT(*) as active_queries
FROM pg_stat_activity
WHERE state = 'active' AND datname = 'learning';

-- Long-running queries (>30s)
SELECT 
  pid,
  now() - query_start as duration,
  query
FROM pg_stat_activity
WHERE state = 'active' 
  AND now() - query_start > interval '30 seconds'
  AND datname = 'learning';

-- Table sizes
SELECT 
  schemaname || '.' || tablename as table,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname IN ('learning', 'monitoring', 'workflow')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Cache hit ratio (should be >99%)
SELECT 
  SUM(heap_blks_hit) / (SUM(heap_blks_hit) + SUM(heap_blks_read)) * 100 as cache_hit_ratio
FROM pg_statio_user_tables
WHERE schemaname IN ('learning', 'monitoring', 'workflow');
```

### Cost Metrics (PostgreSQL)

**API Costs:**
```sql
-- Cost by model (last 24h)
SELECT 
  model,
  SUM(total_cost) as cost_usd,
  SUM(input_tokens) as input_tokens,
  SUM(output_tokens) as output_tokens
FROM costs.entries
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY cost_usd DESC;

-- Hourly cost trend (last 24h)
SELECT 
  DATE_TRUNC('hour', timestamp) as hour,
  SUM(total_cost) as cost_usd
FROM costs.entries
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;

-- Monthly cost projection
SELECT 
  SUM(total_cost) * 30 as projected_monthly_cost_usd
FROM costs.entries
WHERE timestamp > NOW() - INTERVAL '24 hours';

-- Most expensive workflows
SELECT 
  w.workflow_name,
  SUM(wr.cost_usd) as total_cost_usd
FROM workflow.worker_results wr
JOIN workflow.executions w ON wr.workflow_execution_id = w.id
WHERE wr.created_at > NOW() - INTERVAL '24 hours'
GROUP BY w.workflow_name
ORDER BY total_cost_usd DESC
LIMIT 10;
```

### Safety Metrics (Feedback Loop Detection)

**Model Diversity:**
```sql
-- Check for dominance (>70%)
SELECT 
  model,
  COUNT(*) as executions,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage,
  CASE 
    WHEN ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) > 70 THEN 'ALERT: DOMINANCE'
    WHEN ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) > 50 THEN 'WARNING'
    ELSE 'OK'
  END as status
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY percentage DESC;
```

**Eval-Gen Coupling:**
```sql
-- Models evaluating own outputs (should be <40%)
-- This requires workflow instrumentation to track arbiter vs worker
-- Placeholder query:
SELECT 
  'eval_gen_coupling_check' as metric,
  'MANUAL_CHECK_REQUIRED' as status;
-- TODO: Implement tracking in workflow.worker_results
```

**Recent Alerts:**
```sql
-- High-severity diversity alerts
SELECT 
  alert_type,
  severity,
  description,
  timestamp
FROM monitoring.diversity_alerts
WHERE timestamp > NOW() - INTERVAL '24 hours'
  AND severity > 0.6
ORDER BY severity DESC, timestamp DESC;

-- Alert count by type
SELECT 
  alert_type,
  COUNT(*) as count,
  MAX(severity) as max_severity
FROM monitoring.diversity_alerts
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY alert_type
ORDER BY max_severity DESC;
```

---

## Grafana Dashboards

### Dashboard 1: Fleet Overview

**Purpose:** Real-time fleet health and utilization

**Panels:**

1. **Fleet Status** (Stat panel)
   - Metric: Count of reachable nodes
   - Query: `count(up{job="fleet_nodes"} == 1)`
   - Threshold: Red if <6 nodes

2. **Average CPU Usage** (Gauge)
   - Query: `avg(100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))`
   - Threshold: >80% warning, >90% critical

3. **Average Memory Usage** (Gauge)
   - Query: `avg(100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)))`
   - Threshold: >85% warning, >95% critical

4. **CPU per Node** (Graph)
   - Query: `100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
   - Legend: `{{instance}}`

5. **Memory per Node** (Graph)
   - Query: `100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))`
   - Legend: `{{instance}}`

6. **Disk Usage** (Bar gauge)
   - Query: `100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)`
   - Display: Horizontal bar per node

7. **Network I/O** (Graph)
   - Query RX: `rate(node_network_receive_bytes_total{device!="lo"}[5m]) / 1024 / 1024`
   - Query TX: `rate(node_network_transmit_bytes_total{device!="lo"}[5m]) / 1024 / 1024`
   - Y-axis: MB/s

**Export:** `docs/grafana-dashboards/fleet-overview.json`

---

### Dashboard 2: Model Performance

**Purpose:** Track model execution patterns and quality

**Panels:**

1. **Executions Last Hour** (Stat)
   - Data source: PostgreSQL
   - Query: 
     ```sql
     SELECT COUNT(*) FROM workflow.executions 
     WHERE created_at > NOW() - INTERVAL '1 hour'
     ```

2. **Success Rate (24h)** (Gauge)
   - Query:
     ```sql
     SELECT 
       100.0 * SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) / COUNT(*) 
     FROM workflow.executions
     WHERE created_at > NOW() - INTERVAL '24 hours'
     ```
   - Threshold: <90% warning, <80% critical

3. **Model Distribution** (Pie chart)
   - Query:
     ```sql
     SELECT model, COUNT(*) as count
     FROM monitoring.execution_summary
     WHERE timestamp > NOW() - INTERVAL '7 days'
     GROUP BY model
     ```
   - Alert if one slice >70%

4. **Execution Time by Model** (Bar chart)
   - Query:
     ```sql
     SELECT model, AVG(duration_ms) as avg_ms
     FROM workflow.worker_results
     WHERE created_at > NOW() - INTERVAL '24 hours'
     GROUP BY model
     ```

5. **Confidence by Model** (Graph)
   - Query:
     ```sql
     SELECT 
       $__time(created_at),
       model,
       AVG(confidence) as avg_confidence
     FROM workflow.worker_results
     WHERE $__timeFilter(created_at)
     GROUP BY $__time(created_at), model
     ORDER BY 1,2
     ```

6. **Workflow Success Rate** (Table)
   - Query:
     ```sql
     SELECT 
       workflow_name,
       COUNT(*) as total,
       100.0 * SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) / COUNT(*) as success_rate
     FROM workflow.executions
     WHERE created_at > NOW() - INTERVAL '24 hours'
     GROUP BY workflow_name
     ORDER BY total DESC
     ```

7. **Active Workflows** (Stat)
   - Query:
     ```sql
     SELECT COUNT(*)
     FROM workflow.executions
     WHERE created_at > NOW() - INTERVAL '5 minutes'
       AND outcome IS NULL
     ```

**Export:** `docs/grafana-dashboards/model-performance.json`

---

### Dashboard 3: Cost Analysis

**Purpose:** Track API costs and optimize spending

**Panels:**

1. **Cost Last 24h** (Stat)
   - Query:
     ```sql
     SELECT SUM(total_cost)
     FROM costs.entries
     WHERE timestamp > NOW() - INTERVAL '24 hours'
     ```
   - Format: $ USD

2. **Monthly Projection** (Stat)
   - Query:
     ```sql
     SELECT SUM(total_cost) * 30
     FROM costs.entries
     WHERE timestamp > NOW() - INTERVAL '24 hours'
     ```
   - Format: $ USD
   - Threshold: Warning at projected $500/month

3. **Cost by Model** (Pie chart)
   - Query:
     ```sql
     SELECT model, SUM(total_cost) as cost
     FROM costs.entries
     WHERE timestamp > NOW() - INTERVAL '24 hours'
     GROUP BY model
     ```

4. **Hourly Cost Trend** (Graph)
   - Query:
     ```sql
     SELECT 
       $__time(DATE_TRUNC('hour', timestamp)),
       SUM(total_cost) as cost
     FROM costs.entries
     WHERE $__timeFilter(timestamp)
     GROUP BY 1
     ORDER BY 1
     ```

5. **Token Usage** (Graph)
   - Query:
     ```sql
     SELECT 
       $__time(DATE_TRUNC('hour', timestamp)),
       SUM(input_tokens) as input,
       SUM(output_tokens) as output
     FROM costs.entries
     WHERE $__timeFilter(timestamp)
     GROUP BY 1
     ORDER BY 1
     ```

6. **Most Expensive Workflows** (Table)
   - Query:
     ```sql
     SELECT 
       w.workflow_name,
       SUM(wr.cost_usd) as total_cost,
       COUNT(*) as executions,
       SUM(wr.cost_usd) / COUNT(*) as avg_cost_per_exec
     FROM workflow.worker_results wr
     JOIN workflow.executions w ON wr.workflow_execution_id = w.id
     WHERE wr.created_at > NOW() - INTERVAL '24 hours'
     GROUP BY w.workflow_name
     ORDER BY total_cost DESC
     LIMIT 10
     ```

7. **Cost per Model per Workflow** (Heatmap)
   - Query:
     ```sql
     SELECT 
       w.workflow_name,
       wr.model,
       SUM(wr.cost_usd) as cost
     FROM workflow.worker_results wr
     JOIN workflow.executions w ON wr.workflow_execution_id = w.id
     WHERE wr.created_at > NOW() - INTERVAL '24 hours'
     GROUP BY w.workflow_name, wr.model
     ```

**Export:** `docs/grafana-dashboards/cost-analysis.json`

---

### Dashboard 4: Feedback Loop Safety

**Purpose:** Detect and prevent self-referential feedback loops

**Panels:**

1. **Latest Analysis Status** (Stat)
   - Data source: File (read from `~/.claude/reports/feedback-loops/latest.json`)
   - Display: "HEALTHY" or "AT RISK"
   - Color: Green if no risks >0.6, Yellow if 0.6-0.8, Red if >0.8

2. **Model Dominance** (Gauge)
   - Query:
     ```sql
     SELECT MAX(percentage) as max_pct
     FROM (
       SELECT 
         model,
         100.0 * COUNT(*) / SUM(COUNT(*)) OVER () as percentage
       FROM monitoring.execution_summary
       WHERE timestamp > NOW() - INTERVAL '7 days'
       GROUP BY model
     ) sub
     ```
   - Threshold: >70% critical, >50% warning

3. **Recent Alerts** (Table)
   - Query:
     ```sql
     SELECT 
       alert_type,
       severity,
       description,
       timestamp
     FROM monitoring.diversity_alerts
     WHERE timestamp > NOW() - INTERVAL '24 hours'
     ORDER BY severity DESC, timestamp DESC
     LIMIT 20
     ```

4. **Alert Severity Over Time** (Graph)
   - Query:
     ```sql
     SELECT 
       $__time(DATE_TRUNC('hour', timestamp)),
       alert_type,
       MAX(severity) as max_severity
     FROM monitoring.diversity_alerts
     WHERE $__timeFilter(timestamp)
     GROUP BY 1, alert_type
     ORDER BY 1, 2
     ```

5. **Model Distribution Trend** (Stacked area chart)
   - Query:
     ```sql
     SELECT 
       $__time(DATE_TRUNC('hour', timestamp)),
       model,
       COUNT(*) as executions
     FROM monitoring.execution_summary
     WHERE $__timeFilter(timestamp)
     GROUP BY 1, model
     ORDER BY 1, 2
     ```
   - Format: Percentage stacked

6. **Thompson Sampling State** (Table)
   - Query:
     ```sql
     SELECT 
       strategy,
       successes,
       failures,
       avg_reward,
       last_updated
     FROM learning.strategy_performance
     ORDER BY avg_reward DESC
     ```

7. **Embedding Similarity** (Gauge)
   - Query: (Manual calculation required)
   - Display: Average cosine similarity of recent outputs
   - Threshold: >0.90 critical, >0.85 warning

**Export:** `docs/grafana-dashboards/feedback-loop-safety.json`

---

## Alerting Rules

### Critical Alerts (PagerDuty / Email)

**Database Down:**
```yaml
alert: DatabaseDown
expr: up{job="postgresql"} == 0
for: 1m
labels:
  severity: critical
annotations:
  summary: "PostgreSQL is down on {{ $labels.instance }}"
  description: "Database unreachable for 1 minute"
```

**High Model Dominance:**
```sql
-- Alert rule (check via cron)
SELECT 
  model,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY model
HAVING ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) > 70;

-- If returns rows, trigger alert
```

**Feedback Loop Critical:**
```bash
# Alert rule (feedback loop monitor script)
python3 tools/feedback_loop_optimizer.py --window 7 --quiet
EXIT_CODE=$?
if [ $EXIT_CODE -eq 2 ]; then
  # Critical severity >0.8 detected
  # Send PagerDuty alert
fi
```

**Backup Failure:**
```bash
# Alert rule (check in cron after backup)
LATEST_BACKUP=$(ls -t /mnt/backups/laptop-01-learning/learning_*.sql.gz 2>/dev/null | head -1)
BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))

if [ $BACKUP_AGE -gt 25 ]; then
  # No backup in last 25 hours
  # Send alert
fi
```

### Warning Alerts (Email / Slack)

**High CPU Usage:**
```yaml
alert: HighCPU
expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 90
for: 5m
labels:
  severity: warning
annotations:
  summary: "High CPU on {{ $labels.instance }}"
  description: "CPU usage >90% for 5 minutes"
```

**Low Memory:**
```yaml
alert: LowMemory
expr: node_memory_MemAvailable_bytes < 1073741824  # <1GB
for: 5m
labels:
  severity: warning
annotations:
  summary: "Low memory on {{ $labels.instance }}"
  description: "Available memory <1GB for 5 minutes"
```

**High Disk Usage:**
```yaml
alert: HighDiskUsage
expr: 100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100) > 85
for: 10m
labels:
  severity: warning
annotations:
  summary: "High disk usage on {{ $labels.instance }}"
  description: "Disk usage >85% for 10 minutes"
```

**Low Success Rate:**
```sql
-- Alert rule (check via cron every 15 min)
SELECT 
  100.0 * SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) / COUNT(*) as success_rate
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '1 hour'
HAVING success_rate < 90;

-- If returns rows, send alert
```

### Info Alerts (Slack / Dashboard)

**New Fleet Node Added:**
- Trigger: New entry in `~/.claude/fleet-nodes.txt`
- Action: Post to Slack

**Monthly Cost Trend:**
- Trigger: Monthly projection >20% higher than previous month
- Action: Dashboard annotation + email to finance

**Model Performance Degradation:**
```sql
-- Alert rule (check daily)
WITH current AS (
  SELECT model, AVG(confidence) as avg_conf
  FROM workflow.worker_results
  WHERE created_at > NOW() - INTERVAL '24 hours'
  GROUP BY model
),
baseline AS (
  SELECT model, AVG(confidence) as avg_conf
  FROM workflow.worker_results
  WHERE created_at BETWEEN NOW() - INTERVAL '8 days' AND NOW() - INTERVAL '7 days'
  GROUP BY model
)
SELECT c.model, c.avg_conf, b.avg_conf
FROM current c
JOIN baseline b ON c.model = b.model
WHERE c.avg_conf < b.avg_conf * 0.9;  -- 10% degradation

-- If returns rows, send info alert
```

---

## Feedback Loop Monitoring

### Automated Analysis (Every 6 Hours)

**Cron Job:**
```bash
0 */6 * * * /home/claude/bin/monitor-feedback-loops.sh
```

**Script:** `~/bin/monitor-feedback-loops.sh`
```bash
#!/bin/bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 tools/feedback_loop_optimizer.py --window 7 --output ~/.claude/reports/feedback-loops/latest.json

EXIT_CODE=$?
if [ $EXIT_CODE -eq 2 ]; then
  # Critical severity >0.8
  echo "CRITICAL: Feedback loop severity >0.8" | mail -s "ALERT: Feedback Loop" team@example.com
elif [ $EXIT_CODE -eq 1 ]; then
  # High severity 0.6-0.8
  echo "WARNING: Feedback loop severity 0.6-0.8" | mail -s "WARNING: Feedback Loop" team@example.com
fi
```

### Manual Analysis

```bash
# Run immediate analysis
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 tools/feedback_loop_optimizer.py --window 7

# Custom window
python3 tools/feedback_loop_optimizer.py --window 30 --output /tmp/monthly-analysis.json

# View specific risks
cat ~/.claude/reports/feedback-loops/latest.json | jq '.risks[] | select(.severity > 0.6)'

# Check model distribution
cat ~/.claude/reports/feedback-loops/latest.json | jq '.model_distribution'
```

### Interpreting Results

**Risk Types:**

1. **model_dominance:** One model >70% usage
   - **Severity:** `(percentage - 50) / 50`
   - **Action:** Force rotation, exclude dominant model temporarily

2. **eval_gen_coupling:** Model evaluating own outputs >40%
   - **Severity:** `coupling_rate / 40`
   - **Action:** Enforce arbiter ≠ worker constraint

3. **reward_hacking:** Quality up + diversity down
   - **Severity:** `correlation strength`
   - **Action:** Enable adversarial evaluation

4. **concept_collapse:** Output similarity >0.90
   - **Severity:** `(similarity - 0.80) / 0.20`
   - **Action:** Increase task diversity, temperature

**Severity Thresholds:**
- **<0.4:** Normal variation, no action
- **0.4-0.6:** Monitor trend
- **0.6-0.8:** High risk, take action within 24h
- **>0.8:** Critical, immediate intervention

---

## Performance Baselines

### Expected Performance (95th Percentile)

| Metric | Baseline | Warning | Critical |
|--------|----------|---------|----------|
| **CPU per node** | 60% | 80% | 90% |
| **Memory per node** | 70% | 85% | 95% |
| **Disk usage** | 60% | 85% | 95% |
| **DB query latency** | 0.4ms | 1ms | 5ms |
| **Workflow success rate** | 98% | 90% | 80% |
| **Model distribution (max)** | 30% | 50% | 70% |
| **API cost per day** | $10 | $50 | $100 |

### Capacity Limits

| Resource | Current | Max Capacity | Scale Trigger |
|----------|---------|--------------|---------------|
| **Fleet nodes** | 8 | 16 | >80% utilization |
| **Database size** | <10GB | 500GB | >100GB |
| **Workflow executions/hour** | ~100 | ~500 | >400 sustained |
| **PostgreSQL connections** | ~20 | 100 | >80 |

---

## Troubleshooting Dashboards

### Quick Health Check Dashboard

**Single-page status:**

```
┌─────────────────────────────────────────────┐
│ SYSTEM HEALTH                               │
├─────────────────────────────────────────────┤
│ Database:          [●] UP                   │
│ Fleet Nodes:       [●] 8/8                  │
│ Backups:           [●] <2h ago              │
│ Feedback Loops:    [●] Healthy              │
├─────────────────────────────────────────────┤
│ Last Hour:                                  │
│   Executions:      127                      │
│   Success Rate:    99.2%                    │
│   API Cost:        $0.43                    │
├─────────────────────────────────────────────┤
│ Resource Usage:                             │
│   Avg CPU:         [▓▓▓▓░░░░░░] 42%        │
│   Avg Memory:      [▓▓▓▓▓▓░░░░] 63%        │
│   Disk (max):      [▓▓▓▓▓░░░░░] 54%        │
└─────────────────────────────────────────────┘
```

**Grafana Query:**
```json
{
  "panels": [
    {"title": "Database Status", "query": "up{job=\"postgresql\"}"},
    {"title": "Fleet Nodes", "query": "count(up{job=\"fleet_nodes\"} == 1)"},
    {"title": "Executions Last Hour", "query": "SELECT COUNT(*) FROM workflow.executions WHERE created_at > NOW() - INTERVAL '1 hour'"},
    ...
  ]
}
```

---

## Custom Queries

### Most Active Workflows
```sql
SELECT 
  workflow_name,
  COUNT(*) as executions,
  AVG(total_duration_ms) as avg_duration,
  100.0 * SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) / COUNT(*) as success_rate
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY workflow_name
ORDER BY executions DESC
LIMIT 10;
```

### Slowest Models
```sql
SELECT 
  model,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
  COUNT(*) as executions
FROM workflow.worker_results
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY p95_duration_ms DESC;
```

### Cost Efficiency (Cost per Success)
```sql
SELECT 
  w.workflow_name,
  SUM(wr.cost_usd) / NULLIF(SUM(CASE WHEN wr.outcome = 'success' THEN 1 ELSE 0 END), 0) as cost_per_success
FROM workflow.worker_results wr
JOIN workflow.executions w ON wr.workflow_execution_id = w.id
WHERE wr.created_at > NOW() - INTERVAL '24 hours'
GROUP BY w.workflow_name
ORDER BY cost_per_success DESC
LIMIT 10;
```

### Database Cache Hit Ratio
```sql
SELECT 
  SUM(heap_blks_hit) as cache_hits,
  SUM(heap_blks_read) as disk_reads,
  ROUND(100.0 * SUM(heap_blks_hit) / NULLIF(SUM(heap_blks_hit) + SUM(heap_blks_read), 0), 2) as cache_hit_pct
FROM pg_statio_user_tables
WHERE schemaname IN ('learning', 'monitoring', 'workflow');
```

### Fleet Node Uptime
```promql
# Uptime per node (seconds)
time() - node_boot_time_seconds

# Uptime per node (days)
(time() - node_boot_time_seconds) / 86400
```

### Thompson Sampling Bandit Win Rates
```sql
SELECT 
  strategy,
  successes,
  failures,
  ROUND(100.0 * successes / NULLIF(successes + failures, 0), 2) as win_rate_pct,
  avg_reward
FROM learning.strategy_performance
ORDER BY avg_reward DESC;
```

---

## Dashboard Maintenance

### Weekly Tasks

```bash
# 1. Review dashboard performance
# Check slow queries in Grafana query inspector

# 2. Update baseline values
# If performance improved, update warning/critical thresholds

# 3. Archive old snapshots
# Grafana > Dashboards > Snapshots > Delete snapshots >30 days
```

### Monthly Tasks

```bash
# 1. Export dashboard backups
curl -H "Authorization: Bearer <grafana-api-key>" \
  http://pi-02:3000/api/dashboards/uid/<dashboard-uid> > backup.json

# 2. Review alert noise
# Adjust thresholds for frequently-triggered alerts

# 3. Add new panels for emerging patterns
# Based on recent incidents or optimizations
```

---

**Last Updated:** 2026-07-03  
**Version:** 1.0.0  
**Maintained By:** Fleet Operations Team
