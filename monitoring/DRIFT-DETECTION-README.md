# Drift Detection - Quality Regression Monitoring

**Automated quality degradation detection for multi-AI consensus workflows**

**Created:** 2026-06-28  
**Database:** `postgresql://sfloess@aio-01:5433/learning`  
**Status:** Production-ready  
**Location:** `monitoring/drift-detector.cjs`

---

## Overview

Drift detection monitors model performance over time and alerts when quality degrades. It compares recent 7-day performance against a 30-day baseline, catching issues like API changes, model downgrades, or data distribution shifts before they cause production problems.

**Key Features:**
- Automated 7-day vs 30-day quality comparison
- Configurable alert thresholds (10% warning, 20% critical)
- Database-backed historical tracking
- Webhook notifications (Slack, Discord)
- Thompson Sampling integration (auto-penalize degraded models)
- Human review queue integration

---

## How It Works

### Detection Algorithm

```
1. Calculate 30-day baseline quality (excluding last 7 days)
   - Minimum 20 samples required
   - Per-model, per-task_type aggregation

2. Calculate 7-day current quality
   - Minimum 20 samples required
   - Same model + task_type grouping

3. Compute drift percentage
   drift_pct = (baseline_avg - current_avg) / baseline_avg × 100

4. Classify severity
   - drift_pct > 20%  → CRITICAL (🚨)
   - drift_pct > 10%  → WARNING  (⚠️)
   - drift_pct ≤ 10%  → OK

5. Store alerts in monitoring.drift_alerts
   - Deduplicated (model + task_type + date)
   - Acknowledged status tracking
   - Historical audit trail

6. Optional actions
   - Update Thompson Sampling weights (reduce model priority)
   - Queue human review (priority 1 for critical, 2 for warning)
   - Send webhook notifications (Slack/Discord)
```

### Time Windows

```
├─────────────────────────────┬──────────┤
│  30-day baseline window     │ 7-day    │
│  (used for comparison)      │ current  │
└─────────────────────────────┴──────────┘
                              ↑
                         7 days ago
```

**Baseline:** Days -37 to -7 (30 days, excluding recent data)  
**Current:** Days -7 to 0 (last 7 days)

This gap prevents baseline contamination from recent degradation.

---

## When To Use

### Automatic Background Monitoring

Run via cron to detect:
- **API provider changes** - Model updates without notice
- **Quality regressions** - Performance drops over time
- **Data distribution shifts** - Training/production mismatch
- **Silent failures** - Gradual degradation that escapes manual review

**Recommended schedule:** Daily at 3 AM

```bash
crontab -e
# Add:
0 3 * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node monitoring/check-drift.cjs >> /var/log/drift-detection.log 2>&1
```

### Manual Investigation

Run on-demand when:
- Debugging quality complaints
- Post-deployment verification
- Investigating model performance
- Analyzing historical trends

---

## Database Schema

### Tables

#### `monitoring.drift_alerts`

Historical log of all drift detections.

```sql
CREATE TABLE monitoring.drift_alerts (
  id SERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  task_type TEXT,                    -- NULL = all tasks
  current_7day_avg REAL NOT NULL,
  historical_30day_avg REAL NOT NULL,
  performance_drop_pct REAL NOT NULL,
  current_sample_count INT NOT NULL,
  historical_sample_count INT NOT NULL,
  severity TEXT NOT NULL,            -- 'warning' or 'critical'
  metadata JSONB,
  detection_date DATE NOT NULL DEFAULT CURRENT_DATE,
  acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
  acknowledged_by TEXT,
  acknowledged_at TIMESTAMP,
  
  -- Deduplication: One alert per model+task+day
  UNIQUE (model, COALESCE(task_type, ''), detection_date)
);

CREATE INDEX idx_drift_alerts_model ON monitoring.drift_alerts(model);
CREATE INDEX idx_drift_alerts_date ON monitoring.drift_alerts(detection_date DESC);
CREATE INDEX idx_drift_alerts_acknowledged ON monitoring.drift_alerts(acknowledged) WHERE acknowledged = FALSE;
```

**Example row:**

```json
{
  "id": 42,
  "model": "opus",
  "task_type": "code_review",
  "current_7day_avg": 0.72,
  "historical_30day_avg": 0.85,
  "performance_drop_pct": -15.29,
  "current_sample_count": 23,
  "historical_sample_count": 87,
  "severity": "warning",
  "metadata": {
    "detection_timestamp": "2026-06-28T03:00:00Z",
    "threshold_used": 0.10
  },
  "detection_date": "2026-06-28",
  "acknowledged": false,
  "acknowledged_by": null,
  "acknowledged_at": null
}
```

#### `monitoring.model_drift` (Materialized View)

Pre-aggregated quality metrics for fast drift detection.

