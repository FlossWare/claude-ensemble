/**
 * DCAB Layer 1: Diversity Quota Enforcement
 *
 * Purpose: Prevent winner-take-all model convergence by enforcing hard quotas
 * - Ceiling: 40% (exclude models if >40% of last 20 requests)
 * - Floor: 15% (force include models if <15% of last 20 requests)
 *
 * Integration with DCAB router:
 * 1. Call enforceQuota() BEFORE Layer 2 Thompson Sampling
 * 2. Pass eligible_models to Layer 2 for multi-objective scoring
 * 3. Call logRequest() AFTER model execution for quota updates
 *
 * Date: 2026-06-15 (Phase 2 Implementation)
 * Architecture: /home/sfloess/.claude/DCAB_ARCHITECTURE_2026-06-15.md
 *
 * @module dcab-layer1
 */

const { getDB } = require('./postgres-adapter');
const { v4: uuidv4 } = require('uuid');

// ==============================================================================
// CONFIGURATION
// ==============================================================================

const CONFIG = {
    // Diversity quotas (percentages, 0-100)
    FLOOR_PCT: 15.0,   // Force include if <15%
    CEILING_PCT: 40.0, // Exclude if >40%

    // Circular buffer size (number of recent requests to track)
    WINDOW_SIZE: 20,   // As per architecture (not 100!)

    // Entropy thresholds
    ENTROPY_COLLAPSE_THRESHOLD: 1.0,  // Alert if Shannon entropy < 1.0 (architecture target: >1.0)
    ENTROPY_TARGET: 1.33,  // Target from architecture (near-uniform distribution)

    // A/B test configuration
    AB_TEST_ENABLED: process.env.DCAB_AB_TEST === 'true',
    AB_TREATMENT_PCT: 50, // 50% get treatment (DCAB), 50% get control (Thompson)

    // Feature flag
    ENABLED: process.env.DCAB_ENABLED !== 'false', // Default: enabled
};

// Constants for backward compatibility
const WINDOW_SIZE = CONFIG.WINDOW_SIZE;
const DEFAULT_MIN_QUOTA_PCT = CONFIG.FLOOR_PCT;
const DEFAULT_MAX_QUOTA_PCT = CONFIG.CEILING_PCT;
const ENTROPY_COLLAPSE_THRESHOLD = CONFIG.ENTROPY_COLLAPSE_THRESHOLD;

// ==============================================================================
// HELPER FUNCTIONS
// ==============================================================================

/**
 * Calculate Shannon entropy from model distribution
 *
 * Shannon entropy formula: H = -Σ(p_i * log2(p_i))
 * - H = 0: Single model dominance (worst)
 * - H = log2(n): Uniform distribution (best, n = number of models)
 * - H = 1.39 for uniform over 4 models (log2(4) = 2.0)
 *
 * @param {Object} modelCounts - {model: count}
 * @returns {number} Shannon entropy (0-2.0 for 4 models)
 */
function calculateShannonEntropy(modelCounts) {
    const total = Object.values(modelCounts).reduce((sum, count) => sum + count, 0);

    if (total === 0) return 0.0;

    let entropy = 0.0;
    for (const count of Object.values(modelCounts)) {
        if (count > 0) {
            const probability = count / total;
            const logValue = Math.log2(probability);
            if (!isNaN(logValue)) {
                entropy -= probability * logValue;
            }
        }
    }

    if (isNaN(entropy)) entropy = 0.0;
    return entropy;
}

/**
 * Assign A/B test bucket (50/50 split)
 *
 * @returns {string|null} 'A' | 'B' | null
 */
function assignABBucket() {
    if (!CONFIG.AB_TEST_ENABLED) return null;
    return Math.random() < (CONFIG.AB_TREATMENT_PCT / 100.0) ? 'B' : 'A';
}

/**
 * Get recent model distribution (last 20 requests as per architecture)
 *
 * @returns {Promise<Object>} {modelCounts, totalCount, entropy}
 */
