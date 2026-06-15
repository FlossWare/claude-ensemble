#!/usr/bin/env node

/**
 * Background Learner - Recomputes optimal parameters every 30 seconds
 *
 * This process runs in the background and periodically analyzes the execution_log
 * table to update:
 *   - model_tuning: optimal parameters per model/task
 *   - prompt_patterns: best prompt strategies per model/task
 *   - model_combinations: worker synergy scores
 *
 * Usage:
 *   node background-learner.js              # Run once and exit
 *   node background-learner.js --daemon     # Run continuously every 30s
 *   node background-learner.js --interval 60  # Custom interval (seconds)
 *   node background-learner.js --status     # Print current stats and exit
 *
 * The learner reads from the same SQLite database as learning-logger.js.
 * WAL mode ensures reads do not block writes.
 */

import { hotImport } from './shared/hot-reload.js';

// Hot-reload logger for live updates
let logger = null;
async function getLogger() {
  logger = await hotImport('./shared/learning-logger.js', { force: true });
  return logger;
}

// ============================================================================
// CLI ARGUMENT PARSING
// ============================================================================

const args = process.argv.slice(2);
const isDaemon = args.includes('--daemon');
const isStatus = args.includes('--status');
const intervalIdx = args.indexOf('--interval');
const intervalSec = intervalIdx >= 0 ? parseInt(args[intervalIdx + 1], 10) : 30;

// ============================================================================
// STATUS COMMAND
// ============================================================================

if (isStatus) {
  await printStatus();
  process.exit(0);
}

async function printStatus() {
  const log = await getLogger();
  const count = log.getExecutionCount();
  const tuning = log.getAllTuning();
  const combos = log.getAllCombinations();
  const lastRecompute = log.getMetadata('last_tuning_recompute') || 'never';

  console.log('='.repeat(60));
  console.log('LEARNING DATABASE STATUS');
  console.log('='.repeat(60));
  console.log(`Database:            ${log.getDbPath()}`);
  console.log(`Available:           ${log.isAvailable()}`);
  console.log(`Total executions:    ${count}`);
  console.log(`Tuning records:      ${tuning.length}`);
  console.log(`Combination records: ${combos.length}`);
  console.log(`Last recompute:      ${lastRecompute}`);
  console.log('');

  if (tuning.length > 0) {
    console.log('--- MODEL TUNING ---');
    console.log(`${'Model'.padEnd(12)} ${'Task'.padEnd(18)} ${'Quality'.padStart(8)} ${'Confidence'.padStart(11)} ${'SelRate'.padStart(8)} ${'Samples'.padStart(8)}`);
    console.log('-'.repeat(65));
    for (const t of tuning) {
      console.log(
        `${t.model.padEnd(12)} ` +
        `${t.task_type.padEnd(18)} ` +
        `${(t.avg_quality || 0).toFixed(3).padStart(8)} ` +
        `${(t.avg_confidence || 0).toFixed(3).padStart(11)} ` +
        `${(t.selection_rate || 0).toFixed(3).padStart(8)} ` +
        `${String(t.sample_count || 0).padStart(8)}`
      );
    }
    console.log('');
  }

  if (combos.length > 0) {
    console.log('--- MODEL COMBINATIONS ---');
    console.log(`${'Task'.padEnd(18)} ${'Workers'.padEnd(30)} ${'Arbiter'.padEnd(10)} ${'Synergy'.padStart(8)} ${'Uses'.padStart(6)}`);
    console.log('-'.repeat(72));
    for (const c of combos) {
      const workers = typeof c.worker_models === 'string' ? c.worker_models : JSON.stringify(c.worker_models);
      console.log(
        `${c.task_type.padEnd(18)} ` +
        `${workers.substring(0, 30).padEnd(30)} ` +
        `${(c.arbiter_model || '-').padEnd(10)} ` +
        `${(c.synergy_score || 0).toFixed(3).padStart(8)} ` +
        `${String(c.usage_count || 0).padStart(6)}`
      );
    }
    console.log('');
  }

  console.log('='.repeat(60));
}

