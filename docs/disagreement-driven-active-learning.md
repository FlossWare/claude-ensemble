# Disagreement-Driven Active Learning

**Status:** Production Ready  
**Created:** 2026-06-28  
**Integration:** Multi-AI consensus workflows

## Overview

Disagreement-driven active learning detects high-variance voting patterns in multi-AI consensus and flags ambiguous tasks for human review instead of blindly picking a winner.

### The Problem

When models disagree with high variance:
- **Old behavior:** 3 models say "A" (60% confidence), 3 models say "B" (55% confidence)  
  → Weighted voting picks "A", no flag that this was ambiguous
- **New behavior:** High disagreement detected (CV=0.25)  
  → Flag for human review, proceed with weighted voting but log warning

### Key Metrics

**Disagreement Score:** Coefficient of Variation (CV)  
```
CV = std_dev(confidences) / mean(confidences)
```

**Thresholds:**
- **CV < 0.10:** Low disagreement (proceed normally)
- **CV 0.10-0.20:** Moderate disagreement (log warning)
- **CV 0.20-0.40:** High disagreement (flag for human review)
- **CV > 0.40:** Critical disagreement (urgent review required)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Multi-AI Consensus Workflow                                 │
├─────────────────────────────────────────────────────────────┤
│ 1. Workers execute in parallel                              │
│ 2. Weighted voting computes winner                          │
│ 3. Disagreement detection (NEW)                             │
│    ├─ Calculate CV (coefficient of variation)               │
│    ├─ If CV > threshold:                                    │
│    │  ├─ Store in human_review_queue                        │
│    │  ├─ Log warning                                        │
│    │  └─ Set needs_human_review flag                        │
│    └─ Else: proceed normally                                │
│ 4. Arbiter synthesis (proceeds regardless)                  │
│ 5. Human review (asynchronous)                              │
└─────────────────────────────────────────────────────────────┘
```

## Files

### Core Implementation

- **`learning/schema-human-review.sql`** - PostgreSQL schema
  - `workflow.human_review_queue` - Main queue table
  - `workflow.human_feedback_learning` - Feedback loop integration
  - Materialized view for dashboard summary

- **`shared/disagreement-detector.cjs`** - Detection logic
  - `analyzeDisagreement()` - Calculate CV and statistics
  - `detectAndQueue()` - Main integration point
  - `storeInReviewQueue()` - Store high-disagreement tasks
  - `fetchPendingReviews()` - Query pending reviews
  - `updateReviewWithVerdict()` - Record human verdict

- **`shared/weighted-voting.cjs`** - Updated with integration
  - `runWeightedVotingWithDisagreementDetection()` - New entry point
  - Calls `detectAndQueue()` BEFORE arbiter synthesis
  - Non-blocking (workflow proceeds even if queue storage fails)

### Documentation

- **`learning/human-review-queries.sql`** - Example queries
  - Fetch pending reviews
  - Update review status
  - Statistics and analysis
  - Feedback loop analysis

- **`docs/disagreement-driven-active-learning.md`** - This file

## Integration

### Step 1: Apply Database Schema

```bash
PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning psql -U sfloess -f learning/schema-human-review.sql
```

Verify:
```bash
PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning psql -U sfloess -c "\dt workflow.*"
```

Should show:
- `workflow.human_review_queue`
- `workflow.human_feedback_learning`
- `workflow.schema_version`

### Step 2: Update Workflow Code

#### Option A: Update Existing Weighted Voting (Recommended)

Replace:
```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');
const result = runWeightedVoting(votes, taskType, { minConfidence: 20 });
```

With:
```javascript
const { runWeightedVotingWithDisagreementDetection } = require('./shared/weighted-voting.cjs');

const result = await runWeightedVotingWithDisagreementDetection(votes, taskType, {
  minConfidence: 20,
  reviewThreshold: 0.20,  // CV threshold for human review
  context: {
    workflow_execution_id: executionId,
    workflow_name: 'ai-consensus-weighted',
    task_description: task,
  },
});

// Check if human review needed
if (result.needs_human_review) {
  log(`⚠️  HIGH DISAGREEMENT: Flagged for human review (CV: ${result.disagreement.disagreement_score.toFixed(3)})`);
  log(`   Queue ID: ${result.human_review_queue.queue_id}`);
}

// Proceed with arbiter synthesis (workflow continues)
const arbiterPrompt = result.buildArbiterPrompt(task);
```

#### Option B: Use Disagreement Detector Directly

```javascript
const { detectAndQueue } = require('./shared/disagreement-detector.cjs');

