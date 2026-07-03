# Drift Detection System

**Created:** 2026-07-03  
**Status:** Production Ready  
**Components:** 2 (drift_detector.py + drift_monitor_integration.cjs)

## Overview

The Drift Detection System monitors model performance degradation over time using multiple statistical algorithms. It complements the existing Model Regression Monitor by providing real-time drift alerts and continuous monitoring.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL (aio-01:5433)                               │
│  ├─ workflow.executions                                 │
│  ├─ workflow.worker_results (time-series data)          │
│  ├─ workflow.arbiter_decisions                          │
│  └─ workflow.drift_detections (NEW)                     │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┴───────────────────────────────┐
│  drift_detector.py (Statistical Algorithms)             │
│  ├─ CUSUM (Cumulative Sum)                              │
│  ├─ Page-Hinkley Test                                   │
│  ├─ ADWIN (Adaptive Windowing)                          │
│  └─ Kolmogorov-Smirnov Test                             │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┴───────────────────────────────┐
│  drift_monitor_integration.cjs (Orchestration)          │
│  ├─ Periodic checks                                     │
│  ├─ Database persistence                                │
│  ├─ Alert system                                        │
│  └─ Consensus replay trigger                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Downstream Integrations                                │
│  ├─ consensus-replay.cjs (validation)                   │
│  ├─ performance_dashboard.py (visualization)            │
│  └─ Alert system (Slack/email)                          │
└─────────────────────────────────────────────────────────┘
```

## Statistical Algorithms

### 1. CUSUM (Cumulative Sum)
**Purpose:** Detect gradual mean shifts in quality scores  
**Sensitivity:** Medium (configurable threshold)  
**Best for:** Slow degradation over time

```python
# Example: Quality score drifting from 0.85 to 0.75 over 50 runs
# CUSUM accumulates deviations and triggers when threshold exceeded
```

**Configuration:**
- Threshold: 5.0 (adjustable in `DRIFT_THRESHOLDS`)
- Drift threshold: 0.0 (minimum change magnitude)

### 2. Page-Hinkley Test
**Purpose:** Detect abrupt changes in performance  
**Sensitivity:** High (more sensitive than CUSUM)  
**Best for:** Sudden model updates or API changes

```python
# Example: Quality suddenly drops from 0.85 to 0.65 after model update
# Page-Hinkley triggers immediately on significant deviation
```

**Configuration:**
- Threshold: 10.0
- Delta: 0.005 (minimum change magnitude)

### 3. ADWIN (Adaptive Windowing)
**Purpose:** Detect concept drift with adaptive window sizing  
**Sensitivity:** Adaptive (adjusts to data characteristics)  
**Best for:** Non-stationary environments

```python
# Example: Model behavior changes due to new task types
# ADWIN automatically adjusts window size and detects distribution shift
```

**Configuration:**
- Delta: 0.002 (confidence level)
- Max window: 1000 samples

### 4. Kolmogorov-Smirnov Test
**Purpose:** Detect distribution changes  
**Sensitivity:** Statistical (p-value based)  
**Best for:** Overall distribution shifts

```python
# Example: Quality score distribution changes shape
# KS test compares recent vs historical distributions
# Triggers if p-value < 0.05
```

**Configuration:**
- Alpha: 0.05 (significance level)
- Split: 60% historical, 40% recent

## Metrics Monitored

### 1. Quality Score
**Source:** `workflow.worker_results.quality_score`  
**Importance:** CRITICAL (triggers severity escalation)  
**Threshold:** 10% drop triggers alert

### 2. Confidence Score
**Source:** `workflow.worker_results.confidence`  
**Importance:** HIGH (indicates calibration issues)  
**Threshold:** Significant deviation from baseline

### 3. Cost Efficiency
**Source:** `workflow.worker_results.cost_usd`  
**Importance:** MEDIUM (financial impact)  
**Threshold:** 20% increase triggers alert

## Severity Classification

Drift severity is calculated based on multiple factors:

| Severity | Score | Criteria |
|----------|-------|----------|
| **CRITICAL** | ≥10 | Quality drift + multiple detectors agree |
| **HIGH** | 7-9 | Multiple metrics affected or high magnitude |
| **MEDIUM** | 4-6 | Single metric affected, moderate magnitude |
| **LOW** | <4 | Minor deviations, low confidence |

**Severity Factors:**
- Signal count (more detectors = higher severity)
- Magnitude of drift
- Multiple metrics affected
- Quality impact (4 bonus points for quality drift)
- Distribution shift detected

## Usage

### One-Time Analysis

```bash
# Analyze all models (last 30 days)
python3 tools/drift_detector.py --save-report