// ============================================================================
// RECOMPUTE LOGIC
// ============================================================================

/**
 * Main recompute cycle. Analyzes execution_log and updates derived tables.
 * Returns { tuning_updated, combos_updated, duration_ms }.
 */
async function recompute() {
  // Hot-reload logger module for live updates
  const log = await getLogger();
  const startTime = Date.now();
  let tuningUpdated = 0;
  let combosUpdated = 0;
  let patternsUpdated = 0;

  if (!log.isAvailable()) {
    return { tuning_updated: 0, combos_updated: 0, patterns_updated: 0, duration_ms: 0, skipped: true };
  }

  // ---- Gather read-only data outside transaction ----
  const modelTasks = log.getDistinctModelTasks();
  const db = log.getDb();

  // Pre-collect Phase 1 data (reads only)
  const tuningWrites = [];
  for (const { model, task_type } of modelTasks) {
    const stats = log.getModelTaskStats(model, task_type);
    if (!stats || !stats.sample_count || stats.sample_count < 2) continue;

    const qualityTrend = log.getRecentQuality(model, task_type);
    const costTrend = log.getRecentCost(model, task_type);
    const optimalParams = computeOptimalParams(stats, qualityTrend, task_type);

    tuningWrites.push({
      model,
      task_type,
      optimal_params: optimalParams,
      avg_quality:    stats.avg_quality || 0,
      avg_confidence: stats.avg_confidence || 0,
      avg_cost_usd:   stats.avg_cost_usd || 0,
      avg_duration_ms: stats.avg_duration_ms || 0,
      sample_count:   stats.sample_count,
      success_rate:   stats.success_rate || 0,
      selection_rate: stats.selection_rate || 0,
      quality_trend:  qualityTrend.slice(0, 20),
      cost_trend:     costTrend.slice(0, 20),
    });
  }

  // Pre-collect Phase 2 data (reads only)
  const comboWrites = [];
  if (db) {
    try {
      const comboRows = db.prepare(`
        SELECT
          task_type,
          run_id,
          MIN(timestamp) AS min_timestamp,
          GROUP_CONCAT(DISTINCT model ORDER BY model) AS worker_models_csv,
          AVG(consensus_score) AS avg_consensus,
          AVG(quality_score) AS avg_quality,
          SUM(cost_usd) AS total_cost,
          SUM(duration_ms) AS total_duration,
          COUNT(*) AS worker_count
        FROM execution_log
        WHERE model_role = 'worker'
          AND task_type IS NOT NULL
          AND consensus_score IS NOT NULL
          AND run_id IS NOT NULL
        GROUP BY task_type, run_id
        HAVING worker_count >= 2
        UNION ALL
        SELECT
          task_type,
          NULL AS run_id,
          MIN(timestamp) AS min_timestamp,
          GROUP_CONCAT(DISTINCT model ORDER BY model) AS worker_models_csv,
          AVG(consensus_score) AS avg_consensus,
          AVG(quality_score) AS avg_quality,
          SUM(cost_usd) AS total_cost,
          SUM(duration_ms) AS total_duration,
          COUNT(*) AS worker_count
        FROM execution_log
        WHERE model_role = 'worker'
          AND task_type IS NOT NULL
          AND consensus_score IS NOT NULL
          AND run_id IS NULL
        GROUP BY task_type, strftime('%Y-%m-%dT%H:%M', timestamp), workflow
        HAVING worker_count >= 2
      `).all();

      // Prepare arbiter lookup statements (run_id-based and time-correlated fallback)
      const arbiterByRunId = db.prepare(`
        SELECT model FROM execution_log
        WHERE model_role = 'arbiter'
          AND task_type = ?
          AND run_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
      `);
      const arbiterByTime = db.prepare(`
        SELECT model FROM execution_log
        WHERE model_role = 'arbiter'
          AND task_type = ?
          AND timestamp BETWEEN ? AND datetime(?, '+2 minutes')
        ORDER BY timestamp DESC
        LIMIT 1
      `);

      for (const row of comboRows) {
        if (!row.worker_models_csv) continue;

        const workerModels = row.worker_models_csv.split(',').sort();
        const workerModelsJson = JSON.stringify(workerModels);

        // Look for arbiter correlated to same consensus run (by run_id or time window)
        let arbiterRow = null;
        if (row.run_id) {
          arbiterRow = arbiterByRunId.get(row.task_type, row.run_id);
        }
        if (!arbiterRow && row.min_timestamp) {
          arbiterRow = arbiterByTime.get(row.task_type, row.min_timestamp, row.min_timestamp);
        }

        const arbiterModel = arbiterRow ? arbiterRow.model : null;

        // Compute synergy: combo quality vs best individual quality
        let maxIndividualQuality = 0;
        for (const m of workerModels) {
          const indStats = log.getModelTaskStats(m, row.task_type);
          if (indStats && indStats.avg_quality > maxIndividualQuality) {
            maxIndividualQuality = indStats.avg_quality;
          }
        }
        const synergyScore = (row.avg_quality || 0) - maxIndividualQuality;

        // Diversity: standard deviation of individual quality scores
        const individualQualities = [];
        for (const m of workerModels) {
          const indStats = log.getModelTaskStats(m, row.task_type);
          if (indStats) individualQualities.push(indStats.avg_quality || 0);
        }
        const diversityScore = individualQualities.length >= 2
          ? _stddev(individualQualities)
          : 0;

        comboWrites.push({
          task_type:       row.task_type,
          worker_models:   workerModelsJson,
          arbiter_model:   arbiterModel,
          avg_consensus:   row.avg_consensus || 0,
          avg_quality:     row.avg_quality || 0,
          avg_cost_usd:    row.total_cost || 0,
          avg_duration_ms: row.total_duration || 0,
          usage_count:     row.worker_count,
          synergy_score:   synergyScore,
          diversity_score: diversityScore,
        });
      }
    } catch (err) {
      if (process.env.LEARNING_DEBUG) {
        console.error(`[background-learner] Combo recompute error: ${err.message}`);
      }
    }
  }

  // Pre-collect Phase 3 data (reads only)
  const patternWrites = [];
  if (db) {
    try {
      for (const { model, task_type } of modelTasks) {
        const executions = db.prepare(`
          SELECT parameters, quality_score, confidence, outcome
          FROM execution_log
          WHERE model = ? AND task_type = ?
            AND parameters IS NOT NULL AND parameters != '{}'
            AND quality_score IS NOT NULL
          ORDER BY timestamp DESC
          LIMIT 100
        `).all(model, task_type);

        if (executions.length < 3) continue;

        // Group by parameter patterns
        const patternGroups = {};
        for (const exec of executions) {
          let params;
          try { params = JSON.parse(exec.parameters); } catch (_e) { continue; }

          const patternKey = _classifyParams(params);
          if (!patternGroups[patternKey]) {
            patternGroups[patternKey] = { qualities: [], confidences: [], outcomes: [], count: 0 };
          }

          patternGroups[patternKey].qualities.push(exec.quality_score || 0);
          patternGroups[patternKey].confidences.push(exec.confidence || 0);
          patternGroups[patternKey].outcomes.push(exec.outcome || 'unknown');
          patternGroups[patternKey].count++;
        }

        // Compute baseline (all executions)
        const baselineQuality = executions.reduce((s, e) => s + (e.quality_score || 0), 0) / executions.length;

        for (const [patternName, group] of Object.entries(patternGroups)) {
          if (group.count < 2) continue;

          const avgQuality = _mean(group.qualities);
          const avgConfidence = _mean(group.confidences);

          patternWrites.push({
            model,
            task_type,
            pattern_name: patternName,
            pattern_template: null,
            instructions: null,
            avg_quality: avgQuality,
            avg_confidence: avgConfidence,
            usage_count: group.count,
            success_rate: group.outcomes.filter(o => o === 'success').length / group.count,
            vs_baseline_quality: avgQuality - baselineQuality,
          });
        }
      }
    } catch (err) {
      if (process.env.LEARNING_DEBUG) {
        console.error(`[background-learner] Pattern recompute error: ${err.message}`);
      }
    }
  }

  // ---- Write all phases atomically in a single transaction ----
  if (db) {
    const writeAll = db.transaction(() => {
      // Phase 1: Model Tuning writes
      for (const data of tuningWrites) {
        log.writeTuning(data);
        tuningUpdated++;
      }

      // Phase 2: Model Combination writes
      for (const data of comboWrites) {
        log.writeCombination(data);
        combosUpdated++;
      }

      // Phase 3: Prompt Pattern writes
      for (const data of patternWrites) {
        log.writePromptPattern(data);
        patternsUpdated++;
      }

      // Update metadata timestamps
      const now = new Date().toISOString();
      log.setMetadata('last_tuning_recompute', now);
      log.setMetadata('last_combo_recompute', now);
      log.setMetadata('last_prompt_recompute', now);
      log.setMetadata('total_executions_logged', String(log.getExecutionCount()));
    });

    try {
      writeAll();
    } catch (err) {
      if (process.env.LEARNING_DEBUG) {
        console.error(`[background-learner] Transaction failed: ${err.message}`);
      }
    }
  } else {
    // No db available but log helpers may have worked via their own getDb() calls
    // (this path is unlikely since we checked isAvailable() above)
    for (const data of tuningWrites) {
      log.writeTuning(data);
      tuningUpdated++;
    }
  }

  // Checkpoint WAL to persist changes and prevent unbounded growth
  if (db) {
    try {
      db.pragma('wal_checkpoint(PASSIVE)');
    } catch (err) {
      if (process.env.LEARNING_DEBUG) {
        console.error(`[background-learner] WAL checkpoint failed: ${err.message}`);
      }
    }
  }

  const durationMs = Date.now() - startTime;

  return {
    tuning_updated: tuningUpdated,
    combos_updated: combosUpdated,
    patterns_updated: patternsUpdated,
    duration_ms: durationMs,
    skipped: false,
  };
}

