# Model Usage Tracking

**Status:** ✅ Production Ready  
**Created:** 2026-07-08  
**Purpose:** Track which models are used, why, and for what tasks - CRITICAL for Red Hat compliance

---

## Overview

Every model selection is logged with:
- **Which model** was selected
- **Why** it was selected (task type, filter rules)
- **When** it was used (timestamp)
- **What rules** were applied (whitelist, blacklist, Anthropic-only)
- **Which workflow** invoked the selection
- **Context** (additional metadata)

**Storage:** PostgreSQL `monitoring.model_usage` table (with local file fallback)

---

## Quick Commands

### View usage statistics

```bash
# Last 24 hours (default)
node tools/view-model-usage.cjs

# Last 7 days
node tools/view-model-usage.cjs 168

# Last hour
node tools/view-model-usage.cjs 1
```

### PostgreSQL queries

```bash
# Connect
psql -h aio-01 -p 5433 -U claude -d learning

# View recent selections
SELECT timestamp, model, task_type, filter_reason, anthropic_only
FROM monitoring.model_usage
ORDER BY timestamp DESC
LIMIT 20;

# Model distribution (last 24 hours)
SELECT * FROM monitoring.model_usage_stats_24h;

# Check Red Hat compliance
SELECT *
FROM monitoring.model_usage
WHERE task_type LIKE 'redhat_%'
  AND model NOT LIKE '%opus%'
  AND model NOT LIKE '%sonnet%'
  AND model NOT LIKE '%haiku%'
  AND model NOT LIKE '%fable%'
  AND model NOT LIKE '%claude%';
-- Should return 0 rows!

# Model usage by task type
SELECT task_type, model, COUNT(*) as count
FROM monitoring.model_usage
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY task_type, model
ORDER BY count DESC;

# Anthropic-only enforcement rate
SELECT 
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE anthropic_only = true) as anthropic_only,
  ROUND(COUNT(*) FILTER (WHERE anthropic_only = true)::numeric / COUNT(*) * 100, 1) as pct
FROM monitoring.model_usage
WHERE timestamp > NOW() - INTERVAL '24 hours';
```

---

## Example Output

```bash
$ node tools/view-model-usage.cjs

========================================
MODEL USAGE REPORT (last 24 hours)
========================================

Total selections: 156
Anthropic-only enforced: 42 (26.9%)
Filtered selections: 98 (62.8%)

MODEL DISTRIBUTION:
─────────────────────────────
  claude-sonnet-4.5          56 (35.9%) ███████████████████
  claude-opus-4.8            42 (26.9%) █████████████
  deepseek-coder             28 (17.9%) ████████
  gpt-4o                     18 (11.5%) █████
  qwen-coder                 12 (7.7%)  ███

TASK TYPE DISTRIBUTION:
─────────────────────────────
  code_review                 45 (28.8%) ██████████████
  redhat_code_review          42 (26.9%) █████████████
  research                    32 (20.5%) ██████████
  documentation               20 (12.8%) ██████
  consensus                   17 (10.9%) █████

RED HAT COMPLIANCE CHECK:
─────────────────────────────
✓ NO VIOLATIONS - All Red Hat tasks used Anthropic models only!

RECENT SELECTIONS (last 10):
─────────────────────────────
  2:45:23 PM claude-sonnet-4.5      redhat_code_review [ANTHROPIC-ONLY]
             └─ Red Hat proprietary code - Anthropic models only
  2:44:18 PM deepseek-coder          code_review
             └─ Code review requires strong reasoning
  2:42:10 PM claude-opus-4.8         redhat_security_audit [ANTHROPIC-ONLY]
             └─ Red Hat security - highest accuracy required
```

---

## Database Schema

```sql
CREATE TABLE monitoring.model_usage (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  model TEXT NOT NULL,
  task_type TEXT,
  filter_reason TEXT,
  pool JSONB,
  pool_source TEXT,
  rules_applied JSONB,
  workflow TEXT,
  context TEXT,
  anthropic_only BOOLEAN DEFAULT false,
  whitelist JSONB,
  blacklist JSONB
);
```

### Indexes

- `idx_model_usage_timestamp` - Fast time-range queries
- `idx_model_usage_task_type` - Filter by task
- `idx_model_usage_model` - Filter by model
- `idx_model_usage_anthropic_only` - Compliance checks

### Materialized View

```sql
CREATE VIEW monitoring.model_usage_stats_24h AS
SELECT 
  model,
  task_type,
  COUNT(*) as usage_count,
  COUNT(*) FILTER (WHERE anthropic_only = true) as anthropic_only_count,
  MIN(timestamp) as first_used,
  MAX(timestamp) as last_used
FROM monitoring.model_usage
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY model, task_type
ORDER BY usage_count DESC;
```

