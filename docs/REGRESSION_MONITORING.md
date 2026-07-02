# Model Regression Monitoring System

**Status:** Production (Wired 2026-07-02, Issue #265)

## Overview

Automated system to detect model performance changes over time by replaying historical consensus workflows and comparing results.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Weekly Cron Job (Sundays 2am)              │
│  tools/model_regression_monitor.cjs                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           shared/consensus-replay.cjs                        │
│  1. Fetch historical workflows (last 4 weeks)               │
│  2. Select representative samples (one per workflow type)   │
│  3. Re-run with current model weights                       │
│  4. Compare: confidence, quality, cost, speed               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           PostgreSQL workflow.replays table                  │
│  Stores: verdicts, deltas, comparison data                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│        tools/performance_dashboard.py                        │
│  Display: Recent regression analysis results                │
│  Alerts: DEGRADATION verdicts highlighted in red            │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Consensus Replay Engine
**File:** `shared/consensus-replay.cjs`

Core functionality:
- Fetch historical workflow from `workflow.executions`
- Extract original task + worker assignments
- Re-run with current model weights (or override models)
- Compare results on 4 dimensions:
  - Confidence delta (arbiter + workers)
  - Quality improvement (subjective)
  - Speed delta (duration)
  - Cost delta
- Generate verdict: SIGNIFICANT_IMPROVEMENT, MODERATE_IMPROVEMENT, NO_SIGNIFICANT_CHANGE, DEGRADATION

**CLI Usage:**
```bash
node shared/consensus-replay.cjs <workflow-id> \
  --same-models \
  --html-report /tmp/report.html \
  --store
```

**Programmatic Usage:**
```javascript
const { ConsensusReplay } = require('./shared/consensus-replay.cjs');

const replay = new ConsensusReplay();
const historical = await replay.fetchHistoricalWorkflow('wf-1719594345678');
const newRun = await replay.rerunConsensus(historical);
const comparison = replay.compareResults(historical, newRun);
await replay.storeReplayResults(comparison);
```

### 2. Automated Monitor
**File:** `tools/model_regression_monitor.cjs`

Runs weekly regression analysis:
- Queries last 4 weeks of consensus workflows
- Selects representative samples (one per workflow type)
- Minimum quality threshold (exclude failures)
- Re-runs with current models
- Stores results in `workflow.replays`
- Generates HTML reports
- Exits with code 1 if degradations detected (for alerting)

**Manual Run:**
```bash
node tools/model_regression_monitor.cjs --weeks 4 --html /tmp/reports
```

**Automated Setup:**
```bash
./setup-regression-monitoring.sh
```

This creates:
- Cron job: `0 2 * * 0` (Sundays at 2am)
- Log file: `/var/log/model-regression-monitor.log`
- Report directory: `/tmp/consensus-replay-reports`

### 3. Performance Dashboard Integration
**File:** `tools/performance_dashboard.py`

Added section: "Model Regression Analysis (Last 7 Days)"

Displays:
- Recent replay results
- Verdicts (color-coded: green=improvement, red=degradation)
- Confidence deltas
- Cost deltas

**Usage:**
```bash
python3 tools/performance_dashboard.py --hours 24
```

Output includes new section:
```
🔄 Model Regression Analysis (Last 7 Days)
┌──────────────────────┬──────────────────┬────────────────────────────┬──────────────┬────────────┐
│ Workflow ID          │ Replayed         │ Verdict                    │ Confidence Δ │ Cost Δ     │
├──────────────────────┼──────────────────┼────────────────────────────┼──────────────┼────────────┤
│ wf-1719594345678     │ 2026-07-01 02:00 │ SIGNIFICANT_IMPROVEMENT    │ +0.123       │ -$0.0045   │
│ wf-1719594345679     │ 2026-07-01 02:05 │ NO_SIGNIFICANT_CHANGE      │ +0.012       │ +$0.0001   │
│ wf-1719594345680     │ 2026-07-01 02:10 │ DEGRADATION                │ -0.087       │ +$0.0023   │
└──────────────────────┴──────────────────┴────────────────────────────┴──────────────┴────────────┘
```

### 4. Database Schema
**Table:** `workflow.replays`

Created automatically on first run.

```sql
CREATE TABLE workflow.replays (
  id SERIAL PRIMARY KEY,
  original_workflow_id VARCHAR(255),
  replayed_at TIMESTAMP,
  original_created_at TIMESTAMP,
  avg_confidence_delta NUMERIC,
  arbiter_confidence_delta NUMERIC,
  total_cost_delta NUMERIC,
  verdict VARCHAR(50),
  comparison_data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Query Examples:**
```sql
-- Recent degradations
SELECT * FROM workflow.replays
WHERE verdict = 'DEGRADATION'
ORDER BY replayed_at DESC
LIMIT 10;

-- Improvement trends
SELECT
  DATE_TRUNC('week', replayed_at) as week,
  COUNT(*) FILTER (WHERE verdict LIKE '%IMPROVEMENT%') as improvements,
  COUNT(*) FILTER (WHERE verdict = 'DEGRADATION') as degradations
FROM workflow.replays
GROUP BY week
ORDER BY week DESC;
```

## Workflow Selection Strategy

**Goal:** Representative sample, not exhaustive

**Criteria:**
1. Last 4 weeks (configurable via `--weeks`)
2. Success only (exclude failures)
3. Consensus workflows (has arbiter decisions)
4. One per workflow type (diversity)
5. Most recent per type (recency bias)

**Example:** If you have 100 deep-research and 50 code-review workflows, it selects:
- 1 most recent deep-research
- 1 most recent code-review
- etc.

Total: ~10 workflows analyzed per run (fast, focused)

## Verdicts

| Verdict | Criteria | Action |
|---------|----------|--------|
| **SIGNIFICANT_IMPROVEMENT** | Arbiter Δ > +0.1 AND Worker Δ > +0.05 | Celebrate, document what changed |
| **MODERATE_IMPROVEMENT** | Arbiter Δ > +0.05 OR Worker Δ > +0.03 | Track trend |
| **NO_SIGNIFICANT_CHANGE** | Within normal variance | Baseline stable |
| **DEGRADATION** | Arbiter Δ < -0.1 OR Worker Δ < -0.05 | **ALERT**: Investigate model changes |

## Alerting

**Cron job exit code:**
- Exit 0: No degradations
- Exit 1: Degradations detected

**Integration with monitoring:**
```bash
# Example cron with email alert
0 2 * * 0 cd /path/to/claude-global-skills && \
  node tools/model_regression_monitor.cjs --weeks 4 || \
  echo "Model degradation detected" | mail -s "ALERT: Model Regression" admin@example.com
```

## Manual Investigation

When degradation detected:

1. **View HTML report:**
   ```bash
   ls -lt /tmp/consensus-replay-reports/*.html | head -1
   firefox /tmp/consensus-replay-reports/<workflow-id>_<timestamp>.html
   ```

2. **Check database:**
   ```sql
   SELECT comparison_data FROM workflow.replays
   WHERE verdict = 'DEGRADATION'
   ORDER BY replayed_at DESC LIMIT 1;
   ```

3. **Re-run specific workflow:**
   ```bash
   node shared/consensus-replay.cjs wf-<workflow-id> \
     --html-report /tmp/debug-report.html
   ```

4. **Test with different models:**
   ```bash
   node shared/consensus-replay.cjs wf-<workflow-id> \
     --override-models opus,sonnet,haiku
   ```

## Maintenance

**Log rotation:**
```bash
# Add to /etc/logrotate.d/model-regression-monitor
/var/log/model-regression-monitor.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
```

**Report cleanup:**
```bash
# Clean reports older than 30 days
find /tmp/consensus-replay-reports -name "*.html" -mtime +30 -delete
```

**Database cleanup:**
```sql
-- Archive replays older than 90 days
DELETE FROM workflow.replays
WHERE replayed_at < NOW() - INTERVAL '90 days';
```

## Future Enhancements

**Potential additions:**
1. Slack/Discord webhook notifications on degradation
2. Grafana dashboard integration (time series of confidence deltas)
3. A/B testing mode (compare two model sets side-by-side)
4. Fine-tuning impact measurement (replay before/after fine-tuning)
5. Cost optimization mode (find cheaper model combinations with same quality)

## Files Modified (Issue #265)

**New files:**
- `tools/model_regression_monitor.cjs` - Automated weekly monitor
- `setup-regression-monitoring.sh` - One-time setup script
- `docs/REGRESSION_MONITORING.md` - This documentation

**Modified files:**
- `shared/consensus-replay.cjs` - Added production status comment
- `tools/performance_dashboard.py` - Added regression analysis section

**Integration points:**
- `shared/workflow-logger.js` - Already logging to `workflow.executions`
- `workflow.replays` table - Auto-created on first run

## Testing

**Run test analysis:**
```bash
# 1. Setup (one-time)
./setup-regression-monitoring.sh

# 2. Manual test run
node tools/model_regression_monitor.cjs --weeks 1

# 3. Verify results in dashboard
python3 tools/performance_dashboard.py

# 4. Check database
psql -h aio-01 -p 5433 -U claude -d learning \
  -c "SELECT * FROM workflow.replays ORDER BY id DESC LIMIT 5"
```

**Expected output:**
- Console: Verdict summary
- HTML reports: `/tmp/consensus-replay-reports/*.html`
- Database: New rows in `workflow.replays`
- Dashboard: Regression analysis section populated

## Troubleshooting

**Problem:** No workflows selected
- **Cause:** No consensus workflows in last N weeks
- **Fix:** Increase `--weeks` parameter or run some consensus workflows

**Problem:** Claude CLI not found
- **Cause:** `consensus-replay.cjs` uses `claude --model X --message Y`
- **Fix:** Ensure `claude` CLI is in PATH or modify `_executeWorker()` to use API

**Problem:** Permission denied on log file
- **Cause:** `/var/log/model-regression-monitor.log` not writable
- **Fix:** `sudo chown $USER /var/log/model-regression-monitor.log`

**Problem:** Cron job not running
- **Cause:** Crontab not set or PATH issues
- **Fix:** Check `crontab -l` and add `PATH=/usr/local/bin:/usr/bin:/bin` to crontab

## References

- Original implementation: Issue #265 (dead code wire)
- Database schema: `shared/workflow-storage-adapter.js`
- Workflow logging: `shared/workflow-logger.js`
- Performance tracking: `tools/performance_dashboard.py`
