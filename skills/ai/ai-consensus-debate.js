export const meta = {
  name: 'ai-consensus-debate',
  description: 'Adversarial debate consensus - workers propose, exchange, rebut, arbiter judges',
  whenToUse: 'When you need adversarial testing of ideas, critical analysis, or multi-perspective validation',
  phases: [
    { title: 'Get Arbiter', detail: 'Determine next arbiter via rotation' },
    { title: 'Proposal Round', detail: 'Workers independently propose answers' },
    { title: 'Exchange Phase', detail: 'Workers see all competing proposals' },
    { title: 'Rebuttal Round', detail: 'Workers critique others and defend their position' },
    { title: 'Arbiter Judgment', detail: 'Arbiter evaluates proposals + rebuttals' },
    { title: 'Update State', detail: 'Record arbiter usage and feedback' },
  ],
}

// Import workflow storage adapter
import { getWorkflowStorage } from './shared/workflow-storage-adapter.cjs'
const { getLearningAuthHeader } = require('./shared/auth.js')
const workflowStorage = getWorkflowStorage()

// Rate limiting (fail-open)
let _rlm_mod = null;
try { const m = await import('./shared/rate-limit-manager.cjs'); _rlm_mod = m.default || m; } catch (_e) { /* rate limiting unavailable */ }
async function _rlFetch(provider, url, options) {
  if (_rlm_mod) { try { await _rlm_mod.checkRateLimit(provider); } catch (_e) { /* fail open */ } }
  const start = Date.now();
  try {
    const response = await fetch(url, options);
    if (_rlm_mod) { _rlm_mod.recordRequest(provider, response.ok, { url, duration_ms: Date.now() - start }).catch(() => {}); }
    return response;
  } catch (error) {
    if (_rlm_mod) { _rlm_mod.recordRequest(provider, false, { url, error: error.message, duration_ms: Date.now() - start }).catch(() => {}); }
    throw error;
  }
}

