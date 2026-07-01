# Consensus Replay Integration Guide

**Status:** Integrated and Ready  
**Issue:** #265  
**Files Added:** 3 files  
**Files Modified:** 1 file

## Overview

The consensus-replay system allows you to re-run historical consensus workflows with current model weights to measure improvement or degradation over time. This is essential for tracking model quality evolution on your specific workload.

## Integration Points

### 1. CLI Tool: `bin/replay-consensus`

**Location:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/bin/replay-consensus`

The primary interface for replaying workflows.

```bash
# List recent workflows
bin/replay-consensus --list --limit 20

# Replay specific workflow with HTML report
bin/replay-consensus orchestrator-1782851258 \
  --html-report /tmp/replay.html \
  --store

# Replay latest successful workflow
bin/replay-consensus --latest --store

# Batch replay all workflows from last 7 days
bin/replay-consensus --batch-recent --days 7 --store
```

**Features:**
- Lists available workflows from PostgreSQL
- Replays individual or batch workflows
- Generates HTML comparison reports
- Stores results to `workflow.replays` table
- Supports model override for A/B testing

### 2. Programmatic API: `workflow-completion-hook.js`

**Location:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/workflow-completion-hook.js`

Added two new functions:

```javascript
const { replayWorkflow, getReplayHistory } = require('./shared/workflow-completion-hook');

// Replay a workflow
const comparison = await replayWorkflow('orchestrator-1782851258', {
  sameModels: true,
  store: true
});

console.log('Verdict:', comparison.summary.verdict);
console.log('Confidence Delta:', comparison.summary.avg_confidence_delta);

// Get replay history
const history = await getReplayHistory('orchestrator-1782851258');
console.log('Times replayed:', history.length);
```

**API Functions:**

- `replayWorkflow(workflowId, options)` - Replay a historical workflow
  - `options.sameModels` - Use same models as original (default: true)
  - `options.overrideModels` - Override with specific models (array)
  - `options.store` - Store replay results to database (default: false)
  - Returns: Comparison object with verdict and deltas

- `getReplayHistory(workflowId)` - Get all replays for a workflow
  - Returns: Array of replay records with timestamps and verdicts

### 3. Direct Class Import: `consensus-replay.cjs`

**Location:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/consensus-replay.cjs`

For full control over the replay process:

```javascript
const { ConsensusReplay } = require('./shared/consensus-replay.cjs');

const replay = new ConsensusReplay();

try {
  // Fetch historical workflow
  const historical = await replay.fetchHistoricalWorkflow('wf-123');
  
  // Re-run with current models
  const newRun = await replay.rerunConsensus(historical, {
    overrideModels: ['opus', 'sonnet', 'haiku', 'fable']
  });
  
  // Compare results
  const comparison = replay.compareResults(historical, newRun);
  
  // Generate HTML report
  replay.generateHTMLReport(comparison, '/tmp/report.html');
  
  // Store to database
  await replay.storeReplayResults(comparison);
  
} finally {
  await replay.close();
}
```

## Database Schema

### `workflow.replays` Table

Auto-created on first use:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `original_workflow_id` | VARCHAR(255) | Workflow being replayed |
| `replayed_at` | TIMESTAMP | When replay occurred |
| `original_created_at` | TIMESTAMP | When original workflow ran |
| `avg_confidence_delta` | NUMERIC | Average worker confidence change |
| `arbiter_confidence_delta` | NUMERIC | Arbiter confidence change |
| `total_cost_delta` | NUMERIC | Cost difference |
| `verdict` | VARCHAR(50) | IMPROVEMENT / NO_CHANGE / DEGRADATION |
| `comparison_data` | JSONB | Full comparison details |
| `created_at` | TIMESTAMP | Record creation time |

### Useful Queries

```sql
-- Find workflows with significant improvement
SELECT original_workflow_id, avg_confidence_delta, verdict
FROM workflow.replays
WHERE verdict = 'SIGNIFICANT_IMPROVEMENT'
ORDER BY avg_confidence_delta DESC
LIMIT 10;

-- Track quality trends over time
SELECT
  DATE(replayed_at) as replay_date,
  AVG(avg_confidence_delta) as avg_improvement,
  COUNT(*) as total_replays
FROM workflow.replays
GROUP BY DATE(replayed_at)
ORDER BY replay_date DESC;

-- Find degraded workflows (need attention)
SELECT original_workflow_id, avg_confidence_delta, arbiter_confidence_delta
FROM workflow.replays
WHERE verdict = 'DEGRADATION'
ORDER BY avg_confidence_delta ASC;

