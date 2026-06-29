# Grafana Fleet Node Activity Dashboard Setup

Complete guide for importing the Fleet Node Activity Dashboard into Grafana with Prometheus datasource configuration.

## Overview

The Fleet Node Activity Dashboard provides real-time monitoring of your distributed AI learning fleet with:
- **6 nodes**: laptop-01 (Ollama), aio-01 (controller), server-01/02/03 (workers), pi-02 (sentinel)
- **26 monitoring panels** covering topology, performance, costs, and workload patterns
- **5 interactive variables** for filtering by node, model, task type, and workflow
- **Prometheus integration** for metric collection and alerting

## Quick Start (30 seconds)

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/scripts
bash setup-grafana-monitoring.sh
```

This will:
1. ✓ Configure Prometheus datasource at http://aio-01:9091
2. ✓ Import the Fleet Node Activity Dashboard
3. ✓ Set it as default home dashboard
4. ✓ Output access URL and troubleshooting steps

## Prerequisites

- Grafana running on aio-01:3000 (or override with `--grafana-host`)
- Prometheus running on aio-01:9091 (or override with `--prometheus-host`)
- Grafana admin credentials (default: admin/admin)
- Network connectivity from your workstation to aio-01

## Installation Methods

### Method 1: Automated Setup (Recommended)

```bash
bash scripts/setup-grafana-monitoring.sh \
  --grafana-host aio-01 \
  --grafana-port 3000 \
  --prometheus-host aio-01 \
  --prometheus-port 9091 \
  --admin-user admin \
  --admin-password your-password
```

### Method 2: Manual Setup

#### Step 1: Configure Prometheus Datasource

```bash
curl -X POST http://aio-01:3000/api/datasources \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://aio-01:9091",
    "access": "proxy",
    "isDefault": true,
    "jsonData": {
      "httpMethod": "GET",
      "customQueryParameters": ""
    }
  }'
```

Response includes datasource ID:
```json
{
  "id": 1,
  "uid": "prometheus",
  "name": "Prometheus",
  ...
}
```

#### Step 2: Import Dashboard

Save the dashboard JSON from `FLEET_NODE_ACTIVITY_DASHBOARD.json` to a file, then:

```bash
curl -X POST http://aio-01:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @FLEET_NODE_ACTIVITY_DASHBOARD.json
```

#### Step 3: Set as Default Home Dashboard

```bash
curl -X PATCH http://aio-01:3000/api/org/preferences \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "theme": "dark",
    "homeDashboardUID": "fleet-node-activity",
    "timezone": "browser"
  }'
```

## Dashboard Access

### Direct URL

```
http://aio-01:3000/d/fleet-node-activity/fleet-node-activity-dashboard
```

### Via Web UI

1. Open http://aio-01:3000
2. Login with admin credentials
3. Click "Dashboards" → "General" → "Fleet Node Activity Dashboard"

## Dashboard Panels (26 total)

### Infrastructure Monitoring (Panels 1-7)

| Panel | Type | Purpose | Metric |
|-------|------|---------|--------|
| Fleet Topology Map | Node Graph | Visual network layout | `fleet_node_info`, `fleet_connection` |
| laptop-01 Health | Stat | Ollama server status | `fleet_node_health` |
| aio-01 Health | Stat | Controller status | `fleet_node_health` |
| server-01/02/03 Health | Stat | Worker status (3 panels) | `fleet_node_health` |
| pi-02 Health | Stat | Sentinel status | `fleet_node_health` |

### Performance Metrics (Panels 8-9)

| Panel | Type | Purpose | Metric |
|-------|------|---------|--------|
| CPU Utilization per Node | Time Series | CPU usage % over time | `node_cpu_seconds_total` |
| RAM Utilization per Node | Time Series | Memory usage % + GB over time | `node_memory_MemAvailable_bytes`, `node_memory_MemTotal_bytes` |

### Workload Analysis (Panels 10-16)

| Panel | Type | Purpose | Metric |
|-------|------|---------|--------|
| Active Workflows per Node | Bar Gauge | Current workflow count | `fleet_active_workflows` |
| AI Models Running | Table | Models per node with status | `fleet_model_active`, `ollama_model_loaded` |
| Task Distribution Heatmap | Heatmap | Task completion over time | `fleet_tasks_completed_total` |
| Task Type Breakdown | Pie Chart | Task type distribution | `fleet_tasks_completed_total` |
| Workflow Timeline (Gantt) | State Timeline | Workflow execution states | `fleet_workflow_state` |
| Network Traffic | Node Graph | Network traffic volume | `node_network_transmit_bytes_total`, `node_network_receive_bytes_total` |
| NFS Latency & Throughput | Time Series | NFS performance | `nfs_request_duration_seconds_bucket`, `node_nfs_read_bytes_total` |

### Cost Analysis (Panels 17-18)

| Panel | Type | Purpose | Metric |
|-------|------|---------|--------|
| Cost per Node | Bar Gauge | Node cost in USD | `ai_learning_cost_usd`, `fleet_electricity_cost_estimate` |
| Cost Breakdown by Model | Bar Chart | Cost per model and node | `ai_learning_cost_usd` |

### Historical Trends & KPIs (Panels 19-25)

| Panel | Type | Purpose | Metric |
|-------|------|---------|--------|
| Historical Workload Trends | Time Series | Executions, cost, quality over time | `ai_learning_execution_total`, `ai_learning_cost_usd`, `ai_learning_quality_score` |
| Workload Heatmap by Hour | Heatmap | Usage pattern by hour of day | `ai_learning_execution_total` |
| Overall Fleet Utilization | Gauge | Weighted compute usage % | `node_cpu_seconds_total` (role=worker) |
| Worker Balance Score | Gauge | Work distribution evenness (0-1) | `fleet_tasks_completed_total` |
| Cost Efficiency | Gauge | Quality-per-dollar ratio | `ai_learning_quality_score`, `ai_learning_cost_usd` |
| NFS Health | Gauge | % time NFS latency < 50ms | `fleet_nfs_latency_ms` |
| Model Performance Leaderboard | Table | Models ranked by quality/cost/latency | Multiple metrics |

### Alerts (Panel 26)

| Panel | Type | Purpose | Metric |
|-------|------|---------|--------|
| Alerts and Annotations Log | Logs | Recent events and alerts | `fleet_alerts` job |

## Dashboard Variables

All variables are optional and filter all panels when changed:

```yaml
node:
  Type: Query (Prometheus label_values)
  Query: label_values(fleet_node_info, hostname)
  Multi-select: Yes (All by default)
  Filters: CPU, Memory, Workflows, etc.
  Example values: laptop-01, aio-01, server-01, server-02, server-03, pi-02

