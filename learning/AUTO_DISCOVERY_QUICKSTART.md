# Auto-Discovery Quick Start

Get the self-improving AI system running in 5 minutes.

## Prerequisites

- Node.js 18+ installed
- SQLite database with execution logs
- At least 50 executions in the database

## Quick Start

### 1. Check Your Data

```bash
# Verify execution count
sqlite3 ~/.claude/learning/db/learning.db \
  "SELECT COUNT(*) FROM execution_log WHERE quality_score IS NOT NULL"
```

Should return at least 50. If not, run more workflows first.

### 2. Bootstrap Thompson Sampling

```bash
cd /path/to/claude-global-skills

# Initialize Thompson Sampling from historical data
node learning/validate-thompson-sampling.js --bootstrap
```

Expected output:
```
Thompson Sampling State:
  Models: opus, sonnet, haiku, fable
  Total executions: 147
  Avg success rate: 78.2%
```

### 3. Generate Initial Discoveries

```bash
# Discover patterns (dry run first)
node learning/discover-patterns.js

# If patterns look good, apply them
node learning/discover-patterns.js --apply
```

Expected output:
```
[discover-patterns] Discovery generation complete
  Added:    4 new discoveries
  Total:    10 discoveries

--- NEW DISCOVERIES ---
  discovery_thompson_sonnet_over_haiku
    Pattern:     prefer-sonnet-over-haiku
    Description: sonnet outperforms haiku (success rate: 85.3% vs 62.1%)
    Confidence:  89.2%
    Evidence:    147 samples
    Source:      thompson-sampling
```

### 4. Start the Discovery Scheduler

```bash
# Run once to test
node learning/discovery-scheduler.js

# Start as daemon (every 6 hours)
nohup node learning/discovery-scheduler.js --daemon > /dev/null 2>&1 &

# Verify it's running
ps aux | grep discovery-scheduler
```

### 5. Verify Integration

```bash
# Check that discoveries are being applied
node -e "
import('./orchestrator.js').then(async (m) => {
  const model = await m.selectModel('code-review', {
    strategy: 'thompson',
    requires_schema: true,
  });
  console.log('Selected model:', model);
});
"
```

### 6. Monitor Progress

```bash
# View discovery statistics
node learning/update-discovery-metadata.js --stats

# Check logs
tail -f ~/.claude/learning/logs/discovery-scheduler.log
```

## What Happens Now?

1. **Every 6 hours**, the discovery scheduler:
   - Analyzes Thompson Sampling trends
   - Analyzes execution logs for patterns
   - Generates new high-confidence discoveries
   - Auto-appends them to discoveries.json
   - Updates confidence scores based on evidence
   - Prunes low-confidence patterns

2. **On every model selection**, the orchestrator:
   - Applies relevant discoveries (filters/biases)
   - Records which discoveries were used
   - Tracks evidence after execution

3. **Over time**, the system:
   - Learns optimal model selection for each task
   - Discovers cost-quality tradeoffs
   - Identifies schema compliance issues
   - Routes tasks to best-performing models

## Verify It's Working

### Check Discovery Application

```bash
# Run a model selection and see applied discoveries
LEARNING_DEBUG=1 node -e "
import('./orchestrator.js').then(async (m) => {
  const model = await m.selectModel('security-review', {
    strategy: 'thompson',
    cost_sensitivity: 'high',
  });
  console.log('Selected:', model);
});
"
```

Look for log lines like:
```
[apply-discoveries] Filtered models: { applied: [...] }
```

### Check Evidence Collection

```bash
# Simulate an execution and evidence tracking
LEARNING_DEBUG=1 node -e "
import('./orchestrator.js').then(async (m) => {
  const model = await m.selectModel('code-review', { strategy: 'thompson' });
  await m.recordResult(model, 0.85, {
    appliedDiscoveries: ['discovery_001'],
    context: { task_type: 'code-review' }
  });
  console.log('Evidence recorded');
});
"
```

### Check Discovery Stats

```bash
node learning/update-discovery-metadata.js --stats
```

Look for:
- `Avg apply count` > 0 (discoveries being used)
- `Avg evidence count` increasing over time

## Troubleshooting

### No discoveries generated

**Problem:** `Added: 0 new discoveries`

**Solution:**
1. Check execution count: `sqlite3 ~/.claude/learning/db/learning.db "SELECT COUNT(*) FROM execution_log"`
2. Lower confidence threshold: `node learning/discover-patterns.js --apply --min-conf 0.70`
3. Check Thompson Sampling: `node learning/validate-thompson-sampling.js`

### Discoveries not being applied

**Problem:** `applied_discoveries: []` in selection output

**Solution:**
1. Check discovery conditions match your context
2. Verify discoveries are active: `jq '.discoveries[] | select(.status == "active")' ~/.claude/learning/discoveries.json`
3. Enable debug logging: `LEARNING_DEBUG=1`

