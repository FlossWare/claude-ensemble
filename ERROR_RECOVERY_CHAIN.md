# Error Recovery Chain Design

A comprehensive architecture for graceful degradation, error handling, and recovery across the Claude Code global skills ecosystem.

## Overview

The error recovery chain implements a **layered resilience strategy** that catches errors at multiple stages and applies context-appropriate recovery mechanisms. Each layer has different recovery strategies and fall-through paths.

### Design Principles

1. **Fail-Safe by Default** - Errors don't cascade; each layer can recover independently
2. **Context-Aware Recovery** - Recovery strategy depends on error type, stage, and impact
3. **Transparent Degradation** - User gets results, possibly with reduced quality/coverage
4. **Learning & Adaptation** - Failures are tracked for model selection and future optimization
5. **Timeout-First** - Detect stalled operations before they accumulate (30s default)
6. **Circuit Breaker Pattern** - Temporarily disable failing services, retry after recovery window

---

## Layer Architecture

### Layer 1: Input Validation (Preventive)

**Purpose:** Catch errors before execution starts

**Mechanisms:**
```javascript
// Validate inputs with clear error messages
function validateInput(args) {
  const errors = [];
  
  if (!args.task) errors.push('task (string, required)');
  if (args.schema && typeof args.schema !== 'object') errors.push('schema (object, optional)');
  if (args.timeout && (typeof args.timeout !== 'number' || args.timeout < 1000)) 
    errors.push('timeout (number >= 1000ms, optional)');
  
  if (errors.length > 0) {
    throw new ValidationError(
      `Missing or invalid parameters: ${errors.join(', ')}`,
      { fields: errors, received: args }
    );
  }
}

// Sanitize user inputs to prevent injection
function sanitizeInput(input) {
  if (typeof input !== 'string') return input;
  // Remove shell metacharacters, SQL keywords in specific contexts
  return input.replace(/[;&|`$()\\]/g, '').trim();
}
```

**Recovery:** Reject with clear error message listing required fields.

---

### Layer 2: Timeout Protection (Preventive)

**Purpose:** Prevent indefinite hangs; detect stalled workers early

**Mechanisms:**
```javascript
async function executeWithTimeout(fn, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  
  try {
    return await Promise.race([
      fn(controller.signal),
      new Promise((_, reject) => 
        controller.signal.addEventListener('abort', () => 
          reject(new TimeoutError(`Operation exceeded ${timeoutMs}ms`))
        )
      )
    ]);
  } finally {
    clearTimeout(timeoutId);
  }
}

// Per-worker timeout tracking
class WorkerTimeoutTracker {
  constructor(defaultTimeout = 30000) {
    this.timeouts = new Map(); // model -> timeout
    this.defaultTimeout = defaultTimeout;
  }
  
  getTimeout(model) {
    // Slow models get more time
    const slowModels = { 'opus': 45000, 'gpt-4o': 45000 };
    return this.timeouts.get(model) || slowModels[model] || this.defaultTimeout;
  }
}
```

**Recovery:** Cancel operation, mark worker as slow/offline, use fallback.

---

### Layer 3: Model/Service Health Checks (Detective)

**Purpose:** Detect degraded or unavailable services before use

**Mechanisms:**
```javascript
class ServiceHealthCheck {
  constructor() {
    this.state = new Map(); // service -> { healthy, lastCheck, failCount }
  }
  
  async checkHealth(service, checkFn, fastFailMs = 3000) {
    const cached = this.state.get(service);
    
    // Circuit breaker: if recently failed, skip check
    if (cached && !this.shouldRetry(cached)) {
      return cached.healthy;
    }
    
    try {
      const result = await Promise.race([
        checkFn(),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Health check timeout')), fastFailMs)
        )
      ]);
      
      this.recordSuccess(service);
      return true;
    } catch (err) {
      this.recordFailure(service);
      return false;
    }
  }
  
  shouldRetry(state) {
    // Retry after exponential backoff: 30s, 2m, 5m, 10m
    const backoffs = [30000, 120000, 300000, 600000];
    const backoff = backoffs[Math.min(state.failCount, backoffs.length - 1)];
    return Date.now() - state.lastCheck > backoff;
  }
}

