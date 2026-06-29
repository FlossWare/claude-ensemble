# AI Cost Tracker - Token Usage and Budget Enforcement

Tracks token usage and costs per agent call across multi-AI workflows, enforces per-workflow and per-session budget limits, and generates detailed cost reports.

## Features

- **Per-Call Cost Tracking** - Records input/output tokens and computes USD cost for every agent call
- **Model Pricing from Config** - Reads `cost_per_1k_tokens` / `cost_per_1k_input` / `cost_per_1k_output` from model-config.json; falls back to built-in Anthropic pricing
- **Per-Workflow Budget Enforcement** - Enforces `per_workflow_max_dollars` limit; blocks calls that would exceed the cap
- **Per-Session Budget Enforcement** - Enforces `per_session_max_dollars` across all workflows in a session
- **Early Warnings** - Emits warnings at configurable threshold (default 80%) before budget is exhausted
- **Persistent Cost Log** - Stores all entries to `memory/cost-tracking.json` for cross-session analysis
- **Detailed Reports** - Generates tabular breakdowns by session, workflow, model, and recent calls

## Quick Start

```bash
# Generate a cost report for the current session
/ai-cost-tracker

# Track an agent call
/ai-cost-tracker { "action": "track", "model": "opus", "input_tokens": 1500, "output_tokens": 800 }

# Check remaining budget
/ai-cost-tracker { "action": "getRemainingBudget", "workflow_id": "code-review-run-42" }
```

## Actions

### track

Record token usage for a single agent call.

```javascript
workflow('ai-cost-tracker', {
  action: 'track',
  model: 'opus',                    // required - model id
  input_tokens: 1500,               // tokens sent to the model
  output_tokens: 800,               // tokens received from the model
  workflow_id: 'code-review-1234',  // optional - groups costs by workflow
  label: 'security-worker',         // optional - human-readable label
})
```

Returns:
```json
{
  "entry": {
    "timestamp": "2026-06-10T12:00:00.000Z",
    "model": "opus",
    "label": "security-worker",
    "workflow_id": "code-review-1234",
    "input_tokens": 1500,
    "output_tokens": 800,
    "input_cost": 0.0225,
    "output_cost": 0.06,
    "total_cost": 0.0825,
    "pricing_source": "config",
    "budget_allowed": true
  },
  "budget": {
    "allowed": true,
    "warnings": [],
    "workflow_spent": 0.0825,
    "session_spent": 0.0825,
    "workflow_remaining": 4.9175,
    "session_remaining": 24.9175
  },
  "session_total_usd": 0.0825
}
```

### getCost

Retrieve accumulated cost for the session or a specific workflow.

```javascript
// Session-wide cost
workflow('ai-cost-tracker', { action: 'getCost' })

// Workflow-specific cost
workflow('ai-cost-tracker', { action: 'getCost', workflow_id: 'code-review-1234' })
```

### getRemainingBudget

Check how much budget remains before hitting limits.

```javascript
// Session budget
workflow('ai-cost-tracker', { action: 'getRemainingBudget' })

// Workflow + session budget
workflow('ai-cost-tracker', {
  action: 'getRemainingBudget',
  workflow_id: 'code-review-1234',
})
```

Returns:
```json
{
  "session_remaining_usd": 24.9175,
  "session_budget_usd": 25.00,
  "session_used_usd": 0.0825,
  "session_used_percent": 0.33,
  "workflow_id": "code-review-1234",
  "workflow_remaining_usd": 4.9175,
  "workflow_budget_usd": 5.00,
  "workflow_used_usd": 0.0825,
  "workflow_used_percent": 1.65
}
```

### checkBudget

Pre-flight check: would a hypothetical call exceed the budget?

```javascript
workflow('ai-cost-tracker', {
  action: 'checkBudget',
  model: 'opus',
  estimated_input_tokens: 2000,
  estimated_output_tokens: 1000,
  workflow_id: 'code-review-1234',
})
```

Returns `{ allowed: true/false, warnings: [...], estimated_cost: 0.105 }`.

### report

Generate a full cost report with tabular breakdowns.

```javascript
workflow('ai-cost-tracker', { action: 'report' })
```

The report includes:
- Session totals (cost, tokens, calls, budget %)
- Per-workflow breakdown table
- Per-model breakdown table with average cost/call
- Last 10 calls detail
- Pricing reference for all configured models

### reset

Clear all tracked data and start a fresh session.

