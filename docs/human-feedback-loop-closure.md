# Human Feedback Loop Closure

**Status:** Implemented  
**Created:** 2026-06-28  
**Location:** `shared/disagreement-detector.cjs`

## Overview

The human feedback loop closure system completes the learning cycle by updating Thompson Sampling bandit state and confidence calibration based on human review verdicts. When a human reviews a disagreement case, their verdict is used to:

1. Determine which models were correct
2. Update Thompson Sampling alpha/beta parameters
3. Calculate confidence calibration error
4. Track human agreement rates per model

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Multi-AI Consensus → Disagreement Detected                  │
│    ├─ Weighted voting produces winner                          │
│    ├─ Disagreement score (CV) calculated                       │
│    └─ Queue for human review if CV > threshold                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Human Reviews and Provides Verdict                          │
│    ├─ Human selects correct answer                             │
│    ├─ Human provides confidence score                          │
│    └─ Verdict stored in human_review_queue                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Feedback Loop Closure (closeHumanFeedbackLoop)              │
│    ├─ Compare each model's vote to human verdict               │
│    ├─ Update strategy_performance (Thompson Sampling)          │
│    │   ├─ Correct vote: alpha += 1, successes += 1             │
│    │   └─ Wrong vote: beta += 1, failures += 1                 │
│    ├─ Calculate calibration error                              │
│    │   ├─ If weighted correct: |confidence - 1.0|              │
│    │   └─ If weighted wrong: confidence (should be low)        │
│    └─ Store in human_feedback_learning                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Analytics & Monitoring                                      │
│    ├─ Human agreement rates per model                          │
│    ├─ Confidence calibration metrics                           │
│    └─ Thompson Sampling parameters update                      │
└─────────────────────────────────────────────────────────────────┘
```

## API

### Close Feedback Loop

```javascript
const { closeHumanFeedbackLoop } = require('./shared/disagreement-detector.cjs');

const result = await closeHumanFeedbackLoop(reviewId);
// {
//   status: 'success',
//   review_id: 24,
//   weighted_was_correct: true,
//   calibration_error: 0.15,
//   strategy_updates: [
//     { strategy: 'opus', model: 'opus', was_correct: true, reward: 1.0, updated: {...} },
//     { strategy: 'sonnet', model: 'sonnet', was_correct: true, reward: 1.0, updated: {...} },
//     { strategy: 'haiku', model: 'haiku', was_correct: false, reward: 0.0, updated: {...} }
//   ],
//   message: 'Feedback loop closed: 3 strategies updated'
// }
```

### Get Human Agreement Rates

Track how often each model agrees with human reviewers:

```javascript
const { getHumanAgreementRates } = require('./shared/disagreement-detector.cjs');

const rates = await getHumanAgreementRates({ min_reviews: 3 });
// [
//   { model: 'haiku', total_reviews: 5, correct_count: 4, agreement_rate: 0.80 },
//   { model: 'opus', total_reviews: 5, correct_count: 3, agreement_rate: 0.60 },
//   { model: 'sonnet', total_reviews: 5, correct_count: 2, agreement_rate: 0.40 }
// ]
```

### Get Calibration Metrics

Track confidence calibration (how well weighted confidence predicts correctness):

```javascript
const { getCalibrationMetrics } = require('./shared/disagreement-detector.cjs');

