# Cost and Token Tracking System

## Overview

The cost tracking system provides real-time cost calculation and persistent tracking of API usage across the fleet. It:

1. **Maps models to pricing** - Maintains current pricing for 20+ AI models across 7 providers
2. **Calculates costs** - Computes input/output costs based on actual token counts
3. **Persists to PostgreSQL** - Stores cost data for analytics and billing
4. **Aggregates metrics** - Provides cost summaries by model, provider, or time period
5. **Integrates with fleet-execute** - Automatically tracks all fleet executions

## Architecture

```
fleetExecute()
    ↓
getCostTracker()
    ├─ calculateCost(model, inputTokens, outputTokens)
    │   └─ MODEL_PRICING[model] → total_cost_usd
    │
    └─ trackCost(data)
        └─ costs.entries (PostgreSQL)
```

## Usage

### In fleet-execute.js

Cost tracking is automatic when `track_costs=true` (default):

```javascript
import { fleetExecute } from './tools/fleet-execute.js';

const result = await fleetExecute({
  task: 'Analyze code',
  model: 'sonnet',
  track_costs: true,  // Enable cost tracking (default)
  track_execution: true
});

// Result includes:
// {
//   success: true,
//   model: 'sonnet',
//   cost_usd: 0.045,
//   input_tokens: 1500,
//   output_tokens: 800,
//   input_cost_usd: 0.0045,
//   output_cost_usd: 0.012,
//   provider: 'anthropic',
//   cost_tracking: true,
//   cost_tracked: true,
//   cost_entry_id: 42
// }
```

### Direct Usage (CommonJS)

```javascript
const { getCostTracker, MODEL_PRICING } = require('./lib/cost-tracker.cjs');

const tracker = getCostTracker();

// Calculate cost
const cost = tracker.calculateCost('sonnet', 1000000, 1000000);
console.log(`Cost: $${cost.total_cost_usd}`);
// Output: Cost: $18

// Track cost to database
const entry = await tracker.trackCost({
  model: 'sonnet',
  input_tokens: 1000000,
  output_tokens: 1000000,
  worker_id: 'server-01',
  task_hash: 'abc123...'
});

console.log(`Tracked entry ID: ${entry.id}`);
```

### Direct Usage (ES6)

```javascript
import { getCostTracker, MODEL_PRICING } from './lib/cost-tracker.js';

const tracker = getCostTracker();

// Get pricing info
const pricing = tracker.getPricingInfo('opus');
console.log(`Opus input: $${pricing.input_cost_per_1m / 1000}/1M tokens`);

// Calculate and track
const cost = tracker.calculateCost('opus', 500000, 250000);
await tracker.trackCost({
  model: 'opus',
  input_tokens: 500000,
  output_tokens: 250000,
  workflow_id: 'wf-12345'
});
```

## Pricing Database

All pricing updated 2026-06-29. Prices shown as cost per 1M tokens.

### Anthropic Claude API

| Model | Input | Output | Context | Notes |
|-------|-------|--------|---------|-------|
| claude-opus-4 | $15.00 | $75.00 | 200K | Flagship model |
| claude-sonnet-4.5 | $3.00 | $15.00 | 200K | Balanced cost/performance |
| claude-haiku-4 | $0.80 | $4.00 | 200K | Fastest, cheapest |

### OpenAI GPT

| Model | Input | Output | Context | Notes |
|-------|-------|--------|---------|-------|
| gpt-4o | $2.50 | $10.00 | 128K | Latest GPT-4 Omni |
| gpt-4-turbo | $10.00 | $30.00 | 128K | Turbo variant |
| gpt-3.5-turbo | $0.50 | $1.50 | 16K | Legacy model |

### Google Gemini

| Model | Input | Output | Context | Notes |
|-------|-------|--------|---------|-------|
| gemini-2.0-flash-exp | $0.075 | $0.30 | 1M | Experimental, FREE input |
| gemini-1.5-pro | $1.25 | $5.00 | 1M | Massive context window |

### Other Providers

| Provider | Model | Input | Output | Status |
|----------|-------|-------|--------|--------|
| Mistral | mistral-large-latest | $2.00 | $6.00 | Paid |
| Mistral | mistral-small-latest | $0.14 | $0.42 | Paid |
| Cohere | command-r-plus | $3.00 | $15.00 | Paid |
| AI21 | jamba-1.5-large | $0.20 | $0.60 | Paid |
| AI21 | jamba-1.5-mini | $0.02 | $0.06 | Paid |
| Groq | llama-3.3-70b | FREE | FREE | Free tier |
| Groq | mixtral-8x7b-32768 | FREE | FREE | Free tier |
| DeepInfra | llama-3.1-70b | FREE | FREE | Free tier |
| Together | llama-3.1-70b-turbo | FREE | FREE | Free tier |

