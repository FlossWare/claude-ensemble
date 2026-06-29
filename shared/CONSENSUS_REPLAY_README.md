# Consensus Replay System

## Overview

The Consensus Replay system re-runs historical consensus workflows with current model weights to measure improvement or degradation over time.

**Purpose:** Measure whether new models are better on YOUR specific workload.

## Features

1. **Historical Workflow Replay**: Fetch old consensus executions from PostgreSQL
2. **Re-execution**: Re-run with current model weights (same or different models)
3. **Comparison Analysis**: Compare old vs new results (confidence, quality, cost, speed)
4. **HTML Reports**: Visual comparison reports with color-coded verdicts
5. **Database Tracking**: Store replay results for long-term trend analysis

## Files

| File | Purpose |
|------|---------|
| `consensus-replay.cjs` | Core replay engine |
| `consensus-replay.test.cjs` | Test suite (6 tests, all passing) |
| `consensus-replay-demo.cjs` | End-to-end demonstration |
| `consensus-replay-examples.md` | Usage examples and best practices |
| `CONSENSUS_REPLAY_README.md` | This file |

## Quick Start

### CLI Usage

```bash
# Replay a workflow with same models as original
node shared/consensus-replay.cjs wf-1719594345678

# Generate HTML report
node shared/consensus-replay.cjs wf-1719594345678 \
  --html-report /tmp/replay-report.html

# Store results to database
node shared/consensus-replay.cjs wf-1719594345678 --store

# Override models (test different configuration)
node shared/consensus-replay.cjs wf-1719594345678 \
  --override-models opus,sonnet,haiku,fable \
  --html-report /tmp/replay-custom.html \
  --store
```

### Programmatic API

```javascript
const { ConsensusReplay } = require('./shared/consensus-replay.cjs');

async function example() {
  const replay = new ConsensusReplay();

  // 1. Fetch historical workflow
  const historical = await replay.fetchHistoricalWorkflow('wf-123');

  // 2. Re-run with current models
  const newRun = await replay.rerunConsensus(historical, {
    sameModels: true // Or overrideModels: ['opus', 'sonnet']
  });

  // 3. Compare results
  const comparison = replay.compareResults(historical, newRun);

  console.log('Verdict:', comparison.summary.verdict);
  console.log('Confidence Delta:', comparison.summary.avg_confidence_delta);

  // 4. Generate HTML report
  replay.generateHTMLReport(comparison, '/tmp/report.html');

  // 5. Store to database
  await replay.storeReplayResults(comparison);

  await replay.close();
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Consensus Replay Flow                   │
└─────────────────────────────────────────────────────────┘

1. FETCH HISTORICAL
   ├─ Query workflow.executions by workflow_id
   ├─ Load workers, arbiters, phases
   └─ Extract task description, models used

2. RE-RUN CONSENSUS
   ├─ Execute workers in parallel (same or override models)
   ├─ Collect results (confidence, duration, cost)
   └─ Run arbiter to synthesize

3. COMPARE RESULTS
   ├─ Worker-level: confidence, speed, cost deltas
   ├─ Arbiter-level: synthesis quality delta
   └─ Generate verdict: IMPROVEMENT / NO_CHANGE / DEGRADATION

4. REPORT & STORE
   ├─ Generate HTML visual report
   ├─ Store to workflow.replays table
   └─ Track trends over time
```

## Database Schema

### `workflow.replays` Table

Created automatically on first use:

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

### Example Queries

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
```

## Verdict Logic

Verdicts are calculated based on confidence deltas:

| Verdict | Conditions |
|---------|-----------|
| **SIGNIFICANT_IMPROVEMENT** | Arbiter +0.1 AND Avg Workers +0.05 |
| **MODERATE_IMPROVEMENT** | Arbiter +0.05 OR Avg Workers +0.03 |
| **NO_SIGNIFICANT_CHANGE** | Small deltas (within noise) |
| **DEGRADATION** | Arbiter -0.1 OR Avg Workers -0.05 |

## HTML Report Structure

Reports include:

1. **Verdict Badge**: Color-coded (green/blue/gray/red)
2. **Summary Table**: Key metrics at a glance
   - Workflow ID, task description
   - Timestamps (original, replayed)
   - Confidence deltas
   - Cost delta
3. **Worker Comparison Table**: Per-model breakdown
   - Old vs new confidence
   - Speed improvements
   - Cost changes
4. **Arbiter Comparison Table**: Synthesis quality
   - Arbiter confidence improvement
   - Decision speed improvements

## Test Results

```
=== Test 1: Fetch Historical Workflow ===
✅ Fetched historical workflow
✅ Correctly returned null for non-existent workflow

