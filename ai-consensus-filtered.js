export const meta = {
  name: 'ai-consensus-filtered',
  description: 'Multi-AI consensus with confidence filtering - only synthesize from high-confidence results',
  whenToUse: 'When you need consensus but want to filter out low-confidence responses',
  phases: [
    { title: 'Workers', detail: 'Parallel opus/sonnet/haiku execution with confidence scoring' },
    { title: 'Filter', detail: 'Remove results below threshold' },
    { title: 'Arbiter', detail: 'Synthesize from high-confidence results only' },
  ],
}

// USAGE:
// const result = await workflow('ai-consensus-filtered', {
//   task: 'Analyze this code for bugs',
//   context: '<code here>',
//   confidence_threshold: 70,  // default 70, filter out results below this
//   schema: { type: 'object', properties: { ... } },
//   arbiter_instructions: 'Select the most thorough analysis'
// })

const task = args.task || args
const context = args.context || ''
const confidenceThreshold = args.confidence_threshold || 70
const schema = args.schema || {
  type: 'object',
  properties: {
    model: { type: 'string' },
    answer: { type: 'string' }
  }
}
const arbiterInstructions = args.arbiter_instructions || 'Select the best answer with highest quality and accuracy'

if (!task) {
  log('❌ No task provided')
  log('Usage: workflow("ai-consensus-filtered", { task: "...", context: "...", confidence_threshold: 70, schema: {...} })')
  return { error: 'No task provided' }
}

log('═'.repeat(60))
log('🤖 MULTI-AI CONSENSUS WITH CONFIDENCE FILTERING')
log('═'.repeat(60))
log(`Task: ${task}`)
log(`Confidence Threshold: ${confidenceThreshold}%`)
log('')

// Get next arbiter for rotation
const arbiterState = await workflow('get-next-arbiter')
const arbiterModel = arbiterState.arbiter
log(`🎯 Arbiter: ${arbiterModel}`)
log('')

// PHASE 1: Workers execute in parallel with self-assessment
phase('Workers')

log('📝 Workers executing (fable/opus/sonnet/haiku/gpt-4o/gemini) with confidence scoring...')

// Enhanced schema to include confidence
const workerSchema = {
  type: 'object',
  properties: {
    ...schema.properties,
    confidence: { type: 'number', description: 'Your confidence in this answer (0-100)' },
    reasoning: { type: 'string', description: 'Why you assigned this confidence level' }
  },
  required: [...(schema.required || []), 'confidence', 'reasoning']
}

const workerPrompt = (model) => `[${model.toUpperCase()}] ${task}

${context ? `Context:\n${context}\n\n` : ''}

IMPORTANT: You must assess your own confidence in your answer.
- Provide a confidence score (0-100) based on:
  * Clarity of the question
  * Quality of available information
  * Certainty of your analysis
  * Complexity of the task
- Explain your confidence reasoning

Return structured data per schema including confidence and reasoning.`

const workers = await parallel([
  () => agent(workerPrompt('fable'), {
    label: 'fable-worker',
    model: 'fable',
    schema: workerSchema
  }),

  () => agent(workerPrompt('opus'), {
    label: 'opus-worker',
    model: 'opus',
    schema: workerSchema
  }),

  () => agent(workerPrompt('sonnet'), {
    label: 'sonnet-worker',
    model: 'sonnet',
    schema: workerSchema
  }),

  () => agent(workerPrompt('haiku'), {
    label: 'haiku-worker',
    model: 'haiku',
    schema: workerSchema
  }),

  () => agent(workerPrompt('gpt-4o'), {
    label: 'gpt-4o-worker',
    model: 'gpt-4o',
    schema: workerSchema
  }),

  () => agent(workerPrompt('gemini'), {
    label: 'gemini-worker',
    model: 'gemini',
    schema: workerSchema
  }),
])

const validWorkers = workers.filter(Boolean)
log(`✅ ${validWorkers.length}/6 workers completed`)

if (validWorkers.length === 0) {
  log('❌ All workers failed')
  return { error: 'All workers failed', workers: [], filtered_count: 0 }
}

// Log all worker confidences
log('')
log('Worker Confidence Scores:')
validWorkers.forEach((w, i) => {
  const model = w.model || `worker-${i + 1}`
  const confidence = w.confidence || 0
  const status = confidence >= confidenceThreshold ? '✅' : '❌'
  log(`  ${status} ${model}: ${confidence}% - ${w.reasoning || 'no reasoning provided'}`)
})

