#!/usr/bin/env node
/**
 * Feedback Selector -- Active Learning for Quality Feedback (Phase 3)
 *
 * Implements intelligent selection of which executions need quality feedback,
 * MC-dropout-style uncertainty estimation, batch selection with diversity,
 * and Ebbinghaus-inspired replay scheduling.
 *
 * Features:
 *   1. Uncertainty Estimation: variance of quality predictions from k-nearest
 *   2. Batch Selection: entropy + cluster_distance + cost weighting
 *   3. Ebbinghaus Replay: scheduled re-checks at [1, 3, 7, 14] day intervals
 *   4. Self-Supervised Signals: leverage CI outcomes as free labels
 *
 * Usage:
 *   const feedback = require('./feedback-selector');
 *   const batch = await feedback.selectBatch(100, 20);
 *   await feedback.scheduleReplay('exec-123', 'security', 'opus', 0.85);
 *   const pending = await feedback.getPendingReplays();
 *
 * Tables read:  execution_log, quality_ratings, feedback_schedule
 * Tables written: feedback_schedule
 */

const path = require('path');

const DB_PATH = path.join(__dirname, 'db', 'learning.db');
const K_NEIGHBORS = 3;           // neighbors for uncertainty estimation
const REPLAY_INTERVALS = [1, 3, 7, 14]; // days between re-checks
const DEFAULT_BATCH_SIZE = 20;
const DEFAULT_POOL_SIZE = 100;

// Batch selection weights
const WEIGHT_ENTROPY = 0.5;
const WEIGHT_CLUSTER_DISTANCE = 0.3;
const WEIGHT_COST_INVERSE = 0.2;

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

// ---------------------------------------------------------------------------
// Math helpers
// ---------------------------------------------------------------------------

function mean(arr) {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function variance(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  return arr.reduce((sum, v) => sum + (v - m) ** 2, 0) / (arr.length - 1);
}

/**
 * Binary entropy: H(p) = -p*log2(p) - (1-p)*log2(1-p)
 * Returns 0 for p=0 or p=1, max 1.0 for p=0.5.
 */
function binaryEntropy(p) {
  if (p <= 0 || p >= 1) return 0;
  return -(p * Math.log2(p) + (1 - p) * Math.log2(1 - p));
}

/**
 * L2 distance between two numeric arrays.
 */
function l2Distance(a, b) {
  if (a.length !== b.length) return Infinity;
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    sum += (a[i] - b[i]) ** 2;
  }
  return Math.sqrt(sum);
}

// ---------------------------------------------------------------------------
// Core: Uncertainty estimation via k-nearest neighbor variance
// ---------------------------------------------------------------------------

/**
 * Estimate prediction uncertainty for an execution by finding the k nearest
 * historical executions (by feature similarity) and computing the variance
 * of their quality scores. High variance = high uncertainty = high value
 * for annotation.
 *
 * @param {object} execution - Execution row with model, task_type, etc.
 * @param {object[]} historicalExecs - Pool of past executions to compare against
 * @param {number} k - Number of neighbors
 * @returns {number} Uncertainty score (0-1)
 */
function estimateUncertainty(execution, historicalExecs, k = K_NEIGHBORS) {
  if (historicalExecs.length < k) {
    // Not enough history: high uncertainty
    return 1.0;
  }

  // Build a simple feature vector for matching
  const execFeatures = buildExecutionFeatures(execution);

  // Compute distances to all historical executions
  const distances = historicalExecs.map(hist => ({
    quality: hist.quality_score,
    distance: l2Distance(execFeatures, buildExecutionFeatures(hist))
  }));

  // Sort by distance, take k nearest
  distances.sort((a, b) => a.distance - b.distance);
  const neighbors = distances.slice(0, k);

  // Compute variance of neighbor quality scores
  const qualities = neighbors.map(n => n.quality);
  const v = variance(qualities);

  // Normalize to 0-1 (max possible variance for 0-1 values is 0.25)
  return Math.min(1.0, v / 0.25);
}

/**
 * Build a compact feature vector for an execution for distance computation.
 * Features: [confidence, consensus, cost_norm, duration_norm, model_index]
 */
