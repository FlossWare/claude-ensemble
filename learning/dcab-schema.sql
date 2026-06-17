-- DCAB (Diversity-Constrained Adaptive Bandit) Layer 1 Schema
-- PostgreSQL schema for diversity quota enforcement
-- Date: 2026-06-15
-- Architecture: /home/sfloess/.claude/DCAB_ARCHITECTURE_2026-06-15.md

-- ============================================================================
-- TABLE: learning.model_quotas
-- ============================================================================
-- Diversity quota configuration per model
-- Updated manually or via adaptive algorithm

CREATE TABLE IF NOT EXISTS learning.model_quotas (
    model               TEXT PRIMARY KEY,
    floor_pct           REAL NOT NULL DEFAULT 15.0 CHECK(floor_pct >= 0 AND floor_pct <= 100),
    ceiling_pct         REAL NOT NULL DEFAULT 40.0 CHECK(ceiling_pct >= 0 AND ceiling_pct <= 100),
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    pareto_frontier_member BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Seed default quotas for common models
INSERT INTO learning.model_quotas (model, floor_pct, ceiling_pct, enabled, pareto_frontier_member)
VALUES
    ('anthropic/claude-opus-4', 15.0, 40.0, TRUE, TRUE),
    ('anthropic/claude-sonnet-4', 15.0, 40.0, TRUE, TRUE),
    ('anthropic/claude-haiku-4', 15.0, 40.0, TRUE, TRUE),
    ('fable/fable', 15.0, 40.0, TRUE, TRUE),
    ('openai/gpt-4o', 15.0, 40.0, TRUE, FALSE),
    ('google/gemini-2.0-flash-exp', 15.0, 40.0, TRUE, FALSE)
ON CONFLICT (model) DO NOTHING;

-- ============================================================================
-- TABLE: learning.request_history
-- ============================================================================
-- Circular buffer of recent model requests (size: 20 as per architecture)
-- Used for quota enforcement calculations

CREATE TABLE IF NOT EXISTS learning.request_history (
    id                  SERIAL PRIMARY KEY,
    request_id          UUID NOT NULL UNIQUE,
    model               TEXT NOT NULL,
    timestamp           TIMESTAMP NOT NULL DEFAULT NOW(),
    task_type           TEXT,
    success             BOOLEAN,
    quality_score       REAL CHECK(quality_score >= 0 AND quality_score <= 1),
    duration_ms         INTEGER CHECK(duration_ms >= 0),
    cost_usd            REAL CHECK(cost_usd >= 0),
    diversity_score     REAL CHECK(diversity_score >= 0),
    quota_enforced      BOOLEAN NOT NULL DEFAULT FALSE,
    excluded_models     TEXT[] DEFAULT '{}',
    forced_models       TEXT[] DEFAULT '{}',
    ab_bucket           TEXT CHECK(ab_bucket IS NULL OR ab_bucket IN ('A', 'B'))
);

CREATE INDEX IF NOT EXISTS idx_request_history_timestamp ON learning.request_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_history_model ON learning.request_history(model);
CREATE INDEX IF NOT EXISTS idx_request_history_ab_bucket ON learning.request_history(ab_bucket);

-- ============================================================================
-- TABLE: learning.diversity_violations
-- ============================================================================
-- Log of diversity quota violations (for monitoring/alerting)

CREATE TABLE IF NOT EXISTS learning.diversity_violations (
    id                      SERIAL PRIMARY KEY,
    timestamp               TIMESTAMP NOT NULL DEFAULT NOW(),
    violation_type          TEXT NOT NULL CHECK(violation_type IN ('floor_breach', 'ceiling_breach', 'entropy_collapse')),
    model                   TEXT NOT NULL,
    current_usage_pct       REAL NOT NULL,
    quota_limit_pct         REAL NOT NULL,
    diversity_entropy       REAL,
    action_taken            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_diversity_violations_timestamp ON learning.diversity_violations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_diversity_violations_type ON learning.diversity_violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_diversity_violations_model ON learning.diversity_violations(model);

-- ============================================================================
-- VIEW: learning.diversity_current
-- ============================================================================
-- Current diversity status across all models
-- Shows usage percentages and quota violations
-- FIXED: Added all ORDER BY columns to SELECT to avoid PostgreSQL error

CREATE OR REPLACE VIEW learning.diversity_current AS
WITH recent_requests AS (
    -- Last 20 requests (window size from architecture)
    SELECT model, timestamp
    FROM learning.request_history
    ORDER BY timestamp DESC
    LIMIT 20
),
model_counts AS (
    SELECT
        model,
        COUNT(*) AS request_count
    FROM recent_requests
    GROUP BY model
),
total_count AS (
    SELECT COALESCE(SUM(request_count), 0) AS total
    FROM model_counts
)
SELECT
    mq.model,
    COALESCE(mc.request_count, 0) AS request_count,
    CASE
        WHEN tc.total = 0 THEN 0.0
        ELSE (COALESCE(mc.request_count, 0)::REAL / tc.total::REAL * 100.0)
    END AS usage_pct,
    mq.floor_pct,
    mq.ceiling_pct,
    mq.enabled,
    mq.pareto_frontier_member,
    CASE
        WHEN tc.total = 0 THEN 'OK'
        WHEN (COALESCE(mc.request_count, 0)::REAL / tc.total::REAL * 100.0) < mq.floor_pct THEN 'floor_breach'
        WHEN (COALESCE(mc.request_count, 0)::REAL / tc.total::REAL * 100.0) > mq.ceiling_pct THEN 'ceiling_breach'
        ELSE 'OK'
    END AS quota_status,
    CASE WHEN (COALESCE(mc.request_count, 0)::REAL / tc.total::REAL * 100.0) < mq.floor_pct THEN 1 ELSE 0 END AS floor_violations,
    CASE WHEN (COALESCE(mc.request_count, 0)::REAL / tc.total::REAL * 100.0) > mq.ceiling_pct THEN 1 ELSE 0 END AS ceiling_violations
FROM learning.model_quotas mq
CROSS JOIN total_count tc
LEFT JOIN model_counts mc ON mq.model = mc.model
WHERE mq.enabled = TRUE;

-- ============================================================================
-- FUNCTION: get_eligible_models()
-- ============================================================================
-- Compute eligible model pool based on diversity quotas
-- Returns: eligible_models, excluded_models, forced_models, quota_enforced
-- FIXED: Removed DISTINCT from ORDER BY subquery to avoid PostgreSQL error

CREATE OR REPLACE FUNCTION get_eligible_models()
RETURNS TABLE (
    eligible_models TEXT[],
    excluded_models TEXT[],
    forced_models TEXT[],
    quota_enforced BOOLEAN
) AS $$
DECLARE
    v_window_size INTEGER := 20; -- from CONFIG.WINDOW_SIZE
    v_total_count INTEGER;
    v_eligible TEXT[] := '{}';
    v_excluded TEXT[] := '{}';
    v_forced TEXT[] := '{}';
    v_quota_enforced BOOLEAN := FALSE;
    rec RECORD;
BEGIN
    -- Get total count of recent requests
    SELECT COUNT(*) INTO v_total_count
    FROM (
        SELECT model
        FROM learning.request_history
        ORDER BY timestamp DESC
        LIMIT v_window_size
    ) recent;

    -- If no history, return all enabled models
    IF v_total_count = 0 THEN
        SELECT ARRAY_AGG(model) INTO v_eligible
        FROM learning.model_quotas
        WHERE enabled = TRUE;

        RETURN QUERY SELECT v_eligible, v_excluded, v_forced, v_quota_enforced;
        RETURN;
    END IF;

    -- Check each model against quotas
    FOR rec IN
        SELECT
            mq.model,
            COALESCE(mc.request_count, 0) AS request_count,
            (COALESCE(mc.request_count, 0)::REAL / v_total_count::REAL * 100.0) AS usage_pct,
            mq.floor_pct,
            mq.ceiling_pct,
            mq.enabled
        FROM learning.model_quotas mq
        LEFT JOIN (
            SELECT model, COUNT(*) AS request_count
            FROM (
                -- FIXED: Removed DISTINCT to avoid ORDER BY error
                SELECT model
                FROM learning.request_history
                ORDER BY timestamp DESC
                LIMIT v_window_size
            ) recent_requests
            GROUP BY model
        ) mc ON mq.model = mc.model
        WHERE mq.enabled = TRUE
    LOOP
        -- Ceiling check: Exclude if > ceiling_pct
        IF rec.usage_pct > rec.ceiling_pct THEN
            v_excluded := array_append(v_excluded, rec.model);
            v_quota_enforced := TRUE;
            CONTINUE;
        END IF;

        -- Floor check: Force include if < floor_pct
        IF rec.usage_pct < rec.floor_pct THEN
            v_forced := array_append(v_forced, rec.model);
            v_quota_enforced := TRUE;
        END IF;

        -- Add to eligible pool
        v_eligible := array_append(v_eligible, rec.model);
    END LOOP;

    RETURN QUERY SELECT v_eligible, v_excluded, v_forced, v_quota_enforced;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER: Auto-cleanup old request history
-- ============================================================================
-- Keep only last 1000 entries to prevent unbounded growth
-- Triggered after each INSERT into request_history
-- FIXED (2026-06-15): Added retry limit and circuit breaker to prevent infinite loops
-- FIXED (2026-06-15): Added advisory lock protection to prevent race condition with monitor reads

CREATE OR REPLACE FUNCTION cleanup_request_history()
RETURNS TRIGGER AS $$
DECLARE
    v_delete_count INTEGER;
    v_retry_count INTEGER := 0;
    v_max_retries INTEGER := 3;
    v_row_count INTEGER;
    v_lock_acquired BOOLEAN;
BEGIN
    -- Circuit breaker: Check current row count before attempting cleanup
    SELECT COUNT(*) INTO v_row_count
    FROM learning.request_history;

    -- Only cleanup if we're actually over the threshold (1000 rows)
    IF v_row_count <= 1000 THEN
        RETURN NEW;
    END IF;

    -- Retry loop with exponential backoff protection
    LOOP
        BEGIN
            -- Acquire advisory lock to prevent race condition with monitor reads
            -- Use pg_try_advisory_lock to avoid blocking the INSERT trigger
            -- If lock unavailable, skip cleanup this time (will retry on next INSERT)
            SELECT pg_try_advisory_lock(hashtext('request_history_read')) INTO v_lock_acquired;

            IF NOT v_lock_acquired THEN
                -- Monitor is reading, skip cleanup this time
                RAISE NOTICE 'cleanup_request_history: Monitor reading, skipping cleanup';
                RETURN NEW;
            END IF;

            -- Delete excess rows beyond 1000 limit
            DELETE FROM learning.request_history
            WHERE id IN (
                SELECT id FROM learning.request_history
                ORDER BY timestamp DESC
                OFFSET 1000
            );

            -- Get number of rows deleted
            GET DIAGNOSTICS v_delete_count = ROW_COUNT;

            -- Release advisory lock
            PERFORM pg_advisory_unlock(hashtext('request_history_read'));

            -- Exit loop on success
            EXIT;

        EXCEPTION
            WHEN OTHERS THEN
                -- Release lock on error
                PERFORM pg_advisory_unlock(hashtext('request_history_read'));

                v_retry_count := v_retry_count + 1;

                -- Circuit breaker: Stop after max retries to prevent infinite loop
                IF v_retry_count >= v_max_retries THEN
                    -- Log the failure but don't block the INSERT
                    RAISE WARNING 'cleanup_request_history failed after % retries: %', v_max_retries, SQLERRM;
                    EXIT;
                END IF;

                -- Brief pause before retry (PostgreSQL pg_sleep requires seconds)
                PERFORM pg_sleep(0.1 * v_retry_count);  -- 100ms, 200ms, 300ms
        END;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_cleanup_request_history
AFTER INSERT ON learning.request_history
FOR EACH ROW
EXECUTE FUNCTION cleanup_request_history();

-- ============================================================================
-- INDEXES (Performance Optimization)
-- ============================================================================

-- Composite index for quota enforcement queries
CREATE INDEX IF NOT EXISTS idx_request_history_recent
ON learning.request_history(timestamp DESC, model);

-- A/B test analysis index
CREATE INDEX IF NOT EXISTS idx_request_history_ab_analysis
ON learning.request_history(ab_bucket, timestamp DESC)
WHERE ab_bucket IS NOT NULL;

-- ============================================================================
-- GRANTS (Security)
-- ============================================================================

-- Grant access to learning schema (adjust user as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA learning TO claude_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA learning TO claude_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA learning TO claude_user;
