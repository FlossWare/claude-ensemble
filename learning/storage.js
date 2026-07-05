/**
 * Storage module for workflow learnings
 * Integrates ai-extract-learning with PostgreSQL workflows.learnings table
 *
 * SCHEMA: workflows.* (aio-01:5433/learning)
 * - learning_id: UUID primary key
 * - execution_id: UUID foreign key to workflows.executions
 * - embedding: vector(768) - REQUIRES 768-dim embeddings
 * - impact_score: NUMERIC(5,4) (replaces old 'importance')
 * - verified: BOOLEAN
 * - created_at: TIMESTAMP (replaces old 'timestamp')
 */

const { getDB } = require('./postgres-adapter');
const { generateEmbedding } = require('./embeddings'); // MUST return 768-dim vectors

/**
 * Store learnings from ai-extract-learning workflow
 * @param {string} runId - Unique workflow run identifier (stored in metadata.run_id)
 * @param {object} learnings - Learning extraction result from ai-extract-learning
 * @param {object} options - Additional options
 * @param {string} options.executionId - REQUIRED: UUID foreign key to workflows.executions
 * @param {string} options.workflowName - REQUIRED: Name of workflow that generated learnings
 * @param {string} options.strategy - Strategy used for extraction (stored in context)
 * @param {number} options.qualityScore - Optional quality score (stored in context)
 * @returns {Promise<string>} UUID of inserted learning record (learning_id)
 */
async function storeLearnings(runId, learnings, options = {}) {
  const db = getDB();
  const {
    executionId = null,
    workflowName = 'unknown',
    strategy = 'base',
    qualityScore = null
  } = options;

  // Build normalized learning structure for NEW schema
  // learning_type: 'pattern' | 'failure' | 'optimization' | 'insight' | 'best_practice'
  const learningType = 'insight'; // Default type
  const title = buildTitle(learnings);
  const description = buildDescription(learnings);

  // Build context object from all learning fields (JSONB column)
  const context = {
    user_patterns: learnings.user_patterns || {},
    code_patterns: learnings.code_patterns || {},
    recommendations: learnings.recommendations || [],
    memory_suggestions: learnings.memory_suggestions || [],
    strategy: strategy,
    quality_score: qualityScore,
    run_id: runId // Preserve backwards compatibility
  };

  // Generate text representation for embedding
  const learningText = buildLearningText(learnings);

  // Generate embedding for similarity search (MUST be 768-dim for vector(768) column)
  let embedding = null;
  try {
    embedding = await generateEmbedding(learningText);
    if (embedding && embedding.length !== 768) {
      console.warn(`[storage] WARNING: Expected 768-dim embedding, got ${embedding.length}-dim. Database may reject.`);
    }
  } catch (err) {
    console.warn('[storage] Failed to generate embedding:', err.message);
    // Continue without embedding - not critical (embedding column allows NULL)
  }

  // Calculate impact_score (NUMERIC(5,4) - replaces old 'importance' field)
  // Range: 0.0000 to 1.0000 (4 decimal places)
  const impactScore = learnings.recommendations?.length > 0
    ? Math.min(1.0, learnings.recommendations.length * 0.2)
    : 0.5;

  // Confidence (NUMERIC(5,4) - range: 0.0000 to 1.0000)
  const confidence = qualityScore || 0.8;

  // Insert into database using NEW schema
  const sql = `
    INSERT INTO workflows.learnings (
      execution_id, workflow_name, learning_type,
      title, description, embedding, context,
      impact_score, confidence, verified, metadata
    )
    VALUES (
      $1, $2, $3,
      $4, $5, $6, $7,
      $8, $9, $10, $11
    )
    RETURNING learning_id
  `;

  const params = [
    executionId, // UUID (foreign key to workflows.executions)
    workflowName, // VARCHAR(255)
    learningType, // VARCHAR(50) - CHECK constraint enforced
    title, // VARCHAR(500)
    description, // TEXT
    embedding ? `[${embedding.join(',')}]` : null, // vector(768) or NULL
    JSON.stringify(context), // JSONB
    impactScore, // NUMERIC(5,4)
    confidence, // NUMERIC(5,4)
    false, // BOOLEAN - verified (default false)
    JSON.stringify({ original_learnings: learnings }) // JSONB metadata
  ];

  const result = await db.query(sql, params);
  const learningId = result[0].learning_id; // UUID primary key

  console.log(`[storage] Stored learning ${learningId} for run ${runId} (execution ${executionId})`);
  return learningId;
}

