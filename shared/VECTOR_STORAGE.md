# Vector Storage Prototype

Testing ChromaDB concepts for .claude global memory.

## Status: PROTOTYPE

The `vector-store.py` script is a working prototype but has many dependencies. 

## Installation (Optional)

Only install if you want to test vector storage:

```bash
pip3 install chromadb sentence-transformers python-dotenv
```

## Concepts Being Tested

From FlossWare vectordb-ai:

1. **Local Storage** - ChromaDB for lightweight, local vector DB
2. **Embeddings** - all-MiniLM-L6-v2 (384-dim vectors)
3. **Semantic Search** - Similarity-based retrieval
4. **Metadata Filtering** - Filter by type, domain, etc.
5. **Chunking Strategy** - 500-1000 char semantic chunks

## Git Strategy

- ✅ **Code in git**: `vector-store.py`, docs, requirements
- ❌ **Data NOT in git**: `~/.claude/vector_db/` (local only, in .gitignore)
- ✅ **Learnings in git**: What works/doesn't → feed back to vectordb-ai

## Benefit to Learning

**Cross-session knowledge**:
- Without vectors: Markdown files, keyword search
- With vectors: Semantic retrieval - find by meaning

Example:
- Query: "how should I handle errors in workflows"
- Without vectors: grep for "error" OR "workflow" → miss relevant content
- With vectors: Find semantically similar content about error handling, resilience, graceful fallback

**Multi-session learning**:
1. Session A: User teaches me about multi-model consensus
2. Stored in vector DB with embeddings
3. Session B: User asks "how do arbiters work"
4. Vector search finds Session A learnings → I remember!

## Next Steps

Once proven here, concepts flow back to FlossWare vectordb-ai production library.
