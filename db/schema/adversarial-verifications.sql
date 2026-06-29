-- Adversarial Verification Storage Schema
-- Created: 2026-06-28
--
-- Stores results from adversarial refutation attempts on consensus results.
-- Enables learning from failed refutations and cost optimization via caching.

CREATE TABLE IF NOT EXISTS workflow.adversarial_verifications (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER NOT NULL REFERENCES workflow.executions(id) ON DELETE CASCADE,

  -- What was verified
  answer_candidate TEXT NOT NULL, -- Proposed answer from consensus
  original_task TEXT NOT NULL, -- Original task/question

  -- Verification result
  verdict VARCHAR(50) NOT NULL CHECK (verdict IN ('ACCEPT', 'ACCEPT_WITH_CAVEATS', 'REJECT')),
  confidence VARCHAR(20) NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),

  -- Refuter statistics
  refuters_failed INTEGER NOT NULL, -- Number of refuters who failed to disprove (good)
  refuters_total INTEGER NOT NULL, -- Total number of refuters
  critical_issues_count INTEGER DEFAULT 0,
  major_issues_count INTEGER DEFAULT 0,

  -- Individual refuter votes (JSONB)
  -- Schema: [{ refuter_id, model, verdict, confidence, reasoning, severity, cost_usd, ... }]
  votes JSONB NOT NULL,

  -- Performance metrics
  cost_usd NUMERIC(10, 6) DEFAULT 0,
  duration_ms INTEGER,

  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_adversarial_workflow ON workflow.adversarial_verifications(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_adversarial_verdict ON workflow.adversarial_verifications(verdict);
CREATE INDEX IF NOT EXISTS idx_adversarial_confidence ON workflow.adversarial_verifications(confidence);
CREATE INDEX IF NOT EXISTS idx_adversarial_created ON workflow.adversarial_verifications(created_at DESC);

-- Index for vote analysis (JSONB)
CREATE INDEX IF NOT EXISTS idx_adversarial_votes ON workflow.adversarial_verifications USING GIN (votes);

-- Comments
COMMENT ON TABLE workflow.adversarial_verifications IS 'Stores adversarial verification results from refuter agents';
COMMENT ON COLUMN workflow.adversarial_verifications.refuters_failed IS 'Number of refuters who could NOT disprove the answer (higher = better)';
COMMENT ON COLUMN workflow.adversarial_verifications.votes IS 'JSONB array of individual refuter votes with full details';

-- Materialized view: Adversarial verification statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS workflow.adversarial_stats AS
SELECT
  verdict,
  confidence,
  COUNT(*) as total_verifications,
  AVG(refuters_failed::NUMERIC / refuters_total) as avg_success_rate,
  AVG(critical_issues_count) as avg_critical_issues,
  AVG(major_issues_count) as avg_major_issues,
  AVG(cost_usd) as avg_cost_usd,
  AVG(duration_ms) as avg_duration_ms,
  SUM(cost_usd) as total_cost_usd
FROM workflow.adversarial_verifications
GROUP BY verdict, confidence
ORDER BY verdict, confidence;

COMMENT ON MATERIALIZED VIEW workflow.adversarial_stats IS 'Aggregated statistics on adversarial verification outcomes';

-- Refresh materialized view function (call after inserts)
CREATE OR REPLACE FUNCTION workflow.refresh_adversarial_stats()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW workflow.adversarial_stats;
END;
$$ LANGUAGE plpgsql;

-- Example queries:

-- Recent rejections with critical issues
-- SELECT * FROM workflow.adversarial_verifications
-- WHERE verdict = 'REJECT' AND critical_issues_count > 0
-- ORDER BY created_at DESC LIMIT 10;

-- Success rate by confidence level
-- SELECT confidence,
--        AVG(refuters_failed::NUMERIC / refuters_total) as success_rate,
--        COUNT(*) as count
-- FROM workflow.adversarial_verifications
-- GROUP BY confidence;

-- Most expensive verifications
-- SELECT workflow_execution_id, verdict, cost_usd, duration_ms
-- FROM workflow.adversarial_verifications
-- ORDER BY cost_usd DESC LIMIT 20;

-- Extract refuter model performance
-- SELECT
--   vote->>'model' as model,
--   vote->>'verdict' as verdict,
--   (vote->>'confidence')::NUMERIC as confidence,
--   COUNT(*) as count
-- FROM workflow.adversarial_verifications,
--      jsonb_array_elements(votes) as vote
-- GROUP BY vote->>'model', vote->>'verdict'
-- ORDER BY model, verdict;
