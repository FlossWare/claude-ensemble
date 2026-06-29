# Error Recovery Chain Integration Guide

How to integrate the error recovery chain pattern into Claude Code workflows.

## Quick Start

### 1. Import the utilities

```javascript
const {
  executeWithTimeout,
  ServiceHealthCheck,
  tryFallbackChain,
  gatherResultsWithPartialAcceptance,
  AdaptiveWorkerSelection,
  ErrorLearningTracker
} = require('./recovery-chain-utils.js')
```

### 2. Add timeout protection

```javascript
// Wrap worker execution with timeout
const result = await executeWithTimeout(
  () => agent(prompt, { model: 'opus', json: schema }),
  45000  // 45 second timeout for slow models
)
```

### 3. Implement fallback chains

```javascript
const result = await tryFallbackChain([
  {
    label: 'GPT-4o (primary)',
    fn: () => agent(prompt, { model: 'gpt-4o' }),
    retryable: true
  },
  {
    label: 'Opus (fallback)',
    fn: () => agent(prompt, { model: 'opus' }),
    retryable: true
  },
  {
    label: 'Sonnet (last resort)',
    fn: () => agent(prompt, { model: 'sonnet' }),
    retryable: false
  }
])
```

### 4. Handle partial results

```javascript
const { results, errors, coverage } = await gatherResultsWithPartialAcceptance(
  workers,
  {
    minResults: 1,      // Continue with at least 1 result
    timeoutMs: 30000,
    validateFn: (r) => {
      if (!r.answer) throw new Error('No answer provided')
    }
  }
)

if (coverage < 1.0) {
  log(`⚠ Degraded consensus (${results.length}/${workers.length}): ${errors.map(e => e.error).join('; ')}`)
}
```

---

## Integration Patterns by Workflow

### Pattern A: ai-consensus.js

Add recovery to worker execution:

```javascript
// BEFORE: Raw agent execution
const responses = await Promise.all(
  workerModels.map(model =>
    agent(prompt, { model })
  )
)

// AFTER: With recovery
const health = new ServiceHealthCheck()
const responses = []
const errors = []

for (const model of workerModels) {
  try {
    const response = await executeWithTimeout(
      () => agent(prompt, { model }),
      new WorkerTimeoutTracker().getTimeout(model)
    )
    responses.push(response)
  } catch (err) {
    log(`Worker ${model} failed: ${err.message}`)
    errors.push({ model, error: err.message })
  }
}

// Check if we have enough results
if (responses.length < Math.max(1, Math.ceil(workerModels.length / 2))) {
  log(`⚠ Insufficient results (${responses.length}/${workerModels.length})`)
  // Continue anyway if we have at least 1
}
```

### Pattern B: ai-consensus-refinement.js

Add recovery to refinement loop:

```javascript
// Execute refinement with timeout and fallback
async function refineWithRecovery(workers, arbiter, roundNum) {
  const critiquePrompt = buildCritiquePrompt(workers)
  const timeoutMs = new WorkerTimeoutTracker().getTimeout(arbiter)
  
  try {
    return await executeWithTimeout(
      () => agent(critiquePrompt, { model: arbiter, json: schema }),
      timeoutMs
    )
  } catch (err) {
    log(`Refinement round ${roundNum} failed with ${arbiter}: ${err.message}`)
    
    // Try fallback arbiter
    const fallback = arbiter === 'opus' ? 'sonnet' : 'opus'
    return await executeWithTimeout(
      () => agent(critiquePrompt, { model: fallback, json: schema }),
      new WorkerTimeoutTracker().getTimeout(fallback)
    )
  }
}
```

### Pattern C: ai-consensus-hierarchical.js

Add adaptive selection to specialized teams:

```javascript
// Select team members based on health
async function selectSpecializedTeam(specialization, health) {
  const selection = new AdaptiveWorkerSelection()
  const teamModels = getTeamForSpecialization(specialization)
  
  // Filter to healthy models
  const healthyModels = teamModels.filter(m => health.getScore(m) > 40)
  
  if (healthyModels.length === 0) {
    log(`⚠ No healthy models for ${specialization}, using all available`)
    healthyModels.push(...teamModels)
  }
  
  // Adapt count based on failures
  const failureRate = getRecentFailureRate(specialization)
  const selected = selection.selectWorkers(healthyModels, failureRate)
  
  log(`Selected team (${specialization}): ${selected.join(', ')}`)
  return selected
}
```

