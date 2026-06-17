# Cost Enforcer Module Index

Complete hard budget controls implementation with persistent SQLite tracking.

## Quick Links

| File | Purpose | Size |
|------|---------|------|
| **cost-enforcer.js** | Core module (classes, functions, exports) | 19 KB |
| **test-cost-enforcer.js** | Full test suite (8 test scenarios) | 9.6 KB |
| **COST-ENFORCER-SUMMARY.md** | Quick reference & architecture | 12 KB |
| **COST-ENFORCER-README.md** | Complete API reference | 14 KB |
| **COST-ENFORCER-INTEGRATION.md** | Integration patterns & examples | 17 KB |

## What This Does

Hard cost controls with **rejection** (not just warnings) when budgets exceeded:

- **$50/day** limit (per UTC day)
- **$1000/month** limit (per calendar month)
- **$25/session** limit (per session)

All costs tracked in SQLite at `~/.claude/learning/db/costs.db`.

## Start Here

1. **Quick Setup** (5 min)
   - Read: COST-ENFORCER-SUMMARY.md
   - Run: `node test-cost-enforcer.js`
   - Database auto-creates on first use

2. **API Reference** (10 min)
   - Read: COST-ENFORCER-README.md
   - Focus on: checkBudget(), recordCost(), getReport()

3. **Integration** (15 min)
   - Read: COST-ENFORCER-INTEGRATION.md
   - Choose pattern that fits your use case
   - Copy code snippet

4. **Deploy** (5 min)
   - `npm install sqlite3`
   - Copy `cost-enforcer.js` to your project
   - Import and use

## Core Classes

### CostDatabase
SQLite connection and query layer.

```javascript
const db = new CostDatabase()
await db.init()
const rows = await db.all('SELECT * FROM cost_entries LIMIT 10')
await db.close()
```

### CostEnforcer
Main enforcement engine.

```javascript
const enforcer = new CostEnforcer(db)
await enforcer.initialize(sessionId)

// Before API call
const check = await enforcer.checkBudget(model, inputTokens, outputTokens)
if (!check.allowed) throw new Error(check.rejections[0])

// After API call
await enforcer.recordCost(model, inputTokens, outputTokens)

// Get report
const report = await enforcer.getReport()
```

## Three Integration Levels

### Level 1: Simple (Pre-flight Check)
```javascript
const check = await enforcer.checkBudget('opus', 2000, 1000)
if (!check.allowed) process.exit(1)
```

### Level 2: Full (Check + Record)
```javascript
const check = await enforcer.checkBudget('opus', 2000, 1000)
if (!check.allowed) throw new Error(check.rejections[0])
const response = await callApi()
await enforcer.recordCost('opus', response.tokens.input, response.tokens.output)
```

### Level 3: Advanced (Guardian Pattern)
```javascript
const guardian = new BudgetGuardian(enforcer)
try {
  await guardian.checkAndThrow('opus', 2000, 1000)
  const response = await callApi()
  await guardian.record('opus', response.tokens.input, response.tokens.output)
} catch (err) {
  if (err.message.includes('BUDGET_EXCEEDED')) {
    // emergency stop logic
  }
}
```

## Database Tables

All stored in `~/.claude/learning/db/costs.db`:

| Table | Tracks |
|-------|--------|
| cost_entries | Every API call (5 most recent shown) |
| daily_aggregates | Daily totals per date |
| monthly_aggregates | Monthly totals per month |
| sessions | Session-level aggregates |
| budget_limits | Current budget configuration |

## Configuration

### Environment Variables
```bash
export AGENT_ID="my-agent"
export WORKFLOW_ID="my-workflow"
export TZ_OFFSET="5"  # UTC+5
```

### Runtime Budget Changes
```javascript
await enforcer.setBudgetLimits(100, 2000, 50)  // daily, monthly, session
```

