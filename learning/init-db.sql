-- ============================================================================
-- Unified Learning Database Schema
-- Path: ~/.claude/learning/db/learning.db
--
-- Purpose: Track workflow executions, model performance, parameter tuning,
-- quality ratings, and metadata to enable data-driven orchestration decisions.
--
-- This schema merges and supersedes:
--   - init-learning-db.sql (v1: execution_log, model_tuning, prompt_patterns,
--                           model_combinations, learning_metadata)
--   - orchestration-schema.sql (v2: execution_log, model_performance,
--                               parameter_tuning, quality_ratings, learning_metadata)
--
-- Backward compatibility:
--   - v1 tables (model_tuning, prompt_patterns, model_combinations) are preserved
--     so existing code (learning-logger.js) continues to work unmodified.
--   - v2 tables (model_performance, parameter_tuning, quality_ratings) are added
--     alongside, providing richer analytics for the new orchestration layer.
--
-- Design principles:
--   - WAL journal mode for safe concurrent reads/writes
--   - All timestamps stored as ISO-8601 TEXT (SQLite has no native datetime)
--   - JSON columns stored as TEXT (use SQLite json_* functions to query)
--   - Foreign keys enforced for referential integrity
--   - Indexes optimized for the learning queries documented below
-- ============================================================================

-- ============================================================================
-- PRAGMA configuration (apply at connection time)
-- ============================================================================
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -2000;
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: execution_log (v1 - preserved for backward compatibility)
-- ============================================================================
-- Every agent() call or workflow execution gets one row.
-- This is the hot write path -- must be <10ms per insert.
-- Used by: learning-logger.js

CREATE TABLE IF NOT EXISTS execution_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Correlation
    run_id          TEXT,
    execution_id    TEXT    UNIQUE,

    -- What model was used
    model           TEXT    NOT NULL,
    model_role      TEXT    NOT NULL DEFAULT 'worker',

    -- What was being done
    workflow        TEXT,
    task_type       TEXT,
    task_description TEXT,
    phase           TEXT,
    label           TEXT,

    -- Multi-model context (v2 additions, nullable for v1 compat)
    worker_models   TEXT    DEFAULT '[]',
    arbiter_model   TEXT,
    model_count     INTEGER DEFAULT 1,
    strategy        TEXT,

    -- Parameters used
    parameters      TEXT    DEFAULT '{}',

    -- Outcome metrics
    quality_score   REAL,
    confidence      REAL,
    consensus_score REAL,
    diversity_score REAL,
    was_selected    INTEGER DEFAULT 0,

    -- Cost tracking
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL    DEFAULT 0.0,
    total_input_tokens   INTEGER DEFAULT 0,
    total_output_tokens  INTEGER DEFAULT 0,
    total_cost_usd       REAL    DEFAULT 0.0,
    per_model_costs      TEXT    DEFAULT '{}',

    -- Timing
    duration_ms     INTEGER DEFAULT 0,
    per_model_durations TEXT DEFAULT '{}',

    -- Outcome
    outcome         TEXT    DEFAULT 'unknown',
    outcome_notes   TEXT,
    error           TEXT,
    selected_model  TEXT,

    -- Provenance
    session_id      TEXT,
    parent_execution_id TEXT,
    request_hash    TEXT,
    response_hash   TEXT
);

-- v1 indexes (preserved)
CREATE INDEX IF NOT EXISTS idx_exec_model          ON execution_log(model);
CREATE INDEX IF NOT EXISTS idx_exec_workflow        ON execution_log(workflow);
CREATE INDEX IF NOT EXISTS idx_exec_task_type       ON execution_log(task_type);
CREATE INDEX IF NOT EXISTS idx_exec_model_task      ON execution_log(model, task_type);
CREATE INDEX IF NOT EXISTS idx_exec_timestamp       ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_exec_model_workflow  ON execution_log(model, workflow);
CREATE INDEX IF NOT EXISTS idx_exec_outcome         ON execution_log(outcome);
CREATE INDEX IF NOT EXISTS idx_exec_run_id          ON execution_log(run_id);

-- v2 indexes (new)
CREATE INDEX IF NOT EXISTS idx_exec_execution_id    ON execution_log(execution_id);
CREATE INDEX IF NOT EXISTS idx_exec_strategy        ON execution_log(strategy);
CREATE INDEX IF NOT EXISTS idx_exec_quality         ON execution_log(quality_score);
CREATE INDEX IF NOT EXISTS idx_exec_workflow_task   ON execution_log(workflow, task_type);
CREATE INDEX IF NOT EXISTS idx_exec_session         ON execution_log(session_id);
CREATE INDEX IF NOT EXISTS idx_exec_parent          ON execution_log(parent_execution_id);