// PHASE 2: Filter by confidence threshold
phase('Filter')

const highConfidenceWorkers = validWorkers.filter(w =>
  (w.confidence || 0) >= confidenceThreshold
)

const filteredCount = validWorkers.length - highConfidenceWorkers.length

log('')
log(`🔍 Filtering results (threshold: ${confidenceThreshold}%)`)
log(`   High-confidence: ${highConfidenceWorkers.length}`)
log(`   Filtered out: ${filteredCount}`)

if (highConfidenceWorkers.length === 0) {
  log('')
  log('⚠️  WARNING: All results below confidence threshold!')
  log(`   Threshold: ${confidenceThreshold}%`)
  log(`   Highest confidence: ${Math.max(...validWorkers.map(w => w.confidence || 0))}%`)
  log('')
  log('Recommendation: Lower the confidence_threshold or review the task clarity')

  return {
    status: 'insufficient_confidence',
    error: 'All results below confidence threshold',
    threshold: confidenceThreshold,
    highest_confidence: Math.max(...validWorkers.map(w => w.confidence || 0)),
    all_workers: validWorkers,
    filtered_count: filteredCount,
    recommendation: 'Lower threshold or improve task clarity'
  }
}

if (highConfidenceWorkers.length === 1) {
  log('')
  log('⚠️  WARNING: Only 1 result passed threshold')
  log('   Consensus may be limited with single high-confidence result')
}

// PHASE 3: Arbiter synthesis from high-confidence results only
phase('Arbiter')

log('')
log(`⚖️  Arbiter (${arbiterModel}) synthesizing from ${highConfidenceWorkers.length} high-confidence results...`)

const arbiterSchema = {
  type: 'object',
  properties: {
    winning_worker: { type: 'string' },
    why_selected: { type: 'string' },
    confidence: { type: 'number' },
    synthesis: schema
  }
}

const synthesis = await agent(`[ARBITER - ${arbiterModel.toUpperCase()}] Review ${highConfidenceWorkers.length} high-confidence worker responses and synthesize the best answer.

NOTE: These results have been pre-filtered to only include responses with confidence >= ${confidenceThreshold}%.

Task: ${task}

High-Confidence Worker Responses:
${highConfidenceWorkers.map((w, i) => `
Worker ${i + 1} (${w.model || 'unknown'}):
Confidence: ${w.confidence}%
Reasoning: ${w.reasoning}
Response:
${JSON.stringify(w, null, 2)}
`).join('\n')}

${filteredCount > 0 ? `
Filtered Out (${filteredCount} low-confidence responses):
${validWorkers.filter(w => (w.confidence || 0) < confidenceThreshold).map(w =>
  `- ${w.model || 'unknown'}: ${w.confidence}% (${w.reasoning})`
).join('\n')}
` : ''}

Instructions:
${arbiterInstructions}

Return:
1. winning_worker: Which model produced the best answer
2. why_selected: Why this answer is best
3. confidence: 0-100 rating for the final synthesis
4. synthesis: The best answer (or synthesized combination)

`, {
  label: 'arbiter',
  model: arbiterModel,
  schema: arbiterSchema
})

log(`✅ Winner: ${synthesis.winning_worker}`)
log(`   Confidence: ${synthesis.confidence}%`)
log(`   Reason: ${synthesis.why_selected}`)

log('')
log('═'.repeat(60))
log('✅ FILTERED CONSENSUS REACHED')
log('═'.repeat(60))
log(`   Used: ${highConfidenceWorkers.length}/${validWorkers.length} results`)
log(`   Filtered: ${filteredCount} results`)
log('')

// Update arbiter state for rotation
await workflow('update-arbiter-state', { arbiter: arbiterModel })

return {
  status: 'success',
  arbiter: arbiterModel,
  winner: synthesis.winning_worker,
  confidence: synthesis.confidence,
  result: synthesis.synthesis,
  filter_stats: {
    total_workers: validWorkers.length,
    high_confidence_count: highConfidenceWorkers.length,
    filtered_count: filteredCount,
    threshold: confidenceThreshold
  },
  high_confidence_workers: highConfidenceWorkers,
  filtered_workers: validWorkers.filter(w => (w.confidence || 0) < confidenceThreshold),
  all_workers: validWorkers
}
