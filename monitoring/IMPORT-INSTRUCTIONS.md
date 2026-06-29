# Grafana Dashboard Import Instructions

## Quick Import

### Method 1: Web UI (Recommended)

1. Open Grafana: http://pi-02:3000
2. Navigate to: **Dashboards** → **Import**
3. Click **Upload JSON file**
4. Select: `grafana-dashboard-consensus.json`
5. Configure data sources:
   - **PostgreSQL**: Select existing "learning@laptop-01" data source
   - **Prometheus**: Select existing "Prometheus" data source
6. Click **Import**

**Dashboard URL:** http://pi-02:3000/d/consensus-monitoring

---

### Method 2: CLI Import Script

Use existing import script:

```bash
cd monitoring
./import-dashboard.sh grafana-dashboard-consensus.json
```

**Requirements:**
- Grafana API key in `~/.grafana-api-key`
- OR environment variable: `export GRAFANA_API_KEY=<your-key>`

---

### Method 3: Provisioning (Permanent)

Copy to Grafana provisioning directory:

```bash
sudo cp grafana-dashboard-consensus.json /etc/grafana/provisioning/dashboards/
sudo systemctl restart grafana-server
```

**Auto-loads on Grafana restart** (survives upgrades)

---

## Before Import: Start Prometheus Exporter

The dashboard requires metrics from the Prometheus exporter:

```bash
cd monitoring
node prometheus-exporter.cjs &

# Verify metrics endpoint
curl http://localhost:9101/metrics | head -20
```

**Expected output:**
```
# HELP consensus_decisions_total Total consensus decisions (24h window)
# TYPE consensus_decisions_total counter
consensus_decisions_total 42
...
```

---

## Data Source Requirements

### PostgreSQL Data Source

**Must exist before import:**

- **Name:** PostgreSQL (or similar)
- **Host:** laptop-01:5432
- **Database:** learning
- **User:** sfloess
- **SSL Mode:** disable

**Test query:**
```sql
SELECT COUNT(*) FROM workflow.arbiter_decisions;
```

**If missing, create:**
1. Grafana → Configuration → Data Sources → Add data source
2. Select: **PostgreSQL**
3. Configure connection details above
4. Click **Save & Test**

### Prometheus Data Source

**Must exist before import:**

- **Name:** Prometheus
- **URL:** http://localhost:9090
- **Access:** Server (default)

**Test query:**
```promql
up{job="consensus-exporter"}
```

**If missing, create:**
1. Grafana → Configuration → Data Sources → Add data source
2. Select: **Prometheus**
3. URL: http://localhost:9090
4. Click **Save & Test**

---

## Post-Import Verification

### 1. Check Panel Data

Navigate to dashboard and verify each panel shows data:

- **Panel 1:** Consensus Decisions Per Minute (should show time series)
- **Panel 2:** Model Performance Trends (should show multiple model lines)
- **Panel 3:** Drift Alerts (table may be empty if no recent drift)
- **Panel 4:** Disagreement Score Distribution (pie chart with 4 slices)
- **Panel 5:** Cost Per Decision (stacked bars)
- **Panel 6:** Thompson Sampling Weights (donut chart)
- **Panel 7:** Human Review Queue Depth (stat, green if < 10)

### 2. Test Refresh

- Dashboard auto-refreshes every 30 seconds
- Manual refresh: Click refresh icon (top-right)
- Change time range: Click time picker (top-right)

### 3. Verify Prometheus Scrape

Check that Prometheus is collecting metrics:

```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="consensus-exporter")'
```

**Expected output:**
```json
{
  "discoveredLabels": {...},
  "labels": {"job": "consensus-exporter"},
  "scrapePool": "consensus-exporter",
  "scrapeUrl": "http://localhost:9101/metrics",
  "health": "up",
  "lastScrape": "2026-06-28T20:18:42.123Z"
}
```

---

## Troubleshooting

### "No data" on PostgreSQL panels

**Check data source connection:**
```bash
psql -h laptop-01 -U sfloess -d learning -c "SELECT COUNT(*) FROM workflow.arbiter_decisions"
```

**Verify schema exists:**
```bash
psql -h laptop-01 -U sfloess -d learning -c "\dt workflow.*"
```

**Check Grafana logs:**
```bash
sudo journalctl -u grafana-server -f
```

### "No data" on Prometheus panels

**Verify exporter is running:**
```bash
curl http://localhost:9101/health
# Expected: OK
```

**Check Prometheus targets:**
```bash
curl http://localhost:9090/targets
```

**Verify metrics exist:**
```bash
curl http://localhost:9101/metrics | grep consensus_decisions_total
```

### Import fails with "Dashboard with UID already exists"

**Solution 1:** Delete existing dashboard first
```bash
# Find dashboard by UID
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://pi-02:3000/api/dashboards/uid/consensus-monitoring

# Delete it
curl -X DELETE -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://pi-02:3000/api/dashboards/uid/consensus-monitoring
```

**Solution 2:** Change UID in JSON before import
```bash
jq '.uid = "consensus-monitoring-v2"' grafana-dashboard-consensus.json > dashboard-v2.json
```

---

## Next Steps After Import

1. **Pin dashboard to home:**
   - Click star icon (top-right)
   - Dashboard → Manage → Star

2. **Set as default dashboard:**
   - User → Preferences → Home Dashboard → Select "Consensus Monitoring"

3. **Create alerts:**
   - See `README-consensus-dashboard.md` for Prometheus alert rules

4. **Share with team:**
   - Dashboard → Share → Link (copy URL)
   - OR: Dashboard → Share → Snapshot (7-day expiry)

---

## Files

- `grafana-dashboard-consensus.json` - Dashboard definition
- `prometheus-exporter.cjs` - Metrics exporter
- `README-consensus-dashboard.md` - Full documentation
- `IMPORT-INSTRUCTIONS.md` - This file
