# Rate Limit Manager - Free API Throttling

**Created:** 2026-06-28  
**Location:** `shared/rate-limit-manager.cjs`  
**Database:** PostgreSQL `learning` on aio-01  
**Schema:** `monitoring.rate_limits`, `monitoring.rate_limit_requests`

## Overview

Rate Limit Manager prevents HTTP 429 (Too Many Requests) errors when using free API tiers with strict rate limits. It tracks requests per provider using a sliding 60-second window and auto-throttles when approaching limits, ensuring maximum throughput without exhausting quotas.

**Key Features:**
- Sliding window request tracking (60-second precision)
- Per-provider rate limiting (Groq, Perplexity, OpenRouter models)
- Auto-throttling with intelligent wait times
- Database-backed (PostgreSQL with automatic cleanup)
- Graceful degradation (fail-open on database errors)
- Zero-config integration with weighted voting system

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  1. Pre-Flight Check                                │
│     checkRateLimit('groq')                          │
│     ├─ Count requests in last 60 seconds            │
│     ├─ If count >= limit - buffer (28/30):          │
│     │  ├─ Calculate wait time until oldest expires  │
│     │  ├─ Sleep(wait_time + 100ms)                  │
│     │  └─ Increment throttled_count                 │
│     └─ Return { allowed: true, throttled: false }   │
│                                                      │
│  2. Make API Call                                   │
│     const result = await callAPI()                  │
│                                                      │
│  3. Record Request                                  │
│     recordRequest('groq', success=true)             │
│     ├─ Insert into rate_limit_requests              │
│     └─ Update rate_limits summary                   │
│                                                      │
│  4. Automatic Cleanup (every 10 minutes)            │
│     DELETE requests older than 1 hour               │
└─────────────────────────────────────────────────────┘
```

### Sliding Window Algorithm

Traditional fixed-window counters can allow burst traffic:
```
Fixed Window (WRONG):
00:00-00:59 → 30 requests
01:00-01:59 → 30 requests
Problem: 60 requests in 1 second at boundary (00:59 + 01:00)
```

Sliding window (this implementation):
```
Sliding Window (CORRECT):
At any moment, count requests in [now - 60s, now]
11:30:00 → Count 11:29:00 to 11:30:00 (exactly 30 requests max)
11:30:01 → Count 11:29:01 to 11:30:01 (oldest request expires)
```

## Configuration

### Per-Provider Limits

```javascript
const RATE_LIMITS = {
  // Free tier limits
  'groq': { rpm: 30, rph: 1800, buffer: 2 },           // Groq free tier
  'perplexity': { rpm: 0.083, rph: 5, buffer: 1 },     // 5 requests/hour

  // OpenRouter models (free tier)
  'openrouter/anthropic/claude-3-haiku': { rpm: 10, rph: 100, buffer: 1 },
  'openrouter/google/gemini-flash-1.5': { rpm: 15, rph: 200, buffer: 2 },
  'openrouter/meta-llama/llama-3.1-8b-instruct': { rpm: 20, rph: 300, buffer: 2 },

  // Generic OpenRouter (conservative default)
  'openrouter': { rpm: 10, rph: 100, buffer: 2 },

  // Local models (no limit)
  'ollama': { rpm: Infinity, rph: Infinity, buffer: 0 },

  // Generic (default for unknown providers)
  'default': { rpm: 60, rph: 3600, buffer: 5 },
};
```

**Parameters:**
- `rpm`: Requests per minute
- `rph`: Requests per hour (unused currently, reserved for hourly limits)
- `buffer`: Safety margin (throttle at limit - buffer)

**Example:** Groq limit = 30 rpm, buffer = 2 → Throttle at 28 requests/minute

## Database Schema

### Table: `monitoring.rate_limits` (Summary Stats)

```sql
CREATE TABLE monitoring.rate_limits (
  provider VARCHAR(200) PRIMARY KEY,
  requests_last_minute INT DEFAULT 0,
  requests_last_hour INT DEFAULT 0,
  last_reset TIMESTAMPTZ DEFAULT NOW(),
  last_request TIMESTAMPTZ,
  total_requests BIGINT DEFAULT 0,
  throttled_count INT DEFAULT 0,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Fields:**
- `provider`: Provider name (groq, perplexity, openrouter/model)
- `total_requests`: Lifetime request count
- `throttled_count`: Number of times throttled
- `last_request`: Timestamp of most recent request
- `metadata`: Arbitrary JSON metadata

### Table: `monitoring.rate_limit_requests` (Sliding Window)

```sql
CREATE TABLE monitoring.rate_limit_requests (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(200) NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  success BOOLEAN DEFAULT TRUE,
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_rlr_provider_timestamp
ON monitoring.rate_limit_requests(provider, timestamp DESC);
```

**Fields:**
- `provider`: Provider name
- `timestamp`: Request timestamp (for sliding window)
- `success`: Whether request succeeded
- `metadata`: Additional context (optional)

**Auto-Cleanup:** Records older than 1 hour are deleted every 10 minutes.

## API Reference

### Core Functions

#### `checkRateLimit(provider, options)`

Pre-flight check before making API call. Blocks if rate limit exceeded.

**Parameters:**
- `provider` (string): Provider name (groq, perplexity, openrouter/model)
- `options` (object):
  - `throwOnLimit` (boolean): Throw error instead of waiting (default: false)

**Returns:** Promise<Object>
```javascript
{
  allowed: true,           // Always true (blocks until allowed)
  wait_ms: 2500,          // Milliseconds waited (0 if no wait)
  current_count: 28,      // Requests in current window
  limit: 30,              // Provider limit
  throttled: false        // Whether throttling occurred
}
```

**Example:**
```javascript
const { checkRateLimit } = require('./rate-limit-manager.cjs');

// Blocks until allowed
await checkRateLimit('groq');
// ... make API call ...
```

#### `recordRequest(provider, success, metadata)`

Record a request after API call completes.

**Parameters:**
- `provider` (string): Provider name
- `success` (boolean): Whether request succeeded (default: true)
- `metadata` (object): Additional metadata (optional)

**Returns:** Promise<void>

**Example:**
```javascript
const { recordRequest } = require('./rate-limit-manager.cjs');

try {
  const result = await callGroqAPI();
  await recordRequest('groq', true, { model: 'llama-3.1-70b', tokens: 500 });
} catch (err) {
  await recordRequest('groq', false, { error: err.message });
  throw err;
}
```

### Statistics Functions

#### `getRateLimitStats()`

Get rate limit statistics for all providers.

**Returns:** Promise<Array<Object>>
```javascript
[
  {
    provider: 'groq',
    total_requests: 1543,
    throttled_count: 12,
    current_window_count: 18,
    limit: 30,
    utilization_percent: '60.0',
    last_request: '2026-06-28T14:32:10Z'
  },
  // ...
]
```

**Example:**
```javascript
const { getRateLimitStats } = require('./rate-limit-manager.cjs');

const stats = await getRateLimitStats();
console.table(stats);
```

#### `getRequestCount(provider)`

Get current request count in sliding window (last 60 seconds).

**Parameters:**
- `provider` (string): Provider name

**Returns:** Promise<number>

**Example:**
```javascript
const count = await getRequestCount('groq');
console.log(`Groq: ${count}/30 requests in last 60s`);
```

#### `getTimeUntilReset(provider)`

Get milliseconds until rate limit window resets (oldest request expires).

**Parameters:**
- `provider` (string): Provider name

**Returns:** Promise<number> (milliseconds)

**Example:**
```javascript
const waitMs = await getTimeUntilReset('groq');
console.log(`Wait ${(waitMs / 1000).toFixed(1)}s until Groq rate limit resets`);
```

### Utility Functions

#### `filterAvailableProviders(providers)`

Filter list of providers to only those that can accept requests now (not throttled).

**Parameters:**
- `providers` (Array<string>): List of provider names

**Returns:** Promise<Array<string>>

**Example:**
```javascript
const { filterAvailableProviders } = require('./rate-limit-manager.cjs');

const all = ['groq', 'perplexity', 'openrouter/claude-3-haiku'];
const available = await filterAvailableProviders(all);
// Returns only providers below rate limit
```

#### `getRateLimitConfig(provider)`

Get rate limit configuration for a provider (rpm, rph, buffer).

**Parameters:**
- `provider` (string): Provider name

**Returns:** Object `{ rpm, rph, buffer }`

**Example:**
```javascript
const config = getRateLimitConfig('groq');
// { rpm: 30, rph: 1800, buffer: 2 }
```

#### `cleanupOldRequests()`

Manually trigger cleanup of old request records (older than 1 hour).

**Returns:** Promise<number> (records deleted)

**Example:**
```javascript
const deleted = await cleanupOldRequests();
console.log(`Deleted ${deleted} old request records`);
```

### Lifecycle Functions

#### `initializeDatabase()`

Initialize database tables (idempotent). Called automatically on module load.

**Returns:** Promise<void>

#### `close()`

Close database connection pool. Call when shutting down application.

**Returns:** Promise<void>

**Example:**
```javascript
process.on('SIGTERM', async () => {
  const { close } = require('./rate-limit-manager.cjs');
  await close();
  process.exit(0);
});
```

## Integration Patterns

### Pattern 1: Basic Usage (Manual)

```javascript
const { checkRateLimit, recordRequest } = require('./shared/rate-limit-manager.cjs');

async function callGroqAPI(prompt) {
  // Pre-flight check (blocks if rate limited)
  await checkRateLimit('groq');

  try {
    const result = await fetch('https://api.groq.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${process.env.PERSONAL_GROQ_API_KEY}` },
      body: JSON.stringify({ model: 'llama-3.1-70b', messages: [{ role: 'user', content: prompt }] })
    });

    await recordRequest('groq', true);
    return await result.json();

  } catch (err) {
    await recordRequest('groq', false, { error: err.message });
    throw err;
  }
}
```

### Pattern 2: Integrated with Weighted Voting (Automatic)

Rate limit manager is automatically used by `weighted-voting.cjs`:

```javascript
// In weighted-voting.cjs
const { checkRateLimit, recordRequest } = require('./rate-limit-manager.cjs');

