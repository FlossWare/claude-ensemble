-- PostgreSQL Schema Initialization for Workflow Graph Sync
-- Run this on laptop-01:learning database

-- Create schemas
CREATE SCHEMA IF NOT EXISTS orchestrator;
CREATE SCHEMA IF NOT EXISTS workflows;

-- ========================================
-- Orchestrator: Background Job Queue
-- ========================================

CREATE TABLE IF NOT EXISTS orchestrator.work_queue (
  id SERIAL PRIMARY KEY,
  task_type VARCHAR(100) NOT NULL,
  payload JSONB NOT NULL,
  priority INTEGER DEFAULT 5,
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  scheduled_for TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  result JSONB,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_work_queue_status
ON orchestrator.work_queue(status, priority DESC, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_work_queue_task_type
ON orchestrator.work_queue(task_type);

COMMENT ON TABLE orchestrator.work_queue IS 'Background job queue for async tasks (Neo4j sync, embeddings, etc.)';
COMMENT ON COLUMN orchestrator.work_queue.task_type IS 'Job type: neo4j_sync, embedding_generation, etc.';
COMMENT ON COLUMN orchestrator.work_queue.priority IS 'Higher priority = processed first (1-10)';
COMMENT ON COLUMN orchestrator.work_queue.scheduled_for IS 'When to process (enables delayed/scheduled jobs)';

-- ========================================
-- Workflows: Execution Tracking
-- ========================================

CREATE TABLE IF NOT EXISTS workflows.executions (
  id SERIAL PRIMARY KEY,
  workflow_name VARCHAR(100) NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  status VARCHAR(20) DEFAULT 'running',
  metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_executions_workflow_name
ON workflows.executions(workflow_name);

CREATE INDEX IF NOT EXISTS idx_executions_status
ON workflows.executions(status);

CREATE INDEX IF NOT EXISTS idx_executions_completed_at
ON workflows.executions(completed_at DESC);

COMMENT ON TABLE workflows.executions IS 'High-level workflow execution tracking';
COMMENT ON COLUMN workflows.executions.status IS 'running | completed | failed';
COMMENT ON COLUMN workflows.executions.metadata IS 'Query, phases, quality_score, etc.';

-- ========================================
-- Workflows: Worker Results
-- ========================================

CREATE TABLE IF NOT EXISTS workflows.worker_results (
  id SERIAL PRIMARY KEY,
  execution_id INTEGER REFERENCES workflows.executions(id) ON DELETE CASCADE,
  model VARCHAR(100) NOT NULL,
  task_type VARCHAR(100),
  result JSONB,
  quality_score FLOAT,
  confidence FLOAT,
  duration_ms INTEGER,
  timestamp TIMESTAMP DEFAULT NOW(),
  execution_order INTEGER,
  parallel_group INTEGER
);

CREATE INDEX IF NOT EXISTS idx_worker_results_execution
ON workflows.worker_results(execution_id);

CREATE INDEX IF NOT EXISTS idx_worker_results_model
ON workflows.worker_results(model);

CREATE INDEX IF NOT EXISTS idx_worker_results_task_type
ON workflows.worker_results(task_type);

CREATE INDEX IF NOT EXISTS idx_worker_results_quality_score
ON workflows.worker_results(quality_score DESC);

COMMENT ON TABLE workflows.worker_results IS 'Individual worker results in multi-model workflows';
COMMENT ON COLUMN workflows.worker_results.execution_order IS 'Order in workflow (0, 1, 2, ...)';
COMMENT ON COLUMN workflows.worker_results.parallel_group IS 'NULL = sequential, integer = parallel group';

-- ========================================
-- Workflows: Arbiter Decisions
-- ========================================

CREATE TABLE IF NOT EXISTS workflows.arbiter_decisions (
  id SERIAL PRIMARY KEY,
  execution_id INTEGER REFERENCES workflows.executions(id) ON DELETE CASCADE,
  model VARCHAR(100) NOT NULL,
  decision TEXT,
  reasoning TEXT,
  confidence FLOAT,
  selected_worker_id INTEGER REFERENCES workflows.worker_results(id),
  final_quality_score FLOAT,
  timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_execution
ON workflows.arbiter_decisions(execution_id);

CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_model
ON workflows.arbiter_decisions(model);

CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_confidence
ON workflows.arbiter_decisions(confidence DESC);

COMMENT ON TABLE workflows.arbiter_decisions IS 'Arbiter decisions in multi-model consensus workflows';
COMMENT ON COLUMN workflows.arbiter_decisions.decision IS 'ACCEPT | REJECT | NEEDS_REVISION';
COMMENT ON COLUMN workflows.arbiter_decisions.selected_worker_id IS 'Which worker result was selected (if applicable)';

-- ========================================
-- Materialized Views for Analytics
-- ========================================

-- Workflow efficiency summary
CREATE MATERIALIZED VIEW IF NOT EXISTS workflows.efficiency_summary AS
SELECT
  workflow_name,
  COUNT(*) as total_executions,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
  AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_sec,
  AVG((metadata->>'qualityScore')::float) as avg_quality_score
FROM workflows.executions
WHERE completed_at IS NOT NULL
GROUP BY workflow_name
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_efficiency_summary_workflow
ON workflows.efficiency_summary(workflow_name);

COMMENT ON MATERIALIZED VIEW workflows.efficiency_summary IS 'Workflow efficiency metrics (refresh after each execution)';

-- Model performance summary
CREATE MATERIALIZED VIEW IF NOT EXISTS workflows.model_performance AS
SELECT
  model,
  task_type,
  COUNT(*) as executions,
  AVG(quality_score) as avg_quality,
  AVG(confidence) as avg_confidence,
  AVG(duration_ms) as avg_duration_ms,
  MIN(quality_score) as min_quality,
  MAX(quality_score) as max_quality
FROM workflows.worker_results
WHERE quality_score IS NOT NULL
GROUP BY model, task_type
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_performance_key
ON workflows.model_performance(model, task_type);

COMMENT ON MATERIALIZED VIEW workflows.model_performance IS 'Model performance by task type (refresh after each execution)';

-- ========================================
-- Helper Functions
-- ========================================

-- Refresh all workflow materialized views
CREATE OR REPLACE FUNCTION workflows.refresh_all_views()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY workflows.efficiency_summary;
  REFRESH MATERIALIZED VIEW CONCURRENTLY workflows.model_performance;
  -- Add more views here as needed
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION workflows.refresh_all_views IS 'Refresh all workflow materialized views (concurrent, non-blocking)';

-- Get workflow execution path (for graph queries)
CREATE OR REPLACE FUNCTION workflows.get_execution_path(p_execution_id INTEGER)
RETURNS TABLE (
  worker_model VARCHAR,
  worker_quality FLOAT,
  arbiter_decision TEXT,
  selected_worker INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    wr.model::VARCHAR AS worker_model,
    wr.quality_score AS worker_quality,
    ad.decision AS arbiter_decision,
    ad.selected_worker_id AS selected_worker
  FROM workflows.worker_results wr
  LEFT JOIN workflows.arbiter_decisions ad ON wr.execution_id = ad.execution_id
  WHERE wr.execution_id = p_execution_id
  ORDER BY wr.execution_order;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION workflows.get_execution_path IS 'Get workflow execution path (workers -> arbiter) - Neo4j equivalent';

-- Find best model for task type (PostgreSQL CTE fallback for Neo4j)
CREATE OR REPLACE FUNCTION workflows.best_model_for_task(
  p_task_type VARCHAR,
  p_min_executions INTEGER DEFAULT 5
)
RETURNS TABLE (
  model VARCHAR,
  avg_quality FLOAT,
  executions BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    wr.model::VARCHAR,
    AVG(wr.quality_score) AS avg_quality,
    COUNT(*) AS executions
  FROM workflows.worker_results wr
  WHERE wr.task_type = p_task_type
  GROUP BY wr.model
  HAVING COUNT(*) > p_min_executions
  ORDER BY AVG(wr.quality_score) DESC
  LIMIT 10;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION workflows.best_model_for_task IS 'Find best performing model for a task type - Neo4j equivalent';

-- Model collaboration patterns (PostgreSQL CTE fallback for Neo4j)
CREATE OR REPLACE FUNCTION workflows.model_collaboration_patterns()
RETURNS TABLE (
  model1 VARCHAR,
  model2 VARCHAR,
  cooccurrences BIGINT
) AS $$
BEGIN
  RETURN QUERY
  WITH workflow_models AS (
    SELECT
      execution_id,
      ARRAY_AGG(DISTINCT model ORDER BY model) AS models
    FROM workflows.worker_results
    GROUP BY execution_id
    HAVING COUNT(DISTINCT model) > 1
  )
  SELECT
    m1.model::VARCHAR AS model1,
    m2.model::VARCHAR AS model2,
    COUNT(*) AS cooccurrences
  FROM workflow_models wm
  CROSS JOIN LATERAL UNNEST(wm.models) AS m1(model)
  CROSS JOIN LATERAL UNNEST(wm.models) AS m2(model)
  WHERE m1.model < m2.model
  GROUP BY m1.model, m2.model
  ORDER BY COUNT(*) DESC
  LIMIT 20;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION workflows.model_collaboration_patterns IS 'Find which models often work together - Neo4j equivalent';

-- ========================================
-- Sample Data for Testing
-- ========================================

-- Example: Insert a test workflow execution
DO $$
DECLARE
  exec_id INTEGER;
  worker1_id INTEGER;
  worker2_id INTEGER;
BEGIN
  -- Insert execution
  INSERT INTO workflows.executions (workflow_name, started_at, completed_at, status, metadata)
  VALUES (
    'test-workflow',
    NOW() - INTERVAL '5 minutes',
    NOW(),
    'completed',
    '{"query": "Test query", "qualityScore": 0.85, "phases": 3}'::jsonb
  )
  RETURNING id INTO exec_id;

  -- Insert worker results
  INSERT INTO workflows.worker_results (
    execution_id, model, task_type, result, quality_score, confidence, duration_ms, execution_order
  )
  VALUES
    (exec_id, 'claude-opus-4', 'test', '{"output": "result1"}', 0.87, 0.9, 3000, 0),
    (exec_id, 'claude-sonnet-4', 'test', '{"output": "result2"}', 0.83, 0.85, 2500, 1)
  RETURNING id INTO worker1_id, worker2_id;

  -- Insert arbiter decision
  INSERT INTO workflows.arbiter_decisions (
    execution_id, model, decision, reasoning, confidence, selected_worker_id, final_quality_score
  )
  VALUES (
    exec_id,
    'claude-opus-4',
    'ACCEPT',
    'Result 1 has higher quality and confidence',
    0.92,
    worker1_id,
    0.87
  );

  -- Enqueue Neo4j sync job
  INSERT INTO orchestrator.work_queue (task_type, payload, priority)
  VALUES ('neo4j_sync', jsonb_build_object('executionId', exec_id), 5);

  RAISE NOTICE 'Test data inserted: execution_id=%', exec_id;
END $$;

-- ========================================
-- Grants (adjust user as needed)
-- ========================================

GRANT USAGE ON SCHEMA orchestrator TO sfloess;
GRANT USAGE ON SCHEMA workflows TO sfloess;
GRANT ALL ON ALL TABLES IN SCHEMA orchestrator TO sfloess;
GRANT ALL ON ALL TABLES IN SCHEMA workflows TO sfloess;
GRANT ALL ON ALL SEQUENCES IN SCHEMA orchestrator TO sfloess;
GRANT ALL ON ALL SEQUENCES IN SCHEMA workflows TO sfloess;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA workflows TO sfloess;

-- ========================================
-- Verification Queries
-- ========================================

-- Check test data
SELECT 'Workflow executions:' as description, COUNT(*) as count FROM workflows.executions
UNION ALL
SELECT 'Worker results:', COUNT(*) FROM workflows.worker_results
UNION ALL
SELECT 'Arbiter decisions:', COUNT(*) FROM workflows.arbiter_decisions
UNION ALL
SELECT 'Queued jobs:', COUNT(*) FROM orchestrator.work_queue;

-- Test helper functions
SELECT * FROM workflows.get_execution_path(1);
SELECT * FROM workflows.best_model_for_task('test', 0);
SELECT * FROM workflows.model_collaboration_patterns();

-- Refresh materialized views
SELECT workflows.refresh_all_views();
SELECT * FROM workflows.efficiency_summary;
SELECT * FROM workflows.model_performance;

COMMIT;