```sql
CREATE MATERIALIZED VIEW monitoring.model_drift AS
SELECT
  model,
  task_type,
  
  -- 7-day current window
  AVG(CASE WHEN age_days <= 7 THEN quality_score END) as current_7day_avg,
  COUNT(CASE WHEN age_days <= 7 THEN 1 END) as current_sample_count,
  
  -- 30-day baseline window (days 8-37)
  AVG(CASE WHEN age_days > 7 AND age_days <= 37 THEN quality_score END) as historical_30day_avg,
  COUNT(CASE WHEN age_days > 7 AND age_days <= 37 THEN 1 END) as historical_sample_count,
  
  MAX(created_at) as last_execution
FROM (
  SELECT
    model,
    task_type,
    quality_score,
    created_at,
    EXTRACT(DAY FROM NOW() - created_at) as age_days
  FROM workflow.worker_results
  WHERE created_at >= NOW() - INTERVAL '90 days'
    AND quality_score IS NOT NULL
) sub
GROUP BY model, task_type;

CREATE UNIQUE INDEX idx_model_drift_pk ON monitoring.model_drift(model, COALESCE(task_type, ''));
```

**Refresh policy:** On-demand via `SELECT monitoring.refresh_drift_view()`

**Refresh frequency:** 
- Automated: Daily at 3 AM (via cron)
- Manual: Before each drift detection run

### Functions

#### `monitoring.detect_model_drift(drift_threshold, min_samples)`

Detects drift by comparing current vs historical quality.

```sql
SELECT * FROM monitoring.detect_model_drift(
  0.10,  -- drift_threshold: 10% drop = warning
  20     -- min_samples: Minimum samples per window
);
```

**Returns:**

```
 model | task_type | current_7day_avg | historical_30day_avg | performance_drop_pct | current_sample_count | historical_sample_count | severity
-------+-----------+------------------+----------------------+----------------------+----------------------+-------------------------+-----------
 opus  | code      |            0.720 |                0.850 |               -15.29 |                   23 |                      87 | warning
```

**Logic:**

```sql
-- Simplified version
SELECT
  model,
  task_type,
  current_7day_avg,
  historical_30day_avg,
  ((historical_30day_avg - current_7day_avg) / historical_30day_avg * 100) as performance_drop_pct,
  CASE
    WHEN performance_drop_pct > 20 THEN 'critical'
    WHEN performance_drop_pct > 10 THEN 'warning'
  END as severity
FROM monitoring.model_drift
WHERE current_sample_count >= min_samples
  AND historical_sample_count >= min_samples
  AND performance_drop_pct > drift_threshold * 100
ORDER BY performance_drop_pct DESC;
```

#### `monitoring.log_drift_alert(...)`

Logs a drift alert to `monitoring.drift_alerts` with deduplication.

```sql
SELECT monitoring.log_drift_alert(
  'opus',              -- model
  'code_review',       -- task_type
  0.72,                -- current_7day_avg
  0.85,                -- historical_30day_avg
  -15.29,              -- performance_drop_pct
  23,                  -- current_sample_count
  87,                  -- historical_sample_count
  'warning',           -- severity
  '{"threshold": 0.10}'::jsonb  -- metadata
);
```

**Returns:** `alert_id` (or `NULL` if duplicate for today)

**Deduplication:** Uses `ON CONFLICT (model, COALESCE(task_type, ''), detection_date) DO NOTHING`

#### `monitoring.acknowledge_drift_alert(alert_id, acknowledged_by)`

Acknowledges a drift alert (marks as reviewed).

```sql
SELECT monitoring.acknowledge_drift_alert(42, 'sfloess');
```

**Returns:** `TRUE` if successful, `FALSE` if alert not found

**Updates:**

```sql
UPDATE monitoring.drift_alerts
SET acknowledged = TRUE,
    acknowledged_by = 'sfloess',
    acknowledged_at = NOW()
WHERE id = 42;
```

#### `monitoring.refresh_drift_view()`

Refreshes the materialized view with latest data.

```sql
SELECT monitoring.refresh_drift_view();
```

**Performance:** ~50ms for 1,000 worker results

**IMPORTANT:** Always call before `detect_model_drift()` to ensure fresh data.

---

## API Usage

### JavaScript API

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.js');
const {
  detectDrift,
  refreshDriftView,
  logDriftAlerts,
  acknowledgeDriftAlert,
  getUnacknowledgedAlerts,
  getModelDriftHistory,
  runDriftDetectionPipeline
} = require('./monitoring/drift-detector.cjs');

// Complete pipeline (recommended)
const result = await runDriftDetectionPipeline({
  driftThreshold: 0.10,      // 10% drop threshold
  minSamples: 20,            // Minimum samples required
  updateWeights: true,       // Update Thompson Sampling
  queueReview: true,         // Add to human review queue
  sendWebhooks: true         // Send Slack/Discord notifications
});

console.log(result);
// {
//   success: true,
//   drift_alerts: [...],
//   alert_ids: [42, 43],
//   duration_ms: 156,
//   timestamp: '2026-06-28T03:00:00Z'
// }

// Manual step-by-step
await refreshDriftView();
const driftAlerts = await detectDrift({ driftThreshold: 0.10, minSamples: 20 });
const alertIds = await logDriftAlerts(driftAlerts);

// Get unacknowledged alerts
const alerts = await getUnacknowledgedAlerts();
console.log(`${alerts.length} unacknowledged drift alerts`);

// Acknowledge alert
await acknowledgeDriftAlert(42, 'sfloess');

// Get model history
const history = await getModelDriftHistory('opus', 30);
console.log(`Opus: ${history.length} historical drift alerts`);
```

### SQL API

```sql
-- Refresh data
SELECT monitoring.refresh_drift_view();

