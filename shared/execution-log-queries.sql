-- Sample queries for monitoring.execution_log
-- Table wired in: Issue #252

-- ============================================================================
-- 1. Worker Performance by Model and Workflow
-- ============================================================================
SELECT
  model,
  workflow,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(confidence) as avg_confidence,
  SUM(CASE WHEN was_selected THEN 1 ELSE 0 END) as selected_count,
  SUM(CASE WHEN was_selected THEN 1 ELSE 0 END)::float / COUNT(*) as selection_rate,
  AVG(cost_usd) as avg_cost,
  AVG(duration_ms) as avg_duration
FROM monitoring.execution_log
WHERE model_role = 'worker'
  AND quality_score IS NOT NULL
GROUP BY model, workflow
ORDER BY avg_quality DESC;

-- ============================================================================
-- 2. Arbiter Decision Quality
-- ============================================================================
SELECT
  model as arbiter_model,
  workflow,
  COUNT(*) as decisions,
  AVG(quality_score) as avg_quality,
  AVG(confidence) as avg_confidence,
  AVG(jsonb_array_length(worker_models)) as avg_worker_count,
  AVG(duration_ms) as avg_duration
FROM monitoring.execution_log
WHERE model_role = 'arbiter'
  AND worker_models IS NOT NULL
GROUP BY model, workflow
ORDER BY avg_quality DESC;

-- ============================================================================
-- 3. Worker Selection Patterns (which workers get selected most)
-- ============================================================================
SELECT
  model,
  workflow,
  COUNT(*) as total_executions,
  SUM(CASE WHEN was_selected THEN 1 ELSE 0 END) as selected_count,
  AVG(quality_score) as avg_quality,
  AVG(consensus_score) as avg_consensus,
  AVG(CASE WHEN was_selected THEN quality_score END) as avg_quality_when_selected
FROM monitoring.execution_log
WHERE model_role = 'worker'
  AND quality_score IS NOT NULL
GROUP BY model, workflow
ORDER BY selected_count DESC;

-- ============================================================================
-- 4. Strategy Effectiveness
-- ============================================================================
SELECT
  strategy,
  selection_method,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(cost_usd) as avg_cost,
  AVG(duration_ms) as avg_duration,
  SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_log
WHERE strategy IS NOT NULL
  AND quality_score IS NOT NULL
GROUP BY strategy, selection_method
ORDER BY avg_quality DESC;

-- ============================================================================
-- 5. Phase Performance Analysis
-- ============================================================================
SELECT
  workflow,
  phase,
  model_role,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(duration_ms) as avg_duration,
  AVG(cost_usd) as avg_cost
FROM monitoring.execution_log
WHERE quality_score IS NOT NULL
GROUP BY workflow, phase, model_role
ORDER BY workflow, phase;

-- ============================================================================
-- 6. Recent Execution History (debugging)
-- ============================================================================
SELECT
  id,
  timestamp,
  model,
  model_role,
  workflow,
  phase,
  label,
  quality_score,
  confidence,
  outcome,
  duration_ms,
  cost_usd
FROM monitoring.execution_log
ORDER BY timestamp DESC
LIMIT 20;

-- ============================================================================
-- 7. Consensus Quality Analysis (worker vs arbiter)
-- ============================================================================
WITH worker_scores AS (
  SELECT
    run_id,
    AVG(quality_score) as worker_avg_quality,
    AVG(consensus_score) as worker_avg_consensus,
    array_agg(model ORDER BY quality_score DESC) as worker_models
  FROM monitoring.execution_log
  WHERE model_role = 'worker'
    AND run_id IS NOT NULL
    AND quality_score IS NOT NULL
  GROUP BY run_id
),
arbiter_scores AS (
  SELECT
    run_id,
    quality_score as arbiter_quality,
    selected_model
  FROM monitoring.execution_log
  WHERE model_role = 'arbiter'
    AND run_id IS NOT NULL
)
SELECT
  w.run_id,
  w.worker_avg_quality,
  w.worker_avg_consensus,
  a.arbiter_quality,
  a.selected_model,
  w.worker_models
FROM worker_scores w
JOIN arbiter_scores a ON w.run_id = a.run_id
ORDER BY a.arbiter_quality DESC
LIMIT 20;

-- ============================================================================
-- 8. Cost vs Quality Efficiency
-- ============================================================================
SELECT
  model,
  workflow,
  AVG(quality_score) as avg_quality,
  AVG(cost_usd) as avg_cost,
  AVG(quality_score) / NULLIF(AVG(cost_usd), 0) as quality_per_dollar
FROM monitoring.execution_log
WHERE quality_score IS NOT NULL
  AND cost_usd > 0
GROUP BY model, workflow
ORDER BY quality_per_dollar DESC;

-- ============================================================================
-- 9. Task Type Performance Matrix
-- ============================================================================
SELECT
  task_type,
  model,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(duration_ms) as avg_duration,
  AVG(cost_usd) as avg_cost,
  SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_log
WHERE task_type IS NOT NULL
  AND quality_score IS NOT NULL
GROUP BY task_type, model
ORDER BY task_type, avg_quality DESC;

-- ============================================================================
-- 10. Selection Method Comparison
-- ============================================================================
SELECT
  selection_method,
  model_role,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(confidence) as avg_confidence,
  AVG(duration_ms) as avg_duration,
  SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM monitoring.execution_log
WHERE selection_method IS NOT NULL
  AND quality_score IS NOT NULL
GROUP BY selection_method, model_role
ORDER BY avg_quality DESC;
