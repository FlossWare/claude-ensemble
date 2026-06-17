# Cost Enforcer - Hard Budget Controls

Hard cost controls with persistent tracking, budget enforcement, and real-time alerts.

## Overview

The **Cost Enforcer** provides strict, enforceable budget limits at three levels:

1. **Daily Cap**: $50/day (configurable)
2. **Monthly Cap**: $1000/month (configurable)
3. **Per-Session Cap**: $25/session (configurable)

All costs are tracked in SQLite (`~/.claude/learning/db/costs.db`) and API calls are **rejected at enforcement time** if any budget is exceeded.

## Features

- **Hard Rejection**: API calls blocked when budget exceeded (not just warnings)
- **Persistent Tracking**: All costs stored in SQLite with timestamps
- **Automatic Daily Reset**: Daily counter resets automatically at midnight
- **Multi-Level Alerts**:
  - Warning at 80% of limit
  - Critical alert at 95% of limit
  - Hard rejection at 100%
- **Session Isolation**: Track costs per session with automatic session creation
- **Flexible Configuration**: Change budget limits at runtime
- **Comprehensive Reporting**: Query costs by date, month, session, or workflow
- **Model Support**: Built-in pricing for Claude (Opus/Sonnet/Haiku), GPT-4o, Gemini

## Installation

```bash
# Install sqlite3 dependency
npm install sqlite3

# Copy to your project
cp cost-enforcer.js /path/to/shared/
```

## Quick Start

### Initialize and Check Budget

```javascript
const { CostDatabase, CostEnforcer, generateSessionId } = require('./cost-enforcer')

const db = new CostDatabase()
await db.init()

const enforcer = new CostEnforcer(db)
const sessionId = await enforcer.initialize(generateSessionId())

// Check if we can afford an API call
const budgetCheck = await enforcer.checkBudget('claude-opus', 2000, 1000)

if (budgetCheck.allowed) {
  // Safe to proceed
  await makeApiCall()
  
  // Record the actual cost
  await enforcer.recordCost('claude-opus', 2000, 1000, {
    workflow_id: 'my-workflow',
    label: 'processing-task',
  })
} else {
  console.error('Budget exceeded:', budgetCheck.rejections)
  // Stop execution
  process.exit(1)
}

await db.close()
```

### Get Cost Report

```javascript
const report = await enforcer.getReport()

console.log(`Session: $${report.session.total_cost.toFixed(2)} / $${report.session.limit.toFixed(2)}`)
console.log(`Daily:   $${report.daily.total_cost.toFixed(2)} / $${report.daily.limit.toFixed(2)} (${report.daily.usage_percent}%)`)
console.log(`Monthly: $${report.monthly.total_cost.toFixed(2)} / $${report.monthly.limit.toFixed(2)} (${report.monthly.usage_percent}%)`)
```

### Set Custom Budget Limits

```javascript
// Change budget limits at runtime
await enforcer.setBudgetLimits(
  100.00,   // daily
  2000.00,  // monthly
  50.00     // per-session
)
```

## API Reference

### CostDatabase

#### `constructor(dbPath)`
Create a database connection.

**Parameters:**
- `dbPath` (string): Path to SQLite database (default: `~/.claude/learning/db/costs.db`)

#### `async init()`
Initialize database and create tables.

#### `async close()`
Close database connection.

#### `async run(sql, params)`
Execute INSERT/UPDATE/DELETE query.

#### `async get(sql, params)`
Fetch single row.

#### `async all(sql, params)`
Fetch all matching rows.

---

### CostEnforcer

#### `constructor(db)`
Create enforcer with database connection.

#### `async initialize(sessionId)`
Initialize a new session. Returns session ID.

#### `async checkBudget(model, inputTokens, outputTokens, options)`
Check if API call would exceed any budget limit.

**Parameters:**
- `model` (string): Model name (e.g., 'claude-opus', 'gpt-4o')
- `inputTokens` (number): Estimated input tokens
- `outputTokens` (number): Estimated output tokens
- `options` (object, optional):
  - `workflow_id`: Associated workflow ID
  - `label`: Call label for tracking

**Returns:**
```javascript
{
  allowed: boolean,           // true if call would not exceed budget
  warnings: string[],         // Warning messages (80%+ of limit)
  rejections: string[],       // Rejection reasons (would exceed limit)
  cost: number,               // Estimated cost in USD
  daily: { spent, limit, projected },
  monthly: { spent, limit, projected },
  session: { spent, limit, projected }
}
```

