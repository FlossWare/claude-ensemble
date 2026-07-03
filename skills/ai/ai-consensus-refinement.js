export const meta = {
  name: 'ai-consensus-refinement',
  description: 'Self-correcting multi-AI consensus - iteratively refines worker responses via arbiter critique until confidence exceeds threshold',
  whenToUse: 'When you need high-confidence consensus and want low-quality responses automatically improved through critique-revision loops',
  phases: [
    { title: 'Get Arbiter', detail: 'Determine next arbiter via rotation' },
    { title: 'Workers', detail: 'Parallel worker execution with confidence scoring' },
    { title: 'Arbiter Evaluation', detail: 'Arbiter evaluates responses and identifies weaknesses' },
    { title: 'Refinement Loop', detail: 'Workers revise based on critique until confidence threshold met' },
    { title: 'Final Synthesis', detail: 'Arbiter produces final answer from refined responses' },
    { title: 'Update State', detail: 'Record arbiter usage and learning feedback' },
  ],
}

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
// const result = await workflow('ai-consensus-refinement', {
//   task: 'Analyze this code for security vulnerabilities',
//   context: '<code here>',
//   schema: { type: 'object', properties: { ... } },
//   arbiter_instructions: 'Select the most thorough analysis',
//   confidenceThreshold: 80,       // default 80, target confidence to stop refining
//   maxRefinementRounds: 3,        // default 3, max critique-revision cycles
//   models: ['opus', 'sonnet', 'haiku'],  // optional, defaults to task-router selection
//   budget: 'medium',              // optional, passed to task-router
// })

// ============================================================================
// INPUT PARSING
// ============================================================================

const task = args.task || (typeof args === 'string' ? args : null)
const context = args.context || ''
const confidenceThreshold = args.confidenceThreshold ?? args.confidence_threshold ?? 80
const maxRefinementRounds = args.maxRefinementRounds ?? args.max_refinement_rounds ?? 3
const budget = args.budget || 'medium'
const userModels = args.models || null
const schema = args.schema || {
  type: 'object',
  properties: {
    answer: { type: 'string', description: 'Your answer to the task' },
  },
  required: ['answer'],
}
const arbiterInstructions = args.arbiter_instructions || 'Select and synthesize the best answer with highest quality and accuracy'

if (!task) {
  log('ERROR: No task provided')
  log('Usage: workflow("ai-consensus-refinement", { task: "...", context: "...", schema: {...} })')
  log('')
  log('Options:')
  log('  task                   - The question or task (required)')
  log('  context                - Additional context for workers')
  log('  schema                 - JSON Schema for the answer portion')
  log('  arbiter_instructions   - Custom instructions for the arbiter')
  log('  confidenceThreshold    - Target confidence to stop refining (0-100, default: 80)')
  log('  maxRefinementRounds    - Max critique-revision cycles (default: 3)')
  log('  models                 - Array of model names (default: task-router selection)')
  log('  budget                 - Budget tier for task-router (default: medium)')
  return { error: 'No task provided' }
}

// ============================================================================
// HELPERS
// ============================================================================

function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 50
  return Math.max(0, Math.min(100, value))
}

// ============================================================================
// WORKER SCHEMA: wraps user schema with confidence + reasoning
// ============================================================================

const workerSchema = {
  type: 'object',
  properties: {
    answer: schema,
    confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Your confidence in this answer (0-100). Be calibrated: do not default to high confidence.',
    },
    reasoning: {
      type: 'string',
      description: 'Why you chose this answer and why you assigned this confidence level.',
    },
    caveats: {
      type: 'array',
      items: { type: 'string' },
      description: 'Any caveats, limitations, or uncertainties about your answer.',
    },
  },
  required: ['answer', 'confidence', 'reasoning'],
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

log('='.repeat(60))
log('SELF-CORRECTING MULTI-AI CONSENSUS')
log('='.repeat(60))
log(`Task: ${task}`)
log(`Confidence Threshold: ${confidenceThreshold}%`)
log(`Max Refinement Rounds: ${maxRefinementRounds}`)
log('')

// PHASE 0: Get next arbiter from rotation
phase('Get Arbiter')

const arbiterChoice = await workflow('get-next-arbiter')
const arbiterModel = arbiterChoice.arbiter
log(`Arbiter for this run: ${arbiterModel} (previous: ${arbiterChoice.previous || 'none'})`)

// PHASE 1: Initial worker execution
phase('Workers')