const metrics = await getCalibrationMetrics({ min_reviews: 3 });
// {
//   total_reviews: 10,
//   avg_calibration_error: 0.25,
//   calibration_std_dev: 0.15,
//   correct_predictions: 7,
//   accuracy: 0.70,
//   avg_confidence_when_correct: 0.85,
//   avg_confidence_when_wrong: 0.65
// }
```

## Database Schema

### workflow.human_feedback_learning

Stores feedback loop closure results:

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key |
| `review_queue_id` | integer | Foreign key to human_review_queue |
| `weighted_winner` | text | Weighted voting winner (JSON) |
| `weighted_confidence` | numeric | Weighted confidence score |
| `human_winner` | text | Human verdict answer (JSON) |
| `human_confidence` | numeric | Human confidence score |
| `weighted_was_correct` | boolean | Did weighted voting match human? |
| `confidence_calibration_error` | numeric | Calibration error |
| `strategy_updates` | jsonb | Per-strategy update details |
| `created_at` | timestamp | Creation timestamp |

### workflow.strategy_performance

Thompson Sampling bandit state:

| Column | Type | Description |
|--------|------|-------------|
| `strategy` | varchar(255) | Strategy/model name (primary key) |
| `successes` | integer | Number of successful predictions |
| `failures` | integer | Number of failed predictions |
| `alpha` | numeric | Beta distribution alpha parameter |
| `beta` | numeric | Beta distribution beta parameter |
| `total_reward` | numeric | Cumulative reward |
| `avg_reward` | numeric | Average reward |
| `last_updated` | timestamp | Last update timestamp |

## Thompson Sampling Update Logic

When a model vote is reviewed:

```javascript
// If model was correct
successes += 1
alpha += 1
reward = 1.0

// If model was wrong
failures += 1
beta += 1
reward = 0.0

// Average reward (used for sampling)
avg_reward = total_reward / (successes + failures)
```

The alpha/beta parameters are used for Thompson Sampling strategy selection:

1. Sample from Beta(alpha, beta) for each strategy
2. Select strategy with highest sample value
3. Over time, successful strategies have higher alpha → higher sampling probability

## Confidence Calibration Error

Measures how well weighted confidence predicts correctness:

```javascript
// If weighted voting was correct
calibration_error = Math.abs(weighted_confidence - 1.0)
// Example: 0.95 confidence → 0.05 error (good!)
//          0.60 confidence → 0.40 error (underconfident)

// If weighted voting was wrong
calibration_error = weighted_confidence
// Example: 0.95 confidence → 0.95 error (overconfident!)
//          0.30 confidence → 0.30 error (correctly uncertain)
```

**Lower error = better calibrated confidence scores**

## Integration Pattern

### In Workflow

```javascript
const { detectAndQueue } = require('./shared/disagreement-detector.cjs');
const { computeWeightedVote } = require('./shared/weighted-voting.cjs');

// After worker voting
const votingResult = await computeWeightedVote(votes, { ... });

// Detect disagreement and queue if needed
const disagreement = await detectAndQueue(
  votes,
  votingResult,
  {
    workflow_execution_id: execId,
    task_description: 'Analyze firmware',
  },
  { task_type: 'security_audit' }
);

if (disagreement.needs_human_review) {
  console.log(`Queued for human review: ${disagreement.queue_result.queue_id}`);
}
```

### Human Review UI (Example)

```javascript
const {
  fetchPendingReviews,
  updateReviewWithVerdict,
  closeHumanFeedbackLoop,
} = require('./shared/disagreement-detector.cjs');

// 1. Fetch pending reviews
const reviews = await fetchPendingReviews({ limit: 10, order_by: 'priority' });

// 2. Present to human reviewer (web UI, CLI, etc.)
for (const review of reviews) {
  console.log('Task:', review.task_description);
  console.log('Disagreement:', review.disagreement_score);
  console.log('Votes:', review.votes_json);
  console.log('Weighted winner:', review.weighted_winner);
}

// 3. Human provides verdict
const verdict = {
  answer: 'B',  // Human selects answer
  confidence: 0.90,
  reviewer: 'human@example.com',
  notes: 'Weighted voting missed edge case'
};

await updateReviewWithVerdict(review.id, verdict);

