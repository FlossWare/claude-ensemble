-- ============================================================================
-- Human Review Queue - Example Queries
--
-- Common queries for interacting with the human review queue.
--
-- Created: 2026-06-28
-- ============================================================================

-- ============================================================================
-- FETCH PENDING REVIEWS
-- ============================================================================

-- Fetch top 10 pending reviews ordered by disagreement score (highest first)
-- This is the main query for the human review dashboard
SELECT
  id,
  workflow_name,
  task_description,
  disagreement_score,
  disagreement_level,
  num_votes,
  unique_answers,
  priority,
  created_at,
  confidence_range->>'mean' as avg_confidence,
  confidence_range->>'std_dev' as confidence_std_dev
FROM workflow.human_review_queue
WHERE status = 'pending'
ORDER BY disagreement_score DESC, created_at ASC
LIMIT 10;

-- Fetch high-priority pending reviews (priority >= 8)
SELECT
  id,
  workflow_name,
  task_description,
  disagreement_score,
  disagreement_level,
  priority,
  created_at
FROM workflow.human_review_queue
WHERE status = 'pending' AND priority >= 8
ORDER BY priority DESC, created_at ASC
LIMIT 20;

-- Fetch pending reviews for a specific workflow
SELECT
  id,
  task_description,
  disagreement_score,
  num_votes,
  unique_answers,
  created_at
FROM workflow.human_review_queue
WHERE status = 'pending'
  AND workflow_execution_id = 'weighted_1735410000_abc123'
ORDER BY disagreement_score DESC;

-- ============================================================================
-- EXAMINE REVIEW DETAILS
-- ============================================================================

-- Get full details for a specific review (including votes)
SELECT
  id,
  workflow_execution_id,
  workflow_name,
  task_description,
  disagreement_score,
  disagreement_level,
  num_votes,
  unique_answers,
  priority,
  votes_json,
  confidence_range,
  weighted_winner,
  winner_confidence,
  runner_up,
  status,
  created_at,
  updated_at
FROM workflow.human_review_queue
WHERE id = 123;

-- Extract individual votes from a review entry
SELECT
  id,
  task_description,
  jsonb_array_elements(votes_json) as vote
FROM workflow.human_review_queue
WHERE id = 123;

-- Compare weighted winner vs runner-up
SELECT
  id,
  task_description,
  disagreement_score,
  weighted_winner->>'answer' as weighted_winner_answer,
  winner_confidence,
  runner_up->>'answer' as runner_up_answer,
  runner_up->>'total_weight' as runner_up_weight
FROM workflow.human_review_queue
WHERE status = 'pending'
  AND disagreement_score > 0.20
ORDER BY disagreement_score DESC;

-- ============================================================================
-- UPDATE REVIEW STATUS
-- ============================================================================

-- Mark a review as reviewed with human verdict
UPDATE workflow.human_review_queue
SET
  status = 'reviewed',
  human_verdict = '{"answer": "Option A", "confidence": 85}'::jsonb,
  human_reviewer = 'user@example.com',
  reviewed_at = NOW(),
  resolution_notes = 'After careful analysis, Option A is correct because...'
WHERE id = 123
RETURNING id, workflow_execution_id, disagreement_score;

-- Mark a review as dismissed (disagreement was acceptable)
UPDATE workflow.human_review_queue
SET
  status = 'dismissed',
  resolution_notes = 'Disagreement acceptable, weighted voting result approved',
  reviewed_at = NOW(),
  human_reviewer = 'user@example.com'
WHERE id = 123;

-- Mark a review as resolved (action taken)
UPDATE workflow.human_review_queue
SET
  status = 'resolved',
  resolution_notes = 'Issue resolved by updating model weights'
WHERE id = 123;

-- ============================================================================
-- STATISTICS & ANALYSIS
-- ============================================================================

-- Count reviews by status and disagreement level
SELECT
  status,
  disagreement_level,
  COUNT(*) as count,
  AVG(disagreement_score) as avg_disagreement,
  MIN(created_at) as oldest,
  MAX(created_at) as newest
FROM workflow.human_review_queue
GROUP BY status, disagreement_level
ORDER BY status, disagreement_level;

-- Find reviews with very high disagreement (CV > 0.40)
SELECT
  id,
  workflow_name,
  task_description,
  disagreement_score,
  num_votes,
  unique_answers,
  created_at
FROM workflow.human_review_queue
WHERE disagreement_score > 0.40
  AND status = 'pending'
ORDER BY disagreement_score DESC;

