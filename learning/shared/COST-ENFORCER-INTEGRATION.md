# Cost Enforcer Integration Guide

How to integrate hard cost controls into your Claude workflows and applications.

## Architecture

```
Your Application/Workflow
        │
        ▼
┌───────────────────────────┐
│  Check Budget             │
│  Before API Call          │
├───────────────────────────┤
│ checkBudget(model, tokens)│
│ Returns: allowed (bool)   │
└────────┬──────────────────┘
         │
    ┌────┴─────┐
    │           │
  YES          NO
    │           │
    ▼           ▼
┌───────────┐  ┌──────────────┐
│  Call API │  │ Reject Call  │
│  (Safe)   │  │ (Stop exec)  │
└─────┬─────┘  └──────────────┘
      │
      ▼
┌────────────────────────┐
│  Record Actual Cost    │
│ recordCost(actual)     │
└────────────────────────┘
      │
      ▼
┌────────────────────────┐
│  Continue with Result  │
└────────────────────────┘
```

## Implementation Patterns

### Pattern 1: Pre-Call Budget Check

Use before every API call to prevent budget overrun.

```javascript
const { CostDatabase, CostEnforcer, generateSessionId } = require('./cost-enforcer')

async function callModelWithBudgetCheck(model, prompt, options = {}) {
  const db = new CostDatabase()
  await db.init()

  const enforcer = new CostEnforcer(db)
  await enforcer.initialize()

  // Estimate tokens (rough: 1 token ≈ 4 chars)
  const estInputTokens = Math.ceil(prompt.length / 4)
  const estOutputTokens = options.maxTokens || Math.ceil(prompt.length / 2) // rough estimate

  // CHECK BUDGET FIRST
  const budgetCheck = await enforcer.checkBudget(model, estInputTokens, estOutputTokens)

  if (!budgetCheck.allowed) {
    // Log rejection for audit
    console.error('API call rejected due to budget:', budgetCheck.rejections)
    
    // Alert user/admin
    if (budgetCheck.rejections.some(r => r.includes('SESSION'))) {
      console.error('SESSION BUDGET EXCEEDED - Stopping execution')
      process.exit(1)
    }
    
    throw new Error(`Budget limit exceeded: ${budgetCheck.rejections.join(', ')}`)
  }

  // Log warnings
  if (budgetCheck.warnings.length > 0) {
    console.warn('Budget warnings:')
    budgetCheck.warnings.forEach(w => console.warn(`  ⚠ ${w}`))
  }

  // Safe to proceed
  console.log(`Calling ${model}... (budgeted: $${budgetCheck.cost.toFixed(4)})`)
  
  try {
    const response = await callApi(model, prompt, options)

    // Record actual cost
    const record = await enforcer.recordCost(
      model,
      response.usage.input_tokens,
      response.usage.output_tokens,
      {
        workflow_id: options.workflow_id,
        label: options.label,
      }
    )

    console.log(`Call completed: $${record.cost.total_cost.toFixed(4)}`)
    
    return response
  } finally {
    await db.close()
  }
}
```

### Pattern 2: Batch Processing with Budget Enforcement

For workflows processing multiple items.

```javascript
async function processBatchWithBudgetControl(items, processItem, options = {}) {
  const db = new CostDatabase()
  await db.init()
  
  const enforcer = new CostEnforcer(db)
  const sessionId = await enforcer.initialize()
  
  const results = []
  const skipped = []

  for (const item of items) {
    try {
      // Check if we can process this item
      const estCost = estimateCost(item) // app-specific
      const budgetCheck = await enforcer.checkBudget('claude-opus', estCost.input, estCost.output)

      if (!budgetCheck.allowed) {
        console.warn(`Skipping item (budget exceeded): ${item.id}`)
        skipped.push({
          id: item.id,
          reason: budgetCheck.rejections[0],
        })
        continue
      }

      // Process the item
      const result = await processItem(item)
      
      // Record cost
      await enforcer.recordCost('claude-opus', result.tokens.input, result.tokens.output, {
        workflow_id: options.workflow_id,
        label: `batch:${item.id}`,
      })

      results.push(result)
      
      // Check if session budget nearly exhausted
      const remaining = await enforcer.getSessionSpent(sessionId)
      if (remaining > 20) { // Approaching $25 session limit
        console.warn(`Session budget nearly exhausted ($${remaining.toFixed(2)} remaining)`)
        break
      }

    } catch (err) {
      console.error(`Error processing item ${item.id}:`, err.message)
      skipped.push({ id: item.id, reason: err.message })
    }
  }

  // Generate report
  const report = await enforcer.getReport()
  
  await db.close()

  return {
    sessionId,
    processed: results.length,
    skipped: skipped.length,
    cost: report.session.total_cost,
    report,
  }
}
```

