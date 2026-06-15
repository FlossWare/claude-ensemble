/**
 * Database Helper - Connection management, schema migration, and query helpers
 *
 * Provides a unified interface for both v1 (init-learning-db.sql) and v2
 * (orchestration-schema.sql) tables. Manages the SQLite connection lifecycle,
 * handles schema migrations, and exposes prepared statements for all tables.
 *
 * Uses better-sqlite3 for synchronous access with <10ms per operation.
 * Graceful degradation: all operations return null/empty on failure.
 *
 * Usage (ESM):
 *   import { getDb, query, exec, logOrchestration, close } from './learning/db.js';
 *
 *   // Low-level query
 *   const rows = query('SELECT * FROM execution_log WHERE model = ?', ['opus']);
 *
 *   // Log to v2 orchestration tables
 *   logOrchestration({ execution_id: uuid, workflow: 'code-review', ... });
 *
 *   // Get best model for a task type
 *   const best = getBestModel('security', 'week');
 */

import { createRequire } from 'module';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const DB_DIR = join(HOME, '.claude', 'learning', 'db');
const DB_PATH = join(DB_DIR, 'learning.db');
const SCHEMA_PATH = join(HOME, '.claude', 'learning', 'init-db.sql');
const LEGACY_SCHEMA_PATH = join(HOME, '.claude', 'learning', 'init-learning-db.sql');

const CURRENT_SCHEMA_VERSION = 2;

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
    if (!existsSync(DB_DIR)) {
      mkdirSync(DB_DIR, { recursive: true });
    }

    const require = createRequire(import.meta.url);
    const Database = require('better-sqlite3');
    _db = new Database(DB_PATH);

    // Configure for performance + safety
    _db.pragma('journal_mode = WAL');
    _db.pragma('synchronous = NORMAL');
    _db.pragma('busy_timeout = 5000');
    _db.pragma('cache_size = -2000');
    _db.pragma('foreign_keys = ON');

    // Initialize or migrate schema
    _initOrMigrate(_db);

    // Prepare hot-path statements
    _prepareStatements(_db);

    return _db;
  } catch (err) {
    _available = false;
    _db = null;
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] DB unavailable: ${err.message}`);
    }
    return null;
  }
}

// ============================================================================
// SCHEMA INITIALIZATION & MIGRATION
// ============================================================================

function _initOrMigrate(db) {
  const version = _getSchemaVersion(db);

  if (version === 0) {
    // Fresh install: apply full unified schema
    _applySchema(db);
  } else if (version < CURRENT_SCHEMA_VERSION) {
    // Migrate from v1 to v2
    _migrateSchema(db, version);
  }
  // else: already at current version, nothing to do
}

function _getSchemaVersion(db) {
  try {
    const tableCheck = db.prepare(
      "SELECT count(*) as cnt FROM sqlite_master WHERE type='table' AND name='learning_metadata'"
    ).get();

    if (tableCheck.cnt === 0) return 0;

    const row = db.prepare(
      "SELECT value FROM learning_metadata WHERE key = 'schema_version'"
    ).get();

    return row ? parseInt(row.value, 10) : 0;
  } catch (_err) {
    return 0;
  }
}

function _applySchema(db) {
  let sql;
  try {
    sql = readFileSync(SCHEMA_PATH, 'utf-8');
  } catch (_err) {
    try {
      sql = readFileSync(LEGACY_SCHEMA_PATH, 'utf-8');
    } catch (_err2) {
      sql = _INLINE_SCHEMA;
    }
  }
  db.exec(sql);
}

function _migrateSchema(db, fromVersion) {
  if (fromVersion < 2) {
    _migrateV1toV2(db);
  }
}

function _migrateV1toV2(db) {
  const migrate = db.transaction(() => {
    // Add new columns to execution_log if missing
    const columns = _getColumnNames(db, 'execution_log');

    const newColumns = [
      { name: 'execution_id',       type: 'TEXT UNIQUE' },
      { name: 'task_description',   type: 'TEXT' },
      { name: 'worker_models',      type: "TEXT DEFAULT '[]'" },
      { name: 'arbiter_model',      type: 'TEXT' },
      { name: 'model_count',        type: 'INTEGER DEFAULT 1' },
      { name: 'strategy',           type: 'TEXT' },
      { name: 'diversity_score',    type: 'REAL' },
      { name: 'total_input_tokens', type: 'INTEGER DEFAULT 0' },
      { name: 'total_output_tokens',type: 'INTEGER DEFAULT 0' },
      { name: 'total_cost_usd',     type: 'REAL DEFAULT 0.0' },
      { name: 'per_model_costs',    type: "TEXT DEFAULT '{}'" },
      { name: 'per_model_durations',type: "TEXT DEFAULT '{}'" },
      { name: 'selected_model',     type: 'TEXT' },
      { name: 'session_id',         type: 'TEXT' },
      { name: 'parent_execution_id',type: 'TEXT' },
    ];

    for (const col of newColumns) {
      if (!columns.includes(col.name)) {
        try {
          db.exec(`ALTER TABLE execution_log ADD COLUMN ${col.name} ${col.type}`);
        } catch (_err) {
          // Column may already exist in some form
        }
      }
    }

    // Create new v2 indexes
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_exec_execution_id ON execution_log(execution_id);
      CREATE INDEX IF NOT EXISTS idx_exec_strategy     ON execution_log(strategy);
      CREATE INDEX IF NOT EXISTS idx_exec_quality      ON execution_log(quality_score);
      CREATE INDEX IF NOT EXISTS idx_exec_workflow_task ON execution_log(workflow, task_type);
      CREATE INDEX IF NOT EXISTS idx_exec_session      ON execution_log(session_id);
      CREATE INDEX IF NOT EXISTS idx_exec_parent       ON execution_log(parent_execution_id);
    `);

    // Create v2 tables (IF NOT EXISTS is safe)
    db.exec(_V2_TABLES_SQL);

    // Update schema version
    db.prepare(
      "INSERT OR REPLACE INTO learning_metadata (key, value) VALUES ('schema_version', ?)"
    ).run(String(CURRENT_SCHEMA_VERSION));

    // Add new metadata keys
    const metadataKeys = [
      ['last_model_performance_recompute', ''],
      ['last_parameter_tuning_recompute', ''],
      ['total_ratings_recorded', '0'],
    ];
    const upsertMeta = db.prepare(
      "INSERT OR IGNORE INTO learning_metadata (key, value) VALUES (?, ?)"
    );
    for (const [key, value] of metadataKeys) {
      upsertMeta.run(key, value);
    }
  });

  migrate();
}

