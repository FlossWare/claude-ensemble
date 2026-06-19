# Workflow Storage Integration Guide

Quick reference for integrating automated view refresh into existing workflows.

## 1-Minute Integration

### Add to Any Workflow

```javascript
// 1. Import at top
import { WorkflowStorageAdapter } from '~/.claude/learning/workflow-storage-adapter.js';

// 2. Initialize at workflow start
const storage = new WorkflowStorageAdapter();
const startTime = Date.now();

// 3. Store at completion
try {
  // ... your workflow logic ...

  await storage.storeExecution({
    workflow: 'your-workflow-name',
    model: 'claude-sonnet-4',
    task_type: 'your_task_type',
    quality_score: 0.85,  // 0.0-1.0
    input_tokens: 1000,
    output_tokens: 500,
    cost_usd: 0.015,
    duration_ms: Date.now() - startTime,
    outcome: 'success',
    metadata: {
      // Optional: any custom data
      strategy: 'your_strategy',  // Auto-updates Thompson Sampling
      custom_field: 'value'
    }
  });
  await storage.disconnect();
} catch (err) {
  // Store failure
  await storage.storeExecution({
    workflow: 'your-workflow-name',
    model: 'claude-sonnet-4',
    task_type: 'your_task_type',
    quality_score: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    duration_ms: Date.now() - startTime,
    outcome: 'failure',
    metadata: { error: err.message }
  });
  await storage.disconnect();
}
```

**That's it!** Views auto-refresh after each `storeExecution()` call.

## Quality Score Calculation

### Research Workflows
```javascript
const acceptedClaimsCount = verified.length;
const totalClaimsCount = sources.reduce((sum, s) => sum + (s.claims?.length || 0), 0);
const qualityScore = totalClaimsCount > 0 ? acceptedClaimsCount / totalClaimsCount : 0;
```

### Code Review Workflows
```javascript
const issuesFound = results.issues.length;
const criticalIssues = results.issues.filter(i => i.severity === 'critical').length;
const qualityScore = 1.0 - (criticalIssues / Math.max(issuesFound, 1));
```

### Test Workflows
```javascript
const testsRun = results.total;
const testsPassed = results.passed;
const qualityScore = testsRun > 0 ? testsPassed / testsRun : 0;
```

### General Formula
```javascript
// Quality = success_metric / total_metric (0.0-1.0)
const qualityScore = Math.min(1.0, Math.max(0.0, successCount / totalCount));
```

## Token Tracking

### Using Claude API
```javascript
// After API call
const response = await claudeAPI.messages.create({...});

const execution = {
  // ...
  input_tokens: response.usage.input_tokens,
  output_tokens: response.usage.output_tokens,
  cost_usd: calculateCost(response.usage)
};
```

### Cost Calculation
```javascript
function calculateCost(usage) {
  // Prices as of 2026-06 (check current pricing)
  const inputCostPer1M = {
    'claude-opus-4': 15.00,
    'claude-sonnet-4': 3.00,
    'claude-haiku-4': 0.25
  };

  const outputCostPer1M = {
    'claude-opus-4': 75.00,
    'claude-sonnet-4': 15.00,
    'claude-haiku-4': 1.25
  };

  const model = 'claude-sonnet-4'; // or detect from response
  const inputCost = (usage.input_tokens / 1_000_000) * inputCostPer1M[model];
  const outputCost = (usage.output_tokens / 1_000_000) * outputCostPer1M[model];

  return inputCost + outputCost;
}
```

## Thompson Sampling Integration

### Auto-Update Bandit State
```javascript
await storage.storeExecution({
  // ... other fields ...
  metadata: {
    strategy: 'ast_analysis',  // Triggers bandit update
    // ... other metadata ...
  }
});
```

### Select Best Strategy
```javascript
const storage = new WorkflowStorageAdapter();
const bestStrategy = await storage.selectStrategy();

// Use strategy in workflow
if (bestStrategy === 'ast_analysis') {
  // Use AST-based approach
} else if (bestStrategy === 'pattern_match') {
  // Use pattern matching
}
```

### Exploration vs Exploitation
```javascript
// 10% exploration (random strategy)
const shouldExplore = Math.random() < 0.1;

const strategy = shouldExplore
  ? strategies[Math.floor(Math.random() * strategies.length)]
  : await storage.selectStrategy();
```

## Vector Similarity Search