/**
 * Build a title from learnings object
 * @param {object} learnings - Learning object
 * @returns {string} Title
 */
function buildTitle(learnings) {
  // Try to extract a meaningful title
  const recommendations = learnings.recommendations || [];
  if (recommendations.length > 0) {
    return recommendations[0].substring(0, 200); // First recommendation
  }

  const insights = learnings.code_patterns?.architecture_insights || [];
  if (insights.length > 0) {
    return insights[0].substring(0, 200);
  }

  return 'Learning extracted from workflow execution';
}

/**
 * Build a description from learnings object
 * @param {object} learnings - Learning object
 * @returns {string} Description
 */
function buildDescription(learnings) {
  const parts = [];

  if (learnings.user_patterns?.preferences?.length > 0) {
    parts.push('User preferences: ' + learnings.user_patterns.preferences.join(', '));
  }

  if (learnings.code_patterns?.common_bugs?.length > 0) {
    parts.push('Common bugs: ' + learnings.code_patterns.common_bugs.join(', '));
  }

  if (learnings.recommendations?.length > 0) {
    parts.push('Recommendations: ' + learnings.recommendations.join('; '));
  }

  return parts.join('\n\n') || 'No detailed description available';
}

/**
 * Query learnings by workflow name
 * @param {string} workflowName - Workflow name to filter by
 * @param {number} limit - Max results to return
 * @returns {Promise<Array>} Array of learning records from workflows.learnings
 */
async function getLearningsByWorkflow(workflowName, limit = 100) {
  const db = getDB();
  const sql = `
    SELECT
      learning_id, execution_id, workflow_name, learning_type,
      title, description, embedding, context,
      impact_score, confidence, verified, metadata, created_at
    FROM workflows.learnings
    WHERE workflow_name = $1
    ORDER BY created_at DESC
    LIMIT $2
  `;
  return await db.query(sql, [workflowName, limit]);
}

/**
 * Find similar learnings using vector similarity (cosine distance on vector(768))
 * @param {string} queryText - Text to search for
 * @param {number} limit - Max results to return
 * @param {object} filters - Optional filters
 * @param {string} filters.workflowName - Filter by workflow name
 * @param {number} filters.minQualityScore - Min quality_score from context JSONB
 * @param {number} filters.minImpactScore - Min impact_score (NUMERIC(5,4) column)
 * @returns {Promise<Array>} Array of similar learnings with distance scores
 */
