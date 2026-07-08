/**
 * Anthropic Official Models
 *
 * These are the ONLY models that are:
 * - Built into Claude directly
 * - Paid Anthropic subscriptions
 * - Safe for proprietary/Red Hat work
 *
 * DO NOT add third-party models to this list!
 */

const ANTHROPIC_MODELS = [
  // Claude Opus (flagship)
  'claude-opus-4',
  'claude-opus-4-20250514',
  'claude-opus-4.7',
  'claude-opus-4.8',
  'claude-opus-5',
  'opus',

  // Claude Sonnet (balanced)
  'claude-sonnet-4',
  'claude-sonnet-4-20250514',
  'claude-sonnet-4.5',
  'claude-sonnet-4.5-20250929',
  'claude-sonnet-5',
  'sonnet',

  // Claude Haiku (fast/cheap)
  'claude-haiku-4',
  'claude-haiku-4-20250514',
  'claude-haiku-4.5',
  'claude-haiku-4.5-20251001',
  'haiku',

  // Claude Fable (new tier)
  'claude-fable-5',
  'fable'
];

/**
 * Check if a model is an official Anthropic model
 * @param {string} modelName - Model name to check
 * @returns {boolean} - True if Anthropic model
 */
function isAnthropicModel(modelName) {
  return ANTHROPIC_MODELS.some(official =>
    modelName.toLowerCase().includes(official.toLowerCase())
  );
}

/**
 * Filter models to only Anthropic ones
 * @param {Array<string>} models - List of models
 * @returns {Array<string>} - Only Anthropic models
 */
function filterAnthropicOnly(models) {
  return models.filter(isAnthropicModel);
}

/**
 * Get all Anthropic model names (canonical list)
 * @returns {Array<string>}
 */
function getAnthropicModels() {
  return [...ANTHROPIC_MODELS];
}

module.exports = {
  ANTHROPIC_MODELS,
  isAnthropicModel,
  filterAnthropicOnly,
  getAnthropicModels
};
