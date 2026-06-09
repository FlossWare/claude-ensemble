# Semantic Search Prototype

Testing semantic-search-ai concepts for .claude.

## Components

### 1. Hybrid Search (RRF)
Combines semantic (vector) + keyword (text) search using Reciprocal Rank Fusion.

**Why it helps learning/memory:**
- Vector search alone misses exact keyword matches
- Keyword search alone misses semantic meaning
- Hybrid gets both: "multi-model" finds "consensus" AND "arbiter/worker"

```python
from shared.semantic_search import HybridSearch

hybrid = HybridSearch(semantic_weight=0.7, keyword_weight=0.3)
results = hybrid.merge(vector_results, keyword_results, top_k=10)
```

### 2. Reranking
Two-stage retrieval: fast candidates → accurate rerank.

**Why it helps learning/memory:**
- Stage 1 (bi-encoder): Fast, get 100 candidates
- Stage 2 (cross-encoder): Accurate, rerank to top 5
- Better precision than single-stage search

```python
from shared.semantic_search import Reranker

reranker = Reranker()
candidates = vector_db.search(query, top_k=100)  # Fast
top = reranker.rerank(query, candidates, top_k=5)  # Accurate
```

### 3. Advanced Filtering
MongoDB-style operators for memory queries.

**Why it helps learning/memory:**
- Filter by type: `{"type": "feedback"}`
- Filter by score: `{"score": {"$gte": 0.8}}`
- Complex queries: `{"$and": [{"type": "feedback"}, {"domain": "multi-ai"}]}`

```python
from shared.semantic_search import AdvancedFilter

# Find high-confidence feedback about multi-AI
filtered = AdvancedFilter.apply(results, {
    "type": "feedback",
    "score": {"$gte": 0.8},
    "domain": {"$regex": "multi"}
})
```

## How It Helps Learning

**Without semantic search:**
- Query: "how do arbiters work"
- Result: grep for "arbiter" → miss content about "consensus validation"

**With hybrid search + reranking:**
- Query: "how do arbiters work"
- Hybrid finds: exact "arbiter" matches + semantic "consensus", "worker", "validation"
- Reranker scores: most relevant at top
- Filter: only high-confidence memories
- Result: Comprehensive answer from multiple related memories

## Cross-Session Memory Example

**Session A** (you teach me):
```
User: "Use arbiter/worker pattern for multi-model consensus"
→ Stored with embeddings: ["arbiter", "worker", "consensus", "multi-model"]
```

**Session B** (I remember):
```
User: "How should I validate with multiple AIs?"
→ Hybrid search finds Session A memory (semantic similarity)
→ Reranking boosts it to top
→ I respond: "Use arbiter/worker pattern..."
```

## Concepts from semantic-search-ai

- Reciprocal Rank Fusion algorithm
- Bi-encoder → Cross-encoder two-stage retrieval
- MongoDB-style query operators
- Backend-agnostic design

All proven concepts flow back to FlossWare semantic-search-ai.