### Pattern D: ai-task-router.js

Add circuit breaker for service health:

```javascript
const breaker = new CircuitBreaker({ failureThreshold: 3 })

async function routeTask(task, budget) {
  try {
    return await breaker.execute('task-router', async () => {
      // Task router logic
      return optimizeForBudgetAndComplexity(task, budget)
    })
  } catch (err) {
    if (err instanceof CircuitBreakerOpen) {
      log(`Task router unavailable, using fallback selection`)
      return getDefaultWorkerSelection(budget)
    }
    throw err
  }
}
```

---

## Common Integration Scenarios

### Scenario 1: Single-Model Execution with Fallback

**Use Case:** Execute arbiter or critical path with fallback

```javascript
const arbiterResult = await tryFallbackChain([
  {
    label: 'Fable (primary)',
    fn: () => executeWithTimeout(
      () => agent(arbitratePrompt, { model: 'fable' }),
      45000
    ),
    retryable: true
  },
  {
    label: 'Opus (fallback)',
    fn: () => agent(arbitratePrompt, { model: 'opus' }),
    retryable: false
  }
])
```

### Scenario 2: Parallel Execution with Partial Results

**Use Case:** Worker consensus where we can work with subset

```javascript
const workers = [
  { model: 'opus', fn: () => agent(prompt, { model: 'opus' }) },
  { model: 'sonnet', fn: () => agent(prompt, { model: 'sonnet' }) },
  { model: 'haiku', fn: () => agent(prompt, { model: 'haiku' }) },
  { model: 'gpt-4o', fn: () => agent(prompt, { model: 'gpt-4o' }) }
]

const { results, coverage, degradationLevel } = await gatherResultsWithPartialAcceptance(
  workers,
  {
    minResults: 2,  // Need at least 2 for consensus
    timeoutMs: 30000
  }
)

// Adjust consensus algorithm based on coverage
const consensusResult = consensusVote(results)
if (degradationLevel > 0.3) {
  log(`⚠ Degraded consensus - lower confidence in result`)
  consensusResult.confidence *= (1 - degradationLevel)
}
```

### Scenario 3: Health-Aware Service Selection

**Use Case:** Route requests to healthy services

```javascript
const health = new ServiceHealthCheck()

async function getOpenClawVote(prompt) {
  // Check health first
  const isHealthy = await health.checkHealth('openclaw', 
    async () => {
      // Health check implementation
      const res = await fetch('http://localhost:18789/api/status', { timeout: 2000 })
      return res.ok
    }
  )

  if (!isHealthy) {
    log(`OpenClaw unavailable (health score: ${health.getScore('openclaw')})`)
    return null // Use fallback
  }

  return await executeWithTimeout(
    () => getOpenClawResponse(prompt),
    3000
  )
}
```

### Scenario 4: Learning from Failures

**Use Case:** Track errors for future optimization

```javascript
const learner = new ErrorLearningTracker()

async function executeWithLearning(model, prompt) {
  const startTime = Date.now()
  
  try {
    return await executeWithTimeout(
      () => agent(prompt, { model }),
      new WorkerTimeoutTracker().getTimeout(model)
    )
  } catch (err) {
    const failureId = Date.now().toString()
    learner.recordFailure({
      id: failureId,
      model,
      stage: 'worker',
      error: err.message
    })

    // Try recovery
    const fallback = getFallbackChain(model)[0].model
    try {
      const recovered = await agent(prompt, { model: fallback })
      learner.recordResolution(failureId, `fallback-to-${fallback}`, true)
      return recovered
    } catch (recoveryErr) {
      learner.recordResolution(failureId, `fallback-failed`, false)
      throw recoveryErr
    }
  }
}

// Later: examine what went wrong and adjust
const reliability = learner.getModelReliability('opus')
if (reliability.reliability < 0.8) {
  log(`⚠ Opus reliability low (${reliability.reliability}), prefer Sonnet`)
}
```