let workerModels
if (userModels && userModels.length > 0) {
  workerModels = userModels
  log(`Using user-specified models: ${workerModels.join(', ')}`)
} else {
  // Use task router for dynamic model selection
  try {
    const routerResult = await workflow('ai-task-router', { task, budget })
    if (routerResult.error) {
      log(`Task router error: ${routerResult.error}, falling back to defaults`)
      workerModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    } else {
      workerModels = routerResult.models || ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
      log(`Task router selected: ${workerModels.join(', ')}`)
    }
  } catch (err) {
    log(`Task router unavailable: ${err.message || err}, falling back to defaults`)
    workerModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
  }
}

log(`${workerModels.length} workers executing in parallel...`)

const buildWorkerPrompt = (model, critiqueContext) => {
  let prompt = `You are ${model.toUpperCase()}, responding as part of a multi-model consensus process with self-correction.

TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}`

  if (critiqueContext) {
    prompt += `
IMPORTANT - REVISION REQUIRED:
The arbiter has reviewed your previous response and provided specific critique.
You MUST address every point in the critique to improve your answer.

YOUR PREVIOUS ANSWER:
${JSON.stringify(critiqueContext.previousAnswer, null, 2)}

YOUR PREVIOUS CONFIDENCE: ${critiqueContext.previousConfidence}%

ARBITER CRITIQUE:
${critiqueContext.critique}

SPECIFIC WEAKNESSES TO ADDRESS:
${(critiqueContext.weaknesses || []).map((w, i) => `${i + 1}. ${w}`).join('\n')}

Revise your answer to address all critique points. Your confidence should reflect genuine improvement.
Do NOT simply inflate your confidence score without substantive changes.
`
  } else {
    prompt += `
INSTRUCTIONS:
1. Provide your best answer to the task.
2. Rate your confidence from 0 to 100:
   - 0-20: Very uncertain, mostly guessing
   - 21-40: Low confidence, significant uncertainty
   - 41-60: Moderate confidence, could go either way
   - 61-80: Fairly confident, minor uncertainties remain
   - 81-100: Highly confident, strong evidence/reasoning supports this
3. Be calibrated: do NOT default to high confidence. If unsure, say so.
4. List any caveats or limitations.
`
  }

  prompt += '\nReturn structured data per schema.'
  return prompt
}

// Initial worker execution
const initialWorkerTasks = workerModels.map(model =>
  () => {
    try {
      return agent(buildWorkerPrompt(model, null), {
        label: `${model}-refinement-worker`,
        model,
        schema: workerSchema,
      })
    } catch (err) {
      log(`  WARNING: Worker ${model} threw: ${err.message || err}`)
      return null
    }
  }
)

const initialResults = await parallel(initialWorkerTasks)

// Pair results with model names
let currentResponses = workerModels
  .map((model, i) => {
    const result = initialResults[i]
    if (!result) return null
    return {
      model,
      answer: result.answer || null,
      confidence: clampConfidence(result.confidence),
      reasoning: result.reasoning || '',
      caveats: result.caveats || [],
      revision: 0,
    }
  })
  .filter(Boolean)

log(`${currentResponses.length}/${workerModels.length} workers completed`)

if (currentResponses.length === 0) {
  log('ERROR: All workers failed on initial round')
  return {
    status: 'error',
    error: 'All workers failed to produce initial results',
    models_attempted: workerModels,
  }
}

// Log initial confidences
currentResponses.forEach(r => {
  log(`  ${r.model}: confidence=${r.confidence}%`)
})

// ============================================================================
// REFINEMENT LOOP
// ============================================================================

const refinementHistory = [{
  round: 0,
  label: 'initial',
  responses: currentResponses.map(r => ({
    model: r.model,
    confidence: r.confidence,
    reasoning: r.reasoning,
  })),
}]

let roundsUsed = 0
let arbiterConfidence = 0

// Arbiter evaluation schema
const critiqueSchema = {
  type: 'object',
  properties: {
    overall_confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Overall confidence in the current set of worker responses (0-100)',
    },
    meets_threshold: {
      type: 'boolean',
      description: 'Whether the responses collectively meet the quality/confidence threshold',
    },
    per_worker_critique: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          model: { type: 'string' },
          needs_revision: { type: 'boolean' },
          current_confidence: { type: 'number' },
          critique: { type: 'string', description: 'Specific critique of what is wrong or weak' },
          weaknesses: {
            type: 'array',
            items: { type: 'string' },
            description: 'Specific weaknesses to address in revision',
          },
        },
        required: ['model', 'needs_revision', 'critique'],
      },
    },
    synthesis_notes: {
      type: 'string',
      description: 'Notes about the overall quality and where improvement is needed',
    },
  },
  required: ['overall_confidence', 'meets_threshold', 'per_worker_critique', 'synthesis_notes'],
}

