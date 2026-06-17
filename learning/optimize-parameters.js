#!/usr/bin/env node
/**
 * Parameter Optimizer
 *
 * Reads execution_log, finds optimal temperature, top_p, max_tokens, etc. by:
 *   - Grouping by (model, task_type)
 *   - Finding parameter values with highest avg quality
 *   - Computing sensitivity analysis per parameter
 *   - Storing results in model_tuning and parameter_tuning tables
 *
 * Runs every 50 executions (triggered manually for Phase 1).
 *
 * Usage:
 *   node optimize-parameters.js              # Run optimization
 *   node optimize-parameters.js --dry-run    # Analyze without writing
 *   node optimize-parameters.js --force      # Run even if < 50 new executions
 *   node optimize-parameters.js --verbose    # Detailed output
 *
 * Tables written:
 *   model_tuning      (init-learning-db.sql schema)
 *   parameter_tuning   (orchestration-schema.sql schema)
 *   learning_metadata  (last recompute timestamps + execution counts)
 *
 * Message bus channels:
 *   parameter-tuning   - Optimization results and discoveries
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const os = require('os');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DB_PATH = path.join(__dirname, 'db', 'learning.db');
const EXECUTION_THRESHOLD = 50;   // Minimum new executions before re-optimizing
const MIN_SAMPLES = 3;            // Minimum samples per (model, task_type) group
const TREND_WINDOW = 20;          // Number of recent values kept in trend arrays
const TUNABLE_PARAMS = ['temperature', 'top_p', 'max_tokens', 'frequency_penalty', 'presence_penalty'];

// Parameters and their valid ranges for sensitivity analysis
const PARAM_RANGES = {
  temperature:      { min: 0.0, max: 2.0, step: 0.1, default: 1.0 },
  top_p:            { min: 0.0, max: 1.0, step: 0.05, default: 1.0 },
  max_tokens:       { min: 256, max: 16384, step: 256, default: 4096 },
  frequency_penalty: { min: 0.0, max: 2.0, step: 0.1, default: 0.0 },
  presence_penalty:  { min: 0.0, max: 2.0, step: 0.1, default: 0.0 }
};

// ---------------------------------------------------------------------------
// CLI flags
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');
const FORCE   = args.includes('--force');
const VERBOSE = args.includes('--verbose');

// ---------------------------------------------------------------------------
// Database helpers
// ---------------------------------------------------------------------------

function openDb(dbPath) {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(dbPath, (err) => {
      if (err) return reject(err);
      db.run('PRAGMA journal_mode = WAL', () => {
        db.run('PRAGMA synchronous = NORMAL', () => {
          db.run('PRAGMA busy_timeout = 5000', () => {
            db.run('PRAGMA cache_size = -2000', () => {
              db.run('PRAGMA foreign_keys = ON', () => {
                resolve(db);
              });
            });
          });
        });
      });
    });
  });
}

function dbAll(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

function dbGet(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row || null);
    });
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
// Message bus integration (optional -- graceful if not available)
// ---------------------------------------------------------------------------

let messageBus = null;
try {
  messageBus = require('./shared/message-bus');
} catch (_) {
  // message-bus not available; skip notifications
}

function notify(message) {
  if (messageBus) {
    try {
      messageBus.postMessage('parameter-tuning', message);
    } catch (_) {
      // ignore notification failures
    }
  }
}

// ---------------------------------------------------------------------------
// Core: check whether optimization should run
// ---------------------------------------------------------------------------

async function shouldRun(db) {
  if (FORCE) return { should: true, reason: 'forced via --force flag' };

  const meta = await dbGet(db,
    "SELECT value FROM learning_metadata WHERE key = 'last_tuning_recompute'"
  );
  const lastRecompute = meta?.value || '';

  let totalSinceLastRun;
  if (lastRecompute) {
    const row = await dbGet(db,
      'SELECT COUNT(*) AS cnt FROM execution_log WHERE timestamp > ?',
      [lastRecompute]
    );
    totalSinceLastRun = row?.cnt || 0;
  } else {
    const row = await dbGet(db, 'SELECT COUNT(*) AS cnt FROM execution_log');
    totalSinceLastRun = row?.cnt || 0;
  }

  if (totalSinceLastRun < EXECUTION_THRESHOLD) {
    return {
      should: false,
      reason: `Only ${totalSinceLastRun} new executions since last run (need ${EXECUTION_THRESHOLD})`,
      newExecutions: totalSinceLastRun
    };
  }

  return {
    should: true,
    reason: `${totalSinceLastRun} new executions since last run (threshold: ${EXECUTION_THRESHOLD})`,
    newExecutions: totalSinceLastRun
  };
}

// ---------------------------------------------------------------------------
// Core: extract parameter data from execution_log
// ---------------------------------------------------------------------------

async function fetchExecutionData(db) {
  // Fetch all executions that have a quality_score and non-empty parameters
  const rows = await dbAll(db, `
    SELECT
      id,
      model,
      task_type,
      parameters,
      quality_score,
      confidence,
      consensus_score,
      was_selected,
      cost_usd,
      duration_ms,
      outcome,
      timestamp
    FROM execution_log
    WHERE quality_score IS NOT NULL
      AND model NOT IN ('test-model', 'unknown', 'test')
    ORDER BY timestamp ASC
  `);

  return rows.map(row => {
    let params = {};
    try {
      params = JSON.parse(row.parameters || '{}');
    } catch (_) {
      params = {};
    }
    return { ...row, parsedParams: params };
  });
}

// ---------------------------------------------------------------------------
// Core: group executions by (model, task_type)
// ---------------------------------------------------------------------------

function groupExecutions(rows) {
  const groups = new Map();

  for (const row of rows) {
    const model = row.model;
    const taskType = row.task_type || '*';
    const key = `${model}::${taskType}`;

    if (!groups.has(key)) {
      groups.set(key, { model, taskType, executions: [] });
    }
    groups.get(key).executions.push(row);
  }

  return groups;
}

// ---------------------------------------------------------------------------
// Core: find optimal parameter values for a group
// ---------------------------------------------------------------------------

/**
 * For each tunable parameter, bucket executions by parameter value, then
 * pick the bucket with the highest average quality_score.
 *
 * Returns:
 *   {
 *     optimalParams: { temperature: 0.3, top_p: 0.9, ... },
 *     sensitivity: { temperature: { range: [...], impact: 'high', optimal: 0.3 }, ... },
 *     metrics: { avgQuality, avgConfidence, avgCost, avgDuration, sampleCount, successRate, selectionRate }
 *     qualityTrend: [...],
 *     costTrend: [...]
 *   }
 */
