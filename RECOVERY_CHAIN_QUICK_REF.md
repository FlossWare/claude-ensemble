# Error Recovery Chain - Quick Reference

**For detailed documentation, see ERROR_RECOVERY_CHAIN.md and RECOVERY_CHAIN_INTEGRATION.md**

---

## Import

```javascript
const {
  executeWithTimeout,
  WorkerTimeoutTracker,
  ServiceHealthCheck,
  tryFallbackChain,
  getFallbackChain,
  gatherResultsWithPartialAcceptance,
  AdaptiveWorkerSelection,
  ErrorLearningTracker,
  CircuitBreaker
} = require('./recovery-chain-utils.js')
```

---

## Common Patterns

### 1. Timeout Any Operation (3 lines)

```javascript
const result = await executeWithTimeout(
  () => agent(prompt, { model: 'opus' }),
  45000  // milliseconds
)
```

### 2. Health Check Service (5 lines)

```javascript
const health = new ServiceHealthCheck()
const isHealthy = await health.checkHealth('openclaw',
  () => fetch('http://localhost:18789/api/status')
)
if (!isHealthy) log(`Service degraded (score: ${health.getScore('openclaw')})`)
```

### 3. Fallback Chain (8 lines)

```javascript
const result = await tryFallbackChain([
  { label: 'GPT-4o', fn: () => agent(prompt, { model: 'gpt-4o' }), retryable: true },
  { label: 'Opus', fn: () => agent(prompt, { model: 'opus' }), retryable: true },
  { label: 'Sonnet', fn: () => agent(prompt, { model: 'sonnet' }), retryable: false }
])
```

### 4. Partial Results (6 lines)

```javascript
const { results, errors, coverage } = await gatherResultsWithPartialAcceptance(
  workers,  // array of { model, fn }
  { minResults: 1, timeoutMs: 30000 }
)
if (coverage < 1.0) log(`⚠ Degraded (${results.length}/${workers.length}): ${errors.map(e => e.error).join('; ')}`)
```

### 5. Track Failures (6 lines)

```javascript
const learner = new ErrorLearningTracker()
learner.recordFailure({ model: 'opus', stage: 'worker', error: 'timeout' })
const reliability = learner.getModelReliability('opus')
if (reliability.reliability < 0.8) log(`⚠ ${reliability.model} is unreliable`)
```

---

## Error Classes

| Error | When | Recoverable |
|-------|------|-------------|
| `TimeoutError` | Operation exceeded timeout | ✅ Yes |
| `ValidationError` | Invalid input/schema | ❌ No |
| `InsufficientResults` | Not enough workers succeeded | ✅ Yes |
| `AllAttemptsFailedError` | All fallback attempts failed | ❌ No |
| `RateLimitError` | Service rate limiting | ✅ Yes (with backoff) |
| `CircuitBreakerOpen` | Service temporarily disabled | ✅ Yes (after reset window) |

---

## Timeouts per Model

| Model | Timeout |
|-------|---------|
| opus, gpt-4o | 45s |
| fable, sonnet, gemini | 30s |
| haiku | 20s |
| Health checks | 3s |
| Arbiters | 45s |

---

## Fallback Chains

```javascript
// GPT-4o → Opus → Sonnet
// Opus → Sonnet → Haiku
// Sonnet → Haiku
// Haiku → (no fallback)
// Fable → Opus → Sonnet
// Gemini → Fable → Sonnet
```

Get programmatically:
```javascript
const chain = getFallbackChain('opus')
// [{model: 'opus', timeout: 45000}, {model: 'sonnet', timeout: 30000}, ...]
```

---

## Circuit Breaker Config

```javascript
const breaker = new CircuitBreaker({
  failureThreshold: 5,      // failures to trip
  successThreshold: 2,      // successes to close
  windowMs: 60000,          // evaluation window
  resetMs: 300000           // time before retry (5 min)
})

await breaker.execute('service', async () => {
  // Your code
})
```

---

## Adaptive Worker Selection

```javascript
const selection = new AdaptiveWorkerSelection()

// Scale workers based on failure rate
const workers = selection.selectWorkers(
  ['opus', 'sonnet', 'haiku', 'gpt-4o'],
  0.5  // 50% failure rate → scale down
)
```

---

## Health Check State Machine

```
        ✓ success
        ↓
    CLOSED ←─────────────── HALF-OPEN
        ↑                       ↑
        └─── failures ──→ OPEN ──┘
             (threshold)    (backoff)
```

Backoff windows: 30s → 2m → 5m → 10m

---

## Degradation Levels

```javascript
const { degradationLevel } = result
// 0.0 = perfect (all workers succeeded)
// 0.33 = degraded (2/3 workers succeeded)
// 0.5 = significantly degraded (1/2 workers succeeded)
// > 0.5 = severely degraded (minority succeeded)

// Adjust confidence based on degradation:
result.confidence *= (1 - degradationLevel)
```

---

## Logging

**Always log at recovery points:**

```javascript
// Worker failure
log(`Worker ${model} failed: ${error.message}`)

// Fallback attempt
log(`Attempting fallback: ${fallbackModel}`)

// Degradation
log(`⚠ Degraded consensus (${results.length}/${expected}): ${failures}`)

// Recovery success
log(`Recovered via ${recoveryStrategy}`)
```

