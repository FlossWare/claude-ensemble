// TEMPLATE: Arbiter/Worker Pattern Workflow
// Copy this as a starting point for new workflows
// Includes all reusable instructions to prevent prompts

export const meta = {
  name: 'template-arbiter-worker',
  description: 'Template workflow using arbiter/worker pattern with best practices',
  phases: [
    { title: 'Analysis', detail: 'Workers analyze in parallel', model: 'opus' },
    { title: 'Proposals', detail: 'Workers propose solutions', model: 'sonnet' },
    { title: 'Selection', detail: 'Arbiter picks best', model: 'haiku' },
    { title: 'Role Swap', detail: 'Validate with swapped roles' }
  ]
}

// ============================================================================
// REUSABLE INSTRUCTIONS (copy from shared/inline/instructions.js)
// ============================================================================

const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

const INLINE_FUNCTION_INSTRUCTION = `
REMEMBER: Workflows using scriptPath CANNOT use ES6 imports/exports.
- Use plain function declarations (NOT export function)
- Copy functions inline from shared/inline/ directory
- No import statements in the refactored code
`.trim()

const STRUCTURED_OUTPUT_INSTRUCTION = `
Return ONLY valid JSON matching the schema.
- All required fields must be present
- Use correct types (number, string, boolean, array, object)
- No extra fields not in the schema
`.trim()

const ARBITER_ROTATION_INSTRUCTION = `
CRITICAL: Use DIFFERENT arbiters for different phases.
- Review phase: Arbiter A
- Solve phase: Arbiter B (DIFFERENT from A!)
- Verify phase: Arbiter C (DIFFERENT from A and B!)
Never use the same arbiter for review AND solve.
`.trim()

// ============================================================================
// CONFIGURATION
// ============================================================================

const WORKER_MODELS = ['opus', 'sonnet', 'haiku']
const ANALYSIS_ARBITER = 'opus'
const PROPOSAL_ARBITER = 'sonnet'  // Different from analysis!
const VERIFY_ARBITER = 'haiku'     // Different from both!

const ITEMS_TO_PROCESS = args?.items || ['item1', 'item2']

log(`🚀 TEMPLATE WORKFLOW`)
log('═'.repeat(80))
log(`Workers: ${WORKER_MODELS.join(', ')}`)
log(`Arbiters: Analysis=${ANALYSIS_ARBITER}, Proposal=${PROPOSAL_ARBITER}, Verify=${VERIFY_ARBITER}`)
log(`Items: ${ITEMS_TO_PROCESS.length}`)
log('═'.repeat(80))

// ============================================================================
// HELPER: Role Swap Validation
// ============================================================================

async function validateWithRoleSwap(decision, selectedProposal, arbiterModel, workerModels, context) {
  const newWorker = arbiterModel
  const selectedIndex = decision.selected_index
  const newArbiters = workerModels.filter((_, idx) => idx !== selectedIndex)

  log(`🔄 Role swap: ${arbiterModel} → worker, ${newArbiters.join(', ')} → arbiters`)

  // New worker reviews skeptically
  log(`🔍 ${newWorker} reviewing as skeptical worker...`)

  const workerReview = await agent(`Review this proposal as a skeptic.

${NO_BASH_INSTRUCTION}

Proposal:
${JSON.stringify(selectedProposal, null, 2)}

Context: ${context}

Find issues, risks, or problems. Default to concerns if uncertain.`, {
    label: `${newWorker} Skeptical Review`,
    model: newWorker,
    schema: {
      type: 'object',
      properties: {
        approved: { type: 'boolean' },
        concerns: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'number', minimum: 0, maximum: 100 }
      },
      required: ['approved', 'concerns', 'confidence']
    }
  })

  log(`${workerReview.approved ? '✅' : '⚠️'} Worker review: ${workerReview.approved ? 'APPROVED' : 'CONCERNS'}`)

  // New arbiters vote
  log(`🗳️  ${newArbiters.length} arbiters voting...`)

  const arbiterVotes = await parallel(newArbiters.map(model =>
    () => agent(`Vote on this proposal as an arbiter.

${NO_BASH_INSTRUCTION}

Proposal:
${JSON.stringify(selectedProposal, null, 2)}

Worker review from ${newWorker}:
${JSON.stringify(workerReview, null, 2)}

Vote: approve or reject?`, {
      label: `${model} Vote`,
      model: model,
      schema: {
        type: 'object',
        properties: {
          vote: { type: 'string', enum: ['approve', 'reject'] },
          reasoning: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 100 }
        },
        required: ['vote', 'reasoning', 'confidence']
      }
    })
  ))

  const approvals = arbiterVotes.filter(Boolean).filter(v => v.vote === 'approve').length
  const rejections = arbiterVotes.filter(Boolean).length - approvals

  log(`✅ Votes: ${approvals} approve, ${rejections} reject`)

  const hasConsensus = workerReview.approved && approvals > rejections

  return {
    consensus: hasConsensus,
    worker_review: workerReview,
    arbiter_votes: arbiterVotes.filter(Boolean),
    approvals,
    rejections
  }
}

