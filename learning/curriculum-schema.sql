-- Curriculum Learning Schema Extensions
-- Additive schema changes for bandit-based model selection, task embedding,
-- active learning, and continual meta-optimization.
-- All changes are additive -- no existing columns or tables are dropped.

-- ============================================================================
-- TABLE: bandit_state
-- ============================================================================
-- Thompson Sampling posteriors per (model, task_type) pair.
-- alpha/beta parameterize a Beta distribution: higher alpha = more successes.
-- Sliding window tracks non-stationarity; shift detection resets posteriors.

CREATE TABLE IF NOT EXISTS bandit_state (
    model           TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,
    alpha           REAL    NOT NULL DEFAULT 1.0,
    beta            REAL    NOT NULL DEFAULT 1.0,
    window_start    TEXT,                            -- ISO-8601: start of current sliding window
    total_pulls     INTEGER DEFAULT 0,               -- total times this arm was pulled
    cumulative_regret REAL  DEFAULT 0.0,             -- sum(max_predicted - actual_selected)
    last_shift_detected TEXT,                        -- ISO-8601: last distribution shift
    shift_count     INTEGER DEFAULT 0,               -- number of shifts detected
    last_updated    TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(model, task_type)
);

CREATE INDEX IF NOT EXISTS idx_bandit_model      ON bandit_state(model);
CREATE INDEX IF NOT EXISTS idx_bandit_task        ON bandit_state(task_type);
CREATE INDEX IF NOT EXISTS idx_bandit_pulls       ON bandit_state(total_pulls DESC);

-- ============================================================================
-- TABLE: task_affinity
-- ============================================================================
-- Pairwise similarity between task types based on feature embeddings.
-- Used for transfer learning: when a new task has few samples, borrow
-- bandit posteriors from similar tasks.

CREATE TABLE IF NOT EXISTS task_affinity (
    task_type_a     TEXT    NOT NULL,
    task_type_b     TEXT    NOT NULL,
    cosine_similarity REAL,                          -- feature vector similarity
    transfer_score  REAL,                            -- how well preferences transfer
    quality_correlation REAL,                        -- correlation of model quality rankings
    sample_count    INTEGER DEFAULT 0,               -- executions used to compute
    computed_at     TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(task_type_a, task_type_b)
);

CREATE INDEX IF NOT EXISTS idx_affinity_a        ON task_affinity(task_type_a);
CREATE INDEX IF NOT EXISTS idx_affinity_b        ON task_affinity(task_type_b);
CREATE INDEX IF NOT EXISTS idx_affinity_sim      ON task_affinity(cosine_similarity DESC);

-- ============================================================================
-- TABLE: pareto_fronts
-- ============================================================================
-- Pareto-optimal model configurations along quality/cost/latency dimensions.
-- Enables strategy-based selection (QualityFirst picks top-right, CostOptimized
-- picks bottom-left on the Pareto front).

CREATE TABLE IF NOT EXISTS pareto_fronts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type       TEXT    NOT NULL,
    computed_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    configuration   TEXT    NOT NULL,                -- JSON: {model, parameters, strategy}
    quality         REAL,
    cost            REAL,
    latency         REAL,
    is_pareto_optimal INTEGER DEFAULT 1,
    dominated_by    INTEGER,                         -- FK to pareto_fronts.id if dominated
    FOREIGN KEY (dominated_by) REFERENCES pareto_fronts(id)
);

CREATE INDEX IF NOT EXISTS idx_pareto_task       ON pareto_fronts(task_type);
CREATE INDEX IF NOT EXISTS idx_pareto_optimal    ON pareto_fronts(is_pareto_optimal);
CREATE INDEX IF NOT EXISTS idx_pareto_quality    ON pareto_fronts(quality DESC);

-- ============================================================================
-- TABLE: curriculum_state
-- ============================================================================
-- Tracks the curriculum learning progression: which difficulty level the system
-- is at for each task type, success rates per level, and pacing parameters.

