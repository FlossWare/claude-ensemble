#!/usr/bin/env node
/**
 * Cost Enforcer Test Suite
 *
 * Demonstrates usage and tests enforcement behavior:
 * - Budget checking
 * - Cost recording
 * - Reporting
 * - Budget limit changes
 * - Alert thresholds
 */

const { CostDatabase, CostEnforcer, generateSessionId, getDateKey, getMonthKey } = require('./cost-enforcer')
const path = require('path')
const os = require('os')

// Use test database
const TEST_DB_PATH = path.join(process.env.HOME || os.homedir(), '.claude/learning/db/costs-test.db')

async function testCostEnforcer() {
  console.log('╔════════════════════════════════════════════════════════════╗')
  console.log('║        COST ENFORCER TEST SUITE                            ║')
  console.log('╚════════════════════════════════════════════════════════════╝\n')

  const db = new CostDatabase(TEST_DB_PATH)
  console.log(`[INIT] Initializing database: ${TEST_DB_PATH}`)
  await db.init()

  const enforcer = new CostEnforcer(db)
  const sessionId = await enforcer.initialize(generateSessionId())
  console.log(`[INIT] Session ID: ${sessionId}\n`)

  // ========================================================================
  // TEST 1: Budget Checking - Within Limits
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 1: Budget Check - Within Limits')
  console.log('─'.repeat(60))

  const check1 = await enforcer.checkBudget('claude-opus', 1000, 500)
  console.log('Checking budget for: Claude Opus (1000 in, 500 out tokens)')
  console.log(`  Allowed: ${check1.allowed}`)
  console.log(`  Cost: $${check1.cost.toFixed(4)}`)
  console.log(`  Daily: $${check1.daily.spent.toFixed(2)} -> $${check1.daily.projected.toFixed(2)} / $${check1.daily.limit.toFixed(2)}`)
  console.log(`  Session: $${check1.session.spent.toFixed(2)} -> $${check1.session.projected.toFixed(2)} / $${check1.session.limit.toFixed(2)}`)
  console.log(`  Warnings: ${check1.warnings.length > 0 ? check1.warnings.join(', ') : 'None'}\n`)

  // ========================================================================
  // TEST 2: Record Multiple Costs
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 2: Recording Multiple Costs')
  console.log('─'.repeat(60))

  const calls = [
    { model: 'claude-opus', input: 2000, output: 1000, label: 'code-review' },
    { model: 'claude-sonnet', input: 1500, output: 800, label: 'summarization' },
    { model: 'claude-haiku', input: 500, output: 300, label: 'classification' },
    { model: 'claude-opus', input: 3000, output: 1500, label: 'planning' },
  ]

  for (const call of calls) {
    const record = await enforcer.recordCost(call.model, call.input, call.output, {
      workflow_id: 'test-workflow',
      label: call.label,
    })
    console.log(`[${call.label.padEnd(20)}] ${call.model.padEnd(15)} ` +
                `$${record.cost.total_cost.toFixed(4)} (allowed: ${record.allowed ? 'YES' : 'NO'})`)
  }

  const sessionSpent = await enforcer.getSessionSpent(sessionId)
  console.log(`\nSession Total: $${sessionSpent.toFixed(4)}\n`)

  // ========================================================================
  // TEST 3: Approaching Limit Warnings
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 3: Budget Approaching Limits')
  console.log('─'.repeat(60))

  // Add calls to reach 80% of session budget ($20 of $25)
  const remainingSession = 25 - sessionSpent
  console.log(`Session remaining: $${remainingSession.toFixed(2)}`)

  if (remainingSession > 5) {
    const check3 = await enforcer.checkBudget('claude-opus', 3000, 1500)
    console.log(`\nBudget check for large call (would add $${check3.cost.toFixed(4)}):`)
    console.log(`  Allowed: ${check3.allowed}`)
    if (check3.warnings.length > 0) {
      console.log(`  Warnings:`)
      check3.warnings.forEach(w => console.log(`    - ${w}`))
    }
  }

  console.log()

  // ========================================================================
  // TEST 4: Daily Spending Query
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 4: Daily Spending Query')
  console.log('─'.repeat(60))

  const dailySpent = await enforcer.getDailySpent()
  console.log(`Date: ${getDateKey()}`)
  console.log(`Daily spending: $${dailySpent.toFixed(4)}`)
  console.log(`Daily limit: $50.00`)
  console.log(`Usage: ${((dailySpent / 50) * 100).toFixed(1)}%\n`)

  // ========================================================================
  // TEST 5: Cost Report
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 5: Comprehensive Cost Report')
  console.log('─'.repeat(60))

  const report = await enforcer.getReport()

  console.log(`\nSESSION:`)
  console.log(`  ID: ${report.session.id}`)
  console.log(`  Total: $${report.session.total_cost.toFixed(4)} / $${report.session.limit.toFixed(2)}`)
  console.log(`  Calls: ${report.session.calls} (rejected: ${report.session.rejected})`)

  console.log(`\nDAILY (${report.daily.date}):`)
  console.log(`  Total: $${report.daily.total_cost.toFixed(4)} / $${report.daily.limit.toFixed(2)}`)
  console.log(`  Calls: ${report.daily.calls} (rejected: ${report.daily.rejected})`)
  console.log(`  Usage: ${report.daily.usage_percent}%`)

  console.log(`\nMONTHLY (${report.monthly.month}):`)
  console.log(`  Total: $${report.monthly.total_cost.toFixed(4)} / $${report.monthly.limit.toFixed(2)}`)
  console.log(`  Calls: ${report.monthly.calls} (rejected: ${report.monthly.rejected})`)
  console.log(`  Usage: ${report.monthly.usage_percent}%`)

  if (report.recent_daily.length > 0) {
    console.log(`\nRECENT CALLS TODAY (last 5):`)
    report.recent_daily.slice(0, 5).forEach((call, i) => {
      console.log(`  ${i + 1}. [${call.label || 'unlabeled'}] ${call.model} $${call.total_cost.toFixed(4)}`)
    })
  }

  console.log()

  // ========================================================================
  // TEST 6: Budget Limit Changes
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 6: Updating Budget Limits')
  console.log('─'.repeat(60))

  console.log(`\nOld limits:`)
  console.log(`  Daily: $50.00`)
  console.log(`  Monthly: $1000.00`)
  console.log(`  Session: $25.00`)

  const newLimits = await enforcer.setBudgetLimits(100.00, 2000.00, 50.00)

  console.log(`\nNew limits:`)
  console.log(`  Daily: $${newLimits.daily.toFixed(2)}`)
  console.log(`  Monthly: $${newLimits.monthly.toFixed(2)}`)
  console.log(`  Session: $${newLimits.session.toFixed(2)}`)

  // Check budget with new limits
  const check6 = await enforcer.checkBudget('claude-opus', 5000, 2500)
  console.log(`\nBudget check with new limits (would add $${check6.cost.toFixed(4)}):`)
  console.log(`  Allowed: ${check6.allowed}`)
  console.log(`  Session: $${check6.session.projected.toFixed(2)} / $${check6.session.limit.toFixed(2)}`)

  console.log()

  // ========================================================================
  // TEST 7: Model Variety
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 7: Different Model Pricing')
  console.log('─'.repeat(60))

  const models = [
    { name: 'claude-opus', tokens: 1000 },
    { name: 'claude-sonnet', tokens: 1000 },
    { name: 'claude-haiku', tokens: 1000 },
    { name: 'gpt-4o', tokens: 1000 },
  ]

  console.log(`\nCost comparison (1000 input + 500 output tokens):\n`)
  for (const m of models) {
    const check = await enforcer.checkBudget(m.name, 1000, 500)
    console.log(`  ${m.name.padEnd(20)} $${check.cost.toFixed(4)}`)
  }

  console.log()

  // ========================================================================
  // TEST 8: Query Database
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('TEST 8: Database Queries')
  console.log('─'.repeat(60))

  const allEntries = await db.all('SELECT COUNT(*) as count FROM cost_entries')
  console.log(`\nTotal entries in database: ${allEntries[0]?.count || 0}`)

  const byModel = await db.all(`
    SELECT model, COUNT(*) as calls, SUM(total_cost) as total
    FROM cost_entries
    GROUP BY model
    ORDER BY total DESC
  `)

  if (byModel.length > 0) {
    console.log(`\nCost by model:`)
    byModel.forEach(row => {
      console.log(`  ${row.model.padEnd(20)} ${row.calls} calls: $${row.total.toFixed(4)}`)
    })
  }

  const rejected = await db.all('SELECT * FROM cost_entries WHERE rejected = 1')
  console.log(`\nRejected calls: ${rejected.length}`)
  if (rejected.length > 0) {
    rejected.forEach(r => {
      console.log(`  - ${r.model}: ${r.rejection_reason}`)
    })
  }

  console.log()

  // ========================================================================
  // CLEANUP
  // ========================================================================
  console.log('─'.repeat(60))
  console.log('CLEANUP')
  console.log('─'.repeat(60))

  await db.close()
  console.log('\nDatabase connection closed.')
  console.log(`Test database: ${TEST_DB_PATH}`)
  console.log(`\n✓ All tests completed successfully\n`)
}

// Run tests
testCostEnforcer().catch(err => {
  console.error('\n✗ Test failed:', err)
  process.exit(1)
})
