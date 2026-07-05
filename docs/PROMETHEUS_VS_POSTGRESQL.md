# QUICK REFERENCE: Prometheus vs PostgreSQL in Grafana

## 🔍 Visual Identification in Grafana UI

### When Editing a Panel:

```
┌─────────────────────────────────────────┐
│ Panel Settings                          │
├─────────────────────────────────────────┤
│ Datasource: [Prometheus ▼]  ← LOOK HERE│
│                                         │
│ Query:                                  │
│ rate(fleet_node_cpu[5m])   ← PromQL    │
└─────────────────────────────────────────┘

vs

┌─────────────────────────────────────────┐
│ Panel Settings                          │
├─────────────────────────────────────────┤
│ Datasource: [PostgreSQL ▼]  ← LOOK HERE│
│                                         │
│ Query:                                  │
│ SELECT * FROM api_usage    ← SQL        │
└─────────────────────────────────────────┘
```

## 📝 Query Language Cheat Sheet

| Feature | Prometheus (PromQL) | PostgreSQL (SQL) |
|---------|---------------------|------------------|
| **Metric/Table** | `fleet_node_cpu_usage` | `FROM api_usage` |
| **Filtering** | `{node="server-01"}` | `WHERE node = 'server-01'` |
| **Time range** | `[5m]` or `[1h]` | `INTERVAL '5 minutes'` |
| **Rate of change** | `rate(metric[5m])` | `(value - lag(value)) / time_diff` |
| **Aggregation** | `sum by (label)` | `GROUP BY column` |
| **Functions** | `rate()`, `increase()` | `COUNT()`, `SUM()`, `AVG()` |
| **Time column** | Implicit (timestamp) | `timestamp` or `created_at` |

## 🎯 What Each System Has

### PROMETHEUS Metrics (from fleet-exporter :9091)
```
fleet_node_reachable           - 0 or 1 (up/down)
fleet_node_cpu_usage          - percentage
fleet_node_load_1m            - load average
fleet_node_ram_used_bytes     - bytes
fleet_node_claude_processes   - count
fleet_exporter_errors_total   - counter
```

**Check available:** http://aio-01:9091/metrics

### POSTGRESQL Tables (database: learning)
```
api_usage                      - Every API call
  ├─ worker_id
  ├─ provider (groq, openai, etc)
  ├─ model
  ├─ prompt_tokens
  ├─ completion_tokens  
  ├─ cost_usd
  ├─ latency_ms
  └─ timestamp

monitoring.execution_summary   - Orchestrator runs
monitoring.model_selections    - Model choice decisions
costs.entries                  - Cost aggregations
fleet.workers                  - Worker registry
```

**Check available:** 
```bash
ssh root@aio-01 "psql -h aio-01 -p 5433 -U claude -d learning -c '\dt monitoring.*'"
```

## 🔎 Quick Tests

### Test Prometheus:
```bash
# See all metrics
curl http://aio-01:9091/metrics

# Query via Prometheus
curl 'http://aio-01:9090/api/v1/query?query=fleet_node_reachable'
```

### Test PostgreSQL:
```bash
ssh root@aio-01 "psql -h aio-01 -p 5433 -U claude -d learning -c \
  'SELECT COUNT(*) FROM api_usage;'"
```

## 🎨 Examples from Your Dashboards

### Current Dashboards Use PROMETHEUS ONLY:
```json
{
  "title": "Model Request Rate",
  "datasource": null,  ← defaults to Prometheus
  "targets": [{
    "expr": "rate(ai_model_requests_total[5m])"  ← PromQL
  }]
}
```

### To Add PostgreSQL Panel:
```json
{
  "title": "API Costs by Provider",
  "datasource": "PostgreSQL",  ← explicit
  "targets": [{
    "rawSql": "SELECT provider, SUM(cost_usd) as cost FROM api_usage WHERE $__timeFilter(timestamp) GROUP BY provider"
  }]
}
```

## ⚡ When You See This in Grafana:

### PROMETHEUS indicators:
- ✅ Metric names with underscores: `fleet_node_cpu_usage`
- ✅ Square bracket time ranges: `[5m]`, `[1h]`
- ✅ Functions: `rate()`, `increase()`, `sum()`
- ✅ Curly brace labels: `{job="fleet-exporter"}`
- ✅ No FROM keyword

### POSTGRESQL indicators:
- ✅ SQL keywords: `SELECT`, `FROM`, `WHERE`, `GROUP BY`
- ✅ Table names with dots: `monitoring.execution_summary`
- ✅ INTERVAL syntax: `INTERVAL '1 hour'`
- ✅ Column names: `timestamp`, `cost_usd`, `provider`
- ✅ Has FROM clause

## 💡 Pro Tip

**In Grafana query editor:**
- Click the datasource dropdown at the top
- If it says "Prometheus" or "Default" → Prometheus
- If it says "PostgreSQL" → PostgreSQL
- The query syntax will automatically change based on selection!
