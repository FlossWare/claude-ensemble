# Grafana Dashboard - Quick Start Guide

## TL;DR - Get Going in 2 Minutes

```bash
# 1. Run the setup script (handles everything)
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/scripts
bash setup-grafana-monitoring.sh

# 2. Open in browser
http://aio-01:3000/d/fleet-node-activity/fleet-node-activity-dashboard

# 3. Done! Dashboard is now your default home page
```

## What Was Just Installed

✓ **Prometheus datasource** configured at http://aio-01:9091
✓ **Fleet Node Activity Dashboard** imported with 26 panels
✓ **Dashboard variables** for filtering by node/model/task/workflow
✓ **Default home dashboard** set to Fleet Node Activity

## Access Dashboard

**Quick URL:**
```
http://aio-01:3000/d/fleet-node-activity/fleet-node-activity-dashboard
```

**Via UI:**
1. Login to http://aio-01:3000 (admin/admin by default)
2. Click "Dashboards" → "Fleet Node Activity Dashboard"
3. It's also set as your home page when you log in

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│ Variables: [node▼] [model▼] [task_type▼] [workflow▼]   │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Row 1: Fleet Topology + Node Health Status (6 panels)   │
│  ├─ Fleet Topology Map (nodeGraph)                       │
│  ├─ laptop-01, aio-01, server-01/02/03, pi-02 Health    │
│                                                           │
│  Row 2: Performance Metrics (2 panels)                   │
│  ├─ CPU Utilization per Node (timeseries)               │
│  ├─ RAM Utilization per Node (timeseries)               │
│                                                           │
│  Row 3: Workload Analysis (8 panels)                    │
│  ├─ Active Workflows per Node                            │
│  ├─ AI Models Running (table)                            │
│  ├─ Task Distribution Heatmap                            │
│  ├─ Task Type Breakdown (pie)                            │
│  ├─ Workflow Timeline (Gantt)                            │
│  ├─ Network Traffic                                      │
│  ├─ NFS Latency & Throughput                             │
│                                                           │
│  Row 4: Cost Analysis (2 panels)                         │
│  ├─ Cost per Node (bar gauge)                            │
│  ├─ Cost Breakdown by Model (bar chart)                  │
│                                                           │
│  Row 5: Trends & KPIs (6 panels)                         │
│  ├─ Historical Workload Trends (timeseries)              │
│  ├─ Workload Heatmap by Hour (heatmap)                   │
│  ├─ Fleet Utilization (gauge)                            │
│  ├─ Worker Balance Score (gauge)                         │
│  ├─ Cost Efficiency (gauge)                              │
│  ├─ NFS Health (gauge)                                   │
│                                                           │
│  Row 6: Analytics & Logs (2 panels)                      │
│  ├─ Model Performance Leaderboard (table)                │
│  ├─ Alerts & Annotations Log (logs)                      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Common Tasks

### Change Time Range
Click time selector at top right (default: Last 7 days)
- Last hour: `1h`
- Last 24 hours: `24h`
- Last 7 days: `7d` (default)
- Custom: Click "Custom" for date range picker

### Filter by Node
Use dropdown: `[node▼]` at top
- Select specific nodes: server-01, laptop-01, etc.
- Default: All nodes

### Filter by AI Model
Use dropdown: `[model▼]` at top
- Select models: claude-opus-4, gpt-4o, etc.
- Default: All models

### Check Specific Metric
1. Click on any panel title
2. Click "Edit" or hover → Click panel actions
3. View/modify the PromQL query
4. Query format: `metric_name{labels}`

### Set Custom Refresh Rate
Click refresh icon (⟳) at top right → Select interval or "Custom"

## Required Metrics

Dashboard shows data from Prometheus metrics starting with:
- `fleet_*` — Fleet infrastructure metrics
- `ai_learning_*` — AI model execution metrics
- `node_*` — System metrics (CPU, memory, network)
- `ollama_*` — Ollama model metrics
- `nfs_*` — NFS performance metrics

