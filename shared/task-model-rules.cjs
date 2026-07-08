/**
 * Task-Specific Model Rules
 *
 * Defines which models can be used for specific task types.
 * Critical for:
 * - Compliance (Red Hat work MUST use Anthropic models only)
 * - Quality (security audits need strong models)
 * - Cost optimization (don't use Opus for documentation)
 */

const { ANTHROPIC_MODELS, isAnthropicModel } = require('./anthropic-models.cjs');

/**
 * Rule format:
 * {
 *   whitelist: Array<string> - ONLY these models allowed (pattern matching)
 *   blacklist: Array<string> - NEVER these models (pattern matching)
 *   min_score: number - Minimum capability score (0.0-1.0)
 *   anthropic_only: boolean - ONLY Anthropic models (for compliance)
 *   reason: string - Why these rules exist
 * }
 */
const TASK_MODEL_RULES = {
  // ============================================================
  // RED HAT WORK - ANTHROPIC ONLY (COMPLIANCE REQUIREMENT)
  // ============================================================
  redhat_code_review: {
    anthropic_only: true,
    whitelist: ['opus', 'sonnet'],  // Best reasoning for code review
    blacklist: ['haiku', 'fable'],  // Too small for thorough code review
    min_score: 0.8,
    reason: 'Red Hat proprietary code - Anthropic models only, strong reasoning required'
  },

  redhat_security_audit: {
    anthropic_only: true,
    whitelist: ['opus', 'sonnet'],  // Maximum accuracy for security
    blacklist: ['haiku', 'fable'],
    min_score: 0.9,
    reason: 'Red Hat security - Anthropic models only, highest accuracy required'
  },

  redhat_architecture_review: {
    anthropic_only: true,
    whitelist: ['opus', 'sonnet'],
    min_score: 0.8,
    reason: 'Red Hat architecture - Anthropic models only, strong reasoning required'
  },

  redhat_bug_detection: {
    anthropic_only: true,
    whitelist: ['opus', 'sonnet'],
    min_score: 0.8,
    reason: 'Red Hat bug detection - Anthropic models only'
  },

  // ============================================================
  // GENERAL CODE WORK - Allow coding-specialized models
  // ============================================================
  code_review: {
    whitelist: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder'],
    blacklist: ['fable', 'haiku', 'gpt-3.5'],  // Too small
    min_score: 0.7,
    reason: 'Code review requires strong reasoning and code understanding'
  },

  security_audit: {
    whitelist: ['opus', 'sonnet', 'gpt-4o', 'deepseek-coder'],
    blacklist: ['fable', 'haiku', 'gemini-flash', 'gpt-3.5'],
    min_score: 0.85,
    reason: 'Security requires highest accuracy - no small/fast models'
  },

  architecture_review: {
    whitelist: ['opus', 'sonnet', 'gpt-4o'],
    blacklist: ['fable', 'haiku'],
    min_score: 0.75,
    reason: 'Architecture decisions need strong reasoning'
  },

  bug_detection: {
    whitelist: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder', 'gpt-4o'],
    blacklist: ['fable', 'haiku'],
    min_score: 0.7,
    reason: 'Bug detection needs code understanding'
  },

  code_generation: {
    whitelist: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder'],
    min_score: 0.6,
    reason: 'Code generation benefits from specialized models'
  },

  // ============================================================
  // RESEARCH & ANALYSIS - Allow all strong models
  // ============================================================
  research: {
    blacklist: ['haiku', 'fable', 'gpt-3.5', 'gemini-flash'],  // Too small
    min_score: 0.6,
    reason: 'Research needs thorough analysis'
  },

  fact_checking: {
    whitelist: ['opus', 'sonnet', 'gpt-4o', 'gemini-pro'],
    min_score: 0.7,
    reason: 'Fact checking requires accuracy'
  },

  data_analysis: {
    blacklist: ['fable', 'haiku'],
    min_score: 0.6,
    reason: 'Data analysis needs reasoning capability'
  },

  // ============================================================
  // LOW-STAKES WORK - Optimize for cost
  // ============================================================
  documentation: {
    blacklist: ['opus'],  // Too expensive for docs
    min_score: 0.5,
    reason: 'Documentation doesn\'t need flagship models'
  },

  creative_writing: {
    blacklist: ['opus'],  // Save Opus for technical work
    min_score: 0.4,
    reason: 'Creative writing doesn\'t need highest-tier models'
  },

  // ============================================================
  // CONSENSUS & ARBITRATION - Need diversity
  // ============================================================
  consensus: {
    // No restrictions - want diverse perspectives
    min_score: 0.5,
    reason: 'Consensus benefits from diverse model perspectives'
  },

  arbitration: {
    whitelist: ['opus', 'sonnet', 'gpt-4o'],  // Strong reasoning for final decisions
    min_score: 0.75,
    reason: 'Arbitration needs strong reasoning to synthesize diverse inputs'
  },

  // ============================================================
  // OPTIMIZATION & REFACTORING
  // ============================================================
  optimization: {
    whitelist: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder'],
    min_score: 0.7,
    reason: 'Optimization requires deep code understanding'
  },

  refactoring: {
    whitelist: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder'],
    min_score: 0.7,
    reason: 'Refactoring requires understanding code structure'
  },

  // ============================================================
  // TESTING
  // ============================================================
  testing: {
    whitelist: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder', 'gpt-4o'],
    min_score: 0.65,
    reason: 'Test generation requires code understanding'
  },

  // ============================================================
  // DEFAULT - Minimal restrictions
  // ============================================================
  general: {
    blacklist: [],  // No restrictions
    min_score: 0.3,
    reason: 'General tasks can use any model'
  }
};

