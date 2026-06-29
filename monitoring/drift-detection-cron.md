# Model Performance Drift Detection - Cron Setup Guide

**Purpose:** Automated daily monitoring of model performance degradation.

**Created:** 2026-06-28

---

## Quick Start

### 1. Apply Database Schema

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning PGUSER=sfloess psql -f monitoring/schema-drift-detection.sql
```

**Expected output:**
```
CREATE SCHEMA
CREATE TABLE
CREATE INDEX
...
✅ Drift detection schema created successfully
```

### 2. Test Manual Execution

```bash
# Run drift detection manually
node monitoring/check-drift.cjs

# Expected output (when no data):
# ✅ No drift detected. All models performing normally.
```

### 3. Add to Crontab

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 3 AM):
0 3 * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node monitoring/check-drift.cjs >> /var/log/drift-detection.log 2>&1
```

---

## Cron Schedule Options

| Schedule | Cron Expression | Use Case |
|----------|-----------------|----------|
| Every 6 hours | `0 */6 * * *` | High-frequency monitoring |
| Daily at 3 AM | `0 3 * * *` | Standard monitoring (recommended) |
| Twice daily | `0 3,15 * * *` | Morning + afternoon checks |
| Weekly (Monday 3 AM) | `0 3 * * 1` | Low-frequency monitoring |

---

## Log Management

### Create Log Directory

```bash
sudo mkdir -p /var/log/claude
sudo chown $USER:$USER /var/log/claude
```

### Update Cron to Use Log Directory

```bash
0 3 * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node monitoring/check-drift.cjs >> /var/log/claude/drift-detection.log 2>&1
```

### Log Rotation (Optional)

Create `/etc/logrotate.d/drift-detection`:

```
/var/log/claude/drift-detection.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## Monitoring Cron Status

### Check if Cron is Running

```bash
# View current crontab
crontab -l

# Check cron service status
systemctl status cron  # Debian/Ubuntu
systemctl status crond # RHEL/Fedora
```

### View Recent Drift Detection Results

```bash
# Last 50 lines of drift detection log
tail -50 /var/log/drift-detection.log

# Follow log in real-time
tail -f /var/log/drift-detection.log
```

### Check Unacknowledged Alerts

```bash
node monitoring/check-drift.cjs --unacknowledged
```

---

## Command-Line Options

### Basic Usage

```bash
# Run with default settings (10% threshold, 5 min samples)
node monitoring/check-drift.cjs

# Custom threshold (15% drop)
node monitoring/check-drift.cjs --threshold=0.15

# Increase minimum samples requirement
node monitoring/check-drift.cjs --min-samples=10
```

### Alert Management

```bash
# Show unacknowledged alerts
node monitoring/check-drift.cjs --unacknowledged

# Acknowledge alert by ID
node monitoring/check-drift.cjs --acknowledge=42

# Show drift history for a specific model
node monitoring/check-drift.cjs --history=opus
```

### Output Formats

```bash
# JSON output (for programmatic consumption)
node monitoring/check-drift.cjs --json

# Human-readable output (default)
node monitoring/check-drift.cjs
```

### Advanced Options

```bash
# Skip Thompson Sampling weight updates
node monitoring/check-drift.cjs --no-weights

# Skip human review queue
node monitoring/check-drift.cjs --no-review

# Combine options
node monitoring/check-drift.cjs --threshold=0.15 --min-samples=10 --no-weights
```

---

## Database Queries

### Check Recent Drift Alerts

```sql
-- Connect to database
psql -h aio-01 -p 5433 -U sfloess -d learning

-- Recent drift alerts
SELECT model, task_type, performance_drop_pct, detection_date
FROM monitoring.drift_alerts
ORDER BY detection_date DESC
LIMIT 10;

-- Unacknowledged alerts
SELECT model, task_type, performance_drop_pct, severity, detection_date
FROM monitoring.drift_alerts
WHERE acknowledged = FALSE
ORDER BY detection_date DESC;

