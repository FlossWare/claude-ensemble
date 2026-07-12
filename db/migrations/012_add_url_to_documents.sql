-- Migration 012: Add URL tracking to knowledge schema
-- Adds url column to documents table for web scraping integration
-- Author: Integration Test Infrastructure
-- Date: 2026-07-11

BEGIN;

-- Add url column to knowledge.documents (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'knowledge'
        AND table_name = 'documents'
        AND column_name = 'url'
    ) THEN
        ALTER TABLE knowledge.documents ADD COLUMN url TEXT;
        CREATE INDEX idx_documents_url ON knowledge.documents(url);
    END IF;
END $$;

-- Add title column to knowledge.documents (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'knowledge'
        AND table_name = 'documents'
        AND column_name = 'title'
    ) THEN
        ALTER TABLE knowledge.documents ADD COLUMN title TEXT;
    END IF;
END $$;

-- Add fetched_at column to knowledge.documents (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'knowledge'
        AND table_name = 'documents'
        AND column_name = 'fetched_at'
    ) THEN
        ALTER TABLE knowledge.documents ADD COLUMN fetched_at TIMESTAMP;
        CREATE INDEX idx_documents_fetched_at ON knowledge.documents(fetched_at);
    END IF;
END $$;

-- Add content_hash column to knowledge.documents (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'knowledge'
        AND table_name = 'documents'
        AND column_name = 'content_hash'
    ) THEN
        ALTER TABLE knowledge.documents ADD COLUMN content_hash TEXT;
        CREATE UNIQUE INDEX idx_documents_content_hash ON knowledge.documents(content_hash);
    END IF;
END $$;

COMMIT;

-- Verify migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 012 completed successfully';
    RAISE NOTICE 'Added columns: url, title, fetched_at, content_hash to knowledge.documents';
END $$;
