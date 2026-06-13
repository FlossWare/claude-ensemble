# Fleet Monitoring Dashboard - Quick Start

Get your dashboard running in 3 minutes.

## Prerequisites

- Grafana installed on aio-01 (via `install-grafana.sh`)
- Prometheus running on aio-01 (via `install-prometheus.sh`)
- Node exporters deployed to all 5 fleet machines
- Network access to aio-01:3000 (Grafana) and aio-01:9090 (Prometheus)

**Verify setup:**
```bash
curl -s http://aio-01:3000/api/health | jq .
curl -s http://aio-01:9090/api/v1/targets | jq '.data | length'
```

## Option 1: Automated Import (Recommended)

```bash
cd monitoring
chmod +x import-dashboard.sh
./import-dashboard.sh
```

**Output:**
```
[2026-06-13 14:32:15] [INFO]  Starting dashboard import process...
[2026-06-13 14:32:16] [INFO]  Grafana health check passed
[2026-06-13 14:32:17] [INFO]  Found existing Prometheus datasource with UID: prometheus
[2026-06-13 14:32:18] [INFO]  Dashboard imported successfully!
[2026-06-13 14:32:18] [INFO]  Dashboard ID: 1
[2026-06-13 14:32:18] [INFO]  Dashboard UID: fleet-monitoring
[2026-06-13 14:32:18] [INFO]  Access at: http://aio-01:3000/d/fleet-monitoring/fleet-monitoring-dashboard
```

**With Custom Credentials:**
```bash
./import-dashboard.sh \
  --host grafana.example.com:3000 \
  --user myuser \
  --password mypass
```

**With API Token:**
```bash
# Get API token from Grafana UI: Configuration → API Keys
./import-dashboard.sh --token YOUR-API-TOKEN
```

**Dry-Run (Validate Only):**
```bash
./import-dashboard.sh --dry-run --verbose
```

## Option 2: Manual Import via Grafana UI

1. **Open Grafana:**
   ```
   http://aio-01:3000
   ```

2. **Login** with `admin/admin` (change password on first login)

3. **Navigate to Dashboard Import:**
   - Click **Create** (+) in left sidebar
   - Select **Import**

4. **Upload Dashboard:**
   - **Option A:** Paste JSON
     - Copy contents of `grafana-dashboard-fleet.json`
     - Paste into "Import via panel JSON" textbox
   
   - **Option B:** Upload File
     - Click "Upload JSON file"
     - Select `grafana-dashboard-fleet.json`

5. **Configure Import:**
   - **Name:** Fleet Monitoring Dashboard (auto-filled)
   - **Datasource:** Select "Prometheus" from dropdown
   - Click **Import**

6. **Access Dashboard:**
   ```
   http://aio-01:3000/d/fleet-monitoring/fleet-monitoring-dashboard
   ```

## Option 3: Using curl

```bash
# Get Grafana API token (or use basic auth)
GRAFANA_TOKEN="YOUR-API-TOKEN"

# Import dashboard
curl -X POST http://aio-01:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  -d @grafana-dashboard-fleet.json
```

## Verify Dashboard Is Working

### Check All Panels Have Data
1. Open dashboard: http://aio-01:3000/d/fleet-monitoring
2. Look for **"No data"** messages on any panel
3. If any panel shows no data, run these diagnostics:

```bash
# Verify Prometheus targets
curl -s http://aio-01:9090/api/v1/targets | jq '.data.activeTargets[] | {instance: .labels.instance, state: .health}'

# Manually run a metric query
curl -s 'http://aio-01:9090/api/v1/query?query=up' | jq '.data.result[] | {instance: .metric.instance, value: .value[1]}'
```

### Test Individual Metrics
```bash
# CPU usage
curl -s 'http://aio-01:9090/api/v1/query?query=100%20-%20(avg%20by%20(instance)%20(irate(node_cpu_seconds_total%7Bmode%3D%22idle%22%7D%5B5m%5D))%20*%20100)' | jq

# Memory usage
curl -s 'http://aio-01:9090/api/v1/query?query=100%20*%20(1%20-%20((node_memory_MemAvailable_bytes%20or%20(node_memory_MemFree_bytes%20%2B%20node_memory_Buffers_bytes%20%2B%20node_memory_Cached_bytes))%20/%20node_memory_MemTotal_bytes))' | jq
```

## What Each Panel Shows