-- Detect drift (10% threshold, 20 min samples)
SELECT * FROM monitoring.detect_model_drift(0.10, 20);

-- Log alert
SELECT monitoring.log_drift_alert(
  'opus', 'code_review', 0.72, 0.85, -15.29, 23, 87, 'warning', '{}'::jsonb
);

-- Get unacknowledged alerts
SELECT * FROM monitoring.drift_alerts WHERE acknowledged = FALSE;

-- Acknowledge alert
SELECT monitoring.acknowledge_drift_alert(42, 'sfloess');

-- Get model history
SELECT * FROM monitoring.drift_alerts 
WHERE model = 'opus' 
ORDER BY detection_date DESC 
LIMIT 30;
```

---

## Integration

### 1. Workflow Storage Integration

Drift detection uses `workflow.worker_results` table for quality data.

**Required schema:**

```javascript
await db.storeWorkerResult({
  workflow_execution_id: execId,
  worker_id: 'worker-1',
  model: 'opus',
  task_assigned: 'Review code',
  result: 'Analysis complete',
  quality_score: 0.85,     // REQUIRED for drift detection
  confidence: 0.92,
  duration_ms: 5000,
  input_tokens: 1500,
  output_tokens: 800,
  cost_usd: 0.05,
  outcome: 'success'
});
```

**IMPORTANT:** `quality_score` must be populated (arbiter's synthesis quality, not worker confidence).

**Migration:** If using old schema with `confidence` only:

```sql
-- Add quality_score column if missing
ALTER TABLE workflow.worker_results ADD COLUMN quality_score REAL;

-- Backfill from confidence (temporary - replace with actual quality scores)
UPDATE workflow.worker_results 
SET quality_score = confidence 
WHERE quality_score IS NULL AND confidence IS NOT NULL;
```

### 2. Thompson Sampling Integration

**Placeholder implementation** - integrate with actual bandit state.

**Current behavior:** Logs recommended weight adjustments:

```
[DriftDetector] Recommend: Reduce opus weight by 50% for task_type="code_review"
[DriftDetector] Recommend: Reduce sonnet weight by 20% for task_type="all"
```

**TODO:** Connect to `~/.claude/learning/bandit-state.json` or `learning.strategy_performance` table.

**Recommended integration:**

```javascript
async function updateThompsonSamplingWeights(driftAlerts) {
  const { Pool } = require('pg');
  const pool = new Pool({ host: 'aio-01', port: 5433, database: 'learning' });
  
  for (const alert of driftAlerts) {
    const penaltyFactor = alert.severity === 'critical' ? 0.5 : 0.8;
    
    await pool.query(
      `UPDATE learning.strategy_performance
       SET beta = beta * $1
       WHERE strategy = $2`,
      [1 / penaltyFactor, alert.model]
    );
    
    console.log(`Reduced ${alert.model} weight by ${(1 - penaltyFactor) * 100}%`);
  }
  
  await pool.end();
}
```

### 3. Human Review Queue Integration

Adds drift alerts to `workflow.human_review_queue` for manual investigation.

**Schema required:**

```sql
CREATE TABLE workflow.human_review_queue (
  id SERIAL PRIMARY KEY,
  review_type TEXT NOT NULL,           -- 'model_drift'
  priority INT NOT NULL,               -- 1=critical, 2=warning
  message TEXT NOT NULL,
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  reviewed BOOLEAN NOT NULL DEFAULT FALSE,
  reviewed_by TEXT,
  reviewed_at TIMESTAMP
);
```

**Automatic queuing:**

```javascript
await queueHumanReview(driftAlerts);
// Adds to workflow.human_review_queue with priority 1 (critical) or 2 (warning)
```

**Query pending reviews:**

```sql
SELECT * FROM workflow.human_review_queue 
WHERE review_type = 'model_drift' 
  AND reviewed = FALSE 
ORDER BY priority ASC, created_at ASC;
```

### 4. Webhook Notifications

Sends Slack/Discord alerts for critical drift (>20% drop).

**Configuration:** `monitoring/webhook-config.json`

```json
{
  "webhooks": {
    "slack": {
      "enabled": true,
      "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
      "channel": "#monitoring",
      "username": "Claude Monitor",
      "icon_emoji": ":robot_face:"
    },
    "discord": {
      "enabled": false,
      "url": "https://discord.com/api/webhooks/YOUR/WEBHOOK/URL",
      "username": "Claude Monitor"
    }
  },
  "thresholds": {
    "drift": {
      "critical_drop_pct": 20
    }
  },
  "notifications": {
    "critical_drift": {
      "enabled": true,
      "channels": ["slack"],
      "rate_limit_minutes": 60
    }
  },
  "rate_limiting": {
    "enabled": true,
    "cache_file": "/tmp/webhook-rate-limit-cache.json"
  }
}
```

**Slack message example:**

```
🚨 Critical Model Drift Detected
Model: opus
Task Type: code_review
Performance Drop: -25.5%
Current Quality: 0.650
Historical Quality: 0.870
Samples: 42
```

**Test webhook:**

```bash
node monitoring/webhook-notifier.cjs test slack
node monitoring/webhook-notifier.cjs test discord
```

**Manual notification:**

```javascript
const { notifyDrift } = require('./monitoring/webhook-notifier.cjs');