async function getRecentDistribution() {
    const db = getDB();

    const result = await db.query(`
        SELECT model, COUNT(*) as request_count
        FROM (
            SELECT model FROM learning.request_history
            ORDER BY timestamp DESC
            LIMIT $1
        ) last_n
        GROUP BY model
    `, [CONFIG.WINDOW_SIZE]);

    const modelCounts = {};
    let totalCount = 0;

    for (const row of result.rows) {
        modelCounts[row.model] = parseInt(row.request_count);
        totalCount += parseInt(row.request_count);
    }

    const entropy = calculateShannonEntropy(modelCounts);

    return { modelCounts, totalCount, entropy };
}

/**
 * Get quota configuration for a model
 *
 * @param {string} model - Model identifier
 * @returns {Promise<Object>} {floorPct, ceilingPct, enabled}
 */
async function getModelQuota(model) {
    const db = getDB();

    const result = await db.query(`
        SELECT floor_pct, ceiling_pct, enabled
        FROM learning.model_quotas
        WHERE model = $1
    `, [model]);

    if (result.rows.length === 0) {
        // Default quotas if not configured
        return {
            floorPct: DEFAULT_MIN_QUOTA_PCT,
            ceilingPct: DEFAULT_MAX_QUOTA_PCT,
            enabled: true
        };
    }

    return {
        floorPct: parseFloat(result.rows[0].floor_pct),
        ceilingPct: parseFloat(result.rows[0].ceiling_pct),
        enabled: result.rows[0].enabled
    };
}

// ==============================================================================
// CORE FUNCTIONS
// ==============================================================================

/**
 * Enforce diversity quotas and return eligible models for Layer 2
 *
 * This is the main entry point for DCAB Layer 1.
 * Call this BEFORE Layer 2 Thompson Sampling to get the eligible model pool.
 *
 * @param {Object} options - Configuration options
 * @param {string} [options.abBucket] - A/B test bucket ('A' | 'B' | null)
 * @returns {Promise<Object>} Diversity enforcement result
 *
 * @example
 * const result = await enforceQuota();
 * // {
 * //   eligible: ['anthropic/claude-sonnet-4', 'fable/fable'],
 * //   excluded: ['anthropic/claude-haiku-4'], // >40% usage
 * //   forced: [],
 * //   quotaEnforced: true,
 * //   diversity: { entropy: 1.2, distribution: {...} }
 * // }
 */
async function enforceQuota(options = {}) {
    if (!CONFIG.ENABLED) {
        // Feature flag disabled → return all enabled models
        const db = getDB();
        const result = await db.query(`
            SELECT ARRAY_AGG(model) AS models
            FROM learning.model_quotas
            WHERE enabled = TRUE
        `);
        return {
            eligible: result.rows[0]?.models || [],
            excluded: [],
            forced: [],
            quotaEnforced: false,
            diversity: null,
        };
    }

    const { abBucket = null } = options;

    const db = getDB();

    // Call PostgreSQL function to compute eligible pool
    const result = await db.query(`SELECT * FROM get_eligible_models()`);

    const {
        eligible_models: eligible,
        excluded_models: excluded,
        forced_models: forced,
        quota_enforced: quotaEnforced,
    } = result.rows[0];

    // Compute diversity metrics
    const diversity = await computeDiversity();

    return {
        eligible: eligible || [],
        excluded: excluded || [],
        forced: forced || [],
        quotaEnforced,
        diversity,
    };
}

/**
 * Log request to diversity tracking system
 *
 * CRITICAL: Call this AFTER model execution to update circular buffer.
 * This triggers the automatic quota recalculation via database trigger.
 *
 * @param {Object} request - Request metadata
 * @param {string} request.model - Selected model
 * @param {string} [request.taskType] - Task classification
 * @param {boolean} [request.success] - Execution success
 * @param {number} [request.qualityScore] - Quality metric (0-1)
 * @param {number} [request.costUsd] - Cost in USD
 * @param {number} [request.durationMs] - Duration in milliseconds
 * @param {string} [request.abBucket] - A/B test bucket
 * @param {string[]} [request.excluded] - Models excluded by quota
 * @param {string[]} [request.forced] - Models forced by quota
 * @returns {Promise<string>} Request ID (for correlation)
 *
 * @example
 * const requestId = await logRequest({
 *   model: 'anthropic/claude-sonnet-4',
 *   taskType: 'code_generation',
 *   success: true,
 *   qualityScore: 0.85,
 *   costUsd: 0.0056,
 *   durationMs: 451,
 *   excluded: ['anthropic/claude-haiku-4'],
 *   forced: [],
 * });
 */