async function executeModel(model, prompt) {
  const provider = getProviderFromModel(model); // e.g., 'groq'

  // Auto-throttle if needed
  await checkRateLimit(provider);

  try {
    const result = await callModel(model, prompt);
    await recordRequest(provider, true);
    return result;
  } catch (err) {
    await recordRequest(provider, false);
    throw err;
  }
}
```

### Pattern 3: Provider Selection with Rate Limit Awareness

```javascript
const { filterAvailableProviders } = require('./shared/rate-limit-manager.cjs');

async function selectBestProvider(allProviders) {
  // Filter out rate-limited providers
  const available = await filterAvailableProviders(allProviders);

  if (available.length === 0) {
    throw new Error('All providers rate limited');
  }

  // Select best available provider (e.g., by quality, cost, etc.)
  return selectByQuality(available);
}
```

### Pattern 4: Monitoring Dashboard

```javascript
const { getRateLimitStats } = require('./shared/rate-limit-manager.cjs');

async function displayRateLimitDashboard() {
  const stats = await getRateLimitStats();

  console.log('\n=== Rate Limit Dashboard ===\n');
  stats.forEach(s => {
    const bar = '█'.repeat(Math.floor(s.utilization_percent / 5));
    console.log(
      `${s.provider.padEnd(30)} ${s.current_window_count}/${s.limit} [${bar.padEnd(20)}] ${s.utilization_percent}%`
    );
    console.log(`  Total: ${s.total_requests} requests, Throttled: ${s.throttled_count} times`);
  });
}

