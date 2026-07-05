# Universal Semantic Search

Search across **all** your content - PDFs, code, workflows, and documentation - using vector embeddings.

## Quick Start

```bash
# Search everything
./scripts/search-everything "kubernetes networking"

# Search only PDFs
./scripts/search-everything --type pdf "docker security"

# Search only code
./scripts/search-everything --type code "authentication middleware"

# Merged results (all types ranked together)
./scripts/search-everything --merged "database optimization"
```

## What Can You Search?

| Type | Description | Count | Status |
|------|-------------|-------|--------|
| **PDFs** | Technical books and papers | 843 | ✅ Indexed |
| **Code** | Source files (.js, .py, .sh, etc.) | 0 | ⏳ Ready to index |
| **Workflows** | AI workflow outputs | 0 | ⏳ Ready to index |
| **Docs** | Markdown documentation | 0 | ⏳ Ready to index |

## Index Your Codebase

```bash
# Index this project
./tools/index-codebase.js ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Index any repository
./tools/index-codebase.js /path/to/repo
```

**What gets indexed:**
- JavaScript (.js, .mjs, .cjs)
- TypeScript (.ts)
- Python (.py)
- Shell scripts (.sh)
- Java, Go, Rust, C/C++
- Markdown, JSON, YAML

**What gets skipped:**
- node_modules, .git, dist, build
- Binary files
- Files < 50 chars

## Usage Examples

### 1. Search All Content Types

```bash
./scripts/search-everything "how to implement REST API"
```

Output:
```
🔍 Searching for: "how to implement REST API"
   Types: pdf, code, workflow, docs
   Mode: grouped

======================================================================
📑 PDF (3 results)
======================================================================

1. RESTful_API_Design.pdf
   Similarity: 89.2%
   Path: /mnt/nas/media/books/RESTful_API_Design.pdf
   Preview: REST APIs provide a standard way to expose services...

2. Web_Services_Guide.pdf
   Similarity: 82.5%
   ...

======================================================================
📑 CODE (5 results)
======================================================================

1. api/library-assistant-api.js
   Similarity: 91.3%
   Path: /home/sfloess/.../api/library-assistant-api.js
   Preview: POST /api/library/recommend endpoint...

======================================================================
Total: 8 results across all types
```

### 2. Merged Results (Best Match Across All Types)

```bash
./scripts/search-everything --merged "authentication" --limit 10
```

Output:
```
Found 10 results:

Rank | Type     | Similarity | Title
-----|----------|------------|--------------------------------------------------
1.   | code     | 94.2%      | middleware/auth.js
2.   | pdf      | 91.8%      | OAuth2_Complete_Guide.pdf
3.   | code     | 88.5%      | routes/login.js
4.   | workflow | 85.3%      | implement-jwt-authentication
5.   | pdf      | 82.1%      | Web_Security_Essentials.pdf
...

📖 Top result:

  Type: code
  Title: middleware/auth.js
  Similarity: 94.2%
  Path: /home/sfloess/.../middleware/auth.js
  Preview: JWT authentication middleware with role-based...
```

### 3. Search Specific Content Type

```bash
# Only search code
./scripts/search-everything --type code "database connection pool"

# Only search PDFs
./scripts/search-everything --type pdf "machine learning algorithms"

# Only search workflows
./scripts/search-everything --type workflow "parallel processing"
```

## JavaScript API

```javascript
const { universalSearch, addToIndex } = require('./shared/universal-semantic-search.js');

// Search all types
const results = await universalSearch("kubernetes deployment", {
  topK: 5,
  types: ['pdf', 'code', 'workflow', 'docs'],
  mergeResults: false
});

// Search specific types
const codeOnly = await universalSearch("API endpoints", {
  topK: 10,
  types: ['code']
});

// Merged results
const merged = await universalSearch("security best practices", {
  topK: 20,
  mergeResults: true
});

// Add content to index
await addToIndex('code', {
  path: '/path/to/file.js',
  language: 'javascript',
  text: 'const express = require("express");...'
});

await addToIndex('docs', {
  path: '/path/to/doc.md',
  title: 'API Documentation',
  text: '# API Docs\n\nThis API provides...'
});
```

