export const meta = {
  name: 'ai-consensus-weighted',
  description: 'Weighted multi-AI consensus - runs models in parallel with confidence scores, combines via weighted average/voting',
  whenToUse: 'When you need consensus with confidence-weighted synthesis rather than simple arbiter selection',
  phases: [
    { title: 'Workers', detail: 'Parallel model execution with confidence-scored responses' },
    { title: 'Weighting', detail: 'Compute weighted scores and identify agreements/disagreements' },
    { title: 'Synthesis', detail: 'Arbiter produces final answer informed by weights' },
  ],
}

// Import workflow storage adapter
import { getWorkflowStorage } from './shared/workflow-storage-adapter.js'
const workflowStorage = getWorkflowStorage()

// ============================================================================
// USAGE:
//
// const result = await workflow('ai-consensus-weighted', {
//   task: 'What is the best database for this use case?',
//   context: '<details here>',
//   schema: { type: 'object', properties: { recommendation: { type: 'string' } } },
//   arbiter_instructions: 'Focus on practical tradeoffs',
//   models: ['opus', 'sonnet', 'haiku'],         // optional, defaults to opus/sonnet/haiku
//   weight_strategy: 'average',                   // 'average' | 'voting' | 'max_confidence'
//   min_confidence_threshold: 20,                 // optional, discard answers below this
// })
// ============================================================================

// ---------------------------------------------------------------------------
// Input parsing with defaults
// ---------------------------------------------------------------------------

const task = args.task || (typeof args === 'string' ? args : null)
const context = args.context || ''
const userSchema = args.schema || {
  type: 'object',
  properties: {
    answer: { type: 'string', description: 'Your answer to the task' },
  },
  required: ['answer'],
}
const arbiterInstructions = args.arbiter_instructions || 'Synthesize the best answer, weighting higher-confidence responses more heavily'
const models = args.models || ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const weightStrategy = args.weight_strategy || 'average'   // average | voting | max_confidence
const minConfidenceThreshold = args.min_confidence_threshold ?? 0

if (!task) {
  log('ERROR: No task provided')
  log('Usage: workflow("ai-consensus-weighted", { task: "...", context: "...", schema: {...} })')
  log('')
  log('Options:')
  log('  task                    - The question or task (required)')
  log('  context                 - Additional context for workers')
  log('  schema                  - JSON Schema for the answer portion')
  log('  arbiter_instructions    - Custom instructions for the arbiter')
  log('  models                  - Array of model names (default: opus, sonnet, haiku)')
  log('  weight_strategy         - "average" | "voting" | "max_confidence" (default: average)')
  log('  min_confidence_threshold - Discard workers below this confidence (0-100, default: 0)')
  return { error: 'No task provided' }
}

// ---------------------------------------------------------------------------
// Worker schema: wraps the user schema and adds confidence + reasoning
// ---------------------------------------------------------------------------

const workerSchema = {
  type: 'object',
  properties: {
    answer: userSchema,
    confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Your confidence in this answer (0 = no confidence, 100 = completely certain). Be honest and calibrated.',
    },
    reasoning: {
      type: 'string',
      description: 'Brief explanation of why you chose this answer and why you assigned this confidence level.',
    },
    caveats: {
      type: 'array',
      items: { type: 'string' },
      description: 'Any caveats, limitations, or uncertainties about your answer.',
    },
  },
  required: ['answer', 'confidence', 'reasoning'],
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 50
  return Math.max(0, Math.min(100, value))
}

function computeWeightedAverage(responses) {
  const totalWeight = responses.reduce((sum, r) => sum + r.confidence, 0)
  if (totalWeight === 0) return 0
  return totalWeight / responses.length
}

function groupByAnswer(responses) {
  const groups = {}
  for (const r of responses) {
    const key = JSON.stringify(r.answer)
    if (!groups[key]) {
      groups[key] = {
        answer: r.answer,
        supporters: [],
        totalConfidence: 0,
        count: 0,
      }
    }
    groups[key].supporters.push({ model: r.model, confidence: r.confidence, reasoning: r.reasoning })
    groups[key].totalConfidence += r.confidence
    groups[key].count += 1
  }
  return Object.values(groups)
}

