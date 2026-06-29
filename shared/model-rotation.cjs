/**
 * Model Rotation Policy
 *
 * Prevents staleness through forced exploration and graduated rollout.
 *
 * Features:
 * 1. Forced exploration every 7 days (pick random underused model)
 * 2. Canary mode for new models (1% traffic)
 * 3. Graduated rollout (1% → 10% → 100% over 14 days)
 * 4. Track rotation schedule in PostgreSQL
 *
 * Anti-staleness mechanisms:
 * - Detect underused models (0 executions in past 7 days)
 * - Force exploration with reduced weight penalty
 * - Graduated trust building for new models
 * - Automatic promotion based on quality threshold
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');

// Reuse connection pool
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

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Rotation policy configuration
 */
const ROTATION_CONFIG = {
  // Force exploration every N days
  exploration_interval_days: 7,

  // Minimum executions to avoid staleness
  min_executions_threshold: 5,

  // Canary rollout stages
  canary_stages: [
    { name: 'canary', traffic_percent: 1, duration_days: 3, min_quality: 0.60 },
    { name: 'ramp', traffic_percent: 10, duration_days: 7, min_quality: 0.70 },
    { name: 'full', traffic_percent: 100, duration_days: null, min_quality: 0.75 },
  ],

  // Quality threshold for auto-promotion
  auto_promote_quality: 0.80,

  // Quality threshold for auto-demotion
  auto_demote_quality: 0.50,

  // Minimum sample size for quality decision
  min_sample_size: 10,

  // Exploration weight boost
  exploration_weight_multiplier: 1.5,
};

// ============================================================================
// DATABASE SCHEMA
// ============================================================================

/**
 * Initialize rotation schema in PostgreSQL
 */
async function initializeSchema() {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Schema should already exist (created by workflow-storage-adapter)
    // Model rotation schedule table
    await client.query(`
      CREATE TABLE IF NOT EXISTS workflow.model_rotation_schedule (
        id SERIAL PRIMARY KEY,
        model TEXT NOT NULL,
        rollout_stage TEXT NOT NULL,  -- 'canary', 'ramp', 'full', 'dormant'
        traffic_percent NUMERIC NOT NULL,
        stage_started_at TIMESTAMP NOT NULL,
        stage_duration_days INTEGER,
        next_stage TEXT,
        auto_promote BOOLEAN DEFAULT false,
        force_exploration BOOLEAN DEFAULT false,

        -- Quality tracking
        total_executions INTEGER DEFAULT 0,
        successful_executions INTEGER DEFAULT 0,
        avg_quality NUMERIC DEFAULT 0.0,
        last_execution_at TIMESTAMP,

        -- Staleness tracking
        days_since_execution INTEGER DEFAULT 0,
        is_stale BOOLEAN DEFAULT false,

        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // Index for efficient lookups
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rotation_model
      ON workflow.model_rotation_schedule(model)
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rotation_stage
      ON workflow.model_rotation_schedule(rollout_stage)
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rotation_stale
      ON workflow.model_rotation_schedule(is_stale)
    `);

    await client.query('COMMIT');
    console.log('✓ Model rotation schema initialized');

  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ============================================================================
// MODEL REGISTRATION
// ============================================================================

/**
 * Register a new model in rotation schedule
 *
 * @param {string} model - Model name
 * @param {Object} options - Registration options
 * @param {string} options.stage - Initial stage ('canary' | 'ramp' | 'full' | 'dormant')
 * @param {boolean} options.forceExploration - Flag for forced exploration
 * @returns {Promise<Object>} Registration result
 */
async function registerModel(model, options = {}) {
  const stage = options.stage || 'canary';
  const forceExploration = options.forceExploration || false;

  // Find stage config
  const stageConfig = ROTATION_CONFIG.canary_stages.find(s => s.name === stage);
  if (!stageConfig) {
    throw new Error(`Invalid stage: ${stage}`);
  }

  const client = await pool.connect();
  try {
    // Check if model already registered
    const existingResult = await client.query(
      `SELECT id FROM workflow.model_rotation_schedule WHERE model = $1`,
      [model]
    );

    if (existingResult.rows.length > 0) {
      console.warn(`Model ${model} already registered, skipping`);
      return { status: 'already_registered', model };
    }

    // Determine next stage
    const currentIndex = ROTATION_CONFIG.canary_stages.findIndex(s => s.name === stage);
    const nextStage = currentIndex < ROTATION_CONFIG.canary_stages.length - 1
      ? ROTATION_CONFIG.canary_stages[currentIndex + 1].name
      : null;

    // Insert new model
    const result = await client.query(
      `INSERT INTO workflow.model_rotation_schedule
       (model, rollout_stage, traffic_percent, stage_started_at, stage_duration_days,
        next_stage, force_exploration, metadata)
       VALUES ($1, $2, $3, NOW(), $4, $5, $6, $7)
       RETURNING id`,
      [
        model,
        stage,
        stageConfig.traffic_percent,
        stageConfig.duration_days,
        nextStage,
        forceExploration,
        JSON.stringify({ registered_at: new Date().toISOString() })
      ]
    );

    console.log(`✓ Registered model ${model} at ${stage} stage (${stageConfig.traffic_percent}% traffic)`);

    return {
      status: 'registered',
      model,
      stage,
      traffic_percent: stageConfig.traffic_percent,
      id: result.rows[0].id,
    };

  } finally {
    client.release();
  }
}

// ============================================================================
// ROTATION POLICY
// ============================================================================

/**
 * Update model statistics after execution
 *
 * @param {string} model - Model name
 * @param {boolean} success - Execution success
 * @param {number} quality - Quality score (0.0-1.0)
 * @returns {Promise<void>}
 */
async function recordExecution(model, success, quality) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Ensure model is registered
    const checkResult = await client.query(
      `SELECT id FROM workflow.model_rotation_schedule WHERE model = $1`,
      [model]
    );

    if (checkResult.rows.length === 0) {
      // Auto-register as canary
      await registerModel(model, { stage: 'canary' });
    }

    // Update statistics
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         total_executions = total_executions + 1,
         successful_executions = successful_executions + CASE WHEN $2 THEN 1 ELSE 0 END,
         avg_quality = (avg_quality * total_executions + $3) / (total_executions + 1),
         last_execution_at = NOW(),
         days_since_execution = 0,
         is_stale = false,
         updated_at = NOW()
       WHERE model = $1`,
      [model, success, quality]
    );

    await client.query('COMMIT');

  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Detect stale models (no executions in N days)
 *
 * @returns {Promise<Array<string>>} List of stale model names
 */
async function detectStaleModels() {
  const client = await pool.connect();
  try {
    // Update staleness flags
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         days_since_execution = EXTRACT(DAY FROM NOW() - last_execution_at)::INTEGER,
         is_stale = EXTRACT(DAY FROM NOW() - last_execution_at) >= $1,
         updated_at = NOW()
       WHERE last_execution_at IS NOT NULL`,
      [ROTATION_CONFIG.exploration_interval_days]
    );

    // Return stale models
    const result = await client.query(
      `SELECT model, days_since_execution, rollout_stage
       FROM workflow.model_rotation_schedule
       WHERE is_stale = true AND rollout_stage != 'dormant'
       ORDER BY days_since_execution DESC`
    );

    return result.rows;

  } finally {
    client.release();
  }
}

