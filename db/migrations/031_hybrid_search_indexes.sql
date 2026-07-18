-- Migration: Add indexes for hybrid search (semantic + keyword + RRF)
-- Date: 2026-07-18
-- Purpose: Enable fast hybrid search over knowledge.chunks (705K+ rows)
--
-- This migration adds:
-- 1. GIN index on knowledge.chunks.tsv for full-text search
-- 2. HNSW index on knowledge.embeddings.embedding for vector search
-- 3. Backfills tsv column for rows where it's NULL
--
-- The tsv column is auto-populated by the existing trigger:
--   chunks_tsv_update BEFORE INSERT OR UPDATE OF content
--   ON knowledge.chunks FOR EACH ROW
--   EXECUTE FUNCTION knowledge.chunks_tsv_trigger()
--
-- Prerequisites:
-- - pgvector extension (already installed)
-- - knowledge.chunks.tsv column exists (already exists)
-- - knowledge.chunks_tsv_trigger() function exists (already exists)

-- 1. GIN index for full-text search on tsvector column
CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON knowledge.chunks USING GIN (tsv);

-- 2. IVFFlat index for approximate nearest neighbor vector search
-- IVFFlat is faster to build than HNSW on constrained hardware
-- lists=100 is appropriate for ~700K vectors (sqrt(700K) ~ 837, 100 is a good balance)
SET maintenance_work_mem = '1GB';
CREATE INDEX IF NOT EXISTS idx_embeddings_ivfflat
    ON knowledge.embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
RESET maintenance_work_mem;

-- Optional: HNSW index provides better recall at the cost of slower build time
-- Uncomment if hardware allows (requires ~2GB+ maintenance_work_mem, 30+ min build time)
-- SET maintenance_work_mem = '2GB';
-- CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
--     ON knowledge.embeddings
--     USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);
-- RESET maintenance_work_mem;

-- 3. Backfill tsv for existing chunks where it's NULL
-- This uses the same logic as the trigger function
UPDATE knowledge.chunks
SET tsv = to_tsvector('english', COALESCE(content, ''))
WHERE tsv IS NULL;
