/**
 * Learning Logger - Synchronous execution logging with <10ms overhead
 *
 * Uses better-sqlite3 for synchronous, zero-dependency SQLite access.
 * WAL journal mode enables concurrent reads/writes safely.
 * Graceful degradation: if the DB is unavailable, logs are silently dropped.
 *
 * Usage (ESM - standard for this project):
 *   import { logExecution, logWorkerResult, logCombination, getDb, close } from './shared/learning-logger.js'
 *
 *   // Log a single execution (<10ms)
 *   logExecution({
 *     run_id: 'a1b2c3d4-...',   // UUID tying all workers from one consensus run
 *     model: 'opus',
 *     workflow: 'code-review',
 *     task_type: 'security',
 *     quality_score: 0.92,
 *     input_tokens: 1500,
 *     output_tokens: 800,
 *     duration_ms: 3200,
 *   })
 *
 *   // Log a worker result from consensus
 *   logWorkerResult({
 *     model: 'sonnet',
 *     model_role: 'worker',
 *     workflow: 'ai-consensus-debate',
 *     task_type: 'architecture',
 *     phase: 'Proposal',
 *     quality_score: 0.85,
 *     confidence: 0.88,
 *     was_selected: false,
 *     input_tokens: 2000,
 *     output_tokens: 1200,
 *     cost_usd: 0.024,
 *     duration_ms: 4500,
 *   })
 *
 *   // Log a model combination result
 *   logCombination({
 *     task_type: 'security',
 *     worker_models: ['opus', 'sonnet', 'haiku'],
 *     arbiter_model: 'opus',
 *     consensus_score: 0.91,
 *     quality_score: 0.94,
 *     total_cost_usd: 0.15,
 *     total_duration_ms: 12000,
 *   })
 */

import { createRequire } from 'module';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { join } from 'path';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const DB_DIR = join(HOME, '.claude', 'learning', 'db');
const DB_PATH = join(DB_DIR, 'learning.db');
const SCHEMA_PATH = join(HOME, '.claude', 'learning', 'init-learning-db.sql');

// ============================================================================
// DATABASE SINGLETON
// ============================================================================

let _db = null;
let _stmts = {};
let _available = true;

/**
 * Get or create the database connection.
 * Returns null if database is unavailable (graceful degradation).
 */