/**
 * Force exploration of stale models
 *
 * Picks a random stale model and flags for forced exploration.
 *
 * @returns {Promise<string|null>} Model name to explore or null
 */
async function forceExploration() {
  const staleModels = await detectStaleModels();

  if (staleModels.length === 0) {
    return null;
  }

  // Pick random stale model
  const randomModel = staleModels[Math.floor(Math.random() * staleModels.length)];

  const client = await pool.connect();
  try {
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         force_exploration = true,
         updated_at = NOW()
       WHERE model = $1`,
      [randomModel.model]
    );

    console.log(`🔍 Forced exploration: ${randomModel.model} (${randomModel.days_since_execution} days stale)`);

    return randomModel.model;

  } finally {
    client.release();
  }
}

/**
 * Clear forced exploration flag after execution
 *
 * @param {string} model - Model name
 * @returns {Promise<void>}
 */
async function clearExplorationFlag(model) {
  const client = await pool.connect();
  try {
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         force_exploration = false,
         updated_at = NOW()
       WHERE model = $1`,
      [model]
    );
  } finally {
    client.release();
  }
}

/**
 * Check if model should be auto-promoted to next stage
 *
 * @param {string} model - Model name
 * @returns {Promise<Object|null>} Promotion decision or null
 */
async function checkAutoPromotion(model) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT rollout_stage, traffic_percent, stage_started_at, stage_duration_days,
              next_stage, total_executions, avg_quality
       FROM workflow.model_rotation_schedule
       WHERE model = $1`,
      [model]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const row = result.rows[0];

    // Already at full rollout
    if (row.rollout_stage === 'full') {
      return null;
    }

    // Insufficient sample size
    if (row.total_executions < ROTATION_CONFIG.min_sample_size) {
      return { promote: false, reason: 'insufficient_samples' };
    }

    // Check quality threshold
    const currentStage = ROTATION_CONFIG.canary_stages.find(s => s.name === row.rollout_stage);
    if (!currentStage) {
      return null;
    }

    const meetsQuality = row.avg_quality >= currentStage.min_quality;

    // Check duration requirement
    const daysSinceStart = Math.floor(
      (Date.now() - new Date(row.stage_started_at).getTime()) / (1000 * 60 * 60 * 24)
    );

    const meetsDuration = currentStage.duration_days === null ||
                          daysSinceStart >= currentStage.duration_days;

    // Decide promotion
    if (meetsQuality && meetsDuration) {
      return {
        promote: true,
        from_stage: row.rollout_stage,
        to_stage: row.next_stage,
        avg_quality: row.avg_quality,
        total_executions: row.total_executions,
      };
    }

    return {
      promote: false,
      reason: !meetsQuality ? 'quality_below_threshold' : 'duration_not_met',
      avg_quality: row.avg_quality,
      required_quality: currentStage.min_quality,
      days_in_stage: daysSinceStart,
      required_days: currentStage.duration_days,
    };

  } finally {
    client.release();
  }
}

/**
 * Promote model to next rollout stage
 *
 * @param {string} model - Model name
 * @returns {Promise<Object>} Promotion result
 */
async function promoteModel(model) {
  const promotionCheck = await checkAutoPromotion(model);

  if (!promotionCheck || !promotionCheck.promote) {
    return {
      status: 'not_eligible',
      reason: promotionCheck?.reason || 'unknown',
    };
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Get next stage config
    const nextStageConfig = ROTATION_CONFIG.canary_stages.find(
      s => s.name === promotionCheck.to_stage
    );

    if (!nextStageConfig) {
      throw new Error(`Invalid next stage: ${promotionCheck.to_stage}`);
    }

    // Determine next-next stage
    const currentIndex = ROTATION_CONFIG.canary_stages.findIndex(
      s => s.name === promotionCheck.to_stage
    );
    const nextNextStage = currentIndex < ROTATION_CONFIG.canary_stages.length - 1
      ? ROTATION_CONFIG.canary_stages[currentIndex + 1].name
      : null;

    // Update model stage
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         rollout_stage = $2,
         traffic_percent = $3,
         stage_started_at = NOW(),
         stage_duration_days = $4,
         next_stage = $5,
         updated_at = NOW()
       WHERE model = $1`,
      [
        model,
        promotionCheck.to_stage,
        nextStageConfig.traffic_percent,
        nextStageConfig.duration_days,
        nextNextStage
      ]
    );

    await client.query('COMMIT');

    console.log(
      `⬆️  Promoted ${model}: ${promotionCheck.from_stage} → ${promotionCheck.to_stage} ` +
      `(${nextStageConfig.traffic_percent}% traffic)`
    );

    return {
      status: 'promoted',
      model,
      from_stage: promotionCheck.from_stage,
      to_stage: promotionCheck.to_stage,
      new_traffic_percent: nextStageConfig.traffic_percent,
    };

  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Demote model to previous stage (quality degradation)
 *
 * @param {string} model - Model name
 * @param {string} reason - Demotion reason
 * @returns {Promise<Object>} Demotion result
 */
