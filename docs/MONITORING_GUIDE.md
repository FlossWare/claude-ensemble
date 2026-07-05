# Monitoring & Observability Guide

**Last Updated:** 2026-07-03  
**Status:** Dual-layer architecture (Prometheus + PostgreSQL)

## Quick Access

- **Grafana Dashboards:** http://aio-01:3000
- **Prometheus:** http://aio-01:9090
- **Fleet Metrics (raw):** http://aio-01:9091/metrics

## Architecture

```
┌─────────────────────────────────────────┐
│  API Proxy (aio-01:8002)                │
│  Every API call → PostgreSQL logging    │
└───────────────┬─────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────┐
│  PostgreSQL (aio-01:5433/learning)                    │
│  • api_usage - Every API call (452 rows)              │
│  • monitoring.execution_summary - Orchestrator runs   │
│  • monitoring.* - Fleet health, model selections      │
│  Retention: INDEFINITE                                │
└───────────────┬───────────────────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────┐
│  Fleet Prometheus Exporter (:9091)                    │
│  Reads PostgreSQL → Exposes Prometheus metrics        │
│  Updates: Every collection cycle                      │
└───────────────┬───────────────────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────┐
│  Prometheus (:9090)                                   │
│  Scrapes metrics every 15s                            │
│  Retention: 15 days                                   │
└───────────────┬───────────────────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────┐
│  Grafana (:3000)                                      │
│  Queries BOTH Prometheus AND PostgreSQL              │
│  • Prometheus: Real-time fleet metrics               │
│  • PostgreSQL: Historical analysis, cost tracking    │
└───────────────────────────────────────────────────────┘
```

## What to Use When

### Use Prometheus for:
- **Real-time monitoring:** Is a worker up RIGHT NOW?
- **Fleet health:** CPU, memory, load per node
- **Alerting:** Set thresholds on metrics
- **Live dashboards:** Auto-refresh every 15s
- **Infrastructure status:** How many Claude processes running?

**Example queries:**
```promql
# Workers currently reachable
fleet_node_reachable{node="server-01"}

# CPU usage across all workers
avg(fleet_node_cpu_usage)

# Alert if any worker is down
fleet_node_reachable < 1
```

### Use PostgreSQL for:
- **Historical analysis:** All API calls from last month
- **Cost tracking:** Total spend per model/provider
- **Debugging:** Find exactly which call failed and why
- **Detailed forensics:** Worker ID, tokens, latency per request
- **Complex queries:** JOIN across multiple monitoring tables

**Example queries:**
```sql
-- Total cost by provider last week
SELECT provider, COUNT(*), SUM(cost_usd) 
FROM api_usage 
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY provider;

-- Most expensive API calls
SELECT worker_id, model, cost_usd, prompt_tokens, completion_tokens
FROM api_usage
ORDER BY cost_usd DESC
LIMIT 10;

-- Failed executions analysis
SELECT model, outcome, COUNT(*)
FROM monitoring.execution_summary
WHERE outcome != 'success'
GROUP BY model, outcome;
```

## Current Data

**PostgreSQL:**
- 452 total API calls
- $0.0725 total cost
- 62 calls in last hour
- 14 unique models used

**Providers tracked:**
- Groq: 265 calls ($0.072)
- Cache: 162 calls (free)
- OpenRouter: 15 calls
- Cerebras: 6 calls ($0.00015)
- Cohere: 3 calls

**Fleet nodes monitored:**
- server-01, server-02, server-03
- laptop-01, pi-01, pi-02
- desktop-ap, server-ap

## Service Status

Check if all monitoring components are running:

```bash
ssh root@aio-01 "systemctl status \
  fleet-prometheus-exporter \
  prometheus \
  grafana-server"
```

Restart monitoring stack:

```bash
ssh root@aio-01 "systemctl restart \
  fleet-prometheus-exporter \
  prometheus \
  grafana-server"
```

## Troubleshooting

**No data in Grafana dashboards:**
1. Check if services are running (see above)
2. Verify Prometheus is scraping: http://aio-01:9090/targets
3. Check PostgreSQL datasource in Grafana settings
4. View raw metrics: http://aio-01:9091/metrics

**Fleet exporter failing:**
```bash
ssh root@aio-01 "journalctl -u fleet-prometheus-exporter -n 50"
```

**PostgreSQL connection issues:**
```bash
ssh root@aio-01 "psql -h aio-01 -p 5433 -U claude -d learning -c 'SELECT 1;'"
```

**Verify data is being logged:**
```bash
ssh root@aio-01 "psql -h aio-01 -p 5433 -U claude -d learning -c \
  'SELECT COUNT(*) FROM api_usage WHERE timestamp > NOW() - INTERVAL \"1 hour\";'"
```

## Configuration Files

- **Fleet exporter service:** `/etc/systemd/system/fleet-prometheus-exporter.service`
- **Fleet exporter code:** `/opt/claude-monitoring/fleet-prometheus-exporter.js`
- **Prometheus config:** `/etc/prometheus/prometheus.yml`
- **Grafana datasources:** `/etc/grafana/provisioning/datasources/`
- **Grafana dashboards:** `/var/lib/grafana/dashboards/`

## Adding Custom Metrics

To add new metrics from PostgreSQL to Prometheus, edit:
`/opt/claude-monitoring/fleet-prometheus-exporter.js`

Then restart:
```bash
ssh root@aio-01 "systemctl restart fleet-prometheus-exporter"
```

## Database Schema

**Key tables:**
- `api_usage` - Every API call logged by proxy
- `monitoring.execution_summary` - Orchestrator execution logs
- `monitoring.model_selections` - Which model was selected and why
- `costs.entries` - Aggregated cost tracking
- `fleet.workers` - Worker registration and heartbeats

See full schema:
```bash
ssh root@aio-01 "psql -h aio-01 -p 5433 -U claude -d learning -c '\dt monitoring.*'"
```
