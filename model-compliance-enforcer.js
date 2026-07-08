#!/usr/bin/env node
/**
 * Model Compliance Enforcer
 *
 * Prevents AI model compliance violations by enforcing path-based restrictions.
 *
 * Rules:
 * - Red Hat repos: ONLY Anthropic (4 models)
 * - Personal repos: ALL models allowed
 * - Block OpenAI/Google/DeepSeek for Red Hat code
 *
 * Usage:
 *   const { validateModelForPath, getRestrictedModels, getSafeModels } = require('./model-compliance-enforcer.js');
 *   const result = validateModelForPath('/home/sfloess/Development/redhat/scm/gitlab/...', 'gpt-4o');
 *   if (!result.allowed) throw new Error(result.reason);
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// CONFIGURATION
// ============================================================================

const COMPLIANCE_RULES = {
  // Red Hat proprietary paths (RESTRICTED)
  redhat: {
    paths: [
      '/home/sfloess/Development/redhat/scm/gitlab',
      '/home/sfloess/Development/redhat',
      '~/Development/redhat/scm/gitlab',
      '~/Development/redhat'
    ],
    allowedModels: {
      // Anthropic Cloud (4) - ONLY allowed models for Red Hat
      anthropic: [
        'claude-fable-5', 'fable',
        'claude-opus-4-8', 'opus',
        'claude-sonnet-4-6', 'sonnet', 'claude-sonnet-4-5',
        'claude-haiku-4-5', 'haiku'
      ]
    },
    blockedModels: {
      openai: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-4', 'gpt-3.5'],
      google: ['gemini-pro', 'gemini-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
      deepseek: ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-chat'],
      cerebras: ['gpt-oss-120b', 'zai-glm-4.7', 'llama-3.3-70b-cerebras'],
      groq: ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile'],
      openrouter: ['*'], // ALL OpenRouter models blocked
      cloudflare: ['*']  // ALL Cloudflare Workers AI blocked
    },
    reason: 'Red Hat compliance - proprietary code cannot be sent to external vendor APIs'
  },

  // Personal repos (UNRESTRICTED)
  personal: {
    paths: [
      '/home/sfloess/Development/github',
      '/home/sfloess/Development/personal/scm/github',
      '~/Development/github',
      '~/Development/personal/scm/github'
    ],
    allowedModels: 'ALL',
    reason: 'Personal GitHub repositories - no restrictions'
  }
};

// ============================================================================
// PATH NORMALIZATION
// ============================================================================

function normalizePath(inputPath) {
  // Expand ~ to home directory
  if (inputPath.startsWith('~')) {
    const homeDir = process.env.HOME || '/home/sfloess';
    inputPath = inputPath.replace('~', homeDir);
  }
  return path.resolve(inputPath);
}

// ============================================================================
// PATH CLASSIFICATION
// ============================================================================

function classifyPath(targetPath) {
  const normalized = normalizePath(targetPath);

  // Check Red Hat paths (MOST RESTRICTIVE)
  for (const redhatPath of COMPLIANCE_RULES.redhat.paths) {
    const normalizedRule = normalizePath(redhatPath);
    if (normalized.startsWith(normalizedRule)) {
      return {
        type: 'redhat',
        rule: COMPLIANCE_RULES.redhat,
        matchedPath: normalizedRule
      };
    }
  }

  // Check personal paths
  for (const personalPath of COMPLIANCE_RULES.personal.paths) {
    const normalizedRule = normalizePath(personalPath);
    if (normalized.startsWith(normalizedRule)) {
      return {
        type: 'personal',
        rule: COMPLIANCE_RULES.personal,
        matchedPath: normalizedRule
      };
    }
  }

  // Default to personal (unrestricted)
  return {
    type: 'personal',
    rule: COMPLIANCE_RULES.personal,
    matchedPath: null
  };
}

// ============================================================================
// MODEL VALIDATION
// ============================================================================

function normalizeModelName(model) {
  // Handle various model name formats
  const lower = model.toLowerCase();

  // Map common aliases
  const aliases = {
    'fable': 'claude-fable-5',
    'opus': 'claude-opus-4-8',
    'sonnet': 'claude-sonnet-4-6',
    'haiku': 'claude-haiku-4-5',
    'gpt4o': 'gpt-4o',
    'gpt4': 'gpt-4',
    'gemini': 'gemini-pro'
  };

  return aliases[lower] || lower;
}

function isModelAllowed(model, rule) {
  // Personal repos: ALL models allowed
  if (rule === COMPLIANCE_RULES.personal) {
    return { allowed: true, reason: 'Personal repository - no restrictions' };
  }

  // Red Hat repos: Check allowed list
  const normalized = normalizeModelName(model);
  const allowed = rule.allowedModels;

  // Check Anthropic models
  const allAllowed = allowed.anthropic.map(m => m.toLowerCase());

  if (allAllowed.includes(normalized)) {
    return { allowed: true, reason: 'Model on Red Hat allowlist' };
  }

  // Check blocked categories
  for (const [vendor, models] of Object.entries(rule.blockedModels)) {
    if (models.includes('*')) {
      // Wildcard block (e.g., all OpenRouter)
      if (normalized.includes(vendor)) {
        return {
          allowed: false,
          reason: `${vendor} models blocked for Red Hat code: ${rule.reason}`
        };
      }
    } else {
      // Specific model block
      const blockedLower = models.map(m => m.toLowerCase());
      if (blockedLower.includes(normalized)) {
        return {
          allowed: false,
          reason: `${model} blocked for Red Hat code: ${rule.reason}`
        };
      }
    }
  }

  // Model not explicitly allowed OR blocked = default BLOCK for safety
  return {
    allowed: false,
    reason: `Model '${model}' not on Red Hat allowlist (4 Anthropic models only: fable, opus, sonnet, haiku).`
  };
}

// ============================================================================
// PUBLIC API
// ============================================================================

function validateModelForPath(targetPath, model) {
  const classification = classifyPath(targetPath);
  const validation = isModelAllowed(model, classification.rule);

  return {
    allowed: validation.allowed,
    reason: validation.reason,
    pathType: classification.type,
    matchedPath: classification.matchedPath,
    model: model,
    normalizedModel: normalizeModelName(model)
  };
}

function getRestrictedModels(targetPath) {
  const classification = classifyPath(targetPath);

  if (classification.type === 'personal') {
    return []; // No restrictions
  }

  return classification.rule.blockedModels;
}

function getSafeModels(targetPath) {
  const classification = classifyPath(targetPath);

  if (classification.type === 'personal') {
    return 'ALL';
  }

  return classification.rule.allowedModels;
}

function getAllowedModelsFlat(targetPath) {
  const classification = classifyPath(targetPath);

  if (classification.type === 'personal') {
    return ['ALL'];
  }

  const allowed = classification.rule.allowedModels;
  return allowed.anthropic;
}

// ============================================================================
// CLI INTERFACE
// ============================================================================

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.error('Usage: model-compliance-enforcer.js <path> <model>');
    console.error('Example: model-compliance-enforcer.js ~/Development/redhat/scm/gitlab/cee/sfloess/disseminator gpt-4o');
    process.exit(1);
  }

  const [targetPath, model] = args;
  const result = validateModelForPath(targetPath, model);

  console.log(JSON.stringify(result, null, 2));

  if (!result.allowed) {
    console.error(`\n❌ COMPLIANCE VIOLATION: ${result.reason}`);
    console.error(`\nAllowed models for ${result.pathType}:`);
    const allowed = getAllowedModelsFlat(targetPath);
    if (allowed[0] === 'ALL') {
      console.error('  - ALL models allowed (personal repo)');
    } else {
      console.error(`  - ${allowed.length} models: ${allowed.join(', ')}`);
    }
    process.exit(1);
  } else {
    console.log(`\n✅ ALLOWED: ${result.reason}`);
    process.exit(0);
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  validateModelForPath,
  getRestrictedModels,
  getSafeModels,
  getAllowedModelsFlat,
  classifyPath,
  COMPLIANCE_RULES
};
