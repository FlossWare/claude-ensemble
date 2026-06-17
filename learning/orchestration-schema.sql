-- Orchestration Learning Database Schema
-- Path: ~/.claude/learning/orchestration.db
--
-- Purpose: Track workflow executions, model performance, parameter tuning,
-- and quality ratings to enable data-driven orchestration decisions.
--
-- Design principles:
--   - WAL journal mode for safe concurrent reads/writes
--   - All timestamps stored as ISO-8601 TEXT (SQLite has no native datetime)
--   - JSON columns stored as TEXT (use SQLite json_* functions to query)
--   - Foreign keys enforced for referential integrity
--   - Indexes optimized for the learning queries below

-- ============================================================================
-- PRAGMA configuration (apply at connection time)
-- ============================================================================
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -2000;
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: execution_log
-- ============================================================================
-- Every workflow execution gets one row. This is the primary fact table.
-- Records what was run, which models participated, parameters used,
-- quality achieved, cost incurred, and wall-clock time.

CREATE TABLE IF NOT EXISTS execution_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id      TEXT    NOT NULL UNIQUE,       -- UUID for cross-reference
    timestamp         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- What task was executed
    workflow          TEXT    NOT NULL,               -- e.g. 'code-review', 'ai-consensus-debate'
    task_type         TEXT    NOT NULL,               -- e.g. 'security', 'refactoring', 'test_plan'
    task_description  TEXT,                           -- freeform description of what was done
    phase             TEXT,                           -- e.g. 'Proposal', 'Rebuttal', 'Judgment'

    -- Which models participated
    worker_models     TEXT    NOT NULL DEFAULT '[]',  -- JSON array: ["opus","sonnet","haiku","gpt-4o","gemini","fable"]
    arbiter_model     TEXT,                           -- model that arbitrated (null if solo/no arbiter)
    model_count       INTEGER NOT NULL DEFAULT 1,    -- number of models used

    -- Parameters used for this execution
    parameters        TEXT    NOT NULL DEFAULT '{}',  -- JSON: temperature, max_tokens, strategy, etc.
    strategy          TEXT,                           -- e.g. 'QualityFirst', 'Balanced', 'CostOptimized'

    -- Quality metrics
    quality_score     REAL,                           -- 0.0-1.0: overall output quality
    consensus_score   REAL,                           -- 0.0-1.0: inter-model agreement
    diversity_score   REAL,                           -- 0.0-1.0: how different were model outputs
    confidence        REAL,                           -- 0.0-1.0: arbiter/system confidence in result

    -- Cost tracking
    total_input_tokens   INTEGER NOT NULL DEFAULT 0,
    total_output_tokens  INTEGER NOT NULL DEFAULT 0,
    total_cost_usd       REAL    NOT NULL DEFAULT 0.0,
    per_model_costs      TEXT    DEFAULT '{}',        -- JSON: {"opus": 0.12, "sonnet": 0.03, ...}

    -- Timing
    duration_ms       INTEGER NOT NULL DEFAULT 0,     -- total wall-clock time
    per_model_durations TEXT   DEFAULT '{}',          -- JSON: {"opus": 4500, "sonnet": 2100, ...}

    -- Outcome
    outcome           TEXT    NOT NULL DEFAULT 'unknown',  -- 'success', 'failed', 'partial', 'timeout'
    outcome_notes     TEXT,                           -- freeform notes on outcome
    error             TEXT,                           -- error message if execution failed
    selected_model    TEXT,                           -- which worker's output was selected by arbiter

    -- Provenance
    session_id        TEXT,                           -- Claude Code session identifier
    parent_execution_id TEXT,                         -- if this was a sub-workflow, link to parent
    request_hash      TEXT,                           -- SHA-256 of prompt for deduplication
    response_hash     TEXT                            -- SHA-256 of final output
);

