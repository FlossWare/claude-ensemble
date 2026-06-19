-- Workflow Embeddings Retention Policy
-- Deletes embeddings older than specified days while preserving metadata
-- HNSW index overhead: 2× storage (embeddings = 50% of total size)

CREATE OR REPLACE FUNCTION learning.cleanup_old_workflow_embeddings(
  retention_days INTEGER DEFAULT 90
) RETURNS TABLE (
  deleted_count BIGINT,
  freed_mb NUMERIC
) AS $$
DECLARE
  v_deleted_count BIGINT;
  v_freed_mb NUMERIC;
  v_cutoff_date TIMESTAMP;
BEGIN
  v_cutoff_date := NOW() - (retention_days || ' days')::INTERVAL;

  -- Calculate size before deletion (approximate)
  SELECT COUNT(*) INTO v_deleted_count
  FROM learning.workflow_completions
  WHERE completed_at < v_cutoff_date
    AND embedding IS NOT NULL;

  -- Estimate freed space (768-dim vector = 3KB + 3KB HNSW index = 6KB per row)
  v_freed_mb := (v_deleted_count * 6.0) / 1024.0;

  -- Delete embeddings (keep metadata)
  UPDATE learning.workflow_completions
  SET embedding = NULL,
      embedding_cleared_at = NOW()
  WHERE completed_at < v_cutoff_date
    AND embedding IS NOT NULL;

  RETURN QUERY SELECT v_deleted_count, v_freed_mb;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION learning.cleanup_old_workflow_embeddings TO postgres;

COMMENT ON FUNCTION learning.cleanup_old_workflow_embeddings IS
'Clears embeddings older than retention_days (default 90) while preserving metadata.
Returns deleted_count and freed_mb. Run daily at 3 AM via cron.';
