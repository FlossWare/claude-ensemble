---
name: autostorage-expanded
description: "Autostorage now ingests conversations, workflows, and arbiter decisions - not just memory files"
metadata:
  type: feedback
  date: 2026-07-10
---

# Autostorage Expanded to All Data Types

**Implemented:** 2026-07-10

## What Autostorage Now Monitors

**Previously (before 2026-07-10):**
- ✅ Memory files (`memory/*.md`) only

**Now (after 2026-07-10):**
- ✅ Memory files (`memory/*.md`)
- ✅ Conversations (`.jsonl` session files)
- ✅ Workflow results (workflow execution JSON files)

## How It Works

**Autostorage service runs 24/7:**
- Systemd service: `auto-storage.service`
- Checks every 10 seconds
- Uses SHA256 hashing to detect changes
- Stores via REST API (not direct PostgreSQL)

**For each data type:**

1. **Memory files** → `POST http://aio-01:5000/learning/memory`
   - Semantic chunking (if >1500 chars)
   - Embeddings (5-provider cascade)
   - Vector storage (pgvector)
   - Graph relationships (OrientDB)

2. **Conversations** → `POST http://aio-01:5000/learning/session`
   - Full session JSONL ingested
   - Each message stored with embeddings
   - Searchable via semantic similarity

3. **Workflow results** → `POST http://aio-01:5000/workflows/execution`
   - Execution metadata
   - Worker results
   - Arbiter decisions
   - Phase tracking

## Why This Matters

**Before:**
- Had to manually query memory files
- Conversations not searchable
- Workflow results scattered
- No semantic search across data types

**After:**
- All data in PostgreSQL (single source of truth)
- Semantic search across everything
- Can query via REST API
- Embeddings enable similarity search

## Monitored Paths

```python
# Memory files
~/Development/.../memory/*.md

# Conversations
~/.claude/projects/[project]/*.jsonl

# Workflows
/tmp/claude-1000/[project]/tasks/*/workflow*.json
```

## REST API Endpoints Used

- `/learning/memory` - Memory chunks with embeddings
- `/learning/session` - Conversation messages
- `/workflows/execution` - Workflow results

## How to Verify It's Working

```bash
# Check service status
systemctl --user status auto-storage.service

# Check logs
tail -f ~/.claude/learning/auto-storage.log

# Check PostgreSQL ingestion
psql -h aio-01 -p 5433 -U postgres -d learning -c "
  SELECT 
    'memory_chunks' as table, COUNT(*) FROM knowledge.memory_chunks
  UNION ALL
  SELECT 'sessions', COUNT(*) FROM learning.sessions
  UNION ALL  
  SELECT 'workflow_executions', COUNT(*) FROM workflow.executions;
"
```

## What Gets Auto-Ingested

**Memory files:**
- Feedback memories (user preferences)
- Reference memories (how things work)
- Project memories (current work)
- Session summaries

**Conversations:**
- Every Claude Code session
- All messages (user + assistant)
- Tool calls and results
- Timestamps and metadata

**Workflows:**
- Execution metadata
- Worker results (each model's output)
- Arbiter decisions (consensus synthesis)
- Phase-level tracking
- Learnings extracted

## Benefits

1. **Semantic search** - "Find conversations about fleet optimization"
2. **Similarity** - "Show me similar workflow executions"
3. **Analytics** - "Which memories are referenced most?"
4. **REST API access** - Query programmatically, not file reads
5. **Unified storage** - One place for all knowledge

## Related

- [[feedback_autostorage_deployment_pattern]] - How to deploy autostorage fixes
- [[feedback_always_unified_rest_api]] - Always use REST API for access
- [[reference_home_network_AUTHORITATIVE]] - PostgreSQL on aio-01:5433

---

**Summary:** Autostorage is now comprehensive - it ingests memory files, conversations, and workflows automatically every 10 seconds via REST API to PostgreSQL.
