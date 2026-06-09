export const meta = {
  name: 'ai-consensus',
  description: 'Multi-AI consensus helper - run any task with opus/sonnet/haiku workers + arbiter',
  whenToUse: 'Internal helper for multi-AI consensus pattern',
  phases: [
    { title: 'Workers', detail: 'Parallel opus/sonnet/haiku execution' },
    { title: 'Arbiter', detail: 'Synthesize best answer' },
  ],
}

// USAGE:
// const result = await workflow('ai-consensus', {
//   task: 'Analyze this code for bugs',
//   context: '<code here>',
//   schema: { type: 'object', properties: { ... } },
//   arbiter_instructions: 'Select the most thorough analysis'
// })

const task = args.task || args
const context = args.context || ''
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
  log('Usage: workflow("ai-consensus", { task: "...", context: "...", schema: {...} })')
  return { error: 'No task provided' }
}

log('═'.repeat(60))
log('🤖 MULTI-AI CONSENSUS')
log('═'.repeat(60))
log(`Task: ${task}`)
log('')

// PHASE 1: Workers execute in parallel
phase('Workers')

log('📝 Workers executing (opus/sonnet/haiku)...')

const workerPrompt = (model) => `[${model.toUpperCase()}] ${task}

${context ? `Context:\n${context}\n\n` : ''}

Return structured data per schema.`

const workers = await parallel([
  () => agent(workerPrompt('opus'), {
    label: 'opus-worker',
    model: 'opus',
    schema
  }),

  () => agent(workerPrompt('sonnet'), {
    label: 'sonnet-worker',
    model: 'sonnet',
    schema
  }),

  () => agent(workerPrompt('haiku'), {
    label: 'haiku-worker',
    model: 'haiku',
    schema
  }),
])

const validWorkers = workers.filter(Boolean)
log(`✅ ${validWorkers.length}/3 workers completed`)

if (validWorkers.length === 0) {
  log('❌ All workers failed')
  return { error: 'All workers failed', workers: [] }
}

// PHASE 2: Arbiter synthesis
phase('Arbiter')

log('')
log('⚖️  Arbiter synthesizing best answer...')

const arbiterSchema = {
  type: 'object',
  properties: {
    winning_worker: { type: 'string' },
    why_selected: { type: 'string' },
    confidence: { type: 'number' },
    synthesis: schema
  }
}

const synthesis = await agent(`[ARBITER] Review ${validWorkers.length} worker responses and synthesize the best answer.

Task: ${task}

Worker Responses:
${validWorkers.map((w, i) => `
Worker ${i + 1} (${w.model || 'unknown'}):
${JSON.stringify(w, null, 2)}
`).join('\n')}

Instructions:
${arbiterInstructions}

Return:
1. winning_worker: Which model produced the best answer
2. why_selected: Why this answer is best
3. confidence: 0-100 rating
4. synthesis: The best answer (or synthesized combination)

`, {
  label: 'arbiter',
  schema: arbiterSchema
})

log(`✅ Winner: ${synthesis.winning_worker}`)
log(`   Confidence: ${synthesis.confidence}%`)
log(`   Reason: ${synthesis.why_selected}`)

log('')
log('═'.repeat(60))
log('✅ CONSENSUS REACHED')
log('═'.repeat(60))

return {
  status: 'success',
  winner: synthesis.winning_worker,
  confidence: synthesis.confidence,
  result: synthesis.synthesis,
  all_workers: validWorkers
}