export default async function({ args, phase, log, agent, parallel }) {

// USAGE:
// const result = await workflow('ai-consensus-debate', {
//   task: 'Should we use microservices or monolith for this project?',
//   context: '<project details>',
//   schema: { type: 'object', properties: { position: 'string', reasoning: 'string' } },
//   arbiter_instructions: 'Judge which position has strongest evidence and reasoning',
//   debate_rounds: 1  // number of exchange-rebuttal cycles (default: 1)
// })

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

async function getWorkerModels(task, budget = 'medium') {
  // Call ai-task-router to dynamically select optimal models
  const routerResult = await workflow('ai-task-router', { task, budget })

  if (routerResult.error) {
    log(`Task router error: ${routerResult.error}, falling back to default models`)
    return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
  }

  const workers = routerResult.models || []
  log(`Task router selected ${workers.length} models: ${workers.join(', ')}`)

  return workers
}

function formatProposalsForExchange(proposals) {
  return proposals.map((p, i) => `
=== Proposal ${i + 1} (${p.model}) ===
${JSON.stringify(p.response, null, 2)}
`).join('\n')
}

function formatRebuttalsForJudging(rebuttals) {
  return rebuttals.map((r, i) => `
=== Worker ${i + 1} (${r.model}) Rebuttal ===
Defense of own position:
${r.response.defense || 'N/A'}

Critiques of other positions:
${JSON.stringify(r.response.critiques || [], null, 2)}
`).join('\n')
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const task = args.task || args
const context = args.context || ''
const budget = args.budget || 'medium'
const debateRounds = args.debate_rounds || args.debateRounds || 1
const schema = args.schema || {
  type: 'object',
  properties: {
    position: { type: 'string' },
    reasoning: { type: 'string' },
    confidence: { type: 'number' }
  }
}
const arbiterInstructions = args.arbiter_instructions || args.arbiterInstructions ||
  'Judge which proposal demonstrated strongest reasoning, evidence, and ability to address counterarguments'

if (!task) {
  log('No task provided')
  log('Usage: workflow("ai-consensus-debate", { task: "...", context: "...", schema: {...} })')
  return { error: 'No task provided' }
}

// Track workflow execution start time
const workflowStartTime = Date.now()
const workflowExecutionId = `debate_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

log('='.repeat(60))
log('ADVERSARIAL DEBATE CONSENSUS')
log('='.repeat(60))
log(`Task: ${task}`)
log(`Debate rounds: ${debateRounds}`)
log('')

// PHASE 0: Get next arbiter from rotation
phase('Get Arbiter')

const arbiterChoice = await workflow('get-next-arbiter')
log(`Arbiter for this run: ${arbiterChoice.arbiter} (previous: ${arbiterChoice.previous || 'none'})`)

// PHASE 1: Proposal Round - Workers independently propose answers
phase('Proposal Round')

const workerModels = await getWorkerModels(task, budget)
log(`Workers proposing initial answers (${workerModels.join(', ')})...`)

const proposalPrompt = (model) => `[${model.toUpperCase()} - PROPOSAL ROUND]

You are participating in an adversarial debate. In this round, propose your answer to the following task.

Task: ${task}

${context ? `Context:\n${context}\n\n` : ''}

Provide a clear position with strong reasoning. Your proposal will be shared with other AI models who will critique it, so make it robust.

Return structured data per schema.`

const proposalTasks = workerModels.map(model =>
  () => agent(proposalPrompt(model), {
    label: `${model}-proposal`,
    model: model,
    schema
  })
)

const proposals = await parallel(proposalTasks)
const validProposals = proposals.filter(Boolean)

log(`${validProposals.length}/${proposalTasks.length} proposals received`)

if (validProposals.length === 0) {
  log('All workers failed to propose')
  return { error: 'All workers failed in proposal round', workers: [] }
}

// Store debate history
const debateHistory = {
  proposals: validProposals,
  rounds: []
}

// PHASE 2 & 3: Exchange and Rebuttal Rounds (can repeat N times)
let currentRound = 0
let rebuttals = []

while (currentRound < debateRounds) {
  currentRound++

  phase(`Exchange Phase ${currentRound}`)

  log(`\nRound ${currentRound}: Workers reviewing all proposals...`)
  log(formatProposalsForExchange(validProposals))

  phase(`Rebuttal Round ${currentRound}`)

  const rebuttalSchema = {
    type: 'object',
    properties: {
      defense: { type: 'string', description: 'Defense of your original position' },
      critiques: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            target_model: { type: 'string' },
            weakness: { type: 'string' },
            counterargument: { type: 'string' }
          }
        },
        description: 'Critiques of other proposals'
      },
      revised_position: schema,
      confidence: { type: 'number', description: 'Confidence in your position after seeing others (0-100)' }
    }
  }

  const rebuttalPrompt = (model, originalProposal) => `[${model.toUpperCase()} - REBUTTAL ROUND ${currentRound}]

You are participating in an adversarial debate. You have seen all competing proposals.

Task: ${task}

YOUR ORIGINAL PROPOSAL:
${JSON.stringify(originalProposal.response, null, 2)}

ALL COMPETING PROPOSALS:
${formatProposalsForExchange(validProposals)}

Now you must:
1. DEFEND your original position against potential critiques
2. CRITIQUE the weaknesses in other proposals
3. REVISE your position if you found compelling counterarguments (or strengthen it if you remain convinced)

Be intellectually honest: if another proposal has merit, acknowledge it. If you found a flaw in your own reasoning, correct it.

Return structured rebuttal data per schema.`

  const rebuttalTasks = validProposals.map((proposal, idx) =>
    () => agent(rebuttalPrompt(proposal.model, proposal), {
      label: `${proposal.model}-rebuttal-r${currentRound}`,
      model: proposal.model,
      schema: rebuttalSchema
    })
  )

  rebuttals = await parallel(rebuttalTasks)
  const validRebuttals = rebuttals.filter(Boolean)

  log(`${validRebuttals.length}/${rebuttalTasks.length} rebuttals received`)

  if (validRebuttals.length === 0) {
    log('All workers failed in rebuttal round')
    break
  }

  debateHistory.rounds.push({
    round: currentRound,
    rebuttals: validRebuttals
  })

  // For multi-round debates, update proposals with revised positions
  if (currentRound < debateRounds) {
    validProposals.forEach((proposal, idx) => {
      const rebuttal = validRebuttals.find(r => r.model === proposal.model)
      if (rebuttal && rebuttal.response.revised_position) {
        proposal.response = rebuttal.response.revised_position
      }
    })
  }
}

// PHASE 4: Arbiter Judgment
phase('Arbiter Judgment')

log('')
log(`Arbiter (${arbiterChoice.arbiter}) evaluating debate...`)

const judgmentSchema = {
  type: 'object',
  properties: {
    winning_worker: { type: 'string' },
    why_selected: { type: 'string' },
    confidence: { type: 'number' },
    debate_quality: {
      type: 'object',
      properties: {
        quality_score: { type: 'number', description: '0-100 rating of debate quality' },
        key_insights: { type: 'string', description: 'Key insights that emerged from debate' },
        strongest_arguments: { type: 'array', items: { type: 'string' } },
        weakest_arguments: { type: 'array', items: { type: 'string' } }
      }
    },
    synthesis: schema
  }
}

const validRebuttals = rebuttals.filter(Boolean)

const judgment = await agent(`[ARBITER] Evaluate this adversarial debate and determine the winning position.

Task: ${task}

INITIAL PROPOSALS:
${formatProposalsForExchange(validProposals)}

REBUTTALS AND DEFENSES:
${formatRebuttalsForJudging(validRebuttals)}

Instructions:
${arbiterInstructions}

Evaluate based on:
1. Strength of original reasoning
2. Quality of defense against critiques
3. Validity of critiques against others
4. Intellectual honesty (willingness to revise when wrong)
5. Evidence and logical soundness

Return:
1. winning_worker: Which model presented the strongest position
2. why_selected: Detailed explanation of why this position won
3. confidence: 0-100 rating of your judgment certainty
4. debate_quality: Assessment of the debate process itself
5. synthesis: The best answer (or synthesized position)

`, {
  label: 'arbiter-judgment',
  model: arbiterChoice.arbiter,
  schema: judgmentSchema
})

log(`Winner: ${judgment.winning_worker}`)
log(`   Confidence: ${judgment.confidence}%`)
log(`   Debate Quality: ${judgment.debate_quality.quality_score}%`)
log(`   Reason: ${judgment.why_selected}`)

log('')

// PHASE 5: Update arbiter state for rotation tracking
phase('Update State')

await workflow('update-arbiter-state', {
  arbiter: arbiterChoice.arbiter,
  workflow_name: 'ai-consensus-debate'
})

// ============================================================================
// RECORD FEEDBACK TO LEARNING SYSTEM
// ============================================================================

// Use the workflow execution ID generated at the start
const executionId = workflowExecutionId

try {
  log('\nRecording feedback to learning system...')

  for (const proposal of validProposals) {
    const isWinner = proposal.model === judgment.winning_worker

    // Find this worker's final rebuttal to get confidence score
    const finalRebuttal = validRebuttals.find(r => r.model === proposal.model)
    const finalConfidence = finalRebuttal?.response?.confidence || 50

    const feedbackPayload = {
      worker_id: `${proposal.model}-debater`,
      model: proposal.model,
      consensus_score: judgment.confidence,
      tokens_used: 0,
      cost_usd: 0.0,
      accepted: isWinner,
      execution_id: executionId,
      reasoning: isWinner ? judgment.why_selected : `Non-winning position in adversarial debate`,
      outcome: 'success',
      workflow_type: 'ai-consensus-debate',
      metadata: {
        debate_rounds: debateRounds,
        final_worker_confidence: finalConfidence,
        debate_quality_score: judgment.debate_quality.quality_score
      }
    }

    try {
      const authHeader = getLearningAuthHeader()
      const response = await _rlFetch('learning-api', 'http://localhost:8000/api/learning/record-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader
        },
        body: JSON.stringify(feedbackPayload)
      })

      if (response.ok) {
        log(`Feedback recorded for ${proposal.model}: ${isWinner ? 'winner' : 'non-winner'}`)
      } else {
        log(`Failed to record feedback for ${proposal.model}: ${response.statusText}`)
      }
    } catch (err) {
      log(`Feedback recording failed for ${proposal.model}: ${err.message || err}`)
    }
  }
} catch (err) {
  log(`Learning system unavailable: ${err.message || err}`)
}

// ============================================================================
// EXTRACT LEARNINGS FROM DEBATE
// ============================================================================

try {
  log('\nExtracting learnings from debate...')

  await workflow('ai-extract-learning', {
    workflow_name: 'ai-consensus-debate',
    execution_id: executionId,
    outcome: 'success',
    context: {
      task: task,
      winner: judgment.winning_worker,
      debate_quality: judgment.debate_quality,
      rounds: debateRounds,
      key_insights: judgment.debate_quality.key_insights
    }
  })

  log('Learnings extracted successfully')
} catch (err) {
  log(`Learning extraction failed: ${err.message || err}`)
}

// ============================================================================
// WORKFLOW STORAGE: Log execution to PostgreSQL
// ============================================================================

try {
  log('\n💾 Storing workflow execution to PostgreSQL...')

  const workflowDuration = Date.now() - workflowStartTime

  // Store main execution
  const dbExecutionId = await workflowStorage.storeExecution({
    workflow_id: workflowExecutionId,
    workflow_name: 'ai-consensus-debate',
    task_description: task,
    total_workers: validProposals.length,
    total_duration_ms: workflowDuration,
    outcome: 'success',
    metadata: {
      context,
      budget,
      debate_rounds: debateRounds,
      arbiter_model: arbiterChoice.arbiter,
      winning_worker: judgment.winning_worker,
      rounds_completed: currentRound,
      debate_quality: judgment.debate_quality
    }
  })

  // Store worker proposals (from initial round)
  for (const proposal of validProposals) {
    await workflowStorage.storeWorkerResult({
      workflow_execution_id: dbExecutionId,
      worker_id: `${proposal.model}-debate-worker`,
      model: proposal.model,
      task_assigned: task,
      result: JSON.stringify(proposal.response),
      confidence: (proposal.response.confidence || 50) / 100,
      duration_ms: 0,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      outcome: proposal.model === judgment.winning_worker ? 'success' : 'completed',
      metadata: {
        is_winner: proposal.model === judgment.winning_worker,
        debate_rounds: currentRound
      }
    })
  }

  // Store arbiter decision
  await workflowStorage.storeArbiterDecision({
    workflow_execution_id: dbExecutionId,
    arbiter_model: arbiterChoice.arbiter,
    worker_result_ids: [],
    decision: JSON.stringify(judgment.synthesis),
    confidence: (judgment.confidence || 80) / 100,
    reasoning: judgment.reasoning || '',
    duration_ms: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    metadata: {
      winning_worker: judgment.winning_worker,
      debate_quality: judgment.debate_quality,
      rounds_completed: currentRound
    }
  })

  log(`✅ Workflow execution stored (DB ID: ${dbExecutionId})`)

} catch (err) {
  log(`⚠️  Workflow storage failed: ${err.message || err}`)
  log(`Stack: ${err.stack}`)
}

return {
  status: 'success',
  winner: judgment.winning_worker,
  confidence: judgment.confidence,
  result: judgment.synthesis,
  debate_quality: judgment.debate_quality,
  debate_history: debateHistory,
  all_workers: validProposals,
  execution_id: executionId,
  arbiter: arbiterChoice.arbiter,
  rounds_completed: currentRound
}

}