export function getDb() {
  if (_db) return _db;
  if (!_available) return null;

  try {
    // Ensure directory exists
    if (!existsSync(DB_DIR)) {
      mkdirSync(DB_DIR, { recursive: true });
    }

    // better-sqlite3 is a native addon; use createRequire for ESM compatibility
    const require = createRequire(import.meta.url);
    const Database = require('better-sqlite3');
    _db = new Database(DB_PATH);

    // Configure for performance + safety
    _db.pragma('journal_mode = WAL');
    _db.pragma('synchronous = NORMAL');
    _db.pragma('busy_timeout = 5000');
    _db.pragma('cache_size = -2000');
    _db.pragma('foreign_keys = ON');

    // Initialize schema if needed
    _initSchema(_db);

    // Prepare hot-path statements
    _prepareStatements(_db);

    return _db;
  } catch (err) {
    // Graceful degradation: mark as unavailable, never retry this session
    _available = false;
    _db = null;
    console.warn(`[learning-logger] DB initialization failed (learning disabled): ${err.message}`);
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning-logger] DB init stack trace:`, err);
    }
    return null;
  }
}

/**
 * Initialize schema from SQL file or inline fallback
 */
function _initSchema(db) {
  // Check if tables exist
  const tableCheck = db.prepare(
    "SELECT count(*) as cnt FROM sqlite_master WHERE type='table' AND name='execution_log'"
  ).get();

  if (tableCheck.cnt > 0) {
    // Schema exists -- apply migrations for new columns
    _migrateSchema(db);
    return;
  }

  // Try loading from SQL file
  let sql;
  try {
    sql = readFileSync(SCHEMA_PATH, 'utf-8');
  } catch (_err) {
    // Inline fallback: minimal schema
    sql = _INLINE_SCHEMA;
  }

  db.exec(sql);
}

/**
 * Apply incremental schema migrations to an existing database.
 * Each migration checks whether the column/index already exists before altering.
 */
function _migrateSchema(db) {
  // Migration 1: Add run_id column to execution_log
  const cols = db.prepare("PRAGMA table_info(execution_log)").all();
  const colNames = cols.map(c => c.name);

  if (!colNames.includes('run_id')) {
    db.exec("ALTER TABLE execution_log ADD COLUMN run_id TEXT");
    db.exec("CREATE INDEX IF NOT EXISTS idx_exec_run_id ON execution_log(run_id)");
    if (process.env.LEARNING_DEBUG) {
      console.error('[learning-logger] Migration: added run_id column to execution_log');
    }
  }
}

/**
 * Pre-compile prepared statements for <10ms insert performance.
 * Prepared statements skip the SQL parse step on every call.
 */
function _prepareStatements(db) {
  _stmts.insertExecution = db.prepare(`
    INSERT INTO execution_log (
      run_id,
      model, model_role, workflow, task_type, phase, label,
      parameters, quality_score, confidence, consensus_score, was_selected,
      input_tokens, output_tokens, cost_usd, duration_ms,
      outcome, outcome_notes, request_hash, response_hash, error
    ) VALUES (
      @run_id,
      @model, @model_role, @workflow, @task_type, @phase, @label,
      @parameters, @quality_score, @confidence, @consensus_score, @was_selected,
      @input_tokens, @output_tokens, @cost_usd, @duration_ms,
      @outcome, @outcome_notes, @request_hash, @response_hash, @error
    )
  `);

  _stmts.updateOutcome = db.prepare(`
    UPDATE execution_log
    SET outcome = @outcome, outcome_notes = @outcome_notes
    WHERE id = @id
  `);

  _stmts.upsertTuning = db.prepare(`
    INSERT INTO model_tuning (
      model, task_type, optimal_params,
      avg_quality, avg_confidence, avg_cost_usd, avg_duration_ms,
      sample_count, success_rate, selection_rate,
      quality_trend, cost_trend
    ) VALUES (
      @model, @task_type, @optimal_params,
      @avg_quality, @avg_confidence, @avg_cost_usd, @avg_duration_ms,
      @sample_count, @success_rate, @selection_rate,
      @quality_trend, @cost_trend
    )
    ON CONFLICT(model, task_type) DO UPDATE SET
      updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
      optimal_params = @optimal_params,
      avg_quality = @avg_quality,
      avg_confidence = @avg_confidence,
      avg_cost_usd = @avg_cost_usd,
      avg_duration_ms = @avg_duration_ms,
      sample_count = @sample_count,
      success_rate = @success_rate,
      selection_rate = @selection_rate,
      quality_trend = @quality_trend,
      cost_trend = @cost_trend
  `);

  _stmts.upsertPromptPattern = db.prepare(`
    INSERT INTO prompt_patterns (
      model, task_type, pattern_name, pattern_template, instructions,
      avg_quality, avg_confidence, usage_count, success_rate, vs_baseline_quality
    ) VALUES (
      @model, @task_type, @pattern_name, @pattern_template, @instructions,
      @avg_quality, @avg_confidence, @usage_count, @success_rate, @vs_baseline_quality
    )
    ON CONFLICT(model, task_type, pattern_name) DO UPDATE SET
      updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
      pattern_template = @pattern_template,
      instructions = @instructions,
      avg_quality = @avg_quality,
      avg_confidence = @avg_confidence,
      usage_count = @usage_count,
      success_rate = @success_rate,
      vs_baseline_quality = @vs_baseline_quality
  `);

  _stmts.upsertCombination = db.prepare(`
    INSERT INTO model_combinations (
      task_type, worker_models, arbiter_model,
      avg_consensus, avg_quality, avg_cost_usd, avg_duration_ms,
      usage_count, synergy_score, diversity_score
    ) VALUES (
      @task_type, @worker_models, @arbiter_model,
      @avg_consensus, @avg_quality, @avg_cost_usd, @avg_duration_ms,
      @usage_count, @synergy_score, @diversity_score
    )
    ON CONFLICT(task_type, worker_models, arbiter_model) DO UPDATE SET
      updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
      avg_consensus = @avg_consensus,
      avg_quality = @avg_quality,
      avg_cost_usd = @avg_cost_usd,
      avg_duration_ms = @avg_duration_ms,
      usage_count = @usage_count,
      synergy_score = @synergy_score,
      diversity_score = @diversity_score
  `);

  _stmts.upsertMetadata = db.prepare(`
    INSERT INTO learning_metadata (key, value)
    VALUES (@key, @value)
    ON CONFLICT(key) DO UPDATE SET
      value = @value,
      updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
  `);

  _stmts.getMetadata = db.prepare(`
    SELECT value FROM learning_metadata WHERE key = @key
  `);

  // Query statements for background-learner.js
  _stmts.getModelTaskStats = db.prepare(`
    SELECT
      model,
      task_type,
      COUNT(*)                              AS sample_count,
      AVG(quality_score)                    AS avg_quality,
      AVG(confidence)                       AS avg_confidence,
      AVG(cost_usd)                         AS avg_cost_usd,
      AVG(duration_ms)                      AS avg_duration_ms,
      SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS success_rate,
      SUM(was_selected) * 1.0 / COUNT(*)    AS selection_rate
    FROM execution_log
    WHERE model = @model AND task_type = @task_type
      AND quality_score IS NOT NULL
  `);

  _stmts.getRecentQuality = db.prepare(`
    SELECT quality_score FROM execution_log
    WHERE model = @model AND task_type = @task_type
      AND quality_score IS NOT NULL
    ORDER BY timestamp DESC
    LIMIT 20
  `);

  _stmts.getRecentCost = db.prepare(`
    SELECT cost_usd FROM execution_log
    WHERE model = @model AND task_type = @task_type
      AND cost_usd IS NOT NULL
    ORDER BY timestamp DESC
    LIMIT 20
  `);

  _stmts.getDistinctModelTasks = db.prepare(`
    SELECT DISTINCT model, task_type
    FROM execution_log
    WHERE quality_score IS NOT NULL
  `);

  _stmts.getExecutionCount = db.prepare(`
    SELECT COUNT(*) as cnt FROM execution_log
  `);

  _stmts.getRecentExecutions = db.prepare(`
    SELECT * FROM execution_log
    ORDER BY timestamp DESC
    LIMIT @limit
  `);

  _stmts.getTuning = db.prepare(`
    SELECT * FROM model_tuning
    WHERE model = @model AND task_type = @task_type
  `);

  _stmts.getAllTuning = db.prepare(`
    SELECT * FROM model_tuning
    ORDER BY avg_quality DESC
  `);

  _stmts.getBestCombination = db.prepare(`
    SELECT * FROM model_combinations
    WHERE task_type = @task_type
    ORDER BY synergy_score DESC
    LIMIT 1
  `);

  _stmts.getAllCombinations = db.prepare(`
    SELECT * FROM model_combinations
    ORDER BY synergy_score DESC
  `);

  _stmts.getCombinationExact = db.prepare(`
    SELECT * FROM model_combinations
    WHERE task_type = @task_type
      AND worker_models = @worker_models
      AND (arbiter_model = @arbiter_model OR (arbiter_model IS NULL AND @arbiter_model IS NULL))
  `);

  _stmts.getPromptPatterns = db.prepare(`
    SELECT * FROM prompt_patterns
    WHERE model = @model AND task_type = @task_type
    ORDER BY avg_quality DESC
  `);
}

// ============================================================================
// PUBLIC API - LOGGING (<10ms per call)
// ============================================================================

/**
 * Log an execution event. This is the primary hot path.
 * Returns the row ID or -1 if logging was skipped.
 *
 * @param {Object} data - Execution data
 * @returns {number} Row ID or -1
 */
export function logExecution(data) {
  const db = getDb();
  if (!db) return -1;

  try {
    const result = _stmts.insertExecution.run({
      run_id:          data.run_id || null,
      model:           data.model || 'unknown',
      model_role:      data.model_role || 'worker',
      workflow:        data.workflow || null,
      task_type:       data.task_type || null,
      phase:           data.phase || null,
      label:           data.label || null,
      parameters:      data.parameters ? JSON.stringify(data.parameters) : '{}',
      quality_score:   data.quality_score ?? null,
      confidence:      data.confidence ?? null,
      consensus_score: data.consensus_score ?? null,
      was_selected:    data.was_selected ? 1 : 0,
      input_tokens:    data.input_tokens || 0,
      output_tokens:   data.output_tokens || 0,
      cost_usd:        data.cost_usd || 0.0,
      duration_ms:     data.duration_ms || 0,
      outcome:         data.outcome || 'unknown',
      outcome_notes:   data.outcome_notes || null,
      request_hash:    data.request_hash || null,
      response_hash:   data.response_hash || null,
      error:           data.error || null,
    });
    return Number(result.lastInsertRowid);
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning-logger] Insert failed: ${err.message}`);
    }
    return -1;
  }
}

