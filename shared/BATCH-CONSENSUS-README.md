# Batch Consensus API

**Process arrays of questions/tasks using multi-AI consensus with parallel execution, progress tracking, and intelligent caching.**

## Quick Start

```javascript
const { batchConsensus } = require('./shared/batch-consensus.cjs');

// Process 100 questions in one call
const results = await batchConsensus(questions, {
  concurrency: 10,
  taskType: 'research',
  onProgress: (completed, total) => console.log(`${completed}/${total}`),
});

console.log(`Processed ${results.length} questions`);
console.log(`Average confidence: ${results.reduce((s, r) => s + r.confidence, 0) / results.length}`);
```

## Features

- **Parallel Execution**: Process up to 10 questions concurrently (configurable)
- **Progress Tracking**: Real-time callbacks for long-running batches
- **Intelligent Caching**: Avoid duplicate work via consensus cache
- **Graceful Error Handling**: Partial results returned on failures
- **Streaming API**: Memory-efficient processing for large datasets
- **Task-Aware Weighting**: Uses capability matrix for optimal model selection
- **Statistics & Reporting**: Comprehensive analytics on batch results

## API Reference

### `batchConsensus(questions, options)`

Process an array of questions with consensus voting.

**Parameters:**

- `questions` (Array<string>): Array of questions or prompts
- `options` (Object): Configuration options

**Options:**

```javascript
{
  concurrency: 10,           // Max parallel operations (default: 10)
  taskType: 'general',       // Task type for capability weighting
  workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'],
  minAgreement: 0.6,         // Min agreement threshold (0.0-1.0)
  useCache: true,            // Enable consensus cache (default: true)
  onProgress: null,          // Progress callback: (completed, total, current) => void
  onError: null,             // Error callback: (error, question, index) => void
  stopOnError: false,        // Stop entire batch on first error
  retryFailed: false,        // Retry failed items once
  timeout: 30000,            // Per-item timeout in ms
}
```

**Returns:** `Promise<Array<Object>>`

```javascript
[
  {
    question: "What is 2+2?",
    answer: "4",
    confidence: 0.95,
    agreement: 0.89,
    votes: { "4": 5, "four": 1 },
    models: ["opus", "sonnet", "haiku", "gpt-4o", "gemini", "fable"],
    weights: { "opus": 1.0, "sonnet": 0.85, ... },
    cached: false,
    outcome: "success",
    timestamp: "2026-06-28T20:30:00.000Z"
  },
  // ... more results
]
```

**Outcome Types:**

- `"success"`: Agreement >= minAgreement threshold
- `"low_agreement"`: Agreement < minAgreement threshold
- `"error"`: Processing failed (timeout, network error, etc.)

### `batchConsensusStream(questions, options)`

Process questions as a stream for memory-efficient handling of large datasets.

**Parameters:** Same as `batchConsensus`

**Returns:** `AsyncGenerator<Object>` - Yields results as they complete

**Example:**

```javascript
for await (const result of batchConsensusStream(questions, options)) {
  console.log(`${result.question} -> ${result.answer}`);
  // Process result immediately (memory efficient)
}
```

### `analyzeBatchResults(results)`

Generate statistics from batch results.

**Parameters:**

- `results` (Array<Object>): Results from `batchConsensus()`

**Returns:**

```javascript
{
  total: 100,
  successful: 95,
  errors: 3,
  lowAgreement: 2,
  cached: 45,
  cacheHitRate: 0.45,
  successRate: 0.95,
  avgConfidence: 0.87,
  avgAgreement: 0.82,
}
```

### `generateBatchReport(results, options)`

Generate a human-readable report.

**Parameters:**

- `results` (Array<Object>): Results from `batchConsensus()`
- `options` (Object): `{ includeDetails: true }` to show failed questions

**Returns:** String report

**Example Output:**

```
Batch Consensus Report
=====================
Total Questions: 100
Successful: 95 (95.0%)
Errors: 3
Low Agreement: 2
Cache Hits: 45 (45.0%)

Average Confidence: 87.0%
Average Agreement: 82.0%

Failed Questions:
  1. Complex question that timed out
     Error: Timeout
  2. Malformed question
     Error: Invalid input

Low Agreement Questions:
  1. Ambiguous question
     Agreement: 55.0%
```

## Usage Examples

### Example 1: Simple Batch Processing