## Database Schema

### PDFs (Existing)
```sql
learning.pdf_metadata (
  id, pdf_path, text_preview, embedding vector(384)
)
```

### Code Files (Auto-created)
```sql
learning.code_embeddings (
  id, file_path, language, content_preview, embedding vector(384)
)
```

### Documentation (Auto-created)
```sql
learning.documentation_embeddings (
  id, doc_path, doc_title, content_preview, embedding vector(384)
)
```

### Workflows (Uses existing)
```sql
workflow.executions (
  workflow_id, workflow_name, task_description, embedding vector(384)
)
```

All tables have **HNSW indexes** for fast (~0.4ms) vector search.

## How It Works

### 1. Indexing

When you index content, it:
1. Reads file content
2. Generates 384-dim embedding (hash-based or Cloudflare AI)
3. Stores in PostgreSQL with pgvector
4. Creates HNSW index for fast search

### 2. Searching

When you search:
1. Query text → embedding
2. Parallel cosine similarity search across all tables
3. Results ranked by similarity
4. Optional merging across types

### 3. Performance

- **Search time**: ~0.4ms per content type
- **Total for 4 types**: ~1.6ms (parallel)
- **Index size**: ~1.5KB per document (384 floats)

## Workflow Integration

Auto-index workflow outputs:

```javascript
// In workflow completion hook
const { addToIndex } = require('./shared/universal-semantic-search.js');

await addToIndex('workflow', {
  workflow_id: executionId,
  text: taskDescription + ' ' + finalResult
});
```

## Advanced Features

### Category Filtering (PDFs)

```javascript
const results = await universalSearch("python tutorial", {
  types: ['pdf'],
  category: 'programming'  // Filters by path: %/programming/%
});
```

### Language Filtering (Code)

```javascript
// Search only JavaScript files
const jsResults = await pool.query(`
  SELECT * FROM learning.code_embeddings
  WHERE language = 'javascript'
  ORDER BY embedding <=> $1::vector
  LIMIT 10
`, [queryEmbedding]);
```

### Hybrid Search (Vector + Full-Text)

```javascript
// Combine semantic and keyword search
const results = await pool.query(`
  SELECT *,
    1 - (embedding <=> $1::vector) as semantic_score,
    ts_rank(to_tsvector(content_preview), plainto_tsquery($2)) as keyword_score
  FROM learning.code_embeddings
  WHERE to_tsvector(content_preview) @@ plainto_tsquery($2)
  ORDER BY (semantic_score * 0.7 + keyword_score * 0.3) DESC
  LIMIT 10
`, [queryEmbedding, 'authentication']);
```

## Roadmap

- [x] PDF search (843 indexed)
- [ ] Code indexing (ready to use)
- [ ] Workflow auto-indexing
- [ ] Documentation indexing
- [ ] Hybrid search (vector + full-text)
- [ ] Real-time incremental indexing
- [ ] Multi-language support (beyond hash-based)
- [ ] Relevance feedback (click tracking)

## Comparison with PDF-Only Search

| Feature | PDF-Only | Universal |
|---------|----------|-----------|
| Search scope | 843 PDFs | PDFs + Code + Workflows + Docs |
| CLI tool | `library-recommend` | `search-everything` |
| API | `semantic-search.js` | `universal-semantic-search.js` |
| Results format | PDF list | Grouped by type OR merged |
| Code search | ✗ | ✓ |
| Workflow search | ✗ | ✓ |

## Files

- `shared/universal-semantic-search.js` - Core API
- `scripts/search-everything` - CLI tool
- `tools/index-codebase.js` - Code indexer
- `docs/UNIVERSAL_SEARCH.md` - This file

## Related

- [PDF Library Assistant](./LIBRARY_ASSISTANT.md) - PDF-specific search
- [PostgreSQL + pgvector](../CLAUDE.md#continual-learning-infrastructure-2026-06-15)
- [Neo4j Knowledge Graph](../shared/neo4j-realtime-sync.cjs)