function _getColumnNames(db, tableName) {
  try {
    const info = db.pragma(`table_info(${tableName})`);
    return info.map(col => col.name);
  } catch (_err) {
    return [];
  }
}

// ============================================================================
// PREPARED STATEMENTS
// ============================================================================

function _prepareStatements(db) {
  // --- Orchestration (v2) writes ---

  _stmts.insertOrchestration = db.prepare(`
    INSERT INTO execution_log (
      execution_id, run_id, model, model_role,
      workflow, task_type, task_description, phase, label,
      worker_models, arbiter_model, model_count, strategy,
      parameters, quality_score, confidence, consensus_score, diversity_score,
      was_selected, input_tokens, output_tokens, cost_usd,
      total_input_tokens, total_output_tokens, total_cost_usd, per_model_costs,
      duration_ms, per_model_durations,
      outcome, outcome_notes, error, selected_model,
      session_id, parent_execution_id, request_hash, response_hash
    ) VALUES (
      @execution_id, @run_id, @model, @model_role,
      @workflow, @task_type, @task_description, @phase, @label,
      @worker_models, @arbiter_model, @model_count, @strategy,
      @parameters, @quality_score, @confidence, @consensus_score, @diversity_score,
      @was_selected, @input_tokens, @output_tokens, @cost_usd,
      @total_input_tokens, @total_output_tokens, @total_cost_usd, @per_model_costs,
      @duration_ms, @per_model_durations,
      @outcome, @outcome_notes, @error, @selected_model,
      @session_id, @parent_execution_id, @request_hash, @response_hash
    )
  `);

  // --- model_performance writes ---

  _stmts.upsertModelPerformance = db.prepare(`
    INSERT INTO model_performance (
      model, role, task_type, time_window, window_start, window_end,
      avg_quality, min_quality, max_quality, stddev_quality, median_quality,
      avg_confidence, calibration_error,
      selection_rate, avg_consensus, win_rate,
      avg_cost_usd, total_cost_usd, cost_per_quality,
      avg_duration_ms, p50_duration_ms, p95_duration_ms, p99_duration_ms,
      sample_count, success_count, failure_count, success_rate,
      quality_trend, cost_trend, duration_trend, selection_trend,
      quality_rank, efficiency_rank, speed_rank
    ) VALUES (
      @model, @role, @task_type, @time_window, @window_start, @window_end,
      @avg_quality, @min_quality, @max_quality, @stddev_quality, @median_quality,
      @avg_confidence, @calibration_error,
      @selection_rate, @avg_consensus, @win_rate,
      @avg_cost_usd, @total_cost_usd, @cost_per_quality,
      @avg_duration_ms, @p50_duration_ms, @p95_duration_ms, @p99_duration_ms,
      @sample_count, @success_count, @failure_count, @success_rate,
      @quality_trend, @cost_trend, @duration_trend, @selection_trend,
      @quality_rank, @efficiency_rank, @speed_rank
    )
    ON CONFLICT(model, role, task_type, time_window, window_start) DO UPDATE SET
      computed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
      window_end = @window_end,
      avg_quality = @avg_quality, min_quality = @min_quality,
      max_quality = @max_quality, stddev_quality = @stddev_quality,
      median_quality = @median_quality,
      avg_confidence = @avg_confidence, calibration_error = @calibration_error,
      selection_rate = @selection_rate, avg_consensus = @avg_consensus,
      win_rate = @win_rate,
      avg_cost_usd = @avg_cost_usd, total_cost_usd = @total_cost_usd,
      cost_per_quality = @cost_per_quality,
      avg_duration_ms = @avg_duration_ms, p50_duration_ms = @p50_duration_ms,
      p95_duration_ms = @p95_duration_ms, p99_duration_ms = @p99_duration_ms,
      sample_count = @sample_count, success_count = @success_count,
      failure_count = @failure_count, success_rate = @success_rate,
      quality_trend = @quality_trend, cost_trend = @cost_trend,
      duration_trend = @duration_trend, selection_trend = @selection_trend,
      quality_rank = @quality_rank, efficiency_rank = @efficiency_rank,
      speed_rank = @speed_rank
  `);

  // --- parameter_tuning writes ---

  _stmts.upsertParameterTuning = db.prepare(`
    INSERT INTO parameter_tuning (
      model, task_type, optimal_params, tuning_method,
      sample_count, search_iterations,
      avg_quality, avg_cost_usd, avg_duration_ms, success_rate,
      quality_vs_baseline, cost_vs_baseline, duration_vs_baseline,
      confidence, sensitivity, version, previous_params
    ) VALUES (
      @model, @task_type, @optimal_params, @tuning_method,
      @sample_count, @search_iterations,
      @avg_quality, @avg_cost_usd, @avg_duration_ms, @success_rate,
      @quality_vs_baseline, @cost_vs_baseline, @duration_vs_baseline,
      @confidence, @sensitivity, @version, @previous_params
    )
    ON CONFLICT(model, task_type) DO UPDATE SET
      updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
      optimal_params = @optimal_params, tuning_method = @tuning_method,
      sample_count = @sample_count, search_iterations = @search_iterations,
      avg_quality = @avg_quality, avg_cost_usd = @avg_cost_usd,
      avg_duration_ms = @avg_duration_ms, success_rate = @success_rate,
      quality_vs_baseline = @quality_vs_baseline,
      cost_vs_baseline = @cost_vs_baseline,
      duration_vs_baseline = @duration_vs_baseline,
      confidence = @confidence, sensitivity = @sensitivity,
      version = @version, previous_params = @previous_params
  `);

  // --- quality_ratings writes ---

  _stmts.insertRating = db.prepare(`
    INSERT INTO quality_ratings (
      execution_id, workflow, task_type,
      rating_source, rater_model,
      overall_score, accuracy_score, completeness_score,
      clarity_score, actionability_score, relevance_score,
      thumbs_up, user_comment, user_correction,
      tests_passed, tests_total, lint_errors, build_success, ci_pipeline_url,
      compared_to, relative_score,
      rating_context, superseded_by
    ) VALUES (
      @execution_id, @workflow, @task_type,
      @rating_source, @rater_model,
      @overall_score, @accuracy_score, @completeness_score,
      @clarity_score, @actionability_score, @relevance_score,
      @thumbs_up, @user_comment, @user_correction,
      @tests_passed, @tests_total, @lint_errors, @build_success, @ci_pipeline_url,
      @compared_to, @relative_score,
      @rating_context, @superseded_by
    )
  `);

  // --- Common reads ---

  _stmts.getModelPerformance = db.prepare(`
    SELECT * FROM model_performance
    WHERE model = @model AND task_type = @task_type
      AND time_window = @time_window
    ORDER BY window_start DESC
    LIMIT 1
  `);

  _stmts.getBestModel = db.prepare(`
    SELECT model, avg_quality, avg_cost_usd, cost_per_quality, quality_rank,
           sample_count, success_rate
    FROM model_performance
    WHERE task_type = @task_type AND time_window = @time_window AND role = 'worker'
    ORDER BY quality_rank ASC
  `);

  _stmts.getParameterTuning = db.prepare(`
    SELECT * FROM parameter_tuning
    WHERE model = @model AND task_type = @task_type
  `);

  _stmts.getParameterTuningWithFallback = db.prepare(`
    SELECT * FROM parameter_tuning
    WHERE (model = @model OR model = '*')
      AND (task_type = @task_type OR task_type = '*')
    ORDER BY
      CASE WHEN model = @model AND task_type = @task_type THEN 0
           WHEN model = @model AND task_type = '*' THEN 1
           WHEN model = '*' AND task_type = @task_type THEN 2
           ELSE 3 END
    LIMIT 1
  `);

  _stmts.getQualityRatings = db.prepare(`
    SELECT * FROM quality_ratings
    WHERE execution_id = @execution_id
    ORDER BY timestamp DESC
  `);

  _stmts.getQualityTrend = db.prepare(`
    SELECT window_start, avg_quality, sample_count
    FROM model_performance
    WHERE model = @model AND task_type = @task_type AND time_window = 'day'
    ORDER BY window_start DESC
    LIMIT @limit
  `);

  _stmts.getDriftDetection = db.prepare(`
    SELECT m1.model, m1.task_type,
           m1.avg_quality as current_quality,
           m2.avg_quality as previous_quality,
           (m1.avg_quality - m2.avg_quality) as quality_delta
    FROM model_performance m1
    JOIN model_performance m2
      ON m1.model = m2.model AND m1.task_type = m2.task_type
      AND m1.time_window = 'week' AND m2.time_window = 'week'
      AND m1.window_start > m2.window_start
    ORDER BY quality_delta ASC
    LIMIT @limit
  `);

  _stmts.getExecutionsByWorkflow = db.prepare(`
    SELECT * FROM execution_log
    WHERE workflow = @workflow
    ORDER BY timestamp DESC
    LIMIT @limit
  `);

  _stmts.getExecutionById = db.prepare(`
    SELECT * FROM execution_log
    WHERE execution_id = @execution_id
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

  _stmts.getAllModelPerformance = db.prepare(`
    SELECT * FROM model_performance
    WHERE time_window = @time_window
    ORDER BY task_type, quality_rank ASC
  `);

  _stmts.getDistinctModels = db.prepare(`
    SELECT DISTINCT model FROM execution_log
    WHERE quality_score IS NOT NULL
  `);

  _stmts.getDistinctTaskTypes = db.prepare(`
    SELECT DISTINCT task_type FROM execution_log
    WHERE task_type IS NOT NULL
  `);

  _stmts.getRecentExecutions = db.prepare(`
    SELECT * FROM execution_log
    ORDER BY timestamp DESC
    LIMIT @limit
  `);
}

// ============================================================================
// PUBLIC API - LOW-LEVEL
// ============================================================================

/**
 * Execute a read query. Returns an array of rows.
 */
export function query(sql, params = []) {
  const db = getDb();
  if (!db) return [];

  try {
    return db.prepare(sql).all(...params);
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] Query failed: ${err.message}`);
    }
    return [];
  }
}

