# API Health Monitoring - Provider Availability Tracking

**Created:** 2026-06-28  
**File:** `monitoring/api-health-monitor.cjs`  
**Database:** PostgreSQL `learning` (aio-01:5433)  
**Schema:** `monitoring.api_health_status`, `monitoring.api_health_checks`

## Overview

API Health Monitoring runs lightweight health checks every 5 minutes to detect dead, degraded, or quota-exhausted API providers **before** they cause workflow failures. It tracks success rates over the last 20 attempts and auto-disables providers below 50% success, preventing wasted requests on broken endpoints.

**Problem Solved:**
- Free tier quota exhaustion (e.g., Google Gemini daily limits)
- API downtime (provider outages, maintenance windows)
- Network failures (transient connectivity issues)
- Authentication failures (expired keys, rate limits)

**Key Features:**
- Proactive detection (fails fast, not during critical workflows)
- Automatic recovery (providers re-enabled when health improves)
- Circuit breaker integration (disabled providers filtered from model selection)
- Historical tracking (20-check sliding window per provider)
- Minimal cost (lightweight "echo test" prompts)

---

## How It Works

### 1. Health Check Scheduler
Runs every **5 minutes** (configurable via `webhook-config.json`):

```javascript
const { startScheduler } = require('./monitoring/api-health-monitor.cjs');

// Start periodic health checks
const scheduler = startScheduler();

// Stop scheduler when needed
scheduler.stop();
```

### 2. Lightweight Test Prompt
Each check sends a minimal prompt (`"echo test"`) with 10-second timeout:

```javascript
const { executeHealthCheck } = require('./monitoring/api-health-monitor.cjs');

const result = await executeHealthCheck('anthropic');
// { success: true, response_time_ms: 342 }
// OR
// { success: false, response_time_ms: 10000, error: 'Health check timeout' }
```

### 3. Success Rate Calculation
Tracks last **20 attempts** per provider:

- **Success rate** = `successful_checks / total_checks` (over last 20 attempts)
- **Status levels:**
  - `healthy`: ≥75% success rate
  - `degraded`: 50-75% success rate
  - `disabled`: <50% success rate

### 4. Auto-Disable on Failure
When success rate drops below 50%, provider is automatically disabled:

```
[APIHealthMonitor] Provider google DISABLED (success rate: 35.0%)
```

Disabled providers are filtered out by circuit-breaker integration.

### 5. Automatic Re-Enable
When health improves (via ongoing checks), provider status automatically upgrades:

```
[APIHealthMonitor] Provider google degraded (success rate: 65.0%)
[APIHealthMonitor] Provider google healthy (success rate: 80.0%)
```

---

## Database Schema

### `monitoring.api_health_status` (Current Status)

| Column | Type | Description |
|--------|------|-------------|
| `provider` | VARCHAR(100) PRIMARY KEY | Provider name (anthropic, openai, google, etc.) |
| `success_rate` | NUMERIC(5,4) | Success rate over last 20 checks (0.00-1.00) |
| `total_checks` | INTEGER | Total checks performed (lifetime) |
| `successful_checks` | INTEGER | Total successful checks (lifetime) |
| `failed_checks` | INTEGER | Total failed checks (lifetime) |
| `status` | VARCHAR(20) | Current status (healthy, degraded, disabled) |
| `last_check` | TIMESTAMPTZ | Timestamp of last check |
| `last_success` | TIMESTAMPTZ | Timestamp of last successful check |
| `last_failure` | TIMESTAMPTZ | Timestamp of last failed check |
| `failure_reason` | TEXT | Error message from last failure |
| `metadata` | JSONB | Custom metadata |

### `monitoring.api_health_checks` (Historical Log)

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Unique check ID |
| `provider` | VARCHAR(100) | Provider name |
| `success` | BOOLEAN | Check success (true/false) |
| `response_time_ms` | INTEGER | Response time in milliseconds |
| `error_message` | TEXT | Error message (if failed) |
| `created_at` | TIMESTAMPTZ | Check timestamp |

**Index:** `idx_api_health_checks_provider_created` on `(provider, created_at DESC)` for fast history queries

---

## Configuration

### Default Configuration

```javascript
{
  check_interval_ms: 5 * 60 * 1000,        // 5 minutes
  health_check_timeout_ms: 10000,          // 10 seconds
  success_rate_threshold: 0.50,            // 50% success rate
  history_window: 20,                      // Track last 20 attempts
  test_prompt: 'echo test'                 // Lightweight test prompt
}
```

