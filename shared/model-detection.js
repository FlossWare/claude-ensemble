import { DEFAULT_MODELS, ANTHROPIC_MODELS } from './model-constants.js'

/**
 * Dynamic Model Detection for Multi-AI Workflows
 *
 * Auto-detects available models beyond the default Claude trio.
 * Supports: Claude (opus, sonnet, haiku), Gemini, Grok, Ollama, OpenAI, etc.
 * Respects Red Hat compliance (Anthropic-only) when in proprietary context.
 *
 * Usage in workflows:
 *
 *   import { getAvailableWorkers, WORKER_PRESETS } from './shared/model-detection.js'
 *
 *   const WORKERS = await getAvailableWorkers()
 *   // Returns: ['sonnet', 'opus', 'haiku', 'gpt-4o', 'gemini', 'cerebras-120b'] (or Anthropic-only if in RH)
 *
 * Or use presets:
 *
 *   const WORKERS = WORKER_PRESETS.ALL  // All available
 *   const WORKERS = WORKER_PRESETS.CLAUDE_ONLY  // Just opus/sonnet/haiku
 *   const WORKERS = WORKER_PRESETS.FAST  // haiku, gemini (cheap/fast)
 */

// ============================================================================
// Model Detection
// ============================================================================

/**
 * Get all available worker models dynamically
 * @param {Object} options - Configuration options
 * @param {boolean} options.includeGemini - Include Gemini if available (default: true)
 * @param {boolean} options.includeGrok - Include Grok if available (default: true)
 * @param {boolean} options.includeOllama - Include Ollama models if available (default: false)
 * @param {boolean} options.includeOpenAI - Include OpenAI models if available (default: false)
 * @param {string[]} options.customModels - Additional custom models to include
 * @returns {Promise<string[]>} - Array of available model names
 */
export async function getAvailableWorkers(options = {}) {
  const {
    includeGemini = true,
    includeGrok = true,
    includeOllama = false,
    includeOpenAI = false,
    customModels = []
  } = options

  // Auto-detect Red Hat context
  const cwd = process.cwd?.() || ''
  const isRedHat = cwd.includes('/redhat/') || cwd.includes('/rh/')

  // Start with appropriate base models for context
  const models = isRedHat ? [...ANTHROPIC_MODELS] : [...DEFAULT_MODELS]

  // In Red Hat context, restrict to Anthropic only (already has 6 models with DEFAULT_MODELS)
  // For non-Red Hat, add specialized models
  if (!isRedHat) {
    // Check for Gemini (via MCP or direct integration) - not in DEFAULT_MODELS
    if (includeGemini && !models.includes('gemini')) {
      // Gemini is configured via MCP in user's setup
      // models.push('gemini')  // Already in DEFAULT_MODELS
    }

    // Check for Grok (via API integration)
    if (includeGrok && !models.includes('grok')) {
      // Grok availability can be checked via environment or MCP
      // For now, assume available if user wants it
      // models.push('grok')  // Uncomment when Grok is set up
    }

    // Check for Ollama (local models)
    if (includeOllama) {
      // Could check: ollama list | grep running
      // models.push('ollama/codellama')
      // models.push('ollama/deepseek-coder')
    }

    // Check for OpenAI (via API)
    if (includeOpenAI) {
      // models.push('openai/gpt-4')
      // models.push('openai/gpt-4-turbo')
    }
  }

  // Add custom models
  if (customModels.length > 0) {
    models.push(...customModels)
  }

  return models
}

/**
 * Check if a specific model is available
 * @param {string} modelName - Model name to check
 * @returns {Promise<boolean>} - True if model is available
 */
export async function isModelAvailable(modelName) {
  const available = await getAvailableWorkers({
    includeGemini: true,
    includeGrok: true,
    includeOllama: true,
    includeOpenAI: true
  })
  return available.includes(modelName)
}

