#!/usr/bin/env node
/**
 * Model Selector -- Bandit-Based Model Selection (Phase 1)
 *
 * Implements Thompson Sampling with sliding-window non-stationarity handling
 * and distribution shift detection for intelligent model selection.
 *
 * Features:
 *   1. Thompson Sampling: sample from Beta(alpha, beta) posteriors per model
 *   2. Sliding Window: only use recent WINDOW_SIZE executions for posteriors
 *   3. Distribution Shift Detection: KS statistic between recent/historical quality
 *   4. Regret Tracking: log counterfactual outcomes for all candidate models
 *   5. Cold-Start Transfer: delegate to task-embedder for new task types
 *
 * Usage:
 *   const { selectModel, updateOutcome } = require('./model-selector');
 *   const model = await selectModel('security', ['opus','sonnet','haiku','gpt-4o','gemini','fable']);
 *   // ... execute with model ...
 *   await updateOutcome('security', model, 0.85, { opus: 0.9, sonnet: 0.8, ... });
 *
 * Tables read:  bandit_state, execution_log, model_tuning
 * Tables written: bandit_state, execution_log (counterfactual_scores, selection_method)
 * Message bus: publishes to 'distribution-shift' channel
 */

const path = require('path');
const fs = require('fs');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DB_PATH = path.join(__dirname, 'db', 'learning.db');
const WINDOW_SIZE = 100;          // Sliding window for posteriors
const KS_THRESHOLD = 0.15;       // KS statistic threshold for shift detection
const MIN_SAMPLES_FOR_KS = 10;   // Minimum samples before running KS test
const MIN_SAMPLES_FOR_BANDIT = 3; // Below this, delegate to transfer learning
const EXPLORATION_BONUS = 0.1;    // Small bonus for under-explored models

// ---------------------------------------------------------------------------
// Database helpers (inline to avoid dependency on sqlite3 at import time)
// ---------------------------------------------------------------------------