/**
 * Execute a read query returning a single row.
 */
export function queryOne(sql, params = []) {
  const db = getDb();
  if (!db) return null;

  try {
    return db.prepare(sql).get(...params) || null;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] QueryOne failed: ${err.message}`);
    }
    return null;
  }
}

/**
 * Execute a write statement (INSERT/UPDATE/DELETE).
 * Returns { changes, lastInsertRowid } or null.
 */
export function exec(sql, params = []) {
  const db = getDb();
  if (!db) return null;

  try {
    const result = db.prepare(sql).run(...params);
    return {
      changes: result.changes,
      lastInsertRowid: Number(result.lastInsertRowid),
    };
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] Exec failed: ${err.message}`);
    }
    return null;
  }
}

/**
 * Run multiple statements in a transaction.
 * fn receives the db instance.
 */
export function transaction(fn) {
  const db = getDb();
  if (!db) return null;

  try {
    const txn = db.transaction(fn);
    return txn(db);
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] Transaction failed: ${err.message}`);
    }
    return null;
  }
}

// ============================================================================
// PUBLIC API - ORCHESTRATION (v2) WRITES
// ============================================================================

/**
 * Log an orchestration execution (full v2 schema).
 * Returns the execution_id (UUID).
 */
export function logOrchestration(data) {
  const db = getDb();
  if (!db) return null;

  try {
    const executionId = data.execution_id || randomUUID();
    _stmts.insertOrchestration.run({
      execution_id:       executionId,
      run_id:             data.run_id || null,
      model:              data.model || data.arbiter_model || 'unknown',
      model_role:         data.model_role || 'worker',
      workflow:           data.workflow || null,
      task_type:          data.task_type || null,
      task_description:   data.task_description || null,
      phase:              data.phase || null,
      label:              data.label || null,
      worker_models:      _jsonStr(data.worker_models, '[]'),
      arbiter_model:      data.arbiter_model || null,
      model_count:        data.model_count || 1,
      strategy:           data.strategy || null,
      parameters:         _jsonStr(data.parameters, '{}'),
      quality_score:      data.quality_score ?? null,
      confidence:         data.confidence ?? null,
      consensus_score:    data.consensus_score ?? null,
      diversity_score:    data.diversity_score ?? null,
      was_selected:       data.was_selected ? 1 : 0,
      input_tokens:       data.input_tokens || 0,
      output_tokens:      data.output_tokens || 0,
      cost_usd:           data.cost_usd || 0.0,
      total_input_tokens: data.total_input_tokens || 0,
      total_output_tokens:data.total_output_tokens || 0,
      total_cost_usd:     data.total_cost_usd || 0.0,
      per_model_costs:    _jsonStr(data.per_model_costs, '{}'),
      duration_ms:        data.duration_ms || 0,
      per_model_durations:_jsonStr(data.per_model_durations, '{}'),
      outcome:            data.outcome || 'unknown',
      outcome_notes:      data.outcome_notes || null,
      error:              data.error || null,
      selected_model:     data.selected_model || null,
      session_id:         data.session_id || null,
      parent_execution_id:data.parent_execution_id || null,
      request_hash:       data.request_hash || null,
      response_hash:      data.response_hash || null,
    });
    return executionId;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] logOrchestration failed: ${err.message}`);
    }
    return null;
  }
}

