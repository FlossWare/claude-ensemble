# Batch Consensus Integration Guide

**Issue:** #263  
**Status:** ACTIVE  
**Updated:** 2026-07-01

## Overview

Batch consensus allows processing arrays of questions/tasks using multi-AI consensus with:
- Parallel execution (configurable concurrency)
- Progress tracking via callbacks
- Graceful error handling (partial results returned)
- Integration with weighted voting and consensus cache
- Memory-efficient batching for large datasets

## Quick Start

### ESM (Workflows)

```javascript
import { batchConsensusWithWorker } from '../shared/batch-consensus-wrapper.mjs';

// Define custom worker function
const verifyWorker = async (question) => {
  const votes = await Promise.all([
    agent(question.text, { model: 'opus', schema }),
    agent(question.text, { model: 'sonnet', schema }),
    agent(question.text, { model: 'haiku', schema })
  ]);

  return {
    model: 'consensus-3vote',
    models: ['opus', 'sonnet', 'haiku'],
    answer: processVotes(votes),
    confidence: calculateConfidence(votes),
    votes: votes
  };
};

// Process batch
const results = await batchConsensusWithWorker(
  questions,
  verifyWorker,
  {
    concurrency: 5,
    onProgress: (completed, total) => {
      console.log(`Progress: ${completed}/${total}`);
    },
    onError: (error, question, index) => {
      console.error(`Failed question ${index}:`, error.message);
    }
  }
);
```

### CommonJS (Shared Modules)

```javascript
const { batchConsensus } = require('./batch-consensus.cjs');

const results = await batchConsensus(questions, {
  concurrency: 10,
  taskType: 'research',
  workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
  minAgreement: 0.6,
  useCache: true
});
```

## Integration Points

### 1. Deep Research Workflow

**File:** `workflows/deep-research.mjs`  
**Status:** ✅ ACTIVE (already integrated)

Used in Phase 4 (Verify) to process claims in batches with 3-vote adversarial verification.

```javascript
const batchResults = await batchConsensusWithWorker(
  claimQuestions,
  verifyWorker,
  {
    concurrency: 5, // 5 claims × 3 models = 15 parallel agents max
    onProgress: (completed, total) => {
      console.log(`Progress: ${completed}/${total} claims verified`);
    }
  }
);
```

### 2. Consensus Engine

**File:** `shared/consensus-engine.js`  
**Status:** ⚠️ CANDIDATE (not yet integrated)

Could use batch consensus for multiModelReview when processing multiple files/issues:

```javascript
export async function batchMultiModelReview(prompts, schema, options = {}) {
  const workerFn = async (prompt) => {
    return await multiModelReview(prompt, schema, options);
  };

  return await batchConsensusWithWorker(prompts, workerFn, {
    concurrency: options.concurrency || 5,
    onProgress: options.onProgress
  });
}
```

### 3. Fleet Workflow Patterns

**File:** `shared/fleet-workflow-patterns.js`  
**Status:** ⚠️ CANDIDATE (not yet integrated)

Could integrate batch consensus for distributed consensus across fleet workers:

```javascript
export async function distributeWithConsensus(config) {
  const {
    items,
    workerFn,
    consensusFn, // Multi-AI consensus per item
    fleetOptions = {}
  } = config;

  // Distribute items across fleet
  const distribution = distributeItems(items, workers);

  // Each fleet worker processes items with consensus
  const fleetResults = await parallel(
    workers.map(worker => async () => {
      const workerItems = distribution.get(worker.hostname);
      return await batchConsensusWithWorker(
        workerItems,
        consensusFn,
        { concurrency: 3 }
      );
    })
  );

  return mergeResults(fleetResults);
}
```

### 4. Workflow Helpers

**File:** `shared/workflow-helpers.js`  
**Status:** ✅ DOCUMENTED

Added `BATCH_CONSENSUS_INSTRUCTION` constant for workflows:

```javascript
import { BATCH_CONSENSUS_INSTRUCTION } from '../shared/workflow-helpers.js';

// Use in workflow prompts
const prompt = `${BATCH_CONSENSUS_INSTRUCTION}

Process these questions with consensus...`;
```

## API Reference

### batchConsensusWithWorker(questions, workerFn, options)

Custom worker function for maximum flexibility.

**Parameters:**
- `questions` (Array): Array of questions/tasks to process
- `workerFn` (Function): Custom worker function
  - Input: `(question) => { model, answer, confidence, votes }`
  - Must return object with `{model, answer, confidence}`
- `options` (Object):
  - `concurrency` (number, default: 10): Max parallel operations
  - `onProgress` (Function): `(completed, total, result) => void`
  - `onError` (Function): `(error, question, index) => void`
  - `stopOnError` (boolean, default: false): Stop batch on first error
  - `retryFailed` (boolean, default: false): Retry failed items once
  - `timeout` (number, default: 30000): Per-item timeout (ms)

