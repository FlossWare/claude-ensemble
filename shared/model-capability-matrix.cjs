/**
 * Model Capability Matrix
 *
 * Routes tasks to best-suited models based on capability scores.
 * Integrates with weighted-voting.cjs and PostgreSQL monitoring data.
 *
 * Architecture:
 * - Load baseline scores from learning/model-capability-matrix.json
 * - Update scores from PostgreSQL monitoring.execution_summary
 * - Exponentially weighted moving average (decay_factor = 0.95)
 * - Minimum 10 executions before updating baseline scores
 *
 * Usage:
 *   const { selectModelsByCapability, updateCapabilityScores } = require('./shared/model-capability-matrix.js');
 *
 *   // Get best models for a task type
 *   const models = await selectModelsByCapability('code_review', { limit: 5 });
 *   // => [{ model: 'opus', score: 0.95 }, { model: 'sonnet', score: 0.92 }, ...]
 *
 *   // Update scores from execution history
 *   await updateCapabilityScores();
 *
 * Integration with weighted-voting.cjs:
 *   - Uses same CAPABILITY_MATRIX as fallback
 *   - Stores updated scores in PostgreSQL monitoring.model_capabilities
 *   - Auto-updates from monitoring.execution_summary
 *
 * Created: 2026-06-29
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// CONFIGURATION
// ============================================================================

const CAPABILITY_MATRIX_PATH = path.join(
  __dirname,
  '..',
  'learning',
  'model-capability-matrix.json'
);

const MIN_EXECUTIONS_FOR_UPDATE = 10; // Minimum executions before updating baseline
const DECAY_FACTOR = 0.95; // Exponential weighted moving average decay
const DEFAULT_SCORE = 0.5; // Default score for unknown model/task combinations

// Task type aliases (map user-friendly names to internal task types)
const TASK_TYPE_ALIASES = {
  'code': 'code_generation',
  'review': 'code_review',
  'bug': 'bug_detection',
  'security': 'security_audit',
  'architecture': 'architecture_review',
  'search': 'research',
  'verify': 'fact_checking',
  'arbiter': 'consensus',
  'route': 'routing',
};

// ============================================================================
// CAPABILITY MATRIX LOADING
// ============================================================================

/**
 * Load capability matrix from JSON file
 * Supports two schemas:
 * 1. Simple schema: { models: { model: { task: score } } }
 * 2. Complex schema: { models: { model: { capabilities: { task: score } } } }
 *
 * @returns {Object} Capability matrix { model: { task: score } }
 */
function loadCapabilityMatrix() {
  try {
    if (!fs.existsSync(CAPABILITY_MATRIX_PATH)) {
      console.warn(`[model-capability-matrix] File not found: ${CAPABILITY_MATRIX_PATH}`);
      return {};
    }

    const data = JSON.parse(fs.readFileSync(CAPABILITY_MATRIX_PATH, 'utf8'));

    // Extract capabilities based on schema
    const capabilities = {};

    if (data.models) {
      Object.keys(data.models).forEach(model => {
        const modelData = data.models[model];

        // Check if this is complex schema (with capabilities sub-object)
        if (modelData.capabilities) {
          capabilities[model] = modelData.capabilities;
        } else if (typeof modelData === 'object') {
          // Simple schema - model data is directly task scores
          // Filter out non-score fields (strings, arrays, objects)
          capabilities[model] = {};
          Object.keys(modelData).forEach(key => {
            if (typeof modelData[key] === 'number') {
              capabilities[model][key] = modelData[key];
            }
          });
        }
      });
    }

    return capabilities;
  } catch (err) {
    console.warn(`[model-capability-matrix] Error loading matrix: ${err.message}`);
    return {};
  }
}

/**
 * Normalize task type (handle aliases)
 * @param {string} taskType - Task type or alias
 * @returns {string} Normalized task type
 */
function normalizeTaskType(taskType) {
  return TASK_TYPE_ALIASES[taskType] || taskType;
}

/**
 * Get capability score for a model/task combination
 *
 * Priority:
 * 1. PostgreSQL monitoring.model_capabilities (if exists)
 * 2. JSON file capability matrix
 * 3. Fallback to weighted-voting.cjs CAPABILITY_MATRIX
 * 4. Default score (0.5)
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @param {Object} options - Options
 * @param {Object} options.dbCapabilities - Pre-loaded DB capabilities (optional)
 * @param {Object} options.fileCapabilities - Pre-loaded file capabilities (optional)
 * @returns {Promise<number>} Capability score (0.0-1.0)
 */