/**
 * Convenience: log a worker result from a consensus workflow.
 * Normalizes the common fields.
 */
export function logWorkerResult(data) {
  return logExecution({
    run_id:          data.run_id,
    model:           data.model,
    model_role:      data.model_role || 'worker',
    workflow:        data.workflow,
    task_type:       data.task_type,
    phase:           data.phase,
    label:           data.label || `worker:${data.model}`,
    parameters:      data.parameters,
    quality_score:   data.quality_score,
    confidence:      data.confidence,
    consensus_score: data.consensus_score,
    was_selected:    data.was_selected ? 1 : 0,
    input_tokens:    data.input_tokens,
    output_tokens:   data.output_tokens,
    cost_usd:        data.cost_usd,
    duration_ms:     data.duration_ms,
    outcome:         data.outcome,
    error:           data.error,
  });
}

/**
 * Log a model combination from a multi-worker consensus run.
 * This is a write to model_combinations table.
 */
export function logCombination(data) {
  const db = getDb();
  if (!db) return -1;

  try {
    const workerModels = Array.isArray(data.worker_models)
      ? JSON.stringify([...data.worker_models].sort())
      : data.worker_models;

    // Read existing to compute running averages (exact match on combo identity)
    const existing = _stmts.getCombinationExact.get({
      task_type: data.task_type,
      worker_models: workerModels,
      arbiter_model: data.arbiter_model || null,
    });
    let usageCount = 1;
    let avgConsensus = data.consensus_score || 0;
    let avgQuality = data.quality_score || 0;
    let avgCost = data.total_cost_usd || 0;
    let avgDuration = data.total_duration_ms || 0;

    if (existing) {
      usageCount = existing.usage_count + 1;
      avgConsensus = _runningAvg(existing.avg_consensus, data.consensus_score || 0, usageCount);
      avgQuality = _runningAvg(existing.avg_quality, data.quality_score || 0, usageCount);
      avgCost = _runningAvg(existing.avg_cost_usd, data.total_cost_usd || 0, usageCount);
      avgDuration = _runningAvg(existing.avg_duration_ms, data.total_duration_ms || 0, usageCount);
    }

    const result = _stmts.upsertCombination.run({
      task_type:      data.task_type,
      worker_models:  workerModels,
      arbiter_model:  data.arbiter_model || null,
      avg_consensus:  avgConsensus,
      avg_quality:    avgQuality,
      avg_cost_usd:   avgCost,
      avg_duration_ms: avgDuration,
      usage_count:    usageCount,
      synergy_score:  data.synergy_score || 0,
      diversity_score: data.diversity_score || 0,
    });
    return Number(result.lastInsertRowid);
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning-logger] Combination insert failed: ${err.message}`);
    }
    return -1;
  }
}

/**
 * Update the outcome of a previously logged execution.
 */
export function updateOutcome(id, outcome, notes) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.updateOutcome.run({
      id,
      outcome: outcome || 'unknown',
      outcome_notes: notes || null,
    });
    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning-logger] Outcome update failed: ${err.message}`);
    }
    return false;
  }
}