for (let round = 1; round <= maxRefinementRounds; round++) {
  // Evaluate current responses
  phase('Arbiter Evaluation')

  log('')
  log(`--- Refinement Round ${round}/${maxRefinementRounds} ---`)
  log(`Arbiter (${arbiterModel}) evaluating current responses...`)

  const evaluation = await agent(`[ARBITER - EVALUATION - Round ${round}]
You are evaluating ${currentResponses.length} worker responses to determine if they meet the quality bar.

ORIGINAL TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}

CONFIDENCE THRESHOLD: ${confidenceThreshold}%
The responses must collectively demonstrate confidence of at least ${confidenceThreshold}% to pass.

CURRENT WORKER RESPONSES:
${currentResponses.map(r => `
--- ${r.model.toUpperCase()} (Self-reported confidence: ${r.confidence}%, Revision: ${r.revision}) ---
Answer: ${JSON.stringify(r.answer, null, 2)}
Reasoning: ${r.reasoning}
Caveats: ${(r.caveats || []).length > 0 ? r.caveats.join('; ') : 'None'}
`).join('\n')}

${refinementHistory.length > 1 ? `
REFINEMENT HISTORY:
${refinementHistory.map(h => `Round ${h.round} (${h.label}): ${h.responses.map(r => `${r.model}=${r.confidence}%`).join(', ')}`).join('\n')}
` : ''}

EVALUATION INSTRUCTIONS:
1. Assess the OVERALL quality and confidence of the responses.
2. For EACH worker, determine if their response needs revision.
3. If a response needs revision, provide SPECIFIC, ACTIONABLE critique.
4. Set meets_threshold to true ONLY if you are genuinely satisfied the responses are strong enough.
5. Do NOT be lenient. If answers are vague, incomplete, or lack evidence, demand improvement.
6. Consider both individual response quality AND cross-response agreement.

Be rigorous but fair. The goal is to drive genuine improvement, not endless iteration.`, {
    label: `arbiter-evaluate-round-${round}`,
    model: arbiterModel,
    schema: critiqueSchema,
  })

  arbiterConfidence = clampConfidence(evaluation.overall_confidence)

  log(`Arbiter overall confidence: ${arbiterConfidence}%`)
  log(`Meets threshold: ${evaluation.meets_threshold}`)

  // Check if we have met the threshold
  if (evaluation.meets_threshold && arbiterConfidence >= confidenceThreshold) {
    log(`Confidence threshold met at round ${round}. Proceeding to final synthesis.`)
    roundsUsed = round
    refinementHistory.push({
      round,
      label: 'evaluation_passed',
      arbiter_confidence: arbiterConfidence,
      responses: currentResponses.map(r => ({
        model: r.model,
        confidence: r.confidence,
        reasoning: r.reasoning,
      })),
    })
    break
  }

  // Identify which workers need revision
  const workersNeedingRevision = (evaluation.per_worker_critique || [])
    .filter(c => c.needs_revision)

  if (workersNeedingRevision.length === 0) {
    log('No workers flagged for revision despite not meeting threshold. Proceeding to synthesis.')
    roundsUsed = round
    refinementHistory.push({
      round,
      label: 'no_revisions_needed',
      arbiter_confidence: arbiterConfidence,
      responses: currentResponses.map(r => ({
        model: r.model,
        confidence: r.confidence,
        reasoning: r.reasoning,
      })),
    })
    break
  }

  log(`${workersNeedingRevision.length} worker(s) need revision:`)
  workersNeedingRevision.forEach(c => {
    log(`  ${c.model}: ${c.critique.substring(0, 80)}...`)
  })

  // Send critique back to workers for revision
  phase('Refinement Loop')

  log(`Sending critique to ${workersNeedingRevision.length} worker(s) for revision...`)

  const revisionTasks = workersNeedingRevision.map(critique => {
    const currentResponse = currentResponses.find(r => r.model === critique.model)
    if (!currentResponse) return null

    return () => {
      try {
        return agent(buildWorkerPrompt(critique.model, {
          previousAnswer: currentResponse.answer,
          previousConfidence: currentResponse.confidence,
          critique: critique.critique,
          weaknesses: critique.weaknesses || [],
        }), {
          label: `${critique.model}-revision-round-${round}`,
          model: critique.model,
          schema: workerSchema,
        })
      } catch (err) {
        log(`  WARNING: Revision for ${critique.model} threw: ${err.message || err}`)
        return null
      }
    }
  }).filter(Boolean)

  const revisionResults = await parallel(revisionTasks)

  // Merge revised responses back into currentResponses
  let revisionsApplied = 0
  for (let i = 0; i < workersNeedingRevision.length; i++) {
    const critique = workersNeedingRevision[i]
    const revised = revisionResults[i]
    if (!revised) continue

    const idx = currentResponses.findIndex(r => r.model === critique.model)
    if (idx === -1) continue

    const previousConfidence = currentResponses[idx].confidence
    const newConfidence = clampConfidence(revised.confidence)

    currentResponses[idx] = {
      model: critique.model,
      answer: revised.answer || currentResponses[idx].answer,
      confidence: newConfidence,
      reasoning: revised.reasoning || currentResponses[idx].reasoning,
      caveats: revised.caveats || [],
      revision: round,
    }

    const delta = newConfidence - previousConfidence
    log(`  ${critique.model}: ${previousConfidence}% -> ${newConfidence}% (${delta >= 0 ? '+' : ''}${delta})`)
    revisionsApplied++
  }

  log(`${revisionsApplied} revision(s) applied`)

  refinementHistory.push({
    round,
    label: 'revision',
    arbiter_confidence: arbiterConfidence,
    revisions_applied: revisionsApplied,
    responses: currentResponses.map(r => ({
      model: r.model,
      confidence: r.confidence,
      reasoning: r.reasoning,
      revision: r.revision,
    })),
  })

  roundsUsed = round

  // If this is the last round, we proceed to synthesis regardless
  if (round === maxRefinementRounds) {
    log(`Max refinement rounds (${maxRefinementRounds}) reached. Proceeding to final synthesis.`)
  }
}

