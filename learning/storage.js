/**
 * Storage module for workflow learnings
 * Integrates ai-extract-learning with PostgreSQL workflows.learnings table
 */

const { getDB } = require('./postgres-adapter');
const { generateEmbedding } = require('./embeddings');

/**
 * Store learnings from ai-extract-learning workflow
 * @param {string} runId - Unique workflow run identifier
 * @param {object} learnings - Learning extraction result from ai-extract-learning
 * @param {object} options - Additional options
 * @param {number} options.executionId - Foreign key to monitoring.execution_summary
 * @param {string} options.workflowName - Name of workflow that generated learnings
 * @param {string} options.strategy - Strategy used for extraction
 * @param {number} options.qualityScore - Optional quality score
 * @returns {Promise<number>} ID of inserted learning record
 */
async function storeLearnings(runId, learnings, options = {}) {
  const db = getDB();
  const {
    executionId = null,
    workflowName = 'unknown',
    strategy = 'base',
    qualityScore = null
  } = options;

  // Extract structured fields from learnings object
  const userPreferences = learnings.user_patterns?.preferences || null;
  const expertiseLevels = learnings.user_patterns?.expertise_level || null;
  const workflowUsage = learnings.user_patterns?.workflow_usage || null;
  const commonBugs = learnings.code_patterns?.common_bugs || null;
  const architectureInsights = learnings.code_patterns?.architecture_insights || null;
  const techStack = learnings.code_patterns?.tech_stack || null;
  const qualityTrends = learnings.code_patterns?.quality_trends || null;
  const recommendations = learnings.recommendations || null;
  const memorySuggestions = learnings.memory_suggestions || null;

  // Generate text representation for embedding
  const learningText = buildLearningText(learnings);

  // Generate embedding for similarity search
  let embedding = null;
  try {
    embedding = await generateEmbedding(learningText);
  } catch (err) {
    console.warn('[storage] Failed to generate embedding:', err.message);
    // Continue without embedding - not critical
  }

  // Insert into database
  const sql = `
    INSERT INTO workflows.learnings (
      run_id, execution_id, workflow_name, timestamp,
      user_preferences, expertise_levels, workflow_usage,
      common_bugs, architecture_insights, tech_stack, quality_trends,
      recommendations, memory_suggestions,
      learnings, embedding, strategy, quality_score
    )
    VALUES (
      $1, $2, $3, NOW(),
      $4, $5, $6,
      $7, $8, $9, $10,
      $11, $12,
      $13, $14, $15, $16
    )
    RETURNING id
  `;

  const params = [
    runId,
    executionId,
    workflowName,
    userPreferences ? JSON.stringify(userPreferences) : null,
    expertiseLevels ? JSON.stringify(expertiseLevels) : null,
    workflowUsage ? JSON.stringify(workflowUsage) : null,
    commonBugs ? JSON.stringify(commonBugs) : null,
    architectureInsights ? JSON.stringify(architectureInsights) : null,
    techStack ? JSON.stringify(techStack) : null,
    qualityTrends ? JSON.stringify(qualityTrends) : null,
    recommendations ? JSON.stringify(recommendations) : null,
    memorySuggestions ? JSON.stringify(memorySuggestions) : null,
    JSON.stringify(learnings),
    embedding ? `[${embedding.join(',')}]` : null,  // Format as PostgreSQL array
    strategy,
    qualityScore
  ];

  const result = await db.query(sql, params);
  const learningId = result[0].id;

  console.log(`[storage] Stored learning #${learningId} for run ${runId}`);
  return learningId;
}

/**
 * Query learnings by workflow name
 * @param {string} workflowName - Workflow name to filter by
 * @param {number} limit - Max results to return
 * @returns {Promise<Array>} Array of learning records
 */
async function getLearningsByWorkflow(workflowName, limit = 100) {
  const db = getDB();
  const sql = `
    SELECT * FROM workflows.learnings
    WHERE workflow_name = $1
    ORDER BY timestamp DESC
    LIMIT $2
  `;
  return await db.query(sql, [workflowName, limit]);
}

/**
 * Find similar learnings using vector similarity
 * @param {string} queryText - Text to search for
 * @param {number} limit - Max results to return
 * @param {object} filters - Optional filters (workflow_name, min_quality_score)
 * @returns {Promise<Array>} Array of similar learnings with distance scores
 */
async function findSimilarLearnings(queryText, limit = 10, filters = {}) {
  const db = getDB();

  // Generate embedding for query
  const embedding = await generateEmbedding(queryText);

  let sql = `
    SELECT
      *,
      embedding <=> $1::vector as distance
    FROM workflows.learnings
    WHERE embedding IS NOT NULL
  `;
  const params = [`[${embedding.join(',')}]`];
  let paramIdx = 2;

  // Apply filters
  if (filters.workflowName) {
    sql += ` AND workflow_name = $${paramIdx}`;
    params.push(filters.workflowName);
    paramIdx++;
  }

  if (filters.minQualityScore !== undefined) {
    sql += ` AND quality_score >= $${paramIdx}`;
    params.push(filters.minQualityScore);
    paramIdx++;
  }

  sql += ` ORDER BY embedding <=> $1::vector LIMIT $${paramIdx}`;
  params.push(limit);

  return await db.query(sql, params);
}

/**
 * Get recent learnings across all workflows
 * @param {number} limit - Max results to return
 * @returns {Promise<Array>} Array of recent learnings
 */
async function getRecentLearnings(limit = 50) {
  const db = getDB();
  const sql = `
    SELECT * FROM workflows.recent_learnings
    LIMIT $1
  `;
  return await db.query(sql, [limit]);
}

/**
 * Get learning statistics by workflow
 * @returns {Promise<Array>} Array of workflow stats
 */
async function getLearningStats() {
  const db = getDB();
  const sql = 'SELECT * FROM workflows.learning_stats ORDER BY total_learnings DESC';
  return await db.query(sql);
}

/**
 * Build text representation of learnings for embedding
 * @param {object} learnings - Learning object
 * @returns {string} Text representation
 */
function buildLearningText(learnings) {
  const parts = [];

  // User patterns
  if (learnings.user_patterns?.preferences?.length > 0) {
    parts.push('User preferences: ' + learnings.user_patterns.preferences.join('; '));
  }

  if (learnings.user_patterns?.expertise_level) {
    const expertise = Object.entries(learnings.user_patterns.expertise_level)
      .map(([domain, level]) => `${domain}: ${level}`)
      .join('; ');
    parts.push('Expertise levels: ' + expertise);
  }

  // Code patterns
  if (learnings.code_patterns?.common_bugs?.length > 0) {
    parts.push('Common bugs: ' + learnings.code_patterns.common_bugs.join('; '));
  }

  if (learnings.code_patterns?.architecture_insights?.length > 0) {
    parts.push('Architecture: ' + learnings.code_patterns.architecture_insights.join('; '));
  }

  if (learnings.code_patterns?.tech_stack?.length > 0) {
    parts.push('Tech stack: ' + learnings.code_patterns.tech_stack.join('; '));
  }

  // Recommendations
  if (learnings.recommendations?.length > 0) {
    parts.push('Recommendations: ' + learnings.recommendations.join('; '));
  }

  return parts.join('\n');
}

module.exports = {
  storeLearnings,
  getLearningsByWorkflow,
  findSimilarLearnings,
  getRecentLearnings,
  getLearningStats,
  buildLearningText
};