function analyzeGroup(group) {
  const { executions } = group;
  if (executions.length < MIN_SAMPLES) return null;

  // Aggregate metrics across all executions in the group
  const qualities   = executions.map(e => e.quality_score).filter(v => v != null);
  const confidences = executions.map(e => e.confidence).filter(v => v != null);
  const costs       = executions.map(e => e.cost_usd).filter(v => v != null);
  const durations   = executions.map(e => e.duration_ms).filter(v => v != null);
  const successes   = executions.filter(e => e.outcome === 'success').length;
  const selected    = executions.filter(e => e.was_selected === 1).length;

  const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
  const stddev = arr => {
    if (arr.length < 2) return 0;
    const m = avg(arr);
    return Math.sqrt(arr.reduce((sum, v) => sum + (v - m) ** 2, 0) / (arr.length - 1));
  };

  const metrics = {
    avgQuality:    avg(qualities),
    avgConfidence: avg(confidences),
    avgCost:       avg(costs),
    avgDuration:   avg(durations),
    sampleCount:   executions.length,
    successRate:   executions.length > 0 ? successes / executions.length : 0,
    selectionRate: executions.length > 0 ? selected / executions.length : 0
  };

  // Build trend arrays (most recent TREND_WINDOW values)
  const qualityTrend = qualities.slice(-TREND_WINDOW);
  const costTrend    = costs.slice(-TREND_WINDOW);

  // Per-parameter optimization
  const optimalParams = {};
  const sensitivity   = {};

  for (const param of TUNABLE_PARAMS) {
    // Collect (value, quality) pairs where the param was specified
    const pairs = [];
    for (const exec of executions) {
      const val = exec.parsedParams[param];
      if (val != null && typeof val === 'number' && !isNaN(val)) {
        pairs.push({ value: val, quality: exec.quality_score });
      }
    }

    if (pairs.length < MIN_SAMPLES) continue;

    // Bucket by quantized value for continuous params
    const range = PARAM_RANGES[param];
    const buckets = new Map();

    for (const { value, quality } of pairs) {
      // Quantize to nearest step
      const quantized = range
        ? Math.round(value / range.step) * range.step
        : value;
      const bucketKey = Number(quantized.toFixed(6));

      if (!buckets.has(bucketKey)) {
        buckets.set(bucketKey, { values: [], qualities: [] });
      }
      const bucket = buckets.get(bucketKey);
      bucket.values.push(value);
      bucket.qualities.push(quality);
    }

    // Find the bucket with highest average quality (require >= 2 samples per bucket)
    let bestVal   = null;
    let bestAvgQ  = -Infinity;
    let worstAvgQ = Infinity;
    const bucketSummaries = [];

    for (const [bucketKey, bucket] of buckets.entries()) {
      if (bucket.qualities.length < 2) continue;
      const bucketAvg = avg(bucket.qualities);
      bucketSummaries.push({ value: bucketKey, avgQuality: bucketAvg, count: bucket.qualities.length });

      if (bucketAvg > bestAvgQ) {
        bestAvgQ = bucketAvg;
        bestVal = bucketKey;
      }
      if (bucketAvg < worstAvgQ) {
        worstAvgQ = bucketAvg;
      }
    }

    // If we only have one bucket or no valid buckets, use the overall average value
    if (bestVal == null) {
      const allVals = pairs.map(p => p.value);
      bestVal = avg(allVals);
      bestAvgQ = avg(pairs.map(p => p.quality));
      worstAvgQ = bestAvgQ;
    }

    optimalParams[param] = Number(bestVal.toFixed(6));

    // Sensitivity: how much does quality vary across parameter values?
    const qualityRange = bestAvgQ - (worstAvgQ === Infinity ? bestAvgQ : worstAvgQ);
    const overallStddev = stddev(pairs.map(p => p.quality));
    let impact;
    if (qualityRange > 0.15 || overallStddev > 0.2) {
      impact = 'high';
    } else if (qualityRange > 0.05 || overallStddev > 0.1) {
      impact = 'medium';
    } else {
      impact = 'low';
    }

    const allValues = pairs.map(p => p.value);
    sensitivity[param] = {
      range:    [Math.min(...allValues), Math.max(...allValues)],
      impact,
      optimal:  optimalParams[param],
      buckets:  bucketSummaries.length,
      samples:  pairs.length
    };
  }

  // Compute tuning confidence (higher with more samples and lower variance)
  const qualityStddev = stddev(qualities);
  let confidence = Math.min(1.0, executions.length / 100);  // scale with sample size
  if (qualityStddev > 0.3) confidence *= 0.5;               // penalize high variance
  else if (qualityStddev > 0.15) confidence *= 0.75;
  if (Object.keys(optimalParams).length === 0) confidence *= 0.5; // no params to tune
  confidence = Math.max(0.0, Math.min(1.0, confidence));

  return {
    optimalParams,
    sensitivity,
    metrics,
    qualityTrend,
    costTrend,
    confidence
  };
}