/**
 * Upsert model performance metrics.
 */
export function upsertModelPerformance(data) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.upsertModelPerformance.run({
      model:            data.model,
      role:             data.role || 'worker',
      task_type:        data.task_type,
      time_window:      data.time_window,
      window_start:     data.window_start,
      window_end:       data.window_end,
      avg_quality:      data.avg_quality || 0,
      min_quality:      data.min_quality ?? null,
      max_quality:      data.max_quality ?? null,
      stddev_quality:   data.stddev_quality ?? null,
      median_quality:   data.median_quality ?? null,
      avg_confidence:   data.avg_confidence || 0,
      calibration_error:data.calibration_error ?? null,
      selection_rate:   data.selection_rate || 0,
      avg_consensus:    data.avg_consensus || 0,
      win_rate:         data.win_rate || 0,
      avg_cost_usd:     data.avg_cost_usd || 0,
      total_cost_usd:   data.total_cost_usd || 0,
      cost_per_quality: data.cost_per_quality ?? null,
      avg_duration_ms:  data.avg_duration_ms || 0,
      p50_duration_ms:  data.p50_duration_ms ?? null,
      p95_duration_ms:  data.p95_duration_ms ?? null,
      p99_duration_ms:  data.p99_duration_ms ?? null,
      sample_count:     data.sample_count || 0,
      success_count:    data.success_count || 0,
      failure_count:    data.failure_count || 0,
      success_rate:     data.success_rate || 0,
      quality_trend:    _jsonStr(data.quality_trend, '[]'),
      cost_trend:       _jsonStr(data.cost_trend, '[]'),
      duration_trend:   _jsonStr(data.duration_trend, '[]'),
      selection_trend:  _jsonStr(data.selection_trend, '[]'),
      quality_rank:     data.quality_rank ?? null,
      efficiency_rank:  data.efficiency_rank ?? null,
      speed_rank:       data.speed_rank ?? null,
    });
    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] upsertModelPerformance failed: ${err.message}`);
    }
    return false;
  }
}

/**
 * Upsert parameter tuning data.
 */
export function upsertParameterTuning(data) {
  const db = getDb();
  if (!db) return false;

  try {
    _stmts.upsertParameterTuning.run({
      model:                data.model,
      task_type:            data.task_type,
      optimal_params:       _jsonStr(data.optimal_params, '{}'),
      tuning_method:        data.tuning_method || 'empirical',
      sample_count:         data.sample_count || 0,
      search_iterations:    data.search_iterations || 0,
      avg_quality:          data.avg_quality || 0,
      avg_cost_usd:         data.avg_cost_usd || 0,
      avg_duration_ms:      data.avg_duration_ms || 0,
      success_rate:         data.success_rate || 0,
      quality_vs_baseline:  data.quality_vs_baseline || 0,
      cost_vs_baseline:     data.cost_vs_baseline || 0,
      duration_vs_baseline: data.duration_vs_baseline || 0,
      confidence:           data.confidence || 0,
      sensitivity:          _jsonStr(data.sensitivity, '{}'),
      version:              data.version || 1,
      previous_params:      _jsonStr(data.previous_params, '{}'),
    });
    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] upsertParameterTuning failed: ${err.message}`);
    }
    return false;
  }
}

