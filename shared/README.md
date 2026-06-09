# Shared Components

Reusable components for workflows and skills.

## Vector Storage (vector-store.py)

Prototype ChromaDB integration for semantic memory retrieval.

### Setup

```bash
pip3 install -r requirements.txt
```

### Usage

```python
from shared.vector_store import VectorStore

store = VectorStore(collection='claude-memory')
store.add("Multi-model consensus uses arbiter/worker pattern", 
          metadata={'type': 'feedback'})

results = store.query("how does consensus work", top_k=5)
```

### Storage Location

- **Code**: In git repo (`shared/vector-store.py`)
- **Data**: Local only (`~/.claude/vector_db/`) - NOT in git
- **Config**: Add `.claude/vector_db` to `.gitignore`

### Concepts Borrowed from vectordb-ai

- ChromaDB for local vector storage
- Sentence transformers for embeddings (384-dim)
- Metadata filtering
- Batch operations

This is a **prototype** for testing ideas. Proven concepts flow back to FlossWare vectordb-ai.
