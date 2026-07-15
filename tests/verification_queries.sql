-- Database Verification Queries
-- Execute on aio-01:5433/learning after test runs

-- ============================================================================
-- DOCUMENT VERIFICATION
-- ============================================================================

-- 1. Check total documents ingested
SELECT
    document_type,
    COUNT(*) as total_documents,
    SUM(total_chunks) as total_chunks,
    AVG(total_chunks) as avg_chunks_per_doc
FROM ingestion.research_documents
GROUP BY document_type
ORDER BY total_documents DESC;

-- Expected: pdf=1, text=1, code=1 (from api_test_script.sh)

-- 2. Verify document metadata completeness
SELECT
    id,
    document_type,
    title,
    author,
    source,
    tags,
    processing_status,
    total_chunks,
    created_at,
    completed_at
FROM ingestion.research_documents
WHERE source LIKE '%test%'
ORDER BY created_at DESC
LIMIT 10;

-- Expected: All test documents with complete metadata

-- 3. Check for processing errors
SELECT
    id,
    document_type,
    title,
    processing_status,
    processing_error
FROM ingestion.research_documents
WHERE processing_status = 'failed'
ORDER BY created_at DESC;

-- Expected: 0 rows (no failures)

-- ============================================================================
-- CHUNK VERIFICATION
-- ============================================================================

-- 4. Verify all chunks have embeddings
SELECT
    d.document_type,
    COUNT(*) as total_chunks,
    SUM(CASE WHEN c.embedding IS NULL THEN 1 ELSE 0 END) as missing_embeddings,
    AVG(c.char_count) as avg_chunk_size
FROM ingestion.document_chunks c
JOIN ingestion.research_documents d ON c.document_id = d.id
GROUP BY d.document_type;

-- Expected: missing_embeddings = 0 for all document types

-- 5. Check chunk content quality
SELECT
    c.id,
    c.chunk_index,
    c.char_count,
    c.has_code,
    c.language,
    c.chunk_type,
    LEFT(c.content, 100) as content_preview
FROM ingestion.document_chunks c
JOIN ingestion.research_documents d ON c.document_id = d.id
WHERE d.source LIKE '%e2e_test%'
ORDER BY c.chunk_index
LIMIT 5;

-- Expected: Chunks with DFS content, char_count between 500-1500

-- 6. Verify chunk overlaps
SELECT
    document_id,
    chunk_index,
    LENGTH(overlap_prefix) as prefix_len,
    LENGTH(overlap_suffix) as suffix_len
FROM ingestion.document_chunks
WHERE LENGTH(overlap_prefix) > 0 OR LENGTH(overlap_suffix) > 0
ORDER BY document_id, chunk_index
LIMIT 10;

-- Expected: overlap_prefix and overlap_suffix populated for adjacent chunks

-- ============================================================================
-- EMBEDDING VERIFICATION
-- ============================================================================

-- 7. Check embedding dimensions
SELECT
    document_id,
    chunk_index,
    vector_dims(embedding) as embedding_dimensions
FROM ingestion.document_chunks
WHERE embedding IS NOT NULL
LIMIT 5;

-- Expected: embedding_dimensions = 384 (all-mpnet-base-v2 model)

-- 8. Test similarity search (DFS query)
SELECT
    c.id,
    c.content,
    1 - (c.embedding <=> '[0.1, 0.2, ...]'::vector) as similarity_score
FROM ingestion.document_chunks c
JOIN ingestion.research_documents d ON c.document_id = d.id
WHERE d.tags && ARRAY['dfs', 'radar']
ORDER BY c.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;

-- Note: Replace [0.1, 0.2, ...] with actual query embedding