### Custom Configuration

Edit `monitoring/webhook-config.json`:

```json
{
  "thresholds": {
    "api_health": {
      "check_interval_ms": 300000,         // 5 minutes
      "success_rate_threshold": 0.60,      // 60% threshold (stricter)
      "history_window": 50                 // Track last 50 checks
    }
  }
}
```

---

## Usage

### Initialize Schema (One-Time Setup)

```javascript
const { initSchema } = require('./monitoring/api-health-monitor.cjs');

await initSchema();
// [APIHealthMonitor] Schema initialized
```

Creates:
- `monitoring.api_health_status` table
- `monitoring.api_health_checks` table
- Indexes for fast lookups

### Start Health Check Scheduler

```javascript
const { startScheduler } = require('./monitoring/api-health-monitor.cjs');

const scheduler = startScheduler();
// [APIHealthMonitor] Starting scheduler (interval: 300000ms)
// [APIHealthMonitor] Starting health checks...
// [APIHealthMonitor] Checking 4 providers: anthropic, openai, google, openrouter
// [APIHealthMonitor] Provider anthropic healthy (success rate: 100.0%)
// [APIHealthMonitor] Provider google DISABLED (success rate: 40.0%)
```

**Runs automatically in background. No manual intervention needed.**

### Query Health Status

```javascript
const { getHealthStatus } = require('./monitoring/api-health-monitor.cjs');

const status = await getHealthStatus();
console.log(status);
```

**Output:**
```javascript
[
  {
    provider: 'anthropic',
    success_rate: 1.0,
    success_rate_percent: '100.0',
    total_checks: 142,
    successful_checks: 142,
    failed_checks: 0,
    status: 'healthy',
    last_check: '2026-06-28T18:45:00Z',
    last_success: '2026-06-28T18:45:00Z',
    last_failure: null,
    failure_reason: null
  },
  {
    provider: 'google',
    success_rate: 0.35,
    success_rate_percent: '35.0',
    total_checks: 142,
    successful_checks: 50,
    failed_checks: 92,
    status: 'disabled',
    last_check: '2026-06-28T18:45:00Z',
    last_success: '2026-06-28T18:30:00Z',
    last_failure: '2026-06-28T18:45:00Z',
    failure_reason: 'Quota exceeded'
  }
]
```

### Get Provider Health History

```javascript
const { getHealthHistory } = require('./monitoring/api-health-monitor.cjs');

const history = await getHealthHistory('google', 10);
console.log(history);
```

**Output:**
```javascript
[
  { id: 1523, success: false, response_time_ms: 1250, error_message: 'Quota exceeded', created_at: '2026-06-28T18:45:00Z' },
  { id: 1522, success: false, response_time_ms: 1180, error_message: 'Quota exceeded', created_at: '2026-06-28T18:40:00Z' },
  { id: 1521, success: true, response_time_ms: 340, error_message: null, created_at: '2026-06-28T18:35:00Z' },
  // ... 7 more rows
]
```

### Get Provider Availability (For Circuit Breaker)

```javascript
const { getProviderAvailability } = require('./monitoring/api-health-monitor.cjs');

const { available, disabled } = await getProviderAvailability();
console.log('Available:', available);  // ['anthropic', 'openai', 'openrouter']
console.log('Disabled:', disabled);    // [{ provider: 'google', success_rate: 0.35, ... }]
```

### Manually Reset Provider Status

Use this after fixing provider issues (e.g., added new API key, quota reset):

```javascript
const { resetProviderStatus } = require('./monitoring/api-health-monitor.cjs');

await resetProviderStatus('google');
// [APIHealthMonitor] Reset status for provider: google
```

This immediately marks provider as `healthy` with 100% success rate. Next health check will validate.

### Execute Single Health Check (Testing)

```javascript
const { executeHealthCheck } = require('./monitoring/api-health-monitor.cjs');

const result = await executeHealthCheck('anthropic');
console.log(result);
// { success: true, response_time_ms: 342 }
```

---

## Integration with Circuit Breaker

### Automatic Provider Filtering

The health monitor extends `circuit-breaker.cjs` with provider-level filtering:

**Generated file:** `shared/circuit-breaker-provider-extension.cjs`

