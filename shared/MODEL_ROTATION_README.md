# Model Rotation Policy

**Status:** ✅ WORKING (All tests passed)
**Created:** 2026-06-28
**Integration:** weighted-voting.cjs, PostgreSQL workflow schema

## Overview

Prevents model staleness through automated exploration and graduated rollout.

## Features

1. **Forced Exploration** - Auto-test underused models every 7 days
2. **Canary Mode** - New models start at 1% traffic
3. **Graduated Rollout** - 1% → 10% → 100% over 14 days
4. **Auto-Promotion** - Quality-based stage advancement
5. **Auto-Demotion** - Quality degradation triggers rollback
6. **Traffic Allocation** - Weight multipliers in voting
7. **PostgreSQL Tracking** - Full audit trail

## Quick Start

### 1. Initialize Schema

```javascript
const { initializeSchema } = require('./shared/model-rotation.cjs');
await initializeSchema();
```

### 2. Register New Model

```javascript
const { registerModel } = require('./shared/model-rotation.cjs');

// Auto-starts at canary (1% traffic)
await registerModel('new-model', { stage: 'canary' });
```

### 3. Record Executions

```javascript
const { recordExecution } = require('./shared/model-rotation.cjs');

// After each execution
await recordExecution('new-model', success, quality);
```

### 4. Check Rotation Status

```javascript
const { getRotationStatus } = require('./shared/model-rotation.cjs');

const status = await getRotationStatus();
console.table(status);
```

## Rollout Stages

| Stage   | Traffic | Duration | Min Quality | Auto-Promote |
|---------|---------|----------|-------------|--------------|
| Canary  | 1%      | 3 days   | 0.60        | → Ramp       |
| Ramp    | 10%     | 7 days   | 0.70        | → Full       |
| Full    | 100%    | Forever  | 0.75        | N/A          |

## Integration with Weighted Voting

Rotation policy is automatically applied in `runWeightedVoting()`:

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');

const result = await runWeightedVoting(votes, taskType);

// Check rotation analysis
if (result.voting_result.rotation_analysis) {
  console.log('Rotation applied to:', result.voting_result.rotation_analysis.models);
}
```

To disable rotation policy (testing only):

```javascript
const result = await runWeightedVoting(votes, taskType, {
  skipRotationPolicy: true
});
```

## Forced Exploration

Automatically flags stale models (0 executions in 7 days):

```javascript
const { detectStaleModels, forceExploration } = require('./shared/model-rotation.cjs');

// Detect stale models
const stale = await detectStaleModels();

// Force random stale model to be explored
const exploredModel = await forceExploration();

// Exploration boost: traffic × 1.5 (e.g., 10% → 15%)
```

## Promotion/Demotion

### Auto-Promotion

Criteria:
- ≥10 successful executions
- Quality ≥ stage threshold
- Duration ≥ stage duration

```javascript
const { checkAutoPromotion, promoteModel } = require('./shared/model-rotation.cjs');

const check = await checkAutoPromotion('model-name');
if (check.promote) {
  await promoteModel('model-name');
}
```

### Manual Demotion

```javascript
const { demoteModel } = require('./shared/model-rotation.cjs');

await demoteModel('model-name', 'quality_degradation');
```

## Monitoring

### Daily Cron Job

```bash
# Add to crontab
0 2 * * * cd /path/to/project && node shared/rotation-cron.cjs
```

```javascript
// shared/rotation-cron.cjs
const {
  detectStaleModels,
  forceExploration,
  generateRotationReport,
} = require('./model-rotation.cjs');

async function dailyRotationMaintenance() {
  // Detect and explore stale models
  const stale = await detectStaleModels();
  if (stale.length > 0) {
    await forceExploration();
  }

  // Generate report
  const report = await generateRotationReport();
  console.log(JSON.stringify(report, null, 2));
}