// ---------------------------------------------------------------------------
// Core: compute baselines for vs_baseline comparisons
// ---------------------------------------------------------------------------

function computeBaseline(executions) {
  const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

  // Baseline: earliest 30% of executions (representing pre-tuning behavior)
  const cutoff = Math.max(MIN_SAMPLES, Math.floor(executions.length * 0.3));
  const baseline = executions.slice(0, cutoff);

  const qualities = baseline.map(e => e.quality_score).filter(v => v != null);
  const costs     = baseline.map(e => e.cost_usd).filter(v => v != null);
  const durations = baseline.map(e => e.duration_ms).filter(v => v != null);

  return {
    quality:  avg(qualities),
    cost:     avg(costs),
    duration: avg(durations)
  };
}

// ---------------------------------------------------------------------------
// Core: write results to model_tuning table (init-learning-db schema)
// ---------------------------------------------------------------------------

async function writeModelTuning(db, model, taskType, analysis) {
  const { optimalParams, metrics, qualityTrend, costTrend } = analysis;

  await dbRun(db, `
    INSERT INTO model_tuning (
      model, task_type, optimal_params,
      avg_quality, avg_confidence, avg_cost_usd, avg_duration_ms,
      sample_count, success_rate, selection_rate,
      quality_trend, cost_trend,
      updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    ON CONFLICT(model, task_type) DO UPDATE SET
      optimal_params = excluded.optimal_params,
      avg_quality    = excluded.avg_quality,
      avg_confidence = excluded.avg_confidence,
      avg_cost_usd   = excluded.avg_cost_usd,
      avg_duration_ms = excluded.avg_duration_ms,
      sample_count   = excluded.sample_count,
      success_rate   = excluded.success_rate,
      selection_rate = excluded.selection_rate,
      quality_trend  = excluded.quality_trend,
      cost_trend     = excluded.cost_trend,
      updated_at     = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
  `, [
    model,
    taskType,
    JSON.stringify(optimalParams),
    metrics.avgQuality,
    metrics.avgConfidence,
    metrics.avgCost,
    metrics.avgDuration,
    metrics.sampleCount,
    metrics.successRate,
    metrics.selectionRate,
    JSON.stringify(qualityTrend),
    JSON.stringify(costTrend)
  ]);
}

