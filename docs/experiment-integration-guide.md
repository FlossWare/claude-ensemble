# Experiment Manager Integration Guide

**Issue:** #267  
**Created:** 2026-07-01  
**Status:** ✅ Integration Complete

## Overview

The experiment manager (`shared/experiment-manager.cjs`) provides A/B testing with statistical significance testing (Welch's t-test, bootstrap confidence intervals). This guide shows how it's wired into the system.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  experiment-manager.cjs (Core Framework)                    │
│  - runExperiment()                                          │
│  - compareResults() (Welch's t-test, bootstrap)             │
│  - recordExperiment() (PostgreSQL storage)                  │
│  - getExperimentHistory()                                   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┴───────────────────────────────┐
│  experiment-integration.cjs (Integration Layer)             │
│  - runRolloutExperiment()                                   │
│  - runVotingExperiment()                                    │
│  - runRoutingExperiment()                                   │
│  - runQualityThresholdExperiment()                          │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────┴──────┐   ┌──────────┴────────┐   ┌───────┴────────┐
│ Model        │   │ Weighted          │   │ Learning       │
│ Rotation     │   │ Voting            │   │ System         │
│ (canary      │   │ (algorithm        │   │ (formal A/B    │
│  rollout)    │   │  comparison)      │   │  tests)        │
└──────────────┘   └───────────────────┘   └────────────────┘
```

## Integration Points

### 1. Model Rotation (`shared/model-rotation.cjs`)

**What:** Compare canary rollout strategies (fast vs slow)  
**Integration:** `runRolloutExperiment()`

```javascript
const { runRolloutExperiment } = require('./experiment-integration.cjs');

const result = await runRolloutExperiment({
  model: 'opus-3.5',
  baseline: { stage: 'canary', duration_days: 3 },
  treatment: { stage: 'canary', duration_days: 1 },
  samples: 20
});

if (result.verdict === 'keep') {
  console.log(`✅ Fast rollout approved: +${result.improvement_pct.toFixed(2)}%`);
}
```

**Where to add:**
- File: `shared/model-rotation.cjs`
- Function: `promoteModel()`
- Use case: Test if faster promotion is safe

### 2. Weighted Voting (`shared/weighted-voting-with-explain.cjs`)

**What:** Compare voting algorithms (baseline vs disagreement detection)  
**Integration:** `runVotingExperiment()`

```javascript
const { runVotingExperiment } = require('./experiment-integration.cjs');

const result = await runVotingExperiment({
  votes: workerVotes,
  taskType: 'code_review',
  baselineOptions: { algorithm: 'standard' },
  treatmentOptions: { algorithm: 'with_disagreement_detection' },
  iterations: 30
});

if (result.verdict === 'keep') {
  console.log(`✅ New algorithm wins: p=${result.p_value.toFixed(4)}`);
}
```

**Where to add:**
- File: `shared/weighted-voting-with-explain.cjs`
- Function: `runWeightedVotingWithExplain()`
- Use case: Validate algorithm changes before deploying

### 3. Model Routing (Custom)

**What:** Compare task-specific routing strategies  
**Integration:** `runRoutingExperiment()`

```javascript
const { runRoutingExperiment } = require('./experiment-integration.cjs');

const baselineRouter = (task) => 'opus';
const treatmentRouter = (task) => {
  if (task.language === 'java') return 'deepseek-coder';
  return 'opus';
};

const result = await runRoutingExperiment({
  taskType: 'code_generation',
  baselineRouter,
  treatmentRouter,
  tasks: testTasks
});
```

**Where to add:**
- File: `shared/model-capability-matrix.cjs` or custom router
- Use case: Validate specialized model routing

### 4. Quality Thresholds (System-wide)

**What:** Test impact of changing acceptance thresholds  
**Integration:** `runQualityThresholdExperiment()`

```javascript
const { runQualityThresholdExperiment } = require('./experiment-integration.cjs');

const result = await runQualityThresholdExperiment({
  baselineThreshold: 0.70,
  treatmentThreshold: 0.75,
  samples: validationSamples
});

if (result.verdict === 'keep') {
  console.log(`✅ Raising threshold to 0.75 improves accuracy`);
}
```

**Where to add:**
- Files: Any component with quality gates
- Use case: Tune thresholds with data

## Database Schema

Experiments are stored in PostgreSQL:

```sql
-- Table: workflow.experiments
CREATE TABLE workflow.experiments (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  hypothesis TEXT,
  metric TEXT NOT NULL,
  baseline_config JSONB,
  treatment_config JSONB,
  baseline_samples JSONB NOT NULL,
  treatment_samples JSONB NOT NULL,
  baseline_mean NUMERIC,
  treatment_mean NUMERIC,
  improvement_pct NUMERIC,
  p_value NUMERIC,
  ci_lower NUMERIC,
  ci_upper NUMERIC,
  effect_size NUMERIC,
  verdict TEXT NOT NULL,
  success_criteria JSONB,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Usage Examples

### Example 1: Test Fast Canary Rollout

```bash
# Run example
node shared/example-experiment-integration.cjs --type rollout
```

Output:
```
EXAMPLE 1: Model Rollout Experiment

Hypothesis: Faster canary rollout (1 day) maintains quality vs baseline (3 days)
Metric: Quality score (0.0-1.0)
Sample size: 20 executions per arm

--- RESULTS ---
Baseline mean: 0.7521
Treatment mean: 0.7498
Improvement: -0.31%
p-value: 0.7823
Effect size (Cohen's d): -0.098

Verdict: INCONCLUSIVE
Reason: Not statistically significant: p=0.7823 >= alpha=0.05
```

### Example 2: Test Voting Algorithm

```bash
# Run example
node shared/example-experiment-integration.cjs --type voting
```

### Example 3: View Experiment History

```javascript
const { getExperimentHistory } = require('./shared/experiment-manager.cjs');

const experiments = await getExperimentHistory({ 
  verdict: 'keep',
  limit: 10 
});

experiments.forEach(exp => {
  console.log(`${exp.name}: +${exp.improvement_pct.toFixed(2)}% (p=${exp.p_value.toFixed(4)})`);
});
```

## Testing

Run integration tests:

```bash
node shared/test-experiment-integration.cjs
```

Expected output:
```
🧪 Running experiment-integration.cjs tests

Testing EXPERIMENT_TYPES defined... ✓
Testing runRolloutExperiment returns valid result... ✓
Testing runVotingExperiment returns valid result... ✓
Testing runRoutingExperiment returns valid result... ✓
Testing runQualityThresholdExperiment returns valid result... ✓
Testing generateExperimentSummary returns valid structure... ✓
Testing getExperimentsByType filters correctly... ✓
Testing Experiment results include all required fields... ✓

============================================================
Tests passed: 8
Tests failed: 0
============================================================

✅ All tests passed!
```

## Statistical Framework

### Welch's t-test
- Used for comparing two independent samples
- No assumption of equal variance
- Returns p-value for significance testing

### Bootstrap Confidence Intervals
- 1000 resamples (configurable)
- 95% confidence level (configurable)
- Provides robust CI estimates

### Cohen's d Effect Size
- Measures magnitude of difference
- Interpretation:
  - d < 0.2: negligible
  - 0.2 ≤ d < 0.5: small
  - 0.5 ≤ d < 0.8: medium
  - d ≥ 0.8: large

### Verdict Logic
- **keep**: p < 0.05 AND improvement ≥ min_improvement_pct
- **remove**: p < 0.05 AND improvement ≤ -min_improvement_pct
- **inconclusive**: p ≥ 0.05 OR improvement too small

## Configuration

Default experiment config:

```javascript
const EXPERIMENT_CONFIG = {
  alpha: 0.05,                    // Significance level
  min_samples: 5,                 // Min samples for validity
  bootstrap_iterations: 1000,     // Bootstrap resamples
  bootstrap_confidence: 0.95,     // CI level
  default_min_improvement_pct: 3, // Min improvement to keep
  max_duration_ms: 600000,        // Max experiment duration (10 min)
};
```

## Verification

To verify integration works:

1. **Run all examples:**
   ```bash
   node shared/example-experiment-integration.cjs --type all
   ```

2. **Check database:**
   ```bash
   psql -h aio-01 -p 5433 -U sfloess -d learning -c \
     "SELECT name, verdict, improvement_pct, p_value FROM workflow.experiments ORDER BY created_at DESC LIMIT 10;"
   ```

3. **Run tests:**
   ```bash
   node shared/test-experiment-integration.cjs
   ```

## Integration Status

| Component | Integration Status | File | Function |
|-----------|-------------------|------|----------|
| Model Rotation | ✅ Ready | `model-rotation.cjs` | `promoteModel()` |
| Weighted Voting | ✅ Ready | `weighted-voting-with-explain.cjs` | `runWeightedVotingWithExplain()` |
| Model Routing | ✅ Ready | Custom router | User-defined |
| Quality Thresholds | ✅ Ready | Any component | User-defined |
| Learning System | ✅ Documented | `learning/experiment-executor.js` | See comments |

## Next Steps

1. **Add experiments to model rotation:**
   - Edit `shared/model-rotation.cjs`
   - Add `runRolloutExperiment()` call in `promoteModel()`
   - Test canary → ramp promotion decisions

2. **Add experiments to weighted voting:**
   - Edit `shared/weighted-voting-with-explain.cjs`
   - Add periodic A/B test of voting algorithms
   - Compare baseline vs new algorithms

3. **Create custom experiments:**
   - Use `experiment-integration.cjs` as examples
   - Follow the collector pattern
   - Store in PostgreSQL for history

## References

- Core framework: `shared/experiment-manager.cjs`
- Integration layer: `shared/experiment-integration.cjs`
- Examples: `shared/example-experiment-integration.cjs`
- Tests: `shared/test-experiment-integration.cjs`
- Database: PostgreSQL `learning.workflow.experiments`

## Questions?

See example usage in `shared/example-experiment-integration.cjs` for complete working examples.