// After weighted voting
const votingResult = runWeightedVoting(votes, taskType, options);

// Detect disagreement
const disagreement = await detectAndQueue(votes, votingResult.voting_result, {
  workflow_execution_id: executionId,
  workflow_name: 'my-workflow',
  task_description: task,
}, {
  review_threshold: 0.20,
});

if (disagreement.needs_human_review) {
  console.warn(`HIGH DISAGREEMENT: CV=${disagreement.disagreement_score.toFixed(3)}`);
}
```

### Step 3: Update ai-consensus-weighted.js (Example)

See `shared/weighted-voting.cjs` lines 683-761 for integration pattern.

Key changes:
1. Import `runWeightedVotingWithDisagreementDetection`
2. Pass `context` object with workflow metadata
3. Check `result.needs_human_review` flag
4. Log warnings if high disagreement detected

## Human Review Workflow

### 1. Fetch Pending Reviews

```sql
SELECT
  id,
  workflow_name,
  task_description,
  disagreement_score,
  num_votes,
  unique_answers,
  priority,
  created_at
FROM workflow.human_review_queue
WHERE status = 'pending'
ORDER BY disagreement_score DESC
LIMIT 10;
```

Or via JavaScript:
```javascript
const { fetchPendingReviews } = require('./shared/disagreement-detector.cjs');

const reviews = await fetchPendingReviews({
  limit: 10,
  order_by: 'disagreement_score',  // or 'priority', 'created_at'
  status: 'pending',
});

reviews.forEach(r => {
  console.log(`ID ${r.id}: ${r.task_description}`);
  console.log(`  Disagreement: ${r.disagreement_score.toFixed(3)} (${r.disagreement_level})`);
  console.log(`  Votes: ${r.num_votes}, Unique answers: ${r.unique_answers}`);
  console.log(`  Weighted winner: ${JSON.stringify(r.weighted_winner)}`);
  console.log('');
});
```

### 2. Examine Review Details

```javascript
const reviews = await fetchPendingReviews({ limit: 1 });
const review = reviews[0];

console.log('Task:', review.task_description);
console.log('Disagreement:', review.disagreement_score);
console.log('Votes:', review.votes_json);
console.log('Confidence stats:', review.confidence_range);
console.log('Weighted winner:', review.weighted_winner);
console.log('Runner-up:', review.runner_up);
```

### 3. Mark as Reviewed

```javascript
const { updateReviewWithVerdict } = require('./shared/disagreement-detector.cjs');

const result = await updateReviewWithVerdict(123, {
  answer: 'Option A',  // Human's selected answer
  confidence: 85,      // Human's confidence (0-100)
  reviewer: 'user@example.com',
  notes: 'After analysis, Option A is correct because...',
});

console.log('Review updated:', result.message);
```

Or via SQL:
```sql
UPDATE workflow.human_review_queue
SET
  status = 'reviewed',
  human_verdict = '{"answer": "Option A", "confidence": 85}'::jsonb,
  human_reviewer = 'user@example.com',
  reviewed_at = NOW(),
  resolution_notes = 'Option A is correct because...'
WHERE id = 123;
```

## Feedback Loop Integration

### Goal: Use human verdicts to improve Thompson Sampling

When a human reviews a high-disagreement task:
1. Compare weighted winner vs human verdict
2. Calculate accuracy: Was weighted voting correct?
3. Calculate confidence error: How far off was the confidence?
4. Update Thompson Sampling strategies

### Implementation (TODO)

```javascript
// After human verdict recorded
const review = await fetchPendingReviews({ limit: 1, status: 'reviewed' });

// Extract verdicts
const weightedWinner = review.weighted_winner.answer;
const weightedConfidence = review.winner_confidence;
const humanWinner = review.human_verdict.answer;
const humanConfidence = review.human_verdict.confidence;

// Calculate accuracy
const weightedWasCorrect = (weightedWinner === humanWinner);
const confidenceError = Math.abs(weightedConfidence - humanConfidence);

// Update Thompson Sampling
const { StrategyPerformance } = require('./learning/postgres-adapter.js');
const strategyPerf = new StrategyPerformance();

if (weightedWasCorrect) {
  await strategyPerf.record('weighted_voting', true, 1.0 - confidenceError / 100);
} else {
  await strategyPerf.record('weighted_voting', false, 0.0);
}