// ============================================================================
// PUBLIC API - QUERIES (for background-learner.js and workflows)
// ============================================================================

/**
 * Get aggregated stats for a model/task combination.
 */
export function getModelTaskStats(model, taskType) {
  const db = getDb();
  if (!db) return null;

  try {
    return _stmts.getModelTaskStats.get({ model, task_type: taskType });
  } catch (_err) {
    return null;
  }
}

/**
 * Get all distinct model/task pairs that have been logged.
 */
export function getDistinctModelTasks() {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getDistinctModelTasks.all();
  } catch (_err) {
    return [];
  }
}

/**
 * Get recent quality scores for trend analysis.
 */
export function getRecentQuality(model, taskType) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getRecentQuality.all({ model, task_type: taskType })
      .map(r => r.quality_score);
  } catch (_err) {
    return [];
  }
}

/**
 * Get recent cost data for trend analysis.
 */
export function getRecentCost(model, taskType) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getRecentCost.all({ model, task_type: taskType })
      .map(r => r.cost_usd);
  } catch (_err) {
    return [];
  }
}

/**
 * Get tuning data for a model/task pair.
 */
export function getTuning(model, taskType) {
  const db = getDb();
  if (!db) return null;

  try {
    return _stmts.getTuning.get({ model, task_type: taskType });
  } catch (_err) {
    return null;
  }
}

