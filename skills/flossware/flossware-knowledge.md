---
name: flossware-knowledge
description: FlossWare knowledge ingestion and processing pipeline conventions — scraping, chunking, embedding, graph
tags: [flossware, knowledge, pipeline, rag, embeddings]
---

# FlossWare Knowledge

Knowledge ingestion and processing conventions for the FlossWare ecosystem. Use this skill when working with the knowledge pipeline — scraping, storage, chunking, embedding, or graph processing.

## Activation

Use when:
- Building or modifying scrapers
- Working with the knowledge pipeline stages (store, chunk, embed)
- Designing or querying vector search
- Working with the OrientDB knowledge graph
- Troubleshooting pipeline processing

## Before You Act

1. **Read the canonical pipeline docs** in `FlossWare/.github/docs/knowledge/`:
   - `scraping.md` — BaseScraper pattern, fleet distribution, rate limiting
   - `chunking.md` — SemanticChunker, boundary detection, overlap, storage schema
   - `embeddings.md` — all-mpnet-base-v2, HNSW indexing, compute isolation, fallback
   - `graph.md` — triple-store architecture, OrientDB node/edge types, graph sync
2. **Read the architecture sections** in `FlossWare/.github/ARCHITECTURE.md`, sections 9-11 (Knowledge Pipeline, Vector Search, Database Architecture)
3. **Check the current implementation** before proposing changes. The pipeline design is documented in the `.github` repo; the running implementation lives in the personal orchestrator infrastructure on `aio-01`, not in any FlossWare GitHub repository. Verify what actually exists before citing specifics.

## Pipeline Architecture

```
Scrape (fleet workers)
   |
   POST /queue/enqueue
   |
   v
Redis store queue --> Store worker --> PostgreSQL knowledge.documents
                                          |
                                    Redis chunk queue
                                          |
                                          v
                                    Chunk worker --> knowledge.chunks
                                          |
                                    Embed worker --> knowledge.embeddings (pgvector)
                                          |
                                    Graph sync --> OrientDB (RELATED_TO edges)
```

### Stage Responsibilities

| Stage | Bound By | Runs On | Output |
|---|---|---|---|
| Scrape | Network + rate limit | Fleet workers (never controller) | JSON docs to disk + Redis queue |
| Store | I/O | Any node via REST API | `knowledge.documents` rows |
| Chunk | CPU (light) | Any node | `knowledge.chunks` rows |
| Embed | CPU (heavy) | Dedicated compute nodes only | `knowledge.embeddings` (768-dim vectors) |
| Graph sync | Network | Controller | OrientDB nodes + edges |

## Scraper Conventions (per `.github/docs/knowledge/scraping.md`)

- BaseScraper pattern: subclass, define sources, implement `scrape()`, call `save_item()`
- Rate limit: 1.0-1.5 seconds between fetches per domain
- Max content: 50,000 characters per document
- Deduplication: content hash on disk, `(url, source)` uniqueness in database
- Scrapers run on fleet workers, never on the controller
- Workers enqueue results via the REST API — they never write directly to PostgreSQL
- For implementation details (file paths, class names), read the canonical docs rather than assuming from this skill

## Chunking Conventions (per `.github/docs/knowledge/chunking.md`)

- Semantic splitting at natural boundaries (paragraph, heading, function/class)
- Chunk sizes: 500-1500 characters (min/max), 100 character overlap
- Code detection: 30%+ code-indicator lines triggers code-aware splitting
- Streaming and batch interfaces available
- 10MB max document size
- Storage: `knowledge.chunks` with `(document_id, chunk_index)` uniqueness

## Embedding Conventions

- Model: `sentence-transformers/all-mpnet-base-v2` (768 dimensions)
- Different dimensions for different data types:
  - Experiences: 128-dim (`learning.experiences`)
  - Workflows: 384-dim (`workflow.executions`)
  - Knowledge chunks: 768-dim (`knowledge.embeddings`)
- Compute isolation: embedding generation runs only on dedicated compute nodes, never on fleet workers
- Fallback chain: local sentence-transformers -> REST API -> hash-based fallback (tagged `provider="fallback"`)
- Batch size: 50 chunks per inference batch
- Input truncation: 8,000 characters
- HNSW index for approximate nearest-neighbor search

## Graph Conventions

- Triple-store: PostgreSQL (structured + vector) + Redis (queues) + OrientDB (graph)
- OrientDB node types: Infrastructure, Workflows, Models, Documents
- Edge types: EXECUTED_ON, USED_MODEL, DEPENDS_ON, CONNECTED_TO, JUDGED_BY, COMPLETED_WITH, RELATED_TO
- RELATED_TO edges computed from vector similarity (cosine > 0.85 threshold)
- Graph sync is non-blocking — OrientDB failures never break the pipeline
- PostgreSQL recursive CTEs provide fallback graph queries when OrientDB is unavailable
- Graph queries exposed via `POST /graph/query`

## Provenance

Every piece of knowledge must trace back to its source:
- Documents have source URLs and scraper identifiers
- Chunks reference their parent document via `document_id`
- Embeddings reference their chunk via `chunk_id` with cascade delete
- Graph edges encode the relationship type and direction

## Do Not

- Run embedding generation on fleet workers (compute isolation is a hard constraint)
- Have scrapers or workers write directly to PostgreSQL (use the REST API)
- Skip deduplication (content hashing and database uniqueness constraints exist for a reason)
- Redesign the pipeline stages without first understanding the current throughput characteristics (the decoupled design provides significant throughput improvement over monolithic processing — see `scraping.md` for details)
- Remove the OrientDB fallback to PostgreSQL CTEs — the graph database is an optimization, not a hard dependency
- Introduce new embedding dimensions without documenting the rationale
