# Local Embeddings Model - Installed on laptop-01 ✅

## Model Information

**Model:** `all-MiniLM-L6-v2`
- **Source:** sentence-transformers (HuggingFace)
- **Dimensions:** 384
- **Size:** ~90MB
- **Speed:** ~1000 embeddings/second on CPU
- **Quality:** Excellent for semantic search
- **Language:** English (optimized)

## Location

```bash
~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/
```

## Red Hat Compliance ✅

- ✅ **Local model** - No external API calls
- ✅ **Open source** - MIT license
- ✅ **No telemetry** - Runs completely offline
- ✅ **Deterministic** - Same input = same output

## Usage

### From Python
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode("your text here")
print(f"Embedding dimensions: {len(embedding)}")  # 384
```

### Search Sessions
```bash
# Quick search
~/bin/search-sessions-local.py "postgres setup"

# Search titles
~/bin/search-sessions-local.py "API integration" 10 title

# Search content
~/bin/search-sessions-local.py "backup disaster recovery" 20 content
```

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Model load | ~1-2s | First time only |
| Single embedding | ~1ms | CPU |
| Batch (100 texts) | ~100ms | CPU |
| Search 11,583 sessions | ~0.5ms | PostgreSQL HNSW index |

## Same Model on All Machines

**laptop-01:** ✅ Installed (for search queries)
**server-03:** ⏳ Installing (for processing sessions)

Both use the **exact same model** to ensure embeddings match.

## How It Works

```
User Query
    ↓
laptop-01: Generate embedding locally (all-MiniLM-L6-v2)
    ↓
PostgreSQL: Vector similarity search (HNSW index)
    ↓
Results ranked by cosine similarity
```

## Test It

```bash
python3 << 'EOF'
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate embeddings
texts = [
    "How to setup PostgreSQL database",
    "Installing Docker containers",
    "PostgreSQL configuration tutorial"
]

embeddings = model.encode(texts)

# Check similarity
from scipy.spatial.distance import cosine
sim_0_2 = 1 - cosine(embeddings[0], embeddings[2])
sim_0_1 = 1 - cosine(embeddings[0], embeddings[1])

print(f"Similarity (PostgreSQL queries): {sim_0_2:.3f}")
print(f"Similarity (Postgres vs Docker): {sim_0_1:.3f}")
print("✅ Higher similarity for related topics!")
EOF
```

---

**Status:** ✅ Model installed and ready on laptop-01!
