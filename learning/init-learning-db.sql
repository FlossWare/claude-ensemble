-- Learning Database Schema
-- SQLite database for tracking AI model execution, tuning, prompt patterns, and model combinations.
-- Initialized by shared/learning-logger.js on first use.
--
-- Design principles:
--   - WAL journal mode for safe concurrent reads/writes
--   - Synchronous NORMAL for durability without blocking
--   - All timestamps stored as ISO-8601 text (SQLite has no native datetime)
--   - JSON columns stored as TEXT (SQLite has built-in json_* functions)
--   - Composite indexes optimized for the queries background-learner.js runs

-- ============================================================================
-- PRAGMA configuration (applied at connection time by learning-logger.js)
-- ============================================================================
-- PRAGMA journal_mode = WAL;
-- PRAGMA synchronous = NORMAL;
-- PRAGMA busy_timeout = 5000;
-- PRAGMA cache_size = -2000;  -- 2MB cache
-- PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: execution_log
-- ============================================================================
-- Every agent() call or workflow execution gets one row.
-- This is the hot write path -- must be <10ms per insert.

CREATE TABLE IF NOT EXISTS execution_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Correlation: groups all workers + arbiter from the same consensus run
    run_id          TEXT,                        -- UUID tying workers from one consensus run together

    -- What model was used
    model           TEXT    NOT NULL,           -- e.g. 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'
    model_role      TEXT    NOT NULL DEFAULT 'worker',  -- 'worker', 'arbiter', 'solo'

    -- What was being done
    workflow        TEXT,                        -- e.g. 'code-review', 'ai-consensus-debate'
    task_type       TEXT,                        -- e.g. 'security', 'refactoring', 'test_plan'
    phase           TEXT,                        -- e.g. 'Proposal', 'Rebuttal', 'Judgment'
    label           TEXT,                        -- freeform label from agent() call

    -- Parameters used
    parameters      TEXT    DEFAULT '{}',        -- JSON: temperature, max_tokens, schema, etc.

    -- Outcome metrics
    quality_score   REAL,                        -- 0.0-1.0: how good was the output
    confidence      REAL,                        -- 0.0-1.0: model's self-reported confidence
    consensus_score REAL,                        -- 0.0-1.0: agreement with other workers
    was_selected    INTEGER DEFAULT 0,           -- 1 if arbiter selected this worker's output

    -- Cost tracking
    input_tokens    INTEGER DEFAULT 0    CHECK(input_tokens >= 0),
    output_tokens   INTEGER DEFAULT 0    CHECK(output_tokens >= 0),
    cost_usd        REAL    DEFAULT 0.0  CHECK(cost_usd >= 0),

    -- Timing
    duration_ms     INTEGER DEFAULT 0    CHECK(duration_ms >= 0),

    -- Outcome (set later via update)
    outcome         TEXT    DEFAULT 'unknown',    -- 'success', 'failed', 'partial', 'unknown'
    outcome_notes   TEXT,

    -- Raw data (optional, for debugging)
    request_hash    TEXT,                         -- SHA-256 of the prompt (for dedup)
    response_hash   TEXT,                         -- SHA-256 of the response
    error           TEXT                          -- error message if call failed
);

-- Hot-path query indexes
CREATE INDEX IF NOT EXISTS idx_exec_model          ON execution_log(model);
CREATE INDEX IF NOT EXISTS idx_exec_workflow        ON execution_log(workflow);
CREATE INDEX IF NOT EXISTS idx_exec_task_type       ON execution_log(task_type);
CREATE INDEX IF NOT EXISTS idx_exec_model_task      ON execution_log(model, task_type);
CREATE INDEX IF NOT EXISTS idx_exec_timestamp       ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_exec_model_workflow  ON execution_log(model, workflow);
CREATE INDEX IF NOT EXISTS idx_exec_outcome         ON execution_log(outcome);
CREATE INDEX IF NOT EXISTS idx_exec_run_id          ON execution_log(run_id);

-- ============================================================================
-- TABLE: model_tuning
-- ============================================================================
-- Stores optimal parameters per model/task combination.
-- Recomputed by background-learner.js every 30 seconds.