/**
 * Parse worker list from args
 * Examples:
 *   --workers=opus,gemini,haiku
 *   workers: ['opus', 'gemini']
 *
 * @param {any} args - Workflow args
 * @param {string[]} defaultWorkers - Default workers if not specified
 * @returns {string[]} - Array of worker model names
 */
export function parseWorkersFromArgs(args, defaultWorkers) {
  // Check for --workers flag in args
  if (args?.workers) {
    if (typeof args.workers === 'string') {
      return args.workers.split(',').map(w => w.trim())
    }
    if (Array.isArray(args.workers)) {
      return args.workers
    }
  }

  // Check for workers array in args
  if (Array.isArray(args) && args.length > 0) {
    const workersArg = args.find(a => typeof a === 'string' && a.startsWith('--workers='))
    if (workersArg) {
      return workersArg.replace('--workers=', '').split(',').map(w => w.trim())
    }
  }

  return defaultWorkers
}

// ============================================================================
// Presets
// ============================================================================

export const WORKER_PRESETS = {
  // All available models
  ALL: ['opus', 'sonnet', 'haiku', 'gemini'],

  // Claude models only
  CLAUDE_ONLY: ['opus', 'sonnet', 'haiku'],

  // Fast/cheap models for verification
  FAST: ['haiku', 'gemini'],

  // Premium models for complex analysis
  PREMIUM: ['opus', 'sonnet'],

  // Diverse set (different architectures)
  DIVERSE: ['opus', 'haiku', 'gemini'],

  // Maximum coverage (when Grok/Ollama/OpenAI are set up)
  // Note: Fable removed per Issue #197 (API 403 errors)
  MAXIMUM: ['sonnet', 'opus', 'haiku', 'gpt-4o', 'gemini', 'cerebras-120b', 'openclaw'],
}

// ============================================================================
// Model Capabilities
// ============================================================================

export const MODEL_CAPABILITIES = {
  opus: {
    tier: 'premium',
    speed: 'slow',
    cost: 'high',
    strengths: ['complex reasoning', 'code quality', 'architecture'],
  },
  sonnet: {
    tier: 'balanced',
    speed: 'medium',
    cost: 'medium',
    strengths: ['general purpose', 'balanced', 'reliable'],
  },
  haiku: {
    tier: 'fast',
    speed: 'fast',
    cost: 'low',
    strengths: ['quick verification', 'simple tasks', 'cost-effective'],
  },
  gemini: {
    tier: 'balanced',
    speed: 'fast',
    cost: 'low',
    strengths: ['cost-effective', 'fast', 'multimodal'],
  },
  grok: {
    tier: 'experimental',
    speed: 'medium',
    cost: 'medium',
    strengths: ['alternative perspective', 'diverse reasoning'],
  },
  openclaw: {
    tier: 'agent',
    speed: 'variable',
    cost: 'variable',
    strengths: ['execution verification', 'tool use', 'persistent memory', 'code testing'],
  },
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Select best arbiter model from available workers
 * @param {string[]} workers - Available worker models
 * @param {number} iteration - Current iteration (for rotation)
 * @returns {string} - Best arbiter model
 */
export function selectArbiter(workers, iteration = 0) {
  // Prefer opus for arbiter role, but rotate through all available
  if (workers.includes('opus')) {
    return 'opus'
  }
  return workers[iteration % workers.length]
}

/**
 * Get complementary models for adversarial verification
 * @param {string} primaryModel - Primary model to complement
 * @param {string[]} availableModels - All available models
 * @returns {string[]} - Complementary models
 */
export function getComplementaryModels(primaryModel, availableModels) {
  // Return all models except the primary
  return availableModels.filter(m => m !== primaryModel)
}

/**
 * Format model list for logging
 * @param {string[]} models - Model names
 * @returns {string} - Formatted string
 */
export function formatModelList(models) {
  return models.join(', ')
}

export default {
  getAvailableWorkers,
  isModelAvailable,
  parseWorkersFromArgs,
  WORKER_PRESETS,
  MODEL_CAPABILITIES,
  selectArbiter,
  getComplementaryModels,
  formatModelList,
}
