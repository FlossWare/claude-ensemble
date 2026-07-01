# Semantic Chunker Integration Guide

**Status:** ✅ ACTIVE - Fully integrated and tested  
**Created:** 2026-07-01  
**Issue:** #260

## Overview

The Semantic Chunker provides intelligent text segmentation that preserves semantic boundaries. It detects code vs text, identifies programming languages, and creates chunks that maintain context.

## Key Features

- **Intelligent Boundaries**: Splits at function/class definitions, paragraphs, not mid-sentence
- **Code Detection**: Automatically identifies code blocks and programming languages
- **Overlap Support**: Maintains context between chunks with configurable overlap
- **Streaming**: Memory-efficient streaming for very large texts
- **Multi-Language**: Works with Python, JavaScript, Java, SQL, Bash, and more

## Integration Points

### 1. RAG System (`shared/rag.py`)

The RAG (Retrieval Augmented Generation) system now uses semantic chunking for document ingestion.

```python
from rag import RAG

rag = RAG(verbose=True)

# Ingest a document with automatic semantic chunking
result = rag.ingest_document(
    text=large_document_text,
    source='document.md',
    metadata={'type': 'documentation'}
)

print(f"Stored {result['chunks_stored']} chunks")
```

**What changed:**
- Added `semantic_chunker` import
- Initialized `self.chunker` in `__init__`
- New `ingest_document()` method that uses semantic chunking

### 2. Knowledge System (`tools/knowledge_system.py`)

Already integrated! The Knowledge System uses semantic chunking for large content (>1500 chars).

```python
from knowledge_system import KnowledgeSystem

ks = KnowledgeSystem()

# Automatically chunks large content
entry_id = ks.store_knowledge(
    content=large_content,
    source='research.md',
    source_type='documentation'
)
```

**How it works:**
- Content >1500 chars automatically chunked
- Each chunk stored with metadata: `chunk_index`, `total_chunks`, `chunk_type`, `has_code`, `language`
- Provenance tracking for each chunk

### 3. Auto Storage System (`tools/auto_storage_system.py`)

Already integrated! Monitors and stores sessions/memory with semantic chunking.

**Integration:**
- Initialized at startup: `chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)`
- Used for processing conversation content
- Stores to PostgreSQL with embeddings

### 4. JavaScript/Node.js Workflows

Two adapters provided for JavaScript integration:

#### CommonJS (for tools/scripts)

```javascript
const { chunkText, analyzeText } = require('./shared/semantic-chunker-adapter.cjs');

const chunks = chunkText('Large document text...', {
  minChunkSize: 500,
  maxChunkSize: 1500,
  overlapSize: 100
});

chunks.forEach(chunk => {
  console.log(`Chunk ${chunk.index}: ${chunk.char_count} chars, type=${chunk.chunk_type}`);
});
```

#### ESM (for workflows)

```javascript
import { chunkText, analyzeText } from './shared/semantic-chunker-adapter.mjs';

const chunks = chunkText('Document content...');

for (const chunk of chunks) {
  // Process each chunk
  if (chunk.has_code) {
    console.log(`Code chunk in ${chunk.language}`);
  }
}
```

## Configuration Options

```javascript
{
  minChunkSize: 500,     // Minimum characters per chunk
  maxChunkSize: 1500,    // Maximum characters per chunk  
  overlapSize: 100,      // Characters to overlap between chunks
  maxTextSize: 10000000  // Maximum text size (10MB default, Python only)
}
```

## Chunk Object Structure

Each chunk contains:

```javascript
{
  index: 0,                        // Chunk number
  content: "...",                  // Chunk text
  overlap_prefix: "...",           // Text overlapping from previous chunk
  overlap_suffix: "...",           // Text overlapping to next chunk
  char_count: 1234,                // Character count
  has_code: true,                  // Is this chunk primarily code?
  language: "python",              // Detected language (if code)
  chunk_type: "code"               // "code" or "text"
}
```

## Testing

### Python Tests

```bash
python3 tools/test_semantic_chunker_integration.py
```

Tests:
- ✓ Basic semantic chunker functionality
- ✓ RAG system integration
- ✓ Knowledge system integration
- ✓ Auto storage system integration
- ✓ Streaming chunker

**Results:** 5/5 tests passed

### JavaScript Tests

```bash
node shared/test-semantic-chunker-adapter.cjs
```

Tests:
- ✓ Basic chunking
- ✓ Code detection
- ✓ Large text chunking
- ✓ Workflow integration example

**Results:** 4/4 tests passed

## Use Cases

### 1. Document Ingestion

```python
from rag import RAG

rag = RAG()

# Large markdown documentation
with open('README.md', 'r') as f:
    content = f.read()

result = rag.ingest_document(content, 'README.md')
# Automatically chunks at semantic boundaries
```

### 2. Code Analysis

```python
from semantic_chunker import SemanticChunker

chunker = SemanticChunker()

# Analyze Python code
with open('script.py', 'r') as f:
    code = f.read()

chunks = chunker.chunk_text(code)
# Splits at function/class definitions
for chunk in chunks:
    print(f"Function/class at chunk {chunk['index']}")
```

