// AI Prompt - Multi-Model Consensus for Any Prompt
// FIXED: Removed imports, added inline consensus logic

const meta = {
  name: 'ai-prompt',
  description: 'Multi-model consensus response to any prompt',
  whenToUse: 'When user wants multiple AI perspectives on a question',
  phases: [
    { title: 'Multi-Model Response', detail: 'Opus, Sonnet, Haiku respond independently', model: 'opus' },
    { title: 'Arbiter Synthesis', detail: 'Synthesize best answer' },
  ],
}

// INLINE CONSENSUS ENGINE (simplified for ai-prompt use case)
async function multiModelReview(prompt, schema, options = {}) {
  const { workers = ['opus', 'sonnet', 'haiku'], phase = 'Multi-Model Response', labelPrefix = 'Response' } = options

  log(`🔄 ${workers.length} workers responding in parallel...`)

  const workerTasks = workers.map(model =>
    () => agent(prompt, {
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
    answer: { type: 'string', description: 'Your response to the prompt' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    reasoning: { type: 'string', description: 'Why this is your answer' },
    key_points: { type: 'array', items: { type: 'string' } },
    alternative_views: { type: 'array', items: { type: 'string' } },
  },
  required: ['answer', 'confidence', 'reasoning'],
}

const responses = await multiModelReview(userPrompt, schema, {
  phase: 'Multi-Model Response',
  labelPrefix: 'Response',
})

log(`✅ Received responses from ${responses.allReviews.length} models`)

// PHASE 2: Arbiter synthesizes best answer
phase('Arbiter Synthesis')

log('⚖️  Arbiter synthesizing best answer...')

const synthesis = await agent(`You are the arbiter. Review these AI responses and synthesize the best answer:

**Original Prompt**: ${userPrompt}

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

Synthesize the best answer by:
1. Identifying areas of agreement
2. Incorporating the strongest points from each model
3. Resolving any disagreements
4. Providing a unified, comprehensive answer
5. Explaining which models contributed what

Provide your synthesis.`, {
  label: 'Arbiter Synthesis',
  phase: 'Arbiter Synthesis',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      synthesized_answer: { type: 'string' },
      consensus_level: { type: 'string', enum: ['high', 'medium', 'low'] },
      models_agreed: { type: 'number', description: 'How many models agreed (0-3)' },
      best_points_from: {
        type: 'object',
        properties: {
          opus: { type: 'array', items: { type: 'string' } },
          sonnet: { type: 'array', items: { type: 'string' } },
          haiku: { type: 'array', items: { type: 'string' } },
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

log(`**Consensus Level**: ${synthesis.consensus_level.toUpperCase()} (${synthesis.models_agreed || 0}/3 models agreed)`)
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

if (synthesis.best_points_from?.opus && synthesis.best_points_from.opus.length > 0) {
  log('**Opus contributed**:')
  synthesis.best_points_from.opus.forEach(point => log(`  - ${point}`))
}

if (synthesis.best_points_from?.sonnet && synthesis.best_points_from.sonnet.length > 0) {
  log('**Sonnet contributed**:')
  synthesis.best_points_from.sonnet.forEach(point => log(`  - ${point}`))
}

if (synthesis.best_points_from?.haiku && synthesis.best_points_from.haiku.length > 0) {
  log('**Haiku contributed**:')
  synthesis.best_points_from.haiku.forEach(point => log(`  - ${point}`))
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
