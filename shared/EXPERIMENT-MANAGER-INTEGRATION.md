# Experiment Manager Integration Guide

**Issue:** #267  
**Status:** Active  
**Created:** 2026-07-01

## Overview

The experiment manager (`experiment-manager.cjs`) provides A/B testing framework with statistical significance testing (Welch's t-test + bootstrap confidence intervals). This document shows how to integrate it into active workflows.

## Integration Points

### 1. Multi-Dimensional Learning (Thompson Sampling)

**File:** `shared/multi-dimensional-learning.cjs`

**Integration:** Use experiments to compare strategy performance before updating Thompson Sampling bandits.

**Example:**

```javascript
const { runExperiment } = require('./experiment-manager.cjs');
const { selectStrategy, recordStrategyOutcome } = require('./multi-dimensional-learning.cjs');

// A/B test two strategies before deploying to production
async function experimentWithStrategy(capability, taskType, baselineStrategy, treatmentStrategy) {
  const result = await runExperiment({
    name: `strategy_${capability}_${taskType}_${Date.now()}`,
    hypothesis: `${treatmentStrategy} outperforms ${baselineStrategy} for ${taskType}`,
    metric: 'quality_score',
    baseline: { strategy: baselineStrategy },
    treatment: { strategy: treatmentStrategy },
    collector: async (config) => {
      const qualities = [];
      for (let i = 0; i < 20; i++) {
        // Execute task with this strategy
        const quality = await executeTask(capability, taskType, config.strategy);
        qualities.push(quality);
      }
      return qualities;
    },
    success_criteria: {
      min_improvement_pct: 5, // Must be 5% better
      alpha: 0.05
    }
  });

  // If treatment wins, promote it
  if (result.verdict === 'keep') {
    console.log(`✅ Promoting ${treatmentStrategy} (${result.improvement_pct.toFixed(2)}% improvement)`);
    // Update Thompson Sampling priors to favor this strategy
    await recordStrategyOutcome(capability, taskType, treatmentStrategy, true, result.treatment_mean);
  }

  return result;
}
```

**Wiring Location:** Add `experimentWithStrategy()` function to `multi-dimensional-learning.cjs` (lines 400-450)

---

### 2. Workflow Feedback Capture

**File:** `shared/workflow-feedback-capture.js`

**Integration:** Use experiments to test quality scorer improvements.

**Example:**

```javascript
import { runExperiment } from './experiment-manager.cjs';
import { WorkflowFeedbackCapture } from './workflow-feedback-capture.js';

// Test new quality scoring algorithm
async function experimentQualityScorer(baselineScorer, treatmentScorer, testCases) {
  return await runExperiment({
    name: `quality_scorer_${Date.now()}`,
    hypothesis: 'New quality scorer correlates better with ground truth',
    metric: 'accuracy',
    baseline: baselineScorer,
    treatment: treatmentScorer,
    collector: async (scorer) => {
      return testCases.map(testCase => {
        const score = scorer(testCase.workflow_result);
        // Compare to ground truth (manual rating)
        return Math.abs(score - testCase.ground_truth) <= 0.1 ? 1 : 0;
      });
    },
    success_criteria: {
      min_improvement_pct: 3,
      alpha: 0.05
    }
  });
}
```

**Wiring Location:** Add to `workflow-feedback-capture.js` as new method (lines 350-400)

---

### 3. Model Rotation

**File:** `shared/model-rotation.cjs`

**Integration:** Already wired! See `experiment-integration.cjs` `runRolloutExperiment()`

**Usage:**

```javascript
const { runRolloutExperiment } = require('./experiment-integration.cjs');

// Test faster canary rollout
const result = await runRolloutExperiment({
  model: 'opus-4.0',
  baseline: { stage: 'canary', duration_days: 3 },
  treatment: { stage: 'canary', duration_days: 1 },
  samples: 30
});

if (result.verdict === 'keep') {
  console.log('✅ Fast rollout maintains quality - deploying');
}
```

---

### 4. Weighted Voting Algorithms

**File:** `shared/weighted-voting.cjs`

**Integration:** Already wired! See `experiment-integration.cjs` `runVotingExperiment()`

**Usage:**

```javascript
const { runVotingExperiment } = require('./experiment-integration.cjs');

// Test disagreement detection
const result = await runVotingExperiment({
  votes: mockVotes,
  taskType: 'code_review',
  baselineOptions: { algorithm: 'standard' },
  treatmentOptions: { algorithm: 'with_disagreement_detection' },
  iterations: 50
});
```

---

### 5. Batch Consensus

**File:** `shared/batch-consensus.cjs`

**Integration:** Test batch size optimization.

**Example:**

```javascript
const { runExperiment } = require('./experiment-manager.cjs');
const { batchConsensus } = require('./batch-consensus.cjs');

async function experimentBatchSize(tasks, baselineBatchSize, treatmentBatchSize) {
  return await runExperiment({
    name: `batch_size_${Date.now()}`,
    hypothesis: `Batch size ${treatmentBatchSize} improves throughput vs ${baselineBatchSize}`,
    metric: 'throughput_tasks_per_sec',
    baseline: { batchSize: baselineBatchSize },
    treatment: { batchSize: treatmentBatchSize },
    collector: async (config) => {
      const start = Date.now();
      await batchConsensus(tasks, { batchSize: config.batchSize });
      const duration = Date.now() - start;
      return [tasks.length / (duration / 1000)]; // tasks/sec
    },
    success_criteria: {
      min_improvement_pct: 10, // Need 10% throughput gain
      alpha: 0.05
    }
  });
}
```

**Wiring Location:** Add to `batch-consensus.cjs` (lines 450-500)

---

### 6. Circuit Breaker Thresholds

**File:** `shared/circuit-breaker.cjs`

**Integration:** Optimize failure thresholds.

**Example:**

```javascript
const { runExperiment } = require('./experiment-manager.cjs');

async function experimentCircuitBreakerThreshold() {
  return await runExperiment({
    name: `circuit_breaker_threshold_${Date.now()}`,
    hypothesis: 'Lower failure threshold (3) reduces cascading failures vs baseline (5)',
    metric: 'cascade_prevention_rate',
    baseline: { failureThreshold: 5 },
    treatment: { failureThreshold: 3 },
    collector: async (config) => {
      // Simulate 100 request sequences with various failure rates
      const preventionRates = [];
      for (let i = 0; i < 100; i++) {
        const prevented = simulateCascadeScenario(config.failureThreshold);
        preventionRates.push(prevented ? 1 : 0);
      }
      return preventionRates;
    }
  });
}
```

**Wiring Location:** Add to `circuit-breaker.cjs` (lines 300-350)

---

### 7. Intelligent Fallback

**File:** `shared/intelligent-fallback.cjs`

**Integration:** Test fallback chain optimization.

**Example:**

```javascript
async function experimentFallbackChain(baselineChain, treatmentChain) {
  return await runExperiment({
    name: `fallback_chain_${Date.now()}`,
    hypothesis: 'Optimized fallback chain reduces latency while maintaining success',
    metric: 'success_rate',
    baseline: { chain: baselineChain },
    treatment: { chain: treatmentChain },
    collector: async (config) => {
      const results = [];
      for (let i = 0; i < 50; i++) {
        const success = await testFallbackChain(config.chain);
        results.push(success ? 1 : 0);
      }
      return results;
    }
  });
}
```

---

## Database Schema

Experiments are stored in `workflow.experiments` table on `aio-01:5433`:

```sql
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
  verdict TEXT NOT NULL, -- 'keep', 'remove', 'inconclusive'
  success_criteria JSONB,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Usage Patterns

### Pattern 1: Pre-Deployment Validation

Test changes before rolling to production:

```javascript
const result = await runExperiment({
  name: 'pre_deployment_test',
  hypothesis: 'New algorithm maintains quality',
  metric: 'quality_score',
  baseline: currentImplementation,
  treatment: newImplementation,
  collector: runBenchmark,
  success_criteria: {
    min_improvement_pct: 0, // Accept no degradation
    alpha: 0.05
  }
});

if (result.verdict === 'keep' || result.verdict === 'inconclusive') {
  deploy(newImplementation);
} else {
  console.warn('Deployment blocked: regression detected');
}
```

### Pattern 2: Continuous Improvement

Run periodic experiments to discover improvements:

```javascript
// Weekly experiment: test new strategies
setInterval(async () => {
  const candidates = await generateStrategyCandidates();
  for (const candidate of candidates) {
    const result = await runExperiment({
      name: `weekly_strategy_test_${candidate.name}`,
      hypothesis: `${candidate.name} improves over baseline`,
      metric: 'quality_score',
      baseline: getCurrentBestStrategy(),
      treatment: candidate,
      collector: benchmarkStrategy
    });

    if (result.verdict === 'keep') {
      await promoteToBest(candidate);
    }
  }
}, 7 * 24 * 60 * 60 * 1000); // Every 7 days
```

### Pattern 3: Hyperparameter Tuning

Optimize configuration parameters:

```javascript
// Grid search with statistical testing
const batchSizes = [4, 8, 16, 32];
const results = [];

for (let i = 1; i < batchSizes.length; i++) {
  const result = await runExperiment({
    name: `batch_size_${batchSizes[i-1]}_vs_${batchSizes[i]}`,
    hypothesis: `Batch size ${batchSizes[i]} improves throughput`,
    metric: 'throughput',
    baseline: { batchSize: batchSizes[i-1] },
    treatment: { batchSize: batchSizes[i] },
    collector: benchmarkBatchSize
  });
  results.push(result);
}

// Select best performing batch size
const winner = results.find(r => r.verdict === 'keep' && r.improvement_pct > 10);
```

---

## Testing

Run integration tests:

```bash
# Test all experiment types
node shared/example-experiment-integration.cjs --type all

# Test specific integration
node shared/test-experiment-integration.cjs

# Verify database storage
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT * FROM workflow.experiments ORDER BY created_at DESC LIMIT 5;"
```

---

## Verification Steps

1. **Database connectivity:**
   ```bash
   node -e "const {ensureSchema} = require('./shared/experiment-manager.cjs'); ensureSchema().then(() => console.log('✅ Schema ready'))"
   ```

2. **Run example experiment:**
   ```bash
   node shared/example-experiment-integration.cjs --type rollout
   ```

3. **Check results in database:**
   ```sql
   SELECT name, verdict, improvement_pct, p_value, created_at 
   FROM workflow.experiments 
   ORDER BY created_at DESC LIMIT 10;
   ```

4. **Verify statistical correctness:**
   ```bash
   node shared/experiment-manager.test.cjs
   ```

---

## Next Steps

1. ✅ Wire into `multi-dimensional-learning.cjs` (strategy experiments)
2. ✅ Wire into `workflow-feedback-capture.js` (quality scorer experiments)
3. ✅ Wire into `batch-consensus.cjs` (batch size optimization)
4. ✅ Wire into `circuit-breaker.cjs` (threshold tuning)
5. ✅ Wire into `intelligent-fallback.cjs` (fallback chain optimization)
6. ⏳ Create cron job for weekly continuous improvement experiments
7. ⏳ Build Grafana dashboard for experiment tracking

---

## Contact

For questions or issues, see Issue #267 or check the experiment manager tests in `shared/experiment-manager.test.cjs`.
