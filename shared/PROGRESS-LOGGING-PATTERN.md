# Progress Logging Pattern for Parallel Operations

**Purpose**: Provide visibility during long-running parallel operations so users understand what's happening.

## The Pattern

```javascript
// 1. Log BEFORE starting parallel work
log(`🔄 ${count} workers ${action} in parallel...`)

// 2. Use descriptive labels on agent calls (shows in /workflows UI)
const results = await parallel(items.map(item =>
  () => agent('Task description', {
    label: `${model} ${shortDescription}`,  // Shows in progress UI
    model: model,
    schema: SCHEMA
  })
))

// 3. Log AFTER completing with success count
const successCount = results.filter(Boolean).length
log(`✅ Received ${successCount}/${items.length} results`)
```

## Example: Worker Proposals

```javascript
const WORKER_MODELS = ['opus', 'sonnet', 'haiku']

// Before
log(`🔄 ${WORKER_MODELS.length} workers proposing fixes in parallel...`)

// During (labels show in /workflows UI)
const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix for bug #123', {
    label: `${model} Fix Proposal`,  // ← Shows in progress UI
    model: model,
    phase: 'Solve',
    schema: FIX_SCHEMA
  })
))

// After
const successCount = fixes.filter(Boolean).length
log(`✅ Received ${successCount}/${WORKER_MODELS.length} fix proposals`)

if (successCount < WORKER_MODELS.length) {
  log(`⚠️  ${WORKER_MODELS.length - successCount} workers failed`)
}
```

## Example: Arbiter Voting

```javascript
const newArbiters = ['sonnet', 'haiku']

// Before
log(`🗳️  ${newArbiters.length} arbiters voting...`)

// During
const arbiterVotes = await parallel(newArbiters.map(model =>
  () => agent('Vote: approve or reject?', {
    label: `${model} Vote`,  // ← Shows in progress UI
    model: model,
    schema: VOTE_SCHEMA
  })
))

// After
const approvals = arbiterVotes.filter(v => v?.vote === 'approve').length
const rejections = arbiterVotes.length - approvals
log(`✅ Votes: ${approvals} approve, ${rejections} reject`)
```

## Example: Pipeline with Progress

```javascript
const workflows = ['code-review.js', 'code-solve.js', 'pr-review.js']

// Before
log(`📊 Analyzing ${workflows.length} workflows...`)

const results = await pipeline(
  workflows,

  // Stage 1: Analysis
  (workflow) => {
    log(`  🔍 Analyzing ${workflow}...`)
    
    return parallel(WORKER_MODELS.map(model =>
      () => agent(`Analyze ${workflow}`, {
        label: `${model}: Analyze ${workflow}`,
        model: model,
        phase: 'Analysis',
        schema: ANALYSIS_SCHEMA
      })
    )).then(analyses => {
      const count = analyses.filter(Boolean).length
      log(`    ✅ ${count}/${WORKER_MODELS.length} analyses complete`)
      return analyses
    })
  },

  // Stage 2: Arbiter selection
  (analyses, workflow) => {
    log(`  ⚖️  Arbiter selecting best analysis for ${workflow}...`)
    
    return agent(`Select best analysis for ${workflow}`, {
      label: `Arbiter: Select ${workflow}`,
      model: ARBITER_MODEL,
      schema: DECISION_SCHEMA
    }).then(decision => {
      log(`    ✅ Selected analysis #${decision.selected_index}`)
      return decision
    })
  }
)

// After
log(`✅ Analysis complete for ${results.filter(Boolean).length} workflows`)
```

## Emoji Guide

Use consistent emojis for visual scanning:

- 🔄 Starting parallel work
- 🔍 Analyzing / Reviewing
- ✍️  Proposing / Creating
- ⚖️  Arbiter deciding
- 🗳️  Voting
- 🔄 Role swapping
- ✅ Success / Complete
- ⚠️  Warning / Partial failure
- ❌ Error / Failure
- 📊 Statistics / Summary
- 📦 Batch operations
- 🚀 Starting workflow

## Key Rules

### ✅ DO:
1. Log before starting parallel operations
2. Use descriptive labels on agent calls (shows in `/workflows` UI)
3. Log after completing with success count
4. Include counts: `${completed}/${total}`
5. Use consistent emojis for visual scanning
6. Log warnings if some workers fail
7. Include phase context in labels

### ❌ DON'T:
1. Silent parallel operations (users can't see progress)
2. Generic labels like "worker 1" (use model name + task)
3. Forget to count successes (users want to know if all completed)
4. Over-log (one before, one after is enough)
5. Skip emojis (they help with visual scanning)

## Complete Example: Arbiter/Worker Pattern

```javascript
const WORKER_MODELS = ['opus', 'sonnet', 'haiku']
const ARBITER_MODEL = 'opus'

