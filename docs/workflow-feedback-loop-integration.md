# Workflow Feedback Loop Integration (Issue #249)

**Status:** ✅ COMPLETE  
**Database:** workflow.feedback on aio-01:5433  
**Created:** 2026-07-01

## Overview

Automatic quality feedback capture system that wires into workflow execution points and feeds Thompson Sampling strategy optimization.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Workflow Execution Points                                  │
│  ├─ fleet-workflow-wrapper.mjs complete()                   │
│  ├─ adversarial-verification-harness.mjs verifyAdversarially()│
│  ├─ smart-consensus.js smartConsensus()                     │
│  └─ quality-scorer.js calculateQualityScore()               │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  workflow-feedback-capture.js                               │
│  - Captures quality scores (0-1 → 0-5 rating)               │
│  - Generates automated feedback text                        │
│  - Stores to workflow.feedback table                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL: workflow.feedback                              │
│  - Feedback entries (automated/adversarial/user)            │
│  - Quality scores + ratings                                 │
│  - Metadata (source, metrics, context)                      │
│  - processed flag (FALSE by default)                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  feedback-loop-automation.js                                │
│  - Processes unprocessed feedback                           │
│  - Updates Thompson Sampling (learning.strategy_performance)│
│  - Bayesian updates: rating → alpha/beta weights            │
│  - Marks feedback as processed                              │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### workflow.feedback Table

```sql
CREATE TABLE workflow.feedback (
  id                    SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id),
  feedback_type         VARCHAR(32) CHECK (feedback_type IN ('user', 'automated', 'adversarial')),
  quality_score         REAL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
  feedback_text         TEXT NOT NULL,
  metadata              JSONB DEFAULT '{}',
  processed             BOOLEAN DEFAULT FALSE,  -- Added in Issue #249
  processed_at          TIMESTAMP WITH TIME ZONE,  -- Added in Issue #249
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_feedback_processed ON workflow.feedback(processed) WHERE processed = FALSE;
CREATE INDEX idx_feedback_type ON workflow.feedback(feedback_type);
CREATE INDEX idx_feedback_workflow ON workflow.feedback(workflow_execution_id);
```

### Metadata Fields

All feedback entries include:

```json
{
  "rating": 4.25,  // 0-5 scale (for Thompson Sampling)
  "source": "workflow_completion",  // Source of feedback
  "captured_at": "2026-07-01T12:34:56.789Z",
  // Source-specific fields...
}
```

#### Workflow Completion Source

```json
{
  "rating": 4.25,
  "source": "workflow_completion",
  "metrics": {
    "consensus": 0.9,
    "accuracy": 0.87,
    "workers_count": 3
  },
  "outcome": "success",
  "fleet_strategy": "round-robin",
  "total_duration_ms": 5000
}
```

#### Adversarial Verification Source

```json
{
  "rating": 4.5,
  "source": "adversarial_verification",
  "verdict": "ACCEPT",
  "confidence": "high",
  "refuters_failed": 3,
  "refuters_total": 3,
  "critical_issues_count": 0,
  "major_issues_count": 0
}
```

#### Consensus Performance Source

```json
{
  "rating": 4.35,
  "source": "consensus_performance",
  "consensus_rate": 0.92,
  "accuracy": 0.88,
  "findings_count": 12,
  "precision": 0.75
}
```

#### Quality Scorer Source

```json
{
  "rating": 4.6,
  "source": "quality_scorer",
  "score": 92,
  "critical_count": 0,
  "high_count": 1,
  "medium_count": 3,
  "low_count": 2,
  "meets_threshold": true
}
```

#### User Review Source

```json
{
  "rating": 4.5,
  "source": "user_review",
  "user": "username"
}
```

## Integration Points

### 1. Fleet Workflow Wrapper

**File:** `shared/fleet-workflow-wrapper.mjs`

**Location:** `complete()` function

**Captures:** Workflow completion quality score

```javascript
import { captureWorkflowFeedback } from './workflow-feedback-capture.js';

async function complete(finalResult, qualityScore, outcome = 'success') {
  // ... store execution ...

  await captureWorkflowFeedback({
    workflow_execution_id: workflowExecutionId,
    quality_score: qualityScore,
    metrics: { /* ... */ },
    outcome,
    metadata: { /* ... */ }
  });

  return { result: finalResult, stored: true };
}
```

### 2. Adversarial Verification Harness

**File:** `shared/adversarial-verification-harness.mjs`

**Location:** `verifyAdversarially()` function

**Captures:** Adversarial verification verdict

```javascript
import { captureAdversarialFeedback } from './workflow-feedback-capture.js';

export async function verifyAdversarially({ answer, originalTask, workflow_execution_id }) {
  const result = /* ... run verification ... */;

  if (workflow_execution_id) {
    await captureAdversarialFeedback({
      workflow_execution_id,
      verificationResult: result
    });
  }

  return result;
}
```

### 3. Smart Consensus

**File:** `shared/smart-consensus.js`

**Location:** `smartConsensus()` function

**Captures:** Consensus performance metrics

```javascript
import { captureConsensusFeedback } from './workflow-feedback-capture.js';

export async function smartConsensus(taskType, prompt, options = {}) {
  // ... run consensus ...

  if (options.workflow_execution_id) {
    await captureConsensusFeedback({
      workflow_execution_id: options.workflow_execution_id,
      performance: metrics,
      attribution: attribution.summarize()
    });
  }

  return { findings, consensus, unique, performance };
}
```

### 4. Quality Scorer

**File:** `shared/quality-scorer.js`

**Location:** `calculateQualityScoreWithFeedback()` function

**Captures:** Quality score breakdown