| Panel | What To Look For | Alert If |
|-------|------------------|----------|
| Fleet Host Status | Green pie = all 5 hosts up | Any host missing/red |
| CPU Usage | Green < 85%, Yellow 85-95%, Red > 95% | Red on any host |
| Memory Usage | Green < 85%, Yellow 85-95%, Red > 95% | Red on any host |
| CPU Trend | Flat lines = stable | Sharp spikes or sustained high usage |
| Memory Trend | Stable usage | Continuous climb toward 95% |
| Disk Usage | Trend below 90% | Crossing 80% or 90% thresholds |
| Load Average | Lines track CPU count | Exceeding 2x CPU count for 15+ min |
| Network RX/TX | Smooth curves | Sudden spikes or errors |
| Swap Usage | Near 0% | Any swap usage > 0% |

## Customize Thresholds

Edit dashboard in Grafana UI:

1. Click **Panel** title → **Edit**
2. Find **Standard Options** → **Thresholds**
3. Adjust color threshold steps (Green/Yellow/Red)
4. Click **Apply**

**Example: Adjust CPU threshold for pi-02 (more sensitive)**
- Green: < 75%
- Yellow: 75-85%
- Red: > 85%

## Set Up Alerts (Optional)

1. Go to dashboard panel (e.g., CPU Usage)
2. Click **Alert** tab (in panel editor)
3. Create alert rule based on metric threshold
4. Configure notification to Alertmanager or ntfy

**Example Alert:**
```
Condition: avg(cpu_usage) > 85%
Evaluate: Every 5 minutes
Duration: 10 minutes
Notify: ntfy (fleet-alerts channel)
```

## Troubleshooting

### Dashboard Import Fails
```bash
# Check Grafana logs
ssh aio-01 'sudo journalctl -u grafana-server -n 50'

# Verify Prometheus datasource exists
curl -s http://aio-01:3000/api/datasources | jq

# Try dry-run first
./import-dashboard.sh --dry-run --verbose
```

### Panels Show "No data"
```bash
# Check node_exporter on specific host
ssh server-01 'curl -s http://localhost:9100/metrics | grep node_cpu_count'

# Check Prometheus scrape config
curl -s http://aio-01:9090/api/v1/status/config | jq '.data.yaml' | grep -A 5 'job_name.*node'
```

### "Prometheus is not reachable" Error
```bash
# Verify Prometheus is running
ssh aio-01 'systemctl status prometheus'

# Check port 9090
ssh aio-01 'sudo netstat -tlnp | grep 9090'

# Test connectivity
curl -s http://aio-01:9090/api/v1/query?query=up | jq
```

### Authentication Failed
```bash
# Default credentials
Username: admin
Password: admin

# Reset password via Grafana CLI
ssh aio-01 'grafana-cli admin reset-admin-password newpassword'

# Or use API token instead
# Grafana UI → Configuration → API Keys → New API Key
```

## Next Steps

1. **Bookmark dashboard:** Add to browser favorites
   ```
   http://aio-01:3000/d/fleet-monitoring/fleet-monitoring-dashboard
   ```

2. **Share with team:** Click "Share" button in dashboard header
   - Public link (no authentication required)
   - Embed in wiki/docs

3. **Set up alerts:** Link dashboard panels to Alertmanager
   - See [monitoring/README.md](./README.md) for alert rule details

4. **Create additional dashboards:**
   - Per-host deep dives (server-01, server-02, etc.)
   - Application-specific metrics
   - Cost/capacity analysis

5. **Schedule reports:** Use Grafana Cloud or email plugin
   - Daily email with dashboard PNG
   - Weekly trend analysis

## File Reference

| File | Purpose |
|------|---------|
| `grafana-dashboard-fleet.json` | Dashboard definition (Grafana-compatible JSON) |
| `import-dashboard.sh` | Automated import script (recommended) |
| `DASHBOARD_GUIDE.md` | Complete documentation (technical details) |
| `DASHBOARD_QUICKSTART.md` | This file (quick reference) |
| `README.md` | Fleet monitoring architecture and setup |

## Get Help

- **Dashboard UI Help:** Click **?** icon in Grafana dashboard header
- **Prometheus Query Help:** Open Prometheus UI → click **?** in graph editor
- **Monitoring Issues:** See [README.md](./README.md) Troubleshooting section
- **Script Help:** `./import-dashboard.sh --help`

---

**Dashboard Version:** 1.0  
**Last Updated:** 2026-06-13  
**Metrics Source:** Prometheus (node_exporter)  
**Data Retention:** 15 days (Prometheus), Live dashboard (Grafana)