If panels show "No data", verify:
1. Prometheus is running: `curl http://aio-01:9091/-/healthy`
2. Metrics are being exported: `curl http://aio-01:9091/metrics | grep fleet_`
3. Grafana can reach Prometheus: Go to Settings → Data Sources → Prometheus → Test

## Troubleshooting

### "No Data" in Panels

**Check Prometheus connectivity:**
```bash
curl http://aio-01:9091/-/healthy
curl 'http://aio-01:9091/api/v1/query?query=up'
```

**Check specific metrics:**
```bash
curl 'http://aio-01:9091/api/v1/query?query=fleet_node_info'
curl 'http://aio-01:9091/api/v1/query?query=node_cpu_seconds_total'
```

**Edit datasource:**
1. Gear icon (⚙️) → Settings → Data Sources
2. Click "Prometheus"
3. Change URL to http://aio-01:9091
4. Click "Save & Test"

### Variable Dropdowns Empty

Check if labels exist in Prometheus:
```bash
curl 'http://aio-01:9091/api/v1/labels'
curl 'http://aio-01:9091/api/v1/label/hostname/values'
curl 'http://aio-01:9091/api/v1/label/model/values'
```

### Can't Login

Default credentials: `admin` / `admin`

Reset password:
```bash
# Docker containers
docker exec <grafana-container> grafana-cli admin reset-admin-password newpassword

# Or via API
curl -X POST http://aio-01:3000/api/user/password/reset \
  -H "Content-Type: application/json" \
  -d '{"code": "reset-code", "newPassword": "newpassword"}'
```

## Key Metrics Explained

| Metric | Meaning | Threshold |
|--------|---------|-----------|
| CPU Utilization | % of CPU cores in use | 60% = warning, 80% = critical |
| Memory Utilization | % of available RAM in use | 80% = warning, 90% = critical |
| NFS Latency | ms to complete NFS operation | <50ms = good, >100ms = bad |
| Fleet Utilization | Weighted % of available compute | Target: 60-80% |
| Worker Balance | How evenly work is distributed | 1.0 = perfect, 0 = all on one |
| Cost Efficiency | Quality score per dollar | Higher is better |
| Model Quality Score | Normalized 0-1 quality metric | 0.8+ = good, <0.5 = investigate |

## Pro Tips

1. **Bookmark the dashboard**: Save `aio-01:3000/d/fleet-node-activity/...` to favorites
2. **Fullscreen a panel**: Click panel → Click expand (⤢ icon)
3. **Export PNG**: Click panel → More (⋯) → Export image
4. **Share dashboard**: Click arrow/share at top right
5. **Clone dashboard**: Gear icon (⚙️) → Save as
6. **Set alerts**: Click panel → Edit → "Alert" tab → Create threshold alert

## Next Steps

1. ✓ Dashboard is installed and running
2. ✓ Prometheus datasource is configured
3. **Next**: Ensure all metric exporters are sending data
4. **Next**: Configure alerting rules for critical thresholds
5. **Next**: Add custom panels for your specific metrics

## Documentation Links

- **Full Setup Guide**: GRAFANA_SETUP.md (this repo)
- **Grafana Official Docs**: https://grafana.com/docs/
- **Prometheus Docs**: https://prometheus.io/docs/
- **PromQL Cheatsheet**: https://prometheus.io/docs/prometheus/latest/querying/basics/

## Support

For issues with the dashboard:
1. Check GRAFANA_SETUP.md (Troubleshooting section)
2. Review Prometheus metrics: http://aio-01:9091/graph
3. Check Grafana logs: Docker logs or `/var/log/grafana/grafana.log`
4. Test datasource: Settings → Data Sources → Test

---

**Dashboard UID:** `fleet-node-activity`
**Created:** 2026-06-13
**Last Updated:** 2026-06-13
**Panels:** 26
**Variables:** 5
**Refresh Rate:** 30s
**Time Range:** Last 7 days (default)
