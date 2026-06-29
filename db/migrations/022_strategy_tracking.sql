-- Migration 022: Multi-Dimensional Strategy Tracking
-- Created: 2026-06-28
-- Purpose: Extend strategy_performance table with additional strategy dimensions
--          for tracking prompt templates, orchestration patterns, verification methods,
--          and reasoning sequences.

-- Add new columns to learning.strategy_performance
ALTER TABLE learning.strategy_performance
  ADD COLUMN IF NOT EXISTS prompt_template_id VARCHAR(128),
  ADD COLUMN IF NOT EXISTS orchestration_pattern VARCHAR(128),
  ADD COLUMN IF NOT EXISTS verification_method VARCHAR(128),
  ADD COLUMN IF NOT EXISTS reasoning_sequence TEXT;

-- Add composite indexes for fast lookups by strategy dimensions
CREATE INDEX IF NOT EXISTS idx_strategy_perf_prompt_template
  ON learning.strategy_performance(prompt_template_id);

CREATE INDEX IF NOT EXISTS idx_strategy_perf_orchestration
  ON learning.strategy_performance(orchestration_pattern);

CREATE INDEX IF NOT EXISTS idx_strategy_perf_verification
  ON learning.strategy_performance(verification_method);

-- Composite index for multi-dimensional lookups
CREATE INDEX IF NOT EXISTS idx_strategy_perf_composite
  ON learning.strategy_performance(
    prompt_template_id,
    orchestration_pattern,
    verification_method
  ) WHERE avg_reward > 0.5;

-- Create a view for strategy analysis
CREATE OR REPLACE VIEW learning.strategy_analysis AS
SELECT
  strategy,
  prompt_template_id,
  orchestration_pattern,
  verification_method,
  successes,
  failures,
  ROUND(successes::NUMERIC / NULLIF(successes + failures, 0), 4) as success_rate,
  avg_reward,
  alpha,
  beta,
  last_updated,
  CASE
    WHEN successes + failures < 5 THEN 'INSUFFICIENT_DATA'
    WHEN avg_reward >= 0.8 THEN 'HIGH_PERFORMER'
    WHEN avg_reward >= 0.6 THEN 'MODERATE_PERFORMER'
    WHEN avg_reward >= 0.4 THEN 'LOW_PERFORMER'
    ELSE 'POOR_PERFORMER'
  END as performance_tier
FROM learning.strategy_performance
ORDER BY avg_reward DESC, successes + failures DESC;

-- Add comment documentation
COMMENT ON COLUMN learning.strategy_performance.prompt_template_id IS
  'Identifier for the prompt template used (e.g., chain-of-thought, few-shot, zero-shot)';

COMMENT ON COLUMN learning.strategy_performance.orchestration_pattern IS
  'Orchestration pattern used (e.g., parallel, sequential, hierarchical, debate)';

COMMENT ON COLUMN learning.strategy_performance.verification_method IS
  'Verification method used (e.g., multi-ai-consensus, adversarial, self-critique)';

COMMENT ON COLUMN learning.strategy_performance.reasoning_sequence IS
  'Description of the reasoning sequence/chain used in this strategy';

COMMENT ON VIEW learning.strategy_analysis IS
  'Analytical view of strategy performance with success rates and performance tiers';
