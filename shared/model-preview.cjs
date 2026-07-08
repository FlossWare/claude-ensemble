/**
 * Model Selection Preview (Dry-Run Mode)
 *
 * Preview what models would be selected WITHOUT:
 * - Logging to database
 * - Consuming API credits
 * - Executing workflows
 *
 * Shows:
 * - Which models would be available
 * - Which models would be filtered out (and why)
 * - What the rotation pool would be
 * - Which model would be selected next
 */

const { applyRules, getRulesForTask } = require('./task-model-rules.cjs');
const { isAnthropicModel } = require('./anthropic-models.cjs');

/**
 * Preview model selection for a task type
 * @param {Object} options
 * @param {string} options.taskType - Task type to preview
 * @param {Array<string>} options.allModels - All available models (default: fetch from capability matrix)
 * @param {number} options.poolSize - How many models in rotation pool (default: 6)
 * @returns {Object} - Preview details
 */
async function previewModelSelection(options = {}) {
  const taskType = options.taskType || 'general';
  const poolSize = options.poolSize || 6;

  // Get all available models
  let allModels = options.allModels;
  if (!allModels) {
    try {
      const { getAllModels } = require('./model-capability-matrix.cjs');
      allModels = await getAllModels();
    } catch (error) {
      // Fallback to hardcoded list
      allModels = [
        'claude-opus-4.8', 'claude-sonnet-4.5', 'claude-haiku-4.5', 'claude-fable-5',
        'gpt-4o', 'gpt-4o-mini', 'gemini-pro', 'gemini-flash',
        'deepseek-coder', 'qwen-coder', 'gpt-3.5-turbo'
      ];
    }
  }

  // Get task rules
  const rules = getRulesForTask(taskType);

  // Apply filtering
  const beforeFiltering = [...allModels];
  const afterFiltering = applyRules(allModels, taskType);

  // Identify what was filtered out and why
  const filtered = {
    by_anthropic_only: [],
    by_whitelist: [],
    by_blacklist: [],
  };

  for (const model of beforeFiltering) {
    if (!afterFiltering.includes(model)) {
      // Figure out why it was filtered
      if (rules.anthropic_only && !isAnthropicModel(model)) {
        filtered.by_anthropic_only.push(model);
      } else if (rules.whitelist && rules.whitelist.length > 0) {
        const matches = rules.whitelist.some(pattern =>
          model.toLowerCase().includes(pattern.toLowerCase())
        );
        if (!matches) {
          filtered.by_whitelist.push(model);
        }
      } else if (rules.blacklist && rules.blacklist.length > 0) {
        const matches = rules.blacklist.some(pattern =>
          model.toLowerCase().includes(pattern.toLowerCase())
        );
        if (matches) {
          filtered.by_blacklist.push(model);
        }
      }
    }
  }

  // Select rotation pool (top N after filtering)
  const rotationPool = afterFiltering.slice(0, poolSize);

  // Determine which model would be selected next
  // (For dry-run, we don't have arbiter state, so just pick first)
  const selectedModel = rotationPool[0] || 'NO_MODELS_AVAILABLE';

  // Categorize models
  const anthropicModels = beforeFiltering.filter(isAnthropicModel);
  const thirdPartyModels = beforeFiltering.filter(m => !isAnthropicModel(m));

  return {
    taskType,
    rules: {
      anthropic_only: rules.anthropic_only || false,
      whitelist: rules.whitelist || [],
      blacklist: rules.blacklist || [],
      min_score: rules.min_score || 0,
      reason: rules.reason || 'No specific rules',
    },
    models: {
      total_available: beforeFiltering.length,
      anthropic_count: anthropicModels.length,
      third_party_count: thirdPartyModels.length,
      after_filtering: afterFiltering.length,
      rotation_pool_size: rotationPool.length,
    },
    categorized: {
      anthropic: anthropicModels,
      third_party: thirdPartyModels,
    },
    filtering: {
      removed_count: beforeFiltering.length - afterFiltering.length,
      by_anthropic_only: filtered.by_anthropic_only,
      by_whitelist: filtered.by_whitelist,
      by_blacklist: filtered.by_blacklist,
    },
    result: {
      rotation_pool: rotationPool,
      selected_model: selectedModel,
      all_filtered_models: afterFiltering,
    },
  };
}

/**
 * Compare multiple task types side-by-side
 * @param {Array<string>} taskTypes - Task types to compare
 * @returns {Object} - Comparison matrix
 */
async function compareTaskTypes(taskTypes) {
  const results = {};

  for (const taskType of taskTypes) {
    results[taskType] = await previewModelSelection({ taskType });
  }

  return results;
}

/**
 * Check if a specific model would be available for a task
 * @param {string} model - Model to check
 * @param {string} taskType - Task type
 * @returns {Object} - Availability details
 */
async function checkModelAvailability(model, taskType) {
  const preview = await previewModelSelection({ taskType });

  const available = preview.result.all_filtered_models.includes(model);
  const inPool = preview.result.rotation_pool.includes(model);

  let reason = '';
  if (!available) {
    if (preview.filtering.by_anthropic_only.includes(model)) {
      reason = 'Filtered by Anthropic-only requirement';
    } else if (preview.filtering.by_whitelist.includes(model)) {
      reason = 'Not in whitelist: ' + preview.rules.whitelist.join(', ');
    } else if (preview.filtering.by_blacklist.includes(model)) {
      reason = 'In blacklist: ' + preview.rules.blacklist.join(', ');
    } else {
      reason = 'Unknown reason';
    }
  } else if (!inPool) {
    reason = 'Available but not in top ' + preview.models.rotation_pool_size;
  } else {
    reason = 'Available in rotation pool';
  }

  return {
    model,
    taskType,
    available,
    in_rotation_pool: inPool,
    reason,
    pool_position: inPool ? preview.result.rotation_pool.indexOf(model) + 1 : null,
  };
}

module.exports = {
  previewModelSelection,
  compareTaskTypes,
  checkModelAvailability,
};
