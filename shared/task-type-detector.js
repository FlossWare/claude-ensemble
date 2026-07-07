/**
 * Task Type Detector
 *
 * Analyzes prompt and context to determine the task type for optimal arbiter selection.
 * Uses simple keyword matching for speed - no ML dependencies.
 *
 * Usage:
 *   const { detectTaskType } = require('./shared/task-type-detector.js');
 *   const result = detectTaskType('Review this code for bugs', 'function foo() { ... }');
 *   // => { type: 'bug_detection', confidence: 0.85, secondaryTypes: ['code_review'] }
 */

// Task type definitions with keywords and patterns
const TASK_PATTERNS = {
  code_generation: {
    keywords: ['write', 'create', 'implement', 'generate', 'build', 'develop', 'code'],
    phrases: ['write code', 'create function', 'implement feature', 'generate script', 'build tool'],
    weight: 1.0
  },

  code_review: {
    keywords: ['review', 'check', 'analyze', 'examine', 'inspect', 'evaluate'],
    phrases: ['review code', 'code review', 'check implementation', 'analyze code'],
    contexts: ['diff', 'pull request', 'pr', 'commit', 'changes'],
    weight: 1.0
  },

  bug_detection: {
    keywords: ['bug', 'error', 'issue', 'problem', 'fault', 'defect', 'broken', 'failing', 'crash'],
    phrases: ['find bugs', 'detect errors', 'debug', 'troubleshoot', 'fix issue'],
    weight: 1.2  // Higher priority
  },

  security_audit: {
    keywords: ['security', 'vulnerability', 'exploit', 'injection', 'xss', 'csrf', 'authentication', 'authorization', 'sanitize', 'validate'],
    phrases: ['security review', 'security audit', 'vulnerability scan', 'penetration test', 'secure code'],
    weight: 1.3  // High priority
  },

  architecture_review: {
    keywords: ['architecture', 'design', 'structure', 'pattern', 'scalability', 'maintainability', 'system'],
    phrases: ['architecture review', 'design patterns', 'system design', 'refactor', 'restructure'],
    weight: 1.0
  },

  research: {
    keywords: ['research', 'investigate', 'explore', 'study', 'learn', 'understand', 'find out'],
    phrases: ['deep research', 'investigate topic', 'explore options', 'literature review'],
    weight: 0.9
  },

  fact_checking: {
    keywords: ['verify', 'fact', 'true', 'accurate', 'validate', 'confirm', 'check'],
    phrases: ['fact check', 'verify claim', 'validate information', 'confirm accuracy'],
    weight: 1.0
  },

  consensus: {
    keywords: ['consensus', 'vote', 'decide', 'choose', 'select', 'compare', 'evaluate'],
    phrases: ['reach consensus', 'multi-model', 'which is better', 'compare options'],
    weight: 1.0
  },

  creative_writing: {
    keywords: ['write', 'story', 'article', 'blog', 'content', 'creative', 'narrative', 'essay'],
    phrases: ['write article', 'creative writing', 'tell story', 'write blog'],
    negativeKeywords: ['code', 'function', 'bug', 'error'],  // Exclude if code-related
    weight: 0.8
  },

  math_reasoning: {
    keywords: ['calculate', 'solve', 'math', 'equation', 'formula', 'compute', 'number'],
    phrases: ['solve equation', 'calculate result', 'math problem', 'numerical'],
    weight: 1.0
  },

  documentation: {
    keywords: ['document', 'readme', 'guide', 'tutorial', 'documentation', 'explain', 'describe'],
    phrases: ['write documentation', 'create readme', 'document code', 'explain how'],
    weight: 0.9
  },

  testing: {
    keywords: ['test', 'unittest', 'integration', 'coverage', 'spec', 'assertion'],
    phrases: ['write tests', 'unit test', 'test coverage', 'integration test'],
    weight: 1.0
  },

  optimization: {
    keywords: ['optimize', 'performance', 'speed', 'efficiency', 'fast', 'slow', 'bottleneck'],
    phrases: ['improve performance', 'optimize code', 'speed up', 'reduce memory'],
    weight: 1.1
  },

  refactoring: {
    keywords: ['refactor', 'cleanup', 'simplify', 'improve', 'reorganize', 'restructure'],
    phrases: ['refactor code', 'clean up', 'simplify logic', 'improve readability'],
    weight: 1.0
  },

  data_analysis: {
    keywords: ['analyze', 'data', 'statistics', 'metrics', 'trends', 'insights', 'visualization'],
    phrases: ['analyze data', 'data analysis', 'statistical analysis', 'visualize data'],
    weight: 1.0
  }
};

/**
 * Normalize text for matching
 */
function normalizeText(text) {
  if (!text) return '';
  return text.toLowerCase().trim().replace(/\s+/g, ' ');
}

/**
 * Score a task type against the prompt and context
 */
