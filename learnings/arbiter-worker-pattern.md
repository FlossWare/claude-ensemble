---
name: arbiter-worker-pattern
description: Reusable multi-AI pattern for BOTH review and solve with worker proposals, arbiter selection, and role swapping
metadata: 
  node_type: memory
  type: feedback
  originSessionId: current
---

# Arbiter/Worker Pattern

**Concept**: A reusable multi-AI consensus pattern for **BOTH REVIEW AND SOLVE** operations where workers propose solutions, an arbiter selects the best, then roles swap iteratively until consensus is reached.

**Critical**: This pattern supports:
- ✅ **REVIEW**: Workers find issues/bugs, arbiter selects best findings
- ✅ **SOLVE**: Workers propose fixes, arbiter selects best solution
- ✅ **REVIEW + SOLVE**: Both in sequence (MUST use different arbiters!)

**Why**: Ensures high-quality decisions by:
1. Getting diverse proposals from multiple models (parallel execution)
2. Having independent selection by an arbiter
3. Validating through role reversal (workers become skeptics)
4. Iterating until all models agree

**How to apply**: Use this pattern for:
- Code review (finding bugs/issues)
- Code solving (proposing fixes)
- Refactoring (proposing improvements)
- Decision-making (choosing approaches)
- Review + Solve combined workflows

## Core Pattern

### Worker Configuration (Always Include Gemini)
```javascript
// DEFAULT: Include all 4 models when available
const WORKER_MODELS = ['opus', 'sonnet', 'haiku', 'gemini']
let arbiterModel = 'opus' // Will rotate

// Note: Gemini provides cost optimization and diverse perspective
// User preference: "if gemini is found use it in arbiter/worker pattern"
```

### Phase 1: Worker Proposals (ALWAYS use parallel() for BOTH review and solve)
```javascript
// CRITICAL: ALWAYS use parallel() for both review AND solve operations
// User preference: "always use parallel for the arbiter/worker pattern for both reviews and solvers"

log(`🔄 ${WORKER_MODELS.length} workers proposing in parallel...`)

const proposals = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose solution', {
    label: `${model} Proposal`,  // Labels show in /workflows progress
    model: model,
    schema: PROPOSAL_SCHEMA
  })
))

const successCount = proposals.filter(Boolean).length
log(`✅ Received ${successCount}/${WORKER_MODELS.length} proposals`)

// This works for:
// - REVIEW: Workers finding bugs/issues
// - SOLVE: Workers proposing fixes
// - Both use parallel() by default
```

### Phase 2: Arbiter Selection
```javascript
// Arbiter selects best proposal
const decision = await agent(`Review ${proposals.length} proposals.

Select the BEST based on:
1. Correctness
2. Completeness  
3. Minimal risk
4. Clear benefit

Return selected index and reasoning.`, {
  model: arbiterModel,
  schema: {
    type: 'object',
    properties: {
      selected_index: { type: 'number' },
      reasoning: { type: 'string' },
      consensus_score: { type: 'number' },
      concerns: { type: 'array', items: { type: 'string' } }
    }
  }
})

const selectedProposal = proposals[decision.selected_index]
const selectedWorker = WORKER_MODELS[decision.selected_index]
```

### Phase 3: Role Swap
```javascript
// Previous arbiter becomes a worker
// Previous workers (except selected) become arbiters
const newWorkerModel = arbiterModel
const newArbiters = WORKER_MODELS.filter((_, idx) => idx !== decision.selected_index)

log(`Role swap: ${arbiterModel} → worker, ${newArbiters.join(', ')} → arbiters`)
```

### Phase 4: Skeptical Review (Swapped Roles)
```javascript
// New worker (former arbiter) reviews skeptically
log(`🔍 ${newWorkerModel} reviewing as skeptical worker...`)

const workerReview = await agent('Review this proposal as a skeptic. Find issues.', {
  label: `${newWorkerModel} Skeptical Review`,
  model: newWorkerModel,
  schema: REVIEW_SCHEMA
})

log(`📊 Worker review: ${workerReview.approved ? '✅ APPROVED' : '⚠️ CONCERNS'}`)

// New arbiters vote
log(`🗳️  ${newArbiters.length} arbiters voting...`)

const arbiterVotes = await parallel(newArbiters.map(model =>
  () => agent('Vote: approve or reject?', {
    label: `${model} Vote`,
    model: model,
    schema: VOTE_SCHEMA
  })
))

const approvals = arbiterVotes.filter(v => v.vote === 'approve').length
const rejections = arbiterVotes.length - approvals

log(`✅ Votes: ${approvals} approve, ${rejections} reject`)
```

