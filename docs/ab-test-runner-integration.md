# A/B Test Runner Integration

**Status:** ACTIVE  
**Issue:** #262  
**Created:** 2026-07-01

## Overview

The A/B test runner (`shared/ab-runner.cjs`) is now fully integrated into the learning system through `learning/ab-test-integration.js`.

## Integration Points

### 1. Learning System
**File:** `learning/ab-test-integration.js`

Primary integration layer that wires ab-runner into the active learning engine.

**Functions:**
- `runABTestFromPlan(experiment)` - Execute A/B test from learning plan
- `runFeatureComparisonTest(baseline, treatment, handler)` - Simple feature comparison
- `runMultiVariantTest(name, variants, handler)` - Multi-variant testing (A/B/C/D...)
- `recordABTestResult(name, hypothesis, result)` - Store in PostgreSQL
- `getABTestHistory(filters)` - Query past A/B tests
- `generateABTestSummary()` - Summary statistics

### 2. Experiment Executor
**File:** `learning/experiment-executor.js`

Updated to import and use `ab-test-integration.js`:

```javascript
const { runABTestFromPlan } = require('./ab-test-integration.js');
```

### 3. Experiment Manager
**File:** `shared/experiment-manager.cjs`

A/B test results are stored in PostgreSQL using the experiment manager's storage layer.

**Schema:** `workflow.experiments` table
- Stores baseline/treatment configurations
- Records statistical results (p-value, effect size, confidence intervals)
- Tracks verdict (keep/remove/inconclusive)

### 4. System-Level Experiments
**File:** `shared/experiment-integration.cjs`

High-level experiment patterns for system components:
- Model rollout experiments
- Voting algorithm experiments
- Routing strategy experiments
- Quality threshold experiments

## Usage

### Example 1: Simple A/B Test

```javascript
const { runABTestFromPlan } = require('./learning/ab-test-integration.js');

const handler = async (iteration, features) => {
  // Simulate execution with features enabled
  const quality = features.includes('thompson_sampling') ? 0.82 : 0.70;
  return {
    quality: quality + (Math.random() * 0.05 - 0.025),
    latency_ms: 1000 + Math.random() * 200,
    cost_usd: 0.01 + Math.random() * 0.005,
  };
};

const result = await runABTestFromPlan({
  opportunity: 'Thompson Sampling vs Random routing',
  type: 'routing_strategy',
  variants: [
    { name: 'baseline', features: [] },
    { name: 'thompson', features: ['thompson_sampling'] },
  ],
  handler,
}, { samples: 30 });

console.log(`Winner: ${result.winner}`);
console.log(`p-value: ${result.statistics.pairwise.baseline_vs_thompson.quality.t_test.p_value}`);
```

### Example 2: Feature Comparison

```javascript
const { runFeatureComparisonTest } = require('./learning/ab-test-integration.js');

const result = await runFeatureComparisonTest(
  [],  // baseline: no features
  ['thompson_sampling', 'consensus', 'caching'],  // treatment
  handler,
  30  // samples per variant
);
```

### Example 3: Multi-Variant Test

```javascript
const { runMultiVariantTest } = require('./learning/ab-test-integration.js');

const result = await runMultiVariantTest('routing_strategies', [
  { name: 'random', features: [] },
  { name: 'round_robin', features: ['round_robin'] },
  { name: 'thompson', features: ['thompson_sampling'] },
  { name: 'quality_first', features: ['quality_first_routing'] },
], handler);

console.log(`Winner: ${result.winner}`);
```

## Testing

Run the integration test suite:

```bash
# Simple A/B test
node learning/test-ab-integration.js --type simple

# Feature comparison
node learning/test-ab-integration.js --type features

# Multi-variant test
node learning/test-ab-integration.js --type multi

# Summary of all tests
node learning/test-ab-integration.js --type summary

# Run all tests
node learning/test-ab-integration.js --type all
```

## Statistical Features

The ab-runner provides:

1. **Welch's t-test** - Unequal variance comparison with p-values
2. **Cohen's d effect size** - Measure magnitude of difference
3. **Bootstrap confidence intervals** - Non-parametric CI estimation
4. **Cost/Latency/Quality tradeoff** - Multi-objective optimization
5. **Markdown reports** - Automatically generated and saved

## Report Output

Reports are saved to: `~/.claude/learning/ab-test-reports/`

Format: `{experiment_name}_{date}.md`

Example report sections:
- Winner and tradeoff score
- Variant summaries (quality, latency, cost)
- Confidence intervals (95%)
- Pairwise comparisons (p-value, effect size)
- Cost/latency/quality tradeoff analysis

## Database Schema

A/B test results are stored in PostgreSQL `workflow.experiments`:

```sql
SELECT 
  name,
  hypothesis,
  baseline_mean,
  treatment_mean,
  improvement_pct,
  p_value,
  effect_size,
  verdict,
  created_at
FROM workflow.experiments
WHERE metadata->>'ab_test' = 'true'
ORDER BY created_at DESC;
```

## Feature Toggle System

ab-runner includes a feature toggle registry:

```javascript
const { enableFeatures, isFeatureEnabled, clearFeatures } = require('./shared/ab-runner.cjs');

// Enable features for a variant
enableFeatures(['thompson_sampling', 'consensus']);

// Check if enabled
if (isFeatureEnabled('thompson_sampling')) {
  // Use Thompson Sampling routing
}

// Clear all toggles
clearFeatures();
```

## Integration with Existing Systems

### Active Learning Engine
`learning/active-learning-engine.js` can use ab-runner to validate learning opportunities:

```javascript
const { runABTestFromPlan } = require('./ab-test-integration.js');

// Convert learning opportunity to A/B test
const result = await runABTestFromPlan({
  opportunity: opportunity.description,
  type: opportunity.type,
  variants: opportunity.variants,
  handler: opportunity.handler,
});
```

### Strategic Learning Planner
`learning/strategic-learning-planner.js` can prioritize experiments by A/B test results:

```javascript
const { getABTestHistory } = require('./ab-test-integration.js');

const pastTests = await getABTestHistory({ verdict: 'keep', limit: 20 });
// Use successful tests to inform future experiments
```

## Verification

To verify integration is active:

1. **Run test suite:**
   ```bash
   node learning/test-ab-integration.js --type all
   ```

2. **Check PostgreSQL storage:**
   ```bash
   psql -h aio-01 -p 5433 -U sfloess -d learning -c \
     "SELECT COUNT(*) FROM workflow.experiments WHERE metadata->>'ab_test' = 'true';"
   ```

3. **Check report generation:**
   ```bash
   ls -lh ~/.claude/learning/ab-test-reports/
   ```

4. **Check imports:**
   ```bash
   grep -r "ab-test-integration\|ab-runner" learning/ shared/ --include="*.js"
   ```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│ Learning System                                         │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │ active-learning-engine.js                      │    │
│  │ (Identifies learning opportunities)            │    │
│  └───────────────┬────────────────────────────────┘    │
│                  │                                      │
│                  v                                      │
│  ┌────────────────────────────────────────────────┐    │
│  │ ab-test-integration.js (NEW)                   │    │
│  │ - runABTestFromPlan()                          │    │
│  │ - runFeatureComparisonTest()                   │    │
│  │ - runMultiVariantTest()                        │    │
│  │ - recordABTestResult()                         │    │
│  └───────────────┬────────────────────────────────┘    │
│                  │                                      │
│                  v                                      │
│  ┌────────────────────────────────────────────────┐    │
│  │ experiment-executor.js                         │    │
│  │ (Orchestrates experiment execution)            │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                     │
                     v
┌─────────────────────────────────────────────────────────┐
│ Shared Components                                       │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │ ab-runner.cjs (Statistical Framework)          │    │
│  │ - runABTest()                                  │    │
│  │ - computeStatistics()                          │    │
│  │ - generateReport()                             │    │
│  │ - Feature toggle system                        │    │
│  │ - Welch's t-test, Cohen's d, Bootstrap CI      │    │
│  └───────────────┬────────────────────────────────┘    │
│                  │                                      │
│                  v                                      │
│  ┌────────────────────────────────────────────────┐    │
│  │ experiment-manager.cjs (PostgreSQL Storage)    │    │
│  │ - recordExperiment()                           │    │
│  │ - getExperimentHistory()                       │    │
│  │ - workflow.experiments table                   │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                     │
                     v
┌─────────────────────────────────────────────────────────┐
│ PostgreSQL (aio-01:5433)                                │
│ Database: learning                                      │
│ Schema: workflow.experiments                            │
└─────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Wire into active workflows** - Integrate A/B testing into existing multi-AI workflows
2. **Automated experiment scheduling** - Run A/B tests on schedule to validate improvements
3. **Historical analysis** - Use past A/B tests to refine future experiments
4. **Integration with Thompson Sampling** - Use A/B test results to update bandit priors

## Related Files

- `shared/ab-runner.cjs` - Statistical A/B testing framework
- `shared/ab-runner.test.cjs` - Unit tests
- `learning/ab-test-integration.js` - Learning system integration (NEW)
- `learning/test-ab-integration.js` - Integration tests (NEW)
- `learning/experiment-executor.js` - Experiment orchestration (UPDATED)
- `shared/experiment-manager.cjs` - PostgreSQL storage
- `shared/experiment-integration.cjs` - System-level experiments
- `shared/example-experiment-integration.cjs` - Usage examples

## Documentation

- This file: `docs/ab-test-runner-integration.md`
- Experiment integration guide: `docs/experiment-integration-guide.md`
