// Model Discovery Utility
// Detects available AI models/providers at runtime
// Supports: Claude, Gemini, Grok, Ollama, and any MCP-accessible models

/**
 * Discovers all available AI models
 *
 * @param {Function} agent - The agent function from workflow context
 * @param {Object} options - Configuration options
 * @param {string[]} options.preferredModels - Models to try first
 * @param {number} options.minModels - Minimum models required (default: 1)
 * @param {number} options.maxModels - Maximum models to use (default: Infinity)
 * @param {boolean} options.allowDuplicateProviders - Allow multiple models from same provider (default: false)
 * @returns {Promise<Object>} Discovery result with available models
 */
export async function discoverModels(agent, options = {}) {
  const {
    preferredModels = [],
    minModels = 1,
    maxModels = Infinity,
    allowDuplicateProviders = false
  } = options

  // Known model identifiers to try
  const KNOWN_MODELS = [
    // Claude models (built-in)
    'opus',
    'sonnet',
    'haiku',

    // Gemini models
    'gemini',
    'gemini-pro',
    'gemini-flash',

    // Grok models (xAI)
    'grok',
    'grok-2',
    'grok-beta',

    // Ollama models (if running locally)
    'ollama/llama3',
    'ollama/llama3.1',
    'ollama/mistral',
    'ollama/mixtral',
    'ollama/codestral',
    'ollama/qwen',

    // OpenAI models (if MCP available)
    'gpt-4',
    'gpt-4-turbo',
    'gpt-3.5-turbo',

    // Other providers
    'claude-3-opus',
    'claude-3-sonnet',
    'claude-3-haiku',
  ]

  // Try preferred models first, then known models
  const modelsToTry = [
    ...preferredModels,
    ...KNOWN_MODELS.filter(m => !preferredModels.includes(m))
  ]

  const availableModels = []
  const failedModels = []
  const providersSeen = new Set()

  log(`🔍 Discovering available AI models... (testing ${modelsToTry.length} candidates)`)

  // Test each model with a lightweight ping
  for (const modelId of modelsToTry) {
    if (availableModels.length >= maxModels) {
      break
    }

    try {
      // Extract provider (e.g., "ollama" from "ollama/llama3")
      const provider = modelId.includes('/') ? modelId.split('/')[0] : modelId.split('-')[0]

      // Skip if we already have a model from this provider (unless allowed)
      if (!allowDuplicateProviders && providersSeen.has(provider)) {
        continue
      }

      // Lightweight ping test - ask for a single word response
      const result = await agent('Respond with only the word "ok"', {
        model: modelId,
        label: `Ping ${modelId}`,
        schema: {
          type: 'object',
          properties: {
            status: { type: 'string' }
          }
        }
      })

      if (result) {
        availableModels.push(modelId)
        providersSeen.add(provider)
        log(`  ✅ ${modelId} - available`)
      }
    } catch (error) {
      failedModels.push({ model: modelId, error: error.message })
      // Silently continue - model not available
    }
  }

  log(`✅ Discovery complete: ${availableModels.length} models available`)

  if (availableModels.length < minModels) {
    throw new Error(`Only found ${availableModels.length} models, need at least ${minModels}`)
  }

  return {
    available: availableModels,
    failed: failedModels,
    providers: Array.from(providersSeen),
    count: availableModels.length
  }
}

/**
 * Creates rotated model sets for diverse parallel execution
 *
 * @param {string[]} models - Available model identifiers
 * @param {number} groupSize - How many models per group (default: all)
 * @returns {Array<string[]>} Rotated model groups
 */
export function createModelRotations(models, groupSize = null) {
  const size = groupSize || models.length
  const rotations = []

  for (let i = 0; i < models.length; i++) {
    const rotation = []
    for (let j = 0; j < size; j++) {
      rotation.push(models[(i + j) % models.length])
    }
    rotations.push(rotation)
  }

  return rotations
}

/**
 * Selects best arbiter model from available models
 * Prefers most capable model (opus > gemini > sonnet > others)
 *
 * @param {string[]} models - Available models
 * @param {number} index - Optional index for rotation
 * @returns {string} Selected arbiter model
 */
export function selectArbiter(models, index = 0) {
  // Preference order (most capable first)
  const ARBITER_PREFERENCE = [
    'opus',
    'claude-3-opus',
    'gpt-4',
    'gpt-4-turbo',
    'grok-2',
    'gemini-pro',
    'gemini',
    'sonnet',
    'grok',
    'claude-3-sonnet',
    'haiku',
    // Everything else
  ]

  // If rotation index provided, rotate through available models
  if (index > 0) {
    return models[index % models.length]
  }

  // Otherwise, pick most capable
  for (const preferred of ARBITER_PREFERENCE) {
    if (models.includes(preferred)) {
      return preferred
    }
  }

  // Fallback to first available
  return models[0]
}

/**
 * Gets worker models (all available except arbiter)
 *
 * @param {string[]} models - Available models
 * @param {string} arbiter - Arbiter model to exclude
 * @returns {string[]} Worker models
 */
export function getWorkers(models, arbiter) {
  return models.filter(m => m !== arbiter)
}

// Inline version for workflows that can't use imports
// Copy this code directly into workflows if needed
export const INLINE_MODEL_DISCOVERY = `
// Inline model discovery (no imports needed)
async function discoverModels(minModels = 1) {
  const KNOWN_MODELS = [
    'opus', 'sonnet', 'haiku',
    'gemini', 'gemini-pro',
    'grok', 'grok-2',
    'ollama/llama3', 'ollama/mistral',
  ]

  const available = []
  for (const model of KNOWN_MODELS) {
    try {
      await agent('ok?', { model, schema: { type: 'object', properties: { status: { type: 'string' }}}})
      available.push(model)
    } catch { /* skip */ }
  }

  if (available.length < minModels) {
    throw new Error(\`Only \${available.length} models found\`)
  }

  return available
}
`
