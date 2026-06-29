# Benchmark Stats Materialized View Fix - Summary

## Issue Fixed
The `evaluation.benchmark_stats` materialized view was grouping by both `task_type` AND `difficulty`, which caused the percentage columns (`easy_percent`, `medium_percent`, `hard_percent`) to always be 0.00 or 100.00 since each group contained only a single difficulty level.

## Root Cause
Original query:
```sql
GROUP BY task_type, difficulty
ROUND(AVG(CAST(difficulty = 'easy' AS INTEGER)) * 100, 2) as easy_percent,
```

When grouped by difficulty, all rows in a group have the same difficulty value, making:
- `difficulty = 'easy'` → 1 for all rows OR 0 for all rows
- Average of all 1s or all 0s → always 100% or 0%

## Solution Implemented

### 1. Changed GROUP BY Clause
- **Before:** `GROUP BY task_type, difficulty` (separate row per difficulty)
- **After:** `GROUP BY task_type` (one row per task type)

### 2. Restructured Query with CTE
```sql
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
```

### 3. Updated Unique Index
- **Before:** `CREATE UNIQUE INDEX idx_benchmark_stats_unique ON evaluation.benchmark_stats(task_type, difficulty);`
- **After:** `CREATE UNIQUE INDEX idx_benchmark_stats_unique ON evaluation.benchmark_stats(task_type);`

### 4. Added New Columns
- `total_questions` - Total questions per task type
- `easy_count` - Count of easy questions
- `medium_count` - Count of medium questions
- `hard_count` - Count of hard questions
- `avg_difficulty` - Weighted average difficulty (1=easy, 2=medium, 3=hard)

## Benefits

1. **Meaningful Percentages** - Now shows actual distribution (e.g., 60% easy, 30% medium, 10% hard)
2. **Percentages Sum to 100** - Mathematical validation confirms correctness
3. **Better Analytics** - Can see overall task difficulty distribution per task type
4. **Simpler Queries** - One row per task type instead of 3 rows (one per difficulty)
5. **Added Metrics** - `avg_difficulty` provides quick difficulty assessment

## Verification Results

### Test Data
- 20 benchmark questions inserted
- 2 task types: code_generation, question_answering
- Mix of easy, medium, and hard difficulties

### Verification Passed ✓
1. **GROUP BY correctness**: One row per task_type ✓
2. **Percentages meaningful**: code_generation (60/30/10), question_answering (50/40/10) ✓
3. **Percentages sum to 100**: Both task types total 100.00% ✓
4. **Counts match percentages**: All counts validated ✓
5. **Unique index on task_type**: Confirmed ✓

### Sample Output
```
    task_type      | total_questions | easy_percent | medium_percent | hard_percent | avg_difficulty
--------------------+-----------------+--------------+----------------+--------------+----------------
 code_generation    |              10 |        60.00 |          30.00 |        10.00 |           1.50
 question_answering |              10 |        50.00 |          40.00 |        10.00 |           1.60
```

## File Modified
- `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/db/migrations/023_evaluation_schema.sql`

## Migration Status
✅ Applied to PostgreSQL (laptop-01, database: learning)
✅ All materialized views successfully created
✅ UNIQUE index correctly created on task_type only
✅ View can be refreshed with CONCURRENT option

## Additional Fixes
- Added `::NUMERIC` type casts to ROUND() functions for PostgreSQL compatibility
- Fixed both `model_performance` and `task_model_performance` views with same type casting