function selectByStrategy(responses, strategy) {
  const groups = groupByAnswer(responses)

  switch (strategy) {
    case 'voting': {
      // Each response is one vote weighted by confidence
      // Group with highest total weighted votes wins
      groups.sort((a, b) => b.totalConfidence - a.totalConfidence)
      const winner = groups[0]
      return {
        selectedAnswer: winner.answer,
        selectionMethod: 'weighted_voting',
        winningWeight: winner.totalConfidence,
        winningVotes: winner.count,
        totalResponses: responses.length,
        groups,
      }
    }

    case 'max_confidence': {
      // Pick the single response with the highest confidence
      const sorted = [...responses].sort((a, b) => b.confidence - a.confidence)
      const winner = sorted[0]
      return {
        selectedAnswer: winner.answer,
        selectionMethod: 'max_confidence',
        winningModel: winner.model,
        winningConfidence: winner.confidence,
        totalResponses: responses.length,
        groups,
      }
    }

    case 'average':
    default: {
      // Weighted average: pick group with highest avg confidence * sqrt(count)
      // Balances agreement (count) with quality (avg confidence)
      const scored = groups.map(g => ({
        ...g,
        avgConfidence: g.totalConfidence / g.count,
        compositeScore: (g.totalConfidence / g.count) * Math.sqrt(g.count),
      }))
      scored.sort((a, b) => b.compositeScore - a.compositeScore)
      const winner = scored[0]
      return {
        selectedAnswer: winner.answer,
        selectionMethod: 'weighted_average',
        winningAvgConfidence: winner.avgConfidence,
        winningCompositeScore: winner.compositeScore,
        winningVotes: winner.count,
        totalResponses: responses.length,
        groups: scored,
      }
    }
  }
}

// ---------------------------------------------------------------------------
// PHASE 1: Workers
// ---------------------------------------------------------------------------

// Track workflow execution start time
const workflowStartTime = Date.now()
const workflowExecutionId = `weighted_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

log('='.repeat(60))
log('WEIGHTED MULTI-AI CONSENSUS')
log('='.repeat(60))
log(`Task: ${task}`)
log(`Models: ${models.join(', ')}`)
log(`Strategy: ${weightStrategy}`)
if (minConfidenceThreshold > 0) {
  log(`Min confidence threshold: ${minConfidenceThreshold}`)
}
log('')

phase('Workers')

log(`${models.length} workers executing in parallel...`)

const workerPrompt = (model) => `You are ${model.toUpperCase()}, responding as part of a multi-model consensus process.

TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}
IMPORTANT INSTRUCTIONS:
1. Provide your best answer to the task.
2. Rate your confidence from 0 to 100:
   - 0-20: Very uncertain, mostly guessing
   - 21-40: Low confidence, significant uncertainty
   - 41-60: Moderate confidence, could go either way
   - 61-80: Fairly confident, minor uncertainties remain
   - 81-100: Highly confident, strong evidence/reasoning supports this
3. Be calibrated: do NOT default to high confidence. If you are unsure, say so.
4. List any caveats or limitations.