-- ============================================================================
-- TABLE: model_tuning (v1 - preserved for backward compat with learning-logger.js)
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_tuning (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model           TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,
    optimal_params  TEXT    NOT NULL DEFAULT '{}',
    avg_quality     REAL    DEFAULT 0.0,
    avg_confidence  REAL    DEFAULT 0.0,
    avg_cost_usd    REAL    DEFAULT 0.0,
    avg_duration_ms REAL    DEFAULT 0.0,
    sample_count    INTEGER DEFAULT 0,
    success_rate    REAL    DEFAULT 0.0,
    selection_rate  REAL    DEFAULT 0.0,
    quality_trend   TEXT    DEFAULT '[]',
    cost_trend      TEXT    DEFAULT '[]',
    UNIQUE(model, task_type)
);

CREATE INDEX IF NOT EXISTS idx_tuning_model      ON model_tuning(model);
CREATE INDEX IF NOT EXISTS idx_tuning_task        ON model_tuning(task_type);
CREATE INDEX IF NOT EXISTS idx_tuning_model_task  ON model_tuning(model, task_type);

-- ============================================================================
-- TABLE: prompt_patterns (v1 - preserved)
-- ============================================================================
CREATE TABLE IF NOT EXISTS prompt_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model           TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,
    pattern_name    TEXT    NOT NULL,
    pattern_template TEXT,
    instructions    TEXT,
    avg_quality     REAL    DEFAULT 0.0,
    avg_confidence  REAL    DEFAULT 0.0,
    usage_count     INTEGER DEFAULT 0,
    success_rate    REAL    DEFAULT 0.0,
    vs_baseline_quality REAL DEFAULT 0.0,
    UNIQUE(model, task_type, pattern_name)
);

CREATE INDEX IF NOT EXISTS idx_prompt_model_task ON prompt_patterns(model, task_type);

-- ============================================================================
-- TABLE: model_combinations (v1 - preserved)
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_combinations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    task_type       TEXT    NOT NULL,
    worker_models   TEXT    NOT NULL,
    arbiter_model   TEXT,
    avg_consensus   REAL    DEFAULT 0.0,
    avg_quality     REAL    DEFAULT 0.0,
    avg_cost_usd    REAL    DEFAULT 0.0,
    avg_duration_ms REAL    DEFAULT 0.0,
    usage_count     INTEGER DEFAULT 0,
    synergy_score   REAL    DEFAULT 0.0,
    diversity_score REAL    DEFAULT 0.0,
    UNIQUE(task_type, worker_models, arbiter_model)
);

CREATE INDEX IF NOT EXISTS idx_combo_task     ON model_combinations(task_type);
CREATE INDEX IF NOT EXISTS idx_combo_synergy  ON model_combinations(synergy_score DESC);

-- ============================================================================
-- TABLE: model_performance (v2 - new aggregated analytics)
-- ============================================================================
-- Per-model metrics aggregated over time windows. Recomputed periodically.
-- Supports queries like: "Which model is best for security reviews?"

CREATE TABLE IF NOT EXISTS model_performance (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Identity
    model             TEXT    NOT NULL,
    role              TEXT    NOT NULL DEFAULT 'worker',
    task_type         TEXT    NOT NULL,
    time_window       TEXT    NOT NULL,
    window_start      TEXT    NOT NULL,
    window_end        TEXT    NOT NULL,

    -- Quality metrics
    avg_quality       REAL    NOT NULL DEFAULT 0.0,
    min_quality       REAL,
    max_quality       REAL,
    stddev_quality    REAL,
    median_quality    REAL,

    -- Confidence metrics
    avg_confidence    REAL    NOT NULL DEFAULT 0.0,
    calibration_error REAL,

    -- Selection and consensus
    selection_rate    REAL    NOT NULL DEFAULT 0.0,
    avg_consensus     REAL    DEFAULT 0.0,
    win_rate          REAL    DEFAULT 0.0,

    -- Cost metrics
    avg_cost_usd      REAL    NOT NULL DEFAULT 0.0,
    total_cost_usd    REAL    NOT NULL DEFAULT 0.0,
    cost_per_quality  REAL,

    -- Timing metrics
    avg_duration_ms   REAL    NOT NULL DEFAULT 0.0,
    p50_duration_ms   REAL,
    p95_duration_ms   REAL,
    p99_duration_ms   REAL,

    -- Volume
    sample_count      INTEGER NOT NULL DEFAULT 0,
    success_count     INTEGER NOT NULL DEFAULT 0,
    failure_count     INTEGER NOT NULL DEFAULT 0,
    success_rate      REAL    NOT NULL DEFAULT 0.0,

    -- Trend data (JSON arrays for sparklines)
    quality_trend     TEXT    DEFAULT '[]',
    cost_trend        TEXT    DEFAULT '[]',
    duration_trend    TEXT    DEFAULT '[]',
    selection_trend   TEXT    DEFAULT '[]',

    -- Comparative ranking within task_type + time_window
    quality_rank      INTEGER,
    efficiency_rank   INTEGER,
    speed_rank        INTEGER,

    UNIQUE(model, role, task_type, time_window, window_start)
);

