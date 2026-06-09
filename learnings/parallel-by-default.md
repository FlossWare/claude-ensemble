---
name: parallel-by-default
description: Always use parallel execution for arbiter/worker pattern reviews and solvers
metadata: 
  node_type: memory
  type: user
  originSessionId: 43c0d101-3691-456c-9ddf-7e0b1fd97c77
---

# Parallel Execution by Default

**Rule**: ALWAYS use parallel execution for arbiter/worker pattern, for BOTH reviews and solvers.

**Why**: User explicitly stated: "please always use parallel for the arbiter/worker pattern for both reviews and solvers"

**How to apply**: 

### For Reviews
```javascript
// ✅ CORRECT - Parallel reviews
const reviews = await parallel([
  () => agent('Review', { model: 'opus', schema }),
  () => agent('Review', { model: 'sonnet', schema }),
  () => agent('Review', { model: 'haiku', schema })
])
```

```javascript
// ❌ WRONG - Sequential reviews
for (const model of ['opus', 'sonnet', 'haiku']) {
  const review = await agent('Review', { model, schema })
  reviews.push(review)
}
```

### For Solvers
```javascript
// ✅ CORRECT - Parallel solving
const fixes = await parallel([
  () => agent('Fix issue 1', { model: 'opus', schema }),
  () => agent('Fix issue 2', { model: 'sonnet', schema }),
  () => agent('Fix issue 3', { model: 'haiku', schema })
])
```

```javascript
// ❌ WRONG - Sequential solving
for (const issue of issues) {
  const fix = await agent(`Fix ${issue}`, { schema })
  fixes.push(fix)
}
```

### When to Use Parallel

**ALWAYS parallel for**:
- ✅ Multiple workers reviewing the same thing
- ✅ Multiple workers proposing solutions
- ✅ Multiple workers fixing different issues
- ✅ Arbiter voting (after role swap)
- ✅ Verification checks

**Exception**: Only use sequential when one step MUST complete before the next (genuine dependency).

### Pattern Template

```javascript
// Phase 1: Parallel Review
phase('Review')
const reviews = await parallel(WORKERS.map(model =>
  () => agent(reviewPrompt, { model, schema })
))

// Phase 2: Arbiter Selection
phase('Arbiter Decision')
const decision = await agent(arbiterPrompt, { model: ARBITER, schema })

// Phase 3: Parallel Solve
phase('Solve')
const fixes = await parallel(issues.map(issue =>
  () => agent(`Fix ${issue}`, { schema })
))

// Phase 4: Parallel Verification (role swap)
phase('Verify')
const votes = await parallel([
  () => agent('Skeptical review', { model: ARBITER, schema }),
  () => agent('Vote', { model: 'opus', schema }),
  () => agent('Vote', { model: 'sonnet', schema })
])
```

### Key Points

1. **Default to parallel** - Only use sequential if genuine dependency exists
2. **Both reviews AND solvers** - Not just reviews, solvers too
3. **Maximum efficiency** - Parallel execution is 3x+ faster
4. **User preference** - This is a standing instruction from the user

### Examples from Session

**Good parallel usage**:
- 5 workers fixing 5 issues in parallel (2026-06-04 fix session)
- 3 workers reviewing all workflows in parallel (current workflow)
- Arbiter voting in parallel (opus + sonnet voting simultaneously)

**Where parallel was added**:
- User said "fix 8n parallel" → changed from sequential to parallel fixing
- User said "plesde use arbuter/worker pattern and review all in parallel" → added parallel review

---

**Date**: 2026-06-05  
**Source**: User directive during arbiter/worker pattern session  
**Status**: Active preference - apply to ALL future arbiter/worker workflows