// ---------------------------------------------------------------------------
// Core: write results to parameter_tuning table (orchestration schema)
// ---------------------------------------------------------------------------

async function writeParameterTuning(db, model, taskType, analysis, baseline) {
  const { optimalParams, sensitivity, metrics, confidence } = analysis;

  // Check if parameter_tuning table exists (orchestration schema may not be initialized)
  const tableCheck = await dbGet(db,
    "SELECT name FROM sqlite_master WHERE type='table' AND name='parameter_tuning'"
  );
  if (!tableCheck) return false;

  // Fetch previous params for version tracking
  const existing = await dbGet(db,
    'SELECT optimal_params, version FROM parameter_tuning WHERE model = ? AND task_type = ?',
    [model, taskType]
  );

  const previousParams = existing ? existing.optimal_params : '{}';
  const version = existing ? (existing.version || 0) + 1 : 1;

  await dbRun(db, `
    INSERT INTO parameter_tuning (
      model, task_type, optimal_params,
      tuning_method, sample_count, search_iterations,
      avg_quality, avg_cost_usd, avg_duration_ms, success_rate,
      quality_vs_baseline, cost_vs_baseline, duration_vs_baseline,
      confidence, sensitivity,
      version, previous_params,
      updated_at
    ) VALUES (?, ?, ?, 'empirical', ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    ON CONFLICT(model, task_type) DO UPDATE SET
      optimal_params      = excluded.optimal_params,
      tuning_method       = excluded.tuning_method,
      sample_count        = excluded.sample_count,
      search_iterations   = COALESCE(parameter_tuning.search_iterations, 0) + 1,
      avg_quality         = excluded.avg_quality,
      avg_cost_usd        = excluded.avg_cost_usd,
      avg_duration_ms     = excluded.avg_duration_ms,
      success_rate        = excluded.success_rate,
      quality_vs_baseline = excluded.quality_vs_baseline,
      cost_vs_baseline    = excluded.cost_vs_baseline,
      duration_vs_baseline = excluded.duration_vs_baseline,
      confidence          = excluded.confidence,
      sensitivity         = excluded.sensitivity,
      version             = excluded.version,
      previous_params     = excluded.previous_params,
      updated_at          = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
  `, [
    model,
    taskType,
    JSON.stringify(optimalParams),
    metrics.sampleCount,
    metrics.avgQuality,
    metrics.avgCost,
    metrics.avgDuration,
    metrics.successRate,
    baseline ? metrics.avgQuality - baseline.quality : 0,
    baseline ? metrics.avgCost - baseline.cost : 0,
    baseline ? metrics.avgDuration - baseline.duration : 0,
    confidence,
    JSON.stringify(sensitivity),
    version,
    previousParams
  ]);

  return true;
}

