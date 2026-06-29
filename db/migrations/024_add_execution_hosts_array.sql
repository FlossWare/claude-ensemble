-- Migration: Add execution_hosts array to workflow.executions
-- Purpose: Track all fleet nodes that participated in a workflow execution
-- Semantics: execution_host (worker_results) is the actual host that ran each task
--            execution_hosts (executions) is aggregated array of unique hosts
-- Author: Database schema enhancement
-- Date: 2026-06-28

BEGIN;

-- Add execution_hosts array to executions
ALTER TABLE workflow.executions
ADD COLUMN IF NOT EXISTS execution_hosts TEXT[];

-- Add index for efficient host-based queries
CREATE INDEX IF NOT EXISTS idx_executions_execution_hosts
ON workflow.executions USING GIN(execution_hosts);

-- Add comment for documentation
COMMENT ON COLUMN workflow.executions.execution_hosts IS
'Array of unique hostname(s) of fleet nodes that executed workers for this workflow (aggregated from worker_results.execution_host)';

COMMIT;