-- Indexes for common learning queries
CREATE INDEX IF NOT EXISTS idx_execlog_timestamp       ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_execlog_workflow         ON execution_log(workflow);
CREATE INDEX IF NOT EXISTS idx_execlog_task_type        ON execution_log(task_type);
CREATE INDEX IF NOT EXISTS idx_execlog_strategy         ON execution_log(strategy);
CREATE INDEX IF NOT EXISTS idx_execlog_outcome          ON execution_log(outcome);
CREATE INDEX IF NOT EXISTS idx_execlog_arbiter          ON execution_log(arbiter_model);
CREATE INDEX IF NOT EXISTS idx_execlog_quality          ON execution_log(quality_score);
CREATE INDEX IF NOT EXISTS idx_execlog_workflow_task    ON execution_log(workflow, task_type);
CREATE INDEX IF NOT EXISTS idx_execlog_session          ON execution_log(session_id);
CREATE INDEX IF NOT EXISTS idx_execlog_parent           ON execution_log(parent_execution_id);

-- ============================================================================
-- TABLE: model_performance
-- ============================================================================
-- Per-model metrics aggregated over time windows. Recomputed periodically
-- by the background learner. Supports queries like:
--   "Which model is best for security reviews?"
--   "Is opus quality trending down this week?"
--   "What is the cost/quality ratio for each model on refactoring tasks?"

