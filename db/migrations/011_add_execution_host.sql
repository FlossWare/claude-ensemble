-- Migration: Add execution_host column to workflow.worker_results
-- Issue: #11 - Track which fleet node executed each agent
-- Author: Issue #11 implementation
-- Date: 2026-06-28

BEGIN;

-- Add execution_host column to worker_results
ALTER TABLE workflow.worker_results
ADD COLUMN IF NOT EXISTS execution_host VARCHAR(255);

-- Add index for efficient host-based queries
CREATE INDEX IF NOT EXISTS idx_worker_results_execution_host
ON workflow.worker_results(execution_host);

-- Add comment for documentation
COMMENT ON COLUMN workflow.worker_results.execution_host IS
'Hostname of the fleet node that executed this worker task (auto-captured via os.hostname())';

-- Update schema version
INSERT INTO workflow.schema_version (component, version)
VALUES ('worker_results', 2)
ON CONFLICT (component) DO UPDATE SET version = 2, applied_at = now();

COMMIT;