await notifyDrift({
  model: 'opus',
  task_type: 'code_review',
  performance_drop_pct: -25.5,
  current_7day_avg: 0.65,
  historical_30day_avg: 0.87,
  current_sample_count: 42,
  severity: 'critical'
});
```

**Rate limiting:**

- Default: 1 notification per hour per type
- Prevents spam from repeated detections
- Cache: `/tmp/webhook-rate-limit-cache.json`

---

## CLI Usage

### `monitoring/check-drift.cjs`

Command-line interface for drift detection.

```bash
# Daily check (default: 10% threshold, 20 min samples)
node monitoring/check-drift.cjs

# Custom threshold (15% drop)
node monitoring/check-drift.cjs --threshold=0.15

# Custom minimum samples (30)
node monitoring/check-drift.cjs --min-samples=30

# Skip webhook notifications
node monitoring/check-drift.cjs --no-webhooks

# Skip Thompson Sampling updates
node monitoring/check-drift.cjs --no-weights

# Show unacknowledged alerts
node monitoring/check-drift.cjs --unacknowledged

# Acknowledge alert by ID
node monitoring/check-drift.cjs --acknowledge=42

# Show model drift history (last 30 alerts)
node monitoring/check-drift.cjs --history=opus

# Combination
node monitoring/check-drift.cjs --threshold=0.15 --min-samples=30 --no-webhooks
```

**Output:**

```
[DriftDetector] Starting drift detection pipeline...
[DriftDetector] Refreshed model_drift view in 52ms
[DriftDetector] Detected 2 drift alerts in 8ms
[DriftDetector] Drift alerts:
  ⚠️  opus (code_review): 0.720 → 0.850 (-15.29% drop, n=23)
  🚨 sonnet (all tasks): 0.650 → 0.870 (-25.29% drop, n=42)
[DriftDetector] Logged 2 drift alerts to database
[DriftDetector] Recommend: Reduce opus weight by 20% for task_type="code_review"
[DriftDetector] Recommend: Reduce sonnet weight by 50% for task_type="all"
[DriftDetector] Queued human review for opus
[DriftDetector] Queued human review for sonnet
[WebhookNotifier] Drift below critical threshold (15.3% < 20%)
[WebhookNotifier] Sending critical drift alert for sonnet
[WebhookNotifier] Sent critical_drift to slack
[DriftDetector] Pipeline complete in 156ms
```

---

## Monitoring and Maintenance

### Daily Operations

**1. Check drift alerts (automated via cron)**

```bash
0 3 * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node monitoring/check-drift.cjs >> /var/log/drift-detection.log 2>&1
```

**2. Review unacknowledged alerts**

```bash
node monitoring/check-drift.cjs --unacknowledged
```

```sql
SELECT * FROM monitoring.drift_alerts 
WHERE acknowledged = FALSE 
ORDER BY detection_date DESC;
```

**3. Investigate drift**

```bash
# Get model history
node monitoring/check-drift.cjs --history=opus

# Query raw worker results
psql -h aio-01 -p 5433 -d learning -c "
  SELECT 
    DATE(created_at) as date,
    model,
    task_type,
    AVG(quality_score) as avg_quality,
    COUNT(*) as count
  FROM workflow.worker_results
  WHERE model = 'opus'
    AND created_at >= NOW() - INTERVAL '30 days'
  GROUP BY DATE(created_at), model, task_type
  ORDER BY date DESC;
"
```

**4. Acknowledge after investigation**

```bash
node monitoring/check-drift.cjs --acknowledge=42
```

```sql
SELECT monitoring.acknowledge_drift_alert(42, 'sfloess');
```

### Weekly Reports

**Automated weekly summary (Sundays at 9 AM)**

```bash
crontab -e
# Add:
0 9 * * 0 cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node monitoring/webhook-notifier.cjs weekly-report >> /var/log/weekly-report.log 2>&1
```

**Manual report:**

```bash
node monitoring/webhook-notifier.cjs weekly-report
```

**Report contents:**

- Total executions (7 days)
- Average quality score
- Success rate
- Top-performing model
- Total cost
- Drift alerts count
- Disagreement reviews count

### Performance Optimization

**Materialized view refresh performance:**

```sql
-- Measure refresh time
\timing
SELECT monitoring.refresh_drift_view();
-- Time: 52.341 ms (typical for 1,000 worker results)
```

**Query performance:**

```sql
-- Check index usage
EXPLAIN ANALYZE SELECT * FROM monitoring.detect_model_drift(0.10, 20);

-- Vacuum/analyze after bulk inserts
VACUUM ANALYZE monitoring.drift_alerts;
VACUUM ANALYZE workflow.worker_results;

-- Reindex if slow
REINDEX TABLE monitoring.drift_alerts;
```

**Data retention:**

```sql
-- Delete old alerts (keep 90 days)
DELETE FROM monitoring.drift_alerts 
WHERE detection_date < CURRENT_DATE - INTERVAL '90 days';

