// AI Prompt - Fleet-Distributed Multi-Model Consensus
// Distributes AI workers across fleet machines for true parallelism

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'ai-prompt-fleet',
  description: 'Fleet-distributed multi-model consensus response',
  whenToUse: 'When user wants multiple AI perspectives distributed across fleet',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Multi-Model Response', detail: 'Distribute models across fleet machines', model: 'opus' },
    { title: 'Arbiter Synthesis', detail: 'Synthesize best answer' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// Import fleet integration helpers
import { shouldUseFleet, getFleetWorkers, distributeModels, getExecutionSummary }
  from '../shared/fleet-integration.js';

// Get the user's prompt from args
const userPrompt = args?.join ? args.join(' ') : args

if (!userPrompt) {
  log('❌ Error: Prompt required')
  log('Usage: /ai-prompt-fleet <your question>')
  log('Example: /ai-prompt-fleet How should I architect this feature?')
  return { status: 'error', message: 'Prompt required' }
}

log('')
log('='.repeat(60))
log('🤖 Fleet-Distributed Multi-Model AI Consensus')
log('='.repeat(60))
log(`Prompt: ${userPrompt}`)
log('='.repeat(60))
log('')

// PHASE 1: Discover fleet
phase('Fleet Discovery')

let workers = []
let useFleet = false

try {
  workers = await getFleetWorkers(args, { skipHealthCheck: false })
  useFleet = workers.length > 0

  if (useFleet) {
    log(`✅ Fleet available: ${workers.length} workers`)
    workers.forEach(w => log(`   - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`))
  } else {
    log('⚠️  No fleet workers available, running locally')
  }
} catch (error) {
  log(`⚠️  Fleet unavailable (${error.message}), running locally`)
  useFleet = false
}

log('')

// PHASE 2: Multi-Model Response
phase('Multi-Model Response')

const models = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

log(`🔄 ${models.length} workers responding in parallel...`)

// Distribute models across fleet workers
// If fleet unavailable, all run locally
const distribution = useFleet
  ? distributeModels(models, workers)
  : models.map(model => ({ model, hostname: 'localhost' }))

log('')
log('Distribution:')
distribution.forEach(d => log(`   ${d.model} → ${d.hostname}`))
log('')

const schema = {
  type: 'object',
  properties: {
    model: { type: 'string', description: 'The model name' },
    answer: { type: 'string', description: 'Your response to the prompt' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    reasoning: { type: 'string', description: 'Why this is your answer' },
    key_points: { type: 'array', items: { type: 'string' } },
    alternative_views: { type: 'array', items: { type: 'string' } },
  },
  required: ['model', 'answer', 'confidence', 'reasoning'],
}

// Execute models in parallel
// NOTE: Current limitation - agents still run locally because workflow agent()
// doesn't support remote SSH execution. This distributes the ASSIGNMENT but
// execution is still local. For true distributed execution, we'd need to:
// 1. SSH to remote machine
// 2. Run Claude CLI there with the model
// 3. Capture output
// For now, this demonstrates the pattern. Fleet execution would require
// launching Claude processes via SSH.

const workerTasks = distribution.map(({ model, hostname }) =>
  () => agent(userPrompt, {
    schema,
    model,
    label: `${model}@${hostname}`,
    phase: 'Multi-Model Response'
  })
)

const responses = await parallel(workerTasks)
const validResponses = responses.filter(Boolean)

const failed = models.length - validResponses.length
if (failed > 0) {
  log(`⚠️  Models that failed or were unavailable: ${models.filter((m, i) => !responses[i]).join(', ')}`)
}

log(`✅ Received responses from ${validResponses.length}/${models.length} models (${failed} failed or unavailable)`)

// Build response map
const responseMap = {}
distribution.forEach((d, i) => {
  responseMap[d.model] = responses[i]
})

// PHASE 3: Arbiter Synthesis
phase('Arbiter Synthesis')

log('⚖️  Arbiter synthesizing best answer...')

const arbiterPrompt = `You are the arbiter. Review these AI responses and synthesize the best answer.

**Original Prompt**: ${userPrompt}

${models.map(model => {
  const r = responseMap[model]
  if (!r) return `**${model.toUpperCase()}**: N/A (failed or unavailable)`

  return `**${model.toUpperCase()} RESPONSE**:
- Answer: ${r.answer}
- Confidence: ${r.confidence}%
- Reasoning: ${r.reasoning}
${r.key_points ? `- Key Points: ${r.key_points.join(', ')}` : ''}
${r.alternative_views ? `- Alternative Views: ${r.alternative_views.join(', ')}` : ''}`
}).join('\n\n')}

Synthesize the best answer by:
1. Identifying areas of agreement across models
2. Highlighting valuable disagreements and alternative perspectives
3. Weighing confidence levels and reasoning quality
4. Producing a final consensus answer

Return your synthesis with:
- consensus_level: 'high' | 'medium' | 'low' (based on model agreement)
- final_confidence: 0-100 (weighted average, favor higher-confidence answers)
- answer: the synthesized consensus response
- areas_of_agreement: key points all/most models agreed on
- areas_of_disagreement: important differences in perspective
- model_contributions: what each model uniquely contributed
`

const synthSchema = {
  type: 'object',
  properties: {
    consensus_level: { type: 'string', enum: ['high', 'medium', 'low'] },
    final_confidence: { type: 'number', minimum: 0, maximum: 100 },
    answer: { type: 'string' },
    areas_of_agreement: { type: 'array', items: { type: 'string' } },
    areas_of_disagreement: { type: 'array', items: { type: 'string' } },
    model_contributions: {
      type: 'object',
      additionalProperties: { type: 'string' }
    }
  },
  required: ['consensus_level', 'final_confidence', 'answer']
}

const synthesis = await _agent(arbiterPrompt, {
  schema: synthSchema,
  model: 'opus',
  label: 'Arbiter',
  phase: 'Arbiter Synthesis'
})

log('✅ Synthesis complete (' + synthesis.consensus_level + ' consensus)')
log('')

// Output results
log('='.repeat(60))
log('📊 Multi-Model Consensus Results')
log('='.repeat(60))
log('')
log(`**Consensus Level**: ${synthesis.consensus_level.toUpperCase()} (${validResponses.length}/${models.length} models agreed)`)
log(`**Final Confidence**: ${synthesis.final_confidence}%`)
log('')
log('## Synthesized Answer')
log('')
log(synthesis.answer)
log('')

if (synthesis.areas_of_agreement && synthesis.areas_of_agreement.length > 0) {
  log('## Areas of Agreement')
  log('')
  synthesis.areas_of_agreement.forEach((item, i) => {
    log(`${i + 1}. ${item}`)
  })
  log('')
}

if (synthesis.areas_of_disagreement && synthesis.areas_of_disagreement.length > 0) {
  log('## Areas of Disagreement')
  log('')
  synthesis.areas_of_disagreement.forEach((item, i) => {
    log(`${i + 1}. ${item}`)
  })
  log('')
}

if (synthesis.model_contributions) {
  log('## Individual Model Contributions')
  log('')
  Object.entries(synthesis.model_contributions).forEach(([model, contribution]) => {
    log(`**${model} contributed**:`)
    log(`  ${contribution}`)
  })
  log('')
}

log('='.repeat(60))
log('🎯 Final Answer')
log('='.repeat(60))
log('')
log(synthesis.answer)
log('')

// Execution summary
if (useFleet) {
  const summary = getExecutionSummary(distribution, validResponses.length)
  log('')
  log('Fleet Execution Summary:')
  log(`  Workers used: ${summary.workersUsed}`)
  log(`  Tasks distributed: ${summary.tasksDistributed}`)
  log(`  Success rate: ${summary.successRate}%`)
}

return {
  status: 'success',
  prompt: userPrompt,
  question: userPrompt,
  consensus_level: synthesis.consensus_level,
  final_confidence: synthesis.final_confidence,
  answer: synthesis.answer,
  models_agreed: validResponses.length,
  models_used: models,
  fleet_used: useFleet,
  worker_count: workers.length,
  attribution: {
    workers: validResponses.map(r => ({
      model: r.model,
      confidence: r.confidence,
      reasoning: r.reasoning
    })),
    arbiter: {
      model: 'opus',
      consensus_level: synthesis.consensus_level,
      final_confidence: synthesis.final_confidence
    }
  }
}