/**
 * Get all tuning records.
 */
export function getAllTuning() {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getAllTuning.all();
  } catch (_err) {
    return [];
  }
}

/**
 * Get best model combination for a task type.
 */
export function getBestCombination(taskType) {
  const db = getDb();
  if (!db) return null;

  try {
    return _stmts.getBestCombination.get({ task_type: taskType });
  } catch (_err) {
    return null;
  }
}

/**
 * Get all model combinations.
 */
export function getAllCombinations() {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getAllCombinations.all();
  } catch (_err) {
    return [];
  }
}

/**
 * Get prompt patterns for a model/task pair.
 */
export function getPromptPatterns(model, taskType) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getPromptPatterns.all({ model, task_type: taskType });
  } catch (_err) {
    return [];
  }
}

/**
 * Get total execution count.
 */
export function getExecutionCount() {
  const db = getDb();
  if (!db) return 0;

  try {
    return _stmts.getExecutionCount.get().cnt;
  } catch (_err) {
    return 0;
  }
}

/**
 * Get recent executions.
 */
export function getRecentExecutions(limit = 20) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getRecentExecutions.all({ limit });
  } catch (_err) {
    return [];
  }
}

/**
 * Get or set metadata.
 */
export function getMetadata(key) {
  const db = getDb();
  if (!db) return null;

  try {
    const row = _stmts.getMetadata.get({ key });
    return row ? row.value : null;
  } catch (_err) {
    return null;
  }
}

export function setMetadata(key, value) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.upsertMetadata.run({ key, value: String(value) });
    return true;
  } catch (_err) {
    return false;
  }
}

/**
 * Write tuning data (used by background-learner.js).
 */
export function writeTuning(data) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.upsertTuning.run({
      model:          data.model,
      task_type:      data.task_type,
      optimal_params: data.optimal_params ? JSON.stringify(data.optimal_params) : '{}',
      avg_quality:    data.avg_quality || 0,
      avg_confidence: data.avg_confidence || 0,
      avg_cost_usd:   data.avg_cost_usd || 0,
      avg_duration_ms: data.avg_duration_ms || 0,
      sample_count:   data.sample_count || 0,
      success_rate:   data.success_rate || 0,
      selection_rate: data.selection_rate || 0,
      quality_trend:  JSON.stringify(data.quality_trend || []),
      cost_trend:     JSON.stringify(data.cost_trend || []),
    });
    return true;
  } catch (_err) {
    return false;
  }
}

/**
 * Write prompt pattern data (used by background-learner.js).
 */
export function writePromptPattern(data) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.upsertPromptPattern.run({
      model:              data.model,
      task_type:          data.task_type,
      pattern_name:       data.pattern_name,
      pattern_template:   data.pattern_template || null,
      instructions:       data.instructions || null,
      avg_quality:        data.avg_quality || 0,
      avg_confidence:     data.avg_confidence || 0,
      usage_count:        data.usage_count || 0,
      success_rate:       data.success_rate || 0,
      vs_baseline_quality: data.vs_baseline_quality || 0,
    });
    return true;
  } catch (_err) {
    return false;
  }
}

