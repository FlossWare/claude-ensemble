/**
 * Discovery Application System
 *
 * Applies AI-discovered patterns and insights to model selection.
 * Discoveries are learned automatically from execution history and encoded
 * as rules in discoveries.json.
 *
 * This module interprets discovery rules and applies them to:
 * - Filter available models
 * - Bias model selection probabilities
 * - Adjust diversity weights
 * - Route tasks to optimal models
 * - Enforce quality/cost constraints
 *
 * Usage:
 *   import { applyDiscoveries, filterModels, biasSelection } from './apply-discoveries.js';
 *
 *   // Apply all relevant discoveries to model selection
 *   const context = {
 *     task_type: 'security-review',
 *     requires_schema: false,
 *     cost_sensitivity: 'high',
 *   };
 *   const models = ['opus', 'sonnet', 'haiku', 'fable'];
 *   const filtered = await filterModels(models, context);
 *   // => ['sonnet', 'haiku'] (opus filtered due to cost, fable ok)
 *
 *   // Bias Thompson Sampling based on discoveries
 *   const biased = await biasSelection(models, context);
 *   // => { opus: 0.5, sonnet: 1.5, haiku: 1.5, fable: 1.0 }
 */

import { hotImportJSON } from '../shared/hot-reload.js';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// CONSTANTS
// ============================================================================

const DISCOVERIES_PATH = join(__dirname, 'discoveries.json');
const MIN_CONFIDENCE = 0.7; // Only apply discoveries with confidence >= 0.7

// ============================================================================
// DISCOVERY LOADING
// ============================================================================

/**
 * Load active discoveries from discoveries.json
 *
 * @param {object} options - Load options
 * @param {boolean} options.force - Force reload from disk (default: false)
 * @param {number} options.minConfidence - Minimum confidence threshold (default: 0.7)
 * @returns {Promise<object[]>} Array of active discoveries
 */
