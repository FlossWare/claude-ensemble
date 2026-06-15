/**
 * Load multi-AI configuration with fallback to sensible defaults
 *
 * Note: Workflows cannot use fs/require, so this is for non-workflow code only.
 * For workflows, use the inline constants below or pass config via args.
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Default configuration (fallback)
const DEFAULT_CONFIG = {
  enabled: true,
  default_strategy: 'maximum-coverage',
  workers: {
    models: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
    count: 6
  },
  arbiter: {
    enabled: true,
    model: 'fable',
    fallback: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
  }
};

/**
 * Load configuration from multi-ai-config.json
 * @returns {Object} Multi-AI configuration
 */
export function loadMultiAIConfig() {
  try {
    const configPath = join(__dirname, '..', 'multi-ai-config.json');
    const configData = readFileSync(configPath, 'utf8');
    return JSON.parse(configData);
  } catch (error) {
    console.warn(`Failed to load multi-ai-config.json: ${error.message}. Using defaults.`);
    return DEFAULT_CONFIG;
  }
}

/**
 * Get worker model names from config
 * @returns {string[]} Array of model names
 */
export function getWorkerModels() {
  const config = loadMultiAIConfig();

  // If config has array of objects with 'name' property
  if (config.workers.models && Array.isArray(config.workers.models) && config.workers.models[0]?.name) {
    return config.workers.models.map(m => m.name);
  }

  // If config has simple string array
  if (config.workers.models && Array.isArray(config.workers.models)) {
    return config.workers.models;
  }

  return DEFAULT_CONFIG.workers.models;
}

/**
 * Get arbiter fallback chain from config
 * @returns {string[]} Array of model names in fallback order
 */
export function getArbiterFallback() {
  const config = loadMultiAIConfig();
  return config.arbiter?.fallback || DEFAULT_CONFIG.arbiter.fallback;
}

/**
 * INLINE CONSTANTS FOR WORKFLOWS
 *
 * Workflows cannot import this file (no fs access), so copy these constants:
 *
 * const WORKER_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
 * const ARBITER_FALLBACK = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
 *
 * Or pass via workflow args:
 *
 * Workflow({ name: 'my-workflow', args: {
 *   workers: ['fable', 'opus', 'sonnet'],
 *   arbiter: 'fable'
 * }})
 */

export default {
  loadMultiAIConfig,
  getWorkerModels,
  getArbiterFallback,
  DEFAULT_CONFIG
};
