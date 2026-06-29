# Confidence Calibration - Detecting Overconfident Models

**Status:** ✅ Production Ready  
**Created:** 2026-06-28  
**Database:** `workflow.confidence_calibration` (PostgreSQL)  

## Quick Start

```javascript
const { storeObservation, getCalibrationPenalty } = require('./shared/confidence-calibration.cjs');

// Record a model's performance
await storeObservation({
  model: 'opus',
  reported_confidence: 0.90,  // Model claimed 90% confidence
  actual_outcome: 0.60,       // But was only 60% correct
  task_type: 'code_review',
  workflow_execution_id: 'wf-123'
});

// Get calibration penalty (automatic in weighted voting)
const { penalty, reason, stats } = await getCalibrationPenalty('opus', 'code_review');
console.log(penalty);  // => 0.50 (50% weight reduction for 30% error)
console.log(reason);   // => "Major calibration error (30.0% > 20%)"
```

## What is Confidence Calibration?

**Problem:** Models can be overconfident (report 90% confidence but only 60% accurate) or underconfident (report 50% but actually 85% accurate). In weighted voting, overconfident models dominate consensus unfairly.

**Solution:** Track reported confidence vs actual accuracy over time. Apply weight penalties to poorly calibrated models.

### Example: Well-Calibrated vs Overconfident

```javascript
// Model A (well-calibrated):
// 10 tasks at 80% confidence → 8 correct, 2 wrong
avg_reported = 0.80
avg_actual   = 0.80  // (8/10)
error        = 0.00  // ✓ No penalty

// Model B (overconfident):
// 10 tasks at 90% confidence → 6 correct, 4 wrong
avg_reported = 0.90
avg_actual   = 0.60  // (6/10)
error        = 0.30  // ❌ 30% error = 0.25× weight penalty
```

## How It Works

1. **Record observations:** Every time a model makes a prediction:
   - Store `(model, reported_confidence, actual_outcome)`
   - `actual_outcome`: 1.0 (correct) or 0.0 (wrong)

2. **Calculate calibration error:**
   ```
   calibration_error = |avg_reported - avg_actual|
   ```

3. **Apply penalty tiers:**
   - `>30%` error → **0.25×** weight (critical)
   - `>20%` error → **0.50×** weight (major)
   - `>10%` error → **0.75×** weight (minor)
   - `<10%` error → **1.00×** weight (no penalty)

4. **Integrate with voting:** `weighted-voting.cjs` automatically calls `getCalibrationPenalty()` and reduces overconfident models' weights.

## API Reference

### `storeObservation(observation)`

Record a calibration observation.

**Parameters:**
```javascript
{
  model: string,                    // Model name (e.g., 'opus', 'sonnet')
  reported_confidence: number,      // 0.0-1.0 (model's self-reported confidence)
  actual_outcome: number,           // 0.0 (wrong) or 1.0 (correct)
  task_type: string,                // Optional: 'code_review', 'research', etc.
  workflow_execution_id: string     // Optional: workflow tracking ID
}
```

**Returns:** `Promise<void>`

**Storage:**
- Primary: PostgreSQL `workflow.confidence_calibration` table
- Fallback: `~/.claude/learning/confidence-calibration-cache.json`

---

### `getCalibrationStats(model, taskType)`

Get calibration statistics for a model.

**Parameters:**
- `model` (string): Model name
- `taskType` (string, optional): Filter by task type

**Returns:** `Promise<Object>`
```javascript
{
  avg_reported: number,       // Average reported confidence
  avg_actual: number,         // Average actual accuracy
  calibration_error: number,  // |avg_reported - avg_actual|
  num_observations: number    // Total observations
}
```

**Example:**
```javascript
const stats = await getCalibrationStats('opus', 'code_review');
console.log(stats);
// {
//   avg_reported: 0.85,
//   avg_actual: 0.62,
//   calibration_error: 0.23,
//   num_observations: 47
// }
```

---

### `getCalibrationPenalty(model, taskType)`

Calculate weight penalty for a model.

**Parameters:**
- `model` (string): Model name
- `taskType` (string, optional): Filter by task type

**Returns:** `Promise<Object>`
```javascript
{
  penalty: number,    // 0.25, 0.50, 0.75, or 1.0
  reason: string,     // Human-readable explanation
  stats: Object       // Full calibration stats (from getCalibrationStats)
}
```

**Penalty Tiers:**
| Error Range | Penalty | Multiplier |
|-------------|---------|------------|
| `>30%` | Critical | 0.25× |
| `20-30%` | Major | 0.50× |
| `10-20%` | Minor | 0.75× |
| `<10%` | None | 1.00× |

**Minimum Observations:**
- Requires **5+ observations** before penalties apply
- Prevents small-sample bias (e.g., 1 wrong answer = 100% error)