async function logRequest(request) {
    const {
        model,
        taskType = null,
        success = null,
        qualityScore = null,
        costUsd = null,
        durationMs = null,
        abBucket = null,
        excluded = [],
        forced = [],
    } = request;

    const requestId = uuidv4();
    const quotaEnforced = excluded.length > 0 || forced.length > 0;

    // Get current diversity score
    const { entropy } = await getRecentDistribution();

    const db = getDB();

    // Insert into request_history (triggers quota update via database trigger)
    await db.query(`
        INSERT INTO learning.request_history (
            request_id, model, timestamp, task_type,
            success, quality_score, duration_ms, cost_usd,
            diversity_score, quota_enforced, excluded_models, forced_models,
            ab_bucket
        ) VALUES ($1, $2, NOW(), $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    `, [
        requestId, model, taskType,
        success, qualityScore, durationMs, costUsd,
        entropy, quotaEnforced, excluded, forced,
        abBucket,
    ]);

    // Clean up old history (keep last 1000 entries to prevent unbounded growth)
    // Use CTE with FOR UPDATE SKIP LOCKED to prevent race condition
    await db.query(`
        WITH rows_to_delete AS (
            SELECT id FROM learning.request_history
            ORDER BY timestamp DESC
            OFFSET 1000
            FOR UPDATE SKIP LOCKED
        )
        DELETE FROM learning.request_history
        WHERE id IN (SELECT id FROM rows_to_delete)
    `);

    return requestId;
}

/**
 * Check current diversity metrics (for monitoring/alerts)
 *
 * @returns {Promise<Object>} Diversity metrics
 *
 * @example
 * const diversity = await checkDiversity();
 * // {
 * //   entropy: 1.33,  // Shannon entropy (0 = single model, 1.39 = uniform over 4)
 * //   distribution: {
 * //     'anthropic/claude-sonnet-4': 0.35,
 * //     'fable/fable': 0.30,
 * //     ...
 * //   },
 * //   violations: {
 * //     floor: 2,    // Models below 15% (last 24h)
 * //     ceiling: 1,  // Models above 40% (last 24h)
 * //   },
 * //   status: 'OK' | 'FLOOR_VIOLATION' | 'CEILING_VIOLATION' | 'ENTROPY_COLLAPSE'
 * // }
 */
async function checkDiversity() {
    return await computeDiversity();
}

/**
 * Compute Shannon entropy and distribution from model quotas
 *
 * @private
 * @returns {Promise<Object>} Diversity metrics
 */
async function computeDiversity() {
    const db = getDB();

    // Get current distribution from diversity_current view
    const result = await db.query(`
        SELECT
            model, usage_pct, floor_pct, ceiling_pct,
            quota_status, floor_violations, ceiling_violations
        FROM learning.diversity_current
    `);

    const distribution = {};
    let entropy = 0;
    let floorViolations = 0;
    let ceilingViolations = 0;

    for (const row of result.rows) {
        const p = parseFloat(row.usage_pct) / 100.0; // Convert percentage to probability
        distribution[row.model] = p;

        if (p > 0) {
            const logValue = Math.log2(p);
            if (!isNaN(logValue)) {
                entropy -= p * logValue;
            }
        }

        if (row.quota_status === 'floor_breach') floorViolations++;
        if (row.quota_status === 'ceiling_breach') ceilingViolations++;
    }

    if (isNaN(entropy)) entropy = 0.0;

    // Determine overall status
    let status = 'OK';
    if (ceilingViolations > 0) status = 'CEILING_VIOLATION';
    else if (floorViolations > 0) status = 'FLOOR_VIOLATION';
    else if (entropy < CONFIG.ENTROPY_COLLAPSE_THRESHOLD) status = 'ENTROPY_COLLAPSE';

    return {
        entropy,
        distribution,
        violations: {
            floor: floorViolations,
            ceiling: ceilingViolations,
        },
        status,
    };
}

// ==============================================================================
// MONITORING / ALERTS
// ==============================================================================

/**
 * Check for diversity violations and return alert status
 *
 * @returns {Promise<Object>} Alert status
 *
 * @example
 * const alert = await checkDiversityAlert();
 * // {
 * //   alert: true,
 * //   severity: 'CRITICAL',
 * //   message: 'Model anthropic/claude-haiku-4 at 45% (ceiling: 40%)',
 * //   metrics: { ... }
 * // }
 */