```javascript
const { batchConsensus } = require('./shared/batch-consensus.cjs');

const questions = [
  'What is the capital of France?',
  'Who wrote Hamlet?',
  'What is 2 + 2?',
  // ... more questions
];

const results = await batchConsensus(questions);

results.forEach(r => {
  console.log(`Q: ${r.question}`);
  console.log(`A: ${r.answer} (${(r.confidence * 100).toFixed(0)}% confidence)`);
});
```

### Example 2: Progress Tracking

```javascript
const results = await batchConsensus(questions, {
  onProgress: (completed, total, current) => {
    const percent = ((completed / total) * 100).toFixed(0);
    console.log(`[${percent}%] ${current.question} -> ${current.answer}`);
  },
});
```

### Example 3: Error Handling

```javascript
const errors = [];

const results = await batchConsensus(questions, {
  stopOnError: false,
  retryFailed: true,
  onError: (error, question, index) => {
    errors.push({ index, question, error: error.message });
    console.error(`Failed: ${question} - ${error.message}`);
  },
});

console.log(`Completed with ${errors.length} errors`);
```

### Example 4: Streaming Large Datasets

```javascript
const { batchConsensusStream } = require('./shared/batch-consensus.cjs');

// Process 10,000 questions without loading all into memory
const largeDataset = await loadQuestions(); // 10,000 questions

for await (const result of batchConsensusStream(largeDataset, {
  concurrency: 20,
})) {
  // Write to database as results arrive
  await db.insert('results', result);
}
```

### Example 5: Cache-Driven Performance

```javascript
// First run: populate cache
const firstRun = await batchConsensus(questions, {
  useCache: true,
  taskType: 'research',
});

// Second run: instant results from cache
const secondRun = await batchConsensus(questions, {
  useCache: true,
  taskType: 'research',
});

const cacheHits = secondRun.filter(r => r.cached).length;
console.log(`Cache hit rate: ${(cacheHits / questions.length * 100).toFixed(0)}%`);
```

### Example 6: Task-Specific Workers

```javascript
// Code generation with specialized models
const codeResults = await batchConsensus(codeQuestions, {
  taskType: 'code_generation',
  workers: ['deepseek-coder', 'opus', 'sonnet', 'codellama'],
});

// Research with general models
const researchResults = await batchConsensus(researchQuestions, {
  taskType: 'research',
  workers: ['opus', 'gpt-4o', 'gemini'],
});
```

### Example 7: Statistics and Reporting

```javascript
const { analyzeBatchResults, generateBatchReport } = require('./shared/batch-consensus.cjs');

const results = await batchConsensus(questions);

// Get statistics
const stats = analyzeBatchResults(results);
console.log(`Success rate: ${(stats.successRate * 100).toFixed(1)}%`);
console.log(`Cache efficiency: ${(stats.cacheHitRate * 100).toFixed(1)}%`);

// Generate report
const report = generateBatchReport(results, { includeDetails: true });
console.log(report);
```

## Performance

### Concurrency Settings

| Dataset Size | Recommended Concurrency | Expected Time (estimate) |
|--------------|-------------------------|--------------------------|
| 1-10         | 5                       | ~1-2 seconds             |
| 10-50        | 10                      | ~3-5 seconds             |
| 50-100       | 10-15                   | ~8-12 seconds            |
| 100-500      | 15-20                   | ~30-60 seconds           |
| 500+         | 20 (use streaming)      | ~2-5 minutes             |

**Note:** Actual times depend on model response latency and task complexity.

### Cache Performance

**Without cache:**
- 100 questions: ~10-15 seconds
- Re-run: ~10-15 seconds

**With cache:**
- 100 questions (first run): ~10-15 seconds
- Re-run: ~0.5-1 second (20-30× faster)

Cache hit rate typically 90%+ for repeated queries.

### Memory Usage

**Regular API:**
- Holds all results in memory
- Memory usage: ~1KB per result
- 1000 results ≈ 1MB

**Streaming API:**
- Processes in chunks
- Memory usage: ~10KB (chunk buffer only)
- Recommended for 500+ questions

## Integration with Existing Systems

### Weighted Voting Integration

Batch consensus automatically uses weighted voting from `weighted-voting.cjs`:

- Model capability scores from capability matrix
- Historical accuracy (Thompson Sampling)
- Task-specific model selection

### Consensus Cache Integration

Batch consensus integrates with `consensus-cache.cjs`:

- Automatic deduplication across batches
- Configurable TTL (Time To Live)
- Task-type aware caching

### PostgreSQL Storage

Results can be stored for analysis:

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.js');
const db = getWorkflowStorage();

const results = await batchConsensus(questions);