// ============================================================================
// PHASE 1: Analysis (Workers propose in parallel)
// ============================================================================

phase('Analysis')

log(`📊 ${WORKER_MODELS.length} workers analyzing in parallel...`)

const analysisResults = await pipeline(
  ITEMS_TO_PROCESS,

  // Stage 1: Workers analyze each item in parallel
  (item) => {
    log(`  🔍 Analyzing: ${item}`)

    return parallel(WORKER_MODELS.map(model =>
      () => agent(`Analyze item: ${item}

${NO_BASH_INSTRUCTION}

${STRUCTURED_OUTPUT_INSTRUCTION}

Identify patterns, issues, or opportunities.

Return structured analysis.`, {
        label: `${model}: Analyze ${item}`,
        model: model,
        phase: 'Analysis',
        schema: {
          type: 'object',
          properties: {
            item: { type: 'string' },
            findings: { type: 'array', items: { type: 'string' } },
            confidence: { type: 'number', minimum: 0, maximum: 100 }
          }
        }
      })
    )).then(analyses => {
      const count = analyses.filter(Boolean).length
      log(`    ✅ ${count}/${WORKER_MODELS.length} analyses complete`)
      return analyses
    })
  },

  // Stage 2: Arbiter selects best analysis
  (analyses, item) => {
    const validAnalyses = analyses.filter(Boolean)

    log(`  ⚖️  Arbiter (${ANALYSIS_ARBITER}) selecting best analysis for ${item}...`)

    return agent(`Select best analysis for item: ${item}

${ARBITER_ROTATION_INSTRUCTION}

${STRUCTURED_OUTPUT_INSTRUCTION}

Analyses:
${validAnalyses.map((a, i) => `
**Analysis ${i + 1}** (${WORKER_MODELS[i]}):
- Findings: ${a.findings?.length || 0}
- Confidence: ${a.confidence}%
`).join('\n')}

Select the most thorough and accurate analysis.`, {
      label: `Arbiter: Select ${item}`,
      model: ANALYSIS_ARBITER,
      phase: 'Analysis',
      schema: {
        type: 'object',
        properties: {
          selected_index: { type: 'number', minimum: 0, maximum: validAnalyses.length - 1 },
          reasoning: { type: 'string' },
          consensus_score: { type: 'number', minimum: 0, maximum: 100 }
        }
      }
    }).then(decision => {
      log(`    ✅ Selected: ${WORKER_MODELS[decision.selected_index]}'s analysis`)
      return {
        item,
        analysis: validAnalyses[decision.selected_index],
        decision
      }
    })
  }
)

log(`✅ Analysis complete for ${analysisResults.filter(Boolean).length} items`)

// ============================================================================
// PHASE 2: Proposals (Workers propose solutions in parallel)
// ============================================================================

phase('Proposals')

log(`✍️  ${WORKER_MODELS.length} workers proposing solutions in parallel...`)

