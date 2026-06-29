// Multi-AI Workflow Refactoring using Arbiter/Worker Pattern
// Refactors all workflows in parallel with consensus validation

export const meta = {
  name: 'refactor-all-workflows',
  description: 'Refactor all workflows using multi-AI arbiter/worker pattern with inline functions',
  phases: [
    { title: 'Analysis', detail: 'Workers analyze each workflow', model: 'opus' },
    { title: 'Refactor Proposals', detail: 'Workers propose inline function integration' },
    { title: 'Arbiter Selection', detail: 'Arbiter picks best proposals', model: 'sonnet' },
    { title: 'Role Swap Validation', detail: 'Swap roles and validate' },
    { title: 'Apply Changes', detail: 'Apply approved refactorings' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

// Configuration
const WORKFLOWS_TO_REFACTOR = args?.workflows || [
  'code-hygiene-review.js',
  'code-test-review.js',
  'doc-review.js',
  'pr-review.js',
  'pr-verify.js',
  'code-improve.js',
  'ai-prompt.js',
  'workflow-cleanup.js'
]

const WORKER_MODELS = ['opus', 'sonnet', 'haiku']
const REVIEW_ARBITER = 'opus'  // For analysis phase
const REFACTOR_ARBITER = 'sonnet'  // Different arbiter for refactor phase
const VERIFY_ARBITER = 'haiku'  // Different arbiter for verification phase

log(`🔄 MULTI-AI WORKFLOW REFACTORING`)
log('═'.repeat(80))
log(`Workflows: ${WORKFLOWS_TO_REFACTOR.length}`)
log(`Worker models: ${WORKER_MODELS.join(', ')}`)
log(`Arbiters: Review=${REVIEW_ARBITER}, Refactor=${REFACTOR_ARBITER}, Verify=${VERIFY_ARBITER}`)
log('═'.repeat(80))

// ============================================================================
// INLINE FUNCTIONS (Arbiter/Worker Pattern Helper)
// ============================================================================

async function validateWithRoleSwap(decision, selectedProposal, arbiterModel, workerModels, context) {
  // Previous arbiter becomes skeptical worker
  const newWorker = arbiterModel

  // Previous workers (except selected) become arbiters
  const selectedIndex = decision.selected_index
  const newArbiters = workerModels.filter((_, idx) => idx !== selectedIndex)

  log(`🔄 Role swap: ${arbiterModel} → worker, ${newArbiters.join(', ')} → arbiters`)

  // New worker reviews skeptically
  const workerReview = await _agent(`Review this refactoring proposal as a skeptic.

Proposal:
${JSON.stringify(selectedProposal, null, 2)}

Context: ${context}

Find issues, risks, or problems. Default to concerns if uncertain.

Return your assessment.`, {
    label: `${newWorker} Skeptical Review`,
    model: newWorker,
    schema: {
      type: 'object',
      properties: {
        approved: { type: 'boolean' },
        concerns: { type: 'array', items: { type: 'string' } },
        risks: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'number', minimum: 0, maximum: 100 }
      },
      required: ['approved', 'concerns', 'confidence']
    }
  })

  // New arbiters vote
  const arbiterVotes = await parallel(newArbiters.map(model =>
    () => agent(`Vote on this refactoring proposal as an arbiter.

Proposal:
${JSON.stringify(selectedProposal, null, 2)}

Worker review from ${newWorker}:
${JSON.stringify(workerReview, null, 2)}

Context: ${context}

Vote: approve or reject?`, {
      label: `${model} Arbiter Vote`,
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
// PHASE 1: Analysis - Workers analyze each workflow
// ============================================================================

phase('Analysis')

log('📊 Workers analyzing workflows for refactoring opportunities...')

const allAnalyses = await pipeline(
  WORKFLOWS_TO_REFACTOR,

  // Stage 1: Each workflow analyzed by all workers in parallel
  (workflow) => parallel(WORKER_MODELS.map(model =>
    () => agent(`Analyze workflow: ${workflow}

IMPORTANT: Use the Read tool to analyze the file, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data

Identify:
1. Platform detection code (can use detectPlatform inline function)
2. Git operations (can use getCommitHistory, getDiff, findSourceFiles, etc.)
3. Issue operations (can use listIssues, createIssue, etc.)
4. Schema duplication (can use shared schemas)
5. Missing AI attribution

For each pattern found:
- Exact line numbers
- Which inline function to use
- Code to replace

Be specific and thorough.`, {
      label: `${model}: Analyze ${workflow}`,
      model: model,
      phase: 'Analysis',
      schema: {
        type: 'object',
        properties: {
          workflow: { type: 'string' },
          patterns_found: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                pattern_type: { type: 'string', enum: ['platform_detection', 'git_operation', 'issue_operation', 'schema_duplication', 'missing_attribution'] },
                line_start: { type: 'number' },
                line_end: { type: 'number' },
                current_code: { type: 'string' },
                replacement_function: { type: 'string' },
                inline_module: { type: 'string' }
              }
            }
          },
          total_lines_duplicated: { type: 'number' },
          confidence: { type: 'number', minimum: 0, maximum: 100 }
        }
      }
    })
  )),

  // Stage 2: Arbiter selects best analysis for each workflow
  (analyses, workflow) => {
    const validAnalyses = analyses.filter(Boolean)

    return _agent(`Review ${validAnalyses.length} analyses for workflow: ${workflow}

Analyses:
${validAnalyses.map((a, i) => `
**Analysis ${i + 1}** (${WORKER_MODELS[i]}):
- Patterns found: ${a.patterns_found?.length || 0}
- Lines duplicated: ${a.total_lines_duplicated || 0}
- Confidence: ${a.confidence}%
`).join('\n')}

Select the MOST THOROUGH analysis based on:
1. Number of patterns found
2. Specificity (line numbers, exact functions)
3. Completeness (all duplication types covered)
4. Confidence

Return selected index and reasoning.`, {
      label: `Arbiter: Select ${workflow} Analysis`,
      model: REVIEW_ARBITER,
      phase: 'Analysis',
      schema: {
        type: 'object',
        properties: {
          selected_index: { type: 'number', minimum: 0, maximum: validAnalyses.length - 1 },
          reasoning: { type: 'string' },
          consensus_score: { type: 'number', minimum: 0, maximum: 100 }
        }
      }
    }).then(decision => ({
      workflow,
      analysis: validAnalyses[decision.selected_index],
      arbiter_decision: decision
    }))
  }
)

log(`✅ Analysis complete for ${allAnalyses.filter(Boolean).length} workflows`)

// ============================================================================
// PHASE 2: Refactor Proposals - Workers propose specific changes
// ============================================================================

phase('Refactor Proposals')

log('✍️  Workers proposing refactorings...')

const allProposals = await pipeline(
  allAnalyses.filter(Boolean),

  // Stage 1: Each worker proposes refactoring based on analysis
  (analysisResult) => parallel(WORKER_MODELS.map(model =>
    () => agent(`Propose refactoring for: ${analysisResult.workflow}

Analysis:
${JSON.stringify(analysisResult.analysis, null, 2)}

IMPORTANT: Use the Read tool to read files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data

Create a refactoring plan:
1. List all inline functions to copy (with source files)
2. For each pattern, provide exact old_code and new_code
3. Specify line numbers for each change
4. Preserve all functionality
5. Add AI attribution if missing

Return complete refactoring plan.`, {
      label: `${model}: Propose ${analysisResult.workflow}`,
      model: model,
      phase: 'Refactor Proposals',
      schema: {
        type: 'object',
        properties: {
          workflow: { type: 'string' },
          inline_functions_to_copy: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                function_name: { type: 'string' },
                source_file: { type: 'string' }
              }
            }
          },
          changes: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                line_start: { type: 'number' },
                line_end: { type: 'number' },
                old_code: { type: 'string' },
                new_code: { type: 'string' },
                description: { type: 'string' }
              }
            }
          },
          estimated_lines_saved: { type: 'number' },
          confidence: { type: 'number', minimum: 0, maximum: 100 }
        }
      }
    })
  )),

  // Stage 2: Different arbiter selects best refactoring proposal
  (proposals, analysisResult) => {
    const validProposals = proposals.filter(Boolean)

    return _agent(`Review ${validProposals.length} refactoring proposals for: ${analysisResult.workflow}

Proposals:
${validProposals.map((p, i) => `
**Proposal ${i + 1}** (${WORKER_MODELS[i]}):
- Inline functions: ${p.inline_functions_to_copy?.length || 0}
- Changes: ${p.changes?.length || 0}
- Lines saved: ${p.estimated_lines_saved || 0}
- Confidence: ${p.confidence}%
`).join('\n')}

Select the BEST proposal based on:
1. Correctness (preserves functionality)
2. Completeness (addresses all patterns)
3. Minimal risk (clear, simple changes)
4. Maximum benefit (lines saved)

Return selected index and reasoning.`, {
      label: `Arbiter: Select ${analysisResult.workflow} Proposal`,
      model: REFACTOR_ARBITER,  // Different arbiter!
      phase: 'Refactor Proposals',
      schema: {
        type: 'object',
        properties: {
          selected_index: { type: 'number', minimum: 0, maximum: validProposals.length - 1 },
          reasoning: { type: 'string' },
          consensus_score: { type: 'number', minimum: 0, maximum: 100 },
          concerns: { type: 'array', items: { type: 'string' } }
        }
      }
    }).then(decision => ({
      workflow: analysisResult.workflow,
      proposal: validProposals[decision.selected_index],
      selected_by: WORKER_MODELS[decision.selected_index],
      arbiter_decision: decision,
      all_proposals: validProposals
    }))
  }
)