// ============================================================================
// PARAMETER OPTIMIZATION
// ============================================================================

/**
 * Default quality thresholds. Can be overridden per task_type via process.env.QUALITY_THRESHOLDS.
 * Example: QUALITY_THRESHOLDS='{"security":{"high":0.9,"medium":0.75},"default":{"high":0.85,"medium":0.7}}'
 */
const DEFAULT_QUALITY_THRESHOLDS = {
  default: { high: 0.85, medium: 0.7 },
};

let _qualityThresholds = null;

function _getQualityThresholds(taskType) {
  if (!_qualityThresholds) {
    try {
      _qualityThresholds = process.env.QUALITY_THRESHOLDS
        ? JSON.parse(process.env.QUALITY_THRESHOLDS)
        : DEFAULT_QUALITY_THRESHOLDS;
    } catch (_e) {
      _qualityThresholds = DEFAULT_QUALITY_THRESHOLDS;
    }
  }

  return _qualityThresholds[taskType] || _qualityThresholds.default || DEFAULT_QUALITY_THRESHOLDS.default;
}

/**
 * Compute optimal parameters based on execution statistics.
 * Uses simple heuristics -- no ML needed.
 */
function computeOptimalParams(stats, qualityTrend, taskType = 'default') {
  const params = {};
  const thresholds = _getQualityThresholds(taskType);

  // Temperature: lower for high-precision tasks, higher for creative tasks
  if (stats.avg_quality > thresholds.high) {
    // Currently performing well -- keep temperature low
    params.temperature = 0.2;
  } else if (stats.avg_quality > thresholds.medium) {
    params.temperature = 0.4;
  } else {
    // Quality is low -- try more exploration
    params.temperature = 0.6;
  }

  // Max tokens: based on output token usage patterns
  // If model consistently uses many output tokens, suggest higher limit
  // (We do not have per-execution max_tokens data, so estimate from output_tokens)

  // top_p: keep standard unless quality is very low
  if (stats.avg_quality < 0.5) {
    params.top_p = 0.95; // More diverse sampling
  } else {
    params.top_p = 0.9;
  }

  // Quality trend analysis: detect degradation
  if (qualityTrend.length >= 5) {
    const recentAvg = _mean(qualityTrend.slice(0, 5));
    const olderAvg = _mean(qualityTrend.slice(5));
    if (olderAvg > 0 && recentAvg < olderAvg * 0.9) {
      params._quality_degrading = true;
      params._degradation_pct = Math.round((1 - recentAvg / olderAvg) * 100);
    }
  }

  return params;
}