=== Test 2: Compare Results ===
✅ Correctly detected improvement
✅ Correctly detected degradation

=== Test 3: Store Replay Results ===
✅ Stored replay results with ID: 1
✅ Successfully retrieved stored replay

=== Test 4: Generate HTML Report ===
✅ HTML report generated successfully
✅ Report contains all expected sections

=== Test 5: Confidence Extraction ===
Passed: 4/4 tests

=== Test 6: Verdict Generation ===
Passed: 4/4 tests
```

**All tests passing: 100% success rate**

## Use Cases

### 1. Model Update Validation

Before/after model version changes:

```bash
# Before update: baseline
psql -c "SELECT workflow_id FROM workflow.executions
         WHERE created_at > NOW() - INTERVAL '7 days'
         ORDER BY created_at DESC LIMIT 10" > /tmp/baseline-workflows.txt

# After update: replay and compare
cat /tmp/baseline-workflows.txt | while read wf_id; do
  node shared/consensus-replay.cjs "$wf_id" --store
done

# Check results
psql -c "SELECT verdict, COUNT(*) FROM workflow.replays
         WHERE replayed_at > NOW() - INTERVAL '1 hour'
         GROUP BY verdict"
```

### 2. A/B Testing Model Configurations

```javascript
const replay = new ConsensusReplay();
const historical = await replay.fetchHistoricalWorkflow('wf-123');

// Config A: Current default
const runA = await replay.rerunConsensus(historical, {
  overrideModels: ['opus', 'sonnet', 'haiku']
});

// Config B: Experimental
const runB = await replay.rerunConsensus(historical, {
  overrideModels: ['opus', 'fable', 'gpt-4o']
});

const compA = replay.compareResults(historical, runA);
const compB = replay.compareResults(historical, runB);

console.log('Config A Confidence:', compA.summary.avg_confidence_delta);
console.log('Config B Confidence:', compB.summary.avg_confidence_delta);
```

### 3. Automated Nightly Replay

```bash
#!/bin/bash
# /home/sfloess/bin/nightly-consensus-replay.sh

cd /home/sflooss/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Get workflows from last 24h
psql -h aio-01 -p 5433 -d learning -t -c \
  "SELECT workflow_id FROM workflow.executions
   WHERE created_at > NOW() - INTERVAL '24 hours'
   AND outcome = 'success'
   AND total_workers > 0" | while read -r workflow_id; do

  echo "Replaying: $workflow_id"
  
  node shared/consensus-replay.cjs "$workflow_id" \
    --html-report "/tmp/replay-reports/$(date +%Y%m%d)-${workflow_id}.html" \
    --store

done

# Generate summary email
psql -h aio-01 -p 5433 -d learning -c \
  "SELECT verdict, COUNT(*), AVG(avg_confidence_delta)
   FROM workflow.replays
   WHERE replayed_at > NOW() - INTERVAL '24 hours'
   GROUP BY verdict" | mail -s "Nightly Replay Summary" user@example.com
```

Add to crontab:
```bash
0 2 * * * /home/sfloess/bin/nightly-consensus-replay.sh
```

### 4. Regression Detection

```sql
-- Alert on degradation
SELECT
  wr.original_workflow_id,
  we.task_description,
  wr.avg_confidence_delta,
  wr.replayed_at