const proposalResults = await pipeline(
  analysisResults.filter(Boolean),

  // Stage 1: Workers propose solutions
  (analysisResult) => {
    log(`  📝 ${analysisResult.item}: ${WORKER_MODELS.length} workers proposing...`)

    return parallel(WORKER_MODELS.map(model =>
      () => agent(`Propose solution for: ${analysisResult.item}

${NO_BASH_INSTRUCTION}

${INLINE_FUNCTION_INSTRUCTION}

${STRUCTURED_OUTPUT_INSTRUCTION}

Analysis:
${JSON.stringify(analysisResult.analysis, null, 2)}

Propose a complete solution.`, {
        label: `${model}: Propose ${analysisResult.item}`,
        model: model,
        phase: 'Proposals',
        schema: {
          type: 'object',
          properties: {
            solution: { type: 'string' },
            approach: { type: 'string' },
            confidence: { type: 'number', minimum: 0, maximum: 100 }
          }
        }
      })
    )).then(proposals => {
      const count = proposals.filter(Boolean).length
      log(`    ✅ ${count}/${WORKER_MODELS.length} proposals received`)
      return proposals
    })
  },

  // Stage 2: DIFFERENT arbiter selects best proposal
  (proposals, analysisResult) => {
    const validProposals = proposals.filter(Boolean)

    log(`  ⚖️  Arbiter (${PROPOSAL_ARBITER}) selecting best proposal for ${analysisResult.item}...`)

    return agent(`Select best proposal for: ${analysisResult.item}

${ARBITER_ROTATION_INSTRUCTION}

${STRUCTURED_OUTPUT_INSTRUCTION}

Proposals:
${validProposals.map((p, i) => `
**Proposal ${i + 1}** (${WORKER_MODELS[i]}):
- Approach: ${p.approach}
- Confidence: ${p.confidence}%
`).join('\n')}

Select the best proposal.`, {
      label: `Arbiter: Select ${analysisResult.item}`,
      model: PROPOSAL_ARBITER,  // DIFFERENT arbiter!
      phase: 'Proposals',
      schema: {
        type: 'object',
        properties: {
          selected_index: { type: 'number', minimum: 0, maximum: validProposals.length - 1 },
          reasoning: { type: 'string' },
          consensus_score: { type: 'number', minimum: 0, maximum: 100 }
        }
      }
    }).then(decision => {
      log(`    ✅ Selected: ${WORKER_MODELS[decision.selected_index]}'s proposal`)
      return {
        item: analysisResult.item,
        proposal: validProposals[decision.selected_index],
        selected_by: WORKER_MODELS[decision.selected_index],
        arbiter_decision: decision
      }
    })
  },

  // Stage 3: Role swap validation
  (proposalResult, analysisResult) => {
    log(`  🔄 Role swap validation for ${analysisResult.item}...`)

    return validateWithRoleSwap(
      proposalResult.arbiter_decision,
      proposalResult.proposal,
      PROPOSAL_ARBITER,
      WORKER_MODELS,
      `Solution for ${analysisResult.item}`
    ).then(validation => ({
      ...proposalResult,
      validation,
      consensus: validation.consensus
    }))
  }
)

// ============================================================================
// SUMMARY
// ============================================================================

const consensusReached = proposalResults.filter(Boolean).filter(r => r.consensus)
const consensusFailed = proposalResults.filter(Boolean).filter(r => !r.consensus)

log('')
log('═'.repeat(80))
log('✅ WORKFLOW COMPLETE')
log('═'.repeat(80))
log(`Total items: ${ITEMS_TO_PROCESS.length}`)
log(`Consensus reached: ${consensusReached.length}`)
log(`Need revision: ${consensusFailed.length}`)
log('')

if (consensusReached.length > 0) {
  log(`✅ APPROVED:`)
  consensusReached.forEach(r => {
    log(`   ${r.item}: ${r.selected_by}`)
  })
}

if (consensusFailed.length > 0) {
  log('')
  log(`⚠️  NEED REVISION:`)
  consensusFailed.forEach(r => {
    const concerns = r.validation?.worker_review?.concerns?.length || 0
    log(`   ${r.item}: ${concerns} concerns`)
  })
}

return {
  total: ITEMS_TO_PROCESS.length,
  consensus_reached: consensusReached.length,
  consensus_failed: consensusFailed.length,
  approved: consensusReached.map(r => ({
    item: r.item,
    solution: r.proposal.solution,
    selected_by: r.selected_by
  })),
  failed: consensusFailed.map(r => ({
    item: r.item,
    concerns: r.validation?.worker_review?.concerns || []
  }))
}