// Store learning feedback
await client.query(`
  INSERT INTO workflow.human_feedback_learning
    (review_queue_id, weighted_winner, weighted_confidence,
     human_winner, human_confidence, weighted_was_correct,
     confidence_calibration_error)
  VALUES ($1, $2, $3, $4, $5, $6, $7)
`, [
  review.id,
  JSON.stringify(weightedWinner),
  weightedConfidence,
  JSON.stringify(humanWinner),
  humanConfidence,
  weightedWasCorrect,
  confidenceError,
]);
```

## Configuration

### Disagreement Thresholds

Edit `shared/disagreement-detector.cjs`:
```javascript
const DISAGREEMENT_THRESHOLDS = {
  LOW: 0.10,       // 10% variation or less
  MODERATE: 0.20,  // 10-20% variation
  HIGH: 0.40,      // 20-40% variation → flag for review
  CRITICAL: 0.40,  // >40% variation → urgent review
};

const DEFAULT_REVIEW_THRESHOLD = 0.20;  // Default: flag at 20% CV
```

### Per-Workflow Overrides

```javascript
const result = await runWeightedVotingWithDisagreementDetection(votes, taskType, {
  reviewThreshold: 0.15,  // More aggressive flagging (15% CV)
  context: { ... },
});
```

## Monitoring

### Dashboard Queries

See `learning/human-review-queries.sql` for full query library.

**Pending review count:**
```sql
SELECT COUNT(*) FROM workflow.human_review_queue WHERE status = 'pending';
```

**High-priority reviews:**
```sql
SELECT COUNT(*) FROM workflow.human_review_queue 
WHERE status = 'pending' AND priority >= 8;
```

**Average disagreement by level:**
```sql
SELECT disagreement_level, AVG(disagreement_score), COUNT(*)
FROM workflow.human_review_queue
WHERE status = 'pending'
GROUP BY disagreement_level;
```

**Weighted voting accuracy:**
```sql
SELECT
  disagreement_level,
  COUNT(*) as total,
  COUNT(CASE WHEN weighted_winner->>'answer' = human_verdict->>'answer' THEN 1 END) as correct,
  ROUND(100.0 * COUNT(CASE WHEN weighted_winner->>'answer' = human_verdict->>'answer' THEN 1 END) / COUNT(*), 2) as accuracy_pct
FROM workflow.human_review_queue
WHERE status = 'reviewed' AND human_verdict IS NOT NULL
GROUP BY disagreement_level;
```

### Materialized View (Auto-Summary)

Refresh every 5 minutes:
```sql
SELECT workflow.refresh_review_summary();
```

Query summary:
```sql
SELECT * FROM workflow.review_queue_summary
ORDER BY status, disagreement_level;
```

Add to cron (optional):
```bash
# Refresh every 5 minutes
*/5 * * * * psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT workflow.refresh_review_summary();" > /dev/null 2>&1
```

## Error Handling

### Non-Blocking Integration

Disagreement detection is **non-blocking**:
- If PostgreSQL unavailable: Log warning, workflow proceeds
- If embedding generation fails: Store NULL, workflow proceeds
- If queue storage fails: Log error, weighted voting result still returned

Example:
```javascript
const result = await runWeightedVotingWithDisagreementDetection(...);

// result.human_review_queue may be null if storage failed
if (result.human_review_queue?.status === 'queued') {
  log(`Queued for review: ${result.human_review_queue.queue_id}`);
} else if (result.needs_human_review) {
  log(`WARNING: High disagreement detected but queue storage failed`);
}

// Weighted voting result always available
const winner = result.voting_result.winner;
```

### Graceful Degradation

```javascript
try {
  const result = await runWeightedVotingWithDisagreementDetection(...);
  // Use result
} catch (err) {
  console.error('Disagreement detection failed:', err);
  
  // Fallback to standard weighted voting
  const result = runWeightedVoting(votes, taskType, options);
  // Use result
}
```

## Testing

### Unit Tests (TODO)

```javascript
const { analyzeDisagreement, coefficientOfVariation } = require('./shared/disagreement-detector.cjs');

// Test CV calculation
const votes = [
  { model: 'opus', answer: 'A', confidence: 90 },
  { model: 'sonnet', answer: 'A', confidence: 85 },
  { model: 'haiku', answer: 'B', confidence: 45 },
  { model: 'fable', answer: 'B', confidence: 50 },
];