/**
 * Insert a quality rating.
 * Returns the row ID or null.
 */
export function insertRating(data) {
  const db = getDb();
  if (!db) return null;

  try {
    const result = _stmts.insertRating.run({
      execution_id:       data.execution_id,
      workflow:           data.workflow || null,
      task_type:          data.task_type || null,
      rating_source:      data.rating_source || 'automated',
      rater_model:        data.rater_model || null,
      overall_score:      data.overall_score,
      accuracy_score:     data.accuracy_score ?? null,
      completeness_score: data.completeness_score ?? null,
      clarity_score:      data.clarity_score ?? null,
      actionability_score:data.actionability_score ?? null,
      relevance_score:    data.relevance_score ?? null,
      thumbs_up:          data.thumbs_up ?? null,
      user_comment:       data.user_comment || null,
      user_correction:    data.user_correction || null,
      tests_passed:       data.tests_passed ?? null,
      tests_total:        data.tests_total ?? null,
      lint_errors:        data.lint_errors ?? null,
      build_success:      data.build_success ?? null,
      ci_pipeline_url:    data.ci_pipeline_url || null,
      compared_to:        data.compared_to || null,
      relative_score:     data.relative_score ?? null,
      rating_context:     _jsonStr(data.rating_context, '{}'),
      superseded_by:      data.superseded_by ?? null,
    });
    return Number(result.lastInsertRowid);
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning/db] insertRating failed: ${err.message}`);
    }
    return null;
  }
}

// ============================================================================
// PUBLIC API - READS
// ============================================================================

/**
 * Get the best-performing models for a task type.
 */
export function getBestModel(taskType, timeWindow = 'week') {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getBestModel.all({ task_type: taskType, time_window: timeWindow });
  } catch (_err) {
    return [];
  }
}

/**
 * Get model performance for a specific model/task/window.
 */
export function getModelPerformance(model, taskType, timeWindow = 'week') {
  const db = getDb();
  if (!db) return null;

  try {
    return _stmts.getModelPerformance.get({
      model, task_type: taskType, time_window: timeWindow,
    }) || null;
  } catch (_err) {
    return null;
  }
}

/**
 * Get all model performance for a time window.
 */
export function getAllModelPerformance(timeWindow = 'all_time') {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getAllModelPerformance.all({ time_window: timeWindow });
  } catch (_err) {
    return [];
  }
}

/**
 * Get optimal parameters for a model/task, with wildcard fallback.
 */
export function getOptimalParams(model, taskType) {
  const db = getDb();
  if (!db) return null;

  try {
    return _stmts.getParameterTuningWithFallback.get({
      model, task_type: taskType,
    }) || null;
  } catch (_err) {
    return null;
  }
}

/**
 * Get quality ratings for an execution.
 */
export function getQualityRatings(executionId) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getQualityRatings.all({ execution_id: executionId });
  } catch (_err) {
    return [];
  }
}

/**
 * Get quality trend (daily avg quality) for a model/task.
 */
export function getQualityTrend(model, taskType, limit = 30) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getQualityTrend.all({ model, task_type: taskType, limit });
  } catch (_err) {
    return [];
  }
}

/**
 * Detect quality drift: models whose quality dropped between windows.
 */
export function detectDrift(limit = 20) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getDriftDetection.all({ limit });
  } catch (_err) {
    return [];
  }
}

/**
 * Get recent executions for a workflow.
 */
export function getExecutionsByWorkflow(workflow, limit = 50) {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getExecutionsByWorkflow.all({ workflow, limit });
  } catch (_err) {
    return [];
  }
}

/**
 * Get a single execution by execution_id.
 */
export function getExecution(executionId) {
  const db = getDb();
  if (!db) return null;

  try {
    return _stmts.getExecutionById.get({ execution_id: executionId }) || null;
  } catch (_err) {
    return null;
  }
}

/**
 * Get recent executions across all workflows.
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
 * Get distinct models that have execution data.
 */
export function getDistinctModels() {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getDistinctModels.all().map(r => r.model);
  } catch (_err) {
    return [];
  }
}

/**
 * Get distinct task types.
 */
export function getDistinctTaskTypes() {
  const db = getDb();
  if (!db) return [];

  try {
    return _stmts.getDistinctTaskTypes.all().map(r => r.task_type);
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

// ============================================================================
// LIFECYCLE
// ============================================================================

/**
 * Close the database connection.
 */
export function close() {
  if (_db) {
    try {
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

/**
 * Get current schema version.
 */
export function getSchemaVersion() {
  const db = getDb();
  if (!db) return 0;
  return _getSchemaVersion(db);
}

// ============================================================================
// INTERNAL HELPERS
// ============================================================================

function _jsonStr(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch (_err) {
    return fallback;
  }
}

// v2 tables SQL (for migration)
const _V2_TABLES_SQL = `
CREATE TABLE IF NOT EXISTS model_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'worker',
    task_type TEXT NOT NULL, time_window TEXT NOT NULL,
    window_start TEXT NOT NULL, window_end TEXT NOT NULL,
    avg_quality REAL NOT NULL DEFAULT 0.0,
    min_quality REAL, max_quality REAL, stddev_quality REAL, median_quality REAL,
    avg_confidence REAL NOT NULL DEFAULT 0.0, calibration_error REAL,
    selection_rate REAL NOT NULL DEFAULT 0.0,
    avg_consensus REAL DEFAULT 0.0, win_rate REAL DEFAULT 0.0,
    avg_cost_usd REAL NOT NULL DEFAULT 0.0, total_cost_usd REAL NOT NULL DEFAULT 0.0,
    cost_per_quality REAL,
    avg_duration_ms REAL NOT NULL DEFAULT 0.0,
    p50_duration_ms REAL, p95_duration_ms REAL, p99_duration_ms REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0, failure_count INTEGER NOT NULL DEFAULT 0,
    success_rate REAL NOT NULL DEFAULT 0.0,
    quality_trend TEXT DEFAULT '[]', cost_trend TEXT DEFAULT '[]',
    duration_trend TEXT DEFAULT '[]', selection_trend TEXT DEFAULT '[]',
    quality_rank INTEGER, efficiency_rank INTEGER, speed_rank INTEGER,
    UNIQUE(model, role, task_type, time_window, window_start)
);
CREATE INDEX IF NOT EXISTS idx_modelperf_model ON model_performance(model);
CREATE INDEX IF NOT EXISTS idx_modelperf_task ON model_performance(task_type);
CREATE INDEX IF NOT EXISTS idx_modelperf_window ON model_performance(time_window);
CREATE INDEX IF NOT EXISTS idx_modelperf_model_task ON model_performance(model, task_type);
CREATE INDEX IF NOT EXISTS idx_modelperf_model_window ON model_performance(model, time_window);
CREATE INDEX IF NOT EXISTS idx_modelperf_quality_rank ON model_performance(task_type, time_window, quality_rank);
CREATE INDEX IF NOT EXISTS idx_modelperf_computed ON model_performance(computed_at);