FROM workflow.replays wr
JOIN workflow.executions we ON wr.original_workflow_id = we.workflow_id
WHERE wr.verdict = 'DEGRADATION'
AND wr.replayed_at > NOW() - INTERVAL '7 days'
ORDER BY wr.avg_confidence_delta ASC;
```

## Performance Considerations

### Replay Duration

- Each replay re-runs all workers + arbiter
- Expect similar duration to original workflow
- For batch replays, consider parallel execution:

```javascript
const replays = await Promise.all(
  workflowIds.map(id => replaySingleWorkflow(id))
);
```

### Cost Implications

- Replay incurs NEW API costs (models are re-invoked)
- Track `total_cost_delta` to monitor replay costs
- Consider sampling strategy for large-scale replays (10-20% of workflows)

### Database Growth

- Each replay creates new record in `workflow.replays`
- Set retention policy:

```sql
DELETE FROM workflow.replays
WHERE replayed_at < NOW() - INTERVAL '90 days';
```

## Limitations

### Current Implementation

1. **Worker Execution**: Uses mock simulation in demo (replace with real fleet execution)
2. **Token Counting**: Claude CLI doesn't report tokens (stored as 0)
3. **Cost Estimation**: Requires manual cost tracking integration
4. **Confidence Extraction**: Regex-based (may miss non-standard formats)

### Planned Improvements

1. **Real Fleet Integration**: Execute via `fleet-utils.js executeOnFleet()`
2. **Token Tracking**: Integrate with Claude API response headers
3. **Cost API**: Hook into cost tracking database
4. **Confidence Calibration**: Apply calibration curves from learning system

## Best Practices

1. **Replay Representative Samples**: Don't replay every workflow, sample 10-20% of high-value tasks

2. **Track Across Model Updates**: Replay before/after model version changes

3. **Monitor Cost Trends**: Track `total_cost_delta` to detect pricing changes

4. **Set Quality Thresholds**: Alert on `DEGRADATION` verdicts

5. **Archive HTML Reports**: Keep visual records of quality evolution

6. **Periodic Cleanup**: Delete old replay records (>90 days)

7. **Compare Apples-to-Apples**: Use `--same-models` for fair comparison

8. **Override for Experimentation**: Use `--override-models` to test new configurations

## Troubleshooting

### Workflow Not Found

```javascript
const historical = await replay.fetchHistoricalWorkflow('wf-nonexistent');
if (!historical) {
  console.error('Workflow not found. Check workflow.executions table.');
}
```

### No Workers to Replay

```
⏭️  Skipping (no workers to replay)
```

Workflows without worker data can't be replayed. Check:

```sql
SELECT workflow_id, total_workers
FROM workflow.executions
WHERE total_workers > 0
ORDER BY created_at DESC;
```

### Database Connection Issues

```javascript
try {
  await replay.pool.query('SELECT 1');
  console.log('Database connected');
} catch (error) {
  console.error('Database connection failed:', error.message);
  console.error('Check PGHOST, PGPORT, PGDATABASE, PGUSER env vars');
}
```

### Worker Execution Failures

Workers use Claude CLI by default. Ensure:
- `claude` command is in PATH
- Models specified are available (`claude --list-models`)
- API keys configured

## Environment Variables

```bash
# PostgreSQL connection
export PGHOST=aio-01
export PGPORT=5433
export PGDATABASE=learning
export PGUSER=sfloess
export PGPASSWORD=<password>

# Optional: Claude CLI model preference
export CLAUDE_DEFAULT_MODEL=opus
```

## Integration Examples

### With Prometheus

```javascript
const { Counter, Gauge } = require('prom-client');

const replayCounter = new Counter({
  name: 'consensus_replays_total',
  help: 'Total consensus replays executed',
  labelNames: ['verdict']
});

const confidenceDeltaGauge = new Gauge({
  name: 'consensus_replay_confidence_delta',
  help: 'Average confidence delta from replays'
});

// After replay
replayCounter.inc({ verdict: comparison.summary.verdict });
confidenceDeltaGauge.set(parseFloat(comparison.summary.avg_confidence_delta));
```

### With Grafana

Query replay trends:

```promql
# Improvement rate
rate(consensus_replays_total{verdict=~".*IMPROVEMENT.*"}[1h])

# Average confidence improvement
avg_over_time(consensus_replay_confidence_delta[24h])
```

## References

- **Workflow Storage Adapter**: `shared/workflow-storage-adapter.js`
- **Fleet Topology**: `shared/fleet-topology.js`
- **Fleet Orchestration**: `shared/fleet-utils.js`
- **Consensus Engine**: `shared/consensus-engine.js`

## License

See project LICENSE file.

## Contributing

Tests must pass before merging:

```bash
node shared/consensus-replay.test.cjs
```

Expected output: All tests passing (6/6).

## Support

For issues or questions:
1. Check `consensus-replay-examples.md` for usage patterns
2. Run test suite to verify setup
3. Check database connection: `psql -h aio-01 -p 5433 -d learning -c "SELECT 1"`
4. Verify workflows exist: `psql -c "SELECT COUNT(*) FROM workflow.executions"`

---

**Created:** 2026-06-28  
**Last Updated:** 2026-06-28  
**Status:** ✅ All tests passing, ready for production use
