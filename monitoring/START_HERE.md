# Grafana Fleet Monitoring Dashboard - START HERE

Complete monitoring solution for your 5-machine distributed fleet.

## What You Got

A production-ready Grafana dashboard with:
- **14 panels** monitoring all system metrics (CPU, memory, disk, network)
- **Automated import script** (one command to set up)
- **Complete documentation** (quick start to deep technical details)
- **Full alert integration** (connects to your Prometheus alert rules)

## Get It Running (5 minutes)

```bash
cd monitoring
./import-dashboard.sh
```

That's it! Your dashboard will be at: **http://aio-01:3000/d/fleet-monitoring**

## What Each File Does

### To Use (3 files)
- `grafana-dashboard-fleet.json` - The dashboard (import this)
- `import-dashboard.sh` - How to import it (run this)
- `validate-dashboard.sh` - Check if JSON is valid (optional)

### To Read (4 docs)
- `DASHBOARD_QUICKSTART.md` - Get running in 3 min (start here!)
- `DASHBOARD_GUIDE.md` - Complete technical reference (when you need details)
- `DASHBOARD_SUMMARY.md` - Why we designed it this way (for architects)
- `DASHBOARD_INDEX.md` - Find what you need (navigation guide)

## 3-Minute Import (Choose One)

### Option 1: Automated (Easiest)
```bash
./import-dashboard.sh
```
- Auto-detects Grafana
- Creates datasource if needed
- Handles authentication

### Option 2: Manual UI (Slowest)
1. Open http://aio-01:3000
2. Create → Import
3. Upload `grafana-dashboard-fleet.json`
4. Select "Prometheus" datasource
5. Click Import

### Option 3: curl (Most Control)
```bash
curl -X POST http://aio-01:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana-dashboard-fleet.json
```

## Verify It Works

After importing, check:
1. Open dashboard: http://aio-01:3000/d/fleet-monitoring
2. Do you see **5 green segments** in the pie chart? (all hosts up)
3. Do the trend graphs show data? (not "No data")
4. Does the host dropdown list all 5 machines?

If yes → **You're done!** Go use your dashboard.

If no → See DASHBOARD_QUICKSTART.md Troubleshooting section.

## What You Can See

**Real-time Health (Top Row)**
- Fleet status at a glance (all 5 hosts up/down)
- CPU % per machine (green/yellow/red)
- Memory % per machine (green/yellow/red)

**Trends Over Time (Middle Rows)**
- How CPU/memory/disk change hour by hour
- Network traffic in and out
- System load and saturation

**Deep Details (Bottom Rows)**
- Disk inode usage (running out of files?)
- Swap memory (in danger?)
- Network errors (bad cables?)
- Hardware specs (CPU/memory reference)

## Common Tasks

### Q: How do I adjust alert thresholds?
See DASHBOARD_GUIDE.md → "Customization" section

### Q: Can I see just one machine?
Yes! Use the "Host" dropdown at the top to filter

### Q: I want to monitor different metrics
Edit the JSON file, validate it, re-import. See DASHBOARD_SUMMARY.md

### Q: Something isn't working
1. Run `./validate-dashboard.sh` to check JSON
2. Read DASHBOARD_QUICKSTART.md Troubleshooting
3. Try `./import-dashboard.sh --dry-run --verbose`

## Files on Disk

```
monitoring/
├── START_HERE.md                      ← You are here!
├── grafana-dashboard-fleet.json       The dashboard
├── import-dashboard.sh                Run this to import
├── validate-dashboard.sh              Check JSON validity
├── DASHBOARD_QUICKSTART.md            5-min read for setup
├── DASHBOARD_GUIDE.md                 Full technical details
├── DASHBOARD_SUMMARY.md               Design decisions
├── DASHBOARD_INDEX.md                 Navigation guide
└── README.md                          Fleet architecture
```

## Key Thresholds

**When a panel turns yellow/red**, check Alertmanager for alerts:

| Metric | Green | Yellow | Red | Alert |
|--------|-------|--------|-----|-------|
| CPU | <85% | 85-95% | >95% | CriticalCpuUsage |
| Memory | <85% | 85-95% | >95% | CriticalMemory |
| Disk | <80% | 80-90% | >90% | DiskCritical |
| Network Errors | <5/s | 5-10/s | >10/s | HighNetworkErrors |
| Swap | <25% | 25-50% | >50% | HighSwapUsage |

All thresholds are designed to match your Prometheus alert rules.

## Your Fleet

Dashboard monitors 5 machines:

| Machine | Role | CPU | RAM | Notes |
|---------|------|-----|-----|-------|
| aio-01 | Controller | 2C | 7GB | Runs Prometheus/Grafana |
| server-01 | Worker | 4C | 32GB | Main workload |
| server-02 | Worker | 4C | 32GB | Main workload |
| server-03 | Worker | 4C | 32GB | Main workload |
| pi-02 | Sentinel | 1C | 1GB | Low resource warning! |

Special case: **pi-02** has only 1GB RAM, so memory alerts are tighter (>70% triggers)

## Quick Links

**Access Your Monitoring:**
- Dashboard: http://aio-01:3000/d/fleet-monitoring
- Prometheus: http://aio-01:9090
- Alertmanager: http://aio-01:9093

**Read the Docs:**
- Quick Start: DASHBOARD_QUICKSTART.md (5 min)
- Deep Details: DASHBOARD_GUIDE.md (30 min)
- Architecture: DASHBOARD_SUMMARY.md (20 min)

**Test & Validate:**
```bash
./validate-dashboard.sh          # Check JSON
./import-dashboard.sh --dry-run  # Simulate import
curl http://aio-01:3000/api/health  # Check Grafana
```

## Next Steps

1. **Right now:** Run `./import-dashboard.sh`
2. **Next:** Open http://aio-01:3000/d/fleet-monitoring
3. **Then:** Read DASHBOARD_QUICKSTART.md if you have questions
4. **Later:** Customize thresholds or add panels as needed

## Support

**Can't import?**
- Try `./import-dashboard.sh --help`
- Check `./import-dashboard.sh --dry-run --verbose`
- Read DASHBOARD_QUICKSTART.md Troubleshooting

**Don't understand a metric?**
- Check DASHBOARD_GUIDE.md for that panel
- Look at DASHBOARD_INDEX.md for quick reference

**Want to customize?**
- Read DASHBOARD_SUMMARY.md Customization section
- Edit JSON, validate with `./validate-dashboard.sh`
- Re-import

## Status

✓ Production-Ready (tested on real fleet)
✓ Supports all 5 machines (aio-01, server-01/02/03, pi-02)
✓ 14 comprehensive panels
✓ Fully documented (4 guides + index)
✓ Easy to customize and extend

**Created:** 2026-06-13  
**Version:** 1.0  
**Last Updated:** 2026-06-13

---

**Ready to start?**

```bash
./import-dashboard.sh
```

Then open: http://aio-01:3000/d/fleet-monitoring

That's it! Your dashboard is live.
