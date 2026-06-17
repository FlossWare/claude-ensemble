#!/usr/bin/env node
/**
 * Meta-Optimizer -- Continual Learning and Meta-Optimization (Phase 4)
 *
 * The "learning about learning" layer. Tracks which optimization strategies
 * produce the best quality improvements with minimal negative backward transfer.
 *
 * Features:
 *   1. Reptile-Style Interpolation: stabilize parameter updates
 *   2. Backward Transfer Monitoring: detect cross-task quality degradation
 *   3. Stale Knowledge Retirement: age out unused parameter tunings
 *   4. Meta-Optimizer: learn which strategies work best
 *   5. Pareto Front Computation: quality/cost/latency trade-off surfaces
 *
 * Usage:
 *   const meta = require('./meta-optimizer');
 *   await meta.reptileUpdate('opus', 'security', newParams, confidence);
 *   const bwt = await meta.checkBackwardTransfer('opus', 'security');
 *   await meta.retireStaleKnowledge();
 *   const pareto = await meta.computeParetoFront('security');
 *
 * Tables read:  parameter_tuning, execution_log, model_performance
 * Tables written: parameter_tuning, pareto_fronts, meta_insights
 * Message bus: 'negative-transfer', 'pareto-update', 'meta-insight'
 */

const path = require('path');

const DB_PATH = path.join(__dirname, 'db', 'learning.db');

// Configuration
const DEFAULT_BETA = 0.3;        // Reptile interpolation rate
const BWT_DEGRADATION_THRESHOLD = 0.05; // 5% quality drop triggers rollback
const STALE_DAYS = 30;           // Days before marking as stale
const RETIRED_DAYS = 90;         // Days of staleness before retirement
const PARETO_RECOMPUTE_INTERVAL = 25; // executions between Pareto recompute

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
// Phase 4a: Reptile-style parameter interpolation
// ---------------------------------------------------------------------------

/**
 * Apply Reptile-style interpolation when updating parameters.
 * Instead of overwriting:
 *   new_params[key] = old_params[key] + beta * (discovered[key] - old_params[key])
 *
 * This stabilizes parameter evolution and prevents catastrophic forgetting.
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @param {object} discoveredParams - Newly discovered optimal parameters
 * @param {number} confidence - Confidence in discovered params (0-1)
 * @param {object} options - { db, beta }
 * @returns {object} { model, taskType, oldParams, newParams, beta, interpolated }
 */