async function getCapabilityScore(model, taskType, options = {}) {
  taskType = normalizeTaskType(taskType);

  // Priority 1: PostgreSQL (if provided)
  if (options.dbCapabilities && options.dbCapabilities[model]?.[taskType]) {
    return options.dbCapabilities[model][taskType];
  }

  // Priority 2: JSON file (if provided)
  if (options.fileCapabilities && options.fileCapabilities[model]?.[taskType]) {
    return options.fileCapabilities[model][taskType];
  }

  // Priority 3: Load from file (lazy load)
  if (!options.fileCapabilities) {
    const fileCapabilities = loadCapabilityMatrix();
    if (fileCapabilities[model]?.[taskType]) {
      return fileCapabilities[model][taskType];
    }
  }

  // Priority 4: Fallback to weighted-voting.cjs hardcoded CAPABILITY_MATRIX
  // Uses the constant directly (not getCapabilityScore function) to avoid
  // circular lookups since weighted-voting.cjs now delegates to this module's
  // JSON file as its first priority.
  try {
    const { CAPABILITY_MATRIX, getModelTierWeight } = require('./weighted-voting.cjs');
    const taskMatrix = CAPABILITY_MATRIX[taskType] || CAPABILITY_MATRIX.general;
    if (taskMatrix) {
      if (taskMatrix[model] !== undefined) return taskMatrix[model];
      const baseModel = model.toLowerCase().split(':')[0].split('-')[0];
      if (taskMatrix[baseModel] !== undefined) return taskMatrix[baseModel];
    }
    // Last resort: tier weight from weighted-voting
    return getModelTierWeight(model);
  } catch (err) {
    // Weighted voting not available - use default
    return DEFAULT_SCORE;
  }
}

// ============================================================================
// MODEL SELECTION
// ============================================================================

/**
 * Select best models for a task type, sorted by capability score
 *
 * @param {string} taskType - Task type
 * @param {Object} options - Options
 * @param {number} options.limit - Maximum number of models to return (default: all)
 * @param {number} options.minScore - Minimum capability score (default: 0.0)
 * @param {Array<string>} options.excludeModels - Models to exclude (default: [])
 * @param {Array<string>} options.onlyModels - Only consider these models (default: all)
 * @returns {Promise<Array<Object>>} Sorted models [{ model, score }, ...]
 */
async function selectModelsByCapability(taskType, options = {}) {
  const {
    limit = null,
    minScore = 0.0,
    excludeModels = [],
    onlyModels = null,
  } = options;

  taskType = normalizeTaskType(taskType);

  // Load capabilities from all sources
  const fileCapabilities = loadCapabilityMatrix();
  const dbCapabilities = await loadCapabilitiesFromDB();

  // Get all unique models from both sources
  const allModels = new Set([
    ...Object.keys(fileCapabilities),
    ...Object.keys(dbCapabilities),
  ]);

  // Apply filters
  let models = Array.from(allModels);

  if (onlyModels) {
    models = models.filter(m => onlyModels.includes(m));
  }

  if (excludeModels.length > 0) {
    models = models.filter(m => !excludeModels.includes(m));
  }

  // Get scores for each model
  const modelScores = await Promise.all(
    models.map(async model => ({
      model,
      score: await getCapabilityScore(model, taskType, {
        dbCapabilities,
        fileCapabilities,
      }),
    }))
  );

  // Filter by minimum score
  const filtered = modelScores.filter(m => m.score >= minScore);

  // Sort by score descending
  filtered.sort((a, b) => b.score - a.score);

  // Apply limit
  if (limit !== null && limit > 0) {
    return filtered.slice(0, limit);
  }

  return filtered;
}

/**
 * Select diverse models for a task (balance capability with diversity)
 *
 * Algorithm:
 * 1. Get top N models by capability
 * 2. Group by model family
 * 3. Take best from each family first (diversity)
 * 4. Fill remaining slots with next-best models
 *
 * @param {string} taskType - Task type
 * @param {Object} options - Options (same as selectModelsByCapability)
 * @param {number} options.diversityWeight - Weight for diversity vs capability (0-1, default: 0.5)
 * @returns {Promise<Array<Object>>} Diverse models [{ model, score, family }, ...]
 */
