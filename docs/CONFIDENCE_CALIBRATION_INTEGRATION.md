# Confidence Calibration Integration Guide

**Issue:** #264  
**Created:** 2026-07-01  
**Status:** Integration Complete

## Overview

The confidence calibration system tracks model confidence vs. actual accuracy to detect "lying" models (overconfident) and "sandbagging" models (underconfident). This guide documents how to integrate calibration into your workflows.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Workflow Execution                                             │
│  ├─ Workers report confidence (0-100%)                         │
│  ├─ Arbiter/Quality Scorer determines actual outcome           │
│  └─ Integration Helper records observation                     │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Confidence Calibration Storage (PostgreSQL)                   │
│  workflow.confidence_calibration                               │
│  ├─ model: TEXT                                               │
│  ├─ reported_confidence: NUMERIC (0.0-1.0)                    │
│  ├─ actual_outcome: NUMERIC (0.0 or 1.0)                      │
│  ├─ task_type: TEXT                                           │
│  └─ workflow_execution_id: TEXT                               │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Weighted Voting (weighted-voting.cjs)                         │
│  ├─ Loads calibration stats for all models                    │
│  ├─ Calculates calibration penalty (0.25-1.0×)                │
│  └─ Applies penalty to vote weights                           │
└─────────────────────────────────────────────────────────────────┘
```

## Files

### Core Calibration System

- **`shared/confidence-calibration.cjs`** (10K)
  - Core calibration logic
  - `storeObservation()` - Record observations
  - `getCalibrationStats()` - Get model stats
  - `getCalibrationPenalty()` - Calculate penalty multiplier

### Integration Helper (NEW)

- **`shared/confidence-calibration-integration.cjs`** (7K)
  - High-level integration functions
  - `recordArbiterOutcome()` - Record after arbiter decision
  - `recordQualityOutcome()` - Record after quality scoring
  - `recordVotingOutcome()` - Record after weighted voting
  - `recordObservation()` - Manual recording

### Already Integrated

- **`shared/weighted-voting.cjs`** (lines 630-641)
  - Loads calibration penalties for all models
  - Applies penalties during vote weight calculation
  - No changes needed

## Integration Points

### 1. After Arbiter Decision

**When:** Arbiter selects which worker's answer to use

**How:**

```javascript
const { recordArbiterOutcome } = require('./shared/confidence-calibration-integration.cjs');

// Workers execute
const workers = [
  { worker_id: 'w1', model: 'opus', confidence: 0.9, answer: 'A' },
  { worker_id: 'w2', model: 'sonnet', confidence: 0.7, answer: 'B' },
  { worker_id: 'w3', model: 'haiku', confidence: 0.5, answer: 'A' },
];

// Arbiter decides
const arbiterDecision = {
  selected_answer: 'A',
  reasoning: 'Answer A has stronger evidence',
};

// Record observations (opus=correct, sonnet=incorrect, haiku=correct)
await recordArbiterOutcome(
  workers,
  arbiterDecision,
  'code_review', // task type
  workflowExecutionId
);
```

**Result:**
- opus: reported=0.9, actual=1.0 (correct)
- sonnet: reported=0.7, actual=0.0 (incorrect)
- haiku: reported=0.5, actual=1.0 (correct)

### 2. After Quality Scoring

**When:** Quality scorer evaluates code/output

**How:**

```javascript
const { recordQualityOutcome } = require('./shared/confidence-calibration-integration.cjs');
const { calculateQualityScore } = require('./shared/quality-scorer.js');

// Worker generates code
const workerResult = {
  model: 'deepseek-coder',
  confidence: 0.85,
  code: '...',
};

// Quality scorer evaluates
const issues = findIssues(workerResult.code);
const qualityScore = calculateQualityScore(issues);

// Record observation
// qualityScore.score >= 80 → actual_outcome=1.0 (correct)
// qualityScore.score < 80 → actual_outcome=0.0 (incorrect)
await recordQualityOutcome(
  workerResult.model,
  workerResult.confidence,
  qualityScore.score,
  'code_generation',
  workflowExecutionId,
  80 // quality threshold (optional, default: 80)
);
```

**Result:**
- If quality=95: reported=0.85, actual=1.0 (correct)
- If quality=65: reported=0.85, actual=0.0 (incorrect)

### 3. After Weighted Voting

**When:** Weighted voting selects winner

**How:**

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');
const { recordVotingOutcome } = require('./shared/confidence-calibration-integration.cjs');

// Collect votes
const votes = [
  { model: 'opus', answer: 'A', confidence: 0.9 },
  { model: 'sonnet', answer: 'A', confidence: 0.85 },
  { model: 'haiku', answer: 'B', confidence: 0.6 },
];

// Run weighted voting
const result = await runWeightedVoting(votes, 'security_audit');

// Record observations (winner=correct, losers=incorrect)
await recordVotingOutcome(
  result.voting_result,
  'security_audit',
  workflowExecutionId
);
```

**Result:**
- Winner group (A): opus/sonnet reported confidence → actual=1.0
- Loser group (B): haiku reported confidence → actual=0.0

### 4. Manual Recording (Custom Integrations)

**When:** Custom workflow with different outcome determination

**How:**

```javascript
const { recordObservation } = require('./shared/confidence-calibration-integration.cjs');

// Worker executes task
const worker = { model: 'mistral-7b', confidence: 0.75 };

// You determine outcome via custom logic
const isCorrect = customValidation(worker.result);
const actualOutcome = isCorrect ? 1.0 : 0.0;

// Record manually
await recordObservation(
  worker.model,
  worker.confidence,
  actualOutcome,
  'custom_task',
  workflowExecutionId
);
```

## Integration Checklist

### Files That Need Integration

Run this query to find integration points:

```bash
# Find files that determine outcomes (arbiter/quality/consensus)
grep -r "arbiter.*decision\|quality.*score\|consensus.*winner" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/
```

### Recommended Integration Order

1. **High Priority** (Most observations, immediate impact)
   - [ ] `shared/workflow-completion-hook.js` (lines 80-95)
     - Add `recordArbiterOutcome()` after arbiter storage
   - [ ] Any file using `weighted-voting.cjs`
     - Add `recordVotingOutcome()` after `runWeightedVoting()`

2. **Medium Priority** (Quality-based workflows)
   - [ ] `workflows/` files using `quality-scorer.js`
     - Add `recordQualityOutcome()` after quality calculation

3. **Low Priority** (Custom workflows)
   - [ ] Custom workflows with manual outcome determination
     - Add `recordObservation()` where outcome is known

## Calibration Penalty Application

Calibration penalties are **automatically applied** in `weighted-voting.cjs` (lines 630-641):

```javascript
// No changes needed - already integrated!
const calibrationPenalties = {};
for (const model of uniqueModels) {
  calibrationPenalties[model] = await getCalibrationPenalty(model, taskType);
}

// Applied during weight calculation (line 299)
const weight = tierWeight * capabilityScore * confidence * historicalAccuracy * calibrationPenalty;
```

### Penalty Tiers

- **Well-calibrated** (<10% error): 1.0× (no penalty)
- **Minor error** (10-20%): 0.75× penalty
- **Major error** (20-30%): 0.50× penalty
- **Critical error** (>30%): 0.25× penalty

### Minimum Observations

Calibration requires **5+ observations** before penalties activate (prevents small-sample bias).

## Database Schema

**Table:** `workflow.confidence_calibration`

```sql
CREATE TABLE workflow.confidence_calibration (
  id SERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  reported_confidence NUMERIC NOT NULL,  -- 0.0-1.0
  actual_outcome NUMERIC NOT NULL,       -- 0.0 (wrong) or 1.0 (correct)
  task_type TEXT,
  workflow_execution_id TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Query calibration stats:**

```sql
SELECT
  model,
  AVG(reported_confidence) as avg_reported,
  AVG(actual_outcome) as avg_actual,
  ABS(AVG(reported_confidence) - AVG(actual_outcome)) as calibration_error,
  COUNT(*) as num_observations
FROM workflow.confidence_calibration
WHERE task_type = 'code_review'
GROUP BY model
ORDER BY calibration_error DESC;
```

## Testing

**Test file:** `shared/test-bft-protections.cjs`

Run calibration tests:

```bash
cd shared/
node test-bft-protections.cjs
```

**Tests:**
- Detect overconfident models (90% confidence, 50% accuracy → 0.25× penalty)
- Detect underconfident models (50% confidence, 85% accuracy → 0.25× penalty)
- Well-calibrated models (80% confidence, 80% accuracy → 1.0× no penalty)

## Monitoring

### View Calibration Stats

```bash
# PostgreSQL query
psql -h laptop-01 -U sfloess -d learning -c "
  SELECT
    model,
    ROUND(AVG(reported_confidence)::numeric, 2) as avg_reported,
    ROUND(AVG(actual_outcome)::numeric, 2) as avg_actual,
    ROUND(ABS(AVG(reported_confidence) - AVG(actual_outcome))::numeric, 2) as error,
    COUNT(*) as observations
  FROM workflow.confidence_calibration
  GROUP BY model
  ORDER BY error DESC;
"
```

### Check Penalties

```javascript
const { getCalibrationPenalty } = require('./shared/confidence-calibration.cjs');

const penalty = await getCalibrationPenalty('opus', 'code_review');
console.log(`Penalty: ${penalty.penalty}× (${penalty.reason})`);
console.log(`Stats:`, penalty.stats);
```

## Example Integration

**Before:**

```javascript
// Arbiter decides
const arbiterResult = await agent(buildArbiterPrompt(workers));

// Store to database
await storage.storeArbiterDecision({
  workflow_execution_id: execId,
  decision: arbiterResult.selected_answer,
  // ...
});
```

**After (1 line added):**

```javascript
const { recordArbiterOutcome } = require('./shared/confidence-calibration-integration.cjs');

// Arbiter decides
const arbiterResult = await agent(buildArbiterPrompt(workers));

// Store to database
await storage.storeArbiterDecision({
  workflow_execution_id: execId,
  decision: arbiterResult.selected_answer,
  // ...
});

// ✅ NEW: Record confidence observations
await recordArbiterOutcome(workers, arbiterResult, taskType, execId);
```

## Next Steps

1. **Identify integration points** in your workflows
2. **Add 1-line integration** using helper functions
3. **Run workflows** to collect observations
4. **Monitor calibration stats** in PostgreSQL
5. **Weighted voting** automatically applies penalties (no action needed)

## Troubleshooting

### No penalties applied despite observations

- Check observation count: `SELECT COUNT(*) FROM workflow.confidence_calibration WHERE model = 'opus';`
- Minimum 5 observations required before penalties activate

### Observations not storing

- Check PostgreSQL connection: `psql -h laptop-01 -U sfloess -d learning -c "SELECT 1;"`
- Check local cache fallback: `~/.claude/learning/confidence-calibration-cache.json`

### Penalties too aggressive

- Adjust thresholds in `confidence-calibration.cjs` (lines 33-38)
- Increase `MIN_OBSERVATIONS` (default: 5)

## References

- **Core System:** `shared/confidence-calibration.cjs`
- **Integration Helper:** `shared/confidence-calibration-integration.cjs`
- **Tests:** `shared/test-bft-protections.cjs`
- **Weighted Voting:** `shared/weighted-voting.cjs` (lines 630-641, 686-699)
- **Issue:** #264
