/**
 * Workflow Helper Functions
 *
 * Reusable patterns for arbiter/worker workflows.
 * Copy these inline into workflows (no imports - workflows using scriptPath can't use ES6 modules).
 */

// ============================================================================
// STANDARD INSTRUCTIONS (copy these into workflow prompts)
// ============================================================================

export const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

export const INLINE_FUNCTION_INSTRUCTION = `
REMEMBER: Workflows using scriptPath CANNOT use ES6 imports/exports.
- Use plain function declarations (NOT export function)
- Copy functions inline from shared/inline/ directory
- No import statements in the refactored code
`.trim()

export const STRUCTURED_OUTPUT_INSTRUCTION = `
Return ONLY valid JSON matching the schema.
- All required fields must be present
- Use correct types (number, string, boolean, array, object)
- No extra fields not in the schema
`.trim()

export const ARBITER_ROTATION_INSTRUCTION = `
CRITICAL: Use DIFFERENT arbiters for different phases.
- Review phase: Arbiter A
- Solve phase: Arbiter B (DIFFERENT from A!)
- Verify phase: Arbiter C (DIFFERENT from A and B!)
Never use the same arbiter for review AND solve.
`.trim()

export const CONSENSUS_INSTRUCTION = `
Multi-AI consensus requires:
- Different models for workers (Opus, Sonnet, GPT-4o, Gemini, Haiku)
- Independent analysis (no workers see each other's work)
- Arbiter synthesizes AFTER all workers complete
- Graceful fallback if any model fails
- For batch processing, use batchConsensusWithWorker from shared/batch-consensus-wrapper.mjs
`.trim()

export const BATCH_CONSENSUS_INSTRUCTION = `
For processing arrays of questions/tasks with consensus:
- Import batchConsensusWithWorker from '../shared/batch-consensus-wrapper.mjs'
- Define custom worker function that returns {model, answer, confidence, votes}
- Configure concurrency (default: 10 parallel)
- Use onProgress callback for progress tracking
- Graceful error handling (partial results returned)
- Automatic caching for duplicate questions (when consensus-cache is enabled)
`.trim()

// ============================================================================
// COMMON SCHEMAS
// ============================================================================

export const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          title: { type: 'string' },
          description: { type: 'string' },
          suggestion: { type: 'string' }
        },
        required: ['file', 'severity', 'title', 'description']
      }
    }
  },
  required: ['findings']
}

export const PROPOSAL_SCHEMA = {
  type: 'object',
  properties: {
    proposals: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          approach: { type: 'string' },
          rationale: { type: 'string' },
          tradeoffs: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 1 }
        },
        required: ['approach', 'rationale']
      }
    }
  },
  required: ['proposals']
}

export const DECISION_SCHEMA = {
  type: 'object',
  properties: {
    selected_index: { type: 'number' },
    reasoning: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
    concerns: { type: 'array', items: { type: 'string' } }
  },
  required: ['selected_index', 'reasoning', 'confidence']
}

export const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['approve', 'reject', 'revise'] },
    reasoning: { type: 'string' },
    concerns: { type: 'array', items: { type: 'string' } },
    suggestions: { type: 'array', items: { type: 'string' } }
  },
  required: ['verdict', 'reasoning']
}

// ============================================================================
// HELPER FUNCTIONS (copy these inline into workflows)
// ============================================================================

/**
 * Role swap validation pattern
 * Swaps arbiter → worker, workers → new arbiters for adversarial check
 */
export function createRoleSwapValidator() {
  return async function validateWithRoleSwap(decision, selectedProposal, arbiterModel, workerModels, context) {
    const newWorker = arbiterModel
    const selectedIndex = decision.selected_index
    const newArbiters = workerModels.filter((_, idx) => idx !== selectedIndex)

    log(`🔄 Role swap: ${arbiterModel} → worker, ${newArbiters.join(', ')} → arbiters`)

    // New worker (former arbiter) reviews skeptically
    const skepticalReview = await agent(`As ${newWorker}, skeptically review this proposal:

${selectedProposal.approach}

Context: ${context}

You were the arbiter but now you're a worker. Be critical. Find flaws.
What could go wrong? What's missing?

${STRUCTURED_OUTPUT_INSTRUCTION}`, {
      label: `role-swap:${newWorker}`,
      model: newWorker,
      schema: VERDICT_SCHEMA
    })

    // New arbiters vote
    const votes = await parallel(
      newArbiters.map(arbiter => () =>
        agent(`As ${arbiter}, vote on this proposal:

${selectedProposal.approach}

Skeptical review found: ${JSON.stringify(skepticalReview)}

Vote: approve, reject, or revise?

${STRUCTURED_OUTPUT_INSTRUCTION}`, {
          label: `vote:${arbiter}`,
          model: arbiter,
          schema: VERDICT_SCHEMA
        })
      )
    )

    const approvals = votes.filter(Boolean).filter(v => v.verdict === 'approve').length
    const majority = votes.filter(Boolean).length / 2

    return {
      validated: approvals > majority,
      skepticalReview,
      votes: votes.filter(Boolean)
    }
  }
}

/**
 * Graceful fallback for worker failures
 */
export function createGracefulWorkers(models, minRequired = 2) {
  return async function runWorkersWithFallback(taskFn) {
    const results = await parallel(models.map(model => () => taskFn(model)))
    const successful = results.filter(Boolean)

    if (successful.length < minRequired) {
      throw new Error(`Insufficient workers succeeded: ${successful.length}/${models.length} (minimum: ${minRequired})`)
    }

    log(`✓ Workers: ${successful.length}/${models.length} succeeded`)
    return successful
  }
}

/**
 * Progress logging helper
 */
export function createProgressLogger(total, label = 'Progress') {
  let current = 0
  return function logProgress(increment = 1) {
    current += increment
    const percent = Math.round((current / total) * 100)
    log(`📊 ${label}: ${current}/${total} (${percent}%)`)
  }
}

/**
 * Consensus quality scorer
 */
export function calculateConsensusScore(workerResults) {
  if (!workerResults || workerResults.length < 2) return 0

  // Simple scoring: count agreements across findings
  const allFindings = workerResults.flatMap(r => r.findings || [])
  if (allFindings.length === 0) return 0

  const findingCounts = {}
  allFindings.forEach(f => {
    const key = `${f.file}:${f.line}:${f.title}`
    findingCounts[key] = (findingCounts[key] || 0) + 1
  })

  const agreements = Object.values(findingCounts).filter(count => count >= 2).length
  const total = Object.keys(findingCounts).length

  return total > 0 ? agreements / total : 0
}
