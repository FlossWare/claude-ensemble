# RAG - Cross-Session Learning That Actually Works

**Concept:** Query memory → retrieve relevant chunks → generate answer with citations

**Source:** `shared/rag.py`  
**Status:** ✅ Proven, ready for FlossWare knowledge-ai  
**Issue:** FlossWare/knowledge-ai#2

---

## The Problem: AIs Don't Remember

### Without Cross-Session Learning

**Monday (Session A):**
```
You: "Always use different models for workers in multi-AI consensus"
Me: "Got it!" *stores nowhere*
```

**Friday (Session B):**
```
You: "Should I use the same model for all workers?"
Me: "Sure, that's fine!" ← FORGOT what you taught me!
```

**Result:** You have to teach me the same thing every session. 😞

### With RAG + Global Memory

**Monday (Session A):**
```
You: "Always use different models for workers"
Me: "Got it!" 
→ Stores in memory/feedback_multi_model.md
→ Generates embeddings
→ Indexed for semantic search
```

**Friday (Session B):**
```
You: "Should I use the same model for all workers?"
Me: *RAG query: "multi-model worker configuration"*
    *Retrieves: feedback_multi_model.md*
    *Generates answer with context*
    
Me: "No - you taught me to always use DIFFERENT models for workers. 
     Here's why... [Citation: feedback_multi_model.md, Session A]"
```

**Result:** I remember what you taught me! 🎉

---

## How RAG Works

### The Pipeline

```
1. Query
   ↓
2. Hybrid Search (semantic + keyword)
   ↓
3. Rerank (precision)
   ↓
4. Build Context (top chunks)
   ↓
5. Generate Answer (LLM with context)
   ↓
6. Citations (which sources used)
```

### Example

```python
from shared.rag import RAG

# Initialize
rag = RAG(collection='claude-memory')

# Query
result = rag.query('How does multi-model consensus work?')

# Answer generated from memory
print(result.answer)
# "Multi-model consensus uses 3+ different AI models as workers
#  (e.g., Opus, Sonnet, GPT-4o). Each worker analyzes independently,
#  then an arbiter synthesizes their findings. This reduces false
#  positives and provides diverse perspectives."

# Citations show sources
print(result.citations)
# [
#   {
#     'source': 'feedback_arbiter_worker_multi_model.md',
#     'similarity': 0.92,
#     'type': 'feedback'
#   },
#   {
#     'source': 'feedback_multi_model_shorthand.md',
#     'similarity': 0.88,
#     'type': 'feedback'
#   }
# ]

# Retrieval quality
print(result.retrieval_score)
# 0.90 (high quality retrieval)
```

---

## Why RAG > Simple Search

### Simple Vector Search

```python
# Just retrieves similar chunks
results = vector_db.search("consensus")
# Returns: 5 chunks about consensus

# You still have to:
# - Read all 5 chunks manually
# - Figure out the answer yourself
# - No citations
```

### RAG (Retrieval Augmented Generation)

```python
# Retrieves AND generates answer
result = rag.query("How does consensus work?")

# You get:
# ✅ Direct answer (generated from chunks)
# ✅ Citations (which chunks were used)
# ✅ Quality score (how good the retrieval was)
# ✅ Context used (what the LLM saw)
```

---

## The Components

### 1. Hybrid Search

**Why:** Vector search alone misses exact keyword matches.

```python
# Query: "arbiter rotation"

# Vector search only:
# - Finds: "consensus validation", "worker coordination" (similar meaning)
# - Misses: Exact phrase "arbiter rotation" buried in text

# Hybrid search (semantic + keyword + RRF):
# - Finds: "arbiter rotation" (exact keyword match)
# - PLUS: "consensus validation" (semantic similarity)
# - Best of both worlds!
```

**RRF (Reciprocal Rank Fusion):**
```python
# Combines semantic + keyword results
semantic_results = vector_search("arbiter rotation")
keyword_results = text_search("arbiter rotation")

# RRF merges them intelligently
hybrid_results = RRF(semantic, keyword)
# Documents ranking high in BOTH searches bubble to top
```

### 2. Reranking

**Why:** First-stage retrieval is fast but imprecise.

```
Stage 1 (Bi-encoder - FAST):
- Get 100 candidate chunks (cast wide net)
- Uses vector similarity
- Speed: ~10ms

Stage 2 (Cross-encoder - ACCURATE):
- Rerank top 100 → best 5
- Uses deeper semantic understanding
- Speed: ~100ms

Result: Fast + Accurate!
```

```python
# Without reranking
candidates = vector_db.search(query, top_k=5)
# Might miss best chunks (imprecise ranking)

# With reranking
candidates = vector_db.search(query, top_k=100)  # Cast wide net
top_5 = reranker.rerank(query, candidates, top_k=5)  # Precision
# Gets the BEST 5 chunks
```

### 3. Context Building

```python
# Retrieved chunks
chunks = [
  "Multi-model consensus uses different AI models...",
  "Arbiter synthesizes worker findings...",
  "Prevents bias through diverse perspectives..."
]

# Build context
context = """
[1] feedback_multi_model.md:
Multi-model consensus uses different AI models...

[2] workflow_helpers.md:
Arbiter synthesizes worker findings...

[3] consensus_strategies.md:
Prevents bias through diverse perspectives...
"""

# LLM generates answer using this context
```

