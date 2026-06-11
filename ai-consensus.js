export const meta = {
  name: 'ai-consensus',
  description: 'Multi-AI consensus helper - run any task with opus/sonnet/haiku workers + arbiter',
  whenToUse: 'Internal helper for multi-AI consensus pattern',
  phases: [
    { title: 'Get Arbiter', detail: 'Determine next arbiter via rotation' },
    { title: 'Workers', detail: 'Parallel opus/sonnet/haiku execution' },
    { title: 'Arbiter', detail: 'Synthesize best answer' },
    { title: 'Update State', detail: 'Record arbiter usage for rotation' },
  ],
}

// USAGE:
// const result = await workflow('ai-consensus', {
//   task: 'Analyze this code for bugs',
//   context: '<code here>',
//   schema: { type: 'object', properties: { ... } },
//   arbiter_instructions: 'Select the most thorough analysis'
// })

// ============================================================================
// LOCAL MODELS CONFIG LOADING
// ============================================================================

function loadLocalModelsConfig() {
  try {
    const fs = require('fs')
    const configPath = '/home/sfloess/.claude/repos/claude-global-skills/local-models-config.json'
    const configContent = fs.readFileSync(configPath, 'utf-8')
    const config = JSON.parse(configContent)
    return config
  } catch (error) {
    return {
      enabled: false,
      models: {},
      fallbackToClaude: true
    }
  }
}

// ============================================================================
// GET WORKER MODELS
// ============================================================================

function getWorkerModels() {
  const localConfig = loadLocalModelsConfig()
  const workers = []

  // Base models - always use
  workers.push('opus', 'sonnet', 'haiku')

  // Add local Ollama models if enabled
  if (localConfig.enabled && localConfig.models) {
    const ollamaModels = Object.values(localConfig.models).filter(m => typeof m === 'string')
    if (ollamaModels.length > 0) {
      workers.push(...ollamaModels)
      log(`Added ${ollamaModels.length} local Ollama models: ${ollamaModels.join(', ')}`)
    }
  }

  return workers
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

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
  log('No task provided')
  log('Usage: workflow("ai-consensus", { task: "...", context: "...", schema: {...} })')
  return { error: 'No task provided' }
}

log('='.repeat(60))
log('MULTI-AI CONSENSUS')
log('='.repeat(60))
log(`Task: ${task}`)
log('')

// PHASE 0: Get next arbiter from rotation
phase('Get Arbiter')

const arbiterChoice = await workflow('get-next-arbiter')
log(`Arbiter for this run: ${arbiterChoice.arbiter} (previous: ${arbiterChoice.previous || 'none'})`)

// PHASE 1: Workers execute in parallel
phase('Workers')

// Get worker models (includes local Ollama models if enabled)
const workerModels = getWorkerModels()
log(`Workers executing (${workerModels.join(', ')})...`)

const workerPrompt = (model) => `[${model.toUpperCase()}] ${task}

${context ? `Context:\n${context}\n\n` : ''}

Return structured data per schema.`

// Build worker tasks dynamically based on available models
const workerTasks = workerModels.map(model =>
  () => agent(workerPrompt(model), {
    label: `${model}-worker`,
    model: model,
    schema
  })
)

const workers = await parallel(workerTasks)

const validWorkers = workers.filter(Boolean)
log(`${validWorkers.length}/${workerTasks.length} workers completed`)

if (validWorkers.length === 0) {
  log('All workers failed')
  return { error: 'All workers failed', workers: [] }
}

// PHASE 2: Arbiter synthesis
phase('Arbiter')

log('')
log(`Arbiter (${arbiterChoice.arbiter}) synthesizing best answer...`)

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
  model: arbiterChoice.arbiter,
  schema: arbiterSchema
})

log(`Winner: ${synthesis.winning_worker}`)
log(`   Confidence: ${synthesis.confidence}%`)
log(`   Reason: ${synthesis.why_selected}`)

log('')

// PHASE 3: Update arbiter state for rotation tracking
phase('Update State')

await workflow('update-arbiter-state', { arbiter: arbiterChoice.arbiter, workflow_name: 'ai-consensus' })

// ============================================================================
// RECORD FEEDBACK TO LEARNING SYSTEM
// ============================================================================

// Generate execution ID (unique per run)
const executionId = `consensus_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

// Record feedback for all workers
try {
  log('\nRecording feedback to learning system...')

  // Loop over all valid workers, marking winner vs non-winners
  for (const worker of validWorkers) {
    const isWinner = worker.model === synthesis.winning_worker

    const feedbackPayload = {
      worker_id: `${worker.model}-worker`,
      model: worker.model,
      consensus_score: synthesis.confidence,
      tokens_used: 0,
      cost_usd: 0.0,
      accepted: isWinner,
      execution_id: executionId,
      reasoning: isWinner ? synthesis.why_selected : `Non-winning response in consensus`,
      outcome: 'success',
      workflow_type: 'ai-consensus'
    }

    try {
      const response = await fetch('http://localhost:8000/api/learning/record-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer sk-test'
        },
        body: JSON.stringify(feedbackPayload)
      })

      if (response.ok) {
        const result = await response.json()
        log(`Feedback recorded for ${worker.model}: ${isWinner ? 'winner' : 'non-winner'}`)
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

return {
  status: 'success',
  winner: synthesis.winning_worker,
  confidence: synthesis.confidence,
  result: synthesis.synthesis,
  all_workers: validWorkers,
  execution_id: executionId
}