// OpenClaw health check example
async function checkOpenClawHealth() {
  const http = require('http');
  return new Promise((resolve) => {
    const req = http.request({ 
      hostname: 'localhost', 
      port: 18789, 
      path: '/api/status', 
      method: 'GET',
      timeout: 2000
    }, (res) => resolve(res.statusCode === 200));
    
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.end();
  });
}
```

**Recovery:** Use fallback service, disable optional features, degrade gracefully.

---

### Layer 4: Worker-Level Fallback (Reactive)

**Purpose:** When a worker fails, retry with different model

**Mechanisms:**
```javascript
async function executeWithWorkerFallback(model, task, context) {
  const fallbackSequence = getFallbackChain(model);
  
  for (const attempt of fallbackSequence) {
    try {
      return await executeWorker(attempt.model, task, context, {
        timeout: attempt.timeout
      });
    } catch (err) {
      log(`Worker ${attempt.model} failed: ${err.message}`);
      
      // Skip remaining retries on validation errors
      if (isValidationError(err)) throw err;
      
      // Continue to next fallback
      if (attempt.next) continue;
      throw err;
    }
  }
}

// Model-specific fallback chains
function getFallbackChain(model) {
  const chains = {
    'gpt-4o': [
      { model: 'gpt-4o', timeout: 45000 },
      { model: 'opus', timeout: 45000 },
      { model: 'sonnet', timeout: 30000, next: true }
    ],
    'opus': [
      { model: 'opus', timeout: 45000 },
      { model: 'sonnet', timeout: 30000 },
      { model: 'haiku', timeout: 20000, next: true }
    ],
    'sonnet': [
      { model: 'sonnet', timeout: 30000 },
      { model: 'haiku', timeout: 20000, next: true }
    ],
    'haiku': [
      { model: 'haiku', timeout: 20000, next: true }
    ]
  };
  
  return chains[model] || chains['sonnet'];
}
```

**Recovery:** Retry with model from fallback chain, possibly with reduced timeout.

---

### Layer 5: Partial Results (Adaptive)

**Purpose:** Accept incomplete results, continue with what we have

**Mechanisms:**
```javascript
async function gatherResultsWithPartialAcceptance(workers, schema, minResults = 1) {
  const results = [];
  const errors = [];
  const timeoutMs = 30000;
  
  const settled = await Promise.allSettled(
    workers.map(w => executeWithTimeout(w.fn, timeoutMs))
  );
  
  for (let i = 0; i < settled.length; i++) {
    const outcome = settled[i];
    
    if (outcome.status === 'fulfilled') {
      try {
        validateSchema(outcome.value, schema);
        results.push({ model: workers[i].model, value: outcome.value });
      } catch (err) {
        errors.push({ model: workers[i].model, error: err.message });
      }
    } else {
      errors.push({ model: workers[i].model, error: outcome.reason.message });
    }
  }
  
  // Require minimum results
  if (results.length < minResults) {
    throw new InsufficientResults(
      `Got ${results.length} valid results, need ≥${minResults}`,
      { results, errors }
    );
  }
  
  return { results, errors, coverage: results.length / workers.length };
}

// Report degradation to user
function reportDegradation(results, errors, expectedCount) {
  if (errors.length > 0) {
    const failedModels = errors.map(e => `${e.model}: ${e.error}`).join('; ');
    log(`⚠ Degraded consensus (${results.length}/${expectedCount}): ${failedModels}`);
  }
}
```

**Recovery:** Continue with subset of results, adjust consensus algorithm, report degradation.

---

### Layer 6: Arbiter Fallback (Critical)

**Purpose:** If primary arbiter unavailable, use fallback

**Mechanisms:**
```javascript
class ArbiterRotation {
  constructor() {
    this.rotationIndex = 0;
    // Primary order: fast + capable
    this.primaryChain = ['fable', 'opus', 'sonnet', 'gemini'];
    this.fallbackChain = ['haiku', 'gpt-4o'];
  }
  
