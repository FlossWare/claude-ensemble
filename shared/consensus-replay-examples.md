# Consensus Replay Examples

## Overview

The Consensus Replay system re-runs historical consensus workflows with current model weights to measure improvement or degradation over time.

**Use Cases:**
- Measure if model updates improve performance on your workload
- Detect regression after model changes
- Track quality evolution over time
- A/B test different model configurations

## Basic Usage

### CLI

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

async function replayWorkflow() {
  const replay = new ConsensusReplay();

  // 1. Fetch historical workflow
  const historical = await replay.fetchHistoricalWorkflow('wf-1719594345678');

  if (!historical) {
    console.error('Workflow not found');
    return;
  }

  // 2. Re-run with current models
  const newRun = await replay.rerunConsensus(historical, {
    sameModels: true, // Use same models as original
    overrideModels: null // Or specify: ['opus', 'sonnet', 'haiku']
  });

  // 3. Compare results
  const comparison = replay.compareResults(historical, newRun);

  console.log('Verdict:', comparison.summary.verdict);
  console.log('Avg Confidence Delta:', comparison.summary.avg_confidence_delta);
  console.log('Arbiter Confidence Delta:', comparison.summary.arbiter_confidence_delta);

  // 4. Generate HTML report
  replay.generateHTMLReport(comparison, '/tmp/replay-report.html');

  // 5. Store to database
  await replay.storeReplayResults(comparison);

  await replay.close();
}

replayWorkflow();
```

## Understanding Results

### Verdicts

- **SIGNIFICANT_IMPROVEMENT**: Arbiter +0.1 confidence AND avg workers +0.05
- **MODERATE_IMPROVEMENT**: Arbiter +0.05 confidence OR avg workers +0.03
- **NO_SIGNIFICANT_CHANGE**: Small deltas (within noise)
- **DEGRADATION**: Arbiter -0.1 confidence OR avg workers -0.05

### Comparison Report Structure

```javascript
{
  summary: {
    workflow_id: 'wf-123',
    task: 'Original task description',
    replayed_at: '2026-06-28T10:30:00Z',
    original_created_at: '2026-06-20T08:00:00Z',
    avg_confidence_delta: '0.065',      // Average worker improvement
    arbiter_confidence_delta: '0.120',  // Arbiter improvement
    total_cost_delta: '-0.0050',        // Cost savings (negative = cheaper)
    verdict: 'SIGNIFICANT_IMPROVEMENT'
  },
  workers: [
    {
      model: 'opus',
      old_confidence: 0.75,
      new_confidence: 0.85,
      confidence_delta: 0.10,
      old_duration_ms: 5000,
      new_duration_ms: 4500,
      speed_improvement: '10.0%',
      old_cost_usd: 0.05,
      new_cost_usd: 0.04,
      cost_delta: -0.01
    }
  ],
  arbiter: {
    old_confidence: 0.82,
    new_confidence: 0.94,
    confidence_delta: 0.12,
    old_duration_ms: 4000,
    new_duration_ms: 3500,
    speed_improvement: '12.5%'
  }
}
```

## Batch Replay Scenarios

### Replay All Workflows from Last Week

```javascript
const { ConsensusReplay } = require('./shared/consensus-replay.cjs');
const { Pool } = require('pg');

async function replayLastWeek() {
  const pool = new Pool({ /* ... */ });
  const replay = new ConsensusReplay();

  // Get all workflows from last 7 days
  const client = await pool.connect();
  const result = await client.query(`
    SELECT workflow_id
    FROM workflow.executions
    WHERE created_at > NOW() - INTERVAL '7 days'
    AND outcome = 'success'
    ORDER BY created_at DESC
  `);
  client.release();

  const workflowIds = result.rows.map(r => r.workflow_id);

  console.log(`Replaying ${workflowIds.length} workflows...`);

  for (const id of workflowIds) {
    console.log(`\n=== Replaying ${id} ===`);
    const historical = await replay.fetchHistoricalWorkflow(id);
    const newRun = await replay.rerunConsensus(historical);
    const comparison = replay.compareResults(historical, newRun);

    console.log(`Verdict: ${comparison.summary.verdict}`);
    console.log(`Confidence delta: ${comparison.summary.avg_confidence_delta}`);

    await replay.storeReplayResults(comparison);
  }

  await replay.close();
  await pool.end();
}

replayLastWeek();
```

### A/B Test: Compare Two Model Configurations

```javascript
async function compareModelConfigs() {
  const replay = new ConsensusReplay();
  const historical = await replay.fetchHistoricalWorkflow('wf-123');

  // Configuration A: Opus + Sonnet + Haiku
  const runA = await replay.rerunConsensus(historical, {
    overrideModels: ['opus', 'sonnet', 'haiku']
  });

  // Configuration B: Opus + Fable + GPT-4o
  const runB = await replay.rerunConsensus(historical, {
    overrideModels: ['opus', 'fable', 'gpt-4o']
  });

  const comparisonA = replay.compareResults(historical, runA);
  const comparisonB = replay.compareResults(historical, runB);

  console.log('Config A (Opus/Sonnet/Haiku):');
  console.log(`  Confidence: ${comparisonA.summary.avg_confidence_delta}`);
  console.log(`  Cost: $${comparisonA.summary.total_cost_delta}`);

  console.log('\nConfig B (Opus/Fable/GPT-4o):');
  console.log(`  Confidence: ${comparisonB.summary.avg_confidence_delta}`);
  console.log(`  Cost: $${comparisonB.summary.total_cost_delta}`);

  await replay.close();
}
```

## Querying Replay History

### Find Workflows with Improvement

```sql
SELECT
  original_workflow_id,
  replayed_at,
  avg_confidence_delta,
  arbiter_confidence_delta,
  verdict