CREATE INDEX IF NOT EXISTS idx_modelperf_model         ON model_performance(model);
CREATE INDEX IF NOT EXISTS idx_modelperf_task           ON model_performance(task_type);
CREATE INDEX IF NOT EXISTS idx_modelperf_window         ON model_performance(time_window);
CREATE INDEX IF NOT EXISTS idx_modelperf_model_task     ON model_performance(model, task_type);
CREATE INDEX IF NOT EXISTS idx_modelperf_model_window   ON model_performance(model, time_window);
CREATE INDEX IF NOT EXISTS idx_modelperf_quality_rank   ON model_performance(task_type, time_window, quality_rank);
CREATE INDEX IF NOT EXISTS idx_modelperf_computed       ON model_performance(computed_at);

-- ============================================================================
-- TABLE: parameter_tuning (v2 - richer tuning with sensitivity analysis)
-- ============================================================================
-- Optimal parameters discovered per model/task, with sensitivity analysis,
-- baseline comparisons, confidence scores, and version tracking.

CREATE TABLE IF NOT EXISTS parameter_tuning (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- What this tuning applies to
    model             TEXT    NOT NULL,
    task_type         TEXT    NOT NULL,

    -- Optimal parameters (JSON)
    optimal_params    TEXT    NOT NULL DEFAULT '{}',

    -- How these parameters were determined
    tuning_method     TEXT    NOT NULL DEFAULT 'empirical',
    sample_count      INTEGER NOT NULL DEFAULT 0,
    search_iterations INTEGER DEFAULT 0,

    -- Performance with these parameters
    avg_quality       REAL    NOT NULL DEFAULT 0.0,
    avg_cost_usd      REAL    NOT NULL DEFAULT 0.0,
    avg_duration_ms   REAL    NOT NULL DEFAULT 0.0,
    success_rate      REAL    NOT NULL DEFAULT 0.0,

    -- Comparison to baseline
    quality_vs_baseline   REAL DEFAULT 0.0,
    cost_vs_baseline      REAL DEFAULT 0.0,
    duration_vs_baseline  REAL DEFAULT 0.0,

    -- Confidence in this tuning
    confidence        REAL    NOT NULL DEFAULT 0.0,

    -- Parameter sensitivity (JSON)
    sensitivity       TEXT    DEFAULT '{}',

    -- Version tracking
    version           INTEGER NOT NULL DEFAULT 1,
    previous_params   TEXT    DEFAULT '{}',

    UNIQUE(model, task_type)
);