### Pattern 3: Workflow Integration

For use in Claude code workflows.

```javascript
// workflow.js
import { CostDatabase, CostEnforcer, generateSessionId } from './shared/cost-enforcer.js'

export const meta = {
  name: 'my-expensive-workflow',
  description: 'Workflow with hard budget controls',
}

async function enforcedApiCall(enforcer, model, input, output, label) {
  // Check budget before calling
  const check = await enforcer.checkBudget(model, input, output)
  
  if (!check.allowed) {
    log(`ERROR: Budget exceeded - ${check.rejections.join(', ')}`)
    return { error: 'budget_exceeded', details: check.rejections }
  }

  log(`Calling ${model}... (cost: $${check.cost.toFixed(4)})`)

  // Make actual API call here
  const response = await someApiCall(model, input, output)

  // Record it
  const record = await enforcer.recordCost(
    model,
    response.actualInput,
    response.actualOutput,
    { label }
  )

  return { success: true, response, cost: record.cost }
}

// Main workflow
phase('Initialize')

const db = new CostDatabase()
await db.init()

const enforcer = new CostEnforcer(db)
const sessionId = await enforcer.initialize()

log(`Session: ${sessionId}`)

// Get current budget status
const report = await enforcer.getReport()
log(`Session budget: $${report.session.total_cost.toFixed(2)} / $${report.session.limit.toFixed(2)}`)

phase('Processing')

// Use enforcer throughout workflow
const call1 = await enforcedApiCall(enforcer, 'claude-opus', 2000, 1000, 'step-1')
if (call1.error) throw new Error(`Budget exceeded`)

const call2 = await enforcedApiCall(enforcer, 'claude-sonnet', 1500, 800, 'step-2')
if (call2.error) throw new Error(`Budget exceeded`)

phase('Report')

const finalReport = await enforcer.getReport()
log(`\nFinal costs:`)
log(`  Session: $${finalReport.session.total_cost.toFixed(4)}`)
log(`  Daily: $${finalReport.daily.total_cost.toFixed(4)}`)
log(`  Monthly: $${finalReport.monthly.total_cost.toFixed(4)}`)

await db.close()

return finalReport
```

### Pattern 4: Multi-Agent Coordination

For multi-AI workflows with shared budget.

```javascript
async function multiAiWorkflowWithSharedBudget(agents, task, options = {}) {
  const db = new CostDatabase()
  await db.init()
  
  const enforcer = new CostEnforcer(db)
  const sessionId = await enforcer.initialize()

  const results = []
  const budgetPerAgent = 5 / agents.length // $5 shared budget

  for (const agent of agents) {
    const check = await enforcer.checkBudget('claude-opus', 3000, 1500)

    if (check.session.projected > budgetPerAgent) {
      console.warn(`Skipping agent (per-agent budget exceeded): ${agent.name}`)
      continue
    }

    try {
      const response = await agent.process(task)
      
      await enforcer.recordCost('claude-opus', 3000, 1500, {
        label: `agent:${agent.name}`,
      })

      results.push({
        agent: agent.name,
        response,
      })
    } catch (err) {
      console.error(`Agent ${agent.name} failed:`, err)
    }
  }

  await db.close()
  
  return results
}
```

### Pattern 5: Emergency Stop on Budget

For critical workflows that must stop cleanly when budget exceeded.