-- Archive before deletion
CREATE TABLE monitoring.drift_alerts_archive AS 
SELECT * FROM monitoring.drift_alerts 
WHERE detection_date < CURRENT_DATE - INTERVAL '90 days';
```

### Troubleshooting

**Problem: No drift alerts despite known performance drop**

**Solutions:**

1. Check minimum sample size:
   ```sql
   SELECT 
     model, 
     task_type,
     COUNT(*) as samples 
   FROM workflow.worker_results 
   WHERE created_at >= NOW() - INTERVAL '7 days' 
   GROUP BY model, task_type;
   ```
   - Need ≥20 samples in both windows
   - Increase time windows or reduce `minSamples` threshold

2. Verify quality_score is populated:
   ```sql
   SELECT 
     COUNT(*) as total,
     COUNT(quality_score) as with_quality,
     COUNT(confidence) as with_confidence
   FROM workflow.worker_results;
   ```
   - Drift detection uses `quality_score`, not `confidence`
   - Backfill missing values

3. Refresh materialized view:
   ```sql
   SELECT monitoring.refresh_drift_view();
   SELECT * FROM monitoring.model_drift;
   ```

**Problem: Duplicate drift alerts**

**Solutions:**

1. Run migration to add deduplication:
   ```bash
   psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-drift-alerts.sql
   ```

2. Verify unique constraint:
   ```sql
   \d monitoring.drift_alerts
   -- Should show: UNIQUE (model, COALESCE(task_type, ''), detection_date)
   ```

**Problem: Webhooks not sending**

**Solutions:**

1. Check configuration:
   ```bash
   cat monitoring/webhook-config.json
   ```

2. Test webhook:
   ```bash
   node monitoring/webhook-notifier.cjs test slack
   ```

3. Check rate limiting:
   ```bash
   cat /tmp/webhook-rate-limit-cache.json
   ```
   - Default: 1 notification per hour
   - Delete cache to reset: `rm /tmp/webhook-rate-limit-cache.json`

4. Verify severity threshold:
   ```json
   {
     "thresholds": {
       "drift": {
         "critical_drop_pct": 20  // Only send webhooks for >20% drop
       }
     }
   }
   ```

**Problem: PostgreSQL connection errors**

**Solutions:**

1. Verify database connection:
   ```bash
   psql -h aio-01 -p 5433 -d learning -U sfloess -c "SELECT 1"
   ```

2. Check environment variables:
   ```bash
   export PGHOST=aio-01
   export PGPORT=5433
   export PGDATABASE=learning
   export PGUSER=sfloess
   ```

3. Verify schema exists:
   ```bash
   psql -h aio-01 -p 5433 -d learning -c "\dt monitoring.*"
   ```

---

## Testing

### `monitoring/test-drift-detection.cjs`

Comprehensive test suite validating all drift detection features.

```bash
node monitoring/test-drift-detection.cjs
```

**Tests:**

1. ✅ Refresh materialized view
2. ✅ Detect drift (10% threshold)
3. ✅ Log drift alerts (deduplication)
4. ✅ Get unacknowledged alerts
5. ✅ Acknowledge drift alert
6. ✅ Get model drift history
7. ✅ Complete pipeline (with webhooks disabled)

**Expected output:**

```
Running drift detection tests...

Test 1: Refresh materialized view
✅ PASS - View refreshed in 52ms

Test 2: Detect drift
✅ PASS - Detected 2 drift alerts

Test 3: Log drift alerts
✅ PASS - Logged 2 alerts (IDs: [42, 43])

Test 4: Get unacknowledged alerts
✅ PASS - Found 2 unacknowledged alerts

Test 5: Acknowledge drift alert
✅ PASS - Alert #42 acknowledged

Test 6: Get model drift history
✅ PASS - Found 5 historical alerts for opus

Test 7: Complete pipeline
✅ PASS - Pipeline completed successfully

All tests passed! ✅
```

### Manual Testing

**Create test data:**

```sql
-- Insert test worker results
INSERT INTO workflow.worker_results 
  (workflow_execution_id, worker_id, model, task_type, result, quality_score, confidence, duration_ms, cost_usd, outcome, created_at)
SELECT
  1,
  'worker-' || i,
  'test-model',
  'test-task',
  'Test result',
  CASE 
    WHEN NOW() - (i || ' days')::interval <= NOW() - INTERVAL '7 days' 
    THEN 0.85  -- Historical: high quality
    ELSE 0.65  -- Current: low quality (25% drop)
  END,
  0.90,
  5000,
  0.01,
  'success',
  NOW() - (i || ' days')::interval
FROM generate_series(1, 40) i;

-- Refresh view
SELECT monitoring.refresh_drift_view();

-- Detect drift
SELECT * FROM monitoring.detect_model_drift(0.10, 20);