```javascript
workflow('ai-cost-tracker', { action: 'reset' })
```

## Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| action | string | 'report' | Action to perform: track, getCost, getRemainingBudget, checkBudget, report, reset |
| model | string | - | Model id (required for track and checkBudget) |
| input_tokens | number | 0 | Input tokens consumed |
| output_tokens | number | 0 | Output tokens consumed |
| estimated_input_tokens | number | 0 | Estimated input tokens (checkBudget only) |
| estimated_output_tokens | number | 0 | Estimated output tokens (checkBudget only) |
| workflow_id | string | null | Optional workflow identifier for per-workflow tracking |
| label | string | null | Human-readable label for the call |

## Budget Configuration

Budget limits can be set in `model-config.json` under a top-level `budget` key:

```json
{
  "models": { ... },
  "budget": {
    "per_workflow_max_dollars": 5.00,
    "per_session_max_dollars": 25.00,
    "warn_at_percent": 80
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| per_workflow_max_dollars | 5.00 | Max USD spend per workflow_id |
| per_session_max_dollars | 25.00 | Max USD spend per session |
| warn_at_percent | 80 | Emit warnings when this % of budget is consumed |

## Pricing Configuration

The tracker reads per-model pricing from `model-config.json`. Three formats are supported:

```json
{
  "models": {
    "opus": {
      "cost_per_1k_input": 0.015,
      "cost_per_1k_output": 0.075
    },
    "my-custom-model": {
      "cost_per_1k_tokens": 0.01
    }
  }
}
```

- `cost_per_1k_input` / `cost_per_1k_output` - Separate input/output rates (preferred)
- `cost_per_1k_tokens` - Unified rate used as fallback when granular rates are absent

If no config file exists, built-in defaults are used:

| Model | Input $/1K | Output $/1K |
|-------|-----------|------------|
| Opus | $0.015 | $0.075 |
| Sonnet | $0.003 | $0.015 |
| Haiku | $0.00025 | $0.00125 |
| Gemini | $0.00035 | $0.0014 |

Unknown models fall back to Sonnet pricing with a warning logged.

## Integration with Other Workflows

### Pre-call budget guard

```javascript
// Before making an expensive agent call:
const check = await workflow('ai-cost-tracker', {
  action: 'checkBudget',
  model: 'opus',
  estimated_input_tokens: 5000,
  estimated_output_tokens: 2000,
  workflow_id: myWorkflowId,
})

if (!check.allowed) {
  log('Budget exceeded, switching to cheaper model')
  model = 'haiku'
}
```

### Post-call tracking

```javascript
// After each agent() call, record the usage:
const response = await agent(prompt, { model: 'opus', label: 'worker-1' })

await workflow('ai-cost-tracker', {
  action: 'track',
  model: 'opus',
  input_tokens: response.usage?.input_tokens || 0,
  output_tokens: response.usage?.output_tokens || 0,
  workflow_id: 'my-workflow-run-1',
  label: 'worker-1',
})
```

### End-of-workflow report

```javascript
// At the end of a workflow, generate the cost report:
const report = await workflow('ai-cost-tracker', { action: 'report' })
log('Total workflow cost: $' + report.session_total_usd.toFixed(4))
```

## Data Storage

Cost data is persisted to:

```
~/.claude/repos/claude-global-skills/memory/cost-tracking.json
```

The file structure:

```json
{
  "session_id": "session_1718020800000",
  "started_at": "2026-06-10T12:00:00.000Z",
  "entries": [ "..." ],
  "workflow_totals": {
    "code-review-1234": {
      "total_usd": 0.0825,
      "calls": 1,
      "input_tokens": 1500,
      "output_tokens": 800,
      "first_call": "...",
      "last_call": "..."
    }
  },
  "session_total_usd": 0.0825,
  "total_input_tokens": 1500,
  "total_output_tokens": 800
}
```

Use `action: "reset"` to clear the store and start fresh.

## Files

- `~/.claude/repos/claude-global-skills/ai-cost-tracker.js` - Main workflow
- `~/.claude/repos/claude-global-skills/ai-cost-tracker.md` - This documentation
- `~/.claude/repos/claude-global-skills/model-config.json` - Optional pricing and budget overrides
- `~/.claude/repos/claude-global-skills/memory/cost-tracking.json` - Persisted cost data

---

**Version**: 1.0
**Created**: 2026-06-10
**Dependencies**: None (standalone, reads model-config.json when available)