async function reptileUpdate(model, taskType, discoveredParams, confidence = 0.5, options = {}) {
  const ownDb = !options.db;
  const db = options.db || await openDb();

  try {
    // Get existing parameters
    const existing = await dbGet(db,
      'SELECT optimal_params, version, previous_params, interpolation_beta FROM parameter_tuning WHERE model = ? AND task_type = ?',
      [model, taskType]
    );

    let oldParams = {};
    if (existing && existing.optimal_params) {
      try { oldParams = JSON.parse(existing.optimal_params); } catch (_) {}
    }

    // Compute adaptive beta: higher confidence = larger step
    // beta = base_beta * confidence * (1 / (1 + stddev))
    // For simplicity, we use confidence directly as a modifier
    const baseBeta = options.beta || existing?.interpolation_beta || DEFAULT_BETA;
    const adaptiveBeta = baseBeta * confidence;

    // Interpolate each parameter
    const interpolated = {};
    const allKeys = new Set([...Object.keys(oldParams), ...Object.keys(discoveredParams)]);

    for (const key of allKeys) {
      const oldVal = oldParams[key];
      const newVal = discoveredParams[key];

      if (newVal === undefined) {
        // Keep old value if discovered doesn't have it
        interpolated[key] = oldVal;
      } else if (oldVal === undefined || typeof oldVal !== 'number' || typeof newVal !== 'number') {
        // Non-numeric or new key: use discovered value
        interpolated[key] = newVal;
      } else {
        // Reptile interpolation
        interpolated[key] = oldVal + adaptiveBeta * (newVal - oldVal);
        // Round to reasonable precision
        interpolated[key] = Math.round(interpolated[key] * 10000) / 10000;
      }
    }

    // Store the update
    const version = existing ? (existing.version || 0) + 1 : 1;

    await dbRun(db, `
      INSERT INTO parameter_tuning (model, task_type, optimal_params, version, previous_params,
                                     interpolation_beta, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
      ON CONFLICT(model, task_type) DO UPDATE SET
        optimal_params = excluded.optimal_params,
        version = excluded.version,
        previous_params = excluded.previous_params,
        interpolation_beta = excluded.interpolation_beta,
        status = 'active',
        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    `, [
      model, taskType,
      JSON.stringify(interpolated),
      version,
      JSON.stringify(oldParams),
      adaptiveBeta
    ]);

    // Schedule Ebbinghaus replay for backward transfer check
    try {
      const feedbackSelector = require('./feedback-selector');
      await feedbackSelector.scheduleReplay(
        `reptile_${model}_${taskType}_v${version}`,
        taskType, model,
        confidence,
        `reptile_update_v${version}`
      );
    } catch (_) {}

    return {
      model,
      taskType,
      oldParams,
      newParams: interpolated,
      beta: adaptiveBeta,
      version,
      interpolated: true
    };

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Phase 4b: Backward Transfer monitoring
// ---------------------------------------------------------------------------

/**
 * Check if a parameter update for one model/task negatively impacts
 * other task types. Compares recent quality to pre-update quality
 * for all other task types using the same model.
 *
 * @param {string} model - Model that was updated
 * @param {string} updatedTaskType - Task type that was optimized
 * @param {object} options - { db, threshold }
 * @returns {object} { degradedTasks, allTasks, rollbackRecommended }
 */
async function checkBackwardTransfer(model, updatedTaskType, options = {}) {
  const ownDb = !options.db;
  const db = options.db || await openDb();
  const threshold = options.threshold || BWT_DEGRADATION_THRESHOLD;

  try {
    // Get all task types for this model
    const taskTypes = await dbAll(db, `
      SELECT DISTINCT task_type FROM execution_log
      WHERE model = ? AND task_type != ? AND task_type IS NOT NULL
        AND quality_score IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= 5
    `, [model, updatedTaskType]);

    const degradedTasks = [];
    const allTasks = [];

    for (const { task_type } of taskTypes) {
      // Recent quality (last 7 days)
      const recent = await dbGet(db, `
        SELECT AVG(quality_score) AS avg_q, COUNT(*) AS cnt
        FROM execution_log
        WHERE model = ? AND task_type = ? AND quality_score IS NOT NULL
          AND timestamp > datetime('now', '-7 days')
      `, [model, task_type]);

      // Previous quality (8-37 days ago)
      const previous = await dbGet(db, `
        SELECT AVG(quality_score) AS avg_q, COUNT(*) AS cnt
        FROM execution_log
        WHERE model = ? AND task_type = ? AND quality_score IS NOT NULL
          AND timestamp <= datetime('now', '-7 days')
          AND timestamp > datetime('now', '-37 days')
      `, [model, task_type]);

      if (!recent || !previous || recent.cnt < 3 || previous.cnt < 3) continue;

      const delta = recent.avg_q - previous.avg_q;
      const result = {
        taskType: task_type,
        recentQuality: recent.avg_q,
        previousQuality: previous.avg_q,
        delta,
        recentSamples: recent.cnt,
        previousSamples: previous.cnt,
        degraded: delta < -threshold
      };

      allTasks.push(result);
      if (result.degraded) {
        degradedTasks.push(result);
      }
    }

    // If any tasks degraded, notify and record
    if (degradedTasks.length > 0) {
      notify('negative-transfer', {
        type: 'backward_transfer_degradation',
        model,
        updatedTaskType,
        degradedTasks,
        recommendation: 'rollback_suggested'
      });

      // Record BWT impact in parameter_tuning
      const bwtImpact = {};
      for (const t of degradedTasks) {
        bwtImpact[t.taskType] = t.delta;
      }
      await dbRun(db, `
        UPDATE parameter_tuning
        SET bwt_impact = ?
        WHERE model = ? AND task_type = ?
      `, [JSON.stringify(bwtImpact), model, updatedTaskType]);
    }

    return {
      model,
      updatedTaskType,
      degradedTasks,
      allTasks,
      rollbackRecommended: degradedTasks.length > 0
    };

  } finally {
    if (ownDb) await closeDb(db);
  }
}

/**
 * Roll back parameters to previous version if BWT is detected.
 */
async function rollbackParameters(model, taskType) {
  const db = await openDb();

  try {
    const current = await dbGet(db,
      'SELECT optimal_params, previous_params, version FROM parameter_tuning WHERE model = ? AND task_type = ?',
      [model, taskType]
    );

    if (!current || !current.previous_params || current.previous_params === '{}') {
      return { success: false, reason: 'no previous params to rollback to' };
    }

    await dbRun(db, `
      UPDATE parameter_tuning
      SET optimal_params = previous_params,
          previous_params = optimal_params,
          version = version + 1,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE model = ? AND task_type = ?
    `, [model, taskType]);

    // Record meta-insight
    await dbRun(db, `
      INSERT INTO meta_insights (insight_type, task_type, model, update_description,
                                  quality_delta, bwt_impact, recommendation)
      VALUES ('parameter_rollback', ?, ?, 'Rolled back due to negative backward transfer',
              0, 0, 'Monitor quality after rollback')
    `, [taskType, model]);

    return {
      success: true,
      model,
      taskType,
      rolledBackFrom: current.optimal_params,
      rolledBackTo: current.previous_params,
      newVersion: (current.version || 0) + 1
    };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Phase 4c: Stale knowledge retirement
// ---------------------------------------------------------------------------

/**
 * Mark parameter tunings as stale or retired based on age.
 * - Not updated in 30 days: mark as 'stale' (deprioritized but preserved)
 * - Stale for 90+ days: mark as 'retired' (archived, not used)
 */
async function retireStaleKnowledge() {
  const db = await openDb();

  try {
    // Mark stale (not updated in STALE_DAYS)
    const staleResult = await dbRun(db, `
      UPDATE parameter_tuning
      SET status = 'stale'
      WHERE status = 'active'
        AND updated_at < datetime('now', '-' || ? || ' days')
    `, [STALE_DAYS]);

    // Mark retired (stale for RETIRED_DAYS)
    const retiredResult = await dbRun(db, `
      UPDATE parameter_tuning
      SET status = 'retired'
      WHERE status = 'stale'
        AND updated_at < datetime('now', '-' || ? || ' days')
    `, [STALE_DAYS + RETIRED_DAYS]);

    const stats = {
      newlyStale: staleResult.changes,
      newlyRetired: retiredResult.changes,
      timestamp: new Date().toISOString()
    };

    if (stats.newlyStale > 0 || stats.newlyRetired > 0) {
      notify('meta-insight', {
        type: 'stale_knowledge_retirement',
        ...stats
      });
    }

    return stats;

  } finally {
    await closeDb(db);
  }
}

/**
 * Get status counts for parameter tuning entries.
 */
async function getKnowledgeStatus() {
  const db = await openDb();

  try {
    const rows = await dbAll(db, `
      SELECT COALESCE(status, 'active') AS status, COUNT(*) AS cnt
      FROM parameter_tuning
      GROUP BY status
    `);

    const status = {};
    for (const row of rows) {
      status[row.status] = row.cnt;
    }
    return status;

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Phase 4d: Meta-optimizer -- learning about learning
// ---------------------------------------------------------------------------

/**
 * Record a meta-insight: track the causal chain
 * [parameter_update -> quality_change -> BWT_impact]
 * and learn which optimization strategies work best.
 */
async function recordMetaInsight(insightType, taskType, model, details = {}) {
  const db = await openDb();

  try {
    const netBenefit = (details.qualityDelta || 0) - Math.abs(details.bwtImpact || 0);

    await dbRun(db, `
      INSERT INTO meta_insights (
        insight_type, task_type, model, update_description,
        quality_delta, bwt_impact, cost_delta, net_benefit,
        causal_chain, recommendation
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `, [
      insightType,
      taskType,
      model,
      details.description || '',
      details.qualityDelta || 0,
      details.bwtImpact || 0,
      details.costDelta || 0,
      netBenefit,
      JSON.stringify(details.causalChain || {}),
      details.recommendation || ''
    ]);

    notify('meta-insight', {
      type: 'new_insight',
      insightType,
      taskType,
      model,
      netBenefit,
      recommendation: details.recommendation
    });

    return { success: true, netBenefit };

  } finally {
    await closeDb(db);
  }
}

/**
 * Analyze meta-insights to determine which types of updates produce
 * the best results.
 */
async function getMetaAnalysis() {
  const db = await openDb();

  try {
    // Aggregate by insight type
    const byType = await dbAll(db, `
      SELECT
        insight_type,
        COUNT(*) AS count,
        AVG(quality_delta) AS avg_quality_delta,
        AVG(bwt_impact) AS avg_bwt_impact,
        AVG(net_benefit) AS avg_net_benefit,
        MIN(net_benefit) AS worst_outcome,
        MAX(net_benefit) AS best_outcome
      FROM meta_insights
      GROUP BY insight_type
      ORDER BY avg_net_benefit DESC
    `);

    // Overall statistics
    const overall = await dbGet(db, `
      SELECT
        COUNT(*) AS total_insights,
        AVG(quality_delta) AS avg_quality_delta,
        AVG(net_benefit) AS avg_net_benefit,
        SUM(CASE WHEN net_benefit > 0 THEN 1 ELSE 0 END) AS positive_outcomes,
        SUM(CASE WHEN net_benefit <= 0 THEN 1 ELSE 0 END) AS negative_outcomes
      FROM meta_insights
    `);

    // Recent trend (last 30 days)
    const trend = await dbAll(db, `
      SELECT
        DATE(timestamp) AS date,
        AVG(net_benefit) AS avg_benefit,
        COUNT(*) AS count
      FROM meta_insights
      WHERE timestamp > datetime('now', '-30 days')
      GROUP BY DATE(timestamp)
      ORDER BY date ASC
    `);

    return {
      byInsightType: byType,
      overall: overall || {},
      recentTrend: trend,
      recommendation: generateMetaRecommendation(byType, overall)
    };

  } finally {
    await closeDb(db);
  }
}

/**
 * Generate a recommendation based on meta-analysis.
 */
function generateMetaRecommendation(byType, overall) {
  if (!byType || byType.length === 0) {
    return 'Insufficient data for meta-recommendations. Continue collecting insights.';
  }

  const best = byType[0]; // Already sorted by avg_net_benefit DESC
  const worst = byType[byType.length - 1];

  const parts = [];

  if (best && best.avg_net_benefit > 0.05) {
    parts.push(`Best strategy: '${best.insight_type}' (avg benefit: +${best.avg_net_benefit.toFixed(3)})`);
  }

  if (worst && worst.avg_net_benefit < -0.02) {
    parts.push(`Avoid: '${worst.insight_type}' (avg impact: ${worst.avg_net_benefit.toFixed(3)})`);
  }

  if (overall && overall.positive_outcomes > 0) {
    const positiveRate = overall.positive_outcomes / (overall.total_insights || 1);
    parts.push(`Overall success rate: ${(positiveRate * 100).toFixed(1)}%`);
  }

  return parts.length > 0 ? parts.join('. ') : 'Performance is stable. No changes recommended.';
}

// ---------------------------------------------------------------------------
// Phase 4e: Pareto front computation
// ---------------------------------------------------------------------------

/**
 * Compute the Pareto-optimal set of model configurations for a task type
 * along quality/cost/latency dimensions using dominated sorting.
 *
 * A configuration dominates another if it is at least as good on ALL
 * objectives and strictly better on at least one.
 *
 * @param {string} taskType - Task type to compute Pareto front for
 * @returns {object} { paretoOptimal, dominated, allConfigurations }
 */
async function computeParetoFront(taskType) {
  const db = await openDb();

  try {
    // Get average quality, cost, and latency per model for this task type
    const configs = await dbAll(db, `
      SELECT
        model,
        AVG(quality_score) AS avg_quality,
        AVG(cost_usd) AS avg_cost,
        AVG(duration_ms) AS avg_duration,
        COUNT(*) AS sample_count
      FROM execution_log
      WHERE task_type = ? AND quality_score IS NOT NULL
        AND model NOT IN ('test-model', 'unknown', 'test')
      GROUP BY model
      HAVING COUNT(*) >= 3
    `, [taskType]);

    if (configs.length === 0) {
      return { paretoOptimal: [], dominated: [], allConfigurations: [] };
    }

    // Also get per-strategy configurations (if strategy is recorded)
    const strategyConfigs = await dbAll(db, `
      SELECT
        model || '_' || COALESCE(strategy, 'default') AS config_id,
        model,
        strategy,
        AVG(quality_score) AS avg_quality,
        AVG(cost_usd) AS avg_cost,
        AVG(duration_ms) AS avg_duration,
        COUNT(*) AS sample_count
      FROM execution_log
      WHERE task_type = ? AND quality_score IS NOT NULL
        AND model NOT IN ('test-model', 'unknown', 'test')
      GROUP BY model, strategy
      HAVING COUNT(*) >= 2
    `, [taskType]);

    // Merge configs (prefer strategy-specific if available)
    const allConfigs = [];
    const seen = new Set();

    for (const row of strategyConfigs) {
      const id = `${row.model}_${row.strategy || 'default'}`;
      if (!seen.has(id)) {
        seen.add(id);
        allConfigs.push({
          id,
          model: row.model,
          strategy: row.strategy || 'default',
          quality: row.avg_quality,
          cost: row.avg_cost,
          latency: row.avg_duration,
          sampleCount: row.sample_count
        });
      }
    }

    // Add plain model configs if not covered
    for (const row of configs) {
      const id = `${row.model}_default`;
      if (!seen.has(id)) {
        seen.add(id);
        allConfigs.push({
          id,
          model: row.model,
          strategy: 'default',
          quality: row.avg_quality,
          cost: row.avg_cost,
          latency: row.avg_duration,
          sampleCount: row.sample_count
        });
      }
    }

    // Dominated sorting: check each pair
    // Objectives: maximize quality, minimize cost, minimize latency
    const dominated = new Set();

    for (let i = 0; i < allConfigs.length; i++) {
      for (let j = 0; j < allConfigs.length; j++) {
        if (i === j || dominated.has(i)) continue;

        const a = allConfigs[i];
        const b = allConfigs[j];

        // b dominates a if b is at least as good on all objectives
        // and strictly better on at least one
        const bAtLeastAsGoodQuality = b.quality >= a.quality;
        const bAtLeastAsGoodCost = b.cost <= a.cost;
        const bAtLeastAsGoodLatency = b.latency <= a.latency;

        const bStrictlyBetterQuality = b.quality > a.quality;
        const bStrictlyBetterCost = b.cost < a.cost;
        const bStrictlyBetterLatency = b.latency < a.latency;

        if (bAtLeastAsGoodQuality && bAtLeastAsGoodCost && bAtLeastAsGoodLatency &&
            (bStrictlyBetterQuality || bStrictlyBetterCost || bStrictlyBetterLatency)) {
          dominated.add(i);
        }
      }
    }

    // Store results
    const paretoOptimal = [];
    const dominatedConfigs = [];

    // Clear old Pareto front for this task type
    await dbRun(db, 'DELETE FROM pareto_fronts WHERE task_type = ?', [taskType]);

    for (let i = 0; i < allConfigs.length; i++) {
      const config = allConfigs[i];
      const isOptimal = !dominated.has(i);

      // Find who dominates this config (if dominated)
      let dominatedByIdx = null;
      if (!isOptimal) {
        for (let j = 0; j < allConfigs.length; j++) {
          if (i === j) continue;
          const b = allConfigs[j];
          if (b.quality >= config.quality && b.cost <= config.cost && b.latency <= config.latency &&
              (b.quality > config.quality || b.cost < config.cost || b.latency < config.latency)) {
            dominatedByIdx = j;
            break;
          }
        }
      }

      const result = await dbRun(db, `
        INSERT INTO pareto_fronts (task_type, configuration, quality, cost, latency,
                                    is_pareto_optimal, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
      `, [
        taskType,
        JSON.stringify({ model: config.model, strategy: config.strategy }),
        config.quality,
        config.cost,
        config.latency,
        isOptimal ? 1 : 0
      ]);

      if (isOptimal) {
        paretoOptimal.push({ ...config, dbId: result.lastID });
      } else {
        dominatedConfigs.push({ ...config, dominatedBy: dominatedByIdx !== null ? allConfigs[dominatedByIdx].id : null });
      }
    }

    notify('pareto-update', {
      type: 'pareto_front_computed',
      taskType,
      paretoOptimalCount: paretoOptimal.length,
      dominatedCount: dominatedConfigs.length,
      configurations: paretoOptimal.map(c => ({
        model: c.model, quality: c.quality, cost: c.cost, latency: c.latency
      }))
    });

    return {
      taskType,
      paretoOptimal,
      dominated: dominatedConfigs,
      allConfigurations: allConfigs
    };

  } finally {
    await closeDb(db);
  }
}

/**
 * Select a configuration from the Pareto front based on strategy.
 *
 * @param {string} taskType - Task type
 * @param {string} strategy - 'QualityFirst', 'CostOptimized', 'Balanced'
 * @returns {object|null} Selected configuration
 */
async function selectFromParetoFront(taskType, strategy = 'Balanced') {
  const db = await openDb();

  try {
    const paretoConfigs = await dbAll(db, `
      SELECT configuration, quality, cost, latency
      FROM pareto_fronts
      WHERE task_type = ? AND is_pareto_optimal = 1
      ORDER BY quality DESC
    `, [taskType]);

    if (paretoConfigs.length === 0) {
      return null;
    }

    // Parse configurations
    const configs = paretoConfigs.map(row => ({
      ...JSON.parse(row.configuration),
      quality: row.quality,
      cost: row.cost,
      latency: row.latency
    }));

    switch (strategy) {
      case 'QualityFirst':
        // Pick highest quality regardless of cost
        return configs[0];

      case 'CostOptimized':
        // Pick lowest cost that still has acceptable quality (> 0.5)
        configs.sort((a, b) => a.cost - b.cost);
        return configs.find(c => c.quality > 0.5) || configs[0];

      case 'Balanced':
      default: {
        // Maximize quality/cost ratio
        const scored = configs.map(c => ({
          ...c,
          efficiency: c.quality / Math.max(0.001, c.cost)
        }));
        scored.sort((a, b) => b.efficiency - a.efficiency);
        return scored[0];
      }
    }

  } finally {
    await closeDb(db);
  }
}

/**
 * Get the current Pareto front for a task type.
 */
async function getParetoFront(taskType) {
  const db = await openDb();

  try {
    const rows = await dbAll(db, `
      SELECT id, configuration, quality, cost, latency, is_pareto_optimal,
             dominated_by, computed_at
      FROM pareto_fronts
      WHERE task_type = ?
      ORDER BY is_pareto_optimal DESC, quality DESC
    `, [taskType]);

    return rows.map(row => ({
      id: row.id,
      ...JSON.parse(row.configuration),
      quality: row.quality,
      cost: row.cost,
      latency: row.latency,
      isParetoOptimal: row.is_pareto_optimal === 1,
      computedAt: row.computed_at
    }));

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Full meta-optimization cycle
// ---------------------------------------------------------------------------

/**
 * Run the full meta-optimization cycle:
 * 1. Check for stale knowledge
 * 2. Compute Pareto fronts for active task types
 * 3. Analyze meta-insights
 * 4. Generate recommendations
 */
async function runMetaOptimizationCycle() {
  const db = await openDb();

  try {
    const results = {};

    // 1. Retire stale knowledge
    results.staleness = await retireStaleKnowledge();

    // 2. Get active task types and compute Pareto fronts
    const taskTypes = await dbAll(db, `
      SELECT DISTINCT task_type FROM execution_log
      WHERE task_type IS NOT NULL AND quality_score IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= 5
    `);

    results.paretoFronts = {};
    for (const { task_type } of taskTypes) {
      try {
        results.paretoFronts[task_type] = await computeParetoFront(task_type);
      } catch (e) {
        results.paretoFronts[task_type] = { error: e.message };
      }
    }

    // 3. Meta-analysis
    results.metaAnalysis = await getMetaAnalysis();

    // 4. Knowledge status
    results.knowledgeStatus = await getKnowledgeStatus();

    return results;

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  // Phase 4a: Reptile interpolation
  reptileUpdate,

  // Phase 4b: Backward transfer
  checkBackwardTransfer,
  rollbackParameters,

  // Phase 4c: Stale knowledge
  retireStaleKnowledge,
  getKnowledgeStatus,

  // Phase 4d: Meta-optimizer
  recordMetaInsight,
  getMetaAnalysis,

  // Phase 4e: Pareto fronts
  computeParetoFront,
  selectFromParetoFront,
  getParetoFront,

  // Full cycle
  runMetaOptimizationCycle
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
        case 'reptile': {
          const model = args[1] || 'opus';
          const taskType = args[2] || 'code_review';
          const params = args[3] ? JSON.parse(args[3]) : { temperature: 0.3 };
          const confidence = parseFloat(args[4]) || 0.7;
          const result = await reptileUpdate(model, taskType, params, confidence);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'bwt': {
          const model = args[1] || 'opus';
          const taskType = args[2] || 'code_review';
          const result = await checkBackwardTransfer(model, taskType);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'rollback': {
          const model = args[1];
          const taskType = args[2];
          const result = await rollbackParameters(model, taskType);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'retire': {
          const result = await retireStaleKnowledge();
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'pareto': {
          const taskType = args[1] || 'code_review';
          const result = await computeParetoFront(taskType);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'select-pareto': {
          const taskType = args[1] || 'code_review';
          const strategy = args[2] || 'Balanced';
          const result = await selectFromParetoFront(taskType, strategy);
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'meta': {
          const result = await getMetaAnalysis();
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'cycle': {
          const result = await runMetaOptimizationCycle();
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'status': {
          const result = await getKnowledgeStatus();
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        default:
          console.log(`
Meta-Optimizer CLI

Usage:
  meta-optimizer.js reptile <model> <task_type> <params_json> [confidence]
    Apply Reptile-style parameter interpolation

  meta-optimizer.js bwt <model> <task_type>
    Check backward transfer after parameter update

  meta-optimizer.js rollback <model> <task_type>
    Roll back parameters to previous version

  meta-optimizer.js retire
    Mark stale/retired parameter tunings

  meta-optimizer.js pareto <task_type>
    Compute Pareto front for a task type

  meta-optimizer.js select-pareto <task_type> [strategy]
    Select from Pareto front (QualityFirst|CostOptimized|Balanced)

  meta-optimizer.js meta
    Get meta-analysis of optimization strategies

  meta-optimizer.js cycle
    Run full meta-optimization cycle

  meta-optimizer.js status
    Get knowledge status (active/stale/retired counts)
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  })();
}