**Example:**
```javascript
const { penalty, reason, stats } = await getCalibrationPenalty('opus');
console.log(penalty);  // => 0.50
console.log(reason);   // => "Major calibration error (23.0% > 20%)"
```

## Integration with Weighted Voting

Calibration penalties are **automatically applied** by `weighted-voting.cjs`:

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');

const votes = [
  { model: 'opus', answer: 'A', confidence: 90 },     // Overconfident (penalty: 0.5×)
  { model: 'sonnet', answer: 'B', confidence: 70 },   // Well-calibrated (penalty: 1.0×)
  { model: 'haiku', answer: 'A', confidence: 60 },    // Well-calibrated (penalty: 1.0×)
];

// Calibration penalties auto-applied during weight calculation
const result = await runWeightedVoting(votes, 'code_review');

// Effective weights:
// opus:   90 × 0.5 = 45  (overconfident, reduced)
// sonnet: 70 × 1.0 = 70  (well-calibrated, full weight)
// haiku:  60 × 1.0 = 60  (well-calibrated, full weight)
//
// Winner: sonnet (B) - despite opus having higher confidence
```

## When to Use

### Automatic Usage (Recommended)
- **Weighted voting workflows:** Calibration is integrated by default
- **No manual intervention needed:** Just call `runWeightedVoting()` normally
- **Online learning:** Every vote automatically updates calibration stats

### Manual Usage (Advanced)
```javascript
// After evaluating a model's answer manually
const correct = validateAnswer(model_answer);
await storeObservation({
  model: 'opus',
  reported_confidence: 0.85,
  actual_outcome: correct ? 1.0 : 0.0,
  task_type: 'custom_evaluation'
});
```

### Monitoring (Detect Poorly Calibrated Models)
```bash
# Query poorly calibrated models
psql -h laptop-01 -U sfloess -d learning -c "
  SELECT 
    model,
    AVG(reported_confidence) as avg_reported,
    AVG(actual_outcome) as avg_actual,
    ABS(AVG(reported_confidence) - AVG(actual_outcome)) as error,
    COUNT(*) as observations
  FROM workflow.confidence_calibration
  GROUP BY model
  HAVING ABS(AVG(reported_confidence) - AVG(actual_outcome)) > 0.20
  ORDER BY error DESC;
"
```

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

-- Indexes
CREATE INDEX idx_confidence_model ON workflow.confidence_calibration(model);
CREATE INDEX idx_confidence_task_type ON workflow.confidence_calibration(task_type);
CREATE INDEX idx_confidence_created_at ON workflow.confidence_calibration(created_at);
```

**Storage Locations:**
- **Primary:** PostgreSQL on `laptop-01` (database `learning`)
- **Fallback:** `~/.claude/learning/confidence-calibration-cache.json`

## Configuration

**Constants (in `confidence-calibration.cjs`):**

```javascript
const CALIBRATION_THRESHOLDS = {
  CRITICAL: 0.30,  // >30% error = 0.25× weight
  MAJOR: 0.20,     // >20% error = 0.50× weight
  MINOR: 0.10,     // >10% error = 0.75× weight
};

const MIN_OBSERVATIONS = 5;  // Minimum observations before penalties apply
```

**To customize:**
1. Edit thresholds in `shared/confidence-calibration.cjs`
2. Adjust `MIN_OBSERVATIONS` if you want stricter/looser requirements
3. Restart workflows using calibration

## Real-World Example

### Scenario: Code Review Workflow

```javascript
// 3 models review code for bugs
const reviews = [
  { model: 'opus', answer: 'no_bugs', confidence: 95 },
  { model: 'sonnet', answer: 'bug_found', confidence: 70 },
  { model: 'haiku', answer: 'no_bugs', confidence: 80 },
];

// Historical calibration (from previous reviews):
// - opus: 95% confidence, 60% actual accuracy (35% error) → 0.25× penalty
// - sonnet: 70% confidence, 72% actual accuracy (2% error) → 1.0× penalty
// - haiku: 80% confidence, 75% actual accuracy (5% error) → 1.0× penalty

const result = await runWeightedVoting(reviews, 'code_review');

// Effective weights:
// opus:   95 × 0.25 = 23.75  (overconfident, heavily penalized)
// sonnet: 70 × 1.00 = 70.00  (well-calibrated, full weight)
// haiku:  80 × 1.00 = 80.00  (well-calibrated, full weight)
//
// Weighted scores:
// no_bugs:   23.75 + 80.00 = 103.75
// bug_found: 70.00
//
// Winner: no_bugs (BUT sonnet's high-quality signal still visible in logs)
//
// Human then validates: Actually a bug!
// Update calibration:
await storeObservation({
  model: 'sonnet',
  reported_confidence: 0.70,
  actual_outcome: 1.0,  // Correct!
  task_type: 'code_review'
});
await storeObservation({
  model: 'opus',
  reported_confidence: 0.95,
  actual_outcome: 0.0,  // Wrong again
  task_type: 'code_review'
});
await storeObservation({
  model: 'haiku',
  reported_confidence: 0.80,
  actual_outcome: 0.0,  // Wrong
  task_type: 'code_review'
});

// Next review: opus penalty worsens, sonnet improves
```