CREATE TABLE IF NOT EXISTS curriculum_state (
    task_type       TEXT    PRIMARY KEY,
    current_level   INTEGER NOT NULL DEFAULT 1,      -- 1=easy, 2=medium, 3=hard, 4=expert
    level_started_at TEXT,                            -- ISO-8601: when this level started
    success_count   INTEGER DEFAULT 0,               -- successes at current level
    failure_count   INTEGER DEFAULT 0,               -- failures at current level
    total_attempts  INTEGER DEFAULT 0,               -- total attempts at current level
    success_rate    REAL    DEFAULT 0.0,              -- rolling success rate
    promotion_threshold REAL DEFAULT 0.8,            -- success rate needed to advance
    demotion_threshold  REAL DEFAULT 0.4,            -- success rate triggering demotion
    min_attempts_before_change INTEGER DEFAULT 5,    -- minimum attempts before level change
    consecutive_successes INTEGER DEFAULT 0,         -- streak counter
    consecutive_failures  INTEGER DEFAULT 0,         -- streak counter
    last_outcome    TEXT,                             -- 'success' or 'failure'
    difficulty_scores TEXT DEFAULT '{}',              -- JSON: {level: avg_difficulty_score}
    pace_multiplier REAL DEFAULT 1.0,                -- adaptive pace (>1 = faster, <1 = slower)
    updated_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================================
-- TABLE: curriculum_history
-- ============================================================================
-- Log of all curriculum level transitions for analysis and meta-learning.

CREATE TABLE IF NOT EXISTS curriculum_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    task_type       TEXT    NOT NULL,
    from_level      INTEGER NOT NULL,
    to_level        INTEGER NOT NULL,
    trigger         TEXT    NOT NULL,                 -- 'promotion', 'demotion', 'reset', 'manual'
    success_rate_at_change REAL,
    attempts_at_level INTEGER,
    quality_at_change REAL,                          -- avg quality score at transition
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_curriculum_hist_task ON curriculum_history(task_type);
CREATE INDEX IF NOT EXISTS idx_curriculum_hist_time ON curriculum_history(timestamp);

-- ============================================================================
-- TABLE: feedback_schedule
-- ============================================================================
-- Ebbinghaus-inspired replay scheduling for quality re-validation.

CREATE TABLE IF NOT EXISTS feedback_schedule (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id    TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    scheduled_at    TEXT    NOT NULL,                 -- ISO-8601: when to re-check
    interval_days   INTEGER NOT NULL,                -- 1, 3, 7, or 14
    status          TEXT    DEFAULT 'pending',        -- 'pending', 'completed', 'skipped'
    triggered_by    TEXT,                             -- what parameter update triggered this
    quality_before  REAL,                             -- quality before the update
    quality_after   REAL,                             -- quality on re-check (filled when completed)
    completed_at    TEXT,
    FOREIGN KEY (execution_id) REFERENCES execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_sched_status  ON feedback_schedule(status);
CREATE INDEX IF NOT EXISTS idx_feedback_sched_time    ON feedback_schedule(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_feedback_sched_task    ON feedback_schedule(task_type);

-- ============================================================================
-- TABLE: meta_insights
-- ============================================================================
-- Meta-optimizer learnings: which optimization strategies work best.

CREATE TABLE IF NOT EXISTS meta_insights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    insight_type    TEXT    NOT NULL,                 -- 'parameter_update', 'strategy_switch', 'model_change'
    task_type       TEXT,
    model           TEXT,
    update_description TEXT,                          -- what changed
    quality_delta   REAL,                             -- quality improvement
    bwt_impact      REAL,                             -- backward transfer impact
    cost_delta      REAL,                             -- cost change
    net_benefit     REAL,                             -- quality_delta - abs(bwt_impact)
    causal_chain    TEXT    DEFAULT '{}',             -- JSON: full causal chain
    recommendation  TEXT                              -- meta-learned recommendation
);

CREATE INDEX IF NOT EXISTS idx_meta_type ON meta_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_meta_task ON meta_insights(task_type);
CREATE INDEX IF NOT EXISTS idx_meta_benefit ON meta_insights(net_benefit DESC);