CREATE TABLE IF NOT EXISTS parameter_tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    optimal_params TEXT NOT NULL DEFAULT '{}',
    tuning_method TEXT NOT NULL DEFAULT 'empirical',
    sample_count INTEGER NOT NULL DEFAULT 0, search_iterations INTEGER DEFAULT 0,
    avg_quality REAL NOT NULL DEFAULT 0.0, avg_cost_usd REAL NOT NULL DEFAULT 0.0,
    avg_duration_ms REAL NOT NULL DEFAULT 0.0, success_rate REAL NOT NULL DEFAULT 0.0,
    quality_vs_baseline REAL DEFAULT 0.0, cost_vs_baseline REAL DEFAULT 0.0,
    duration_vs_baseline REAL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 0.0,
    sensitivity TEXT DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1, previous_params TEXT DEFAULT '{}',
    UNIQUE(model, task_type)
);
CREATE INDEX IF NOT EXISTS idx_paramtune_model ON parameter_tuning(model);
CREATE INDEX IF NOT EXISTS idx_paramtune_task ON parameter_tuning(task_type);
CREATE INDEX IF NOT EXISTS idx_paramtune_model_task ON parameter_tuning(model, task_type);
CREATE INDEX IF NOT EXISTS idx_paramtune_confidence ON parameter_tuning(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_paramtune_updated ON parameter_tuning(updated_at);

CREATE TABLE IF NOT EXISTS quality_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    execution_id TEXT NOT NULL, workflow TEXT, task_type TEXT,
    rating_source TEXT NOT NULL, rater_model TEXT,
    overall_score REAL NOT NULL,
    accuracy_score REAL, completeness_score REAL, clarity_score REAL,
    actionability_score REAL, relevance_score REAL,
    thumbs_up INTEGER, user_comment TEXT, user_correction TEXT,
    tests_passed INTEGER, tests_total INTEGER, lint_errors INTEGER,
    build_success INTEGER, ci_pipeline_url TEXT,
    compared_to TEXT, relative_score REAL,
    rating_context TEXT DEFAULT '{}', superseded_by INTEGER,
    FOREIGN KEY (execution_id) REFERENCES execution_log(execution_id)
);
CREATE INDEX IF NOT EXISTS idx_ratings_execution ON quality_ratings(execution_id);
CREATE INDEX IF NOT EXISTS idx_ratings_source ON quality_ratings(rating_source);
CREATE INDEX IF NOT EXISTS idx_ratings_workflow ON quality_ratings(workflow);
CREATE INDEX IF NOT EXISTS idx_ratings_task_type ON quality_ratings(task_type);
CREATE INDEX IF NOT EXISTS idx_ratings_timestamp ON quality_ratings(timestamp);
CREATE INDEX IF NOT EXISTS idx_ratings_overall ON quality_ratings(overall_score);
CREATE INDEX IF NOT EXISTS idx_ratings_thumbs ON quality_ratings(thumbs_up);
CREATE INDEX IF NOT EXISTS idx_ratings_workflow_task ON quality_ratings(workflow, task_type);
CREATE INDEX IF NOT EXISTS idx_ratings_source_task ON quality_ratings(rating_source, task_type);
`;

// Minimal inline fallback (if no SQL files are available at all)
const _INLINE_SCHEMA = `
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -2000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    run_id TEXT, execution_id TEXT UNIQUE,
    model TEXT NOT NULL, model_role TEXT NOT NULL DEFAULT 'worker',
    workflow TEXT, task_type TEXT, task_description TEXT, phase TEXT, label TEXT,
    worker_models TEXT DEFAULT '[]', arbiter_model TEXT,
    model_count INTEGER DEFAULT 1, strategy TEXT,
    parameters TEXT DEFAULT '{}',
    quality_score REAL, confidence REAL, consensus_score REAL, diversity_score REAL,
    was_selected INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    total_input_tokens INTEGER DEFAULT 0, total_output_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0, per_model_costs TEXT DEFAULT '{}',
    duration_ms INTEGER DEFAULT 0, per_model_durations TEXT DEFAULT '{}',
    outcome TEXT DEFAULT 'unknown', outcome_notes TEXT, error TEXT,
    selected_model TEXT, session_id TEXT, parent_execution_id TEXT,
    request_hash TEXT, response_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_model ON execution_log(model);
