/**
 * Consensus Pattern Adapter
 *
 * Retrieves and applies reasoning patterns extracted from multi-AI consensus.
 * Uses PostgreSQL learning.reasoning_patterns table.
 *
 * Architecture:
 * - PostgreSQL: Pattern storage with structured metadata
 * - Pattern matching: Category-based or semantic similarity (future)
 * - Context injection: Augment task descriptions with proven approaches
 *
 * Created: 2026-07-03
 */

const { Pool } = require('pg');

// Reuse connection pool from workflow-storage-adapter
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('PostgreSQL pool error:', err.message);
});

/**
 * Consensus Pattern Database Adapter
 */
class ConsensusPatternDB {
  constructor() {
    this.pool = pool;
  }

  /**
   * Get reasoning pattern by category
   *
   * @param {string} category - Problem category (e.g., 'debugging', 'optimization')
   * @param {number} minConfidence - Minimum pattern confidence (default: 0.7)
   * @returns {Promise<Object|null>} Pattern object or null if not found
   */
  async getPatternByCategory(category, minConfidence = 0.7) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT * FROM learning.reasoning_patterns
         WHERE problem_category = $1 AND pattern_confidence >= $2
         ORDER BY pattern_confidence DESC, created_at DESC
         LIMIT 1`,
        [category, minConfidence]
      );

      return result.rows.length > 0 ? result.rows[0] : null;
    } finally {
      client.release();
    }
  }

  /**
   * Get all patterns for multiple categories
   *
   * @param {string[]} categories - Array of problem categories
   * @param {number} minConfidence - Minimum pattern confidence (default: 0.7)
   * @returns {Promise<Array>} Array of pattern objects
   */
  async getPatternsByCategories(categories, minConfidence = 0.7) {
    if (!categories || categories.length === 0) {
      return [];
    }

    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT * FROM learning.reasoning_patterns
         WHERE problem_category = ANY($1::varchar[]) AND pattern_confidence >= $2
         ORDER BY problem_category, pattern_confidence DESC`,
        [categories, minConfidence]
      );

      return result.rows;
    } finally {
      client.release();
    }
  }

  /**
   * Get top N patterns by confidence
   *
   * @param {number} limit - Max patterns to return (default: 10)
   * @param {number} minConfidence - Minimum pattern confidence (default: 0.7)
   * @returns {Promise<Array>} Array of pattern objects
   */
  async getTopPatterns(limit = 10, minConfidence = 0.7) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT * FROM learning.reasoning_patterns
         WHERE pattern_confidence >= $1
         ORDER BY pattern_confidence DESC, created_at DESC
         LIMIT $2`,
        [minConfidence, limit]
      );

      return result.rows;
    } finally {
      client.release();
    }
  }

  /**
   * Get all available pattern categories
   *
   * @returns {Promise<Array<string>>} Array of category names
   */
  async getCategories() {
    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT DISTINCT problem_category
         FROM learning.reasoning_patterns
         ORDER BY problem_category`
      );

      return result.rows.map(row => row.problem_category);
    } finally {
      client.release();
    }
  }

  /**
   * Auto-detect pattern categories from task description
   *
   * @param {string} taskText - Task description
   * @returns {Array<string>} Detected categories
   */
  detectCategories(taskText) {
    if (!taskText || typeof taskText !== 'string') {
      return [];
    }

    const lower = taskText.toLowerCase();
    const categories = [];

    // Pattern detection heuristics
    const detectionRules = {
      'debugging': ['debug', 'bug', 'error', 'fix', 'broken', 'issue', 'problem'],
      'optimization': ['optimize', 'improve', 'performance', 'faster', 'efficient', 'reduce'],
      'code-complexity': ['complex', 'simplify', 'refactor', 'maintainability', 'readability'],
      'system-design': ['architecture', 'design', 'system', 'component', 'module', 'structure'],
      'multi-step-planning': ['plan', 'strategy', 'approach', 'steps', 'sequence', 'workflow'],
      'logical-deduction': ['logic', 'deduce', 'infer', 'conclude', 'prove', 'reason'],
      'causal-reasoning': ['cause', 'effect', 'why', 'because', 'reason for', 'lead to'],
      'constraint-satisfaction': ['constraint', 'requirement', 'must', 'cannot', 'limit', 'boundary'],
      'recursive-thinking': ['recursive', 'recursion', 'repeat', 'iterate', 'loop', 'self-reference'],
      'probability': ['probability', 'likely', 'chance', 'odds', 'risk', 'uncertain'],
      'game-theory': ['game', 'strategy', 'opponent', 'decision', 'payoff', 'equilibrium'],
      'ethical-reasoning': ['ethical', 'moral', 'right', 'wrong', 'should', 'responsibility'],
      'abstraction': ['abstract', 'generalize', 'pattern', 'concept', 'principle', 'model'],
      'analogy': ['similar', 'like', 'analogy', 'compare', 'parallel', 'metaphor'],
      'counterfactual': ['what if', 'alternative', 'instead', 'different', 'suppose', 'imagine'],
      'paradox-resolution': ['paradox', 'contradiction', 'conflict', 'inconsistent', 'puzzle'],
      'language-ambiguity': ['ambiguous', 'unclear', 'interpret', 'meaning', 'context'],
      'mathematical-proof': ['proof', 'theorem', 'lemma', 'demonstrate', 'mathematical'],
      'inference': ['infer', 'imply', 'suggest', 'indicate', 'evidence', 'conclusion'],
      'induction': ['induction', 'generalize', 'from examples', 'pattern', 'trend']
    };

    for (const [category, keywords] of Object.entries(detectionRules)) {
      if (keywords.some(keyword => lower.includes(keyword))) {
        categories.push(category);
      }
    }

    return categories;
  }

  /**
   * Get relevant patterns for a task
   *
   * @param {string} taskDescription - Task description
   * @param {number} minConfidence - Minimum pattern confidence (default: 0.7)
   * @param {number} limit - Max patterns to return (default: 3)
   * @returns {Promise<Array>} Array of relevant pattern objects
   */
  async getPatternsForTask(taskDescription, minConfidence = 0.7, limit = 3) {
    // Auto-detect categories
    const categories = this.detectCategories(taskDescription);

    if (categories.length === 0) {
      // No specific categories detected, return top patterns
      return this.getTopPatterns(limit, minConfidence);
    }

    // Get patterns for detected categories
    const patterns = await this.getPatternsByCategories(categories, minConfidence);

    // Limit results
    return patterns.slice(0, limit);
  }

  /**
   * Format pattern as context for task injection
   *
   * @param {Object} pattern - Pattern object from database
   * @returns {string} Formatted context text
   */
  formatPatternContext(pattern) {
    if (!pattern) return '';

    const steps = Array.isArray(pattern.common_reasoning_steps)
      ? pattern.common_reasoning_steps
      : (pattern.common_reasoning_steps?.steps || []);

    const errors = Array.isArray(pattern.error_patterns_to_avoid)
      ? pattern.error_patterns_to_avoid
      : (pattern.error_patterns_to_avoid?.errors || []);

    return `
## Proven Approach for ${pattern.problem_category} (${Math.round(pattern.pattern_confidence * 100)}% consensus, ${pattern.models_used} models)

**Successful Strategy:**
${pattern.successful_approach}

**Reasoning Steps:**
${steps.map((step, i) => `${i + 1}. ${step}`).join('\n')}

**Avoid These Errors:**
${errors.map(err => `- ${err}`).join('\n')}
`.trim();
  }

  /**
   * Augment task description with relevant patterns
   *
   * @param {string} taskDescription - Original task description
   * @param {number} minConfidence - Minimum pattern confidence (default: 0.7)
   * @param {number} maxPatterns - Max patterns to inject (default: 2)
   * @returns {Promise<string>} Augmented task description
   */
  async augmentTaskWithPatterns(taskDescription, minConfidence = 0.7, maxPatterns = 2) {
    const patterns = await this.getPatternsForTask(taskDescription, minConfidence, maxPatterns);

    if (patterns.length === 0) {
      return taskDescription;
    }

    const patternContext = patterns
      .map(p => this.formatPatternContext(p))
      .join('\n\n---\n\n');

    return `${taskDescription}

---

# Consensus-Validated Reasoning Patterns

The following approaches were validated by ${patterns[0]?.models_used || 'multiple'} AI models with high consensus:

${patternContext}

---

Apply these proven strategies to the task above.`;
  }

  /**
   * Get pattern statistics
   *
   * @returns {Promise<Object>} Statistics object
   */
  async getStats() {
    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT
           COUNT(*) as total_patterns,
           COUNT(DISTINCT problem_category) as unique_categories,
           ROUND(AVG(pattern_confidence), 2) as avg_confidence,
           ROUND(MIN(pattern_confidence), 2) as min_confidence,
           ROUND(MAX(pattern_confidence), 2) as max_confidence,
           ROUND(AVG(models_used), 1) as avg_models_used
         FROM learning.reasoning_patterns`
      );

      return result.rows[0];
    } finally {
      client.release();
    }
  }

  /**
   * Close connection pool
   */
  async close() {
    await this.pool.end();
  }
}

// Singleton instance
let _patternDB = null;

/**
 * Get singleton consensus pattern instance
 */
function getConsensusPatterns() {
  if (!_patternDB) _patternDB = new ConsensusPatternDB();
  return _patternDB;
}

module.exports = {
  ConsensusPatternDB,
  getConsensusPatterns,
  pool
};