```javascript
import { captureQualityFeedback } from './workflow-feedback-capture.js';

export async function calculateQualityScoreWithFeedback(issues, options = {}) {
  const qualityScore = calculateQualityScore(issues);

  if (options.workflow_execution_id) {
    await captureQualityFeedback({
      workflow_execution_id: options.workflow_execution_id,
      qualityScore
    });
  }

  return qualityScore;
}
```

## Usage Examples

### Automated Feedback Capture

Feedback is captured automatically when workflows complete:

```javascript
import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, parallel, complete } = createFleetWorkflow(
    'my-workflow',
    'task description',
    { enableStorage: true }
  );

  const result = await agent('Do something');

  // Automated feedback captured here
  await complete(result, 0.85, 'success');
}
```

### Manual User Feedback

Capture manual user reviews:

```javascript
import { captureUserFeedback } from './shared/workflow-feedback-capture.js';

await captureUserFeedback({
  workflow_execution_id: 123,
  rating: 4.5,  // 0-5 scale
  feedback_text: 'Great results, minor improvements needed',
  metadata: {
    user: 'username',
    review_type: 'post-execution'
  }
});
```

## Feedback Processing

Process unprocessed feedback and update Thompson Sampling:

```bash
# Process all unprocessed feedback
node shared/feedback-loop-automation.js

# Run as daemon (process every 5 minutes)
node shared/feedback-loop-automation.js --daemon

# Check feedback statistics
node shared/feedback-loop-automation.js --stats
```

## Queries

### Recent Feedback

```sql
SELECT
  id,
  feedback_type,
  quality_score,
  ROUND((metadata->>'rating')::numeric, 2) as rating,
  metadata->>'source' as source,
  processed
FROM workflow.feedback
ORDER BY id DESC
LIMIT 10;
```

### Unprocessed Feedback Count

```sql
SELECT
  COUNT(*) as total_feedback,
  COUNT(*) FILTER (WHERE processed = FALSE) as unprocessed
FROM workflow.feedback;
```

### Feedback by Source

```sql
SELECT
  metadata->>'source' as source,
  COUNT(*) as count,
  AVG(quality_score) as avg_quality_score,
  AVG((metadata->>'rating')::float) as avg_rating
FROM workflow.feedback
GROUP BY metadata->>'source'
ORDER BY count DESC;
```

### Workflow with Feedback

```sql
SELECT
  we.workflow_name,
  we.task_description,
  wf.feedback_type,
  wf.quality_score,
  wf.metadata->>'rating' as rating,
  wf.metadata->>'source' as source,
  wf.processed
FROM workflow.executions we
JOIN workflow.feedback wf ON we.id = wf.workflow_execution_id
WHERE we.id = 123
ORDER BY wf.created_at DESC;
```

## Testing

Run integration tests:

```bash
# Test feedback capture (creates test workflow + 5 feedback entries)
node shared/test-workflow-feedback.js

# Expected output:
# ✅ ALL TESTS PASSED
# Integration verified:
#   ✓ Feedback capture functions work
#   ✓ Data flows to workflow.feedback table
#   ✓ Multiple feedback types supported
#   ✓ Ready for Thompson Sampling processing
```

## Metrics

Current feedback statistics:

```bash
psql -h aio-01 -p 5433 -U claude -d learning -c "
  SELECT
    COUNT(*) as total_feedback,
    COUNT(*) FILTER (WHERE feedback_type = 'automated') as automated,
    COUNT(*) FILTER (WHERE feedback_type = 'adversarial') as adversarial,
    COUNT(*) FILTER (WHERE feedback_type = 'user') as user_reviews,
    COUNT(*) FILTER (WHERE processed = FALSE) as unprocessed,
    AVG(quality_score) as avg_quality_score
  FROM workflow.feedback
"
```

## Thompson Sampling Integration

Feedback flows into Thompson Sampling via `feedback-loop-automation.js`:

1. **Unprocessed feedback** (processed = FALSE) is queried
2. **Rating conversion**: 0-5 rating → success/failure weights
   - rating = 5.0 → alpha += 1.0, beta += 0.0 (full success)
   - rating = 2.5 → alpha += 0.5, beta += 0.5 (neutral)
   - rating = 0.0 → alpha += 0.0, beta += 1.0 (full failure)
3. **Strategy update**: `learning.strategy_performance` updated
4. **Mark processed**: processed = TRUE, processed_at = NOW()

## Files Modified

- ✅ `shared/workflow-feedback-capture.js` (NEW)
- ✅ `shared/fleet-workflow-wrapper.mjs` (integrated)
- ✅ `shared/adversarial-verification-harness.mjs` (integrated)
- ✅ `shared/smart-consensus.js` (integrated)
- ✅ `shared/quality-scorer.js` (integrated)
- ✅ `shared/test-workflow-feedback.js` (NEW test)
- ✅ `workflow.feedback` table (added processed/processed_at columns)

## Next Steps

1. ✅ Wire feedback capture into 4 integration points
2. ✅ Add processed/processed_at columns to workflow.feedback
3. ✅ Create test script to verify integration
4. ⏭️  Run feedback-loop-automation.js to process entries
5. ⏭️  Monitor Thompson Sampling updates in learning.strategy_performance
6. ⏭️  Measure quality improvements over time

## Related Issues

- Issue #249: Wire in workflow feedback loop
- Building Block #1: Feedback loop automation (already implemented)
- Thompson Sampling: learning.strategy_performance table

## References

- Feedback Loop Automation: `shared/feedback-loop-automation.js`
- Workflow Storage: `shared/workflow-storage-adapter.cjs`
- Thompson Sampling: `learning/postgres-adapter.js`