### Evidence count not increasing

**Problem:** `Avg evidence count: 0.0`

**Solution:**
1. Ensure `recordResult()` is called after executions
2. Pass `appliedDiscoveries` to `recordResult()`:
   ```javascript
   await recordResult(model, qualityScore, {
     appliedDiscoveries: config.applied_discoveries,
     context: { task_type: 'my-task' }
   });
   ```

## Next Steps

1. **Monitor for 1 week** - Let the system collect evidence
2. **Review discoveries** - Check which patterns are working
3. **Tune thresholds** - Adjust confidence thresholds if needed
4. **Add custom patterns** - Manually add domain-specific patterns

## Advanced Configuration

### Custom Discovery Interval

```bash
# Run every 2 hours instead of 6
node learning/discovery-scheduler.js --daemon --interval 2
```

### Custom Confidence Thresholds

```bash
# Only auto-add very high-confidence patterns
node learning/discover-patterns.js --apply --min-conf 0.85
```

### Manual Discovery Management

```bash
# Force confidence recompute
node learning/update-discovery-metadata.js --recompute

# Prune low-confidence patterns
node learning/update-discovery-metadata.js --prune

# View all discoveries
jq '.discoveries' ~/.claude/learning/discoveries.json
```

## Performance Tuning

### Reduce Discovery Interval (More Frequent Learning)

```bash
# Every hour (aggressive learning)
node learning/discovery-scheduler.js --daemon --interval 1
```

**Trade-off:** Higher CPU usage, faster adaptation

### Increase Discovery Interval (Less Frequent Learning)

```bash
# Every 12 hours (conservative learning)
node learning/discovery-scheduler.js --daemon --interval 12
```

**Trade-off:** Lower CPU usage, slower adaptation

### Adjust Confidence Thresholds

```bash
# More aggressive (add lower-confidence patterns)
export MIN_CONFIDENCE=0.60

# More conservative (only very high confidence)
export MIN_CONFIDENCE=0.85
```

## Integration with Existing Workflows

### Add to Your Workflow

```javascript
import { selectModel, recordResult } from './orchestrator.js';

async function runWorkflow(taskType, prompt) {
  // 1. Select model with discoveries applied
  const config = await selectModel(taskType, {
    strategy: 'thompson',
    requires_schema: true,
    cost_sensitivity: 'medium',
  });

  // 2. Execute with selected model
  const result = await executeWithModel(config, prompt);

  // 3. Record result with evidence tracking
  await recordResult(config.model, result.qualityScore, {
    appliedDiscoveries: config.applied_discoveries,
    context: { task_type: taskType }
  });

  return result;
}
```

### Example: Code Review Workflow

```javascript
// workflows/code-review.js
import { selectModel, recordResult } from '../orchestrator.js';

export async function codeReview(code) {
  // Select model (discoveries auto-applied)
  const model = await selectModel('code-review', {
    strategy: 'thompson',
    requires_schema: false,
    quality_threshold: 0.85,
  });

  // Run review
  const review = await runCodeReview(model, code);
  const qualityScore = assessReviewQuality(review);

  // Record evidence
  await recordResult(model, qualityScore, {
    appliedDiscoveries: ['discovery_001', 'discovery_003'],
    context: { task_type: 'code-review' }
  });

  return review;
}
```

## Success Metrics

After 1 week, you should see:

- ✅ Active discoveries: 5-15
- ✅ Avg confidence: 75-90%
- ✅ Avg apply count: 20+ per discovery
- ✅ Avg evidence count: 10+ per discovery
- ✅ Quality impact: positive for most discoveries

Check metrics:
```bash
node learning/update-discovery-metadata.js --stats
```

## Getting Help

1. **Check logs**: `tail -f ~/.claude/learning/logs/discovery-scheduler.log`
2. **Enable debug mode**: `LEARNING_DEBUG=1`
3. **Review documentation**: `cat learning/AUTO_DISCOVERY_SYSTEM.md`
4. **Inspect database**: `sqlite3 ~/.claude/learning/db/learning.db`

## Files to Know

```
~/.claude/learning/
├── discoveries.json              # Active discoveries (edit manually if needed)
├── bandit-state.json             # Thompson Sampling state
├── db/learning.db                # Execution history (SQLite)
└── logs/
    └── discovery-scheduler.log   # Discovery generation logs
```

## Summary

You now have a fully automated self-improving AI system:

1. ✅ Thompson Sampling for exploration/exploitation
2. ✅ Auto-discovery of optimization patterns
3. ✅ Evidence-based confidence updates
4. ✅ Automatic pattern application
5. ✅ Continuous learning from execution history

The system will improve itself over time with zero manual intervention.