async function findSimilarLearnings(queryText, limit = 10, filters = {}) {
  const db = getDB();

  // Generate embedding for query (MUST be 768-dim)
  const embedding = await generateEmbedding(queryText);
  if (embedding.length !== 768) {
    throw new Error(`Expected 768-dim embedding for similarity search, got ${embedding.length}-dim`);
  }

  let sql = `
    SELECT
      learning_id, execution_id, workflow_name, learning_type,
      title, description, context, impact_score, confidence,
      verified, metadata, created_at,
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

  // quality_score stored in context JSONB column
  if (filters.minQualityScore !== undefined) {
    sql += ` AND (context->>'quality_score')::decimal >= $${paramIdx}`;
    params.push(filters.minQualityScore);
    paramIdx++;
  }

  // impact_score is a dedicated NUMERIC(5,4) column (replaces old 'importance')
  if (filters.minImpactScore !== undefined) {
    sql += ` AND impact_score >= $${paramIdx}`;
    params.push(filters.minImpactScore);
    paramIdx++;
  }

  sql += ` ORDER BY embedding <=> $1::vector LIMIT $${paramIdx}`;
  params.push(limit);

  return await db.query(sql, params);
}

/**
 * Get recent learnings across all workflows
 * NOTE: workflows.recent_learnings view does not exist yet - querying table directly
 * @param {number} limit - Max results to return
 * @returns {Promise<Array>} Array of recent learnings
 */
async function getRecentLearnings(limit = 50) {
  const db = getDB();
  // TODO: Create workflows.recent_learnings materialized view for performance
  const sql = `
    SELECT
      learning_id,
      execution_id,
      workflow_name,
      learning_type,
      title,
      description,
      impact_score,
      confidence,
      verified,
      created_at
    FROM workflows.learnings
    ORDER BY created_at DESC
    LIMIT $1
  `;
  return await db.query(sql, [limit]);
}

/**
 * Get learning statistics by workflow
 * NOTE: workflows.learning_stats view does not exist yet - computing directly
 * @returns {Promise<Array>} Array of workflow stats with aggregated metrics
 */
async function getLearningStats() {
  const db = getDB();
  // TODO: Create workflows.learning_stats materialized view for performance
  const sql = `
    SELECT
      workflow_name,
      COUNT(*) as total_learnings,
      AVG(impact_score) as avg_impact,
      AVG(confidence) as avg_confidence,
      COUNT(*) FILTER (WHERE verified = true) as verified_count,
      COUNT(*) FILTER (WHERE verified = false) as unverified_count,
      MAX(created_at) as last_learning_at,
      MIN(created_at) as first_learning_at
    FROM workflows.learnings
    GROUP BY workflow_name
    ORDER BY total_learnings DESC
  `;
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

/**
 * DATABASE SCHEMA REFERENCE (workflows.learnings table)
 *
 * Database: learning@aio-01:5433
 * Schema: workflows
 * Table: learnings
 *
 * Columns:
 * - learning_id: UUID PRIMARY KEY (auto-generated)
 * - execution_id: UUID FOREIGN KEY → workflows.executions(execution_id)
 * - workflow_name: VARCHAR(255) NOT NULL
 * - learning_type: VARCHAR(50) CHECK IN ('pattern','failure','optimization','insight','best_practice')
 * - title: VARCHAR(500) NOT NULL
 * - description: TEXT NOT NULL
 * - embedding: vector(768) - HNSW index for similarity search
 * - context: JSONB - stores user_patterns, code_patterns, recommendations, quality_score, run_id
 * - impact_score: NUMERIC(5,4) - range 0.0000 to 1.0000 (replaces old 'importance')
 * - confidence: NUMERIC(5,4) - range 0.0000 to 1.0000
 * - verified: BOOLEAN DEFAULT false
 * - metadata: JSONB - stores original_learnings and other metadata
 * - created_at: TIMESTAMP DEFAULT NOW()
 *
 * Indexes:
 * - PRIMARY KEY (learning_id)
 * - FOREIGN KEY (execution_id)
 * - idx_learnings_embedding: HNSW on embedding (cosine distance)
 * - idx_learnings_impact: BTREE on impact_score DESC NULLS LAST
 * - idx_learnings_type: BTREE on learning_type
 * - idx_learnings_workflow: BTREE on workflow_name
 *
 * MIGRATION NOTES (from old workflow.* schema):
 * - Table: workflow.learnings → workflows.learnings
 * - PK: id (SERIAL) → learning_id (UUID)
 * - FK: workflow_execution_id (INTEGER) → execution_id (UUID)
 * - Field: importance (REAL) → impact_score (NUMERIC(5,4))
 * - Field: learning_embedding (vector(384)) → embedding (vector(768))
 * - Field: timestamp → created_at
 * - Removed: actionable_insight (merged into description)
 * - Added: title, context, verified, workflow_name
 * - Index: IVFFlat → HNSW (better performance)
 */
