# Learning System - Phase 1: Supervised Learning

Phase 1 implements manual, user-initiated workflow execution with automatic learning capture. No background daemons—just run workflows and track improvement.

## Quick Start

### 1. Run a learning session

```bash
./scripts/learning-session.sh code-review --high
```

This:
- Logs the session start
- Executes the workflow
- Automatically captures all execution metrics
- Displays what was learned

### 2. Check learning status

```bash
./scripts/learning-status.sh
```

Shows:
- **LIS (Learning Intelligence Score)**: 0-100 aggregate metric
- **Quality trends**: Improving/stable/declining
- **Cost efficiency**: Cost per quality point
- **Speed improvements**: Execution time trends
- **Recent executions**: Last 10 runs with outcomes

## Detailed Usage

### Running Workflows with Learning

Any workflow can be run through the learning session wrapper:

```bash
# Code review with learning capture
./scripts/learning-session.sh code-review --high

# Multi-AI consensus with learning
./scripts/learning-session.sh ai-consensus-debate "analyze this architecture"

# Autonomous SDLC with learning
./scripts/learning-session.sh code-sdlc-auto
```

The wrapper:
1. Generates a unique session ID and run ID
2. Sets environment variables for child workflows
3. Executes the workflow normally
4. Captures all metrics automatically (via `learning-logger.js`)
5. Displays session summary with LIS components

### Viewing Learning Status

Basic status:
```bash
./scripts/learning-status.sh
```

Full metrics:
```bash
./scripts/learning-status.sh --full
```

Complete leaderboard:
```bash
./scripts/learning-status.sh --leaderboard
```

Filter by model:
```bash
./scripts/learning-status.sh --model opus
```

Filter by task type:
```bash
./scripts/learning-status.sh --task security
```

Show more recent executions:
```bash
./scripts/learning-status.sh --recent 25
```

## Status Output Explained

### LIS (Learning Intelligence Score)

**Range**: 0-100 (higher is better)

**Rating Scale**:
- 90-100: Excellent
- 75-89: Good
- 60-74: Fair
- 40-59: Poor
- 0-39: Very Poor

**Components** (shown as Q/C/S):
- **Q (Quality)**: 0-100, weighted 35% in LIS
  - Based on percentile rank among all models
  - Bonus for improving trends (+10 points max)
- **C (Cost)**: 0-100, weighted 25% in LIS
  - Lower cost = higher score (inverted percentile)
  - Bonus for reducing cost over time (+15 points max)
- **S (Speed)**: 0-100, weighted 20% in LIS
  - Lower duration = higher score (inverted percentile)
  - Bonus for getting faster (+10 points max)
- **Consistency**: 0-100, weighted 20% in LIS
  - Low variance in quality and cost = higher score

### Trends

**Symbols**:
- `↑ +X%`: Improving (green) - recent performance better than older
- `→ stable`: Stable (yellow) - no significant change
- `↓ -X%`: Declining (red) - recent performance worse than older

**Statistical Significance**:
- Trends are only shown if p-value < 0.05 (95% confidence)
- Uses t-test to compare older half vs recent half of executions

### Model Combinations (Synergy)

Shows multi-AI consensus combinations with synergy scores:
- **Positive synergy** (+X%): Combination performs better than best individual
- **Negative synergy** (-X%): Combination underperforms
- **Star (★)**: Synergy > 5% (significant improvement)

## Adding Learning to Workflows

### Simple Workflow Logging

For single-model workflows:

```javascript
import { logWorkflowExecution } from './shared/workflow-logger.js';

// At workflow start
const logger = logWorkflowExecution({
  workflow: 'code-review',
  taskType: 'security',
  model: 'opus',
  runId: process.env.LEARNING_RUN_ID // Optional: ties executions together
});

try {
  // Your workflow code here
  const result = await performCodeReview();

  // Log success with metrics
  logger.success({
    qualityScore: 0.92,
    inputTokens: 1500,
    outputTokens: 800,
    costUsd: 0.024,
    durationMs: 3200
  });
} catch (error) {
  // Log failure
  logger.error(error);
}
```

### Consensus Workflow Logging

For multi-AI consensus workflows:

```javascript
import { logConsensusExecution } from './shared/workflow-logger.js';

const consensusLogger = logConsensusExecution({
  workflow: 'ai-consensus-debate',
  taskType: 'architecture',
  workers: ['opus', 'sonnet', 'gpt4o'],
  arbiter: 'gemini',
  runId: process.env.LEARNING_RUN_ID
});

// Log each worker
for (const worker of workers) {
  consensusLogger.logWorker({
    model: worker.model,
    phase: 'Proposal',
    qualityScore: worker.quality,
    confidence: worker.confidence,
    wasSelected: worker.wasSelected,
    inputTokens: worker.inputTokens,
    outputTokens: worker.outputTokens,
    costUsd: worker.cost,
    durationMs: worker.duration
  });
}

// Log arbiter
consensusLogger.logArbiter({
  model: 'gemini',
  consensusScore: 0.91,
  inputTokens: 3000,
  outputTokens: 500,
  costUsd: 0.035,
  durationMs: 2100
});

// Log combination synergy
consensusLogger.logCombination({
  consensusScore: 0.91,
  qualityScore: 0.94,
  totalCostUsd: 0.15,
  totalDurationMs: 12000
});
```

