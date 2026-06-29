export const meta = {
  name: 'ai-cost-tracker',
  description: 'Track token usage and costs per agent call, enforce per-workflow budgets, and generate cost reports',
  whenToUse: 'When you need to monitor spending, enforce budget limits, or generate cost reports for multi-AI workflows',
  phases: [
    { title: 'Init', detail: 'Load model pricing and budget configuration' },
    { title: 'Track', detail: 'Record token usage and compute costs' },
    { title: 'Report', detail: 'Generate cost summary and budget status' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// ============================================================================
// USAGE:
//
// --- Track a single agent call ---
// const result = await workflow('ai-cost-tracker', {
//   action: 'track',
//   model: 'opus',
//   input_tokens: 1500,
//   output_tokens: 800,
//   workflow_id: 'code-review-1234',
//   label: 'security-worker',
// })
//
// --- Get accumulated cost for the current session ---
// const cost = await workflow('ai-cost-tracker', { action: 'getCost' })
//
// --- Get remaining budget ---
// const budget = await workflow('ai-cost-tracker', {
//   action: 'getRemainingBudget',
//   workflow_id: 'code-review-1234',
// })
//
// --- Check if a call would exceed budget before making it ---
// const check = await workflow('ai-cost-tracker', {
//   action: 'checkBudget',
//   model: 'opus',
//   estimated_input_tokens: 2000,
//   estimated_output_tokens: 1000,
//   workflow_id: 'code-review-1234',
// })
//
// --- Generate a cost report ---
// const report = await workflow('ai-cost-tracker', { action: 'report' })
//
// --- Reset session tracking ---
// const reset = await workflow('ai-cost-tracker', { action: 'reset' })
// ============================================================================

// ============================================================================
// MODEL PRICING CONFIG
// ============================================================================

// Default pricing per 1K tokens (USD). These are overridden by model-config.json
// if it contains cost_per_1k_tokens, cost_per_1k_input, or cost_per_1k_output fields.
const DEFAULT_PRICING = {
  opus: {
    cost_per_1k_input: 0.015,
    cost_per_1k_output: 0.075,
  },
  sonnet: {
    cost_per_1k_input: 0.003,
    cost_per_1k_output: 0.015,
  },
  haiku: {
    cost_per_1k_input: 0.00025,
    cost_per_1k_output: 0.00125,
  },
  gemini: {
    cost_per_1k_input: 0.00035,
    cost_per_1k_output: 0.0014,
  },
}

// Default budget limits
const DEFAULT_BUDGET = {
  per_workflow_max_dollars: 5.00,
  per_session_max_dollars: 25.00,
  warn_at_percent: 80,
}

// ============================================================================
// LOAD MODEL CONFIG (pricing overrides)
// ============================================================================

function loadModelPricing() {
  const pricing = {}
  // Deep-copy defaults
  for (const [k, v] of Object.entries(DEFAULT_PRICING)) {
    pricing[k] = { ...v }
  }

  try {
    const fs = require('fs')
    const configPath = '~/.claude/repos/claude-global-skills/model-config.json'
    const raw = fs.readFileSync(configPath, 'utf-8')
    const config = JSON.parse(raw)

    if (config.models) {
      for (const [id, modelCfg] of Object.entries(config.models)) {
        if (!pricing[id]) {
          pricing[id] = {}
        }

        // Support both granular and unified cost_per_1k_tokens
        if (modelCfg.cost_per_1k_input !== undefined) {
          pricing[id].cost_per_1k_input = modelCfg.cost_per_1k_input
        }
        if (modelCfg.cost_per_1k_output !== undefined) {
          pricing[id].cost_per_1k_output = modelCfg.cost_per_1k_output
        }
        if (modelCfg.cost_per_1k_tokens !== undefined) {
          // Unified rate applies as fallback for input and output
          pricing[id].cost_per_1k_input = pricing[id].cost_per_1k_input || modelCfg.cost_per_1k_tokens
          pricing[id].cost_per_1k_output = pricing[id].cost_per_1k_output || modelCfg.cost_per_1k_tokens
        }
      }
    }

    // Support top-level budget overrides
    if (config.budget) {
      return { pricing, budget: { ...DEFAULT_BUDGET, ...config.budget } }
    }

    return { pricing, budget: { ...DEFAULT_BUDGET } }
  } catch (_err) {
    // No external config or parse error; use defaults
    return { pricing, budget: { ...DEFAULT_BUDGET } }
  }
}

// ============================================================================
// SESSION COST STORE (persisted to disk)
// ============================================================================

const COST_LOG_PATH = '~/.claude/repos/claude-global-skills/memory/cost-tracking.json'

function loadCostStore() {
  try {
    const fs = require('fs')
    const raw = fs.readFileSync(COST_LOG_PATH, 'utf-8')
    return JSON.parse(raw)
  } catch (_err) {
    return {
      session_id: `session_${args?._timestamp || 'exec'}`,
      started_at: args?._timestamp || 'timestamp-at-runtime',
      entries: [],
      workflow_totals: {},
      session_total_usd: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
    }
  }
}

function saveCostStore(store) {
  try {
    const fs = require('fs')
    const path = require('path')
    const dir = path.dirname(COST_LOG_PATH)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }
    fs.writeFileSync(COST_LOG_PATH, JSON.stringify(store, null, 2), 'utf-8')
  } catch (err) {
    log(`WARNING: Could not persist cost data: ${err.message}`)
  }
}

// ============================================================================
// COST CALCULATION
// ============================================================================

function calculateCost(model, inputTokens, outputTokens, pricing) {
  const modelPricing = pricing[model] || pricing[model.toLowerCase()]

  if (!modelPricing) {
    // Unknown model - estimate using Sonnet pricing as a conservative middle ground
    log(`WARNING: No pricing data for model "${model}". Using Sonnet pricing as fallback.`)
    const fallback = pricing.sonnet || { cost_per_1k_input: 0.003, cost_per_1k_output: 0.015 }
    return {
      input_cost: (inputTokens / 1000) * fallback.cost_per_1k_input,
      output_cost: (outputTokens / 1000) * fallback.cost_per_1k_output,
      total_cost: (inputTokens / 1000) * fallback.cost_per_1k_input + (outputTokens / 1000) * fallback.cost_per_1k_output,
      pricing_source: 'fallback (sonnet)',
    }
  }

  const inputCost = (inputTokens / 1000) * (modelPricing.cost_per_1k_input || 0)
  const outputCost = (outputTokens / 1000) * (modelPricing.cost_per_1k_output || 0)

  return {
    input_cost: inputCost,
    output_cost: outputCost,
    total_cost: inputCost + outputCost,
    pricing_source: 'config',
  }
}

// ============================================================================
// BUDGET ENFORCEMENT
// ============================================================================

function checkBudgetLimit(store, workflowId, additionalCost, budgetConfig) {
  const result = {
    allowed: true,
    warnings: [],
    workflow_spent: 0,
    session_spent: store.session_total_usd,
    workflow_budget: budgetConfig.per_workflow_max_dollars,
    session_budget: budgetConfig.per_session_max_dollars,
  }

  // Check workflow-level budget
  if (workflowId) {
    const workflowSpent = (store.workflow_totals[workflowId] || { total_usd: 0 }).total_usd
    result.workflow_spent = workflowSpent
    const projectedWorkflow = workflowSpent + additionalCost

    const warnThreshold = budgetConfig.per_workflow_max_dollars * (budgetConfig.warn_at_percent / 100)
    if (projectedWorkflow > budgetConfig.per_workflow_max_dollars) {
      result.allowed = false
      result.warnings.push(
        `BUDGET EXCEEDED: Workflow "${workflowId}" would reach $${projectedWorkflow.toFixed(4)} ` +
        `(limit: $${budgetConfig.per_workflow_max_dollars.toFixed(2)})`
      )
    } else if (projectedWorkflow > warnThreshold) {
      result.warnings.push(
        `BUDGET WARNING: Workflow "${workflowId}" at $${projectedWorkflow.toFixed(4)} ` +
        `(${((projectedWorkflow / budgetConfig.per_workflow_max_dollars) * 100).toFixed(1)}% of $${budgetConfig.per_workflow_max_dollars.toFixed(2)} limit)`
      )
    }
  }

  // Check session-level budget
  const projectedSession = store.session_total_usd + additionalCost
  const sessionWarnThreshold = budgetConfig.per_session_max_dollars * (budgetConfig.warn_at_percent / 100)

  if (projectedSession > budgetConfig.per_session_max_dollars) {
    result.allowed = false
    result.warnings.push(
      `SESSION BUDGET EXCEEDED: Would reach $${projectedSession.toFixed(4)} ` +
      `(limit: $${budgetConfig.per_session_max_dollars.toFixed(2)})`
    )
  } else if (projectedSession > sessionWarnThreshold) {
    result.warnings.push(
      `SESSION BUDGET WARNING: At $${projectedSession.toFixed(4)} ` +
      `(${((projectedSession / budgetConfig.per_session_max_dollars) * 100).toFixed(1)}% of $${budgetConfig.per_session_max_dollars.toFixed(2)} limit)`
    )
  }

  result.workflow_remaining = workflowId
    ? budgetConfig.per_workflow_max_dollars - ((store.workflow_totals[workflowId] || { total_usd: 0 }).total_usd + additionalCost)
    : null
  result.session_remaining = budgetConfig.per_session_max_dollars - projectedSession

  return result
}

// ============================================================================
// REPORT GENERATION
// ============================================================================

function generateReport(store, pricing, budgetConfig) {
  const lines = []
  lines.push('='.repeat(64))
  lines.push('COST TRACKING REPORT')
  lines.push('='.repeat(64))
  lines.push(`Session: ${store.session_id}`)
  lines.push(`Started: ${store.started_at}`)
  lines.push(`Generated: ${args?._timestamp || 'timestamp-at-runtime'}`)
  lines.push('')

  // Session totals
  lines.push('--- SESSION TOTALS ---')
  lines.push(`Total cost:          $${store.session_total_usd.toFixed(6)}`)
  lines.push(`Total input tokens:  ${store.total_input_tokens.toLocaleString()}`)
  lines.push(`Total output tokens: ${store.total_output_tokens.toLocaleString()}`)
  lines.push(`Total calls:         ${store.entries.length}`)
  lines.push(`Session budget:      $${budgetConfig.per_session_max_dollars.toFixed(2)}`)
  lines.push(`Session remaining:   $${Math.max(0, budgetConfig.per_session_max_dollars - store.session_total_usd).toFixed(6)}`)
  lines.push(`Budget used:         ${((store.session_total_usd / budgetConfig.per_session_max_dollars) * 100).toFixed(2)}%`)
  lines.push('')

  // Per-workflow breakdown
  const workflows = Object.entries(store.workflow_totals)
  if (workflows.length > 0) {
    lines.push('--- PER-WORKFLOW BREAKDOWN ---')
    lines.push(
      `${'Workflow'.padEnd(30)} ${'Cost'.padStart(12)} ${'Calls'.padStart(8)} ` +
      `${'In Tokens'.padStart(12)} ${'Out Tokens'.padStart(12)} ${'Budget %'.padStart(10)}`
    )
    lines.push('-'.repeat(84))

    for (const [wfId, wfData] of workflows.sort((a, b) => b[1].total_usd - a[1].total_usd)) {
      const budgetPct = ((wfData.total_usd / budgetConfig.per_workflow_max_dollars) * 100).toFixed(1)
      lines.push(
        `${wfId.substring(0, 30).padEnd(30)} ` +
        `$${wfData.total_usd.toFixed(6).padStart(11)} ` +
        `${String(wfData.calls).padStart(8)} ` +
        `${wfData.input_tokens.toLocaleString().padStart(12)} ` +
        `${wfData.output_tokens.toLocaleString().padStart(12)} ` +
        `${budgetPct.padStart(9)}%`
      )
    }
    lines.push('')
  }

  // Per-model breakdown
  const modelBreakdown = {}
  for (const entry of store.entries) {
    if (!modelBreakdown[entry.model]) {
      modelBreakdown[entry.model] = { total_usd: 0, calls: 0, input_tokens: 0, output_tokens: 0 }
    }
    modelBreakdown[entry.model].total_usd += entry.total_cost
    modelBreakdown[entry.model].calls += 1
    modelBreakdown[entry.model].input_tokens += entry.input_tokens
    modelBreakdown[entry.model].output_tokens += entry.output_tokens
  }

  const models = Object.entries(modelBreakdown)
  if (models.length > 0) {
    lines.push('--- PER-MODEL BREAKDOWN ---')
    lines.push(
      `${'Model'.padEnd(16)} ${'Cost'.padStart(12)} ${'Calls'.padStart(8)} ` +
      `${'In Tokens'.padStart(12)} ${'Out Tokens'.padStart(12)} ${'Avg $/call'.padStart(12)}`
    )
    lines.push('-'.repeat(72))

    for (const [modelId, mData] of models.sort((a, b) => b[1].total_usd - a[1].total_usd)) {
      const avgCost = mData.calls > 0 ? mData.total_usd / mData.calls : 0
      lines.push(
        `${modelId.padEnd(16)} ` +
        `$${mData.total_usd.toFixed(6).padStart(11)} ` +
        `${String(mData.calls).padStart(8)} ` +
        `${mData.input_tokens.toLocaleString().padStart(12)} ` +
        `${mData.output_tokens.toLocaleString().padStart(12)} ` +
        `$${avgCost.toFixed(6).padStart(11)}`
      )
    }
    lines.push('')
  }

  // Recent entries (last 10)
  if (store.entries.length > 0) {
    const recent = store.entries.slice(-10)
    lines.push(`--- RECENT CALLS (last ${recent.length} of ${store.entries.length}) ---`)
    lines.push(
      `${'Time'.padEnd(22)} ${'Model'.padEnd(10)} ${'Label'.padEnd(20)} ` +
      `${'Cost'.padStart(12)} ${'In'.padStart(8)} ${'Out'.padStart(8)}`
    )
    lines.push('-'.repeat(80))

    for (const entry of recent) {
      const time = entry.timestamp ? entry.timestamp.substring(11, 19) : '??:??:??'
      lines.push(
        `${time.padEnd(22)} ` +
        `${(entry.model || '?').padEnd(10)} ` +
        `${(entry.label || '-').substring(0, 20).padEnd(20)} ` +
        `$${entry.total_cost.toFixed(6).padStart(11)} ` +
        `${String(entry.input_tokens).padStart(8)} ` +
        `${String(entry.output_tokens).padStart(8)}`
      )
    }
    lines.push('')
  }

  // Pricing reference
  lines.push('--- PRICING REFERENCE ---')
  for (const [modelId, rates] of Object.entries(pricing)) {
    lines.push(`  ${modelId}: $${rates.cost_per_1k_input}/1K input, $${rates.cost_per_1k_output}/1K output`)
  }
  lines.push('')
  lines.push('='.repeat(64))

  return lines.join('\n')
}

// ============================================================================
// ACTION: getCost
// ============================================================================

function getCost(store, workflowId) {
  if (workflowId) {
    const wfData = store.workflow_totals[workflowId]
    return {
      workflow_id: workflowId,
      total_usd: wfData ? wfData.total_usd : 0,
      calls: wfData ? wfData.calls : 0,
      input_tokens: wfData ? wfData.input_tokens : 0,
      output_tokens: wfData ? wfData.output_tokens : 0,
    }
  }

  return {
    session_total_usd: store.session_total_usd,
    total_calls: store.entries.length,
    total_input_tokens: store.total_input_tokens,
    total_output_tokens: store.total_output_tokens,
    workflows: Object.keys(store.workflow_totals),
  }
}

// ============================================================================
// ACTION: getRemainingBudget
// ============================================================================

function getRemainingBudget(store, workflowId, budgetConfig) {
  const sessionRemaining = Math.max(0, budgetConfig.per_session_max_dollars - store.session_total_usd)

  const result = {
    session_remaining_usd: sessionRemaining,
    session_budget_usd: budgetConfig.per_session_max_dollars,
    session_used_usd: store.session_total_usd,
    session_used_percent: ((store.session_total_usd / budgetConfig.per_session_max_dollars) * 100),
  }

  if (workflowId) {
    const wfSpent = (store.workflow_totals[workflowId] || { total_usd: 0 }).total_usd
    result.workflow_id = workflowId
    result.workflow_remaining_usd = Math.max(0, budgetConfig.per_workflow_max_dollars - wfSpent)
    result.workflow_budget_usd = budgetConfig.per_workflow_max_dollars
    result.workflow_used_usd = wfSpent
    result.workflow_used_percent = ((wfSpent / budgetConfig.per_workflow_max_dollars) * 100)
  }

  return result
}

// ============================================================================
// ACTION: track
// ============================================================================

function trackCall(store, model, inputTokens, outputTokens, workflowId, label, pricing, budgetConfig) {
  const cost = calculateCost(model, inputTokens, outputTokens, pricing)

  // Enforce budget before recording
  const budgetCheck = checkBudgetLimit(store, workflowId, cost.total_cost, budgetConfig)

  const entry = {
    timestamp: args?._timestamp || 'timestamp-at-runtime',
    model,
    label: label || null,
    workflow_id: workflowId || null,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    input_cost: cost.input_cost,
    output_cost: cost.output_cost,
    total_cost: cost.total_cost,
    pricing_source: cost.pricing_source,
    budget_allowed: budgetCheck.allowed,
  }

  // Always record the entry (even if over budget) so the log is complete
  store.entries.push(entry)
  store.session_total_usd += cost.total_cost
  store.total_input_tokens += inputTokens
  store.total_output_tokens += outputTokens

  // Update workflow totals
  if (workflowId) {
    if (!store.workflow_totals[workflowId]) {
      store.workflow_totals[workflowId] = {
        total_usd: 0,
        calls: 0,
        input_tokens: 0,
        output_tokens: 0,
        first_call: entry.timestamp,
      }
    }
    const wf = store.workflow_totals[workflowId]
    wf.total_usd += cost.total_cost
    wf.calls += 1
    wf.input_tokens += inputTokens
    wf.output_tokens += outputTokens
    wf.last_call = entry.timestamp
  }

  saveCostStore(store)

  return {
    entry,
    budget: budgetCheck,
    session_total_usd: store.session_total_usd,
  }
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const action = args.action || (typeof args === 'string' ? args : 'report')

if (!action) {
  log('ERROR: No action provided')
  log('')
  log('Usage:')
  log('  workflow("ai-cost-tracker", { action: "track", model: "opus", input_tokens: 1000, output_tokens: 500 })')
  log('  workflow("ai-cost-tracker", { action: "getCost" })')
  log('  workflow("ai-cost-tracker", { action: "getCost", workflow_id: "my-workflow" })')
  log('  workflow("ai-cost-tracker", { action: "getRemainingBudget" })')
  log('  workflow("ai-cost-tracker", { action: "checkBudget", model: "opus", estimated_input_tokens: 2000 })')
  log('  workflow("ai-cost-tracker", { action: "report" })')
  log('  workflow("ai-cost-tracker", { action: "reset" })')
  return { error: 'No action provided' }
}

// PHASE 1: Init - Load pricing and budget config
phase('Init')

const { pricing, budget: budgetConfig } = loadModelPricing()
const store = loadCostStore()

log('='.repeat(60))
log('AI COST TRACKER')
log('='.repeat(60))
log(`Action: ${action}`)
log(`Session: ${store.session_id}`)
log(`Models with pricing: ${Object.keys(pricing).join(', ')}`)
log(`Per-workflow budget: $${budgetConfig.per_workflow_max_dollars.toFixed(2)}`)
log(`Per-session budget:  $${budgetConfig.per_session_max_dollars.toFixed(2)}`)
log('')

// PHASE 2: Track - Execute the requested action
phase('Track')

let result

switch (action) {
  case 'track': {
    const model = args.model
    const inputTokens = args.input_tokens || 0
    const outputTokens = args.output_tokens || 0
    const workflowId = args.workflow_id || null
    const label = args.label || null

    if (!model) {
      log('ERROR: "model" is required for track action')
      return { error: 'model is required for track action' }
    }

    result = trackCall(store, model, inputTokens, outputTokens, workflowId, label, pricing, budgetConfig)

    log(`Tracked: ${model} call`)
    log(`  Input tokens:  ${inputTokens.toLocaleString()}`)
    log(`  Output tokens: ${outputTokens.toLocaleString()}`)
    log(`  Call cost:     $${result.entry.total_cost.toFixed(6)}`)
    log(`  Session total: $${result.session_total_usd.toFixed(6)}`)

    if (result.budget.warnings.length > 0) {
      log('')
      for (const warning of result.budget.warnings) {
        log(`  ** ${warning}`)
      }
    }

    if (!result.budget.allowed) {
      log('')
      log('  !! BUDGET LIMIT REACHED - Further calls may be blocked !!')
    }
    break
  }

  case 'getCost': {
    result = getCost(store, args.workflow_id || null)

    if (args.workflow_id) {
      log(`Cost for workflow "${args.workflow_id}":`)
      log(`  Total: $${result.total_usd.toFixed(6)}`)
      log(`  Calls: ${result.calls}`)
      log(`  Input tokens:  ${result.input_tokens.toLocaleString()}`)
      log(`  Output tokens: ${result.output_tokens.toLocaleString()}`)
    } else {
      log(`Session cost summary:`)
      log(`  Total: $${result.session_total_usd.toFixed(6)}`)
      log(`  Calls: ${result.total_calls}`)
      log(`  Input tokens:  ${result.total_input_tokens.toLocaleString()}`)
      log(`  Output tokens: ${result.total_output_tokens.toLocaleString()}`)
      log(`  Workflows: ${result.workflows.length}`)
    }
    break
  }

  case 'getRemainingBudget': {
    result = getRemainingBudget(store, args.workflow_id || null, budgetConfig)

    log(`Session budget:`)
    log(`  Used:      $${result.session_used_usd.toFixed(6)} (${result.session_used_percent.toFixed(1)}%)`)
    log(`  Remaining: $${result.session_remaining_usd.toFixed(6)}`)
    log(`  Limit:     $${result.session_budget_usd.toFixed(2)}`)

    if (result.workflow_id) {
      log('')
      log(`Workflow "${result.workflow_id}" budget:`)
      log(`  Used:      $${result.workflow_used_usd.toFixed(6)} (${result.workflow_used_percent.toFixed(1)}%)`)
      log(`  Remaining: $${result.workflow_remaining_usd.toFixed(6)}`)
      log(`  Limit:     $${result.workflow_budget_usd.toFixed(2)}`)
    }
    break
  }

  case 'checkBudget': {
    const model = args.model || 'sonnet'
    const estInput = args.estimated_input_tokens || 0
    const estOutput = args.estimated_output_tokens || 0
    const workflowId = args.workflow_id || null

    const estCost = calculateCost(model, estInput, estOutput, pricing)
    result = checkBudgetLimit(store, workflowId, estCost.total_cost, budgetConfig)
    result.estimated_cost = estCost.total_cost
    result.model = model

    log(`Budget check for ${model}:`)
    log(`  Estimated cost: $${estCost.total_cost.toFixed(6)}`)
    log(`  Allowed: ${result.allowed ? 'YES' : 'NO'}`)

    if (result.warnings.length > 0) {
      for (const warning of result.warnings) {
        log(`  ** ${warning}`)
      }
    }
    break
  }

  case 'report': {
    // Report phase handles this
    result = { action: 'report' }
    break
  }

  case 'reset': {
    const newStore = {
      session_id: `session_${args?._timestamp || 'exec'}`,
      started_at: args?._timestamp || 'timestamp-at-runtime',
      entries: [],
      workflow_totals: {},
      session_total_usd: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
    }
    saveCostStore(newStore)
    result = { status: 'reset', session_id: newStore.session_id }
    log('Cost tracking data has been reset.')
    log(`New session: ${newStore.session_id}`)
    break
  }

  default: {
    log(`ERROR: Unknown action "${action}"`)
    log('Valid actions: track, getCost, getRemainingBudget, checkBudget, report, reset')
    return { error: `Unknown action: ${action}` }
  }
}

// PHASE 3: Report
phase('Report')

if (action === 'report') {
  const reportText = generateReport(store, pricing, budgetConfig)
  log(reportText)

  result = {
    status: 'success',
    session_id: store.session_id,
    session_total_usd: store.session_total_usd,
    total_calls: store.entries.length,
    total_input_tokens: store.total_input_tokens,
    total_output_tokens: store.total_output_tokens,
    workflow_count: Object.keys(store.workflow_totals).length,
    workflows: store.workflow_totals,
    budget: {
      per_workflow_max_dollars: budgetConfig.per_workflow_max_dollars,
      per_session_max_dollars: budgetConfig.per_session_max_dollars,
      session_remaining: Math.max(0, budgetConfig.per_session_max_dollars - store.session_total_usd),
      session_used_percent: ((store.session_total_usd / budgetConfig.per_session_max_dollars) * 100),
    },
    report: reportText,
  }
} else {
  log('')
  log(`Session running total: $${store.session_total_usd.toFixed(6)} / $${budgetConfig.per_session_max_dollars.toFixed(2)}`)
}

log('')
log('='.repeat(60))

return result

}
