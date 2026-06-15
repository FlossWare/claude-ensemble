---
name: workflow-no-math-random
description: Don't use Math.random() in workflows - breaks resume capability
metadata:
  type: feedback
  created: 2026-06-14
  priority: medium
  originSessionId: session-2026-06-14-fleet-config-audit
---

**Don't use Math.random() in Claude Code workflows - it breaks resume capability.**

**Why:** Workflows can be paused and resumed. Math.random() produces different values on resume, breaking determinism.

**How to apply:**

**❌ WRONG:**
```javascript
const componentReviews = await parallel(
  components.map(component => () => agent(prompt, {
    model: ['opus', 'sonnet', 'haiku'][Math.floor(Math.random() * 3)]
  }))
)
```

**✅ CORRECT:**
```javascript
const componentReviews = await parallel(
  components.map((component, idx) => () => agent(prompt, {
    model: ['opus', 'sonnet', 'haiku'][idx % 3]  // Deterministic based on index
  }))
)
```

**Error message you'll see:**
```
Error: Math.random() is unavailable in workflow scripts (breaks resume).
For N independent samples, include the index in the agent label or prompt.
```

**Alternatives to Math.random():**

1. **Use array index:** `idx % arrayLength`
2. **Use prompt variation:** Include component name/ID in prompt for natural diversity
3. **Use hash of input:** Deterministic pseudo-random based on input data
4. **Pass randomness via args:** Generate random values OUTSIDE workflow, pass in via args

**Also unavailable in workflows:**
- `Date.now()` - breaks resume (time changes)
- `new Date()` (no args) - same reason
- `Math.random()` - as discussed

**What you CAN use:**
- `args` parameter (pass timestamps/random values from outside)
- Deterministic computation based on input
- Array indices, string hashes, etc.

**Related:** [[feedback_workflow_no_fs_execsync]] - Other workflow limitations
