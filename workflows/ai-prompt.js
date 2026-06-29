// AI Prompt - Multi-Model Consensus for Any Prompt
// PHASE 3: Fleet remote execution via fleet-agent-wrapper.js (dynamic import)
// MODEL COMPLIANCE: Auto-filters workers/arbiters based on path restrictions

export const meta = {
  name: 'ai-prompt',
  description: 'Multi-model consensus response to any prompt',
  whenToUse: 'When user wants multiple AI perspectives on a question',
  phases: [
    { title: 'Multi-Model Response', detail: 'Compliance-filtered workers (Claude, Gemini, Ollama - no OpenAI in Red Hat paths)', model: 'opus' },
    { title: 'Arbiter Synthesis', detail: 'Synthesize best answer' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// === PHASE 3 FLEET INTEGRATION ===
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}
// === END PHASE 3 FLEET INTEGRATION ===

// === MODEL COMPLIANCE ===
let modelCompliance;
try {
  modelCompliance = await import('../shared/model-compliance.js');
} catch (e) {
  // Fallback: no filtering if module unavailable
  modelCompliance = {
    filterAllowedModels: (models) => models,
    getCompliantArbiter: (arbiter) => arbiter,
    getActiveRestriction: () => null
  };
}
// === END MODEL COMPLIANCE ===


// INLINE CONSENSUS ENGINE (simplified for ai-prompt use case)
async function multiModelReview(prompt, schema, options = {}) {
  // Apply model compliance filtering to workers
  const defaultWorkers = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
  const filteredWorkers = modelCompliance.filterAllowedModels(options.workers || defaultWorkers);

  const { workers = filteredWorkers, phase = 'Multi-Model Response', labelPrefix = 'Response' } = { ...options, workers: filteredWorkers }

  // Log restriction if active
  const restriction = modelCompliance.getActiveRestriction();
  if (restriction) {
    log(`🔒 Model restrictions active: ${restriction.reason}`);
    log(`📋 Using ${workers.length} compliant workers: ${workers.join(', ')}`);
  }

  log(`🔄 ${workers.length} workers responding in parallel...`)

  const workerTasks = workers.map(model =>
    () => _agent(prompt, {
      schema,
      model,
      label: `${labelPrefix} (${model})`,
      phase
    })
  )

  const reviews = await parallel(workerTasks)

  const result = { allReviews: reviews.filter(Boolean) }
  workers.forEach((model, i) => {
    result[model] = reviews[i]
  })
  result.opus = result.opus || null
  result.sonnet = result.sonnet || null
  result.haiku = result.haiku || null
  result.gemini = result.gemini || null

  return result
}

// Get the user's prompt from args
const userPrompt = args?.join ? args.join(' ') : args

if (!userPrompt) {
  log('❌ Error: Prompt required')
  log('Usage: /ai-prompt <your question>')
  log('Example: /ai-prompt How should I architect this feature?')
  return { status: 'error', message: 'Prompt required' }
}

log('')
log('='.repeat(60))
log('🤖 Multi-Model AI Consensus')
log('='.repeat(60))
log(`Prompt: ${userPrompt}`)
log('='.repeat(60))
log('')

// PHASE 1: Get responses from multiple models
phase('Multi-Model Response')

const schema = {
  type: 'object',
  properties: {
    model: { type: 'string', description: 'The model name (opus/sonnet/haiku/gemini)' },
    answer: { type: 'string', description: 'Your response to the prompt' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    reasoning: { type: 'string', description: 'Why this is your answer' },
    key_points: { type: 'array', items: { type: 'string' } },
    alternative_views: { type: 'array', items: { type: 'string' } },
  },
  required: ['model', 'answer', 'confidence', 'reasoning'],
}

const responses = await multiModelReview(userPrompt, schema, {
  phase: 'Multi-Model Response',
  labelPrefix: 'Response',
})

log(`✅ Received responses from ${responses.allReviews.length} models`)

// PHASE 2: Arbiter synthesizes best answer
phase('Arbiter Synthesis')

// Get compliant arbiter model
const arbiterModel = modelCompliance.getCompliantArbiter('opus', ['opus', 'sonnet', 'haiku']);

log('⚖️  Arbiter synthesizing best answer...')

const synthesis = await _agent(`You are the arbiter. Review these AI responses and synthesize the best answer:

**Original Prompt**: ${userPrompt}

**FABLE RESPONSE**:
- Answer: ${responses.fable?.answer || 'N/A'}
- Confidence: ${responses.fable?.confidence || 0}%
- Reasoning: ${responses.fable?.reasoning || 'N/A'}
${responses.fable?.key_points ? `- Key Points: ${responses.fable.key_points.join(', ')}` : ''}

**OPUS RESPONSE**:
- Answer: ${responses.opus?.answer || 'N/A'}
- Confidence: ${responses.opus?.confidence || 0}%
- Reasoning: ${responses.opus?.reasoning || 'N/A'}
${responses.opus?.key_points ? `- Key Points: ${responses.opus.key_points.join(', ')}` : ''}

**SONNET RESPONSE**:
- Answer: ${responses.sonnet?.answer || 'N/A'}
- Confidence: ${responses.sonnet?.confidence || 0}%
- Reasoning: ${responses.sonnet?.reasoning || 'N/A'}
${responses.sonnet?.key_points ? `- Key Points: ${responses.sonnet.key_points.join(', ')}` : ''}

**HAIKU RESPONSE**:
- Answer: ${responses.haiku?.answer || 'N/A'}
- Confidence: ${responses.haiku?.confidence || 0}%
- Reasoning: ${responses.haiku?.reasoning || 'N/A'}
${responses.haiku?.key_points ? `- Key Points: ${responses.haiku.key_points.join(', ')}` : ''}

**GPT-4O RESPONSE**:
- Answer: ${responses['gpt-4o']?.answer || 'N/A'}
- Confidence: ${responses['gpt-4o']?.confidence || 0}%
- Reasoning: ${responses['gpt-4o']?.reasoning || 'N/A'}
${responses['gpt-4o']?.key_points ? `- Key Points: ${responses['gpt-4o'].key_points.join(', ')}` : ''}

**GEMINI RESPONSE**:
- Answer: ${responses.gemini?.answer || 'N/A'}
- Confidence: ${responses.gemini?.confidence || 0}%
- Reasoning: ${responses.gemini?.reasoning || 'N/A'}
${responses.gemini?.key_points ? `- Key Points: ${responses.gemini.key_points.join(', ')}` : ''}

Synthesize the best answer by:
1. Identifying areas of agreement
2. Incorporating the strongest points from each model
3. Resolving any disagreements
4. Providing a unified, comprehensive answer
5. Explaining which models contributed what

Provide your synthesis.`, {
  label: 'Arbiter Synthesis',
  phase: 'Arbiter Synthesis',
  model: arbiterModel,
  schema: {
    type: 'object',
    properties: {
      synthesized_answer: { type: 'string' },
      consensus_level: { type: 'string', enum: ['high', 'medium', 'low'] },
      models_agreed: { type: 'number', description: 'How many models agreed (0-6)' },
      best_points_from: {
        type: 'object',
        properties: {
          fable: { type: 'array', items: { type: 'string' } },
          opus: { type: 'array', items: { type: 'string' } },
          sonnet: { type: 'array', items: { type: 'string' } },
          haiku: { type: 'array', items: { type: 'string' } },
          'gpt-4o': { type: 'array', items: { type: 'string' } },
          gemini: { type: 'array', items: { type: 'string' } },
        }
      },
      areas_of_agreement: { type: 'array', items: { type: 'string' } },
      areas_of_disagreement: { type: 'array', items: { type: 'string' } },
      final_confidence: { type: 'number', minimum: 0, maximum: 100 },
    },
    required: ['synthesized_answer', 'consensus_level', 'final_confidence'],
  }
})

log(`✅ Synthesis complete (${synthesis.consensus_level} consensus)`)

// Display results
log('')
log('='.repeat(60))
log('📊 Multi-Model Consensus Results')
log('='.repeat(60))
log('')

log(`**Consensus Level**: ${synthesis.consensus_level.toUpperCase()} (${synthesis.models_agreed || 0}/6 models agreed)`)
log(`**Final Confidence**: ${synthesis.final_confidence}%`)
log('')

log('## Synthesized Answer')
log('')
log(synthesis.synthesized_answer)
log('')

if (synthesis.areas_of_agreement && synthesis.areas_of_agreement.length > 0) {
  log('## Areas of Agreement')
  log('')
  synthesis.areas_of_agreement.forEach((area, i) => {
    log(`${i + 1}. ${area}`)
  })
  log('')
}

if (synthesis.areas_of_disagreement && synthesis.areas_of_disagreement.length > 0) {
  log('## Areas of Disagreement')
  log('')
  synthesis.areas_of_disagreement.forEach((area, i) => {
    log(`${i + 1}. ${area}`)
  })
  log('')
}

log('## Individual Model Contributions')
log('')

const modelNames = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
for (const modelName of modelNames) {
  const points = synthesis.best_points_from?.[modelName]
  if (points && points.length > 0) {
    log(`**${modelName.charAt(0).toUpperCase() + modelName.slice(1)} contributed**:`)
    points.forEach(point => log(`  - ${point}`))
  }
}

log('')
log('='.repeat(60))
log('🎯 Final Answer')
log('='.repeat(60))
log('')
log(synthesis.synthesized_answer)
log('')

return {
  status: 'success',
  prompt: userPrompt,
  consensus_level: synthesis.consensus_level,
  final_confidence: synthesis.final_confidence,
  answer: synthesis.synthesized_answer,
  models_agreed: synthesis.models_agreed || 0,
  attribution: {
    workers: responses.allReviews.map(r => ({
      model: r.model || 'unknown',
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

}
