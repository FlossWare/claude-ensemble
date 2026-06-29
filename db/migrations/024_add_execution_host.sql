ALTER TABLE workflow.worker_results ADD COLUMN IF NOT EXISTS execution_host VARCHAR(64);
UPDATE workflow.worker_results SET execution_host = worker_id WHERE execution_host IS NULL;
ALTER TABLE workflow.executions ADD COLUMN IF NOT EXISTS execution_hosts TEXT[];
COMMENT ON COLUMN workflow.worker_results.execution_host IS 'Physical host that executed this worker task';
COMMENT ON COLUMN workflow.executions.execution_hosts IS 'Array of all physical hosts used in this workflow execution';