async function demoteModel(model, reason = 'quality_degradation') {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const result = await client.query(
      `SELECT rollout_stage FROM workflow.model_rotation_schedule WHERE model = $1`,
      [model]
    );

    if (result.rows.length === 0) {
      return { status: 'not_found' };
    }

    const currentStage = result.rows[0].rollout_stage;

    // Cannot demote canary or dormant
    if (currentStage === 'canary' || currentStage === 'dormant') {
      return { status: 'cannot_demote', reason: 'already_at_minimum' };
    }

    // Find previous stage
    const currentIndex = ROTATION_CONFIG.canary_stages.findIndex(s => s.name === currentStage);
    if (currentIndex <= 0) {
      return { status: 'cannot_demote', reason: 'no_previous_stage' };
    }

    const prevStageConfig = ROTATION_CONFIG.canary_stages[currentIndex - 1];

    // Update to previous stage
    await client.query(
      `UPDATE workflow.model_rotation_schedule
       SET
         rollout_stage = $2,
         traffic_percent = $3,
         stage_started_at = NOW(),
         stage_duration_days = $4,
         updated_at = NOW(),
         metadata = jsonb_set(
           metadata,
           '{demotion_history}',
           COALESCE(metadata->'demotion_history', '[]'::jsonb) ||
           jsonb_build_object(
             'timestamp', NOW()::text,
             'reason', $5::text,
             'from_stage', $6::text
           )::jsonb
         )
       WHERE model = $1`,
      [
        model,
        prevStageConfig.name,
        prevStageConfig.traffic_percent,
        prevStageConfig.duration_days,
        reason,
        currentStage
      ]
    );

    await client.query('COMMIT');

    console.log(
      `⬇️  Demoted ${model}: ${currentStage} → ${prevStageConfig.name} ` +
      `(${prevStageConfig.traffic_percent}% traffic) - ${reason}`
    );

    return {
      status: 'demoted',
      model,
      from_stage: currentStage,
      to_stage: prevStageConfig.name,
      new_traffic_percent: prevStageConfig.traffic_percent,
      reason,
    };

  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ============================================================================
// WEIGHTED VOTING INTEGRATION
// ============================================================================

/**
 * Get traffic allocation for model (0.0-1.0 multiplier)
 *
 * Used to reduce model weight in weighted voting based on rollout stage.
 *
 * @param {string} model - Model name
 * @returns {Promise<number>} Traffic multiplier (0.0-1.0)
 */
async function getTrafficMultiplier(model) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT traffic_percent, force_exploration FROM workflow.model_rotation_schedule
       WHERE model = $1`,
      [model]
    );

    if (result.rows.length === 0) {
      // Model not registered - default to full traffic
      return 1.0;
    }

    const row = result.rows[0];

    // If forced exploration, apply boost
    if (row.force_exploration) {
      return Math.min(1.0, (row.traffic_percent / 100.0) * ROTATION_CONFIG.exploration_weight_multiplier);
    }

    return row.traffic_percent / 100.0;

  } finally {
    client.release();
  }
}

/**
 * Apply rotation policy to model weights
 *
 * Integrates with weighted voting by adjusting weights based on rollout stage.
 *
 * @param {Array<Object>} votes - Votes with calculated weights
 * @returns {Promise<Array<Object>>} Votes with rotation-adjusted weights
 */
async function applyRotationPolicy(votes) {
  const adjustedVotes = [];

  for (const vote of votes) {
    const trafficMultiplier = await getTrafficMultiplier(vote.model);

    adjustedVotes.push({
      ...vote,
      rotation_multiplier: trafficMultiplier,
      rotation_adjusted_weight: vote.weight * trafficMultiplier,
    });
  }

  return adjustedVotes;
}

// ============================================================================
// MONITORING & REPORTING
// ============================================================================

/**
 * Get rotation status for all models
 *
 * @returns {Promise<Array<Object>>} Rotation status
 */
async function getRotationStatus() {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT
         model, rollout_stage, traffic_percent,
         total_executions, avg_quality,
         days_since_execution, is_stale, force_exploration,
         stage_started_at, next_stage
       FROM workflow.model_rotation_schedule
       ORDER BY traffic_percent DESC, avg_quality DESC`
    );

    return result.rows;

  } finally {
    client.release();
  }
}

