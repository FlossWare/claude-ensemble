#!/usr/bin/env node
/**
 * Curriculum Learning Orchestrator
 *
 * Implements curriculum learning for the AI learning system: start with easy
 * tasks, gradually increase difficulty, and adapt pacing based on success rate.
 *
 * The curriculum has 4 levels:
 *   Level 1 (Easy):    Simple tasks, single-model, forgiving thresholds
 *   Level 2 (Medium):  Standard tasks, multi-model, normal thresholds
 *   Level 3 (Hard):    Complex tasks, full consensus, tight thresholds
 *   Level 4 (Expert):  Edge cases, adversarial, maximum rigor
 *
 * Promotion:  success_rate >= promotion_threshold AND min_attempts met
 * Demotion:   success_rate <= demotion_threshold OR consecutive failures >= 3
 *
 * Integration:
 *   - Uses model-selector.js for Thompson Sampling model selection
 *   - Uses task-embedder.js for cold-start transfer learning
 *   - Uses feedback-selector.js for active learning annotation
 *   - Uses meta-optimizer.js for Reptile updates and Pareto selection
 *   - Publishes to message-bus channels: 'curriculum', 'distribution-shift'
 *
 * Usage:
 *   const curriculum = require('./curriculum-learning');
 *
 *   // Get current level and configuration for a task type
 *   const config = await curriculum.getTaskConfig('security');
 *
 *   // Record an execution outcome and update curriculum state
 *   await curriculum.recordOutcome('security', { quality: 0.85, ... });
 *
 *   // Get curriculum summary across all task types
 *   const summary = await curriculum.getSummary();
 *
 * Tables read/written: curriculum_state, curriculum_history, execution_log
 */

const path = require('path');

const DB_PATH = path.join(__dirname, 'db', 'learning.db');

// ---------------------------------------------------------------------------
// Curriculum Level Definitions
// ---------------------------------------------------------------------------

const CURRICULUM_LEVELS = {
  1: {
    name: 'Easy',
    description: 'Single model, forgiving thresholds, simple tasks',
    modelCount: 1,
    qualityThreshold: 0.5,       // minimum quality to count as success
    maxComplexity: 'simple',
    useConsensus: false,
    useBandit: false,             // use static model selection at easy level
    temperatureRange: [0.3, 0.7],
    maxTokens: 2048,
    retryOnFailure: true,
    features: ['basic_output', 'single_model']
  },
  2: {
    name: 'Medium',
    description: 'Multi-model with basic consensus, standard thresholds',
    modelCount: 3,
    qualityThreshold: 0.6,
    maxComplexity: 'standard',
    useConsensus: true,
    useBandit: true,              // start using Thompson Sampling
    temperatureRange: [0.2, 0.8],
    maxTokens: 4096,
    retryOnFailure: true,
    features: ['consensus', 'bandit_selection', 'quality_tracking']
  },
  3: {
    name: 'Hard',
    description: 'Full 6-model consensus, tight quality thresholds',
    modelCount: 6,
    qualityThreshold: 0.7,
    maxComplexity: 'complex',
    useConsensus: true,
    useBandit: true,
    temperatureRange: [0.1, 0.9],
    maxTokens: 8192,
    retryOnFailure: false,
    features: ['full_consensus', 'pareto_selection', 'bwt_monitoring', 'active_learning']
  },
  4: {
    name: 'Expert',
    description: 'Adversarial verification, edge cases, maximum rigor',
    modelCount: 6,
    qualityThreshold: 0.8,
    maxComplexity: 'adversarial',
    useConsensus: true,
    useBandit: true,
    temperatureRange: [0.0, 1.0],
    maxTokens: 16384,
    retryOnFailure: false,
    features: ['adversarial_debate', 'meta_optimization', 'transfer_learning', 'pareto_selection', 'bwt_monitoring', 'active_learning']
  }
};

const MAX_LEVEL = 4;
const MIN_LEVEL = 1;

// Default pacing parameters
const DEFAULT_PROMOTION_THRESHOLD = 0.8;
const DEFAULT_DEMOTION_THRESHOLD = 0.4;
const DEFAULT_MIN_ATTEMPTS = 5;
const CONSECUTIVE_FAILURE_LIMIT = 3;
const CONSECUTIVE_SUCCESS_BONUS = 5; // promote early after N consecutive successes