// ============================================================================
// FINAL SYNTHESIS
// ============================================================================

phase('Final Synthesis')

log('')
log(`Arbiter (${arbiterModel}) producing final synthesis from refined responses...`)

const finalArbiterSchema = {
  type: 'object',
  properties: {
    winning_worker: { type: 'string' },
    why_selected: { type: 'string' },
    confidence: { type: 'number' },
    synthesis: schema,
    refinement_impact: {
      type: 'string',
      description: 'How the refinement process improved the final answer compared to initial responses',
    },
  },
  required: ['winning_worker', 'why_selected', 'confidence', 'synthesis'],
}

const synthesis = await agent(`[ARBITER - FINAL SYNTHESIS]
You are producing the final synthesized answer after ${roundsUsed} round(s) of refinement.

ORIGINAL TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}

REFINED WORKER RESPONSES:
${currentResponses.map(r => `
--- ${r.model.toUpperCase()} (Confidence: ${r.confidence}%, Revisions: ${r.revision}) ---
Answer: ${JSON.stringify(r.answer, null, 2)}
Reasoning: ${r.reasoning}
Caveats: ${(r.caveats || []).length > 0 ? r.caveats.join('; ') : 'None'}
`).join('\n')}

REFINEMENT HISTORY:
${refinementHistory.map(h => `Round ${h.round} (${h.label}): ${h.responses.map(r => `${r.model}=${r.confidence}%`).join(', ')}${h.arbiter_confidence ? ` | Arbiter: ${h.arbiter_confidence}%` : ''}`).join('\n')}

INSTRUCTIONS:
${arbiterInstructions}

1. Select the best worker response (or synthesize a combination).
2. Explain why it was selected.
3. Rate your overall confidence in the final answer (0-100).
4. Describe how the refinement process improved the outcome (if at all).

If refinement produced genuine improvement, reflect that in your confidence score.
If responses remained stagnant despite critique, note that honestly.`, {
  label: 'arbiter-final-synthesis',
  model: arbiterModel,
  schema: finalArbiterSchema,
})

const finalConfidence = clampConfidence(synthesis.confidence)

log(`Winner: ${synthesis.winning_worker}`)
log(`  Final Confidence: ${finalConfidence}%`)
log(`  Reason: ${synthesis.why_selected}`)
if (synthesis.refinement_impact) {
  log(`  Refinement Impact: ${synthesis.refinement_impact}`)
}

// ============================================================================
// UPDATE STATE
// ============================================================================

phase('Update State')

await workflow('update-arbiter-state', { arbiter: arbiterModel, workflow_name: 'ai-consensus-refinement' })

