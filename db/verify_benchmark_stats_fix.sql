-- Verification script for benchmark_stats materialized view fix
-- This script tests the corrected GROUP BY logic

-- Step 1: Drop and recreate the materialized view
DROP MATERIALIZED VIEW IF EXISTS evaluation.benchmark_stats CASCADE;

-- Step 2: Recreate with corrected GROUP BY
CREATE MATERIALIZED VIEW evaluation.benchmark_stats AS
WITH difficulty_counts AS (
    SELECT
        task_type,
        COUNT(*) as total_questions,
        COUNT(CASE WHEN difficulty = 'easy' THEN 1 END) as easy_count,
        COUNT(CASE WHEN difficulty = 'medium' THEN 1 END) as medium_count,
        COUNT(CASE WHEN difficulty = 'hard' THEN 1 END) as hard_count,
        ROUND(AVG(CASE WHEN difficulty = 'easy' THEN 1 ELSE 0 END)::NUMERIC * 100, 2) as easy_percent,
        ROUND(AVG(CASE WHEN difficulty = 'medium' THEN 1 ELSE 0 END)::NUMERIC * 100, 2) as medium_percent,
        ROUND(AVG(CASE WHEN difficulty = 'hard' THEN 1 ELSE 0 END)::NUMERIC * 100, 2) as hard_percent
    FROM evaluation.benchmarks
    GROUP BY task_type
)
SELECT
    task_type,
    total_questions,
    easy_count,
    medium_count,
    hard_count,
    easy_percent,
    medium_percent,
    hard_percent,
    ROUND((easy_count + (medium_count * 2) + (hard_count * 3))::NUMERIC / total_questions, 2) as avg_difficulty
FROM difficulty_counts
ORDER BY task_type;

-- Step 3: Create unique index on task_type only
CREATE UNIQUE INDEX idx_benchmark_stats_unique ON evaluation.benchmark_stats(task_type);

-- Step 4: Refresh the materialized view
REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.benchmark_stats;

-- Step 5: Verify the results
-- Query to show that percentages are now meaningful (not all 0 or 100)
SELECT
    task_type,
    total_questions,
    easy_count,
    medium_count,
    hard_count,
    easy_percent,
    medium_percent,
    hard_percent,
    avg_difficulty
FROM evaluation.benchmark_stats
ORDER BY task_type;

-- Additional verification: Check that percentages add up to 100 (with rounding)
SELECT
    task_type,
    easy_percent,
    medium_percent,
    hard_percent,
    ROUND(easy_percent + medium_percent + hard_percent, 2) as total_percent,
    CASE
        WHEN ROUND(easy_percent + medium_percent + hard_percent, 2) = 100.00 THEN 'PASS'
        ELSE 'FAIL'
    END as validation_status
FROM evaluation.benchmark_stats
ORDER BY task_type;