```javascript
class BudgetGuardian {
  constructor(enforcer) {
    this.enforcer = enforcer
    this.emergencyStopped = false
  }

  async checkAndThrow(model, input, output, context = {}) {
    const check = await this.enforcer.checkBudget(model, input, output)

    if (!check.allowed) {
      this.emergencyStopped = true
      
      // Log emergency stop
      console.error('\n' + '='.repeat(60))
      console.error('EMERGENCY STOP: BUDGET LIMIT EXCEEDED')
      console.error('='.repeat(60))
      console.error(`Context: ${JSON.stringify(context)}`)
      console.error(`Rejections: ${check.rejections.join(', ')}`)
      console.error('='.repeat(60) + '\n')

      // Trigger cleanup/rollback
      if (context.onBudgetExceeded) {
        await context.onBudgetExceeded()
      }

      throw new Error(`BUDGET_EXCEEDED: ${check.rejections[0]}`)
    }

    return check
  }

  async record(model, input, output, label) {
    if (this.emergencyStopped) {
      throw new Error('Cannot record cost: Emergency stop was triggered')
    }

    return await this.enforcer.recordCost(model, input, output, { label })
  }

  async getStatus() {
    const report = await this.enforcer.getReport()
    return {
      emergencyStopped: this.emergencyStopped,
      session: report.session,
      daily: report.daily,
      monthly: report.monthly,
    }
  }
}

// Usage
const guardian = new BudgetGuardian(enforcer)

try {
  await guardian.checkAndThrow('claude-opus', 2000, 1000, {
    step: 'code-review',
    onBudgetExceeded: async () => {
      console.log('Rolling back incomplete work...')
      // cleanup logic
    }
  })

  // Safe to proceed
} catch (err) {
  if (err.message.includes('BUDGET_EXCEEDED')) {
    // Handle budget emergency
    console.error('Workflow terminated:', err.message)
    process.exit(1)
  }
  throw err
}
```

## Configuration in Workflows

### Set Custom Budget Limits

In your workflow's initialization:

```javascript
// Set per-session budget to $50 (more generous)
const newLimits = await enforcer.setBudgetLimits(100, 2000, 50)
log(`Updated session budget to: $${newLimits.session}`)
```

### Monitor Approaching Limits

```javascript
async function monitorBudget(enforcer, interval = 10) {
  setInterval(async () => {
    const report = await enforcer.getReport()
    
    if (report.daily.usage_percent > 95) {
      console.error(`⚠ CRITICAL: Daily budget at ${report.daily.usage_percent}%`)
    } else if (report.daily.usage_percent > 80) {
      console.warn(`⚠ WARNING: Daily budget at ${report.daily.usage_percent}%`)
    }

    if (report.session.total_cost > report.session.limit * 0.9) {
      console.error(`⚠ SESSION CRITICAL: Near session limit`)
    }
  }, interval * 1000)
}

// Start monitoring
monitorBudget(enforcer)
```

## Error Handling

### Handle Budget Rejections

```javascript
async function safeApiCall(enforcer, model, tokens) {
  const check = await enforcer.checkBudget(model, tokens.input, tokens.output)

  if (!check.allowed) {
    // Determine which limit was hit
    const rejection = check.rejections[0]

    if (rejection.includes('DAILY')) {
      // Try again tomorrow
      console.error('Daily budget exhausted. Retrying tomorrow...')
      return { error: 'daily_limit', retryAt: getNextMidnight() }

    } else if (rejection.includes('MONTHLY')) {
      // Wait for next month
      console.error('Monthly budget exhausted. Retrying next month...')
      return { error: 'monthly_limit', retryAt: getNextMonth() }

    } else if (rejection.includes('SESSION')) {
      // Start new session or stop
      console.error('Session budget exhausted. Start new session...')
      return { error: 'session_limit', action: 'start_new_session' }
    }
  }

  // Safe to proceed
  return { allowed: true, cost: check.cost }
}
```

### Logging and Audit

```javascript
async function logCostEvent(enforcer, event) {
  const fs = require('fs')
  const timestamp = new Date().toISOString()

  const logEntry = {
    timestamp,
    type: event.type, // 'check', 'record', 'reject', 'alert'
    model: event.model,
    tokens: event.tokens,
    cost: event.cost,
    allowed: event.allowed,
    reason: event.reason,
  }

  // Append to audit log
  fs.appendFileSync('~/.claude/learning/costs-audit.jsonl', 
    JSON.stringify(logEntry) + '\n'
  )
}

// On every budget check
const check = await enforcer.checkBudget(model, input, output)
await logCostEvent(enforcer, {
  type: 'check',
  model,
  tokens: { input, output },
  cost: check.cost,
  allowed: check.allowed,
  reason: check.rejections[0],
})
```