/**
 * Write combination data (used by background-learner.js).
 */
export function writeCombination(data) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.upsertCombination.run({
      task_type:       data.task_type,
      worker_models:   Array.isArray(data.worker_models) ? JSON.stringify([...data.worker_models].sort()) : data.worker_models,
      arbiter_model:   data.arbiter_model || null,
      avg_consensus:   data.avg_consensus || 0,
      avg_quality:     data.avg_quality || 0,
      avg_cost_usd:    data.avg_cost_usd || 0,
      avg_duration_ms: data.avg_duration_ms || 0,
      usage_count:     data.usage_count || 0,
      synergy_score:   data.synergy_score || 0,
      diversity_score: data.diversity_score || 0,
    });
    return true;
  } catch (_err) {
    return false;
  }
}

// ============================================================================
// PUBLIC API - BATCH OPERATIONS
// ============================================================================

/**
 * Log multiple executions in a single transaction.
 * Much faster than individual inserts for bulk logging.
 */
export function logExecutionBatch(entries) {
  const db = getDb();
  if (!db) return [];

  try {
    const ids = [];
    const batchInsert = db.transaction((rows) => {
      for (const data of rows) {
        const result = _stmts.insertExecution.run({
          run_id:          data.run_id || null,
          model:           data.model || 'unknown',
          model_role:      data.model_role || 'worker',
          workflow:        data.workflow || null,
          task_type:       data.task_type || null,
          phase:           data.phase || null,
          label:           data.label || null,
          parameters:      data.parameters ? JSON.stringify(data.parameters) : '{}',
          quality_score:   data.quality_score ?? null,
          confidence:      data.confidence ?? null,
          consensus_score: data.consensus_score ?? null,
          was_selected:    data.was_selected ? 1 : 0,
          input_tokens:    data.input_tokens || 0,
          output_tokens:   data.output_tokens || 0,
          cost_usd:        data.cost_usd || 0.0,
          duration_ms:     data.duration_ms || 0,
          outcome:         data.outcome || 'unknown',
          outcome_notes:   data.outcome_notes || null,
          request_hash:    data.request_hash || null,
          response_hash:   data.response_hash || null,
          error:           data.error || null,
        });
        ids.push(Number(result.lastInsertRowid));
      }
    });
    batchInsert(entries);
    return ids;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning-logger] Batch insert failed: ${err.message}`);
    }
    return [];
  }
}

// ============================================================================
// LIFECYCLE
// ============================================================================

/**
 * Close the database connection.
 * Call this during process exit cleanup.
 */
export function close() {
  if (_db) {
    try {
      // Finalize all prepared statements before closing
      for (const stmt of Object.values(_stmts)) {
        try {
          if (stmt && typeof stmt.finalize === 'function') {
            stmt.finalize();
          }
        } catch (_e) {
          // Ignore finalize errors
        }
      }
      _db.close();
    } catch (_err) {
      // Ignore close errors
    }
    _db = null;
    _stmts = {};
  }
}

/**
 * Check if the database is available.
 */
export function isAvailable() {
  return _available && (!!_db || getDb() !== null);
}

/**
 * Get database file path.
 */
export function getDbPath() {
  return DB_PATH;
}

// ============================================================================
// INTERNAL HELPERS
// ============================================================================

function _runningAvg(oldAvg, newValue, count) {
  if (count <= 1) return newValue;
  return (oldAvg * (count - 1) + newValue) / count;
}

// Inline fallback schema (used if init-learning-db.sql is not found)
const _INLINE_SCHEMA = `
CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    run_id TEXT,
    model TEXT NOT NULL,
    model_role TEXT NOT NULL DEFAULT 'worker',
    workflow TEXT, task_type TEXT, phase TEXT, label TEXT,
    parameters TEXT DEFAULT '{}',
    quality_score REAL, confidence REAL, consensus_score REAL,
    was_selected INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0 CHECK(input_tokens >= 0),
    output_tokens INTEGER DEFAULT 0 CHECK(output_tokens >= 0),
    cost_usd REAL DEFAULT 0.0 CHECK(cost_usd >= 0),
    duration_ms INTEGER DEFAULT 0 CHECK(duration_ms >= 0),
    outcome TEXT DEFAULT 'unknown', outcome_notes TEXT,
    request_hash TEXT, response_hash TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_model ON execution_log(model);
CREATE INDEX IF NOT EXISTS idx_exec_workflow ON execution_log(workflow);
CREATE INDEX IF NOT EXISTS idx_exec_task_type ON execution_log(task_type);
CREATE INDEX IF NOT EXISTS idx_exec_model_task ON execution_log(model, task_type);
CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_exec_run_id ON execution_log(run_id);

CREATE TABLE IF NOT EXISTS model_tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    optimal_params TEXT NOT NULL DEFAULT '{}',
    avg_quality REAL DEFAULT 0.0 CHECK(avg_quality >= 0),
    avg_confidence REAL DEFAULT 0.0 CHECK(avg_confidence >= 0),
    avg_cost_usd REAL DEFAULT 0.0 CHECK(avg_cost_usd >= 0),
    avg_duration_ms REAL DEFAULT 0.0 CHECK(avg_duration_ms >= 0),
    sample_count INTEGER DEFAULT 0 CHECK(sample_count >= 0),
    success_rate REAL DEFAULT 0.0 CHECK(success_rate >= 0),
    selection_rate REAL DEFAULT 0.0 CHECK(selection_rate >= 0),
    quality_trend TEXT DEFAULT '[]', cost_trend TEXT DEFAULT '[]',
    UNIQUE(model, task_type)
);

