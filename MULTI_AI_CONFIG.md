# Multi-AI Worker Configuration

**Control the cost vs quality tradeoff** for all multi-AI workflows.

## Configuration File

`~/.claude/workflows/multi-ai-config.json`

## Quick Start

**Single-AI (fast & cheap):**
```json
{
  "enabled": false
}
```
All workflows use single model, no consensus. **1x cost**.

**Dual consensus (balanced):**
```json
{
  "enabled": true,
  "workers": {
    "models": ["opus", "sonnet"],
    "count": 2
  },
  "arbiter": {
    "enabled": true,
    "model": "opus"
  }
}
```
Two workers + arbiter. **3x cost**.

**Triple consensus (standard - default):**
```json
{
  "enabled": true,
  "workers": {
    "models": ["opus", "sonnet", "haiku"],
    "count": 3
  },
  "arbiter": {
    "enabled": true,
    "model": "opus"
  }
}
```
Three workers + arbiter. **4x cost**.

**Quad consensus (maximum quality):**
```json
{
  "enabled": true,
  "workers": {
    "models": ["opus", "sonnet", "haiku", "gemini"],
    "count": 4
  },
  "arbiter": {
    "enabled": true,
    "model": "opus"
  }
}
```
Four workers + arbiter. **5x cost**.

## How Workflows Use This

Workflows read `multi-ai-config.json` at runtime:

```javascript
// Load config
const fs = require('fs')
const config = JSON.parse(fs.readFileSync(`${process.env.HOME}/.claude/workflows/multi-ai-config.json`))

// Check if multi-AI is enabled
if (!config.enabled) {
  // Single-AI mode - use first model only
  const result = await agent(prompt, { model: config.workers.models[0], schema })
  return result
}

// Multi-AI mode - spawn workers
const workers = await parallel(
  config.workers.models.slice(0, config.workers.count).map(model => () =>
    agent(prompt, { model, schema })
  )
)

// Arbiter (if enabled)
if (config.arbiter.enabled) {
  const synthesis = await agent(arbiterPrompt, { 
    model: config.arbiter.model, 
    schema 
  })
  return synthesis.result
} else {
  // No arbiter - return all worker results
  return workers.filter(Boolean)
}
```

## Cost Examples

**Assume 1 phase = 50k tokens per agent**

| Mode | Workers | Arbiter | Total Agents | Cost |
|------|---------|---------|--------------|------|
| Single-AI | 0 | No | 1 | 50k |
| Dual | 2 | Yes | 3 | 150k (3x) |
| Triple | 3 | Yes | 4 | 200k (4x) |
| Quad | 4 | Yes | 5 | 250k (5x) |
| Workers-only | 3 | No | 3 | 150k (3x) |

## When to Use Each Mode

**Single-AI (1x cost):**
- ✅ Development/testing
- ✅ Non-critical decisions
- ✅ Speed over accuracy
- ✅ Budget-constrained

**Dual consensus (3x cost):**
- ✅ Good balance
- ✅ Most workflows
- ✅ Moderate confidence needed

**Triple consensus (4x cost):**
- ✅ Default/standard
- ✅ Production code reviews
- ✅ Security audits
- ✅ High confidence needed

**Quad consensus (5x cost):**
- ✅ Critical security issues
- ✅ Production releases
- ✅ Maximum accuracy required
- ✅ No budget constraint

## Per-Workflow Override

Workflows can override the global config:

```javascript
// Force single-AI for this phase
const result = await agent(prompt, { 
  model: 'haiku',  // Fast model
  schema 
})

// Force multi-AI even if config.enabled = false
const workers = await parallel([
  () => agent(prompt, { model: 'opus', schema }),
  () => agent(prompt, { model: 'sonnet', schema }),
])
```

## Future Enhancement

Command-line override:
```bash
# Single-AI mode for this run
MULTI_AI=off claude run code-review-auto

# Dual consensus
MULTI_AI=dual claude run code-review-auto

# Maximum quality
MULTI_AI=quad claude run code-review-auto +1M
```

(Not yet implemented - would require workflows to check environment variables)

## Migration Path

**Existing workflows:** All use hardcoded triple consensus (opus/sonnet/haiku + arbiter)

**To support config:** Each workflow needs to:
1. Load `multi-ai-config.json` at startup
2. Check `config.enabled`
3. Use `config.workers.models` instead of hardcoded list
4. Conditionally call arbiter based on `config.arbiter.enabled`

**Backward compatible:** If config file doesn't exist, fall back to triple consensus (current behavior)