## Testing

### Mock Budget Checks

For testing without real API calls:

```javascript
class MockEnforcer {
  constructor(sessionLimit = 25) {
    this.spent = 0
    this.sessionLimit = sessionLimit
  }

  async checkBudget(model, input, output) {
    const cost = (input + output) * 0.000001 // Mock pricing
    return {
      allowed: this.spent + cost <= this.sessionLimit,
      cost,
      warnings: (this.spent + cost) / this.sessionLimit > 0.8 ? ['approaching limit'] : [],
    }
  }

  async recordCost(model, input, output) {
    const cost = (input + output) * 0.000001
    this.spent += cost
    return { cost: { total_cost: cost } }
  }

  async getReport() {
    return {
      session: { total_cost: this.spent, limit: this.sessionLimit },
    }
  }
}

// Use in tests
const mockEnforcer = new MockEnforcer()
const check = await mockEnforcer.checkBudget('mock-model', 1000, 500)
assert(check.allowed === true)
```

## Deployment

### Production Checklist

- [ ] Database path is writable: `~/.claude/learning/db/costs.db`
- [ ] SQLite3 module installed: `npm install sqlite3`
- [ ] Budget limits set appropriately for your use case
- [ ] Monitoring/alerting configured for approaching limits
- [ ] Audit logging enabled for compliance
- [ ] Emergency stop procedure documented
- [ ] Daily/monthly budget reset behavior tested
- [ ] Multiple concurrent enforcer sessions tested

### Health Check

```javascript
async function healthCheckCostEnforcer() {
  try {
    const db = new CostDatabase()
    await db.init()
    
    const enforcer = new CostEnforcer(db)
    await enforcer.initialize()
    
    const report = await enforcer.getReport()
    
    await db.close()

    return {
      status: 'healthy',
      database_path: CONFIG.db_path,
      session: report.session,
      daily: report.daily,
      monthly: report.monthly,
    }
  } catch (err) {
    return {
      status: 'unhealthy',
      error: err.message,
    }
  }
}
```

## Troubleshooting Integration

### Issue: "Database is locked"

Multiple enforcer instances accessing DB simultaneously.

```javascript
// WRONG: Creating new enforcer for each call
for (const item of items) {
  const enforcer = new CostEnforcer(new CostDatabase())
  await enforcer.checkBudget(...)
}

// RIGHT: Reuse enforcer throughout session
const db = new CostDatabase()
const enforcer = new CostEnforcer(db)
for (const item of items) {
  await enforcer.checkBudget(...)
}
await db.close()
```

### Issue: Costs not recording

Check that `recordCost()` is called after every API call:

```javascript
// WRONG
const check = await enforcer.checkBudget(...)
if (check.allowed) {
  await callApi(...)
  // Missing: await enforcer.recordCost(...)
}

// RIGHT
const check = await enforcer.checkBudget(...)
if (check.allowed) {
  const response = await callApi(...)
  await enforcer.recordCost(model, response.tokens.input, response.tokens.output)
}
```

## Best Practices

1. **Always check before calling**: Never skip budget checks
2. **Record actual costs**: Use real token counts from API responses
3. **Handle rejections gracefully**: Don't just throw errors, provide user feedback
4. **Monitor approaching limits**: Alert when approaching 80% of any limit
5. **Batch expensive operations**: Process in smaller batches to avoid single session exhaustion
6. **Review daily reports**: Audit costs regularly to identify trends
7. **Set conservative initial limits**: Start low, increase if needed
8. **Test budget rejection paths**: Ensure emergency stop works correctly

## Support

For issues or questions:

1. Check `~/.claude/learning/db/costs-audit.jsonl` for cost history
2. Review `~/.claude/learning/db/costs.db` schema
3. Run test suite: `node test-cost-enforcer.js`
4. Enable debug logging: `DEBUG=cost-enforcer node your-app.js`