export async function loadDiscoveries(options = {}) {
  const {
    force = false,
    minConfidence = MIN_CONFIDENCE,
  } = options;

  try {
    const data = await hotImportJSON(DISCOVERIES_PATH, {
      force,
      defaultValue: { discoveries: [] },
    });

    // Filter to active discoveries with sufficient confidence
    const active = (data.discoveries || []).filter(d =>
      d.status === 'active' &&
      d.confidence >= minConfidence
    );

    if (process.env.LEARNING_DEBUG) {
      console.log(`[apply-discoveries] Loaded ${active.length} active discoveries (min confidence: ${minConfidence})`);
    }

    return active;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[apply-discoveries] Failed to load discoveries: ${err.message}`);
    }
    return [];
  }
}

// ============================================================================
// CONDITION MATCHING
// ============================================================================

/**
 * Check if a discovery's conditions match the given context
 *
 * @param {object} discovery - Discovery object
 * @param {object} context - Execution context
 * @returns {boolean} True if conditions match
 */
function matchesConditions(discovery, context) {
  if (!discovery.conditions) {
    return true; // No conditions = always match
  }

  const conditions = discovery.conditions;

  // Match task_type (exact or array)
  if (conditions.task_type !== undefined) {
    if (Array.isArray(conditions.task_type)) {
      if (!conditions.task_type.includes(context.task_type)) {
        return false;
      }
    } else if (conditions.task_type !== context.task_type) {
      return false;
    }
  }

  // Match requires_schema
  if (conditions.requires_schema !== undefined) {
    if (conditions.requires_schema !== context.requires_schema) {
      return false;
    }
  }

  // Match output_format
  if (conditions.output_format !== undefined) {
    if (conditions.output_format !== context.output_format) {
      return false;
    }
  }

  // Match cost_sensitivity
  if (conditions.cost_sensitivity !== undefined) {
    if (conditions.cost_sensitivity !== context.cost_sensitivity) {
      return false;
    }
  }

  // Match budget_constraint
  if (conditions.budget_constraint !== undefined) {
    if (conditions.budget_constraint !== context.budget_constraint) {
      return false;
    }
  }

  // Match quality_threshold
  if (conditions.quality_threshold !== undefined) {
    if (context.quality_threshold === undefined ||
        context.quality_threshold < conditions.quality_threshold) {
      return false;
    }
  }

  // Match complexity
  if (conditions.complexity !== undefined) {
    if (conditions.complexity !== context.complexity) {
      return false;
    }
  }

  // Match workflow
  if (conditions.workflow !== undefined) {
    if (conditions.workflow !== context.workflow) {
      return false;
    }
  }

  // Match min_workers
  if (conditions.min_workers !== undefined) {
    if (context.worker_count === undefined ||
        context.worker_count < conditions.min_workers) {
      return false;
    }
  }

  return true;
}

// ============================================================================
// MODEL FILTERING
// ============================================================================

/**
 * Filter models based on active discoveries
 *
 * @param {string[]} models - Available models
 * @param {object} context - Execution context
 * @param {object} options - Filtering options
 * @returns {Promise<string[]>} Filtered models
 */
export async function filterModels(models, context = {}, options = {}) {
  const discoveries = await loadDiscoveries(options);

  let filtered = [...models];
  const applied = [];

  for (const discovery of discoveries) {
    if (!matchesConditions(discovery, context)) {
      continue;
    }

    if (discovery.action.type === 'filter_models') {
      const params = discovery.action.params;

      // Apply exclusions
      if (params.exclude) {
        const beforeCount = filtered.length;
        filtered = filtered.filter(m => !params.exclude.includes(m));

        if (filtered.length < beforeCount) {
          applied.push({
            discovery: discovery.id,
            pattern: discovery.pattern,
            excluded: params.exclude,
          });
        }
      }

      // Apply preferences (but don't exclude others unless explicit)
      if (params.prefer && params.exclude_others) {
        filtered = filtered.filter(m => params.prefer.includes(m));
        applied.push({
          discovery: discovery.id,
          pattern: discovery.pattern,
          preferred: params.prefer,
        });
      }
    }
  }

  if (process.env.LEARNING_DEBUG && applied.length > 0) {
    console.log(`[apply-discoveries] Filtered models:`, {
      original: models,
      filtered,
      applied,
    });
  }

  // Ensure at least one model remains
  if (filtered.length === 0) {
    if (process.env.LEARNING_DEBUG) {
      console.warn(`[apply-discoveries] All models filtered out, reverting to original list`);
    }
    return models;
  }

  return filtered;
}

// ============================================================================
// SELECTION BIASING
// ============================================================================

/**
 * Calculate model selection biases based on discoveries
 *
 * Returns a mapping of model -> bias multiplier (1.0 = neutral, >1.0 = prefer, <1.0 = avoid)
 *
 * @param {string[]} models - Available models
 * @param {object} context - Execution context
 * @param {object} options - Bias options
 * @returns {Promise<object>} Model bias map
 */
export async function biasSelection(models, context = {}, options = {}) {
  const discoveries = await loadDiscoveries(options);

  // Start with neutral biases
  const biases = {};
  for (const model of models) {
    biases[model] = 1.0;
  }

  const applied = [];

  for (const discovery of discoveries) {
    if (!matchesConditions(discovery, context)) {
      continue;
    }

    if (discovery.action.type === 'bias_models') {
      const params = discovery.action.params;

      if (params.bias) {
        for (const [model, bias] of Object.entries(params.bias)) {
          if (biases[model] !== undefined) {
            // Multiply biases (allows multiple discoveries to compound)
            biases[model] *= bias;
            applied.push({
              discovery: discovery.id,
              pattern: discovery.pattern,
              model,
              bias,
            });
          }
        }
      }
    }

    if (discovery.action.type === 'prefer_model') {
      const params = discovery.action.params;
      const model = params.model;

      if (biases[model] !== undefined) {
        // Strong preference: 2x bias
        biases[model] *= 2.0;
        applied.push({
          discovery: discovery.id,
          pattern: discovery.pattern,
          model,
          bias: 2.0,
        });
      }
    }
  }

  if (process.env.LEARNING_DEBUG && applied.length > 0) {
    console.log(`[apply-discoveries] Applied biases:`, {
      biases,
      applied,
    });
  }

  return biases;
}

// ============================================================================
// DIVERSITY ADJUSTMENT
// ============================================================================

/**
 * Calculate diversity weight adjustment based on discoveries
 *
 * @param {object} context - Execution context
 * @param {object} options - Options
 * @returns {Promise<number>} Diversity weight (0-1, default 0.5)
 */
export async function getDiversityWeight(context = {}, options = {}) {
  const discoveries = await loadDiscoveries(options);

  let diversityWeight = 0.5; // Default
  const applied = [];

  for (const discovery of discoveries) {
    if (!matchesConditions(discovery, context)) {
      continue;
    }

    if (discovery.action.type === 'increase_diversity') {
      const params = discovery.action.params;

      if (params.diversity_weight !== undefined) {
        diversityWeight = Math.max(diversityWeight, params.diversity_weight);
        applied.push({
          discovery: discovery.id,
          pattern: discovery.pattern,
          weight: params.diversity_weight,
        });
      }
    }
  }

  if (process.env.LEARNING_DEBUG && applied.length > 0) {
    console.log(`[apply-discoveries] Diversity weight: ${diversityWeight}`, applied);
  }

  return diversityWeight;
}

// ============================================================================
// WORKER COUNT ADJUSTMENT
// ============================================================================

/**
 * Get optimal worker count based on discoveries
 *
 * @param {object} context - Execution context
 * @param {number} defaultCount - Default worker count
 * @param {object} options - Options
 * @returns {Promise<number>} Recommended worker count
 */
export async function getWorkerCount(context = {}, defaultCount = 3, options = {}) {
  const discoveries = await loadDiscoveries(options);

  let workerCount = defaultCount;
  const applied = [];

  for (const discovery of discoveries) {
    if (!matchesConditions(discovery, context)) {
      continue;
    }

    if (discovery.action.type === 'set_worker_count') {
      const params = discovery.action.params;

      if (params.count !== undefined) {
        workerCount = params.count;

        // Apply max_count constraint
        if (params.max_count !== undefined) {
          workerCount = Math.min(workerCount, params.max_count);
        }

        applied.push({
          discovery: discovery.id,
          pattern: discovery.pattern,
          count: workerCount,
        });
      }
    }
  }

  if (process.env.LEARNING_DEBUG && applied.length > 0) {
    console.log(`[apply-discoveries] Worker count: ${workerCount}`, applied);
  }

  return workerCount;
}

// ============================================================================
// UNIFIED DISCOVERY APPLICATION
// ============================================================================

/**
 * Apply all relevant discoveries to model selection context
 *
 * Returns a comprehensive configuration object with all discovery adjustments.
 *
 * @param {string[]} models - Available models
 * @param {object} context - Execution context
 * @param {object} options - Application options
 * @returns {Promise<object>} Applied configuration
 */
export async function applyDiscoveries(models, context = {}, options = {}) {
  const discoveries = await loadDiscoveries(options);

  // Track which discoveries match this context
  const appliedDiscoveryIds = [];

  for (const discovery of discoveries) {
    if (matchesConditions(discovery, context)) {
      appliedDiscoveryIds.push(discovery.id);
    }
  }

  const [
    filteredModels,
    biases,
    diversityWeight,
    workerCount,
  ] = await Promise.all([
    filterModels(models, context, options),
    biasSelection(models, context, options),
    getDiversityWeight(context, options),
    getWorkerCount(context, context.worker_count || 3, options),
  ]);

  // Record discovery applications (async, don't wait)
  if (appliedDiscoveryIds.length > 0 && !options.skipTracking) {
    _recordApplications(appliedDiscoveryIds).catch(err => {
      if (process.env.LEARNING_DEBUG) {
        console.error(`[apply-discoveries] Application tracking failed: ${err.message}`);
      }
    });
  }

  return {
    models: filteredModels,
    biases,
    diversity_weight: diversityWeight,
    worker_count: workerCount,
    context,
    applied_discoveries: appliedDiscoveryIds,
  };
}

/**
 * Record discovery applications (internal helper)
 */
async function _recordApplications(discoveryIds) {
  try {
    const { default: updateMetadata } = await import('./update-discovery-metadata.js');
    await updateMetadata.recordMultipleApplications(discoveryIds);
  } catch (err) {
    // Ignore tracking errors
  }
}

// ============================================================================
// DISCOVERY STATISTICS
// ============================================================================

/**
 * Get statistics about active discoveries
 *
 * @param {object} options - Options
 * @returns {Promise<object>} Discovery statistics
 */
export async function getDiscoveryStats(options = {}) {
  const discoveries = await loadDiscoveries(options);

  const stats = {
    total: discoveries.length,
    by_type: {},
    avg_confidence: 0,
    avg_quality_impact: 0,
    avg_cost_savings: 0,
  };

  let totalConfidence = 0;
  let totalQualityImpact = 0;
  let totalCostSavings = 0;
  let qualityCount = 0;
  let costCount = 0;

  for (const discovery of discoveries) {
    // Count by type
    stats.by_type[discovery.type] = (stats.by_type[discovery.type] || 0) + 1;

    // Aggregate confidence
    totalConfidence += discovery.confidence || 0;

    // Aggregate quality impact
    if (discovery.quality_impact !== undefined) {
      totalQualityImpact += discovery.quality_impact;
      qualityCount++;
    }

    // Aggregate cost savings
    if (discovery.cost_savings !== undefined) {
      totalCostSavings += discovery.cost_savings;
      costCount++;
    }
  }

  if (discoveries.length > 0) {
    stats.avg_confidence = totalConfidence / discoveries.length;
  }

  if (qualityCount > 0) {
    stats.avg_quality_impact = totalQualityImpact / qualityCount;
  }

  if (costCount > 0) {
    stats.avg_cost_savings = totalCostSavings / costCount;
  }

  return stats;
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  loadDiscoveries,
  filterModels,
  biasSelection,
  getDiversityWeight,
  getWorkerCount,
  applyDiscoveries,
  getDiscoveryStats,
};