// ---------------------------------------------------------------------------
// Database helpers
// ---------------------------------------------------------------------------

let _sqlite3 = null;
function getSqlite3() {
  if (!_sqlite3) {
    try { _sqlite3 = require('sqlite3').verbose(); } catch (_) {
      _sqlite3 = require(path.join(__dirname, 'node_modules', 'sqlite3')).verbose();
    }
  }
  return _sqlite3;
}

function openDb() {
  const sqlite3 = getSqlite3();
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) return reject(err);
      db.run('PRAGMA journal_mode = WAL', () => {
        db.run('PRAGMA synchronous = NORMAL', () => {
          db.run('PRAGMA busy_timeout = 5000', () => resolve(db));
        });
      });
    });
  });
}

function dbAll(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => err ? reject(err) : resolve(rows || []));
  });
}

function dbGet(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => err ? reject(err) : resolve(row || null));
  });
}

function dbRun(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) reject(err);
      else resolve({ lastID: this.lastID, changes: this.changes });
    });
  });
}

function closeDb(db) {
  return new Promise((resolve) => {
    if (db) db.close(() => resolve());
    else resolve();
  });
}

// Message bus (optional)
let messageBus = null;
try { messageBus = require('./shared/message-bus'); } catch (_) {}

function notify(channel, message) {
  if (messageBus) {
    try { messageBus.postMessage(channel, message); } catch (_) {}
  }
}

// ---------------------------------------------------------------------------
// Core: Get or initialize curriculum state for a task type
// ---------------------------------------------------------------------------

/**
 * Get the current curriculum state for a task type.
 * Initializes at level 1 if no state exists.
 */