### Custom Model Pricing
```javascript
PRICING['my-model'] = { input: 0.001, output: 0.005 }  // per 1K tokens
```

## Enforcement Behavior

```
Plan API Call
     ↓
checkBudget(model, tokens)
     ├─→ Calculate cost
     ├─→ Check daily limit
     ├─→ Check monthly limit
     ├─→ Check session limit
     └─→ Return { allowed: boolean, warnings: [], rejections: [] }
     ↓
  allowed?
  ╱ YES  NO
 ↓        ↓
Call    Reject
API     (Stop)
 ↓
Record cost
 ↓
Continue
```

## Alert Levels

| Level | Threshold | Behavior |
|-------|-----------|----------|
| **Normal** | 0-80% | Proceed normally |
| **Warning** | 80-95% | Log warning, continue |
| **Critical** | 95-100% | Log critical alert, continue |
| **Rejection** | >100% | **REJECT - Do not call API** |

Example outputs:
```
DAILY_WARNING: $40.00 (80.0%)
DAILY_CRITICAL: $47.50 (95.0%)
DAILY_LIMIT_EXCEEDED: Would reach $50.50 / $50.00  ← REJECTED
```

## Usage Patterns

### Pattern 1: Pre-Call Only
For simple cost awareness:
```javascript
const check = await enforcer.checkBudget(...)
```

### Pattern 2: Check + Record
For accurate cost tracking:
```javascript
const check = await enforcer.checkBudget(...)
if (check.allowed) {
  const response = await callApi()
  await enforcer.recordCost(...)
}
```

### Pattern 3: Batch Processing
For processing multiple items:
```javascript
for (const item of items) {
  const check = await enforcer.checkBudget(...)
  if (!check.allowed) {
    console.log(`Skipped (budget): ${item.id}`)
    break
  }
  // process item...
}
```

### Pattern 4: Emergency Stop
For critical workflows:
```javascript
const guardian = new BudgetGuardian(enforcer)
try {
  await guardian.checkAndThrow(model, input, output)
  // ... proceed
} catch (err) {
  // Emergency cleanup
  process.exit(1)
}
```

### Pattern 5: Multi-Agent
For multi-AI coordination:
```javascript
const budgetPerAgent = sessionLimit / agents.length
for (const agent of agents) {
  const check = await enforcer.checkBudget(...)
  if (check.session.projected > budgetPerAgent) {
    console.log(`Skipped agent (budget): ${agent.name}`)
  }
}
```

## Query Examples

### Get today's spending
```javascript
const spent = await enforcer.getDailySpent()
console.log(`Today: $${spent.toFixed(2)}`)
```

### Get month's spending
```javascript
const spent = await enforcer.getMonthlySpent()
console.log(`This month: $${spent.toFixed(2)}`)
```

### Get session spending
```javascript
const spent = await enforcer.getSessionSpent(sessionId)
console.log(`Session: $${spent.toFixed(2)}`)
```

### Get full report
```javascript
const report = await enforcer.getReport()
console.log(`
  Session: $${report.session.total_cost} / $${report.session.limit}
  Daily: $${report.daily.total_cost} / $${report.daily.limit} (${report.daily.usage_percent}%)
  Monthly: $${report.monthly.total_cost} / $${report.monthly.limit} (${report.monthly.usage_percent}%)
`)
```

### Query recent calls
```javascript
const recent = await db.all(
  'SELECT * FROM cost_entries ORDER BY timestamp DESC LIMIT 10'
)
recent.forEach(r => {
  console.log(`${r.timestamp}: ${r.model} $${r.total_cost.toFixed(4)}`)
})
```

## Error Handling

### Budget Exceeded
```javascript
const check = await enforcer.checkBudget(...)
if (!check.allowed) {
  console.error(check.rejections)  // ["DAILY_LIMIT_EXCEEDED: ...", ...]
  // Handle based on which limit:
  if (check.rejections[0].includes('SESSION')) {
    // Start new session
  } else if (check.rejections[0].includes('DAILY')) {
    // Wait for tomorrow
  }
}
```

