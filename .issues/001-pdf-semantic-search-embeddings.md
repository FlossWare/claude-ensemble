# Add embeddings to PDF knowledge base for semantic search

**Status:** Open  
**Priority:** High  
**Created:** 2026-07-04  

## Goal

Enable semantic search over the 849 PDFs in the knowledge base using vector embeddings.

## Context

Currently PDFs are stored in PostgreSQL with text extraction and in Neo4j with topic/category relationships. Semantic search would enable finding relevant PDFs by meaning, not just keywords.

## Implementation

- Generate embeddings for PDF text using Cloudflare Workers AI or Mistral Embed API (both free)
- Store 384-dim or 768-dim vectors in PostgreSQL pgvector
- Create similarity search function
- Add to Neo4j sync for graph-aware semantic queries

## Benefits

- "Find PDFs similar to this query" (semantic matching)
- "What do I have about distributed systems?" (conceptual search)
- Better than keyword matching for technical concepts

## Related

- PDFs already extracted: `learning.pdf_metadata` (243/849 complete as of 2026-07-04)
- Neo4j sync: `shared/neo4j-realtime-sync.cjs`
- Existing embeddings: `learning.consciousness_research` uses 768-dim vectors

## Acceptance Criteria

- [ ] Embeddings generated for all PDF text
- [ ] Semantic search API/function created
- [ ] Query: "Find PDFs about container orchestration" returns relevant results
- [ ] Performance: <100ms for similarity search