CREATE TABLE IF NOT EXISTS prompt_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    pattern_template TEXT, instructions TEXT,
    avg_quality REAL DEFAULT 0.0 CHECK(avg_quality >= 0),
    avg_confidence REAL DEFAULT 0.0 CHECK(avg_confidence >= 0),
    usage_count INTEGER DEFAULT 0 CHECK(usage_count >= 0),
    success_rate REAL DEFAULT 0.0 CHECK(success_rate >= 0),
    vs_baseline_quality REAL DEFAULT 0.0,
    UNIQUE(model, task_type, pattern_name)
);

CREATE TABLE IF NOT EXISTS model_combinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    task_type TEXT NOT NULL,
    worker_models TEXT NOT NULL, arbiter_model TEXT,
    avg_consensus REAL DEFAULT 0.0 CHECK(avg_consensus >= 0),
    avg_quality REAL DEFAULT 0.0 CHECK(avg_quality >= 0),
    avg_cost_usd REAL DEFAULT 0.0 CHECK(avg_cost_usd >= 0),
    avg_duration_ms REAL DEFAULT 0.0 CHECK(avg_duration_ms >= 0),
    usage_count INTEGER DEFAULT 0 CHECK(usage_count >= 0),
    synergy_score REAL DEFAULT 0.0, diversity_score REAL DEFAULT 0.0,
    UNIQUE(task_type, worker_models, arbiter_model)
);

CREATE TABLE IF NOT EXISTS learning_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT OR IGNORE INTO learning_metadata (key, value) VALUES
    ('schema_version', '1'),
    ('created_at', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('last_tuning_recompute', ''),
    ('last_prompt_recompute', ''),
    ('last_combo_recompute', ''),
    ('total_executions_logged', '0');
`;

// ============================================================================
// PROCESS CLEANUP
// ============================================================================

// Auto-close on exit to prevent WAL corruption
process.on('exit', close);

// ============================================================================
// DEFAULT EXPORT (for convenience)
// ============================================================================

export default {
  logExecution,
  logWorkerResult,
  logCombination,
  logExecutionBatch,
  updateOutcome,
  getModelTaskStats,
  getDistinctModelTasks,
  getRecentQuality,
  getRecentCost,
  getTuning,
  getAllTuning,
  getBestCombination,
  getAllCombinations,
  getPromptPatterns,
  getExecutionCount,
  getRecentExecutions,
  getMetadata,
  setMetadata,
  writeTuning,
  writePromptPattern,
  writeCombination,
  getDb,
  close,
  isAvailable,
  getDbPath,
};