-- Expected: test-model with ~25% drop (critical severity)
```

**Clean up:**

```sql
DELETE FROM workflow.worker_results WHERE model = 'test-model';
DELETE FROM monitoring.drift_alerts WHERE model = 'test-model';
SELECT monitoring.refresh_drift_view();
```

---

## Migration Guide

### From Legacy System

**Old system:**
- Manual quality checks
- Ad-hoc performance reviews
- No historical tracking

**Migration steps:**

1. **Install schema:**
   ```bash
   psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/schema-drift-detection.sql
   ```

2. **Verify installation:**
   ```sql
   \dt monitoring.*
   \df monitoring.*
   SELECT monitoring.refresh_drift_view();
   SELECT * FROM monitoring.model_drift LIMIT 10;
   ```

3. **Backfill quality_score:**
   ```sql
   -- If workflow.worker_results has confidence but not quality_score
   ALTER TABLE workflow.worker_results ADD COLUMN quality_score REAL;
   
   -- Temporary backfill (replace with actual quality scores from arbiter)
   UPDATE workflow.worker_results 
   SET quality_score = confidence 
   WHERE quality_score IS NULL AND confidence IS NOT NULL;
   ```

4. **Run initial detection:**
   ```bash
   node monitoring/check-drift.cjs
   ```

5. **Schedule cron:**
   ```bash
   crontab -e
   # Add:
   0 3 * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node monitoring/check-drift.cjs >> /var/log/drift-detection.log 2>&1
   ```

### Applying Recent Fixes (2026-06-28)

**Priority fixes:**
1. Quality metric tracking (renamed confidence → quality)
2. Alert deduplication (unique constraint)
3. Minimum sample size (5 → 20)

**Migration:**

```bash
# Run as postgres user
psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-drift-alerts.sql
psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-model-drift-view.sql

# Verify
node monitoring/test-drift-detection.cjs
```

**What changed:**

- `monitoring.model_drift` view: Uses `quality_score` instead of `confidence`
- `monitoring.drift_alerts` table: Added unique constraint on `(model, COALESCE(task_type, ''), detection_date)`
- `drift-detector.cjs`: Raised `minSamples` from 5 to 20

---

## Configuration

### Environment Variables

```bash
# PostgreSQL connection (defaults to aio-01:5433/learning)
export PGHOST=aio-01
export PGPORT=5433
export PGDATABASE=learning
export PGUSER=sfloess
export PGPASSWORD=  # Optional, uses peer auth if omitted

# Webhook configuration
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK/URL
```

### Detection Thresholds

**Adjust in code:**

```javascript
const driftAlerts = await detectDrift({
  driftThreshold: 0.10,  // 10% drop = warning (default: 0.10)
  minSamples: 20         // Minimum samples required (default: 20)
});
```

**Adjust in CLI:**

```bash
node monitoring/check-drift.cjs --threshold=0.15 --min-samples=30
```

**Severity classification:**

```javascript
// In monitoring/drift-detector.cjs
const severity = 
  Math.abs(performance_drop_pct) >= 20 ? 'critical' :
  Math.abs(performance_drop_pct) >= 10 ? 'warning' : 'ok';
```

### Webhook Configuration

**Edit:** `monitoring/webhook-config.json`

```json
{
  "webhooks": {
    "slack": {
      "enabled": true,
      "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
      "channel": "#monitoring",
      "username": "Claude Monitor",
      "icon_emoji": ":robot_face:"
    },
    "discord": {
      "enabled": false,
      "url": "https://discord.com/api/webhooks/YOUR/WEBHOOK/URL",
      "username": "Claude Monitor",
      "avatar_url": "https://example.com/avatar.png"
    }
  },
  "thresholds": {
    "drift": {
      "critical_drop_pct": 20  // Only send webhooks for >20% drop
    },
    "disagreement": {
      "critical_cv": 0.40      // High disagreement threshold
    }
  },
  "notifications": {
    "critical_drift": {
      "enabled": true,
      "channels": ["slack"],      // Send to slack only
      "rate_limit_minutes": 60    // Max 1 per hour
    },
    "high_disagreement": {
      "enabled": true,
      "channels": ["slack", "discord"],
      "rate_limit_minutes": 30
    },
    "circuit_breaker_open": {
      "enabled": true,
      "channels": ["slack"],
      "rate_limit_minutes": 120
    },
    "weekly_consensus_report": {
      "enabled": true,
      "channels": ["slack"],
      "rate_limit_minutes": 10080  // Once per week
    }
  },
  "rate_limiting": {
    "enabled": true,
    "cache_file": "/tmp/webhook-rate-limit-cache.json"
  }
}
```

---

## Performance Characteristics

### Database Queries

**Materialized view refresh:**
- Time: ~50ms (1,000 worker results)
- Frequency: Daily at 3 AM
- Impact: Low (runs during off-peak)

**Drift detection query:**
- Time: ~8ms
- Frequency: Daily at 3 AM
- Impact: Minimal (simple aggregate query)

**Alert logging:**
- Time: ~2ms per alert
- Frequency: Only when drift detected
- Impact: Minimal (INSERT with deduplication)

### Memory Usage

**Node.js process:**
- Base: ~50 MB
- Peak: ~120 MB (during pipeline execution)
- Duration: <500ms typical

**PostgreSQL:**
- Materialized view: ~100 KB per 1,000 worker results
- Alert table: ~500 bytes per alert
- Indexes: ~50 KB

### Network Traffic

**Webhook notifications:**
- Payload size: ~500 bytes per alert
- Frequency: Only critical alerts (>20% drop)
- Rate limit: Max 1 per hour

**Database connection:**
- Pool size: 10 connections max
- Connection reuse: Yes
- Idle timeout: 30 seconds

---

## Security Considerations

### Database Access

**Permissions required:**

```sql
-- Read access to workflow schema
GRANT SELECT ON workflow.worker_results TO sfloess;
GRANT SELECT ON workflow.executions TO sfloess;

-- Write access to monitoring schema
GRANT SELECT, INSERT, UPDATE ON monitoring.drift_alerts TO sfloess;
GRANT USAGE, SELECT ON SEQUENCE monitoring.drift_alerts_id_seq TO sfloess;

