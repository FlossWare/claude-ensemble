-- Materialized view for tracking context effectiveness
-- Part of ECC #192 fix (Cross-Session Context Inheritance)
--
-- Analyzes correlation between context usage and workflow quality scores
-- Helps identify if pre-workflow context injection actually improves outcomes

CREATE MATERIALIZED VIEW IF NOT EXISTS workflow.context_effectiveness AS
WITH context_stats AS (
  SELECT
    e.workflow_name,
    (e.metadata->>'context_used')::boolean as context_used,
    (e.metadata->>'context_count')::int as context_count,
    e.outcome,
    e.total_duration_ms,
    e.total_workers,
    e.created_at,
    -- Average worker confidence
    (
      SELECT AVG(wr.confidence)
      FROM workflow.worker_results wr
      WHERE wr.workflow_execution_id = e.id
    ) as avg_worker_confidence,
    -- Average learning importance
    (
      SELECT AVG(l.importance)
      FROM workflow.learnings l
      WHERE l.workflow_execution_id = e.id
    ) as avg_learning_importance,
    -- Feedback quality score
    (
      SELECT AVG(f.quality_score)
      FROM workflow.feedback f
      WHERE f.workflow_execution_id = e.id
    ) as avg_quality_score
  FROM workflow.executions e
  WHERE e.outcome = 'success'
)
SELECT
  workflow_name,
  context_used,
  COUNT(*) as execution_count,
  AVG(context_count) as avg_context_count,
  AVG(total_duration_ms) as avg_duration_ms,
  AVG(avg_worker_confidence) as avg_worker_confidence,
  AVG(avg_learning_importance) as avg_learning_importance,
  AVG(avg_quality_score) as avg_quality_score,
  -- Success rate
  COUNT(*) FILTER (WHERE outcome = 'success')::float / NULLIF(COUNT(*), 0) as success_rate,
  -- Most recent execution
  MAX(created_at) as last_execution
FROM context_stats
GROUP BY workflow_name, context_used
ORDER BY workflow_name, context_used DESC;

-- Create index for fast refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_context_effectiveness_key
  ON workflow.context_effectiveness (workflow_name, context_used);

-- Refresh materialized view (initially empty)
REFRESH MATERIALIZED VIEW workflow.context_effectiveness;

-- Add comment
COMMENT ON MATERIALIZED VIEW workflow.context_effectiveness IS
'Tracks effectiveness of pre-workflow context injection by comparing outcomes with/without context. Part of ECC #192 fix.';

COMMENT ON COLUMN workflow.context_effectiveness.context_used IS
'Whether pre-workflow context was loaded and injected into worker prompts';

COMMENT ON COLUMN workflow.context_effectiveness.avg_context_count IS
'Average number of similar workflows loaded as context';

COMMENT ON COLUMN workflow.context_effectiveness.avg_worker_confidence IS
'Average confidence score across all workers (0.0-1.0)';

COMMENT ON COLUMN workflow.context_effectiveness.avg_quality_score IS
'Average quality score from feedback table (0.0-1.0)';
