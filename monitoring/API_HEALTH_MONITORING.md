# API Health Monitoring System

**Created:** 2026-06-28  
**Status:** Production Ready (12/12 tests passing)

## Overview

Automatic health monitoring for API providers with provider-level circuit breaking.

- **Health checks:** Every 5 minutes (configurable)
- **Success tracking:** Last 20 attempts per provider
- **Auto-disable:** Providers with <50% success rate
- **Degraded status:** 50-75% success rate warning
- **Integration:** Works with circuit-breaker.cjs and weighted-voting.cjs

## Quick Start

```javascript
const { startScheduler, getHealthStatus } = require('./monitoring/api-health-monitor.cjs');

// Start periodic health checks
const scheduler = startScheduler();

// Get current status
const status = await getHealthStatus();
console.log(status);

// Stop scheduler (if needed)
scheduler.stop();
```

## Database Schema

Tables created in `monitoring` schema on PostgreSQL (aio-01:5433):

- `api_health_status` - Current provider state
- `api_health_checks` - Historical check results (rolling window)
- `provider_health_summary` - Materialized view (optional)

## Status Values

- **healthy:** Success rate > 75%
- **degraded:** Success rate 50-75% (warning)
- **disabled:** Success rate < 50% (auto-disabled)

## API Reference

### Health Check Execution

```javascript
const { executeHealthCheck, recordHealthCheck } = require('./monitoring/api-health-monitor.cjs');

// Execute health check
const result = await executeHealthCheck('anthropic');
// => { success: true, response_time_ms: 250 }

// Record result
await recordHealthCheck('anthropic', result);
```

### Query Status

```javascript
// Get all provider statuses
const statuses = await getHealthStatus();
// => [{ provider: 'anthropic', success_rate: 0.95, status: 'healthy', ... }]

// Get health history
const history = await getHealthHistory('anthropic', 20);
// => [{ success: true, response_time_ms: 250, created_at: ... }, ...]

// Get provider availability (for circuit breaker)
const { available, disabled } = await getProviderAvailability();
// => { available: ['anthropic', 'openai'], disabled: [{ provider: 'google', success_rate: 0.35, ... }] }
```

### Manual Reset

```javascript
// Re-enable a disabled provider
await resetProviderStatus('google');
```

## Circuit Breaker Integration

The health monitor extends `circuit-breaker.cjs` with provider-level filtering:

```javascript
const { getCircuitBreaker } = require('./shared/circuit-breaker.cjs');
const circuitBreaker = getCircuitBreaker();

// Filter models by provider availability
const models = ['anthropic/opus', 'google/gemini', 'openai/gpt-4o'];
const available = await circuitBreaker.filterAvailableModels(models);
// => ['anthropic/opus', 'openai/gpt-4o'] (if google disabled)
```

This is automatically used by `weighted-voting.cjs` in PRIORITY 0 filtering.

## SQL Queries

```sql
-- Current status
SELECT provider, status, success_rate, last_check, failure_reason
FROM monitoring.api_health_status
ORDER BY success_rate DESC;

-- Recent failures
SELECT provider, error_message, created_at
FROM monitoring.api_health_checks
WHERE success = false
ORDER BY created_at DESC
LIMIT 20;

-- Provider history
SELECT
  success,
  response_time_ms,
  error_message,
  created_at
FROM monitoring.api_health_checks
WHERE provider = 'anthropic'
ORDER BY created_at DESC
LIMIT 20;
```

## Configuration

Default config (can override via `monitoring/webhook-config.json`):

```javascript
{
  "thresholds": {
    "api_health": {
      "check_interval_ms": 300000,        // 5 minutes
      "health_check_timeout_ms": 10000,   // 10 seconds
      "success_rate_threshold": 0.50,     // 50% threshold
      "history_window": 20,               // Track last 20 checks
      "test_prompt": "echo test"          // Lightweight test
    }
  }
}
```

## Testing

Run the test suite:

```bash
node monitoring/api-health-monitor.test.cjs
```

Test scenarios:
- Schema initialization
- Health check execution
- Success/failure recording
- Auto-disable logic (<50% success)
- Degraded status (50-75% success)
- Provider availability queries
- Manual reset
- Circuit breaker integration

**Current status:** 12/12 tests passing (100%)

## Migration

Database migration file: `db/migrations/001_api_health_monitoring.sql`

Apply manually:
```bash
psql -h aio-01 -p 5433 -U sfloess -d learning -f db/migrations/001_api_health_monitoring.sql
```

## Production Deployment

### Option 1: Standalone Scheduler

```javascript
// Start in background process
const { startScheduler } = require('./monitoring/api-health-monitor.cjs');
const scheduler = startScheduler();

// Runs every 5 minutes automatically
```

### Option 2: Integrate with Existing Cron

```javascript
// In your cron job (every 5 minutes)
const { runHealthChecks } = require('./monitoring/api-health-monitor.cjs');
await runHealthChecks();
```

### Option 3: On-Demand Checks

```javascript
// Run health checks on-demand (e.g., before critical workflows)
const { runHealthChecks } = require('./monitoring/api-health-monitor.cjs');
await runHealthChecks();
```

## Monitoring

Check logs for provider status changes:

```bash
# Health check runs
grep "APIHealthMonitor" your-app.log

# Provider disabled events
grep "DISABLED" your-app.log

# Provider degraded warnings
grep "degraded" your-app.log
```

## Files

- `monitoring/api-health-monitor.cjs` - Main implementation (693 LOC)
- `monitoring/api-health-monitor.test.cjs` - Test suite (295 LOC)
- `db/migrations/001_api_health_monitoring.sql` - Database schema (77 LOC)
- `shared/circuit-breaker-provider-extension.cjs` - Circuit breaker extension (38 LOC)
- `shared/circuit-breaker.cjs` - Modified to support getCircuitBreaker()

**Total:** 1,103 lines of code

## Architecture

```
┌─────────────────────────────────────────┐
│  API Health Monitor (5 min intervals)  │
│  ├─ Discover providers (fleet-topology) │
│  ├─ Execute lightweight checks          │
│  ├─ Record results (PostgreSQL)         │
│  └─ Update status (healthy/degraded/    │
│     disabled)                            │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  PostgreSQL (aio-01:5433)               │
│  ├─ monitoring.api_health_status        │
│  └─ monitoring.api_health_checks        │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Circuit Breaker Integration            │
│  ├─ getCircuitBreaker()                 │
│  └─ filterAvailableModels()             │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Weighted Voting (PRIORITY 0)           │
│  ├─ Filter votes from disabled providers│
│  └─ Prevent routing to failed APIs      │
└─────────────────────────────────────────┘
```

## Next Steps

1. **Deploy to production:** Integrate with main orchestration system
2. **Add Grafana dashboard:** Visualize provider health trends
3. **Webhook notifications:** Alert on provider disabled events
4. **Cost tracking integration:** Correlate failures with cost spikes
5. **Predictive alerting:** Alert before hitting 50% threshold

## License

Part of claude-global-skills project.