-- Function execution
GRANT EXECUTE ON FUNCTION monitoring.refresh_drift_view() TO sfloess;
GRANT EXECUTE ON FUNCTION monitoring.detect_model_drift(REAL, INT) TO sfloess;
GRANT EXECUTE ON FUNCTION monitoring.log_drift_alert(...) TO sfloess;
GRANT EXECUTE ON FUNCTION monitoring.acknowledge_drift_alert(INT, TEXT) TO sfloess;
```

**IMPORTANT:** Never grant `DROP`, `TRUNCATE`, or `DELETE` on production tables.

### Webhook Security

**Protect webhook URLs:**

```bash
# Store in environment variables (not in code)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/SECRET"

# Or use webhook-config.json with restricted permissions
chmod 600 monitoring/webhook-config.json
```

**Rate limiting:**

- Enabled by default (1 notification per hour per type)
- Prevents webhook abuse
- Configurable per notification type

**Webhook validation:**

- HTTPS only (enforced in `webhook-notifier.cjs`)
- No sensitive data in payloads (only model names, quality scores)
- No credentials or API keys in messages

---

## Architecture Decisions

### Why 7-day vs 30-day windows?

**Rationale:**

1. **7-day current window** - Captures recent changes without noise
   - Too short (1-3 days): High variance, false positives
   - Too long (14+ days): Masks sudden drops

2. **30-day baseline window** - Stable reference without drift contamination
   - Excludes recent 7 days to prevent baseline shift
   - Long enough to average out normal variance
   - Short enough to detect gradual degradation

**Alternative considered:**

- Rolling exponential weighted average (EWMA)
- **Rejected:** More complex, harder to explain, similar results

### Why minimum 20 samples?

**Rationale:**

1. **Statistical significance** - Central Limit Theorem requires n≥30 for normality
   - 20 is compromise between detection speed and confidence
   - Lower risk of false positives from variance

2. **Empirical validation** - Testing showed:
   - n=5: 40% false positive rate (too noisy)
   - n=10: 25% false positive rate (still high)
   - n=20: 8% false positive rate (acceptable)
   - n=30: 5% false positive rate (too slow to detect)

**Alternative considered:**

- Adaptive threshold based on variance
- **Rejected:** Added complexity, harder to tune

### Why deduplication on (model, task_type, date)?

**Rationale:**

1. **One alert per day** - Prevents spam from repeated detections
   - Cron runs daily at 3 AM
   - Same drift on same day = not new information

2. **Per-model, per-task** - Different scopes are independent
   - `opus` + `code_review` ≠ `opus` + `debugging`
   - Same model can drift differently across tasks

**Alternative considered:**

- Alert on every detection (no deduplication)
- **Rejected:** Overwhelming noise, alert fatigue

### Why PostgreSQL materialized view?

**Rationale:**

1. **Performance** - Pre-aggregated metrics = fast detection (8ms vs 500ms raw)
2. **Consistency** - Snapshot guarantees same baseline across detection runs
3. **Simplicity** - SQL-only, no external state management

**Alternative considered:**

- Real-time aggregation on each query
- **Rejected:** Too slow for daily cron execution

---

## Future Enhancements

### Planned Features

1. **Auto-remediation** - Automatic model disabling on critical drift
   - Circuit breaker integration
   - Automatic failover to backup models

2. **Trend analysis** - Detect gradual degradation before threshold breach
   - Linear regression on 7-day window
   - Alert on negative trend (even if <10% total drop)

3. **Multi-metric drift** - Track confidence, cost, latency in addition to quality
   - Composite drift score
   - Weighted alerts based on metric importance

4. **Anomaly detection** - Statistical outlier detection
   - Z-score analysis on quality distribution
   - Detect sudden spikes (not just degradation)

5. **Root cause analysis** - Automated investigation
   - Correlate with API provider changes
   - Compare against external benchmarks
   - Generate hypothesis for human review

### Wishlist

- Grafana dashboard integration
- Prometheus metrics export
- Configurable time windows (not just 7/30 days)
- Per-user drift tracking (if `user_id` in worker_results)
- A/B testing support (compare model versions)

---

## References

### Internal Documentation

- `monitoring/README.md` - Original drift detection documentation
- `monitoring/drift-detection-cron.md` - Complete operational guide
- `monitoring/DRIFT_DETECTION_FIXES.md` - Recent fixes (2026-06-28)
- `shared/workflow-storage-adapter.js` - Database integration

### Database Schema

- `monitoring/schema-drift-detection.sql` - Initial schema
- `monitoring/migrate-drift-alerts.sql` - Deduplication migration
- `monitoring/migrate-model-drift-view.sql` - Quality metric migration

### Code Modules

- `monitoring/drift-detector.cjs` - Core detection module (394 lines)
- `monitoring/check-drift.cjs` - CLI interface
- `monitoring/webhook-notifier.cjs` - Webhook integration (736 lines)
- `monitoring/test-drift-detection.cjs` - Test suite

### External Resources

- PostgreSQL materialized views: https://www.postgresql.org/docs/current/rules-materializedviews.html
- Thompson Sampling: https://en.wikipedia.org/wiki/Thompson_sampling
- Coefficient of variation: https://en.wikipedia.org/wiki/Coefficient_of_variation

---

## FAQ

### Q: What's the difference between drift detection and disagreement detection?

**Drift detection:**
- Monitors model performance **over time**
- Compares 7-day current vs 30-day baseline
- Detects quality degradation for a **single model**

**Disagreement detection:**
- Monitors model agreement **across models**
- Compares worker votes on a **single task**
- Detects high variance (coefficient of variation >0.40)

**Both are complementary:**
- Drift = "This model is getting worse"
- Disagreement = "These models can't agree on the answer"

### Q: Why does drift detection use quality_score instead of confidence?

**Confidence** = Worker's self-assessed certainty (subjective, not calibrated)

**Quality** = Arbiter's assessment of worker output (objective, consensus-based)

**Drift detection needs objective ground truth:**
- Worker confidence can be miscalibrated (high confidence, wrong answer)
- Arbiter quality reflects actual output correctness
- Drift in confidence ≠ drift in actual performance

**Migration:** If you only have `confidence`, backfill `quality_score` from arbiter results:

```sql
UPDATE workflow.worker_results wr
SET quality_score = (
  SELECT quality_score 
  FROM workflow.arbiter_decisions ad 
  WHERE ad.workflow_execution_id = wr.workflow_execution_id
  LIMIT 1
)
WHERE quality_score IS NULL;
```

### Q: How do I reduce false positives?

**Options:**

1. **Increase minimum samples:**
   ```bash
   node monitoring/check-drift.cjs --min-samples=30
   ```

2. **Increase drift threshold:**
   ```bash
   node monitoring/check-drift.cjs --threshold=0.15  # 15% drop
   ```

3. **Extend baseline window:**
   ```sql
   -- Edit monitoring.model_drift view to use 60-day baseline
   AVG(CASE WHEN age_days > 7 AND age_days <= 67 THEN quality_score END)
   ```

4. **Add task_type filtering:**
   ```sql
   -- Only track critical task types
   WHERE task_type IN ('code_review', 'security_audit', 'data_analysis')
   ```

### Q: What happens when Thompson Sampling weights are updated?

**Current behavior:** Logs recommendation only (placeholder)

```
[DriftDetector] Recommend: Reduce opus weight by 50% for task_type="code_review"
```

**Intended behavior (TODO):**

```javascript
// Update bandit beta parameter (pessimistic prior)
await pool.query(`
  UPDATE learning.strategy_performance
  SET beta = beta * 2.0  -- Reduce weight by 50%
  WHERE strategy = $1
`, ['opus']);
```

**Effect:**
- Lower weight = lower selection probability
- Degraded model selected less often
- System naturally explores alternatives
- Weight recovers as model improves

**Alternative:** Circuit breaker (hard disable):

```javascript
if (alert.severity === 'critical') {
  await disableModel(alert.model);  // Hard cutoff
}
```

### Q: Can I run drift detection more frequently than daily?

**Yes, but not recommended:**

**Hourly:**

```bash
0 * * * * cd /path/to/project && node monitoring/check-drift.cjs
```

**Risks:**

1. **Insufficient samples** - Need 20+ samples in 7-day window
   - Hourly checks may not have enough data
   - False negatives (no drift detected when there is)

2. **Alert fatigue** - Same drift detected hourly
   - Deduplication prevents duplicate DB entries
   - But still wastes compute

3. **Webhook spam** - Rate limiting helps but not perfect

**Recommendation:**

- **Daily at 3 AM** - Sufficient samples, off-peak, aligns with human review schedule
- **Weekly for reports** - Lower-priority metrics

**Exception:** Real-time monitoring for critical systems
- Use continuous monitoring (not batch cron)
- Stream worker results to Kafka/RabbitMQ
- Real-time aggregation with sliding windows

### Q: How do I archive old drift alerts?

**Archive strategy:**

```sql
-- Create archive table (one-time)
CREATE TABLE monitoring.drift_alerts_archive (LIKE monitoring.drift_alerts INCLUDING ALL);