```javascript
const { filterAvailableModels } = require('./shared/circuit-breaker-provider-extension.cjs');

const models = ['anthropic/opus', 'google/gemini-pro', 'openai/gpt-4'];
const filtered = await filterAvailableModels(models);
// Returns: ['anthropic/opus', 'openai/gpt-4']
// (google filtered due to disabled status)
```

### Integration in Workflows

```javascript
const { getProviderAvailability } = require('./monitoring/api-health-monitor.cjs');
const { filterAvailableModels } = require('./shared/circuit-breaker-provider-extension.cjs');

// Get available models for consensus
const allModels = ['anthropic/opus', 'google/gemini-pro', 'openai/gpt-4', 'openrouter/meta-llama/llama-3-8b'];
const availableModels = await filterAvailableModels(allModels);

// Use only healthy providers
const workers = await parallel(availableModels.map(model => agent({
  name: `worker-${model}`,
  model: model,
  // ...
})));
```

**Prevents:**
- Wasting worker slots on dead providers
- Waiting for 10s timeout on disabled APIs
- Quota exhaustion errors mid-workflow

---

## Monitoring and Alerts

### PostgreSQL Query for Current Status

```sql
SELECT
  provider,
  ROUND(success_rate * 100, 1) || '%' AS success_rate,
  status,
  total_checks,
  successful_checks,
  failed_checks,
  last_check,
  failure_reason
FROM monitoring.api_health_status
ORDER BY success_rate DESC;
```

**Output:**
```
 provider   | success_rate | status   | total_checks | successful_checks | failed_checks | last_check           | failure_reason
------------+--------------+----------+--------------+-------------------+---------------+---------------------+----------------
 anthropic  | 100.0%       | healthy  | 142          | 142               | 0             | 2026-06-28 18:45:00 | NULL
 openai     | 95.5%        | healthy  | 142          | 136               | 6             | 2026-06-28 18:45:00 | NULL
 openrouter | 72.5%        | degraded | 142          | 103               | 39            | 2026-06-28 18:45:00 | NULL
 google     | 35.0%        | disabled | 142          | 50                | 92            | 2026-06-28 18:45:00 | Quota exceeded
```

### Recent Failures for Degraded Providers

```sql
SELECT
  provider,
  success,
  response_time_ms,
  error_message,
  created_at
FROM monitoring.api_health_checks
WHERE provider = 'google'
  AND success = FALSE
ORDER BY created_at DESC
LIMIT 10;
```

### Grafana Dashboard Metrics

**Panel 1: Provider Success Rate (Time Series)**
```sql
SELECT
  created_at AS time,
  provider,
  success::int AS value
FROM monitoring.api_health_checks
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at;
```

**Panel 2: Provider Status (Table)**
```sql
SELECT * FROM monitoring.api_health_status;
```

**Panel 3: Response Time Distribution (Histogram)**
```sql
SELECT
  response_time_ms,
  COUNT(*) AS frequency
FROM monitoring.api_health_checks
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY response_time_ms
ORDER BY response_time_ms;
```

---

## Provider Discovery

### Automatic Detection from Fleet Topology

Health monitor reads `shared/fleet-topology.js` to discover providers:

```javascript
// Example fleet-topology.js
module.exports = {
  workers: [
    { name: 'worker-1', model: 'anthropic/opus', provider: 'anthropic' },
    { name: 'worker-2', model: 'google/gemini-pro', provider: 'google' },
    { name: 'worker-3', model: 'openai/gpt-4', provider: 'openai' },
  ]
};
```

**Detected providers:** `anthropic`, `google`, `openai`

### Manual Provider List

If `fleet-topology.js` not found, defaults to:

```javascript
['anthropic', 'openai', 'google', 'openrouter']
```

---

## Common Scenarios

### Scenario 1: Google Free Tier Quota Exhausted

**Symptoms:**
- Google API calls return `429 Quota exceeded`
- Workflows timeout waiting for Google responses

**Health Monitor Response:**
1. Health check fails with "Quota exceeded"
2. After 10 consecutive failures (50% of 20-check window), status → `disabled`
3. Circuit breaker filters `google/*` models from selection
4. Workflows use remaining healthy providers (anthropic, openai)

**Recovery:**
- Wait 24 hours for quota reset
- Manually reset status: `resetProviderStatus('google')`
- OR let scheduler automatically re-enable after 10 successful checks

### Scenario 2: OpenRouter Intermittent Failures

**Symptoms:**
- OpenRouter has 60% success rate (network issues)
- Status: `degraded` (above 50% threshold, but below 75%)