async function selectDiverseModels(taskType, options = {}) {
  const {
    limit = 5,
    diversityWeight = 0.5,
    ...otherOptions
  } = options;

  // Get all candidate models
  const candidates = await selectModelsByCapability(taskType, {
    ...otherOptions,
    limit: null, // Get all models first
  });

  if (candidates.length === 0) {
    return [];
  }

  // Extract model family (first part before '-' or ':')
  candidates.forEach(c => {
    c.family = c.model.toLowerCase().split(/[-:]/)[0];
  });

  // Group by family
  const families = {};
  candidates.forEach(c => {
    if (!families[c.family]) {
      families[c.family] = [];
    }
    families[c.family].push(c);
  });

  // Sort each family by score
  Object.keys(families).forEach(family => {
    families[family].sort((a, b) => b.score - a.score);
  });

  // Diversity-aware selection
  const selected = [];
  const familyCounts = {};

  // Round-robin: take best from each family first
  let familyNames = Object.keys(families);
  let round = 0;

  while (selected.length < limit && familyNames.length > 0) {
    const remainingFamilies = [];

    for (const family of familyNames) {
      if (families[family].length > round) {
        const candidate = families[family][round];

        // Calculate diversity-adjusted score
        const familyCount = familyCounts[family] || 0;
        const diversityPenalty = familyCount * diversityWeight;
        candidate.diversityScore = candidate.score * (1 - diversityPenalty);

        selected.push(candidate);
        familyCounts[family] = familyCount + 1;

        if (selected.length >= limit) {
          break;
        }

        remainingFamilies.push(family);
      }
    }

    familyNames = remainingFamilies;
    round++;
  }

  // Sort by diversity-adjusted score
  selected.sort((a, b) => b.diversityScore - a.diversityScore);

  return selected.slice(0, limit);
}

// ============================================================================
// POSTGRESQL INTEGRATION
// ============================================================================

/**
 * Load capability scores from PostgreSQL monitoring.model_capabilities
 * @returns {Promise<Object>} Capabilities { model: { task: score } }
 */
