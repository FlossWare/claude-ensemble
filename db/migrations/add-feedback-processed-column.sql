-- Add 'processed' tracking to workflow.feedback table
-- This allows feedback-loop-automation to track which feedback has been applied to Thompson Sampling

DO $$
BEGIN
  -- Add processed column if it doesn't exist
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'workflow'
    AND table_name = 'feedback'
    AND column_name = 'processed'
  ) THEN
    ALTER TABLE workflow.feedback
    ADD COLUMN processed BOOLEAN DEFAULT FALSE,
    ADD COLUMN processed_at TIMESTAMP;

    COMMENT ON COLUMN workflow.feedback.processed IS 'Whether this feedback has been processed by feedback-loop-automation';
    COMMENT ON COLUMN workflow.feedback.processed_at IS 'Timestamp when feedback was processed';

    RAISE NOTICE 'Added processed columns to workflow.feedback';
  ELSE
    RAISE NOTICE 'Columns already exist, skipping migration';
  END IF;
END $$;