  async getArbiter(health) {
    // Try primary chain first
    for (const arbiter of this.primaryChain) {
      if (health.isHealthy(arbiter)) {
        return arbiter;
      }
    }
    
    // Fall back to secondary chain
    for (const arbiter of this.fallbackChain) {
      if (health.isHealthy(arbiter)) {
        log(`⚠ Using fallback arbiter: ${arbiter}`);
        return arbiter;
      }
    }
    
    // Last resort: use cheapest available
    return 'haiku';
  }
}

// Handle arbiter failures
async function executeArbiterWithFallback(arbiter, prompt, schema) {
  try {
    return await executeWithTimeout(
      () => agent(prompt, { model: arbiter, json: schema }),
      45000 // Arbiters get more time
    );
  } catch (err) {
    log(`Arbiter ${arbiter} failed: ${err.message}`);
    
    // Try fallback
    const fallback = arbiter === 'fable' ? 'opus' : 'fable';
    return await agent(prompt, { model: fallback, json: schema });
  }
}
```

**Recovery:** Use fallback arbiter, report quality impact.

---

### Layer 7: Graceful Degradation (Strategic)

**Purpose:** Reduce scope/quality rather than fail completely

**Mechanisms:**
```javascript
// Scale back worker count on failures
class AdaptiveWorkerSelection {
  selectWorkers(availableModels, failureRate) {
    const targetCount = Math.ceil(availableModels.length * (1 - failureRate));
    
    if (targetCount < 1) {
      throw new Error(`No viable workers available`);
    }
    
    // Prefer faster/cheaper models as failures increase
    if (failureRate > 0.5) {
      return availableModels
        .sort((a, b) => this.modelSpeed(a) - this.modelSpeed(b))
        .slice(0, Math.max(1, targetCount));
    }
    
    return availableModels.slice(0, targetCount);
  }
  
  modelSpeed(model) {
    const speeds = { haiku: 1, sonnet: 2, opus: 3, 'gpt-4o': 4 };
    return speeds[model] || 2;
  }
}

// Skip expensive features on errors
function buildDegradedSchema(fullSchema, degradationLevel) {
  if (degradationLevel < 0.3) return fullSchema;
  
  // Level 1: Drop optional fields
  if (degradationLevel < 0.6) {
    const props = { ...fullSchema.properties };
    const required = fullSchema.required.filter(
      f => !isOptionalField(f)
    );
    return { ...fullSchema, properties: props, required };
  }
  
  // Level 2: Simplify to bare minimum
  return {
    type: 'object',
    properties: {
      answer: { type: 'string', description: 'Your answer' },
      confidence: { type: 'number', min: 0, max: 100 }
    },
    required: ['answer', 'confidence']
  };
}
```

**Recovery:** Reduce worker count, simplify schema, drop non-critical features.

---

### Layer 8: Learning & Feedback (Continuous)

**Purpose:** Track failures for future optimization

**Mechanisms:**
```javascript
class ErrorLearningTracker {
  constructor() {
    this.failures = []; // { timestamp, model, error, stage, resolved, resolution }
  }
  
  recordFailure(failure) {
    this.failures.push({
      timestamp: Date.now(),
      ...failure
    });
  }
  
  recordResolution(failureId, resolution, success) {
    const failure = this.failures.find(f => f.id === failureId);
    if (failure) {
      failure.resolved = true;
      failure.resolution = resolution;
      failure.success = success;
    }
  }
  
