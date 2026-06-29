# Error Handling Specification

**Location:** `mcp-servers/fleet-orchestrator/lib/`
**Components:** `retry.js`, `circuit-breaker.js`, `fallback-strategy.js`

---

## 1. Retry Policy

### Overview

All transient failures are retried with exponential backoff and full jitter. The retry wrapper (`withRetry`) is the first line of defense before circuit breakers or fallback strategies are engaged.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `maxRetries` | 3 | Maximum retry attempts (total attempts = maxRetries + 1) |
| `backoffMs` | 1000 | Base delay between retries (ms) |
| `backoffMultiplier` | 2 | Multiplier applied per retry |
| `maxBackoffMs` | 30000 | Maximum backoff cap (ms) |
| `jitter` | true | Apply full jitter to prevent thundering herd |
| `timeoutMs` | null | Per-attempt timeout (null = no timeout) |
| `retryableErrors` | null | Custom filter function: `(error) => boolean` |
| `onRetry` | null | Callback on each retry: `(error, attempt, delay) => void` |

### Backoff Schedule (without jitter)

| Attempt | Delay |
|---|---|
| 1st retry | 1000ms |
| 2nd retry | 2000ms |
| 3rd retry | 4000ms |
| 4th retry (if configured) | 8000ms |

### Backoff with Full Jitter

When `jitter: true`, each delay is `random(0, min(maxBackoffMs, backoffMs * 2^attempt))`. This distributes retry load uniformly and prevents thundering herd when many workers fail simultaneously.

### Retryable Errors (default)

**By error code:**
- `ECONNRESET`, `ECONNREFUSED`, `ETIMEDOUT`, `ENOTFOUND`, `EPIPE`, `EAI_AGAIN`, `ERR_SOCKET_TIMEOUT`

**By HTTP status:**
- 408 (Request Timeout)
- 429 (Too Many Requests)
- 500 (Internal Server Error)
- 502 (Bad Gateway)
- 503 (Service Unavailable)
- 504 (Gateway Timeout)

**By message pattern:**
- `/rate.?limit|too many requests|throttl/i`
- `/timeout|timed?\s*out/i`
- `/ECONNR|ENOTFOUND|EPIPE|socket hang up/i`

### Non-Retryable Errors

These errors are NOT retried (they throw `RetryExhaustedError` immediately):
- 400 Bad Request (validation error)
- 401 Unauthorized (invalid credentials)
- 403 Forbidden (insufficient permissions)
- 404 Not Found (resource does not exist)
- 422 Unprocessable Entity (schema error)

### Usage Example

```javascript
const { withRetry } = require('./retry');

const { result, attempts, totalDurationMs } = await withRetry(
  () => callProvider(prompt),
  {
    maxRetries: 3,
    backoffMs: 1000,
    backoffMultiplier: 2,
    onRetry: (err, attempt, delay) => {
      console.log(`Retry ${attempt} after ${delay}ms: ${err.message}`);
    }
  }
);
```

---

## 2. Circuit Breaker

### Overview

The circuit breaker prevents cascading failures by tracking error rates per worker and fast-failing calls to unhealthy workers. It follows the standard three-state model.

### State Machine

```
         success                    failure >= threshold
  ┌──── CLOSED ────┐           ┌──── CLOSED ──────────── OPEN
  │   (normal)     │           │   (counting)           (reject)
  │                │           │                          │
  │  failure       │           │                          │
  │  (count++)     │           │                          │ resetTimeoutMs
  └────────────────┘           │                          │ elapsed
                               │                          v
                               │                      HALF_OPEN
                               │                      (probe: 1 call)
                               │                          │
                               │    success               │ failure
                               └──────────────────────────┘
                                     -> CLOSED              -> OPEN
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `failureThreshold` | 5 | Consecutive failures before opening the circuit |
| `resetTimeoutMs` | 30000 | Time in OPEN state before allowing a probe (ms) |
| `successThreshold` | 1 | Successes in HALF_OPEN needed to close the circuit |
| `halfOpenMaxConcurrent` | 1 | Maximum concurrent probe calls in HALF_OPEN |
| `onStateChange` | null | Callback: `(workerId, oldState, newState) => void` |
| `onFailure` | null | Callback: `(workerId, error, circuitStatus) => void` |
| `onSuccess` | null | Callback: `(workerId, circuitStatus) => void` |

### Per-Worker Tracking

Each worker has its own independent circuit. This means:
- Worker A failing does not affect Worker B's circuit
- A fleet of 8 workers can have different circuit states simultaneously
- Manual trip/reset is available per worker or globally

### State Behavior

**CLOSED (normal operation):**
- All requests pass through
- Failures increment the counter
- At `failureThreshold` failures, transitions to OPEN
- Successes decrement the failure count by 1 (gradual recovery)

**OPEN (rejecting requests):**
- All requests are immediately rejected with `CircuitOpenError`
- After `resetTimeoutMs` elapses, transitions to HALF_OPEN
- No timer is set; the check happens on the next call attempt

**HALF_OPEN (probing):**
- Allows `halfOpenMaxConcurrent` calls through as probes
- If the probe succeeds (`successThreshold` times), transitions to CLOSED
- If the probe fails, transitions back to OPEN immediately

### Usage Example

```javascript
const { CircuitBreaker } = require('./circuit-breaker');