-- Average time to review by disagreement level
SELECT
  disagreement_level,
  COUNT(*) as total_reviews,
  COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed_count,
  AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at))) / 3600 as avg_hours_to_review,
  MAX(EXTRACT(EPOCH FROM (reviewed_at - created_at))) / 3600 as max_hours_to_review
FROM workflow.human_review_queue
WHERE reviewed_at IS NOT NULL
GROUP BY disagreement_level
ORDER BY disagreement_level;

-- ============================================================================
-- FEEDBACK LOOP ANALYSIS
-- ============================================================================

-- Compare weighted voting accuracy vs human verdicts
WITH reviews_with_verdict AS (
  SELECT
    id,
    workflow_execution_id,
    disagreement_score,
    disagreement_level,
    weighted_winner->>'answer' as weighted_answer,
    winner_confidence,
    human_verdict->>'answer' as human_answer,
    (human_verdict->>'confidence')::numeric as human_confidence
  FROM workflow.human_review_queue
  WHERE status = 'reviewed'
    AND human_verdict IS NOT NULL
)
SELECT
  disagreement_level,
  COUNT(*) as total_reviews,
  COUNT(CASE WHEN weighted_answer = human_answer THEN 1 END) as weighted_correct,
  COUNT(CASE WHEN weighted_answer != human_answer THEN 1 END) as weighted_incorrect,
  ROUND(100.0 * COUNT(CASE WHEN weighted_answer = human_answer THEN 1 END) / COUNT(*), 2) as weighted_accuracy_pct,
  AVG(disagreement_score) as avg_disagreement,
  AVG(ABS(winner_confidence - human_confidence)) as avg_confidence_error
FROM reviews_with_verdict
GROUP BY disagreement_level
ORDER BY disagreement_level;

-- Find cases where weighted voting was wrong
SELECT
  id,
  workflow_execution_id,
  task_description,
  disagreement_score,
  weighted_winner->>'answer' as weighted_answer,
  winner_confidence,
  human_verdict->>'answer' as human_answer,
  (human_verdict->>'confidence')::numeric as human_confidence,
  resolution_notes
FROM workflow.human_review_queue
WHERE status = 'reviewed'
  AND human_verdict IS NOT NULL
  AND weighted_winner->>'answer' != human_verdict->>'answer'
ORDER BY disagreement_score DESC;

-- ============================================================================
-- DASHBOARD SUMMARY VIEW
-- ============================================================================

-- Overall dashboard summary
SELECT
  'pending' as category,
  COUNT(*) as count,
  AVG(disagreement_score) as avg_disagreement,
  MAX(priority) as max_priority,
  MIN(created_at) as oldest
FROM workflow.human_review_queue
WHERE status = 'pending'

UNION ALL

SELECT
  'high_priority_pending' as category,
  COUNT(*) as count,
  AVG(disagreement_score) as avg_disagreement,
  MAX(priority) as max_priority,
  MIN(created_at) as oldest
FROM workflow.human_review_queue
WHERE status = 'pending' AND priority >= 8

UNION ALL

SELECT
  'reviewed' as category,
  COUNT(*) as count,
  AVG(disagreement_score) as avg_disagreement,
  NULL as max_priority,
  MIN(reviewed_at) as oldest
FROM workflow.human_review_queue
WHERE status = 'reviewed'

UNION ALL

SELECT
  'dismissed' as category,
  COUNT(*) as count,
  AVG(disagreement_score) as avg_disagreement,
  NULL as max_priority,
  MIN(reviewed_at) as oldest
FROM workflow.human_review_queue
WHERE status = 'dismissed';

-- ============================================================================
-- MATERIALIZED VIEW REFRESH
-- ============================================================================

-- Refresh the summary materialized view (run periodically)
SELECT workflow.refresh_review_summary();

-- Query the summary view
SELECT * FROM workflow.review_queue_summary
ORDER BY status, disagreement_level;

-- ============================================================================
-- MAINTENANCE
-- ============================================================================

-- Clean up old dismissed reviews (older than 30 days)
DELETE FROM workflow.human_review_queue
WHERE status = 'dismissed'
  AND reviewed_at < NOW() - INTERVAL '30 days';

-- Archive old reviewed entries (move to archive table)
-- CREATE TABLE workflow.human_review_archive (LIKE workflow.human_review_queue INCLUDING ALL);
--
-- INSERT INTO workflow.human_review_archive
-- SELECT * FROM workflow.human_review_queue
-- WHERE status IN ('reviewed', 'resolved', 'dismissed')
--   AND reviewed_at < NOW() - INTERVAL '90 days';
--
-- DELETE FROM workflow.human_review_queue
-- WHERE status IN ('reviewed', 'resolved', 'dismissed')
--   AND reviewed_at < NOW() - INTERVAL '90 days';
