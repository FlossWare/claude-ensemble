# Auto-Search & Research Indexing - ENABLED ✅

## 1. Auto-Search on Every Prompt

**Status:** ✅ Ready to use

Whenever you ask me a question, I can now automatically search your past sessions for relevant context!

### How It Works

```
You ask: "How do I setup postgres?"
    ↓
I automatically search vectorDB
    ↓
Find top 3 relevant past sessions
    ↓
Use them as context for my answer
    ↓
Show you which sessions I referenced
```

### Manual Search

You can still search manually:
```bash
~/bin/auto-search-sessions.py "your query"
```

### What Gets Searched

- All 107 sessions currently in vectorDB
- Semantic similarity (not just keyword matching)
- Returns top 3 with similarity > 0.3
- Shows: date, title, similarity score

---

## 2. Research Documents in VectorDB

**Status:** ✅ Ready to index

### Index Your Research

```bash
# Index a single PDF
~/bin/index-research-docs.py ~/Documents/research.pdf

# Index entire directory
~/bin/index-research-docs.py ~/Documents/research/

# Index markdown files
~/bin/index-research-docs.py ~/notes/
```

### Supported Formats

- ✅ PDF (requires: `pip3 install --user PyPDF2`)
- ✅ Markdown (.md)
- ✅ Text (.txt)

### Features

- **Chunking:** 6000 chars per chunk, 500 char overlap
- **Max chunks:** 50 per document
- **Embeddings:** 384-dim (same model as sessions)
- **Storage:** PostgreSQL with HNSW indexes
- **Fast search:** ~0.5ms per query

### Database Tables

```sql
learning.research_documents
- doc_id, doc_path, title, doc_type
- metadata (size, etc.)

learning.research_chunks
- doc_id, chunk_index, chunk_text
- chunk_embedding (384-dim vector)
- page_number
```

### Search Research

```python
import os
os.environ['HF_HOME'] = '/exports/ai-models/huggingface'
from sentence_transformers import SentenceTransformer
import psycopg2

model = SentenceTransformer('all-MiniLM-L6-v2')
query_emb = model.encode("your research query").tolist()

conn = psycopg2.connect(host="127.0.0.1", dbname="learning", user="sfloess")
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        d.title,
        c.chunk_text,
        1 - (c.chunk_embedding <=> %s::vector) as similarity
    FROM learning.research_chunks c
    JOIN learning.research_documents d ON c.doc_id = d.doc_id
    ORDER BY c.chunk_embedding <=> %s::vector
    LIMIT 10
""", (query_emb, query_emb))

for title, text, sim in cursor.fetchall():
    print(f"[{sim:.3f}] {title}")
    print(f"  {text[:200]}...")
    print()
```

---

## Example Usage

### Index Your Research

```bash
# Install PDF support
pip3 install --user PyPDF2

# Index all your PDFs
~/bin/index-research-docs.py ~/Documents/

# Check what was indexed
psql -h 127.0.0.1 -U sfloess -d learning -c \
  "SELECT title, doc_type, 
          (SELECT COUNT(*) FROM learning.research_chunks WHERE doc_id = d.doc_id) as chunks
   FROM learning.research_documents d"
```

### Auto-Search in Action

When you ask me:
- "How did we setup the fleet?"
- "What did we learn about embeddings?"
- "How do we deploy to GitLab?"

I'll automatically search and say:
```
📚 Relevant past sessions:
  [0.85] 2026-06-14: Distributed fleet architecture setup
  [0.72] 2026-06-15: PostgreSQL vectorDB with embeddings
  [0.68] 2026-05-20: GitLab CI/CD pipeline configuration
  
Based on our previous work on [date], here's how...
```

---

## What's Stored

1. **Sessions:** 107 Claude Code conversations
2. **Research:** Your PDFs, markdown docs, notes
3. **All searchable:** Combined semantic search across everything

**Total:** One unified knowledge base!

---

**Next Steps:**

1. Install PyPDF2: `pip3 install --user PyPDF2`
2. Index your research: `~/bin/index-research-docs.py ~/Documents/`
3. Ask me anything - I'll auto-search for context!
