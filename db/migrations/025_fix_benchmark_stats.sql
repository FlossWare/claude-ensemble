DROP MATERIALIZED VIEW IF EXISTS evaluation.benchmark_stats;

CREATE MATERIALIZED VIEW evaluation.benchmark_stats AS
SELECT
  task_type,
  COUNT(*) as total_questions,
  COUNT(CASE WHEN difficulty = 'easy' THEN 1 END) * 100.0 / COUNT(*) as easy_percent,
  COUNT(CASE WHEN difficulty = 'medium' THEN 1 END) * 100.0 / COUNT(*) as medium_percent,
  COUNT(CASE WHEN difficulty = 'hard' THEN 1 END) * 100.0 / COUNT(*) as hard_percent
FROM evaluation.benchmark_questions
GROUP BY task_type;

CREATE UNIQUE INDEX idx_benchmark_stats_task_type ON evaluation.benchmark_stats(task_type);