function buildExecutionFeatures(exec) {
  const modelIndex = {
    'opus': 0, 'sonnet': 0.2, 'haiku': 0.4,
    'gpt-4o': 0.6, 'gemini': 0.8, 'fable': 1.0
  };
  return [
    exec.confidence || 0,
    exec.consensus_score || 0,
    Math.min(1, (exec.cost_usd || exec.total_cost_usd || 0)),
    Math.min(1, (exec.duration_ms || 0) / 60000),
    modelIndex[exec.model] || 0.5
  ];
}

// ---------------------------------------------------------------------------
// Core: Batch selection with entropy + diversity + cost
// ---------------------------------------------------------------------------

/**
 * Select a batch of executions that would benefit most from quality annotation.
 *
 * A(x) = w1 * entropy(x) + w2 * cluster_distance(x) + w3 * (1/cost(x))
 *
 * @param {number} poolSize - Number of recent unrated executions to consider
 * @param {number} batchSize - Number to select for annotation
 * @param {object} options - { db }
 * @returns {object[]} Selected executions with annotation scores
 */
async function selectBatch(poolSize = DEFAULT_POOL_SIZE, batchSize = DEFAULT_BATCH_SIZE, options = {}) {
  const ownDb = !options.db;
  const db = options.db || await openDb();

  try {
    // Get recent executions that haven't been rated
    const unrated = await dbAll(db, `
      SELECT el.*
      FROM execution_log el
      LEFT JOIN quality_ratings qr ON el.execution_id = qr.execution_id
      WHERE qr.id IS NULL
        AND el.quality_score IS NOT NULL
        AND el.execution_id IS NOT NULL
      ORDER BY el.timestamp DESC
      LIMIT ?
    `, [poolSize]);

    if (unrated.length === 0) {
      return [];
    }

    // Get historical rated executions for uncertainty estimation
    const historical = await dbAll(db, `
      SELECT el.*
      FROM execution_log el
      INNER JOIN quality_ratings qr ON el.execution_id = qr.execution_id
      WHERE el.quality_score IS NOT NULL
      ORDER BY el.timestamp DESC
      LIMIT 200
    `);

    // Score each unrated execution
    const scored = [];
    for (const exec of unrated) {
      // 1. Entropy: uncertainty about whether this is good or bad
      const confidence = exec.confidence || 0.5;
      const entropy = binaryEntropy(confidence);

      // 2. Uncertainty: neighbor-based prediction variance
      const uncertainty = estimateUncertainty(exec, historical);

      // 3. Cost inverse: prefer annotating cheaper executions
      const cost = exec.cost_usd || exec.total_cost_usd || 0.01;
      const costInverse = Math.min(1, 1 / (cost * 100)); // normalize

      // Combined score
      const annotationValue =
        WEIGHT_ENTROPY * entropy +
        WEIGHT_CLUSTER_DISTANCE * uncertainty +
        WEIGHT_COST_INVERSE * costInverse;

      scored.push({
        executionId: exec.execution_id || exec.id,
        model: exec.model,
        taskType: exec.task_type,
        qualityScore: exec.quality_score,
        confidence: exec.confidence,
        annotationValue,
        components: { entropy, uncertainty, costInverse },
        timestamp: exec.timestamp
      });
    }

    // Sort by annotation value descending, take top batchSize
    scored.sort((a, b) => b.annotationValue - a.annotationValue);

    // Apply diversity filter: don't take too many from same model/task pair
    const selected = [];
    const counts = new Map();
    const maxPerGroup = Math.ceil(batchSize / 3);

    for (const item of scored) {
      if (selected.length >= batchSize) break;

      const key = `${item.model}::${item.taskType}`;
      const count = counts.get(key) || 0;
      if (count >= maxPerGroup) continue;

      selected.push(item);
      counts.set(key, count + 1);
    }

    return selected;

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Ebbinghaus replay scheduling
// ---------------------------------------------------------------------------

/**
 * Schedule quality re-checks at Ebbinghaus intervals after a parameter update.
 * Intervals: [1 day, 3 days, 7 days, 14 days]
 *
 * @param {string} executionId - Execution to re-check
 * @param {string} taskType - Task type
 * @param {string} model - Model name
 * @param {number} qualityBefore - Quality before the parameter update
 * @param {string} triggeredBy - Description of what parameter update triggered this
 * @returns {object} { scheduled: number, intervals }
 */
async function scheduleReplay(executionId, taskType, model, qualityBefore, triggeredBy = '') {
  const db = await openDb();

  try {
    const now = new Date();
    const scheduled = [];

    for (const days of REPLAY_INTERVALS) {
      const scheduledAt = new Date(now.getTime() + days * 24 * 60 * 60 * 1000);

      await dbRun(db, `
        INSERT INTO feedback_schedule (
          execution_id, task_type, model, scheduled_at,
          interval_days, status, triggered_by, quality_before
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
      `, [
        executionId,
        taskType,
        model,
        scheduledAt.toISOString(),
        days,
        triggeredBy,
        qualityBefore
      ]);

      scheduled.push({ days, scheduledAt: scheduledAt.toISOString() });
    }

    return { scheduled: scheduled.length, intervals: scheduled };

  } finally {
    await closeDb(db);
  }
}

/**
 * Get all pending replay checks that are due.
 */
async function getPendingReplays() {
  const db = await openDb();

  try {
    const now = new Date().toISOString();
    const pending = await dbAll(db, `
      SELECT id, execution_id, task_type, model, scheduled_at,
             interval_days, triggered_by, quality_before
      FROM feedback_schedule
      WHERE status = 'pending' AND scheduled_at <= ?
      ORDER BY scheduled_at ASC
    `, [now]);

    return pending;

  } finally {
    await closeDb(db);
  }
}

/**
 * Complete a replay check with the observed quality.
 */
async function completeReplay(scheduleId, qualityAfter) {
  const db = await openDb();

  try {
    await dbRun(db, `
      UPDATE feedback_schedule
      SET status = 'completed',
          quality_after = ?,
          completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
    `, [qualityAfter, scheduleId]);

    // Check if quality degraded
    const schedule = await dbGet(db,
      'SELECT quality_before, quality_after, task_type, model FROM feedback_schedule WHERE id = ?',
      [scheduleId]
    );

    const degradation = (schedule?.quality_before || 0) - qualityAfter;

    return {
      success: true,
      scheduleId,
      qualityBefore: schedule?.quality_before,
      qualityAfter,
      degradation,
      degraded: degradation > 0.05
    };

  } finally {
    await closeDb(db);
  }
}

/**
 * Skip a replay check (e.g., if it's no longer relevant).
 */
async function skipReplay(scheduleId, reason = 'manual_skip') {
  const db = await openDb();

  try {
    await dbRun(db, `
      UPDATE feedback_schedule
      SET status = 'skipped',
          completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
          triggered_by = triggered_by || ' [skipped: ' || ? || ']'
      WHERE id = ?
    `, [reason, scheduleId]);

    return { success: true, scheduleId };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Self-supervised quality signals from CI outcomes
// ---------------------------------------------------------------------------

/**
 * Find executions that have CI outcome data (tests_passed, build_success)
 * but haven't been used for quality prediction training.
 * These provide free labels that don't require human annotation.
 *
 * @param {number} limit - Maximum number of CI-labeled executions
 * @returns {object[]} Executions with CI-derived quality labels
 */
async function getCILabeledExecutions(limit = 50) {
  const db = await openDb();

  try {
    const rows = await dbAll(db, `
      SELECT
        el.execution_id, el.model, el.task_type, el.quality_score,
        el.confidence, el.consensus_score,
        qr.tests_passed, qr.tests_total, qr.build_success,
        qr.lint_errors, qr.overall_score AS rated_quality
      FROM execution_log el
      INNER JOIN quality_ratings qr ON el.execution_id = qr.execution_id
      WHERE qr.rating_source = 'ci_outcome'
        AND qr.tests_passed IS NOT NULL
      ORDER BY qr.timestamp DESC
      LIMIT ?
    `, [limit]);

    return rows.map(row => ({
      executionId: row.execution_id,
      model: row.model,
      taskType: row.task_type,
      predictedQuality: row.quality_score,
      ciQuality: computeCIQuality(row),
      predictionError: Math.abs((row.quality_score || 0) - computeCIQuality(row)),
      testPassRate: row.tests_total > 0 ? row.tests_passed / row.tests_total : null,
      buildSuccess: row.build_success === 1,
      lintErrors: row.lint_errors || 0
    }));

  } finally {
    await closeDb(db);
  }
}

/**
 * Compute a quality score from CI outcome signals.
 */
function computeCIQuality(row) {
  let score = 0;
  let weights = 0;

  if (row.tests_total && row.tests_total > 0) {
    const testRate = row.tests_passed / row.tests_total;
    score += testRate * 0.5;
    weights += 0.5;
  }

  if (row.build_success !== null) {
    score += (row.build_success ? 1.0 : 0.0) * 0.3;
    weights += 0.3;
  }

  if (row.lint_errors !== null) {
    const lintScore = Math.max(0, 1 - row.lint_errors * 0.1);
    score += lintScore * 0.2;
    weights += 0.2;
  }

  return weights > 0 ? score / weights : 0.5;
}

/**
 * Identify executions where automated quality prediction is most uncertain
 * relative to CI labels. These are the best candidates for human review.
 */
async function selectForHumanReview(limit = 10) {
  const ciLabeled = await getCILabeledExecutions(100);

  // Sort by prediction error descending
  ciLabeled.sort((a, b) => b.predictionError - a.predictionError);

  return ciLabeled.slice(0, limit);
}

// ---------------------------------------------------------------------------
// Core: Feedback statistics
// ---------------------------------------------------------------------------

/**
 * Get statistics about the feedback pipeline.
 */
async function getFeedbackStats() {
  const db = await openDb();

  try {
    const totalScheduled = await dbGet(db,
      'SELECT COUNT(*) AS cnt FROM feedback_schedule'
    );
    const pending = await dbGet(db,
      "SELECT COUNT(*) AS cnt FROM feedback_schedule WHERE status = 'pending'"
    );
    const completed = await dbGet(db,
      "SELECT COUNT(*) AS cnt FROM feedback_schedule WHERE status = 'completed'"
    );
    const degraded = await dbGet(db, `
      SELECT COUNT(*) AS cnt FROM feedback_schedule
      WHERE status = 'completed' AND quality_before - quality_after > 0.05
    `);

    const overdue = await dbGet(db, `
      SELECT COUNT(*) AS cnt FROM feedback_schedule
      WHERE status = 'pending' AND scheduled_at < datetime('now')
    `);

    return {
      total: totalScheduled?.cnt || 0,
      pending: pending?.cnt || 0,
      completed: completed?.cnt || 0,
      skipped: (totalScheduled?.cnt || 0) - (pending?.cnt || 0) - (completed?.cnt || 0),
      degraded: degraded?.cnt || 0,
      overdue: overdue?.cnt || 0
    };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  selectBatch,
  scheduleReplay,
  getPendingReplays,
  completeReplay,
  skipReplay,
  getCILabeledExecutions,
  selectForHumanReview,
  getFeedbackStats,
  // Exposed for testing
  estimateUncertainty,
  binaryEntropy,
  computeCIQuality
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
        case 'batch': {
          const poolSize = parseInt(args[1]) || DEFAULT_POOL_SIZE;
          const batchSize = parseInt(args[2]) || DEFAULT_BATCH_SIZE;
          const batch = await selectBatch(poolSize, batchSize);
          console.log(JSON.stringify(batch, null, 2));
          break;
        }
        case 'schedule': {
          const execId = args[1];
          const taskType = args[2];
          const model = args[3];
          const quality = parseFloat(args[4]) || 0.5;
          const result = await scheduleReplay(execId, taskType, model, quality, 'manual');
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'pending': {
          const pending = await getPendingReplays();
          console.log(JSON.stringify(pending, null, 2));
          break;
        }
        case 'ci-labeled': {
          const limit = parseInt(args[1]) || 50;
          const labeled = await getCILabeledExecutions(limit);
          console.log(JSON.stringify(labeled, null, 2));
          break;
        }
        case 'review': {
          const limit = parseInt(args[1]) || 10;
          const forReview = await selectForHumanReview(limit);
          console.log(JSON.stringify(forReview, null, 2));
          break;
        }
        case 'stats': {
          const stats = await getFeedbackStats();
          console.log(JSON.stringify(stats, null, 2));
          break;
        }
        default:
          console.log(`
Feedback Selector CLI (Active Learning)

Usage:
  feedback-selector.js batch [pool_size] [batch_size]
    Select batch of executions for quality annotation

  feedback-selector.js schedule <exec_id> <task_type> <model> <quality>
    Schedule Ebbinghaus replay for an execution

  feedback-selector.js pending
    Get overdue replay checks

  feedback-selector.js ci-labeled [limit]
    Get CI-labeled executions for training

  feedback-selector.js review [limit]
    Select executions needing human review

  feedback-selector.js stats
    Get feedback pipeline statistics
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  })();
}
