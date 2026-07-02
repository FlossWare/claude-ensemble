# Experiment Manager - Usage Examples

**Status:** Production Active ✓ (Issue #267, 2026-07-02)

## Overview

The experiment-manager provides statistical A/B testing with Welch's t-test and bootstrap confidence intervals.

**Production Integration:**
- ✓ `shared/consensus-replay.cjs` - Statistical regression detection (Issue #267)

## Quick Start

### 1. Statistical Comparison (Direct)

Compare two sample arrays with statistical rigor:

```javascript
const { compareResults } = require('./shared/experiment-manager.cjs');

// Example: Compare old vs new model confidence scores
const baselineConfidences = [0.72, 0.68, 0.75, 0.70, 0.73];
const treatmentConfidences = [0.78, 0.82, 0.76, 0.79, 0.81];

const result = compareResults(baselineConfidences, treatmentConfidences, {
  alpha: 0.05,              // Significance level
  min_improvement_pct: 3,   // Minimum improvement to declare success
});

console.log(result);
// {
//   verdict: 'keep',  // or 'remove', 'inconclusive'
//   baseline_mean: 0.716,
//   treatment_mean: 0.792,
//   improvement_pct: 10.61,
//   p_value: 0.0012,
//   t_stat: 4.71,
//   df: 7.88,
//   ci_lower: 0.048,
//   ci_upper: 0.106,
//   effect_size: 2.98,
//   significant: true,
//   reason: "Significant improvement: +10.61% (p=0.0012, effect_size=2.981)"
// }
```

### 2. Consensus Replay Integration (Production)

Use statistical verdicts for regression detection:

```javascript
const { ConsensusReplay } = require('./shared/consensus-replay.cjs');

const replay = new ConsensusReplay();

// Collect multiple replays of same workflow
const baselineConfidences = [0.72, 0.68, 0.75, 0.70, 0.73];  // Historical runs
const treatmentConfidences = [0.78, 0.82, 0.76, 0.79, 0.81]; // New model runs

const result = replay.generateStatisticalVerdict(
  baselineConfidences, 
  treatmentConfidences,
  { alpha: 0.05, min_improvement_pct: 3 }
);

console.log(result.verdict);  // 'SIGNIFICANT_IMPROVEMENT'
console.log(result.statistics.p_value);  // 0.0012
console.log(result.statistics.reason);
// "Significant improvement: +10.61% (p=0.0012, effect_size=2.981)"
```

### 3. Full Experiment with Custom Collector

Run a complete A/B experiment:

```javascript
const { runExperiment } = require('./shared/experiment-manager.cjs');

const result = await runExperiment({
  name: 'model_latency_test',
  hypothesis: 'New model reduces latency without quality loss',
  metric: 'response_time_ms',
  
  baseline: { model: 'opus-3.0', timeout: 30000 },
  treatment: { model: 'opus-3.5', timeout: 30000 },
  
  // Collector function: runs task with given config, returns array of samples
  collector: async (config) => {
    const samples = [];
    for (let i = 0; i < 20; i++) {
      const start = Date.now();
      await executeTask(config.model, 'test-prompt');
      samples.push(Date.now() - start);
    }
    return samples;
  },
  
  success_criteria: {
    min_improvement_pct: 10,  // Need 10% latency reduction
    alpha: 0.05,
  },
  
  record: true,  // Store in PostgreSQL
  metadata: { team: 'ml-infra' }
});

console.log(result.verdict);  // 'keep', 'remove', or 'inconclusive'
console.log(result.reason);
```

## Statistical Methods

### Welch's t-test
- Compares means of two samples with unequal variances
- Returns t-statistic, degrees of freedom, and p-value
- Null hypothesis: No difference between groups

### Bootstrap Confidence Intervals
- Resampling method (default: 1000 iterations)
- Provides CI for difference of means
- Cohen's d effect size calculation
- Robust to non-normal distributions

### Verdict Criteria

| Verdict | Conditions |
|---------|-----------|
| `keep` | p < alpha AND improvement ≥ min_improvement_pct |
| `remove` | p < alpha AND improvement ≤ -min_improvement_pct |
| `inconclusive` | Not statistically significant OR improvement too small |

## Database Storage

Experiments are automatically stored in `workflow.experiments`:

```sql
SELECT name, verdict, improvement_pct, p_value, created_at
FROM workflow.experiments
WHERE verdict = 'keep'
ORDER BY improvement_pct DESC
LIMIT 10;
```

Query past experiments:

```javascript
const { getExperimentHistory } = require('./shared/experiment-manager.cjs');

const recentWins = await getExperimentHistory({
  verdict: 'keep',
  limit: 10,
  order: 'desc'
});
```

## Production Consumer

### Consensus Replay (Active)

**File:** `shared/consensus-replay.cjs`
**Consumer:** `tools/model_regression_monitor.js` (weekly cron)

Replaces threshold-based verdicts with statistical testing:

```javascript
// OLD METHOD (legacy, still available)
const verdict = replay._generateVerdict(arbiterDelta, avgWorkerDelta);
// Returns: 'SIGNIFICANT_IMPROVEMENT', 'MODERATE_IMPROVEMENT', 'DEGRADATION', 'NO_SIGNIFICANT_CHANGE'

// NEW METHOD (statistical, Issue #267)
const result = replay.generateStatisticalVerdict(baselineConfidences, treatmentConfidences);
console.log(result.verdict);  // Same verdicts, but with statistical rigor
console.log(result.statistics.p_value);  // 0.0012
console.log(result.statistics.effect_size);  // 2.98
```

**When to use:**
- Multiple replays available (≥5 samples per group)
- Need statistical confidence in verdicts
- Automated regression detection

**When to use legacy:**
- Single replay comparison
- Quick threshold check
- Backward compatibility

## Configuration

Default settings:

```javascript
const { EXPERIMENT_CONFIG } = require('./shared/experiment-manager.cjs');

console.log(EXPERIMENT_CONFIG);
// {
//   alpha: 0.05,                      // Significance level
//   min_samples: 5,                   // Minimum samples for t-test
//   bootstrap_iterations: 1000,       // Resampling iterations
//   bootstrap_confidence: 0.95,       // CI level
//   default_min_improvement_pct: 3,   // Minimum improvement to keep
//   max_duration_ms: 600000,          // 10 minutes max
// }
```

Override per experiment:

```javascript
const result = compareResults(baseline, treatment, {
  alpha: 0.01,  // More stringent
  min_improvement_pct: 5,
  bootstrap_iterations: 5000,  // More accurate CI
});
```

## API Reference

### compareResults(baseline, treatment, options)

Direct statistical comparison.

**Returns:**
```javascript
{
  baseline_mean: number,
  treatment_mean: number,
  improvement_pct: number,
  t_stat: number,
  df: number,
  p_value: number,
  ci_lower: number,
  ci_upper: number,
  effect_size: number,
  significant: boolean,
  verdict: 'keep' | 'remove' | 'inconclusive',
  reason: string
}
```

### runExperiment(config)

Full A/B experiment with collector function.

**Config:**
```javascript
{
  name: string,              // Experiment name
  hypothesis: string,        // What you expect
  metric: string,            // What you're measuring
  baseline: Object,          // Baseline config
  treatment: Object,         // Treatment config
  collector: async (config) => number[],  // Metric collector
  success_criteria: {
    min_improvement_pct: number,
    alpha: number,
  },
  record: boolean,           // Store in DB (default: true)
  metadata: Object,          // Additional context
}
```

### recordExperiment(name, hypothesis, result)

Store experiment result in PostgreSQL.

**Returns:** `Promise<number>` (inserted row ID)

### getExperimentHistory(filters)

Query past experiments.

**Filters:**
```javascript
{
  name: string,      // Exact match
  verdict: string,   // 'keep', 'remove', 'inconclusive'
  metric: string,    // Metric name
  limit: number,     // Max results (default: 20)
  order: string,     // 'asc' or 'desc' (default: 'desc')
}
```

## Integration Layers

### experiment-integration.cjs

High-level experiment patterns (not yet in production):
- `runRolloutExperiment()` - Model rollout A/B tests
- `runVotingExperiment()` - Voting algorithm comparisons
- `runRoutingExperiment()` - Routing strategy tests
- `runQualityThresholdExperiment()` - Threshold tuning

### multi-dimensional-learning.cjs

Thompson Sampling integration (planned):
- Experiment-driven strategy selection
- Automatic A/B testing of routing decisions

## Related Documentation

- `docs/REGRESSION_MONITORING.md` - Consensus replay + regression detection
- `shared/experiment-manager.test.cjs` - Test suite with examples
- `shared/test-experiment-manager-integration.cjs` - Integration verification