CREATE INDEX IF NOT EXISTS idx_exec_workflow ON execution_log(workflow);
CREATE INDEX IF NOT EXISTS idx_exec_task_type ON execution_log(task_type);
CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_exec_execution_id ON execution_log(execution_id);

CREATE TABLE IF NOT EXISTS model_tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    optimal_params TEXT NOT NULL DEFAULT '{}',
    avg_quality REAL DEFAULT 0.0, avg_confidence REAL DEFAULT 0.0,
    avg_cost_usd REAL DEFAULT 0.0, avg_duration_ms REAL DEFAULT 0.0,
    sample_count INTEGER DEFAULT 0, success_rate REAL DEFAULT 0.0,
    selection_rate REAL DEFAULT 0.0,
    quality_trend TEXT DEFAULT '[]', cost_trend TEXT DEFAULT '[]',
    UNIQUE(model, task_type)
);

CREATE TABLE IF NOT EXISTS prompt_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    pattern_template TEXT, instructions TEXT,
    avg_quality REAL DEFAULT 0.0, avg_confidence REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0, success_rate REAL DEFAULT 0.0,
    vs_baseline_quality REAL DEFAULT 0.0,
    UNIQUE(model, task_type, pattern_name)
);

CREATE TABLE IF NOT EXISTS model_combinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    task_type TEXT NOT NULL,
    worker_models TEXT NOT NULL, arbiter_model TEXT,
    avg_consensus REAL DEFAULT 0.0, avg_quality REAL DEFAULT 0.0,
    avg_cost_usd REAL DEFAULT 0.0, avg_duration_ms REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    synergy_score REAL DEFAULT 0.0, diversity_score REAL DEFAULT 0.0,
    UNIQUE(task_type, worker_models, arbiter_model)
);