/**
 * Parameter classifiers registry. Can be extended via _registerParamClassifier().
 * Each classifier is a function (params) => string | null that returns a pattern part.
 */
const _paramClassifiers = [
  // Temperature bucket
  (params) => {
    const temp = params.temperature;
    if (temp === undefined) return null;
    if (temp <= 0.1) return 'temp_zero';
    if (temp <= 0.3) return 'temp_low';
    if (temp <= 0.6) return 'temp_mid';
    return 'temp_high';
  },

  // Schema presence
  (params) => params.schema ? 'with_schema' : null,

  // Max tokens bucket
  (params) => {
    const maxTok = params.max_tokens;
    if (maxTok === undefined) return null;
    if (maxTok <= 500) return 'short_output';
    if (maxTok <= 2000) return 'medium_output';
    return 'long_output';
  },
];

/**
 * Register a custom parameter classifier.
 * Example: _registerParamClassifier((params) => params.top_p >= 0.95 ? 'high_diversity' : null)
 */
function _registerParamClassifier(classifier) {
  if (typeof classifier === 'function') {
    _paramClassifiers.push(classifier);
  }
}

/**
 * Classify parameters into a named pattern.
 */
function _classifyParams(params) {
  const parts = [];

  for (const classifier of _paramClassifiers) {
    try {
      const part = classifier(params);
      if (part) parts.push(part);
    } catch (_e) {
      // Ignore classifier errors
    }
  }

  return parts.length > 0 ? parts.join('+') : 'default';
}