/**
 * Get rules for a specific task type
 * @param {string} taskType - Task type (e.g., 'code_review', 'redhat_code_review')
 * @returns {Object} - Rules object
 */
function getRulesForTask(taskType) {
  return TASK_MODEL_RULES[taskType] || TASK_MODEL_RULES.general;
}

/**
 * Check if task type requires Anthropic-only models
 * @param {string} taskType
 * @returns {boolean}
 */
function requiresAnthropicOnly(taskType) {
  const rules = getRulesForTask(taskType);
  return rules.anthropic_only === true;
}

/**
 * Apply rules to filter models
 * @param {Array<string>} models - All available models
 * @param {string} taskType - Task type
 * @returns {Array<string>} - Filtered models that pass rules
 */
function applyRules(models, taskType) {
  const rules = getRulesForTask(taskType);
  let filtered = [...models];

  // Anthropic-only filter (compliance requirement)
  if (rules.anthropic_only) {
    filtered = filtered.filter(isAnthropicModel);
  }

  // Whitelist filter (ONLY these patterns allowed)
  if (rules.whitelist && rules.whitelist.length > 0) {
    filtered = filtered.filter(model =>
      rules.whitelist.some(pattern =>
        model.toLowerCase().includes(pattern.toLowerCase())
      )
    );
  }

  // Blacklist filter (NEVER these patterns)
  if (rules.blacklist && rules.blacklist.length > 0) {
    filtered = filtered.filter(model =>
      !rules.blacklist.some(pattern =>
        model.toLowerCase().includes(pattern.toLowerCase())
      )
    );
  }

  // If no models pass filters, return original list (safety fallback)
  if (filtered.length === 0) {
    console.warn(`[task-model-rules] No models passed filters for ${taskType}, using all models`);
    return models;
  }

  return filtered;
}

/**
 * Get explanation of why models were filtered
 * @param {string} taskType
 * @returns {string}
 */
function getFilterReason(taskType) {
  const rules = getRulesForTask(taskType);
  return rules.reason || 'No specific rules';
}

module.exports = {
  TASK_MODEL_RULES,
  getRulesForTask,
  requiresAnthropicOnly,
  applyRules,
  getFilterReason
};