CREATE TABLE IF NOT EXISTS model_tuning (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- What this tuning applies to
    model           TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,

    -- Optimal parameters (JSON)
    optimal_params  TEXT    NOT NULL DEFAULT '{}',
    -- Example: {"temperature": 0.3, "max_tokens": 2000, "top_p": 0.9}

    -- Performance summary
    avg_quality     REAL    DEFAULT 0.0  CHECK(avg_quality >= 0),
    avg_confidence  REAL    DEFAULT 0.0  CHECK(avg_confidence >= 0),
    avg_cost_usd    REAL    DEFAULT 0.0  CHECK(avg_cost_usd >= 0),
    avg_duration_ms REAL    DEFAULT 0.0  CHECK(avg_duration_ms >= 0),
    sample_count    INTEGER DEFAULT 0    CHECK(sample_count >= 0),
    success_rate    REAL    DEFAULT 0.0  CHECK(success_rate >= 0),
    selection_rate  REAL    DEFAULT 0.0  CHECK(selection_rate >= 0),

    -- Trend data
    quality_trend   TEXT    DEFAULT '[]',         -- JSON array of last 20 quality scores
    cost_trend      TEXT    DEFAULT '[]',         -- JSON array of last 20 costs

    UNIQUE(model, task_type)
);

CREATE INDEX IF NOT EXISTS idx_tuning_model      ON model_tuning(model);
CREATE INDEX IF NOT EXISTS idx_tuning_task        ON model_tuning(task_type);
CREATE INDEX IF NOT EXISTS idx_tuning_model_task  ON model_tuning(model, task_type);

-- ============================================================================
-- TABLE: prompt_patterns
-- ============================================================================
-- Best-performing prompts per model/task.
-- Recomputed by background-learner.js.

CREATE TABLE IF NOT EXISTS prompt_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- What this pattern applies to
    model           TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,

    -- Pattern data
    pattern_name    TEXT    NOT NULL,             -- e.g. 'structured_output', 'chain_of_thought'
    pattern_template TEXT,                        -- template string with {{placeholders}}
    instructions    TEXT,                         -- specific instructions that work well

    -- Performance for this pattern
    avg_quality     REAL    DEFAULT 0.0  CHECK(avg_quality >= 0),
    avg_confidence  REAL    DEFAULT 0.0  CHECK(avg_confidence >= 0),
    usage_count     INTEGER DEFAULT 0    CHECK(usage_count >= 0),
    success_rate    REAL    DEFAULT 0.0  CHECK(success_rate >= 0),

    -- Comparison
    vs_baseline_quality  REAL DEFAULT 0.0,       -- quality improvement over no-pattern baseline

    UNIQUE(model, task_type, pattern_name)
);

CREATE INDEX IF NOT EXISTS idx_prompt_model_task ON prompt_patterns(model, task_type);

-- ============================================================================
-- TABLE: model_combinations
-- ============================================================================
-- Tracks which worker combinations produce the best consensus results.
-- Recomputed by background-learner.js.

CREATE TABLE IF NOT EXISTS model_combinations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- Combination identity
    task_type       TEXT    NOT NULL,
    worker_models   TEXT    NOT NULL,             -- JSON array sorted: ["haiku","opus","sonnet"]
    arbiter_model   TEXT,                         -- which arbiter model was used

    -- Performance metrics
    avg_consensus   REAL    DEFAULT 0.0  CHECK(avg_consensus >= 0),
    avg_quality     REAL    DEFAULT 0.0  CHECK(avg_quality >= 0),
    avg_cost_usd    REAL    DEFAULT 0.0  CHECK(avg_cost_usd >= 0),
    avg_duration_ms REAL    DEFAULT 0.0  CHECK(avg_duration_ms >= 0),
    usage_count     INTEGER DEFAULT 0    CHECK(usage_count >= 0),

    -- Synergy score: how much better is this combo vs individual models
    synergy_score   REAL    DEFAULT 0.0,
    -- synergy = combo_quality - max(individual_qualities)

    -- Diversity metric: how different are the workers' outputs
    diversity_score REAL    DEFAULT 0.0,

    UNIQUE(task_type, worker_models, arbiter_model)
);

CREATE INDEX IF NOT EXISTS idx_combo_task     ON model_combinations(task_type);
CREATE INDEX IF NOT EXISTS idx_combo_synergy  ON model_combinations(synergy_score DESC);

-- ============================================================================
-- TABLE: learning_metadata
-- ============================================================================
-- Tracks schema version, last recompute times, and configuration.

CREATE TABLE IF NOT EXISTS learning_metadata (
    key             TEXT    PRIMARY KEY,
    value           TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed metadata
INSERT OR IGNORE INTO learning_metadata (key, value) VALUES
    ('schema_version', '1'),
    ('created_at', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('last_tuning_recompute', ''),
    ('last_prompt_recompute', ''),
    ('last_combo_recompute', ''),
    ('total_executions_logged', '0');
