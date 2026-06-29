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

**IMPORTANT:** Claude Code workflows cannot use `fs` or `require` directly. They must use `agent()` to read files.

### Implementation Pattern

```javascript
// STEP 1: Load config at workflow start (using agent() to read file)
const configResult = await agent(`Read and parse multi-AI config:

cat ${process.env.HOME}/.claude/workflows/multi-ai-config.json 2>/dev/null || echo '{"enabled":true,"workers":{"models":["opus","sonnet","haiku"],"count":3},"arbiter":{"enabled":true,"model":"opus"}}'

Return the JSON object.`, {
  label: 'load-multi-ai-config',
  schema: {
    type: 'object',
    properties: {
      enabled: { type: 'boolean' },
      workers: {
        type: 'object',
        properties: {
          models: { type: 'array', items: { type: 'string' } },
          count: { type: 'number' }
        }
      },
      arbiter: {
        type: 'object',
        properties: {
          enabled: { type: 'boolean' },
          model: { type: 'string' }
        }
      }
    }
  }
})

// Extract config values with defaults
const MULTI_AI = configResult?.enabled !== false
const WORKER_MODELS = configResult?.workers?.models || ['opus', 'sonnet', 'haiku']
const WORKER_COUNT = configResult?.workers?.count || 3
const ARBITER_ENABLED = configResult?.arbiter?.enabled !== false
const ARBITER_MODEL = configResult?.arbiter?.model || 'opus'

// STEP 2: Use config values
if (!MULTI_AI) {
  // Single-AI mode - use first model only
  const result = await agent(prompt, { model: WORKER_MODELS[0], schema })
  return result
}

// Multi-AI mode - spawn workers based on config
const activeModels = WORKER_MODELS.slice(0, WORKER_COUNT)
const workers = await parallel(
  activeModels.map(model => () =>
    agent(prompt, { model, label: `${model}-worker`, schema })
  )
)

// Arbiter (if enabled)
if (ARBITER_ENABLED) {
  const synthesis = await agent(arbiterPrompt, { 
    model: ARBITER_MODEL,
    label: 'arbiter',
    schema 
  })
  return synthesis
} else {
  // No arbiter - return all worker results
  return workers.filter(Boolean)
}
```

### Why `agent()` Instead of `fs`?

Claude Code workflows run in a sandboxed environment without Node.js built-ins. The `agent()` call spawns a subagent that CAN read files via the `Read` tool. The schema forces structured output so you get a clean JSON object back.

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

**Existing workflows:** All use hardcoded triple consensus (opus/sonnet/haiku + arbiter) - **4x cost**

**To support config:** Each workflow needs to:
1. Load `multi-ai-config.json` at startup (using `agent()` with schema - see pattern above)
2. Extract config values with defaults (`configResult?.enabled !== false`)
3. Use `WORKER_MODELS.slice(0, WORKER_COUNT)` instead of hardcoded list
4. Conditionally call arbiter based on `ARBITER_ENABLED`

**Backward compatible:** Config loading includes fallback in the shell command:
```bash
cat ... || echo '{"enabled":true,...}'  # Falls back to triple consensus if file missing
```

**Current status (2026-06-09):** 
- ✅ Config system documented
- ✅ Default config file created (triple consensus)
- ⏳ Workflows NOT YET updated to read config (still hardcoded)
- ⏳ All workflows still use 4x cost (3 workers + arbiter)

**Next steps:**
1. Update `memory-rag-search.js` to read config
2. Update `memory-rag-index.js` to read config  
3. Update `ai-consensus.js` to read config
4. Test that workflows still show as skills (`export const meta` must be line 1)
5. Update other multi-AI workflows as needed