FROM workflow.replays
WHERE verdict IN ('SIGNIFICANT_IMPROVEMENT', 'MODERATE_IMPROVEMENT')
ORDER BY avg_confidence_delta DESC
LIMIT 10;
```

### Track Quality Trends Over Time

```sql
SELECT
  DATE(replayed_at) as replay_date,
  COUNT(*) as total_replays,
  AVG(avg_confidence_delta) as avg_improvement,
  COUNT(*) FILTER (WHERE verdict LIKE '%IMPROVEMENT%') as improved_count,
  COUNT(*) FILTER (WHERE verdict = 'DEGRADATION') as degraded_count
FROM workflow.replays
GROUP BY DATE(replayed_at)
ORDER BY replay_date DESC;
```

### Find Workflows Needing Attention (Degradation)

```sql
SELECT
  wr.original_workflow_id,
  we.task_description,
  wr.avg_confidence_delta,
  wr.arbiter_confidence_delta,
  wr.verdict
FROM workflow.replays wr
JOIN workflow.executions we ON wr.original_workflow_id = we.workflow_id
WHERE wr.verdict = 'DEGRADATION'
ORDER BY wr.avg_confidence_delta ASC
LIMIT 20;
```

## Automated Replay Pipeline

### Cron Job: Daily Replay of Last 24h Workflows

```bash
#!/bin/bash
# /home/sfloess/bin/daily-consensus-replay.sh

cd /home/sflooss/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Get workflows from last 24h
psql -h aio-01 -p 5433 -d learning -t -c \
  "SELECT workflow_id FROM workflow.executions
   WHERE created_at > NOW() - INTERVAL '24 hours'
   AND outcome = 'success'" | while read -r workflow_id; do

  echo "Replaying: $workflow_id"
  
  node shared/consensus-replay.cjs "$workflow_id" \
    --html-report "/tmp/replay-reports/$(date +%Y%m%d)-${workflow_id}.html" \
    --store

done

echo "Daily replay complete"
```

Add to crontab:
```bash
0 2 * * * /home/sfloess/bin/daily-consensus-replay.sh >> /tmp/daily-replay.log 2>&1
```

## HTML Report Interpretation

The HTML report includes:

1. **Verdict Badge**: Color-coded summary
   - Green: Significant improvement
   - Blue: Moderate improvement
   - Gray: No significant change
   - Red: Degradation

2. **Summary Table**: Key metrics at a glance
   - Confidence deltas (positive = improvement)
   - Cost delta (negative = savings)
   - Timestamps

3. **Worker Comparison Table**: Per-model breakdown
   - Old vs new confidence
   - Speed improvements
   - Cost changes

4. **Arbiter Comparison**: Final synthesis quality
   - Arbiter confidence improvement
   - Decision speed improvements

## Troubleshooting

### Workflow Not Found

```javascript
const historical = await replay.fetchHistoricalWorkflow('wf-nonexistent');
if (!historical) {
  console.error('Workflow not found. Check workflow.executions table.');
}
```

### Worker Execution Failures

Workers use Claude CLI, so ensure:
- `claude` command is in PATH
- Models specified are available (check `claude --list-models`)
- API keys configured

### Database Connection Issues

```javascript
const replay = new ConsensusReplay();
try {
  await replay.pool.query('SELECT 1');
  console.log('Database connected');
} catch (error) {
  console.error('Database connection failed:', error.message);
  console.error('Check PGHOST, PGPORT, PGDATABASE, PGUSER env vars');
}
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
- Track total cost delta across all replays
- Consider sampling strategy for large-scale replays

### Database Growth

- Each replay creates new record in `workflow.replays`
- Set retention policy:

```sql
DELETE FROM workflow.replays
WHERE replayed_at < NOW() - INTERVAL '90 days';
```

## Integration with Monitoring

### Prometheus Metrics

Export replay metrics to Prometheus:

```javascript
const { register, Counter, Gauge } = require('prom-client');

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

### Grafana Dashboard

Query replay trends:

```promql
# Improvement rate
rate(consensus_replays_total{verdict=~".*IMPROVEMENT.*"}[1h])

# Average confidence improvement
avg_over_time(consensus_replay_confidence_delta[24h])
```

## Best Practices

1. **Replay Representative Samples**: Don't replay every workflow, sample 10-20% of high-value tasks

2. **Track Across Model Updates**: Replay before/after model version changes

3. **Monitor Cost Trends**: Track `total_cost_delta` to detect pricing changes

4. **Set Quality Thresholds**: Alert on degradation verdicts

5. **Archive HTML Reports**: Keep visual records of quality evolution

6. **Periodic Cleanup**: Delete old replay records (>90 days)

7. **Compare Apples-to-Apples**: Use `--same-models` for fair comparison

8. **Override for Experimentation**: Use `--override-models` to test new configurations