## API Reference

### CostTracker Class

#### Constructor

```javascript
const tracker = new CostTracker(pgConfig);
```

**Parameters:**
- `pgConfig` (optional): PostgreSQL connection config
  - `host`: Database host (default: `localhost`)
  - `port`: Database port (default: 5432)
  - `database`: Database name (default: `learning`)
  - `user`: Database user (default: current user)
  - `password`: Database password (optional)
  - `ssl`: Enable SSL (default: false)

#### Methods

##### `getPricingInfo(model)`

Get pricing information for a model.

```javascript
const pricing = tracker.getPricingInfo('sonnet');
// {
//   provider: 'anthropic',
//   input_cost_per_1m: 3000,
//   output_cost_per_1m: 15000,
//   context_window: 200000,
//   notes: 'Balanced cost/performance'
// }
```

##### `calculateCost(model, inputTokens, outputTokens)`

Calculate cost for token usage.

```javascript
const cost = tracker.calculateCost('sonnet', 1000, 2000);
// {
//   model: 'sonnet',
//   provider: 'anthropic',
//   input_tokens: 1000,
//   output_tokens: 2000,
//   input_cost_usd: 0.000003,
//   output_cost_usd: 0.00003,
//   total_cost_usd: 0.000033,
//   pricing_ref: {...}
// }
```

##### `async initialize()`

Initialize PostgreSQL schema and tables (called automatically).

```javascript
await tracker.initialize();
```

##### `async trackCost(data)`

Track a cost entry to PostgreSQL.

```javascript
const entry = await tracker.trackCost({
  model: 'sonnet',
  input_tokens: 1500,
  output_tokens: 800,
  worker_id: 'server-01',           // optional
  workflow_id: 'wf-12345',          // optional
  task_hash: 'abc123...',           // optional
  metadata: { custom: 'data' }      // optional
});

// {
//   model: 'sonnet',
//   provider: 'anthropic',
//   input_tokens: 1500,
//   output_tokens: 800,
//   total_cost_usd: 0.027,
//   id: 42,
//   created_at: '2026-06-29T10:30:00.000Z',
//   database_tracked: true
// }
```

##### `async getAggregate(options)`

Get cost aggregates by model, provider, or time.

```javascript
const stats = await tracker.getAggregate({
  since_hours: 24,
  groupBy: 'model'  // 'model' | 'provider' | 'hour'
});

// groupBy: 'model'
// {
//   period: '24 hours',
//   group_by: 'model',
//   results: [
//     {
//       model: 'sonnet',
//       provider: 'anthropic',
//       request_count: 145,
//       total_input_tokens: 1234567,
//       total_output_tokens: 987654,
//       total_cost_usd: 18.52,
//       avg_cost_per_request: 0.1276,
//       first_request: '2026-06-28T10:30:00.000Z',
//       last_request: '2026-06-29T10:30:00.000Z'
//     }
//   ],
//   timestamp: '2026-06-29T10:31:00.000Z'
// }
```

##### `async close()`

Close database connection pool.

```javascript
await tracker.close();
```

### getCostTracker(pgConfig)

Get or create singleton instance.

```javascript
import { getCostTracker } from './lib/cost-tracker.js';

const tracker = getCostTracker();
// Returns same instance on subsequent calls
```

## Database Schema

### costs.entries

Stores all cost tracking entries.

```sql
CREATE TABLE costs.entries (
  id SERIAL PRIMARY KEY,
  model VARCHAR(255) NOT NULL,           -- Model used (e.g., 'sonnet')
  provider VARCHAR(100),                 -- Provider (anthropic, openai, google, etc.)
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_cost NUMERIC(12, 6) NOT NULL DEFAULT 0,  -- USD cost
  worker_id VARCHAR(255),                -- Which worker executed (optional)
  workflow_id VARCHAR(255),              -- Associated workflow (optional)
  task_hash VARCHAR(64),                 -- Hash of task (optional)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  metadata JSONB                         -- Custom metadata
);

-- Indexes for fast queries
CREATE INDEX idx_costs_model ON costs.entries(model);
CREATE INDEX idx_costs_created ON costs.entries(created_at);
CREATE INDEX idx_costs_provider ON costs.entries(provider);
```

## Queries

### Total cost by model (24 hours)

```sql
SELECT
  model,
  COUNT(*) as requests,
  SUM(total_cost) as total_cost_usd,
  AVG(total_cost) as avg_cost_per_request
FROM costs.entries
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY total_cost_usd DESC;
```

### Cost by provider

