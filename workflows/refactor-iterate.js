// Multi-AI Workflow Refactoring - ITERATION with Concern Feedback
// Takes failed proposals and their concerns, workers propose fixes

export const meta = {
  name: 'refactor-iterate',
  description: 'Iterate on failed refactorings with concern feedback using arbiter/worker pattern',
  phases: [
    { title: 'Load Concerns', detail: 'Load failed proposals and validation concerns' },
    { title: 'Revised Proposals', detail: 'Workers address concerns and revise', model: 'haiku' },
    { title: 'Arbiter Selection', detail: 'Different arbiter picks best revision', model: 'haiku' },
    { title: 'Role Swap Validation', detail: 'Validate with swapped roles' },
    { title: 'Consensus Check', detail: 'Iterate until consensus or max iterations' }
  ]
}

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


// Configuration
const MAX_ITERATIONS = args?.maxIterations || 3

// Load failed refactorings from file (args don't work reliably in workflows)
let FAILED_REFACTORINGS = args?.failedRefactorings || []

if (FAILED_REFACTORINGS.length === 0) {
  // Try to load from file
  const fileContent = await _agent(`Read the failed refactorings file and return its raw JSON content.

Use the Read tool to read:
/home/sfloess/.claude/repos/claude-global-skills/workflows/failed-refactorings.json

Return the complete file content as a string.`, {
    label: 'Load Failed Refactorings',
    schema: {
      type: 'object',
      properties: {
        json_content: { type: 'string' }
      }
    }
  })

  if (fileContent?.json_content) {
    try {
      FAILED_REFACTORINGS = JSON.parse(fileContent.json_content)
      log(`📂 Loaded ${FAILED_REFACTORINGS.length} failed refactorings from file`)
    } catch (error) {
      log(`⚠️  Failed to parse JSON: ${error.message}`)
    }
  } else {
    log(`⚠️  No failed refactorings found in file`)
  }
}

const WORKER_MODELS = ['opus', 'sonnet', 'haiku']

// Different arbiters for different iterations (rotation)
const ITERATION_ARBITERS = {
  1: 'haiku',   // Different from initial 'sonnet'
  2: 'opus',    // Rotate
  3: 'sonnet'   // Rotate back
}