# Analyze specific model
python3 tools/drift_detector.py --model opus --days 30 --save-report

# Quick check without saving
python3 tools/drift_detector.py --days 7
```

### Continuous Monitoring

```bash
# Monitor every hour (default)
python3 tools/drift_detector.py --continuous --check-interval 3600

# Monitor every 15 minutes
python3 tools/drift_detector.py --continuous --check-interval 900
```

### Integrated Monitoring (Recommended)

```bash
# One-time check with database persistence
node tools/drift_monitor_integration.cjs --once --days 30

# Continuous monitoring with alerts
node tools/drift_monitor_integration.cjs --continuous --interval 3600

# Model-specific monitoring
node tools/drift_monitor_integration.cjs --model opus --days 7
```

## Database Schema

### `workflow.drift_detections`

```sql
CREATE TABLE workflow.drift_detections (
  id SERIAL PRIMARY KEY,
  detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
  model VARCHAR(255) NOT NULL,
  drift_type VARCHAR(100),          -- performance_degradation, confidence_miscalibration, etc.
  severity VARCHAR(20),              -- CRITICAL, HIGH, MEDIUM, LOW
  affected_metrics TEXT[],           -- ['quality', 'confidence', 'cost']
  signal_count INTEGER,              -- Number of detectors that triggered
  sample_count INTEGER,              -- Time buckets analyzed
  time_range_start TIMESTAMP,
  time_range_end TIMESTAMP,
  details JSONB,                     -- Full drift analysis results
  report_path TEXT,                  -- Path to detailed report
  resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMP,
  resolution_notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Indexes:**
- `idx_drift_detections_model` (model)
- `idx_drift_detections_detected_at` (detected_at DESC)
- `idx_drift_detections_severity` (severity)
- `idx_drift_detections_unresolved` (WHERE resolved = FALSE)

## Output Files

### Drift Reports
**Location:** `~/.claude/learning/drift_reports/`

- `latest_drift_report.json` - Most recent analysis
- `drift_detection_log.jsonl` - Historical log (one line per check)
- `drift_alerts.jsonl` - Critical/high severity alerts

### Report Structure

```json
{
  "timestamp": "2026-07-03T18:30:00",
  "models_analyzed": 8,
  "drift_detected": true,
  "models": {
    "opus": {
      "drift_detected": true,
      "drift_type": "performance_degradation",
      "severity": "HIGH",
      "affected_metrics": ["quality", "confidence"],
      "signal_count": 3,
      "sample_count": 145,
      "time_range": {
        "start": "2026-06-03T00:00:00",
        "end": "2026-07-03T18:00:00"
      },
      "drift_signals": [...],
      "distribution_changes": {...}
    }
  },
  "summary": {
    "total_models": 8,
    "models_with_drift": 2,
    "severity_breakdown": {
      "CRITICAL": 1,
      "HIGH": 1
    }
  }
}
```

## Integration with Existing Systems

### 1. Model Regression Monitor
**Relationship:** Complementary  
**Integration:** Drift detector triggers regression monitor for validation

```javascript
// When critical drift detected, trigger consensus replay
if (drift.severity === 'CRITICAL') {
  await runRegressionAnalysis([{
    workflow_id: representativeWorkflow,
    model: drift.model
  }]);
}
```

### 2. Performance Dashboard
**Relationship:** Visualization  
**Integration:** Drift reports feed into dashboard metrics

```python
# In performance_dashboard.py, read drift detection log
drift_log = read_jsonl('~/.claude/learning/drift_reports/drift_detection_log.jsonl')
plot_drift_timeline(drift_log)
```

### 3. Novelty Detector
**Relationship:** Orthogonal  
**Integration:** Drift detection focuses on performance, novelty on task type

```
Novelty Detector: "Is this task new/unfamiliar?"
Drift Detector: "Is model performance degrading over time?"
```

## Alert System (TODO)

Planned integrations:

### Slack Notifications
```javascript
// Send alert to #model-monitoring channel
await sendSlackAlert({
  channel: '#model-monitoring',
  severity: 'CRITICAL',
  model: 'opus',
  drift_type: 'performance_degradation',
  report_url: 'http://...'
});
```

### Email Alerts
```javascript
// Email on-call engineer
await sendEmailAlert({
  to: 'oncall-ml@example.com',
  subject: 'CRITICAL: Model drift detected (opus)',
  body: driftSummary
});
```

## Automated Response (Planned)

When drift is detected:

1. **CRITICAL Severity:**
   - Trigger consensus replay for validation
   - Send immediate alert
   - Auto-create incident ticket
   - Consider automatic model rotation

2. **HIGH Severity:**
   - Schedule validation replay
   - Alert monitoring channel
   - Flag for manual review

3. **MEDIUM/LOW Severity:**
   - Log for analysis
   - Include in weekly report
   - No immediate action

## Deployment

### Cron Job (Recommended)

```bash
# Check for drift every hour
0 * * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node tools/drift_monitor_integration.cjs --once --days 7 >> /var/log/drift_monitor.log 2>&1
```

### Systemd Service

```ini
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
```

## Tuning Parameters

### Increasing Sensitivity (More Alerts)
```python
DRIFT_THRESHOLDS = {
    'cusum_threshold': 3.0,          # Lower = more sensitive
    'page_hinkley_threshold': 5.0,   # Lower = more sensitive
    'ks_test_alpha': 0.10,           # Higher = more sensitive
    'min_samples': 20                # Lower = faster detection
}
```

### Decreasing Sensitivity (Fewer False Positives)
```python
DRIFT_THRESHOLDS = {
    'cusum_threshold': 10.0,         # Higher = less sensitive
    'page_hinkley_threshold': 20.0,  # Higher = less sensitive
    'ks_test_alpha': 0.01,           # Lower = less sensitive
    'min_samples': 50                # Higher = more data required
}
```

## Validation

To validate drift detector is working:

```bash
# 1. Run analysis on known model
python3 tools/drift_detector.py --model opus --days 30 --save-report

# 2. Check results
cat ~/.claude/learning/drift_reports/latest_drift_report.json | jq '.models.opus'

# 3. Store in database
node tools/drift_monitor_integration.cjs --once --model opus

# 4. Query database
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT * FROM workflow.drift_detections ORDER BY detected_at DESC LIMIT 5"
```

## Known Limitations

1. **Requires Sufficient Data:** Minimum 30 samples per time bucket
2. **Hourly Granularity:** Data bucketed by hour (may miss very fast drift)
3. **Model-Specific:** Does not detect cross-model drift patterns
4. **Stateless:** Each run is independent (no persistent detector state)

## Future Enhancements

1. **Multi-Variate Drift:** Detect correlated drift across metrics
2. **Task-Specific Drift:** Per-task-type drift detection
3. **Seasonal Adjustment:** Account for time-of-day/day-of-week patterns
4. **Predictive Alerts:** Forecast drift before it becomes critical
5. **Auto-Remediation:** Automatic model rotation on critical drift

## References

- **CUSUM:** Page, E. S. (1954). "Continuous Inspection Schemes"
- **Page-Hinkley:** Page, E. S. (1954). "A test for a change in a parameter"
- **ADWIN:** Bifet & Gavaldà (2007). "Learning from Time-Changing Data"
- **KS Test:** Kolmogorov (1933), Smirnov (1948)

## Support

For issues or questions:
1. Check drift detection log: `~/.claude/learning/drift_reports/drift_detection_log.jsonl`
2. Review database table: `SELECT * FROM workflow.drift_detections WHERE resolved = FALSE`
3. Validate Python dependencies: `python3 -c "import numpy, scipy; print('OK')"`

---

**Last Updated:** 2026-07-03  
**Version:** 1.0.0  
**Maintainer:** sfloess