### Database Locked
```javascript
try {
  await enforcer.recordCost(...)
} catch (err) {
  if (err.message.includes('locked')) {
    // Multiple enforcer instances accessing DB
    // Wait and retry
    await new Promise(r => setTimeout(r, 100))
  }
}
```

## Performance

| Operation | Time |
|-----------|------|
| checkBudget() | 10-50ms |
| recordCost() | 20-100ms |
| getReport() | 100-500ms |

For high-throughput apps, cache budget checks:
```javascript
const cached = { timestamp: 0, result: null }
async function cachedCheck(model, tokens, ttl = 5000) {
  if (Date.now() - cached.timestamp < ttl) return cached.result
  cached.result = await enforcer.checkBudget(model, tokens, tokens)
  cached.timestamp = Date.now()
  return cached.result
}
```

## Testing

Run full test suite:
```bash
node test-cost-enforcer.js
```

Tests:
1. Budget checking (within limits)
2. Recording multiple costs
3. Approaching limit warnings
4. Daily spending queries
5. Comprehensive reporting
6. Budget limit updates
7. Model variety & pricing
8. Database queries

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Database locked | Only one enforcer per session; reuse instance |
| Costs not recording | Call recordCost() after every API call |
| Budget exceeded unexpectedly | Check recent calls: `SELECT * FROM cost_entries ORDER BY timestamp DESC` |
| Missing pricing | Add custom pricing: `PRICING['model'] = {...}` |
| Session budget exhausted | Start new session: `await enforcer.initialize()` |

## Deployment Checklist

- [ ] `npm install sqlite3`
- [ ] Copy cost-enforcer.js to project
- [ ] Initialize database: `await db.init()`
- [ ] Create enforcer: `const enforcer = new CostEnforcer(db)`
- [ ] Set custom budget limits if needed
- [ ] Add pre-flight checks before each API call
- [ ] Add post-flight recording after each API call
- [ ] Implement rejection handling
- [ ] Add monitoring for approaching limits
- [ ] Test with mock data
- [ ] Review cost reports regularly

## File Locations

```
~/.claude/learning/shared/
├── cost-enforcer.js                    ← Main module (import this)
├── test-cost-enforcer.js               ← Run tests
├── COST-ENFORCER-INDEX.md              ← This file
├── COST-ENFORCER-SUMMARY.md            ← Quick reference
├── COST-ENFORCER-README.md             ← Full API docs
└── COST-ENFORCER-INTEGRATION.md        ← Integration patterns

~/.claude/learning/db/
└── costs.db                             ← SQLite database (auto-created)
```

## Import Statements

```javascript
// Node.js / CommonJS
const { CostDatabase, CostEnforcer, generateSessionId } = require('./cost-enforcer')

// ES Modules (if using .mjs or "type": "module")
import { CostDatabase, CostEnforcer, generateSessionId } from './cost-enforcer.js'
```

## Next Steps

1. **Read** COST-ENFORCER-SUMMARY.md (5 min overview)
2. **Run** test-cost-enforcer.js to see it work
3. **Read** COST-ENFORCER-README.md for full API
4. **Choose** integration pattern from COST-ENFORCER-INTEGRATION.md
5. **Integrate** cost checks into your application
6. **Monitor** costs with getReport()
7. **Adjust** budgets as needed via setBudgetLimits()

## Support

For issues:
1. Check test output: `node test-cost-enforcer.js`
2. Query database: SQLite3 CLI on `~/.claude/learning/db/costs.db`
3. Review audit log: `~/.claude/learning/costs-audit.jsonl`
4. Check error messages in rejection_reason column

---

**Created**: 2026-06-13
**Module Version**: 1.0
**Database Schema Version**: 1
**Node.js Version**: 14+ (sqlite3 support)