// Run every minute
setInterval(displayRateLimitDashboard, 60000);
```

## When To Use

### Automatic Usage (Recommended)

Rate limit manager is integrated into:
- `weighted-voting.cjs` (automatic pre-flight checks)
- `circuit-breaker.cjs` (failure tracking)
- Multi-AI consensus workflows

**No manual intervention required** - just use these systems normally.

### Manual Usage (Advanced)

Use directly when:
- Building custom API wrappers
- Implementing new providers
- Testing rate limit behavior
- Building monitoring dashboards

## Performance Characteristics

### Latency

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| `checkRateLimit()` (no throttle) | 1-5ms | Single DB query |
| `checkRateLimit()` (throttled) | Variable | Sleep until window resets |
| `recordRequest()` | 1-3ms | Single INSERT |
| `getRateLimitStats()` | 10-50ms | N queries (N = providers) |
| `cleanupOldRequests()` | 5-20ms | DELETE with index |

### Database Load

- **Writes:** 1 INSERT per API call (~50-200/hour typical)
- **Reads:** 1 SELECT per API call (fast, indexed)
- **Cleanup:** 1 DELETE every 10 minutes (low overhead)
- **Storage:** ~100 bytes/request, auto-purged after 1 hour

**Example:** 1000 API calls/hour = 100 KB storage, 2000 DB queries/hour (well within PostgreSQL capacity)

## Error Handling

### Graceful Degradation

Rate limit manager **fails open** on database errors:

```javascript
// If database unreachable:
checkRateLimit('groq')  // Returns { allowed: true, wait_ms: 0 }
recordRequest('groq')   // Logs error, continues