-- 9. Verify HNSW index exists and is used
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    c.id,
    1 - (c.embedding <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM ingestion.document_chunks c
ORDER BY c.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- Expected: "Index Scan using document_chunks_embedding_idx"

-- ============================================================================
-- DEDUPLICATION VERIFICATION
-- ============================================================================

-- 10. Check for duplicate file hashes
SELECT
    file_hash,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(title) as titles
FROM ingestion.research_documents
WHERE file_hash IS NOT NULL
GROUP BY file_hash
HAVING COUNT(*) > 1;

-- Expected: 0 rows (no duplicates)

-- 11. Verify deduplication tracking
SELECT
    file_hash,
    document_type,
    title,
    created_at
FROM ingestion.research_documents
WHERE file_hash = (
    SELECT file_hash
    FROM ingestion.research_documents
    WHERE title LIKE '%DFS%'
    LIMIT 1
);

-- Expected: Single document with unique hash

-- ============================================================================
-- AUTOSTORAGE SESSION VERIFICATION
-- ============================================================================

-- 12. Check session chunks stored
SELECT
    session_id,
    COUNT(*) as chunk_count,
    SUM(char_count) as total_chars,
    AVG(quality_score) as avg_quality,
    BOOL_OR(has_code) as contains_code
FROM learning.session_chunks
WHERE session_id LIKE 'e2e%' OR session_id LIKE 'test%'
GROUP BY session_id;

-- Expected: Session chunks with quality_score >= 0.7

-- 13. Verify model tuning extraction
SELECT
    model,
    task_type,
    avg_quality,
    avg_cost_usd,
    avg_duration_ms,
    sample_count,
    updated_at
FROM monitoring.model_tuning
WHERE updated_at > NOW() - INTERVAL '1 day'
ORDER BY sample_count DESC;

-- Expected: Recent model performance data

-- 14. Check procedural rules extraction
SELECT
    condition_hash,
    action,
    confidence,
    evidence_count,
    last_updated
FROM learning.procedural_rules
WHERE last_updated > NOW() - INTERVAL '1 day'
ORDER BY confidence DESC
LIMIT 10;

-- Expected: Procedural patterns extracted from sessions

-- ============================================================================
-- API AUTHENTICATION VERIFICATION
-- ============================================================================

-- 15. Check API key usage
SELECT
    k.key_prefix,
    k.scopes,
    k.is_active,
    k.last_used_at,
    k.failed_auth_count,
    k.rate_limit_per_minute
FROM auth.api_keys k
WHERE k.last_used_at > NOW() - INTERVAL '1 hour'
ORDER BY k.last_used_at DESC;

-- Expected: Test API keys with recent usage, failed_auth_count = 0

-- 16. Verify rate limiting
SELECT
    key_prefix,
    COUNT(*) as total_requests,
    MAX(last_used_at) as last_request,
    rate_limit_per_minute
FROM auth.api_keys
WHERE last_used_at > NOW() - INTERVAL '10 minutes'
GROUP BY key_prefix, rate_limit_per_minute;

-- Expected: Request counts within rate limits

-- ============================================================================
-- PERFORMANCE METRICS
-- ============================================================================

-- 17. Check embedding generation performance
SELECT
    COUNT(*) as total_chunks,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_seconds
FROM ingestion.document_chunks
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Expected: avg_processing_seconds < 5 (background processing efficient)

-- 18. Search performance analysis
SELECT
    COUNT(*) as total_searches,
    AVG(query_time_ms) as avg_query_ms,
    MAX(query_time_ms) as max_query_ms
FROM (
    -- Simulated search query for performance testing
    SELECT 1 as query_time_ms
) AS search_log;

-- Note: Replace with actual search log table if available

-- 19. Database size and growth
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as indexes_size
FROM pg_tables
WHERE schemaname IN ('ingestion', 'learning', 'auth')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Expected: Reasonable sizes with indexes ~30-50% of table size

-- ============================================================================
-- SECURITY VERIFICATION
-- ============================================================================

-- 20. Check for SQL injection attempts in logs
SELECT
    id,
    content,
    created_at
FROM ingestion.document_chunks
WHERE content LIKE '%DROP TABLE%'
   OR content LIKE '%DELETE FROM%'
   OR content LIKE '%UNION SELECT%';

-- Expected: 0 rows (SQL injection blocked)

-- 21. Verify path traversal protection
SELECT
    original_filename,
    file_hash
FROM ingestion.research_documents
WHERE original_filename LIKE '%../%'
   OR original_filename LIKE '%etc/passwd%';

-- Expected: 0 rows (path traversal blocked)

-- 22. Check for firmware upload attempts
SELECT
    id,
    mime_type,
    original_filename,
    processing_status,
    processing_error
FROM ingestion.research_documents
WHERE mime_type = 'application/octet-stream'
   OR processing_error LIKE '%firmware%';

-- Expected: Rows with processing_status='failed' and error='firmware detected'

-- ============================================================================
-- DATA QUALITY VERIFICATION
-- ============================================================================

-- 23. Check tag distribution
SELECT
    tag,
    COUNT(*) as document_count
FROM (
    SELECT UNNEST(tags) as tag
    FROM ingestion.research_documents
) AS tag_list
GROUP BY tag
ORDER BY document_count DESC
LIMIT 20;

-- Expected: Common tags like 'dfs', 'radar', 'test' with counts

-- 24. Verify metadata completeness
SELECT
    CASE
        WHEN title IS NULL THEN 'missing_title'
        WHEN author IS NULL THEN 'missing_author'
        WHEN source IS NULL THEN 'missing_source'
        WHEN ARRAY_LENGTH(tags, 1) IS NULL THEN 'missing_tags'
        ELSE 'complete'
    END as metadata_status,
    COUNT(*) as count
FROM ingestion.research_documents
GROUP BY metadata_status;

-- Expected: Majority 'complete', some 'missing_author' acceptable

-- 25. Final health check
SELECT
    'Documents' as metric,
    COUNT(*) as total,
    SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed,
    SUM(CASE WHEN processing_status = 'processing' THEN 1 ELSE 0 END) as processing
FROM ingestion.research_documents

UNION ALL

SELECT
    'Chunks',
    COUNT(*),
    SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END),
    0,
    SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END)
FROM ingestion.document_chunks;

-- Expected: All documents completed, all chunks with embeddings