#### `async recordCost(model, inputTokens, outputTokens, options)`
Record an actual API call cost.

**Parameters:**
- Same as `checkBudget()`
- `options` additionally supports:
  - `agent_id`: Agent making the call (default: $AGENT_ID env var)

**Returns:**
```javascript
{
  allowed: boolean,
  cost: { input_cost, output_cost, total_cost },
  budgetCheck: { ... },
  entry: { ... }  // Database record
}
```

#### `async getDailySpent(date)`
Get total cost spent on a specific date (UTC).

#### `async getMonthlySpent(date)`
Get total cost spent in a specific month.

#### `async getSessionSpent(sessionId)`
Get total cost spent in a session.

#### `async getReport(options)`
Generate comprehensive cost report.

**Returns:**
```javascript
{
  session: { id, total_cost, calls, rejected, limit },
  daily: { date, total_cost, calls, rejected, limit, usage_percent },
  monthly: { month, total_cost, calls, rejected, limit, usage_percent },
  recent_daily: [...],   // Last 20 calls today
  recent_monthly: [...]  // Last 50 calls this month
}
```

#### `async setBudgetLimits(daily, monthly, session)`
Update budget limits at runtime.

**Parameters:**
- `daily` (number): Daily limit in USD
- `monthly` (number): Monthly limit in USD
- `session` (number): Per-session limit in USD

---

## Database Schema

### cost_entries
Main tracking table for all API calls.

```sql
CREATE TABLE cost_entries (
  id INTEGER PRIMARY KEY,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  date DATE,
  month TEXT,
  session_id TEXT,
  model TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  input_cost REAL,
  output_cost REAL,
  total_cost REAL,
  workflow_id TEXT,
  label TEXT,
  agent_id TEXT,
  rejected INTEGER,           -- 1 if call was rejected
  rejection_reason TEXT
)
```

### daily_aggregates
Pre-computed daily totals for fast reporting.

```sql
CREATE TABLE daily_aggregates (
  date DATE PRIMARY KEY,
  total_cost REAL,
  call_count INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  rejected_calls INTEGER,
  last_updated DATETIME
)
```

### monthly_aggregates
Pre-computed monthly totals.

```sql
CREATE TABLE monthly_aggregates (
  month TEXT PRIMARY KEY,
  total_cost REAL,
  call_count INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  rejected_calls INTEGER,
  last_updated DATETIME
)
```

### sessions
Session-level tracking.

```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME,
  total_cost REAL,
  call_count INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  rejected_calls INTEGER,
  agent_id TEXT,
  workflow_id TEXT
)
```

### budget_limits
Current budget configuration.

```sql
CREATE TABLE budget_limits (
  id TEXT PRIMARY KEY,
  daily_limit_dollars REAL,
  monthly_limit_dollars REAL,
  session_limit_dollars REAL,
  updated_at DATETIME
)
```

## Configuration

### Environment Variables

```bash
# Set custom database path
export CLAUDE_COST_DB="$HOME/.claude/costs.db"

# Track agent/workflow context
export AGENT_ID="my-agent"
export WORKFLOW_ID="code-review-1234"
```

### Budget Limits (config options)

Edit budget limits in database:

```javascript
await enforcer.setBudgetLimits(
  100.00,   // daily_limit_dollars
  2000.00,  // monthly_limit_dollars
  50.00     // session_limit_dollars
)
```

Or modify CONFIG in `cost-enforcer.js`:

```javascript
const CONFIG = {
  daily_limit_dollars: 50.00,
  monthly_limit_dollars: 1000.00,
  session_limit_dollars: 25.00,
  warn_threshold_percent: 80,      // warning at 80%
  critical_threshold_percent: 95,   // critical at 95%
}
```

### Pricing

Built-in pricing for major models (per 1K tokens):

| Model | Input | Output |
|-------|-------|--------|
| Claude 3 Opus | $0.015 | $0.075 |
| Claude 3 Sonnet | $0.003 | $0.015 |
| Claude 3 Haiku | $0.00025 | $0.00125 |
| GPT-4o | $0.005 | $0.015 |
| Gemini 2.0 Flash | $0.075 | $0.3 (per 1M) |

Add custom pricing:

```javascript
PRICING['my-model'] = { input: 0.001, output: 0.005 }
```

## Enforcement Workflow