---

## Configuration Examples

### Conservative (High Reliability)

For critical operations where we need 100% success:

```javascript
const config = {
  timeouts: {
    default: 45000,
    arbiter: 60000
  },
  consensus: {
    minResults: 2,  // Require 2+ workers even if 3+ available
    preferredCount: 4
  },
  retry: {
    maxAttempts: 3,
    backoffMs: [100, 500, 2000]
  }
}
```

### Balanced (Default)

For most workflows:

```javascript
const config = {
  timeouts: {
    default: 30000,
    arbiter: 45000
  },
  consensus: {
    minResults: 1,  // Continue with 1+ result
    preferredCount: 3
  },
  retry: {
    maxAttempts: 2,
    backoffMs: [100, 500]
  }
}
```

### Optimized (Speed First)

For time-sensitive operations:

```javascript
const config = {
  timeouts: {
    default: 15000,
    arbiter: 20000
  },
  consensus: {
    minResults: 1,
    preferredCount: 2
  },
  retry: {
    maxAttempts: 1,
    backoffMs: []
  }
}
```

---

## Migration Checklist

When adding error recovery to an existing workflow:

- [ ] Import recovery utilities
- [ ] Add timeout wrappers to all external calls (agent, fetch, workflow)
- [ ] Implement health checks for optional services (OpenClaw, learning API)
- [ ] Add fallback chains for critical functions (arbiters)
- [ ] Switch from `Promise.all` to `Promise.allSettled` for parallel workers
- [ ] Use `gatherResultsWithPartialAcceptance` instead of requiring all results
- [ ] Add error logging at recovery points
- [ ] Test each recovery path (can disable services to simulate failures)
- [ ] Document timeouts in comments (why each timeout value)
- [ ] Add integration tests for recovery scenarios

---

## Testing Recovery Chains

### Unit Test Template

```javascript
describe('Recovery Integration', () => {
  test('worker timeout triggers fallback', async () => {
    const workers = [
      {
        label: 'Slow model',
        fn: () => new Promise(r => setTimeout(r, 50000)),
        retryable: true
      },
      {
        label: 'Fast model',
        fn: async () => ({ result: 'success' }),
        retryable: false
      }
    ]

    const result = await tryFallbackChain(workers)
    expect(result.result).toBe('success')
  })

  test('partial results accepted', async () => {
    const workers = [
      { model: 'a', fn: async () => ({ v: 1 }) },
      { model: 'b', fn: async () => { throw new Error() } },
      { model: 'c', fn: async () => ({ v: 3 }) }
    ]

    const result = await gatherResultsWithPartialAcceptance(workers, {
      minResults: 2
    })

    expect(result.results).toHaveLength(2)
    expect(result.coverage).toBeCloseTo(2/3)
  })

  test('insufficient results throws with details', async () => {
    const workers = [
      { model: 'a', fn: async () => { throw new Error() } }
    ]

    await expect(
      gatherResultsWithPartialAcceptance(workers, { minResults: 2 })
    ).rejects.toThrow(InsufficientResults)
  })
})
```

### Integration Test Template

```javascript
describe('Workflow with Recovery', () => {
  test('continues when service unavailable', async () => {
    // Mock service as unavailable
    jest.mock('openclaw', () => ({
      getVote: () => Promise.reject(new Error('ECONNREFUSED'))
    }))

    const result = await workflow('ai-consensus', { task: 'test' })
    expect(result.error).toBeUndefined()
    expect(result.consensus).toBeTruthy()
  })

  test('degrades gracefully under load', async () => {
    // Simulate slow models
    jest.spyOn(agent, 'default').mockImplementation(
      (prompt, opts) => new Promise(r => 
        setTimeout(() => r({ answer: 'ok' }), 40000)
      )
    )

    const result = await workflow('ai-consensus', {
      task: 'test',
      models: ['opus', 'sonnet', 'haiku']
    })

    expect(result.degradedCount).toBeGreaterThan(0)
  })
})
```

---

## Performance Impact

Adding recovery chains has minimal overhead:

| Component | Overhead | When |
|-----------|----------|------|
| Timeout wrapper | ~1ms | Every operation |
| Health check (cached) | 0ms | Cached result |
| Health check (real) | ~3ms | First check or after backoff |
| Fallback chain | 0-30s | On failure |
| Partial results aggregation | ~5ms | Gathering phase |

**Total expected impact: < 5% latency increase under normal conditions**

---

## Debugging Recovery Chains

### Enable verbose logging

```javascript
const log = (msg) => {
  console.log(`[Recovery] ${new Date().toISOString()}: ${msg}`)
}

// Pass to utilities
await tryFallbackChain(attempts, { logFn: log })
```

### Inspect recovery metrics

```javascript
const learner = new ErrorLearningTracker()
const metrics = learner.getMetrics()

console.log('Failure metrics:')
console.log(`  Total failures: ${metrics.totalFailures}`)
console.log(`  By stage:`, metrics.byStage)
console.log(`  By model:`, metrics.byModel)
console.log(`  Resolution rate: ${(metrics.resolutionRate * 100).toFixed(1)}%`)
```

### Trace recovery path

```javascript
// Add logging at each recovery step
log(`Worker ${model} starting (timeout: ${timeout}ms)`)
try {
  const result = await executeWithTimeout(fn, timeout)
  log(`  → Success`)
  return result
} catch (err) {
  log(`  → Failed: ${err.message}`)
  log(`  → Attempting recovery: ${recoveryStrategy}`)
  // attempt recovery
}
```

---

## Best Practices

1. **Always timeout external calls** - No unbounded waits

2. **Log at recovery points** - Make failures visible:
   ```javascript
   log(`Worker ${model} timeout after ${elapsed}ms, trying fallback`)
   ```

3. **Make degradation transparent** - Report to user:
   ```javascript
   if (coverage < 1.0) {
     log(`⚠ Degraded results (${results.length}/${expected}): ${failures}`)
   }
   ```

4. **Test failure paths** - Don't just test happy path:
   ```javascript
   // Disable service to test fallback
   process.env.OPENCLAW_ENABLED = 'false'
   ```

5. **Learn from failures** - Feed into model selection:
   ```javascript
   const reliability = learner.getModelReliability(model)
   if (reliability.reliability < threshold) {
     // Reduce preference for this model
   }
   ```

6. **Monitor recovery metrics** - Track what breaks:
   ```javascript
   // Periodic analysis
   const metrics = learner.getMetrics()
   if (metrics.byModel['opus'] > threshold) {
     log(`⚠ Opus failing frequently, reducing usage`)
   }
   ```

---

## Common Pitfalls

### ❌ Don't: Ignore timeouts
```javascript
// BAD: No timeout
const result = await agent(prompt, { model: 'opus' })
```

### ✅ Do: Always timeout
```javascript
// GOOD: Bounded wait
const result = await executeWithTimeout(
  () => agent(prompt, { model: 'opus' }),
  45000
)
```

### ❌ Don't: Fail on any worker error
```javascript
// BAD: All-or-nothing
const results = await Promise.all(workers.map(w => w.fn()))
```

### ✅ Do: Accept partial results
```javascript
// GOOD: Continue with subset
const { results } = await gatherResultsWithPartialAcceptance(workers, {
  minResults: 1
})
```

### ❌ Don't: Cascade error into degradation
```javascript
// BAD: Error breaks everything
const schema = userSchema // May be invalid
```

### ✅ Do: Degrade gracefully
```javascript
// GOOD: Fallback to safe schema
const schema = validateSchema(userSchema) || getMinimalSchema()
```

---

## Next Steps

1. **Review ERROR_RECOVERY_CHAIN.md** for architectural details
2. **Run recovery-chain-utils.test.js** to understand behavior
3. **Start with one workflow** (e.g., ai-consensus.js)
4. **Add timeouts first**, then health checks, then fallbacks
5. **Test each recovery path** with deliberate failures
6. **Monitor metrics** with ErrorLearningTracker
7. **Expand to other workflows** as patterns stabilize

---

## Support

For issues or questions:
1. Check test file for working examples
2. Review ERROR_RECOVERY_CHAIN.md for pattern details
3. Search workflows for existing recovery implementations
4. Check metrics: `ErrorLearningTracker().getMetrics()`