// Application continues working (unthrottled)
```

**Rationale:** Better to occasionally hit rate limits than block all requests on DB failure.

### Database Reconnection

PostgreSQL connection pool auto-reconnects on transient failures:

```javascript
pool.on('error', (err) => {
  console.error('[RateLimitManager] PostgreSQL pool error:', err.message);
  // Pool will attempt reconnection automatically
});
```

### Manual Error Recovery

```javascript
const { initializeDatabase, close } = require('./rate-limit-manager.cjs');

try {
  await initializeDatabase();
} catch (err) {
  console.error('Failed to initialize rate limit manager:', err);
  // Fallback to unthrottled mode
}
```

## Monitoring and Debugging

### Check Current Status

```bash
# Get stats for all providers
node -e "require('./shared/rate-limit-manager.cjs').getRateLimitStats().then(console.table)"

# Check specific provider
node -e "require('./shared/rate-limit-manager.cjs').getRequestCount('groq').then(c => console.log('Groq:', c))"
```

### Database Queries

```sql
-- Current window counts
SELECT provider, COUNT(*) as requests_last_60s
FROM monitoring.rate_limit_requests
WHERE timestamp >= NOW() - INTERVAL '60 seconds'
GROUP BY provider
ORDER BY requests_last_60s DESC;

-- Summary stats
SELECT * FROM monitoring.rate_limits ORDER BY total_requests DESC;

-- Recent requests
SELECT provider, timestamp, success
FROM monitoring.rate_limit_requests
ORDER BY timestamp DESC
LIMIT 20;

-- Throttling frequency
SELECT provider, throttled_count, total_requests,
       (throttled_count::float / NULLIF(total_requests, 0) * 100) as throttle_percent
FROM monitoring.rate_limits
ORDER BY throttled_count DESC;
```

### Enable Debug Logging

```javascript
// Set environment variable
process.env.DEBUG = 'rate-limit-manager';

// Or modify code temporarily
console.log(`[RateLimitManager] Current count: ${currentCount}/${limit}`);
```

## Troubleshooting

### Problem: Excessive Throttling

**Symptom:** Frequent "Rate limit approaching, waiting..." messages

**Diagnosis:**
```javascript
const stats = await getRateLimitStats();
const groq = stats.find(s => s.provider === 'groq');
console.log(`Groq utilization: ${groq.utilization_percent}%`);
console.log(`Throttled ${groq.throttled_count} times`);
```

**Solutions:**
1. Increase buffer to throttle earlier: `{ rpm: 30, buffer: 5 }`
2. Add more providers to distribute load
3. Upgrade to paid tier with higher limits
4. Implement request batching/caching

### Problem: Rate Limit Still Hit Despite Throttling

**Symptom:** HTTP 429 errors even with rate limit manager

**Possible Causes:**
1. **Multiple processes:** Each process has separate rate limit tracking
2. **Clock skew:** Database server time != application server time
3. **Provider changed limits:** Update `RATE_LIMITS` config
4. **Concurrent requests:** Multiple workers calling same provider simultaneously

**Solutions:**
1. Use single orchestrator process (current architecture)
2. Sync clocks with NTP
3. Check provider docs, adjust limits
4. Add mutex/semaphore for concurrent control

### Problem: Database Connection Errors

**Symptom:** "PostgreSQL pool error" in logs

**Diagnosis:**
```bash
# Check PostgreSQL is running
systemctl status postgresql-15.service

