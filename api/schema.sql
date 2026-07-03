-- Document Ingestion API - PostgreSQL Schema
-- Database: learning (aio-01:5433)

-- ============================================================================
-- SCHEMA: auth (API key management)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_prefix VARCHAR(8) NOT NULL,  -- First 8 chars of API key for fast lookup
    key_hash TEXT NOT NULL,  -- bcrypt hash of full API key
    scopes TEXT[] NOT NULL DEFAULT '{}',  -- e.g., ARRAY['ingest:documents', 'query:embeddings']
    rate_limit_per_minute INT NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE (key_prefix),
    UNIQUE (key_hash)  -- Prevent duplicate API keys
);

CREATE INDEX idx_api_keys_prefix ON auth.api_keys(key_prefix) WHERE is_active = true;
CREATE INDEX idx_api_keys_active ON auth.api_keys(is_active);

-- ============================================================================
-- SCHEMA: documents (document storage)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS documents;

CREATE TABLE IF NOT EXISTS documents.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for deduplication
    file_name TEXT NOT NULL,
    file_type VARCHAR(50) NOT NULL,  -- pdf, image, text, firmware
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),

    -- Metadata
    source VARCHAR(100),  -- user_upload, api_import, filesystem_scan
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Processing status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    error_message TEXT,

    -- Constraints: completed status requires timestamp
    CONSTRAINT valid_completed_status CHECK (
        status != 'completed' OR processing_completed_at IS NOT NULL
    ),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (file_hash)
);

CREATE INDEX idx_documents_hash ON documents.documents(file_hash);
CREATE INDEX idx_documents_status ON documents.documents(status);
CREATE INDEX idx_documents_type ON documents.documents(file_type);
CREATE INDEX idx_documents_created ON documents.documents(created_at DESC);
CREATE INDEX idx_documents_tags ON documents.documents USING GIN(tags);

-- ============================================================================
-- SCHEMA: documents.chunks (chunked document content with embeddings)
-- ============================================================================

CREATE TABLE IF NOT EXISTS documents.chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,  -- Order within document

    -- Content
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 for deduplication

    -- Embedding
    embedding vector(384) NOT NULL,  -- sentence-transformers/all-MiniLM-L6-v2

    -- Metadata
    page_number INT,  -- For PDFs
    bounding_box JSONB,  -- For images/OCR: {x, y, width, height}
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON documents.chunks(document_id);
CREATE INDEX idx_chunks_hash ON documents.chunks(content_hash);

-- HNSW index for fast vector similarity search
CREATE INDEX idx_chunks_embedding ON documents.chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- SCHEMA: documents.processing_log (audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS documents.processing_log (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,

    -- Processing details
    stage VARCHAR(50) NOT NULL,  -- upload, validation, extraction, chunking, embedding
    status VARCHAR(20) NOT NULL,  -- success, error
    duration_ms INT,
    error_message TEXT,

    -- Metrics
    chunks_created INT,
    embeddings_generated INT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_processing_log_document ON documents.processing_log(document_id);
CREATE INDEX idx_processing_log_stage ON documents.processing_log(stage);
CREATE INDEX idx_processing_log_created ON documents.processing_log(created_at DESC);

-- ============================================================================
-- SCHEMA: monitoring (metrics and rate limiting)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.api_usage (
    id BIGSERIAL PRIMARY KEY,
    api_key_id UUID NOT NULL REFERENCES auth.api_keys(id),

    -- Request details
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INT NOT NULL,
    duration_ms INT,

    -- Resource usage
    file_size_bytes BIGINT,
    chunks_processed INT,
    embeddings_generated INT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_usage_key ON monitoring.api_usage(api_key_id);
CREATE INDEX idx_api_usage_endpoint ON monitoring.api_usage(endpoint);
CREATE INDEX idx_api_usage_created ON monitoring.api_usage(created_at DESC);

-- Rate limiting state (Redis Sentinel preferred, PostgreSQL fallback)
CREATE TABLE IF NOT EXISTS monitoring.rate_limit_state (
    api_key_id UUID PRIMARY KEY REFERENCES auth.api_keys(id),
    minute_window TIMESTAMPTZ NOT NULL,
    request_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents.documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Function to find similar documents by embedding
-- FIXED: Filter AFTER retrieval to use HNSW index efficiently
CREATE OR REPLACE FUNCTION documents.find_similar_chunks(
    query_embedding vector(384),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INT DEFAULT 10
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    similarity FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM (
        SELECT
            c.id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) AS similarity,
            c.metadata
        FROM documents.chunks c
        ORDER BY c.embedding <=> query_embedding
        LIMIT max_results * 2  -- Over-fetch to allow filtering
    ) subquery
    WHERE similarity >= similarity_threshold
    ORDER BY similarity DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MATERIALIZED VIEWS (refresh every 5 minutes)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.document_stats AS
SELECT
    file_type,
    status,
    COUNT(*) as document_count,
    SUM(file_size_bytes) as total_size_bytes,
    AVG(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at))) as avg_processing_seconds
FROM documents.documents
GROUP BY file_type, status;

CREATE UNIQUE INDEX idx_document_stats ON monitoring.document_stats(file_type, status);

-- Refresh materialized views (cron job: */5 * * * *)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.document_stats;

-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT USAGE ON SCHEMA auth TO sfloess;
GRANT USAGE ON SCHEMA documents TO sfloess;
GRANT USAGE ON SCHEMA monitoring TO sfloess;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA auth TO sfloess;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA documents TO sfloess;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA monitoring TO sfloess;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA auth TO sfloess;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA documents TO sfloess;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA monitoring TO sfloess;

-- ============================================================================
-- SAMPLE DATA (for testing)
-- ============================================================================

-- Generate API key (Python):
-- import secrets, bcrypt
-- api_key = secrets.token_urlsafe(32)
-- key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
-- print(f"API Key: {api_key}\nKey Prefix: {api_key[:8]}\nKey Hash: {key_hash}")

-- Example API key insertion:
-- INSERT INTO auth.api_keys (key_prefix, key_hash, scopes, rate_limit_per_minute)
-- VALUES ('AbCdEfGh', '$2b$12$...', ARRAY['ingest:documents'], 100);