```
┌─────────────────────────────────┐
│  Plan API Call                  │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  checkBudget(model, tokens)     │
├─────────────────────────────────┤
│ - Calculate estimated cost      │
│ - Check daily limit             │
│ - Check monthly limit           │
│ - Check session limit           │
│ - Return allowed: boolean       │
└────────┬────────────────────────┘
         │
    allowed?
    ╱     ╲
  YES     NO
   │       │
   │       ▼
   │   ┌──────────────────────┐
   │   │ Reject API call      │
   │   │ Log rejection reason │
   │   │ Increment rejected   │
   │   └──────────────────────┘
   │
   ▼
┌──────────────────────────────┐
│ Execute API call             │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ recordCost(model, actual)    │
├──────────────────────────────┤
│ - Store in cost_entries      │
│ - Update session totals      │
│ - Update daily_aggregates    │
│ - Update monthly_aggregates  │
│ - Return recorded entry      │
└──────────────────────────────┘
```

## Alerts

### Warning (80%)
```
DAILY_WARNING: $40.00 (80.0%)
```
Cost approaching daily limit. Continue cautiously.

### Critical (95%)
```
DAILY_CRITICAL: $47.50 (95.0%)
```
Cost near limit. Next call may be rejected.

### Rejection (100%)
```
DAILY_LIMIT_EXCEEDED: Would reach $50.50 / $50.00
```
API call rejected. Session must complete or wait for next day.

## Examples

### Integration with Workflow

```javascript
// In your workflow
async function runWithBudgetControl(model, prompt) {
  const enforcer = new CostEnforcer(db)
  await enforcer.initialize()

  // Estimate cost (prompt char count / 4 = tokens)
  const estTokens = prompt.length / 4
  const budgetCheck = await enforcer.checkBudget(model, estTokens, estTokens * 2)

  if (!budgetCheck.allowed) {
    throw new Error(`Budget exceeded: ${budgetCheck.rejections.join(', ')}`)
  }

  // Safe to call API
  const response = await callApi(model, prompt)
  const actualTokens = response.usage.total_tokens

  // Record actual cost
  await enforcer.recordCost(model, response.usage.input_tokens, response.usage.output_tokens, {
    workflow_id: 'my-workflow',
    label: 'api-call',
  })

  return response
}
```

### Query Cost History

```javascript
// Get all calls from today
const today = getDateKey()
const entries = await db.all(
  'SELECT * FROM cost_entries WHERE date = ? ORDER BY timestamp DESC',
  [today]
)

// Get rejected calls
const rejected = await db.all(
  'SELECT * FROM cost_entries WHERE rejected = 1 ORDER BY timestamp DESC'
)

// Get calls by workflow
const wfCalls = await db.all(
  'SELECT * FROM cost_entries WHERE workflow_id = ? ORDER BY timestamp DESC',
  ['my-workflow']
)
```

## Troubleshooting

### Budget Exceeded Errors

If you're hitting budget limits unexpectedly:

1. Check daily spending:
   ```javascript
   const daily = await enforcer.getDailySpent()
   console.log(`Spent today: $${daily.toFixed(2)}`)
   ```

2. Check recent calls:
   ```javascript
   const recent = await db.all(
     'SELECT * FROM cost_entries ORDER BY timestamp DESC LIMIT 10'
   )
   recent.forEach(r => {
     console.log(`${r.timestamp}: ${r.model} $${r.total_cost.toFixed(4)}`)
   })
   ```

3. Increase budget limits:
   ```javascript
   await enforcer.setBudgetLimits(100, 2000, 50)
   ```

### Database Locked

If you get "database is locked" errors:

```javascript
// Ensure you're closing connections
await db.close()

// Or check for multiple concurrent enforcer instances
// Only create one CostEnforcer per session
```

### Missing Pricing Data

Add pricing for custom models:

```javascript
PRICING['custom-model'] = {
  input: 0.001,
  output: 0.005
}
```

If model not found, falls back to Sonnet pricing as conservative default.

## Performance

- **Cost check**: ~10-50ms (single database query)
- **Record cost**: ~20-100ms (3-4 database queries)
- **Report generation**: ~100-500ms (aggregates across all time periods)

For high-throughput applications, consider caching budget checks:

```javascript
const lastCheck = { timestamp: 0, result: null }

async function cachedCheckBudget(model, tokens, ttl = 5000) {
  const now = Date.now()
  if (now - lastCheck.timestamp < ttl) {
    return lastCheck.result
  }
  const result = await enforcer.checkBudget(model, tokens, tokens)
  lastCheck = { timestamp: now, result }
  return result
}
```

## License

MIT