for (const result of results) {
  await db.storeLearnings({
    workflow_execution_id: execId,
    description: result.question,
    actionable_insight: result.answer,
    confidence: result.confidence,
    importance: result.agreement,
  });
}
```

## Testing

Run the test suite:

```bash
node shared/test-batch-consensus.cjs
```

**Test Coverage:**

1. ✓ Single question processing
2. ✓ Small batch (10 questions)
3. ✓ Large batch (100 questions)
4. ✓ Progress tracking
5. ✓ Error handling
6. ✓ Cache effectiveness
7. ✓ Streaming API
8. ✓ Statistics and reporting
9. ✓ Mixed task types

Expected output:

```
=============================================================
TEST SUMMARY
=============================================================
Total Tests: 9
Passed: 9 ✓
Failed: 0 ✗
Duration: 5.2s
```

## Best Practices

### 1. Choose Appropriate Concurrency

```javascript
// Good: Balanced concurrency
const results = await batchConsensus(questions, { concurrency: 10 });

// Bad: Too high (may hit rate limits)
const results = await batchConsensus(questions, { concurrency: 100 });

// Bad: Too low (inefficient)
const results = await batchConsensus(questions, { concurrency: 1 });
```

### 2. Always Track Progress

```javascript
// Good: User feedback
const results = await batchConsensus(questions, {
  onProgress: (completed, total) => {
    console.log(`Processing: ${completed}/${total}`);
  },
});

// Bad: No feedback on long operations
const results = await batchConsensus(questions);
```

### 3. Handle Errors Gracefully

```javascript
// Good: Collect errors, continue processing
const errors = [];
const results = await batchConsensus(questions, {
  stopOnError: false,
  onError: (error, question, index) => {
    errors.push({ index, question, error });
  },
});

// Bad: Fail entire batch on one error
const results = await batchConsensus(questions, { stopOnError: true });
```

### 4. Use Streaming for Large Datasets

```javascript
// Good: Memory efficient
for await (const result of batchConsensusStream(largeDataset)) {
  await processResult(result);
}

// Bad: Load all into memory
const results = await batchConsensus(largeDataset);
```

### 5. Leverage Caching

```javascript
// Good: Enable caching
const results = await batchConsensus(questions, { useCache: true });

// Bad: Disable cache for repeated queries
const results = await batchConsensus(questions, { useCache: false });
```

## Troubleshooting

### High Error Rate

**Symptom:** Many results have `outcome: 'error'`

**Solutions:**
1. Increase timeout: `{ timeout: 60000 }` (60 seconds)
2. Reduce concurrency: `{ concurrency: 5 }`
3. Enable retry: `{ retryFailed: true }`

### Low Agreement Rate

**Symptom:** Many results have `outcome: 'low_agreement'`

**Solutions:**
1. Lower threshold: `{ minAgreement: 0.5 }`
2. Add more workers: `{ workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'] }`
3. Use task-specific models: `{ taskType: 'code_generation', workers: ['deepseek-coder', ...] }`

### Slow Performance

**Symptom:** Batch takes longer than expected

**Solutions:**
1. Increase concurrency: `{ concurrency: 15 }`
2. Enable caching: `{ useCache: true }`
3. Use streaming for large datasets
4. Reduce worker count: `{ workers: ['opus', 'sonnet', 'haiku'] }` (3 instead of 6)

### Memory Issues

**Symptom:** Out of memory errors on large batches

**Solutions:**
1. Use streaming API: `batchConsensusStream()`
2. Process in chunks:
   ```javascript
   const chunkSize = 100;
   for (let i = 0; i < questions.length; i += chunkSize) {
     const chunk = questions.slice(i, i + chunkSize);
     const results = await batchConsensus(chunk);
     await processResults(results);
   }
   ```

## Roadmap

Future enhancements:

- [ ] Dynamic concurrency adjustment based on performance
- [ ] Automatic retry with exponential backoff
- [ ] Distributed processing across fleet nodes
- [ ] Real-time dashboard for batch monitoring
- [ ] Integration with workflow orchestration
- [ ] A/B testing between different worker configurations

## Related Documentation

- [Weighted Voting](./WEIGHTED_VOTING_SUMMARY.md) - How votes are weighted
- [Consensus Cache](./consensus-cache.cjs) - Caching implementation
- [Workflow Storage](./WORKFLOW_STORAGE_README.md) - Result persistence

---

**Created:** 2026-06-28  
**Version:** 1.0.0  
**Status:** Production Ready