// ============================================================================
// MATH HELPERS
// ============================================================================

function _mean(arr) {
  if (!arr || arr.length === 0) return 0;
  return arr.reduce((s, v) => s + (v || 0), 0) / arr.length;
}

function _stddev(arr) {
  if (!arr || arr.length < 2) return 0;
  const avg = _mean(arr);
  const variance = arr.reduce((s, v) => s + Math.pow((v || 0) - avg, 2), 0) / arr.length;
  return Math.sqrt(variance);
}

// ============================================================================
// MAIN
// ============================================================================

async function runOnce() {
  const result = await recompute();

  if (!result.skipped) {
    console.log(
      `[background-learner] Recompute complete: ` +
      `tuning=${result.tuning_updated}, combos=${result.combos_updated}, ` +
      `patterns=${result.patterns_updated} in ${result.duration_ms}ms`
    );
  } else {
    console.log('[background-learner] Skipped: database unavailable');
  }

  return result;
}

if (isDaemon) {
  const log = await getLogger();
  console.log(`[background-learner] Starting daemon mode (interval: ${intervalSec}s)`);
  console.log(`[background-learner] Database: ${log.getDbPath()}`);
  console.log(`[background-learner] Press Ctrl+C to stop`);
  console.log('');

  // Run immediately, then on interval
  await runOnce();

  const intervalId = setInterval(async () => {
    await runOnce();
  }, intervalSec * 1000);

  // Clean shutdown
  process.on('SIGINT', async () => {
    console.log('\n[background-learner] Shutting down...');
    clearInterval(intervalId);
    const log = await getLogger();
    log.close();
    process.exit(0);
  });
  process.on('SIGTERM', async () => {
    clearInterval(intervalId);
    const log = await getLogger();
    log.close();
    process.exit(0);
  });
} else {
  // Single run mode
  const result = await runOnce();
  const log = await getLogger();
  log.close();
  process.exit(result.skipped ? 1 : 0);
}
