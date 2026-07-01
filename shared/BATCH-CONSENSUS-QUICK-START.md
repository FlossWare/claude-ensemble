# Batch Consensus - Quick Start Guide

**File:** `shared/batch-consensus.cjs`  
**Wrapper:** `shared/batch-consensus-wrapper.mjs` (ESM)  
**Status:** Integrated ✓ (Issue #263)

## When to Use

Use batch consensus when you have **multiple questions/tasks** that need consensus voting:
- ✅ Verifying 10+ claims in a research workflow
- ✅ Evaluating multiple code changes
- ✅ Processing survey responses
- ✅ Any scenario with N > 5 similar consensus operations

**Don't use for:**
- ✗ Single consensus call (use `weighted-voting.cjs` directly)
- ✗ Already parallelized with `parallel()` (no benefit)

## Basic Usage (3 lines)

```javascript
import { batchConsensusWithWorker } from './shared/batch-consensus-wrapper.mjs';

// 1. Prepare questions
const questions = ['Question 1', 'Question 2', 'Question 3'];

// 2. Define worker (how to get consensus for ONE question)
const worker = async (question) => {
  // Your consensus logic here (3-vote, weighted voting, etc.)
  return {
    model: 'consensus',
    answer: 'result',
    confidence: 0.85
  };
};

// 3. Process batch
const results = await batchConsensusWithWorker(questions, worker, {
  concurrency: 5,  // Max 5 questions at once
  onProgress: (completed, total) => console.log(`${completed}/${total}`)
});
```

## Options

```javascript
{
  concurrency: 5,              // Max parallel operations (default: 10)
  onProgress: (c, t) => {},    // Progress callback
  onError: (err, q, i) => {},  // Error callback
  stopOnError: false,          // Stop entire batch on first error
  retryFailed: false,          // Retry failed items once
  timeout: 30000,              // Per-item timeout (ms)
}
```

## Real Example (deep-research.mjs)

```javascript
// Verify 20 claims with 3-vote consensus each
const claimQuestions = allClaims.map(({ claim, source }) => ({
  text: `Verify: "${claim}"`,
  claim,
  source
}));

const verifyWorker = async (question) => {
  // 3 voters per claim
  const votes = await Promise.all([
    runAgent(question.text, 'opus'),
    runAgent(question.text, 'sonnet'),
    runAgent(question.text, 'haiku')
  ]);

  // Calculate consensus (2/3 majority)
  const refuteCount = votes.filter(v => v.verdict === 'REFUTE').length;
  
  return {
    model: 'consensus-3vote',
    answer: {
      claim: question.claim,
      accepted: refuteCount < 2,
      votes
    },
    confidence: avgConfidence(votes)
  };
};

const results = await batchConsensusWithWorker(
  claimQuestions,
  verifyWorker,
  {
    concurrency: 5,  // 5 claims × 3 models = 15 parallel agents
    onProgress: (completed, total) => {
      console.log(`Progress: ${completed}/${total} claims verified`);
    }
  }
);
```

## Performance

| Metric | Without Batch | With Batch |
|--------|--------------|------------|
| Concurrency | Unbounded | Controlled (10 default) |
| Progress Tracking | No | Yes (callback) |
| Cache Integration | Manual | Automatic |
| Rate Limiting | Risk | Protected |
| Typical Speedup | - | 30-40% (with cache) |

## Error Handling

```javascript
const results = await batchConsensusWithWorker(questions, worker, {
  onError: (error, question, index) => {
    console.error(`Failed question ${index}:`, error.message);
    // Log to database, send alert, etc.
  },
  stopOnError: false  // Continue processing other questions
});

// Check results
const successful = results.filter(r => !r.error);
const failed = results.filter(r => r.error);

console.log(`Success: ${successful.length}, Failed: ${failed.length}`);
```

## Cache Integration

Batch consensus automatically integrates with `consensus-cache.cjs`:
- Cache lookup before processing
- Cache store after successful consensus
- ~30% hit rate for similar topics
- 0.4ms cache hits vs ~5s computation

No configuration needed - just works! ✓

## Testing

```bash
# Run integration tests
node shared/test-batch-consensus-integration.mjs

# Expected output:
# Test 1: Basic batch processing ............ PASSED ✓
# Test 2: Error handling .................... PASSED ✓
# Test 3: Concurrency control ............... PASSED ✓
```

## Common Patterns

### Pattern 1: Verification Workflow
```javascript
const claims = extractClaims(document);
const worker = (claim) => verifyWithMultipleModels(claim);
const results = await batchConsensusWithWorker(claims, worker);
```

### Pattern 2: Evaluation Workflow
```javascript
const codeChanges = getCodeChanges();
const worker = (change) => evaluateQuality(change);
const results = await batchConsensusWithWorker(codeChanges, worker);
```

### Pattern 3: Survey Analysis
```javascript
const responses = getSurveyResponses();
const worker = (response) => classifyResponse(response);
const results = await batchConsensusWithWorker(responses, worker);
```

## Troubleshooting

### Q: "Unexpected end of input" error
A: Check `consensus-cache.cjs` syntax with `node -c shared/consensus-cache.cjs`

### Q: No progress callbacks firing
A: Ensure `onProgress` is a function: `onProgress: (c, t) => console.log(c, t)`

### Q: Hitting rate limits
A: Reduce `concurrency` value (try 3-5 instead of 10)

### Q: Cache not working
A: Check PostgreSQL connection (`psql -h aio-01 -p 5433 -d learning`)

## Files

- `shared/batch-consensus.cjs` - Core implementation (13K)
- `shared/batch-consensus-wrapper.mjs` - ESM wrapper (120 lines)
- `shared/BATCH-CONSENSUS-INTEGRATION.md` - Full guide (250 lines)
- `shared/test-batch-consensus-integration.mjs` - Tests (200 lines)
- `workflows/deep-research.mjs` - Example integration

## Integration Checklist

- [ ] Import wrapper: `import { batchConsensusWithWorker } from ...`
- [ ] Extract questions into array
- [ ] Create worker function
- [ ] Set appropriate concurrency (items × models_per_item)
- [ ] Add progress callback
- [ ] Add error callback
- [ ] Test with small batch (5-10 items)
- [ ] Validate cache hits work
- [ ] Measure performance improvement

## Next Steps

1. **Try it:** Integrate into your workflow
2. **Measure:** Track cache hit rate and performance
3. **Optimize:** Adjust concurrency based on API limits
4. **Share:** Document your use case for others

**Questions?** See full guide: `shared/BATCH-CONSENSUS-INTEGRATION.md`