// 4. Close feedback loop (updates Thompson Sampling)
const result = await closeHumanFeedbackLoop(review.id);
console.log('Strategies updated:', result.strategy_updates.length);
```

## Test Coverage

**Location:** `shared/test-feedback-loop-closure.cjs`

**Scenarios tested:**

1. ✅ All models correct, high confidence
   - All strategies get alpha+=1
   - Low calibration error (underconfident)

2. ✅ Weighted voting wrong, human corrects
   - Majority wrong → beta+=1
   - Minority correct → alpha+=1
   - High calibration error (overconfident)

3. ✅ Overconfident wrong prediction
   - Very high confidence but wrong
   - Highest calibration error (0.98)
   - Teaches system to be less confident

4. ✅ Underconfident correct prediction
   - Low confidence but correct
   - Low calibration error (0.15)
   - Teaches system to be more confident

5. ✅ Mixed model correctness
   - Some models right, some wrong
   - Different alpha/beta updates per model
   - Realistic multi-model scenario

**Run tests:**

```bash
node shared/test-feedback-loop-closure.cjs
```

**Expected output:**

```
Passed: 5/5
Failed: 0/5
Success rate: 100.0%

[Human Agreement Rates]
  haiku: 80.0% (4/5)
  opus: 60.0% (3/5)
  sonnet: 40.0% (2/5)

[Calibration Metrics]
  Total reviews: 5
  Accuracy: 60.0%
  Avg calibration error: 1.156
```

## Performance Considerations

### Database Impact

- Single transaction per feedback loop closure
- Batch updates to strategy_performance (one per model)
- One insert to human_feedback_learning
- Advisory locks prevent race conditions

### Scalability

- O(N) where N = number of votes in review
- Typical N = 3-10 workers
- Expected time: <100ms per closure

### Indexes Used

```sql
-- Fast lookups
idx_hrq_status (status, disagreement_score DESC)

-- Agreement rate queries
idx_hfl_calibration (weighted_was_correct, confidence_calibration_error)

-- Strategy performance
strategy_performance_pkey (strategy)
idx_strategy_avg_reward (avg_reward DESC)
```

## Monitoring Queries

### Check recent feedback loops

```sql
SELECT
  hfl.id,
  hrq.workflow_name,
  hrq.task_description,
  hfl.weighted_was_correct,
  hfl.confidence_calibration_error,
  hfl.created_at
FROM workflow.human_feedback_learning hfl
JOIN workflow.human_review_queue hrq ON hfl.review_queue_id = hrq.id
ORDER BY hfl.created_at DESC
LIMIT 10;
```

### Check Thompson Sampling state

```sql
SELECT
  strategy,
  successes,
  failures,
  alpha,
  beta,
  avg_reward,
  last_updated
FROM workflow.strategy_performance
ORDER BY avg_reward DESC;
```

### Check per-model agreement rates

```sql
WITH model_stats AS (
  SELECT
    update_item->>'model' AS model,
    (update_item->>'was_correct')::boolean AS was_correct
  FROM workflow.human_feedback_learning hfl,
       jsonb_array_elements(hfl.strategy_updates) AS update_item
)
SELECT
  model,
  COUNT(*) AS total,
  SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) AS correct,
  AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) AS agreement_rate
FROM model_stats
GROUP BY model
ORDER BY agreement_rate DESC;
```

## Next Steps

### Automated Review Integration

Create automated review UI:

```bash
# CLI tool for human reviewers
node scripts/human-review-cli.mjs
```

### Calibration-Based Routing

Use calibration metrics to adjust confidence thresholds:

```javascript
// If model is overconfident, reduce its confidence scores
if (calibration.avg_conf_when_wrong > 0.8) {
  adjustedConfidence = vote.confidence * 0.8;
}
```

### Active Learning

Prioritize reviews that maximize learning:

```javascript
// High disagreement + low prior reviews for this task type
const priority = disagreement_score * (1 / (1 + past_reviews));
```

## References

- **Thompson Sampling:** [arxiv.org/abs/1707.02038](https://arxiv.org/abs/1707.02038)
- **Confidence Calibration:** [arxiv.org/abs/1706.04599](https://arxiv.org/abs/1706.04599)
- **Active Learning:** [burrsettles.com/pub/settles.activelearning.pdf](http://burrsettles.com/pub/settles.activelearning.pdf)