dailyRotationMaintenance();
```

### Grafana Dashboard

**Query:** `workflow.model_rotation_schedule`

Metrics:
- Models by stage (pie chart)
- Stale model count (gauge)
- Avg quality by stage (line chart)
- Traffic distribution (bar chart)

## PostgreSQL Schema

### Table: `workflow.model_rotation_schedule`

```sql
SELECT model, rollout_stage, traffic_percent, avg_quality, is_stale
FROM workflow.model_rotation_schedule
ORDER BY traffic_percent DESC, avg_quality DESC;
```

Fields:
- `model` - Model name
- `rollout_stage` - 'canary', 'ramp', 'full', 'dormant'
- `traffic_percent` - Traffic allocation (1, 10, 100)
- `total_executions` - Execution count
- `avg_quality` - Running average quality
- `is_stale` - True if >7 days since execution
- `force_exploration` - True if flagged for exploration

## Configuration

Edit `ROTATION_CONFIG` in `model-rotation.cjs`:

```javascript
const ROTATION_CONFIG = {
  exploration_interval_days: 7,      // Staleness threshold
  min_executions_threshold: 5,       // Min before skipping staleness
  canary_stages: [...],              // Rollout stages
  auto_promote_quality: 0.80,        // Fast-track threshold
  auto_demote_quality: 0.50,         // Quality floor
  min_sample_size: 10,               // Min executions for promotion
  exploration_weight_multiplier: 1.5, // Exploration boost
};
```

## Testing

Run test suite:

```bash
node shared/test-model-rotation.cjs
```

Tests:
1. Graduated rollout (canary → ramp → full)
2. Forced exploration of stale models
3. Auto-demotion on quality degradation
4. Traffic allocation in weighted voting
5. Rotation status and reporting
6. Edge cases (insufficient samples, etc.)

## API Reference

### Core Functions

- `initializeSchema()` - Create PostgreSQL tables
- `registerModel(model, options)` - Register new model
- `recordExecution(model, success, quality)` - Track execution
- `detectStaleModels()` - Find models >7 days idle
- `forceExploration()` - Flag random stale model
- `checkAutoPromotion(model)` - Check promotion eligibility
- `promoteModel(model)` - Advance to next stage
- `demoteModel(model, reason)` - Rollback to previous stage
- `getTrafficMultiplier(model)` - Get voting weight multiplier
- `applyRotationPolicy(votes)` - Adjust vote weights
- `getRotationStatus()` - Get all model status
- `generateRotationReport()` - Summary report

### Integration Functions

- `runWeightedVoting()` - Auto-applies rotation (weighted-voting.cjs)

## Examples

See `shared/example-rotation-usage.cjs` for:
- Basic integration
- Staleness check
- Rotation monitoring
- Cron job integration

## Architecture

```
┌─────────────────────────────────────────┐
│  Weighted Voting (weighted-voting.cjs)  │
│  ├─ Calculate base weights              │
│  ├─ Apply rotation policy ◄──┐          │
│  └─ Return adjusted weights  │          │
└──────────────────────────────┼──────────┘
                               │
┌──────────────────────────────┼──────────┐
│  Model Rotation (model-rotation.cjs) ◄──┘
│  ├─ Detect stale models                 │
│  ├─ Force exploration                   │
│  ├─ Check auto-promotion                │
│  ├─ Apply traffic multipliers           │
│  └─ Track in PostgreSQL                 │
└──────────────────────────────┬──────────┘
                               │
┌──────────────────────────────▼──────────┐
│  PostgreSQL (aio-01:5433/learning)      │
│  └─ workflow.model_rotation_schedule    │
└─────────────────────────────────────────┘
```

## Anti-Staleness Mechanisms

1. **Staleness Detection** - Flag models with 0 executions in 7 days
2. **Forced Exploration** - Random selection from stale pool
3. **Exploration Boost** - 1.5× traffic multiplier during exploration
4. **Auto-Promotion** - Quality-based graduation prevents manual tuning
5. **Traffic Allocation** - Canary/ramp models get reduced vote weight

## Known Limitations

1. **Minimum Sample Size** - Requires ≥10 executions for promotion
2. **Stage Duration** - Hard-coded (3d/7d/∞), not adaptive
3. **Quality Threshold** - Fixed per stage, not task-specific
4. **Exploration Boost** - Fixed 1.5× multiplier

## Future Improvements

- [ ] Adaptive stage duration (based on execution rate)
- [ ] Task-specific quality thresholds
- [ ] Multi-armed bandit exploration (Thompson Sampling)
- [ ] A/B testing mode (traffic split comparison)
- [ ] Automatic rollback on quality drop

## Related Components

- `weighted-voting.cjs` - Vote weighting system
- `circuit-breaker.cjs` - Failure detection
- `confidence-calibration.cjs` - Confidence penalty
- `disagreement-detector.cjs` - Disagreement detection
- `workflow-storage-adapter.js` - PostgreSQL storage

## Changelog

### 2026-06-28 - Initial Release

- ✅ Graduated rollout (canary → ramp → full)
- ✅ Forced exploration (7-day staleness)
- ✅ Auto-promotion (quality + duration)
- ✅ Auto-demotion (quality degradation)
- ✅ Traffic allocation in weighted voting
- ✅ PostgreSQL tracking
- ✅ Full test suite (6 test scenarios)
- ✅ Integration with weighted-voting.cjs

---

**Documentation complete.** See `test-model-rotation.cjs` for validation.