CREATE TABLE IF NOT EXISTS model_performance (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Identity
    model             TEXT    NOT NULL,               -- e.g. 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'
    role              TEXT    NOT NULL DEFAULT 'worker',  -- 'worker', 'arbiter', 'solo'
    task_type         TEXT    NOT NULL,               -- e.g. 'security', 'refactoring', 'code_review'
    time_window       TEXT    NOT NULL,               -- 'day', 'week', 'month', 'all_time'
    window_start      TEXT    NOT NULL,               -- ISO-8601 start of this window
    window_end        TEXT    NOT NULL,               -- ISO-8601 end of this window

    -- Quality metrics
    avg_quality       REAL    NOT NULL DEFAULT 0.0,
    min_quality       REAL,
    max_quality       REAL,
    stddev_quality    REAL,
    median_quality    REAL,

    -- Confidence metrics
    avg_confidence    REAL    NOT NULL DEFAULT 0.0,
    calibration_error REAL,                           -- |avg_confidence - actual_accuracy|

    -- Selection and consensus
    selection_rate    REAL    NOT NULL DEFAULT 0.0,   -- fraction of times arbiter chose this model
    avg_consensus     REAL    DEFAULT 0.0,            -- average agreement with other workers
    win_rate          REAL    DEFAULT 0.0,            -- fraction of times this model's output was best

    -- Cost metrics
    avg_cost_usd      REAL    NOT NULL DEFAULT 0.0,
    total_cost_usd    REAL    NOT NULL DEFAULT 0.0,
    cost_per_quality  REAL,                           -- cost_usd / quality_score (efficiency)

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

    -- Trend data (JSON arrays of recent values for sparklines/charts)
    quality_trend     TEXT    DEFAULT '[]',           -- last 50 quality scores
    cost_trend        TEXT    DEFAULT '[]',           -- last 50 costs
    duration_trend    TEXT    DEFAULT '[]',           -- last 50 durations
    selection_trend   TEXT    DEFAULT '[]',           -- last 50 selection outcomes (0/1)

    -- Comparative ranking within this task_type + time_window
    quality_rank      INTEGER,                        -- 1 = best quality among all models
    efficiency_rank   INTEGER,                        -- 1 = best cost/quality ratio
    speed_rank        INTEGER,                        -- 1 = fastest

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
-- TABLE: parameter_tuning
-- ============================================================================
-- Optimal parameters discovered per model and task type. Updated by the
-- background learner after analyzing execution_log outcomes. Supports queries:
--   "What temperature works best for opus on code reviews?"
--   "Should I use 6 models or 3 for refactoring tasks?"
--   "What is the optimal max_tokens for haiku on test generation?"

CREATE TABLE IF NOT EXISTS parameter_tuning (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- What this tuning applies to
    model             TEXT    NOT NULL,               -- model name or '*' for all-model defaults
    task_type         TEXT    NOT NULL,               -- task type or '*' for all-task defaults

    -- Optimal parameters (JSON blob)
    optimal_params    TEXT    NOT NULL DEFAULT '{}',
    -- Example: {
    --   "temperature": 0.3,
    --   "max_tokens": 4000,
    --   "top_p": 0.95,
    --   "model_count": 6,
    --   "strategy": "QualityFirst",
    --   "arbiter_model": "fable",
    --   "worker_models": ["opus","sonnet","haiku","gpt-4o","gemini","fable"]
    -- }

    -- How these parameters were determined
    tuning_method     TEXT    NOT NULL DEFAULT 'empirical',  -- 'empirical', 'bayesian', 'grid_search', 'manual'
    sample_count      INTEGER NOT NULL DEFAULT 0,     -- number of executions analyzed
    search_iterations INTEGER DEFAULT 0,              -- tuning iterations performed

    -- Performance with these parameters
    avg_quality       REAL    NOT NULL DEFAULT 0.0,
    avg_cost_usd      REAL    NOT NULL DEFAULT 0.0,
    avg_duration_ms   REAL    NOT NULL DEFAULT 0.0,
    success_rate      REAL    NOT NULL DEFAULT 0.0,

    -- Comparison to baseline (default parameters)
    quality_vs_baseline   REAL DEFAULT 0.0,           -- improvement over defaults (can be negative)
    cost_vs_baseline      REAL DEFAULT 0.0,           -- cost change vs defaults (negative = cheaper)
    duration_vs_baseline  REAL DEFAULT 0.0,           -- duration change vs defaults

    -- Confidence in this tuning
    confidence        REAL    NOT NULL DEFAULT 0.0,   -- 0.0-1.0: how confident are we in these params
    -- Low sample_count or high variance = low confidence

    -- Parameter sensitivity analysis (JSON)
    sensitivity       TEXT    DEFAULT '{}',
    -- Example: {
    --   "temperature": {"range": [0.1, 0.5], "impact": "high", "optimal": 0.3},
    --   "model_count": {"range": [3, 6], "impact": "medium", "optimal": 6}
    -- }

    -- Version tracking for parameter evolution
    version           INTEGER NOT NULL DEFAULT 1,
    previous_params   TEXT    DEFAULT '{}',           -- JSON: what params were before this update

    UNIQUE(model, task_type)
);

CREATE INDEX IF NOT EXISTS idx_paramtune_model         ON parameter_tuning(model);
CREATE INDEX IF NOT EXISTS idx_paramtune_task           ON parameter_tuning(task_type);
CREATE INDEX IF NOT EXISTS idx_paramtune_model_task     ON parameter_tuning(model, task_type);
CREATE INDEX IF NOT EXISTS idx_paramtune_confidence     ON parameter_tuning(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_paramtune_updated        ON parameter_tuning(updated_at);

-- ============================================================================
-- TABLE: quality_ratings
-- ============================================================================
-- User feedback and automated quality scores for execution outputs.
-- Links back to execution_log via execution_id. Supports queries:
--   "Are my quality scores drifting down over time?"
--   "Which workflows get the best user ratings?"
--   "Does automated quality correlate with user satisfaction?"

CREATE TABLE IF NOT EXISTS quality_ratings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Link to execution
    execution_id      TEXT    NOT NULL,               -- references execution_log.execution_id
    workflow          TEXT,                            -- denormalized for faster queries
    task_type         TEXT,                            -- denormalized for faster queries

    -- Rating source
    rating_source     TEXT    NOT NULL,               -- 'user', 'automated', 'arbiter', 'consensus', 'ci_outcome'
    rater_model       TEXT,                           -- if automated, which model rated it

    -- Scores (all 0.0-1.0 scale)
    overall_score     REAL    NOT NULL,               -- overall quality rating
    accuracy_score    REAL,                           -- correctness of the output
    completeness_score REAL,                          -- did it cover everything needed
    clarity_score     REAL,                           -- readability and understandability
    actionability_score REAL,                         -- can the user act on it directly
    relevance_score   REAL,                           -- was it relevant to the actual need

    -- User feedback (for rating_source='user')
    thumbs_up         INTEGER,                        -- 1 = positive, 0 = negative, NULL = no feedback
    user_comment      TEXT,                           -- freeform user feedback
    user_correction   TEXT,                           -- what the user changed/corrected

    -- Automated quality signals (for rating_source='automated' or 'ci_outcome')
    tests_passed      INTEGER,                        -- if code change, did tests pass
    tests_total       INTEGER,                        -- total tests run
    lint_errors       INTEGER,                        -- lint/style issues introduced
    build_success     INTEGER,                        -- 1 = build passed, 0 = failed
    ci_pipeline_url   TEXT,                           -- link to CI pipeline for verification

    -- Comparative quality (when multiple executions tried same task)
    compared_to       TEXT,                           -- execution_id of the baseline
    relative_score    REAL,                           -- how much better/worse than baseline (-1.0 to 1.0)

    -- Metadata
    rating_context    TEXT    DEFAULT '{}',           -- JSON: additional context about the rating
    superseded_by     INTEGER,                        -- if user re-rated, points to newer rating id

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
-- Schema version, recompute timestamps, and system configuration.

CREATE TABLE IF NOT EXISTS learning_metadata (
    key               TEXT    PRIMARY KEY,
    value             TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed metadata
INSERT OR IGNORE INTO learning_metadata (key, value) VALUES
    ('schema_version', '1'),
    ('created_at', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('last_model_performance_recompute', ''),
    ('last_parameter_tuning_recompute', ''),
    ('total_executions_logged', '0'),
    ('total_ratings_recorded', '0');

-- ============================================================================
-- EXAMPLE LEARNING QUERIES
-- ============================================================================
-- These are the queries the background learner and orchestration engine use.
-- They are documented here for reference; they are NOT executed by this script.

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

-- Q5: User satisfaction correlation with automated scores
-- SELECT
--     qr.rating_source,
--     AVG(qr.overall_score) as avg_rating,
--     AVG(el.quality_score) as avg_auto_quality,
--     COUNT(*) as n
-- FROM quality_ratings qr
-- JOIN execution_log el ON qr.execution_id = el.execution_id
-- WHERE qr.rating_source = 'user'
-- GROUP BY qr.workflow;

-- Q6: Which worker models get selected most by arbiters
-- SELECT model, task_type, selection_rate, win_rate, sample_count
-- FROM model_performance
-- WHERE role = 'worker' AND time_window = 'all_time'
-- ORDER BY selection_rate DESC;

-- Q7: Parameter sensitivity -- which parameters matter most
-- SELECT model, task_type, sensitivity, confidence
-- FROM parameter_tuning
-- WHERE confidence > 0.5
-- ORDER BY confidence DESC;

-- Q8: Execution history for a specific workflow
-- SELECT timestamp, worker_models, arbiter_model, quality_score,
--        consensus_score, total_cost_usd, duration_ms, outcome
-- FROM execution_log
-- WHERE workflow = ?
-- ORDER BY timestamp DESC LIMIT 50;

-- Q9: Model combination effectiveness
-- SELECT worker_models, arbiter_model, AVG(quality_score) as avg_q,
--        AVG(consensus_score) as avg_c, AVG(total_cost_usd) as avg_cost,
--        COUNT(*) as n
-- FROM execution_log
-- WHERE task_type = ? AND outcome = 'success'
-- GROUP BY worker_models, arbiter_model
-- ORDER BY avg_q DESC;

-- Q10: Drift detection -- quality degradation over recent windows
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
