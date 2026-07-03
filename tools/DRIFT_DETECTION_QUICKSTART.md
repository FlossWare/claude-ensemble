# Drift Detection Quick Start

## Installation Check

```bash
# Verify dependencies
python3 -c "import numpy, scipy, psycopg2; print('✓ Dependencies OK')"

# Run validation tests
python3 tools/test_drift_detector.py
```

## Basic Usage

### 1. One-Time Analysis

```bash
# Analyze all models (last 30 days)
python3 tools/drift_detector.py --save-report --days 30

# Check specific model
python3 tools/drift_detector.py --model opus --days 30
```

**Output:**
- Console: Drift analysis summary
- File: `~/.claude/learning/drift_reports/latest_drift_report.json`

### 2. Database Integration (Recommended)

```bash
# Run analysis and store in PostgreSQL
node tools/drift_monitor_integration.cjs --once --days 30

# Query results
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT model, drift_type, severity, detected_at 
   FROM workflow.drift_detections 
   ORDER BY detected_at DESC LIMIT 10"
```

### 3. Continuous Monitoring

```bash
# Start continuous monitoring (checks every hour)
node tools/drift_monitor_integration.cjs --continuous --interval 3600

# Or use Python version
python3 tools/drift_detector.py --continuous --check-interval 3600
```

## Reading Results

### Console Output

```
=== Analyzing opus (145 time buckets) ===
  ⚠ DRIFT DETECTED: performance_degradation
  Severity: HIGH
  Affected metrics: quality, confidence
  Signal count: 3
```

### JSON Report

```bash
cat ~/.claude/learning/drift_reports/latest_drift_report.json | jq '.models.opus'
```

```json
{
  "drift_detected": true,
  "drift_type": "performance_degradation",
  "severity": "HIGH",
  "affected_metrics": ["quality", "confidence"],
  "signal_count": 3,
  "sample_count": 145,
  "drift_signals": [
    {
      "detector": "CUSUM",
      "metric": "quality",
      "index": 67,
      "magnitude": 5.234
    }
  ]
}
```

### Database Query

```sql
-- Unresolved drifts
SELECT model, drift_type, severity, detected_at
FROM workflow.drift_detections
WHERE resolved = FALSE
ORDER BY severity DESC, detected_at DESC;

-- Drift history for a model
SELECT detected_at, drift_type, severity, resolved
FROM workflow.drift_detections
WHERE model = 'opus'
ORDER BY detected_at DESC
LIMIT 20;
```

## Common Scenarios

### Scenario 1: Performance Degradation Detected

```bash
# 1. Run detailed analysis
python3 tools/drift_detector.py --model opus --days 30 --save-report

# 2. Validate with regression monitor
node tools/model_regression_monitor.cjs --weeks 4

# 3. Check unresolved drifts
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT * FROM workflow.drift_detections WHERE model = 'opus' AND resolved = FALSE"
```

### Scenario 2: Multiple Models Drifting

```bash
# 1. Run full analysis
node tools/drift_monitor_integration.cjs --once --days 7

# 2. Check severity breakdown
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT severity, COUNT(*) 
   FROM workflow.drift_detections 
   WHERE resolved = FALSE 
   GROUP BY severity"
```

### Scenario 3: Continuous Monitoring Setup

```bash
# Create systemd service
sudo cat > /etc/systemd/system/drift-monitor.service <<EOF
[Unit]
Description=Model Drift Continuous Monitoring
After=postgresql.service

[Service]
Type=simple
User=sfloess
WorkingDirectory=/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
ExecStart=/usr/bin/node tools/drift_monitor_integration.cjs --continuous --interval 3600
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable drift-monitor.service
sudo systemctl start drift-monitor.service

# Check status
sudo systemctl status drift-monitor.service
```

## Tuning

### Increase Sensitivity (Catch More Drift)

Edit `tools/drift_detector.py`:

```python
DRIFT_THRESHOLDS = {
    'cusum_threshold': 3.0,          # Default: 5.0
    'page_hinkley_threshold': 5.0,   # Default: 10.0
    'min_samples': 20,               # Default: 30
}
```

### Decrease Sensitivity (Reduce False Positives)

```python
DRIFT_THRESHOLDS = {
    'cusum_threshold': 10.0,         # Default: 5.0
    'page_hinkley_threshold': 20.0,  # Default: 10.0
    'min_samples': 50,               # Default: 30
}
```

## Troubleshooting

### "Insufficient samples" Error

```bash
# Check available data
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT model, COUNT(*) 
   FROM workflow.worker_results 
   WHERE created_at > NOW() - INTERVAL '30 days' 
   GROUP BY model"

# Reduce min_samples threshold or increase analysis window
python3 tools/drift_detector.py --days 60  # More data
```

### No Drift Detected (But You Expect It)

```bash
# Run with lower thresholds
# Edit DRIFT_THRESHOLDS in drift_detector.py (see Tuning above)

# Or check raw data distribution
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT 
     DATE_TRUNC('day', created_at) as day,
     AVG(quality_score) as avg_quality
   FROM workflow.worker_results
   WHERE model = 'opus' AND created_at > NOW() - INTERVAL '30 days'
   GROUP BY day
   ORDER BY day"
```

### Continuous Monitor Not Running

```bash
# Check systemd service
sudo systemctl status drift-monitor.service

# View logs
sudo journalctl -u drift-monitor.service -f

# Restart service
sudo systemctl restart drift-monitor.service
```

## Integration with Other Tools

### With Model Regression Monitor

```bash
# 1. Detect drift
node tools/drift_monitor_integration.cjs --once

# 2. Validate with regression testing
node tools/model_regression_monitor.cjs --weeks 4 --samples 5
```

### With Performance Dashboard

```bash
# Dashboard reads drift reports automatically
python3 tools/performance_dashboard.py

# View drift timeline
# (Opens web interface at http://localhost:8050)
```

### With Novelty Detector

```bash
# Drift detection: Performance over time
python3 tools/drift_detector.py --model opus

# Novelty detection: Task familiarity
python3 tools/novelty_detector.py
```

## Files and Locations

| File | Purpose |
|------|---------|
| `tools/drift_detector.py` | Core drift detection algorithms |
| `tools/drift_monitor_integration.cjs` | Database integration + orchestration |
| `tools/test_drift_detector.py` | Validation tests |
| `~/.claude/learning/drift_reports/latest_drift_report.json` | Most recent report |
| `~/.claude/learning/drift_reports/drift_detection_log.jsonl` | Historical log |
| `workflow.drift_detections` | PostgreSQL table |

## Next Steps

1. **Test:** Run validation tests (`python3 tools/test_drift_detector.py`)
2. **Analyze:** One-time analysis (`node tools/drift_monitor_integration.cjs --once`)
3. **Monitor:** Set up continuous monitoring (cron or systemd)
4. **Integrate:** Connect to alert system (Slack/email)
5. **Validate:** Use regression monitor on detected drifts

## Support

- **Documentation:** `docs/DRIFT_DETECTION_SYSTEM.md`
- **Logs:** `~/.claude/learning/drift_reports/drift_detection_log.jsonl`
- **Database:** `SELECT * FROM workflow.drift_detections`

---

**Quick Commands:**

```bash
# Health check
python3 tools/test_drift_detector.py

# One-time analysis
node tools/drift_monitor_integration.cjs --once

# Continuous monitoring
node tools/drift_monitor_integration.cjs --continuous --interval 3600

# Check unresolved drifts
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT model, severity, detected_at FROM workflow.drift_detections WHERE resolved = FALSE"
```
