# Grafana Fleet Monitoring Dashboard

Comprehensive monitoring dashboard for the 5-machine distributed fleet (aio-01, server-01, server-02, server-03, pi-02).

## Overview

The **Fleet Monitoring Dashboard** provides real-time visibility into system performance across all fleet machines:
- **Host Availability** - Uptime status and reboot detection
- **Resource Usage** - CPU, Memory, Disk, Network metrics
- **Performance Indicators** - Load averages, context switches, swap usage
- **Hardware Specifications** - CPU count, memory capacity per host

**Design Philosophy:** Health-at-a-glance + drill-down capability. All 14 panels feed into alert thresholds configured in Prometheus alert rules.

## Quick Import

```bash
# Option 1: Import via Grafana UI
1. Grafana Home → Create → Import
2. Paste contents of grafana-dashboard-fleet.json
3. Select Prometheus datasource
4. Click Import

# Option 2: Direct HTTP import (if Grafana is accessible)
curl -X POST http://aio-01:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana-dashboard-fleet.json
```

## Dashboard Panels (14 total)

### Row 1: Fleet Overview

#### Panel 1: Fleet Host Status (Up/Down)
- **Type:** Pie chart
- **Metric:** `up{job="node"}`
- **Purpose:** At-a-glance health status of all 5 fleet machines
- **Healthy State:** 5 active hosts (100% up)
- **Alert Trigger:** One or more hosts down → see Alertmanager

#### Panel 2: CPU Usage by Host
- **Type:** Stat (latest value with color thresholds)
- **Metric:** `100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
- **Thresholds:**
  - Green: < 85%
  - Yellow: 85-95%
  - Red: > 95%
- **Purpose:** Instant view of CPU saturation per machine
- **Note:** Protects controller (aio-01) from NFS latency due to CPU pressure

#### Panel 3: Memory Usage by Host
- **Type:** Stat (latest value with color thresholds)
- **Metric:** `100 * (1 - ((node_memory_MemAvailable_bytes or ...) / node_memory_MemTotal_bytes))`
- **Thresholds:**
  - Green: < 85%
  - Yellow: 85-95%
  - Red: > 95%
- **Purpose:** Instant memory saturation per machine
- **Special Note:** pi-02 (1GB RAM) threshold should be monitored closely

### Row 2: Trends (5-minute averages)

#### Panel 4: CPU Usage Trend
- **Type:** Time series (line chart)
- **Metric:** CPU % usage over time
- **Time Range:** Last 6 hours (default)
- **Legend:** Shows mean and max values

#### Panel 5: Memory Usage Trend
- **Type:** Time series (line chart)
- **Metric:** Memory % usage over time
- **Legend:** Shows mean and max values

#### Panel 6: Disk Usage Trend
- **Type:** Time series (line chart)
- **Metric:** Root filesystem (/) usage %
- **Thresholds:**
  - Green: < 80%
  - Yellow: 80-90%
  - Red: > 90%
- **Purpose:** Track filling rate; predicts 24-hour full disk

#### Panel 7: Load Average Trend
- **Type:** Time series (line chart)
- **Metrics:** node_load1, node_load5, node_load15
- **Purpose:** System responsiveness indicator
- **Alert Rule:** HighLoadAverage fires when > 2x CPU count for 15 minutes

### Row 3: Network Performance

#### Panel 8: Network Receive Rate
- **Type:** Time series (stacked area)
- **Metric:** `rate(node_network_receive_bytes_total{device!~"lo"}[5m])`
- **Unit:** Bytes/sec
- **Purpose:** Monitor inbound traffic saturation

#### Panel 9: Network Transmit Rate
- **Type:** Time series (stacked area)
- **Metric:** `rate(node_network_transmit_bytes_total{device!~"lo"}[5m])`
- **Unit:** Bytes/sec
- **Purpose:** Monitor outbound traffic saturation

#### Panel 10: Network Errors Rate
- **Type:** Time series (line chart)
- **Metrics:** RX/TX errors per second
- **Thresholds:**
  - Green: < 5 errors/sec
  - Yellow: 5-10 errors/sec
  - Red: > 10 errors/sec
- **Alert Rule:** HighNetworkErrors (> 10/sec = warning)

### Row 4: Advanced Metrics

#### Panel 11: Inode Usage
- **Type:** Time series (line chart)
- **Metric:** Percent of inodes used (root filesystem)
- **Thresholds:**
  - Green: < 80%
  - Yellow: 80-95%
  - Red: > 95%
- **Alert Rule:** DiskInodesLow fires at > 90%

#### Panel 12: Swap Usage
- **Type:** Time series (line chart)
- **Metric:** Percent of swap used
- **Thresholds:**
  - Green: < 25%
  - Yellow: 25-50%
  - Red: > 50%
- **Purpose:** Detect memory pressure
- **Alert Rule:** HighSwapUsage fires at > 50%

#### Panel 13: Context Switches Rate
- **Type:** Time series (line chart)
- **Metric:** Context switches per second
- **Purpose:** Indicator of CPU contention and thread scheduling pressure

#### Panel 14: Fleet Hardware Specifications
- **Type:** Table
- **Metrics:** CPU count, Memory (GB) per host
- **Purpose:** Reference spec sheet for capacity planning

## Template Variables

### Host Filter
- **Variable:** `$instance`
- **Type:** Multi-select query
- **Query:** `label_values(node_cpu_count, instance)`
- **Default:** All hosts
- **Usage:** Filter specific host for detailed analysis

**Example Usage:**
```promql
# Filter CPU to single host
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", instance=~"$instance"}[5m])) * 100)
```

## Performance Optimization

### Refresh Rate
- **Default:** 30 seconds
- **Recommendation:** Keep at 30s for balance between freshness and Prometheus load
- **For Real-Time Ops:** Change to 10s (uses 3x more resources)

### Time Range
- **Default:** Last 6 hours
- **Retention Policy:** 15 days (see monitoring/README.md)
- **For Incident Analysis:** Extend to 7-14 days

### Query Optimization
All PromQL queries use:
- **Rate intervals:** 5 minutes (minimizes noise)
- **Aggregation:** `by (instance)` to isolate per-host metrics
- **Filters:** `device!~"lo"` to exclude loopback network interface

## Integration with Alerting

Dashboard thresholds **mirror** Prometheus alert rules:

| Alert Rule | Dashboard Threshold | Duration | Severity |
|-----------|-------------------|----------|----------|
| HighCpuUsage | > 85% | 10m | Warning |
| CriticalCpuUsage | > 95% | 5m | Critical |
| HighMemoryUsage | > 85% | 10m | Warning |
| CriticalMemoryUsage | > 95% | 5m | Critical |
| DiskSpaceLow | > 80% | instant | Warning |
| DiskSpaceCritical | > 90% | instant | Critical |
| DiskInodesLow | > 90% | instant | Warning |
| HighNetworkErrors | > 10/sec | instant | Warning |
| HighLoadAverage | > 2x CPUs | 15m | Warning |
| HighSwapUsage | > 50% | instant | Warning |

**Key Principle:** If a dashboard panel is red → check Alertmanager for active alerts.

## Customization for Your Fleet

### Adjust Thresholds
1. Edit `grafana-dashboard-fleet.json`
2. Update `steps` in `fieldConfig.overrides.thresholds`
3. Re-import dashboard

**Example: CPU threshold for specific host**
```json
"thresholds": {
  "mode": "absolute",
  "steps": [
    {"color": "green", "value": null},
    {"color": "yellow", "value": 75},      // Lower for pi-02
    {"color": "red", "value": 90}
  ]
}
```

### Add Custom Panels

#### Memory Breakdown Panel
```promql
# Cache + Buffer estimation
node_memory_Cached_bytes + node_memory_Buffers_bytes
```

#### Disk I/O Panel
```promql
# Read/Write rates
rate(node_disk_reads_completed_total[5m])
rate(node_disk_writes_completed_total[5m])
```

#### Process Count Panel
```promql
# Total running processes
node_processes_running
```

### Machine-Specific Dashboards

Create separate dashboards by role:

**aio-01 (Controller) Dashboard:**
- Focus on Prometheus + Alertmanager performance
- Monitor NFS server metrics
- Track memory budget (3.75GB cap)

**Worker Nodes Dashboard:**
- Job execution time
- Task queue depth
- Memory per role

**pi-02 (Sentinel) Dashboard:**
- Memory pressure (1GB limit)
- CPU thermal throttling
- Swap usage (critical)

## Troubleshooting

### Panel Shows "No data"
1. Check Prometheus connectivity: `curl http://aio-01:9090/-/healthy`
2. Verify scrape targets: `http://aio-01:9090/targets`
3. Run query manually in Prometheus UI: `http://aio-01:9090/graph`