async function loadCapabilitiesFromDB() {
  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Check if table exists
    const tableCheck = await db.pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'monitoring'
        AND table_name = 'model_capabilities'
      )
    `);

    if (!tableCheck.rows[0].exists) {
      // Table doesn't exist yet - return empty
      return {};
    }

    // Load all capabilities
    const result = await db.pool.query(`
      SELECT model, task_type, capability_score, executions
      FROM monitoring.model_capabilities
      WHERE executions >= $1
    `, [MIN_EXECUTIONS_FOR_UPDATE]);

    // Build capabilities object
    const capabilities = {};

    result.rows.forEach(row => {
      if (!capabilities[row.model]) {
        capabilities[row.model] = {};
      }
      capabilities[row.model][row.task_type] = parseFloat(row.capability_score);
    });

    return capabilities;
  } catch (err) {
    console.warn(`[model-capability-matrix] Error loading from DB: ${err.message}`);
    return {};
  }
}

/**
 * Create monitoring.model_capabilities table (idempotent)
 * @returns {Promise<void>}
 */
async function createCapabilitiesTable() {
  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    await db.pool.query(`
      CREATE TABLE IF NOT EXISTS monitoring.model_capabilities (
        id SERIAL PRIMARY KEY,
        model TEXT NOT NULL,
        task_type TEXT NOT NULL,
        capability_score NUMERIC NOT NULL,
        executions INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT NOW(),
        UNIQUE(model, task_type)
      )
    `);

    // Create index for fast lookups
    await db.pool.query(`
      CREATE INDEX IF NOT EXISTS idx_model_capabilities_lookup
      ON monitoring.model_capabilities(model, task_type)
    `);

    console.log('[model-capability-matrix] Table monitoring.model_capabilities created');
  } catch (err) {
    console.warn(`[model-capability-matrix] Error creating table: ${err.message}`);
    throw err;
  }
}

/**
 * Update capability scores from monitoring.execution_summary
 *
 * Algorithm:
 * 1. Load baseline scores from JSON file
 * 2. Query execution_summary for quality scores per model/task
 * 3. Calculate exponentially weighted moving average (EWMA)
 * 4. Update monitoring.model_capabilities table
 *
 * EWMA formula: new_score = baseline * decay + observed * (1 - decay)
 *
 * @param {Object} options - Options
 * @param {number} options.minExecutions - Minimum executions to update (default: 10)
 * @param {number} options.decayFactor - EWMA decay factor (default: 0.95)
 * @returns {Promise<Object>} Update summary { updated: N, models: [...] }
 */
async function updateCapabilityScores(options = {}) {
  const {
    minExecutions = MIN_EXECUTIONS_FOR_UPDATE,
    decayFactor = DECAY_FACTOR,
  } = options;

  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Ensure table exists
    await createCapabilitiesTable();

    // Load baseline scores
    const baseline = loadCapabilityMatrix();

    // Query execution summary for observed quality scores
    const result = await db.pool.query(`
      SELECT
        model,
        task_type,
        COUNT(*) as executions,
        AVG(quality_score) as avg_quality,
        STDDEV(quality_score) as stddev_quality,
        MIN(quality_score) as min_quality,
        MAX(quality_score) as max_quality
      FROM monitoring.execution_summary
      WHERE quality_score IS NOT NULL
        AND task_type IS NOT NULL
      GROUP BY model, task_type
      HAVING COUNT(*) >= $1
    `, [minExecutions]);

    const updates = [];

    for (const row of result.rows) {
      const model = row.model;
      const taskType = row.task_type;
      const observedScore = parseFloat(row.avg_quality);
      const executions = parseInt(row.executions);

      // Get baseline score
      const baselineScore = baseline[model]?.[taskType] || DEFAULT_SCORE;

      // Calculate EWMA
      const newScore = baselineScore * decayFactor + observedScore * (1 - decayFactor);

      // Upsert into database
      await db.pool.query(`
        INSERT INTO monitoring.model_capabilities
        (model, task_type, capability_score, executions, last_updated)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (model, task_type) DO UPDATE SET
          capability_score = EXCLUDED.capability_score,
          executions = EXCLUDED.executions,
          last_updated = NOW()
      `, [model, taskType, newScore, executions]);

      updates.push({
        model,
        task_type: taskType,
        baseline_score: baselineScore,
        observed_score: observedScore,
        new_score: newScore,
        executions,
        stddev: parseFloat(row.stddev_quality),
      });
    }

    console.log(`[model-capability-matrix] Updated ${updates.length} capability scores`);

    return {
      status: 'success',
      updated: updates.length,
      updates,
    };
  } catch (err) {
    console.error(`[model-capability-matrix] Error updating scores: ${err.message}`);
    return {
      status: 'error',
      error: err.message,
      updated: 0,
    };
  }
}

/**
 * Get capability score with confidence interval
 *
 * Returns score plus confidence based on number of executions.
 * More executions = higher confidence.
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @returns {Promise<Object>} { score, confidence, executions, source }
 */
async function getCapabilityScoreWithConfidence(model, taskType) {
  taskType = normalizeTaskType(taskType);

  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Try DB first
    const result = await db.pool.query(`
      SELECT capability_score, executions
      FROM monitoring.model_capabilities
      WHERE model = $1 AND task_type = $2
    `, [model, taskType]);

    if (result.rows.length > 0) {
      const row = result.rows[0];
      const score = parseFloat(row.capability_score);
      const executions = parseInt(row.executions);

      // Confidence based on executions (sigmoid function)
      // 10 executions = 0.50 confidence
      // 50 executions = 0.88 confidence
      // 100+ executions = 0.95+ confidence
      const confidence = 1 / (1 + Math.exp(-0.05 * (executions - 50)));

      return {
        score,
        confidence,
        executions,
        source: 'database',
      };
    }
  } catch (err) {
    console.warn(`[model-capability-matrix] DB lookup failed: ${err.message}`);
  }

  // Fallback to file/weighted-voting
  const score = await getCapabilityScore(model, taskType);

  return {
    score,
    confidence: 0.3, // Low confidence for baseline scores
    executions: 0,
    source: 'baseline',
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  selectModelsByCapability,
  selectDiverseModels,
  getCapabilityScore,
  getCapabilityScoreWithConfidence,

  // PostgreSQL integration
  updateCapabilityScores,
  createCapabilitiesTable,
  loadCapabilitiesFromDB,

  // Utilities
  loadCapabilityMatrix,
  normalizeTaskType,

  // Configuration
  TASK_TYPE_ALIASES,
  MIN_EXECUTIONS_FOR_UPDATE,
  DECAY_FACTOR,
  DEFAULT_SCORE,
};