// ============================================================================
// PHASE 1: Worker Proposals
// ============================================================================

log(`🔄 ${WORKER_MODELS.length} workers proposing solutions in parallel...`)

const proposals = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose solution', {
    label: `${model} Proposal`,
    model: model,
    phase: 'Propose',
    schema: PROPOSAL_SCHEMA
  })
))

const proposalCount = proposals.filter(Boolean).length
log(`✅ Received ${proposalCount}/${WORKER_MODELS.length} proposals`)

if (proposalCount === 0) {
  log(`❌ No proposals received - aborting`)
  return { status: 'failed', reason: 'No proposals' }
}

// ============================================================================
// PHASE 2: Arbiter Selection
// ============================================================================

log(`⚖️  Arbiter (${ARBITER_MODEL}) selecting best proposal...`)

const decision = await agent(`Select best of ${proposalCount} proposals`, {
  label: `${ARBITER_MODEL} Arbiter`,
  model: ARBITER_MODEL,
  phase: 'Decide',
  schema: DECISION_SCHEMA
})

log(`✅ Selected: ${WORKER_MODELS[decision.selected_index]}'s proposal`)
log(`   Consensus: ${decision.consensus_score}%`)

// ============================================================================
// PHASE 3: Role Swap Validation
// ============================================================================

log(`🔄 Swapping roles for validation...`)

const newWorker = ARBITER_MODEL
const newArbiters = WORKER_MODELS.filter((_, idx) => idx !== decision.selected_index)

log(`   New worker: ${newWorker}`)
log(`   New arbiters: ${newArbiters.join(', ')}`)

// Worker reviews
log(`🔍 ${newWorker} reviewing as skeptical worker...`)

const workerReview = await agent('Review proposal skeptically', {
  label: `${newWorker} Skeptical Review`,
  model: newWorker,
  schema: REVIEW_SCHEMA
})

log(`${workerReview.approved ? '✅' : '⚠️'} Worker review: ${workerReview.approved ? 'APPROVED' : 'CONCERNS'}`)

if (!workerReview.approved) {
  log(`   Concerns: ${workerReview.concerns?.join(', ')}`)
}

// Arbiters vote
log(`🗳️  ${newArbiters.length} arbiters voting...`)

const arbiterVotes = await parallel(newArbiters.map(model =>
  () => agent('Vote on proposal', {
    label: `${model} Vote`,
    model: model,
    schema: VOTE_SCHEMA
  })
))

const approvals = arbiterVotes.filter(v => v?.vote === 'approve').length
const rejections = arbiterVotes.length - approvals

log(`✅ Votes: ${approvals} approve, ${rejections} reject`)

// ============================================================================
// PHASE 4: Consensus Check
// ============================================================================

const hasConsensus = workerReview.approved && approvals > rejections

log(`${hasConsensus ? '✅' : '❌'} Consensus: ${hasConsensus ? 'REACHED' : 'NOT REACHED'}`)

if (!hasConsensus) {
  log(`⚠️  Would iterate with refined proposals (iteration 1/${MAX_ITERATIONS})`)
}

return {
  consensus: hasConsensus,
  selected_proposal: proposals[decision.selected_index],
  selected_by: WORKER_MODELS[decision.selected_index],
  validation: {
    worker_approved: workerReview.approved,
    arbiter_approvals: approvals,
    arbiter_rejections: rejections
  }
}
```

## Why This Matters

**Without progress logging:**
```
[Long pause...]
[User sees nothing]
[Long pause...]
✅ Complete
```
User experience: "Is it frozen? What's happening?"

**With progress logging:**
```
🔄 3 workers proposing fixes in parallel...
✅ Received 3/3 proposals
⚖️  Arbiter (opus) selecting best proposal...
✅ Selected: sonnet's proposal
   Consensus: 85%
🔄 Swapping roles for validation...
   New worker: opus
   New arbiters: haiku, sonnet
🔍 opus reviewing as skeptical worker...
✅ Worker review: APPROVED
🗳️  2 arbiters voting...
✅ Votes: 2 approve, 0 reject
✅ Consensus: REACHED
```
User experience: "I can see exactly what's happening at each step!"

---

**Status**: Best practice pattern  
**Date**: 2026-06-04  
**Use in**: All arbiter/worker workflows, any parallel operations  
**Related**: [[arbiter-worker-pattern]]
