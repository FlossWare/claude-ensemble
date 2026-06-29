export const meta = {
  name: 'ai-prompt',
  description: 'Multi-model consensus response to any prompt',
  whenToUse: 'When user wants multiple AI perspectives on a question',
  phases: [
    { title: 'Multi-Model Response', detail: 'Opus, Sonnet, Haiku, Gemini respond independently', model: 'opus' },
    { title: 'Arbiter Synthesis', detail: 'Synthesize best answer' },
  ],
}

// ============================================================================
// THOMPSON SAMPLING INTEGRATION
// ============================================================================

import { selectWorkers, recordResult } from './orchestrator.js'

export default async function({ args, phase, log, agent, parallel }) {

// Fleet dispatcher pilot: DISABLED - workflows don't support ES6 imports
// import { createFleetAgent } from './fleet-agent-wrapper.js'
// const _originalAgent = agent
// globalThis.agent = (process.env.FLEET_DISPATCHER !== 'false') ? createFleetAgent(_originalAgent) : _originalAgent

// ============================================================================
// LOCAL MODELS CONFIG LOADING
// ============================================================================

function loadLocalModelsConfig() {
  try {
    const fs = require('fs')
    const configPath = '~/.claude/repos/claude-global-skills/local-models-config.json'
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
// DYNAMIC MODEL DETECTION (Thompson Sampling enabled)
// ============================================================================

async function getAvailableWorkers(customWorkers = null) {
  // Allow override via args or parameter
  if (customWorkers && Array.isArray(customWorkers)) {
    return customWorkers
  }

  // Define available models
  const baseModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

  // Load local Ollama models from config if enabled
  const localConfig = loadLocalModelsConfig()
  if (localConfig.enabled && localConfig.models) {
    const ollamaModels = Object.values(localConfig.models).filter(m => typeof m === 'string')
    baseModels.push(...ollamaModels)
    log(`✅ Loaded ${ollamaModels.length} local Ollama models from config`)
  }

  // Use Thompson Sampling for model selection
  try {
    const selectedModels = await selectWorkers('multi-model-prompt', {
      strategy: 'thompson',
      models: baseModels,
      count: 6
    })
    log(`Thompson Sampling selected: ${selectedModels.join(', ')}`)
    return selectedModels
  } catch (err) {
    log(`Thompson Sampling failed: ${err.message || err}, using all available models`)
    return baseModels
  }
}

// ============================================================================
// INLINE CONSENSUS ENGINE (simplified for ai-prompt use case)
// ============================================================================

async function multiModelReview(prompt, schema, options = {}) {
  const { workers = await getAvailableWorkers(), phase = 'Multi-Model Response', labelPrefix = 'Response' } = options

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

  // Filter out failed models and track which ones succeeded
  const successfulReviews = reviews.filter(Boolean)
  const successfulWorkers = workers.filter((model, i) => reviews[i] !== null)

  const result = { allReviews: successfulReviews }
  workers.forEach((model, i) => {
    result[model] = reviews[i]
  })

  // Ensure all possible models are in result (null if not used)
  const allPossibleModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'grok']
  allPossibleModels.forEach(model => {
    if (!(model in result)) {
      result[model] = null
    }
  })

  // Log which models failed (if any)
  const failedWorkers = workers.filter((model, i) => reviews[i] === null)
  if (failedWorkers.length > 0) {
    log(`⚠️  Models that failed or were unavailable: ${failedWorkers.join(', ')}`)
  }

  return { ...result, workers: successfulWorkers }  // Only include successful workers
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

const totalModels = 6  // fable, opus, sonnet, haiku, gpt-4o, gemini
const successfulModels = responses.allReviews.length
const failedCount = totalModels - successfulModels

if (failedCount > 0) {
  log(`✅ Received responses from ${successfulModels}/${totalModels} models (${failedCount} failed or unavailable)`)
} else {
  log(`✅ Received responses from all ${successfulModels} models`)
}

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

// ============================================================================
// RECORD THOMPSON SAMPLING RESULTS
// ============================================================================

try {
  for (const review of responses.allReviews) {
    const modelName = Object.keys(responses).find(key => responses[key] === review)
    if (!modelName) continue

    // Quality score based on confidence and consensus
    const qualityScore = (review.confidence / 100) * (synthesis.final_confidence / 100)

    try {
      recordResult(modelName, qualityScore)
      log(`Thompson Sampling updated for ${modelName}: quality=${qualityScore.toFixed(3)}`)
    } catch (err) {
      log(`Thompson Sampling update failed for ${modelName}: ${err.message || err}`)
    }
  }
} catch (err) {
  log(`Thompson Sampling recording failed: ${err.message || err}`)
}

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
  models_used: responses.workers || [],
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
  await workflow('ai-extract-learning', {
    workflow_name: 'ai-prompt',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result

}