  // Generate insights for model selection
  getModelReliability(model, windowMs = 86400000) {
    const cutoff = Date.now() - windowMs;
    const recent = this.failures.filter(
      f => f.model === model && f.timestamp > cutoff
    );
    
    return {
      attempts: recent.length,
      failures: recent.filter(f => !f.success).length,
      reliability: 1 - (recent.filter(f => !f.success).length / recent.length || 0)
    };
  }
  
  // Export for performance-monitor
  getMetrics() {
    return {
      totalFailures: this.failures.length,
      byStage: groupBy(this.failures, f => f.stage),
      byModel: groupBy(this.failures, f => f.model),
      resolutionRate: this.failures.filter(f => f.resolved).length / this.failures.length
    };
  }
}

// Send learnings to learning system
async function sendLearning(error, stage, resolution) {
  try {
    await workflow('ai-extract-learning', {
      experience: `Error in ${stage}: ${error.message}`,
      resolution: resolution,
      tags: ['error-recovery', stage.toLowerCase()]
    });
  } catch (err) {
    // Learning is non-critical, don't fail if it's unavailable
    log(`Warning: Could not record learning: ${err.message}`);
  }
}
```

**Recovery:** Track for future improvement, adjust model selection probabilities.

---

## Recovery Strategy Map

| Error Stage | Error Type | Primary Recovery | Fallback | Timeout |
|---|---|---|---|---|
| **Input Validation** | Invalid schema | Reject with details | N/A | N/A |
| **Service Health** | Timeout (health check) | Skip check, use cached | Use fallback service | 3s |
| **Worker Execution** | Model timeout | Retry with next model | Use fallback chain | 30-45s |
| **Worker Execution** | Rate limit | Exponential backoff | Use different model | 1s + backoff |
| **Worker Execution** | Auth error | Fail validation | Report to user | N/A |
| **Worker Execution** | Malformed response | Validate & reject | Try next worker | N/A |
| **Consensus** | Insufficient results | Use subset + report | Degrade schema | N/A |
| **Arbiter** | Arbiter timeout | Use fallback arbiter | Use cheapest available | 45s |
| **Arbiter** | Arbiter validation error | Reject & report | Escalate to user | N/A |
| **Remote Execution** | SSH connection failed | Skip remote, use local | Continue without sync | 5s |
| **Learning API** | Unavailable | Continue, skip learning | Silent fail (non-critical) | 5s |

---

## Implementation Patterns

### Pattern 1: Try-Fallback Chain

```javascript
async function tryFallbackChain(attempts) {
  const errors = [];
  
  for (const attempt of attempts) {
    try {
      log(`Attempting: ${attempt.label}`);
      return await attempt.fn();
    } catch (err) {
      errors.push({ label: attempt.label, error: err.message });
      log(`  Failed: ${err.message}`);
      
      // Escalate non-retryable errors immediately
      if (!attempt.retryable) throw err;
    }
  }
  
  throw new AllAttemptsFailedError('All recovery attempts exhausted', { errors });
}