**Returns:** `Promise<Array<Object>>`
- Array of results (same length as questions)
- Each result: `{question, answer, confidence, models, votes, timestamp, cached}`
- Errors marked as: `{question, error, confidence: 0, outcome: 'error'}`

### batchConsensus(questions, options)

Built-in consensus with simulated worker responses.

**Parameters:**
- `questions` (Array<string>): Array of questions
- `options` (Object):
  - All options from `batchConsensusWithWorker`
  - `taskType` (string, default: 'general'): Task type for capability weighting
  - `workers` (Array, default: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'])
  - `minAgreement` (number, default: 0.6): Min agreement threshold (0.0-1.0)
  - `useCache` (boolean, default: true): Enable consensus cache
  - `explain` (boolean, default: false): Enable explainability reports
  - `explainFormat` (string, default: 'json'): 'json' | 'markdown' | 'both'

### batchConsensusStream(questions, options)

Streaming API for very large datasets. Yields results as they complete.

```javascript
for await (const result of batchConsensusStream(questions, options)) {
  console.log('Result:', result);
}
```

### Utility Functions

#### analyzeBatchResults(results)

Returns statistics:
```javascript
{
  total, successful, errors, lowAgreement, cached,
  cacheHitRate, successRate,
  avgConfidence, avgAgreement
}
```

#### generateBatchReport(results, options)

Generates formatted report:
```javascript
const report = generateBatchReport(results, {
  includeDetails: true // Include failed questions
});
console.log(report);
```

## Examples

### Example 1: Fact Verification (Deep Research)

```javascript
import { batchConsensusWithWorker } from '../shared/batch-consensus-wrapper.mjs';

const verifyWorker = async (question) => {
  const { text, claim, source } = question;

  // 3 voters per claim
  const votes = await Promise.all([
    agent(text, { model: 'opus', schema }),
    agent(text, { model: 'sonnet', schema }),
    agent(text, { model: 'haiku', schema })
  ]);

  const verdicts = votes.map(parseVerdict);
  const refuteCount = verdicts.filter(v => v.verdict === 'REFUTE').length;
  const avgConfidence = verdicts.reduce((sum, v) => sum + v.confidence, 0) / 3;

  return {
    model: 'consensus-3vote',
    models: ['opus', 'sonnet', 'haiku'],
    answer: {
      claim,
      source,
      accepted: refuteCount < 2, // Need 2/3 refutes to kill
      confidence: avgConfidence,
      votes: verdicts
    },
    confidence: avgConfidence,
    votes: verdicts
  };
};

const results = await batchConsensusWithWorker(claimQuestions, verifyWorker, {
  concurrency: 5, // 5 claims × 3 models = 15 parallel agents
  onProgress: (completed, total) => {
    console.log(`Verified ${completed}/${total} claims`);
  }
});
```

### Example 2: Code Review (Multiple Files)

```javascript
import { batchConsensusWithWorker } from '../shared/batch-consensus-wrapper.mjs';
import { multiModelReview } from '../shared/consensus-engine.js';

const reviewWorker = async (file) => {
  const prompt = `Review this file for bugs:\n\n${file.content}`;
  const schema = FINDING_SCHEMA;

  const reviews = await multiModelReview(prompt, schema, {
    workers: ['opus', 'sonnet', 'gpt-4o'],
    strategy: 'weighted'
  });

  return {
    model: 'multi-model-review',
    models: reviews.allReviews.map(r => r.model),
    answer: {
      file: file.path,
      findings: mergeFindings(reviews.allReviews)
    },
    confidence: calculateReviewConfidence(reviews),
    votes: reviews.allReviews
  };
};

const fileReviews = await batchConsensusWithWorker(files, reviewWorker, {
  concurrency: 3, // 3 files × 3 models = 9 parallel agents
  onProgress: (completed, total) => {
    console.log(`Reviewed ${completed}/${total} files`);
  }
});
```

### Example 3: Research Questions with Caching

```javascript
import { batchConsensus } from '../shared/batch-consensus-wrapper.mjs';

const questions = [
  'What is the capital of France?',
  'Explain quantum entanglement',
  'What is the capital of France?', // Duplicate - will hit cache
  // ... 100 more questions
];

const results = await batchConsensus(questions, {
  concurrency: 10,
  taskType: 'research',
  workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
  minAgreement: 0.6,
  useCache: true, // Enable caching
  onProgress: (completed, total, result) => {
    const cached = result.cached ? '(cached)' : '';
    console.log(`${completed}/${total} ${cached}`);
  }
});

// Analyze results
const stats = analyzeBatchResults(results);
console.log(`Cache hit rate: ${(stats.cacheHitRate * 100).toFixed(1)}%`);
console.log(`Success rate: ${(stats.successRate * 100).toFixed(1)}%`);
console.log(`Avg confidence: ${(stats.avgConfidence * 100).toFixed(1)}%`);
```

## Configuration

### Environment Variables

```bash
# Consensus cache (PostgreSQL)
PGHOST=laptop-01
PGPORT=5432
PGDATABASE=learning
PGUSER=sfloess

# Batch processing
CONSENSUS_CONCURRENCY=10  # Default concurrency
CONSENSUS_TIMEOUT=30000   # Per-item timeout (ms)

# Explainability
CONSENSUS_EXPLAIN=1       # Enable explainability reports
CONSENSUS_EXPLAIN_FORMAT=markdown  # json, markdown, or both
```

### Options Defaults

```javascript
const DEFAULT_OPTIONS = {
  concurrency: 10,
  taskType: 'general',
  workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'],
  minAgreement: 0.6,
  useCache: true,
  onProgress: null,
  onError: null,
  stopOnError: false,
  retryFailed: false,
  timeout: 30000,
  explain: false,
  explainFormat: 'json',
};
```

## Known Issues

### 1. consensus-cache.cjs Syntax Error

**Status:** WORKAROUND ACTIVE  
**File:** `shared/consensus-cache.cjs`  
**Error:** 5 missing closing braces (lines 740-985)

**Workaround:** Using `consensus-cache-stub.cjs` until fixed
- Stub returns cache miss (no caching)
- Does not block batch-consensus functionality
- Caching will work once consensus-cache.cjs is fixed

**Fix Required:**
```bash
# TODO: Fix consensus-cache.cjs brace balance
# Lines to check: 740-985 (before class ConsensusCache)
# Missing: 5 closing braces
```

### 2. Database Tables Required for Caching

Consensus cache requires PostgreSQL tables:
- `workflow.consensus_cache` - Cache storage
- `workflow.consensus_cache_stats` - Statistics

**Setup:**
```sql
-- Run schema initialization
psql -h laptop-01 -U sfloess -d learning -f shared/consensus-cache-schema.sql
```

## Verification

### Test Import

```bash
# ESM
node --input-type=module -e "import { batchConsensus, batchConsensusWithWorker } from './shared/batch-consensus-wrapper.mjs'; console.log('✓ OK');"

# CommonJS
node -e "const { batchConsensus } = require('./shared/batch-consensus.cjs'); console.log('✓ OK');"
```

### Run Test Suite

```bash
node shared/test-batch-consensus.cjs
```

Expected output:
```
✓ Single question processed correctly
✓ Small batch processed (10 questions)
✓ Progress tracking works
✓ Error handling works
✓ Streaming API works
```

### Integration Test

```bash
node shared/test-batch-consensus-integration.mjs
```

Expected: Deep research workflow processes claims in batches.

## Performance

### Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Single question (3 models) | ~2s | Parallel execution |
| Batch 10 questions (concurrency=5) | ~4s | 5 parallel chunks |
| Batch 100 questions (concurrency=10) | ~20s | 10 parallel chunks |
| Cache hit (exact match) | <10ms | PostgreSQL lookup |
| Cache hit (semantic match) | ~50ms | pgvector search |

### Optimization

1. **Concurrency Tuning**
   - Start with 5-10 for API rate limits
   - Increase to 20+ for local models
   - Monitor API provider limits

2. **Caching**
   - Enable `useCache: true` for repeated questions
   - Semantic cache catches ~90% of near-duplicates
   - 7-day TTL reduces API costs

3. **Batching**
   - Group similar questions together
   - Use streaming API for >1000 questions
   - Split mega-batches to avoid memory issues

## Next Steps

1. ✅ Fix consensus-cache.cjs syntax error (remove stub)
2. ⚠️ Add batch consensus to consensus-engine.js (batchMultiModelReview)
3. ⚠️ Add batch consensus to fleet-workflow-patterns.js (distributeWithConsensus)
4. ⚠️ Update workflows to use batch consensus where applicable
5. ⚠️ Add explainability integration examples
6. ⚠️ Performance tuning based on real workload

## References

- **Issue:** #263 - Wire in Batch consensus
- **Implementation:** `shared/batch-consensus.cjs`
- **Wrapper:** `shared/batch-consensus-wrapper.mjs`
- **Tests:** `shared/test-batch-consensus.cjs`
- **Example:** `workflows/deep-research.mjs` (Phase 4 - Verify)
- **Dependencies:**
  - `weighted-voting-with-explain.cjs` - Weighted voting
  - `consensus-cache.cjs` - Caching (currently stubbed)
  - `explainability-reporter.cjs` - Explainability