-- Replay history for specific workflow
SELECT replayed_at, verdict, avg_confidence_delta
FROM workflow.replays
WHERE original_workflow_id = 'orchestrator-1782851258'
ORDER BY replayed_at DESC;
```

## Use Cases

### 1. Model Update Validation

After updating models, replay historical workflows to verify quality didn't degrade:

```bash
# Replay all successful workflows from last 30 days
bin/replay-consensus --batch-recent --days 30 --store

# Check for degradations
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT original_workflow_id, avg_confidence_delta, verdict
  FROM workflow.replays
  WHERE replayed_at > NOW() - INTERVAL '1 hour'
    AND verdict = 'DEGRADATION'
"
```

### 2. Nightly Quality Monitoring

Set up automated nightly replays:

```bash
#!/bin/bash
# /home/sfloess/bin/nightly-consensus-replay.sh

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Replay all workflows from last 7 days
bin/replay-consensus --batch-recent --days 7 --store >> /tmp/nightly-replay.log 2>&1

# Email summary if degradations found
DEGRADATIONS=$(psql -h aio-01 -p 5433 -U sfloess -d learning -t -c "
  SELECT COUNT(*) FROM workflow.replays
  WHERE replayed_at > NOW() - INTERVAL '1 day'
    AND verdict = 'DEGRADATION'
")

if [ "$DEGRADATIONS" -gt 0 ]; then
  echo "WARNING: $DEGRADATIONS workflows degraded" | mail -s "Consensus Quality Alert" user@example.com
fi

# Crontab entry:
# 0 2 * * * /home/sfloess/bin/nightly-consensus-replay.sh
```

### 3. A/B Testing Model Configurations

Test different model combinations:

```javascript
const { ConsensusReplay } = require('./shared/consensus-replay.cjs');

async function testModelConfig() {
  const replay = new ConsensusReplay();
  
  const workflowId = 'orchestrator-1782851258';
  const historical = await replay.fetchHistoricalWorkflow(workflowId);
  
  // Test different configurations
  const configs = [
    ['opus', 'sonnet', 'haiku', 'fable'],
    ['opus', 'sonnet', 'gpt-4o', 'gemini'],
    ['sonnet', 'haiku', 'fable', 'gpt-4o']
  ];
  
  for (const models of configs) {
    const newRun = await replay.rerunConsensus(historical, {
      overrideModels: models
    });
    const comparison = replay.compareResults(historical, newRun);
    
    console.log(`Config ${models.join(',')}:`);
    console.log(`  Verdict: ${comparison.summary.verdict}`);
    console.log(`  Avg Confidence Δ: ${comparison.summary.avg_confidence_delta}`);
  }
  
  await replay.close();
}
```

### 4. Track Quality Evolution

Monitor how model quality changes over weeks/months:

```sql
-- Monthly improvement trends
SELECT
  DATE_TRUNC('month', replayed_at) as month,
  AVG(avg_confidence_delta) as avg_improvement,
  COUNT(*) as total_replays,
  SUM(CASE WHEN verdict LIKE '%IMPROVEMENT%' THEN 1 ELSE 0 END) as improvements,
  SUM(CASE WHEN verdict = 'DEGRADATION' THEN 1 ELSE 0 END) as degradations
FROM workflow.replays
GROUP BY DATE_TRUNC('month', replayed_at)
ORDER BY month DESC;

-- Best performing workflows
SELECT
  original_workflow_id,
  MAX(avg_confidence_delta) as best_improvement,
  MIN(avg_confidence_delta) as worst_delta,
  COUNT(*) as replay_count
FROM workflow.replays
GROUP BY original_workflow_id
HAVING COUNT(*) > 5
ORDER BY best_improvement DESC;
```

## Integration Examples

See `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/consensus-replay-integration-example.js` for complete code examples covering:

1. CLI wrapper usage
2. Programmatic API from workflow-completion-hook
3. Direct ConsensusReplay class
4. Automated nightly replay
5. Integration with consensus-engine
6. Query replay trends
7. Automated cron job setup

## How to Replay a Consensus Decision

### Quick Start (3 steps)

1. **List available workflows:**
   ```bash
   bin/replay-consensus --list --limit 20
   ```

2. **Replay a specific workflow:**
   ```bash
   bin/replay-consensus <workflow-id> --html-report /tmp/replay.html --store
   ```

3. **View results:**
   - Console output shows verdict and confidence deltas
   - HTML report at `/tmp/replay.html`
   - Database record in `workflow.replays` table

### Example Session

```bash
# List recent workflows
$ bin/replay-consensus --list --limit 5

Available Workflows:

ID                             Name                 Outcome    Workers Created
------------------------------------------------------------------------------------------------
orchestrator-1782851258        fleet-orchestrator   failed     0       6/30/2026, 4:27:38 PM
orchestrator-1782851030        fleet-orchestrator   failed     0       6/30/2026, 4:23:50 PM
orchestrator-1782851018        fleet-orchestrator   failed     0       6/30/2026, 4:23:38 PM

Total: 5

Replay with: replay-consensus <workflow-id> [options]

# Replay a workflow
$ bin/replay-consensus orchestrator-1782851258 --store

Fetching historical workflow: orchestrator-1782851258
Found workflow from 2026-06-30T20:27:38.382Z
Task: What is 3+5? Just the number...
Workers: 0

Re-running consensus with current models...
Replaying workflow with 0 workers:

Comparing results...

=== COMPARISON SUMMARY ===
Verdict: NO_SIGNIFICANT_CHANGE
Avg Confidence Delta: 0.000
Arbiter Confidence Delta: 0.000
Total Cost Delta: $0.0000

Storing replay results to database...
Stored as replay ID: 1
```

## Files Added/Modified

### Added Files

1. **`bin/replay-consensus`** (executable CLI wrapper)
   - List workflows
   - Replay individual/batch workflows
   - Generate HTML reports
   - Store results

2. **`shared/consensus-replay-integration-example.js`** (code examples)
   - 7 complete integration examples
   - Automated cron job template
   - A/B testing patterns

3. **`docs/CONSENSUS_REPLAY_INTEGRATION.md`** (this file)
   - Complete integration guide
   - API documentation
   - Use cases and examples

### Modified Files

1. **`shared/workflow-completion-hook.js`**
   - Added `replayWorkflow()` function
   - Added `getReplayHistory()` function
   - Now exports consensus-replay functionality

## Dependencies

- **PostgreSQL** (aio-01:5433) with `workflow` schema
- **Node.js** pg library (already installed)
- **consensus-replay.cjs** (already exists, 21KB)
- **Claude CLI** (for re-running workers)

## Testing

Basic integration test available:

```bash
node shared/test-consensus-replay-integration.cjs
```

Tests:
- Direct import of ConsensusReplay class
- Database connection
- Workflow listing
- Historical workflow fetching
- Replay table schema verification
- CLI wrapper exists and is executable

## Next Steps

1. **Test replay on a real workflow:**
   ```bash
   bin/replay-consensus --latest --html-report /tmp/first-replay.html
   ```

2. **Set up nightly automated replays:**
   - Create `/home/sfloess/bin/nightly-consensus-replay.sh`
   - Add to crontab: `0 2 * * * /home/sfloess/bin/nightly-consensus-replay.sh`

3. **Monitor quality trends:**
   ```sql
   SELECT DATE(replayed_at), AVG(avg_confidence_delta), COUNT(*)
   FROM workflow.replays
   GROUP BY DATE(replayed_at)
   ORDER BY DATE(replayed_at) DESC;
   ```

## Troubleshooting

### "Workflow not found"

Ensure the workflow has workers and exists in `workflow.executions`:

```sql
SELECT workflow_id, total_workers
FROM workflow.executions
WHERE workflow_id = 'your-workflow-id';
```

### "Cannot use a pool after calling end"

Create a new ConsensusReplay instance for each replay operation:

```javascript
// DON'T: Reuse same instance
const replay = new ConsensusReplay();
await replay.rerunConsensus(...);
await replay.close();
await replay.rerunConsensus(...); // ERROR

// DO: New instance per operation
async function replayOne(wfId) {
  const replay = new ConsensusReplay();
  try {
    await replay.rerunConsensus(...);
  } finally {
    await replay.close();
  }
}
```

### "No successful workflows found"

Check if workflows have outcome='success' and total_workers > 0:

```sql
SELECT COUNT(*)
FROM workflow.executions
WHERE outcome = 'success' AND total_workers > 0;
```

## Summary

Consensus-replay is now integrated and accessible via:

1. **CLI:** `bin/replay-consensus` for interactive/scripted use
2. **API:** `workflow-completion-hook.js` for programmatic integration
3. **Direct:** `consensus-replay.cjs` for full control

All replay data is stored in `workflow.replays` table for long-term trend analysis.

Use cases:
- Model update validation
- Nightly quality monitoring
- A/B testing model configs
- Quality evolution tracking

**Integration complete. Ready to use.**