CREATE INDEX IF NOT EXISTS idx_paramtune_model         ON parameter_tuning(model);
CREATE INDEX IF NOT EXISTS idx_paramtune_task           ON parameter_tuning(task_type);
CREATE INDEX IF NOT EXISTS idx_paramtune_model_task     ON parameter_tuning(model, task_type);
CREATE INDEX IF NOT EXISTS idx_paramtune_confidence     ON parameter_tuning(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_paramtune_updated        ON parameter_tuning(updated_at);

-- ============================================================================
-- TABLE: quality_ratings (v2 - multi-source quality feedback)
-- ============================================================================
-- User feedback and automated quality scores for execution outputs.

CREATE TABLE IF NOT EXISTS quality_ratings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Link to execution
    execution_id      TEXT    NOT NULL,
    workflow          TEXT,
    task_type         TEXT,

    -- Rating source
    rating_source     TEXT    NOT NULL,
    rater_model       TEXT,

    -- Scores (all 0.0-1.0)
    overall_score     REAL    NOT NULL,
    accuracy_score    REAL,
    completeness_score REAL,
    clarity_score     REAL,
    actionability_score REAL,
    relevance_score   REAL,

    -- User feedback
    thumbs_up         INTEGER,
    user_comment      TEXT,
    user_correction   TEXT,

    -- Automated quality signals
    tests_passed      INTEGER,
    tests_total       INTEGER,
    lint_errors       INTEGER,
    build_success     INTEGER,
    ci_pipeline_url   TEXT,

    -- Comparative quality
    compared_to       TEXT,
    relative_score    REAL,

    -- Metadata
    rating_context    TEXT    DEFAULT '{}',
    superseded_by     INTEGER,

    FOREIGN KEY (execution_id) REFERENCES execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_ratings_execution       ON quality_ratings(execution_id);
CREATE INDEX IF NOT EXISTS idx_ratings_source           ON quality_ratings(rating_source);
CREATE INDEX IF NOT EXISTS idx_ratings_workflow         ON quality_ratings(workflow);
CREATE INDEX IF NOT EXISTS idx_ratings_task_type        ON quality_ratings(task_type);
CREATE INDEX IF NOT EXISTS idx_ratings_timestamp        ON quality_ratings(timestamp);
CREATE INDEX IF NOT EXISTS idx_ratings_overall          ON quality_ratings(overall_score);
CREATE INDEX IF NOT EXISTS idx_ratings_thumbs           ON quality_ratings(thumbs_up);
CREATE INDEX IF NOT EXISTS idx_ratings_workflow_task    ON quality_ratings(workflow, task_type);
CREATE INDEX IF NOT EXISTS idx_ratings_source_task      ON quality_ratings(rating_source, task_type);

-- ============================================================================
-- TABLE: learning_metadata
-- ============================================================================
CREATE TABLE IF NOT EXISTS learning_metadata (
    key               TEXT    PRIMARY KEY,
    value             TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed metadata (v1 + v2 keys)
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

-- ============================================================================
-- MIGRATION: v1 -> v2
-- ============================================================================
-- If upgrading from v1, add new columns to execution_log.
-- These ALTER TABLE statements are safe: SQLite ignores them if columns exist.
-- Wrapped in a check so they only run if needed.

-- Note: SQLite does not support ADD COLUMN IF NOT EXISTS, so we rely on
-- CREATE TABLE IF NOT EXISTS above creating the full schema on fresh installs.
-- For existing v1 databases, the db.js helper runs migration logic.

-- Update schema version
INSERT OR REPLACE INTO learning_metadata (key, value) VALUES
    ('schema_version', '2');

-- ============================================================================
-- EXAMPLE LEARNING QUERIES (reference only, not executed)
-- ============================================================================

-- Q1: Best model for a given task type (by quality, cost-adjusted)
-- SELECT model, avg_quality, avg_cost_usd, cost_per_quality, quality_rank
-- FROM model_performance
-- WHERE task_type = ? AND time_window = 'week' AND role = 'worker'
-- ORDER BY quality_rank ASC;

-- Q2: Optimal parameters for a model/task combination
-- SELECT optimal_params, confidence, avg_quality, sample_count
-- FROM parameter_tuning
-- WHERE model = ? AND task_type = ?;

-- Q3: Quality trend for a model over time
-- SELECT window_start, avg_quality, sample_count
-- FROM model_performance
-- WHERE model = ? AND task_type = ? AND time_window = 'day'
-- ORDER BY window_start DESC LIMIT 30;

-- Q4: Cost vs quality tradeoff across models
-- SELECT model, avg_quality, avg_cost_usd, cost_per_quality
-- FROM model_performance
-- WHERE task_type = ? AND time_window = 'all_time' AND role = 'worker'
-- ORDER BY cost_per_quality ASC;

-- Q5: User satisfaction correlation
-- SELECT
--     qr.rating_source,
--     AVG(qr.overall_score) as avg_rating,
--     AVG(el.quality_score) as avg_auto_quality,
--     COUNT(*) as n
-- FROM quality_ratings qr
-- JOIN execution_log el ON qr.execution_id = el.execution_id
-- WHERE qr.rating_source = 'user'
-- GROUP BY qr.workflow;

-- Q6: Model combination effectiveness
-- SELECT worker_models, arbiter_model, AVG(quality_score) as avg_q,
--        AVG(consensus_score) as avg_c, AVG(total_cost_usd) as avg_cost,
--        COUNT(*) as n
-- FROM execution_log
-- WHERE task_type = ? AND outcome = 'success'
-- GROUP BY worker_models, arbiter_model
-- ORDER BY avg_q DESC;

-- Q7: Drift detection
-- SELECT m1.model, m1.task_type,
--        m1.avg_quality as current_quality,
--        m2.avg_quality as previous_quality,
--        (m1.avg_quality - m2.avg_quality) as quality_delta
-- FROM model_performance m1
-- JOIN model_performance m2
--   ON m1.model = m2.model AND m1.task_type = m2.task_type
--   AND m1.time_window = 'week' AND m2.time_window = 'week'
--   AND m1.window_start > m2.window_start
-- ORDER BY quality_delta ASC;