log(`🔄 MULTI-AI REFACTORING ITERATION`)
log('═'.repeat(80))
log(`Failed refactorings to iterate: ${FAILED_REFACTORINGS.length}`)
log(`Worker models: ${WORKER_MODELS.join(', ')}`)
log(`Max iterations: ${MAX_ITERATIONS}`)
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
  log(`🔍 ${newWorker} reviewing as skeptical worker...`)

  const workerReview = await _agent(`Review this REVISED refactoring proposal as a skeptic.

Proposal:
${JSON.stringify(selectedProposal, null, 2)}

Context: ${context}

The proposal claims to address these concerns from previous iteration.
Your job: Find if concerns are ACTUALLY addressed or if new problems introduced.

Default to concerns if uncertain.

Return your assessment.`, {
    label: `${newWorker} Skeptical Review`,
    model: newWorker,
    schema: {
      type: 'object',
      properties: {
        approved: { type: 'boolean' },
        concerns_addressed: { type: 'array', items: { type: 'string' } },
        new_concerns: { type: 'array', items: { type: 'string' } },
        remaining_concerns: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'number', minimum: 0, maximum: 100 }
      },
      required: ['approved', 'concerns_addressed', 'new_concerns', 'remaining_concerns', 'confidence']
    }
  })

  log(`${workerReview.approved ? '✅' : '⚠️'} Worker review: ${workerReview.approved ? 'APPROVED' : 'CONCERNS'}`)

  if (workerReview.concerns_addressed?.length > 0) {
    log(`   ✅ Addressed: ${workerReview.concerns_addressed.length} concerns`)
  }
  if (workerReview.new_concerns?.length > 0) {
    log(`   ⚠️  New concerns: ${workerReview.new_concerns.length}`)
  }
  if (workerReview.remaining_concerns?.length > 0) {
    log(`   ❌ Remaining: ${workerReview.remaining_concerns.length} unresolved`)
  }

  // New arbiters vote
  log(`🗳️  ${newArbiters.length} arbiters voting...`)

  const arbiterVotes = await parallel(newArbiters.map(model =>
    () => agent(`Vote on this REVISED refactoring proposal as an arbiter.

Proposal:
${JSON.stringify(selectedProposal, null, 2)}

Worker review from ${newWorker}:
${JSON.stringify(workerReview, null, 2)}

Context: ${context}

Vote: approve or reject?

Approve ONLY if:
1. Original concerns are addressed
2. No new critical issues introduced
3. Changes are safe and correct

Reject if ANY critical concerns remain.`, {
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
// ITERATION LOOP
// ============================================================================

const allResults = []

for (let iteration = 1; iteration <= MAX_ITERATIONS; iteration++) {
  log('')
  log('═'.repeat(80))
  log(`🔄 ITERATION ${iteration}/${MAX_ITERATIONS}`)
  log('═'.repeat(80))

  const arbiterModel = ITERATION_ARBITERS[iteration] || ITERATION_ARBITERS[1]
  log(`Arbiter for this iteration: ${arbiterModel}`)

  // Determine which workflows to work on this iteration
  const workflowsToRefactor = iteration === 1
    ? FAILED_REFACTORINGS
    : allResults.filter(r => !r.consensus).map(r => ({
        workflow: r.workflow,
        concerns: r.validation.worker_review.remaining_concerns,
        risks: r.validation.worker_review.new_concerns || []
      }))

  if (workflowsToRefactor.length === 0) {
    log(`✅ All workflows reached consensus!`)
    break
  }

  log(`Working on ${workflowsToRefactor.length} workflows`)

  // ============================================================================
  // PHASE: Revised Proposals - Workers address concerns
  // ============================================================================

  phase('Revised Proposals')

  log(`✍️  ${WORKER_MODELS.length} workers proposing REVISED refactorings in parallel...`)

  const iterationResults = await pipeline(
    workflowsToRefactor,

    // Stage 1: Workers propose revised refactorings
    (failedItem) => {
      log(`  📝 ${failedItem.workflow}: ${WORKER_MODELS.length} workers revising...`)

      return parallel(WORKER_MODELS.map(model =>
        () => agent(`Propose REVISED refactoring for: ${failedItem.workflow}

CRITICAL CONCERNS FROM VALIDATION:
${failedItem.concerns?.map((c, i) => `${i + 1}. ${c}`).join('\n')}

${failedItem.risks?.length > 0 ? `\nRISKS IDENTIFIED:\n${failedItem.risks.map((r, i) => `${i + 1}. ${r}`).join('\n')}` : ''}

Your task: Propose a REVISED refactoring that:
1. ADDRESSES EVERY CONCERN above
2. Does NOT introduce new problems
3. Actually saves lines (don't add more than you remove)
4. Uses inline functions correctly (NO export syntax!)
5. Doesn't add unused dead code

IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data

For each concern, explain HOW you addressed it.

Return complete refactoring plan.`, {
          label: `${model}: Revise ${failedItem.workflow}`,
          model: model,
          phase: 'Revised Proposals',
          schema: {
            type: 'object',
            properties: {
              workflow: { type: 'string' },
              concerns_addressed: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    concern: { type: 'string' },
                    how_addressed: { type: 'string' }
                  }
                }
              },
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
              actual_lines_saved: { type: 'number' },
              confidence: { type: 'number', minimum: 0, maximum: 100 }
            }
          }
        })
      )).then(proposals => {
        const count = proposals.filter(Boolean).length
        log(`    ✅ Received ${count}/${WORKER_MODELS.length} revised proposals`)
        return proposals
      })
    },

    // Stage 2: Arbiter selects best revised proposal
    (proposals, failedItem) => {
      const validProposals = proposals.filter(Boolean)

      log(`  ⚖️  Arbiter (${arbiterModel}) selecting best revision for ${failedItem.workflow}...`)

      return agent(`Review ${validProposals.length} REVISED refactoring proposals for: ${failedItem.workflow}

ORIGINAL CONCERNS:
${failedItem.concerns?.map((c, i) => `${i + 1}. ${c}`).join('\n')}

REVISED PROPOSALS:
${validProposals.map((p, i) => `
**Proposal ${i + 1}** (${WORKER_MODELS[i]}):
- Concerns addressed: ${p.concerns_addressed?.length || 0}
- Changes: ${p.changes?.length || 0}
- Lines saved: ${p.actual_lines_saved || 0}
- Confidence: ${p.confidence}%

Addresses:
${p.concerns_addressed?.map(ca => `  ✅ ${ca.concern}\n     → ${ca.how_addressed}`).join('\n')}
`).join('\n')}

Select the BEST revised proposal based on:
1. All critical concerns addressed (REQUIRED)
2. No new problems introduced
3. Actually saves lines (positive actual_lines_saved)
4. Clear, safe changes
5. High confidence

Return selected index and reasoning.`, {
        label: `Arbiter: Select ${failedItem.workflow}`,
        model: arbiterModel,
        phase: 'Revised Proposals',
        schema: {
          type: 'object',
          properties: {
            selected_index: { type: 'number', minimum: 0, maximum: validProposals.length - 1 },
            reasoning: { type: 'string' },
            consensus_score: { type: 'number', minimum: 0, maximum: 100 },
            concerns_fully_addressed: { type: 'boolean' }
          }
        }
      }).then(decision => {
        log(`    ✅ Selected: ${WORKER_MODELS[decision.selected_index]}'s proposal`)
        log(`       Consensus: ${decision.consensus_score}%`)
        log(`       Concerns addressed: ${decision.concerns_fully_addressed ? 'YES' : 'PARTIAL'}`)

        return {
          workflow: failedItem.workflow,
          proposal: validProposals[decision.selected_index],
          selected_by: WORKER_MODELS[decision.selected_index],
          arbiter_decision: decision,
          all_proposals: validProposals
        }
      })
    },

    // Stage 3: Role swap validation
    (proposalResult, failedItem) => {
      log(`  🔄 Role swap validation for ${failedItem.workflow}...`)

      return validateWithRoleSwap(
        proposalResult.arbiter_decision,
        proposalResult.proposal,
        arbiterModel,
        WORKER_MODELS,
        `Iteration ${iteration} revision for ${failedItem.workflow}`
      ).then(validation => ({
        ...proposalResult,
        validation,
        iteration,
        consensus: validation.consensus
      }))
    }
  )

  // Add to all results
  allResults.push(...iterationResults.filter(Boolean))

  // Summary for this iteration
  const consensusReached = iterationResults.filter(Boolean).filter(r => r.consensus)
  const consensusFailed = iterationResults.filter(Boolean).filter(r => !r.consensus)

  log('')
  log(`📊 ITERATION ${iteration} SUMMARY:`)
  log(`   Consensus reached: ${consensusReached.length}`)
  log(`   Need more work: ${consensusFailed.length}`)

  if (consensusReached.length > 0) {
    log(`   ✅ Approved:`)
    consensusReached.forEach(r => {
      log(`      - ${r.workflow} (${r.selected_by})`)
    })
  }

  if (consensusFailed.length > 0 && iteration < MAX_ITERATIONS) {
    log(`   ⚠️  Continuing to iteration ${iteration + 1} for:`)
    consensusFailed.forEach(r => {
      const remaining = r.validation.worker_review.remaining_concerns?.length || 0
      const newConcerns = r.validation.worker_review.new_concerns?.length || 0
      log(`      - ${r.workflow} (${remaining} remaining, ${newConcerns} new)`)
    })
  }

  // Stop if all reached consensus
  if (consensusFailed.length === 0) {
    log(`✅ All workflows reached consensus in ${iteration} iterations!`)
    break
  }

  // Stop if max iterations reached
  if (iteration === MAX_ITERATIONS) {
    log(`⚠️  Max iterations (${MAX_ITERATIONS}) reached`)
    log(`   ${consensusFailed.length} workflows still need work`)
  }
}

// ============================================================================
// FINAL SUMMARY
// ============================================================================

log('')
log('═'.repeat(80))
log('✅ ITERATION COMPLETE')
log('═'.repeat(80))

// Get final consensus state
const finalConsensus = allResults.filter(r => r.consensus)
const finalFailed = allResults
  .filter(r => !r.consensus)
  // Get latest iteration for each workflow
  .reduce((acc, r) => {
    const existing = acc.find(x => x.workflow === r.workflow)
    if (!existing || r.iteration > existing.iteration) {
      return [...acc.filter(x => x.workflow !== r.workflow), r]
    }
    return acc
  }, [])

log(`Total workflows: ${FAILED_REFACTORINGS.length}`)
log(`Consensus reached: ${finalConsensus.length}`)
log(`Still need work: ${finalFailed.length}`)
log('')

if (finalConsensus.length > 0) {
  log(`✅ APPROVED REFACTORINGS (ready to apply):`)
  finalConsensus.forEach(r => {
    log(`   ${r.workflow}:`)
    log(`      Selected by: ${r.selected_by}`)
    log(`      Iteration: ${r.iteration}`)
    log(`      Lines saved: ${r.proposal.actual_lines_saved || 0}`)
    log(`      Changes: ${r.proposal.changes?.length || 0}`)
    log(`      Concerns addressed: ${r.proposal.concerns_addressed?.length || 0}`)
  })
}

if (finalFailed.length > 0) {
  log('')
  log(`⚠️  STILL NEED WORK:`)
  finalFailed.forEach(r => {
    log(`   ${r.workflow}:`)
    log(`      Remaining concerns: ${r.validation.worker_review.remaining_concerns?.length || 0}`)
    log(`      New concerns: ${r.validation.worker_review.new_concerns?.length || 0}`)
    log(`      Last iteration: ${r.iteration}`)
  })
}

return {
  total_workflows: FAILED_REFACTORINGS.length,
  consensus_reached: finalConsensus.length,
  still_need_work: finalFailed.length,
  max_iterations_reached: MAX_ITERATIONS,
  approved_refactorings: finalConsensus.map(r => ({
    workflow: r.workflow,
    proposal: r.proposal,
    selected_by: r.selected_by,
    iteration_reached_consensus: r.iteration,
    arbiter_reasoning: r.arbiter_decision.reasoning,
    validation: r.validation
  })),
  failed_refactorings: finalFailed.map(r => ({
    workflow: r.workflow,
    remaining_concerns: r.validation.worker_review.remaining_concerns || [],
    new_concerns: r.validation.worker_review.new_concerns || [],
    last_iteration: r.iteration
  }))
}
