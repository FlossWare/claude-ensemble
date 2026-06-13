// AI Prompt - Multi-Model Consensus for Any Prompt
// FIXED: Removed imports, added inline consensus logic

export const meta = {
  name: 'ai-prompt',
  description: 'Multi-model consensus response to any prompt',
  whenToUse: 'When user wants multiple AI perspectives on a question',
  phases: [
    { title: 'Multi-Model Response', detail: 'Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini respond independently (6 workers)', model: 'opus' },
    { title: 'Arbiter Synthesis', detail: 'Synthesize best answer' },
  ],
}

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await _agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


// INLINE CONSENSUS ENGINE (simplified for ai-prompt use case)
async function multiModelReview(prompt, schema, options = {}) {
  const { workers = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'], phase = 'Multi-Model Response', labelPrefix = 'Response' } = options

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
  model: 'opus',
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