Return structured data per schema.`

const workerResults = await parallel(
  models.map(model => () => {
    try {
      return agent(workerPrompt(model), {
        label: `${model}-weighted-worker`,
        model,
        schema: workerSchema,
      })
    } catch (err) {
      log(`  WARNING: Worker ${model} threw: ${err.message || err}`)
      return null
    }
  })
)

// Pair results with model names, filter failures
const pairedResults = models
  .map((model, i) => {
    const result = workerResults[i]
    if (!result) return null
    return {
      model,
      answer: result.answer || null,
      confidence: clampConfidence(result.confidence),
      reasoning: result.reasoning || '',
      caveats: result.caveats || [],
    }
  })
  .filter(Boolean)

log(`${pairedResults.length}/${models.length} workers completed`)

if (pairedResults.length === 0) {
  log('ERROR: All workers failed')
  return {
    status: 'error',
    error: 'All workers failed to produce results',
    models_attempted: models,
  }
}

// Log individual worker results
pairedResults.forEach(r => {
  log(`  ${r.model}: confidence=${r.confidence}%`)
})

// Apply confidence threshold
let filteredResults = pairedResults.filter(r => r.confidence >= minConfidenceThreshold)

if (filteredResults.length === 0) {
  log(`WARNING: All workers fell below the confidence threshold of ${minConfidenceThreshold}`)
  log('Proceeding with all results despite low confidence')
  filteredResults = [...pairedResults]
}

const discardedCount = pairedResults.length - filteredResults.length
if (discardedCount > 0) {
  log(`  ${discardedCount} worker(s) discarded (below confidence threshold ${minConfidenceThreshold})`)
}

// ---------------------------------------------------------------------------
// PHASE 2: Weighting
// ---------------------------------------------------------------------------

phase('Weighting')

log('')
log('Computing weighted scores...')

const overallAvgConfidence = computeWeightedAverage(filteredResults)
const selection = selectByStrategy(filteredResults, weightStrategy)

log(`Strategy: ${selection.selectionMethod}`)
log(`Pre-synthesis selection: ${selection.winningVotes || 1} worker(s) agree`)
log(`Average confidence: ${overallAvgConfidence.toFixed(1)}%`)

// Detect agreement level
const agreementRatio = (selection.winningVotes || 1) / filteredResults.length
let agreementLevel
if (agreementRatio >= 0.9) agreementLevel = 'strong'
else if (agreementRatio >= 0.6) agreementLevel = 'moderate'
else if (agreementRatio >= 0.4) agreementLevel = 'weak'
else agreementLevel = 'no_consensus'

log(`Agreement level: ${agreementLevel} (${(agreementRatio * 100).toFixed(0)}%)`)

// ---------------------------------------------------------------------------
// PHASE 3: Synthesis
// ---------------------------------------------------------------------------

phase('Synthesis')

log('')
log('Arbiter synthesizing weighted consensus...')

const arbiterSchema = {
  type: 'object',
  properties: {
    synthesized_answer: userSchema,
    overall_confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Overall confidence in the synthesized answer (0-100)',
    },
    consensus_level: {
      type: 'string',
      enum: ['strong', 'moderate', 'weak', 'no_consensus'],
    },
    synthesis_notes: {
      type: 'string',
      description: 'How you combined/reconciled the worker responses',
    },
    key_agreements: {
      type: 'array',
      items: { type: 'string' },
      description: 'Points where workers agreed',
    },
    key_disagreements: {
      type: 'array',
      items: { type: 'string' },
      description: 'Points where workers disagreed',
    },
    per_model_assessment: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          model: { type: 'string' },
          contributed: { type: 'string', description: 'What this model contributed to the synthesis' },
          weight_applied: { type: 'number', description: 'Effective weight given (0-100)' },
        },
      },
    },
  },
  required: ['synthesized_answer', 'overall_confidence', 'consensus_level', 'synthesis_notes'],
}

const synthesis = await agent(`[ARBITER - WEIGHTED CONSENSUS SYNTHESIS]

You are synthesizing ${filteredResults.length} worker responses into a single best answer.
Each worker provided a confidence score. You must weight higher-confidence responses more heavily.

ORIGINAL TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}

WORKER RESPONSES (ordered by confidence, highest first):
${filteredResults
  .sort((a, b) => b.confidence - a.confidence)
  .map(r => `
--- ${r.model.toUpperCase()} (Confidence: ${r.confidence}%) ---
Answer: ${JSON.stringify(r.answer, null, 2)}
Reasoning: ${r.reasoning}
Caveats: ${r.caveats.length > 0 ? r.caveats.join('; ') : 'None'}
`).join('\n')}

PRE-SYNTHESIS ANALYSIS:
- Weight strategy used: ${selection.selectionMethod}
- Average confidence: ${overallAvgConfidence.toFixed(1)}%
- Agreement level: ${agreementLevel} (${(agreementRatio * 100).toFixed(0)}%)

INSTRUCTIONS:
${arbiterInstructions}

WEIGHTING RULES:
1. A worker with confidence 90 should influence the answer ~3x more than a worker with confidence 30.
2. If workers disagree, favor the higher-confidence response unless a lower-confidence worker raises a valid caveat.
3. If all workers agree but with varying confidence, synthesize a combined answer and set overall confidence near the weighted average.
4. If workers fundamentally disagree, acknowledge the disagreement and explain your resolution.