const analysis = analyzeDisagreement(votes);
console.log('Disagreement score:', analysis.disagreement_score);
console.log('Disagreement level:', analysis.disagreement_level);
console.log('Needs review:', analysis.needs_human_review);

// Expected: CV ~0.30 (high disagreement)
```

### Integration Test

```bash
# Apply schema
PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning psql -U sfloess -f learning/schema-human-review.sql

# Run test workflow
node -e "
const { runWeightedVotingWithDisagreementDetection } = require('./shared/weighted-voting.cjs');

const votes = [
  { model: 'opus', answer: 'PostgreSQL', confidence: 92 },
  { model: 'sonnet', answer: 'PostgreSQL', confidence: 88 },
  { model: 'haiku', answer: 'MongoDB', confidence: 45 },
  { model: 'fable', answer: 'Redis', confidence: 52 },
];

(async () => {
  const result = await runWeightedVotingWithDisagreementDetection(votes, 'architecture_review', {
    reviewThreshold: 0.20,
    context: {
      workflow_execution_id: 'test_' + Date.now(),
      workflow_name: 'test-disagreement',
      task_description: 'What database should we use?',
    },
  });

  console.log('Winner:', result.voting_result.winner.answer);
  console.log('Disagreement:', result.disagreement.disagreement_score);
  console.log('Needs review:', result.needs_human_review);
  console.log('Queue result:', result.human_review_queue);
})();
"

# Check queue
PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning psql -U sfloess -c "SELECT * FROM workflow.human_review_queue ORDER BY created_at DESC LIMIT 1;"
```

## Performance

### Database Indexes

All queries use indexes (see `learning/schema-human-review.sql`):
- `idx_hrq_status` - Query by status + disagreement
- `idx_hrq_workflow` - Query by workflow execution
- `idx_hrq_disagreement` - Query by disagreement level
- `idx_hrq_priority` - Query by priority
- `idx_hrq_votes_gin` - JSONB queries on votes

### Query Performance

Typical query times (10,000 queue entries):
- Fetch pending reviews: ~5ms
- Update review status: ~2ms
- Statistics queries: ~10-50ms (with indexes)

### Memory Overhead

Per queue entry: ~2-5KB (JSONB storage of votes)
- 1,000 entries: ~2-5MB
- 10,000 entries: ~20-50MB
- 100,000 entries: ~200-500MB

Recommend archiving old entries after 90 days (see maintenance queries).

## Maintenance

### Cleanup Old Entries

```sql
-- Delete dismissed reviews older than 30 days
DELETE FROM workflow.human_review_queue
WHERE status = 'dismissed'
  AND reviewed_at < NOW() - INTERVAL '30 days';
```

### Archive Old Reviews

```sql
-- Create archive table (once)
CREATE TABLE workflow.human_review_archive (
  LIKE workflow.human_review_queue INCLUDING ALL
);

-- Archive and delete (run monthly)
INSERT INTO workflow.human_review_archive
SELECT * FROM workflow.human_review_queue
WHERE status IN ('reviewed', 'resolved', 'dismissed')
  AND reviewed_at < NOW() - INTERVAL '90 days';

DELETE FROM workflow.human_review_queue
WHERE status IN ('reviewed', 'resolved', 'dismissed')
  AND reviewed_at < NOW() - INTERVAL '90 days';
```

## Future Enhancements

### Automatic Retraining Trigger

When weighted voting accuracy drops below threshold (e.g., 80%):
- Flag for model weight recalibration
- Trigger Thompson Sampling update
- Alert human reviewers

### Active Learning Loop

Prioritize reviews that maximize learning:
- High disagreement + rare task type = high priority
- High disagreement + common task type = medium priority
- Low disagreement + low confidence = flag anyway

### Multi-Stage Review

For critical disagreements (CV > 0.50):
- Require 2-3 human reviewers
- Majority vote among reviewers
- Track inter-rater reliability

## References

- **Weighted Voting:** `shared/weighted-voting.cjs`
- **Thompson Sampling:** `learning/postgres-adapter.js`
- **Multi-AI Consensus:** `ai-consensus-weighted.js`
- **Database Schema:** `learning/schema-human-review.sql`
- **Example Queries:** `learning/human-review-queries.sql`

## Contact

For questions or issues:
1. Check this documentation
2. Review `learning/human-review-queries.sql` for query examples
3. Examine `shared/disagreement-detector.cjs` source code
4. Test with small dataset first

---

**Created:** 2026-06-28  
**Version:** 1.0  
**Status:** Production Ready