### Phase 5: Consensus Check
```javascript
const hasConsensus = workerReview.approved && approvals > rejections

if (!hasConsensus) {
  // Iterate: swap roles again and refine proposals
  arbiterModel = newArbiters[0] // Rotate arbiter
  // Repeat from Phase 1 with concerns incorporated
}
```

## Pattern Variants

### Variant 1: Review + Solve (Different Arbiters) - MOST COMMON

**CRITICAL RULE**: When using the pattern for BOTH review and solve in sequence, **NEVER use the same arbiter for both phases**.

**Why**: Same arbiter would create bias - they'd favor their own review findings when solving.

**Use Case**: Workflows like code-review-and-solve that need to find issues AND fix them.

```javascript
// ============================================================================
// REVIEW PHASE
// ============================================================================

const REVIEW_WORKERS = ['opus', 'sonnet', 'haiku', 'gemini']  // Include Gemini!
let REVIEW_ARBITER = 'opus'

log('Phase 1: REVIEW - Finding issues...')

// Workers find issues IN PARALLEL (REQUIRED)
log(`🔄 ${REVIEW_WORKERS.length} workers reviewing in parallel...`)
const reviewProposals = await parallel(REVIEW_WORKERS.map(model =>
  () => agent('Find bugs', { 
    label: `${model} Review`,
    model, 
    schema: FINDING_SCHEMA 
  })
))
log(`✅ Received ${reviewProposals.filter(Boolean).length} reviews`)

// Arbiter selects best findings
const reviewDecision = await agent('Pick best findings', {
  model: REVIEW_ARBITER,
  schema: ARBITER_SCHEMA
})

// Role swap for review validation
const reviewConsensus = await validateWithRoleSwap(reviewDecision, REVIEW_ARBITER, REVIEW_WORKERS)

// ============================================================================
// SOLVE PHASE - DIFFERENT ARBITER (CRITICAL!)
// ============================================================================

const SOLVE_WORKERS = ['opus', 'sonnet', 'haiku', 'gemini']  // Include Gemini!
let SOLVE_ARBITER = 'sonnet' // ⚠️ MUST BE DIFFERENT from review arbiter!

log('Phase 2: SOLVE - Proposing fixes...')

// Workers propose fixes IN PARALLEL (REQUIRED)
log(`🔄 ${SOLVE_WORKERS.length} workers solving in parallel...`)
const solveProposals = await parallel(SOLVE_WORKERS.map(model =>
  () => agent('Propose fix', { 
    label: `${model} Fix`,
    model, 
    schema: FIX_SCHEMA 
  })
))
log(`✅ Received ${solveProposals.filter(Boolean).length} fixes`)

// Different arbiter selects best fix
const solveDecision = await agent('Pick best fix', {
  model: SOLVE_ARBITER, // 'sonnet', not 'opus' - MUST be different!
  schema: ARBITER_SCHEMA
})

// Role swap for solve validation
const solveConsensus = await validateWithRoleSwap(solveDecision, SOLVE_ARBITER, SOLVE_WORKERS)
```

**Key Points**:
- ✅ Include Gemini in both worker sets (4 workers)
- ✅ ALWAYS use parallel() for both review AND solve
- ✅ DIFFERENT arbiters for review vs solve (prevents bias)
- ✅ Log before/after parallel operations for visibility

### Variant 2: Iterative Refinement (Loop Until Consensus)