-- Critical alerts only
SELECT model, task_type, performance_drop_pct, detection_date
FROM monitoring.drift_alerts
WHERE severity = 'critical'
ORDER BY detection_date DESC
LIMIT 10;
```

### Manual Materialized View Refresh

```sql
-- Refresh materialized view manually
SELECT monitoring.refresh_drift_view();
```

### Query Model Performance Trends

```sql
-- Weekly performance for a specific model
SELECT week_start, avg_confidence, execution_count, success_rate
FROM monitoring.model_drift
WHERE model = 'opus'
ORDER BY week_start DESC
LIMIT 12; -- Last 12 weeks
```

---

## Troubleshooting

### Cron Job Not Running

**Check cron service:**
```bash
sudo systemctl status crond
sudo systemctl restart crond
```

**Verify crontab entry:**
```bash
crontab -l | grep drift
```

**Check for errors in system log:**
```bash
sudo tail -100 /var/log/cron
```

### No Drift Detected (Expected When Starting)

When first deployed, there may be no drift alerts because:
1. `workflow.worker_results` table is empty (no executions yet)
2. Not enough data to establish 30-day baseline
3. Minimum sample threshold not met (default: 5 samples)

**Solution:** Wait for workflow executions to populate data, or use synthetic test data.

### Database Connection Errors

**Check PostgreSQL connection:**
```bash
PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning PGUSER=sfloess psql -c "\dt monitoring.*"
```

**Check environment variables:**
```bash
echo "PGHOST=$PGHOST PGPORT=$PGPORT PGDATABASE=$PGDATABASE PGUSER=$PGUSER"
```

### Permission Denied Errors

**Ensure user has access to workflow and monitoring schemas:**
```sql
GRANT USAGE ON SCHEMA workflow TO sfloess;
GRANT USAGE ON SCHEMA monitoring TO sfloess;
GRANT SELECT ON ALL TABLES IN SCHEMA workflow TO sfloess;
GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO sfloess;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO sfloess;
```

---

## Integration with Other Systems

### Thompson Sampling Weight Updates

When drift is detected, the system recommends weight adjustments:

```javascript
// Example: Reduce model weight when drift detected
// TODO: Integrate with actual bandit state (~/.claude/learning/bandit-state.json)
```

### Human Review Queue

Critical drift alerts are automatically queued in `workflow.human_review_queue`:

```sql
-- Check human review queue
SELECT * FROM workflow.human_review_queue
WHERE review_type = 'model_drift'
ORDER BY created_at DESC;
```

---

## Maintenance

### Weekly Maintenance Tasks

```bash
# 1. Review unacknowledged alerts
node monitoring/check-drift.cjs --unacknowledged

# 2. Acknowledge resolved alerts
node monitoring/check-drift.cjs --acknowledge=<ID>

# 3. Check log file size
du -sh /var/log/drift-detection.log
```

### Monthly Maintenance Tasks

```bash
# 1. Review drift trends for key models
node monitoring/check-drift.cjs --history=opus
node monitoring/check-drift.cjs --history=sonnet
node monitoring/check-drift.cjs --history=haiku

# 2. Archive old alerts (optional)
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "DELETE FROM monitoring.drift_alerts WHERE detection_date < NOW() - INTERVAL '90 days'"
```

---

## Example Output

### No Drift Detected

```
🔍 Model Performance Drift Detection
Threshold: 10% drop
Minimum samples: 5

[DriftDetector] Refreshed model_drift view in 45ms
[DriftDetector] Detected 0 drift alerts in 12ms

✅ Drift detection complete (57ms)

✅ No drift detected. All models performing normally.
```

### Drift Detected

```
🔍 Model Performance Drift Detection
Threshold: 10% drop
Minimum samples: 5

[DriftDetector] Refreshed model_drift view in 52ms
[DriftDetector] Detected 2 drift alerts in 18ms
[DriftDetector] Drift alerts:
  ⚠️  opus (code_review): 0.720 → 0.850 (-15.29% drop, n=23)
  🚨 sonnet (data_analysis): 0.650 → 0.900 (-27.78% drop, n=31)

✅ Drift detection complete (70ms)

🚨 Detected 2 drift alert(s):

[1] ⚠️  WARNING: opus (code_review)
    Performance drop: -15.29%
    Current (7-day): 0.720 (n=23)
    Historical (30-day): 0.850 (n=87)
    Alert ID: 1

[2] 🚨 CRITICAL: sonnet (data_analysis)
    Performance drop: -27.78%
    Current (7-day): 0.650 (n=31)
    Historical (30-day): 0.900 (n=124)
    Alert ID: 2

Actions taken:
  ✓ Logged 2 alerts to monitoring.drift_alerts
  ✓ Updated Thompson Sampling weights (recommended)
  ✓ Queued human review

Next steps:
  1. Review alerts: node monitoring/check-drift.cjs --unacknowledged
  2. Acknowledge: node monitoring/check-drift.cjs --acknowledge=<ID>
  3. Investigate model API changes, regional routing, or fine-tuning updates
```

---

## Resources

- **Schema:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/monitoring/schema-drift-detection.sql`
- **Detector:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/monitoring/drift-detector.cjs`
- **CLI:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/monitoring/check-drift.cjs`
- **Database:** `postgresql://sfloess@aio-01:5433/learning`
- **Schemas:** `workflow.*`, `monitoring.*`

---

## Contact

For issues or questions:
1. Check logs: `/var/log/drift-detection.log`
2. Review database: `psql -h aio-01 -p 5433 -U sfloess -d learning`
3. Test manually: `node monitoring/check-drift.cjs --unacknowledged`
