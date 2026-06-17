# Grafana Dashboard - Complete Index

Quick navigation for all dashboard resources.

## Dashboard Files

| File | Size | Purpose |
|------|------|---------|
| `grafana-dashboard-fleet.json` | 31 KB | Dashboard definition (Grafana-compatible JSON) |
| `import-dashboard.sh` | 9.1 KB | Automated import script (recommended) |
| `validate-dashboard.sh` | 2.6 KB | Dashboard JSON validation utility |

## Documentation Files

| File | Purpose | Read When |
|------|---------|-----------|
| `DASHBOARD_QUICKSTART.md` | Get running in 3 minutes | First-time setup |
| `DASHBOARD_GUIDE.md` | Complete technical reference | Need details on any panel/metric |
| `DASHBOARD_SUMMARY.md` | Design decisions and overview | Want to understand the "why" |
| `DASHBOARD_INDEX.md` | This file - file navigation | Looking for something specific |

## Related Files

| File | Purpose |
|------|---------|
| `README.md` | Fleet monitoring architecture and setup |
| `install-grafana.sh` | Grafana installation script |
| `install-prometheus.sh` | Prometheus + Alertmanager setup |
| `install-node-exporter.sh` | Node exporter agent installation |
| `deploy-fleet-prometheus.sh` | Orchestrated fleet-wide deployment |

## Quick Links

### Getting Started (5 min)
```bash
cd monitoring
./import-dashboard.sh           # Auto-import to aio-01
# Access at http://aio-01:3000/d/fleet-monitoring
```

### Understanding the Dashboard (15 min)
1. Read: `DASHBOARD_QUICKSTART.md` - What each panel means
2. Import: `./import-dashboard.sh`
3. Access: http://aio-01:3000/d/fleet-monitoring

### Technical Deep Dive (30 min)
1. Read: `DASHBOARD_GUIDE.md` - Metrics, thresholds, optimization
2. Read: `DASHBOARD_SUMMARY.md` - Design decisions, customization
3. Check: `README.md` - Alert rule integration

### Customizing Thresholds (10 min)
1. Edit: `grafana-dashboard-fleet.json` (JSON threshold sections)
2. Validate: `./validate-dashboard.sh`
3. Import: `./import-dashboard.sh`

### Troubleshooting (varies)
1. Check: `DASHBOARD_QUICKSTART.md` Troubleshooting section
2. Verify: `./validate-dashboard.sh`
3. Debug: `./import-dashboard.sh --dry-run --verbose`
4. Read: `README.md` Fleet monitoring issues

## Dashboard Metrics at a Glance

### System Health (Panels 1-3)
- Fleet Host Status: Up/down pie chart (5 hosts)
- CPU Usage: Current % per host (Green/Yellow/Red)
- Memory Usage: Current % per host (Green/Yellow/Red)

### Trends (Panels 4-7)
- CPU Usage Trend: 5-min average over time
- Memory Usage Trend: 5-min average over time
- Disk Usage Trend: Root filesystem / usage
- Load Average Trend: 1min/5min/15min lines

### Network (Panels 8-10)
- Receive Rate: Inbound bytes/sec per device
- Transmit Rate: Outbound bytes/sec per device
- Network Errors: RX/TX errors/sec with thresholds

### Advanced (Panels 11-14)
- Inode Usage: Root filesystem inode %
- Hardware Specs: CPU/Memory table reference
- Swap Usage: Swap memory % (danger indicator)
- Context Switches: Scheduling pressure indicator

## Common Tasks

### Import Dashboard
**Time:** 5 minutes
```bash
./import-dashboard.sh
# or with custom credentials:
./import-dashboard.sh --host grafana.example.com --user myuser --password mypass
```

### Verify All Panels Have Data
**Time:** 2 minutes
1. Open http://aio-01:3000/d/fleet-monitoring
2. Look for "No data" on any panel
3. If found, run: `curl -s http://aio-01:9090/api/v1/targets | jq`

### Adjust Thresholds
**Time:** 10 minutes
1. Edit `grafana-dashboard-fleet.json`
2. Find `"thresholds"` sections
3. Adjust `"value"` fields for yellow/red levels
4. Save and re-import: `./import-dashboard.sh`

### Check Alert Rule Integration
**Time:** 5 minutes
1. Find alert name in `DASHBOARD_GUIDE.md` table
2. Open Prometheus: http://aio-01:9090/alerts
3. Verify rule is active
4. Verify Alertmanager has it: http://aio-01:9093

### Create Additional Dashboards
**Time:** 30 minutes per dashboard
1. Copy `grafana-dashboard-fleet.json`
2. Modify panels and thresholds for specific role (e.g., aio-01 controller)
3. Save with new UID (e.g., `"uid": "fleet-controller"`)
4. Import: `curl -X POST http://aio-01:3000/api/dashboards/db -d @new-dashboard.json`

## Key Thresholds Quick Reference