CREATE TABLE IF NOT EXISTS model_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'worker',
    task_type TEXT NOT NULL, time_window TEXT NOT NULL,
    window_start TEXT NOT NULL, window_end TEXT NOT NULL,
    avg_quality REAL NOT NULL DEFAULT 0.0,
    min_quality REAL, max_quality REAL, stddev_quality REAL, median_quality REAL,
    avg_confidence REAL NOT NULL DEFAULT 0.0, calibration_error REAL,
    selection_rate REAL NOT NULL DEFAULT 0.0,
    avg_consensus REAL DEFAULT 0.0, win_rate REAL DEFAULT 0.0,
    avg_cost_usd REAL NOT NULL DEFAULT 0.0, total_cost_usd REAL NOT NULL DEFAULT 0.0,
    cost_per_quality REAL,
    avg_duration_ms REAL NOT NULL DEFAULT 0.0,
    p50_duration_ms REAL, p95_duration_ms REAL, p99_duration_ms REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0, failure_count INTEGER NOT NULL DEFAULT 0,
    success_rate REAL NOT NULL DEFAULT 0.0,
    quality_trend TEXT DEFAULT '[]', cost_trend TEXT DEFAULT '[]',
    duration_trend TEXT DEFAULT '[]', selection_trend TEXT DEFAULT '[]',
    quality_rank INTEGER, efficiency_rank INTEGER, speed_rank INTEGER,
    UNIQUE(model, role, task_type, time_window, window_start)
);

CREATE TABLE IF NOT EXISTS parameter_tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    optimal_params TEXT NOT NULL DEFAULT '{}',
    tuning_method TEXT NOT NULL DEFAULT 'empirical',
    sample_count INTEGER NOT NULL DEFAULT 0, search_iterations INTEGER DEFAULT 0,
    avg_quality REAL NOT NULL DEFAULT 0.0, avg_cost_usd REAL NOT NULL DEFAULT 0.0,
    avg_duration_ms REAL NOT NULL DEFAULT 0.0, success_rate REAL NOT NULL DEFAULT 0.0,
    quality_vs_baseline REAL DEFAULT 0.0, cost_vs_baseline REAL DEFAULT 0.0,
    duration_vs_baseline REAL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 0.0,
    sensitivity TEXT DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1, previous_params TEXT DEFAULT '{}',
    UNIQUE(model, task_type)
);

CREATE TABLE IF NOT EXISTS quality_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    execution_id TEXT NOT NULL, workflow TEXT, task_type TEXT,
    rating_source TEXT NOT NULL, rater_model TEXT,
    overall_score REAL NOT NULL,
    accuracy_score REAL, completeness_score REAL, clarity_score REAL,
    actionability_score REAL, relevance_score REAL,
    thumbs_up INTEGER, user_comment TEXT, user_correction TEXT,
    tests_passed INTEGER, tests_total INTEGER, lint_errors INTEGER,
    build_success INTEGER, ci_pipeline_url TEXT,
    compared_to TEXT, relative_score REAL,
    rating_context TEXT DEFAULT '{}', superseded_by INTEGER,
    FOREIGN KEY (execution_id) REFERENCES execution_log(execution_id)
);

CREATE TABLE IF NOT EXISTS learning_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT OR IGNORE INTO learning_metadata (key, value) VALUES
    ('schema_version', '2'),
    ('created_at', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('last_tuning_recompute', ''),
    ('last_prompt_recompute', ''),
    ('last_combo_recompute', ''),
    ('last_model_performance_recompute', ''),
    ('last_parameter_tuning_recompute', ''),
    ('total_executions_logged', '0'),
    ('total_ratings_recorded', '0');
`;

// ============================================================================
// PROCESS CLEANUP
// ============================================================================

process.on('exit', close);

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  getDb,
  query,
  queryOne,
  exec,
  transaction,
  logOrchestration,
  upsertModelPerformance,
  upsertParameterTuning,
  insertRating,
  getBestModel,
  getModelPerformance,
  getAllModelPerformance,
  getOptimalParams,
  getQualityRatings,
  getQualityTrend,
  detectDrift,
  getExecutionsByWorkflow,
  getExecution,
  getRecentExecutions,
  getDistinctModels,
  getDistinctTaskTypes,
  getMetadata,
  setMetadata,
  close,
  isAvailable,
  getDbPath,
  getSchemaVersion,
};
