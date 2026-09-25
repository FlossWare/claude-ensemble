-- Fact Storage Schema
-- PostgreSQL + pgvector for structured fact extraction and retrieval
-- Stores subject-predicate-object triples extracted from documents
--
-- Usage:
--   psql -h aio-01 -p 5433 -U $USER -d learning -f fact-storage-schema.sql

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create facts schema
CREATE SCHEMA IF NOT EXISTS facts;

-- Primary facts table: stores extracted SPO triples with source provenance
CREATE TABLE IF NOT EXISTS facts.facts (
    id SERIAL PRIMARY KEY,

    -- Source document reference
    document_id VARCHAR(128) NOT NULL,
    document_title VARCHAR(512),

    -- The raw fact as extracted
    fact_text TEXT NOT NULL,

    -- Structured triple decomposition
    subject VARCHAR(512) NOT NULL,
    predicate VARCHAR(512) NOT NULL,
    object VARCHAR(512) NOT NULL,

    -- Embedding for semantic similarity search (1024-dim)
    fact_embedding vector(1024),

    -- Confidence and provenance
    confidence REAL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    extraction_model VARCHAR(64),
    extraction_method VARCHAR(64) DEFAULT 'llm',

    -- Categorization
    domain VARCHAR(128),
    tags TEXT[] DEFAULT '{}',

    -- Metadata (arbitrary JSON for extension)
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for document lookups
CREATE INDEX IF NOT EXISTS idx_facts_document_id
ON facts.facts(document_id);

-- Index for subject lookups (knowledge graph traversal)
CREATE INDEX IF NOT EXISTS idx_facts_subject
ON facts.facts(subject);

-- Index for predicate lookups
CREATE INDEX IF NOT EXISTS idx_facts_predicate
ON facts.facts(predicate);

-- Index for object lookups (reverse graph traversal)
CREATE INDEX IF NOT EXISTS idx_facts_object
ON facts.facts(object);

-- Composite index for full triple lookups
CREATE INDEX IF NOT EXISTS idx_facts_spo
ON facts.facts(subject, predicate, object);

-- Index for semantic similarity search (HNSW for better recall than IVFFlat)
CREATE INDEX IF NOT EXISTS idx_facts_embedding
ON facts.facts USING hnsw (fact_embedding vector_cosine_ops);

-- Index for domain filtering
CREATE INDEX IF NOT EXISTS idx_facts_domain
ON facts.facts(domain);

-- Index for tag filtering (GIN for array containment)
CREATE INDEX IF NOT EXISTS idx_facts_tags
ON facts.facts USING gin (tags);

-- Index for temporal queries
CREATE INDEX IF NOT EXISTS idx_facts_created_at
ON facts.facts(created_at DESC);

-- Index for metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_facts_metadata
ON facts.facts USING gin (metadata);

-- Materialized view: fact counts per document
CREATE MATERIALIZED VIEW IF NOT EXISTS facts.document_summary AS
SELECT
    document_id,
    document_title,
    COUNT(*) AS fact_count,
    AVG(confidence) AS avg_confidence,
    array_agg(DISTINCT domain) FILTER (WHERE domain IS NOT NULL) AS domains,
    MIN(created_at) AS first_extracted,
    MAX(created_at) AS last_extracted
FROM facts.facts
GROUP BY document_id, document_title;

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_summary_id
ON facts.document_summary(document_id);

-- Materialized view: predicate frequency (useful for schema discovery)
CREATE MATERIALIZED VIEW IF NOT EXISTS facts.predicate_summary AS
SELECT
    predicate,
    COUNT(*) AS usage_count,
    COUNT(DISTINCT document_id) AS document_count,
    COUNT(DISTINCT subject) AS unique_subjects,
    COUNT(DISTINCT object) AS unique_objects
FROM facts.facts
GROUP BY predicate
ORDER BY usage_count DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_predicate_summary_predicate
ON facts.predicate_summary(predicate);

-- Auto-refresh function for materialized views
-- Call: SELECT facts.refresh_views();
CREATE OR REPLACE FUNCTION facts.refresh_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY facts.document_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY facts.predicate_summary;
END;
$$ LANGUAGE plpgsql;

-- Example queries:
--
-- 1. All facts from a document:
-- SELECT fact_text, subject, predicate, object, confidence
-- FROM facts.facts
-- WHERE document_id = 'doc-123'
-- ORDER BY created_at;
--
-- 2. Knowledge graph traversal (find all facts about a subject):
-- SELECT predicate, object, confidence
-- FROM facts.facts
-- WHERE subject = 'PostgreSQL'
-- ORDER BY confidence DESC;
--
-- 3. Semantic similarity search:
-- SELECT fact_text, subject, predicate, object,
--        1 - (fact_embedding <=> $1::vector) AS similarity
-- FROM facts.facts
-- ORDER BY fact_embedding <=> $1::vector
-- LIMIT 10;
--
-- 4. Facts by domain with minimum confidence:
-- SELECT fact_text, subject, predicate, object
-- FROM facts.facts
-- WHERE domain = 'networking' AND confidence >= 0.8
-- ORDER BY confidence DESC;
--
-- 5. Find related entities (graph walk):
-- WITH RECURSIVE related AS (
--   SELECT object AS entity, 1 AS depth
--   FROM facts.facts
--   WHERE subject = 'Linux' AND predicate = 'runs_on'
--   UNION
--   SELECT f.object, r.depth + 1
--   FROM facts.facts f
--   JOIN related r ON f.subject = r.entity
--   WHERE r.depth < 3
-- )
-- SELECT DISTINCT entity, depth FROM related ORDER BY depth;