const breaker = new CircuitBreaker({
  failureThreshold: 5,
  resetTimeoutMs: 30000,
  onStateChange: (workerId, oldState, newState) => {
    console.log(`Worker ${workerId}: ${oldState} -> ${newState}`);
  }
});

try {
  const result = await breaker.execute('worker-1', () => callWorker());
} catch (error) {
  if (error.name === 'CircuitOpenError') {
    // Worker is unhealthy, use fallback
  }
}
```

---

## 3. Fallback Decision Tree

### Error Classification

Every error is classified into one of these categories:

| Category | Trigger Conditions | Example |
|---|---|---|
| `AUTH_ERROR` | 401, 403, "invalid api key" | Expired API token |
| `RATE_LIMIT` | 429, "rate limit", "quota" | Provider throttling |
| `VALIDATION_ERROR` | 400, 422, "schema", "bad request" | Malformed prompt |
| `NETWORK_ERROR` | ECONNRESET, ETIMEDOUT, "socket hang up" | DNS failure |
| `WORKER_ERROR` | "ssh", "oom", "killed" | Worker node down |
| `PROVIDER_ERROR` | 500+, "model not found", "overloaded" | API outage |
| `UNKNOWN_ERROR` | Everything else | Unhandled exception |

### Decision Tree by Error Category

```
Error occurs
  |
  v
Classify error category
  |
  +-- RATE_LIMIT --------> Try next provider
  |                          -> Try next worker
  |                          -> Degrade quality
  |                          -> Execute locally
  |
  +-- AUTH_ERROR ---------> Try next provider (auth is per-provider)
  |                          -> Try next worker
  |                          -> Execute locally
  |
  +-- PROVIDER_ERROR -----> Retry same provider (may be transient)
  |                          -> Try next provider
  |                          -> Try next worker
  |                          -> Execute locally
  |
  +-- NETWORK_ERROR ------> Try next worker (different network path)
  |                          -> Retry same provider
  |                          -> Try next provider
  |                          -> Execute locally
  |
  +-- WORKER_ERROR -------> Try next worker
  |                          -> Try next provider
  |                          -> Execute locally
  |
  +-- VALIDATION_ERROR ---> Degrade quality (simpler prompt)
  |                          -> FAIL (not recoverable by switching)
  |
  +-- UNKNOWN_ERROR ------> Retry same provider
                              -> Try next provider
                              -> Try next worker
                              -> Degrade quality
                              -> Execute locally
```

### Provider Priority (default)

1. `anthropic` - Claude Sonnet 4, Claude Haiku 4
2. `openai` - GPT-4o, GPT-4o-mini
3. `google` - Gemini 2.0 Flash, Gemini 2.5 Pro
4. `openrouter` - Meta Llama 3 70B Instruct

### Fallback Actions

| Action | Description | When Used |
|---|---|---|
| `RETRY_SAME_PROVIDER` | Retry the same provider/worker | Transient 5xx, network blip |
| `TRY_NEXT_PROVIDER` | Switch to the next provider in priority order | Auth failure, rate limit, provider down |
| `TRY_NEXT_WORKER` | Route to a different fleet worker | Worker OOM, SSH failure, network issue |
| `EXECUTE_LOCALLY` | Run on the orchestrator node itself | All workers unavailable |
| `DEGRADE_QUALITY` | Use simpler prompt or smaller model | Validation errors, last resort |
| `FAIL` | All options exhausted | No providers, no workers, not recoverable |

### Usage Example

```javascript
const { gracefulFallback } = require('./fallback-strategy');

const decision = gracefulFallback(error, {
  currentProvider: 'anthropic',
  currentWorker: 'server-01',
  triedProviders: ['anthropic'],
  triedWorkers: ['server-01'],
  localExecutionAvailable: true,
});