```javascript
const MAX_ITERATIONS = 10
let iteration = 0
let consensus = false
let currentArbiter = 'opus'
const models = ['opus', 'sonnet', 'haiku']

while (!consensus && iteration < MAX_ITERATIONS) {
  iteration++
  log(`Iteration ${iteration}`)

  // Phase 1: Workers propose
  const workers = models.filter(m => m !== currentArbiter)
  const proposals = await parallel(workers.map(model =>
    () => agent('Propose solution', { model, schema: PROPOSAL_SCHEMA })
  ))

  // Phase 2: Arbiter selects
  const decision = await agent('Select best', {
    model: currentArbiter,
    schema: DECISION_SCHEMA
  })

  // Phase 3: Role swap
  const newWorker = currentArbiter
  const newArbiters = workers.filter((_, idx) => idx !== decision.selected_index)

  // Phase 4: Validate with swapped roles
  const workerReview = await agent('Review skeptically', {
    model: newWorker,
    schema: REVIEW_SCHEMA
  })

  const arbiterVotes = await parallel(newArbiters.map(model =>
    () => agent('Vote', { model, schema: VOTE_SCHEMA })
  ))

  // Phase 5: Check consensus
  const approvals = arbiterVotes.filter(v => v.vote === 'approve').length
  consensus = workerReview.approved && approvals > arbiterVotes.length / 2

  if (!consensus) {
    // Rotate arbiter for next iteration
    currentArbiter = newArbiters[iteration % newArbiters.length]
    log(`No consensus. Rotating arbiter to ${currentArbiter}`)
  }
}

log(`Consensus ${consensus ? 'REACHED' : 'FAILED'} after ${iteration} iterations`)
```

### Variant 3: Multi-Phase (Review → Solve → Verify)

**Rule**: Each phase gets a DIFFERENT arbiter. Rotate through models.

```javascript
const phases = ['review', 'solve', 'verify']
const arbiters = {
  review: 'opus',
  solve: 'sonnet',
  verify: 'haiku'
}

for (const phase of phases) {
  log(`Phase: ${phase}, Arbiter: ${arbiters[phase]}`)

  // Workers (all models except current arbiter)
  const workers = ['opus', 'sonnet', 'haiku'].filter(m => m !== arbiters[phase])

  // Worker proposals
  const proposals = await parallel(workers.map(model =>
    () => agent(`${phase} task`, { model })
  ))

  // Arbiter decision
  const decision = await agent('Select best', {
    model: arbiters[phase]
  })

  // Role swap validation
  const consensus = await validateWithRoleSwap(
    decision,
    arbiters[phase],
    workers
  )

  if (!consensus) {
    log(`⚠️ Phase ${phase} failed consensus`)
    break
  }
}
```

## Helper Function: Role Swap Validation

```javascript
async function validateWithRoleSwap(decision, arbiterModel, workerModels) {
  // Previous arbiter becomes skeptical worker
  const newWorker = arbiterModel
  
  // Previous workers (except selected) become arbiters
  const selectedIndex = decision.selected_index
  const newArbiters = workerModels.filter((_, idx) => idx !== selectedIndex)

  // New worker reviews
  const workerReview = await agent('Review proposal as skeptic', {
    model: newWorker,
    schema: {
      type: 'object',
      properties: {
        approved: { type: 'boolean' },
        concerns: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  // New arbiters vote
  const votes = await parallel(newArbiters.map(model =>
    () => agent('Vote: approve or reject', {
      model: model,
      schema: {
        type: 'object',
        properties: {
          vote: { type: 'string', enum: ['approve', 'reject'] },
          reasoning: { type: 'string' }
        }
      }
    })
  ))

  const approvals = votes.filter(v => v.vote === 'approve').length
  const hasConsensus = workerReview.approved && approvals > votes.length / 2

  return {
    consensus: hasConsensus,
    worker_review: workerReview,
    arbiter_votes: votes,
    approvals: approvals,
    rejections: votes.length - approvals
  }
}
```

## Key Rules

### ✅ DO:
1. **Use different arbiters** for different phases (review vs solve vs verify)
2. **Swap roles** after initial selection for validation
3. **Iterate** if consensus not reached (max 10 iterations recommended)
4. **Rotate arbiters** between iterations to prevent bias
5. **Track all proposals** (accepted and rejected) for AI attribution
6. **Log decisions** clearly for transparency
7. **Use `parallel()` for solve/refactor phases** - workers should propose solutions independently and concurrently by default
8. **Log progress before/after parallel operations** - helps users understand what's happening during long-running parallel work
9. **Use descriptive labels** on agent calls - labels show in `/workflows` progress UI