```sql
SELECT
  provider,
  COUNT(*) as requests,
  SUM(input_tokens) as total_input_tokens,
  SUM(output_tokens) as total_output_tokens,
  SUM(total_cost) as total_cost_usd
FROM costs.entries
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY provider
ORDER BY total_cost_usd DESC;
```

### Hourly cost trends

```sql
SELECT
  DATE_TRUNC('hour', created_at) as hour,
  COUNT(*) as requests,
  SUM(total_cost) as total_cost_usd,
  AVG(total_cost) as avg_cost_per_request
FROM costs.entries
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;
```

### Top 10 most expensive requests

```sql
SELECT
  model,
  provider,
  worker_id,
  workflow_id,
  input_tokens,
  output_tokens,
  total_cost,
  created_at
FROM costs.entries
ORDER BY total_cost DESC
LIMIT 10;
```

## Configuration

### Environment Variables

```bash
# PostgreSQL connection
PG_HOST=laptop-01
PG_PORT=5432
PG_DB=learning
PG_USER=sfloess
PG_PASSWORD=secret
PG_SSL=false
```

### Integration with fleet-execute

The cost tracker is automatically integrated into `fleetExecute()`:

```javascript
// Cost tracking enabled by default
const result = await fleetExecute({
  task: 'Analyze code',
  model: 'sonnet',
  track_costs: true      // Optional, true by default
});

// Cost data in result:
result.cost_usd          // Total cost
result.input_cost_usd    // Input cost only
result.output_cost_usd   // Output cost only
result.provider          // Provider name
result.cost_tracking     // true if calculated
result.cost_tracked      // true if persisted to DB
result.cost_entry_id     // Database row ID
```

## Monitoring

### View aggregated costs in PostgreSQL

```bash
# Connect to database
psql -h laptop-01 -U sfloess -d learning

# Get recent costs
SELECT * FROM costs.entries ORDER BY created_at DESC LIMIT 20;

# Get cost summary
SELECT 
  model, 
  COUNT(*) as requests,
  SUM(total_cost) as total_usd,
  AVG(total_cost) as avg_usd
FROM costs.entries
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY total_usd DESC;
```

### Programmatic monitoring

```javascript
const tracker = getCostTracker();

// Get stats for last 24 hours
const stats = await tracker.getAggregate({
  since_hours: 24,
  groupBy: 'model'
});

stats.results.forEach(row => {
  console.log(`${row.model}: ${row.total_cost_usd.toFixed(2)} USD (${row.request_count} requests)`);
});
```

## Testing

Run cost tracker tests:

```bash
npm test -- test/cost-tracker.test.js
```

Tests cover:
- Pricing calculation accuracy
- Model lookup (direct and aliases)
- Provider coverage
- Free tier tracking
- Database operations (when PostgreSQL available)
- Singleton pattern
- Edge cases (zero tokens, unknown models)

## Implementation Notes

1. **Fallback pricing**: Unknown models default to Haiku pricing ($0.80 input / $4.00 output)
2. **Precision**: All costs calculated to 6 decimal places
3. **Free models**: Tracked with $0 cost for metrics purposes
4. **Graceful degradation**: System continues if PostgreSQL unavailable (costs calculated but not persisted)
5. **Singleton pattern**: `getCostTracker()` returns same instance across application
6. **No side effects**: Calculating costs never fails - falls back to defaults if needed

## Cost Optimization Tips

1. **Use Haiku for simple tasks** - 5× cheaper than Sonnet
2. **Batch operations** - Fewer requests = lower overhead
3. **Monitor trends** - Query `costs.entries` for expensive patterns
4. **Free tier for experiments** - Use Groq/Together/DeepInfra for testing
5. **Track by workflow** - Set `workflow_id` to analyze project costs

## Troubleshooting

### PostgreSQL connection fails

```
Failed to track cost in database: connect ECONNREFUSED
```

**Solution**: Ensure PostgreSQL is running on configured host/port:

```bash
psql -h laptop-01 -U sfloess -d learning -c "SELECT 1"
```

### Costs not persisting

```
database_tracked: false
error: "Failed to track cost in database"
```

**Solution**: Check database schema is initialized:

```bash
psql -h laptop-01 -U sfloess -d learning -c "\dt costs.*"
```

### Unknown model pricing

Models not in `MODEL_PRICING` default to Haiku pricing. To add new models, update `MODEL_PRICING` in:
- `lib/cost-tracker.js` (ES6 module)
- `lib/cost-tracker.cjs` (CommonJS)

Keep both in sync for consistency.

## Future Enhancements

- Budget alerts (warn when threshold exceeded)
- Cost estimation before execution
- Model cost comparison reports
- Billing export (CSV, JSON)
- Cost attribution by project/team
- Monthly cost projections
- Provider switching recommendations