// decision = {
//   action: 'TRY_NEXT_PROVIDER',
//   category: 'RATE_LIMIT',
//   nextProvider: 'openai',
//   nextWorker: 'server-02',
//   recommendation: "Switch to provider 'openai' (models: gpt-4o, gpt-4o-mini).",
//   exhausted: false,
// }
```

---

## 4. Error Codes and Meanings

### Custom Error Classes

| Error Class | Module | Meaning |
|---|---|---|
| `RetryExhaustedError` | retry.js | All retry attempts failed |
| `RetryTimeoutError` | retry.js | Individual attempt exceeded `timeoutMs` |
| `CircuitOpenError` | circuit-breaker.js | Worker circuit is open, call rejected |

### RetryExhaustedError Properties

| Property | Type | Description |
|---|---|---|
| `name` | string | Always `'RetryExhaustedError'` |
| `message` | string | Human-readable summary |
| `attempts` | Object[] | Array of attempt records with timing and errors |
| `lastError` | Error/string | The error from the final attempt |

### CircuitOpenError Properties

| Property | Type | Description |
|---|---|---|
| `name` | string | Always `'CircuitOpenError'` |
| `workerId` | string | The worker whose circuit is open |
| `remainingMs` | number | Milliseconds until the circuit enters HALF_OPEN |

### HTTP Status Code Mapping

| Status | Category | Retryable? | Fallback Action |
|---|---|---|---|
| 400 | VALIDATION_ERROR | No | DEGRADE_QUALITY |
| 401 | AUTH_ERROR | No | TRY_NEXT_PROVIDER |
| 403 | AUTH_ERROR | No | TRY_NEXT_PROVIDER |
| 404 | UNKNOWN_ERROR | No | TRY_NEXT_PROVIDER |
| 408 | NETWORK_ERROR | Yes | RETRY_SAME_PROVIDER |
| 422 | VALIDATION_ERROR | No | DEGRADE_QUALITY |
| 429 | RATE_LIMIT | Yes* | TRY_NEXT_PROVIDER |
| 500 | PROVIDER_ERROR | Yes | RETRY_SAME_PROVIDER |
| 502 | PROVIDER_ERROR | Yes | TRY_NEXT_PROVIDER |
| 503 | PROVIDER_ERROR | Yes | TRY_NEXT_PROVIDER |
| 504 | PROVIDER_ERROR | Yes | TRY_NEXT_PROVIDER |

*429 is retryable via the retry module, but the fallback strategy recommends switching providers immediately since rate limits are per-provider.

---

## 5. Integration Pattern

### Combined Usage (retry + circuit breaker + fallback)

```javascript
const { withRetry } = require('./retry');
const { CircuitBreaker } = require('./circuit-breaker');
const { gracefulFallback, FallbackStrategy } = require('./fallback-strategy');

const breaker = new CircuitBreaker({ failureThreshold: 5, resetTimeoutMs: 30000 });
const strategy = new FallbackStrategy({
  workers: ['server-01', 'server-02', 'server-03'],
});

async function executeWithResilience(task, workerId, provider) {
  const triedProviders = [];
  const triedWorkers = [];
  let currentWorker = workerId;
  let currentProvider = provider;

  while (true) {
    try {
      // Layer 1: Circuit breaker check
      const result = await breaker.execute(currentWorker, async () => {
        // Layer 2: Retry with backoff
        const { result } = await withRetry(
          () => callProvider(currentProvider, task),
          { maxRetries: 2, backoffMs: 500 }
        );
        return result;
      });
      return result;
    } catch (error) {
      // Layer 3: Fallback decision
      triedProviders.push(currentProvider);
      triedWorkers.push(currentWorker);

      const decision = gracefulFallback(error, {
        currentProvider,
        currentWorker,
        triedProviders,
        triedWorkers,
      }, strategy);

      if (decision.exhausted) {
        throw new Error(`All fallbacks exhausted: ${decision.recommendation}`);
      }

      // Apply the decision
      if (decision.nextProvider) currentProvider = decision.nextProvider;
      if (decision.nextWorker) currentWorker = decision.nextWorker;
    }
  }
}
```

---

## 6. Configuration Recommendations

### Development Environment

```javascript
{
  maxRetries: 1,
  backoffMs: 100,
  failureThreshold: 3,
  resetTimeoutMs: 5000,
}
```

### Production Environment

```javascript
{
  maxRetries: 3,
  backoffMs: 1000,
  backoffMultiplier: 2,
  maxBackoffMs: 30000,
  failureThreshold: 5,
  resetTimeoutMs: 30000,
  successThreshold: 1,
}
```

### High-Throughput Environment

```javascript
{
  maxRetries: 2,
  backoffMs: 500,
  backoffMultiplier: 1.5,
  maxBackoffMs: 10000,
  jitter: true,
  failureThreshold: 10,
  resetTimeoutMs: 15000,
  halfOpenMaxConcurrent: 3,
}
```
