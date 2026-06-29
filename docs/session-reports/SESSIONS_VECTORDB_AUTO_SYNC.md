# Automatic Session Vector DB Sync ✅

## Status: ACTIVE

Your Claude Code sessions are now **automatically** synced to PostgreSQL + pgvector every hour!

## What's Syncing

- **Source:** `~/.claude/projects/-home-sfloess/*.jsonl`
- **Destination:** PostgreSQL `learning.sessions` table (192.168.1.126)
- **Frequency:** Every hour
- **Method:** Systemd timer (`sessions-vectordb-sync.timer`)

## How It Works

```
Every Hour:
1. Timer triggers sync script
2. Script processes NEW sessions only (skips existing)
3. Generates 768-dim embeddings (title, summary, content)
4. Inserts into PostgreSQL with vector indexes
5. Logs to ~/.claude/sessions-vectordb-sync.log
```

## Manual Commands

```bash
# Force sync now
~/bin/sync-sessions-to-vectordb.sh

# Check sync status
systemctl --user status sessions-vectordb-sync.timer

# View sync logs
tail -f ~/.claude/sessions-vectordb-sync.log

# Check how many sessions synced
psql -h 192.168.1.126 -U sfloess -d learning -c \
  "SELECT COUNT(*) FROM learning.sessions"

# Restart timer (after config changes)
systemctl --user restart sessions-vectordb-sync.timer
```

## Search Sessions

```bash
# Semantic search
~/bin/search-sessions.py "your search query"

# Search in titles
~/bin/search-sessions.py "setup postgres" 10 title

# Search in content
~/bin/search-sessions.py "backup disaster recovery" 20 content
```

## Database Schema

**Table:** `learning.sessions`

| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT | UUID |
| title | TEXT | First user message |
| summary | TEXT | First exchange |
| full_content | TEXT | All messages (50k limit) |
| created_at | TIMESTAMP | Session start |
| message_count | INTEGER | Total messages |
| metadata | JSONB | Stats |
| title_embedding | vector(768) | Title embedding |
| summary_embedding | vector(768) | Summary embedding |
| content_embedding | vector(768) | Content embedding |

## Performance

- **Sync time:** ~2-5 seconds for new sessions
- **Search time:** ~0.4ms per query (HNSW index)
- **Storage:** ~1KB per session + vectors
- **Cost:** $0 (FREE Cerebras embeddings)

## Disable Auto-Sync

```bash
systemctl --user stop sessions-vectordb-sync.timer
systemctl --user disable sessions-vectordb-sync.timer
```

## Re-enable Auto-Sync

```bash
systemctl --user enable sessions-vectordb-sync.timer
systemctl --user start sessions-vectordb-sync.timer
```

---

**Next:** Your sessions are now automatically indexed! Just use `search-sessions.py` anytime.