model:
  Type: Query
  Query: label_values(ai_learning_execution_total, model)
  Multi-select: Yes (All by default)
  Example values: claude-opus-4, claude-sonnet-4, claude-haiku-4, gpt-4o

task_type:
  Type: Query
  Query: label_values(ai_learning_execution_total, task_type)
  Multi-select: Yes (All by default)
  Example values: code-review, test, solve, learn

workflow:
  Type: Query
  Query: label_values(ai_learning_execution_total, workflow)
  Multi-select: Yes (All by default)
  Example values: ai-consensus, code-sdlc, ai-learning
```

## Metric Requirements

The dashboard expects these Prometheus metrics. If any are missing, those panels will show "No data":

### Fleet Infrastructure
```
fleet_node_info{hostname,role,ip,cpu_count,memory_gb}
fleet_node_health{hostname}
fleet_node_uptime_seconds{hostname}
fleet_active_workflows{hostname}
fleet_connection{source,dest,type}
fleet_model_active{hostname,model,status}
fleet_tasks_completed_total{hostname,task_type}
fleet_workflow_state{run_id,workflow,hostname,status}
fleet_nfs_latency_ms{}
fleet_electricity_cost_estimate{hostname}
```

### Node Metrics (Node Exporter)
```
node_cpu_seconds_total{hostname,mode}
node_memory_MemAvailable_bytes{hostname}
node_memory_MemTotal_bytes{hostname}
node_network_transmit_bytes_total{hostname}
node_network_receive_bytes_total{hostname}
node_nfs_read_bytes_total{hostname}
node_nfs_write_bytes_total{hostname}
```

### AI Learning Metrics
```
ai_learning_execution_total{model,hostname,task_type,workflow,status}
ai_learning_cost_usd{model,hostname}
ai_learning_quality_score{model}
ai_learning_success_rate{model}
ai_learning_duration_seconds{model}
ai_learning_model_selection_rate{model}
ai_learning_consensus_score{model}
```

### Ollama Metrics
```
ollama_model_loaded{hostname,model}
```

### NFS Metrics
```
nfs_request_duration_seconds_bucket{hostname,quantile}
fleet_nfs_bytes_total{source,dest}
```

## Configuration Options

### Time Range
Default: Last 7 days (now-7d to now)
Change: Click time selector at top right of dashboard

### Refresh Rate
Default: 30 seconds
Change: Click refresh icon at top right, or click dashboard settings (gear icon)

### Variables
Change: Use dropdowns at top of dashboard (if configured)

### Dashboard Settings
1. Click gear icon (⚙️) at top right
2. Edit JSON model, annotations, variables, or general settings

## Prometheus Queries Reference

### CPU Utilization
```promql
100 - (avg by(hostname) (rate(node_cpu_seconds_total{mode="idle",hostname=~"$node"}[5m])) * 100)
```

### Memory Utilization
```promql
(1 - (node_memory_MemAvailable_bytes{hostname=~"$node"} / node_memory_MemTotal_bytes{hostname=~"$node"})) * 100
```

### Active Workflows
```promql
count by(hostname) (fleet_active_workflows{hostname=~"$node"})
```

### NFS Latency (95th percentile)
```promql
histogram_quantile(0.95, rate(nfs_request_duration_seconds_bucket[5m]))*1000
```

### Total Cost
```promql
sum(ai_learning_cost_usd)
```

### Fleet Utilization
```promql
avg(100 - (avg by(hostname) (rate(node_cpu_seconds_total{mode="idle",role="worker"}[5m])) * 100)) / 100
```

## Troubleshooting

### "No data" in panels

**Check 1: Prometheus connectivity**
```bash
curl -s http://aio-01:9091/-/healthy
curl -s http://aio-01:9091/api/v1/query?query=up
```

**Check 2: Metrics being exported**
```bash
curl -s http://aio-01:9091/metrics | grep fleet_
curl -s http://aio-01:9091/metrics | grep ai_learning_
```

**Check 3: Datasource configuration**
1. Click gear icon (⚙️) on dashboard
2. Click "Datasources" in sidebar
3. Click "Prometheus"
4. Verify URL is http://aio-01:9091
5. Click "Save & Test"

### Metrics not showing
1. Verify metric exporters are running:
   - Node Exporter on each node (port 9100)
   - Prometheus scraping the metrics
2. Check Prometheus scrape targets: http://aio-01:9091/targets
3. Check for errors: http://aio-01:9091/alerts

### Dashboard variables not populating
1. Verify Prometheus can query labels:
   ```bash
   curl -s 'http://aio-01:9091/api/v1/label/hostname/values'
   curl -s 'http://aio-01:9091/api/v1/label/model/values'
   ```

2. Edit dashboard variables:
   - Click gear icon → Variables
   - Edit each variable
   - Change datasource if needed
   - Save and test query

### Permission errors
```bash
# Verify admin user exists and has correct password
curl -u admin:admin http://aio-01:3000/api/user
```

## Advanced Configuration

### Custom Thresholds

Edit any panel and adjust thresholds:
1. Click panel title
2. Click "Edit"
3. Go to "Field config" tab
4. Adjust "Thresholds" values and colors

Example CPU threshold:
- Yellow at 60%
- Red at 85%

### Custom Alerting

Create alerts based on panel queries:
1. Click panel → Edit
2. Go to "Alert" tab
3. Create alert rule with conditions
4. Choose notification channel

Example: Alert when aio-01 CPU > 80%

### Panel Customization

All panels are fully editable:
1. Click panel title
2. Click "Edit"
3. Modify query, visualization, or options
4. Click "Apply"

### Save Custom Dashboard

1. Make changes to dashboard
2. Click "Save dashboard" at top
3. Enter name, tags, description
4. Click "Save"

## Performance Tips

### Reduce Data Points
- Increase graph step interval in queries
- Reduce time range viewed

### Optimize Refresh Rate
- Increase refresh interval (top right)
- Disable refresh for static panels

### Filter with Variables
- Use node, model, task_type filters to reduce dataset size
- Especially helpful for large fleets

## Integration with Alerts

Connect to notification channels:
1. Go to Grafana → Alerting → Notification channels
2. Create channels: Slack, PagerDuty, Email, Webhook, etc.
3. Create alert rules from dashboard panels

Example Slack webhook:
```json
{
  "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "name": "Slack",
  "type": "slack",
  "send_resolved": true
}
```

## Dashboard Export/Backup

### Export Dashboard JSON
1. Click gear icon (⚙️)
2. Click "Settings" → "Save" option
3. Or use API:
```bash
curl -s http://aio-01:3000/api/dashboards/uid/fleet-node-activity \
  -u admin:admin | jq .dashboard > dashboard-backup.json
```

### Import Dashboard from Backup
```bash
curl -X POST http://aio-01:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @dashboard-backup.json
```

## Support & Documentation

- **Grafana Docs**: https://grafana.com/docs/
- **Prometheus Docs**: https://prometheus.io/docs/
- **Query Docs**: https://prometheus.io/docs/prometheus/latest/querying/basics/

## Next Steps

1. ✓ Dashboard is imported and configured
2. ✓ Prometheus datasource is set as default
3. ✓ Variables are configured for filtering
4. **Next**: Configure alerting rules for critical thresholds
5. **Next**: Set up notification channels (Slack, PagerDuty, etc.)
6. **Next**: Add custom panels for specific metrics
7. **Next**: Create dashboard copies for different teams

---

**Last Updated**: 2026-06-13
**Dashboard Version**: 1.0
**Prometheus Version Required**: 2.30+
**Grafana Version Required**: 8.0+