---

## API Usage

### Log usage (automatic)

This happens automatically in `get-next-arbiter.js`:

```javascript
const { logModelUsage } = require('./shared/model-usage-tracker.cjs');

await logModelUsage({
  model: 'opus',
  taskType: 'redhat_code_review',
  filterReason: 'Red Hat proprietary code - Anthropic models only',
  pool: ['opus', 'sonnet'],
  poolSource: 'quality_first_task_aware_filtered',
  rulesApplied: { anthropic_only: true, whitelist: ['opus', 'sonnet'] },
  workflow: 'ai-consensus',
  context: 'Reviewing authentication changes'
});
```

### Get recent usage

```javascript
const { getRecentUsage } = require('./shared/model-usage-tracker.cjs');

// Last 100 selections
const recent = await getRecentUsage({ limit: 100, hours: 24 });

// Filter by task type
const redhatOnly = await getRecentUsage({ 
  taskType: 'redhat_code_review',
  hours: 168  // 7 days
});
```

### Get statistics

```javascript
const { getUsageStats } = require('./shared/model-usage-tracker.cjs');

const stats = await getUsageStats(24);  // Last 24 hours

console.log(stats.total);  // Total selections
console.log(stats.by_model);  // Count per model
console.log(stats.by_task_type);  // Count per task
console.log(stats.anthropic_only_count);  // Compliance count
console.log(stats.model_distribution);  // Percentages
```

### Check compliance

```javascript
const { checkRedHatCompliance } = require('./shared/model-usage-tracker.cjs');

const violations = await checkRedHatCompliance(168);  // 7 days

if (violations.length > 0) {
  console.error('⚠️  RED HAT COMPLIANCE VIOLATIONS!');
  for (const v of violations) {
    console.error(`${v.timestamp}: ${v.task_type} used ${v.model}`);
  }
}
```

---

## Integration Points

### Automatically tracked

- ✅ `get-next-arbiter.js` - Logs every selection
- ✅ All consensus workflows using `get-next-arbiter`

### Manual tracking (optional)

For workflows that don't use `get-next-arbiter`:

```javascript
const { logModelUsage } = require('./shared/model-usage-tracker.cjs');

// Before using a model
await logModelUsage({
  model: 'custom-model',
  taskType: 'custom_task',
  workflow: 'my-workflow',
  context: 'Why this model was chosen'
});
```

---

## Monitoring Alerts

### Set up alerts

```bash
# Add to crontab - check every hour
0 * * * * cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node tools/check-compliance.cjs | mail -s "Model Compliance Check" scot@example.com
```

### Create check script

```javascript
// tools/check-compliance.cjs
const { checkRedHatCompliance } = require('../shared/model-usage-tracker.cjs');

async function main() {
  const violations = await checkRedHatCompliance(24);
  
  if (violations.length > 0) {
    console.log('⚠️  VIOLATIONS DETECTED!');
    for (const v of violations) {
      console.log(`${v.timestamp}: ${v.task_type} -> ${v.model}`);
    }
    process.exit(1);
  } else {
    console.log('✓ No violations in last 24 hours');
    process.exit(0);
  }
}

main();
```

---

## Files

| File | Purpose |
|------|---------|
| `shared/model-usage-tracker.cjs` | Core tracking library |
| `tools/view-model-usage.cjs` | CLI viewer (statistics + compliance) |
| `skills/misc/get-next-arbiter.js` | Automatic logging integration |
| `docs/MODEL_USAGE_TRACKING.md` | This document |

---

## FAQ

**Q: What if PostgreSQL is unavailable?**  
A: Falls back to local JSONL file at `~/.claude/learning/model-usage-log.jsonl`

**Q: How long is data retained?**  
A: Forever (no automatic cleanup). Archive/truncate manually if needed.

**Q: Can I disable tracking?**  
A: Technically yes, but DON'T - it's critical for Red Hat compliance!

**Q: What if I see violations?**  
A: Investigate immediately! Red Hat code MUST NOT go to third-party models.

**Q: How much data does this generate?**  
A: ~500 bytes per selection. 1000 selections/day = ~500KB/day = ~180MB/year.

---

## Next Steps

1. ✅ Tracking implemented
2. ✅ PostgreSQL table created
3. ✅ Integrated into `get-next-arbiter`
4. ✅ CLI viewer created
5. ⏳ TODO: Set up compliance alerts (cron + email)
6. ⏳ TODO: Create Grafana dashboard for usage visualization

**Status: Production ready! Start tracking immediately! 🎉**
