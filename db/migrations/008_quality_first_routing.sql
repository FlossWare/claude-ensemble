-- Migration 008: Quality-First Routing Configuration
-- Created: 2026-06-28
-- Purpose: Add configuration table for quality-first routing mode
--
-- Quality-first routing removes cost weights from routing decisions,
-- prioritizing capability × confidence × history only.
--
-- Use cases:
--   - Free API fleets (DeepSeek, Gemini Flash, etc.)
--   - Critical tasks where accuracy > cost
--   - Research workflows requiring maximum quality

-- ============================================================================
-- Quality-First Routing Configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow.quality_first_config (
  id SERIAL PRIMARY KEY,
  workflow_name TEXT NOT NULL,
  task_type TEXT NOT NULL,
  use_quality_first_routing BOOLEAN DEFAULT FALSE,

  -- Reasoning for quality-first mode
  reason TEXT,

  -- Cost tolerance (optional - for hybrid mode)
  max_cost_per_call NUMERIC DEFAULT NULL,

  -- Performance tracking
  enabled_at TIMESTAMP DEFAULT NOW(),
  disabled_at TIMESTAMP DEFAULT NULL,
  last_updated TIMESTAMP DEFAULT NOW(),

  -- Ensure unique config per workflow+task
  UNIQUE(workflow_name, task_type)
);

COMMENT ON TABLE workflow.quality_first_config IS
  'Configuration for quality-first routing mode (cost ignored)';

COMMENT ON COLUMN workflow.quality_first_config.use_quality_first_routing IS
  'If TRUE, use quality-first weights (no cost multiplier)';

COMMENT ON COLUMN workflow.quality_first_config.max_cost_per_call IS
  'Optional cost limit for hybrid mode (NULL = unlimited)';

-- ============================================================================
-- Quality-First Routing Audit Trail
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow.quality_first_decisions (
  id SERIAL PRIMARY KEY,
  workflow_execution_id TEXT NOT NULL,
  task_type TEXT NOT NULL,

  -- Models considered
  models_evaluated JSONB,

  -- Winner selection
  winner_model TEXT NOT NULL,
  winner_quality_weight NUMERIC,

  -- Comparison with cost-weighted (if available)
  cost_weighted_winner TEXT,
  cost_weighted_weight NUMERIC,
  same_winner BOOLEAN,

  -- Performance metrics
  quality_advantage NUMERIC,
  cost_incurred NUMERIC,

  created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE workflow.quality_first_decisions IS
  'Audit trail for quality-first routing decisions';

CREATE INDEX idx_quality_first_decisions_workflow ON workflow.quality_first_decisions(workflow_execution_id);
CREATE INDEX idx_quality_first_decisions_task_type ON workflow.quality_first_decisions(task_type);
CREATE INDEX idx_quality_first_decisions_created_at ON workflow.quality_first_decisions(created_at);

-- ============================================================================
-- Helper Views
-- ============================================================================

-- View: Active quality-first workflows
CREATE OR REPLACE VIEW workflow.active_quality_first_workflows AS
SELECT
  workflow_name,
  task_type,
  reason,
  max_cost_per_call,
  enabled_at
FROM workflow.quality_first_config
WHERE use_quality_first_routing = TRUE
  AND (disabled_at IS NULL OR disabled_at > NOW());

COMMENT ON VIEW workflow.active_quality_first_workflows IS
  'List of workflows using quality-first routing';

-- View: Quality-first vs cost-weighted comparison
CREATE OR REPLACE VIEW workflow.quality_vs_cost_comparison AS
SELECT
  task_type,
  COUNT(*) AS total_decisions,
  SUM(CASE WHEN same_winner THEN 1 ELSE 0 END) AS agreement_count,
  ROUND(100.0 * SUM(CASE WHEN same_winner THEN 1 ELSE 0 END) / COUNT(*), 1) AS agreement_percentage,
  AVG(quality_advantage) AS avg_quality_advantage,
  AVG(cost_incurred) AS avg_cost,
  MAX(created_at) AS last_decision
FROM workflow.quality_first_decisions
WHERE cost_weighted_winner IS NOT NULL
GROUP BY task_type;

COMMENT ON VIEW workflow.quality_vs_cost_comparison IS
  'Comparison of quality-first vs cost-weighted routing by task type';

-- ============================================================================
-- Sample Configuration
-- ============================================================================

-- Example: Enable quality-first routing for deep-research workflow
INSERT INTO workflow.quality_first_config
  (workflow_name, task_type, use_quality_first_routing, reason)
VALUES
  ('deep-research', 'research', TRUE, 'Free API fleet (DeepSeek, Gemini Flash) - cost not a factor'),
  ('code-security', 'security_audit', TRUE, 'Critical security tasks - accuracy > cost'),
  ('code-review', 'code_review', FALSE, 'Cost-sensitive - use weighted routing')
ON CONFLICT (workflow_name, task_type) DO NOTHING;

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify tables created
SELECT
  schemaname,
  tablename,
  tableowner
FROM pg_tables
WHERE schemaname = 'workflow'
  AND tablename IN ('quality_first_config', 'quality_first_decisions')
ORDER BY tablename;

-- Verify views created
SELECT
  schemaname,
  viewname,
  viewowner
FROM pg_views
WHERE schemaname = 'workflow'
  AND viewname IN ('active_quality_first_workflows', 'quality_vs_cost_comparison')
ORDER BY viewname;
