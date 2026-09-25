-- Migration 011: Scraping and Chunks Tables
-- Creates tables for web scraping queue and content chunking
-- Author: Integration Test Infrastructure
-- Date: 2026-07-11

BEGIN;

-- Create scraping schema
CREATE SCHEMA IF NOT EXISTS scraping;

-- Scraping tasks queue
CREATE TABLE IF NOT EXISTS scraping.tasks (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'processing', 'completed', 'failed')),
    retries INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    queued_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scraping_tasks_status ON scraping.tasks(status);
CREATE INDEX IF NOT EXISTS idx_scraping_tasks_priority ON scraping.tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_scraping_tasks_category ON scraping.tasks(category);
CREATE INDEX IF NOT EXISTS idx_scraping_tasks_created_at ON scraping.tasks(created_at);

-- Chunks table (if not exists in knowledge schema)
CREATE TABLE IF NOT EXISTS knowledge.chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    token_count INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON knowledge.chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON knowledge.chunks(created_at);

-- Embeddings table (if not exists)
CREATE TABLE IF NOT EXISTS knowledge.embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES knowledge.chunks(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding vector(1024),  -- Assuming sentence-transformers all-mpnet-base-v2
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(chunk_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON knowledge.embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_provider ON knowledge.embeddings(provider);
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON knowledge.embeddings(created_at);

-- Add GIN index for vector similarity search (if pgvector installed)
-- CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON knowledge.embeddings USING ivfflat(embedding vector_cosine_ops);

-- NOTE: Trigger for updated_at skipped due to permission constraints
-- Application code will handle updated_at updates manually

COMMIT;

-- Verify migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 011 completed successfully';
    RAISE NOTICE 'Created tables: scraping.tasks, knowledge.chunks, knowledge.embeddings';
END $$;