## Why This Matters

### Without Calibration
```
❌ Overconfident weak models dominate consensus
❌ "Loudest voice wins" problem
❌ No correction mechanism for bad confidence estimates
```

### With Calibration
```
✓ Accurate models gain influence over time
✓ Overconfident models auto-penalized
✓ Self-correcting system via online learning
✓ Improved consensus quality (fewer false positives/negatives)
```

## Common Patterns

### Pattern 1: Sandbagging Detection
```javascript
// Model consistently underestimates confidence
// (reports 50% but is 85% accurate)
const stats = await getCalibrationStats('conservative_model');
if (stats.avg_actual > stats.avg_reported + 0.20) {
  console.log('Model is sandbagging - boost its weight manually');
}
```

### Pattern 2: Task-Specific Calibration
```javascript
// Model might be well-calibrated for code review but not research
const codeReviewPenalty = await getCalibrationPenalty('opus', 'code_review');
const researchPenalty = await getCalibrationPenalty('opus', 'research');

console.log(codeReviewPenalty.penalty);  // => 1.0 (well-calibrated)
console.log(researchPenalty.penalty);    // => 0.5 (overconfident)
```

### Pattern 3: Model Debugging
```javascript
// Investigate why a model is penalized
const { stats } = await getCalibrationPenalty('opus');
console.log(`
  Model: opus
  Avg Reported: ${(stats.avg_reported * 100).toFixed(1)}%
  Avg Actual:   ${(stats.avg_actual * 100).toFixed(1)}%
  Error:        ${(stats.calibration_error * 100).toFixed(1)}%
  Observations: ${stats.num_observations}
`);
```

## Files

- **Implementation:** `shared/confidence-calibration.cjs`
- **Integration:** `shared/weighted-voting.cjs` (auto-applies penalties)
- **Database:** `workflow.confidence_calibration` (PostgreSQL)
- **Fallback:** `~/.claude/learning/confidence-calibration-cache.json`

## Troubleshooting

### Problem: Penalties not applying

**Check 1:** Enough observations?
```javascript
const stats = await getCalibrationStats('opus');
console.log(stats.num_observations);  // Need >= 5
```

**Check 2:** PostgreSQL connection?
```bash
psql -h laptop-01 -U sfloess -d learning -c "\dt workflow.*"
# Should show confidence_calibration table
```

**Check 3:** Using weighted voting?
```javascript
// Calibration only applies in weighted voting (not simple majority)
runWeightedVoting(votes, taskType, { strategy: 'weighted-average' });
```

---

### Problem: Model always penalized

**Check:** Is model actually poorly calibrated?
```javascript
const stats = await getCalibrationStats('opus');
console.log({
  reported: (stats.avg_reported * 100).toFixed(1) + '%',
  actual:   (stats.avg_actual * 100).toFixed(1) + '%',
  error:    (stats.calibration_error * 100).toFixed(1) + '%'
});
```

**Fix:** If model is legitimately overconfident, penalty is working correctly. Options:
1. Accept penalty (model needs better confidence estimation)
2. Manually boost weight as override (not recommended)
3. Train model to output calibrated probabilities

---

### Problem: Fallback to local cache

**Cause:** PostgreSQL unavailable
```bash
# Check connection
psql -h laptop-01 -U sfloess -d learning -c "SELECT 1"
```

**Impact:** Calibration still works, but:
- Slower (file I/O vs database)
- No multi-worker coordination (each worker has separate cache)
- No centralized monitoring (can't query across workflows)

**Fix:** Ensure PostgreSQL running on `laptop-01`:
```bash
ssh laptop-01 'systemctl status postgresql'
```

## Related Systems

- **Weighted Voting:** `shared/weighted-voting.cjs` (auto-applies calibration)
- **BFT Median Voting:** `shared/BFT-README.md` (outlier resistance)
- **Workflow Storage:** `shared/workflow-storage-adapter.cjs` (tracks outcomes)
- **Disagreement Detection:** `shared/DISAGREEMENT-DETECTION-README.md` (find learning opportunities)

## References

- **Original Research:** Platt Scaling, Isotonic Regression (confidence calibration methods)
- **Implementation:** Online learning (incremental updates, no batch retraining)
- **Database:** PostgreSQL + pgvector (0.4ms similarity search)

---

**Next Steps:**
1. Run workflows with weighted voting (calibration auto-enabled)
2. Monitor `workflow.confidence_calibration` table for patterns
3. Investigate poorly calibrated models via `getCalibrationStats()`
4. Adjust `CALIBRATION_THRESHOLDS` if needed (after 100+ observations)