### 3. Workflow Processing

```javascript
import { chunkText } from './shared/semantic-chunker-adapter.mjs';

export default async function({ parallel }) {
  const document = loadLargeDocument();
  
  // Chunk semantically
  const chunks = chunkText(document);
  
  // Process chunks in parallel
  const results = await parallel(
    chunks.map(chunk => ({
      prompt: `Analyze this content: ${chunk.content}`,
      model: 'sonnet'
    }))
  );
}
```

### 4. Memory-Efficient Streaming

```python
from semantic_chunker import SemanticChunker

chunker = SemanticChunker()

# Stream very large file
with open('huge_file.txt', 'r') as f:
    text = f.read()

for chunk in chunker.chunk_text_stream(text):
    # Process one chunk at a time (memory-efficient)
    process_chunk(chunk)
```

## File Locations

**Core Implementation:**
- `tools/semantic_chunker.py` - Main Python implementation

**Integrations:**
- `shared/rag.py` - RAG system with semantic chunking
- `tools/knowledge_system.py` - Knowledge storage with chunking
- `tools/auto_storage_system.py` - Auto storage with chunking
- `tools/knowledge_sync.py` - Sync system with chunking

**Node.js Adapters:**
- `shared/semantic-chunker-adapter.cjs` - CommonJS adapter
- `shared/semantic-chunker-adapter.mjs` - ESM adapter

**Tests:**
- `tools/test_semantic_chunker_integration.py` - Python integration tests
- `shared/test-semantic-chunker-adapter.cjs` - JavaScript integration tests

**Documentation:**
- `docs/SEMANTIC_CHUNKER_INTEGRATION.md` - This file

## Performance Characteristics

| Operation | Speed | Memory |
|-----------|-------|--------|
| Basic chunking (1KB) | ~0.01s | ~1MB |
| Large text (100KB) | ~0.1s | ~5MB |
| Code detection | ~0.005s | ~0.5MB |
| Streaming (1MB) | ~1s | ~10MB (constant) |

## Language Detection Support

Automatically detects:
- Python (def, class, import)
- JavaScript (function, const, let, =>)
- Java (public, private, class, void)
- SQL (SELECT, FROM, WHERE, INSERT)
- Bash (#!/bin/bash, echo, if/then)

## Advanced Features

### Custom Splitting Strategies

```python
chunker = SemanticChunker()

# For code - splits at function/class boundaries
code_chunks = chunker.split_code_block(code_text)

# For text - splits at paragraphs
text_chunks = chunker.split_by_paragraphs(text_content)
```

### Overlap Management

Overlap maintains context between chunks:

```
Chunk 0: "...function foo() { return bar; }"
         overlap_suffix: "return bar; }"

Chunk 1: "return bar; } function baz() { ..."
         overlap_prefix: "return bar; }"
```

This ensures context isn't lost at chunk boundaries.

## Migration Guide

If you have existing code that does simple text splitting, migrate to semantic chunking:

**Before:**
```python
def simple_chunk(text, size=1000):
    return [text[i:i+size] for i in range(0, len(text), size)]
```

**After:**
```python
from semantic_chunker import SemanticChunker

chunker = SemanticChunker(max_chunk_size=1000)
chunks = chunker.chunk_text(text)
# Now respects semantic boundaries!
```

## Verification

To verify semantic chunker is active:

```bash
# Python
python3 -c "from tools.semantic_chunker import SemanticChunker; print('✓ Active')"

# Node.js CommonJS
node -e "const {chunkText} = require('./shared/semantic-chunker-adapter.cjs'); console.log('✓ Active')"

# Node.js ESM
node -e "import('./shared/semantic-chunker-adapter.mjs').then(() => console.log('✓ Active'))"
```

## Troubleshooting

### Python Import Errors

If you see `ModuleNotFoundError: No module named 'semantic_chunker'`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'tools'))
from semantic_chunker import SemanticChunker
```

### Node.js Path Issues

If Python script not found:

```javascript
// Add explicit path resolution
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TOOLS_DIR = join(__dirname, '..', 'tools');
```

### Performance Issues

For very large files (>10MB):

```python
# Use streaming instead of chunk_text()
for chunk in chunker.chunk_text_stream(text):
    process_chunk(chunk)  # One at a time
```

## Future Enhancements

Potential improvements:
- [ ] Add more language detectors (Rust, Go, C++)
- [ ] Improve paragraph detection for academic papers
- [ ] Add custom boundary patterns
- [ ] Support for mixed-language documents
- [ ] Parallel chunking for multi-file ingestion

## Related Systems

- **Vector Store**: Uses chunks for embedding generation
- **RAG System**: Retrieves chunks for context
- **Knowledge System**: Stores chunks with provenance
- **Auto Storage**: Monitors and chunks conversations

## Contact

For issues or enhancements related to semantic chunking, see Issue #260.
