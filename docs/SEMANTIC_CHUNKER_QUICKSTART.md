# Semantic Chunker - Quick Start Guide

## TL;DR

Semantic chunker is ACTIVE and integrated into:
- ✅ RAG system (`shared/rag.py`)
- ✅ Knowledge system (`tools/knowledge_system.py`)
- ✅ Auto storage (`tools/auto_storage_system.py`)
- ✅ JavaScript workflows (via adapters)

## 30-Second Examples

### Python

```python
from semantic_chunker import SemanticChunker

chunker = SemanticChunker(max_chunk_size=1000)
chunks = chunker.chunk_text(large_document)

for chunk in chunks:
    print(f"Chunk {chunk['index']}: {chunk['char_count']} chars")
```

### JavaScript (ESM)

```javascript
import { chunkText } from './shared/semantic-chunker-adapter.mjs';

const chunks = chunkText(document, { maxChunkSize: 1000 });
chunks.forEach(chunk => console.log(`Chunk ${chunk.index}`));
```

### JavaScript (CommonJS)

```javascript
const { chunkText } = require('./shared/semantic-chunker-adapter.cjs');

const chunks = chunkText(document);
// Process chunks...
```

## Verify It's Working

```bash
# Python
python3 tools/test_semantic_chunker_integration.py

# JavaScript
node shared/test-semantic-chunker-adapter.cjs
```

Both should show 100% tests passed.

## Common Options

```javascript
{
  minChunkSize: 500,   // Min chars per chunk
  maxChunkSize: 1500,  // Max chars per chunk
  overlapSize: 100     // Overlap between chunks
}
```

## What It Does

✅ Splits at function/class definitions (code)  
✅ Splits at paragraph breaks (text)  
✅ Detects programming languages  
✅ Maintains context with overlap  
✅ Streams large files efficiently  

❌ Does NOT split mid-sentence  
❌ Does NOT break code blocks  
❌ Does NOT lose context  

## Key Files

**Implementation:**
- `tools/semantic_chunker.py`

**Adapters:**
- `shared/semantic-chunker-adapter.mjs` (ESM)
- `shared/semantic-chunker-adapter.cjs` (CommonJS)

**Tests:**
- `tools/test_semantic_chunker_integration.py`
- `shared/test-semantic-chunker-adapter.cjs`

**Docs:**
- `docs/SEMANTIC_CHUNKER_INTEGRATION.md` (full guide)
- `docs/SEMANTIC_CHUNKER_QUICKSTART.md` (this file)

## Chunk Object

```javascript
{
  index: 0,              // Chunk number
  content: "...",        // Chunk text
  char_count: 1234,      // Size
  has_code: true,        // Is it code?
  language: "python",    // Detected language
  chunk_type: "code"     // "code" or "text"
}
```

## Integration Examples

### RAG Document Ingestion

```python
from rag import RAG

rag = RAG()
result = rag.ingest_document(text, 'doc.md')
print(f"Stored {result['chunks_stored']} chunks")
```

### Knowledge Storage

```python
from knowledge_system import KnowledgeSystem

ks = KnowledgeSystem()
entry_id = ks.store_knowledge(large_content, 'source.md')
# Automatically chunked if >1500 chars
```

### Workflow Processing

```javascript
import { chunkText } from './shared/semantic-chunker-adapter.mjs';

export default async function({ parallel }) {
  const chunks = chunkText(document);
  
  await parallel(
    chunks.map(chunk => ({
      prompt: `Process: ${chunk.content}`,
      model: 'sonnet'
    }))
  );
}
```

## Need More?

See full documentation: `docs/SEMANTIC_CHUNKER_INTEGRATION.md`
