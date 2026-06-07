export const meta = {
  name: 'ai-prompt',
  description: 'Multi-model consensus response to any prompt',
  whenToUse: 'When user wants multiple AI perspectives on a question',
  phases: [
    { title: 'Multi-Model Response', detail: 'Opus, Sonnet, Haiku respond independently', model: 'opus' },
    { title: 'Arbiter Synthesis', detail: 'Synthesize best answer' },
  ],
}

// ============================================================================
// DYNAMIC MODEL DETECTION
// ============================================================================

function getAvailableWorkers(customWorkers = null) {
  // Allow override via args or parameter
  if (customWorkers && Array.isArray(customWorkers)) {
    return customWorkers
  }

  // Define available models
  // Note: Models that fail at runtime will return null from agent() calls
  // and be filtered out by .filter(Boolean) in parallel operations

  const models = []

  // Base Claude models - always available
  models.push('opus', 'sonnet', 'haiku')

  // Gemini (via MCP or Google AI API)
  models.push('gemini')

  // Grok (via xAI API) - uncomment when configured
  // models.push('grok')

  // Ollama (local models) - uncomment when running locally
  // models.push('ollama/llama3', 'ollama/codestral', 'ollama/deepseek-coder')

  // OpenAI (via MCP) - uncomment when configured
  // models.push('gpt-4', 'gpt-4-turbo')

  // Anthropic models via Bedrock - uncomment when configured
  // models.push('bedrock/claude-opus', 'bedrock/claude-sonnet')

  return models
}

// ============================================================================
// INLINE CONSENSUS ENGINE (simplified for ai-prompt use case)
// ============================================================================

async function multiModelReview(prompt, schema, options = {}) {
  const { workers = getAvailableWorkers(), phase = 'Multi-Model Response', labelPrefix = 'Response' } = options

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

  // Ensure all possible models are in result (null if not used)
  const allPossibleModels = ['opus', 'sonnet', 'haiku', 'gemini', 'grok']
  allPossibleModels.forEach(model => {
    if (!(model in result)) {
      result[model] = null
    }
  })

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

// Build dynamic response summary for arbiter
const responsesSummary = responses.allReviews.map((review, idx) => {
  const modelName = Object.keys(responses).find(key => responses[key] === review) || `model-${idx}`
  return `**${modelName.toUpperCase()} RESPONSE**:
- Answer: ${review?.answer || 'N/A'}
- Confidence: ${review?.confidence || 0}%
- Reasoning: ${review?.reasoning || 'N/A'}
${review?.key_points ? `- Key Points: ${review.key_points.join(', ')}` : ''}`
}).join('\n\n')

const synthesis = await agent(`You are the arbiter. Review these AI responses and synthesize the best answer:

**Original Prompt**: ${userPrompt}

${responsesSummary}

Synthesize the best answer by:
1. Identifying areas of agreement
2. Incorporating the strongest points from each model
3. Resolving any disagreements
4. Providing a unified, comprehensive answer
5. Explaining which models contributed what

You have ${responses.allReviews.length} model responses to synthesize.

Provide your synthesis.`, {
  label: 'Arbiter Synthesis',
  phase: 'Arbiter Synthesis',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      synthesized_answer: { type: 'string' },
      consensus_level: { type: 'string', enum: ['high', 'medium', 'low'] },
      models_agreed: { type: 'number', description: 'How many models agreed' },
      best_points_from: {
        type: 'object',
        additionalProperties: {
          type: 'array',
          items: { type: 'string' }
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

log(`**Consensus Level**: ${synthesis.consensus_level.toUpperCase()} (${synthesis.models_agreed || 0}/${responses.allReviews.length} models agreed)`)
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

// Dynamically show all model contributions
if (synthesis.best_points_from) {
  Object.keys(synthesis.best_points_from).forEach(model => {
    const points = synthesis.best_points_from[model]
    if (points && points.length > 0) {
      log(`**${model.charAt(0).toUpperCase() + model.slice(1)} contributed**:`)
      points.forEach(point => log(`  - ${point}`))
    }
  })
}

log('')
log('='.repeat(60))
log('🎯 Final Answer')
log('='.repeat(60))
log('')
log(synthesis.synthesized_answer)
log('')

const result = {
  status: 'success',
  prompt: userPrompt,
  question: userPrompt,
  consensus_level: synthesis.consensus_level,
  final_confidence: synthesis.final_confidence,
  answer: synthesis.synthesized_answer,
  models_agreed: synthesis.models_agreed || 0,
  models_used: WORKERS,
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

// Extract learnings
try {
  await workflow('extract-learning', {
    workflow_name: 'ai-prompt',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