// ---------------------------------------------------------------------------
// Core: Reptile-style parameter interpolation (Phase 4a integration)
// ---------------------------------------------------------------------------

/**
 * Use Reptile-style interpolation for smoother parameter updates.
 * Instead of overwriting params, interpolate:
 *   new[k] = old[k] + beta * (discovered[k] - old[k])
 * where beta = confidence * base_beta
 */
async function writeParameterTuningReptile(db, model, taskType, analysis, baseline) {
  const { optimalParams, confidence } = analysis;

  // Check if parameter_tuning table exists
  const tableCheck = await dbGet(db,
    "SELECT name FROM sqlite_master WHERE type='table' AND name='parameter_tuning'"
  );
  if (!tableCheck) return false;

  // Only apply Reptile if there are existing params to interpolate with
  const existing = await dbGet(db,
    'SELECT optimal_params, version, interpolation_beta FROM parameter_tuning WHERE model = ? AND task_type = ?',
    [model, taskType]
  );

  if (!existing || !existing.optimal_params || existing.optimal_params === '{}') {
    return false; // No existing params; fallback to direct write
  }

  try {
    const metaOptimizer = require('./meta-optimizer');
    await metaOptimizer.reptileUpdate(model, taskType, optimalParams, confidence, { db });

    verbose(`  Reptile update applied for ${model}/${taskType} (beta=${(existing.interpolation_beta || 0.3) * confidence})`);

    // Phase 4b: Check backward transfer after update
    try {
      const bwt = await metaOptimizer.checkBackwardTransfer(model, taskType, { db });
      if (bwt.rollbackRecommended) {
        verbose(`  WARNING: Backward transfer degradation detected for ${model}/${taskType}`);
        verbose(`  Degraded tasks: ${bwt.degradedTasks.map(t => t.taskType).join(', ')}`);
        // Auto-rollback
        await metaOptimizer.rollbackParameters(model, taskType);
        verbose(`  Auto-rolled back parameters for ${model}/${taskType}`);
      }
    } catch (_) {
      // BWT check failed; continue
    }

    return true;
  } catch (_) {
    return false; // meta-optimizer not available; fallback
  }
}

// ---------------------------------------------------------------------------
// Core: update metadata timestamps
// ---------------------------------------------------------------------------

async function updateMetadata(db, groupCount, totalSamples) {
  const now = new Date().toISOString();

  await dbRun(db, `
    INSERT INTO learning_metadata (key, value, updated_at)
    VALUES ('last_tuning_recompute', ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `, [now, now]);

  await dbRun(db, `
    INSERT INTO learning_metadata (key, value, updated_at)
    VALUES ('last_parameter_tuning_recompute', ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `, [now, now]);

  await dbRun(db, `
    INSERT INTO learning_metadata (key, value, updated_at)
    VALUES ('parameter_optimizer_groups', ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `, [String(groupCount), now]);

  await dbRun(db, `
    INSERT INTO learning_metadata (key, value, updated_at)
    VALUES ('parameter_optimizer_samples', ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `, [String(totalSamples), now]);
}

// ---------------------------------------------------------------------------
// Main: orchestrate the full optimization pipeline
// ---------------------------------------------------------------------------