### 4. Answer Generation

```python
prompt = f"""Based on these memories:

{context}

Answer: {query}

Cite your sources using [1], [2], [3] notation."""

answer = llm.generate(prompt)
# "Multi-model consensus uses 3+ AI models [1] where each
#  worker analyzes independently [2]. An arbiter synthesizes
#  their findings [2] which prevents bias through diverse
#  perspectives [3]."
```

### 5. Citation Tracking

```python
# Extract which sources were actually used
citations = [
  {
    'index': 1,
    'source': 'feedback_multi_model.md',
    'similarity': 0.92,
    'type': 'feedback'
  },
  {
    'index': 2,
    'source': 'workflow_helpers.md',
    'similarity': 0.88,
    'type': 'technical'
  }
]
```

---

## Real Example: Cross-Session Learning

### Session A: Teaching Phase

```python
# User teaches me about arbiter rotation
user_message = """
IMPORTANT: Never use the same arbiter for review AND solve phases.
Use different models:
- Review: Opus (thorough analysis)
- Solve: Sonnet (validates review findings)
- Verify: Haiku (validates fixes)

Why: Same arbiter can rubber-stamp their own findings (bias).
"""

# I extract and store this
learning = {
  'type': 'feedback',
  'name': 'arbiter-rotation-pattern',
  'content': user_message,
  'why': 'Prevents bias',
  'howToApply': 'Use different arbiters for different phases'
}

# Store in memory with embeddings
vector_db.add(learning['content'], metadata={
  'type': 'feedback',
  'name': 'arbiter-rotation-pattern'
})
```

### Session B: Recall Phase (Days Later)

```python
# User asks question
query = "Can I use opus for both review and solve?"

# RAG retrieves learned knowledge
result = rag.query(query)

print(result.answer)
# "No - you should use DIFFERENT arbiters for review and solve phases.
#  Use Opus for review and Sonnet for solve. This prevents bias because
#  the same arbiter might rubber-stamp their own findings.
#  
#  Source: You taught me this pattern in a previous session."

print(result.citations)
# [{'source': 'feedback_arbiter-rotation-pattern.md', 'similarity': 0.94}]

# I REMEMBERED! 🎉
```

---

## Advanced: Workers/Arbiters Query Memory

**Concept:** Not just YOU learn - the AI models themselves query memory before working.

```javascript
// Worker queries memory before analyzing
phase('Prepare')

const relevantLearnings = await agent(`Query memory for relevant patterns:

Topic: Multi-model code review
Question: What best practices should I follow?

Use RAG to search memory and return top insights.`, {
  label: 'query-memory'
})

// Worker uses learnings in analysis
phase('Analyze')

const findings = await agent(`Review this code.

APPLY THESE LEARNINGS:
${JSON.stringify(relevantLearnings)}

Look for patterns mentioned in the learnings.`, {
  label: 'worker:opus',
  model: 'opus'
})
```

**Result:**
- Workers apply past learnings automatically
- Consistent behavior across sessions
- Self-improving over time

---

## Benefits Summary

### 1. Cross-Session Memory
- ✅ Learn from Session A → Remember in Session B
- ✅ Accumulate knowledge over time
- ✅ Never forget what user taught

### 2. Trust Through Citations
- ✅ Show which sources were used
- ✅ User can verify accuracy
- ✅ Transparent retrieval process

### 3. Quality Through Hybrid Search
- ✅ Semantic similarity (meaning)
- ✅ Keyword matching (exact phrases)
- ✅ Reranking (precision)

### 4. Continuous Learning
- ✅ Workers query memory before tasks
- ✅ Apply learned best practices
- ✅ Improve over time

---

## API Reference

### `RAG`

**Constructor:**
```python
rag = RAG(
    collection='claude-memory',
    persist_directory='~/.claude/vector_db',
    top_k=5,
    verbose=False
)
```

**Methods:**

**`query(query, use_hybrid=True, use_rerank=True, metadata_filter=None)`**
```python
result = rag.query(
    'How does consensus work?',
    use_hybrid=True,      # Semantic + keyword
    use_rerank=True,      # Precision reranking
    metadata_filter={'type': 'feedback'}  # Only feedback memories
)
```

Returns `RAGResult`:
- `answer` (str): Generated answer
- `citations` (list): Source documents used
- `context_used` (list): Context chunks
- `retrieval_score` (float): Quality (0-1)

---

## Migration to FlossWare knowledge-ai

**Issue:** https://github.com/FlossWare/knowledge-ai/issues/2

**Implementation checklist:**
- [ ] Port `rag.py` to production
- [ ] Add JavaScript version (`rag.js`)
- [ ] Integrate with vectordb-ai (retrieval)
- [ ] Integrate with semantic-search-ai (hybrid + rerank)
- [ ] Add LLM generation (API agnostic)
- [ ] Citation tracking
- [ ] Quality metrics
- [ ] Add tests
- [ ] Update README

**Working code:**
https://gitlab.cee.redhat.com/sfloess/claude-global-skills/-/blob/main/shared/rag.py