Provide your synthesis.`, {
  label: 'weighted-arbiter',
  model: 'opus',
  schema: arbiterSchema,
})

const overallConfidence = clampConfidence(synthesis.overall_confidence)

log(`Synthesis complete`)
log(`  Overall confidence: ${overallConfidence}%`)
log(`  Consensus level: ${synthesis.consensus_level}`)

// ---------------------------------------------------------------------------
// Final output
// ---------------------------------------------------------------------------

log('')
log('='.repeat(60))
log('WEIGHTED CONSENSUS RESULT')
log('='.repeat(60))
log('')
log(`Consensus level: ${(synthesis.consensus_level || agreementLevel).toUpperCase()}`)
log(`Overall confidence: ${overallConfidence}%`)
log(`Models: ${filteredResults.map(r => `${r.model}(${r.confidence}%)`).join(', ')}`)
log(`Strategy: ${weightStrategy}`)
log('')

if (synthesis.key_agreements && synthesis.key_agreements.length > 0) {
  log('Agreements:')
  synthesis.key_agreements.forEach((a, i) => log(`  ${i + 1}. ${a}`))
  log('')
}

if (synthesis.key_disagreements && synthesis.key_disagreements.length > 0) {
  log('Disagreements:')
  synthesis.key_disagreements.forEach((d, i) => log(`  ${i + 1}. ${d}`))
  log('')
}

log('Synthesis notes:')
log(`  ${synthesis.synthesis_notes}`)
log('')
log('='.repeat(60))

const finalResult = {
  status: 'success',
  task,
  weight_strategy: weightStrategy,
  consensus_level: synthesis.consensus_level || agreementLevel,
  overall_confidence: overallConfidence,
  result: synthesis.synthesized_answer,
  synthesis_notes: synthesis.synthesis_notes,
  agreements: synthesis.key_agreements || [],
  disagreements: synthesis.key_disagreements || [],
  per_model: synthesis.per_model_assessment || filteredResults.map(r => ({
    model: r.model,
    confidence: r.confidence,
    reasoning: r.reasoning,
  })),
  workers: {
    attempted: models.length,
    succeeded: pairedResults.length,
    passed_threshold: filteredResults.length,
    discarded: discardedCount,
    details: pairedResults.map(r => ({
      model: r.model,
      confidence: r.confidence,
      reasoning: r.reasoning,
      caveats: r.caveats,
    })),
  },
  weighting: {
    strategy: weightStrategy,
    selection: {
      method: selection.selectionMethod,
      winning_votes: selection.winningVotes || 1,
      total_responses: selection.totalResponses,
    },
    average_confidence: overallAvgConfidence,
    agreement_ratio: agreementRatio,
    agreement_level: agreementLevel,
    min_confidence_threshold: minConfidenceThreshold,
  },
}


// ============================================================================
// RECORD FEEDBACK TO LEARNING SYSTEM
// ============================================================================

// Use the workflow execution ID generated at the start
const executionId = workflowExecutionId

// Record feedback for each worker with their confidence scores
try {
  log('\n📊 Recording feedback to learning system...')

  // Send per-worker feedback entries
  for (const worker of filteredResults) {
    const feedbackPayload = {
      worker_id: `${worker.model}-weighted-worker`,
      model: worker.model,
      consensus_score: worker.confidence,
      confidence: worker.confidence,
      tokens_used: 0,
      cost_usd: 0.0,
      accepted: true,
      execution_id: executionId,
      reasoning: worker.reasoning,
      caveats: worker.caveats,
      outcome: 'success',
      workflow_type: 'ai-consensus-weighted',
      per_model_confidence: filteredResults.reduce((acc, r) => { acc[r.model] = r.confidence; return acc; }, {}),
      agreement_level: synthesis.consensus_level || agreementLevel
    }

    try {
      const token = process.env.LEARNING_API_TOKEN
      const authHeader = token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await fetch('http://localhost:8000/api/learning/record-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader
        },
        body: JSON.stringify(feedbackPayload)
      })

      if (response.ok) {
        const result = await response.json()
        log(`✅ Feedback recorded for ${worker.model} (confidence: ${worker.confidence}%)`)
      } else {
        log(`⚠️  Failed to record feedback for ${worker.model}: ${response.statusText}`)
      }
    } catch (err) {
      log(`⚠️  Feedback recording failed for ${worker.model}: ${err.message || err}`)
    }
  }
} catch (err) {
  log(`⚠️  Learning system unavailable: ${err.message || err}`)
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'ai-consensus-weighted',
    execution_data: finalResult,
  })
} catch (err) {
  log(`WARNING: Learning extraction failed: ${err.message || err}`)
}

// ============================================================================
// RECORD REACTION SIGNALS (behavioral analysis)
// ============================================================================

try {
  log('\nRecording reaction signals (behavioral analysis)...')

  // Build response objects for reaction tracker from worker results
  const reactionResponses = filteredResults.map(r => ({
    model: r.model,
    text: `${r.reasoning || ''}\n\nAnswer: ${JSON.stringify(r.answer, null, 2)}\n\nCaveats: ${(r.caveats || []).join('; ')}`,
    confidence: r.confidence,
  }))

  const reactionResult = await workflow('ai-reaction-tracker', {
    action: 'record',
    task: task,
    task_type: args.task_type || 'consensus',
    workflow: 'ai-consensus-weighted',
    responses: reactionResponses,
  })

  if (reactionResult && !reactionResult.error) {
    finalResult.reaction_signals = {
      record_id: reactionResult.record_id,
      aggregate: reactionResult.aggregate,
      disagreement: reactionResult.disagreement,
      calibration: reactionResult.calibration,
      learning_signals: reactionResult.learning_signals,
      task_assessment: reactionResult.task_assessment,
    }
    log(`Reaction signals recorded: ${reactionResult.learning_signals?.length || 0} learning signals derived`)
    log(`Task difficulty estimate: ${reactionResult.task_assessment?.difficulty || 'unknown'}`)
  }
} catch (err) {
  log(`WARNING: Reaction tracking failed: ${err.message || err}`)
}

// ============================================================================
// WORKFLOW STORAGE: Log execution to PostgreSQL
// ============================================================================

try {
  log('\n💾 Storing workflow execution to PostgreSQL...')

  const workflowDuration = Date.now() - workflowStartTime
  const totalTokens = filteredResults.reduce((sum, r) => sum + (r.tokens?.total || 0), 0)
  const totalCost = filteredResults.reduce((sum, r) => sum + (r.cost_usd || 0), 0)

  // Store main execution
  const dbExecutionId = await workflowStorage.storeExecution({
    workflow_id: workflowExecutionId,
    workflow_name: 'ai-consensus-weighted',
    task_description: task,
    total_workers: filteredResults.length,
    total_duration_ms: workflowDuration,
    outcome: finalResult.status === 'error' ? 'failed' : 'success',
    metadata: {
      context,
      weight_strategy: weightStrategy,
      min_confidence_threshold: minConfidenceThreshold,
      models_attempted: models,
      selection_method: synthesis.selectionMethod,
      consensus_level: synthesis.consensus_level,
      agreement_level: agreementLevel,
    }
  })

  // Store worker results
  for (const worker of filteredResults) {
    await workflowStorage.storeWorkerResult({
      workflow_execution_id: dbExecutionId,
      worker_id: `${worker.model}-weighted-worker`,
      model: worker.model,
      task_assigned: task,
      result: JSON.stringify({
        answer: worker.answer,
        reasoning: worker.reasoning,
        caveats: worker.caveats
      }),
      confidence: worker.confidence / 100, // Convert to 0.0-1.0 scale
      duration_ms: 0, // Not tracked per-worker currently
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      outcome: 'success',
      metadata: {
        raw_confidence: worker.confidence,
        caveats_count: worker.caveats?.length || 0
      }
    })
  }

  // Store arbiter decision
  await workflowStorage.storeArbiterDecision({
    workflow_execution_id: dbExecutionId,
    arbiter_model: synthesis.arbiterModel || 'opus',
    worker_result_ids: [], // Would need to track individual worker IDs
    decision: JSON.stringify(synthesis.answer),
    confidence: (synthesis.confidence || 80) / 100, // Convert to 0.0-1.0 scale
    reasoning: synthesis.reasoning || '',
    duration_ms: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    metadata: {
      selection_method: synthesis.selectionMethod,
      consensus_level: synthesis.consensus_level,
      weights_used: synthesis.weights
    }
  })

  log(`✅ Workflow execution stored (DB ID: ${dbExecutionId})`)
  finalResult.db_execution_id = dbExecutionId

} catch (err) {
  log(`⚠️  Workflow storage failed: ${err.message || err}`)
  log(`Stack: ${err.stack}`)
}

// Return with execution ID
finalResult.execution_id = executionId
return finalResult