### Convenience Wrapper

For simple async functions:

```javascript
import { withLogging } from './shared/workflow-logger.js';

const result = await withLogging(
  {
    workflow: 'code-review',
    taskType: 'security',
    model: 'opus'
  },
  async () => {
    // Your workflow logic
    return { findings: [...] };
  }
);
```

## Database Schema

The learning database is at: `~/.claude/learning/db/learning.db`

### Main Tables

**execution_log**:
- Every workflow execution (worker, arbiter, single-model)
- Tracks: model, task_type, quality_score, cost, duration, outcome
- Indexed by: model, task_type, timestamp, run_id

**model_tuning**:
- Aggregated stats per model/task combination
- Rolling averages: quality, cost, duration
- Trend data: quality_trend, cost_trend
- Success/selection rates

**model_combinations**:
- Multi-AI consensus combination performance
- Tracks: worker_models, arbiter_model, synergy_score, diversity_score
- Shows which combinations work best together

**prompt_patterns**:
- Future use: track which prompt patterns work best
- Per model/task: avg_quality, avg_confidence, usage_count

**learning_metadata**:
- Key-value store for system metadata
- Last session info, schema version, etc.

### Querying Directly

```bash
# Check if DB exists
ls -lh ~/.claude/learning/db/learning.db

# Query with sqlite3 (if installed)
sqlite3 ~/.claude/learning/db/learning.db "SELECT COUNT(*) FROM execution_log"

# Or use Node.js
node --input-type=module <<'EOF'
import { getDb } from './shared/learning-logger.js';
const db = getDb();
console.log(db.prepare("SELECT COUNT(*) as cnt FROM execution_log").get());
EOF
```

## Metrics Explained

### LIS Calculation

```
LIS = 35*qualityScore + 25*costScore + 20*speedScore + 20*consistencyScore
```

Each component normalized to [0, 100]:

1. **Quality Score**:
   - Percentile rank among all models (0-100)
   - Trend bonus: +10 points if improving
   - Based on `quality_score` field in execution_log

2. **Cost Score**:
   - Inverted percentile (low cost = high score)
   - Trend bonus: +15 points if reducing cost
   - Based on `cost_usd` field

3. **Speed Score**:
   - Inverted percentile (low duration = high score)
   - Trend bonus: +10 points if getting faster
   - Based on `duration_ms` field

4. **Consistency Score**:
   - Coefficient of variation (CV) for quality and cost
   - Lower CV = higher score
   - CV < 0.2 = excellent, CV > 0.5 = penalized

### Quality Trend

Compares older half vs recent half of executions:
- Uses t-test for statistical significance (p < 0.05)
- Calculates percent improvement
- Linear regression on recent window for slope/R²

### Cost Efficiency

Cost per quality point: `cost_usd / quality_score`
- Lower is better
- Tracks trend over time
- Percentile rank among all models

### Speed Improvement

Compares older vs recent execution times:
- Percent improvement (positive = faster)
- Linear regression for trend slope
- Percentile rank among all models

## Troubleshooting

### "Database unavailable"

The database initializes on first use. Run any workflow to create it:

```bash
./scripts/learning-session.sh code-review
```

### "No metrics available yet (need min 5 samples)"

LIS requires at least 5 executions per model/task. Run more workflows:

```bash
for i in {1..5}; do
  ./scripts/learning-session.sh code-review
done
```

### "No trend data available"

Trends require at least 10 samples. Keep running workflows.

### Logging disabled

If you see warnings about learning being disabled, check:

1. Is better-sqlite3 installed?
   ```bash
   npm list better-sqlite3
   ```

2. Is the DB directory writable?
   ```bash
   ls -ld ~/.claude/learning/db/
   ```

3. Check debug logs:
   ```bash
   LEARNING_DEBUG=1 ./scripts/learning-session.sh code-review
   ```

## What's NOT in Phase 1

Phase 1 is **manual/supervised only**. It does NOT include:

- ❌ Background daemons (Phase 2)
- ❌ Automatic workflow triggers (Phase 2)
- ❌ Continuous recomputation (Phase 2)
- ❌ Self-optimization loops (Phase 3)
- ❌ Autonomous model selection (Phase 3)
- ❌ Dynamic prompt tuning (Phase 3)

Phase 1 is about **learning what works** through manual execution. You run workflows, the system captures metrics, you review status.

## Next Steps

After collecting sufficient data (50+ executions):

1. **Review leaderboard**: `./scripts/learning-status.sh --leaderboard`
2. **Identify top performers**: Which models excel at which tasks?
3. **Check synergies**: Which combinations work best together?
4. **Spot regressions**: Are any models declining?

Then proceed to **Phase 2** (background learning) or **Phase 3** (autonomous optimization).

## Files Reference

**Scripts**:
- `scripts/learning-session.sh` - Manual session wrapper
- `scripts/learning-status.sh` - Status dashboard

**Libraries**:
- `shared/learning-logger.js` - Database logging (<10ms overhead)
- `shared/learning-metrics.js` - LIS and trend calculations
- `shared/workflow-logger.js` - Workflow integration helpers

**Database**:
- `~/.claude/learning/db/learning.db` - SQLite database (WAL mode)
- `~/.claude/learning/init-learning-db.sql` - Schema definition

**Queries**:
- `shared/learning-metrics-queries.sql` - Ready-to-use SQL queries