async function optimize() {
  const startTime = Date.now();
  let db = null;

  try {
    db = await openDb(DB_PATH);
    log('Connected to database:', DB_PATH);

    // 1. Check if we should run
    const runCheck = await shouldRun(db);
    if (!runCheck.should) {
      log('Skipping optimization:', runCheck.reason);
      return {
        status: 'skipped',
        reason: runCheck.reason,
        newExecutions: runCheck.newExecutions || 0
      };
    }
    log('Running optimization:', runCheck.reason);

    // 2. Fetch all execution data
    const rows = await fetchExecutionData(db);
    if (rows.length < MIN_SAMPLES) {
      log(`Insufficient data: only ${rows.length} executions with quality scores`);
      return {
        status: 'skipped',
        reason: `Insufficient data (${rows.length} executions, need ${MIN_SAMPLES})`
      };
    }
    log(`Fetched ${rows.length} executions with quality scores`);

    // 3. Group by (model, task_type)
    const groups = groupExecutions(rows);
    log(`Found ${groups.size} (model, task_type) groups`);

    // 4. Analyze each group and write results
    const results = [];
    let updatedCount = 0;
    let skippedCount = 0;

    for (const [key, group] of groups.entries()) {
      const analysis = analyzeGroup(group);
      if (!analysis) {
        skippedCount++;
        verbose(`  Skipped ${key}: fewer than ${MIN_SAMPLES} samples`);
        continue;
      }

      const { model, taskType, executions } = group;
      const baseline = computeBaseline(executions);
      const qualityDelta = analysis.metrics.avgQuality - baseline.quality;

      verbose(`  ${key}:`);
      verbose(`    samples=${analysis.metrics.sampleCount}`);
      verbose(`    avgQuality=${analysis.metrics.avgQuality.toFixed(4)}`);
      verbose(`    confidence=${analysis.confidence.toFixed(3)}`);
      verbose(`    params=${JSON.stringify(analysis.optimalParams)}`);
      verbose(`    qualityDelta=${qualityDelta >= 0 ? '+' : ''}${qualityDelta.toFixed(4)}`);

      if (!DRY_RUN) {
        // Write to model_tuning table
        await writeModelTuning(db, model, taskType, analysis);

        // Write to parameter_tuning table (if it exists)
        // Phase 4a: Use Reptile-style interpolation instead of hard overwrites
        const reptileApplied = await writeParameterTuningReptile(db, model, taskType, analysis, baseline);
        if (!reptileApplied) {
          // Fallback to direct write if Reptile not applicable
          await writeParameterTuning(db, model, taskType, analysis, baseline);
        }
      }

      results.push({
        model,
        taskType,
        sampleCount: analysis.metrics.sampleCount,
        avgQuality:  analysis.metrics.avgQuality,
        confidence:  analysis.confidence,
        optimalParams: analysis.optimalParams,
        sensitivity: analysis.sensitivity,
        qualityVsBaseline: qualityDelta,
        successRate: analysis.metrics.successRate,
        selectionRate: analysis.metrics.selectionRate
      });

      updatedCount++;
    }

    // 5. Update metadata
    if (!DRY_RUN) {
      const totalSamples = results.reduce((sum, r) => sum + r.sampleCount, 0);
      await updateMetadata(db, updatedCount, totalSamples);

      // Phase 4c: Retire stale knowledge
      try {
        const metaOptimizer = require('./meta-optimizer');
        const staleResult = await metaOptimizer.retireStaleKnowledge();
        if (staleResult.newlyStale > 0 || staleResult.newlyRetired > 0) {
          log(`  Stale knowledge: ${staleResult.newlyStale} stale, ${staleResult.newlyRetired} retired`);
        }
      } catch (_) {}

      // Phase 4e: Recompute Pareto fronts for updated task types
      try {
        const metaOptimizer = require('./meta-optimizer');
        const updatedTaskTypes = new Set(results.map(r => r.taskType));
        for (const taskType of updatedTaskTypes) {
          await metaOptimizer.computeParetoFront(taskType);
        }
        verbose(`  Pareto fronts recomputed for ${updatedTaskTypes.size} task types`);
      } catch (_) {}

      // Phase 2: Recompute task affinity matrix periodically
      try {
        const taskEmbedder = require('./task-embedder');
        await taskEmbedder.recomputeAffinityMatrix();
        verbose('  Task affinity matrix recomputed');
      } catch (_) {}
    }

    const elapsed = Date.now() - startTime;
    const summary = {
      status:       DRY_RUN ? 'dry-run' : 'completed',
      groupsFound:  groups.size,
      groupsUpdated: updatedCount,
      groupsSkipped: skippedCount,
      totalSamples: results.reduce((sum, r) => sum + r.sampleCount, 0),
      durationMs:   elapsed,
      results
    };

    // 6. Notify via message bus
    if (!DRY_RUN) {
      notify({
        type: 'optimization_complete',
        summary: {
          groupsUpdated: updatedCount,
          groupsSkipped: skippedCount,
          totalSamples: summary.totalSamples,
          durationMs: elapsed,
          topFindings: results
            .filter(r => Object.keys(r.optimalParams).length > 0)
            .sort((a, b) => b.avgQuality - a.avgQuality)
            .slice(0, 5)
            .map(r => ({
              model: r.model,
              taskType: r.taskType,
              avgQuality: r.avgQuality,
              confidence: r.confidence,
              optimalParams: r.optimalParams
            }))
        }
      });
    }

    // 7. Print summary
    log('');
    log('=== Parameter Optimization Summary ===');
    log(`Status:          ${summary.status}`);
    log(`Groups found:    ${summary.groupsFound}`);
    log(`Groups updated:  ${summary.groupsUpdated}`);
    log(`Groups skipped:  ${summary.groupsSkipped}`);
    log(`Total samples:   ${summary.totalSamples}`);
    log(`Duration:        ${summary.durationMs}ms`);

    if (results.length > 0) {
      log('');
      log('--- Top Tunings (by quality) ---');
      const sorted = [...results].sort((a, b) => b.avgQuality - a.avgQuality);
      for (const r of sorted.slice(0, 10)) {
        const paramStr = Object.entries(r.optimalParams)
          .map(([k, v]) => `${k}=${v}`)
          .join(', ');
        const delta = r.qualityVsBaseline >= 0 ? `+${r.qualityVsBaseline.toFixed(4)}` : r.qualityVsBaseline.toFixed(4);
        log(`  ${r.model}/${r.taskType}: quality=${r.avgQuality.toFixed(4)} (${delta} vs baseline), confidence=${r.confidence.toFixed(3)}, n=${r.sampleCount}`);
        if (paramStr) log(`    optimal: ${paramStr}`);

        const highImpact = Object.entries(r.sensitivity)
          .filter(([, s]) => s.impact === 'high')
          .map(([k]) => k);
        if (highImpact.length > 0) {
          log(`    high-impact params: ${highImpact.join(', ')}`);
        }
      }
    }

    return summary;

  } catch (err) {
    const elapsed = Date.now() - startTime;
    log('ERROR:', err.message);
    if (VERBOSE) console.error(err.stack);

    notify({
      type: 'optimization_error',
      error: err.message,
      durationMs: elapsed
    });

    return { status: 'error', error: err.message, durationMs: elapsed };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Logging helpers
// ---------------------------------------------------------------------------

function log(...args) {
  console.log('[optimize-parameters]', ...args);
}

function verbose(...args) {
  if (VERBOSE) console.log('[optimize-parameters]', ...args);
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

if (require.main === module) {
  optimize()
    .then(result => {
      if (result.status === 'error') process.exit(1);
    })
    .catch(err => {
      console.error('[optimize-parameters] Fatal:', err);
      process.exit(1);
    });
}

module.exports = { optimize, analyzeGroup, groupExecutions, fetchExecutionData, writeParameterTuningReptile };
