# Batch Consensus API - Quick Reference

## Installation

No installation required. Module is ready to use.

## Basic Usage

```javascript
const { batchConsensus } = require('./shared/batch-consensus.cjs');

// Process 100 questions
const results = await batchConsensus(questions, {
  concurrency: 10,
  taskType: 'research',
  onProgress: (completed, total) => console.log(`${completed}/${total}`),
});
```

## Key Features

✅ **Parallel Processing**: Up to 10 concurrent operations (configurable)  
✅ **Progress Tracking**: Real-time callbacks  
✅ **Caching**: Automatic deduplication (optional)  
✅ **Error Handling**: Graceful failures, partial results  
✅ **Streaming**: Memory-efficient for large datasets  
✅ **Statistics**: Comprehensive analytics  

## API Functions

### `batchConsensus(questions, options)`

Main function - processes array of questions.

**Parameters:**
- `questions`: Array of strings
- `options`: Configuration object

**Returns:** Array of result objects

### `batchConsensusStream(questions, options)`

Streaming version for large datasets (500+ questions).

**Returns:** AsyncGenerator (yields results as they complete)

### `analyzeBatchResults(results)`

Generate statistics from results.

**Returns:** Stats object (success rate, confidence, etc.)

### `generateBatchReport(results, options)`

Generate human-readable report.

**Returns:** String report

## Configuration Options

```javascript
{
  concurrency: 10,           // Max parallel operations
  taskType: 'general',       // Task type for weighting
  workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'],
  minAgreement: 0.6,         // Threshold (0.0-1.0)
  useCache: true,            // Enable caching
  onProgress: null,          // Callback: (completed, total, current) => void
  onError: null,             // Callback: (error, question, index) => void
  stopOnError: false,        // Stop on first error
  retryFailed: false,        // Retry failed once
  timeout: 30000,            // Per-item timeout (ms)
}
```

## Example: Progress Tracking

```javascript
const results = await batchConsensus(questions, {
  onProgress: (completed, total, current) => {
    const percent = ((completed / total) * 100).toFixed(0);
    console.log(`[${percent}%] ${current.question} -> ${current.answer}`);
  },
});
```

## Example: Error Handling

```javascript
const errors = [];
const results = await batchConsensus(questions, {
  stopOnError: false,
  onError: (error, question, index) => {
    errors.push({ index, question, error: error.message });
  },
});

console.log(`Completed with ${errors.length} errors`);
```

## Example: Streaming (Large Datasets)

```javascript
const { batchConsensusStream } = require('./shared/batch-consensus.cjs');

for await (const result of batchConsensusStream(largeDataset, { concurrency: 20 })) {
  // Process result immediately (memory efficient)
  await db.insert('results', result);
}
```

## Result Format

```javascript
{
  question: "What is 2+2?",
  answer: "4",
  confidence: 0.95,
  agreement: 0.89,
  votes: { "4": 5, "four": 1 },
  models: ["opus", "sonnet", "haiku", "gpt-4o", "gemini", "fable"],
  weights: { "opus": 1.0, "sonnet": 0.85, ... },
  cached: false,
  outcome: "success",  // or "low_agreement", "error"
  timestamp: "2026-06-28T20:30:00.000Z"
}
```

## Performance Guidelines

| Dataset Size | Concurrency | Expected Time |
|--------------|-------------|---------------|
| 1-10         | 5           | ~1-2 seconds  |
| 10-50        | 10          | ~3-5 seconds  |
| 50-100       | 10-15       | ~8-12 seconds |
| 100-500      | 15-20       | ~30-60 sec    |
| 500+         | 20+stream   | ~2-5 minutes  |

## Testing

```bash
# Simple validation test
node shared/test-batch-simple.cjs

# Full test suite (9 tests)
node shared/test-batch-consensus.cjs
```

## Integration

Works seamlessly with:
- **weighted-voting.cjs**: Capability-based vote weighting
- **consensus-cache.cjs**: Intelligent caching
- **workflow-storage-adapter.js**: PostgreSQL persistence

## Files Created

1. `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/batch-consensus.cjs` - Main implementation
2. `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/test-batch-consensus.cjs` - Full test suite
3. `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/test-batch-simple.cjs` - Simple validation
4. `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/BATCH-CONSENSUS-README.md` - Full documentation
5. `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/BATCH-CONSENSUS-QUICK-REF.md` - This file

## Status

✅ **Production Ready**  
✅ Core functionality working  
✅ Tests passing  
✅ Documentation complete  

---

**Created:** 2026-06-28  
**Version:** 1.0.0