// ============================================================================
// RECORD FEEDBACK TO LEARNING SYSTEM
// ============================================================================

const executionId = `refinement_${args?._timestamp || 'exec'}_${Math.random().toString(36).substr(2, 9)}`

try {
  log('')
  log('Recording feedback to learning system...')

  for (const worker of currentResponses) {
    const isWinner = worker.model === synthesis.winning_worker

    const feedbackPayload = {
      worker_id: `${worker.model}-refinement-worker`,
      model: worker.model,
      consensus_score: finalConfidence,
      confidence: worker.confidence,
      tokens_used: 0,
      cost_usd: 0.0,
      accepted: isWinner,
      execution_id: executionId,
      reasoning: isWinner ? synthesis.why_selected : `Non-winning response in refinement consensus`,
      outcome: 'success',
      workflow_type: 'ai-consensus-refinement',
      refinement_rounds: roundsUsed,
      revision_count: worker.revision,
    }

    try {
      const token = process.env.LEARNING_API_TOKEN
      const authHeader = token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await _rlFetch('learning-api', 'http://localhost:8000/api/learning/record-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader
        },
        body: JSON.stringify(feedbackPayload)
      })

      if (response.ok) {
        log(`Feedback recorded for ${worker.model}: ${isWinner ? 'winner' : 'non-winner'} (${worker.revision} revisions)`)
      } else {
        log(`Failed to record feedback for ${worker.model}: ${response.statusText}`)
      }
    } catch (err) {
      log(`Feedback recording failed for ${worker.model}: ${err.message || err}`)
    }
  }
} catch (err) {
  log(`Learning system unavailable: ${err.message || err}`)
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'ai-consensus-refinement',
    execution_data: {
      task,
      rounds_used: roundsUsed,
      max_rounds: maxRefinementRounds,
      confidence_threshold: confidenceThreshold,
      final_confidence: finalConfidence,
      threshold_met: finalConfidence >= confidenceThreshold,
      refinement_history: refinementHistory,
    },
  })
} catch (err) {
  log(`WARNING: Learning extraction failed: ${err.message || err}`)
}

// ============================================================================
// FINAL OUTPUT
// ============================================================================

// Compute improvement metrics
const initialAvgConfidence = refinementHistory[0].responses.reduce((s, r) => s + r.confidence, 0) / refinementHistory[0].responses.length
const finalAvgWorkerConfidence = currentResponses.reduce((s, r) => s + r.confidence, 0) / currentResponses.length
const confidenceImprovement = finalAvgWorkerConfidence - initialAvgConfidence

log('')
log('='.repeat(60))
log('SELF-CORRECTING CONSENSUS RESULT')
log('='.repeat(60))
log(`  Rounds Used: ${roundsUsed}/${maxRefinementRounds}`)
log(`  Threshold: ${confidenceThreshold}% | Final: ${finalConfidence}%`)
log(`  Threshold Met: ${finalConfidence >= confidenceThreshold ? 'YES' : 'NO'}`)
log(`  Avg Worker Confidence: ${initialAvgConfidence.toFixed(1)}% -> ${finalAvgWorkerConfidence.toFixed(1)}% (${confidenceImprovement >= 0 ? '+' : ''}${confidenceImprovement.toFixed(1)})`)
log(`  Winner: ${synthesis.winning_worker}`)
log('='.repeat(60))

return {
  status: finalConfidence >= confidenceThreshold ? 'threshold_met' : 'max_rounds_reached',
  winner: synthesis.winning_worker,
  why_selected: synthesis.why_selected,
  confidence: finalConfidence,
  result: synthesis.synthesis,
  refinement_impact: synthesis.refinement_impact || null,
  refinement: {
    rounds_used: roundsUsed,
    max_rounds: maxRefinementRounds,
    confidence_threshold: confidenceThreshold,
    threshold_met: finalConfidence >= confidenceThreshold,
    initial_avg_confidence: parseFloat(initialAvgConfidence.toFixed(1)),
    final_avg_worker_confidence: parseFloat(finalAvgWorkerConfidence.toFixed(1)),
    confidence_improvement: parseFloat(confidenceImprovement.toFixed(1)),
    history: refinementHistory,
  },
  arbiter: arbiterModel,
  workers: currentResponses.map(r => ({
    model: r.model,
    confidence: r.confidence,
    reasoning: r.reasoning,
    caveats: r.caveats,
    revisions: r.revision,
  })),
  execution_id: executionId,
}
return

}