// Usage:
const result = await tryFallbackChain([
  {
    label: 'OpenClaw (local)',
    fn: () => getOpenClawWorkerVote(prompt),
    retryable: true
  },
  {
    label: 'Opus worker (fallback)',
    fn: () => agent(prompt, { model: 'opus' }),
    retryable: true
  },
  {
    label: 'Sonnet worker (final)',
    fn: () => agent(prompt, { model: 'sonnet' }),
    retryable: false // Last resort
  }
]);
```

### Pattern 2: Partial Results Aggregation

```javascript
async function aggregateWithPartialResults(workers, options) {
  const { minResults = 1, timeoutMs = 30000, maxErrors = 0.5 } = options;
  const results = [];
  const errors = [];
  
  const settled = await Promise.allSettled(
    workers.map(w => executeWithTimeout(w.fn, timeoutMs))
  );
  
  for (let i = 0; i < settled.length; i++) {
    if (settled[i].status === 'fulfilled') {
      results.push(settled[i].value);
    } else {
      errors.push(settled[i].reason.message);
    }
  }
  
  const errorRate = errors.length / workers.length;
  if (errorRate > maxErrors) {
    log(`⚠ High error rate (${Math.round(errorRate * 100)}%) - degrading quality`);
  }
  
  if (results.length < minResults) {
    throw new Error(
      `Insufficient results: got ${results.length}, need ≥${minResults}. ` +
      `Errors: ${errors.join('; ')}`
    );
  }
  
  return { results, errors, coverage: results.length / workers.length };
}
```

### Pattern 3: Health-Aware Selection

```javascript
async function selectBestModel(candidates, health) {
  // Score each model by health + speed
  const scores = candidates.map(model => ({
    model,
    healthScore: health.getScore(model), // 0-100
    speedScore: getSpeedScore(model),    // 0-100
    combined: (health.getScore(model) * 0.7) + (getSpeedScore(model) * 0.3)
  }));
  
  const best = scores.sort((a, b) => b.combined - a.combined)[0];
  
  if (best.combined < 30) {
    log(`⚠ All models degraded (best score: ${best.combined})`);
  }
  
  return best.model;
}
```

---

## Error Types & Handlers

### Custom Error Classes

```javascript
// Base error with context
class RecoveryError extends Error {
  constructor(message, context = {}) {
    super(message);
    this.name = this.constructor.name;
    this.context = context;
    this.stage = context.stage || 'unknown';
    this.recoverable = context.recoverable !== false;
  }
}

// Specific error types
class TimeoutError extends RecoveryError {}
class ValidationError extends RecoveryError {}
class InsufficientResults extends RecoveryError {}
class AllAttemptsFailedError extends RecoveryError {}
class RateLimitError extends RecoveryError {
  constructor(message, retryAfterMs) {
    super(message, { recoverable: true });
    this.retryAfterMs = retryAfterMs;
  }
}
class CircuitBreakerOpen extends RecoveryError {}
```

---

## Configuration & Tuning

### Recovery Configuration

```javascript
const RECOVERY_CONFIG = {
  // Timeouts
  timeouts: {
    default: 30000,
    healthCheck: 3000,
    arbiter: 45000,
    slowModels: { 'opus': 45000, 'gpt-4o': 45000 }
  },
  
  // Fallback chains
  fallbacks: {
    'gpt-4o': ['opus', 'sonnet', 'haiku'],
    'opus': ['sonnet', 'haiku'],
    'sonnet': ['haiku'],
  },
  
  // Minimum results for consensus
  consensus: {
    minResults: 1,
    preferredCount: 3,
    maxErrorRate: 0.5
  },
  
  // Circuit breaker
  circuitBreaker: {
    failureThreshold: 5,      // Fail count to trip breaker
    successThreshold: 2,      // Success count to close breaker
    windowMs: 60000,          // Evaluation window
    resetMs: 300000           // Time before retry (5 minutes)
  },
  
  // Retry strategy
  retry: {
    maxAttempts: 3,
    backoffMs: [100, 500, 2000],
    exponentialBase: 2
  },
  
  // Degradation triggers
  degradation: {
    errorRateThreshold: 0.5,  // Scale back workers if >50% fail
    minWorkers: 1,
    minArbiterConfidence: 0.6
  }
};
```

---

## Monitoring & Observability

### Key Metrics to Track

1. **Recovery Success Rate** - % of errors that resolved successfully
2. **Mean Time to Recovery (MTTR)** - Average recovery time by error type
3. **Fallback Activation** - How often each fallback chain is used
4. **Worker Reliability** - Success rate by model and stage
5. **Degradation Events** - When consensus quality drops
6. **Circuit Breaker Trips** - When services are temporarily disabled

### Logging Best Practices

```javascript
// Always log recovery attempts
log(`Recovery attempt 1/${maxAttempts}: ${strategy.label}`);
log(`  → Success: ${strategyWorked}`);