# Check network connectivity
ping aio-01
nc -zv aio-01 5433

# Check database exists
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1"
```

**Solutions:**
1. Restart PostgreSQL: `systemctl restart postgresql-15.service`
2. Check firewall: `firewall-cmd --list-all`
3. Verify credentials: `echo $PGPASSWORD`
4. Fall back to local SQLite (requires code modification)

### Problem: Old Requests Not Cleaned Up

**Symptom:** `monitoring.rate_limit_requests` table growing indefinitely

**Diagnosis:**
```sql
SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
FROM monitoring.rate_limit_requests;
```

**Solutions:**
1. Check cleanup is running: `grep "Cleaned up" logs/*.log`
2. Manually trigger: `node -e "require('./shared/rate-limit-manager.cjs').cleanupOldRequests()"`
3. Restart application (cleanup runs every 10 min after start)

## Testing

### Unit Tests

```javascript
const { checkRateLimit, recordRequest, cleanupOldRequests } = require('./shared/rate-limit-manager.cjs');

async function testRateLimit() {
  console.log('Testing rate limit manager...');

  // Test 1: No throttling below limit
  const check1 = await checkRateLimit('groq');
  console.assert(check1.allowed === true, 'Should allow below limit');
  console.assert(check1.throttled === false, 'Should not throttle');

  // Test 2: Throttling at limit
  for (let i = 0; i < 30; i++) {
    await recordRequest('test-provider', true);
  }
  const check2 = await checkRateLimit('test-provider');
  console.assert(check2.throttled === true, 'Should throttle at limit');

  // Test 3: Cleanup
  const deleted = await cleanupOldRequests();
  console.log(`Deleted ${deleted} old requests`);

  console.log('All tests passed');
}

testRateLimit().catch(console.error);
```

### Integration Tests

```javascript
async function testGroqIntegration() {
  const { checkRateLimit, recordRequest } = require('./shared/rate-limit-manager.cjs');

  for (let i = 0; i < 50; i++) {
    await checkRateLimit('groq');
    console.log(`Request ${i + 1}/50 sent`);
    await recordRequest('groq', true);
    await new Promise(r => setTimeout(r, 100)); // 100ms between requests
  }

  // Should complete without hitting rate limit
}
```

## Configuration Examples

### Conservative (Enterprise)

Minimize risk of rate limit errors:

```javascript
const RATE_LIMITS = {
  'groq': { rpm: 30, rph: 1800, buffer: 10 },  // Throttle at 20/30
  'perplexity': { rpm: 0.083, rph: 5, buffer: 2 },  // Throttle at 3/5
};
```

### Aggressive (Development)

Maximize throughput, accept occasional 429s:

```javascript
const RATE_LIMITS = {
  'groq': { rpm: 30, rph: 1800, buffer: 0 },  // Use full quota
  'perplexity': { rpm: 0.083, rph: 5, buffer: 0 },
};
```

### Hybrid (Recommended)

Balance throughput vs reliability:

```javascript
const RATE_LIMITS = {
  'groq': { rpm: 30, rph: 1800, buffer: 2 },  // 93% utilization
  'perplexity': { rpm: 0.083, rph: 5, buffer: 1 },  // 80% utilization
};
```

## Migration Guide

### Migrating from Fixed-Window Counter

If you have existing rate limiting code:

**Before:**
```javascript
let requestCount = 0;
setInterval(() => { requestCount = 0 }, 60000);

async function callAPI() {
  if (requestCount >= 30) {
    throw new Error('Rate limit exceeded');
  }
  requestCount++;
  // ... make call ...
}
```

**After:**
```javascript
const { checkRateLimit, recordRequest } = require('./shared/rate-limit-manager.cjs');

async function callAPI() {
  await checkRateLimit('groq');
  // ... make call ...
  await recordRequest('groq', true);
}
```

### Migrating from In-Memory Tracking

**Before (in-memory, lost on restart):**
```javascript
const requestLog = [];

async function checkLimit() {
  const recent = requestLog.filter(t => t > Date.now() - 60000);
  if (recent.length >= 30) {
    throw new Error('Rate limit');
  }
  requestLog.push(Date.now());
}
```

**After (persistent, survives restarts):**
```javascript
const { checkRateLimit, recordRequest } = require('./shared/rate-limit-manager.cjs');

await checkRateLimit('groq');
// ... call API ...
await recordRequest('groq', true);
```

## Advanced Usage

### Custom Provider Configuration

Add new provider at runtime:

```javascript
const { RATE_LIMITS } = require('./shared/rate-limit-manager.cjs');

RATE_LIMITS['custom-api'] = { rpm: 100, rph: 6000, buffer: 5 };
```

### Per-Model Limits (OpenRouter)

```javascript
// Different limits per model
RATE_LIMITS['openrouter/anthropic/claude-3-opus'] = { rpm: 5, rph: 50, buffer: 1 };
RATE_LIMITS['openrouter/anthropic/claude-3-haiku'] = { rpm: 20, rph: 200, buffer: 2 };
```

### Dynamic Buffer Adjustment

```javascript
const { checkRateLimit } = require('./shared/rate-limit-manager.cjs');

async function adaptiveCheckRateLimit(provider) {
  const hourOfDay = new Date().getHours();
  const isPeakHours = hourOfDay >= 9 && hourOfDay <= 17;

  // More conservative during peak hours
  const buffer = isPeakHours ? 5 : 2;
  RATE_LIMITS[provider].buffer = buffer;

  return await checkRateLimit(provider);
}
```

### Burst Protection

```javascript
async function checkBurstProtection(provider, maxBurst = 10) {
  const count = await getRequestCount(provider);
  
  if (count >= maxBurst) {
    throw new Error(`Burst limit exceeded: ${count}/${maxBurst} requests in last 60s`);
  }
  
  await checkRateLimit(provider);
}
```

## Best Practices

1. **Always record requests:** Call `recordRequest()` after every API call (success or failure)
2. **Check limits early:** Call `checkRateLimit()` before expensive operations
3. **Use provider filtering:** `filterAvailableProviders()` for load balancing
4. **Monitor stats:** Regularly check `getRateLimitStats()` for trends
5. **Set appropriate buffers:** Start with buffer=2, increase if hitting limits
6. **Handle errors gracefully:** Rate limit manager fails open on DB errors
7. **Test limits:** Use unit tests to verify throttling behavior
8. **Document custom configs:** Add comments when adding new providers

## Related Components

- **weighted-voting.cjs** - Uses rate limit manager for pre-flight checks
- **circuit-breaker.cjs** - Tracks failures alongside rate limits
- **multi-model-router.py** - Integrates rate limit awareness (future)
- **monitoring.rate_limits** - PostgreSQL table for rate limit stats
- **fleet-topology.js** - Provider configuration and selection

## Future Enhancements

- Hourly limit tracking (currently only per-minute)
- Token-based rate limiting (track input/output tokens, not just requests)
- Predictive throttling (ML-based rate limit prediction)
- Multi-region support (different limits per region)
- Grafana dashboard integration
- Alert thresholds (notify when utilization > 80%)
- Rate limit sharing across distributed workers

## References

- Groq API Limits: https://console.groq.com/docs/rate-limits
- OpenRouter Free Tier: https://openrouter.ai/docs/limits
- PostgreSQL pgvector: https://github.com/pgvector/pgvector
- Sliding Window Algorithm: https://en.wikipedia.org/wiki/Sliding_window_protocol

## Support

**Questions or Issues?**
- Check logs: `tail -f logs/rate-limit-manager.log`
- View stats: `node -e "require('./shared/rate-limit-manager.cjs').getRateLimitStats().then(console.table)"`
- Database queries: `psql -h aio-01 -p 5433 -U sfloess -d learning`

**Contributing:**
- Add new providers to `RATE_LIMITS` config
- Report rate limit changes from providers
- Submit improvements via pull request