### ❌ DON'T:
1. **Never use same arbiter** for review AND solve in sequence
2. **Don't skip role swap** - it's critical for validation
3. **Don't iterate forever** - set max iterations (10 recommended)
4. **Don't ignore concerns** - if consensus fails, refine proposals
5. **Don't lose rejected proposals** - include in AI attribution
6. **Don't let same model** be arbiter twice in a row without rotation

## Model Selection Strategy

### Initial Assignment:
- **Opus**: Best for complex decisions, architectural choices
- **Sonnet**: Balanced, good for implementation decisions
- **Haiku**: Fast, good for simple validations

### Rotation Strategy:
```javascript
// Rotate arbiter based on iteration
const models = ['opus', 'sonnet', 'haiku']
const arbiterIndex = iteration % models.length
const currentArbiter = models[arbiterIndex]
```

### Multi-Phase Strategy:
```javascript
const phaseArbiters = {
  analysis: 'opus',     // Complex understanding
  design: 'sonnet',     // Balanced approach
  implement: 'haiku',   // Fast execution
  review: 'opus',       // Thorough validation
  verify: 'sonnet'      // Final check
}
```

## AI Attribution Integration

When using arbiter/worker pattern, capture full attribution:

```javascript
const attribution = {
  pattern: 'arbiter-worker',
  iteration: iteration,
  
  workers: WORKER_MODELS.map((model, idx) => ({
    model: model,
    proposal: proposals[idx],
    selected: idx === decision.selected_index
  })),
  
  arbiter: {
    model: arbiterModel,
    decision: decision.selected_index,
    reasoning: decision.reasoning,
    consensus_score: decision.consensus_score
  },
  
  role_swap: {
    new_worker: newWorkerModel,
    new_arbiters: newArbiters,
    worker_review: workerReview,
    arbiter_votes: arbiterVotes
  },
  
  consensus: hasConsensus,
  
  rejected_proposals: proposals
    .filter((_, idx) => idx !== decision.selected_index)
    .map((p, idx) => ({
      model: WORKER_MODELS[idx],
      proposal: p,
      rejection_reason: 'Not selected by arbiter'
    }))
}
```

## Use Cases

### Code Review
```javascript
// Workers find bugs
// Arbiter selects most critical findings
// Role swap validates findings aren't false positives
```

### Code Solve
```javascript
// Workers propose fixes in parallel (DEFAULT - always use parallel for solve)
const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix', { model, schema: FIX_SCHEMA })
))
// Arbiter selects best fix
// Role swap validates fix correctness
```

### Refactoring
```javascript
// Workers propose refactorings in parallel (DEFAULT - always use parallel for refactoring)
const refactorings = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose refactoring', { model, schema: REFACTOR_SCHEMA })
))
// Arbiter selects safest approach
// Role swap validates no regressions
```

### Architecture Decisions
```javascript
// Workers propose architectures
// Arbiter selects best fit
// Role swap identifies risks
```

### Multi-Phase Workflows
```javascript
// Review phase: Arbiter A
// Solve phase: Arbiter B (different!)
// Verify phase: Arbiter C (different!)
// Each phase validated with role swap
```

## Example: Complete Review + Solve

```javascript
// ============================================================================
// REVIEW PHASE (Arbiter: Opus)
// ============================================================================

const reviewWorkers = ['sonnet', 'haiku', 'opus']
const reviewArbiter = 'opus'

// 1. Workers find issues
const findings = await parallel(reviewWorkers.map(model =>
  () => agent('Find bugs', { model, schema: FINDING_SCHEMA })
))

// 2. Arbiter selects best findings
const reviewDecision = await agent('Select best findings', {
  model: reviewArbiter,
  schema: ARBITER_SCHEMA
})

// 3. Role swap validation
const reviewValidation = await validateWithRoleSwap(
  reviewDecision,
  reviewArbiter,
  reviewWorkers
)

if (!reviewValidation.consensus) {
  log('⚠️ Review phase failed consensus, iterating...')
  // Would iterate here
}

// ============================================================================
// SOLVE PHASE (Arbiter: Sonnet - DIFFERENT!)
// ============================================================================

const solveWorkers = ['opus', 'haiku', 'sonnet']
const solveArbiter = 'sonnet' // ⚠️ MUST be different from reviewArbiter

// 1. Workers propose fixes
const fixes = await parallel(solveWorkers.map(model =>
  () => agent('Propose fix', { model, schema: FIX_SCHEMA })
))

// 2. Arbiter selects best fix
const solveDecision = await agent('Select best fix', {
  model: solveArbiter, // Different arbiter!
  schema: ARBITER_SCHEMA
})

// 3. Role swap validation
const solveValidation = await validateWithRoleSwap(
  solveDecision,
  solveArbiter,
  solveWorkers
)

if (!solveValidation.consensus) {
  log('⚠️ Solve phase failed consensus, iterating...')
  // Would iterate here
}
```