// Report degradation clearly
log(`⚠ Degraded consensus (2/3 workers): opus timeout, gpt-4o validation error`);

// Link to learning
log(`Recorded learning: error in ${stage}, recovery: ${resolution}`);

// Show final state
log(`Final result: ${results.length}/${expectedCount} workers, coverage: ${coverage}%`);
```

---

## Testing Recovery Chains

### Unit Test Pattern

```javascript
describe('Error Recovery Chain', () => {
  test('worker timeout triggers fallback', async () => {
    const slowWorker = () => new Promise(r => setTimeout(r, 50000));
    const fallback = jest.fn().mockResolvedValue({ answer: 'fallback' });
    
    const result = await executeWithWorkerFallback('slow-model', task, context);
    expect(fallback).toHaveBeenCalled();
    expect(result).toEqual({ answer: 'fallback' });
  });
  
  test('partial results accepted if > minResults', async () => {
    const workers = [
      { model: 'a', fn: async () => ({ v: 1 }) },
      { model: 'b', fn: async () => { throw new Error('fail'); } },
      { model: 'c', fn: async () => ({ v: 3 }) }
    ];
    
    const result = await aggregateWithPartialResults(workers, { minResults: 2 });
    expect(result.results).toHaveLength(2);
    expect(result.coverage).toEqual(2/3);
  });
  
  test('insufficient results throws with details', async () => {
    const workers = [
      { model: 'a', fn: async () => { throw new Error('fail'); } }
    ];
    
    await expect(aggregateWithPartialResults(workers, { minResults: 2 }))
      .rejects
      .toThrow(InsufficientResults);
  });
});
```

---

## Integration Points

### With ai-consensus.js

```javascript
// Add recovery wrapper
async function executeConsensusWithRecovery(args) {
  const health = new ServiceHealthCheck();
  
  try {
    // Check worker health first
    const workerModels = getWorkerModels()
      .filter(m => await health.checkHealth(`worker-${m}`, ...));
    
    // Execute with partial result acceptance
    const consensus = await executeConsensusWithPartialResults(
      workerModels,
      { minResults: Math.max(1, workerModels.length - 1) }
    );
    
    return consensus;
  } catch (err) {
    // Apply degradation strategy
    log(`Consensus failed: ${err.message}`);
    return applyDegradedConsensus(args, err);
  }
}
```

### With ai-consensus-refinement.js

```javascript
// Add refinement with error recovery
async function refineWithRecovery(workers, arbiter, roundNum) {
  try {
    return await executeArbiterWithFallback(
      arbiter,
      buildCritiquePrompt(workers),
      refinementSchema
    );
  } catch (err) {
    // If critique fails, return best result without refinement
    log(`Refinement round ${roundNum} failed, using unrefined result`);
    return selectBestResult(workers);
  }
}
```

---

## Future Enhancements

1. **Machine Learning-Based Recovery** - Predict optimal recovery strategy based on error pattern
2. **Adaptive Timeout Learning** - Auto-adjust timeouts per model based on historical latency
3. **Recovery Strategy A/B Testing** - Test multiple recovery paths and pick winners
4. **Failure Prediction** - Pre-emptively switch to fallback before timeout
5. **Distributed Health Checks** - Fleet-wide health monitoring with gossip protocol
6. **Recovery Metrics Dashboard** - Real-time visibility into recovery chain performance

---

## Summary

The error recovery chain provides **8 layers of resilience**:

1. **Input Validation** - Prevent bad requests
2. **Timeouts** - Detect hangs early
3. **Health Checks** - Know service state before use
4. **Worker Fallbacks** - Retry with different model
5. **Partial Results** - Continue with subset
6. **Arbiter Fallback** - Critical path redundancy
7. **Graceful Degradation** - Reduce scope not quality
8. **Learning** - Improve future decisions

Each layer is **independent**, making the system resilient to cascading failures. Users get results even when subsystems fail, with transparent reporting of degradation.