function scoreTaskType(taskType, pattern, normalizedPrompt, normalizedContext) {
  let score = 0;
  const combinedText = `${normalizedPrompt} ${normalizedContext}`;

  // Check negative keywords first (exclusion)
  if (pattern.negativeKeywords) {
    for (const negKeyword of pattern.negativeKeywords) {
      if (combinedText.includes(negKeyword)) {
        return 0;  // Exclude this task type
      }
    }
  }

  // Check keywords (single words)
  if (pattern.keywords) {
    for (const keyword of pattern.keywords) {
      // Check prompt
      if (normalizedPrompt.includes(keyword)) {
        score += 1.0;
      }
      // Check context (half weight)
      if (normalizedContext.includes(keyword)) {
        score += 0.5;
      }
    }
  }

  // Check phrases (higher weight)
  if (pattern.phrases) {
    for (const phrase of pattern.phrases) {
      if (normalizedPrompt.includes(phrase)) {
        score += 2.0;  // Phrases are stronger signals
      }
      if (normalizedContext.includes(phrase)) {
        score += 1.0;
      }
    }
  }

  // Check context-specific keywords
  if (pattern.contexts) {
    for (const ctx of pattern.contexts) {
      if (normalizedContext.includes(ctx)) {
        score += 1.5;
      }
    }
  }

  // Apply weight multiplier
  score *= (pattern.weight || 1.0);

  return score;
}

/**
 * Detect task type from prompt and context
 *
 * @param {string} prompt - The task prompt/description
 * @param {string} [context=''] - Optional context (code, diff, etc.)
 * @returns {object} { type: string, confidence: number, secondaryTypes: string[], scores: object }
 */
function detectTaskType(prompt, context = '') {
  if (!prompt || typeof prompt !== 'string') {
    return {
      type: 'general',
      confidence: 0.0,
      secondaryTypes: [],
      scores: {}
    };
  }

  const normalizedPrompt = normalizeText(prompt);
  const normalizedContext = normalizeText(context);

  // Score all task types
  const scores = {};
  for (const [taskType, pattern] of Object.entries(TASK_PATTERNS)) {
    scores[taskType] = scoreTaskType(taskType, pattern, normalizedPrompt, normalizedContext);
  }

  // Sort by score
  const sorted = Object.entries(scores)
    .filter(([_, score]) => score > 0)
    .sort((a, b) => b[1] - a[1]);

  if (sorted.length === 0) {
    return {
      type: 'general',
      confidence: 0.0,
      secondaryTypes: [],
      scores
    };
  }

  const [primaryType, primaryScore] = sorted[0];

  // Calculate confidence (normalize to 0-1 range)
  // Max realistic score is around 10-15 for strong matches
  const confidence = Math.min(primaryScore / 10.0, 1.0);

  // Identify secondary types (within 70% of primary score)
  const secondaryTypes = sorted
    .slice(1)
    .filter(([_, score]) => score >= primaryScore * 0.7)
    .map(([type, _]) => type);

  return {
    type: primaryType,
    confidence: parseFloat(confidence.toFixed(2)),
    secondaryTypes,
    scores
  };
}

/**
 * Get recommended arbiter configuration for a task type
 */
function getArbiterConfig(taskType) {
  const configs = {
    code_generation: {
      models: ['opus', 'sonnet', 'deepseek-coder'],
      minConsensus: 2,
      strategy: 'majority_vote'
    },
    code_review: {
      models: ['opus', 'sonnet', 'gpt4o'],
      minConsensus: 2,
      strategy: 'weighted_consensus'
    },
    bug_detection: {
      models: ['opus', 'sonnet', 'deepseek-coder', 'gpt4o'],
      minConsensus: 3,
      strategy: 'unanimous_for_critical'
    },
    security_audit: {
      models: ['opus', 'gpt4o', 'sonnet', 'gemini'],
      minConsensus: 3,
      strategy: 'conservative_consensus'  // Err on side of flagging issues
    },
    architecture_review: {
      models: ['opus', 'sonnet', 'gpt4o'],
      minConsensus: 2,
      strategy: 'weighted_consensus'
    },
    research: {
      models: ['opus', 'sonnet', 'gemini', 'gpt4o'],
      minConsensus: 2,
      strategy: 'diversity_weighted'
    },
    fact_checking: {
      models: ['opus', 'gpt4o', 'gemini', 'sonnet'],
      minConsensus: 3,
      strategy: 'strict_consensus'
    },
    consensus: {
      models: ['opus', 'sonnet', 'haiku', 'gpt4o', 'gemini', 'fable'],
      minConsensus: 4,
      strategy: 'full_consensus'
    },
    creative_writing: {
      models: ['opus', 'sonnet', 'gpt4o'],
      minConsensus: 1,
      strategy: 'single_best'
    },
    math_reasoning: {
      models: ['opus', 'gpt4o', 'sonnet'],
      minConsensus: 2,
      strategy: 'majority_vote'
    },
    general: {
      models: ['opus', 'sonnet', 'gpt4o'],
      minConsensus: 2,
      strategy: 'majority_vote'
    }
  };

  return configs[taskType] || configs.general;
}

module.exports = {
  detectTaskType,
  getArbiterConfig,
  TASK_PATTERNS  // Export for testing/extension
};