**Health Monitor Response:**
1. Status marked as `degraded`
2. Provider still available (not disabled)
3. Circuit breaker allows usage but logs warning
4. If success rate drops to <50%, auto-disables

**Action:**
- Monitor `monitoring.api_health_checks` for error patterns
- Check OpenRouter status page
- If persistent, manually disable: `UPDATE monitoring.api_health_status SET status = 'disabled' WHERE provider = 'openrouter'`

### Scenario 3: Anthropic API Key Expired

**Symptoms:**
- Health check fails with `401 Unauthorized`
- All Anthropic API calls fail

**Health Monitor Response:**
1. Health check fails with "ANTHROPIC_API_KEY not set" (or 401 error)
2. After 10 failures, status → `disabled`
3. Workflows automatically fallback to other providers

**Recovery:**
1. Update API key: `export ANTHROPIC_API_KEY=sk-...`
2. Reset status: `resetProviderStatus('anthropic')`
3. Next health check validates new key

---

## Testing and Validation

### Run Manual Health Check

```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
node -e "
const { executeHealthCheck, recordHealthCheck } = require('./monitoring/api-health-monitor.cjs');
(async () => {
  const result = await executeHealthCheck('anthropic');
  console.log('Result:', result);
  await recordHealthCheck('anthropic', result);
})();
"
```

### Simulate Provider Failure

```bash
# Temporarily remove API key
unset ANTHROPIC_API_KEY

# Run health check
node -e "
const { runHealthChecks } = require('./monitoring/api-health-monitor.cjs');
(async () => {
  await runHealthChecks();
})();
"

# Check status
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT provider, status, success_rate, failure_reason FROM monitoring.api_health_status WHERE provider = 'anthropic';"
```

### Test Circuit Breaker Integration

```bash
node -e "
const { filterAvailableModels } = require('./shared/circuit-breaker-provider-extension.cjs');
(async () => {
  const models = ['anthropic/opus', 'google/gemini-pro', 'openai/gpt-4'];
  const filtered = await filterAvailableModels(models);
  console.log('Filtered models:', filtered);
})();
"
```

---

## Troubleshooting

### Health Checks Not Running

**Check scheduler status:**
```bash
ps aux | grep api-health-monitor
```

**Restart scheduler:**
```javascript
const { startScheduler } = require('./monitoring/api-health-monitor.cjs');
const scheduler = startScheduler();
```

### Database Connection Errors

**Verify PostgreSQL connection:**
```bash
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1;"
```

**Check environment variables:**
```bash
echo $PGHOST      # aio-01
echo $PGPORT      # 5433
echo $PGDATABASE  # learning
echo $PGUSER      # sfloess
```

### Provider Status Stuck as Disabled

**Check recent health checks:**
```sql
SELECT * FROM monitoring.api_health_checks
WHERE provider = 'google'
ORDER BY created_at DESC LIMIT 20;
```

**Manually reset:**
```javascript
const { resetProviderStatus } = require('./monitoring/api-health-monitor.cjs');
await resetProviderStatus('google');
```

### False Positives (Healthy Provider Marked Disabled)

**Adjust success rate threshold:**

Edit `monitoring/webhook-config.json`:
```json
{
  "thresholds": {
    "api_health": {
      "success_rate_threshold": 0.40  // Lower to 40%
    }
  }
}
```

**Increase history window:**
```json
{
  "thresholds": {
    "api_health": {
      "history_window": 50  // More samples = smoother rate
    }
  }
}
```

---

## Performance Considerations

### Health Check Cost

**Per check:**
- Prompt: `"echo test"` (2 tokens input)
- Expected output: 5-10 tokens
- **Total cost per check:** ~$0.0001 (Anthropic), $0.00005 (OpenRouter)

**Monthly cost (5-minute interval, 4 providers):**
- Checks per month: `(60 / 5) * 24 * 30 * 4 = 34,560 checks`
- Estimated cost: `34,560 * $0.0001 = $3.46/month`

**Optimization:**
- Increase interval to 10 minutes: `$1.73/month`
- Use only critical providers: `$0.87/month` (2 providers)

### Database Performance

**Indexes:**
- `api_health_status` primary key: O(1) lookups
- `api_health_checks` composite index: O(log n) history queries

**Query performance (100K rows):**
- Get provider status: <1ms
- Get last 20 checks: <5ms
- Filter available providers: <10ms

