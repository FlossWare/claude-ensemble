# PDF Library Assistant

Semantic search and recommendations for your 843-PDF technical library using vector embeddings.

## Quick Start

```bash
# Search for PDFs by topic
./scripts/library-recommend "kubernetes networking"

# Interactive mode
./scripts/library-recommend --interactive
```

## Architecture

```
┌─────────────────────────────────────────┐
│  PostgreSQL (aio-01:5433)               │
│  ├─ learning.pdf_metadata               │
│  │  ├─ 843 PDFs                         │
│  │  ├─ 384-dim embeddings (pgvector)    │
│  │  └─ Full-text previews               │
│  └─ HNSW index for O(log n) search      │
└─────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  Semantic Search (shared/semantic-search.js) │
│  ├─ Query embedding generation          │
│  ├─ Cosine similarity search            │
│  └─ Filtering by category               │
└─────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  CLI Tool (scripts/library-recommend)   │
│  ├─ Interactive & batch mode            │
│  ├─ Top-10 results table                │
│  └─ Detailed top recommendation         │
└─────────────────────────────────────────┘
```

## Usage Examples

### Basic Search

```bash
./scripts/library-recommend "docker container security"
```

Output:
```
🔍 Searching for: "docker container security"

Found 10 relevant PDFs:

Rank | Similarity | PDF
-----|------------|------------------------------------------------------------
1.   | 87.3%      | Container_Security_Guide.pdf
2.   | 82.1%      | Docker_Best_Practices.pdf
3.   | 76.5%      | Kubernetes_Security.pdf
...

📖 Top recommendation:

  Container_Security_Guide.pdf
  Similarity: 87.3%
  Length: 145k chars
  Preview: Container security involves multiple layers...
  Path: /mnt/nas/media/books/Container_Security_Guide.pdf
```

### Interactive Mode

```bash
./scripts/library-recommend

📚 PDF Library Assistant
Enter your question or topic:

> how do I optimize database queries

🔍 Searching for: "how do I optimize database queries"
...
```

## JavaScript API

```javascript
const { semanticSearch, findByTopic, findSimilar } = require('./shared/semantic-search.js');

// Basic search
const results = await semanticSearch("machine learning basics", { topK: 5 });

// Filter by category
const filtered = await semanticSearch("python tutorial", {
  topK: 10,
  category: "programming"
});

// Find similar PDFs
const similar = await findSimilar("/mnt/nas/media/books/some_book.pdf", 5);
```

## How It Works

### 1. Embedding Generation

Each PDF's text is converted to a 384-dimensional vector using:
- **Production**: Cloudflare Workers AI (`@cf/baai/bge-small-en-v1.5`)
- **Fallback**: SHA-256 hash-based embedding (for testing)

```python
# From tools/generate_pdf_embeddings.py
embedding = generate_embedding(text[:2048])  # First 2KB
```

### 2. Vector Storage

Embeddings stored in PostgreSQL with pgvector extension:

```sql
CREATE TABLE learning.pdf_metadata (
    id SERIAL PRIMARY KEY,
    pdf_path TEXT NOT NULL,
    text_preview TEXT,
    text_length INTEGER,
    embedding vector(384),
    processed_at TIMESTAMP
);

CREATE INDEX ON learning.pdf_metadata 
USING hnsw (embedding vector_cosine_ops);
```

### 3. Similarity Search

Uses cosine distance (`<=>` operator) for fast nearest-neighbor search:

```sql
SELECT pdf_path, 
       1 - (embedding <=> $query_embedding) as similarity
FROM learning.pdf_metadata
ORDER BY embedding <=> $query_embedding
LIMIT 10;
```

**Performance**: ~0.4ms per query (HNSW index)

## Advanced Features

### Category Filtering

```javascript
await semanticSearch("REST API design", {
  topK: 10,
  category: "webdev"  // Filters by path: %/webdev/%
});
```

### Find Similar Documents

```javascript
// "More like this" functionality
const similar = await findSimilar(
  "/mnt/nas/media/books/Kubernetes_Guide.pdf",
  5  // Top 5 similar
);
```

## Database Stats

```bash
# Check embedding coverage
psql -h aio-01 -p 5433 -U claude learning -c "
  SELECT 
    COUNT(*) as total,
    COUNT(embedding) as with_embeddings,
    COUNT(*) FILTER (WHERE embedding IS NULL) as missing
  FROM learning.pdf_metadata;
"
```

Current: **843/843 PDFs** with embeddings (100%)

## Integration with Neo4j

All PDFs also synced to Neo4j knowledge graph:

```cypher
// Find PDFs and their topics
MATCH (p:PDFDocument)-[:HAS_TOPIC]->(t:Topic)
WHERE t.name = "Kubernetes"
RETURN p.path, p.filename
```

## Troubleshooting

### No results returned

```bash
# Check database connectivity
psql -h aio-01 -p 5433 -U claude learning -c "SELECT COUNT(*) FROM learning.pdf_metadata WHERE embedding IS NOT NULL;"
```

### Slow queries

```bash
# Verify HNSW index exists
psql -h aio-01 -p 5433 -U claude learning -c "\d learning.pdf_metadata"
```

## Future Enhancements

- **Learning Path Builder**: Multi-PDF sequences ordered by difficulty
- **Recommendation API**: REST endpoint with context-aware suggestions
- **Workflow Integration**: Auto-suggest PDFs based on current task
- **Chat Interface**: Conversational library assistant

## Files

- `shared/semantic-search.js` - Core search logic
- `scripts/library-recommend` - CLI tool
- `tools/generate_pdf_embeddings.py` - Embedding generation
- `docs/LIBRARY_ASSISTANT.md` - This file

## Related Documentation

- [PostgreSQL + pgvector Setup](../CLAUDE.md#continual-learning-infrastructure-2026-06-15)
- [Neo4j Knowledge Graph](../shared/neo4j-realtime-sync.cjs)
- [PDF Processing Pipeline](../tools/generate_pdf_embeddings.py)
