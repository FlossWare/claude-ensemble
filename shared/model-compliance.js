/**
 * Model Compliance Utility
 *
 * Filters model lists based on path_restrictions in fleet.json
 * Use this in workflows to ensure workers/arbiters only use approved models
 */

import fs from 'fs';
import path from 'path';

/**
 * Match model name against pattern (supports wildcards)
 * @param {string} modelName - Model name to check
 * @param {string} pattern - Pattern (e.g., "gpt-*", "ollama-*")
 * @returns {boolean} true if matches
 */
function matchesModelPattern(modelName, pattern) {
  if (pattern === '*') return true;
  if (!pattern.includes('*')) return modelName === pattern;

  const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
  return regex.test(modelName);
}

/**
 * Check if model is allowed in current directory
 * @param {string} modelName - Model name to check
 * @returns {{allowed: boolean, reason?: string}} Compliance result
 */
export function isModelAllowed(modelName) {
  if (!modelName) return { allowed: true };

  try {
    const fleetConfigPath = path.join(process.env.HOME || '/home/sfloess', '.claude', 'fleet.json');
    if (!fs.existsSync(fleetConfigPath)) return { allowed: true };

    const config = JSON.parse(fs.readFileSync(fleetConfigPath, 'utf8'));
    const restrictions = config.compliance?.path_restrictions || [];

    let cwd;
    try {
      cwd = fs.realpathSync(process.cwd());
    } catch (e) {
      cwd = process.cwd();
    }

    // Find matching restrictions (longest path first = most specific)
    const matching = restrictions
      .filter(r => cwd.startsWith(r.path))
      .sort((a, b) => b.path.length - a.path.length);

    if (!matching.length) return { allowed: true };

    const restriction = matching[0];

    // Check denied models first
    if (restriction.denied_models) {
      for (const pattern of restriction.denied_models) {
        if (matchesModelPattern(modelName, pattern)) {
          return {
            allowed: false,
            reason: restriction.reason || `Model ${modelName} not allowed in ${restriction.path}`
          };
        }
      }
    }

    // Check allowed models if specified
    if (restriction.allowed_models) {
      for (const pattern of restriction.allowed_models) {
        if (matchesModelPattern(modelName, pattern)) {
          return { allowed: true };
        }
      }
      // Model not in allow list
      return {
        allowed: false,
        reason: restriction.reason || `Model ${modelName} not in allowed list for ${restriction.path}`
      };
    }

    // No denied, no allowed = allow by default
    return { allowed: true };
  } catch (e) {
    // If we can't read config, assume compliant
    return { allowed: true };
  }
}

/**
 * Filter a list of models based on path restrictions
 * Removes any models that are not allowed in current directory
 *
 * @param {string[]} models - Array of model names
 * @returns {string[]} Filtered array with only allowed models
 *
 * @example
 * // In Red Hat directory with denied_models: ["gpt-*"]
 * const workers = filterAllowedModels(['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']);
 * // Returns: ['opus', 'sonnet', 'haiku', 'gemini']
 */
export function filterAllowedModels(models) {
  if (!Array.isArray(models)) return [];

  return models.filter(model => {
    const check = isModelAllowed(model);
    if (!check.allowed) {
      console.warn(`⚠️  Model ${model} filtered out: ${check.reason}`);
    }
    return check.allowed;
  });
}

/**
 * Get compliance-filtered worker list for multi-AI workflows
 * Returns default worker list with restricted models removed
 *
 * @param {string[]} defaultWorkers - Default worker model list
 * @returns {string[]} Filtered worker list
 *
 * @example
 * const workers = getCompliantWorkers(['sonnet', 'opus', 'haiku', 'gpt-4o', 'gemini']);
 */
export function getCompliantWorkers(defaultWorkers = ['sonnet', 'opus', 'haiku', 'gpt-4o', 'gemini', 'cerebras-120b']) {
  return filterAllowedModels(defaultWorkers);
}

/**
 * Get compliance-filtered arbiter model
 * If default arbiter not allowed, returns first allowed model from list
 *
 * @param {string} defaultArbiter - Default arbiter model
 * @param {string[]} fallbackList - Fallback models to try
 * @returns {string} Allowed arbiter model
 *
 * @example
 * const arbiter = getCompliantArbiter('opus', ['opus', 'sonnet', 'haiku']);
 */
export function getCompliantArbiter(defaultArbiter = 'opus', fallbackList = ['opus', 'sonnet', 'haiku']) {
  const check = isModelAllowed(defaultArbiter);
  if (check.allowed) return defaultArbiter;

  // Try fallback list
  for (const model of fallbackList) {
    if (isModelAllowed(model).allowed) {
      console.warn(`⚠️  Arbiter ${defaultArbiter} not allowed, using ${model}: ${check.reason}`);
      return model;
    }
  }

  // Last resort - return first allowed from workers
  console.warn(`⚠️  No arbiter from fallback list allowed, using first available`);
  return fallbackList[0];
}

/**
 * Check if current directory has model restrictions
 * @returns {boolean} true if restrictions apply
 */
export function hasModelRestrictions() {
  try {
    const fleetConfigPath = path.join(process.env.HOME || '/home/sfloess', '.claude', 'fleet.json');
    if (!fs.existsSync(fleetConfigPath)) return false;

    const config = JSON.parse(fs.readFileSync(fleetConfigPath, 'utf8'));
    const restrictions = config.compliance?.path_restrictions || [];

    let cwd;
    try {
      cwd = fs.realpathSync(process.cwd());
    } catch (e) {
      cwd = process.cwd();
    }

    return restrictions.some(r => cwd.startsWith(r.path));
  } catch (e) {
    return false;
  }
}

/**
 * Get active restriction for current directory
 * @returns {{path: string, denied_models?: string[], allowed_models?: string[], reason?: string} | null}
 */
export function getActiveRestriction() {
  try {
    const fleetConfigPath = path.join(process.env.HOME || '/home/sfloess', '.claude', 'fleet.json');
    if (!fs.existsSync(fleetConfigPath)) return null;

    const config = JSON.parse(fs.readFileSync(fleetConfigPath, 'utf8'));
    const restrictions = config.compliance?.path_restrictions || [];

    let cwd;
    try {
      cwd = fs.realpathSync(process.cwd());
    } catch (e) {
      cwd = process.cwd();
    }

    // Find matching restrictions (longest path first = most specific)
    const matching = restrictions
      .filter(r => cwd.startsWith(r.path))
      .sort((a, b) => b.path.length - a.path.length);

    return matching.length > 0 ? matching[0] : null;
  } catch (e) {
    return null;
  }
}
