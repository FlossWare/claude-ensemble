-- Background Tasks Schema for Admin API
-- Database: learning (PostgreSQL on aio-01:5433)

-- Create admin schema
CREATE SCHEMA IF NOT EXISTS admin;

-- Background tasks tracking table
CREATE TABLE IF NOT EXISTS admin.background_tasks (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,           -- model_maintenance, chunking, vacuum
    status VARCHAR(20) NOT NULL,              -- pending, running, success, error
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT,                       -- Error details if status = error
    result_summary TEXT                       -- Brief summary of results
);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_background_tasks_status
ON admin.background_tasks(status);

-- Index for sorting by start time
CREATE INDEX IF NOT EXISTS idx_background_tasks_started
ON admin.background_tasks(started_at DESC);

-- Example queries

-- Get task status by job_id
-- SELECT * FROM admin.background_tasks WHERE job_id = '<uuid>';

-- List recent tasks
-- SELECT * FROM admin.background_tasks ORDER BY started_at DESC LIMIT 50;

-- List failed tasks
-- SELECT * FROM admin.background_tasks WHERE status = 'error' ORDER BY started_at DESC;

-- List running tasks
-- SELECT * FROM admin.background_tasks WHERE status = 'running' ORDER BY started_at DESC;

-- Count tasks by status
-- SELECT status, COUNT(*) FROM admin.background_tasks GROUP BY status;

-- Clean up old completed tasks (optional maintenance)
-- DELETE FROM admin.background_tasks
-- WHERE status IN ('success', 'error')
-- AND started_at < NOW() - INTERVAL '30 days';