let _sqlite3 = null;
function getSqlite3() {
  if (!_sqlite3) {
    try {
      _sqlite3 = require('sqlite3').verbose();
    } catch (e) {
      // Fallback: try from learning directory node_modules
      const localPath = path.join(__dirname, 'node_modules', 'sqlite3');
      _sqlite3 = require(localPath).verbose();
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
          db.run('PRAGMA busy_timeout = 5000', () => {
            resolve(db);
          });
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
// Statistics helpers
// ---------------------------------------------------------------------------

/**
 * Sample from a Beta distribution using the Joehnk method.
 * Returns a value in [0, 1].
 */
function sampleBeta(alpha, beta) {
  if (alpha <= 0) alpha = 0.001;
  if (beta <= 0) beta = 0.001;

  // Use the Gamma sampling method: Beta(a,b) = Ga/(Ga+Gb)
  const ga = sampleGamma(alpha);
  const gb = sampleGamma(beta);
  if (ga + gb === 0) return 0.5;
  return ga / (ga + gb);
}

/**
 * Sample from Gamma(shape, 1) using Marsaglia and Tsang's method.
 */
function sampleGamma(shape) {
  if (shape < 1) {
    // Boost: Gamma(a) = Gamma(a+1) * U^(1/a)
    return sampleGamma(shape + 1) * Math.pow(Math.random(), 1 / shape);
  }

  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x, v;
    do {
      x = normalRandom();
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = Math.random();

    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

/**
 * Standard normal random using Box-Muller transform.
 */
function normalRandom() {
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/**
 * Kolmogorov-Smirnov statistic between two arrays of values.
 * Returns D statistic in [0, 1].
 */
function ksStatistic(sample1, sample2) {
  if (sample1.length === 0 || sample2.length === 0) return 0;

  const all = [
    ...sample1.map(v => ({ v, group: 1 })),
    ...sample2.map(v => ({ v, group: 2 }))
  ].sort((a, b) => a.v - b.v);

  const n1 = sample1.length;
  const n2 = sample2.length;
  let cdf1 = 0, cdf2 = 0;
  let maxD = 0;

  for (const item of all) {
    if (item.group === 1) cdf1 += 1 / n1;
    else cdf2 += 1 / n2;
    const d = Math.abs(cdf1 - cdf2);
    if (d > maxD) maxD = d;
  }

  return maxD;
}

// ---------------------------------------------------------------------------
// Core: Load or initialize bandit state
// ---------------------------------------------------------------------------

/**
 * Load bandit posteriors from database. Initialize with uniform priors
 * (alpha=1, beta=1) for any missing (model, task_type) pairs.
 */
async function loadBanditState(db, taskType, candidateModels) {
  const states = new Map();

  // Load existing state
  const rows = await dbAll(
    db,
    'SELECT model, alpha, beta, total_pulls, cumulative_regret, window_start FROM bandit_state WHERE task_type = ?',
    [taskType]
  );

  for (const row of rows) {
    states.set(row.model, {
      alpha: row.alpha,
      beta: row.beta,
      totalPulls: row.total_pulls,
      cumulativeRegret: row.cumulative_regret,
      windowStart: row.window_start
    });
  }

  // Initialize missing models with uniform priors
  for (const model of candidateModels) {
    if (!states.has(model)) {
      states.set(model, {
        alpha: 1.0,
        beta: 1.0,
        totalPulls: 0,
        cumulativeRegret: 0.0,
        windowStart: null
      });
    }
  }

  return states;
}

/**
 * Initialize posteriors from execution_log data for models that have
 * historical executions but no bandit_state entry yet.
 */
async function initializeFromHistory(db, taskType, candidateModels) {
  const states = new Map();

  for (const model of candidateModels) {
    // Count successes and failures in recent window
    const row = await dbGet(db, `
      SELECT
        SUM(CASE WHEN quality_score >= 0.6 THEN 1 ELSE 0 END) AS successes,
        SUM(CASE WHEN quality_score < 0.6 THEN 1 ELSE 0 END) AS failures,
        COUNT(*) AS total
      FROM execution_log
      WHERE model = ? AND task_type = ?
        AND quality_score IS NOT NULL
      ORDER BY timestamp DESC
      LIMIT ?
    `, [model, taskType, WINDOW_SIZE]);

    const successes = row?.successes || 0;
    const failures = row?.failures || 0;

    states.set(model, {
      alpha: 1.0 + successes,
      beta: 1.0 + failures,
      totalPulls: successes + failures,
      cumulativeRegret: 0.0,
      windowStart: null
    });
  }

  return states;
}

// ---------------------------------------------------------------------------
// Core: Thompson Sampling selection
// ---------------------------------------------------------------------------

/**
 * Select the best model using Thompson Sampling.
 *
 * For each candidate model, sample from its Beta(alpha, beta) posterior.
 * Return the model with the highest sample. This naturally balances
 * exploration (uncertain models get wide samples) and exploitation
 * (high-performing models have peaked distributions).
 *
 * @param {string} taskType - The task type to select a model for
 * @param {string[]} candidateModels - List of candidate model names
 * @param {object} options - Optional: { strategy, db }
 * @returns {object} { model, score, method, allScores }
 */
async function selectModel(taskType, candidateModels, options = {}) {
  if (!candidateModels || candidateModels.length === 0) {
    throw new Error('candidateModels must be a non-empty array');
  }
  if (candidateModels.length === 1) {
    return {
      model: candidateModels[0],
      score: 1.0,
      method: 'single_candidate',
      allScores: { [candidateModels[0]]: 1.0 }
    };
  }

  const ownDb = !options.db;
  const db = options.db || await openDb();

  try {
    // Load bandit state
    let states = await loadBanditState(db, taskType, candidateModels);

    // Check if we have enough data for bandit selection
    const totalPulls = Array.from(states.values()).reduce((s, st) => s + st.totalPulls, 0);

    if (totalPulls < MIN_SAMPLES_FOR_BANDIT) {
      // Cold start: try transfer learning
      let transferResult = null;
      try {
        const taskEmbedder = require('./task-embedder');
        transferResult = await taskEmbedder.transferPriors(db, taskType, candidateModels);
      } catch (_) {
        // task-embedder not available, fall through
      }

      if (transferResult && transferResult.transferred) {
        states = transferResult.states;
      } else {
        // Initialize from any historical execution data
        states = await initializeFromHistory(db, taskType, candidateModels);
      }
    }

    // Run distribution shift detection
    await detectShifts(db, taskType, states);

    // Thompson Sampling: sample from each model's Beta posterior
    const samples = {};
    for (const model of candidateModels) {
      const state = states.get(model);
      if (!state) continue;

      let sample = sampleBeta(state.alpha, state.beta);

      // Apply exploration bonus for under-explored models
      if (state.totalPulls < 5) {
        sample += EXPLORATION_BONUS * (1 - state.totalPulls / 5);
      }

      samples[model] = Math.max(0, Math.min(1, sample));
    }

    // Select model with highest sample
    let bestModel = candidateModels[0];
    let bestScore = -Infinity;
    for (const [model, score] of Object.entries(samples)) {
      if (score > bestScore) {
        bestScore = score;
        bestModel = model;
      }
    }

    return {
      model: bestModel,
      score: bestScore,
      method: totalPulls < MIN_SAMPLES_FOR_BANDIT ? 'transfer' : 'thompson',
      allScores: samples,
      banditState: Object.fromEntries(
        Array.from(states.entries()).map(([m, s]) => [m, { alpha: s.alpha, beta: s.beta, pulls: s.totalPulls }])
      )
    };

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Update outcome after model execution
// ---------------------------------------------------------------------------

/**
 * Update bandit posteriors after observing an execution outcome.
 *
 * @param {string} taskType - Task type
 * @param {string} selectedModel - The model that was selected and executed
 * @param {number} qualityScore - Observed quality (0-1)
 * @param {object} counterfactualScores - Predicted scores for non-selected models
 * @param {object} options - Optional: { db, executionId }
 */
async function updateOutcome(taskType, selectedModel, qualityScore, counterfactualScores = {}, options = {}) {
  const ownDb = !options.db;
  const db = options.db || await openDb();

  try {
    // Convert quality to binary success/failure for Beta update
    const success = qualityScore >= 0.6;

    // Update selected model's posterior
    if (success) {
      await dbRun(db, `
        INSERT INTO bandit_state (model, task_type, alpha, beta, total_pulls, last_updated)
        VALUES (?, ?, 2.0, 1.0, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        ON CONFLICT(model, task_type) DO UPDATE SET
          alpha = alpha + 1.0,
          total_pulls = total_pulls + 1,
          last_updated = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      `, [selectedModel, taskType]);
    } else {
      await dbRun(db, `
        INSERT INTO bandit_state (model, task_type, alpha, beta, total_pulls, last_updated)
        VALUES (?, ?, 1.0, 2.0, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        ON CONFLICT(model, task_type) DO UPDATE SET
          beta = beta + 1.0,
          total_pulls = total_pulls + 1,
          last_updated = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      `, [selectedModel, taskType]);
    }

    // Compute regret: difference between best counterfactual and actual
    const allScores = { [selectedModel]: qualityScore, ...counterfactualScores };
    const maxPredicted = Math.max(...Object.values(allScores));
    const regret = maxPredicted - qualityScore;

    if (regret > 0) {
      await dbRun(db, `
        UPDATE bandit_state
        SET cumulative_regret = cumulative_regret + ?
        WHERE model = ? AND task_type = ?
      `, [regret, selectedModel, taskType]);
    }

    // Log counterfactual scores to execution_log if executionId provided
    if (options.executionId) {
      await dbRun(db, `
        UPDATE execution_log
        SET counterfactual_scores = ?,
            selection_method = 'thompson'
        WHERE execution_id = ?
      `, [JSON.stringify(counterfactualScores), options.executionId]);
    }

    // Apply sliding window decay: if total_pulls exceeds WINDOW_SIZE,
    // scale down alpha and beta proportionally
    const state = await dbGet(db,
      'SELECT alpha, beta, total_pulls FROM bandit_state WHERE model = ? AND task_type = ?',
      [selectedModel, taskType]
    );

    if (state && state.total_pulls > WINDOW_SIZE) {
      const scaleFactor = WINDOW_SIZE / state.total_pulls;
      const newAlpha = Math.max(1.0, state.alpha * scaleFactor);
      const newBeta = Math.max(1.0, state.beta * scaleFactor);
      await dbRun(db, `
        UPDATE bandit_state
        SET alpha = ?, beta = ?, total_pulls = ?,
            window_start = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE model = ? AND task_type = ?
      `, [newAlpha, newBeta, WINDOW_SIZE, selectedModel, taskType]);
    }

    return { success: true, regret, updatedModel: selectedModel };

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Distribution shift detection
// ---------------------------------------------------------------------------

/**
 * Detect distribution shifts by comparing recent quality to historical quality.
 * Uses Kolmogorov-Smirnov test. If KS > threshold, reset posteriors to
 * uniform priors to force re-exploration.
 */
async function detectShifts(db, taskType, states) {
  let messageBus = null;
  try {
    messageBus = require('./shared/message-bus');
  } catch (_) {}

  for (const [model, state] of states.entries()) {
    if (state.totalPulls < MIN_SAMPLES_FOR_KS) continue;

    // Get recent week quality scores
    const recentRows = await dbAll(db, `
      SELECT quality_score FROM execution_log
      WHERE model = ? AND task_type = ? AND quality_score IS NOT NULL
        AND timestamp > datetime('now', '-7 days')
      ORDER BY timestamp DESC
      LIMIT 50
    `, [model, taskType]);

    // Get previous month quality scores (excluding recent week)
    const historicalRows = await dbAll(db, `
      SELECT quality_score FROM execution_log
      WHERE model = ? AND task_type = ? AND quality_score IS NOT NULL
        AND timestamp <= datetime('now', '-7 days')
        AND timestamp > datetime('now', '-37 days')
      ORDER BY timestamp DESC
      LIMIT 100
    `, [model, taskType]);

    if (recentRows.length < MIN_SAMPLES_FOR_KS || historicalRows.length < MIN_SAMPLES_FOR_KS) {
      continue;
    }

    const recentScores = recentRows.map(r => r.quality_score);
    const historicalScores = historicalRows.map(r => r.quality_score);

    const ks = ksStatistic(recentScores, historicalScores);

    if (ks > KS_THRESHOLD) {
      // Distribution shift detected! Reset posteriors.
      state.alpha = 1.0;
      state.beta = 1.0;

      await dbRun(db, `
        UPDATE bandit_state
        SET alpha = 1.0, beta = 1.0,
            last_shift_detected = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            shift_count = shift_count + 1,
            last_updated = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE model = ? AND task_type = ?
      `, [model, taskType]);

      // Publish shift event
      if (messageBus) {
        try {
          messageBus.postMessage('distribution-shift', {
            type: 'shift_detected',
            model,
            taskType,
            ksStatistic: ks,
            recentMean: recentScores.reduce((a, b) => a + b, 0) / recentScores.length,
            historicalMean: historicalScores.reduce((a, b) => a + b, 0) / historicalScores.length,
            recentN: recentScores.length,
            historicalN: historicalScores.length,
            action: 'posteriors_reset'
          });
        } catch (_) {}
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Core: Get bandit state summary
// ---------------------------------------------------------------------------

/**
 * Get a summary of all bandit states for monitoring/visualization.
 */
async function getBanditSummary(taskType = null) {
  const db = await openDb();
  try {
    let sql = `
      SELECT model, task_type, alpha, beta, total_pulls,
             cumulative_regret, last_shift_detected, shift_count,
             alpha / (alpha + beta) AS expected_value,
             last_updated
      FROM bandit_state
    `;
    const params = [];
    if (taskType) {
      sql += ' WHERE task_type = ?';
      params.push(taskType);
    }
    sql += ' ORDER BY task_type, expected_value DESC';

    const rows = await dbAll(db, sql, params);

    // Group by task_type
    const summary = {};
    for (const row of rows) {
      if (!summary[row.task_type]) {
        summary[row.task_type] = [];
      }
      summary[row.task_type].push({
        model: row.model,
        alpha: row.alpha,
        beta: row.beta,
        expectedValue: row.expected_value,
        totalPulls: row.total_pulls,
        cumulativeRegret: row.cumulative_regret,
        shiftCount: row.shift_count,
        lastShift: row.last_shift_detected,
        lastUpdated: row.last_updated
      });
    }

    return summary;

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Reset bandit state
// ---------------------------------------------------------------------------

/**
 * Reset bandit posteriors for a specific model/task or all entries.
 */
async function resetBanditState(taskType = null, model = null) {
  const db = await openDb();
  try {
    if (taskType && model) {
      await dbRun(db,
        'UPDATE bandit_state SET alpha = 1.0, beta = 1.0, total_pulls = 0, cumulative_regret = 0.0 WHERE model = ? AND task_type = ?',
        [model, taskType]
      );
    } else if (taskType) {
      await dbRun(db,
        'UPDATE bandit_state SET alpha = 1.0, beta = 1.0, total_pulls = 0, cumulative_regret = 0.0 WHERE task_type = ?',
        [taskType]
      );
    } else {
      await dbRun(db,
        'UPDATE bandit_state SET alpha = 1.0, beta = 1.0, total_pulls = 0, cumulative_regret = 0.0'
      );
    }
    return { success: true };
  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  selectModel,
  updateOutcome,
  detectShifts,
  getBanditSummary,
  resetBanditState,
  loadBanditState,
  initializeFromHistory,
  // Expose stats helpers for testing
  sampleBeta,
  sampleGamma,
  ksStatistic
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
        case 'select': {
          const taskType = args[1] || 'code_review';
          const models = (args[2] || 'opus,sonnet,haiku,gpt-4o,gemini,fable').split(',');
          const result = await selectModel(taskType, models);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'update': {
          const taskType = args[1];
          const model = args[2];
          const quality = parseFloat(args[3]);
          const result = await updateOutcome(taskType, model, quality);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'summary': {
          const taskType = args[1] || null;
          const summary = await getBanditSummary(taskType);
          console.log(JSON.stringify(summary, null, 2));
          break;
        }
        case 'reset': {
          const taskType = args[1] || null;
          const model = args[2] || null;
          const result = await resetBanditState(taskType, model);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        default:
          console.log(`
Model Selector CLI (Thompson Sampling)

Usage:
  model-selector.js select <task_type> [models]
    Select best model via Thompson Sampling
    models: comma-separated list (default: opus,sonnet,haiku,gpt-4o,gemini,fable)

  model-selector.js update <task_type> <model> <quality_score>
    Update bandit posteriors after observing outcome

  model-selector.js summary [task_type]
    Show bandit state summary

  model-selector.js reset [task_type] [model]
    Reset bandit posteriors to uniform priors
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  })();
}
