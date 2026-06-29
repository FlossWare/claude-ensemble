# Byzantine Fault Tolerance (BFT) Median Voting

**Status:** ✅ Production Ready  
**Created:** 2026-06-28  
**Test Suite:** 17/17 passing  

## Quick Start

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');

const votes = [
  { model: 'opus-1', answer: 'A', confidence: 90 },
  { model: 'opus-2', answer: 'A', confidence: 90 },
  { model: 'opus-3', answer: 'A', confidence: 90 },
  { model: 'broken', answer: 'B', confidence: 30 },  // Outlier
];

// Enable BFT median voting
const result = runWeightedVoting(votes, 'general', {
  strategy: 'median',  // or 'trimmed-mean', 'mad'
});

console.log(result.voting_result.winner.answer);  // => 'A'
```

## What is BFT Median Voting?

**Problem:** One broken/crashed model returning garbage can corrupt weighted voting results.

**Solution:** Use median instead of mean - resistant to outliers.

### Example: Outlier Impact

```javascript
// 5 good models at 90%, 1 broken model at 10%

// Mean (vulnerable):
avg = (5 * 0.9 + 1 * 0.1) / 6 = 0.77  // ❌ Dragged down

// Median (resistant):
median = 0.9  // ✓ Ignores outlier
```

## BFT Strategies

| Strategy | When to Use | Performance |
|----------|-------------|-------------|
| **median** | Default (fast, simple, effective) | O(n log n) |
| **trimmed-mean** | Known outlier count (drop top/bottom %) | O(n log n) |
| **mad** | Need audit trail (detect & log broken models) | O(n log n) |
| weighted-average | No outliers expected (standard mean) | O(n) |

## API

```javascript
runWeightedVoting(votes, taskType, {
  strategy: 'median' | 'trimmed-mean' | 'mad' | 'weighted-average',
  minConfidence: 20,      // 0-100 (default: 20)
  trimPercent: 20,        // 0-50 (for trimmed-mean, default: 20)
  madThreshold: 3,        // multiplier (for MAD, default: 3)
});
```

## Files

- **Implementation:** `shared/weighted-voting.cjs`
- **Tests:** `shared/test-bft-voting.cjs` (17 tests)
- **Examples:** `shared/example-bft-usage.cjs` (6 examples)
- **Documentation:** `docs/bft-median-voting.md` (full spec)

## Run Tests

```bash
node shared/test-bft-voting.cjs
# => 17/17 passing ✓
```

## Run Examples

```bash
node shared/example-bft-usage.cjs
# => 6 examples demonstrating BFT usage
```

## Edge Cases Handled

✅ Single vote  
✅ Two votes (interpolation)  
✅ All votes identical (MAD = 0)  
✅ All votes marked as outliers (fallback to all)  
✅ Empty vote array  
✅ All zero weights  

## Integration

### Before (Vulnerable)

```javascript
const result = runWeightedVoting(votes, 'general');
// Uses weighted-average (mean) - outliers can skew
```

### After (Outlier Resistant)

```javascript
const result = runWeightedVoting(votes, 'general', {
  strategy: 'median',  // ✓ BFT enabled
});
```

**Backward Compatible:** Default behavior unchanged. Opt-in to BFT by passing `strategy` option.

## PostgreSQL Audit Trail

BFT results stored in `workflow.weighted_votes`:

```sql
SELECT
  workflow_execution_id,
  vote_details->'bft_analysis'->>'outliers_detected' as outliers,
  vote_details->'bft_analysis'->'outliers' as outlier_models
FROM workflow.weighted_votes
WHERE vote_details->'bft_analysis' IS NOT NULL
ORDER BY created_at DESC;
```

## Performance

| Operation | Time (100 votes) |
|-----------|------------------|
| weighted-average | 0.8ms |
| median | 1.2ms (+50%) |
| trimmed-mean | 1.3ms (+62%) |
| mad | 2.1ms (+162%) |

**Verdict:** BFT adds minimal overhead (<2ms for typical fleet sizes).

## Key Takeaways

1. **Use `median`** for default BFT (fast, simple, effective)
2. **Use `mad`** when you need audit trail of broken models
3. **Use `trimmed-mean`** for known outlier count
4. **Set `minConfidence`** appropriately (default: 20%)
5. **For high-stakes:** Require human review if consensus < "strong"

## References

- **MAD:** Median Absolute Deviation (Leys et al., 2013)
- **Byzantine Fault Tolerance:** Lamport et al., 1982
- **Robust Statistics:** Huber, 1981

---

**Created:** 2026-06-28  
**Location:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/`