## Inline Code (Copy into Workflows)

See the helper function `validateWithRoleSwap` above - copy it into your workflow along with the pattern phases.

## Progress Logging for Parallel Operations

When running parallel operations, always log before/after to provide visibility:

```javascript
// ❌ BAD: Silent parallel operation
const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix', { model, schema: FIX_SCHEMA })
))

// ✅ GOOD: Log before, use labels, log after
log(`🔄 ${WORKER_MODELS.length} workers proposing fixes in parallel...`)

const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix for bug #123', {
    label: `${model} Fix Proposal`,  // Shows in /workflows UI
    model: model,
    schema: FIX_SCHEMA
  })
))

const successCount = fixes.filter(Boolean).length
log(`✅ Received ${successCount}/${WORKER_MODELS.length} fix proposals`)
```

**Best practices:**
- Log BEFORE starting parallel work with count and purpose
- Use descriptive `label` on each agent call (shows in `/workflows` UI)
- Log AFTER completing with success count
- Include emojis for visual scanning: 🔄 (starting), ✅ (complete), ⚠️ (warnings)

## Parallel vs Pipeline: When to Use Each

### Use `parallel()` for Solve/Refactor Phases (DEFAULT)
```javascript
// ✅ CORRECT: Workers propose solutions independently
log(`🔄 ${WORKER_MODELS.length} workers proposing fixes...`)

const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix for bug', {
    label: `${model} Fix`,
    model: model,
    schema: FIX_SCHEMA
  })
))

log(`✅ Received ${fixes.filter(Boolean).length} proposals`)

// ✅ CORRECT: Workers propose refactorings independently
log(`🔄 ${WORKER_MODELS.length} workers proposing refactorings...`)

const refactorings = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose refactoring', {
    label: `${model} Refactoring`,
    model: model,
    schema: REFACTOR_SCHEMA
  })
))

log(`✅ Received ${refactorings.filter(Boolean).length} proposals`)
```

**Why parallel()**: In solve/refactor phases, workers should propose independently without seeing each other's work. This gives diverse perspectives and prevents groupthink.

### Use `pipeline()` for Multi-Stage Analysis
```javascript
// ✅ CORRECT: Review multiple items sequentially through stages
const results = await pipeline(
  items,
  // Stage 1: Analyze each item
  item => agent('Analyze', { schema: ANALYSIS_SCHEMA }),
  // Stage 2: Based on analysis, propose fix
  (analysis, item) => agent('Propose fix', { schema: FIX_SCHEMA })
)
```

**Why pipeline()**: Use when each item needs to go through multiple dependent stages, but items can process independently of each other.

### Rule of Thumb
- **Solve/Refactor/Fix phases**: Always `parallel()` (workers propose independently)
- **Review phases with multiple items**: `pipeline()` if stages are dependent, `parallel()` if single-stage
- **When in doubt for solve**: Use `parallel()`

## Related Memories
- [[ai-attribution-tracking]] - How to capture arbiter/worker attribution
- [[code-skills-autonomous]] - Autonomous workflow patterns
- [[workflow-registration-filter]] - Workflow constraints

## When to Use This Pattern

**Use when:**
- ✅ Decision quality is critical
- ✅ Multiple valid approaches exist
- ✅ You need consensus validation
- ✅ Bias must be minimized
- ✅ Transparency is required

**Don't use when:**
- ❌ Decision is trivial
- ❌ One model is clearly sufficient
- ❌ Speed is more important than quality
- ❌ No ambiguity in the solution

---

**Status**: Production pattern, proven effective  
**Date**: 2026-06-04  
**Applications**: Code review, code solve, refactoring, architecture decisions  
**Key Rule**: Different arbiters for different phases (review ≠ solve ≠ verify)