async function checkDiversityAlert() {
    const diversity = await checkDiversity();

    if (diversity.status === 'CEILING_VIOLATION') {
        return {
            alert: true,
            severity: 'CRITICAL',
            message: `${diversity.violations.ceiling} model(s) above 40% ceiling`,
            metrics: diversity,
        };
    }

    if (diversity.status === 'FLOOR_VIOLATION') {
        return {
            alert: true,
            severity: 'WARNING',
            message: `${diversity.violations.floor} model(s) below 15% floor`,
            metrics: diversity,
        };
    }

    if (diversity.entropy < CONFIG.ENTROPY_COLLAPSE_THRESHOLD) {
        return {
            alert: true,
            severity: 'WARNING',
            message: `Low diversity entropy: ${diversity.entropy.toFixed(2)} (target: >${CONFIG.ENTROPY_COLLAPSE_THRESHOLD})`,
            metrics: diversity,
        };
    }

    return {
        alert: false,
        severity: 'OK',
        message: 'Diversity within acceptable range',
        metrics: diversity,
    };
}

/**
 * Get diversity dashboard view (for Grafana/monitoring)
 *
 * @returns {Promise<Object[]>} Dashboard data
 */
async function getDiversityDashboard() {
    const db = getDB();
    const result = await db.query(`SELECT * FROM learning.diversity_current`);
    return result.rows;
}

/**
 * Update model quotas (manual override for testing)
 *
 * @param {string} model - Model identifier
 * @param {Object} quotas - New quota values
 * @param {number} [quotas.floorPct] - Floor percentage (0-100)
 * @param {number} [quotas.ceilingPct] - Ceiling percentage (0-100)
 * @param {boolean} [quotas.enabled] - Enable/disable model
 * @param {boolean} [quotas.paretoFrontierMember] - Pareto frontier status
 * @returns {Promise<void>}
 */
async function updateModelQuota(model, quotas) {
    const db = getDB();
    const updates = [];
    const values = [model];
    let idx = 2;

    if (quotas.floorPct !== undefined) {
        updates.push(`floor_pct = $${idx++}`);
        values.push(quotas.floorPct);
    }
    if (quotas.ceilingPct !== undefined) {
        updates.push(`ceiling_pct = $${idx++}`);
        values.push(quotas.ceilingPct);
    }
    if (quotas.enabled !== undefined) {
        updates.push(`enabled = $${idx++}`);
        values.push(quotas.enabled);
    }
    if (quotas.paretoFrontierMember !== undefined) {
        updates.push(`pareto_frontier_member = $${idx++}`);
        values.push(quotas.paretoFrontierMember);
    }

    if (updates.length === 0) return;

    await db.query(`
        UPDATE learning.model_quotas
        SET ${updates.join(', ')}, updated_at = NOW()
        WHERE model = $1
    `, values);
}

/**
 * Cleanup old request history (keep last 1000)
 *
 * @returns {Promise<number>} Number of deleted rows
 */
async function cleanupRequestHistory() {
    const db = getDB();
    // Use CTE with FOR UPDATE SKIP LOCKED to prevent race condition
    const result = await db.query(`
        WITH rows_to_delete AS (
            SELECT id FROM learning.request_history
            ORDER BY timestamp DESC
            OFFSET 1000
            FOR UPDATE SKIP LOCKED
        )
        DELETE FROM learning.request_history
        WHERE id IN (SELECT id FROM rows_to_delete)
    `);
    return result.rowCount || 0;
}

// ==============================================================================
// EXPORTS
// ==============================================================================

module.exports = {
    // Core functions (Phase 2 API)
    enforceQuota,
    logRequest,
    checkDiversity,

    // Helpers
    assignABBucket,
    getDiversityDashboard,
    updateModelQuota,
    cleanupRequestHistory,
    checkDiversityAlert,
    calculateShannonEntropy,
    getRecentDistribution,
    getModelQuota,

    // Config
    CONFIG,

    // Backward compatibility constants
    WINDOW_SIZE,
    DEFAULT_MIN_QUOTA_PCT,
    DEFAULT_MAX_QUOTA_PCT,
    ENTROPY_COLLAPSE_THRESHOLD,
};