async function getCurriculumState(taskType, db = null) {
  const ownDb = !db;
  if (!db) db = await openDb();

  try {
    let state = await dbGet(db,
      'SELECT * FROM curriculum_state WHERE task_type = ?',
      [taskType]
    );

    if (!state) {
      // Initialize at level 1
      await dbRun(db, `
        INSERT INTO curriculum_state (
          task_type, current_level, level_started_at,
          promotion_threshold, demotion_threshold, min_attempts_before_change
        ) VALUES (?, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, ?)
      `, [taskType, DEFAULT_PROMOTION_THRESHOLD, DEFAULT_DEMOTION_THRESHOLD, DEFAULT_MIN_ATTEMPTS]);

      state = await dbGet(db,
        'SELECT * FROM curriculum_state WHERE task_type = ?',
        [taskType]
      );

      // Record initialization in history
      await dbRun(db, `
        INSERT INTO curriculum_history (task_type, from_level, to_level, trigger, notes)
        VALUES (?, 0, 1, 'init', 'Curriculum initialized for new task type')
      `, [taskType]);

      notify('curriculum', {
        type: 'initialized',
        taskType,
        level: 1,
        levelName: CURRICULUM_LEVELS[1].name
      });
    }

    return state;

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Get task configuration based on curriculum level
// ---------------------------------------------------------------------------

/**
 * Get the current configuration for a task type based on its curriculum level.
 * This is the main entry point for workflow code: call this to determine
 * how many models to use, whether to use consensus, etc.
 *
 * @param {string} taskType - Task type
 * @returns {object} Configuration for current curriculum level
 */
async function getTaskConfig(taskType) {
  const db = await openDb();

  try {
    const state = await getCurriculumState(taskType, db);
    const level = state.current_level;
    const levelConfig = CURRICULUM_LEVELS[level];

    // Build configuration merging level config with current state
    const config = {
      taskType,
      level,
      levelName: levelConfig.name,
      levelDescription: levelConfig.description,

      // Model configuration
      modelCount: levelConfig.modelCount,
      useConsensus: levelConfig.useConsensus,
      useBandit: levelConfig.useBandit,

      // Quality thresholds
      qualityThreshold: levelConfig.qualityThreshold,
      maxComplexity: levelConfig.maxComplexity,

      // Parameter ranges
      temperatureRange: levelConfig.temperatureRange,
      maxTokens: levelConfig.maxTokens,
      retryOnFailure: levelConfig.retryOnFailure,

      // Features enabled at this level
      features: levelConfig.features,

      // Model selection: use bandit or static
      selectModel: null,  // will be set below

      // Curriculum state
      successRate: state.success_rate,
      totalAttempts: state.total_attempts,
      consecutiveSuccesses: state.consecutive_successes,
      consecutiveFailures: state.consecutive_failures,
      paceMultiplier: state.pace_multiplier,
      promotionThreshold: state.promotion_threshold,
      demotionThreshold: state.demotion_threshold
    };

    // Set up model selection based on level
    if (levelConfig.useBandit) {
      try {
        const modelSelector = require('./model-selector');
        // Return a function that workflows can call
        config.selectModel = async (candidates) =>
          modelSelector.selectModel(taskType, candidates);
      } catch (_) {
        // Fall back to random selection
        config.selectModel = async (candidates) => ({
          model: candidates[Math.floor(Math.random() * candidates.length)],
          method: 'random_fallback'
        });
      }
    } else {
      // Static selection for easy level: always use the most reliable model
      config.selectModel = async (candidates) => ({
        model: candidates.includes('sonnet') ? 'sonnet' : candidates[0],
        method: 'static_easy_level'
      });
    }

    // Set up Pareto selection for hard/expert levels
    if (levelConfig.features.includes('pareto_selection')) {
      try {
        const metaOptimizer = require('./meta-optimizer');
        config.selectFromPareto = async (strategy) =>
          metaOptimizer.selectFromParetoFront(taskType, strategy);
      } catch (_) {
        config.selectFromPareto = null;
      }
    }

    return config;

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Record outcome and update curriculum state
// ---------------------------------------------------------------------------

/**
 * Record an execution outcome and update the curriculum state.
 * This is the feedback loop: after each execution, we update success/failure
 * counts and potentially promote or demote the task type.
 *
 * @param {string} taskType - Task type
 * @param {object} outcome - { quality, model, executionId, ... }
 * @returns {object} { level, levelChanged, promotion, demotion, ... }
 */
async function recordOutcome(taskType, outcome) {
  const db = await openDb();

  try {
    const state = await getCurriculumState(taskType, db);
    const level = state.current_level;
    const levelConfig = CURRICULUM_LEVELS[level];

    // Determine success/failure based on quality threshold
    const quality = outcome.quality || 0;
    const success = quality >= levelConfig.qualityThreshold;

    // Update counters
    const newSuccessCount = state.success_count + (success ? 1 : 0);
    const newFailureCount = state.failure_count + (success ? 0 : 1);
    const newTotalAttempts = state.total_attempts + 1;
    const newSuccessRate = newSuccessCount / newTotalAttempts;
    const newConsecutiveSuccesses = success ? state.consecutive_successes + 1 : 0;
    const newConsecutiveFailures = success ? 0 : state.consecutive_failures + 1;

    // Check for level change
    let newLevel = level;
    let trigger = null;

    // Promotion check
    if (newTotalAttempts >= state.min_attempts_before_change) {
      if (newSuccessRate >= state.promotion_threshold && level < MAX_LEVEL) {
        newLevel = level + 1;
        trigger = 'promotion';
      } else if (newSuccessRate <= state.demotion_threshold && level > MIN_LEVEL) {
        newLevel = level - 1;
        trigger = 'demotion';
      }
    }

    // Early promotion on long success streaks
    if (newConsecutiveSuccesses >= CONSECUTIVE_SUCCESS_BONUS && level < MAX_LEVEL) {
      newLevel = level + 1;
      trigger = 'promotion';
    }

    // Emergency demotion on failure streaks
    if (newConsecutiveFailures >= CONSECUTIVE_FAILURE_LIMIT && level > MIN_LEVEL) {
      newLevel = level - 1;
      trigger = 'demotion';
    }

    const levelChanged = newLevel !== level;

    // Compute adaptive pace multiplier
    // Fast learners (high success rate) get faster progression
    // Struggling task types get slower pace
    let paceMultiplier = state.pace_multiplier;
    if (newTotalAttempts >= 10) {
      if (newSuccessRate > 0.9) {
        paceMultiplier = Math.min(2.0, paceMultiplier * 1.05);
      } else if (newSuccessRate < 0.5) {
        paceMultiplier = Math.max(0.5, paceMultiplier * 0.95);
      }
    }

    // Update difficulty scores for this level
    let difficultyScores = {};
    try { difficultyScores = JSON.parse(state.difficulty_scores || '{}'); } catch (_) {}
    const levelKey = String(level);
    if (!difficultyScores[levelKey]) {
      difficultyScores[levelKey] = { sum: 0, count: 0 };
    }
    difficultyScores[levelKey].sum += quality;
    difficultyScores[levelKey].count += 1;

    // Write updated state
    if (levelChanged) {
      // Reset counters for new level
      await dbRun(db, `
        UPDATE curriculum_state SET
          current_level = ?,
          level_started_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
          success_count = 0,
          failure_count = 0,
          total_attempts = 0,
          success_rate = 0.0,
          consecutive_successes = 0,
          consecutive_failures = 0,
          last_outcome = ?,
          difficulty_scores = ?,
          pace_multiplier = ?,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE task_type = ?
      `, [
        newLevel,
        success ? 'success' : 'failure',
        JSON.stringify(difficultyScores),
        paceMultiplier,
        taskType
      ]);

      // Record level transition in history
      await dbRun(db, `
        INSERT INTO curriculum_history (
          task_type, from_level, to_level, trigger,
          success_rate_at_change, attempts_at_level, quality_at_change
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `, [
        taskType, level, newLevel, trigger,
        newSuccessRate, newTotalAttempts, quality
      ]);

      notify('curriculum', {
        type: trigger,
        taskType,
        fromLevel: level,
        toLevel: newLevel,
        fromLevelName: CURRICULUM_LEVELS[level].name,
        toLevelName: CURRICULUM_LEVELS[newLevel].name,
        successRate: newSuccessRate,
        attempts: newTotalAttempts
      });
    } else {
      // Just update counters
      await dbRun(db, `
        UPDATE curriculum_state SET
          success_count = ?,
          failure_count = ?,
          total_attempts = ?,
          success_rate = ?,
          consecutive_successes = ?,
          consecutive_failures = ?,
          last_outcome = ?,
          difficulty_scores = ?,
          pace_multiplier = ?,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE task_type = ?
      `, [
        newSuccessCount, newFailureCount, newTotalAttempts, newSuccessRate,
        newConsecutiveSuccesses, newConsecutiveFailures,
        success ? 'success' : 'failure',
        JSON.stringify(difficultyScores),
        paceMultiplier,
        taskType
      ]);
    }

    // Update bandit posteriors if bandit is enabled
    if (CURRICULUM_LEVELS[level].useBandit && outcome.model) {
      try {
        const modelSelector = require('./model-selector');
        await modelSelector.updateOutcome(
          taskType, outcome.model, quality,
          outcome.counterfactualScores || {},
          { db, executionId: outcome.executionId }
        );
      } catch (_) {}
    }

    // Schedule active learning feedback at hard/expert levels
    if (level >= 3 && outcome.executionId) {
      try {
        const feedbackSelector = require('./feedback-selector');
        // Only for executions with high uncertainty
        const batch = await feedbackSelector.selectBatch(10, 1, { db });
        // If this execution would be selected, schedule replay
        if (batch.some(b => b.executionId === outcome.executionId)) {
          await feedbackSelector.scheduleReplay(
            outcome.executionId, taskType, outcome.model || 'unknown',
            quality, 'curriculum_level_' + level
          );
        }
      } catch (_) {}
    }

    // Run backward transfer check at hard/expert levels
    if (levelChanged && trigger === 'promotion' && newLevel >= 3 && outcome.model) {
      try {
        const metaOptimizer = require('./meta-optimizer');
        const bwt = await metaOptimizer.checkBackwardTransfer(outcome.model, taskType, { db });
        if (bwt.rollbackRecommended) {
          notify('curriculum', {
            type: 'bwt_warning',
            taskType,
            model: outcome.model,
            degradedTasks: bwt.degradedTasks.map(t => t.taskType)
          });
        }
      } catch (_) {}
    }

    return {
      taskType,
      level: newLevel,
      levelName: CURRICULUM_LEVELS[newLevel].name,
      levelChanged,
      trigger,
      quality,
      success,
      successRate: levelChanged ? 0 : newSuccessRate,
      totalAttempts: levelChanged ? 0 : newTotalAttempts,
      consecutiveSuccesses: levelChanged ? 0 : newConsecutiveSuccesses,
      consecutiveFailures: levelChanged ? 0 : newConsecutiveFailures,
      paceMultiplier
    };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Curriculum summary and visualization
// ---------------------------------------------------------------------------

/**
 * Get a summary of curriculum state across all task types.
 */
async function getSummary() {
  const db = await openDb();

  try {
    const states = await dbAll(db,
      'SELECT * FROM curriculum_state ORDER BY current_level DESC, success_rate DESC'
    );

    // Level distribution
    const levelCounts = { 1: 0, 2: 0, 3: 0, 4: 0 };
    for (const state of states) {
      levelCounts[state.current_level] = (levelCounts[state.current_level] || 0) + 1;
    }

    // Recent transitions
    const transitions = await dbAll(db, `
      SELECT * FROM curriculum_history
      ORDER BY timestamp DESC
      LIMIT 20
    `);

    // Overall statistics
    const totalTasks = states.length;
    const avgLevel = totalTasks > 0
      ? states.reduce((s, st) => s + st.current_level, 0) / totalTasks
      : 0;
    const avgSuccessRate = totalTasks > 0
      ? states.reduce((s, st) => s + (st.success_rate || 0), 0) / totalTasks
      : 0;

    return {
      totalTaskTypes: totalTasks,
      averageLevel: avgLevel,
      averageSuccessRate: avgSuccessRate,
      levelDistribution: levelCounts,
      levelNames: {
        1: CURRICULUM_LEVELS[1].name,
        2: CURRICULUM_LEVELS[2].name,
        3: CURRICULUM_LEVELS[3].name,
        4: CURRICULUM_LEVELS[4].name
      },
      taskTypes: states.map(s => ({
        taskType: s.task_type,
        level: s.current_level,
        levelName: CURRICULUM_LEVELS[s.current_level]?.name || 'Unknown',
        successRate: s.success_rate,
        totalAttempts: s.total_attempts,
        consecutiveSuccesses: s.consecutive_successes,
        consecutiveFailures: s.consecutive_failures,
        paceMultiplier: s.pace_multiplier,
        lastOutcome: s.last_outcome,
        updatedAt: s.updated_at
      })),
      recentTransitions: transitions.map(t => ({
        taskType: t.task_type,
        from: t.from_level,
        to: t.to_level,
        fromName: CURRICULUM_LEVELS[t.from_level]?.name,
        toName: CURRICULUM_LEVELS[t.to_level]?.name,
        trigger: t.trigger,
        successRate: t.success_rate_at_change,
        quality: t.quality_at_change,
        timestamp: t.timestamp
      }))
    };

  } finally {
    await closeDb(db);
  }
}

/**
 * Get detailed curriculum info for a specific task type.
 */
async function getTaskDetail(taskType) {
  const db = await openDb();

  try {
    const state = await getCurriculumState(taskType, db);
    const level = state.current_level;
    const levelConfig = CURRICULUM_LEVELS[level];

    const history = await dbAll(db, `
      SELECT * FROM curriculum_history
      WHERE task_type = ?
      ORDER BY timestamp DESC
      LIMIT 50
    `, [taskType]);

    // Difficulty scores per level
    let difficultyScores = {};
    try { difficultyScores = JSON.parse(state.difficulty_scores || '{}'); } catch (_) {}

    const levelScores = {};
    for (const [lev, data] of Object.entries(difficultyScores)) {
      if (typeof data === 'object' && data.count > 0) {
        levelScores[lev] = {
          avgQuality: data.sum / data.count,
          attempts: data.count,
          levelName: CURRICULUM_LEVELS[parseInt(lev)]?.name || `Level ${lev}`
        };
      }
    }

    // Progress to next level
    let progressToPromotion = null;
    if (level < MAX_LEVEL && state.total_attempts > 0) {
      const attemptsRemaining = Math.max(0, state.min_attempts_before_change - state.total_attempts);
      const rateGap = state.promotion_threshold - state.success_rate;
      progressToPromotion = {
        currentRate: state.success_rate,
        requiredRate: state.promotion_threshold,
        rateGap: Math.max(0, rateGap),
        attemptsRemaining,
        streakProgress: `${state.consecutive_successes}/${CONSECUTIVE_SUCCESS_BONUS}`,
        estimatedAttemptsToPromote: rateGap > 0 && state.success_rate > 0
          ? Math.ceil(rateGap * state.total_attempts / (1 - state.success_rate))
          : attemptsRemaining
      };
    }

    return {
      taskType,
      currentLevel: level,
      levelName: levelConfig.name,
      levelDescription: levelConfig.description,
      features: levelConfig.features,
      state: {
        successCount: state.success_count,
        failureCount: state.failure_count,
        totalAttempts: state.total_attempts,
        successRate: state.success_rate,
        consecutiveSuccesses: state.consecutive_successes,
        consecutiveFailures: state.consecutive_failures,
        paceMultiplier: state.pace_multiplier,
        lastOutcome: state.last_outcome,
        levelStartedAt: state.level_started_at,
        updatedAt: state.updated_at
      },
      levelScores,
      progressToPromotion,
      thresholds: {
        promotion: state.promotion_threshold,
        demotion: state.demotion_threshold,
        quality: levelConfig.qualityThreshold,
        minAttempts: state.min_attempts_before_change,
        consecutiveFailureLimit: CONSECUTIVE_FAILURE_LIMIT,
        consecutiveSuccessBonus: CONSECUTIVE_SUCCESS_BONUS
      },
      history: history.map(h => ({
        fromLevel: h.from_level,
        toLevel: h.to_level,
        trigger: h.trigger,
        successRate: h.success_rate_at_change,
        attempts: h.attempts_at_level,
        quality: h.quality_at_change,
        timestamp: h.timestamp,
        notes: h.notes
      }))
    };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Manual level adjustment
// ---------------------------------------------------------------------------

/**
 * Manually set a task type's curriculum level.
 */
async function setLevel(taskType, level, reason = 'manual') {
  if (level < MIN_LEVEL || level > MAX_LEVEL) {
    throw new Error(`Level must be between ${MIN_LEVEL} and ${MAX_LEVEL}`);
  }

  const db = await openDb();

  try {
    const state = await getCurriculumState(taskType, db);
    const oldLevel = state.current_level;

    if (oldLevel === level) {
      return { changed: false, level, reason: 'already at requested level' };
    }

    await dbRun(db, `
      UPDATE curriculum_state SET
        current_level = ?,
        level_started_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
        success_count = 0,
        failure_count = 0,
        total_attempts = 0,
        success_rate = 0.0,
        consecutive_successes = 0,
        consecutive_failures = 0,
        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE task_type = ?
    `, [level, taskType]);

    await dbRun(db, `
      INSERT INTO curriculum_history (task_type, from_level, to_level, trigger, notes)
      VALUES (?, ?, ?, 'manual', ?)
    `, [taskType, oldLevel, level, reason]);

    notify('curriculum', {
      type: 'manual_adjustment',
      taskType,
      fromLevel: oldLevel,
      toLevel: level,
      reason
    });

    return {
      changed: true,
      taskType,
      fromLevel: oldLevel,
      toLevel: level,
      fromLevelName: CURRICULUM_LEVELS[oldLevel].name,
      toLevelName: CURRICULUM_LEVELS[level].name,
      reason
    };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Adaptive pacing adjustment
// ---------------------------------------------------------------------------

/**
 * Adjust pacing parameters for a task type.
 * Call this to make promotion easier or harder.
 */
async function adjustPacing(taskType, adjustments = {}) {
  const db = await openDb();

  try {
    const updates = [];
    const params = [];

    if (adjustments.promotionThreshold !== undefined) {
      updates.push('promotion_threshold = ?');
      params.push(Math.max(0.5, Math.min(1.0, adjustments.promotionThreshold)));
    }
    if (adjustments.demotionThreshold !== undefined) {
      updates.push('demotion_threshold = ?');
      params.push(Math.max(0.1, Math.min(0.5, adjustments.demotionThreshold)));
    }
    if (adjustments.minAttempts !== undefined) {
      updates.push('min_attempts_before_change = ?');
      params.push(Math.max(3, Math.min(20, adjustments.minAttempts)));
    }
    if (adjustments.paceMultiplier !== undefined) {
      updates.push('pace_multiplier = ?');
      params.push(Math.max(0.5, Math.min(2.0, adjustments.paceMultiplier)));
    }

    if (updates.length === 0) {
      return { changed: false, reason: 'no valid adjustments provided' };
    }

    updates.push("updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')");
    params.push(taskType);

    await dbRun(db,
      `UPDATE curriculum_state SET ${updates.join(', ')} WHERE task_type = ?`,
      params
    );

    return { changed: true, taskType, adjustments };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Initialize curriculum for all existing task types
// ---------------------------------------------------------------------------

/**
 * Scan execution_log for task types and initialize curriculum state
 * for any that don't have one yet. Sets initial level based on
 * historical success rate.
 */
async function initializeAllTaskTypes() {
  const db = await openDb();

  try {
    const taskTypes = await dbAll(db, `
      SELECT
        task_type,
        COUNT(*) AS total,
        AVG(quality_score) AS avg_quality,
        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS success_rate
      FROM execution_log
      WHERE task_type IS NOT NULL AND quality_score IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= 3
    `);

    let initialized = 0;
    for (const { task_type, avg_quality, success_rate } of taskTypes) {
      const existing = await dbGet(db,
        'SELECT task_type FROM curriculum_state WHERE task_type = ?',
        [task_type]
      );

      if (existing) continue;

      // Determine initial level based on historical performance
      let startLevel = 1;
      if (avg_quality >= 0.8 && success_rate >= 0.8) {
        startLevel = 3; // Jump to Hard if historically great
      } else if (avg_quality >= 0.6 && success_rate >= 0.6) {
        startLevel = 2; // Jump to Medium if historically good
      }

      await dbRun(db, `
        INSERT INTO curriculum_state (
          task_type, current_level, level_started_at,
          promotion_threshold, demotion_threshold, min_attempts_before_change
        ) VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, ?)
      `, [task_type, startLevel, DEFAULT_PROMOTION_THRESHOLD, DEFAULT_DEMOTION_THRESHOLD, DEFAULT_MIN_ATTEMPTS]);

      await dbRun(db, `
        INSERT INTO curriculum_history (task_type, from_level, to_level, trigger,
                                        success_rate_at_change, quality_at_change, notes)
        VALUES (?, 0, ?, 'init', ?, ?, 'Auto-initialized from historical performance')
      `, [task_type, startLevel, success_rate, avg_quality]);

      initialized++;
    }

    return { initialized, total: taskTypes.length };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  // Core API
  getTaskConfig,
  recordOutcome,
  getCurriculumState,

  // Summary and detail
  getSummary,
  getTaskDetail,

  // Manual controls
  setLevel,
  adjustPacing,

  // Initialization
  initializeAllTaskTypes,

  // Constants
  CURRICULUM_LEVELS,
  MAX_LEVEL,
  MIN_LEVEL
};

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  (async () => {
    try {
      switch (command) {
        case 'config': {
          const taskType = args[1] || 'code_review';
          const config = await getTaskConfig(taskType);
          // Remove function references for JSON serialization
          const printable = { ...config };
          delete printable.selectModel;
          delete printable.selectFromPareto;
          console.log(JSON.stringify(printable, null, 2));
          break;
        }
        case 'record': {
          const taskType = args[1];
          const quality = parseFloat(args[2]) || 0.5;
          const model = args[3] || null;
          const result = await recordOutcome(taskType, { quality, model });
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'summary': {
          const summary = await getSummary();
          console.log(JSON.stringify(summary, null, 2));
          break;
        }
        case 'detail': {
          const taskType = args[1] || 'code_review';
          const detail = await getTaskDetail(taskType);
          console.log(JSON.stringify(detail, null, 2));
          break;
        }
        case 'set-level': {
          const taskType = args[1];
          const level = parseInt(args[2]);
          const reason = args[3] || 'manual';
          const result = await setLevel(taskType, level, reason);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'adjust': {
          const taskType = args[1];
          const adjustments = args[2] ? JSON.parse(args[2]) : {};
          const result = await adjustPacing(taskType, adjustments);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'init': {
          const result = await initializeAllTaskTypes();
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        default:
          console.log(`
Curriculum Learning CLI

Usage:
  curriculum-learning.js config <task_type>
    Get current configuration for a task type

  curriculum-learning.js record <task_type> <quality> [model]
    Record an execution outcome

  curriculum-learning.js summary
    Get curriculum summary across all task types

  curriculum-learning.js detail <task_type>
    Get detailed curriculum info for a task type

  curriculum-learning.js set-level <task_type> <level> [reason]
    Manually set curriculum level (1-4)

  curriculum-learning.js adjust <task_type> <json_adjustments>
    Adjust pacing parameters

  curriculum-learning.js init
    Initialize curriculum for all existing task types

Levels:
  1 = Easy    - Single model, forgiving thresholds
  2 = Medium  - Multi-model with basic consensus
  3 = Hard    - Full 6-model consensus, tight thresholds
  4 = Expert  - Adversarial verification, maximum rigor
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  })();
}
