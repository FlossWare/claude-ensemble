---
name: gemini-in-pattern
description: Include Gemini in arbiter/worker pattern when available
metadata: 
  node_type: memory
  type: user
  originSessionId: 43c0d101-3691-456c-9ddf-7e0b1fd97c77
---

# Gemini in Arbiter/Worker Pattern

**Rule**: If Gemini is found/available, use it in the arbiter/worker pattern.

**Why**: User explicitly stated: "please, if gemini is found use it 8n arbiter/worker pattern"

**How to apply**:

### Default Worker Set (without Gemini)
```javascript
const WORKERS = ['opus', 'sonnet', 'haiku']
```

### Enhanced Worker Set (with Gemini)
```javascript
const WORKERS = ['opus', 'sonnet', 'haiku', 'gemini']
```

### Pattern Implementation

```javascript
// Check if Gemini is available
const AVAILABLE_MODELS = ['opus', 'sonnet', 'haiku']
// Try to include gemini if available (check MCP tools, model list, etc.)
const hasGemini = true  // Check if gemini model is accessible

const WORKERS = hasGemini 
  ? ['opus', 'sonnet', 'haiku', 'gemini']
  : ['opus', 'sonnet', 'haiku']

log(`🤖 Workers: ${WORKERS.join(', ')}`)

// Use in parallel reviews
const reviews = await parallel(WORKERS.map(model =>
  () => agent(reviewPrompt, { model, schema })
))
```

### When to Use Gemini

**Include Gemini for**:
- ✅ Multi-worker reviews (4 workers instead of 3)
- ✅ Parallel solving (more diverse solutions)
- ✅ Consensus voting (broader agreement check)
- ✅ Cost-effective verification tasks (Gemini is cheaper)

**Arbiter selection**:
- Gemini can be arbiter OR worker
- Rotate through all 4 models (opus, sonnet, haiku, gemini)

### Examples

**4-Worker Review Pattern**:
```javascript
const WORKERS = ['opus', 'sonnet', 'haiku', 'gemini']

const reviews = await parallel(WORKERS.map(model =>
  () => agent(`Review this code...`, { 
    label: `${model} Review`,
    model, 
    schema 
  })
))
```

**Arbiter Rotation (including Gemini)**:
```javascript
const ARBITERS = ['opus', 'sonnet', 'haiku', 'gemini']
const arbiterIndex = iteration % ARBITERS.length
const ARBITER = ARBITERS[arbiterIndex]

log(`⚖️ Arbiter: ${ARBITER}`)
```

**Role Swap with 4 Models**:
```javascript
// After arbiter (e.g., gemini) makes decision
// Gemini → skeptical worker
// Opus, Sonnet, Haiku → voting arbiters
const verification = await agent('Skeptical review', { model: 'gemini', schema })

const votes = await parallel([
  () => agent('Vote', { model: 'opus', schema }),
  () => agent('Vote', { model: 'sonnet', schema }),
  () => agent('Vote', { model: 'haiku', schema })
])
```

### Benefits of Including Gemini

1. **More diverse perspectives** - 4 models instead of 3
2. **Better consensus detection** - Broader agreement validation
3. **Cost optimization** - Gemini is cheaper for verification tasks
4. **Increased coverage** - Different model architectures catch different issues

### Integration Points

**Current workflows to update**:
- code-review.js (already has Gemini support in some areas)
- code-solve.js (uses 3 workers, could use 4)
- refactor workflows (could benefit from 4th worker)
- Any new arbiter/worker pattern workflows

**pr-verify.js already uses Gemini** - it's designed specifically for Gemini workers.

---

**Date**: 2026-06-05  
**Source**: User directive during parallel review session  
**Status**: Active preference - include Gemini when available