### Metrics Missing for Specific Host
```bash
# Check if node_exporter is running
ssh server-01 'systemctl status node_exporter'

# Verify firewall allows 9100/tcp
ssh server-01 'sudo firewall-cmd --list-ports'

# Test scrape endpoint directly
curl http://server-01:9100/metrics | head -20
```

### Dashboard Too Slow
- Reduce refresh rate: 30s → 60s
- Shorten time window: 6h → 3h
- Disable 2-3 least-used panels (hide via panel menu)

### Thresholds Not Reflecting Alerts
- Verify `prometheus.yml` has correct `alerting` section
- Check Alertmanager status: `curl http://aio-01:9093/api/v1/alerts`
- Reload Prometheus config: `curl -X POST http://aio-01:9090/-/reload`

## Multi-AI Design Notes

**Dashboard Design from:**
- **Opus:** Comprehensive metric selection, threshold calibration, layout strategy
- **Sonnet:** Network error detection, inode monitoring, template variables
- **Haiku:** Performance tuning, query optimization, refresh rate analysis

**Design Principles:**
1. **Single Pane of Glass** - Overview all 5 hosts instantly
2. **Threshold Alignment** - Dashboard mirrors alert rules
3. **Drill-Down Capability** - Zoom into trends and time ranges
4. **ARM-Aware** - Special handling for pi-02 (1GB, ARMv7)
5. **Fleet-Centric** - Labels for role/arch/capacity in legends

## Related Documentation

- [Fleet Monitoring README](./README.md) - Installation and architecture
- [Prometheus Alert Rules](./install-prometheus.sh) - 21 alert rules across 7 groups
- [Node Exporter Reference](https://github.com/prometheus/node_exporter) - Metric definitions
- [Grafana Docs](https://grafana.com/docs/) - Dashboard design patterns

## Export & Backup

```bash
# Export dashboard as JSON (for version control)
curl -s http://aio-01:3000/api/dashboards/uid/fleet-monitoring \
  -H "Authorization: Bearer YOUR-API-TOKEN" | jq '.dashboard' > dashboard-backup.json

# Re-import after changes
curl -X POST http://aio-01:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR-API-TOKEN" \
  -d @dashboard-backup.json
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-13 | Initial dashboard with 14 panels, 5-host fleet support |

---

**Dashboard UID:** `fleet-monitoring`  
**Data Source:** Prometheus  
**Refresh Rate:** 30s  
**Time Range:** Last 6 hours  
**Retention Policy:** 15 days (Prometheus), 24 hours (Grafana default)