### Store with Embedding
```javascript
import { generateEmbedding } from './embedding-utils.js';

const embedding = await generateEmbedding(problemDescription);

await storage.storeExperience({
  problem_type: 'code_refactor',
  problem_hash: hashProblem(code),
  context: { language: 'java', complexity: 'high' },
  embedding: embedding,  // 128-dim or 768-dim
  strategy: 'ast_analysis',
  success: true,
  reward: qualityScore,
  novelty_score: 0.7,
  importance: 0.8
});
```

### Query Similar Experiences
```javascript
const queryEmbedding = await generateEmbedding(newProblem);

const similar = await storage.findSimilarExperiences(
  queryEmbedding,
  limit = 10,
  minReward = 0.7  // Only successful past experiences
);

// Use top match strategy
if (similar.length > 0) {
  const topStrategy = similar[0].strategy;
  console.log(`Using strategy from similar problem: ${topStrategy}`);
}
```

## Common Patterns

### Multi-Phase Workflow
```javascript
const storage = new WorkflowStorageAdapter();
const startTime = Date.now();
const phaseMetrics = {};

try {
  // Phase 1
  const phase1Start = Date.now();
  const result1 = await runPhase1();
  phaseMetrics.phase1_duration = Date.now() - phase1Start;
  phaseMetrics.phase1_quality = calculateQuality(result1);

  // Phase 2
  const phase2Start = Date.now();
  const result2 = await runPhase2(result1);
  phaseMetrics.phase2_duration = Date.now() - phase2Start;
  phaseMetrics.phase2_quality = calculateQuality(result2);

  // Store with phase metrics
  await storage.storeExecution({
    workflow: 'multi-phase',
    model: 'claude-sonnet-4',
    task_type: 'complex_task',
    quality_score: (phaseMetrics.phase1_quality + phaseMetrics.phase2_quality) / 2,
    input_tokens: result1.tokens + result2.tokens,
    output_tokens: result1.output_tokens + result2.output_tokens,
    cost_usd: result1.cost + result2.cost,
    duration_ms: Date.now() - startTime,
    outcome: 'success',
    metadata: phaseMetrics
  });

  await storage.disconnect();
} catch (err) {
  // Store partial progress
  await storage.storeExecution({
    workflow: 'multi-phase',
    model: 'claude-sonnet-4',
    task_type: 'complex_task',
    quality_score: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    duration_ms: Date.now() - startTime,
    outcome: 'failure',
    metadata: { ...phaseMetrics, error: err.message }
  });
  await storage.disconnect();
}
```

### Parallel Workers
```javascript
const storage = new WorkflowStorageAdapter();

const results = await Promise.all([
  runWorker('worker-1'),
  runWorker('worker-2'),
  runWorker('worker-3')
]);

// Store aggregated results
const avgQuality = results.reduce((sum, r) => sum + r.quality, 0) / results.length;
const totalTokens = results.reduce((sum, r) => sum + r.tokens, 0);

await storage.storeExecution({
  workflow: 'parallel-workers',
  model: 'claude-sonnet-4',
  task_type: 'distributed_task',
  quality_score: avgQuality,
  input_tokens: totalTokens,
  output_tokens: results.reduce((sum, r) => sum + r.output_tokens, 0),
  cost_usd: results.reduce((sum, r) => sum + r.cost, 0),
  duration_ms: Math.max(...results.map(r => r.duration)),
  outcome: 'success',
  metadata: {
    workers: results.length,
    worker_results: results.map(r => ({ quality: r.quality, duration: r.duration }))
  }
});
```

### Retry Loop
```javascript
const storage = new WorkflowStorageAdapter();
const maxRetries = 3;
let attempt = 0;
let success = false;

while (attempt < maxRetries && !success) {
  attempt++;
  const attemptStart = Date.now();

  try {
    const result = await runWorkflow();
    success = true;

    await storage.storeExecution({
      workflow: 'retry-workflow',
      model: 'claude-sonnet-4',
      task_type: 'with_retry',
      quality_score: result.quality,
      input_tokens: result.tokens,
      output_tokens: result.output_tokens,
      cost_usd: result.cost,
      duration_ms: Date.now() - attemptStart,
      outcome: 'success',
      metadata: { attempts: attempt }
    });

  } catch (err) {
    if (attempt === maxRetries) {
      // Final failure
      await storage.storeExecution({
        workflow: 'retry-workflow',
        model: 'claude-sonnet-4',
        task_type: 'with_retry',
        quality_score: 0,
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        duration_ms: Date.now() - attemptStart,
        outcome: 'failure',
        metadata: { attempts: attempt, error: err.message }
      });
    }
  }
}

await storage.disconnect();
```

