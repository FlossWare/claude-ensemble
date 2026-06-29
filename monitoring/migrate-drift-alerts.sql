-- Migration script to add deduplication features to drift_alerts
-- Run as postgres user:
--   psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-drift-alerts.sql

-- Add deduplication tracking columns
ALTER TABLE monitoring.drift_alerts ADD COLUMN IF NOT EXISTS times_alerted INTEGER DEFAULT 1;
ALTER TABLE monitoring.drift_alerts ADD COLUMN IF NOT EXISTS last_alerted TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Create unique daily alert index for deduplication
CREATE UNIQUE INDEX IF NOT EXISTS idx_drift_alerts_unique_daily
ON monitoring.drift_alerts(model, COALESCE(task_type, ''), DATE(detection_date));

-- Summary
DO $$
BEGIN
    RAISE NOTICE '✅ Drift alerts migration complete';
    RAISE NOTICE '- Added times_alerted column (tracks duplicate alert count)';
    RAISE NOTICE '- Added last_alerted column (tracks last alert time)';
    RAISE NOTICE '- Created idx_drift_alerts_unique_daily index (prevents duplicates per day)';
END $$;

-- Show updated schema
\d monitoring.drift_alerts