log(`✅ Proposals complete for ${allProposals.filter(Boolean).length} workflows`)

// ============================================================================
// PHASE 3: Role Swap Validation
// ============================================================================

phase('Role Swap Validation')

log('🔄 Validating proposals with role swapping...')

const validatedProposals = await parallel(allProposals.filter(Boolean).map(proposalResult =>
  () => validateWithRoleSwap(
    proposalResult.arbiter_decision,
    proposalResult.proposal,
    REFACTOR_ARBITER,
    WORKER_MODELS,
    `Refactoring ${proposalResult.workflow}`
  ).then(validation => ({
    ...proposalResult,
    validation
  }))
))

const consensusReached = validatedProposals.filter(Boolean).filter(p => p.validation?.consensus)
const consensusFailed = validatedProposals.filter(Boolean).filter(p => !p.validation?.consensus)

log(`✅ Consensus: ${consensusReached.length} approved, ${consensusFailed.length} need revision`)

if (consensusFailed.length > 0) {
  log(`⚠️  Failed consensus:`)
  consensusFailed.forEach(p => {
    log(`   - ${p.workflow}: ${p.validation?.worker_review?.concerns?.join(', ') || 'Unknown concerns'}`)
  })
}

// ============================================================================
// PHASE 4: Summary
// ============================================================================

log('')
log('═'.repeat(80))
log('✅ MULTI-AI REFACTORING ANALYSIS COMPLETE')
log('═'.repeat(80))
log(`Total workflows: ${WORKFLOWS_TO_REFACTOR.length}`)
log(`Analyzed: ${allAnalyses.filter(Boolean).length}`)
log(`Proposals created: ${allProposals.filter(Boolean).length}`)
log(`Consensus reached: ${consensusReached.length}`)
log(`Need revision: ${consensusFailed.length}`)
log('')

// Return approved refactorings
return {
  total_workflows: WORKFLOWS_TO_REFACTOR.length,
  consensus_reached: consensusReached.length,
  consensus_failed: consensusFailed.length,
  approved_refactorings: consensusReached.map(p => ({
    workflow: p.workflow,
    proposal: p.proposal,
    selected_by: p.selected_by,
    arbiter_reasoning: p.arbiter_decision.reasoning,
    validation: p.validation
  })),
  failed_refactorings: consensusFailed.map(p => ({
    workflow: p.workflow,
    concerns: p.validation?.worker_review?.concerns || [],
    risks: p.validation?.worker_review?.risks || []
  }))
}

}