## Workflow Examples

### 1. Deep Research (Already Integrated)
**Location:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/deep-research.mjs`

### 2. Code Review
```javascript
import { WorkflowStorageAdapter } from '~/.claude/learning/workflow-storage-adapter.js';

async function codeReview(filePath) {
  const storage = new WorkflowStorageAdapter();
  const startTime = Date.now();

  try {
    const issues = await analyzeCode(filePath);
    const criticalIssues = issues.filter(i => i.severity === 'critical').length;
    const qualityScore = 1.0 - (criticalIssues / Math.max(issues.length, 1));

    await storage.storeExecution({
      workflow: 'code-review',
      model: 'claude-sonnet-4',
      task_type: 'static_analysis',
      quality_score: qualityScore,
      input_tokens: 2000,
      output_tokens: 800,
      cost_usd: 0.018,
      duration_ms: Date.now() - startTime,
      outcome: 'success',
      metadata: {
        file: filePath,
        issues_found: issues.length,
        critical_issues: criticalIssues,
        strategy: 'ast_analysis'
      }
    });

    await storage.disconnect();
    return issues;
  } catch (err) {
    await storage.storeExecution({
      workflow: 'code-review',
      model: 'claude-sonnet-4',
      task_type: 'static_analysis',
      quality_score: 0,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      duration_ms: Date.now() - startTime,
      outcome: 'failure',
      metadata: { file: filePath, error: err.message }
    });
    await storage.disconnect();
    throw err;
  }
}
```

### 3. Test Runner
```javascript
async function runTests(testSuite) {
  const storage = new WorkflowStorageAdapter();
  const startTime = Date.now();

  try {
    const results = await executeTests(testSuite);
    const qualityScore = results.passed / results.total;

    await storage.storeExecution({
      workflow: 'test-runner',
      model: 'local-test-runner',
      task_type: 'unit_tests',
      quality_score: qualityScore,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      duration_ms: Date.now() - startTime,
      outcome: results.failed === 0 ? 'success' : 'failure',
      metadata: {
        total: results.total,
        passed: results.passed,
        failed: results.failed,
        skipped: results.skipped
      }
    });

    await storage.disconnect();
    return results;
  } catch (err) {
    await storage.storeExecution({
      workflow: 'test-runner',
      model: 'local-test-runner',
      task_type: 'unit_tests',
      quality_score: 0,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      duration_ms: Date.now() - startTime,
      outcome: 'failure',
      metadata: { error: err.message }
    });
    await storage.disconnect();
    throw err;
  }
}
```

## Checklist

- [ ] Import `WorkflowStorageAdapter`
- [ ] Initialize at workflow start
- [ ] Track `startTime = Date.now()`
- [ ] Calculate quality score (0.0-1.0)
- [ ] Track token usage (if applicable)
- [ ] Call `storeExecution()` on success
- [ ] Call `storeExecution()` on failure
- [ ] Disconnect storage adapter
- [ ] Test with `node ~/.claude/learning/test-view-refresh.js`
- [ ] Verify views refresh in PostgreSQL

## Troubleshooting

### "Cannot find module 'pg'"
```bash
cd ~/.claude/learning
npm install pg
```

### "Connection refused to laptop-01:5432"
```bash
# Check PostgreSQL is running
ssh laptop-01 'systemctl status postgresql'

# Check network connectivity
ping laptop-01
```

### "Views not refreshing"
```javascript
// Manual refresh
const storage = new WorkflowStorageAdapter();
await storage.connect();
await storage.refreshViews();
await storage.disconnect();
```

### "Quality score always 0"
Check calculation logic. Should return 0.0-1.0:
```javascript
// Good
const qualityScore = Math.min(1.0, Math.max(0.0, successCount / totalCount));

// Bad
const qualityScore = successCount / totalCount; // May be >1.0 or NaN
```

## Next Steps

1. **Integrate into your workflow** (copy pattern above)
2. **Test locally** (`node your-workflow.js`)
3. **Verify views** (`psql -h laptop-01 -U sfloess -d learning`)
4. **Monitor Grafana** (if configured)
5. **Iterate based on metrics**