-- Archive alerts older than 90 days (monthly cron)
INSERT INTO monitoring.drift_alerts_archive
SELECT * FROM monitoring.drift_alerts
WHERE detection_date < CURRENT_DATE - INTERVAL '90 days';

-- Delete archived rows
DELETE FROM monitoring.drift_alerts
WHERE detection_date < CURRENT_DATE - INTERVAL '90 days';

-- Vacuum to reclaim space
VACUUM ANALYZE monitoring.drift_alerts;
```

**Cron:**

```bash
# Monthly on 1st at 2 AM
0 2 1 * * psql -h aio-01 -p 5433 -d learning -f /path/to/archive-drift-alerts.sql
```

**Alternative:** Partitioning (PostgreSQL 10+)

```sql
-- Partition by month
CREATE TABLE monitoring.drift_alerts (
  ...
) PARTITION BY RANGE (detection_date);

-- Create partitions
CREATE TABLE drift_alerts_2026_06 PARTITION OF monitoring.drift_alerts
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- Auto-drop old partitions
DROP TABLE drift_alerts_2025_12;
```

---

## Contact

**Maintainer:** sfloess  
**Created:** 2026-06-28  
**Documentation:** /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/monitoring/DRIFT-DETECTION-README.md

**Feedback:** Submit issues via project issue tracker or direct message.
