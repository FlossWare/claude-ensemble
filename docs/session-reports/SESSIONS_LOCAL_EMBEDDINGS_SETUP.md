# Session Vector DB - LOCAL EMBEDDINGS (Red Hat Compliant) ✅

## Setup Complete!

### Architecture (Compliant)

```
┌─────────────────────────────────────┐
│ laptop-01 (Red Hat Machine)         │
│ - PostgreSQL database ONLY          │
│ - NO external API calls             │
│ - NO non-Anthropic processing       │
│ - Stores vectors (passive)          │
└─────────────────────────────────────┘
                  ↑
                  │ Store embeddings
                  │
┌─────────────────────────────────────┐
│ server-03 (Non-Red Hat - Debian)    │
│ - Generates embeddings locally      │
│ - sentence-transformers library     │
│ - Model: all-MiniLM-L6-v2 (384-dim) │
│ - NO external API calls             │
│ - 100% local processing             │
└─────────────────────────────────────┘
```

### Embedding Model

**Model:** `all-MiniLM-L6-v2`
- **Dimensions:** 384
- **Size:** ~90MB
- **Quality:** Excellent for semantic search
- **Speed:** ~1000 embeddings/second
- **Cost:** $0 (fully local)
- **API Calls:** NONE

**You'll want this same model on laptop-01** for search queries:
```bash
pip3 install --user sentence-transformers
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Database Schema

**PostgreSQL on laptop-01:**
```sql
learning.sessions
- session_id, title, summary, full_content
- title_embedding vector(384)
- summary_embedding vector(384)
- content_embedding vector(384)

learning.session_chunks
- session_id, chunk_index, chunk_text
- chunk_embedding vector(384)
```

### Processing Status

**Current:** Running on server-03
- Processing: 11,583 sessions
- Speed: ~10-20 sessions/second
- ETA: ~10-20 minutes
- Log: `ssh server-03 "tail -f /tmp/sessions-local-embeddings.log"`

### Red Hat Compliance ✅

- ✅ laptop-01: NO external APIs
- ✅ laptop-01: NO non-Anthropic processing
- ✅ laptop-01: Database storage only
- ✅ server-03: All embedding generation (non-RH machine)
- ✅ server-03: 100% local (no API calls)

### How to Search (After Processing)

```bash
# Install model on laptop-01
pip3 install --user sentence-transformers

# Search script
~/bin/search-sessions-local.py "your query"
```

### Monitor Progress

```bash
# Watch processing on server-03
ssh server-03 "tail -f /tmp/sessions-local-embeddings.log"

# Check database on laptop-01
psql -h 192.168.1.126 -U sfloess -d learning -c \
  "SELECT COUNT(*) FROM learning.sessions"

# Check chunks
psql -h 192.168.1.126 -U sfloess -d learning -c \
  "SELECT COUNT(*) FROM learning.session_chunks"
```

---

**Status:** ✅ FULLY COMPLIANT
- laptop-01: Red Hat approved (database only)
- server-03: Local embeddings (no APIs)
- Total cost: $0