---

## Testing

```javascript
// Simulate timeout
await executeWithTimeout(
  () => new Promise(r => setTimeout(r, 50000)),
  100  // Will timeout
)

// Simulate failure
const chain = [
  { label: 'fail', fn: () => { throw new Error('x') }, retryable: true },
  { label: 'succeed', fn: async () => ({ ok: true }), retryable: false }
]
const result = await tryFallbackChain(chain)  // Returns { ok: true }

// Simulate partial results
const workers = [
  { model: 'a', fn: async () => ({ v: 1 }) },
  { model: 'b', fn: async () => { throw new Error() } },
  { model: 'c', fn: async () => ({ v: 3 }) }
]
const res = await gatherResultsWithPartialAcceptance(workers, { minResults: 2 })
// result.results.length === 2, result.coverage === 2/3
```

---

## Integration Checklist (Per Workflow)

- [ ] Import recovery-chain-utils.js
- [ ] Add timeout to agent() calls
- [ ] Add health check for optional services
- [ ] Switch Promise.all() to gatherResultsWithPartialAcceptance()
- [ ] Add fallback chain for arbiters
- [ ] Log at recovery points
- [ ] Test failure scenarios
- [ ] Monitor with ErrorLearningTracker
- [ ] Document timeouts in code

---

## Performance

| Operation | Overhead |
|-----------|----------|
| Timeout check | ~1ms |
| Health check (cached) | 0ms |
| Health check (real) | ~3ms |
| Fallback (on failure) | 0-30s |
| Partial results | ~5ms |
| **Total overhead** | **< 5%** |

---

## Configuration Presets

**Conservative** (critical operations):
```javascript
minResults: 2, maxAttempts: 3, backoffs: [100, 500, 2000]
```

**Balanced** (default):
```javascript
minResults: 1, maxAttempts: 2, backoffs: [100, 500]
```

**Optimized** (time-sensitive):
```javascript
minResults: 1, maxAttempts: 1, backoffs: []
```

---

## Metrics Export

```javascript
const learner = new ErrorLearningTracker()
const metrics = learner.getMetrics()

console.log(metrics)
// {
//   totalFailures: 42,
//   resolvedCount: 40,
//   resolutionRate: 0.95,
//   byStage: { worker: 30, arbiter: 5, health: 7 },
//   byModel: { opus: 15, sonnet: 12, haiku: 10, gpt4o: 5 }
// }
```

---

## When to Use Each Utility

| Utility | Use When |
|---------|----------|
| `executeWithTimeout` | Calling any external service |
| `WorkerTimeoutTracker` | Tracking worker performance over time |
| `ServiceHealthCheck` | Using optional services (OpenClaw, APIs) |
| `tryFallbackChain` | Critical paths (arbiters) need fallbacks |
| `gatherResultsWithPartialAcceptance` | Consensus with multiple workers |
| `AdaptiveWorkerSelection` | Degrading gracefully under load |
| `ErrorLearningTracker` | Feeding metrics back to model selection |
| `CircuitBreaker` | Protecting against cascading failures |

---

## Troubleshooting

**Workers timing out?**
- Increase timeout in WorkerTimeoutTracker
- Or use explicit timeout: `executeWithTimeout(fn, 60000)`

**Insufficient results?**
- Lower minResults requirement
- Or improve worker health with health checks

**Circuit breaker stuck open?**
- Check resetMs (default 5 min)
- Or call breaker.reset(service) manually

**Not logging recovery?**
- Pass logFn to tryFallbackChain: `{ logFn: console.log }`
- Or inspect ErrorLearningTracker metrics

**High false positives from health checks?**
- Increase fastFailMs (default 3s)
- Or tune backoff windows

---

## Examples

### Example 1: Consensus with Recovery

```javascript
const workers = modelList.map(model => ({
  model,
  fn: () => executeWithTimeout(
    () => agent(prompt, { model }),
    new WorkerTimeoutTracker().getTimeout(model)
  )
}))

const { results, coverage } = await gatherResultsWithPartialAcceptance(workers, {
  minResults: Math.max(1, Math.ceil(workers.length / 2))
})

const consensusResult = consensus(results)
consensusResult.quality = coverage
```

### Example 2: Arbiter with Fallback

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

### Example 3: Learning from Failures

```javascript
const learner = new ErrorLearningTracker()

async function executeAndLearn(model, prompt) {
  try {
    return await executeWithTimeout(
      () => agent(prompt, { model }),
      new WorkerTimeoutTracker().getTimeout(model)
    )
  } catch (err) {
    learner.recordFailure({ model, stage: 'worker', error: err.message })
    throw err
  }
}

// Later: check reliability
const reliability = learner.getModelReliability('opus')
log(`Opus: ${(reliability.reliability * 100).toFixed(1)}% reliable`)
```

---

## More Info

- **Architecture:** ERROR_RECOVERY_CHAIN.md
- **Integration Guide:** RECOVERY_CHAIN_INTEGRATION.md
- **Test Examples:** recovery-chain-utils.test.js
- **Summary:** RECOVERY_CHAIN_SUMMARY.md