/**
 * Generate rotation report
 *
 * @returns {Promise<Object>} Rotation summary report
 */
async function generateRotationReport() {
  const status = await getRotationStatus();

  const byStage = {
    canary: [],
    ramp: [],
    full: [],
    dormant: [],
  };

  const staleModels = [];
  const explorationModels = [];

  status.forEach(row => {
    if (byStage[row.rollout_stage]) {
      byStage[row.rollout_stage].push(row);
    }

    if (row.is_stale) {
      staleModels.push(row);
    }

    if (row.force_exploration) {
      explorationModels.push(row);
    }
  });

  return {
    total_models: status.length,
    by_stage: {
      canary: byStage.canary.length,
      ramp: byStage.ramp.length,
      full: byStage.full.length,
      dormant: byStage.dormant.length,
    },
    stale_models: staleModels.length,
    exploration_active: explorationModels.length,
    details: {
      canary: byStage.canary,
      ramp: byStage.ramp,
      full: byStage.full,
      dormant: byStage.dormant,
      stale: staleModels,
      exploration: explorationModels,
    },
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Initialization
  initializeSchema,

  // Model registration
  registerModel,

  // Execution tracking
  recordExecution,

  // Staleness detection
  detectStaleModels,
  forceExploration,
  clearExplorationFlag,

  // Promotion/demotion
  checkAutoPromotion,
  promoteModel,
  demoteModel,

  // Weighted voting integration
  getTrafficMultiplier,
  applyRotationPolicy,

  // Monitoring
  getRotationStatus,
  generateRotationReport,

  // Configuration (export for testing)
  ROTATION_CONFIG,

  // Connection pool
  pool,
};