**Cleanup strategy:**

Retention policy (optional):
```sql
-- Delete checks older than 30 days
DELETE FROM monitoring.api_health_checks
WHERE created_at < NOW() - INTERVAL '30 days';
```

Add to cron (daily cleanup):
```bash
0 2 * * * psql -h aio-01 -p 5433 -U sfloess -d learning -c "DELETE FROM monitoring.api_health_checks WHERE created_at < NOW() - INTERVAL '30 days';"
```

---

## API Reference

### Functions

#### `initSchema()`
Initialize PostgreSQL schema (one-time setup).

**Returns:** `Promise<void>`

**Example:**
```javascript
await initSchema();
```

#### `executeHealthCheck(provider)`
Execute single health check for provider.

**Parameters:**
- `provider` (string): Provider name (`anthropic`, `openai`, `google`, `openrouter`)

**Returns:** `Promise<Object>` - `{ success: boolean, response_time_ms: number, error?: string }`

**Example:**
```javascript
const result = await executeHealthCheck('anthropic');
```

#### `runHealthChecks()`
Run health checks for all discovered providers.

**Returns:** `Promise<void>`

**Example:**
```javascript
await runHealthChecks();
```

#### `recordHealthCheck(provider, result)`
Record health check result and update status.

**Parameters:**
- `provider` (string): Provider name
- `result` (Object): Result from `executeHealthCheck()`

**Returns:** `Promise<void>`

**Example:**
```javascript
const result = await executeHealthCheck('anthropic');
await recordHealthCheck('anthropic', result);
```

#### `startScheduler()`
Start periodic health check scheduler.

**Returns:** `Object` - `{ stop: function }`

**Example:**
```javascript
const scheduler = startScheduler();
// Later: scheduler.stop();
```

#### `getHealthStatus()`
Get health status for all providers.

**Returns:** `Promise<Array<Object>>`

**Example:**
```javascript
const status = await getHealthStatus();
```

#### `getHealthHistory(provider, limit = 20)`
Get recent health check history for provider.

**Parameters:**
- `provider` (string): Provider name
- `limit` (number): Number of recent checks to return

**Returns:** `Promise<Array<Object>>`

**Example:**
```javascript
const history = await getHealthHistory('google', 10);
```

#### `getProviderAvailability()`
Get provider availability for circuit breaker.

**Returns:** `Promise<Object>` - `{ available: Array<string>, disabled: Array<Object> }`

**Example:**
```javascript
const { available, disabled } = await getProviderAvailability();
```

#### `resetProviderStatus(provider)`
Manually reset provider status to healthy.

**Parameters:**
- `provider` (string): Provider name

**Returns:** `Promise<void>`

**Example:**
```javascript
await resetProviderStatus('google');
```

#### `close()`
Close database connection pool.

**Returns:** `Promise<void>`

**Example:**
```javascript
await close();
```

---

## Related Documentation

- **Circuit Breaker:** `shared/circuit-breaker.cjs` - Request-level failure handling
- **Fleet Topology:** `shared/fleet-topology.js` - Worker and provider configuration
- **Webhook Configuration:** `monitoring/webhook-config.json` - Alert and threshold settings
- **Workflow Storage:** `shared/workflow-storage-adapter.js` - Workflow execution tracking

---

## Change Log

**2026-06-28:**
- Initial implementation (1,103 lines)
- PostgreSQL schema (api_health_status, api_health_checks)
- 5-minute health check scheduler
- Auto-disable at <50% success rate
- Circuit breaker integration (provider filtering)
- Provider discovery from fleet topology

---

## Future Enhancements

**Planned Features:**
1. **Adaptive Intervals:**
   - Increase check frequency when degraded (every 1 minute)
   - Decrease when healthy (every 10 minutes)

2. **Anomaly Detection:**
   - Alert on sudden success rate drops (>20% change)
   - Detect quota reset patterns (daily/weekly cycles)

3. **Multi-Region Support:**
   - Track provider health per region
   - Route to healthy regions automatically

4. **Cost Optimization:**
   - Cache health status for 1 minute (reduce DB queries)
   - Batch health checks (single API call tests multiple models)

5. **Advanced Metrics:**
   - P95/P99 response time tracking
   - Error category analysis (timeout vs auth vs quota)
   - Success rate trends (7-day moving average)

**Feedback welcome:** Open issues for feature requests or bug reports.
