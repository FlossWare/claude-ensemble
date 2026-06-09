---
name: progress-logging-parallel
description: Always log before/after parallel operations with descriptive labels for visibility
metadata:
  node_type: memory
  type: feedback
  originSessionId: current
---

# Progress Logging for Parallel Operations

**Rule**: When running parallel operations in workflows, ALWAYS provide progress visibility through logging.

**Why**: Parallel operations can take a long time. Without logging, users see nothing and wonder if the workflow is frozen. Good progress logging shows exactly what's happening at each step.

**How to apply**: Use this three-step pattern for every parallel operation.

## The Three-Step Pattern

### 1. Log BEFORE starting
```javascript
log(`🔄 ${count} workers ${action} in parallel...`)
```

### 2. Use descriptive labels (shows in /workflows UI)
```javascript
const results = await parallel(items.map(item =>
  () => agent('Task description', {
    label: `${model} ${shortDescription}`,  // ← Shows in /workflows progress UI
    model: model,
    schema: SCHEMA
  })
))
```

### 3. Log AFTER completing with count
```javascript
const successCount = results.filter(Boolean).length
log(`✅ Received ${successCount}/${items.length} results`)
```

## Complete Example

```javascript
// BEFORE
log(`🔄 ${WORKER_MODELS.length} workers proposing fixes in parallel...`)

// DURING (labels show in /workflows UI)
const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix for bug #123', {
    label: `${model} Fix Proposal`,  // Shows in progress
    model: model,
    phase: 'Solve',
    schema: FIX_SCHEMA
  })
))

// AFTER
const successCount = fixes.filter(Boolean).length
log(`✅ Received ${successCount}/${WORKER_MODELS.length} fix proposals`)

if (successCount < WORKER_MODELS.length) {
  log(`⚠️  ${WORKER_MODELS.length - successCount} workers failed`)
}
```

## Arbiter/Worker Pattern Application

### Phase 1: Worker Proposals
```javascript
log(`🔄 ${WORKER_MODELS.length} workers proposing solutions in parallel...`)

const proposals = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose solution', {
    label: `${model} Proposal`,  // Descriptive label
    model: model,
    schema: PROPOSAL_SCHEMA
  })
))

log(`✅ Received ${proposals.filter(Boolean).length}/${WORKER_MODELS.length} proposals`)
```

### Phase 2: Arbiter Selection
```javascript
log(`⚖️  Arbiter (${ARBITER_MODEL}) selecting best proposal...`)

const decision = await agent(`Select best proposal`, {
  label: `${ARBITER_MODEL} Arbiter`,
  model: ARBITER_MODEL,
  schema: DECISION_SCHEMA
})

log(`✅ Selected: ${WORKER_MODELS[decision.selected_index]}'s proposal`)
log(`   Consensus: ${decision.consensus_score}%`)
```

### Phase 3: Role Swap - Worker Review
```javascript
log(`🔍 ${newWorker} reviewing as skeptical worker...`)

const workerReview = await agent('Review skeptically', {
  label: `${newWorker} Skeptical Review`,
  model: newWorker,
  schema: REVIEW_SCHEMA
})

log(`${workerReview.approved ? '✅' : '⚠️'} Worker review: ${workerReview.approved ? 'APPROVED' : 'CONCERNS'}`)
```

### Phase 4: Role Swap - Arbiter Voting
```javascript
log(`🗳️  ${newArbiters.length} arbiters voting...`)

const arbiterVotes = await parallel(newArbiters.map(model =>
  () => agent('Vote on proposal', {
    label: `${model} Vote`,
    model: model,
    schema: VOTE_SCHEMA
  })
))

const approvals = arbiterVotes.filter(v => v?.vote === 'approve').length
log(`✅ Votes: ${approvals} approve, ${rejections} reject`)
```

### Phase 5: Consensus Check
```javascript
const hasConsensus = workerReview.approved && approvals > rejections
log(`${hasConsensus ? '✅' : '❌'} Consensus: ${hasConsensus ? 'REACHED' : 'NOT REACHED'}`)
```

## Emoji Guide (Use Consistently)

- 🔄 Starting parallel work
- 🔍 Analyzing / Reviewing
- ✍️  Proposing / Creating
- ⚖️  Arbiter deciding
- 🗳️  Voting
- ✅ Success / Complete
- ⚠️  Warning / Partial failure
- ❌ Error / Failure
- 📊 Statistics / Summary

## Key Rules

### ✅ DO:
1. Log before every parallel() call
2. Use descriptive labels on agent calls (they show in `/workflows` UI)
3. Log after completing with success count: `${completed}/${total}`
4. Include emojis for visual scanning
5. Log warnings if some workers fail
6. Show phase context in labels

### ❌ DON'T:
1. Silent parallel operations (users can't see progress)
2. Generic labels like "worker 1" (use model name + task)
3. Forget to count successes
4. Over-log (one before, one after is enough)
5. Skip emojis

## User Experience Comparison

### Without Progress Logging (BAD)
```
[Long pause - 2 minutes...]
[User sees nothing]
[Long pause continues...]
✅ Complete
```
**User thinks**: "Is it frozen? What's happening? Should I cancel?"

### With Progress Logging (GOOD)
```
🔄 3 workers proposing fixes in parallel...
✅ Received 3/3 proposals
⚖️  Arbiter (opus) selecting best proposal...
✅ Selected: sonnet's proposal
   Consensus: 85%
🔄 Swapping roles for validation...
🔍 opus reviewing as skeptical worker...
✅ Worker review: APPROVED
🗳️  2 arbiters voting...
✅ Votes: 2 approve, 0 reject
✅ Consensus: REACHED
```
**User thinks**: "I can see exactly what's happening at each step!"

## When This Applies

- ✅ Every `parallel()` call in workflows
- ✅ Arbiter/worker pattern (all phases)
- ✅ Multi-AI consensus operations
- ✅ Pipeline stages with parallel sub-operations
- ✅ Batch processing
- ✅ Any operation taking >10 seconds

## Reference Implementation

See: `shared/PROGRESS-LOGGING-PATTERN.md` for complete examples

## Related Memories
- [[arbiter-worker-pattern]] - Core pattern that uses this
- [[workflow-registration-filter]] - Workflow system constraints

---

**Status**: Required pattern for all parallel operations  
**Date**: 2026-06-04  
**Applies to**: All workflows, all arbiter/worker patterns  
**User feedback**: "when running in parallel itd be nice to have some periodic info"