**CPU Usage:**
- Green: < 85%
- Yellow: 85-95%
- Red: > 95%
- Alert: CriticalCpuUsage (> 95% for 5min)

**Memory Usage:**
- Green: < 85%
- Yellow: 85-95%
- Red: > 95%
- Alert: CriticalMemoryUsage (> 95% for 5min)

**Disk Usage:**
- Green: < 80%
- Yellow: 80-90%
- Red: > 90%
- Alert: DiskSpaceCritical (> 90%)

**Network Errors:**
- Green: < 5/sec
- Yellow: 5-10/sec
- Red: > 10/sec
- Alert: HighNetworkErrors (> 10/sec)

## Troubleshooting Flowchart

```
Dashboard shows "No data"?
├─ Check Grafana health: curl http://aio-01:3000/api/health
├─ Check Prometheus: curl http://aio-01:9090/-/healthy
├─ Check targets: curl http://aio-01:9090/api/v1/targets | jq
│  └─ Missing hosts? → SSH to host, check node_exporter status
├─ Check datasource: Dashboard Settings → Data Sources
│  └─ Not found? → Create: Configuration → Data Sources → Prometheus
└─ Run validation: ./validate-dashboard.sh

Import fails?
├─ Try dry-run first: ./import-dashboard.sh --dry-run --verbose
├─ Check Grafana logs: ssh aio-01 'journalctl -u grafana-server -n 50'
├─ Validate JSON: ./validate-dashboard.sh
└─ Check auth: curl -u admin:admin http://aio-01:3000/api/user

Panel thresholds not matching alerts?
├─ Review thresholds in DASHBOARD_GUIDE.md table
├─ Check Prometheus alert rules: ssh aio-01 'cat /etc/prometheus/rules/*.yml'
├─ Sync thresholds: Edit JSON, re-import
└─ Reload Prometheus: curl -X POST http://aio-01:9090/-/reload
```

## File Purposes

### grafana-dashboard-fleet.json
**What it is:** Grafana dashboard definition in JSON format
**Who uses it:** Grafana when importing
**Why it exists:** Machine-readable format for dashboard configuration
**How to use:** Pass to import-dashboard.sh OR import manually in Grafana UI

### import-dashboard.sh
**What it is:** Bash script to automate dashboard setup
**Who uses it:** Fleet operators (you)
**Why it exists:** Zero-friction onboarding (no clicking around Grafana UI)
**How to use:** `./import-dashboard.sh`

### validate-dashboard.sh
**What it is:** Dashboard JSON validation tool
**Who uses it:** Developers/operators verifying custom dashboards
**Why it exists:** Catch JSON syntax errors before import
**How to use:** `./validate-dashboard.sh my-custom-dashboard.json`

### DASHBOARD_QUICKSTART.md
**What it is:** 7.5 KB quick reference for getting started
**Who reads it:** Anyone new to the dashboard
**Why it exists:** Fast path to seeing the dashboard work
**What to read:** First 2-3 minutes of your time

### DASHBOARD_GUIDE.md
**What it is:** 11 KB comprehensive technical documentation
**Who reads it:** Anyone needing details on metrics/thresholds
**Why it exists:** Complete reference for all 14 panels and features
**What to read:** When QUICKSTART doesn't answer your question

### DASHBOARD_SUMMARY.md
**What it is:** This-is-how-we-got-here design document
**Who reads it:** Architects, code reviewers, technical leads
**Why it exists:** Understand design decisions and rationale
**What to read:** When making changes or customizing extensively

### DASHBOARD_INDEX.md
**What it is:** This file - navigation guide
**Who reads it:** Anyone looking for something specific
**Why it exists:** Find the right file for your task
**What to read:** When you don't know where to start

## Multi-AI Design Details

See `DASHBOARD_GUIDE.md` and `DASHBOARD_SUMMARY.md` for:
- Opus contributions (comprehensive metrics, thresholds, layout)
- Sonnet contributions (network, inodes, templates, ARM)
- Haiku contributions (performance, optimization, quickstart)

## Version & Status

**Current Version:** 1.0  
**Created:** 2026-06-13  
**Status:** Production-Ready  
**Tested:** 14 panels on 5-host fleet  
**Retention:** 15 days (Prometheus), Live (Grafana)  
**Refresh:** 30 seconds

## Next Steps

1. **First time here?** → Read `DASHBOARD_QUICKSTART.md`
2. **Ready to import?** → Run `./import-dashboard.sh`
3. **Want details?** → Read `DASHBOARD_GUIDE.md`
4. **Customizing?** → Edit JSON, validate, re-import
5. **Troubleshooting?** → Check QUICKSTART Troubleshooting section

---

**Quick Access:**
- Dashboard: http://aio-01:3000/d/fleet-monitoring
- Prometheus: http://aio-01:9090
- Alertmanager: http://aio-01:9093
- Grafana Config: http://aio-01:3000/admin

